"""
BuySignalCalculator单元测试

测试买入信号计算器的所有功能，包括：
- 策略1: EMA斜率未来预测
- 策略2: 惯性下跌中值突破
- 边界条件
- 异常处理
- 数据结构契约

Related:
    - PRD: docs/iterations/011-buy-signal-markers/prd.md
    - Architecture: docs/iterations/011-buy-signal-markers/architecture.md
    - Task: TASK-011-007
"""

import unittest
from datetime import datetime, timezone

import numpy as np
from django.test import TestCase

from ddps_z.calculators.buy_signal_calculator import (
    BuySignalCalculator,
    DataInsufficientError,
    InvalidBetaError,
    InvalidKlineError,
)


class BuySignalCalculatorStrategy1Test(TestCase):
    """测试策略1: EMA斜率未来预测买入

    策略1触发条件:
        1. K线low < P5（价格跌破P5静态阈值）
        2. 未来6周期EMA预测价格 > 当前close（趋势向好）
        公式: 未来EMA = EMA[t] + (β × 6)
    """

    def setUp(self):
        """测试前准备：创建计算器实例和基础测试数据"""
        self.calculator = BuySignalCalculator()

    def _create_test_data(
        self,
        low: float,
        close: float,
        ema: float,
        p5: float,
        beta: float,
        inertia_mid: float = 100.0
    ) -> tuple:
        """辅助方法：创建单根K线的测试数据"""
        klines = [
            {
                'open_time': datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
                'high': 110.0,
                'low': low,
                'close': close,
            }
        ]
        ema_series = np.array([ema])
        p5_series = np.array([p5])
        beta_series = np.array([beta])
        inertia_mid_series = np.array([inertia_mid])
        return klines, ema_series, p5_series, beta_series, inertia_mid_series

    def test_strategy1_triggered_when_low_below_p5_and_future_ema_above_close(self):
        """策略1正常触发：low < P5 且 未来EMA > close

        场景：
        - low = 98, P5 = 100 → low < P5 ✓
        - EMA = 105, β = 1.0 → 未来EMA = 105 + 1.0×6 = 111
        - close = 100 → 未来EMA(111) > close(100) ✓
        - 预期: 触发
        """
        klines, ema_series, p5_series, beta_series, inertia_mid_series = (
            self._create_test_data(
                low=98.0,      # < P5(100) ✓
                close=100.0,
                ema=105.0,
                p5=100.0,
                beta=1.0,      # future_ema = 105 + 6 = 111 > close(100) ✓
            )
        )

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        self.assertEqual(len(signals), 1, "应触发1个买入信号")
        strategy1 = signals[0]['strategies'][0]
        self.assertTrue(
            strategy1['triggered'],
            "策略1应该触发: low < P5 且 future_ema > close"
        )
        self.assertEqual(strategy1['id'], 'strategy_1')
        self.assertIn('reason', strategy1, "触发时应有reason字段")
        self.assertIn('details', strategy1, "触发时应有details字段")

    def test_strategy1_not_triggered_when_low_above_p5(self):
        """策略1不触发：low >= P5

        场景：
        - low = 102, P5 = 100 → low >= P5 ✗
        - 预期: 不触发
        """
        klines, ema_series, p5_series, beta_series, inertia_mid_series = (
            self._create_test_data(
                low=102.0,     # >= P5(100) ✗
                close=100.0,
                ema=105.0,
                p5=100.0,
                beta=1.0,
            )
        )

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        self.assertEqual(len(signals), 0, "low >= P5时不应触发")

    def test_strategy1_not_triggered_when_future_ema_below_close(self):
        """策略1不触发：未来EMA <= close

        场景：
        - low = 98 < P5(100) ✓
        - EMA = 95, β = -1.0 → 未来EMA = 95 + (-1.0)×6 = 89
        - close = 100 → 未来EMA(89) <= close(100) ✗
        - 预期: 不触发
        """
        klines, ema_series, p5_series, beta_series, inertia_mid_series = (
            self._create_test_data(
                low=98.0,      # < P5 ✓
                close=100.0,
                ema=95.0,
                p5=100.0,
                beta=-1.0,     # future_ema = 95 - 6 = 89 <= close(100) ✗
            )
        )

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        self.assertEqual(len(signals), 0, "未来EMA <= close时不应触发")

    def test_strategy1_beta_calculation_accuracy(self):
        """策略1: β斜率计算精度验证

        验证未来EMA = EMA[t] + (β × 6) 的计算准确性
        """
        # 设置精确的测试值
        ema = 100.0
        beta = 0.5
        expected_future_ema = ema + (beta * 6)  # 100 + 3 = 103

        klines, ema_series, p5_series, beta_series, inertia_mid_series = (
            self._create_test_data(
                low=90.0,      # < P5(95) ✓
                close=95.0,    # < future_ema(103) ✓ → 触发
                ema=ema,
                p5=95.0,
                beta=beta,
            )
        )

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        self.assertEqual(len(signals), 1)
        details = signals[0]['strategies'][0]['details']

        # 验证计算精度
        self.assertAlmostEqual(
            details['future_ema'],
            expected_future_ema,
            places=6,
            msg=f"未来EMA计算误差: expected={expected_future_ema}, actual={details['future_ema']}"
        )
        self.assertEqual(details['beta'], beta)

    def test_strategy1_future_ema_calculation_accuracy(self):
        """策略1: 未来EMA预测计算精度验证

        使用不同的β值验证公式: 未来EMA = EMA[t] + β × 6
        """
        test_cases = [
            {'ema': 100.0, 'beta': 2.0, 'expected_future_ema': 112.0},
            {'ema': 100.0, 'beta': 0.0, 'expected_future_ema': 100.0},
            {'ema': 100.0, 'beta': -0.5, 'expected_future_ema': 97.0},
            {'ema': 50000.0, 'beta': 100.0, 'expected_future_ema': 50600.0},
        ]

        for case in test_cases:
            with self.subTest(case=case):
                klines, ema_series, p5_series, beta_series, inertia_mid_series = (
                    self._create_test_data(
                        low=90.0,
                        close=95.0,
                        ema=case['ema'],
                        p5=100.0,
                        beta=case['beta'],
                    )
                )

                signals = self.calculator.calculate(
                    klines, ema_series, p5_series, beta_series, inertia_mid_series
                )

                # 策略1触发时才有details
                if signals and signals[0]['strategies'][0]['triggered']:
                    actual = signals[0]['strategies'][0]['details']['future_ema']
                    self.assertAlmostEqual(
                        actual,
                        case['expected_future_ema'],
                        places=6,
                        msg=f"EMA={case['ema']}, β={case['beta']}: "
                            f"expected={case['expected_future_ema']}, actual={actual}"
                    )


class BuySignalCalculatorStrategy2Test(TestCase):
    """测试策略2: 惯性下跌中值突破买入

    策略2触发条件:
        1. β < 0（下跌趋势）
        2. 惯性mid < P5（惯性预测低于P5阈值）
        3. K线low < (惯性mid + P5) / 2（价格跌破中值线）
    """

    def setUp(self):
        """测试前准备：创建计算器实例"""
        self.calculator = BuySignalCalculator()

    def _create_test_data(
        self,
        low: float,
        close: float,
        p5: float,
        beta: float,
        inertia_mid: float,
        ema: float = 100.0
    ) -> tuple:
        """辅助方法：创建单根K线的测试数据"""
        klines = [
            {
                'open_time': datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
                'high': 110.0,
                'low': low,
                'close': close,
            }
        ]
        ema_series = np.array([ema])
        p5_series = np.array([p5])
        beta_series = np.array([beta])
        inertia_mid_series = np.array([inertia_mid])
        return klines, ema_series, p5_series, beta_series, inertia_mid_series

    def test_strategy2_triggered_when_downtrend_and_mid_below_p5_and_low_below_midline(self):
        """策略2正常触发：β < 0 且 惯性mid < P5 且 low < 中值线

        场景：
        - β = -1.0 → 下跌趋势 ✓
        - inertia_mid = 90, P5 = 100 → inertia_mid < P5 ✓
        - 中值线 = (90 + 100) / 2 = 95
        - low = 92 → low < 中值线(95) ✓
        - 预期: 触发
        """
        klines, ema_series, p5_series, beta_series, inertia_mid_series = (
            self._create_test_data(
                low=92.0,          # < 中值线(95) ✓
                close=95.0,
                p5=100.0,
                beta=-1.0,         # < 0 下跌趋势 ✓
                inertia_mid=90.0,  # < P5(100) ✓
            )
        )

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        self.assertEqual(len(signals), 1, "应触发1个买入信号")
        strategy2 = signals[0]['strategies'][1]
        self.assertTrue(
            strategy2['triggered'],
            "策略2应该触发: β<0 且 inertia_mid<P5 且 low<中值线"
        )
        self.assertEqual(strategy2['id'], 'strategy_2')
        self.assertIn('reason', strategy2)
        self.assertIn('details', strategy2)

    def test_strategy2_not_triggered_when_uptrend(self):
        """策略2不触发：β >= 0（非下跌趋势）

        场景：
        - β = 0.5 → 上涨趋势 ✗
        - 预期: 不触发
        """
        klines, ema_series, p5_series, beta_series, inertia_mid_series = (
            self._create_test_data(
                low=92.0,
                close=95.0,
                p5=100.0,
                beta=0.5,          # >= 0 非下跌趋势 ✗
                inertia_mid=90.0,
            )
        )

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        # 策略2不应触发（但策略1可能触发）
        if signals:
            strategy2 = signals[0]['strategies'][1]
            self.assertFalse(
                strategy2['triggered'],
                "β >= 0时策略2不应触发"
            )

    def test_strategy2_not_triggered_when_inertia_mid_above_p5(self):
        """策略2不触发：惯性mid >= P5

        场景：
        - β = -1.0 ✓
        - inertia_mid = 105, P5 = 100 → inertia_mid >= P5 ✗
        - 预期: 不触发
        """
        klines, ema_series, p5_series, beta_series, inertia_mid_series = (
            self._create_test_data(
                low=92.0,
                close=95.0,
                p5=100.0,
                beta=-1.0,          # < 0 ✓
                inertia_mid=105.0,  # >= P5 ✗
            )
        )

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        # 策略2不应触发
        if signals:
            strategy2 = signals[0]['strategies'][1]
            self.assertFalse(
                strategy2['triggered'],
                "inertia_mid >= P5时策略2不应触发"
            )

    def test_strategy2_not_triggered_when_low_above_midline(self):
        """策略2不触发：low >= 中值线

        场景：
        - β = -1.0 ✓
        - inertia_mid = 90, P5 = 100 → inertia_mid < P5 ✓
        - 中值线 = (90 + 100) / 2 = 95
        - low = 96 → low >= 中值线(95) ✗
        - 预期: 不触发
        """
        klines, ema_series, p5_series, beta_series, inertia_mid_series = (
            self._create_test_data(
                low=96.0,          # >= 中值线(95) ✗
                close=98.0,
                p5=100.0,
                beta=-1.0,
                inertia_mid=90.0,
            )
        )

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        # 策略2不应触发
        if signals:
            strategy2 = signals[0]['strategies'][1]
            self.assertFalse(
                strategy2['triggered'],
                "low >= 中值线时策略2不应触发"
            )

    def test_strategy2_midline_calculation_accuracy(self):
        """策略2: 中值线计算精度验证

        验证中值线 = (惯性mid + P5) / 2 的计算准确性
        """
        inertia_mid = 90.0
        p5 = 100.0
        expected_midline = (inertia_mid + p5) / 2  # 95.0

        klines, ema_series, p5_series, beta_series, inertia_mid_series = (
            self._create_test_data(
                low=92.0,      # < 中值线(95) ✓
                close=95.0,
                p5=p5,
                beta=-1.0,     # 下跌趋势 ✓
                inertia_mid=inertia_mid,
            )
        )

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        self.assertEqual(len(signals), 1)
        details = signals[0]['strategies'][1]['details']

        self.assertAlmostEqual(
            details['mid_line'],
            expected_midline,
            places=6,
            msg=f"中值线计算误差: expected={expected_midline}, actual={details['mid_line']}"
        )


class BuySignalCalculatorMultiStrategyTest(TestCase):
    """测试多策略并存场景"""

    def setUp(self):
        """测试前准备"""
        self.calculator = BuySignalCalculator()

    def test_both_strategies_triggered_simultaneously(self):
        """两个策略同时触发

        场景：
        - 策略1: low < P5 ✓, future_ema > close ✓
        - 策略2: β < 0 ✓, inertia_mid < P5 ✓, low < 中值线 ✓
        """
        # 构造同时满足两个策略的数据
        klines = [
            {
                'open_time': datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
                'high': 110.0,
                'low': 88.0,       # < P5(100) ✓ 且 < 中值线(92.5) ✓
                'close': 90.0,
            }
        ]
        ema_series = np.array([95.0])
        p5_series = np.array([100.0])
        beta_series = np.array([-0.5])  # 下跌趋势, future_ema=95+(-0.5)*6=92 > close(90) ✓
        inertia_mid_series = np.array([85.0])  # < P5 ✓, 中值线=(85+100)/2=92.5

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        self.assertEqual(len(signals), 1)
        strategy1 = signals[0]['strategies'][0]
        strategy2 = signals[0]['strategies'][1]

        self.assertTrue(strategy1['triggered'], "策略1应该触发")
        self.assertTrue(strategy2['triggered'], "策略2应该触发")

    def test_buy_price_consistent_when_both_triggered(self):
        """多策略触发时buy_price一致

        验证buy_price始终为K线的close价格
        """
        expected_close = 90.0
        klines = [
            {
                'open_time': datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
                'high': 110.0,
                'low': 88.0,
                'close': expected_close,
            }
        ]
        ema_series = np.array([95.0])
        p5_series = np.array([100.0])
        beta_series = np.array([-0.5])
        inertia_mid_series = np.array([85.0])

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        self.assertEqual(len(signals), 1)
        self.assertEqual(
            signals[0]['buy_price'],
            expected_close,
            "buy_price应等于K线close价格"
        )


class BuySignalCalculatorBoundaryTest(TestCase):
    """测试边界条件"""

    def setUp(self):
        """测试前准备"""
        self.calculator = BuySignalCalculator()

    def _create_test_data(self, low, close, ema, p5, beta, inertia_mid):
        """辅助方法"""
        klines = [
            {
                'open_time': datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
                'high': 110.0,
                'low': low,
                'close': close,
            }
        ]
        return (
            klines,
            np.array([ema]),
            np.array([p5]),
            np.array([beta]),
            np.array([inertia_mid]),
        )

    def test_beta_equals_zero(self):
        """边界条件：β = 0

        - 策略1: future_ema = EMA + 0×6 = EMA，需检查是否 > close
        - 策略2: β = 0 不满足 β < 0 条件，不触发
        """
        klines, ema_series, p5_series, beta_series, inertia_mid_series = (
            self._create_test_data(
                low=98.0,
                close=100.0,
                ema=105.0,     # future_ema = 105 + 0 = 105 > close(100) ✓
                p5=100.0,      # low(98) < p5 ✓
                beta=0.0,      # β = 0
                inertia_mid=90.0,
            )
        )

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        # 策略1可能触发（如果其他条件满足）
        self.assertEqual(len(signals), 1)
        strategy1 = signals[0]['strategies'][0]
        strategy2 = signals[0]['strategies'][1]

        self.assertTrue(strategy1['triggered'], "β=0时策略1应基于其他条件判断")
        self.assertFalse(strategy2['triggered'], "β=0时策略2不应触发")

    def test_low_equals_p5(self):
        """边界条件：low = P5（不触发）

        策略1要求 low < P5（严格小于）
        """
        klines, ema_series, p5_series, beta_series, inertia_mid_series = (
            self._create_test_data(
                low=100.0,     # = P5(100)，不满足 < 条件
                close=100.0,
                ema=105.0,
                p5=100.0,
                beta=1.0,
                inertia_mid=90.0,
            )
        )

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        # 策略1不应触发（low = P5，不是严格小于）
        if signals:
            strategy1 = signals[0]['strategies'][0]
            self.assertFalse(
                strategy1['triggered'],
                "low = P5时策略1不应触发（需要严格小于）"
            )

    def test_inertia_mid_equals_p5(self):
        """边界条件：惯性mid = P5（策略2不触发）

        策略2要求 inertia_mid < P5（严格小于）
        """
        klines, ema_series, p5_series, beta_series, inertia_mid_series = (
            self._create_test_data(
                low=92.0,
                close=95.0,
                ema=105.0,
                p5=100.0,
                beta=-1.0,
                inertia_mid=100.0,  # = P5
            )
        )

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        # 策略2不应触发
        if signals:
            strategy2 = signals[0]['strategies'][1]
            self.assertFalse(
                strategy2['triggered'],
                "inertia_mid = P5时策略2不应触发（需要严格小于）"
            )

    def test_future_ema_equals_close(self):
        """边界条件：未来EMA = close（策略1不触发）

        策略1要求 future_ema > close（严格大于）
        """
        # 设置 future_ema = close
        # EMA + β×6 = close → 需要: 100 + β×6 = 100 → β = 0
        klines, ema_series, p5_series, beta_series, inertia_mid_series = (
            self._create_test_data(
                low=98.0,      # < P5 ✓
                close=100.0,
                ema=100.0,     # future_ema = 100 + 0×6 = 100 = close
                p5=100.0,
                beta=0.0,
                inertia_mid=90.0,
            )
        )

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        # 策略1不应触发（future_ema = close，不是严格大于）
        if signals:
            strategy1 = signals[0]['strategies'][0]
            self.assertFalse(
                strategy1['triggered'],
                "future_ema = close时策略1不应触发（需要严格大于）"
            )

    def test_low_equals_midline(self):
        """边界条件：low = 中值线（策略2不触发）

        策略2要求 low < 中值线（严格小于）
        """
        # 中值线 = (inertia_mid + P5) / 2 = (90 + 100) / 2 = 95
        klines, ema_series, p5_series, beta_series, inertia_mid_series = (
            self._create_test_data(
                low=95.0,      # = 中值线
                close=98.0,
                ema=105.0,
                p5=100.0,
                beta=-1.0,
                inertia_mid=90.0,
            )
        )

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        # 策略2不应触发
        if signals:
            strategy2 = signals[0]['strategies'][1]
            self.assertFalse(
                strategy2['triggered'],
                "low = 中值线时策略2不应触发（需要严格小于）"
            )


class BuySignalCalculatorExceptionTest(TestCase):
    """测试异常处理"""

    def setUp(self):
        """测试前准备"""
        self.calculator = BuySignalCalculator()

    def test_raises_error_when_data_insufficient_empty_klines(self):
        """数据不足时抛出DataInsufficientError: K线为空"""
        with self.assertRaises(DataInsufficientError) as context:
            self.calculator.calculate(
                klines=[],  # 空K线
                ema_series=np.array([]),
                p5_series=np.array([]),
                beta_series=np.array([]),
                inertia_mid_series=np.array([]),
            )

        self.assertIn("K线数据为空", str(context.exception))

    def test_raises_error_when_series_length_mismatch_ema(self):
        """输入序列长度不一致时抛出错误: EMA"""
        klines = [
            {
                'open_time': datetime(2025, 1, 1, tzinfo=timezone.utc),
                'high': 110.0,
                'low': 95.0,
                'close': 100.0,
            }
        ]

        with self.assertRaises(DataInsufficientError) as context:
            self.calculator.calculate(
                klines=klines,
                ema_series=np.array([100.0, 101.0]),  # 长度=2，不一致
                p5_series=np.array([100.0]),
                beta_series=np.array([1.0]),
                inertia_mid_series=np.array([90.0]),
            )

        self.assertIn("EMA序列长度", str(context.exception))

    def test_raises_error_when_series_length_mismatch_p5(self):
        """输入序列长度不一致时抛出错误: P5"""
        klines = [
            {
                'open_time': datetime(2025, 1, 1, tzinfo=timezone.utc),
                'high': 110.0,
                'low': 95.0,
                'close': 100.0,
            }
        ]

        with self.assertRaises(DataInsufficientError) as context:
            self.calculator.calculate(
                klines=klines,
                ema_series=np.array([100.0]),
                p5_series=np.array([100.0, 101.0]),  # 长度=2，不一致
                beta_series=np.array([1.0]),
                inertia_mid_series=np.array([90.0]),
            )

        self.assertIn("P5序列长度", str(context.exception))

    def test_raises_error_when_series_length_mismatch_beta(self):
        """输入序列长度不一致时抛出错误: β"""
        klines = [
            {
                'open_time': datetime(2025, 1, 1, tzinfo=timezone.utc),
                'high': 110.0,
                'low': 95.0,
                'close': 100.0,
            }
        ]

        with self.assertRaises(DataInsufficientError) as context:
            self.calculator.calculate(
                klines=klines,
                ema_series=np.array([100.0]),
                p5_series=np.array([100.0]),
                beta_series=np.array([1.0, 2.0]),  # 长度=2，不一致
                inertia_mid_series=np.array([90.0]),
            )

        self.assertIn("β序列长度", str(context.exception))

    def test_raises_error_when_series_length_mismatch_inertia_mid(self):
        """输入序列长度不一致时抛出错误: 惯性mid"""
        klines = [
            {
                'open_time': datetime(2025, 1, 1, tzinfo=timezone.utc),
                'high': 110.0,
                'low': 95.0,
                'close': 100.0,
            }
        ]

        with self.assertRaises(DataInsufficientError) as context:
            self.calculator.calculate(
                klines=klines,
                ema_series=np.array([100.0]),
                p5_series=np.array([100.0]),
                beta_series=np.array([1.0]),
                inertia_mid_series=np.array([90.0, 91.0]),  # 长度=2，不一致
            )

        self.assertIn("惯性mid序列长度", str(context.exception))

    def test_raises_error_when_beta_contains_inf(self):
        """β序列包含Inf时抛出InvalidBetaError"""
        klines = [
            {
                'open_time': datetime(2025, 1, 1, tzinfo=timezone.utc),
                'high': 110.0,
                'low': 95.0,
                'close': 100.0,
            }
        ]

        with self.assertRaises(InvalidBetaError) as context:
            self.calculator.calculate(
                klines=klines,
                ema_series=np.array([100.0]),
                p5_series=np.array([100.0]),
                beta_series=np.array([np.inf]),  # Inf值
                inertia_mid_series=np.array([90.0]),
            )

        self.assertIn("Inf", str(context.exception))

    def test_raises_error_when_beta_contains_negative_inf(self):
        """β序列包含-Inf时抛出InvalidBetaError"""
        klines = [
            {
                'open_time': datetime(2025, 1, 1, tzinfo=timezone.utc),
                'high': 110.0,
                'low': 95.0,
                'close': 100.0,
            }
        ]

        with self.assertRaises(InvalidBetaError) as context:
            self.calculator.calculate(
                klines=klines,
                ema_series=np.array([100.0]),
                p5_series=np.array([100.0]),
                beta_series=np.array([-np.inf]),  # -Inf值
                inertia_mid_series=np.array([90.0]),
            )

        self.assertIn("Inf", str(context.exception))

    def test_handles_nan_values_gracefully(self):
        """β序列包含NaN时不触发（优雅处理，不抛异常）

        注意：当前实现中NaN会被策略计算跳过，不会触发
        """
        klines = [
            {
                'open_time': datetime(2025, 1, 1, tzinfo=timezone.utc),
                'high': 110.0,
                'low': 95.0,
                'close': 100.0,
            }
        ]

        # NaN不会触发Inf检查，但会导致策略不触发
        signals = self.calculator.calculate(
            klines=klines,
            ema_series=np.array([np.nan]),  # NaN
            p5_series=np.array([100.0]),
            beta_series=np.array([1.0]),
            inertia_mid_series=np.array([90.0]),
        )

        # 不应有信号（NaN导致条件判断跳过）
        self.assertEqual(len(signals), 0, "NaN值应导致策略不触发")

    def test_raises_error_when_kline_missing_fields(self):
        """K线数据缺少必要字段时抛出InvalidKlineError"""
        # 缺少 'low' 字段
        klines = [
            {
                'open_time': datetime(2025, 1, 1, tzinfo=timezone.utc),
                'high': 110.0,
                # 'low': 95.0,  # 缺失
                'close': 100.0,
            }
        ]

        with self.assertRaises(InvalidKlineError) as context:
            self.calculator.calculate(
                klines=klines,
                ema_series=np.array([100.0]),
                p5_series=np.array([100.0]),
                beta_series=np.array([1.0]),
                inertia_mid_series=np.array([90.0]),
            )

        self.assertIn("low", str(context.exception))

    def test_raises_error_when_kline_missing_open_time(self):
        """K线数据缺少open_time字段时抛出InvalidKlineError"""
        klines = [
            {
                # 'open_time': ...,  # 缺失
                'high': 110.0,
                'low': 95.0,
                'close': 100.0,
            }
        ]

        with self.assertRaises(InvalidKlineError) as context:
            self.calculator.calculate(
                klines=klines,
                ema_series=np.array([100.0]),
                p5_series=np.array([100.0]),
                beta_series=np.array([1.0]),
                inertia_mid_series=np.array([90.0]),
            )

        self.assertIn("open_time", str(context.exception))


class BuySignalCalculatorOutputStructureTest(TestCase):
    """测试输出数据结构符合接口契约"""

    def setUp(self):
        """测试前准备"""
        self.calculator = BuySignalCalculator()

    def test_output_structure_matches_contract(self):
        """输出数据结构符合接口契约

        接口契约:
        - timestamp: int (毫秒时间戳)
        - kline_index: int (K线索引)
        - strategies: List[Dict] (策略触发信息)
        - buy_price: float (买入价格)
        """
        klines = [
            {
                'open_time': datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
                'high': 110.0,
                'low': 88.0,
                'close': 90.0,
            }
        ]
        ema_series = np.array([95.0])
        p5_series = np.array([100.0])
        beta_series = np.array([-0.5])
        inertia_mid_series = np.array([85.0])

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        self.assertEqual(len(signals), 1)
        signal = signals[0]

        # 验证必要字段存在
        self.assertIn('timestamp', signal, "缺少timestamp字段")
        self.assertIn('kline_index', signal, "缺少kline_index字段")
        self.assertIn('strategies', signal, "缺少strategies字段")
        self.assertIn('buy_price', signal, "缺少buy_price字段")

        # 验证字段类型
        self.assertIsInstance(signal['timestamp'], int, "timestamp应为int")
        self.assertIsInstance(signal['kline_index'], int, "kline_index应为int")
        self.assertIsInstance(signal['strategies'], list, "strategies应为list")
        self.assertIsInstance(signal['buy_price'], float, "buy_price应为float")

        # 验证timestamp是毫秒级
        expected_timestamp = int(
            datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        self.assertEqual(
            signal['timestamp'],
            expected_timestamp,
            "timestamp应为毫秒时间戳"
        )

    def test_strategy_id_naming_convention(self):
        """策略ID命名规范（strategy_1, strategy_2）"""
        klines = [
            {
                'open_time': datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
                'high': 110.0,
                'low': 88.0,
                'close': 90.0,
            }
        ]
        ema_series = np.array([95.0])
        p5_series = np.array([100.0])
        beta_series = np.array([-0.5])
        inertia_mid_series = np.array([85.0])

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        self.assertEqual(len(signals), 1)
        strategies = signals[0]['strategies']

        self.assertEqual(len(strategies), 2, "应有2个策略结果")
        self.assertEqual(strategies[0]['id'], 'strategy_1')
        self.assertEqual(strategies[1]['id'], 'strategy_2')

    def test_strategy_structure_when_triggered(self):
        """策略触发时的数据结构"""
        klines = [
            {
                'open_time': datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
                'high': 110.0,
                'low': 88.0,
                'close': 90.0,
            }
        ]
        ema_series = np.array([95.0])
        p5_series = np.array([100.0])
        beta_series = np.array([-0.5])
        inertia_mid_series = np.array([85.0])

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        for strategy in signals[0]['strategies']:
            if strategy['triggered']:
                self.assertIn('id', strategy)
                self.assertIn('name', strategy)
                self.assertIn('triggered', strategy)
                self.assertIn('reason', strategy, "触发时应有reason")
                self.assertIn('details', strategy, "触发时应有details")

    def test_strategy_structure_when_not_triggered(self):
        """策略未触发时的数据结构"""
        klines = [
            {
                'open_time': datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
                'high': 110.0,
                'low': 105.0,  # > P5，策略1不触发
                'close': 108.0,
            }
        ]
        ema_series = np.array([95.0])
        p5_series = np.array([100.0])
        beta_series = np.array([0.5])  # >= 0，策略2不触发
        inertia_mid_series = np.array([85.0])

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        # 无触发信号
        self.assertEqual(len(signals), 0)

    def test_timestamp_from_datetime(self):
        """timestamp从datetime对象正确转换"""
        test_time = datetime(2025, 6, 15, 12, 30, 45, tzinfo=timezone.utc)
        expected_ms = int(test_time.timestamp() * 1000)

        klines = [
            {
                'open_time': test_time,
                'high': 110.0,
                'low': 88.0,
                'close': 90.0,
            }
        ]
        ema_series = np.array([95.0])
        p5_series = np.array([100.0])
        beta_series = np.array([-0.5])
        inertia_mid_series = np.array([85.0])

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        self.assertEqual(signals[0]['timestamp'], expected_ms)

    def test_timestamp_from_milliseconds(self):
        """timestamp从毫秒时间戳直接使用"""
        expected_ms = 1750000000000  # 毫秒时间戳

        klines = [
            {
                'open_time': expected_ms,
                'high': 110.0,
                'low': 88.0,
                'close': 90.0,
            }
        ]
        ema_series = np.array([95.0])
        p5_series = np.array([100.0])
        beta_series = np.array([-0.5])
        inertia_mid_series = np.array([85.0])

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        self.assertEqual(signals[0]['timestamp'], expected_ms)


class BuySignalCalculatorMultiKlineTest(TestCase):
    """测试多根K线场景"""

    def setUp(self):
        """测试前准备"""
        self.calculator = BuySignalCalculator()

    def test_multiple_klines_multiple_signals(self):
        """多根K线产生多个买入信号"""
        klines = [
            {
                'open_time': datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
                'high': 110.0,
                'low': 105.0,  # > P5，不触发
                'close': 108.0,
            },
            {
                'open_time': datetime(2025, 1, 1, 4, 0, tzinfo=timezone.utc),
                'high': 110.0,
                'low': 88.0,   # < P5，触发
                'close': 90.0,
            },
            {
                'open_time': datetime(2025, 1, 1, 8, 0, tzinfo=timezone.utc),
                'high': 110.0,
                'low': 102.0,  # > P5，不触发
                'close': 105.0,
            },
            {
                'open_time': datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
                'high': 110.0,
                'low': 85.0,   # < P5，触发
                'close': 88.0,
            },
        ]

        ema_series = np.array([95.0, 95.0, 95.0, 95.0])
        p5_series = np.array([100.0, 100.0, 100.0, 100.0])
        beta_series = np.array([-0.5, -0.5, -0.5, -0.5])
        inertia_mid_series = np.array([85.0, 85.0, 85.0, 85.0])

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        self.assertEqual(len(signals), 2, "应有2个买入信号")

        # 验证kline_index正确
        self.assertEqual(signals[0]['kline_index'], 1)
        self.assertEqual(signals[1]['kline_index'], 3)

    def test_no_signals_when_no_triggers(self):
        """无触发条件时返回空列表"""
        klines = [
            {
                'open_time': datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
                'high': 110.0,
                'low': 105.0,  # > P5
                'close': 108.0,
            },
        ]

        ema_series = np.array([95.0])
        p5_series = np.array([100.0])
        beta_series = np.array([0.5])  # >= 0，策略2不触发
        inertia_mid_series = np.array([105.0])  # >= P5

        signals = self.calculator.calculate(
            klines, ema_series, p5_series, beta_series, inertia_mid_series
        )

        self.assertEqual(len(signals), 0, "无触发时应返回空列表")
        self.assertIsInstance(signals, list)


if __name__ == "__main__":
    unittest.main()
