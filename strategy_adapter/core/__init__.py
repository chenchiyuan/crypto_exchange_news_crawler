"""
核心组件模块

包含策略适配层的核心组件：
- signal_converter: SignalConverter（信号转换器）
- unified_order_manager: UnifiedOrderManager（统一订单管理器）
- strategy_adapter: StrategyAdapter（策略适配器）
"""

from .signal_converter import SignalConverter
from .unified_order_manager import UnifiedOrderManager
from .strategy_adapter import StrategyAdapter

__all__ = [
    "SignalConverter",
    "UnifiedOrderManager",
    "StrategyAdapter",
]
