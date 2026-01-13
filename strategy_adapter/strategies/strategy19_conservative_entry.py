"""
策略19：保守入场策略（动态复利仓位管理版本）

在策略16基础上增加保守入场控制：
- bear_warning周期禁止创建买入挂单
- 震荡期（consolidation）挂单金额倍增（默认3倍）
- 使用动态复利仓位管理：单笔金额 = 可用现金 / (max_positions - 持仓数)

核心逻辑：
1. 继承Strategy16LimitEntry所有功能
2. 在创建买入挂单前检查cycle_phase
3. bear_warning时跳过挂单创建
4. 使用DynamicPositionManager计算基础仓位金额
5. consolidation时在基础金额上应用multiplier

迭代编号: 041 (策略19-保守入场策略)
修改迭代: 043 (动态复利仓位管理)
创建日期: 2026-01-13
修改日期: 2026-01-13
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional

import pandas as pd
import numpy as np

from strategy_adapter.strategies.strategy16_limit_entry import Strategy16LimitEntry
from strategy_adapter.models import PendingOrder, PendingOrderStatus, PendingOrderSide
from strategy_adapter.core.position_manager import IPositionManager, DynamicPositionManager

logger = logging.getLogger(__name__)


class Strategy19ConservativeEntry(Strategy16LimitEntry):
    """
    策略19：保守入场策略（动态复利仓位管理版本）

    在策略16基础上增加入场控制：
    - bear_warning周期禁止挂单
    - 震荡期挂单金额倍增
    - 使用动态复利仓位管理

    与策略16的差异：
    - 策略16：固定仓位金额，所有周期均可挂单
    - 策略19：动态仓位计算，bear_warning跳过，consolidation金额×multiplier

    动态仓位公式：
        base_size = available_cash / (max_positions - current_positions)

    Attributes:
        position_manager: 仓位管理器实例
        consolidation_multiplier: 震荡期挂单金额倍数（默认3）

    Example:
        >>> from strategy_adapter.core.position_manager import DynamicPositionManager
        >>> pm = DynamicPositionManager()
        >>> strategy = Strategy19ConservativeEntry(
        ...     position_manager=pm,
        ...     consolidation_multiplier=3
        ... )
        >>> result = strategy.run_backtest(klines_df, initial_capital=10000)
    """

    STRATEGY_ID = 'strategy_19'
    STRATEGY_NAME = '保守入场策略'
    STRATEGY_VERSION = '2.0'  # 升级版本号

    def __init__(
        self,
        position_manager: IPositionManager = None,
        discount: float = 0.001,
        max_positions: int = 10,
        consolidation_multiplier: int = 3
    ):
        """
        初始化策略19

        Args:
            position_manager: 仓位管理器实例，默认使用DynamicPositionManager
            discount: 挂单折扣比例，默认0.001（0.1%）
            max_positions: 最大持仓数量，默认10
            consolidation_multiplier: 震荡期挂单金额倍数，默认3
        """
        # 使用默认的动态仓位管理器
        if position_manager is None:
            position_manager = DynamicPositionManager()

        self.position_manager = position_manager
        self.consolidation_multiplier = consolidation_multiplier

        # 不调用父类的__init__，因为我们不再使用固定的position_size
        # 直接初始化所需属性
        self.discount = Decimal(str(discount))
        self.max_positions = max_positions

        # 状态管理（复制自Strategy16）
        self._pending_order: Optional[PendingOrder] = None
        self._pending_sell_orders: Dict[str, Dict] = {}
        self._holdings: Dict[str, Dict] = {}
        self._completed_orders: List[Dict] = []
        self._available_capital: Decimal = Decimal("0")

        logger.info(
            f"初始化Strategy19ConservativeEntry: "
            f"position_manager={type(position_manager).__name__}, "
            f"discount={discount}, max_positions={max_positions}, "
            f"consolidation_multiplier={consolidation_multiplier}"
        )

    def get_extra_csv_headers(self) -> List[str]:
        """
        返回策略19特有的CSV表头

        Returns:
            List[str]: ['skipped_bear_warning', 'consolidation_multiplier']
        """
        return ['skipped_bear_warning', 'consolidation_multiplier']

    def _should_skip_entry(self, cycle_phase: Optional[str]) -> bool:
        """
        判断是否跳过入场

        Args:
            cycle_phase: 当前周期状态

        Returns:
            bool: True表示跳过入场，False表示允许入场
        """
        return cycle_phase == 'bear_warning'

    def _get_actual_position_size(self, cycle_phase: Optional[str]) -> Decimal:
        """
        获取实际挂单金额

        使用动态仓位管理器计算基础金额，然后根据周期应用倍数。

        Args:
            cycle_phase: 当前周期状态

        Returns:
            Decimal: 实际挂单金额，0表示跳过挂单
        """
        # 使用仓位管理器计算基础金额
        base_size = self.position_manager.calculate_position_size(
            available_cash=self._available_capital,
            max_positions=self.max_positions,
            current_positions=len(self._holdings)
        )

        # 返回0则跳过挂单
        if base_size == Decimal("0"):
            return Decimal("0")

        # 应用震荡期倍数
        if cycle_phase == 'consolidation':
            return base_size * self.consolidation_multiplier

        return base_size

    def run_backtest(
        self,
        klines_df: pd.DataFrame,
        initial_capital: Decimal = Decimal("10000")
    ) -> Dict:
        """
        执行回测

        重写父类方法，增加bear_warning跳过和震荡期金额倍增逻辑

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
        skipped_bear_warning = 0  # 统计跳过的bear_warning次数

        # 逐K线处理
        for i in range(1, len(klines_df)):
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

            # === Step 0: 检查卖出挂单是否成交 ===
            sell_orders_to_remove = []
            for order_id, sell_order in self._pending_sell_orders.items():
                if order_id not in self._holdings:
                    sell_orders_to_remove.append(order_id)
                    continue

                sell_price = Decimal(str(sell_order['price']))

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

                    self._available_capital += holding['amount'] + profit_loss

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
                    sell_orders_to_remove.append(order_id)
                    logger.debug(f"卖出挂单未成交，取消: {order_id}")

            for order_id in sell_orders_to_remove:
                if order_id in self._pending_sell_orders:
                    del self._pending_sell_orders[order_id]

            # === Step 1: 检查买入挂单是否成交 ===
            if self._pending_order and self._pending_order.is_pending():
                if low <= self._pending_order.price:
                    self._pending_order.mark_filled(timestamp)
                    order_id = self._pending_order.order_id

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
                    self._available_capital += self._pending_order.frozen_capital
                    self._pending_order.mark_cancelled()
                    logger.debug(f"买入挂单未成交，取消: {self._pending_order.order_id}")

                self._pending_order = None

            # === Step 2: 为持仓创建卖出挂单 ===
            for order_id, holding in self._holdings.items():
                if order_id in self._pending_sell_orders:
                    continue

                ema25_val = current_indicators.get('ema25')
                p95_val = current_indicators.get('p95')
                cycle_phase = current_indicators.get('cycle_phase')

                if (ema25_val is None or np.isnan(ema25_val) or
                    p95_val is None or np.isnan(p95_val) or
                    cycle_phase is None):
                    continue

                ema25 = Decimal(str(ema25_val))
                p95 = Decimal(str(p95_val))

                if cycle_phase in ('bear_warning', 'bear_strong'):
                    sell_price = ema25
                    reason = f"EMA25挂单止盈 (EMA25={float(ema25):.2f})"
                elif cycle_phase == 'consolidation':
                    sell_price = (p95 + ema25) / 2
                    reason = f"震荡期挂单止盈 ((P95+EMA25)/2={float(sell_price):.2f})"
                else:
                    sell_price = p95
                    reason = f"P95挂单止盈 (P95={float(p95):.2f})"

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

            # === Step 3: 创建新的买入挂单 (策略19核心修改) ===
            cycle_phase = current_indicators.get('cycle_phase')

            # 策略19: bear_warning时跳过挂单
            if self._should_skip_entry(cycle_phase):
                skipped_bear_warning += 1
                logger.debug(f"bear_warning周期，跳过买入挂单创建")
                continue

            # 策略19: 根据周期获取实际挂单金额（使用动态仓位管理器）
            actual_position_size = self._get_actual_position_size(cycle_phase)

            # 动态仓位管理器返回0表示跳过挂单（资金不足或持仓已满）
            if actual_position_size == Decimal("0"):
                logger.debug(f"动态仓位计算返回0，跳过买入挂单创建")
                continue

            # 条件：有足够可用资金
            if self._available_capital >= actual_position_size:

                p5_val = current_indicators['p5']
                mid_val = current_indicators['inertia_mid']

                if not (np.isnan(p5_val) or np.isnan(mid_val)):
                    p5 = Decimal(str(p5_val))
                    inertia_mid = Decimal(str(mid_val))

                    if p5 > 0 and inertia_mid > 0:
                        base_price = self._calculate_base_price(p5, close, inertia_mid)
                        order_price = self._calculate_order_price(base_price)

                        quantity = actual_position_size / order_price
                        self._pending_order = PendingOrder(
                            order_id=f"pending_{timestamp}_{i}",
                            price=order_price,
                            amount=actual_position_size,
                            quantity=quantity,
                            status=PendingOrderStatus.PENDING,
                            side=PendingOrderSide.BUY,
                            frozen_capital=actual_position_size,
                            kline_index=i,
                            created_at=timestamp,
                            metadata={
                                'base_price': float(base_price),
                                'p5': float(p5),
                                'close': float(close),
                                'mid_p5': float((p5 + inertia_mid) / 2),
                                'cycle_phase': cycle_phase,
                                'position_multiplier': self.consolidation_multiplier if cycle_phase == 'consolidation' else 1,
                            }
                        )

                        self._available_capital -= actual_position_size

                        logger.debug(
                            f"创建买入挂单: {self._pending_order.order_id}, "
                            f"价格: {order_price:.2f}, 金额: {actual_position_size}, "
                            f"周期: {cycle_phase}"
                        )

        # 生成回测结果
        last_close_price = Decimal(str(klines_df['close'].iloc[-1]))
        start_timestamp = int(klines_df.index[0].timestamp() * 1000)
        end_timestamp = int(klines_df.index[-1].timestamp() * 1000)

        result = self._generate_result(
            initial_capital, len(klines_df), last_close_price,
            start_timestamp, end_timestamp
        )

        # 添加策略19特有统计（同时添加到顶层和strategy19_stats）
        result['skipped_bear_warning'] = skipped_bear_warning
        result['consolidation_multiplier'] = self.consolidation_multiplier
        result['strategy19_stats'] = {
            'skipped_bear_warning': skipped_bear_warning,
            'consolidation_multiplier': self.consolidation_multiplier,
        }

        logger.info(
            f"策略19回测完成: 跳过bear_warning={skipped_bear_warning}次, "
            f"震荡期倍数={self.consolidation_multiplier}"
        )

        return result
