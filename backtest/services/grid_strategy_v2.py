"""
箱体网格策略 V2.0
动态网格 + 渐进式买卖 + 分级止盈 + 双向止损
"""
import logging
import pandas as pd
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any

from django.utils import timezone

from backtest.models import BacktestResult, KLine, BacktestSnapshot
from backtest.services.dynamic_grid_calculator import DynamicGridCalculator
from backtest.services.position_manager import PositionManager
from backtest.services.executors import create_executor

logger = logging.getLogger(__name__)


class GridStrategyV2:
    """箱体网格策略 V2.0"""

    def __init__(
        self,
        symbol: str,
        interval: str,
        start_date: datetime,
        end_date: datetime,
        initial_cash: float = 10000.0,
        commission: float = 0.001,
        support_1_max_pct: float = 0.20,
        support_2_max_pct: float = 0.30,
        stop_loss_pct: float = 0.03,
        decay_k: float = 3.0,
        price_deviation_pct: float = 0.10,
        executor_type: str = 'progressive'
    ):
        """
        初始化GridStrategyV2

        Args:
            symbol: 交易对
            interval: K线周期
            start_date: 开始日期
            end_date: 结束日期
            initial_cash: 初始资金
            commission: 手续费率
            support_1_max_pct: 支撑位1最大投入比例
            support_2_max_pct: 支撑位2最大投入比例
            stop_loss_pct: 止损阈值
            decay_k: 权重衰减系数（仅progressive模式使用）
            price_deviation_pct: 价格偏离百分比（默认10%，即±10%范围内寻找支撑压力）
            executor_type: 执行器类型（'simple'简单模式 / 'progressive'渐进模式，默认progressive）
        """
        self.symbol = symbol
        self.interval = interval
        self.start_date = start_date
        self.end_date = end_date
        self.initial_cash = initial_cash
        self.commission = commission
        self.support_1_max_pct = support_1_max_pct
        self.support_2_max_pct = support_2_max_pct
        self.stop_loss_pct = stop_loss_pct
        self.decay_k = decay_k
        self.price_deviation_pct = price_deviation_pct
        self.executor_type = executor_type

        # 组件（延迟初始化）
        self.grid_calculator = None
        self.position_manager = None
        self.executor = None
        self.backtest_result = None

        # 数据
        self.klines = None

        # 当前K线的事件记录
        self.current_events = []

        logger.info(
            f"GridStrategyV2初始化: {symbol} {interval}, "
            f"执行器={executor_type}, "
            f"初始资金={initial_cash:.2f}, "
            f"支撑1={support_1_max_pct*100}%, "
            f"支撑2={support_2_max_pct*100}%, "
            f"止损={stop_loss_pct*100}%, "
            f"价格偏离范围=±{price_deviation_pct*100}%"
        )

    def _load_klines(self) -> pd.DataFrame:
        """从数据库加载K线数据"""
        queryset = KLine.objects.filter(
            symbol=self.symbol,
            interval=self.interval,
            open_time__gte=self.start_date,
            open_time__lte=self.end_date
        ).order_by('open_time')

        if not queryset.exists():
            raise ValueError(
                f"没有找到K线数据: {self.symbol} {self.interval} "
                f"{self.start_date} ~ {self.end_date}"
            )

        # 转换为DataFrame
        data = list(queryset.values(
            'open_time', 'open_price', 'high_price',
            'low_price', 'close_price', 'volume'
        ))

        df = pd.DataFrame(data)

        # 重命名列
        df = df.rename(columns={
            'open_price': 'Open',
            'high_price': 'High',
            'low_price': 'Low',
            'close_price': 'Close',
            'volume': 'Volume'
        })

        # 转换为float
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = df[col].astype(float)

        # 设置索引
        df['open_time'] = pd.to_datetime(df['open_time'])
        df = df.set_index('open_time')

        logger.info(
            f"K线数据加载成功: {len(df)}根, "
            f"{df.index[0]} ~ {df.index[-1]}"
        )

        return df

    def run(self) -> BacktestResult:
        """
        运行回测

        主循环逻辑（每根K线）:
        1. 计算动态网格
        2. 检查多头止损
        3. 检查空头止损（预留）
        4. 检查卖出信号（压力位区间）
        5. 检查买入信号（支撑位区间）
        6. 记录状态
        """
        logger.info("=" * 60)
        logger.info(f"开始回测: {self.symbol} {self.interval}")
        logger.info("=" * 60)

        # 1. 加载K线数据
        self.klines = self._load_klines()

        # 2. 创建回测结果记录
        self.backtest_result = BacktestResult.objects.create(
            name=f"Grid V2 - {self.symbol} {self.interval}",
            symbol=self.symbol,
            interval=self.interval,
            start_date=self.klines.index[0],
            end_date=self.klines.index[-1],
            strategy_params={
                'strategy_type': 'grid_v2',
                'support_1_max_pct': self.support_1_max_pct,
                'support_2_max_pct': self.support_2_max_pct,
                'stop_loss_pct': self.stop_loss_pct,
                'decay_k': self.decay_k,
                'commission': self.commission,
                'price_deviation_pct': self.price_deviation_pct
            },
            initial_cash=Decimal(str(self.initial_cash)),
            final_value=Decimal(str(self.initial_cash)),  # 临时值
            total_return=Decimal('0'),  # 临时值
            max_drawdown=Decimal('0'),  # 临时值
            win_rate=Decimal('0')  # 临时值
        )

        # 3. 初始化组件
        self.grid_calculator = DynamicGridCalculator(
            symbol=self.symbol,
            price_deviation_pct=self.price_deviation_pct
        )

        self.position_manager = PositionManager(
            backtest_result_id=self.backtest_result.id,
            initial_cash=self.initial_cash,
            support_1_max_pct=self.support_1_max_pct,
            support_2_max_pct=self.support_2_max_pct
        )

        # 使用工厂函数创建执行器
        executor_params = {
            'position_manager': self.position_manager,
            'fee_rate': self.commission,
            'stop_loss_pct': self.stop_loss_pct
        }
        # progressive模式需要额外参数
        if self.executor_type == 'progressive':
            executor_params['decay_k'] = self.decay_k

        self.executor = create_executor(
            executor_type=self.executor_type,
            **executor_params
        )

        # 4. 主循环
        total_bars = len(self.klines)
        for idx, (timestamp, row) in enumerate(self.klines.iterrows()):
            current_time = timestamp
            current_price = row['Close']

            # 进度日志（每10%）
            if idx % (total_bars // 10) == 0:
                progress = idx / total_bars * 100
                logger.info(
                    f"进度: {progress:.1f}% ({idx}/{total_bars}), "
                    f"价格={current_price:.2f}, "
                    f"现金={self.position_manager.current_cash:.2f}"
                )

            # 4.1 动态计算网格
            grid_levels = self.grid_calculator.calculate_grid_levels(current_time)

            if grid_levels is None:
                logger.debug(f"网格计算失败，跳过: {current_time}")
                continue

            # 4.2 检查止损
            self._check_stop_loss(current_price, grid_levels, current_time)

            # 4.3 检查卖出
            self._check_sell_signals(current_price, current_time, grid_levels)

            # 4.4 检查买入
            self._check_buy_signals(current_price, current_time, grid_levels)

            # 4.5 记录快照
            self._record_snapshot(idx, current_time, current_price, grid_levels)

            # 重置当前事件列表
            self.current_events = []

        # 5. 计算最终结果
        self._finalize_result()

        logger.info("=" * 60)
        logger.info(f"回测完成: {self.backtest_result.name}")
        logger.info("=" * 60)

        return self.backtest_result

    def _check_stop_loss(self, current_price: float, grid_levels, current_time: datetime):
        """检查止损（多头+空头）"""
        # 获取所有持仓
        all_positions = self.position_manager.get_all_open_positions()

        if not all_positions:
            return

        # 检查每个仓位的止损
        positions_to_stop = []
        for pos in all_positions:
            stop_price = float(pos.stop_loss_price)
            if current_price < stop_price:
                positions_to_stop.append(pos)
                logger.warning(
                    f"⚠️ 仓位{pos.id}触发止损: "
                    f"买入价={float(pos.buy_price):.2f}, "
                    f"止损价={stop_price:.2f}, "
                    f"当前价={current_price:.2f}"
                )

        # 执行止损
        if positions_to_stop:
            total_revenue = self.executor.execute_stop_loss(
                positions=positions_to_stop,
                current_price=current_price,
                current_time=current_time,
                reason=f"多头止损(跌破止损线)"
            )
            logger.warning(
                f"⚠️ 批量止损完成: 价格={current_price:.2f}, "
                f"平仓{len(positions_to_stop)}个仓位, "
                f"收入={total_revenue:.2f}"
            )

            # 记录止损事件
            self.current_events.append({
                'type': 'stop_loss',
                'position_ids': [pos.id for pos in positions_to_stop],
                'price': current_price,
                'total_revenue': total_revenue,
                'reason': '多头止损(跌破止损线)'
            })

        # 2. 空头止损（预留，暂不实现）
        # resistance_2_zone_high = grid_levels.resistance_2.zone_high
        # short_stop_boundary = resistance_2_zone_high * (1 + self.stop_loss_pct)
        # if current_price > short_stop_boundary:
        #     ...

    def _check_sell_signals(
        self,
        current_price: float,
        current_time: datetime,
        grid_levels
    ):
        """检查卖出信号"""
        # 遍历压力位
        for target_level in ['resistance_1', 'resistance_2']:
            level_info = getattr(grid_levels, target_level)

            # ⭐⭐⭐ 关键：检查压力位是否存在
            if level_info is None:
                logger.debug(f"{target_level} 不存在，跳过卖出检查")
                continue

            # 查找需要在此压力位卖出的仓位
            positions = self.position_manager.get_positions_to_sell(
                current_price=current_price,
                target_level=target_level
            )

            if positions:
                logger.info(
                    f"→ 触发卖出信号: {target_level} @ {current_price:.2f}, "
                    f"匹配仓位={len(positions)}个"
                )

            for pos in positions:
                revenue = self.executor.execute_sell(
                    position=pos,
                    target_level=target_level,
                    current_price=current_price,
                    current_time=current_time
                )

                # 记录卖出事件
                if revenue:
                    self.current_events.append({
                        'type': 'sell',
                        'position_id': pos.id,
                        'target': target_level,
                        'price': current_price,
                        'revenue': revenue
                    })

    def _check_buy_signals(
        self,
        current_price: float,
        current_time: datetime,
        grid_levels
    ):
        """检查买入信号"""
        # 遍历支撑位
        for level_name in ['support_1', 'support_2']:
            level_info = getattr(grid_levels, level_name)

            # ⭐⭐⭐ 关键：检查支撑位是否存在
            if level_info is None:
                logger.debug(f"{level_name} 不存在，跳过买入检查")
                continue

            # ⭐ 不再在此处预检查价格条件，由Executor自己决定买入逻辑
            # Simple模式：只在zone_high买入
            # Progressive模式：在区间内根据权重买入

            # 调用执行器
            buy_amount = self.executor.execute_buy(
                level_name=level_name,
                current_price=current_price,
                current_time=current_time,
                level_info={
                    'zone_low': level_info.zone_low,
                    'zone_high': level_info.zone_high
                },
                grid_levels=grid_levels
            )

            # 记录买入事件
            if buy_amount:
                # 获取刚创建的仓位
                latest_position = self.position_manager.get_all_open_positions()[-1]
                self.current_events.append({
                    'type': 'buy',
                    'position_id': latest_position.id,
                    'level': level_name,
                    'price': current_price,
                    'cost': buy_amount
                })

    def _record_snapshot(
        self,
        kline_index: int,
        timestamp: datetime,
        current_price: float,
        grid_levels
    ):
        """记录当前K线的快照"""
        # 1. 计算总价值
        cash_balance = self.position_manager.get_cash_balance()
        total_value = self.position_manager.get_account_value(current_price)

        # 2. 序列化网格层级（支持None值）
        grid_data = None
        if grid_levels:
            grid_data = {}

            # ⭐⭐⭐ 关键：检查每个层级是否存在再序列化
            if grid_levels.support_2 is not None:
                grid_data['support_2'] = {
                    'price': float(grid_levels.support_2.price),
                    'zone_low': float(grid_levels.support_2.zone_low),
                    'zone_high': float(grid_levels.support_2.zone_high),
                }
            else:
                grid_data['support_2'] = None

            if grid_levels.support_1 is not None:
                grid_data['support_1'] = {
                    'price': float(grid_levels.support_1.price),
                    'zone_low': float(grid_levels.support_1.zone_low),
                    'zone_high': float(grid_levels.support_1.zone_high),
                }
            else:
                grid_data['support_1'] = None

            if grid_levels.resistance_1 is not None:
                grid_data['resistance_1'] = {
                    'price': float(grid_levels.resistance_1.price),
                    'zone_low': float(grid_levels.resistance_1.zone_low),
                    'zone_high': float(grid_levels.resistance_1.zone_high),
                }
            else:
                grid_data['resistance_1'] = None

            if grid_levels.resistance_2 is not None:
                grid_data['resistance_2'] = {
                    'price': float(grid_levels.resistance_2.price),
                    'zone_low': float(grid_levels.resistance_2.zone_low),
                    'zone_high': float(grid_levels.resistance_2.zone_high),
                }
            else:
                grid_data['resistance_2'] = None

        # 3. 序列化持仓列表
        positions = self.position_manager.get_all_open_positions()
        positions_data = []
        for pos in positions:
            buy_amount = float(pos.buy_amount)
            total_sold = float(pos.total_sold_amount)
            remaining = buy_amount - total_sold
            buy_cost = float(pos.buy_cost)

            # 计算持仓总价（剩余数量 * 当前价格）
            current_value = remaining * current_price if remaining > 0 else 0

            # 计算买入均价（总成本 / 总数量）
            avg_buy_price = buy_cost / buy_amount if buy_amount > 0 else float(pos.buy_price)

            positions_data.append({
                'id': pos.id,
                'buy_level': pos.buy_level,
                'buy_price': float(pos.buy_price),  # 首次买入价
                'avg_buy_price': avg_buy_price,  # 平均买入价
                'buy_amount': buy_amount,  # 总买入数量
                'total_sold': total_sold,  # 已卖出数量
                'remaining': remaining,  # 剩余持仓数量
                'buy_cost': buy_cost,  # 总买入成本
                'current_value': current_value,  # 持仓总价（当前价格）
                'stop_loss_price': float(pos.stop_loss_price),
                'r1_target': float(pos.sell_target_r1_price),
                'r1_sold_pct': float(pos.sell_target_r1_sold) / buy_amount * 100 if buy_amount > 0 else 0,
                'r2_target': float(pos.sell_target_r2_price),
                'r2_sold_pct': float(pos.sell_target_r2_sold) / buy_amount * 100 if buy_amount > 0 else 0,
                'status': pos.status,
                'pnl': float(pos.pnl)
            })

        # 4. 创建快照
        BacktestSnapshot.objects.create(
            backtest_result_id=self.backtest_result.id,
            kline_index=kline_index,
            timestamp=timestamp,
            current_price=Decimal(str(current_price)),
            cash_balance=Decimal(str(cash_balance)),
            total_value=Decimal(str(total_value)),
            grid_levels=grid_data,
            positions=positions_data,
            events=self.current_events.copy()
        )

    def _finalize_result(self):
        """计算最终收益指标"""
        final_price = self.klines.iloc[-1]['Close']

        # 计算最终价值
        final_value = self.position_manager.get_account_value(final_price)
        total_return = (final_value - self.initial_cash) / self.initial_cash

        # 统计交易次数
        from backtest.models import GridPosition
        positions = GridPosition.objects.filter(
            backtest_result_id=self.backtest_result.id
        )
        total_trades = positions.count()
        closed_positions = positions.filter(status='closed')
        profitable_trades = closed_positions.filter(pnl__gt=0).count()
        losing_trades = closed_positions.filter(pnl__lt=0).count()
        win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0

        # 更新回测结果
        self.backtest_result.final_value = Decimal(str(final_value))
        self.backtest_result.total_return = Decimal(str(total_return))
        self.backtest_result.total_trades = total_trades
        self.backtest_result.profitable_trades = profitable_trades
        self.backtest_result.losing_trades = losing_trades
        self.backtest_result.win_rate = Decimal(str(win_rate))
        self.backtest_result.save()

        logger.info(
            f"最终结果: "
            f"初始资金={self.initial_cash:.2f}, "
            f"最终价值={final_value:.2f}, "
            f"收益率={total_return:.2%}, "
            f"交易次数={total_trades}, "
            f"胜率={win_rate:.1f}%"
        )
