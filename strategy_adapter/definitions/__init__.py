"""
策略定义层 - 提供策略声明式定义和注册管理

本模块包含：
- StrategyDefinition: 策略声明式定义数据结构
- StrategyRegistry: 策略注册表
- 内置策略定义（策略1、2、7）
"""

from .base import StrategyDefinition
from .registry import StrategyRegistry

# 导入builtin模块以自动注册内置策略
from . import builtin  # noqa: F401

__all__ = [
    'StrategyDefinition',
    'StrategyRegistry',
]
