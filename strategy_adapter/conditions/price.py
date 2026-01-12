"""
价格相关条件

包含：
- PriceTouchesLevel: 价格触及指标级别
- PriceInRange: 价格在指标范围内（K线包含指标值）
"""

from decimal import Decimal
from typing import List

from .base import ICondition, ConditionContext, ConditionResult


class PriceTouchesLevel(ICondition):
    """价格触及指标级别条件

    判断K线价格是否触及某个指标级别。

    Args:
        level: 指标名称（'p5', 'p95', 'ema25' 等）
        direction: 触及方向
            - 'below': low <= level（价格下探触及）
            - 'above': high >= level（价格上冲触及）
        strict: 是否严格比较
            - True: 使用 < 或 >
            - False: 使用 <= 或 >=（默认）

    Examples:
        >>> # 价格触及P5（下方支撑），包含等于
        >>> condition = PriceTouchesLevel('p5', 'below')
        >>> # 价格跌破P5（严格小于）
        >>> condition = PriceTouchesLevel('p5', 'below', strict=True)
    """

    def __init__(self, level: str, direction: str = 'below', strict: bool = False):
        if direction not in ('below', 'above'):
            raise ValueError(f"direction must be 'below' or 'above', got '{direction}'")
        self.level = level
        self.direction = direction
        self.strict = strict

    def evaluate(self, ctx: ConditionContext) -> ConditionResult:
        level_value = ctx.get_indicator(self.level)
        if level_value is None:
            return ConditionResult.not_triggered()

        low = ctx.get_kline_float('low')
        high = ctx.get_kline_float('high')

        if low is None or high is None:
            return ConditionResult.not_triggered()

        level_float = float(level_value)
        triggered = False

        if self.direction == 'below':
            if self.strict:
                triggered = low < level_float
                reason = f"价格跌破{self.level}({level_float:.4f})"
            else:
                triggered = low <= level_float
                reason = f"价格下探触及{self.level}({level_float:.4f})"
            trigger_price = Decimal(str(level_float))
        else:
            if self.strict:
                triggered = high > level_float
                reason = f"价格突破{self.level}({level_float:.4f})"
            else:
                triggered = high >= level_float
                reason = f"价格上冲触及{self.level}({level_float:.4f})"
            trigger_price = Decimal(str(level_float))

        if triggered:
            return ConditionResult.triggered_with(
                price=trigger_price,
                reason=reason,
                condition_name=self.get_name()
            )
        return ConditionResult.not_triggered()

    def get_name(self) -> str:
        suffix = "_strict" if self.strict else ""
        return f"price_touches_{self.level}_{self.direction}{suffix}"

    def get_description(self) -> str:
        if self.direction == 'below':
            if self.strict:
                return f"价格跌破{self.level}"
            return f"价格下探触及{self.level}"
        if self.strict:
            return f"价格突破{self.level}"
        return f"价格上冲触及{self.level}"

    def get_required_indicators(self) -> List[str]:
        return [self.level]


class PriceInRange(ICondition):
    """价格在指标范围内条件

    判断K线是否"包含"某个指标值，即指标值在K线的high和low之间。
    常用于判断价格是否回归到某个均线。

    Args:
        indicator: 指标名称（'ema25' 等）

    Examples:
        >>> # 价格回归EMA25
        >>> condition = PriceInRange('ema25')
    """

    def __init__(self, indicator: str):
        self.indicator = indicator

    def evaluate(self, ctx: ConditionContext) -> ConditionResult:
        indicator_value = ctx.get_indicator(self.indicator)
        if indicator_value is None:
            return ConditionResult.not_triggered()

        low = ctx.get_kline_float('low')
        high = ctx.get_kline_float('high')

        if low is None or high is None:
            return ConditionResult.not_triggered()

        indicator_float = float(indicator_value)

        # 判断指标值是否在K线范围内
        if low <= indicator_float <= high:
            return ConditionResult.triggered_with(
                price=Decimal(str(indicator_float)),
                reason=f"价格包含{self.indicator}({indicator_float:.4f})",
                condition_name=self.get_name()
            )
        return ConditionResult.not_triggered()

    def get_name(self) -> str:
        return f"price_in_range_{self.indicator}"

    def get_description(self) -> str:
        return f"价格包含{self.indicator}"

    def get_required_indicators(self) -> List[str]:
        return [self.indicator]
