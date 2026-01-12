"""
原子条件层 - 提供可组合的交易条件原子单元

本模块实现ICondition接口及其各类具体条件：
- 价格条件（PriceTouchesLevel, PriceInRange）
- 指标条件（BetaNegative, FutureEmaPrediction, IndicatorLessThan, PriceBelowMidLine）
- 周期条件（CyclePhaseIs, CyclePhaseIn）
- 逻辑组合（AndCondition, OrCondition, NotCondition）
"""

from .base import (
    ICondition,
    ConditionContext,
    ConditionResult,
)
from .price import (
    PriceTouchesLevel,
    PriceInRange,
)
from .indicator import (
    BetaNegative,
    BetaPositive,
    FutureEmaPrediction,
    IndicatorLessThan,
    PriceBelowMidLine,
)
from .cycle import (
    CyclePhaseIs,
    CyclePhaseIn,
)
from .logic import (
    AndCondition,
    OrCondition,
    NotCondition,
)

__all__ = [
    # 基础接口
    'ICondition',
    'ConditionContext',
    'ConditionResult',
    # 价格条件
    'PriceTouchesLevel',
    'PriceInRange',
    # 指标条件
    'BetaNegative',
    'BetaPositive',
    'FutureEmaPrediction',
    'IndicatorLessThan',
    'PriceBelowMidLine',
    # 周期条件
    'CyclePhaseIs',
    'CyclePhaseIn',
    # 逻辑组合
    'AndCondition',
    'OrCondition',
    'NotCondition',
]
