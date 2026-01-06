"""
VolumeTrapStateMachine单元测试

测试状态机核心功能，包括：
- 初始化测试
- scan方法基本流程
- interval参数验证

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md
    - Task: TASK-002-021

注意：这是基础单元测试，完整的集成测试需要大量测试数据。
"""

import unittest

from django.test import TestCase

from volume_trap.services.volume_trap_fsm import VolumeTrapStateMachine


class VolumeTrapStateMachineInitTest(TestCase):
    """测试状态机初始化。"""

    def test_init_success(self):
        """测试状态机初始化成功。"""
        fsm = VolumeTrapStateMachine()

        # 验证所有检测器都已初始化
        self.assertIsNotNone(fsm.rvol_calculator)
        self.assertIsNotNone(fsm.amplitude_detector)
        self.assertIsNotNone(fsm.volume_retention_analyzer)
        self.assertIsNotNone(fsm.key_level_breach_detector)
        self.assertIsNotNone(fsm.price_efficiency_analyzer)
        self.assertIsNotNone(fsm.ma_cross_detector)
        self.assertIsNotNone(fsm.obv_divergence_analyzer)
        self.assertIsNotNone(fsm.atr_compression_detector)
        self.assertIsNotNone(fsm.condition_evaluator)


class VolumeTrapStateMachineScanTest(TestCase):
    """测试scan方法基本流程。"""

    def setUp(self):
        """测试前准备。"""
        self.fsm = VolumeTrapStateMachine()

    def test_scan_invalid_interval(self):
        """测试scan方法：无效interval应抛出ValueError。"""
        with self.assertRaises(ValueError) as context:
            self.fsm.scan(interval="invalid")

        self.assertIn("interval参数错误", str(context.exception))

    def test_scan_valid_interval_1h(self):
        """测试scan方法：有效interval='1h'应返回结果字典。"""
        result = self.fsm.scan(interval="1h")

        # 验证返回结构
        self.assertIn("discovery", result)
        self.assertIn("confirmation", result)
        self.assertIn("validation", result)
        self.assertIn("errors", result)

        # 验证类型
        self.assertIsInstance(result["discovery"], int)
        self.assertIsInstance(result["confirmation"], int)
        self.assertIsInstance(result["validation"], int)
        self.assertIsInstance(result["errors"], list)

    def test_scan_valid_interval_4h(self):
        """测试scan方法：有效interval='4h'应返回结果字典。"""
        result = self.fsm.scan(interval="4h")

        # 验证返回结构
        self.assertIn("discovery", result)
        self.assertIn("confirmation", result)
        self.assertIn("validation", result)
        self.assertIn("errors", result)

    def test_scan_valid_interval_1d(self):
        """测试scan方法：有效interval='1d'应返回结果字典。"""
        result = self.fsm.scan(interval="1d")

        # 验证返回结构
        self.assertIn("discovery", result)
        self.assertIn("confirmation", result)
        self.assertIn("validation", result)
        self.assertIn("errors", result)

    def test_scan_default_interval(self):
        """测试scan方法：默认interval='4h'应返回结果字典。"""
        result = self.fsm.scan()  # 使用默认参数

        # 验证返回结构
        self.assertIn("discovery", result)
        self.assertIn("confirmation", result)
        self.assertIn("validation", result)
        self.assertIn("errors", result)


if __name__ == "__main__":
    unittest.main()
