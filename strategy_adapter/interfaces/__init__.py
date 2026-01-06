"""
接口定义模块

包含策略适配层的核心接口：
- strategy: IStrategy接口（策略标准化接口）
"""

from .strategy import IStrategy

__all__ = [
    "IStrategy",
]
