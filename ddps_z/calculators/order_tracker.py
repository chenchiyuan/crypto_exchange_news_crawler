"""
订单追踪计算器 (Order Tracker)

负责将买入信号转化为虚拟订单，检测EMA25回归卖出条件，计算盈亏和统计指标。

Related:
    - PRD: docs/iterations/012-buy-sell-order-tracking/prd.md
    - Architecture: docs/iterations/012-buy-sell-order-tracking/architecture.md
    - TASK: TASK-012-001
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class OrderTrackerError(Exception):
    """订单追踪异常基类"""
    pass


class DataInsufficientError(OrderTrackerError):
    """数据不足异常"""
    pass


class InvalidDataError(OrderTrackerError):
    """无效数据异常"""
    pass


@dataclass
class VirtualOrder:
    """
    虚拟订单数据类

    表示一个从买入信号创建的虚拟订单，包含买入/卖出信息、状态和盈亏数据。
    """
    # 订单标识
    id: str

    # 买入信息
    buy_timestamp: int              # 买入时间戳（毫秒）
    buy_price: Decimal              # 买入价格
    buy_amount_usdt: Decimal        # 买入金额（固定100U）
    buy_quantity: Decimal           # 买入数量
    buy_strategy_id: str            # 触发的买入策略ID

    # 卖出信息
    sell_timestamp: Optional[int] = None     # 卖出时间戳
    sell_price: Optional[Decimal] = None     # 卖出价格（EMA25）
    sell_strategy_id: Optional[str] = None   # 卖出策略ID

    # 状态
    status: str = "holding"         # "holding" | "sold"

    # 盈亏（已卖出订单）
    profit_usdt: Optional[Decimal] = None    # 盈亏金额
    profit_rate: Optional[Decimal] = None    # 盈亏率（%）
    holding_periods: Optional[int] = None    # 持仓K线数

    # 浮动盈亏（持仓订单）
    floating_profit_usdt: Optional[Decimal] = None   # 浮动盈亏
    floating_profit_rate: Optional[Decimal] = None   # 浮动盈亏率（%）

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于API响应"""
        result = {
            'id': self.id,
            'buy_timestamp': self.buy_timestamp,
            'buy_price': float(self.buy_price),
            'buy_amount_usdt': float(self.buy_amount_usdt),
            'buy_quantity': float(self.buy_quantity),
            'buy_strategy_id': self.buy_strategy_id,
            'sell_timestamp': self.sell_timestamp,
            'sell_price': float(self.sell_price) if self.sell_price else None,
            'sell_strategy_id': self.sell_strategy_id,
            'status': self.status,
            'profit_usdt': float(self.profit_usdt) if self.profit_usdt is not None else None,
            'profit_rate': float(self.profit_rate) if self.profit_rate is not None else None,
            'holding_periods': self.holding_periods,
        }

        # 持仓订单添加浮动盈亏
        if self.status == "holding":
            result['floating_profit_usdt'] = float(self.floating_profit_usdt) if self.floating_profit_usdt is not None else None
            result['floating_profit_rate'] = float(self.floating_profit_rate) if self.floating_profit_rate is not None else None

        return result


@dataclass
class OrderStatistics:
    """
    订单统计数据类

    汇总所有订单的统计指标。
    """
    # 订单数量
    total_orders: int = 0
    sold_orders: int = 0
    holding_orders: int = 0

    # 胜率
    win_orders: int = 0
    lose_orders: int = 0
    win_rate: Decimal = Decimal("0")

    # 收益
    total_invested: Decimal = Decimal("0")
    total_profit: Decimal = Decimal("0")
    total_profit_rate: Decimal = Decimal("0")
    floating_profit: Decimal = Decimal("0")

    # 平均指标
    avg_profit_rate: Decimal = Decimal("0")
    avg_holding_periods: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于API响应"""
        return {
            'total_orders': self.total_orders,
            'sold_orders': self.sold_orders,
            'holding_orders': self.holding_orders,
            'win_orders': self.win_orders,
            'lose_orders': self.lose_orders,
            'win_rate': float(self.win_rate),
            'total_invested': float(self.total_invested),
            'total_profit': float(self.total_profit),
            'total_profit_rate': float(self.total_profit_rate),
            'floating_profit': float(self.floating_profit),
            'avg_profit_rate': float(self.avg_profit_rate),
            'avg_holding_periods': self.avg_holding_periods,
        }


@dataclass
class TradeEvent:
    """
    交易事件数据类（操作日志）

    表示一个买入或卖出事件。
    """
    event_type: str                 # "buy" | "sell"
    timestamp: int                  # 事件时间戳
    price: Decimal                  # 价格
    quantity: Decimal               # 数量
    order_id: str                   # 关联订单ID
    amount_usdt: Decimal            # 金额
    profit_usdt: Optional[Decimal] = None    # 盈亏（仅卖出）
    profit_rate: Optional[Decimal] = None    # 盈亏率（仅卖出）

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于API响应"""
        return {
            'event_type': self.event_type,
            'timestamp': self.timestamp,
            'price': float(self.price),
            'quantity': float(self.quantity),
            'order_id': self.order_id,
            'amount_usdt': float(self.amount_usdt),
            'profit_usdt': float(self.profit_usdt) if self.profit_usdt is not None else None,
            'profit_rate': float(self.profit_rate) if self.profit_rate is not None else None,
        }


class OrderTracker:
    """
    订单追踪计算器

    职责：
    1. 从买入信号创建虚拟订单（固定100U买入）
    2. 检测EMA25回归卖出条件
    3. 计算单笔盈亏和统计汇总
    4. 生成交易事件日志
    """

    # 固定买入金额
    BUY_AMOUNT_USDT = Decimal("100")

    # 卖出策略ID
    SELL_STRATEGY_ID = "ema25_reversion"

    def __init__(self):
        """初始化订单追踪计算器"""
        pass

    def _validate_inputs(
        self,
        buy_signals: List[Dict],
        klines: List[Dict],
        ema_series: np.ndarray
    ) -> None:
        """
        验证输入数据

        Raises:
            DataInsufficientError: 数据不足或长度不一致
            InvalidDataError: 数据格式无效
        """
        if not klines:
            raise DataInsufficientError("K线数据为空")

        n = len(klines)

        if len(ema_series) != n:
            raise DataInsufficientError(
                f"EMA序列长度({len(ema_series)})与K线数量({n})不一致"
            )

        # 检查K线必要字段
        required_fields = ['open_time', 'high', 'low', 'close']
        for i, kline in enumerate(klines):
            for field_name in required_fields:
                if field_name not in kline:
                    raise InvalidDataError(
                        f"K线索引{i}缺少必要字段: {field_name}"
                    )

    def _get_triggered_strategy_id(self, signal: Dict) -> str:
        """
        获取触发的买入策略ID

        Args:
            signal: 买入信号

        Returns:
            触发的策略ID（优先返回第一个触发的策略）
        """
        strategies = signal.get('strategies', [])
        for strategy in strategies:
            if strategy.get('triggered', False):
                return strategy.get('id', 'unknown')
        return 'unknown'

    def _find_kline_index(self, klines: List[Dict], timestamp: int) -> int:
        """
        根据时间戳查找K线索引

        Args:
            klines: K线列表
            timestamp: 目标时间戳（毫秒）

        Returns:
            K线索引，未找到返回-1
        """
        for i, kline in enumerate(klines):
            open_time = kline['open_time']
            # 处理datetime对象
            if hasattr(open_time, 'timestamp'):
                kline_ts = int(open_time.timestamp() * 1000)
            else:
                kline_ts = int(open_time)

            if kline_ts == timestamp:
                return i
        return -1

    def _create_orders_from_signals(
        self,
        buy_signals: List[Dict]
    ) -> List[VirtualOrder]:
        """
        从买入信号创建虚拟订单

        Args:
            buy_signals: 买入信号列表

        Returns:
            虚拟订单列表（状态为holding）
        """
        orders = []

        for signal in buy_signals:
            timestamp = signal['timestamp']
            buy_price = Decimal(str(signal['buy_price']))

            # 计算买入数量
            buy_quantity = self.BUY_AMOUNT_USDT / buy_price

            order = VirtualOrder(
                id=f"order_{timestamp}",
                buy_timestamp=timestamp,
                buy_price=buy_price,
                buy_amount_usdt=self.BUY_AMOUNT_USDT,
                buy_quantity=buy_quantity,
                buy_strategy_id=self._get_triggered_strategy_id(signal),
                status="holding"
            )
            orders.append(order)

        return orders

    def _check_sell_condition(
        self,
        order: VirtualOrder,
        klines: List[Dict],
        ema_series: np.ndarray
    ) -> bool:
        """
        检测EMA25回归卖出条件

        条件：K线的 low <= EMA25 <= high

        Args:
            order: 虚拟订单
            klines: K线列表
            ema_series: EMA25序列

        Returns:
            是否触发卖出
        """
        buy_index = self._find_kline_index(klines, order.buy_timestamp)

        if buy_index < 0:
            logger.warning(f"订单{order.id}的买入K线未找到")
            return False

        # 从买入后的下一根K线开始检查
        for i in range(buy_index + 1, len(klines)):
            kline = klines[i]
            ema25 = ema_series[i]

            # 跳过无效EMA值
            if np.isnan(ema25):
                continue

            low = Decimal(str(kline['low']))
            high = Decimal(str(kline['high']))
            ema25_decimal = Decimal(str(ema25))

            # 检查K线是否包含EMA25
            if low <= ema25_decimal <= high:
                # 获取卖出时间戳
                sell_time = kline['open_time']
                if hasattr(sell_time, 'timestamp'):
                    sell_timestamp = int(sell_time.timestamp() * 1000)
                else:
                    sell_timestamp = int(sell_time)

                # 更新订单状态
                order.sell_timestamp = sell_timestamp
                order.sell_price = ema25_decimal
                order.sell_strategy_id = self.SELL_STRATEGY_ID
                order.status = "sold"
                order.holding_periods = i - buy_index

                # 计算盈亏
                order.profit_usdt = (order.sell_price - order.buy_price) * order.buy_quantity
                order.profit_rate = ((order.sell_price - order.buy_price) / order.buy_price * Decimal("100")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )

                return True

        return False

    def _calculate_floating_profit(
        self,
        order: VirtualOrder,
        current_price: Decimal
    ) -> None:
        """
        计算持仓订单的浮动盈亏

        Args:
            order: 虚拟订单（必须是holding状态）
            current_price: 当前价格
        """
        if order.status != "holding":
            return

        order.floating_profit_usdt = (current_price - order.buy_price) * order.buy_quantity
        order.floating_profit_rate = ((current_price - order.buy_price) / order.buy_price * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    def _calculate_statistics(
        self,
        orders: List[VirtualOrder]
    ) -> OrderStatistics:
        """
        计算订单统计汇总

        Args:
            orders: 虚拟订单列表

        Returns:
            统计数据
        """
        stats = OrderStatistics()

        if not orders:
            return stats

        stats.total_orders = len(orders)

        sold_orders = [o for o in orders if o.status == "sold"]
        holding_orders = [o for o in orders if o.status == "holding"]

        stats.sold_orders = len(sold_orders)
        stats.holding_orders = len(holding_orders)

        # 计算胜率
        stats.win_orders = len([o for o in sold_orders if o.profit_usdt and o.profit_usdt > 0])
        stats.lose_orders = len([o for o in sold_orders if o.profit_usdt and o.profit_usdt <= 0])

        if stats.sold_orders > 0:
            stats.win_rate = (Decimal(stats.win_orders) / Decimal(stats.sold_orders) * Decimal("100")).quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP
            )
        else:
            stats.win_rate = Decimal("0")

        # 计算总投入
        stats.total_invested = sum(o.buy_amount_usdt for o in orders)

        # 计算总盈亏（已卖出订单）
        stats.total_profit = sum(o.profit_usdt for o in sold_orders if o.profit_usdt is not None)

        # 计算总收益率
        if stats.total_invested > 0:
            sold_invested = sum(o.buy_amount_usdt for o in sold_orders)
            if sold_invested > 0:
                stats.total_profit_rate = (stats.total_profit / sold_invested * Decimal("100")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )

        # 计算浮动盈亏
        stats.floating_profit = sum(o.floating_profit_usdt for o in holding_orders if o.floating_profit_usdt is not None)

        # 计算平均收益率
        if stats.sold_orders > 0:
            profit_rates = [o.profit_rate for o in sold_orders if o.profit_rate is not None]
            if profit_rates:
                stats.avg_profit_rate = (sum(profit_rates) / Decimal(len(profit_rates))).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )

        # 计算平均持仓周期
        holding_periods_list = [o.holding_periods for o in sold_orders if o.holding_periods is not None]
        if holding_periods_list:
            stats.avg_holding_periods = round(sum(holding_periods_list) / len(holding_periods_list))

        return stats

    def _generate_trade_events(
        self,
        orders: List[VirtualOrder]
    ) -> List[TradeEvent]:
        """
        从订单生成交易事件（操作日志）

        每个订单生成一个买入事件，已卖出订单额外生成卖出事件。
        按时间倒序排列。

        Args:
            orders: 虚拟订单列表

        Returns:
            交易事件列表
        """
        events = []

        for order in orders:
            # 买入事件
            buy_event = TradeEvent(
                event_type="buy",
                timestamp=order.buy_timestamp,
                price=order.buy_price,
                quantity=order.buy_quantity,
                order_id=order.id,
                amount_usdt=order.buy_amount_usdt,
                profit_usdt=None,
                profit_rate=None
            )
            events.append(buy_event)

            # 卖出事件（如果已卖出）
            if order.status == "sold" and order.sell_timestamp:
                sell_amount = order.sell_price * order.buy_quantity if order.sell_price else Decimal("0")
                sell_event = TradeEvent(
                    event_type="sell",
                    timestamp=order.sell_timestamp,
                    price=order.sell_price,
                    quantity=order.buy_quantity,
                    order_id=order.id,
                    amount_usdt=sell_amount,
                    profit_usdt=order.profit_usdt,
                    profit_rate=order.profit_rate
                )
                events.append(sell_event)

        # 按时间倒序排列
        events.sort(key=lambda e: e.timestamp, reverse=True)

        return events

    def track(
        self,
        buy_signals: List[Dict],
        klines: List[Dict],
        ema_series: np.ndarray,
        current_price: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """
        追踪订单状态

        主方法：创建订单、检测卖出、计算盈亏、生成统计和事件日志。

        Args:
            buy_signals: 买入信号列表（来自BuySignalCalculator）
            klines: K线数据列表
            ema_series: EMA25序列
            current_price: 当前价格（用于计算浮动盈亏），如为None则使用最后一根K线close

        Returns:
            {
                'orders': List[Dict],           # 订单列表
                'statistics': Dict,             # 统计信息
                'trade_events': List[Dict]      # 操作日志
            }
        """
        # 验证输入
        self._validate_inputs(buy_signals, klines, ema_series)

        # 如果没有买入信号，返回空结果
        if not buy_signals:
            logger.info("无买入信号，返回空订单数据")
            empty_stats = OrderStatistics()
            return {
                'orders': [],
                'statistics': empty_stats.to_dict(),
                'trade_events': []
            }

        # 获取当前价格（默认使用最后一根K线的close）
        if current_price is None:
            current_price = Decimal(str(klines[-1]['close']))

        # 1. 创建订单
        orders = self._create_orders_from_signals(buy_signals)

        # 2. 检测卖出条件
        for order in orders:
            self._check_sell_condition(order, klines, ema_series)

        # 3. 计算持仓订单的浮动盈亏
        for order in orders:
            if order.status == "holding":
                self._calculate_floating_profit(order, current_price)

        # 4. 计算统计汇总
        statistics = self._calculate_statistics(orders)

        # 5. 生成交易事件
        trade_events = self._generate_trade_events(orders)

        logger.info(
            f"订单追踪完成: 总订单{statistics.total_orders}, "
            f"已卖出{statistics.sold_orders}, 持仓{statistics.holding_orders}, "
            f"胜率{statistics.win_rate}%"
        )

        return {
            'orders': [o.to_dict() for o in orders],
            'statistics': statistics.to_dict(),
            'trade_events': [e.to_dict() for e in trade_events]
        }
