"""
执行引擎层 - 基于条件的信号计算和出场适配

本模块包含：
- ConditionBasedSignalCalculator: 基于策略定义生成交易信号
- ConditionBasedExit: 将ICondition适配为IExitCondition
"""

from .signal_calculator import ConditionBasedSignalCalculator
from .exit_adapter import ConditionBasedExit

__all__ = [
    'ConditionBasedSignalCalculator',
    'ConditionBasedExit',
]
