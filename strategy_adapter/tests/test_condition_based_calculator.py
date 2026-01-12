"""
基于条件的信号计算器集成测试
"""

import numpy as np
import pytest
from decimal import Decimal

from strategy_adapter.conditions import (
    PriceTouchesLevel,
    PriceInRange,
    BetaNegative,
    FutureEmaPrediction,
)
from strategy_adapter.definitions import StrategyDefinition, StrategyRegistry
from strategy_adapter.engine import ConditionBasedSignalCalculator, ConditionBasedExit


class TestConditionBasedSignalCalculator:
    """ConditionBasedSignalCalculator 集成测试"""

    @pytest.fixture
    def sample_klines(self):
        """生成测试K线数据"""
        return [
            {'open': 100, 'high': 105, 'low': 96, 'close': 102, 'open_time': 1000},  # low=96 > p5=95, 不触发
            {'open': 102, 'high': 108, 'low': 98, 'close': 106, 'open_time': 2000},  # low=98 > p5=95, 不触发
            {'open': 106, 'high': 110, 'low': 92, 'close': 94, 'open_time': 3000},   # low=92 < p5=95, 触发
            {'open': 94, 'high': 100, 'low': 90, 'close': 98, 'open_time': 4000},    # low=90 < p5=95, 触发
            {'open': 98, 'high': 103, 'low': 97, 'close': 101, 'open_time': 5000},   # low=97 > p5=95, 不触发
        ]

    @pytest.fixture
    def sample_indicators(self):
        """生成测试指标数据"""
        return {
            'p5': np.array([95, 95, 95, 95, 95]),
            'p95': np.array([115, 115, 115, 115, 115]),
            'ema25': np.array([100, 101, 102, 100, 99]),
            'beta': np.array([0.5, 0.3, -0.2, -0.5, 0.1]),
        }

    @pytest.fixture
    def test_registry(self):
        """创建测试用策略注册表"""
        # 清空现有注册
        StrategyRegistry.clear()

        # 注册测试策略
        test_strategy = StrategyDefinition(
            id='test_strategy',
            name='测试策略',
            direction='long',
            entry_condition=PriceTouchesLevel('p5', 'below'),
        )
        StrategyRegistry.register(test_strategy)

        yield StrategyRegistry

        # 清理
        StrategyRegistry.clear()

    def test_basic_signal_generation(self, sample_klines, sample_indicators, test_registry):
        """基本信号生成测试"""
        calculator = ConditionBasedSignalCalculator(registry=test_registry)
        result = calculator.calculate(
            klines=sample_klines,
            indicators=sample_indicators,
            enabled_strategies=['test_strategy']
        )

        # 第3和第4根K线应该触发信号（low=92<95 和 low=90<95）
        assert 'long_signals' in result
        assert 'short_signals' in result
        assert len(result['long_signals']) == 2
        assert len(result['short_signals']) == 0

        # 验证信号内容
        signal = result['long_signals'][0]
        assert signal['strategy_id'] == 'test_strategy'
        assert signal['direction'] == 'long'
        assert signal['index'] == 2

    def test_combined_condition_strategy(self, sample_klines, sample_indicators):
        """组合条件策略测试"""
        StrategyRegistry.clear()

        # 注册组合条件策略：价格触及P5 且 Beta为负
        combined_strategy = StrategyDefinition(
            id='combined_strategy',
            name='组合条件策略',
            direction='long',
            entry_condition=(
                PriceTouchesLevel('p5', 'below') &
                BetaNegative()
            ),
        )
        StrategyRegistry.register(combined_strategy)

        calculator = ConditionBasedSignalCalculator()
        result = calculator.calculate(
            klines=sample_klines,
            indicators=sample_indicators,
            enabled_strategies=['combined_strategy']
        )

        # 只有第3和第4根K线同时满足两个条件
        # K3: low=92<p5=95, beta=-0.2<0 ✓
        # K4: low=90<p5=95, beta=-0.5<0 ✓
        assert len(result['long_signals']) == 2

        StrategyRegistry.clear()

    def test_multiple_strategies(self, sample_klines, sample_indicators):
        """多策略同时评估测试"""
        StrategyRegistry.clear()

        # 策略1：只看P5
        strategy1 = StrategyDefinition(
            id='strategy_1',
            name='P5策略',
            direction='long',
            entry_condition=PriceTouchesLevel('p5', 'below'),
        )

        # 策略2：只看Beta
        strategy2 = StrategyDefinition(
            id='strategy_2',
            name='Beta策略',
            direction='long',
            entry_condition=BetaNegative(),
        )

        StrategyRegistry.register(strategy1)
        StrategyRegistry.register(strategy2)

        calculator = ConditionBasedSignalCalculator()
        result = calculator.calculate(
            klines=sample_klines,
            indicators=sample_indicators
        )

        # 策略1: K3, K4触发 = 2个信号
        # 策略2: K3(beta=-0.2), K4(beta=-0.5)触发 = 2个信号
        # 总计4个long_signals
        assert len(result['long_signals']) == 4

        StrategyRegistry.clear()

    def test_short_strategy(self, sample_klines, sample_indicators):
        """做空策略测试"""
        StrategyRegistry.clear()

        short_strategy = StrategyDefinition(
            id='short_strategy',
            name='做空策略',
            direction='short',
            entry_condition=PriceTouchesLevel('p95', 'above'),
        )
        StrategyRegistry.register(short_strategy)

        # 修改K线数据使其触及P95
        klines = [
            {'open': 100, 'high': 120, 'low': 95, 'close': 118, 'open_time': 1000},  # high=120 > p95=115
        ]

        calculator = ConditionBasedSignalCalculator()
        result = calculator.calculate(
            klines=klines,
            indicators={'p95': np.array([115])},
            enabled_strategies=['short_strategy']
        )

        assert len(result['short_signals']) == 1
        assert result['short_signals'][0]['direction'] == 'short'

        StrategyRegistry.clear()


class TestConditionBasedExit:
    """ConditionBasedExit 适配器测试"""

    def test_exit_triggered(self):
        """Exit触发测试"""
        condition = PriceInRange('ema25')
        exit_adapter = ConditionBasedExit(condition=condition, priority=30)

        # 模拟订单
        class MockOrder:
            pass

        order = MockOrder()
        kline = {'low': 98, 'high': 102, 'close': 100}
        indicators = {'ema25': 100}  # ema25在K线范围内

        signal = exit_adapter.check(order, kline, indicators, 1000)

        assert signal is not None
        assert signal.exit_type == 'price_in_range_ema25'
        assert signal.timestamp == 1000

    def test_exit_not_triggered(self):
        """Exit不触发测试"""
        condition = PriceInRange('ema25')
        exit_adapter = ConditionBasedExit(condition=condition, priority=30)

        class MockOrder:
            pass

        order = MockOrder()
        kline = {'low': 95, 'high': 99, 'close': 97}
        indicators = {'ema25': 100}  # ema25不在K线范围内

        signal = exit_adapter.check(order, kline, indicators, 1000)

        assert signal is None

    def test_priority(self):
        """优先级测试"""
        exit1 = ConditionBasedExit(PriceInRange('ema25'), priority=10)
        exit2 = ConditionBasedExit(PriceTouchesLevel('p95', 'above'), priority=30)

        assert exit1.get_priority() == 10
        assert exit2.get_priority() == 30


class TestBuiltinStrategies:
    """内置策略测试"""

    def test_builtin_strategies_registered(self):
        """测试内置策略是否已注册"""
        # 重新注册内置策略（因为前面的测试可能清空了注册表）
        from strategy_adapter.definitions.builtin import (
            strategy_1, strategy_2, strategy_7, register_builtin_strategies
        )
        register_builtin_strategies()

        # 验证可以从注册表获取
        s1 = StrategyRegistry.get('strategy_1')
        s2 = StrategyRegistry.get('strategy_2')
        s7 = StrategyRegistry.get('strategy_7')

        assert s1 is not None
        assert s1.name == 'EMA斜率未来预测做多'
        assert s1.direction == 'long'

        assert s2 is not None
        assert s2.name == '惯性下跌中值突破做多'

        assert s7 is not None
        assert s7.name == '动态周期自适应做多'

    def test_strategy_1_entry_condition(self):
        """策略1入场条件测试"""
        from strategy_adapter.definitions.builtin import strategy_1
        from strategy_adapter.conditions import ConditionContext

        # 满足条件的情况：触及P5 且 预测EMA > 收盘价
        ctx = ConditionContext(
            kline={'low': 90, 'high': 105, 'close': 100},
            indicators={
                'p5': 95,  # low=90 < p5=95 ✓
                'ema25': 98,
                'beta': 1.0  # 预测EMA = 98 + 1*6 = 104 > 100 ✓
            }
        )

        result = strategy_1.entry_condition.evaluate(ctx)
        assert result.triggered is True

    def test_strategy_2_entry_condition(self):
        """策略2入场条件测试"""
        from strategy_adapter.definitions.builtin import strategy_2
        from strategy_adapter.conditions import ConditionContext

        # 满足条件的情况：
        # 1. beta < 0 (下跌趋势)
        # 2. inertia_mid < p5 (惯性中值低于P5)
        # 3. low < (inertia_mid + p5) / 2 (价格跌破中值线)
        ctx = ConditionContext(
            kline={'low': 90, 'high': 105, 'close': 100},
            indicators={
                'p5': 100,          # P5值
                'inertia_mid': 92,  # inertia_mid=92 < p5=100 ✓
                'beta': -0.5        # beta < 0 ✓
                # mid_line = (92 + 100) / 2 = 96
                # low=90 < mid_line=96 ✓
            }
        )

        result = strategy_2.entry_condition.evaluate(ctx)
        assert result.triggered is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
