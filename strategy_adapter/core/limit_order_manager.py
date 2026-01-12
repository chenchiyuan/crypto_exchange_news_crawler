"""
限价挂单管理器

本模块实现限价挂单的生命周期管理：
- 资金管理：可用资金、冻结资金追踪
- 买入挂单：创建、取消、成交判断
- 卖出挂单：创建、更新价格、成交判断

设计决策：独立新模块，与UnifiedOrderManager并行（architecture.md 决策一）

迭代编号: 027 (策略11-限价挂单买卖机制)
创建日期: 2026-01-10
关联任务: TASK-027-004
关联需求: FP-027-002~006 (function-points.md)
关联架构: architecture.md#5.2 LimitOrderManager
"""

from typing import Dict, List, Optional
from decimal import Decimal
import logging

from strategy_adapter.models import (
    PendingOrder,
    PendingOrderStatus,
    PendingOrderSide
)

logger = logging.getLogger(__name__)


class LimitOrderManager:
    """
    限价挂单管理器

    职责：
    - 资金管理：追踪可用资金和冻结资金
    - 买入挂单：创建挂单、冻结资金、取消挂单、解冻资金、成交判断
    - 卖出挂单：创建卖出挂单、更新价格、成交判断

    设计原则：
    - 纯内存存储：挂单不持久化，每次回测从头开始
    - 资金安全：严格追踪冻结资金，避免超支
    - 独立性：不依赖UnifiedOrderManager

    Example:
        >>> manager = LimitOrderManager(position_size=Decimal("100"))
        >>> manager.initialize(Decimal("10000"))
        >>> order = manager.create_buy_order(
        ...     price=Decimal("3200"),
        ...     kline_index=100,
        ...     timestamp=1736500800000
        ... )
        >>> if order:
        ...     print(f"挂单成功: {order.order_id}")
    """

    def __init__(self, position_size: Decimal = Decimal("100")):
        """
        初始化限价挂单管理器

        Args:
            position_size: 单笔挂单金额（USDT），默认100
        """
        self.position_size = position_size

        # 资金状态
        self._available_capital: Decimal = Decimal("0")
        self._frozen_capital: Decimal = Decimal("0")

        # 挂单存储
        self._pending_orders: Dict[str, PendingOrder] = {}
        self._order_counter: int = 0  # 用于生成唯一ID

        # 统计信息
        self._insufficient_capital_count: int = 0

    def initialize(self, initial_capital: Decimal) -> None:
        """
        初始化资金

        Args:
            initial_capital: 初始资金（USDT）
        """
        self._available_capital = initial_capital
        self._frozen_capital = Decimal("0")
        self._pending_orders.clear()
        self._order_counter = 0
        self._insufficient_capital_count = 0

        logger.info(f"LimitOrderManager初始化完成，初始资金: {initial_capital}")

    @property
    def available_capital(self) -> Decimal:
        """可用资金"""
        return self._available_capital

    @property
    def frozen_capital(self) -> Decimal:
        """冻结资金"""
        return self._frozen_capital

    @property
    def total_capital(self) -> Decimal:
        """总资金（可用 + 冻结）"""
        return self._available_capital + self._frozen_capital

    @property
    def insufficient_capital_count(self) -> int:
        """资金不足次数统计"""
        return self._insufficient_capital_count

    def create_buy_order(
        self,
        price: Decimal,
        kline_index: int,
        timestamp: int,
        amount: Optional[Decimal] = None
    ) -> Optional[PendingOrder]:
        """
        创建买入挂单

        创建挂单并冻结资金。如果资金不足，返回None并记录日志。

        Args:
            price: 挂单价格
            kline_index: K线索引
            timestamp: 创建时间戳（毫秒）
            amount: 自定义挂单金额（USDT）。None时使用self.position_size（向后兼容）

        Returns:
            Optional[PendingOrder]: 创建的挂单，资金不足时返回None

        Example:
            >>> # 使用默认金额
            >>> order = manager.create_buy_order(
            ...     price=Decimal("3200"),
            ...     kline_index=100,
            ...     timestamp=1736500800000
            ... )
            >>> # 使用自定义金额（策略12倍增仓位）
            >>> order = manager.create_buy_order(
            ...     price=Decimal("3200"),
            ...     kline_index=100,
            ...     timestamp=1736500800000,
            ...     amount=Decimal("200")
            ... )
        """
        # 确定实际挂单金额（向后兼容）
        actual_amount = amount if amount is not None else self.position_size

        # 检查资金是否充足
        if self._available_capital < actual_amount:
            self._insufficient_capital_count += 1
            logger.debug(
                f"资金不足，无法创建买入挂单: "
                f"需要 {actual_amount}, 可用 {self._available_capital}"
            )
            return None

        # 生成唯一ID
        self._order_counter += 1
        order_id = f"pending_buy_{timestamp}_{self._order_counter}"

        # 计算数量
        quantity = actual_amount / price

        # 创建挂单
        order = PendingOrder(
            order_id=order_id,
            price=price,
            amount=actual_amount,
            quantity=quantity,
            status=PendingOrderStatus.PENDING,
            side=PendingOrderSide.BUY,
            frozen_capital=actual_amount,
            kline_index=kline_index,
            created_at=timestamp
        )

        # 冻结资金
        self._available_capital -= actual_amount
        self._frozen_capital += actual_amount

        # 存储挂单
        self._pending_orders[order_id] = order

        logger.debug(
            f"创建买入挂单: {order_id}, 价格: {price}, "
            f"金额: {actual_amount}, 冻结后可用: {self._available_capital}"
        )

        return order

    def cancel_all_buy_orders(self) -> Decimal:
        """
        取消所有买入挂单

        取消所有待成交的买入挂单，解冻资金。

        Returns:
            Decimal: 解冻的资金总额

        Example:
            >>> unfrozen = manager.cancel_all_buy_orders()
            >>> print(f"解冻资金: {unfrozen}")
        """
        unfrozen_amount = Decimal("0")
        orders_to_cancel = []

        for order_id, order in self._pending_orders.items():
            if order.is_buy_order() and order.is_pending():
                orders_to_cancel.append(order_id)
                unfrozen_amount += order.frozen_capital

        # 取消挂单并解冻资金
        for order_id in orders_to_cancel:
            order = self._pending_orders[order_id]
            order.mark_cancelled()

            # 解冻资金
            self._frozen_capital -= order.frozen_capital
            self._available_capital += order.frozen_capital

        # 清理已取消的挂单
        for order_id in orders_to_cancel:
            del self._pending_orders[order_id]

        if orders_to_cancel:
            logger.debug(
                f"取消 {len(orders_to_cancel)} 笔买入挂单，"
                f"解冻资金: {unfrozen_amount}"
            )

        return unfrozen_amount

    def check_buy_order_fill(
        self,
        order: PendingOrder,
        kline_low: Decimal,
        kline_high: Decimal
    ) -> bool:
        """
        检查买入挂单是否成交

        成交条件：挂单价格在K线的 [low, high] 范围内

        Args:
            order: 买入挂单
            kline_low: K线最低价
            kline_high: K线最高价

        Returns:
            bool: True表示成交

        Example:
            >>> if manager.check_buy_order_fill(order, Decimal("3180"), Decimal("3220")):
            ...     print("订单成交")
        """
        # 成交条件：low <= 挂单价 <= high
        return kline_low <= order.price <= kline_high

    def fill_buy_order(
        self,
        order_id: str,
        fill_timestamp: int
    ) -> Optional[PendingOrder]:
        """
        确认买入挂单成交

        标记挂单为已成交状态。资金保持冻结状态（已占用于持仓）。

        Args:
            order_id: 挂单ID
            fill_timestamp: 成交时间戳

        Returns:
            Optional[PendingOrder]: 成交的挂单，订单不存在时返回None
        """
        if order_id not in self._pending_orders:
            logger.warning(f"挂单不存在: {order_id}")
            return None

        order = self._pending_orders[order_id]
        order.mark_filled(fill_timestamp)

        # 移除已成交挂单（但资金保持冻结状态，用于持仓管理）
        del self._pending_orders[order_id]

        logger.debug(f"买入挂单成交: {order_id}, 价格: {order.price}")

        return order

    def create_sell_order(
        self,
        parent_order_id: str,
        sell_price: Decimal,
        quantity: Decimal,
        kline_index: int,
        timestamp: int
    ) -> PendingOrder:
        """
        创建卖出挂单

        为持仓创建卖出挂单。卖出挂单不冻结额外资金。

        Args:
            parent_order_id: 关联的持仓订单ID
            sell_price: 卖出价格
            quantity: 卖出数量
            kline_index: K线索引
            timestamp: 创建时间戳

        Returns:
            PendingOrder: 创建的卖出挂单
        """
        self._order_counter += 1
        order_id = f"pending_sell_{timestamp}_{self._order_counter}"

        # 计算卖出金额
        amount = sell_price * quantity

        order = PendingOrder(
            order_id=order_id,
            price=sell_price,
            amount=amount,
            quantity=quantity,
            status=PendingOrderStatus.PENDING,
            side=PendingOrderSide.SELL,
            frozen_capital=Decimal("0"),  # 卖出不冻结资金
            kline_index=kline_index,
            created_at=timestamp,
            parent_order_id=parent_order_id
        )

        self._pending_orders[order_id] = order

        logger.debug(
            f"创建卖出挂单: {order_id}, 关联持仓: {parent_order_id}, "
            f"价格: {sell_price}"
        )

        return order

    def update_sell_order_price(
        self,
        order_id: str,
        new_price: Decimal
    ) -> bool:
        """
        更新卖出挂单价格

        动态更新卖出挂单的价格（每根K线根据EMA25变化更新）。

        Args:
            order_id: 卖出挂单ID
            new_price: 新价格

        Returns:
            bool: True表示更新成功
        """
        if order_id not in self._pending_orders:
            logger.warning(f"卖出挂单不存在: {order_id}")
            return False

        order = self._pending_orders[order_id]
        if not order.is_sell_order():
            logger.warning(f"订单 {order_id} 不是卖出挂单")
            return False

        old_price = order.price
        order.price = new_price
        order.amount = new_price * order.quantity

        logger.debug(
            f"更新卖出挂单价格: {order_id}, "
            f"{old_price} -> {new_price}"
        )

        return True

    def check_sell_order_fill(
        self,
        order: PendingOrder,
        kline_low: Decimal,
        kline_high: Decimal
    ) -> bool:
        """
        检查卖出挂单是否成交

        成交条件：挂单价格在K线的 [low, high] 范围内

        Args:
            order: 卖出挂单
            kline_low: K线最低价
            kline_high: K线最高价

        Returns:
            bool: True表示成交
        """
        return kline_low <= order.price <= kline_high

    def fill_sell_order(
        self,
        order_id: str,
        fill_timestamp: int,
        buy_price: Decimal
    ) -> Optional[Dict]:
        """
        确认卖出挂单成交

        标记卖出挂单为已成交，释放冻结资金（加上盈亏）。

        Args:
            order_id: 卖出挂单ID
            fill_timestamp: 成交时间戳
            buy_price: 原买入价格（用于计算盈亏）

        Returns:
            Optional[Dict]: 成交信息，包含盈亏数据
        """
        if order_id not in self._pending_orders:
            logger.warning(f"卖出挂单不存在: {order_id}")
            return None

        order = self._pending_orders[order_id]
        order.mark_filled(fill_timestamp)

        # 计算盈亏
        profit_loss = (order.price - buy_price) * order.quantity
        profit_rate = profit_loss / (buy_price * order.quantity) * 100

        # 释放资金：原冻结资金 + 盈亏
        released_capital = buy_price * order.quantity + profit_loss
        self._frozen_capital -= buy_price * order.quantity
        self._available_capital += released_capital

        # 移除已成交挂单
        del self._pending_orders[order_id]

        result = {
            'order_id': order_id,
            'parent_order_id': order.parent_order_id,
            'sell_price': order.price,
            'buy_price': buy_price,
            'quantity': order.quantity,
            'profit_loss': profit_loss,
            'profit_rate': profit_rate,
            'fill_timestamp': fill_timestamp
        }

        logger.debug(
            f"卖出挂单成交: {order_id}, "
            f"盈亏: {profit_loss} ({profit_rate:.2f}%)"
        )

        return result

    def get_pending_buy_orders(self) -> List[PendingOrder]:
        """
        获取所有待成交的买入挂单

        Returns:
            List[PendingOrder]: 买入挂单列表
        """
        return [
            order for order in self._pending_orders.values()
            if order.is_buy_order() and order.is_pending()
        ]

    def get_pending_sell_orders(self) -> List[PendingOrder]:
        """
        获取所有待成交的卖出挂单

        Returns:
            List[PendingOrder]: 卖出挂单列表
        """
        return [
            order for order in self._pending_orders.values()
            if order.is_sell_order() and order.is_pending()
        ]

    def get_sell_order_by_parent(
        self,
        parent_order_id: str
    ) -> Optional[PendingOrder]:
        """
        根据持仓ID获取卖出挂单

        Args:
            parent_order_id: 持仓订单ID

        Returns:
            Optional[PendingOrder]: 对应的卖出挂单
        """
        for order in self._pending_orders.values():
            if order.parent_order_id == parent_order_id and order.is_sell_order():
                return order
        return None

    def get_statistics(self) -> Dict:
        """
        获取统计信息

        Returns:
            Dict: 统计数据
        """
        return {
            'available_capital': float(self._available_capital),
            'frozen_capital': float(self._frozen_capital),
            'total_capital': float(self.total_capital),
            'pending_buy_orders': len(self.get_pending_buy_orders()),
            'pending_sell_orders': len(self.get_pending_sell_orders()),
            'insufficient_capital_count': self._insufficient_capital_count,
        }
