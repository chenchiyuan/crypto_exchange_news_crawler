"""
DDPSCalculator 单元测试

测试DDPSCalculator的核心计算功能。

Related:
    - TASK: TASK-024-008
"""

from django.test import TestCase
import random

from ddps_z.calculators import DDPSCalculator, DDPSResult
from ddps_z.models import StandardKLine, Interval


class DDPSCalculatorTests(TestCase):
    """DDPSCalculator 单元测试"""

    def setUp(self):
        """设置测试数据"""
        self.calculator = DDPSCalculator()

    def _generate_mock_klines(self, count: int, base_price: float = 100.0) -> list:
        """
        生成模拟K线数据

        Args:
            count: K线数量
            base_price: 基准价格

        Returns:
            StandardKLine列表
        """
        klines = []
        price = base_price
        timestamp = 1704067200000  # 2024-01-01 00:00:00 UTC

        for i in range(count):
            # 随机波动
            change = random.uniform(-0.02, 0.02)
            price = price * (1 + change)

            high = price * (1 + random.uniform(0, 0.01))
            low = price * (1 - random.uniform(0, 0.01))
            open_price = price * (1 + random.uniform(-0.005, 0.005))
            volume = random.uniform(1000, 10000)

            klines.append(StandardKLine(
                timestamp=timestamp,
                open=open_price,
                high=high,
                low=low,
                close=price,
                volume=volume
            ))

            timestamp += 4 * 3600 * 1000  # 4小时间隔

        return klines

    def test_calculate_with_sufficient_data(self):
        """测试：数据充足时正常计算"""
        klines = self._generate_mock_klines(200)

        result = self.calculator.calculate(klines, interval_hours=4.0)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, DDPSResult)
        self.assertIsNotNone(result.current_price)
        self.assertIsNotNone(result.ema25)
        self.assertIsNotNone(result.p5)
        self.assertIsNotNone(result.p95)
        self.assertIsNotNone(result.cycle_phase)
        self.assertIn(result.cycle_phase, [
            'bull_warning', 'bull_strong',
            'bear_warning', 'bear_strong',
            'consolidation'
        ])

    def test_calculate_with_insufficient_data(self):
        """测试：数据不足时返回None"""
        klines = self._generate_mock_klines(100)  # 少于180根

        result = self.calculator.calculate(klines, interval_hours=4.0)

        self.assertIsNone(result)

    def test_calculate_with_4h_interval(self):
        """测试：4小时周期计算"""
        klines = self._generate_mock_klines(200)

        result = self.calculator.calculate(klines, interval_hours=4.0)

        self.assertIsNotNone(result)
        # 检查周期持续时间计算是否正确
        expected_hours = result.cycle_duration_bars * 4.0
        self.assertEqual(result.cycle_duration_hours, expected_hours)

    def test_calculate_with_1h_interval(self):
        """测试：1小时周期计算"""
        klines = self._generate_mock_klines(200)

        result = self.calculator.calculate(klines, interval_hours=1.0)

        self.assertIsNotNone(result)
        # 检查周期持续时间计算是否正确
        expected_hours = result.cycle_duration_bars * 1.0
        self.assertEqual(result.cycle_duration_hours, expected_hours)

    def test_calculate_with_1d_interval(self):
        """测试：日线周期计算"""
        klines = self._generate_mock_klines(200)

        result = self.calculator.calculate(klines, interval_hours=24.0)

        self.assertIsNotNone(result)
        # 检查周期持续时间计算是否正确
        expected_hours = result.cycle_duration_bars * 24.0
        self.assertEqual(result.cycle_duration_hours, expected_hours)

    def test_calculate_with_interval_method(self):
        """测试：使用interval字符串的便捷方法"""
        klines = self._generate_mock_klines(200)

        result = self.calculator.calculate_with_interval(klines, interval='4h')

        self.assertIsNotNone(result)
        self.assertIsInstance(result, DDPSResult)

    def test_probability_range(self):
        """测试：概率值在0-100范围内"""
        klines = self._generate_mock_klines(200)

        result = self.calculator.calculate(klines, interval_hours=4.0)

        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.probability, 0)
        self.assertLessEqual(result.probability, 100)

    def test_p5_less_than_p95(self):
        """测试：P5应小于P95"""
        klines = self._generate_mock_klines(200)

        result = self.calculator.calculate(klines, interval_hours=4.0)

        self.assertIsNotNone(result)
        self.assertLess(result.p5, result.p95)

    def test_empty_klines(self):
        """测试：空K线列表"""
        result = self.calculator.calculate([], interval_hours=4.0)

        self.assertIsNone(result)

    def test_custom_calculator_params(self):
        """测试：自定义计算器参数"""
        custom_calc = DDPSCalculator(
            ema_period=20,
            ewma_window=40,
            adx_period=10,
            inertia_base_period=3
        )

        klines = self._generate_mock_klines(200)
        result = custom_calc.calculate(klines, interval_hours=4.0)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, DDPSResult)


class IntervalHelperTests(TestCase):
    """Interval辅助方法测试"""

    def test_to_hours_common_intervals(self):
        """测试：常用周期转小时"""
        self.assertEqual(Interval.to_hours('1m'), 1/60)
        self.assertEqual(Interval.to_hours('5m'), 5/60)
        self.assertEqual(Interval.to_hours('15m'), 0.25)
        self.assertEqual(Interval.to_hours('30m'), 0.5)
        self.assertEqual(Interval.to_hours('1h'), 1.0)
        self.assertEqual(Interval.to_hours('4h'), 4.0)
        self.assertEqual(Interval.to_hours('1d'), 24.0)
        self.assertEqual(Interval.to_hours('1w'), 168.0)

    def test_to_minutes(self):
        """测试：周期转分钟"""
        self.assertEqual(Interval.to_minutes('1h'), 60)
        self.assertEqual(Interval.to_minutes('4h'), 240)
        self.assertEqual(Interval.to_minutes('1d'), 1440)

    def test_to_seconds(self):
        """测试：周期转秒"""
        self.assertEqual(Interval.to_seconds('1h'), 3600)
        self.assertEqual(Interval.to_seconds('4h'), 14400)
        self.assertEqual(Interval.to_seconds('1d'), 86400)

    def test_unknown_interval_default(self):
        """测试：未知周期返回默认值"""
        self.assertEqual(Interval.to_hours('unknown'), 4.0)
