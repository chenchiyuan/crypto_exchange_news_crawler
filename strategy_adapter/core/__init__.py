"""
核心组件模块

包含策略适配层的核心组件：
- signal_converter: SignalConverter（信号转换器）
- unified_order_manager: UnifiedOrderManager（统一订单管理器）
- strategy_adapter: StrategyAdapter（策略适配器）
- strategy_selector: StrategySelector（策略选择器）
- project_loader: ProjectLoader（项目配置加载器，TASK-017）
- strategy_factory: StrategyFactory（策略工厂，TASK-017）
- shared_capital_manager: SharedCapitalManager（共享资金管理，TASK-017）
- multi_strategy_adapter: MultiStrategyAdapter（多策略适配器，TASK-017）
"""

from .signal_converter import SignalConverter
from .unified_order_manager import UnifiedOrderManager
from .strategy_adapter import StrategyAdapter
from .strategy_selector import StrategySelector
from .project_loader import ProjectLoader, ProjectLoaderError
from .strategy_factory import StrategyFactory
from .shared_capital_manager import SharedCapitalManager
from .multi_strategy_adapter import MultiStrategyAdapter

__all__ = [
    "SignalConverter",
    "UnifiedOrderManager",
    "StrategyAdapter",
    "StrategySelector",
    "ProjectLoader",
    "ProjectLoaderError",
    "StrategyFactory",
    "SharedCapitalManager",
    "MultiStrategyAdapter",
]
