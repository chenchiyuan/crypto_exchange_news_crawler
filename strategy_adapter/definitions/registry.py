"""
策略注册表

包含：
- StrategyRegistry: 策略注册和查询管理
"""

from typing import Dict, List, Optional

from .base import StrategyDefinition


class StrategyRegistry:
    """策略注册表

    管理所有策略定义的注册和查询。使用类方法实现全局单例模式。

    Examples:
        >>> # 注册策略
        >>> StrategyRegistry.register(strategy_1)
        >>> StrategyRegistry.register(strategy_2)
        >>>
        >>> # 查询策略
        >>> strategy = StrategyRegistry.get('strategy_1')
        >>>
        >>> # 列出所有策略
        >>> all_strategies = StrategyRegistry.list_all()
        >>>
        >>> # 按方向筛选
        >>> long_strategies = StrategyRegistry.list_by_direction('long')
    """

    _strategies: Dict[str, StrategyDefinition] = {}

    @classmethod
    def register(cls, strategy: StrategyDefinition) -> None:
        """注册策略定义

        Args:
            strategy: 策略定义

        Raises:
            ValueError: 如果策略ID已存在
        """
        if strategy.id in cls._strategies:
            # 允许覆盖，但打印警告
            import warnings
            warnings.warn(
                f"Strategy '{strategy.id}' already registered, overwriting.",
                UserWarning
            )
        cls._strategies[strategy.id] = strategy

    @classmethod
    def get(cls, strategy_id: str) -> Optional[StrategyDefinition]:
        """获取策略定义

        Args:
            strategy_id: 策略ID

        Returns:
            策略定义，如果不存在返回None
        """
        return cls._strategies.get(strategy_id)

    @classmethod
    def list_all(cls) -> List[StrategyDefinition]:
        """列出所有注册的策略

        Returns:
            策略定义列表
        """
        return list(cls._strategies.values())

    @classmethod
    def list_by_direction(cls, direction: str) -> List[StrategyDefinition]:
        """按交易方向筛选策略

        Args:
            direction: 'long' 或 'short'

        Returns:
            符合方向的策略列表
        """
        return [s for s in cls._strategies.values() if s.direction == direction]

    @classmethod
    def list_ids(cls) -> List[str]:
        """列出所有策略ID

        Returns:
            策略ID列表
        """
        return list(cls._strategies.keys())

    @classmethod
    def clear(cls) -> None:
        """清空注册表（主要用于测试）"""
        cls._strategies.clear()

    @classmethod
    def count(cls) -> int:
        """返回注册的策略数量"""
        return len(cls._strategies)
