"""
订单数据类定义

本模块定义了统一的订单数据结构Order，包含订单完整生命周期的所有信息：
- 开仓信息（价格、数量、时间戳）
- 平仓信息（价格、时间戳、理由）
- 策略信息（名称、ID、入场理由）
- 盈亏计算（自动计算盈亏金额和盈亏率）
- 手续费（开仓和平仓手续费）
- 扩展字段（通过metadata支持策略特定数据）

迭代编号: 013 (策略适配层)
创建日期: 2026-01-06
关联任务: TASK-013-003
关联需求: FP-013-003 (prd.md)
关联架构: architecture.md#4.2 数据模型模块
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from .enums import OrderStatus, OrderSide


@dataclass
class Order:
    """
    统一订单数据结构

    设计原则：
    - 完整性：包含订单完整生命周期的所有信息
    - 扩展性：通过metadata支持策略特定数据
    - 自包含：包含盈亏计算方法

    Attributes:
        id (str): 订单唯一标识符，格式：order_{timestamp}
        symbol (str): 交易对符号，如 "ETHUSDT"
        side (OrderSide): 订单方向（BUY做多 / SELL做空）
        status (OrderStatus): 订单状态（PENDING/FILLED/CLOSED/CANCELLED）

        open_timestamp (int): 开仓时间戳（毫秒）
        open_price (Decimal): 开仓价格
        quantity (Decimal): 数量（币的数量，如0.04348 ETH）
        position_value (Decimal): 开仓金额（USDT，如100）

        close_timestamp (Optional[int]): 平仓时间戳（毫秒），未平仓时为None
        close_price (Optional[Decimal]): 平仓价格，未平仓时为None
        close_reason (Optional[str]): 平仓理由，如"take_profit"/"stop_loss"/"strategy_signal"

        strategy_name (str): 策略名称，如"DDPS-Z"
        strategy_id (str): 策略ID，用于区分同一策略的不同子策略
        entry_reason (str): 入场理由，如"EMA斜率未来预测"

        profit_loss (Optional[Decimal]): 盈亏金额（USDT），自动计算
        profit_loss_rate (Optional[Decimal]): 盈亏率（%），自动计算
        holding_periods (Optional[int]): 持仓K线数，自动计算

        open_commission (Decimal): 开仓手续费（USDT）
        close_commission (Decimal): 平仓手续费（USDT）

        metadata (dict): 扩展字段，存储策略特定数据

    Example:
        >>> order = Order(
        ...     id="order_1736164800000",
        ...     symbol="ETHUSDT",
        ...     side=OrderSide.BUY,
        ...     status=OrderStatus.FILLED,
        ...     open_timestamp=1736164800000,
        ...     open_price=Decimal("2300"),
        ...     quantity=Decimal("0.04348"),
        ...     position_value=Decimal("100")
        ... )
        >>> order.calculate_pnl()  # 未平仓，profit_loss为None

    Raises:
        None: calculate_pnl()方法不抛出异常，优雅处理边界情况
    """
    # 基础信息
    id: str
    symbol: str
    side: OrderSide
    status: OrderStatus

    # 开仓信息
    open_timestamp: int
    open_price: Decimal
    quantity: Decimal
    position_value: Decimal      # 开仓金额

    # 平仓信息（可选）
    close_timestamp: Optional[int] = None
    close_price: Optional[Decimal] = None
    close_reason: Optional[str] = None  # "take_profit" | "stop_loss" | "strategy_signal"

    # 策略信息
    strategy_name: str = ""
    strategy_id: str = ""
    entry_reason: str = ""       # 入场理由

    # 盈亏计算（自动计算）
    profit_loss: Optional[Decimal] = None
    profit_loss_rate: Optional[Decimal] = None
    holding_periods: Optional[int] = None  # 持仓K线数

    # 手续费
    open_commission: Decimal = Decimal("0")
    close_commission: Decimal = Decimal("0")

    # 扩展字段（策略特定数据）
    metadata: dict = field(default_factory=dict)

    def calculate_pnl(self) -> None:
        """
        计算盈亏

        基于订单的开平仓价格、数量和手续费计算盈亏金额和盈亏率。

        计算逻辑：
        - 做多盈亏 = (平仓价 - 开仓价) * 数量 - 手续费
        - 做空盈亏 = (开仓价 - 平仓价) * 数量 - 手续费
        - 盈亏率 = 盈亏金额 / 开仓金额 * 100%

        边界处理：
        - 如果订单未平仓（close_price为None），不进行计算，保持profit_loss为None
        - 如果position_value为0，盈亏率设为None（避免除零）
        - 所有计算使用Decimal类型，确保金融精度

        Side Effects:
            更新以下字段：
            - self.profit_loss: 盈亏金额（USDT）
            - self.profit_loss_rate: 盈亏率（%）

        Example:
            >>> order = Order(
            ...     id="test_order",
            ...     symbol="ETHUSDT",
            ...     side=OrderSide.BUY,
            ...     status=OrderStatus.CLOSED,
            ...     open_price=Decimal("2300"),
            ...     close_price=Decimal("2350"),
            ...     quantity=Decimal("0.04348"),
            ...     position_value=Decimal("100"),
            ...     open_commission=Decimal("0.1"),
            ...     close_commission=Decimal("0.102")
            ... )
            >>> order.calculate_pnl()
            >>> print(order.profit_loss)  # 约1.972 USDT
            >>> print(order.profit_loss_rate)  # 约1.972%
        """
        # 边界检查：如果订单未平仓或状态不是CLOSED，不计算盈亏
        if self.status != OrderStatus.CLOSED or self.close_price is None:
            return

        # 计算盈亏金额
        if self.side == OrderSide.BUY:
            # 做多盈亏 = (平仓价 - 开仓价) * 数量
            self.profit_loss = (self.close_price - self.open_price) * self.quantity
        else:
            # 做空盈亏 = (开仓价 - 平仓价) * 数量
            self.profit_loss = (self.open_price - self.close_price) * self.quantity

        # 扣除手续费
        self.profit_loss -= (self.open_commission + self.close_commission)

        # 计算盈亏率（避免除零）
        if self.position_value > 0:
            self.profit_loss_rate = (self.profit_loss / self.position_value * Decimal("100"))
        else:
            # 边界处理：position_value为0时，盈亏率设为None
            self.profit_loss_rate = None

    def to_dict(self) -> dict:
        """
        转换为字典（用于API响应或持久化）

        将Order对象转换为JSON可序列化的字典，所有Decimal类型转换为float。

        Returns:
            dict: 订单的字典表示，所有字段都转换为基础类型

        Example:
            >>> order = Order(id="order_123", symbol="ETHUSDT", ...)
            >>> order_dict = order.to_dict()
            >>> print(order_dict['id'])  # "order_123"
            >>> print(type(order_dict['open_price']))  # <class 'float'>
        """
        return {
            'id': self.id,
            'symbol': self.symbol,
            'side': self.side.value,
            'status': self.status.value,
            'open_timestamp': self.open_timestamp,
            'open_price': float(self.open_price),
            'quantity': float(self.quantity),
            'position_value': float(self.position_value),
            'close_timestamp': self.close_timestamp,
            'close_price': float(self.close_price) if self.close_price else None,
            'close_reason': self.close_reason,
            'strategy_name': self.strategy_name,
            'strategy_id': self.strategy_id,
            'entry_reason': self.entry_reason,
            'profit_loss': float(self.profit_loss) if self.profit_loss else None,
            'profit_loss_rate': float(self.profit_loss_rate) if self.profit_loss_rate else None,
            'holding_periods': self.holding_periods,
            'open_commission': float(self.open_commission),
            'close_commission': float(self.close_commission),
            'metadata': self.metadata,
        }
