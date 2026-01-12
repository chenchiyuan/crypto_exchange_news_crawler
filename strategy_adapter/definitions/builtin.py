"""
内置策略定义

将现有策略1、2、7迁移到声明式定义。
"""

from .base import StrategyDefinition
from .registry import StrategyRegistry
from strategy_adapter.conditions import (
    PriceTouchesLevel,
    PriceInRange,
    BetaNegative,
    FutureEmaPrediction,
    IndicatorLessThan,
    PriceBelowMidLine,
)


# 策略1: EMA斜率未来预测做多
# 原条件: low < p5 且 future_ema > close
strategy_1 = StrategyDefinition(
    id='strategy_1',
    name='EMA斜率未来预测做多',
    version='2.0',
    direction='long',
    entry_condition=(
        PriceTouchesLevel('p5', 'below', strict=True) &
        FutureEmaPrediction(periods=6, above_close=True)
    ),
    exit_conditions=[
        (PriceInRange('ema25'), 30),
    ],
    metadata={
        'description': '价格跌破P5且预测EMA上穿收盘价时做多',
        'original_strategy': 'strategy_1',
    }
)


# 策略2: 惯性下跌中值突破做多
# 原条件: beta < 0 且 inertia_mid < p5 且 low < (inertia_mid + p5) / 2
strategy_2 = StrategyDefinition(
    id='strategy_2',
    name='惯性下跌中值突破做多',
    version='2.0',
    direction='long',
    entry_condition=(
        BetaNegative() &
        IndicatorLessThan('inertia_mid', 'p5') &
        PriceBelowMidLine('inertia_mid', 'p5')
    ),
    exit_conditions=[
        (PriceInRange('ema25'), 30),
    ],
    metadata={
        'description': 'Beta为负、惯性中值低于P5且价格跌破中值线时做多（惯性下跌突破）',
        'original_strategy': 'strategy_2',
    }
)


# 策略7: 动态周期自适应做多
# 注：策略7使用DynamicExitSelector，出场条件在adapter层处理
strategy_7 = StrategyDefinition(
    id='strategy_7',
    name='动态周期自适应做多',
    version='2.0',
    direction='long',
    entry_condition=PriceTouchesLevel('p5', 'below'),
    exit_conditions=[],  # 使用DynamicExitSelector
    metadata={
        'description': '价格触及P5时做多，使用动态出场策略',
        'original_strategy': 'strategy_7',
        'use_dynamic_exit': True,
    }
)


def register_builtin_strategies():
    """注册所有内置策略"""
    StrategyRegistry.register(strategy_1)
    StrategyRegistry.register(strategy_2)
    StrategyRegistry.register(strategy_7)


# 模块加载时自动注册
register_builtin_strategies()
