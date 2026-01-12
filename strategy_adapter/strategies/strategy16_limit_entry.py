"""
策略16：P5限价挂单入场 + EMA状态止盈

本模块实现策略16的限价挂单入场机制：
- 入场：每根K线结束时计算挂单价格，下根K线判断成交
- 止盈：EMA状态止盈（强势上涨/强势下跌/震荡下跌不同条件）
- 止损：可配置比例止损（默认5%）

核心逻辑（避免后验偏差）：
1. 当前K线结束时：base_price = min(p5, close, (p5+mid)/2)
2. 挂单价格 = base_price × (1 - discount)
3. 下根K线开始时：如果 low <= 挂单价格 → 以挂单价格成交
4. 下根K线结束时：取消未成交挂单，重新计算新挂单

迭代编号: 036 (策略16-P5限价挂单入场)
创建日期: 2026-01-12
关联需求: Bug-Fix - 策略16买入条件后验问题
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Any

import pandas as pd
import numpy as np

from strategy_adapter.interfaces import IStrategy
from strategy_adapter.models import PendingOrder, PendingOrderStatus, PendingOrderSide
from strategy_adapter.exits import EmaStateExit

logger = logging.getLogger(__name__)


class Strategy16LimitEntry(IStrategy):
    """
    策略16：P5限价挂单入场 + EMA状态止盈

    与策略7的核心差异：
    - 策略7：当前K线low<=P5时，以close买入（后验问题）
    - 策略16：当前K线结束时计算挂单价格，下根K线判断成交（前瞻性）

    工作流程：
    1. 每根K线结束时：
       - 检查上根K线的挂单是否成交（当前low <= 挂单价格）
       - 检查持仓是否触发止盈/止损
       - 取消未成交挂单
       - 计算新的挂单价格并创建新挂单

    Attributes:
        position_size: 单笔仓位金额（USDT）
        discount: 挂单折扣比例（默认0.001即0.1%）
        stop_loss_pct: 止损比例（默认5%）
        max_positions: 最大持仓数量

    Example:
        >>> strategy = Strategy16LimitEntry(
        ...     position_size=Decimal("1000"),
        ...     discount=0.001,
        ...     stop_loss_pct=5.0
        ... )
        >>> result = strategy.run_backtest(klines_df, initial_capital=10000)
    """

    STRATEGY_ID = 'strategy_16'
    STRATEGY_NAME = 'P5限价挂单入场'
    STRATEGY_VERSION = '1.0'

    def __init__(
        self,
        position_size: Decimal = Decimal("1000"),
        discount: float = 0.001,
        stop_loss_pct: float = 5.0,
        max_positions: int = 10
    ):
        """
        初始化策略16

        Args:
            position_size: 单笔仓位金额（USDT），默认1000
            discount: 挂单折扣比例，默认0.001（0.1%）
            stop_loss_pct: 止损比例，默认5.0%
            max_positions: 最大持仓数量，默认10
        """
        self.position_size = position_size
        self.discount = Decimal(str(discount))
        self.stop_loss_pct = stop_loss_pct
        self.max_positions = max_positions

        # 止盈条件
        self.ema_state_exit = EmaStateExit()

        # 状态管理
        self._pending_order: Optional[PendingOrder] = None  # 当前挂单（每次只挂1笔）
        self._holdings: Dict[str, Dict] = {}  # 持仓: order_id -> {buy_price, quantity, ...}
        self._completed_orders: List[Dict] = []  # 已完成交易
        self._available_capital: Decimal = Decimal("0")

        logger.info(
            f"初始化Strategy16LimitEntry: position_size={position_size}, "
            f"discount={discount}, stop_loss_pct={stop_loss_pct}, "
            f"max_positions={max_positions}"
        )

    def get_strategy_name(self) -> str:
        return self.STRATEGY_NAME

    def get_strategy_version(self) -> str:
        return self.STRATEGY_VERSION

    def get_required_indicators(self) -> List[str]:
        """返回所需的技术指标"""
        return ['ema7', 'ema25', 'ema99', 'p5', 'inertia_mid', 'cycle_phase']

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
        self._holdings.clear()
        self._completed_orders.clear()

        # 计算指标
        indicators = self._calculate_indicators(klines_df)

        # 统计
        total_buy_fills = 0
        total_sell_fills = 0
        total_stop_loss = 0
        total_take_profit = 0

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
                'inertia_mid': indicators['inertia_mid'].iloc[i],
                'cycle_phase': indicators['cycle_phase'].iloc[i],
            }

            # 获取上根K线的指标（用于判断挂单）
            prev_indicators = {
                'p5': indicators['p5'].iloc[i-1],
                'inertia_mid': indicators['inertia_mid'].iloc[i-1],
            }

            low = Decimal(str(kline['low']))
            high = Decimal(str(kline['high']))
            close = Decimal(str(kline['close']))
            prev_close = Decimal(str(prev_kline['close']))

            # === Step 1: 检查挂单是否成交 ===
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

                    # 释放冻结资金，扣除买入金额
                    # （冻结资金在创建挂单时已扣除，成交时不需要额外操作）

                    total_buy_fills += 1
                    logger.info(
                        f"买入成交: {order_id}, 价格: {self._pending_order.price:.2f}, "
                        f"数量: {self._pending_order.quantity:.6f}"
                    )
                else:
                    # 未成交，取消挂单，释放冻结资金
                    self._available_capital += self._pending_order.frozen_capital
                    self._pending_order.mark_cancelled()
                    logger.debug(f"挂单未成交，取消: {self._pending_order.order_id}")

                self._pending_order = None

            # === Step 2: 检查持仓是否触发止盈/止损 ===
            holdings_to_close = []
            for order_id, holding in self._holdings.items():
                buy_price = holding['buy_price']

                # 使用简单对象代替Order类（仅需id和metadata属性）
                class SimpleOrder:
                    def __init__(self, order_id, metadata=None):
                        self.id = order_id
                        self.metadata = metadata or {}
                        self.open_price = buy_price

                order = SimpleOrder(order_id, holding.get('metadata', {}))

                # 检查止损
                loss_rate = (float(low) / float(buy_price) - 1) * 100
                if loss_rate <= -self.stop_loss_pct:
                    # 止损触发
                    sell_price = buy_price * (1 - Decimal(str(self.stop_loss_pct)) / 100)
                    profit_loss = (sell_price - buy_price) * holding['quantity']
                    profit_rate = (sell_price / buy_price - 1) * 100

                    holdings_to_close.append({
                        'order_id': order_id,
                        'sell_price': sell_price,
                        'profit_loss': profit_loss,
                        'profit_rate': profit_rate,
                        'exit_reason': 'stop_loss',
                    })
                    total_stop_loss += 1
                    logger.info(
                        f"止损触发: {order_id}, 买入价: {buy_price:.2f}, "
                        f"卖出价: {sell_price:.2f}, 亏损: {profit_rate:.2f}%"
                    )
                    continue

                # 检查EMA状态止盈（先检查EMA指标是否有效）
                ema7_val = current_indicators.get('ema7')
                ema25_val = current_indicators.get('ema25')
                ema99_val = current_indicators.get('ema99')

                if (ema7_val is not None and ema25_val is not None and ema99_val is not None
                    and not np.isnan(ema7_val) and not np.isnan(ema25_val) and not np.isnan(ema99_val)):
                    exit_signal = self.ema_state_exit.check(
                        order=order,
                        kline={'low': float(low), 'high': float(high), 'close': float(close)},
                        indicators=current_indicators,
                        current_timestamp=timestamp
                    )
                    if exit_signal is not None:
                        # 止盈触发，以收盘价卖出
                        sell_price = close
                        profit_loss = (sell_price - buy_price) * holding['quantity']
                        profit_rate = (sell_price / buy_price - 1) * 100

                        # 保存更新后的metadata
                        holding['metadata'] = order.metadata

                        holdings_to_close.append({
                            'order_id': order_id,
                            'sell_price': sell_price,
                            'profit_loss': profit_loss,
                            'profit_rate': profit_rate,
                            'exit_reason': exit_signal.reason,
                        })
                        total_take_profit += 1
                        logger.info(
                            f"EMA状态止盈触发: {order_id}, 原因: {exit_signal.reason}, "
                            f"买入价: {buy_price:.2f}, 卖出价: {sell_price:.2f}, "
                            f"盈利: {profit_rate:.2f}%"
                        )

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
                    'profit_rate': float(close_info['profit_rate']),
                    'buy_timestamp': holding['buy_timestamp'],
                    'sell_timestamp': timestamp,
                    'exit_reason': close_info['exit_reason'],
                })

                del self._holdings[order_id]
                total_sell_fills += 1

            # === Step 3: 创建新的挂单 ===
            # 条件：有可用资金 且 持仓未满
            if (self._available_capital >= self.position_size and
                len(self._holdings) < self.max_positions):

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

                        # 创建挂单
                        quantity = self.position_size / order_price
                        self._pending_order = PendingOrder(
                            order_id=f"pending_{timestamp}_{i}",
                            price=order_price,
                            amount=self.position_size,
                            quantity=quantity,
                            status=PendingOrderStatus.PENDING,
                            side=PendingOrderSide.BUY,
                            frozen_capital=self.position_size,
                            kline_index=i,
                            created_at=timestamp,
                            metadata={
                                'base_price': float(base_price),
                                'p5': float(p5),
                                'close': float(close),
                                'mid_p5': float((p5 + inertia_mid) / 2),
                            }
                        )

                        # 冻结资金
                        self._available_capital -= self.position_size

                        logger.debug(
                            f"创建挂单: {self._pending_order.order_id}, "
                            f"价格: {order_price:.2f}, base_price: {base_price:.2f}"
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

        # P5计算
        deviation = ema25_calc.calculate_deviation_series(prices)
        _, ewma_std_series = ewma_calc.calculate_ewma_stats(deviation)
        z_p5 = -1.645
        p5_array = ema25_array * (1 + z_p5 * ewma_std_series)

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
            'inertia_mid': pd.Series(inertia_mid_array, index=klines_df.index),
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
        # 回测结束时，未成交挂单的冻结资金应视为可用
        if self._pending_order and self._pending_order.is_pending():
            final_capital += self._pending_order.frozen_capital

        return_rate = (float(final_capital) / float(initial_capital) - 1) * 100

        # 返回格式兼容 _convert_limit_order_result
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
        """生成买入信号（策略16使用限价挂单模式，此方法不使用）"""
        return []

    def generate_sell_signals(self, klines, indicators, open_orders):
        """生成卖出信号（策略16使用限价挂单模式，此方法不使用）"""
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
