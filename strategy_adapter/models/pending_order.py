"""
限价挂单数据类定义

本模块定义了限价挂单的数据结构PendingOrder，用于策略11的限价挂单机制：
- 买入挂单：记录挂单价格、数量、冻结资金等信息
- 卖出挂单：记录关联持仓ID、动态更新的卖出价格
- 状态管理：pending/filled/cancelled三种状态

迭代编号: 027 (策略11-限价挂单买卖机制)
创建日期: 2026-01-10
关联任务: TASK-027-001
关联需求: FP-027-001 (function-points.md)
关联架构: architecture.md#5.1 PendingOrder数据结构
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from enum import Enum


class PendingOrderStatus(Enum):
    """
    挂单状态枚举

    Attributes:
        PENDING (str): 待成交 - 挂单已创建但未成交
        FILLED (str): 已成交 - 挂单已成交
        CANCELLED (str): 已取消 - 挂单被取消（如每根K线重新挂单时取消旧挂单）
    """
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"


class PendingOrderSide(Enum):
    """
    挂单方向枚举

    Attributes:
        BUY (str): 买入挂单
        SELL (str): 卖出挂单
    """
    BUY = "buy"
    SELL = "sell"


@dataclass
class PendingOrder:
    """
    限价挂单数据结构

    设计原则：
    - 完整性：包含挂单生命周期的所有信息
    - 资金追踪：记录冻结资金用于资金管理
    - 关联性：卖出挂单通过parent_order_id关联持仓

    Attributes:
        order_id (str): 挂单唯一标识符，格式：pending_{timestamp}_{index}
        price (Decimal): 挂单价格
        amount (Decimal): 挂单金额(USDT)
        quantity (Decimal): 挂单数量 = amount / price
        status (PendingOrderStatus): 挂单状态（pending/filled/cancelled）
        side (PendingOrderSide): 挂单方向（buy/sell）
        frozen_capital (Decimal): 冻结资金（买入挂单时等于amount）
        kline_index (int): 创建时的K线索引
        created_at (int): 创建时间戳（毫秒）
        filled_at (Optional[int]): 成交时间戳（毫秒），未成交时为None
        parent_order_id (Optional[str]): 卖出挂单关联的持仓订单ID

    Example:
        >>> # 创建买入挂单
        >>> buy_order = PendingOrder(
        ...     order_id="pending_1736500800000_0",
        ...     price=Decimal("3200"),
        ...     amount=Decimal("100"),
        ...     quantity=Decimal("0.03125"),
        ...     status=PendingOrderStatus.PENDING,
        ...     side=PendingOrderSide.BUY,
        ...     frozen_capital=Decimal("100"),
        ...     kline_index=100,
        ...     created_at=1736500800000
        ... )

        >>> # 创建卖出挂单（关联持仓）
        >>> sell_order = PendingOrder(
        ...     order_id="pending_1736504400000_sell_0",
        ...     price=Decimal("3360"),  # min(3200*1.05, EMA25)
        ...     amount=Decimal("105"),
        ...     quantity=Decimal("0.03125"),
        ...     status=PendingOrderStatus.PENDING,
        ...     side=PendingOrderSide.SELL,
        ...     frozen_capital=Decimal("0"),  # 卖出挂单不冻结资金
        ...     kline_index=101,
        ...     created_at=1736504400000,
        ...     parent_order_id="order_1736500800000"
        ... )
    """
    # 基础信息
    order_id: str
    price: Decimal
    amount: Decimal
    quantity: Decimal
    status: PendingOrderStatus
    side: PendingOrderSide

    # 资金管理
    frozen_capital: Decimal

    # 时间信息
    kline_index: int
    created_at: int
    filled_at: Optional[int] = None

    # 关联信息（卖出挂单关联持仓）
    parent_order_id: Optional[str] = None

    # 扩展字段
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """
        转换为字典（用于日志或调试）

        Returns:
            dict: 挂单的字典表示，所有Decimal类型转换为float
        """
        return {
            'order_id': self.order_id,
            'price': float(self.price),
            'amount': float(self.amount),
            'quantity': float(self.quantity),
            'status': self.status.value,
            'side': self.side.value,
            'frozen_capital': float(self.frozen_capital),
            'kline_index': self.kline_index,
            'created_at': self.created_at,
            'filled_at': self.filled_at,
            'parent_order_id': self.parent_order_id,
            'metadata': self.metadata,
        }

    def mark_filled(self, filled_timestamp: int) -> None:
        """
        标记挂单为已成交

        Args:
            filled_timestamp: 成交时间戳（毫秒）
        """
        self.status = PendingOrderStatus.FILLED
        self.filled_at = filled_timestamp

    def mark_cancelled(self) -> None:
        """
        标记挂单为已取消
        """
        self.status = PendingOrderStatus.CANCELLED

    def is_pending(self) -> bool:
        """
        检查挂单是否待成交

        Returns:
            bool: True表示待成交
        """
        return self.status == PendingOrderStatus.PENDING

    def is_buy_order(self) -> bool:
        """
        检查是否为买入挂单

        Returns:
            bool: True表示买入挂单
        """
        return self.side == PendingOrderSide.BUY

    def is_sell_order(self) -> bool:
        """
        检查是否为卖出挂单

        Returns:
            bool: True表示卖出挂单
        """
        return self.side == PendingOrderSide.SELL
