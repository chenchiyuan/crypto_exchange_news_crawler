"""
KeyLevelBreachDetector单元测试

测试关键位跌破检测器的所有功能，包括：
- Guard Clauses异常路径
- 正常计算路径
- 边界条件
- 计算准确性验证

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md
    - Task: TASK-002-013
"""

import unittest
from decimal import Decimal

from django.test import TestCase

from volume_trap.detectors.key_level_breach_detector import KeyLevelBreachDetector
from volume_trap.exceptions import InvalidDataError


class KeyLevelBreachDetectorGuardClausesTest(TestCase):
    """测试KeyLevelBreachDetector的Guard Clauses异常路径。

    验证所有边界检查和异常处理是否按预期工作。
    """

    def setUp(self):
        """测试前准备。"""
        self.detector = KeyLevelBreachDetector()

    def test_guard_clause_trigger_high_zero(self):
        """测试trigger_high检查：最高价为0应抛出InvalidDataError。"""
        with self.assertRaises(InvalidDataError) as context:
            self.detector.detect(
                trigger_high=Decimal("0.00"),  # 异常：high=0
                trigger_low=Decimal("49000.00"),
                current_close=Decimal("50000.00"),
            )

        exc = context.exception
        self.assertEqual(exc.field, "trigger_high")
        self.assertEqual(exc.value, 0.0)
        self.assertIn("触发K线最高价必须>0", exc.context)

    def test_guard_clause_trigger_low_zero(self):
        """测试trigger_low检查：最低价为0应抛出InvalidDataError。"""
        with self.assertRaises(InvalidDataError) as context:
            self.detector.detect(
                trigger_high=Decimal("51000.00"),
                trigger_low=Decimal("0.00"),  # 异常：low=0
                current_close=Decimal("50000.00"),
            )

        exc = context.exception
        self.assertEqual(exc.field, "trigger_low")
        self.assertEqual(exc.value, 0.0)
        self.assertIn("触发K线最低价必须>0", exc.context)

    def test_guard_clause_current_close_zero(self):
        """测试current_close检查：收盘价为0应抛出InvalidDataError。"""
        with self.assertRaises(InvalidDataError) as context:
            self.detector.detect(
                trigger_high=Decimal("51000.00"),
                trigger_low=Decimal("49000.00"),
                current_close=Decimal("0.00"),  # 异常：close=0
            )

        exc = context.exception
        self.assertEqual(exc.field, "current_close")
        self.assertEqual(exc.value, 0.0)
        self.assertIn("当前收盘价必须>0", exc.context)

    def test_guard_clause_trigger_high_negative(self):
        """测试trigger_high检查：负数应抛出InvalidDataError。"""
        with self.assertRaises(InvalidDataError) as context:
            self.detector.detect(
                trigger_high=Decimal("-51000.00"),  # 异常：负数
                trigger_low=Decimal("49000.00"),
                current_close=Decimal("50000.00"),
            )

        exc = context.exception
        self.assertEqual(exc.field, "trigger_high")

    def test_guard_clause_trigger_low_negative(self):
        """测试trigger_low检查：负数应抛出InvalidDataError。"""
        with self.assertRaises(InvalidDataError) as context:
            self.detector.detect(
                trigger_high=Decimal("51000.00"),
                trigger_low=Decimal("-49000.00"),  # 异常：负数
                current_close=Decimal("50000.00"),
            )

        exc = context.exception
        self.assertEqual(exc.field, "trigger_low")

    def test_guard_clause_current_close_negative(self):
        """测试current_close检查：负数应抛出InvalidDataError。"""
        with self.assertRaises(InvalidDataError) as context:
            self.detector.detect(
                trigger_high=Decimal("51000.00"),
                trigger_low=Decimal("49000.00"),
                current_close=Decimal("-50000.00"),  # 异常：负数
            )

        exc = context.exception
        self.assertEqual(exc.field, "current_close")

    def test_guard_clause_high_less_than_low(self):
        """测试high<low检查：最高价小于最低价应抛出InvalidDataError。"""
        with self.assertRaises(InvalidDataError) as context:
            self.detector.detect(
                trigger_high=Decimal("48000.00"),  # 异常：high < low
                trigger_low=Decimal("49000.00"),
                current_close=Decimal("50000.00"),
            )

        exc = context.exception
        self.assertEqual(exc.field, "trigger_high")
        self.assertIn("数据异常：trigger_high", exc.context)
        self.assertIn("< trigger_low", exc.context)


class KeyLevelBreachDetectorAccuracyTest(TestCase):
    """测试关键位和跌破幅度计算准确性。

    验证中轴、关键位、跌破幅度的计算是否正确。
    """

    def setUp(self):
        """测试前准备。"""
        self.detector = KeyLevelBreachDetector()

    def test_key_level_calculation_normal_case(self):
        """测试正常情况下的关键位计算准确性。

        场景：
        - trigger_high = 51000, trigger_low = 49000
        - 中轴 = (51000 + 49000) / 2 = 50000
        - 关键位 = min(50000, 49000) = 49000
        """
        result = self.detector.detect(
            trigger_high=Decimal("51000.00"),
            trigger_low=Decimal("49000.00"),
            current_close=Decimal("50000.00"),
        )

        # 验证中轴 = 50000
        expected_midpoint = 50000.0
        actual_midpoint = float(result["midpoint"])
        self.assertAlmostEqual(
            actual_midpoint,
            expected_midpoint,
            delta=0.01,
            msg=f"中轴计算误差: expected={expected_midpoint}, actual={actual_midpoint}",
        )

        # 验证关键位 = 49000（取min值）
        expected_key_level = 49000.0
        actual_key_level = float(result["key_level"])
        self.assertAlmostEqual(
            actual_key_level,
            expected_key_level,
            delta=0.01,
            msg=f"关键位计算误差: expected={expected_key_level}, actual={actual_key_level}",
        )

    def test_midpoint_calculation(self):
        """测试中轴计算准确性。

        场景：
        - trigger_high = 60000, trigger_low = 40000
        - 预期中轴 = (60000 + 40000) / 2 = 50000
        """
        result = self.detector.detect(
            trigger_high=Decimal("60000.00"),
            trigger_low=Decimal("40000.00"),
            current_close=Decimal("45000.00"),
        )

        expected_midpoint = 50000.0
        actual_midpoint = float(result["midpoint"])
        self.assertAlmostEqual(actual_midpoint, expected_midpoint, delta=0.01)

    def test_key_level_equals_low(self):
        """测试关键位取min值逻辑：当中轴>low时，关键位=low。

        场景：
        - trigger_high = 51000, trigger_low = 49000
        - 中轴 = 50000 > low (49000)
        - 预期关键位 = 49000
        """
        result = self.detector.detect(
            trigger_high=Decimal("51000.00"),
            trigger_low=Decimal("49000.00"),
            current_close=Decimal("50000.00"),
        )

        # 关键位应该等于low
        expected_key_level = 49000.0
        actual_key_level = float(result["key_level"])
        self.assertEqual(actual_key_level, expected_key_level)

    def test_breach_percentage_calculation(self):
        """测试跌破幅度计算准确性。

        场景：
        - 关键位 = 49000
        - 当前收盘价 = 48500
        - 预期跌破幅度 = (49000 - 48500) / 49000 × 100 ≈ 1.02%
        """
        result = self.detector.detect(
            trigger_high=Decimal("51000.00"),
            trigger_low=Decimal("49000.00"),
            current_close=Decimal("48500.00"),  # 跌破关键位
        )

        # 验证跌破幅度 ≈ 1.02%
        expected_breach = 1.02
        actual_breach = float(result["breach_percentage"])
        self.assertAlmostEqual(
            actual_breach,
            expected_breach,
            delta=0.01,
            msg=f"跌破幅度计算误差: expected={expected_breach}, actual={actual_breach}",
        )

    def test_breach_percentage_zero_when_not_triggered(self):
        """测试未跌破时幅度为0。

        场景：
        - 当前价 = 50000 > 关键位 (49000)
        - 预期跌破幅度 = 0
        """
        result = self.detector.detect(
            trigger_high=Decimal("51000.00"),
            trigger_low=Decimal("49000.00"),
            current_close=Decimal("50000.00"),  # 未跌破
        )

        # 验证跌破幅度 = 0
        self.assertEqual(float(result["breach_percentage"]), 0.0)


class KeyLevelBreachDetectorTriggerTest(TestCase):
    """测试触发条件逻辑。"""

    def setUp(self):
        """测试前准备。"""
        self.detector = KeyLevelBreachDetector()

    def test_triggered_below_key_level(self):
        """测试触发条件：当前价<关键位，应触发。"""
        result = self.detector.detect(
            trigger_high=Decimal("51000.00"),
            trigger_low=Decimal("49000.00"),
            current_close=Decimal("48500.00"),  # < 关键位49000
        )

        self.assertTrue(result["triggered"], "当前价=48500 < 关键位49000应该触发")
        self.assertGreater(float(result["breach_percentage"]), 0)

    def test_not_triggered_above_key_level(self):
        """测试触发条件：当前价>关键位，不应触发。"""
        result = self.detector.detect(
            trigger_high=Decimal("51000.00"),
            trigger_low=Decimal("49000.00"),
            current_close=Decimal("50000.00"),  # > 关键位49000
        )

        self.assertFalse(result["triggered"], "当前价=50000 > 关键位49000不应触发")
        self.assertEqual(float(result["breach_percentage"]), 0.0)

    def test_boundary_equals_key_level(self):
        """测试边界：当前价恰好等于关键位，不应触发（<条件）。"""
        result = self.detector.detect(
            trigger_high=Decimal("51000.00"),
            trigger_low=Decimal("49000.00"),
            current_close=Decimal("49000.00"),  # = 关键位49000
        )

        # 当前价=关键位，不应触发（<条件）
        self.assertFalse(result["triggered"], "当前价=关键位不应触发")
        self.assertEqual(float(result["breach_percentage"]), 0.0)


class KeyLevelBreachDetectorBoundaryTest(TestCase):
    """测试KeyLevelBreachDetector的边界条件。"""

    def setUp(self):
        """测试前准备。"""
        self.detector = KeyLevelBreachDetector()

    def test_boundary_high_equals_low(self):
        """测试边界：high=low时（十字星）。

        场景：
        - trigger_high = trigger_low = 50000
        - 中轴 = 50000
        - 关键位 = min(50000, 50000) = 50000
        """
        result = self.detector.detect(
            trigger_high=Decimal("50000.00"),
            trigger_low=Decimal("50000.00"),  # high = low
            current_close=Decimal("49500.00"),
        )

        # 验证中轴 = 50000
        self.assertEqual(float(result["midpoint"]), 50000.0)

        # 验证关键位 = 50000
        self.assertEqual(float(result["key_level"]), 50000.0)

        # 验证触发（49500 < 50000）
        self.assertTrue(result["triggered"])

    def test_small_price_values(self):
        """测试小价格值的计算（如山寨币）。

        场景：
        - trigger_high = 0.0010, trigger_low = 0.0008
        - 中轴 = 0.0009
        - 关键位 = 0.0008
        """
        result = self.detector.detect(
            trigger_high=Decimal("0.0010"),
            trigger_low=Decimal("0.0008"),
            current_close=Decimal("0.0007"),
        )

        # 验证中轴
        expected_midpoint = 0.0009
        actual_midpoint = float(result["midpoint"])
        self.assertAlmostEqual(actual_midpoint, expected_midpoint, delta=0.0001)

        # 验证关键位 = 0.0008
        expected_key_level = 0.0008
        actual_key_level = float(result["key_level"])
        self.assertAlmostEqual(actual_key_level, expected_key_level, delta=0.0001)

        # 验证触发（0.0007 < 0.0008）
        self.assertTrue(result["triggered"])

    def test_large_price_values(self):
        """测试大价格值的计算（如BTC）。

        场景：
        - trigger_high = 100000, trigger_low = 95000
        - 中轴 = 97500
        - 关键位 = 95000
        """
        result = self.detector.detect(
            trigger_high=Decimal("100000.00"),
            trigger_low=Decimal("95000.00"),
            current_close=Decimal("94000.00"),
        )

        # 验证中轴 = 97500
        expected_midpoint = 97500.0
        actual_midpoint = float(result["midpoint"])
        self.assertAlmostEqual(actual_midpoint, expected_midpoint, delta=0.01)

        # 验证关键位 = 95000
        expected_key_level = 95000.0
        actual_key_level = float(result["key_level"])
        self.assertAlmostEqual(actual_key_level, expected_key_level, delta=0.01)

        # 验证触发（94000 < 95000）
        self.assertTrue(result["triggered"])

        # 验证跌破幅度 ≈ 1.05%
        expected_breach = 1.05
        actual_breach = float(result["breach_percentage"])
        self.assertAlmostEqual(actual_breach, expected_breach, delta=0.01)


if __name__ == "__main__":
    unittest.main()
