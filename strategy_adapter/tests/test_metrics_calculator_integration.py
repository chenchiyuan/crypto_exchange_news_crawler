"""
测试文件：MetricsCalculator集成测试

Purpose:
    验证 MetricsCalculator.calculate_all_metrics() 方法的正确性

关联任务: TASK-014-008
关联需求: FP-014-001至FP-014-015（prd.md）
关联架构: architecture.md#4.2 MetricsCalculator

测试策略:
    - 集成测试
    - 覆盖正常场景、边界场景、异常场景
    - 验证所有17个P0指标的正确计算
"""

import unittest
from decimal import Decimal
from strategy_adapter.core.metrics_calculator import MetricsCalculator
from strategy_adapter.models.equity_point import EquityPoint
from strategy_adapter.models.order import Order, OrderStatus, OrderSide


class TestMetricsCalculatorIntegration(unittest.TestCase):
    """MetricsCalculator集成测试套件"""

    def test_calculate_all_metrics_standard_case(self):
        """
        测试用例1：标准场景 - 完整的订单和权益曲线

        验收标准: 返回包含17个P0指标的完整字典，所有指标计算正确
        """
        # Arrange
        calculator = MetricsCalculator(risk_free_rate=Decimal("0.03"))

        # 构建标准订单列表（4笔已平仓：2盈2亏）
        orders = [
            Order(
                id="ORDER-001",
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                status=OrderStatus.CLOSED,
                open_price=Decimal("47000.00"),
                open_timestamp=1640995200000,
                close_price=Decimal("48000.00"),
                close_timestamp=1641081600000,
                quantity=Decimal("1.0"),
                position_value=Decimal("100.00"),
                open_commission=Decimal("0.10"),
                close_commission=Decimal("0.10"),
                profit_loss=Decimal("99.80"),
                profit_loss_rate=Decimal("99.80")
            ),
            Order(
                id="ORDER-002",
                symbol="ETHUSDT",
                side=OrderSide.BUY,
                status=OrderStatus.CLOSED,
                open_price=Decimal("3000.00"),
                open_timestamp=1641081600000,
                close_price=Decimal("3200.00"),
                close_timestamp=1641168000000,
                quantity=Decimal("1.0"),
                position_value=Decimal("100.00"),
                open_commission=Decimal("0.10"),
                close_commission=Decimal("0.10"),
                profit_loss=Decimal("199.80"),
                profit_loss_rate=Decimal("199.80")
            ),
            Order(
                id="ORDER-003",
                symbol="BNBUSDT",
                side=OrderSide.BUY,
                status=OrderStatus.CLOSED,
                open_price=Decimal("400.00"),
                open_timestamp=1641168000000,
                close_price=Decimal("380.00"),
                close_timestamp=1641254400000,
                quantity=Decimal("1.0"),
                position_value=Decimal("100.00"),
                open_commission=Decimal("0.10"),
                close_commission=Decimal("0.10"),
                profit_loss=Decimal("-100.20"),
                profit_loss_rate=Decimal("-100.20")
            ),
            Order(
                id="ORDER-004",
                symbol="ADAUSDT",
                side=OrderSide.BUY,
                status=OrderStatus.CLOSED,
                open_price=Decimal("1.00"),
                open_timestamp=1641254400000,
                close_price=Decimal("0.95"),
                close_timestamp=1641340800000,
                quantity=Decimal("1.0"),
                position_value=Decimal("100.00"),
                open_commission=Decimal("0.10"),
                close_commission=Decimal("0.10"),
                profit_loss=Decimal("-50.20"),
                profit_loss_rate=Decimal("-50.20")
            ),
        ]

        # 构建权益曲线：10000 → 10100 → 10300 → 10200 → 10150
        equity_curve = [
            EquityPoint(timestamp=1640995200000, cash=Decimal("10000.00"), position_value=Decimal("0.00"), equity=Decimal("10000.00"), equity_rate=Decimal("0.00")),
            EquityPoint(timestamp=1641081600000, cash=Decimal("10100.00"), position_value=Decimal("0.00"), equity=Decimal("10100.00"), equity_rate=Decimal("1.00")),
            EquityPoint(timestamp=1641168000000, cash=Decimal("10300.00"), position_value=Decimal("0.00"), equity=Decimal("10300.00"), equity_rate=Decimal("3.00")),
            EquityPoint(timestamp=1641254400000, cash=Decimal("10200.00"), position_value=Decimal("0.00"), equity=Decimal("10200.00"), equity_rate=Decimal("2.00")),
            EquityPoint(timestamp=1641340800000, cash=Decimal("10150.00"), position_value=Decimal("0.00"), equity=Decimal("10150.00"), equity_rate=Decimal("1.50")),
        ]

        initial_cash = Decimal("10000.00")
        days = 365

        # Act
        metrics = calculator.calculate_all_metrics(orders, equity_curve, initial_cash, days)

        # Assert: 验证返回字典包含所有17个P0指标
        expected_keys = {
            # 收益分析（3个）
            'apr', 'absolute_return', 'cumulative_return',
            # 风险分析（4个）
            'mdd', 'mdd_start_time', 'mdd_end_time', 'recovery_time',
            # 波动率
            'volatility',
            # 风险调整收益（4个）
            'sharpe_ratio', 'calmar_ratio', 'mar_ratio', 'profit_factor',
            # 交易效率（4个）
            'trade_frequency', 'cost_percentage', 'win_rate', 'payoff_ratio',
        }
        self.assertEqual(set(metrics.keys()), expected_keys)

        # 验证收益指标
        # total_profit = 99.80 + 199.80 - 100.20 - 50.20 = 149.20
        self.assertEqual(metrics['absolute_return'], Decimal("149.20"))
        self.assertEqual(metrics['cumulative_return'], Decimal("1.49"))  # 149.20/10000*100
        self.assertEqual(metrics['apr'], Decimal("1.49"))  # (149.20/10000)*(365/365)*100

        # 验证风险指标（MDD从10300跌到10150）
        self.assertEqual(metrics['mdd'], Decimal("-1.46"))  # (10150-10300)/10300*100
        self.assertIsNotNone(metrics['mdd_start_time'])
        self.assertIsNotNone(metrics['mdd_end_time'])

        # 验证波动率（应大于0）
        self.assertIsInstance(metrics['volatility'], Decimal)
        self.assertGreater(metrics['volatility'], Decimal("0.00"))

        # 验证风险调整收益指标
        self.assertIsInstance(metrics['sharpe_ratio'], Decimal)
        self.assertIsInstance(metrics['calmar_ratio'], Decimal)
        self.assertIsInstance(metrics['mar_ratio'], Decimal)
        self.assertIsInstance(metrics['profit_factor'], Decimal)

        # 验证交易效率指标
        self.assertEqual(metrics['trade_frequency'], Decimal("0.01"))  # 4/365
        self.assertIsInstance(metrics['cost_percentage'], Decimal)
        self.assertEqual(metrics['win_rate'], Decimal("50.00"))  # 2/4*100
        self.assertIsInstance(metrics['payoff_ratio'], Decimal)

    def test_calculate_all_metrics_no_closed_orders(self):
        """
        测试用例2：边界场景 - 无已平仓订单

        验收标准: 返回默认值（MDD=0, 夏普率=None等）
        """
        # Arrange
        calculator = MetricsCalculator()

        # 空订单列表
        orders = []
        equity_curve = [
            EquityPoint(timestamp=1640995200000, cash=Decimal("10000.00"), position_value=Decimal("0.00"), equity=Decimal("10000.00"), equity_rate=Decimal("0.00")),
        ]
        initial_cash = Decimal("10000.00")
        days = 365

        # Act
        metrics = calculator.calculate_all_metrics(orders, equity_curve, initial_cash, days)

        # Assert: 验证默认值
        self.assertEqual(metrics['absolute_return'], Decimal("0.00"))
        self.assertEqual(metrics['cumulative_return'], Decimal("0.00"))
        self.assertEqual(metrics['apr'], Decimal("0.00"))
        self.assertEqual(metrics['mdd'], Decimal("0.00"))
        self.assertEqual(metrics['volatility'], Decimal("0.00"))
        self.assertIsNone(metrics['sharpe_ratio'])  # 波动率=0，无法计算
        self.assertIsNone(metrics['calmar_ratio'])  # MDD=0，无法计算
        self.assertIsNone(metrics['mar_ratio'])  # MDD=0，无法计算
        self.assertEqual(metrics['trade_frequency'], Decimal("0.00"))  # 0/365
        self.assertIsNone(metrics['cost_percentage'])  # total_profit=0，无法计算
        self.assertEqual(metrics['win_rate'], Decimal("0.00"))

    def test_calculate_all_metrics_zero_volatility(self):
        """
        测试用例3：边界场景 - 波动率=0（所有权益点相同）

        验收标准: 夏普率返回None（优雅降级）
        """
        # Arrange
        calculator = MetricsCalculator()

        # 1笔盈利订单
        orders = [
            Order(
                id="ORDER-001",
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                status=OrderStatus.CLOSED,
                open_price=Decimal("47000.00"),
                open_timestamp=1640995200000,
                close_price=Decimal("48000.00"),
                close_timestamp=1641081600000,
                quantity=Decimal("1.0"),
                position_value=Decimal("100.00"),
                open_commission=Decimal("0.00"),
                close_commission=Decimal("0.00"),
                profit_loss=Decimal("100.00"),
                profit_loss_rate=Decimal("100.00")
            ),
        ]

        # 权益曲线无波动：10000 → 10000 → 10000
        equity_curve = [
            EquityPoint(timestamp=1640995200000, cash=Decimal("10000.00"), position_value=Decimal("0.00"), equity=Decimal("10000.00"), equity_rate=Decimal("0.00")),
            EquityPoint(timestamp=1641081600000, cash=Decimal("10000.00"), position_value=Decimal("0.00"), equity=Decimal("10000.00"), equity_rate=Decimal("0.00")),
            EquityPoint(timestamp=1641168000000, cash=Decimal("10000.00"), position_value=Decimal("0.00"), equity=Decimal("10000.00"), equity_rate=Decimal("0.00")),
        ]

        initial_cash = Decimal("10000.00")
        days = 365

        # Act
        metrics = calculator.calculate_all_metrics(orders, equity_curve, initial_cash, days)

        # Assert: 验证波动率=0，夏普率=None
        self.assertEqual(metrics['volatility'], Decimal("0.00"))
        self.assertIsNone(metrics['sharpe_ratio'])  # 除零保护

    def test_calculate_all_metrics_zero_mdd(self):
        """
        测试用例4：边界场景 - MDD=0（无回撤）

        验收标准: Calmar和MAR比率返回None（优雅降级）
        """
        # Arrange
        calculator = MetricsCalculator()

        # 1笔盈利订单
        orders = [
            Order(
                id="ORDER-001",
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                status=OrderStatus.CLOSED,
                open_price=Decimal("47000.00"),
                open_timestamp=1640995200000,
                close_price=Decimal("48000.00"),
                close_timestamp=1641081600000,
                quantity=Decimal("1.0"),
                position_value=Decimal("100.00"),
                open_commission=Decimal("0.00"),
                close_commission=Decimal("0.00"),
                profit_loss=Decimal("100.00"),
                profit_loss_rate=Decimal("100.00")
            ),
        ]

        # 权益曲线无回撤：10000 → 11000 → 12000
        equity_curve = [
            EquityPoint(timestamp=1640995200000, cash=Decimal("10000.00"), position_value=Decimal("0.00"), equity=Decimal("10000.00"), equity_rate=Decimal("0.00")),
            EquityPoint(timestamp=1641081600000, cash=Decimal("11000.00"), position_value=Decimal("0.00"), equity=Decimal("11000.00"), equity_rate=Decimal("10.00")),
            EquityPoint(timestamp=1641168000000, cash=Decimal("12000.00"), position_value=Decimal("0.00"), equity=Decimal("12000.00"), equity_rate=Decimal("20.00")),
        ]

        initial_cash = Decimal("10000.00")
        days = 365

        # Act
        metrics = calculator.calculate_all_metrics(orders, equity_curve, initial_cash, days)

        # Assert: 验证MDD=0，Calmar和MAR比率=None
        self.assertEqual(metrics['mdd'], Decimal("0.00"))
        self.assertIsNone(metrics['calmar_ratio'])  # 除零保护
        self.assertIsNone(metrics['mar_ratio'])  # 除零保护

    # === 异常场景测试 ===

    def test_calculate_all_metrics_invalid_initial_cash_raises_valueerror(self):
        """
        测试用例5：异常场景 - initial_cash <= 0

        验收标准: 立即抛出ValueError
        """
        # Arrange
        calculator = MetricsCalculator()
        orders = []
        equity_curve = []
        invalid_initial_cash = Decimal("0.00")
        days = 365

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            calculator.calculate_all_metrics(orders, equity_curve, invalid_initial_cash, days)

        self.assertIn("initial_cash必须大于0", str(context.exception))

    def test_calculate_all_metrics_invalid_days_raises_valueerror(self):
        """
        测试用例6：异常场景 - days <= 0

        验收标准: 立即抛出ValueError
        """
        # Arrange
        calculator = MetricsCalculator()
        orders = []
        equity_curve = []
        initial_cash = Decimal("10000.00")
        invalid_days = 0

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            calculator.calculate_all_metrics(orders, equity_curve, initial_cash, invalid_days)

        self.assertIn("days必须大于0", str(context.exception))


if __name__ == '__main__':
    unittest.main()
