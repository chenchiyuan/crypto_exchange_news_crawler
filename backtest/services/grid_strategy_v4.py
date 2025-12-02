"""
箱体网格策略 V4.0 - 双向交易
Grid Strategy V4 - Bidirectional Trading

核心特性：
- 双向交易：同时做多和做空
- 简单止盈：到达目标位一次性全平（多单到R1，空单到S1）
- 突破止损：关键位突破后+3%触发止损
- 固定仓位：支撑位1/2 (20%/30%)，压力位1/2 (20%/30%)
"""
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from decimal import Decimal
from typing import Optional

from django.utils import timezone

from backtest.models import BacktestResult, KLine, BacktestSnapshot
from backtest.services.dynamic_grid_calculator import DynamicGridCalculator
from backtest.services.bidirectional_position_manager import BidirectionalPositionManager
from backtest.services.simple_take_profit_executor import SimpleTakeProfitExecutor
from backtest.services.breakout_stop_loss_manager import BreakoutStopLossManager
from backtest.services.metrics_calculator import MetricsCalculator

logger = logging.getLogger(__name__)


class GridStrategyV4:
    """箱体网格策略 V4.0 - 双向交易"""

    def __init__(
        self,
        symbol: str,
        interval: str,
        start_date: datetime,
        end_date: datetime,
        initial_cash: float = 10000.0,
        stop_loss_pct: float = 0.03,  # 3%
        commission: float = 0.001,  # 0.1%
        price_deviation_pct: float = 0.10  # ±10%
    ):
        """
        初始化Grid V4策略

        Args:
            symbol: 交易对（如ETHUSDT）
            interval: 时间周期（如4h）
            start_date: 开始日期
            end_date: 结束日期
            initial_cash: 初始资金
            stop_loss_pct: 止损百分比（默认3%）
            commission: 手续费率（默认0.1%）
            price_deviation_pct: 价格偏离范围（默认±10%）
        """
        self.symbol = symbol
        self.interval = interval
        self.start_date = start_date
        self.end_date = end_date
        self.initial_cash = initial_cash
        self.stop_loss_pct = stop_loss_pct
        self.commission = commission
        self.price_deviation_pct = price_deviation_pct

        # 追踪已开仓的层级（避免重复开仓）
        self.opened_levels = {
            'support_1': set(),
            'support_2': set(),
            'resistance_1': set(),
            'resistance_2': set()
        }

        logger.info(
            f"GridStrategyV4初始化: {symbol} {interval}, "
            f"初始资金={initial_cash:.2f}, "
            f"止损={stop_loss_pct*100:.1f}%, "
            f"价格偏离范围=±{price_deviation_pct*100:.1f}%"
        )

    def run(self) -> BacktestResult:
        """运行回测"""
        logger.info("=" * 60)
        logger.info(f"开始回测: {self.symbol} {self.interval} (V4 - 双向交易)")
        logger.info("=" * 60)

        # 1. 加载K线数据
        self.klines = self._load_klines()

        # 2. 创建回测结果记录
        self.backtest_result = BacktestResult.objects.create(
            name=f"Grid V4 - {self.symbol} {self.interval}",
            symbol=self.symbol,
            interval=self.interval,
            start_date=self.klines.index[0],
            end_date=self.klines.index[-1],
            strategy_params={
                'strategy_type': 'grid_v4',
                'stop_loss_pct': self.stop_loss_pct,
                'commission': self.commission,
                'price_deviation_pct': self.price_deviation_pct
            },
            initial_cash=Decimal(str(self.initial_cash)),
            final_value=Decimal(str(self.initial_cash)),
            total_return=Decimal('0'),
            max_drawdown=Decimal('0'),
            win_rate=Decimal('0')
        )

        # 3. 初始化组件
        self.grid_calculator = DynamicGridCalculator(
            symbol=self.symbol,
            price_deviation_pct=self.price_deviation_pct
        )

        self.position_manager = BidirectionalPositionManager(
            backtest_result_id=self.backtest_result.id,
            initial_cash=self.initial_cash,
            fee_rate=self.commission
        )

        self.take_profit_executor = SimpleTakeProfitExecutor(
            position_manager=self.position_manager,
            fee_rate=self.commission
        )

        self.stop_loss_manager = BreakoutStopLossManager(
            position_manager=self.position_manager,
            stop_loss_pct=self.stop_loss_pct,
            fee_rate=self.commission
        )

        # 4. 主循环
        total_bars = len(self.klines)
        self.current_bar_index = 0  # 追踪当前K线索引（用于冷却期计算）

        for idx, (timestamp, row) in enumerate(self.klines.iterrows()):
            self.current_bar_index = idx  # 更新当前索引
            current_time = timestamp
            current_price = row['Close']

            # 进度日志（每10%）
            if idx % max(1, total_bars // 10) == 0:
                progress = idx / total_bars * 100
                logger.info(
                    f"进度: {progress:.1f}% ({idx}/{total_bars}), "
                    f"价格={current_price:.2f}, "
                    f"现金={self.position_manager.current_cash:.2f}"
                )

            # 4.1 计算动态网格
            grid_levels_obj = self.grid_calculator.calculate_grid_levels(current_time)

            if not grid_levels_obj:
                continue

            # 转换GridLevels对象为dict格式（兼容性）
            grid_levels = self._convert_grid_levels_to_dict(grid_levels_obj)

            # 4.2 检查止损（优先级最高）
            self.stop_loss_manager.check_and_execute(current_price, grid_levels)

            # 4.3 检查止盈
            self.take_profit_executor.check_and_execute(current_price, grid_levels)

            # 4.4 检查开仓信号
            self._check_entry_signals(current_price, grid_levels, current_time)

            # 4.5 记录快照
            self._record_snapshot(idx, timestamp, current_price, grid_levels)

        # 5. 计算最终结果
        self._finalize_result()

        logger.info("=" * 60)
        logger.info(f"回测完成: Grid V4 - {self.symbol} {self.interval}")
        logger.info("=" * 60)

        return self.backtest_result

    def _convert_grid_levels_to_dict(self, grid_levels_obj) -> dict:
        """
        将GridLevels对象转换为dict格式

        Args:
            grid_levels_obj: GridLevels dataclass对象

        Returns:
            dict格式的网格层级
        """
        result = {}

        # 支撑位1
        if grid_levels_obj.support_1:
            result['support_1'] = {
                'price': grid_levels_obj.support_1.price,
                'zone_low': grid_levels_obj.support_1.zone_low,
                'zone_high': grid_levels_obj.support_1.zone_high
            }
        else:
            result['support_1'] = {'price': 0, 'zone_low': 0, 'zone_high': 0}

        # 支撑位2
        if grid_levels_obj.support_2:
            result['support_2'] = {
                'price': grid_levels_obj.support_2.price,
                'zone_low': grid_levels_obj.support_2.zone_low,
                'zone_high': grid_levels_obj.support_2.zone_high
            }
        else:
            result['support_2'] = {'price': 0, 'zone_low': 0, 'zone_high': 0}

        # 压力位1
        if grid_levels_obj.resistance_1:
            result['resistance_1'] = {
                'price': grid_levels_obj.resistance_1.price,
                'zone_low': grid_levels_obj.resistance_1.zone_low,
                'zone_high': grid_levels_obj.resistance_1.zone_high
            }
        else:
            result['resistance_1'] = {'price': 0, 'zone_low': 0, 'zone_high': 0}

        # 压力位2
        if grid_levels_obj.resistance_2:
            result['resistance_2'] = {
                'price': grid_levels_obj.resistance_2.price,
                'zone_low': grid_levels_obj.resistance_2.zone_low,
                'zone_high': grid_levels_obj.resistance_2.zone_high
            }
        else:
            result['resistance_2'] = {'price': 0, 'zone_low': 0, 'zone_high': 0}

        return result

    def _load_klines(self) -> pd.DataFrame:
        """从数据库加载K线数据"""
        queryset = KLine.objects.filter(
            symbol=self.symbol,
            interval=self.interval,
            open_time__gte=self.start_date,
            open_time__lte=self.end_date
        ).order_by('open_time')

        if not queryset.exists():
            raise ValueError(f"没有找到数据: {self.symbol} {self.interval}")

        data = list(queryset.values(
            'open_time', 'open_price', 'high_price',
            'low_price', 'close_price', 'volume'
        ))

        df = pd.DataFrame(data)
        df = df.rename(columns={
            'open_price': 'Open',
            'high_price': 'High',
            'low_price': 'Low',
            'close_price': 'Close',
            'volume': 'Volume'
        })

        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = df[col].astype(float)

        df['open_time'] = pd.to_datetime(df['open_time'])
        df = df.set_index('open_time')

        logger.info(
            f"K线数据加载成功: {len(df)}根, "
            f"{df.index[0]} ~ {df.index[-1]}"
        )

        return df

    def _check_entry_signals(self, current_price: float, grid_levels: dict, timestamp: datetime):
        """
        检查开仓信号

        开仓逻辑：
        - 价格到达支撑位1 → 开多单（20%）
        - 价格到达支撑位2 → 开多单（30%）
        - 价格到达压力位1 → 开空单（20%）
        - 价格到达压力位2 → 开空单（30%）

        注意：使用价格范围（±2%）判断是否已在该层级持仓，避免重复开仓
        """
        s1_price = grid_levels['support_1']['price']
        s2_price = grid_levels['support_2']['price']
        r1_price = grid_levels['resistance_1']['price']
        r2_price = grid_levels['resistance_2']['price']

        # 检查支撑位1（多单）- 当前价格 <= S1
        if s1_price > 0 and current_price <= s1_price:
            # 检查是否已有S1附近（±5%）的多单持仓或在冷却期
            if not self._has_open_position_near('long', 'support_1', s1_price, current_time=timestamp):
                self._open_long_at_support_1(current_price, grid_levels, timestamp)

        # 检查支撑位2（多单）- 当前价格 <= S2
        if s2_price > 0 and current_price <= s2_price:
            if not self._has_open_position_near('long', 'support_2', s2_price, current_time=timestamp):
                self._open_long_at_support_2(current_price, grid_levels, timestamp)

        # 检查压力位1（空单）- 当前价格 >= R1
        if r1_price > 0 and current_price >= r1_price:
            if not self._has_open_position_near('short', 'resistance_1', r1_price, current_time=timestamp):
                self._open_short_at_resistance_1(current_price, grid_levels, timestamp)

        # 检查压力位2（空单）- 当前价格 >= R2
        if r2_price > 0 and current_price >= r2_price:
            if not self._has_open_position_near('short', 'resistance_2', r2_price, current_time=timestamp):
                self._open_short_at_resistance_2(current_price, grid_levels, timestamp)

    def _has_open_position_near(self, direction: str, level: str, target_price: float, tolerance: float = 0.05, cooldown_bars: int = 5, current_time=None) -> bool:
        """
        检查是否已有指定方向和层级的持仓，且开仓价格在目标价格附近

        增加冷却期机制：除了检查持仓中的仓位，还检查最近N根K线内是否有已平仓的仓位在同一价格范围内

        Args:
            direction: 'long' 或 'short'
            level: 层级（support_1, support_2, resistance_1, resistance_2）
            target_price: 目标价格
            tolerance: 容忍度（默认±5%）
            cooldown_bars: 冷却期K线数量（默认5根，即4小时*5=20小时）
            current_time: 当前K线时间戳（如未指定则使用current_bar_index获取）

        Returns:
            True表示已有持仓或在冷却期内，False表示可以开仓
        """
        from backtest.models import GridPosition
        from datetime import timedelta

        # 计算价格范围
        price_low = target_price * (1 - tolerance)
        price_high = target_price * (1 + tolerance)

        # 1. 检查是否有持仓中的仓位
        has_open = GridPosition.objects.filter(
            backtest_result_id=self.backtest_result.id,
            direction=direction,
            buy_level=level,
            status__in=['open', 'partial'],
            buy_price__gte=price_low,
            buy_price__lte=price_high
        ).exists()

        if has_open:
            return True

        # 2. 检查冷却期：最近N根K线内是否有已平仓的仓位
        # 获取当前K线时间
        if current_time is None:
            current_time = self.klines.index[min(self.current_bar_index, len(self.klines) - 1)]

        # 计算冷却期时间范围（N根K线 = N * 4小时）
        cooldown_duration = timedelta(hours=4 * cooldown_bars)
        cooldown_start = current_time - cooldown_duration

        # 查询冷却期内的已平仓仓位
        cooldown_positions = GridPosition.objects.filter(
            backtest_result_id=self.backtest_result.id,
            direction=direction,
            buy_level=level,
            status='closed',
            buy_time__gte=cooldown_start,
            buy_time__lte=current_time,
            buy_price__gte=price_low,
            buy_price__lte=price_high
        )

        has_recent_closed = cooldown_positions.exists()

        return has_recent_closed

    def _open_long_at_support_1(self, price: float, grid_levels: dict, timestamp: datetime):
        """支撑位1开多单（20%）"""
        size_pct = 0.20
        amount = (self.initial_cash * size_pct) / price

        position = self.position_manager.open_long_position(
            level='support_1',
            price=price,
            amount=amount,
            grid_levels=grid_levels,
            timestamp=timestamp
        )

        if position:
            logger.info(f"🟢 S1开多单: position#{position.id}, 价格={price:.2f}, 数量={amount:.6f}")

    def _open_long_at_support_2(self, price: float, grid_levels: dict, timestamp: datetime):
        """支撑位2开多单（30%）"""
        size_pct = 0.30
        amount = (self.initial_cash * size_pct) / price

        position = self.position_manager.open_long_position(
            level='support_2',
            price=price,
            amount=amount,
            grid_levels=grid_levels,
            timestamp=timestamp
        )

        if position:
            logger.info(f"🟢 S2开多单: position#{position.id}, 价格={price:.2f}, 数量={amount:.6f}")

    def _open_short_at_resistance_1(self, price: float, grid_levels: dict, timestamp: datetime):
        """压力位1开空单（20%）"""
        size_pct = 0.20
        amount = (self.initial_cash * size_pct) / price

        position = self.position_manager.open_short_position(
            level='resistance_1',
            price=price,
            amount=amount,
            grid_levels=grid_levels,
            timestamp=timestamp
        )

        if position:
            logger.info(f"🔴 R1开空单: position#{position.id}, 价格={price:.2f}, 数量={amount:.6f}")

    def _open_short_at_resistance_2(self, price: float, grid_levels: dict, timestamp: datetime):
        """压力位2开空单（30%）"""
        size_pct = 0.30
        amount = (self.initial_cash * size_pct) / price

        position = self.position_manager.open_short_position(
            level='resistance_2',
            price=price,
            amount=amount,
            grid_levels=grid_levels,
            timestamp=timestamp
        )

        if position:
            logger.info(f"🔴 R2开空单: position#{position.id}, 价格={price:.2f}, 数量={amount:.6f}")

    def _record_snapshot(self, kline_index: int, timestamp: datetime, current_price: float, grid_levels: dict):
        """记录快照"""
        # 计算账户价值
        cash_balance = self.position_manager.current_cash
        total_value = self.position_manager.get_account_value(current_price)

        # 收集本K线的所有事件
        events = []
        events.extend(self.position_manager.get_events())  # 开仓事件
        events.extend(self.take_profit_executor.get_events())  # 止盈事件
        events.extend(self.stop_loss_manager.get_events())  # 止损事件

        # 收集持仓信息
        positions_data = []
        for pos in self.position_manager.get_open_long_positions():
            remaining = float(pos.buy_amount - pos.total_sold_amount)
            total_sold = float(pos.total_sold_amount)

            # 计算已卖出比例
            r1_sold_pct = 0.0
            r2_sold_pct = 0.0
            if total_sold > 0:
                # Grid V4没有渐进式卖出，全部平仓时R1为100%
                if pos.status == 'closed':
                    r1_sold_pct = 100.0

            positions_data.append({
                'id': pos.id,
                'direction': 'long',
                'buy_level': pos.buy_level,
                'buy_price': float(pos.buy_price),  # 保留原字段兼容性
                'avg_buy_price': float(pos.buy_price),  # 前端期望的字段
                'remaining': remaining,
                'current_value': remaining * current_price,
                'pnl': float(pos.pnl),
                'status': pos.status,
                'buy_cost': float(pos.buy_cost),
                'stop_loss_price': float(pos.stop_loss_price),
                'r1_target': float(pos.sell_target_r1_price),
                'r1_sold_pct': r1_sold_pct,
                'r2_target': float(pos.sell_target_r2_price),
                'r2_sold_pct': r2_sold_pct
            })

        for pos in self.position_manager.get_open_short_positions():
            remaining = float(pos.buy_amount - pos.total_sold_amount)
            total_sold = float(pos.total_sold_amount)

            # 计算已卖出比例
            r1_sold_pct = 0.0
            r2_sold_pct = 0.0
            if total_sold > 0:
                # Grid V4没有渐进式卖出，全部平仓时R1为100%
                if pos.status == 'closed':
                    r1_sold_pct = 100.0

            positions_data.append({
                'id': pos.id,
                'direction': 'short',
                'buy_level': pos.buy_level,
                'buy_price': float(pos.buy_price),  # 保留原字段兼容性
                'avg_buy_price': float(pos.buy_price),  # 前端期望的字段
                'remaining': remaining,
                'current_value': remaining * (2 * float(pos.buy_price) - current_price),
                'pnl': float(pos.pnl),
                'status': pos.status,
                'buy_cost': float(pos.buy_cost),
                'stop_loss_price': float(pos.stop_loss_price),
                'r1_target': float(pos.sell_target_r1_price),  # 空单的S1目标
                'r1_sold_pct': r1_sold_pct,
                'r2_target': float(pos.sell_target_r2_price),  # 空单的S2目标
                'r2_sold_pct': r2_sold_pct
            })

        # 网格数据
        grid_data = {
            'support_1': {'price': grid_levels['support_1']['price']},
            'support_2': {'price': grid_levels['support_2']['price']},
            'resistance_1': {'price': grid_levels['resistance_1']['price']},
            'resistance_2': {'price': grid_levels['resistance_2']['price']}
        }

        # 创建快照
        BacktestSnapshot.objects.create(
            backtest_result_id=self.backtest_result.id,
            kline_index=kline_index,
            timestamp=timestamp,
            current_price=Decimal(str(current_price)),
            cash_balance=Decimal(str(cash_balance)),
            total_value=Decimal(str(total_value)),
            grid_levels=grid_data,
            positions=positions_data,
            events=events
        )

        # 清空事件列表
        self.position_manager.clear_events()
        self.take_profit_executor.clear_events()
        self.stop_loss_manager.clear_events()

    def _finalize_result(self):
        """计算最终收益指标"""
        final_price = self.klines.iloc[-1]['Close']

        # 计算最终价值
        final_value = self.position_manager.get_account_value(final_price)
        total_return = (final_value - self.initial_cash) / self.initial_cash

        # 统计交易次数
        from backtest.models import GridPosition
        all_positions = GridPosition.objects.filter(
            backtest_result_id=self.backtest_result.id
        )
        total_trades = all_positions.count()
        closed_positions = all_positions.filter(status='closed')
        profitable_trades = closed_positions.filter(pnl__gt=0).count()
        losing_trades = closed_positions.filter(pnl__lt=0).count()
        win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0

        # 计算增强指标
        days = (self.klines.index[-1] - self.klines.index[0]).days

        # 从快照中提取权益曲线和日收益
        snapshots = BacktestSnapshot.objects.filter(
            backtest_result_id=self.backtest_result.id
        ).order_by('kline_index')

        equity_values = []
        timestamps = []
        for snapshot in snapshots:
            equity_values.append(float(snapshot.total_value))
            timestamps.append(snapshot.timestamp)

        equity_curve_series = pd.Series(equity_values, index=pd.DatetimeIndex(timestamps))
        daily_returns_series = equity_curve_series.pct_change().fillna(0)

        # 提取交易盈亏列表
        trades_pnl = [float(pos.pnl) for pos in closed_positions if pos.pnl is not None]

        # 计算最大回撤
        equity_array = np.array(equity_values)
        running_max = np.maximum.accumulate(equity_array)
        drawdown = (equity_array - running_max) / running_max
        max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0

        # 使用MetricsCalculator计算所有增强指标
        metrics_calc = MetricsCalculator()
        enhanced_metrics = metrics_calc.calculate_all_metrics(
            total_return=total_return,
            days=days,
            daily_returns=daily_returns_series,
            equity_curve=equity_curve_series,
            trades_pnl=trades_pnl,
            max_drawdown=max_drawdown
        )

        # 更新基础指标
        self.backtest_result.final_value = Decimal(str(final_value))
        self.backtest_result.total_return = Decimal(str(total_return))
        self.backtest_result.max_drawdown = Decimal(str(max_drawdown))
        self.backtest_result.total_trades = total_trades
        self.backtest_result.profitable_trades = profitable_trades
        self.backtest_result.losing_trades = losing_trades
        self.backtest_result.win_rate = Decimal(str(win_rate))

        # 更新增强指标
        if enhanced_metrics['annual_return'] is not None:
            self.backtest_result.annual_return = Decimal(str(enhanced_metrics['annual_return']))
        if enhanced_metrics['annual_volatility'] is not None:
            self.backtest_result.annual_volatility = Decimal(str(enhanced_metrics['annual_volatility']))
        if enhanced_metrics['sortino_ratio'] is not None and not np.isinf(enhanced_metrics['sortino_ratio']):
            self.backtest_result.sortino_ratio = Decimal(str(enhanced_metrics['sortino_ratio']))
        if enhanced_metrics['calmar_ratio'] is not None and not np.isinf(enhanced_metrics['calmar_ratio']):
            self.backtest_result.calmar_ratio = Decimal(str(enhanced_metrics['calmar_ratio']))
        if enhanced_metrics['max_drawdown_duration'] is not None:
            self.backtest_result.max_drawdown_duration = enhanced_metrics['max_drawdown_duration']
        if enhanced_metrics['profit_factor'] is not None and not np.isinf(enhanced_metrics['profit_factor']):
            self.backtest_result.profit_factor = Decimal(str(enhanced_metrics['profit_factor']))
        if enhanced_metrics['avg_win'] is not None:
            self.backtest_result.avg_win = Decimal(str(enhanced_metrics['avg_win']))
        if enhanced_metrics['avg_loss'] is not None:
            self.backtest_result.avg_loss = Decimal(str(enhanced_metrics['avg_loss']))

        self.backtest_result.save()

        # 构建日志信息
        log_msg = (
            f"最终结果: "
            f"初始资金={self.initial_cash:.2f}, "
            f"最终价值={final_value:.2f}, "
            f"收益率={total_return:.2%}, "
        )
        if enhanced_metrics['annual_return'] is not None:
            log_msg += f"年化收益={enhanced_metrics['annual_return']:.2%}, "
        log_msg += (
            f"最大回撤={max_drawdown:.2%}, "
            f"交易次数={total_trades}, "
            f"胜率={win_rate:.1f}%"
        )
        logger.info(log_msg)
