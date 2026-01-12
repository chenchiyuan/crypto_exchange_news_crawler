"""
指标相关条件

包含：
- BetaNegative: Beta斜率为负
- BetaPositive: Beta斜率为正
- FutureEmaPrediction: 未来EMA预测
- IndicatorLessThan: 指标小于另一指标
- PriceBelowMidLine: 价格低于中值线
- IndicatorComparison: 通用指标比较
"""

from decimal import Decimal
from typing import List, Optional

from .base import ICondition, ConditionContext, ConditionResult


class BetaNegative(ICondition):
    """Beta斜率为负条件

    判断EMA斜率（beta）是否为负值，表示下跌趋势。

    Examples:
        >>> # 判断趋势下跌
        >>> condition = BetaNegative()
    """

    def __init__(self):
        pass

    def evaluate(self, ctx: ConditionContext) -> ConditionResult:
        beta = ctx.get_indicator('beta')
        if beta is None:
            return ConditionResult.not_triggered()

        beta_float = float(beta)
        if beta_float < 0:
            return ConditionResult.triggered_with(
                reason=f"Beta为负({beta_float:.6f})",
                condition_name=self.get_name()
            )
        return ConditionResult.not_triggered()

    def get_name(self) -> str:
        return "beta_negative"

    def get_description(self) -> str:
        return "Beta斜率为负（下跌趋势）"

    def get_required_indicators(self) -> List[str]:
        return ['beta']


class BetaPositive(ICondition):
    """Beta斜率为正条件

    判断EMA斜率（beta）是否为正值，表示上涨趋势。

    Examples:
        >>> # 判断趋势上涨
        >>> condition = BetaPositive()
    """

    def __init__(self):
        pass

    def evaluate(self, ctx: ConditionContext) -> ConditionResult:
        beta = ctx.get_indicator('beta')
        if beta is None:
            return ConditionResult.not_triggered()

        beta_float = float(beta)
        if beta_float > 0:
            return ConditionResult.triggered_with(
                reason=f"Beta为正({beta_float:.6f})",
                condition_name=self.get_name()
            )
        return ConditionResult.not_triggered()

    def get_name(self) -> str:
        return "beta_positive"

    def get_description(self) -> str:
        return "Beta斜率为正（上涨趋势）"

    def get_required_indicators(self) -> List[str]:
        return ['beta']


class FutureEmaPrediction(ICondition):
    """未来EMA预测条件

    基于当前EMA和Beta斜率预测未来EMA值，与当前收盘价比较。

    Args:
        periods: 预测周期数（默认6）
        above_close:
            - True: 预测EMA > 收盘价时触发（看多信号）
            - False: 预测EMA < 收盘价时触发（看空信号）

    计算公式:
        future_ema = ema25 + (beta * periods)

    Examples:
        >>> # 策略1: 预测EMA上穿收盘价
        >>> condition = FutureEmaPrediction(periods=6, above_close=True)
        >>> # 策略3/4: 预测EMA下穿收盘价
        >>> condition = FutureEmaPrediction(periods=6, above_close=False)
    """

    def __init__(self, periods: int = 6, above_close: bool = True):
        self.periods = periods
        self.above_close = above_close

    def evaluate(self, ctx: ConditionContext) -> ConditionResult:
        ema = ctx.get_indicator('ema25')
        beta = ctx.get_indicator('beta')
        close = ctx.get_kline_float('close')

        if ema is None or beta is None or close is None:
            return ConditionResult.not_triggered()

        ema_float = float(ema)
        beta_float = float(beta)
        close_float = float(close)

        # 预测未来EMA
        future_ema = ema_float + (beta_float * self.periods)

        triggered = False
        if self.above_close:
            triggered = future_ema > close_float
            direction = "上穿"
        else:
            triggered = future_ema < close_float
            direction = "下穿"

        if triggered:
            return ConditionResult.triggered_with(
                price=Decimal(str(future_ema)),
                reason=f"预测{self.periods}周期后EMA({future_ema:.4f}){direction}收盘价({close_float:.4f})",
                condition_name=self.get_name()
            )
        return ConditionResult.not_triggered()

    def get_name(self) -> str:
        direction = "above" if self.above_close else "below"
        return f"future_ema_prediction_{self.periods}_{direction}"

    def get_description(self) -> str:
        direction = "高于" if self.above_close else "低于"
        return f"预测{self.periods}周期后EMA{direction}收盘价"

    def get_required_indicators(self) -> List[str]:
        return ['ema25', 'beta']


class IndicatorLessThan(ICondition):
    """指标小于另一指标条件

    判断一个指标是否小于另一个指标。

    Args:
        indicator1: 第一个指标名称
        indicator2: 第二个指标名称
        strict: 是否严格小于（默认True）

    Examples:
        >>> # 惯性中值小于P5
        >>> condition = IndicatorLessThan('inertia_mid', 'p5')
    """

    def __init__(self, indicator1: str, indicator2: str, strict: bool = True):
        self.indicator1 = indicator1
        self.indicator2 = indicator2
        self.strict = strict

    def evaluate(self, ctx: ConditionContext) -> ConditionResult:
        value1 = ctx.get_indicator(self.indicator1)
        value2 = ctx.get_indicator(self.indicator2)

        if value1 is None or value2 is None:
            return ConditionResult.not_triggered()

        v1_float = float(value1)
        v2_float = float(value2)

        if self.strict:
            triggered = v1_float < v2_float
            op = "<"
        else:
            triggered = v1_float <= v2_float
            op = "<="

        if triggered:
            return ConditionResult.triggered_with(
                reason=f"{self.indicator1}({v1_float:.4f}) {op} {self.indicator2}({v2_float:.4f})",
                condition_name=self.get_name()
            )
        return ConditionResult.not_triggered()

    def get_name(self) -> str:
        suffix = "_strict" if self.strict else ""
        return f"indicator_less_than_{self.indicator1}_{self.indicator2}{suffix}"

    def get_description(self) -> str:
        op = "小于" if self.strict else "小于等于"
        return f"{self.indicator1}{op}{self.indicator2}"

    def get_required_indicators(self) -> List[str]:
        return [self.indicator1, self.indicator2]


class PriceBelowMidLine(ICondition):
    """价格低于两个指标中值线条件

    计算两个指标的中值线，判断K线低点是否低于该中值线。
    常用于策略2的惯性下跌判断。

    Args:
        indicator1: 第一个指标名称
        indicator2: 第二个指标名称
        strict: 是否严格小于（默认True）

    计算公式:
        mid_line = (indicator1 + indicator2) / 2

    Examples:
        >>> # 价格低于惯性中值与P5的中值线
        >>> condition = PriceBelowMidLine('inertia_mid', 'p5')
    """

    def __init__(self, indicator1: str, indicator2: str, strict: bool = True):
        self.indicator1 = indicator1
        self.indicator2 = indicator2
        self.strict = strict

    def evaluate(self, ctx: ConditionContext) -> ConditionResult:
        value1 = ctx.get_indicator(self.indicator1)
        value2 = ctx.get_indicator(self.indicator2)
        low = ctx.get_kline_float('low')

        if value1 is None or value2 is None or low is None:
            return ConditionResult.not_triggered()

        v1_float = float(value1)
        v2_float = float(value2)
        low_float = float(low)

        # 计算中值线
        mid_line = (v1_float + v2_float) / 2

        if self.strict:
            triggered = low_float < mid_line
            op = "跌破"
        else:
            triggered = low_float <= mid_line
            op = "触及"

        if triggered:
            return ConditionResult.triggered_with(
                price=Decimal(str(mid_line)),
                reason=f"价格{op}中值线({mid_line:.4f})，由{self.indicator1}({v1_float:.4f})和{self.indicator2}({v2_float:.4f})计算",
                condition_name=self.get_name()
            )
        return ConditionResult.not_triggered()

    def get_name(self) -> str:
        suffix = "_strict" if self.strict else ""
        return f"price_below_midline_{self.indicator1}_{self.indicator2}{suffix}"

    def get_description(self) -> str:
        op = "跌破" if self.strict else "触及"
        return f"价格{op}{self.indicator1}与{self.indicator2}的中值线"

    def get_required_indicators(self) -> List[str]:
        return [self.indicator1, self.indicator2]
