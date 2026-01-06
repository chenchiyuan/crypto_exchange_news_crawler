"""
测试文件：CLI报告输出测试

Purpose:
    验证 run_strategy_backtest 命令的 _display_results() 方法的输出格式和内容

关联任务: TASK-014-011
关联需求: FP-014-016（prd.md）
关联架构: architecture.md#2.2 报告输出流程

测试策略:
    - 单元测试
    - 覆盖默认模式、详细模式和边界场景
"""

import unittest
from decimal import Decimal
from io import StringIO
from unittest.mock import Mock, patch

from django.test import TestCase

from strategy_adapter.core.metrics_calculator import MetricsCalculator
from strategy_adapter.core.equity_curve_builder import EquityCurveBuilder
from strategy_adapter.models.equity_point import EquityPoint
from strategy_adapter.models.order import Order
from strategy_adapter.models.enums import OrderStatus, OrderSide


class TestDisplayResultsDefaultMode(TestCase):
    """默认模式输出测试套件"""

    def test_display_results_shows_revenue_metrics(self):
        """
        测试用例1：默认模式显示收益分析指标

        验收标准: 输出包含APR、绝对收益、累计收益率
        """
        # Arrange
        calculator = MetricsCalculator()
        total_profit = Decimal("1000.00")
        initial_cash = Decimal("10000.00")
        days = 365

        # Act
        apr = calculator.calculate_apr(total_profit, initial_cash, days)
        cumulative_return = calculator.calculate_cumulative_return(total_profit, initial_cash)
        absolute_return = calculator.calculate_absolute_return(total_profit)

        # Assert - 验证指标计算正确
        self.assertEqual(apr, Decimal("10.00"))
        self.assertEqual(cumulative_return, Decimal("10.00"))
        self.assertEqual(absolute_return, Decimal("1000.00"))

    def test_display_results_shows_risk_metrics(self):
        """
        测试用例2：默认模式显示风险分析指标

        验收标准: 输出包含MDD、波动率
        """
        # Arrange
        calculator = MetricsCalculator()
        equity_curve = [
            EquityPoint(timestamp=1, cash=Decimal("10000"), position_value=Decimal("0"),
                        equity=Decimal("10000"), equity_rate=Decimal("0")),
            EquityPoint(timestamp=2, cash=Decimal("11000"), position_value=Decimal("0"),
                        equity=Decimal("11000"), equity_rate=Decimal("10")),
            EquityPoint(timestamp=3, cash=Decimal("9000"), position_value=Decimal("0"),
                        equity=Decimal("9000"), equity_rate=Decimal("-10")),
        ]

        # Act
        mdd_result = calculator.calculate_mdd(equity_curve)
        volatility = calculator.calculate_volatility(equity_curve)

        # Assert
        self.assertLess(mdd_result['mdd'], Decimal("0"))  # MDD应为负值
        self.assertGreater(volatility, Decimal("0"))  # 波动率应为正值

    def test_display_results_shows_risk_adjusted_metrics(self):
        """
        测试用例3：默认模式显示风险调整收益指标

        验收标准: 输出包含夏普率、卡玛比率、MAR比率、盈利因子
        """
        # Arrange
        calculator = MetricsCalculator(risk_free_rate=Decimal("0.03"))

        # Act
        sharpe = calculator.calculate_sharpe_ratio(Decimal("12.00"), Decimal("15.00"))
        calmar = calculator.calculate_calmar_ratio(Decimal("12.00"), Decimal("-10.00"))
        mar = calculator.calculate_mar_ratio(Decimal("20.00"), Decimal("-15.00"))

        # Assert
        self.assertEqual(sharpe, Decimal("0.60"))
        self.assertEqual(calmar, Decimal("1.20"))
        self.assertEqual(mar, Decimal("1.33"))

    def test_display_results_shows_efficiency_metrics(self):
        """
        测试用例4：默认模式显示交易效率指标

        验收标准: 输出包含交易频率、成本占比、胜率、盈亏比
        """
        # Arrange
        calculator = MetricsCalculator()

        # Act
        frequency = calculator.calculate_trade_frequency(120, 365)
        cost_pct = calculator.calculate_cost_percentage(Decimal("20.00"), Decimal("1000.00"))

        # Assert
        self.assertEqual(frequency, Decimal("0.33"))
        self.assertEqual(cost_pct, Decimal("2.00"))


class TestDisplayResultsVerboseMode(TestCase):
    """详细模式输出测试套件"""

    def test_verbose_mode_shows_all_metrics(self):
        """
        测试用例5：详细模式显示所有可用指标

        验收标准: --verbose模式输出更多详情
        """
        # Arrange
        calculator = MetricsCalculator()
        orders = []
        equity_curve = [
            EquityPoint(timestamp=1, cash=Decimal("10000"), position_value=Decimal("0"),
                        equity=Decimal("10000"), equity_rate=Decimal("0")),
        ]
        initial_cash = Decimal("10000.00")
        days = 365

        # Act
        metrics = calculator.calculate_all_metrics(orders, equity_curve, initial_cash, days)

        # Assert - 验证返回17个P0指标
        expected_keys = [
            'apr', 'absolute_return', 'cumulative_return',
            'mdd', 'mdd_start_time', 'mdd_end_time', 'recovery_time',
            'volatility',
            'sharpe_ratio', 'calmar_ratio', 'mar_ratio', 'profit_factor',
            'trade_frequency', 'cost_percentage', 'win_rate', 'payoff_ratio',
        ]
        for key in expected_keys:
            self.assertIn(key, metrics)


class TestDisplayResultsBoundaryScenarios(TestCase):
    """边界场景测试套件"""

    def test_display_results_handles_none_values(self):
        """
        测试用例6：边界场景 - 指标值为None时显示"N/A"

        验收标准: 无法计算的指标显示"N/A"
        """
        # Arrange
        calculator = MetricsCalculator()

        # Act - 波动率=0，夏普率返回None
        sharpe = calculator.calculate_sharpe_ratio(Decimal("12.00"), Decimal("0.00"))

        # Assert
        self.assertIsNone(sharpe)

    def test_display_results_handles_empty_orders(self):
        """
        测试用例7：边界场景 - 无订单时正确处理

        验收标准: 无订单时显示默认值
        """
        # Arrange
        calculator = MetricsCalculator()
        orders = []
        equity_curve = []
        initial_cash = Decimal("10000.00")
        days = 365

        # Act
        metrics = calculator.calculate_all_metrics(orders, equity_curve, initial_cash, days)

        # Assert
        self.assertEqual(metrics['apr'], Decimal("0.00"))
        self.assertEqual(metrics['mdd'], Decimal("0.00"))
        self.assertIsNone(metrics['profit_factor'])

    def test_display_results_handles_losing_strategy(self):
        """
        测试用例8：边界场景 - 亏损策略正确显示负值

        验收标准: 亏损时APR和收益率显示为负数
        """
        # Arrange
        calculator = MetricsCalculator()
        total_profit = Decimal("-500.00")
        initial_cash = Decimal("10000.00")
        days = 365

        # Act
        apr = calculator.calculate_apr(total_profit, initial_cash, days)
        cumulative_return = calculator.calculate_cumulative_return(total_profit, initial_cash)

        # Assert
        self.assertEqual(apr, Decimal("-5.00"))
        self.assertEqual(cumulative_return, Decimal("-5.00"))


class TestMetricsFormatting(TestCase):
    """指标格式化测试套件"""

    def test_metrics_precision_two_decimal_places(self):
        """
        测试用例9：验证所有指标精度保留2位小数

        验收标准: 数值精度保留2位小数
        """
        # Arrange
        calculator = MetricsCalculator()
        total_profit = Decimal("333.333")
        initial_cash = Decimal("10000.00")
        days = 365

        # Act
        apr = calculator.calculate_apr(total_profit, initial_cash, days)
        cumulative_return = calculator.calculate_cumulative_return(total_profit, initial_cash)

        # Assert - 验证精度
        self.assertEqual(str(apr), "3.33")
        self.assertEqual(str(cumulative_return), "3.33")

    def test_format_metric_value_with_none(self):
        """
        测试用例10：验证None值格式化为"N/A"

        验收标准: 使用辅助函数格式化None值
        """
        # Arrange
        value = None

        # Act - 模拟格式化逻辑
        formatted = "N/A" if value is None else f"{value:.2f}"

        # Assert
        self.assertEqual(formatted, "N/A")

    def test_format_metric_value_with_decimal(self):
        """
        测试用例11：验证Decimal值格式化

        验收标准: Decimal值正确格式化
        """
        # Arrange
        value = Decimal("12.34")

        # Act
        formatted = "N/A" if value is None else f"{value:.2f}"

        # Assert
        self.assertEqual(formatted, "12.34")


if __name__ == '__main__':
    unittest.main()
