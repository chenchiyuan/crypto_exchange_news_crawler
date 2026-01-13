"""
策略18：周期趋势入场策略

本模块实现策略18的周期趋势入场机制：
- 入场：基于42周期占比和EMA25斜率双重确认，在上涨周期使用EMA7/EMA25双挂单入场
- 止盈：周期状态止盈（非上涨周期+EMA7下穿EMA25）、固定比例止盈（10%）
- 止损：固定比例止损（3%）

核心逻辑：
1. 周期状态判断：强势上涨占比>40%且EMA25斜率为近6根最高 → 上涨周期
2. 双挂单机制：上涨周期时，在EMA7和EMA25价格各挂一笔限价买单
3. 成交判断：下根K线low<=挂单价格时成交
4. 卖出优先级：止损(3%) > 止盈(10%) > 周期状态止盈

迭代编号: 039 (策略18-周期趋势入场)
创建日期: 2026-01-13
关联需求: FP-039-001 ~ FP-039-008
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Any

import pandas as pd
import numpy as np

from strategy_adapter.interfaces import IStrategy
from strategy_adapter.models import PendingOrder, PendingOrderStatus, PendingOrderSide

logger = logging.getLogger(__name__)


class Strategy18CycleTrendEntry(IStrategy):
    """
    策略18：周期趋势入场策略

    基于42周期占比和EMA25斜率双重确认的趋势跟踪策略。

    工作流程：
    1. 计算42周期占比（统计最近42根K线的周期状态分布）
    2. 计算EMA25斜率，判断是否为近6根最高
    3. 综合判断周期状态：上涨周期/下跌周期/震荡周期
    4. 上涨周期时创建双挂单（EMA7+EMA25）
    5. 检查持仓止盈止损

    Attributes:
        position_size: 单笔仓位金额（USDT）
        max_positions: 最大持仓数量
        cycle_window: 周期占比统计窗口（默认42）
        bull_threshold: 上涨周期占比阈值（默认40%）
        bear_threshold: 下跌周期占比阈值（默认40%）
        slope_window: EMA25斜率比较窗口（默认6）
        take_profit_pct: 止盈比例（默认10%）
        stop_loss_pct: 止损比例（默认3%）

    Example:
        >>> strategy = Strategy18CycleTrendEntry(
        ...     position_size=Decimal("1000"),
        ...     take_profit_pct=10.0,
        ...     stop_loss_pct=3.0
        ... )
        >>> result = strategy.run_backtest(klines_df, initial_capital=10000)
    """

    STRATEGY_ID = 'strategy_18'
    STRATEGY_NAME = '周期趋势入场'
    STRATEGY_VERSION = '1.0'

    def __init__(
        self,
        position_size: Decimal = Decimal("1000"),
        max_positions: int = 10,
        cycle_window: int = 42,
        bull_threshold: float = 24.0,
        bear_threshold: float = 24.0,
        slope_window: int = 2,
        take_profit_pct: float = 10.0,
        stop_loss_pct: float = 3.0
    ):
        """
        初始化策略18

        Args:
            position_size: 单笔仓位金额（USDT），默认1000
            max_positions: 最大持仓数量，默认10
            cycle_window: 周期占比统计窗口，默认42
            bull_threshold: 上涨周期占比阈值，默认24%
            bear_threshold: 下跌周期占比阈值，默认24%
            slope_window: EMA25斜率比较窗口，默认2
            take_profit_pct: 止盈比例，默认10%
            stop_loss_pct: 止损比例，默认3%
        """
        self.position_size = position_size
        self.max_positions = max_positions
        self.cycle_window = cycle_window
        self.bull_threshold = bull_threshold
        self.bear_threshold = bear_threshold
        self.slope_window = slope_window
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct

        # 状态管理
        self._pending_orders: List[PendingOrder] = []  # 当前挂单（最多2笔）
        self._holdings: Dict[str, Dict] = {}  # 持仓: order_id -> {buy_price, quantity, ...}
        self._completed_orders: List[Dict] = []  # 已完成交易
        self._available_capital: Decimal = Decimal("0")

        logger.info(
            f"初始化Strategy18CycleTrendEntry: position_size={position_size}, "
            f"max_positions={max_positions}, cycle_window={cycle_window}, "
            f"bull_threshold={bull_threshold}, bear_threshold={bear_threshold}, "
            f"slope_window={slope_window}, take_profit_pct={take_profit_pct}, "
            f"stop_loss_pct={stop_loss_pct}"
        )

    def get_strategy_name(self) -> str:
        return self.STRATEGY_NAME

    def get_strategy_version(self) -> str:
        return self.STRATEGY_VERSION

    def get_required_indicators(self) -> List[str]:
        """返回所需的技术指标"""
        return ['ema7', 'ema25', 'ema99', 'cycle_phase']

    # ============================================================
    # 周期状态判断方法 (FP-039-001, FP-039-002, FP-039-003)
    # ============================================================

    def _calculate_cycle_distribution(self, cycle_phases: List[str]) -> Dict[str, float]:
        """
        计算周期状态分布占比（FP-039-001）

        统计最近cycle_window根K线的周期状态分布。

        Args:
            cycle_phases: 周期状态列表（时间升序）

        Returns:
            Dict: 各状态占比（%），例如 {'bull_strong': 30, 'consolidation': 40, ...}
        """
        # 取最近cycle_window根
        recent_phases = cycle_phases[-self.cycle_window:] if len(cycle_phases) >= self.cycle_window else cycle_phases
        total = len(recent_phases)

        if total == 0:
            return {}

        # 统计各状态数量
        counts = {
            'bull_strong': 0,
            'bull_warning': 0,
            'consolidation': 0,
            'bear_warning': 0,
            'bear_strong': 0,
        }

        for phase in recent_phases:
            if phase in counts:
                counts[phase] += 1

        # 转换为百分比
        distribution = {k: (v / total) * 100 for k, v in counts.items()}
        return distribution

    def _calculate_ema_slopes(self, ema25_series: np.ndarray) -> np.ndarray:
        """
        计算EMA25斜率序列（FP-039-002）

        斜率 = 当前值 - 前一值

        Args:
            ema25_series: EMA25序列

        Returns:
            np.ndarray: 斜率序列（长度比输入少1）
        """
        if len(ema25_series) < 2:
            return np.array([])
        return np.diff(ema25_series)

    def _is_slope_highest(self, slopes: np.ndarray) -> bool:
        """
        判断当前斜率是否为近slope_window根最高（FP-039-002）

        Args:
            slopes: 斜率序列

        Returns:
            bool: True表示当前斜率为近slope_window根最高
        """
        if len(slopes) < self.slope_window:
            return False
        recent = slopes[-self.slope_window:]
        return slopes[-1] == np.max(recent)

    def _is_slope_lowest(self, slopes: np.ndarray) -> bool:
        """
        判断当前斜率是否为近slope_window根最低（FP-039-002）

        Args:
            slopes: 斜率序列

        Returns:
            bool: True表示当前斜率为近slope_window根最低
        """
        if len(slopes) < self.slope_window:
            return False
        recent = slopes[-self.slope_window:]
        return slopes[-1] == np.min(recent)

    def _determine_cycle_state(
        self,
        distribution: Dict[str, float],
        is_slope_highest: bool,
        is_slope_lowest: bool
    ) -> str:
        """
        综合判断当前周期状态（FP-039-003）

        判断逻辑：
        - 上涨周期：强势上涨占比>40% 且 EMA25斜率为近6根最高
        - 下跌周期：强势下跌占比>40% 且 EMA25斜率为近6根最低
        - 震荡周期：其他情况

        Args:
            distribution: 周期占比
            is_slope_highest: 斜率是否最高
            is_slope_lowest: 斜率是否最低

        Returns:
            str: 'bull' | 'bear' | 'consolidation'
        """
        bull_strong_pct = distribution.get('bull_strong', 0)
        bear_strong_pct = distribution.get('bear_strong', 0)

        if bull_strong_pct > self.bull_threshold and is_slope_highest:
            return 'bull'
        elif bear_strong_pct > self.bear_threshold and is_slope_lowest:
            return 'bear'
        else:
            return 'consolidation'

    # ============================================================
    # 双挂单机制 (FP-039-004, FP-039-005)
    # ============================================================

    def _create_pending_orders(
        self,
        ema7: Decimal,
        ema25: Decimal,
        timestamp: int,
        kline_index: int
    ) -> List[PendingOrder]:
        """
        创建双挂单（EMA7 + EMA25）（FP-039-005）

        Args:
            ema7: EMA7价格
            ema25: EMA25价格
            timestamp: 当前时间戳
            kline_index: 当前K线索引

        Returns:
            List[PendingOrder]: 创建的挂单列表
        """
        orders = []

        # 检查持仓数量
        if len(self._holdings) >= self.max_positions:
            return orders

        # 挂单1: EMA7价格
        if self._available_capital >= self.position_size:
            quantity1 = self.position_size / ema7
            order1 = PendingOrder(
                order_id=f"pending_{timestamp}_{kline_index}_ema7",
                price=ema7,
                amount=self.position_size,
                quantity=quantity1,
                status=PendingOrderStatus.PENDING,
                side=PendingOrderSide.BUY,
                frozen_capital=self.position_size,
                kline_index=kline_index,
                created_at=timestamp,
                metadata={'entry_type': 'ema7'}
            )
            orders.append(order1)
            self._available_capital -= self.position_size

        # 挂单2: EMA25价格（再次检查资金和持仓）
        if (self._available_capital >= self.position_size and
            len(self._holdings) + len(orders) < self.max_positions):
            quantity2 = self.position_size / ema25
            order2 = PendingOrder(
                order_id=f"pending_{timestamp}_{kline_index}_ema25",
                price=ema25,
                amount=self.position_size,
                quantity=quantity2,
                status=PendingOrderStatus.PENDING,
                side=PendingOrderSide.BUY,
                frozen_capital=self.position_size,
                kline_index=kline_index,
                created_at=timestamp,
                metadata={'entry_type': 'ema25'}
            )
            orders.append(order2)
            self._available_capital -= self.position_size

        return orders

    def _process_pending_orders(self, low: Decimal, timestamp: int, kline_index: int) -> int:
        """
        处理待成交挂单

        Args:
            low: 当前K线最低价
            timestamp: 当前时间戳
            kline_index: 当前K线索引

        Returns:
            int: 成交的挂单数量
        """
        filled_count = 0
        orders_to_remove = []

        for order in self._pending_orders:
            if not order.is_pending():
                continue

            if low <= order.price:
                # 挂单成交
                order.mark_filled(timestamp)
                order_id = order.order_id.replace('pending_', 'order_')

                # 记录持仓
                self._holdings[order_id] = {
                    'buy_price': order.price,
                    'quantity': order.quantity,
                    'amount': order.amount,
                    'buy_timestamp': timestamp,
                    'kline_index': kline_index,
                    'metadata': {
                        'entry_type': order.metadata.get('entry_type', 'unknown'),
                        'cross_triggered': False,
                        'pending_exit': False,
                    },
                }

                filled_count += 1
                orders_to_remove.append(order)
                logger.info(
                    f"买入成交: {order_id}, 价格: {order.price:.2f}, "
                    f"数量: {order.quantity:.6f}, 入场类型: {order.metadata.get('entry_type')}"
                )

        # 移除已成交的挂单
        for order in orders_to_remove:
            self._pending_orders.remove(order)

        return filled_count

    def _cancel_pending_orders(self) -> None:
        """
        取消所有未成交挂单，释放冻结资金
        """
        for order in self._pending_orders:
            if order.is_pending():
                self._available_capital += order.frozen_capital
                order.mark_cancelled()
                logger.debug(f"挂单取消: {order.order_id}, 释放资金: {order.frozen_capital}")

        self._pending_orders.clear()

    # ============================================================
    # 卖出策略 (FP-039-006, FP-039-007, FP-039-008)
    # ============================================================

    def _check_stop_loss(self, holding: Dict, low: Decimal) -> Optional[Dict]:
        """
        检查止损（FP-039-008）

        Args:
            holding: 持仓信息
            low: 当前K线最低价

        Returns:
            Optional[Dict]: 如果触发止损，返回平仓信息；否则返回None
        """
        buy_price = holding['buy_price']
        stop_loss_price = buy_price * (1 - Decimal(str(self.stop_loss_pct)) / 100)

        if low <= stop_loss_price:
            sell_price = stop_loss_price
            profit_loss = (sell_price - buy_price) * holding['quantity']
            profit_rate = (sell_price / buy_price - 1) * 100

            return {
                'sell_price': sell_price,
                'profit_loss': profit_loss,
                'profit_rate': float(profit_rate),
                'exit_reason': 'stop_loss',
            }
        return None

    def _check_take_profit(self, holding: Dict, high: Decimal) -> Optional[Dict]:
        """
        检查止盈（FP-039-007）

        Args:
            holding: 持仓信息
            high: 当前K线最高价

        Returns:
            Optional[Dict]: 如果触发止盈，返回平仓信息；否则返回None
        """
        buy_price = holding['buy_price']
        take_profit_price = buy_price * (1 + Decimal(str(self.take_profit_pct)) / 100)

        if high >= take_profit_price:
            sell_price = take_profit_price
            profit_loss = (sell_price - buy_price) * holding['quantity']
            profit_rate = (sell_price / buy_price - 1) * 100

            return {
                'sell_price': sell_price,
                'profit_loss': profit_loss,
                'profit_rate': float(profit_rate),
                'exit_reason': 'take_profit',
            }
        return None

    def _check_cycle_exit(
        self,
        holding: Dict,
        cycle_state: str,
        ema7: float,
        ema25: float,
        prev_ema7: float,
        prev_ema25: float
    ) -> bool:
        """
        检查周期状态止盈条件（FP-039-006）

        触发条件：
        1. 当前周期状态 ≠ 上涨周期
        2. EMA7 下穿 EMA25
        3. 该订单首次触发

        Args:
            holding: 持仓信息
            cycle_state: 当前周期状态
            ema7: 当前EMA7
            ema25: 当前EMA25
            prev_ema7: 前一根EMA7
            prev_ema25: 前一根EMA25

        Returns:
            bool: True表示触发周期状态止盈
        """
        # 条件1：非上涨周期
        if cycle_state == 'bull':
            return False

        # 条件2：EMA7下穿EMA25
        cross_down = (ema7 < ema25) and (prev_ema7 >= prev_ema25)
        if not cross_down:
            return False

        # 条件3：首次触发
        if holding['metadata'].get('cross_triggered', False):
            return False

        # 标记触发
        holding['metadata']['cross_triggered'] = True
        holding['metadata']['pending_exit'] = True
        return True

    def _process_pending_exits(self, open_price: Decimal, timestamp: int) -> List[Dict]:
        """
        处理待卖出订单（下根K线以open卖出）

        Args:
            open_price: 当前K线开盘价
            timestamp: 当前时间戳

        Returns:
            List[Dict]: 平仓信息列表
        """
        close_list = []

        for order_id, holding in list(self._holdings.items()):
            if holding['metadata'].get('pending_exit', False):
                buy_price = holding['buy_price']
                sell_price = open_price
                profit_loss = (sell_price - buy_price) * holding['quantity']
                profit_rate = (sell_price / buy_price - 1) * 100

                close_list.append({
                    'order_id': order_id,
                    'sell_price': sell_price,
                    'profit_loss': profit_loss,
                    'profit_rate': float(profit_rate),
                    'exit_reason': 'cycle_state_exit',
                })

        return close_list

    # ============================================================
    # 回测主循环
    # ============================================================

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
        self._pending_orders.clear()
        self._holdings.clear()
        self._completed_orders.clear()

        # 计算指标
        indicators = self._calculate_indicators(klines_df)

        # 统计
        total_buy_fills = 0
        total_sell_fills = 0

        # 需要至少cycle_window根K线历史
        start_index = max(self.cycle_window, self.slope_window + 1)

        # 逐K线处理
        for i in range(start_index, len(klines_df)):
            kline = klines_df.iloc[i]
            timestamp = int(klines_df.index[i].timestamp() * 1000)

            # 获取当前K线数据
            open_price = Decimal(str(kline['open']))
            low = Decimal(str(kline['low']))
            high = Decimal(str(kline['high']))
            close = Decimal(str(kline['close']))

            # 获取指标
            ema7 = indicators['ema7'].iloc[i]
            ema25 = indicators['ema25'].iloc[i]
            prev_ema7 = indicators['ema7'].iloc[i-1]
            prev_ema25 = indicators['ema25'].iloc[i-1]
            cycle_phases = indicators['cycle_phase'].iloc[:i+1].tolist()
            ema25_series = indicators['ema25'].iloc[:i+1].values

            # 跳过NaN值
            if np.isnan(ema7) or np.isnan(ema25):
                continue

            ema7_dec = Decimal(str(ema7))
            ema25_dec = Decimal(str(ema25))

            # === Step 1: 处理待卖出订单（上根K线标记的周期状态止盈）===
            pending_exits = self._process_pending_exits(open_price, timestamp)
            for close_info in pending_exits:
                order_id = close_info['order_id']
                holding = self._holdings[order_id]

                # 回收资金
                self._available_capital += holding['amount'] + close_info['profit_loss']

                # 记录完成的交易
                self._completed_orders.append({
                    'buy_order_id': order_id,
                    'buy_price': float(holding['buy_price']),
                    'sell_price': float(close_info['sell_price']),
                    'quantity': float(holding['quantity']),
                    'amount': float(holding['amount']),
                    'profit_loss': float(close_info['profit_loss']),
                    'profit_rate': close_info['profit_rate'],
                    'buy_timestamp': holding['buy_timestamp'],
                    'sell_timestamp': timestamp,
                    'exit_reason': close_info['exit_reason'],
                })

                del self._holdings[order_id]
                total_sell_fills += 1
                logger.info(
                    f"周期状态止盈: {order_id}, 卖出价: {close_info['sell_price']:.2f}, "
                    f"盈亏: {close_info['profit_rate']:.2f}%"
                )

            # === Step 2: 检查挂单成交 ===
            filled = self._process_pending_orders(low, timestamp, i)
            total_buy_fills += filled

            # === Step 3: 检查持仓止盈止损 ===
            holdings_to_close = []
            for order_id, holding in list(self._holdings.items()):
                # 跳过待卖出的订单
                if holding['metadata'].get('pending_exit', False):
                    continue

                # 检查止损（最高优先级）
                stop_loss_result = self._check_stop_loss(holding, low)
                if stop_loss_result:
                    holdings_to_close.append({'order_id': order_id, **stop_loss_result})
                    continue

                # 检查止盈
                take_profit_result = self._check_take_profit(holding, high)
                if take_profit_result:
                    holdings_to_close.append({'order_id': order_id, **take_profit_result})
                    continue

            # 执行平仓
            for close_info in holdings_to_close:
                order_id = close_info['order_id']
                holding = self._holdings[order_id]

                # 回收资金
                self._available_capital += holding['amount'] + close_info['profit_loss']

                # 记录完成的交易
                self._completed_orders.append({
                    'buy_order_id': order_id,
                    'buy_price': float(holding['buy_price']),
                    'sell_price': float(close_info['sell_price']),
                    'quantity': float(holding['quantity']),
                    'amount': float(holding['amount']),
                    'profit_loss': float(close_info['profit_loss']),
                    'profit_rate': close_info['profit_rate'],
                    'buy_timestamp': holding['buy_timestamp'],
                    'sell_timestamp': timestamp,
                    'exit_reason': close_info['exit_reason'],
                })

                del self._holdings[order_id]
                total_sell_fills += 1
                logger.info(
                    f"{close_info['exit_reason']}: {order_id}, 卖出价: {close_info['sell_price']:.2f}, "
                    f"盈亏: {close_info['profit_rate']:.2f}%"
                )

            # === Step 4: 判断周期状态 ===
            distribution = self._calculate_cycle_distribution(cycle_phases)
            slopes = self._calculate_ema_slopes(ema25_series)
            is_highest = self._is_slope_highest(slopes)
            is_lowest = self._is_slope_lowest(slopes)
            cycle_state = self._determine_cycle_state(distribution, is_highest, is_lowest)

            # === Step 5: 检查周期状态止盈（标记，下根K线执行）===
            for order_id, holding in self._holdings.items():
                if holding['metadata'].get('pending_exit', False):
                    continue

                if self._check_cycle_exit(
                    holding, cycle_state, ema7, ema25, prev_ema7, prev_ema25
                ):
                    logger.info(
                        f"周期状态止盈触发: {order_id}, 将在下根K线open卖出"
                    )

            # === Step 6: 创建新挂单（仅上涨周期）===
            self._cancel_pending_orders()  # 取消旧挂单

            if cycle_state == 'bull':
                # 检查是否有可用资金和持仓空间
                if (self._available_capital >= self.position_size and
                    len(self._holdings) < self.max_positions):
                    new_orders = self._create_pending_orders(ema7_dec, ema25_dec, timestamp, i)
                    self._pending_orders.extend(new_orders)

                    if new_orders:
                        logger.debug(
                            f"创建双挂单: K线={i}, EMA7={ema7:.2f}, EMA25={ema25:.2f}, "
                            f"挂单数={len(new_orders)}"
                        )

        # 生成回测结果
        return self._generate_result(initial_capital, len(klines_df))

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

        # 偏离率和标准差计算（用于β计算）
        deviation = ema25_calc.calculate_deviation_series(prices)
        _, ewma_std_series = ewma_calc.calculate_ewma_stats(deviation)

        # ADX计算
        adx_calc = ADXCalculator(period=14)
        adx_result = adx_calc.calculate(high, low, prices)
        adx_series = adx_result['adx']

        # 惯性计算（获取β值）
        inertia_calc = InertiaCalculator(base_period=5)
        fan_result = inertia_calc.calculate_historical_fan_series(
            timestamps=timestamps_ms,
            ema_series=ema25_array,
            sigma_series=ewma_std_series,
            adx_series=adx_series
        )
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
            'cycle_phase': pd.Series(cycle_phases, index=klines_df.index),
        }

    def _generate_result(self, initial_capital: Decimal, kline_count: int) -> Dict:
        """
        生成回测结果

        Args:
            initial_capital: 初始资金
            kline_count: K线数量

        Returns:
            Dict: 回测结果
        """
        # 计算统计
        total_orders = len(self._completed_orders)
        winning_orders = [o for o in self._completed_orders if o['profit_loss'] > 0]
        losing_orders = [o for o in self._completed_orders if o['profit_loss'] <= 0]

        total_profit = sum(o['profit_loss'] for o in self._completed_orders)
        win_rate = len(winning_orders) / total_orders * 100 if total_orders > 0 else 0

        # 计算最终资产（可用资金 + 持仓市值 + 挂单冻结资金）
        final_capital = self._available_capital
        for holding in self._holdings.values():
            final_capital += holding['amount']
        for order in self._pending_orders:
            if order.is_pending():
                final_capital += order.frozen_capital

        return_rate = (float(final_capital) / float(initial_capital) - 1) * 100

        return {
            'orders': self._completed_orders,
            'total_trades': total_orders,
            'winning_trades': len(winning_orders),
            'losing_trades': len(losing_orders),
            'total_profit_loss': float(total_profit),
            'win_rate': win_rate,
            'return_rate': return_rate,
            'remaining_holdings': len(self._holdings),
            'statistics': {
                'total_orders': total_orders,
                'winning_orders': len(winning_orders),
                'losing_orders': len(losing_orders),
                'open_positions': len(self._holdings),
                'win_rate': win_rate,
                'total_profit': total_profit,
                'initial_capital': float(initial_capital),
                'final_capital': float(final_capital),
                'return_rate': return_rate,
                'kline_count': kline_count,
            }
        }

    # === IStrategy接口的其他方法（回测模式下不使用） ===

    def generate_buy_signals(self, klines, indicators):
        """生成买入信号（策略18使用周期趋势入场模式，此方法不使用）"""
        return []

    def generate_sell_signals(self, klines, indicators, open_orders):
        """生成卖出信号（策略18使用周期趋势入场模式，此方法不使用）"""
        return []

    def calculate_position_size(self, signal, available_capital, current_price):
        """计算仓位大小"""
        return self.position_size

    def should_stop_loss(self, order, current_price, current_timestamp):
        """检查是否需要止损"""
        return False

    def should_take_profit(self, order, current_price, current_timestamp):
        """检查是否需要止盈"""
        return False
