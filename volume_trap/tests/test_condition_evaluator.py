"""
ConditionEvaluator单元测试

测试条件评估器的所有功能，包括：
- 三阶段评估逻辑正确性
- 缺少required key时抛出KeyError
- 检测器返回None时的处理

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md
    - Task: TASK-002-020
"""

import unittest

from django.test import TestCase

from volume_trap.evaluators.condition_evaluator import ConditionEvaluator


class ConditionEvaluatorDiscoveryTest(TestCase):
    """测试Discovery阶段条件评估。

    验证RVOL和振幅的组合逻辑是否正确。
    """

    def setUp(self):
        """测试前准备。"""
        self.evaluator = ConditionEvaluator()

    def test_discovery_both_triggered(self):
        """测试Discovery条件：RVOL和振幅都触发，应返回True。"""
        results = {"rvol_triggered": True, "amplitude_triggered": True}

        result = self.evaluator.evaluate_discovery_condition(results)

        self.assertTrue(result, "RVOL和振幅都触发，应返回True")

    def test_discovery_rvol_only(self):
        """测试Discovery条件：仅RVOL触发，应返回False。"""
        results = {"rvol_triggered": True, "amplitude_triggered": False}

        result = self.evaluator.evaluate_discovery_condition(results)

        self.assertFalse(result, "仅RVOL触发，应返回False")

    def test_discovery_amplitude_only(self):
        """测试Discovery条件：仅振幅触发，应返回False。"""
        results = {"rvol_triggered": False, "amplitude_triggered": True}

        result = self.evaluator.evaluate_discovery_condition(results)

        self.assertFalse(result, "仅振幅触发，应返回False")

    def test_discovery_neither_triggered(self):
        """测试Discovery条件：都未触发，应返回False。"""
        results = {"rvol_triggered": False, "amplitude_triggered": False}

        result = self.evaluator.evaluate_discovery_condition(results)

        self.assertFalse(result, "都未触发，应返回False")

    def test_discovery_missing_key(self):
        """测试Discovery条件：缺少required key，应抛出KeyError。"""
        results = {
            "rvol_triggered": True
            # 缺少 amplitude_triggered
        }

        with self.assertRaises(KeyError):
            self.evaluator.evaluate_discovery_condition(results)

    def test_discovery_none_results(self):
        """测试Discovery条件：results为None，应返回False。"""
        result = self.evaluator.evaluate_discovery_condition(None)

        self.assertFalse(result, "results为None，应返回False")

    def test_discovery_none_value(self):
        """测试Discovery条件：检测器结果为None，应返回False。"""
        results = {"rvol_triggered": None, "amplitude_triggered": True}

        result = self.evaluator.evaluate_discovery_condition(results)

        self.assertFalse(result, "检测器结果为None，应返回False")


class ConditionEvaluatorConfirmationTest(TestCase):
    """测试Confirmation阶段条件评估。

    验证成交量留存、关键位跌破、PE异常的组合逻辑是否正确。
    """

    def setUp(self):
        """测试前准备。"""
        self.evaluator = ConditionEvaluator()

    def test_confirmation_all_triggered(self):
        """测试Confirmation条件：三者都触发，应返回True。"""
        results = {
            "volume_retention_triggered": True,
            "key_level_breached": True,
            "pe_triggered": True,
        }

        result = self.evaluator.evaluate_confirmation_condition(results)

        self.assertTrue(result, "三者都触发，应返回True")

    def test_confirmation_partial_triggered(self):
        """测试Confirmation条件：部分触发，应返回False。"""
        # 测试1：成交量留存+关键位跌破
        results = {
            "volume_retention_triggered": True,
            "key_level_breached": True,
            "pe_triggered": False,
        }
        result = self.evaluator.evaluate_confirmation_condition(results)
        self.assertFalse(result, "缺少PE触发，应返回False")

        # 测试2：成交量留存+PE触发
        results = {
            "volume_retention_triggered": True,
            "key_level_breached": False,
            "pe_triggered": True,
        }
        result = self.evaluator.evaluate_confirmation_condition(results)
        self.assertFalse(result, "缺少关键位跌破，应返回False")

        # 测试3：关键位跌破+PE触发
        results = {
            "volume_retention_triggered": False,
            "key_level_breached": True,
            "pe_triggered": True,
        }
        result = self.evaluator.evaluate_confirmation_condition(results)
        self.assertFalse(result, "缺少成交量留存触发，应返回False")

    def test_confirmation_none_triggered(self):
        """测试Confirmation条件：都未触发，应返回False。"""
        results = {
            "volume_retention_triggered": False,
            "key_level_breached": False,
            "pe_triggered": False,
        }

        result = self.evaluator.evaluate_confirmation_condition(results)

        self.assertFalse(result, "都未触发，应返回False")

    def test_confirmation_missing_key(self):
        """测试Confirmation条件：缺少required key，应抛出KeyError。"""
        results = {
            "volume_retention_triggered": True,
            "key_level_breached": True,
            # 缺少 pe_triggered
        }

        with self.assertRaises(KeyError):
            self.evaluator.evaluate_confirmation_condition(results)

    def test_confirmation_none_results(self):
        """测试Confirmation条件：results为None，应返回False。"""
        result = self.evaluator.evaluate_confirmation_condition(None)

        self.assertFalse(result, "results为None，应返回False")

    def test_confirmation_none_value(self):
        """测试Confirmation条件：检测器结果为None，应返回False。"""
        results = {
            "volume_retention_triggered": True,
            "key_level_breached": None,
            "pe_triggered": True,
        }

        result = self.evaluator.evaluate_confirmation_condition(results)

        self.assertFalse(result, "检测器结果为None，应返回False")


class ConditionEvaluatorValidationTest(TestCase):
    """测试Validation阶段条件评估。

    验证MA死叉、OBV单边下滑、ATR压缩的组合逻辑是否正确。
    """

    def setUp(self):
        """测试前准备。"""
        self.evaluator = ConditionEvaluator()

    def test_validation_all_triggered(self):
        """测试Validation条件：三者都触发，应返回True。"""
        results = {"ma_death_cross": True, "obv_single_side_decline": True, "atr_compressed": True}

        result = self.evaluator.evaluate_validation_condition(results)

        self.assertTrue(result, "三者都触发，应返回True")

    def test_validation_partial_triggered(self):
        """测试Validation条件：部分触发，应返回False。"""
        # 测试1：MA死叉+OBV单边下滑
        results = {"ma_death_cross": True, "obv_single_side_decline": True, "atr_compressed": False}
        result = self.evaluator.evaluate_validation_condition(results)
        self.assertFalse(result, "缺少ATR压缩，应返回False")

        # 测试2：MA死叉+ATR压缩
        results = {"ma_death_cross": True, "obv_single_side_decline": False, "atr_compressed": True}
        result = self.evaluator.evaluate_validation_condition(results)
        self.assertFalse(result, "缺少OBV单边下滑，应返回False")

        # 测试3：OBV单边下滑+ATR压缩
        results = {"ma_death_cross": False, "obv_single_side_decline": True, "atr_compressed": True}
        result = self.evaluator.evaluate_validation_condition(results)
        self.assertFalse(result, "缺少MA死叉，应返回False")

    def test_validation_none_triggered(self):
        """测试Validation条件：都未触发，应返回False。"""
        results = {
            "ma_death_cross": False,
            "obv_single_side_decline": False,
            "atr_compressed": False,
        }

        result = self.evaluator.evaluate_validation_condition(results)

        self.assertFalse(result, "都未触发，应返回False")

    def test_validation_missing_key(self):
        """测试Validation条件：缺少required key，应抛出KeyError。"""
        results = {
            "ma_death_cross": True,
            "obv_single_side_decline": True,
            # 缺少 atr_compressed
        }

        with self.assertRaises(KeyError):
            self.evaluator.evaluate_validation_condition(results)

    def test_validation_none_results(self):
        """测试Validation条件：results为None，应返回False。"""
        result = self.evaluator.evaluate_validation_condition(None)

        self.assertFalse(result, "results为None，应返回False")

    def test_validation_none_value(self):
        """测试Validation条件：检测器结果为None，应返回False。"""
        results = {"ma_death_cross": True, "obv_single_side_decline": True, "atr_compressed": None}

        result = self.evaluator.evaluate_validation_condition(results)

        self.assertFalse(result, "检测器结果为None，应返回False")


if __name__ == "__main__":
    unittest.main()
