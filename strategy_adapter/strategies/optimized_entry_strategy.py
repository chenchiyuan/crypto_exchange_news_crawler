"""
优化买入策略（策略14）

本模块实现策略14的优化买入机制：
- 价格分布：首档base_price，第2档低first_gap(4%)，后续每档低interval(1%)
- 金额分布：1×, 3×, 9×, 27×, 剩余全部可用资金
- 卖出机制：限价挂单卖出（2%止盈，6%止损）

与策略12的核心差异：
- 价格间隔：策略12固定1%，策略14首档4%后续1%
- 金额倍增：策略12用2倍，策略14用3倍
- 第5档：策略12固定金额，策略14使用剩余全部可用资金
- 卖出方式：策略14使用限价挂单卖出，支持止盈→止损价格调整

限价挂单卖出流程：
1. 买入成交后，立即创建卖出挂单（2%止盈价）
2. 每根K线检查是否需要调整为止损价（价格跌破止损线时）
3. 下根K线起，判断卖出挂单是否成交

迭代编号: 030 (策略14-优化买入策略+限价挂单卖出)
创建日期: 2026-01-11
"""

import logging
from decimal import Decimal
from typing import Dict, List, Any

import pandas as pd

from strategy_adapter.interfaces import IStrategy
from strategy_adapter.models import Order
from strategy_adapter.core.limit_order_manager import LimitOrderManager
from strategy_adapter.core.limit_order_price_calculator import LimitOrderPriceCalculator

logger = logging.getLogger(__name__)


class OptimizedEntryStrategy(IStrategy):
    """
    优化买入策略（策略14）

    价格分布：
    - 第1档: base_price
    - 第2档: base_price × (1 - first_gap)
    - 第3档: base_price × (1 - first_gap - interval)
    - 第4档: base_price × (1 - first_gap - 2×interval)
    - 第5档: base_price × (1 - first_gap - 3×interval)

    金额分布：
    - 第1档: base_amount (1×)
    - 第2档: base_amount × 3 (3×)
    - 第3档: base_amount × 9 (9×)
    - 第4档: base_amount × 27 (27×)
    - 第5档: 剩余全部可用资金

    止盈止损：沿用策略12（2%止盈，6%止损）
    """

    STRATEGY_ID = 'strategy_14'
    STRATEGY_NAME = '优化买入策略'
    STRATEGY_VERSION = '1.0'

    def __init__(
        self,
        base_amount: Decimal = Decimal("100"),
        multiplier: float = 3.0,
        order_count: int = 5,
        first_gap: float = 0.04,
        interval: float = 0.01,
        first_order_discount: float = 0.003,
        take_profit_rate: float = 0.02,
        stop_loss_rate: float = 0.06
    ):
        """
        初始化优化买入策略

        Args:
            base_amount: 首单金额（USDT），默认100
            multiplier: 金额倍数，默认3.0
            order_count: 挂单数量，默认5
            first_gap: 首档间隔，默认0.04（4%）
            interval: 后续间隔，默认0.01（1%）
            first_order_discount: 首笔折扣，默认0.003（0.3%）
            take_profit_rate: 止盈比例，默认0.02（2%）
            stop_loss_rate: 止损比例，默认0.06（6%）
        """
        self.base_amount = base_amount
        self.multiplier = Decimal(str(multiplier))
        self.order_count = order_count
        self.first_gap = Decimal(str(first_gap))
        self.interval = Decimal(str(interval))
        self.first_order_discount = first_order_discount
        self.take_profit_rate = take_profit_rate
        self.stop_loss_rate = stop_loss_rate

        # 初始化组件
        self.order_manager = LimitOrderManager(position_size=base_amount)
        self.price_calculator = LimitOrderPriceCalculator(
            order_count=order_count,
            order_interval=float(interval),
            first_order_discount=first_order_discount
        )

        # 持仓管理
        self._holdings: Dict[str, Dict] = {}
        self._completed_orders: List[Dict] = []

        # 预计算前4档固定金额
        self._fixed_amounts = self._calculate_fixed_amounts()

        logger.info(
            f"初始化OptimizedEntryStrategy: base_amount={base_amount}, "
            f"multiplier={multiplier}, order_count={order_count}, "
            f"first_gap={first_gap}, interval={interval}, "
            f"take_profit_rate={take_profit_rate}, stop_loss_rate={stop_loss_rate}"
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
        计算5档挂单价格

        价格分布：
        - 第1档: base_price × (1 - first_order_discount)  【如2%】
        - 第2档: base_price × (1 - first_order_discount - first_gap)  【如2%+4%=6%】
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
        计算5档挂单金额

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

    def get_total_required_capital(self) -> Decimal:
        """计算前4档所需资金"""
        return sum(self._fixed_amounts)

    def initialize(self, initial_capital: Decimal) -> None:
        """初始化策略"""
        self.order_manager.initialize(initial_capital)
        self._holdings.clear()
        self._completed_orders.clear()
        logger.info(f"OptimizedEntryStrategy初始化完成，初始资金: {initial_capital}")

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

        # 注意：首笔折扣在_calculate_prices中应用，这里不再应用

        return base_price

    def process_kline(
        self,
        kline_index: int,
        kline: Dict[str, Any],
        indicators: Dict[str, Any],
        timestamp: int
    ) -> Dict[str, List[Dict]]:
        """
        处理单根K线（策略14的核心方法）

        流程（限价挂单版本）：
        1. 检查买入挂单是否成交 → 立即创建卖出挂单
        2. 检查卖出挂单是否需要调整为止损价
        3. 检查卖出挂单是否成交
        4. 取消未成交的买入挂单
        5. 创建新的买入挂单
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

        # === Step 1: 检查买入挂单是否成交 → 立即创建卖出挂单 ===
        pending_buy_orders = self.order_manager.get_pending_buy_orders()
        for order in pending_buy_orders:
            if self.order_manager.check_buy_order_fill(order, low, high):
                filled_order = self.order_manager.fill_buy_order(order.order_id, timestamp)
                if filled_order:
                    # 添加到持仓
                    self._holdings[filled_order.order_id] = {
                        'buy_price': filled_order.price,
                        'quantity': filled_order.quantity,
                        'amount': filled_order.amount,
                        'buy_timestamp': timestamp,
                        'kline_index': kline_index,
                    }

                    result['buy_fills'].append({
                        'order_id': filled_order.order_id,
                        'price': filled_order.price,
                        'quantity': filled_order.quantity,
                        'amount': filled_order.amount,
                        'timestamp': timestamp,
                        'kline_index': kline_index,
                    })

                    # 立即创建卖出挂单（2%止盈价）
                    sell_price = filled_order.price * (Decimal("1") + Decimal(str(self.take_profit_rate)))
                    self.order_manager.create_sell_order(
                        parent_order_id=filled_order.order_id,
                        sell_price=sell_price,
                        quantity=filled_order.quantity,
                        kline_index=kline_index,
                        timestamp=timestamp
                    )

                    logger.debug(
                        f"买入成交: {filled_order.order_id}, "
                        f"价格: {filled_order.price}, 金额: {filled_order.amount}, "
                        f"创建卖出挂单: {sell_price:.4f}"
                    )

        # === Step 2: 检查卖出挂单是否需要调整为止损价 ===
        for order_id, holding in self._holdings.items():
            sell_order = self.order_manager.get_sell_order_by_parent(order_id)
            if sell_order:
                buy_price = holding['buy_price']
                stop_loss_price = buy_price * (Decimal("1") - Decimal(str(self.stop_loss_rate)))

                # 如果当前价格跌破止损线，调整挂单价格为止损价
                if low <= stop_loss_price:
                    current_sell_price = sell_order.price
                    # 只有当前价格高于止损价时才调整（避免重复调整）
                    if current_sell_price > stop_loss_price:
                        self.order_manager.update_sell_order_price(
                            sell_order.order_id,
                            stop_loss_price
                        )
                        logger.debug(
                            f"调整卖出挂单为止损价: {order_id}, "
                            f"{current_sell_price:.4f} -> {stop_loss_price:.4f}"
                        )

        # === Step 3: 检查卖出挂单是否成交 ===
        pending_sell_orders = self.order_manager.get_pending_sell_orders()
        for sell_order in pending_sell_orders:
            if self.order_manager.check_sell_order_fill(sell_order, low, high):
                parent_order_id = sell_order.parent_order_id
                if parent_order_id in self._holdings:
                    holding = self._holdings[parent_order_id]
                    buy_price = holding['buy_price']

                    # 确认卖出挂单成交
                    fill_result = self.order_manager.fill_sell_order(
                        sell_order.order_id,
                        timestamp,
                        buy_price
                    )

                    if fill_result:
                        # 判断平仓原因
                        take_profit_price = buy_price * (Decimal("1") + Decimal(str(self.take_profit_rate)))
                        stop_loss_price = buy_price * (Decimal("1") - Decimal(str(self.stop_loss_rate)))

                        if abs(sell_order.price - take_profit_price) < Decimal("0.0001"):
                            close_reason = 'take_profit'
                        elif abs(sell_order.price - stop_loss_price) < Decimal("0.0001"):
                            close_reason = 'stop_loss'
                        else:
                            close_reason = 'limit_order_exit'

                        result['sell_fills'].append({
                            'order_id': sell_order.order_id,
                            'parent_order_id': parent_order_id,
                            'buy_price': buy_price,
                            'sell_price': fill_result['sell_price'],
                            'quantity': fill_result['quantity'],
                            'profit_loss': fill_result['profit_loss'],
                            'profit_rate': float(fill_result['profit_rate']),
                            'timestamp': timestamp,
                            'kline_index': kline_index,
                            'close_reason': close_reason,
                        })

                        self._completed_orders.append({
                            'buy_order_id': parent_order_id,
                            'sell_order_id': sell_order.order_id,
                            'buy_price': float(buy_price),
                            'sell_price': float(fill_result['sell_price']),
                            'quantity': float(fill_result['quantity']),
                            'profit_loss': float(fill_result['profit_loss']),
                            'profit_rate': float(fill_result['profit_rate']),
                            'buy_timestamp': holding['buy_timestamp'],
                            'sell_timestamp': timestamp,
                            'close_reason': close_reason,
                        })

                        # 从持仓中移除
                        del self._holdings[parent_order_id]

                        logger.debug(
                            f"卖出成交: {sell_order.order_id}, "
                            f"原因: {close_reason}, "
                            f"盈亏: {fill_result['profit_loss']:.4f} ({fill_result['profit_rate']:.2f}%)"
                        )

        # === Step 4: 取消所有未成交的买入挂单 ===
        pending_before = len(self.order_manager.get_pending_buy_orders())
        self.order_manager.cancel_all_buy_orders()
        result['orders_cancelled'] = pending_before

        # === Step 5: 创建新的买入挂单（优化价格和金额分布）===
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

        return {
            **manager_stats,
            'holdings_count': total_holdings,
            'completed_trades': total_completed,
            'total_profit_loss': total_profit_loss,
            'winning_trades': winning_trades,
            'win_rate': win_rate,
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
        """策略14不使用传统的信号生成方式"""
        return []

    def generate_sell_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series],
        open_orders: List[Order]
    ) -> List[Dict]:
        """策略14不使用传统的信号生成方式"""
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
        """策略14在process_kline中处理止损"""
        return False

    def should_take_profit(
        self,
        order: Order,
        current_price: Decimal,
        current_timestamp: int
    ) -> bool:
        """策略14在process_kline中处理止盈"""
        return False

    def run_optimized_backtest(
        self,
        klines_df: pd.DataFrame,
        indicators: Dict[str, pd.Series],
        initial_capital: Decimal = Decimal("10000")
    ) -> Dict:
        """
        执行优化买入回测（策略14专用）

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
            f"开始优化买入回测: {len(klines_df)}根K线, "
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
            quantity = holding['quantity']
            cost = buy_price * quantity
            current_value = last_close * quantity
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
