"""
分批止盈优化策略（策略15）

本模块实现策略15的核心机制：
- 价格分布：沿用策略14（首档base_price，第2档低first_gap(4%)，后续每档低interval(1%)）
- 金额分布：沿用策略14（1×, 3×, 9×, 27×, 剩余全部可用资金）
- 快速止损：3%
- 分批止盈：5档（2%, 3%, 4%, 5%, 6%），每档20%仓位
- 持仓合并：同价格持仓合并为单一订单

与策略14的核心差异：
- 止损：策略14为6%，策略15为3%
- 止盈：策略14为2%全仓单一价位，策略15为2%~6%分批5档
- 持仓管理：策略14独立持仓，策略15同价合并

迭代编号: 031 (策略15-分批止盈优化策略)
创建日期: 2026-01-11
"""

import logging
import uuid
from decimal import Decimal
from typing import Dict, List, Any
from collections import defaultdict

import pandas as pd

from strategy_adapter.interfaces import IStrategy
from strategy_adapter.models import Order
from strategy_adapter.core.limit_order_manager import LimitOrderManager
from strategy_adapter.core.limit_order_price_calculator import LimitOrderPriceCalculator

logger = logging.getLogger(__name__)


class SplitTakeProfitStrategy(IStrategy):
    """
    分批止盈优化策略（策略15）

    价格分布（沿用策略14）：
    - 第1档: base_price × (1 - first_order_discount)
    - 第2档: base_price × (1 - first_order_discount - first_gap)
    - 第3档: base_price × (1 - first_order_discount - first_gap - interval)
    - 第4档: base_price × (1 - first_order_discount - first_gap - 2×interval)
    - 第5档: base_price × (1 - first_order_discount - first_gap - 3×interval)

    金额分布（沿用策略14）：
    - 第1档: base_amount (1×)
    - 第2档: base_amount × 3 (3×)
    - 第3档: base_amount × 9 (9×)
    - 第4档: base_amount × 27 (27×)
    - 第5档: 剩余全部可用资金

    止损止盈（策略15新增）：
    - 快速止损: 3%
    - 分批止盈: 5档（2%, 3%, 4%, 5%, 6%），每档20%仓位
    """

    STRATEGY_ID = 'strategy_15'
    STRATEGY_NAME = '分批止盈优化策略'
    STRATEGY_VERSION = '1.0'

    def __init__(
        self,
        # === 沿用策略14参数 ===
        base_amount: Decimal = Decimal("100"),
        multiplier: float = 3.0,
        order_count: int = 5,
        first_gap: float = 0.04,
        interval: float = 0.01,
        first_order_discount: float = 0.003,
        # === 策略15新增参数 ===
        stop_loss_rate: float = 0.03,      # 快速止损3%
        tp_levels: int = 5,                 # 止盈档位数
        first_tp_rate: float = 0.02,        # 首档止盈2%
        tp_interval: float = 0.01,          # 止盈间隔1%
    ):
        """
        初始化分批止盈优化策略

        Args:
            base_amount: 首单金额（USDT），默认100
            multiplier: 金额倍数，默认3.0
            order_count: 挂单数量，默认5
            first_gap: 首档间隔，默认0.04（4%）
            interval: 后续间隔，默认0.01（1%）
            first_order_discount: 首笔折扣，默认0.003（0.3%）
            stop_loss_rate: 止损比例，默认0.03（3%）
            tp_levels: 止盈档位数，默认5
            first_tp_rate: 首档止盈比例，默认0.02（2%）
            tp_interval: 止盈间隔，默认0.01（1%）
        """
        self.base_amount = base_amount
        self.multiplier = Decimal(str(multiplier))
        self.order_count = order_count
        self.first_gap = Decimal(str(first_gap))
        self.interval = Decimal(str(interval))
        self.first_order_discount = first_order_discount
        self.stop_loss_rate = stop_loss_rate
        self.tp_levels = tp_levels
        self.first_tp_rate = first_tp_rate
        self.tp_interval = tp_interval

        # 初始化组件
        self.order_manager = LimitOrderManager(position_size=base_amount)
        self.price_calculator = LimitOrderPriceCalculator(
            order_count=order_count,
            order_interval=float(interval),
            first_order_discount=first_order_discount
        )

        # 持仓管理（扩展数据结构）
        self._holdings: Dict[str, Dict] = {}
        self._completed_orders: List[Dict] = []

        # 止盈卖单管理
        self._tp_sell_orders: Dict[str, Dict] = {}  # order_id -> tp_sell_order

        # 预计算前4档固定金额
        self._fixed_amounts = self._calculate_fixed_amounts()

        logger.info(
            f"初始化SplitTakeProfitStrategy: base_amount={base_amount}, "
            f"multiplier={multiplier}, order_count={order_count}, "
            f"first_gap={first_gap}, interval={interval}, "
            f"stop_loss_rate={stop_loss_rate}, tp_levels={tp_levels}, "
            f"first_tp_rate={first_tp_rate}, tp_interval={tp_interval}"
        )
        logger.info(f"前4档固定金额: {self._fixed_amounts}")
        logger.info(f"前4档总金额: {sum(self._fixed_amounts)}")

    def _calculate_fixed_amounts(self) -> List[Decimal]:
        """
        计算前4档固定金额

        Returns:
            List[Decimal]: [100, 300, 900, 2700] (multiplier=3, base=100时)
        """
        amounts = []
        for i in range(self.order_count - 1):  # 前4档
            amount = self.base_amount * (self.multiplier ** i)
            amounts.append(amount)
        return amounts

    def _calculate_prices(self, base_price: Decimal) -> List[Decimal]:
        """
        计算5档挂单价格（沿用策略14）

        价格分布：
        - 第1档: base_price × (1 - first_order_discount)
        - 第2档: base_price × (1 - first_order_discount - first_gap)
        - 第3档及后续: base_price × (1 - first_order_discount - first_gap - (i-1)×interval)

        Args:
            base_price: 基础价格（未折扣的原始价格）

        Returns:
            List[Decimal]: 5档价格列表
        """
        prices = []
        first_discount = Decimal(str(self.first_order_discount))

        for i in range(self.order_count):
            if i == 0:
                # 第1档: base_price × (1 - first_order_discount)
                discount = first_discount
            elif i == 1:
                # 第2档: base_price × (1 - first_order_discount - first_gap)
                discount = first_discount + self.first_gap
            else:
                # 第3-5档: base_price × (1 - first_order_discount - first_gap - (i-1)×interval)
                discount = first_discount + self.first_gap + Decimal(str(i - 1)) * self.interval

            price = base_price * (Decimal("1") - discount)
            prices.append(price)
        return prices

    def _calculate_amounts(self, available_capital: Decimal) -> List[Decimal]:
        """
        计算5档挂单金额（沿用策略14）

        Args:
            available_capital: 当前可用资金

        Returns:
            List[Decimal]: 5档金额列表，第5档为剩余全部可用资金
        """
        amounts = self._fixed_amounts.copy()

        # 计算第5档金额 = 可用资金 - 前4档总和
        fixed_total = sum(self._fixed_amounts)
        remaining = available_capital - fixed_total

        # 确保第5档金额至少为0
        if remaining < Decimal("0"):
            remaining = Decimal("0")

        amounts.append(remaining)
        return amounts

    def _calculate_tp_prices(self, buy_price: Decimal) -> List[Decimal]:
        """
        计算5档止盈价格

        Args:
            buy_price: 买入价格

        Returns:
            List[Decimal]: [buy_price*1.02, buy_price*1.03, ..., buy_price*1.06]
        """
        tp_prices = []
        first_tp = Decimal(str(self.first_tp_rate))
        tp_interval = Decimal(str(self.tp_interval))

        for i in range(self.tp_levels):
            tp_rate = first_tp + Decimal(str(i)) * tp_interval
            tp_price = buy_price * (Decimal("1") + tp_rate)
            tp_prices.append(tp_price)

        return tp_prices

    def _merge_holdings(self):
        """
        合并同价持仓

        将相同买入价格的持仓合并为单一订单
        """
        if not self._holdings:
            return

        # 按价格分组
        price_groups = defaultdict(list)
        for order_id, holding in self._holdings.items():
            price_key = str(holding['buy_price'])
            price_groups[price_key].append((order_id, holding))

        # 合并同价持仓
        merged_holdings = {}
        for price_key, holdings in price_groups.items():
            if len(holdings) == 1:
                # 只有一个持仓，不需要合并
                order_id, holding = holdings[0]
                merged_holdings[order_id] = holding
            else:
                # 多个持仓，需要合并
                merged_order_id = f"merged_{uuid.uuid4().hex[:8]}"
                buy_price = holdings[0][1]['buy_price']
                total_quantity = sum(h[1]['quantity'] for h in holdings)
                total_amount = sum(h[1]['amount'] for h in holdings)
                merged_from = [h[0] for h in holdings]

                # 使用最早的买入时间
                earliest_timestamp = min(h[1]['buy_timestamp'] for h in holdings)
                earliest_kline = min(h[1]['kline_index'] for h in holdings)

                merged_holdings[merged_order_id] = {
                    'buy_price': buy_price,
                    'quantity': total_quantity,
                    'amount': total_amount,
                    'buy_timestamp': earliest_timestamp,
                    'kline_index': earliest_kline,
                    'remaining_quantity': total_quantity,
                    'tp_quantity_per_level': total_quantity / Decimal(str(self.tp_levels)),
                    'tp_levels_filled': [False] * self.tp_levels,
                    'merged_from': merged_from,
                }

                logger.debug(
                    f"合并持仓: {len(holdings)}笔 -> {merged_order_id}, "
                    f"价格={buy_price}, 总量={total_quantity}"
                )

        self._holdings = merged_holdings

    def _create_tp_sell_orders(self, kline_index: int):
        """
        为所有持仓创建止盈卖单

        Args:
            kline_index: 当前K线索引
        """
        for order_id, holding in self._holdings.items():
            if 'tp_levels_filled' not in holding:
                # 初始化止盈字段（兼容旧持仓）
                holding['remaining_quantity'] = holding['quantity']
                holding['tp_quantity_per_level'] = holding['quantity'] / Decimal(str(self.tp_levels))
                holding['tp_levels_filled'] = [False] * self.tp_levels

            buy_price = holding['buy_price']
            tp_prices = self._calculate_tp_prices(buy_price)
            tp_quantity = holding['tp_quantity_per_level']

            # 为每个未成交的档位创建卖单
            for level in range(self.tp_levels):
                if not holding['tp_levels_filled'][level]:
                    sell_order_id = f"tp_{order_id}_L{level}"

                    # 检查是否已存在
                    if sell_order_id not in self._tp_sell_orders:
                        self._tp_sell_orders[sell_order_id] = {
                            'order_id': sell_order_id,
                            'parent_order_id': order_id,
                            'tp_level': level,
                            'price': tp_prices[level],
                            'quantity': tp_quantity,
                            'status': 'pending',
                            'created_kline': kline_index,
                        }

    def _check_tp_sell_fills(self, high: Decimal, kline_index: int, timestamp: int) -> List[Dict]:
        """
        检查止盈卖单是否成交

        Args:
            high: 当前K线最高价
            kline_index: 当前K线索引
            timestamp: 当前时间戳

        Returns:
            List[Dict]: 成交的卖单列表
        """
        sell_fills = []
        orders_to_remove = []

        for sell_order_id, tp_order in self._tp_sell_orders.items():
            if tp_order['status'] == 'pending' and high >= tp_order['price']:
                parent_order_id = tp_order['parent_order_id']

                if parent_order_id not in self._holdings:
                    orders_to_remove.append(sell_order_id)
                    continue

                holding = self._holdings[parent_order_id]
                tp_level = tp_order['tp_level']

                # 标记该档位已成交
                holding['tp_levels_filled'][tp_level] = True
                holding['remaining_quantity'] -= tp_order['quantity']
                tp_order['status'] = 'filled'

                # 计算盈亏
                buy_price = holding['buy_price']
                sell_price = tp_order['price']
                quantity = tp_order['quantity']
                profit_loss = (sell_price - buy_price) * quantity
                profit_rate = float(profit_loss / (buy_price * quantity) * 100)

                # 释放资金
                released_capital = buy_price * quantity + profit_loss
                self.order_manager._frozen_capital -= buy_price * quantity
                self.order_manager._available_capital += released_capital

                sell_fills.append({
                    'order_id': sell_order_id,
                    'parent_order_id': parent_order_id,
                    'tp_level': tp_level,
                    'buy_price': buy_price,
                    'sell_price': sell_price,
                    'quantity': quantity,
                    'profit_loss': profit_loss,
                    'profit_rate': profit_rate,
                    'timestamp': timestamp,
                    'kline_index': kline_index,
                    'close_reason': f'take_profit_L{tp_level}',
                })

                self._completed_orders.append({
                    'buy_order_id': parent_order_id,
                    'sell_order_id': sell_order_id,
                    'tp_level': tp_level,
                    'buy_price': float(buy_price),
                    'sell_price': float(sell_price),
                    'quantity': float(quantity),
                    'profit_loss': float(profit_loss),
                    'profit_rate': profit_rate,
                    'buy_timestamp': holding['buy_timestamp'],
                    'sell_timestamp': timestamp,
                    'close_reason': f'take_profit_L{tp_level}',
                })

                orders_to_remove.append(sell_order_id)

                logger.debug(
                    f"止盈成交 L{tp_level}: {parent_order_id}, "
                    f"盈亏: {profit_loss:.4f} ({profit_rate:.2f}%)"
                )

                # 如果全部档位已成交，从持仓移除
                if all(holding['tp_levels_filled']):
                    del self._holdings[parent_order_id]
                    logger.debug(f"持仓全部止盈完成: {parent_order_id}")

        # 移除已成交的卖单
        for sell_order_id in orders_to_remove:
            if sell_order_id in self._tp_sell_orders:
                del self._tp_sell_orders[sell_order_id]

        return sell_fills

    def _check_stop_loss(self, low: Decimal, kline_index: int, timestamp: int) -> List[Dict]:
        """
        检查止损触发（3%快速止损）

        Args:
            low: 当前K线最低价
            kline_index: 当前K线索引
            timestamp: 当前时间戳

        Returns:
            List[Dict]: 止损成交列表
        """
        sell_fills = []
        holdings_to_stop_loss = []

        for order_id, holding in self._holdings.items():
            buy_price = holding['buy_price']
            stop_loss_price = buy_price * (Decimal("1") - Decimal(str(self.stop_loss_rate)))

            if low <= stop_loss_price:
                holdings_to_stop_loss.append((order_id, holding, stop_loss_price))

        for order_id, holding, sell_price in holdings_to_stop_loss:
            buy_price = holding['buy_price']
            quantity = holding['remaining_quantity']  # 使用剩余数量

            profit_loss = (sell_price - buy_price) * quantity
            profit_rate = float(profit_loss / (buy_price * quantity) * 100)

            # 释放资金（只释放剩余仓位的资金）
            released_capital = buy_price * quantity + profit_loss
            self.order_manager._frozen_capital -= buy_price * quantity
            self.order_manager._available_capital += released_capital

            sell_fills.append({
                'order_id': f"sl_{order_id}",
                'parent_order_id': order_id,
                'buy_price': buy_price,
                'sell_price': sell_price,
                'quantity': quantity,
                'profit_loss': profit_loss,
                'profit_rate': profit_rate,
                'timestamp': timestamp,
                'kline_index': kline_index,
                'close_reason': 'stop_loss',
            })

            self._completed_orders.append({
                'buy_order_id': order_id,
                'sell_order_id': f"sl_{order_id}",
                'buy_price': float(buy_price),
                'sell_price': float(sell_price),
                'quantity': float(quantity),
                'profit_loss': float(profit_loss),
                'profit_rate': profit_rate,
                'buy_timestamp': holding['buy_timestamp'],
                'sell_timestamp': timestamp,
                'close_reason': 'stop_loss',
            })

            # 取消该持仓的所有止盈卖单
            tp_orders_to_cancel = [
                sell_order_id for sell_order_id, tp_order in self._tp_sell_orders.items()
                if tp_order['parent_order_id'] == order_id
            ]
            for sell_order_id in tp_orders_to_cancel:
                del self._tp_sell_orders[sell_order_id]

            del self._holdings[order_id]

            logger.debug(
                f"止损成交: {order_id}, 盈亏: {profit_loss:.4f} ({profit_rate:.2f}%)"
            )

        return sell_fills

    def get_total_required_capital(self) -> Decimal:
        """计算前4档所需资金"""
        return sum(self._fixed_amounts)

    def initialize(self, initial_capital: Decimal) -> None:
        """初始化策略"""
        self.order_manager.initialize(initial_capital)
        self._holdings.clear()
        self._completed_orders.clear()
        self._tp_sell_orders.clear()
        logger.info(f"SplitTakeProfitStrategy初始化完成，初始资金: {initial_capital}")

    def get_strategy_name(self) -> str:
        return self.STRATEGY_NAME

    def get_strategy_version(self) -> str:
        return self.STRATEGY_VERSION

    def get_required_indicators(self) -> List[str]:
        return ['p5', 'inertia_mid']

    def _get_base_price(self, p5: Decimal, mid: Decimal, close: Decimal) -> Decimal:
        """
        计算基础价格（未折扣的原始价格）

        Args:
            p5: P5指标
            mid: 惯性中线
            close: 当前收盘价

        Returns:
            Decimal: 基础价格（不含折扣，折扣在_calculate_prices中应用）
        """
        if mid < p5:
            base_price = (p5 + mid) / Decimal("2")
        else:
            base_price = p5

        # 应用close上限约束
        base_price = min(base_price, close)

        return base_price

    def process_kline(
        self,
        kline_index: int,
        kline: Dict[str, Any],
        indicators: Dict[str, Any],
        timestamp: int
    ) -> Dict[str, List[Dict]]:
        """
        处理单根K线（策略15的核心方法）

        流程：
        1. 检查上一根K线的买入挂单是否成交
        2. 合并同价持仓
        3. 检查止盈卖单是否成交
        4. 检查持仓是否达到止损条件
        5. 更新/创建止盈卖单
        6. 取消未成交的买入挂单
        7. 创建新的买入挂单
        """
        result = {
            'buy_fills': [],
            'sell_fills': [],
            'orders_placed': 0,
            'orders_cancelled': 0,
            'insufficient_capital_count': 0,
        }

        low = Decimal(str(kline['low']))
        high = Decimal(str(kline['high']))

        # === Step 1: 检查买入挂单是否成交 ===
        pending_buy_orders = self.order_manager.get_pending_buy_orders()
        for order in pending_buy_orders:
            if self.order_manager.check_buy_order_fill(order, low, high):
                filled_order = self.order_manager.fill_buy_order(order.order_id, timestamp)
                if filled_order:
                    self._holdings[filled_order.order_id] = {
                        'buy_price': filled_order.price,
                        'quantity': filled_order.quantity,
                        'amount': filled_order.amount,
                        'buy_timestamp': timestamp,
                        'kline_index': kline_index,
                        'remaining_quantity': filled_order.quantity,
                        'tp_quantity_per_level': filled_order.quantity / Decimal(str(self.tp_levels)),
                        'tp_levels_filled': [False] * self.tp_levels,
                        'merged_from': [],
                    }

                    result['buy_fills'].append({
                        'order_id': filled_order.order_id,
                        'price': filled_order.price,
                        'quantity': filled_order.quantity,
                        'amount': filled_order.amount,
                        'timestamp': timestamp,
                        'kline_index': kline_index,
                    })

                    logger.debug(
                        f"买入成交: {filled_order.order_id}, "
                        f"价格: {filled_order.price}, 金额: {filled_order.amount}"
                    )

        # === Step 2: 合并同价持仓 ===
        self._merge_holdings()

        # === Step 3: 检查止盈卖单成交 ===
        tp_fills = self._check_tp_sell_fills(high, kline_index, timestamp)
        result['sell_fills'].extend(tp_fills)

        # === Step 4: 检查持仓止损 ===
        sl_fills = self._check_stop_loss(low, kline_index, timestamp)
        result['sell_fills'].extend(sl_fills)

        # === Step 5: 更新/创建止盈卖单 ===
        self._create_tp_sell_orders(kline_index)

        # === Step 6: 取消所有未成交的买入挂单 ===
        pending_before = len(self.order_manager.get_pending_buy_orders())
        self.order_manager.cancel_all_buy_orders()
        result['orders_cancelled'] = pending_before

        # === Step 7: 创建新的买入挂单 ===
        p5 = Decimal(str(indicators.get('p5', 0)))
        inertia_mid = Decimal(str(indicators.get('inertia_mid', 0)))
        close = Decimal(str(kline['close']))

        if p5 > 0 and inertia_mid > 0:
            # 计算基础价格
            base_price = self._get_base_price(p5, inertia_mid, close)

            # 计算5档价格
            buy_prices = self._calculate_prices(base_price)

            # 计算5档金额（第5档使用剩余可用资金）
            available = self.order_manager._available_capital
            buy_amounts = self._calculate_amounts(available)

            # 创建挂单
            for i, (price, amount) in enumerate(zip(buy_prices, buy_amounts)):
                if amount <= Decimal("0"):
                    result['insufficient_capital_count'] += 1
                    continue

                order = self.order_manager.create_buy_order(
                    price=price,
                    kline_index=kline_index,
                    timestamp=timestamp,
                    amount=amount
                )
                if order:
                    result['orders_placed'] += 1
                else:
                    result['insufficient_capital_count'] += 1

        return result

    def get_statistics(self) -> Dict:
        """获取策略统计信息"""
        manager_stats = self.order_manager.get_statistics()

        total_holdings = len(self._holdings)
        total_completed = len(self._completed_orders)

        total_profit_loss = sum(
            order.get('profit_loss', 0) for order in self._completed_orders
        )
        winning_trades = sum(
            1 for order in self._completed_orders
            if order.get('profit_loss', 0) > 0
        )
        win_rate = winning_trades / total_completed * 100 if total_completed > 0 else 0

        # 分批止盈统计
        tp_by_level = {}
        for level in range(self.tp_levels):
            tp_count = sum(
                1 for order in self._completed_orders
                if order.get('close_reason', '').startswith('take_profit_L')
                and order.get('tp_level') == level
            )
            tp_by_level[f'tp_level_{level}'] = tp_count

        return {
            **manager_stats,
            'holdings_count': total_holdings,
            'completed_trades': total_completed,
            'total_profit_loss': total_profit_loss,
            'winning_trades': winning_trades,
            'win_rate': win_rate,
            **tp_by_level,
        }

    def get_completed_orders(self) -> List[Dict]:
        """获取已完成的交易记录"""
        return self._completed_orders.copy()

    def get_holdings(self) -> Dict[str, Dict]:
        """获取当前持仓"""
        return self._holdings.copy()

    # === IStrategy 接口实现（用于兼容性）===

    def generate_buy_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series]
    ) -> List[Dict]:
        """策略15不使用传统的信号生成方式"""
        return []

    def generate_sell_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series],
        open_orders: List[Order]
    ) -> List[Dict]:
        """策略15不使用传统的信号生成方式"""
        return []

    def calculate_position_size(
        self,
        signal: Dict,
        available_capital: Decimal,
        current_price: Decimal
    ) -> Decimal:
        """返回首单金额"""
        return self.base_amount

    def should_stop_loss(
        self,
        order: Order,
        current_price: Decimal,
        current_timestamp: int
    ) -> bool:
        """策略15在process_kline中处理止损"""
        return False

    def should_take_profit(
        self,
        order: Order,
        current_price: Decimal,
        current_timestamp: int
    ) -> bool:
        """策略15在process_kline中处理止盈"""
        return False

    def run_optimized_backtest(
        self,
        klines_df: pd.DataFrame,
        indicators: Dict[str, pd.Series],
        initial_capital: Decimal = Decimal("10000")
    ) -> Dict:
        """
        执行分批止盈回测（策略15专用）

        Args:
            klines_df: K线数据DataFrame
            indicators: 技术指标字典
            initial_capital: 初始资金

        Returns:
            Dict: 回测结果
        """
        self.initialize(initial_capital)

        total_buy_fills = 0
        total_sell_fills = 0
        all_buy_fills = []
        all_sell_fills = []

        logger.info(
            f"开始分批止盈回测: {len(klines_df)}根K线, "
            f"初始资金: {initial_capital}"
        )

        for i, (idx, row) in enumerate(klines_df.iterrows()):
            kline = {
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'open_time': idx,
            }

            current_indicators = {}
            for name, series in indicators.items():
                if i < len(series):
                    value = series.iloc[i]
                    if not pd.isna(value):
                        current_indicators[name] = value

            if hasattr(idx, 'timestamp'):
                timestamp = int(idx.timestamp() * 1000)
            else:
                timestamp = int(idx)

            result = self.process_kline(i, kline, current_indicators, timestamp)

            total_buy_fills += len(result['buy_fills'])
            total_sell_fills += len(result['sell_fills'])
            all_buy_fills.extend(result['buy_fills'])
            all_sell_fills.extend(result['sell_fills'])

            if (i + 1) % 1000 == 0:
                stats = self.get_statistics()
                logger.info(
                    f"进度: {i+1}/{len(klines_df)}, "
                    f"买入: {total_buy_fills}, 卖出: {total_sell_fills}, "
                    f"持仓: {stats['holdings_count']}, "
                    f"资金: {stats['available_capital']:.2f}"
                )

        final_stats = self.get_statistics()
        completed_orders = self.get_completed_orders()
        holdings = self.get_holdings()

        last_close = Decimal(str(klines_df.iloc[-1]['close']))

        holding_cost = Decimal('0')
        holding_value = Decimal('0')
        holding_unrealized_pnl = Decimal('0')
        holding_losing_count = 0

        for order_id, holding in holdings.items():
            buy_price = holding['buy_price']
            remaining_quantity = holding.get('remaining_quantity', holding['quantity'])
            cost = buy_price * remaining_quantity
            current_value = last_close * remaining_quantity
            unrealized_pnl = current_value - cost

            holding_cost += cost
            holding_value += current_value
            holding_unrealized_pnl += unrealized_pnl

            if unrealized_pnl < 0:
                holding_losing_count += 1

        winning_trades = sum(1 for o in completed_orders if o.get('profit_loss', 0) > 0)
        losing_trades_closed = sum(1 for o in completed_orders if o.get('profit_loss', 0) <= 0)
        losing_trades = losing_trades_closed + holding_losing_count
        total_orders_for_win_rate = len(completed_orders) + len(holdings)

        total_profit_loss = sum(o.get('profit_loss', 0) for o in completed_orders)
        final_capital = final_stats['total_capital']
        available_capital = final_stats['available_capital']
        frozen_capital = final_stats['frozen_capital']
        return_rate = (float(final_capital) - float(initial_capital)) / float(initial_capital) * 100

        pending_frozen = Decimal(str(frozen_capital)) - holding_cost
        if pending_frozen < 0:
            pending_frozen = Decimal('0')

        total_equity = Decimal(str(available_capital)) + pending_frozen + holding_value

        result = {
            'total_trades': len(completed_orders),
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': winning_trades / total_orders_for_win_rate * 100 if total_orders_for_win_rate > 0 else 0,
            'total_profit_loss': total_profit_loss,
            'final_capital': float(final_capital),
            'return_rate': return_rate,
            'total_buy_fills': total_buy_fills,
            'total_sell_fills': total_sell_fills,
            'remaining_holdings': len(holdings),
            'orders': completed_orders,
            'buy_fills': all_buy_fills,
            'sell_fills': all_sell_fills,
            'statistics': final_stats,
            'holding_cost': float(holding_cost),
            'holding_value': float(holding_value),
            'holding_unrealized_pnl': float(holding_unrealized_pnl),
            'holding_losing_count': holding_losing_count,
            'last_close_price': float(last_close),
            'available_capital': float(available_capital),
            'frozen_capital': float(pending_frozen),
            'total_equity': float(total_equity),
        }

        logger.info(
            f"回测完成: 总交易={result['total_trades']}, "
            f"胜率={result['win_rate']:.2f}%, "
            f"盈亏={result['total_profit_loss']:.4f}, "
            f"收益率={result['return_rate']:.2f}%"
        )

        return result
