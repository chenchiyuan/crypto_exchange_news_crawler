"""
倍增仓位限价挂单策略（策略12）

本模块实现策略12的倍增仓位限价挂单机制：
- 买入挂单：复用策略11价格计算逻辑
- 挂单金额：倍增式（100→200→400→800→1600）
- 卖出条件：固定2%止盈，单笔独立止盈

与策略11的核心差异：
- 挂单金额：策略11固定100U，策略12倍增
- 挂单数量：策略11默认10笔，策略12默认5笔
- 止盈方式：策略11用min(5%止盈, EMA25)，策略12用固定2%

迭代编号: 028 (策略12-倍增仓位限价挂单)
创建日期: 2026-01-11
关联任务: TASK-028-003~005
关联需求: FP-028-001~010 (function-points.md)
关联架构: architecture.md#2.2 DoublingPositionStrategy
"""

import logging
from decimal import Decimal
from typing import Dict, List, Any

import pandas as pd

from strategy_adapter.interfaces import IStrategy
from strategy_adapter.models import Order
from strategy_adapter.core.limit_order_manager import LimitOrderManager
from strategy_adapter.core.limit_order_price_calculator import LimitOrderPriceCalculator
from strategy_adapter.exits.take_profit import TakeProfitExit

logger = logging.getLogger(__name__)


class DoublingPositionStrategy(IStrategy):
    """
    倍增仓位限价挂单策略（策略12）

    与策略11的核心差异：
    - 挂单金额：倍增式（100→200→400→800→1600）
    - 止盈方式：固定2%止盈，单笔独立止盈

    工作流程：
    1. 每根K线结束时：
       - 取消所有未成交的买入挂单
       - 根据当前P5和mid计算新的挂单价格
       - 创建新的买入挂单（倍增金额）
    2. 下根K线开始时：
       - 检查买入挂单是否成交
       - 成交的挂单转为持仓
    3. 止盈处理：
       - 每根K线检查持仓是否达到2%止盈

    Attributes:
        base_amount: 首单金额（USDT）
        multiplier: 倍增系数
        order_count: 每根K线挂单数量
        order_interval: 挂单间隔比例
        first_order_discount: 首笔折扣
        take_profit_rate: 止盈比例
        order_manager: 限价挂单管理器
        price_calculator: 价格计算器
        exit_condition: 止盈条件

    Example:
        >>> strategy = DoublingPositionStrategy(
        ...     base_amount=Decimal("100"),
        ...     multiplier=2.0,
        ...     order_count=5,
        ...     take_profit_rate=0.02
        ... )
        >>> strategy.initialize(Decimal("10000"))
        >>> for i, kline in enumerate(klines):
        ...     signals = strategy.process_kline(i, kline, indicators, timestamp)
    """

    # 策略配置
    STRATEGY_ID = 'strategy_12'
    STRATEGY_NAME = '倍增仓位限价挂单'
    STRATEGY_VERSION = '1.0'

    def __init__(
        self,
        base_amount: Decimal = Decimal("100"),
        multiplier: float = 2.0,
        order_count: int = 5,
        order_interval: float = 0.01,
        first_order_discount: float = 0.01,
        take_profit_rate: float = 0.02,
        stop_loss_rate: float = 0.10
    ):
        """
        初始化倍增仓位策略

        Args:
            base_amount: 首单金额（USDT），默认100
            multiplier: 倍增系数，默认2.0
            order_count: 每根K线挂单数量，默认5
            order_interval: 挂单间隔比例，默认0.01（1%）
            first_order_discount: 首笔折扣，默认0.01（1%）
            take_profit_rate: 止盈比例，默认0.02（2%）
            stop_loss_rate: 止损比例，默认0.10（10%）
        """
        self.base_amount = base_amount
        self.multiplier = Decimal(str(multiplier))
        self.order_count = order_count
        self.order_interval = order_interval
        self.first_order_discount = first_order_discount
        self.take_profit_rate = take_profit_rate
        self.stop_loss_rate = stop_loss_rate

        # 初始化组件
        self.order_manager = LimitOrderManager(position_size=base_amount)
        self.price_calculator = LimitOrderPriceCalculator(
            order_count=order_count,
            order_interval=order_interval,
            first_order_discount=first_order_discount
        )
        # 使用百分比形式（2%传入2.0）
        self.exit_condition = TakeProfitExit(percentage=take_profit_rate * 100)

        # 持仓管理
        self._holdings: Dict[str, Dict] = {}
        self._completed_orders: List[Dict] = []

        # 预计算倍增金额列表
        self._doubling_amounts = self.calculate_doubling_amounts()

        logger.info(
            f"初始化DoublingPositionStrategy: base_amount={base_amount}, "
            f"multiplier={multiplier}, order_count={order_count}, "
            f"take_profit_rate={take_profit_rate}, stop_loss_rate={stop_loss_rate}"
        )
        logger.info(f"倍增金额列表: {self._doubling_amounts}")
        logger.info(f"总资金需求: {self.get_total_required_capital()}")

    def calculate_doubling_amounts(self) -> List[Decimal]:
        """
        计算倍增金额列表

        Returns:
            List[Decimal]: [100, 200, 400, 800, 1600] (multiplier=2, count=5时)
        """
        amounts = []
        for i in range(self.order_count):
            amount = self.base_amount * (self.multiplier ** i)
            amounts.append(amount)
        return amounts

    def get_total_required_capital(self) -> Decimal:
        """
        计算所需总资金

        Returns:
            Decimal: 全部挂单的总金额
        """
        return sum(self._doubling_amounts)

    def initialize(self, initial_capital: Decimal) -> None:
        """
        初始化策略（回测开始前调用）

        Args:
            initial_capital: 初始资金
        """
        self.order_manager.initialize(initial_capital)
        self._holdings.clear()
        self._completed_orders.clear()
        logger.info(f"DoublingPositionStrategy初始化完成，初始资金: {initial_capital}")

    def get_strategy_name(self) -> str:
        return self.STRATEGY_NAME

    def get_strategy_version(self) -> str:
        return self.STRATEGY_VERSION

    def get_required_indicators(self) -> List[str]:
        """
        返回所需的技术指标

        Returns:
            List[str]: ['p5', 'inertia_mid']
        """
        return ['p5', 'inertia_mid']

    def process_kline(
        self,
        kline_index: int,
        kline: Dict[str, Any],
        indicators: Dict[str, Any],
        timestamp: int
    ) -> Dict[str, List[Dict]]:
        """
        处理单根K线（策略12的核心方法）

        流程：
        1. 检查上一根K线的买入挂单是否成交
        2. 检查持仓是否达到止盈条件
        3. 取消未成交的买入挂单
        4. 创建新的买入挂单（倍增金额）

        Args:
            kline_index: K线索引
            kline: K线数据 {'open', 'high', 'low', 'close', 'open_time'}
            indicators: 当前K线的技术指标 {'p5', 'inertia_mid'}
            timestamp: 当前时间戳（毫秒）

        Returns:
            Dict: {
                'buy_fills': List[Dict],
                'sell_fills': List[Dict],
                'orders_placed': int,
                'orders_cancelled': int,
                'insufficient_capital_count': int
            }
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

        # === Step 2: 检查持仓止盈 ===
        holdings_to_close = []
        for order_id, holding in self._holdings.items():
            buy_price = holding['buy_price']
            take_profit_price = buy_price * (Decimal("1") + Decimal(str(self.take_profit_rate)))

            # 检查止盈价是否在K线范围内
            if high >= take_profit_price:
                holdings_to_close.append((order_id, holding, take_profit_price, 'take_profit'))

        for order_id, holding, sell_price, close_reason in holdings_to_close:
            buy_price = holding['buy_price']
            quantity = holding['quantity']

            # 计算盈亏
            profit_loss = (sell_price - buy_price) * quantity
            profit_rate = float(profit_loss / (buy_price * quantity) * 100)

            # 释放资金
            released_capital = buy_price * quantity + profit_loss
            self.order_manager._frozen_capital -= buy_price * quantity
            self.order_manager._available_capital += released_capital

            result['sell_fills'].append({
                'order_id': f"sell_{order_id}",
                'parent_order_id': order_id,
                'buy_price': buy_price,
                'sell_price': sell_price,
                'quantity': quantity,
                'profit_loss': profit_loss,
                'profit_rate': profit_rate,
                'timestamp': timestamp,
                'kline_index': kline_index,
                'close_reason': close_reason,
            })

            # 记录完成的交易
            self._completed_orders.append({
                'buy_order_id': order_id,
                'sell_order_id': f"sell_{order_id}",
                'buy_price': float(buy_price),
                'sell_price': float(sell_price),
                'quantity': float(quantity),
                'profit_loss': float(profit_loss),
                'profit_rate': profit_rate,
                'buy_timestamp': holding['buy_timestamp'],
                'sell_timestamp': timestamp,
                'close_reason': close_reason,
            })

            # 移除持仓
            del self._holdings[order_id]

            logger.debug(
                f"止盈成交: {order_id}, 盈亏: {profit_loss:.4f} ({profit_rate:.2f}%)"
            )

        # === Step 2.5: 检查持仓止损 ===
        holdings_to_stop_loss = []
        for order_id, holding in self._holdings.items():
            buy_price = holding['buy_price']
            stop_loss_price = buy_price * (Decimal("1") - Decimal(str(self.stop_loss_rate)))

            # 检查止损价是否在K线范围内（价格跌破止损价）
            if low <= stop_loss_price:
                holdings_to_stop_loss.append((order_id, holding, stop_loss_price))

        for order_id, holding, sell_price in holdings_to_stop_loss:
            buy_price = holding['buy_price']
            quantity = holding['quantity']

            # 计算盈亏（止损为负）
            profit_loss = (sell_price - buy_price) * quantity
            profit_rate = float(profit_loss / (buy_price * quantity) * 100)

            # 释放资金
            released_capital = buy_price * quantity + profit_loss
            self.order_manager._frozen_capital -= buy_price * quantity
            self.order_manager._available_capital += released_capital

            result['sell_fills'].append({
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

            # 记录完成的交易
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

            # 移除持仓
            del self._holdings[order_id]

            logger.debug(
                f"止损成交: {order_id}, 盈亏: {profit_loss:.4f} ({profit_rate:.2f}%)"
            )

        # === Step 3: 取消所有未成交的买入挂单 ===
        pending_before = len(self.order_manager.get_pending_buy_orders())
        self.order_manager.cancel_all_buy_orders()
        result['orders_cancelled'] = pending_before

        # === Step 4: 创建新的买入挂单（倍增金额）===
        p5 = Decimal(str(indicators.get('p5', 0)))
        inertia_mid = Decimal(str(indicators.get('inertia_mid', 0)))
        close = Decimal(str(kline['close']))

        if p5 > 0 and inertia_mid > 0:
            # 计算挂单价格列表（传入close限制挂单价格上限）
            buy_prices = self.price_calculator.calculate_buy_prices(p5, inertia_mid, close)

            # 创建倍增金额挂单
            for i, (price, amount) in enumerate(zip(buy_prices, self._doubling_amounts)):
                order = self.order_manager.create_buy_order(
                    price=price,
                    kline_index=kline_index,
                    timestamp=timestamp,
                    amount=amount
                )
                if order:
                    result['orders_placed'] += 1
                else:
                    # 资金不足，后续挂单也无法创建
                    result['insufficient_capital_count'] = self.order_count - i
                    break

        return result

    def get_statistics(self) -> Dict:
        """
        获取策略统计信息

        Returns:
            Dict: 统计数据
        """
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
        """策略12不使用传统的信号生成方式"""
        logger.warning(
            "DoublingPositionStrategy.generate_buy_signals被调用，"
            "但策略12应使用process_kline逐K线处理"
        )
        return []

    def generate_sell_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series],
        open_orders: List[Order]
    ) -> List[Dict]:
        """策略12不使用传统的信号生成方式"""
        logger.warning(
            "DoublingPositionStrategy.generate_sell_signals被调用，"
            "但策略12应使用process_kline逐K线处理"
        )
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
        """策略12不使用止损"""
        return False

    def should_take_profit(
        self,
        order: Order,
        current_price: Decimal,
        current_timestamp: int
    ) -> bool:
        """策略12在process_kline中处理止盈"""
        return False

    def run_doubling_backtest(
        self,
        klines_df: pd.DataFrame,
        indicators: Dict[str, pd.Series],
        initial_capital: Decimal = Decimal("10000")
    ) -> Dict:
        """
        执行倍增仓位回测（策略12专用）

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
            f"开始倍增仓位回测: {len(klines_df)}根K线, "
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

        # 获取最后K线收盘价，用于计算持仓浮盈浮亏
        last_close = Decimal(str(klines_df.iloc[-1]['close']))

        # 计算持仓统计
        holding_cost = Decimal('0')  # 持仓买入成本
        holding_value = Decimal('0')  # 当前持仓价值
        holding_unrealized_pnl = Decimal('0')  # 持仓浮盈浮亏
        holding_losing_count = 0  # 持仓中亏损的订单数

        for order_id, holding in holdings.items():
            buy_price = holding['buy_price']
            quantity = holding['quantity']
            cost = buy_price * quantity
            current_value = last_close * quantity
            unrealized_pnl = current_value - cost

            holding_cost += cost
            holding_value += current_value
            holding_unrealized_pnl += unrealized_pnl

            # 如果持仓浮亏，计入亏损订单
            if unrealized_pnl < 0:
                holding_losing_count += 1

        # 计算胜率：包含持仓中亏损的订单
        winning_trades = sum(1 for o in completed_orders if o.get('profit_loss', 0) > 0)
        losing_trades_closed = sum(1 for o in completed_orders if o.get('profit_loss', 0) <= 0)
        losing_trades = losing_trades_closed + holding_losing_count  # 加上持仓中亏损的
        total_orders_for_win_rate = len(completed_orders) + len(holdings)  # 总订单数包含持仓

        total_profit_loss = sum(o.get('profit_loss', 0) for o in completed_orders)
        final_capital = final_stats['total_capital']
        available_capital = final_stats['available_capital']  # 可用现金
        frozen_capital = final_stats['frozen_capital']  # 挂单冻结资金（包含持仓成本）
        return_rate = (float(final_capital) - float(initial_capital)) / float(initial_capital) * 100

        # 计算未成交挂单冻结资金 = 总冻结 - 持仓成本
        # 因为已成交持仓的资金仍在frozen中，需要扣除
        pending_frozen = Decimal(str(frozen_capital)) - holding_cost
        if pending_frozen < 0:
            pending_frozen = Decimal('0')

        # 计算总资产 = 可用现金 + 未成交挂单冻结 + 持仓市值
        # 注意：不能用 frozen_capital，因为它包含了持仓成本，会与 holding_value 重复
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
            # 新增：持仓统计
            'holding_cost': float(holding_cost),
            'holding_value': float(holding_value),
            'holding_unrealized_pnl': float(holding_unrealized_pnl),
            'holding_losing_count': holding_losing_count,
            'last_close_price': float(last_close),
            # 新增：资金统计
            'available_capital': float(available_capital),
            'frozen_capital': float(pending_frozen),  # 只返回未成交挂单的冻结资金
            'total_equity': float(total_equity),
        }

        logger.info(
            f"回测完成: 总交易={result['total_trades']}, "
            f"胜率={result['win_rate']:.2f}%, "
            f"盈亏={result['total_profit_loss']:.4f}, "
            f"收益率={result['return_rate']:.2f}%"
        )

        return result
