"""
策略17：上涨预警入场 + EMA状态止盈

本模块实现策略17的上涨预警入场机制：
- 入场：检测cycle_phase从consolidation首次变为bull_warning，下一根K线open买入
- 止盈：EMA状态止盈（强势上涨/强势下跌/震荡下跌不同条件）
- 止损：可配置比例止损（默认5%）

核心逻辑（避免后验偏差）：
1. 当前K线结束时：检测cycle_phase是否首次进入bull_warning
2. 如果触发入场信号：标记下一根K线以open价格买入
3. 下一根K线开始时：执行买入

迭代编号: 038 (策略17-上涨预警入场)
创建日期: 2026-01-12
关联需求: FP-038-001, FP-038-002, FP-038-003
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Any

import pandas as pd
import numpy as np

from strategy_adapter.interfaces import IStrategy
from strategy_adapter.exits import EmaStateExit

logger = logging.getLogger(__name__)


class Strategy17BullWarningEntry(IStrategy):
    """
    策略17：上涨预警入场 + EMA状态止盈

    与策略16的核心差异：
    - 策略16：P5限价挂单入场（等待价格回调到支撑位）
    - 策略17：上涨预警信号入场（捕捉趋势启动的第一时间）

    工作流程：
    1. 计算每根K线的cycle_phase（基于β宏观周期状态机）
    2. 检测cycle_phase从consolidation首次变为bull_warning
    3. 触发信号后，在下一根K线的open价格买入
    4. 持仓期间检测止盈/止损条件

    Attributes:
        position_size: 单笔仓位金额（USDT）
        stop_loss_pct: 止损比例（默认5%）
        max_positions: 最大持仓数量

    Example:
        >>> strategy = Strategy17BullWarningEntry(
        ...     position_size=Decimal("1000"),
        ...     stop_loss_pct=5.0
        ... )
        >>> result = strategy.run_backtest(klines_df, initial_capital=10000)
    """

    STRATEGY_ID = 'strategy_17'
    STRATEGY_NAME = '上涨预警入场'
    STRATEGY_VERSION = '1.0'

    def __init__(
        self,
        position_size: Decimal = Decimal("1000"),
        stop_loss_pct: float = 5.0,
        max_positions: int = 10
    ):
        """
        初始化策略17

        Args:
            position_size: 单笔仓位金额（USDT），默认1000
            stop_loss_pct: 止损比例，默认5.0%
            max_positions: 最大持仓数量，默认10
        """
        self.position_size = position_size
        self.stop_loss_pct = stop_loss_pct
        self.max_positions = max_positions

        # 止盈条件
        self.ema_state_exit = EmaStateExit()

        # 状态管理
        self._pending_entry: bool = False  # 是否有待执行的入场信号
        self._holdings: Dict[str, Dict] = {}  # 持仓: order_id -> {buy_price, quantity, ...}
        self._completed_orders: List[Dict] = []  # 已完成交易
        self._available_capital: Decimal = Decimal("0")

        logger.info(
            f"初始化Strategy17BullWarningEntry: position_size={position_size}, "
            f"stop_loss_pct={stop_loss_pct}, max_positions={max_positions}"
        )

    def get_strategy_name(self) -> str:
        return self.STRATEGY_NAME

    def get_strategy_version(self) -> str:
        return self.STRATEGY_VERSION

    def get_required_indicators(self) -> List[str]:
        """返回所需的技术指标"""
        return ['ema7', 'ema25', 'ema99', 'cycle_phase']

    def _detect_entry_signal(self, prev_phase: str, curr_phase: str) -> bool:
        """
        检测是否触发入场信号

        入场条件：cycle_phase从consolidation首次变为bull_warning

        Args:
            prev_phase: 前一根K线的cycle_phase
            curr_phase: 当前K线的cycle_phase

        Returns:
            bool: True表示触发入场信号
        """
        return (
            curr_phase == 'bull_warning' and
            prev_phase == 'consolidation'
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
        self._pending_entry = False
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
        for i in range(1, len(klines_df)):  # 从第1根开始（需要前一根判断状态转变）
            kline = klines_df.iloc[i]
            prev_kline = klines_df.iloc[i-1]
            timestamp = int(klines_df.index[i].timestamp() * 1000)

            # 获取当前K线的指标
            current_indicators = {
                'ema7': indicators['ema7'].iloc[i],
                'ema25': indicators['ema25'].iloc[i],
                'ema99': indicators['ema99'].iloc[i],
                'cycle_phase': indicators['cycle_phase'].iloc[i],
            }

            # 获取前一根K线的cycle_phase
            prev_phase = indicators['cycle_phase'].iloc[i-1]
            curr_phase = current_indicators['cycle_phase']

            open_price = Decimal(str(kline['open']))
            low = Decimal(str(kline['low']))
            high = Decimal(str(kline['high']))
            close = Decimal(str(kline['close']))

            # === Step 1: 执行待入场信号 ===
            if self._pending_entry:
                # 检查是否有可用资金和持仓空间
                if (self._available_capital >= self.position_size and
                    len(self._holdings) < self.max_positions):

                    # 以当前K线的open价格买入
                    buy_price = open_price
                    quantity = self.position_size / buy_price
                    order_id = f"order_{timestamp}_{i}"

                    # 记录持仓
                    self._holdings[order_id] = {
                        'buy_price': buy_price,
                        'quantity': quantity,
                        'amount': self.position_size,
                        'buy_timestamp': timestamp,
                        'kline_index': i,
                        'metadata': {},
                    }

                    # 扣除资金
                    self._available_capital -= self.position_size

                    total_buy_fills += 1
                    logger.info(
                        f"买入成交: {order_id}, 价格: {buy_price:.2f}, "
                        f"数量: {quantity:.6f}, 触发原因: 上涨预警信号"
                    )

                self._pending_entry = False

            # === Step 2: 检查持仓是否触发止盈/止损 ===
            holdings_to_close = []
            for order_id, holding in self._holdings.items():
                buy_price = holding['buy_price']

                # 使用简单对象代替Order类（仅需id和metadata属性）
                class SimpleOrder:
                    def __init__(self, order_id, buy_price, metadata=None):
                        self.id = order_id
                        self.open_price = buy_price
                        self.metadata = metadata or {}

                order = SimpleOrder(order_id, buy_price, holding.get('metadata', {}))

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

            # === Step 3: 检测新的入场信号 ===
            # 条件：有可用资金、持仓未满、检测到状态转变
            if (self._available_capital >= self.position_size and
                len(self._holdings) < self.max_positions and
                not self._pending_entry):

                if self._detect_entry_signal(prev_phase, curr_phase):
                    self._pending_entry = True
                    logger.info(
                        f"入场信号触发: K线索引={i}, timestamp={timestamp}, "
                        f"phase={prev_phase}→{curr_phase}, 将在下一根K线open买入"
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

        # 计算最终资产（可用资金 + 持仓市值）
        final_capital = self._available_capital
        for holding in self._holdings.values():
            final_capital += holding['amount']

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
        """生成买入信号（策略17使用上涨预警入场模式，此方法不使用）"""
        return []

    def generate_sell_signals(self, klines, indicators, open_orders):
        """生成卖出信号（策略17使用上涨预警入场模式，此方法不使用）"""
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
