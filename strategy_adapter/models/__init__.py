"""
数据模型模块

包含策略适配层的核心数据结构：
- enums: OrderStatus和OrderSide枚举类型
- order: Order数据类（订单完整生命周期信息）
"""

from .enums import OrderStatus, OrderSide
from .order import Order

__all__ = [
    "OrderStatus",
    "OrderSide",
    "Order",
]
