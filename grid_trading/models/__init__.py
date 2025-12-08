"""
网格交易系统数据模型
"""

# 新的网格交易模型
from .grid_config import GridConfig, GridMode
from .grid_level import GridLevel, GridLevelStatus, GridLevelSide
from .order_intent import OrderIntent, OrderIntentType, OrderSide, OrderStatus
from .trade_log import TradeLog, LogType
from .grid_statistics import GridStatistics

# 筛选系统的 dataclass 模型 (向后兼容)
from .market_symbol import MarketSymbol
from .volatility_metrics import VolatilityMetrics
from .trend_metrics import TrendMetrics
from .microstructure_metrics import MicrostructureMetrics
from .screening_result import ScreeningResult, calculate_grid_parameters

# 导入旧的 Django ORM 模型 (保持向后兼容 - 用于screening系统和数据更新)
from ..django_models import (
    GridZone,
    StrategyConfig,
    GridStrategy,
    GridOrder,
    SymbolInfo,
    KlineData,
    ScreeningRecord,
    ScreeningResultModel,
)

__all__ = [
    # 网格交易模型 (新)
    'GridConfig',
    'GridLevel',
    'OrderIntent',
    'TradeLog',
    'GridStatistics',
    # 枚举
    'GridMode',
    'GridLevelStatus',
    'GridLevelSide',
    'OrderIntentType',
    'OrderSide',
    'OrderStatus',
    'LogType',
    # 筛选系统 dataclass 模型 (向后兼容)
    'MarketSymbol',
    'VolatilityMetrics',
    'TrendMetrics',
    'MicrostructureMetrics',
    'ScreeningResult',
    'calculate_grid_parameters',
    # 旧 Django ORM 模型 (向后兼容 - 用于screening系统和K线数据管理)
    'GridZone',
    'StrategyConfig',
    'GridStrategy',
    'GridOrder',
    'SymbolInfo',
    'KlineData',
    'ScreeningRecord',
    'ScreeningResultModel',
]
