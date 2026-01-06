"""
订单状态和方向枚举类型定义

本模块定义了策略适配层使用的核心枚举类型：
- OrderStatus: 订单生命周期状态（待成交、已成交、已平仓、已取消）
- OrderSide: 订单方向（买入做多、卖出做空）

这些枚举为订单管理提供类型安全性，避免使用魔法字符串。

迭代编号: 013 (策略适配层)
创建日期: 2026-01-06
关联任务: TASK-013-002
关联需求: FP-013-004 (prd.md)
"""

from enum import Enum


class OrderStatus(Enum):
    """
    订单状态枚举

    定义订单在生命周期中的各个状态。MVP阶段仅使用FILLED和CLOSED状态，
    PENDING和CANCELLED状态为未来扩展预留。

    Attributes:
        PENDING (str): 待成交 - 订单已创建但未成交（MVP阶段不使用）
        FILLED (str): 已成交/持仓中 - 订单已成交，等待卖出信号
        CLOSED (str): 已平仓 - 订单已卖出平仓，包含完整盈亏数据
        CANCELLED (str): 已取消 - 订单被取消（MVP阶段不使用）

    Example:
        >>> order.status = OrderStatus.FILLED
        >>> if order.status == OrderStatus.CLOSED:
        ...     print(f"盈亏: {order.profit_loss}")
    """
    PENDING = "pending"      # 待成交
    FILLED = "filled"        # 已成交（持仓中）
    CLOSED = "closed"        # 已平仓
    CANCELLED = "cancelled"  # 已取消


class OrderSide(Enum):
    """
    订单方向枚举

    定义订单的交易方向。MVP阶段仅支持做多（BUY），
    做空（SELL）功能为未来扩展预留。

    Attributes:
        BUY (str): 买入（做多）- 预期价格上涨获利
        SELL (str): 卖出（做空）- 预期价格下跌获利（MVP阶段不使用）

    Example:
        >>> order = Order(side=OrderSide.BUY, ...)
        >>> if order.side == OrderSide.BUY:
        ...     profit = (close_price - open_price) * quantity
    """
    BUY = "buy"    # 买入（做多）
    SELL = "sell"  # 卖出（做空）
