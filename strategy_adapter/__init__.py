"""
策略适配层 (Strategy Adapter Layer)

这是一个连接应用层策略和回测层的中间层，提供以下核心功能：

1. **标准化策略接口** (IStrategy)：定义统一的策略行为规范
2. **统一订单管理** (UnifiedOrderManager)：整合应用层和回测层的订单管理逻辑
3. **信号转换** (SignalConverter)：将应用层信号转换为vectorbt格式
4. **策略适配** (StrategyAdapter)：编排策略、订单管理和信号转换

模块结构:
├── interfaces/     - 策略接口定义
├── core/          - 核心组件（订单管理器、适配器、信号转换器）
├── models/        - 数据模型（Order、枚举类型）
├── adapters/      - 应用层策略适配器（如DDPSZStrategy）
└── tests/         - 单元测试和集成测试

迭代编号: 013
迭代名称: 策略适配层
创建日期: 2026-01-06
文档版本: 1.0
"""

from strategy_adapter.interfaces import IStrategy
from strategy_adapter.models import Order, OrderStatus, OrderSide
from strategy_adapter.core import (
    SignalConverter,
    UnifiedOrderManager,
    StrategyAdapter
)
from strategy_adapter.adapters import DDPSZStrategy

__version__ = "1.0.0"
__author__ = "PowerBy Engineer"

__all__ = [
    "IStrategy",
    "Order",
    "OrderStatus",
    "OrderSide",
    "UnifiedOrderManager",
    "StrategyAdapter",
    "SignalConverter",
    "DDPSZStrategy",
]
