"""
逻辑组合条件

包含：
- AndCondition: 所有子条件都满足时触发
- OrCondition: 任一子条件满足时触发
- NotCondition: 子条件不满足时触发
"""

from typing import List, Tuple

from .base import ICondition, ConditionContext, ConditionResult


class AndCondition(ICondition):
    """与条件组合

    所有子条件都满足时触发。采用短路评估，第一个不满足即返回。

    Args:
        *conditions: 子条件列表

    Examples:
        >>> # 方式1: 构造函数
        >>> condition = AndCondition(
        ...     PriceTouchesLevel('p5', 'below'),
        ...     FutureEmaPrediction(6, above_close=True)
        ... )
        >>> # 方式2: 运算符
        >>> condition = PriceTouchesLevel('p5', 'below') & FutureEmaPrediction(6, True)
    """

    def __init__(self, *conditions: ICondition):
        if len(conditions) < 2:
            raise ValueError("AndCondition requires at least 2 conditions")
        self.conditions: Tuple[ICondition, ...] = conditions

    def evaluate(self, ctx: ConditionContext) -> ConditionResult:
        last_result = None
        for condition in self.conditions:
            result = condition.evaluate(ctx)
            if not result.triggered:
                return ConditionResult.not_triggered()
            last_result = result

        # 所有条件都满足，返回最后一个结果（保留价格和原因）
        if last_result:
            return ConditionResult.triggered_with(
                price=last_result.price,
                reason=f"AND组合满足: {last_result.reason}",
                condition_name=self.get_name()
            )
        return ConditionResult.not_triggered()

    def get_name(self) -> str:
        names = [c.get_name() for c in self.conditions]
        return f"and({', '.join(names)})"

    def get_description(self) -> str:
        descriptions = [c.get_description() for c in self.conditions]
        return " 且 ".join(descriptions)

    def get_required_indicators(self) -> List[str]:
        indicators = []
        for condition in self.conditions:
            indicators.extend(condition.get_required_indicators())
        return list(set(indicators))


class OrCondition(ICondition):
    """或条件组合

    任一子条件满足时触发。采用短路评估，第一个满足即返回。

    Args:
        *conditions: 子条件列表

    Examples:
        >>> # 方式1: 构造函数
        >>> condition = OrCondition(
        ...     PriceInRange('ema25'),
        ...     PriceTouchesLevel('p95', 'above')
        ... )
        >>> # 方式2: 运算符
        >>> condition = PriceInRange('ema25') | PriceTouchesLevel('p95', 'above')
    """

    def __init__(self, *conditions: ICondition):
        if len(conditions) < 2:
            raise ValueError("OrCondition requires at least 2 conditions")
        self.conditions: Tuple[ICondition, ...] = conditions

    def evaluate(self, ctx: ConditionContext) -> ConditionResult:
        for condition in self.conditions:
            result = condition.evaluate(ctx)
            if result.triggered:
                return ConditionResult.triggered_with(
                    price=result.price,
                    reason=f"OR组合满足: {result.reason}",
                    condition_name=self.get_name()
                )
        return ConditionResult.not_triggered()

    def get_name(self) -> str:
        names = [c.get_name() for c in self.conditions]
        return f"or({', '.join(names)})"

    def get_description(self) -> str:
        descriptions = [c.get_description() for c in self.conditions]
        return " 或 ".join(descriptions)

    def get_required_indicators(self) -> List[str]:
        indicators = []
        for condition in self.conditions:
            indicators.extend(condition.get_required_indicators())
        return list(set(indicators))


class NotCondition(ICondition):
    """取反条件

    子条件不满足时触发。

    Args:
        condition: 子条件

    Examples:
        >>> # 方式1: 构造函数
        >>> condition = NotCondition(BetaNegative())
        >>> # 方式2: 运算符
        >>> condition = ~BetaNegative()
    """

    def __init__(self, condition: ICondition):
        self.condition = condition

    def evaluate(self, ctx: ConditionContext) -> ConditionResult:
        result = self.condition.evaluate(ctx)
        if not result.triggered:
            return ConditionResult.triggered_with(
                reason=f"NOT条件满足: {self.condition.get_description()}不成立",
                condition_name=self.get_name()
            )
        return ConditionResult.not_triggered()

    def get_name(self) -> str:
        return f"not({self.condition.get_name()})"

    def get_description(self) -> str:
        return f"非({self.condition.get_description()})"

    def get_required_indicators(self) -> List[str]:
        return self.condition.get_required_indicators()
