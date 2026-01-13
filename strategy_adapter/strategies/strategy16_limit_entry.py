"""
策略16：P5限价挂单入场 + 动态挂单止盈（v4.0 动态仓位管理版本）

本模块实现策略16的限价挂单入场机制：
- 入场：每根K线结束时计算挂单价格，下根K线判断成交
- 入场控制：bear_warning周期跳过挂单创建
- 仓位管理：动态复利仓位 = available_cash / (max_positions - current_positions)
- 止盈：动态挂单止盈（根据cycle_phase周期计算挂单价位）
  - 下跌期（bear_warning, bear_strong）: 挂单价 = EMA25
  - 震荡期（consolidation）: 挂单价 = (P95 + EMA25) / 2
  - 上涨期（bull_warning, bull_strong）: 挂单价 = P95
- 止损：无

止盈挂单机制（v3.0 改进）：
- 当前K线结束时：根据cycle_phase计算卖出挂单价，创建卖出挂单
- 下根K线：判断是否成交（high >= 挂单价），成交则以挂单价卖出
- 未成交则取消挂单，下根K线重新计算

核心逻辑（避免后验偏差）：
1. 买入前检查：bear_warning周期跳过
2. 买入：当前K线结束时计算 base_price = min(p5, close, (p5+mid)/2)
3. 买入挂单价格 = base_price × (1 - discount)
4. 仓位金额 = 动态计算（复利效应）
5. 下根K线：如果 low <= 买入挂单价格 → 以挂单价格成交
6. 卖出：当前K线结束时根据周期计算卖出挂单价
7. 下根K线：如果 high >= 卖出挂单价格 → 以挂单价格成交

迭代编号: 036 (策略16-P5限价挂单入场)
修改迭代: 044 (策略16动态仓位管理升级)
创建日期: 2026-01-12
修改日期: 2026-01-13
关联需求: Bug-Fix - 策略16买入条件后验问题
修改需求: 止盈改为挂单模式，避免次日开盘价滑点
升级需求: 添加bear_warning跳过和动态仓位管理
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Any

import pandas as pd
import numpy as np

from strategy_adapter.interfaces import IStrategy
from strategy_adapter.models import PendingOrder, PendingOrderStatus, PendingOrderSide, BacktestResult
from strategy_adapter.core.position_manager import IPositionManager, DynamicPositionManager

logger = logging.getLogger(__name__)


class Strategy16LimitEntry(IStrategy):
    """
    策略16：P5限价挂单入场 + 动态挂单止盈（v4.0 动态仓位管理版本）

    入场控制（v4.0新增）：
    - bear_warning周期跳过挂单创建
    - 使用动态仓位管理：单笔金额 = available_cash / (max_positions - current_positions)

    与策略7的核心差异：
    - 策略7：当前K线low<=P5时，以close买入（后验问题）
    - 策略16：当前K线结束时计算挂单价格，下根K线判断成交（前瞻性）

    止盈机制（v3.0 动态挂单止盈）：
    - 当前K线结束时，根据cycle_phase计算卖出挂单价：
      - 下跌期（bear_warning, bear_strong）: 挂单价 = EMA25
      - 震荡期（consolidation）: 挂单价 = (P95 + EMA25) / 2
      - 上涨期（bull_warning, bull_strong）: 挂单价 = P95
    - 下根K线：判断是否成交（high >= 挂单价），成交则以挂单价卖出
    - 未成交则取消挂单，下根K线重新计算

    止损：无

    工作流程：
    1. 每根K线开始时（处理上根K线创建的挂单）：
       - 检查卖出挂单是否成交（high >= 挂单价）
       - 检查买入挂单是否成交（low <= 挂单价）
    2. 每根K线结束时：
       - 取消未成交的挂单
       - 为持仓创建新的卖出挂单
       - 检查周期：bear_warning跳过
       - 创建新的买入挂单（动态仓位）

    Attributes:
        position_manager: 仓位管理器实例
        discount: 挂单折扣比例（默认0.001即0.1%）
        max_positions: 最大持仓数量

    Example:
        >>> from strategy_adapter.core.position_manager import DynamicPositionManager
        >>> pm = DynamicPositionManager()
        >>> strategy = Strategy16LimitEntry(
        ...     position_manager=pm,
        ...     discount=0.001
        ... )
        >>> result = strategy.run_backtest(klines_df, initial_capital=10000)
    """

    STRATEGY_ID = 'strategy_16'
    STRATEGY_NAME = 'P5限价挂单入场'
    STRATEGY_VERSION = '4.0'

    def __init__(
        self,
        position_manager: IPositionManager = None,
        discount: float = 0.001,
        max_positions: int = 10
    ):
        """
        初始化策略16

        Args:
            position_manager: 仓位管理器实例，默认使用DynamicPositionManager
            discount: 挂单折扣比例，默认0.001（0.1%）
            max_positions: 最大持仓数量，默认10
        """
        # 使用默认的动态仓位管理器
        if position_manager is None:
            position_manager = DynamicPositionManager()

        self.position_manager = position_manager
        self.discount = Decimal(str(discount))
        self.max_positions = max_positions

        # 状态管理
        self._pending_order: Optional[PendingOrder] = None  # 当前买入挂单（每次只挂1笔）
        self._pending_sell_orders: Dict[str, Dict] = {}  # 卖出挂单: order_id -> {price, reason, ...}
        self._holdings: Dict[str, Dict] = {}  # 持仓: order_id -> {buy_price, quantity, ...}
        self._completed_orders: List[Dict] = []  # 已完成交易
        self._available_capital: Decimal = Decimal("0")

        # 统计
        self._skipped_bear_warning: int = 0

        logger.info(
            f"初始化Strategy16LimitEntry: "
            f"position_manager={type(position_manager).__name__}, "
            f"discount={discount}, max_positions={max_positions}, "
            f"止盈=动态挂单止盈, 止损=无"
        )

    def get_strategy_name(self) -> str:
        return self.STRATEGY_NAME

    def get_strategy_version(self) -> str:
        return self.STRATEGY_VERSION

    def get_required_indicators(self) -> List[str]:
        """返回所需的技术指标"""
        return ['ema7', 'ema25', 'ema99', 'p5', 'p95', 'inertia_mid', 'cycle_phase']

    def _calculate_base_price(
        self,
        p5: Decimal,
        close: Decimal,
        inertia_mid: Decimal
    ) -> Decimal:
        """
        计算基准价格

        公式: base_price = min(p5, close, (p5+mid)/2)

        Args:
            p5: P5支撑价格
            close: 收盘价
            inertia_mid: 惯性中值

        Returns:
            Decimal: 基准价格
        """
        mid_p5 = (p5 + inertia_mid) / 2
        return min(p5, close, mid_p5)

    def _calculate_order_price(self, base_price: Decimal) -> Decimal:
        """
        计算挂单价格

        公式: order_price = base_price × (1 - discount)

        Args:
            base_price: 基准价格

        Returns:
            Decimal: 挂单价格
        """
        return base_price * (1 - self.discount)

    def _should_skip_entry(self, cycle_phase: Optional[str]) -> bool:
        """
        判断是否跳过入场

        Args:
            cycle_phase: 当前周期状态

        Returns:
            bool: True表示跳过入场，False表示允许入场
        """
        return cycle_phase == 'bear_warning'

    def _get_position_size(self) -> Decimal:
        """
        获取动态仓位金额

        使用position_manager计算当前应该使用的仓位金额。

        Returns:
            Decimal: 仓位金额，0表示无法下单
        """
        return self.position_manager.calculate_position_size(
            available_cash=self._available_capital,
            max_positions=self.max_positions,
            current_positions=len(self._holdings)
        )

    def run_backtest(
        self,
        klines_df: pd.DataFrame,
        initial_capital: Decimal = Decimal("10000")
    ) -> Dict:
        """
        执行回测

        Args:
            klines_df: K线数据DataFrame，index为DatetimeIndex
            initial_capital: 初始资金

        Returns:
            Dict: 回测结果
        """
        # 初始化
        self._available_capital = initial_capital
        self._pending_order = None
        self._pending_sell_orders.clear()
        self._holdings.clear()
        self._completed_orders.clear()

        # 计算指标
        indicators = self._calculate_indicators(klines_df)

        # 统计
        total_buy_fills = 0
        total_sell_fills = 0
        self._skipped_bear_warning = 0  # 重置统计

        # 逐K线处理
        for i in range(1, len(klines_df)):  # 从第1根开始（第0根用于计算挂单）
            kline = klines_df.iloc[i]
            prev_kline = klines_df.iloc[i-1]
            timestamp = int(klines_df.index[i].timestamp() * 1000)

            # 获取当前K线的指标
            current_indicators = {
                'ema7': indicators['ema7'].iloc[i],
                'ema25': indicators['ema25'].iloc[i],
                'ema99': indicators['ema99'].iloc[i],
                'p5': indicators['p5'].iloc[i],
                'p95': indicators['p95'].iloc[i],
                'inertia_mid': indicators['inertia_mid'].iloc[i],
                'cycle_phase': indicators['cycle_phase'].iloc[i],
            }

            low = Decimal(str(kline['low']))
            high = Decimal(str(kline['high']))
            close = Decimal(str(kline['close']))
            prev_close = Decimal(str(prev_kline['close']))

            # === Step 0: 检查卖出挂单是否成交 ===
            sell_orders_to_remove = []
            for order_id, sell_order in self._pending_sell_orders.items():
                if order_id not in self._holdings:
                    sell_orders_to_remove.append(order_id)
                    continue

                sell_price = Decimal(str(sell_order['price']))

                # 检查是否成交：high >= 挂单价
                if high >= sell_price:
                    holding = self._holdings[order_id]
                    buy_price = holding['buy_price']
                    quantity = holding['quantity']

                    profit_loss = (sell_price - buy_price) * quantity
                    profit_rate = (sell_price / buy_price - 1) * 100

                    logger.info(
                        f"卖出挂单成交: {order_id}, "
                        f"挂单价: {sell_price:.2f}, 原因: {sell_order['reason']}, "
                        f"买入价: {buy_price:.2f}, 盈亏: {profit_rate:.2f}%"
                    )

                    # 回收资金
                    self._available_capital += holding['amount'] + profit_loss

                    # 记录完成的交易
                    self._completed_orders.append({
                        'buy_order_id': order_id,
                        'buy_price': float(buy_price),
                        'sell_price': float(sell_price),
                        'quantity': float(quantity),
                        'amount': float(holding['amount']),
                        'profit_loss': float(profit_loss),
                        'profit_rate': float(profit_rate),
                        'buy_timestamp': holding['buy_timestamp'],
                        'sell_timestamp': timestamp,
                        'exit_reason': sell_order['reason'],
                    })

                    del self._holdings[order_id]
                    sell_orders_to_remove.append(order_id)
                    total_sell_fills += 1
                else:
                    # 未成交，取消挂单（后续会重新创建）
                    sell_orders_to_remove.append(order_id)
                    logger.debug(f"卖出挂单未成交，取消: {order_id}")

            # 清理已处理的卖出挂单
            for order_id in sell_orders_to_remove:
                if order_id in self._pending_sell_orders:
                    del self._pending_sell_orders[order_id]

            # === Step 1: 检查买入挂单是否成交 ===
            if self._pending_order and self._pending_order.is_pending():
                if low <= self._pending_order.price:
                    # 挂单成交
                    self._pending_order.mark_filled(timestamp)
                    order_id = self._pending_order.order_id

                    # 记录持仓
                    self._holdings[order_id] = {
                        'buy_price': self._pending_order.price,
                        'quantity': self._pending_order.quantity,
                        'amount': self._pending_order.amount,
                        'buy_timestamp': timestamp,
                        'kline_index': i,
                    }

                    total_buy_fills += 1
                    logger.info(
                        f"买入成交: {order_id}, 价格: {self._pending_order.price:.2f}, "
                        f"数量: {self._pending_order.quantity:.6f}"
                    )
                else:
                    # 未成交，取消挂单，释放冻结资金
                    self._available_capital += self._pending_order.frozen_capital
                    self._pending_order.mark_cancelled()
                    logger.debug(f"买入挂单未成交，取消: {self._pending_order.order_id}")

                self._pending_order = None

            # === Step 2: 为持仓创建卖出挂单 ===
            for order_id, holding in self._holdings.items():
                # 跳过已有卖出挂单的持仓（不应该有，因为每轮都清理了）
                if order_id in self._pending_sell_orders:
                    continue

                # 验证指标有效性
                ema25_val = current_indicators.get('ema25')
                p95_val = current_indicators.get('p95')
                cycle_phase = current_indicators.get('cycle_phase')

                if (ema25_val is None or np.isnan(ema25_val) or
                    p95_val is None or np.isnan(p95_val) or
                    cycle_phase is None):
                    continue

                ema25 = Decimal(str(ema25_val))
                p95 = Decimal(str(p95_val))

                # 根据cycle_phase计算卖出挂单价
                if cycle_phase in ('bear_warning', 'bear_strong'):
                    sell_price = ema25
                    reason = f"EMA25挂单止盈 (EMA25={float(ema25):.2f})"
                elif cycle_phase == 'consolidation':
                    sell_price = (p95 + ema25) / 2
                    reason = f"震荡期挂单止盈 ((P95+EMA25)/2={float(sell_price):.2f})"
                else:  # bull_warning, bull_strong
                    sell_price = p95
                    reason = f"P95挂单止盈 (P95={float(p95):.2f})"

                # 创建卖出挂单
                self._pending_sell_orders[order_id] = {
                    'price': float(sell_price),
                    'reason': reason,
                    'cycle_phase': cycle_phase,
                    'created_at': timestamp,
                }

                logger.debug(
                    f"创建卖出挂单: {order_id}, 挂单价: {sell_price:.2f}, "
                    f"周期: {cycle_phase}, 原因: {reason}"
                )

            # === Step 3: 创建新的买入挂单 ===
            cycle_phase = current_indicators.get('cycle_phase')

            # v4.0: bear_warning周期跳过挂单创建
            if self._should_skip_entry(cycle_phase):
                self._skipped_bear_warning += 1
                logger.debug(f"bear_warning周期，跳过买入挂单创建")
                continue

            # v4.0: 使用动态仓位计算
            position_size = self._get_position_size()

            # 动态仓位返回0表示跳过（资金不足或持仓已满）
            if position_size == Decimal("0"):
                logger.debug(f"动态仓位计算返回0，跳过买入挂单创建")
                continue

            # 条件：有足够可用资金
            if self._available_capital >= position_size:

                p5_val = current_indicators['p5']
                mid_val = current_indicators['inertia_mid']

                # 跳过NaN值
                if not (np.isnan(p5_val) or np.isnan(mid_val)):
                    p5 = Decimal(str(p5_val))
                    inertia_mid = Decimal(str(mid_val))

                    if p5 > 0 and inertia_mid > 0:
                        # 计算挂单价格
                        base_price = self._calculate_base_price(p5, close, inertia_mid)
                        order_price = self._calculate_order_price(base_price)

                        # 创建挂单（使用动态仓位金额）
                        quantity = position_size / order_price
                        self._pending_order = PendingOrder(
                            order_id=f"pending_{timestamp}_{i}",
                            price=order_price,
                            amount=position_size,
                            quantity=quantity,
                            status=PendingOrderStatus.PENDING,
                            side=PendingOrderSide.BUY,
                            frozen_capital=position_size,
                            kline_index=i,
                            created_at=timestamp,
                            metadata={
                                'base_price': float(base_price),
                                'p5': float(p5),
                                'close': float(close),
                                'mid_p5': float((p5 + inertia_mid) / 2),
                                'cycle_phase': cycle_phase,
                            }
                        )

                        # 冻结资金
                        self._available_capital -= position_size

                        logger.debug(
                            f"创建买入挂单: {self._pending_order.order_id}, "
                            f"价格: {order_price:.2f}, 金额: {position_size}, "
                            f"周期: {cycle_phase}"
                        )

        # 生成回测结果（传入最后收盘价和时间戳用于计算持仓市值和APR/APY）
        last_close_price = Decimal(str(klines_df['close'].iloc[-1]))
        start_timestamp = int(klines_df.index[0].timestamp() * 1000)
        end_timestamp = int(klines_df.index[-1].timestamp() * 1000)

        result = self._generate_result(
            initial_capital, len(klines_df), last_close_price,
            start_timestamp, end_timestamp
        )

        # v4.0: 添加策略16特有统计
        result['skipped_bear_warning'] = self._skipped_bear_warning

        logger.info(
            f"策略16回测完成: 跳过bear_warning={self._skipped_bear_warning}次"
        )

        return result

    def _calculate_indicators(self, klines_df: pd.DataFrame) -> Dict[str, pd.Series]:
        """
        计算所需的技术指标

        Args:
            klines_df: K线数据

        Returns:
            Dict: 指标字典
        """
        from ddps_z.calculators.ema_calculator import EMACalculator
        from ddps_z.calculators.ewma_calculator import EWMACalculator
        from ddps_z.calculators.inertia_calculator import InertiaCalculator
        from ddps_z.calculators.adx_calculator import ADXCalculator
        from ddps_z.calculators.beta_cycle_calculator import BetaCycleCalculator

        prices = klines_df['close'].values
        high = klines_df['high'].values
        low = klines_df['low'].values
        timestamps_ms = np.array([int(ts.timestamp() * 1000) for ts in klines_df.index])

        # EMA计算
        ema7_calc = EMACalculator(period=7)
        ema25_calc = EMACalculator(period=25)
        ema99_calc = EMACalculator(period=99)
        ewma_calc = EWMACalculator(window_n=50)

        ema7_array = ema7_calc.calculate_ema_series(prices)
        ema25_array = ema25_calc.calculate_ema_series(prices)
        ema99_array = ema99_calc.calculate_ema_series(prices)

        # P5和P95计算
        deviation = ema25_calc.calculate_deviation_series(prices)
        _, ewma_std_series = ewma_calc.calculate_ewma_stats(deviation)
        z_p5 = -1.645
        z_p95 = 1.645
        p5_array = ema25_array * (1 + z_p5 * ewma_std_series)
        p95_array = ema25_array * (1 + z_p95 * ewma_std_series)

        # 惯性计算
        adx_calc = ADXCalculator(period=14)
        inertia_calc = InertiaCalculator(base_period=5)

        adx_result = adx_calc.calculate(high, low, prices)
        adx_series = adx_result['adx']

        fan_result = inertia_calc.calculate_historical_fan_series(
            timestamps=timestamps_ms,
            ema_series=ema25_array,
            sigma_series=ewma_std_series,
            adx_series=adx_series
        )
        inertia_mid_array = fan_result['mid']
        beta_array = fan_result['beta']

        # 周期计算
        cycle_calc = BetaCycleCalculator()
        beta_list = [b if not np.isnan(b) else None for b in beta_array]
        cycle_phases, _ = cycle_calc.calculate(
            beta_list=beta_list,
            timestamps=timestamps_ms.tolist(),
            prices=prices.tolist(),
            interval_hours=4.0
        )

        return {
            'ema7': pd.Series(ema7_array, index=klines_df.index),
            'ema25': pd.Series(ema25_array, index=klines_df.index),
            'ema99': pd.Series(ema99_array, index=klines_df.index),
            'p5': pd.Series(p5_array, index=klines_df.index),
            'p95': pd.Series(p95_array, index=klines_df.index),
            'inertia_mid': pd.Series(inertia_mid_array, index=klines_df.index),
            'cycle_phase': pd.Series(cycle_phases, index=klines_df.index),
        }

    def _generate_result(
        self,
        initial_capital: Decimal,
        kline_count: int,
        last_close_price: Decimal = None,
        start_timestamp: int = None,
        end_timestamp: int = None
    ) -> Dict:
        """
        生成回测结果

        使用BacktestResult数据类构建标准化结果，并通过to_dict()返回字典格式
        以保持向后兼容。

        Args:
            initial_capital: 初始资金
            kline_count: K线数量
            last_close_price: 最后一根K线收盘价（用于计算持仓市值）
            start_timestamp: 回测开始时间戳（毫秒）
            end_timestamp: 回测结束时间戳（毫秒）

        Returns:
            Dict: 回测结果（通过BacktestResult.to_dict()生成）
        """
        # 计算统计
        total_orders = len(self._completed_orders)
        winning_orders_list = [o for o in self._completed_orders if o['profit_loss'] > 0]
        losing_orders_list = [o for o in self._completed_orders if o['profit_loss'] <= 0]

        total_profit = sum(o['profit_loss'] for o in self._completed_orders)
        win_rate = len(winning_orders_list) / total_orders * 100 if total_orders > 0 else 0

        # 计算总交易量和手续费
        commission_rate = Decimal('0.001')  # 默认手续费率 0.1%
        total_volume = Decimal('0')
        for order in self._completed_orders:
            buy_amount = Decimal(str(order['amount']))
            sell_amount = Decimal(str(order['sell_price'])) * Decimal(str(order['quantity']))
            total_volume += buy_amount + sell_amount

        # 计算持仓统计
        holding_cost = Decimal('0')
        holding_quantity = Decimal('0')
        for holding in self._holdings.values():
            holding_cost += holding['amount']
            holding_quantity += holding['quantity']
            total_volume += Decimal(str(holding['amount']))

        # 计算总手续费
        total_commission = total_volume * commission_rate

        # 计算持仓市值
        if last_close_price and holding_quantity > 0:
            holding_value = last_close_price * holding_quantity
        else:
            holding_value = holding_cost

        # 计算持仓浮盈浮亏
        holding_unrealized_pnl = holding_value - holding_cost

        # 计算挂单冻结资金
        frozen_capital = Decimal('0')
        if self._pending_order and self._pending_order.is_pending():
            frozen_capital = self._pending_order.frozen_capital

        # 计算可用资金
        available_capital = self._available_capital

        # 计算账户总价值
        total_equity = available_capital + frozen_capital + holding_value

        # 收益率
        return_rate = (float(total_equity) / float(initial_capital) - 1) * 100

        # 计算回测天数和日期
        MS_PER_DAY = 24 * 60 * 60 * 1000
        if start_timestamp and end_timestamp:
            backtest_days = max((end_timestamp - start_timestamp) / MS_PER_DAY, 1)
            from datetime import datetime, timezone
            start_date = datetime.fromtimestamp(start_timestamp / 1000, tz=timezone.utc).strftime('%Y-%m-%d')
            end_date = datetime.fromtimestamp(end_timestamp / 1000, tz=timezone.utc).strftime('%Y-%m-%d')
        else:
            backtest_days = 1
            start_date = ''
            end_date = ''

        # 计算APR和APY
        static_apr = self._calculate_static_apr(total_equity, initial_capital, backtest_days)
        weighted_apy = self._calculate_weighted_apy(
            self._completed_orders,
            self._holdings,
            end_timestamp or 0,
            last_close_price
        )

        # 构建BacktestResult
        result = BacktestResult(
            total_orders=total_orders,
            winning_orders=len(winning_orders_list),
            losing_orders=len(losing_orders_list),
            open_positions=len(self._holdings),
            win_rate=win_rate,
            net_profit=float(total_profit),
            return_rate=return_rate,
            initial_capital=float(initial_capital),
            total_equity=float(total_equity),
            available_capital=float(available_capital),
            frozen_capital=float(frozen_capital),
            holding_cost=float(holding_cost),
            holding_value=float(holding_value),
            holding_unrealized_pnl=float(holding_unrealized_pnl),
            total_volume=float(total_volume),
            total_commission=float(total_commission),
            last_close_price=float(last_close_price) if last_close_price else 0,
            static_apr=static_apr,
            weighted_apy=weighted_apy,
            backtest_days=int(backtest_days),
            start_date=start_date,
            end_date=end_date,
            orders=self._completed_orders,
        )

        return result.to_dict()

    def _calculate_static_apr(
        self,
        total_equity: Decimal,
        initial_capital: Decimal,
        backtest_days: float
    ) -> float:
        """
        计算静态APR（年化收益率）

        公式: (total_equity - initial_capital) / initial_capital / backtest_days * 365 * 100

        Args:
            total_equity: 账户总价值
            initial_capital: 初始资金
            backtest_days: 回测天数

        Returns:
            float: 静态年化收益率（%）
        """
        if backtest_days <= 0 or initial_capital <= 0:
            return 0.0
        return float((total_equity - initial_capital) / initial_capital / Decimal(str(backtest_days)) * 365 * 100)

    def _calculate_weighted_apy(
        self,
        completed_orders: list,
        holdings: dict,
        end_timestamp: int,
        last_close_price: Decimal = None
    ) -> float:
        """
        计算时间加权年化收益率（APY）

        公式: Σ(年化收益率_i × 金额_i) / Σ(金额_i)
        其中: 年化收益率_i = 收益率_i × (365 / 持仓天数_i)

        Args:
            completed_orders: 已平仓订单列表
            holdings: 持仓中订单字典
            end_timestamp: 回测结束时间戳（毫秒）
            last_close_price: 最后收盘价（用于计算持仓浮盈）

        Returns:
            float: 时间加权年化收益率（%）
        """
        MS_PER_DAY = 24 * 60 * 60 * 1000
        weighted_sum = 0.0
        total_amount = 0.0

        # 处理已平仓订单
        for order in completed_orders:
            amount = float(order.get('amount', 0))
            if amount <= 0:
                continue

            profit_rate = order.get('profit_rate', 0) / 100  # 转为小数
            buy_ts = order.get('buy_timestamp', 0)
            sell_ts = order.get('sell_timestamp', 0)

            holding_days = max((sell_ts - buy_ts) / MS_PER_DAY, 1)  # 最小1天
            annualized_rate = profit_rate * (365 / holding_days)

            weighted_sum += annualized_rate * amount
            total_amount += amount

        # 处理持仓中订单（使用浮动盈亏）
        if last_close_price and end_timestamp:
            for order_id, holding in holdings.items():
                amount = float(holding.get('amount', 0))
                if amount <= 0:
                    continue

                buy_price = Decimal(str(holding.get('buy_price', 0)))
                quantity = Decimal(str(holding.get('quantity', 0)))
                buy_ts = holding.get('buy_timestamp', 0)

                if buy_price > 0:
                    # 计算浮动收益率
                    current_value = last_close_price * quantity
                    profit_rate = float((current_value - Decimal(str(amount))) / Decimal(str(amount)))

                    holding_days = max((end_timestamp - buy_ts) / MS_PER_DAY, 1)
                    annualized_rate = profit_rate * (365 / holding_days)

                    weighted_sum += annualized_rate * amount
                    total_amount += amount

        if total_amount <= 0:
            return 0.0

        return round(weighted_sum / total_amount * 100, 2)

    # === IStrategy接口的其他方法（回测模式下不使用） ===

    def generate_buy_signals(self, klines, indicators):
        """生成买入信号（策略16使用限价挂单模式，此方法不使用）"""
        return []

    def generate_sell_signals(self, klines, indicators, open_orders):
        """生成卖出信号（策略16使用限价挂单模式，此方法不使用）"""
        return []

    def calculate_position_size(self, signal, available_capital, current_price):
        """计算仓位大小（v4.0使用动态仓位管理器）"""
        return self._get_position_size()

    def should_stop_loss(self, order, current_price, current_timestamp):
        """检查是否需要止损"""
        return False

    def should_take_profit(self, order, current_price, current_timestamp):
        """检查是否需要止盈"""
        return False
