"""
测试文件：MetricsCalculator 初始化测试

Purpose:
    验证 MetricsCalculator 类的构造函数正确性、参数校验和异常处理

关联任务: TASK-014-003
关联需求: FP-014-001至FP-014-015（prd.md）
关联架构: architecture.md#4.2 MetricsCalculator - 核心原子服务

测试策略:
    - 单元测试
    - 覆盖正常场景、边界场景、异常场景
    - Fail-Fast验证：risk_free_rate 超出范围应立即抛出异常
"""

import unittest
from decimal import Decimal
from strategy_adapter.core.metrics_calculator import MetricsCalculator


class TestMetricsCalculatorInit(unittest.TestCase):
    """MetricsCalculator 初始化测试套件"""

    def test_metrics_calculator_creation_with_default_risk_free_rate(self):
        """
        测试用例1：使用默认无风险收益率创建 MetricsCalculator

        验收标准: 默认 risk_free_rate = 3%
        """
        # Arrange & Act
        calculator = MetricsCalculator()

        # Assert
        self.assertEqual(calculator.risk_free_rate, Decimal("0.03"))
        self.assertIsInstance(calculator.risk_free_rate, Decimal)

    def test_metrics_calculator_creation_with_custom_risk_free_rate(self):
        """
        测试用例2：使用自定义无风险收益率创建 MetricsCalculator

        验收标准: 支持自定义 risk_free_rate 参数
        """
        # Arrange
        custom_rate = Decimal("0.05")

        # Act
        calculator = MetricsCalculator(risk_free_rate=custom_rate)

        # Assert
        self.assertEqual(calculator.risk_free_rate, custom_rate)

    def test_metrics_calculator_risk_free_rate_boundary_min(self):
        """
        测试用例3：边界测试 - risk_free_rate = 0（最小边界）

        验收标准: risk_free_rate = 0 应该被接受
        """
        # Arrange & Act
        calculator = MetricsCalculator(risk_free_rate=Decimal("0"))

        # Assert
        self.assertEqual(calculator.risk_free_rate, Decimal("0"))

    def test_metrics_calculator_risk_free_rate_boundary_max(self):
        """
        测试用例4：边界测试 - risk_free_rate = 1（最大边界）

        验收标准: risk_free_rate = 1 应该被接受
        """
        # Arrange & Act
        calculator = MetricsCalculator(risk_free_rate=Decimal("1"))

        # Assert
        self.assertEqual(calculator.risk_free_rate, Decimal("1"))

    # === Fail-Fast 异常测试 ===

    def test_metrics_calculator_negative_risk_free_rate_raises_valueerror(self):
        """
        测试用例5：Fail-Fast验证 - 负数 risk_free_rate 应立即抛出 ValueError

        验收标准: 当 risk_free_rate < 0 时抛出 ValueError
        边界检查: risk_free_rate 必须在 [0, 1] 范围内
        """
        # Arrange
        invalid_rate = Decimal("-0.05")

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            MetricsCalculator(risk_free_rate=invalid_rate)

        # 验证异常消息包含上下文信息（预期范围 vs 实际值）
        self.assertIn("risk_free_rate必须在[0, 1]范围内", str(context.exception))
        self.assertIn(str(invalid_rate), str(context.exception))

    def test_metrics_calculator_risk_free_rate_greater_than_one_raises_valueerror(self):
        """
        测试用例6：Fail-Fast验证 - risk_free_rate > 1 应立即抛出 ValueError

        验收标准: 当 risk_free_rate > 1 时抛出 ValueError
        边界检查: risk_free_rate 必须在 [0, 1] 范围内
        """
        # Arrange
        invalid_rate = Decimal("1.5")

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            MetricsCalculator(risk_free_rate=invalid_rate)

        # 验证异常消息包含上下文信息
        self.assertIn("risk_free_rate必须在[0, 1]范围内", str(context.exception))
        self.assertIn(str(invalid_rate), str(context.exception))

    def test_metrics_calculator_has_calculate_all_metrics_method(self):
        """
        测试用例7：验证 calculate_all_metrics 方法存在

        验收标准: MetricsCalculator 必须有 calculate_all_metrics 方法
        """
        # Arrange
        calculator = MetricsCalculator()

        # Assert
        self.assertTrue(hasattr(calculator, 'calculate_all_metrics'))
        self.assertTrue(callable(getattr(calculator, 'calculate_all_metrics')))


class TestMetricsCalculatorFramework(unittest.TestCase):
    """MetricsCalculator 框架方法测试套件"""

    def test_calculate_all_metrics_returns_dict_with_17_keys(self):
        """
        测试用例8：验证 calculate_all_metrics 返回包含 17 个 P0 指标的字典

        验收标准: 返回值结构定义：Dict[str, Decimal]，包含 17 个 P0 指标键
        """
        # Arrange
        calculator = MetricsCalculator()

        # 准备测试数据（空数据，仅测试返回结构）
        orders = []
        equity_curve = []
        initial_cash = Decimal("10000")
        days = 365

        # Act
        metrics = calculator.calculate_all_metrics(orders, equity_curve, initial_cash, days)

        # Assert
        self.assertIsInstance(metrics, dict)

        # 验证包含 17 个 P0 指标键
        expected_keys = [
            # 收益分析（3个）
            'apr', 'absolute_return', 'cumulative_return',
            # 风险分析（4个）
            'mdd', 'mdd_start_time', 'mdd_end_time', 'recovery_time',
            # 波动率
            'volatility',
            # 风险调整收益（4个）
            'sharpe_ratio', 'calmar_ratio', 'mar_ratio', 'profit_factor',
            # 交易效率（4个）
            'trade_frequency', 'cost_percentage', 'win_rate', 'payoff_ratio'
        ]

        for key in expected_keys:
            self.assertIn(key, metrics, f"缺少指标键: {key}")


if __name__ == '__main__':
    unittest.main()
