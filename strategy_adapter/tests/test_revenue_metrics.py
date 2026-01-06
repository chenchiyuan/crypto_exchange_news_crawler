"""
测试文件：收益指标计算测试

Purpose:
    验证 MetricsCalculator 的收益指标计算方法的正确性

关联任务: TASK-014-004
关联需求: FP-014-001, FP-014-002, FP-014-003（prd.md）
关联架构: architecture.md#4.2 MetricsCalculator

测试策略:
    - 单元测试
    - 覆盖正常场景、边界场景、异常场景
    - Fail-Fast验证：非法输入应立即抛出异常
"""

import unittest
from decimal import Decimal
from strategy_adapter.core.metrics_calculator import MetricsCalculator


class TestAPRCalculation(unittest.TestCase):
    """APR（年化收益率）计算测试套件"""

    def test_apr_calculation_standard_case(self):
        """
        测试用例1：标准场景 - 365天，10%收益

        验收标准: APR = (total_profit / initial_cash) × (365 / days) × 100%
        """
        # Arrange
        calculator = MetricsCalculator()
        total_profit = Decimal("1000.00")
        initial_cash = Decimal("10000.00")
        days = 365

        # Act
        apr = calculator.calculate_apr(total_profit, initial_cash, days)

        # Assert
        expected_apr = Decimal("10.00")  # (1000/10000) × (365/365) × 100
        self.assertEqual(apr, expected_apr)

    def test_apr_calculation_half_year(self):
        """
        测试用例2：半年场景 - 182.5天，10%收益

        验收标准: APR应该年化为20%
        """
        # Arrange
        calculator = MetricsCalculator()
        total_profit = Decimal("1000.00")
        initial_cash = Decimal("10000.00")
        days = 182  # 约半年

        # Act
        apr = calculator.calculate_apr(total_profit, initial_cash, days)

        # Assert
        # APR = (1000/10000) × (365/182) × 100 ≈ 20.05%
        expected_apr = Decimal("20.05")
        self.assertEqual(apr, expected_apr)

    def test_apr_calculation_negative_profit(self):
        """
        测试用例3：亏损场景 - 负收益应返回负APR

        验收标准: 支持负收益率计算
        """
        # Arrange
        calculator = MetricsCalculator()
        total_profit = Decimal("-500.00")
        initial_cash = Decimal("10000.00")
        days = 365

        # Act
        apr = calculator.calculate_apr(total_profit, initial_cash, days)

        # Assert
        expected_apr = Decimal("-5.00")
        self.assertEqual(apr, expected_apr)

    def test_apr_calculation_short_period(self):
        """
        测试用例4：短期回测 - 7天回测期

        验收标准: 短期高收益应正确年化
        """
        # Arrange
        calculator = MetricsCalculator()
        total_profit = Decimal("100.00")  # 7天赚100
        initial_cash = Decimal("10000.00")
        days = 7

        # Act
        apr = calculator.calculate_apr(total_profit, initial_cash, days)

        # Assert
        # APR = (100/10000) × (365/7) × 100 ≈ 52.14%
        expected_apr = Decimal("52.14")
        self.assertEqual(apr, expected_apr)

    # === Fail-Fast 异常测试 ===

    def test_apr_zero_initial_cash_raises_valueerror(self):
        """
        测试用例5：Fail-Fast验证 - initial_cash = 0 应立即抛出 ValueError

        验收标准: 当 initial_cash <= 0 时立即抛出 ValueError
        """
        # Arrange
        calculator = MetricsCalculator()
        total_profit = Decimal("1000.00")
        invalid_initial_cash = Decimal("0")
        days = 365

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            calculator.calculate_apr(total_profit, invalid_initial_cash, days)

        self.assertIn("initial_cash必须大于0", str(context.exception))
        self.assertIn(str(invalid_initial_cash), str(context.exception))

    def test_apr_negative_initial_cash_raises_valueerror(self):
        """
        测试用例6：Fail-Fast验证 - 负数 initial_cash 应立即抛出 ValueError

        验收标准: 边界检查验证
        """
        # Arrange
        calculator = MetricsCalculator()
        total_profit = Decimal("1000.00")
        invalid_initial_cash = Decimal("-10000.00")
        days = 365

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            calculator.calculate_apr(total_profit, invalid_initial_cash, days)

        self.assertIn("initial_cash必须大于0", str(context.exception))

    def test_apr_zero_days_raises_valueerror(self):
        """
        测试用例7：Fail-Fast验证 - days = 0 应立即抛出 ValueError

        验收标准: 当 days <= 0 时立即抛出 ValueError
        """
        # Arrange
        calculator = MetricsCalculator()
        total_profit = Decimal("1000.00")
        initial_cash = Decimal("10000.00")
        invalid_days = 0

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            calculator.calculate_apr(total_profit, initial_cash, invalid_days)

        self.assertIn("days必须大于0", str(context.exception))
        self.assertIn(str(invalid_days), str(context.exception))

    def test_apr_negative_days_raises_valueerror(self):
        """
        测试用例8：Fail-Fast验证 - 负数 days 应立即抛出 ValueError

        验收标准: 边界检查验证
        """
        # Arrange
        calculator = MetricsCalculator()
        total_profit = Decimal("1000.00")
        initial_cash = Decimal("10000.00")
        invalid_days = -365

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            calculator.calculate_apr(total_profit, initial_cash, invalid_days)

        self.assertIn("days必须大于0", str(context.exception))


class TestCumulativeReturnCalculation(unittest.TestCase):
    """累计收益率计算测试套件"""

    def test_cumulative_return_calculation_standard_case(self):
        """
        测试用例9：标准场景 - 初始10000，收益1000

        验收标准: 累计收益率 = (total_profit / initial_cash) × 100%
        """
        # Arrange
        calculator = MetricsCalculator()
        total_profit = Decimal("1000.00")
        initial_cash = Decimal("10000.00")

        # Act
        cumulative_return = calculator.calculate_cumulative_return(total_profit, initial_cash)

        # Assert
        expected_return = Decimal("10.00")  # (1000/10000) × 100
        self.assertEqual(cumulative_return, expected_return)

    def test_cumulative_return_calculation_negative_profit(self):
        """
        测试用例10：亏损场景 - 负收益应返回负累计收益率

        验收标准: 支持负收益率
        """
        # Arrange
        calculator = MetricsCalculator()
        total_profit = Decimal("-2000.00")
        initial_cash = Decimal("10000.00")

        # Act
        cumulative_return = calculator.calculate_cumulative_return(total_profit, initial_cash)

        # Assert
        expected_return = Decimal("-20.00")
        self.assertEqual(cumulative_return, expected_return)

    def test_cumulative_return_calculation_large_profit(self):
        """
        测试用例11：大幅盈利场景 - 翻倍收益

        验收标准: 收益超过100%应正确计算
        """
        # Arrange
        calculator = MetricsCalculator()
        total_profit = Decimal("15000.00")  # 翻1.5倍
        initial_cash = Decimal("10000.00")

        # Act
        cumulative_return = calculator.calculate_cumulative_return(total_profit, initial_cash)

        # Assert
        expected_return = Decimal("150.00")
        self.assertEqual(cumulative_return, expected_return)

    def test_cumulative_return_zero_profit(self):
        """
        测试用例12：无盈亏场景 - 零收益

        验收标准: 零收益应返回0%
        """
        # Arrange
        calculator = MetricsCalculator()
        total_profit = Decimal("0.00")
        initial_cash = Decimal("10000.00")

        # Act
        cumulative_return = calculator.calculate_cumulative_return(total_profit, initial_cash)

        # Assert
        expected_return = Decimal("0.00")
        self.assertEqual(cumulative_return, expected_return)

    # === Fail-Fast 异常测试 ===

    def test_cumulative_return_zero_initial_cash_raises_valueerror(self):
        """
        测试用例13：Fail-Fast验证 - initial_cash = 0 应立即抛出 ValueError

        验收标准: 当 initial_cash <= 0 时立即抛出 ValueError
        """
        # Arrange
        calculator = MetricsCalculator()
        total_profit = Decimal("1000.00")
        invalid_initial_cash = Decimal("0")

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            calculator.calculate_cumulative_return(total_profit, invalid_initial_cash)

        self.assertIn("initial_cash必须大于0", str(context.exception))


class TestAbsoluteReturnCalculation(unittest.TestCase):
    """绝对收益计算测试套件"""

    def test_absolute_return_is_total_profit(self):
        """
        测试用例14：绝对收益 = total_profit

        验收标准: 绝对收益复用 UnifiedOrderManager.calculate_statistics() 的 total_profit
        """
        # Arrange
        calculator = MetricsCalculator()
        total_profit = Decimal("1234.56")

        # Act
        absolute_return = calculator.calculate_absolute_return(total_profit)

        # Assert
        self.assertEqual(absolute_return, total_profit)

    def test_absolute_return_negative_profit(self):
        """
        测试用例15：负收益场景

        验收标准: 支持负收益
        """
        # Arrange
        calculator = MetricsCalculator()
        total_profit = Decimal("-500.00")

        # Act
        absolute_return = calculator.calculate_absolute_return(total_profit)

        # Assert
        self.assertEqual(absolute_return, total_profit)

    def test_absolute_return_precision(self):
        """
        测试用例16：精度测试 - 保留2位小数

        验收标准: 精度保留2位小数
        """
        # Arrange
        calculator = MetricsCalculator()
        total_profit = Decimal("123.456")

        # Act
        absolute_return = calculator.calculate_absolute_return(total_profit)

        # Assert
        expected_return = Decimal("123.46")  # 四舍五入到2位小数
        self.assertEqual(absolute_return, expected_return)


if __name__ == '__main__':
    unittest.main()
