"""
策略选择器

Purpose:
    提供策略ID的解析、验证和分类功能。
    支持--strategies参数的解析和验证。

关联任务: TASK-015-004
关联需求: FP-015-010, FP-015-015（prd.md）
关联架构: architecture.md#StrategySelector

Usage:
    from strategy_adapter.core.strategy_selector import StrategySelector

    # 解析策略字符串
    strategies = StrategySelector.parse("1,2,3,4")  # [1, 2, 3, 4]

    # 验证策略有效性
    StrategySelector.validate([1, 2])  # OK
    StrategySelector.validate([5])  # raises ValueError

    # 检查策略类型
    StrategySelector.has_long([1, 2])  # True
    StrategySelector.has_short([3, 4])  # True
"""

from typing import List, Set


class StrategySelector:
    """
    策略选择器

    策略ID定义:
        - 1: EMA斜率未来预测做多
        - 2: 惯性下跌中值突破做多
        - 3: EMA斜率未来预测做空
        - 4: 惯性上涨中值突破做空

    Attributes:
        VALID_STRATEGIES: 所有有效的策略ID集合
        LONG_STRATEGIES: 做多策略ID集合 (1, 2)
        SHORT_STRATEGIES: 做空策略ID集合 (3, 4)
    """

    VALID_STRATEGIES: Set[int] = {1, 2, 3, 4}
    LONG_STRATEGIES: Set[int] = {1, 2}
    SHORT_STRATEGIES: Set[int] = {3, 4}

    @classmethod
    def parse(cls, strategies_str: str) -> List[int]:
        """
        解析策略字符串

        Args:
            strategies_str: 逗号分隔的策略ID字符串，如 "1,2,3,4"

        Returns:
            策略ID列表，如 [1, 2, 3, 4]

        Raises:
            ValueError: 当策略ID无效时

        Example:
            >>> StrategySelector.parse("1,2")
            [1, 2]
            >>> StrategySelector.parse("3,4")
            [3, 4]
            >>> StrategySelector.parse("5")
            ValueError: 无效的策略ID: 5。有效值: 1, 2, 3, 4
        """
        strategies = []
        for part in strategies_str.split(','):
            part = part.strip()
            if not part:
                continue
            try:
                strategy_id = int(part)
            except ValueError:
                raise ValueError(
                    f"无效的策略ID: {part}。策略ID必须是整数。"
                )
            strategies.append(strategy_id)

        if not strategies:
            raise ValueError("策略列表不能为空")

        cls.validate(strategies)
        return strategies

    @classmethod
    def validate(cls, strategies: List[int]) -> None:
        """
        验证策略ID有效性

        Args:
            strategies: 策略ID列表

        Raises:
            ValueError: 当存在无效的策略ID时

        Example:
            >>> StrategySelector.validate([1, 2])  # OK
            >>> StrategySelector.validate([5])
            ValueError: 无效的策略ID: 5。有效值: 1, 2, 3, 4
        """
        for strategy_id in strategies:
            if strategy_id not in cls.VALID_STRATEGIES:
                valid_str = ', '.join(str(s) for s in sorted(cls.VALID_STRATEGIES))
                raise ValueError(
                    f"无效的策略ID: {strategy_id}。有效值: {valid_str}"
                )

    @classmethod
    def has_long(cls, strategies: List[int]) -> bool:
        """
        检查是否包含做多策略

        Args:
            strategies: 策略ID列表

        Returns:
            True如果包含策略1或2

        Example:
            >>> StrategySelector.has_long([1, 2])
            True
            >>> StrategySelector.has_long([3, 4])
            False
        """
        return bool(set(strategies) & cls.LONG_STRATEGIES)

    @classmethod
    def has_short(cls, strategies: List[int]) -> bool:
        """
        检查是否包含做空策略

        Args:
            strategies: 策略ID列表

        Returns:
            True如果包含策略3或4

        Example:
            >>> StrategySelector.has_short([3, 4])
            True
            >>> StrategySelector.has_short([1, 2])
            False
        """
        return bool(set(strategies) & cls.SHORT_STRATEGIES)

    @classmethod
    def get_long_strategies(cls, strategies: List[int]) -> List[int]:
        """
        获取做多策略子集

        Args:
            strategies: 策略ID列表

        Returns:
            做多策略ID列表（保持原顺序）

        Example:
            >>> StrategySelector.get_long_strategies([1, 3, 2, 4])
            [1, 2]
        """
        return [s for s in strategies if s in cls.LONG_STRATEGIES]

    @classmethod
    def get_short_strategies(cls, strategies: List[int]) -> List[int]:
        """
        获取做空策略子集

        Args:
            strategies: 策略ID列表

        Returns:
            做空策略ID列表（保持原顺序）

        Example:
            >>> StrategySelector.get_short_strategies([1, 3, 2, 4])
            [3, 4]
        """
        return [s for s in strategies if s in cls.SHORT_STRATEGIES]
