"""
数据模型模块

包含策略适配层的核心数据结构：
- enums: OrderStatus和OrderSide枚举类型
- order: Order数据类（订单完整生命周期信息）
- equity_point: EquityPoint数据类（权益曲线点）
- pending_order: PendingOrder数据类（限价挂单信息）
- db_models: Django数据库模型（BacktestResult, BacktestOrder）
"""

from .enums import OrderStatus, OrderSide
from .order import Order
from .equity_point import EquityPoint
from .pending_order import PendingOrder, PendingOrderStatus, PendingOrderSide

# Django 模型延迟导入
# 注意：Django 会在 app registry 初始化后自动加载 db_models 模块

__all__ = [
    "OrderStatus",
    "OrderSide",
    "Order",
    "EquityPoint",
    "PendingOrder",
    "PendingOrderStatus",
    "PendingOrderSide",
]


def get_db_models():
    """
    延迟导入 Django 数据库模型

    Purpose:
        避免在 Django app registry 初始化前导入 Django 模型导致的 AppRegistryNotReady 错误。
        使用函数延迟导入，只在实际需要时才加载 Django 模型。

    Returns:
        tuple: (BacktestResult, BacktestOrder) Django 模型类

    Example:
        >>> from strategy_adapter.models import get_db_models
        >>> BacktestResult, BacktestOrder = get_db_models()
    """
    from .db_models import BacktestResult, BacktestOrder
    return BacktestResult, BacktestOrder
