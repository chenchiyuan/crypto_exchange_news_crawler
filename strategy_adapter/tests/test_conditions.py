"""
原子条件单元测试

测试所有原子条件的正向触发、反向不触发、边界情况。
"""

import math
import pytest
from decimal import Decimal

from strategy_adapter.conditions import (
    ICondition,
    ConditionContext,
    ConditionResult,
    PriceTouchesLevel,
    PriceInRange,
    BetaNegative,
    BetaPositive,
    FutureEmaPrediction,
    IndicatorLessThan,
    PriceBelowMidLine,
    CyclePhaseIs,
    CyclePhaseIn,
    AndCondition,
    OrCondition,
    NotCondition,
)


class TestConditionResult:
    """ConditionResult 测试"""

    def test_not_triggered(self):
        result = ConditionResult.not_triggered()
        assert result.triggered is False
        assert result.price is None
        assert result.reason is None

    def test_triggered_with(self):
        result = ConditionResult.triggered_with(
            price=Decimal('100.5'),
            reason='测试原因',
            condition_name='test_condition'
        )
        assert result.triggered is True
        assert result.price == Decimal('100.5')
        assert result.reason == '测试原因'
        assert result.condition_name == 'test_condition'


class TestConditionContext:
    """ConditionContext 测试"""

    def test_get_indicator(self):
        ctx = ConditionContext(
            kline={'open': 100, 'high': 110, 'low': 90, 'close': 105},
            indicators={'ema25': 102.5, 'beta': 0.5}
        )
        assert ctx.get_indicator('ema25') == 102.5
        assert ctx.get_indicator('beta') == 0.5
        assert ctx.get_indicator('nonexistent') is None
        assert ctx.get_indicator('nonexistent', 0) == 0

    def test_get_indicator_nan(self):
        ctx = ConditionContext(
            kline={'close': 100},
            indicators={'nan_value': float('nan')}
        )
        assert ctx.get_indicator('nan_value', 'default') == 'default'

    def test_get_kline_value(self):
        ctx = ConditionContext(
            kline={'open': 100, 'high': 110, 'low': 90, 'close': 105},
            indicators={}
        )
        assert ctx.get_kline_value('close') == Decimal('105')
        assert ctx.get_kline_value('nonexistent') is None


class TestPriceTouchesLevel:
    """PriceTouchesLevel 测试"""

    def test_below_triggered(self):
        """价格下探触及P5"""
        condition = PriceTouchesLevel('p5', 'below')
        ctx = ConditionContext(
            kline={'low': 95, 'high': 110},
            indicators={'p5': 100}
        )
        result = condition.evaluate(ctx)
        assert result.triggered is True
        assert result.price == Decimal('100')

    def test_below_not_triggered(self):
        """价格未触及P5"""
        condition = PriceTouchesLevel('p5', 'below')
        ctx = ConditionContext(
            kline={'low': 105, 'high': 110},
            indicators={'p5': 100}
        )
        result = condition.evaluate(ctx)
        assert result.triggered is False

    def test_above_triggered(self):
        """价格上冲触及P95"""
        condition = PriceTouchesLevel('p95', 'above')
        ctx = ConditionContext(
            kline={'low': 90, 'high': 105},
            indicators={'p95': 100}
        )
        result = condition.evaluate(ctx)
        assert result.triggered is True

    def test_above_not_triggered(self):
        """价格未触及P95"""
        condition = PriceTouchesLevel('p95', 'above')
        ctx = ConditionContext(
            kline={'low': 90, 'high': 95},
            indicators={'p95': 100}
        )
        result = condition.evaluate(ctx)
        assert result.triggered is False

    def test_indicator_not_exists(self):
        """指标不存在时不触发"""
        condition = PriceTouchesLevel('p5', 'below')
        ctx = ConditionContext(
            kline={'low': 95, 'high': 110},
            indicators={}
        )
        result = condition.evaluate(ctx)
        assert result.triggered is False

    def test_invalid_direction(self):
        """无效方向应抛出异常"""
        with pytest.raises(ValueError):
            PriceTouchesLevel('p5', 'invalid')


class TestPriceInRange:
    """PriceInRange 测试"""

    def test_in_range(self):
        """指标值在K线范围内"""
        condition = PriceInRange('ema25')
        ctx = ConditionContext(
            kline={'low': 95, 'high': 105},
            indicators={'ema25': 100}
        )
        result = condition.evaluate(ctx)
        assert result.triggered is True
        assert result.price == Decimal('100')

    def test_not_in_range(self):
        """指标值不在K线范围内"""
        condition = PriceInRange('ema25')
        ctx = ConditionContext(
            kline={'low': 95, 'high': 99},
            indicators={'ema25': 100}
        )
        result = condition.evaluate(ctx)
        assert result.triggered is False

    def test_boundary_low(self):
        """边界情况：恰好等于low"""
        condition = PriceInRange('ema25')
        ctx = ConditionContext(
            kline={'low': 100, 'high': 110},
            indicators={'ema25': 100}
        )
        result = condition.evaluate(ctx)
        assert result.triggered is True

    def test_boundary_high(self):
        """边界情况：恰好等于high"""
        condition = PriceInRange('ema25')
        ctx = ConditionContext(
            kline={'low': 90, 'high': 100},
            indicators={'ema25': 100}
        )
        result = condition.evaluate(ctx)
        assert result.triggered is True


class TestBetaNegative:
    """BetaNegative 测试"""

    def test_negative_beta(self):
        """Beta为负时触发"""
        condition = BetaNegative()
        ctx = ConditionContext(
            kline={},
            indicators={'beta': -0.5}
        )
        result = condition.evaluate(ctx)
        assert result.triggered is True

    def test_positive_beta(self):
        """Beta为正时不触发"""
        condition = BetaNegative()
        ctx = ConditionContext(
            kline={},
            indicators={'beta': 0.5}
        )
        result = condition.evaluate(ctx)
        assert result.triggered is False

    def test_zero_beta(self):
        """Beta为零时不触发"""
        condition = BetaNegative()
        ctx = ConditionContext(
            kline={},
            indicators={'beta': 0}
        )
        result = condition.evaluate(ctx)
        assert result.triggered is False

    def test_beta_none(self):
        """Beta不存在时不触发"""
        condition = BetaNegative()
        ctx = ConditionContext(
            kline={},
            indicators={}
        )
        result = condition.evaluate(ctx)
        assert result.triggered is False


class TestFutureEmaPrediction:
    """FutureEmaPrediction 测试"""

    def test_above_close_triggered(self):
        """预测EMA高于收盘价时触发（做多信号）"""
        condition = FutureEmaPrediction(periods=6, above_close=True)
        ctx = ConditionContext(
            kline={'close': 100},
            indicators={'ema25': 95, 'beta': 2}  # 预测值: 95 + 2*6 = 107 > 100
        )
        result = condition.evaluate(ctx)
        assert result.triggered is True

    def test_above_close_not_triggered(self):
        """预测EMA低于收盘价时不触发"""
        condition = FutureEmaPrediction(periods=6, above_close=True)
        ctx = ConditionContext(
            kline={'close': 100},
            indicators={'ema25': 95, 'beta': -1}  # 预测值: 95 + (-1)*6 = 89 < 100
        )
        result = condition.evaluate(ctx)
        assert result.triggered is False

    def test_below_close_triggered(self):
        """预测EMA低于收盘价时触发（做空信号）"""
        condition = FutureEmaPrediction(periods=6, above_close=False)
        ctx = ConditionContext(
            kline={'close': 100},
            indicators={'ema25': 95, 'beta': -1}  # 预测值: 95 + (-1)*6 = 89 < 100
        )
        result = condition.evaluate(ctx)
        assert result.triggered is True


class TestIndicatorLessThan:
    """IndicatorLessThan 测试"""

    def test_less_than_triggered(self):
        """指标1小于指标2时触发"""
        condition = IndicatorLessThan('inertia_mid', 'p5')
        ctx = ConditionContext(
            kline={},
            indicators={'inertia_mid': 90, 'p5': 100}
        )
        result = condition.evaluate(ctx)
        assert result.triggered is True

    def test_less_than_not_triggered(self):
        """指标1大于指标2时不触发"""
        condition = IndicatorLessThan('inertia_mid', 'p5')
        ctx = ConditionContext(
            kline={},
            indicators={'inertia_mid': 110, 'p5': 100}
        )
        result = condition.evaluate(ctx)
        assert result.triggered is False

    def test_equal_strict(self):
        """严格模式：等于时不触发"""
        condition = IndicatorLessThan('inertia_mid', 'p5', strict=True)
        ctx = ConditionContext(
            kline={},
            indicators={'inertia_mid': 100, 'p5': 100}
        )
        result = condition.evaluate(ctx)
        assert result.triggered is False

    def test_equal_non_strict(self):
        """非严格模式：等于时触发"""
        condition = IndicatorLessThan('inertia_mid', 'p5', strict=False)
        ctx = ConditionContext(
            kline={},
            indicators={'inertia_mid': 100, 'p5': 100}
        )
        result = condition.evaluate(ctx)
        assert result.triggered is True

    def test_missing_indicator(self):
        """缺少指标时不触发"""
        condition = IndicatorLessThan('inertia_mid', 'p5')
        ctx = ConditionContext(
            kline={},
            indicators={'inertia_mid': 90}
        )
        result = condition.evaluate(ctx)
        assert result.triggered is False


class TestPriceBelowMidLine:
    """PriceBelowMidLine 测试"""

    def test_below_midline_triggered(self):
        """价格低于中值线时触发"""
        condition = PriceBelowMidLine('inertia_mid', 'p5')
        ctx = ConditionContext(
            kline={'low': 90, 'high': 100},
            indicators={'inertia_mid': 100, 'p5': 98}  # mid_line = 99
        )
        result = condition.evaluate(ctx)
        assert result.triggered is True
        assert result.price == Decimal('99')

    def test_above_midline_not_triggered(self):
        """价格高于中值线时不触发"""
        condition = PriceBelowMidLine('inertia_mid', 'p5')
        ctx = ConditionContext(
            kline={'low': 105, 'high': 110},
            indicators={'inertia_mid': 100, 'p5': 98}  # mid_line = 99
        )
        result = condition.evaluate(ctx)
        assert result.triggered is False

    def test_equal_strict(self):
        """严格模式：等于中值线时不触发"""
        condition = PriceBelowMidLine('inertia_mid', 'p5', strict=True)
        ctx = ConditionContext(
            kline={'low': 99, 'high': 110},
            indicators={'inertia_mid': 100, 'p5': 98}  # mid_line = 99
        )
        result = condition.evaluate(ctx)
        assert result.triggered is False

    def test_equal_non_strict(self):
        """非严格模式：等于中值线时触发"""
        condition = PriceBelowMidLine('inertia_mid', 'p5', strict=False)
        ctx = ConditionContext(
            kline={'low': 99, 'high': 110},
            indicators={'inertia_mid': 100, 'p5': 98}  # mid_line = 99
        )
        result = condition.evaluate(ctx)
        assert result.triggered is True

    def test_missing_indicator(self):
        """缺少指标时不触发"""
        condition = PriceBelowMidLine('inertia_mid', 'p5')
        ctx = ConditionContext(
            kline={'low': 90, 'high': 100},
            indicators={'inertia_mid': 100}
        )
        result = condition.evaluate(ctx)
        assert result.triggered is False


class TestCyclePhase:
    """CyclePhaseIs 和 CyclePhaseIn 测试"""

    def test_phase_is_match(self):
        """周期匹配"""
        condition = CyclePhaseIs('consolidation')
        ctx = ConditionContext(
            kline={},
            indicators={'cycle_phase': 'consolidation'}
        )
        result = condition.evaluate(ctx)
        assert result.triggered is True

    def test_phase_is_no_match(self):
        """周期不匹配"""
        condition = CyclePhaseIs('consolidation')
        ctx = ConditionContext(
            kline={},
            indicators={'cycle_phase': 'bull_strong'}
        )
        result = condition.evaluate(ctx)
        assert result.triggered is False

    def test_phase_in_match(self):
        """周期在列表中"""
        condition = CyclePhaseIn(['consolidation', 'bear_warning', 'bear_strong'])
        ctx = ConditionContext(
            kline={},
            indicators={'cycle_phase': 'bear_warning'}
        )
        result = condition.evaluate(ctx)
        assert result.triggered is True

    def test_phase_in_no_match(self):
        """周期不在列表中"""
        condition = CyclePhaseIn(['consolidation', 'bear_warning', 'bear_strong'])
        ctx = ConditionContext(
            kline={},
            indicators={'cycle_phase': 'bull_strong'}
        )
        result = condition.evaluate(ctx)
        assert result.triggered is False


class TestLogicConditions:
    """逻辑组合条件测试"""

    def test_and_all_true(self):
        """AND: 所有条件满足"""
        cond1 = PriceTouchesLevel('p5', 'below')
        cond2 = BetaNegative()
        and_cond = AndCondition(cond1, cond2)

        ctx = ConditionContext(
            kline={'low': 95, 'high': 110},
            indicators={'p5': 100, 'beta': -0.5}
        )
        result = and_cond.evaluate(ctx)
        assert result.triggered is True

    def test_and_one_false(self):
        """AND: 一个条件不满足"""
        cond1 = PriceTouchesLevel('p5', 'below')
        cond2 = BetaNegative()
        and_cond = AndCondition(cond1, cond2)

        ctx = ConditionContext(
            kline={'low': 95, 'high': 110},
            indicators={'p5': 100, 'beta': 0.5}  # beta正，不满足
        )
        result = and_cond.evaluate(ctx)
        assert result.triggered is False

    def test_or_one_true(self):
        """OR: 一个条件满足"""
        cond1 = PriceTouchesLevel('p5', 'below')
        cond2 = BetaNegative()
        or_cond = OrCondition(cond1, cond2)

        ctx = ConditionContext(
            kline={'low': 105, 'high': 110},  # 不触及p5
            indicators={'p5': 100, 'beta': -0.5}  # beta负
        )
        result = or_cond.evaluate(ctx)
        assert result.triggered is True

    def test_or_all_false(self):
        """OR: 所有条件不满足"""
        cond1 = PriceTouchesLevel('p5', 'below')
        cond2 = BetaNegative()
        or_cond = OrCondition(cond1, cond2)

        ctx = ConditionContext(
            kline={'low': 105, 'high': 110},  # 不触及p5
            indicators={'p5': 100, 'beta': 0.5}  # beta正
        )
        result = or_cond.evaluate(ctx)
        assert result.triggered is False

    def test_not_invert(self):
        """NOT: 取反"""
        cond = BetaNegative()
        not_cond = NotCondition(cond)

        ctx = ConditionContext(
            kline={},
            indicators={'beta': 0.5}  # beta正，原条件不满足
        )
        result = not_cond.evaluate(ctx)
        assert result.triggered is True

    def test_operator_and(self):
        """运算符 &"""
        cond1 = PriceTouchesLevel('p5', 'below')
        cond2 = BetaNegative()
        and_cond = cond1 & cond2

        assert isinstance(and_cond, AndCondition)

    def test_operator_or(self):
        """运算符 |"""
        cond1 = PriceTouchesLevel('p5', 'below')
        cond2 = BetaNegative()
        or_cond = cond1 | cond2

        assert isinstance(or_cond, OrCondition)

    def test_operator_not(self):
        """运算符 ~"""
        cond = BetaNegative()
        not_cond = ~cond

        assert isinstance(not_cond, NotCondition)

    def test_nested_combination(self):
        """嵌套组合"""
        # (P5触及 AND Beta负) OR (P95触及)
        cond1 = PriceTouchesLevel('p5', 'below')
        cond2 = BetaNegative()
        cond3 = PriceTouchesLevel('p95', 'above')

        combined = (cond1 & cond2) | cond3

        # 测试第一个分支满足
        ctx1 = ConditionContext(
            kline={'low': 95, 'high': 98},
            indicators={'p5': 100, 'p95': 120, 'beta': -0.5}
        )
        result1 = combined.evaluate(ctx1)
        assert result1.triggered is True

        # 测试第二个分支满足
        ctx2 = ConditionContext(
            kline={'low': 100, 'high': 125},
            indicators={'p5': 90, 'p95': 120, 'beta': 0.5}
        )
        result2 = combined.evaluate(ctx2)
        assert result2.triggered is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
