"""
周期阶段条件

包含：
- CyclePhaseIs: 周期等于指定阶段
- CyclePhaseIn: 周期在指定阶段列表内
"""

from typing import List

from .base import ICondition, ConditionContext, ConditionResult


class CyclePhaseIs(ICondition):
    """周期等于指定阶段条件

    判断当前周期阶段是否等于指定值。

    Args:
        phase: 周期阶段名称
            - 'bear_strong': 强势下跌
            - 'bear_warning': 下跌警告
            - 'consolidation': 盘整
            - 'bull_warning': 上涨警告
            - 'bull_strong': 强势上涨

    Examples:
        >>> # 策略6: 盘整区间
        >>> condition = CyclePhaseIs('consolidation')
        >>> # 策略8: 强势下跌
        >>> condition = CyclePhaseIs('bear_strong')
    """

    def __init__(self, phase: str):
        self.phase = phase

    def evaluate(self, ctx: ConditionContext) -> ConditionResult:
        cycle_phase = ctx.get_indicator('cycle_phase')
        if cycle_phase is None:
            return ConditionResult.not_triggered()

        if cycle_phase == self.phase:
            return ConditionResult.triggered_with(
                reason=f"当前周期为{self.phase}",
                condition_name=self.get_name()
            )
        return ConditionResult.not_triggered()

    def get_name(self) -> str:
        return f"cycle_phase_is_{self.phase}"

    def get_description(self) -> str:
        return f"周期阶段为{self.phase}"

    def get_required_indicators(self) -> List[str]:
        return ['cycle_phase']


class CyclePhaseIn(ICondition):
    """周期在指定阶段列表内条件

    判断当前周期阶段是否在指定的阶段列表中。

    Args:
        phases: 周期阶段名称列表

    Examples:
        >>> # 策略4: 非上涨区间（盘整或下跌）
        >>> condition = CyclePhaseIn(['consolidation', 'bear_warning', 'bear_strong'])
    """

    def __init__(self, phases: List[str]):
        self.phases = phases

    def evaluate(self, ctx: ConditionContext) -> ConditionResult:
        cycle_phase = ctx.get_indicator('cycle_phase')
        if cycle_phase is None:
            return ConditionResult.not_triggered()

        if cycle_phase in self.phases:
            return ConditionResult.triggered_with(
                reason=f"当前周期{cycle_phase}在允许列表{self.phases}中",
                condition_name=self.get_name()
            )
        return ConditionResult.not_triggered()

    def get_name(self) -> str:
        phases_str = "_".join(self.phases)
        return f"cycle_phase_in_{phases_str}"

    def get_description(self) -> str:
        return f"周期阶段在{self.phases}中"

    def get_required_indicators(self) -> List[str]:
        return ['cycle_phase']
