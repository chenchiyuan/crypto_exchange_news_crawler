"""
测试文件：交易效率指标计算测试

Purpose:
    验证 MetricsCalculator 的交易效率指标计算方法的正确性

关联任务: TASK-014-007
关联需求: FP-014-012, FP-014-013, FP-014-015（prd.md）
关联架构: architecture.md#4.2 MetricsCalculator

测试策略:
    - 单元测试
    - 覆盖正常场景、边界场景、异常场景
    - Fail-Fast: days <=  0时抛出异常
    - 优雅降级：除零时返回None
"""

import unittest
from decimal import Decimal
from strategy_adapter.core.metrics_calculator import MetricsCalculator
from strategy_adapter.models.order import Order, OrderStatus, OrderSide


class TestTradeFrequencyCalculation(unittest.TestCase):
    """交易频率计算测试套件"""

    def test_trade_frequency_standard_case(self):
        """
        测试用例1：标准场景 - 365天120笔交易

        验收标准: 交易频率 = 120 / 365 = 0.33次/天
        """
        # Arrange
        calculator = MetricsCalculator()
        total_orders = 120
        days = 365

        # Act
        frequency = calculator.calculate_trade_frequency(total_orders, days)

        # Assert
        expected_frequency = Decimal("0.33")
        self.assertEqual(frequency, expected_frequency)

    def test_trade_frequency_high_frequency_trading(self):
        """
        测试用例2：高频交易场景 - 30天300笔

        验收标准: 交易频率 = 300 / 30 = 10.00次/天
        """
        # Arrange
        calculator = MetricsCalculator()
        total_orders = 300
        days = 30

        # Act
        frequency = calculator.calculate_trade_frequency(total_orders, days)

        # Assert
        expected_frequency = Decimal("10.00")
        self.assertEqual(frequency, expected_frequency)

    def test_trade_frequency_zero_orders(self):
        """
        测试用例3：边界场景 - 无交易

        验收标准: 交易频率 = 0 / 365 = 0.00次/天
        """
        # Arrange
        calculator = MetricsCalculator()
        total_orders = 0
        days = 365

        # Act
        frequency = calculator.calculate_trade_frequency(total_orders, days)

        # Assert
        self.assertEqual(frequency, Decimal("0.00"))

    # === Fail-Fast 异常测试 ===

    def test_trade_frequency_zero_days_raises_valueerror(self):
        """
        测试用例4：Fail-Fast验证 - days=0时抛出ValueError

        验收标准: 立即抛出异常
        """
        # Arrange
        calculator = MetricsCalculator()
        total_orders = 100
        invalid_days = 0

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            calculator.calculate_trade_frequency(total_orders, invalid_days)

        self.assertIn("days必须大于0", str(context.exception))

    def test_trade_frequency_negative_days_raises_valueerror(self):
        """
        测试用例5：Fail-Fast验证 - 负数days抛出ValueError

        验收标准: 立即抛出异常
        """
        # Arrange
        calculator = MetricsCalculator()
        total_orders = 100
        invalid_days = -365

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            calculator.calculate_trade_frequency(total_orders, invalid_days)

        self.assertIn("days必须大于0", str(context.exception))


class TestCostPercentageCalculation(unittest.TestCase):
    """成本占比计算测试套件"""

    def test_cost_percentage_standard_case(self):
        """
        测试用例6：标准场景 - 收益1000，手续费20

        验收标准: Cost % = 20 / 1000 × 100% = 2.00%
        """
        # Arrange
        calculator = MetricsCalculator()
        total_commission = Decimal("20.00")
        total_profit = Decimal("1000.00")

        # Act
        cost_pct = calculator.calculate_cost_percentage(total_commission, total_profit)

        # Assert
        expected_cost_pct = Decimal("2.00")
        self.assertEqual(cost_pct, expected_cost_pct)

    def test_cost_percentage_low_cost(self):
        """
        测试用例7：低成本场景 - 收益5000，手续费25

        验收标准: Cost % = 25 / 5000 × 100% = 0.50%
        """
        # Arrange
        calculator = MetricsCalculator()
        total_commission = Decimal("25.00")
        total_profit = Decimal("5000.00")

        # Act
        cost_pct = calculator.calculate_cost_percentage(total_commission, total_profit)

        # Assert
        expected_cost_pct = Decimal("0.50")
        self.assertEqual(cost_pct, expected_cost_pct)

    def test_cost_percentage_high_cost(self):
        """
        测试用例8：高成本场景 - 收益1000，手续费100

        验收标准: Cost % = 100 / 1000 × 100% = 10.00%
        """
        # Arrange
        calculator = MetricsCalculator()
        total_commission = Decimal("100.00")
        total_profit = Decimal("1000.00")

        # Act
        cost_pct = calculator.calculate_cost_percentage(total_commission, total_profit)

        # Assert
        expected_cost_pct = Decimal("10.00")
        self.assertEqual(cost_pct, expected_cost_pct)

    # === 除零保护测试 ===

    def test_cost_percentage_zero_profit_returns_none(self):
        """
        测试用例9：除零保护 - total_profit=0时返回None

        验收标准: 优雅降级，返回None
        """
        # Arrange
        calculator = MetricsCalculator()
        total_commission = Decimal("20.00")
        total_profit = Decimal("0.00")

        # Act
        cost_pct = calculator.calculate_cost_percentage(total_commission, total_profit)

        # Assert
        self.assertIsNone(cost_pct)


class TestPayoffRatioCalculation(unittest.TestCase):
    """盈亏比计算测试套件"""

    def test_payoff_ratio_standard_case(self):
        """
        测试用例10：标准场景 - 平均盈利100，平均亏损50

        验收标准: Payoff = 100 / 50 = 2.00
        """
        # Arrange
        calculator = MetricsCalculator()

        # 2笔盈利，平均100；2笔亏损，平均50
        orders = [
            Order(
                id="WIN-001",
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                status=OrderStatus.CLOSED,
                open_price=Decimal("47000.00"),
                open_timestamp=1640995200000,
                close_price=Decimal("47100.00"),
                close_timestamp=1641081600000,
                quantity=Decimal("1.0"),
                position_value=Decimal("47000.00"),
                open_commission=Decimal("0.00"),
                close_commission=Decimal("0.00"),
                profit_loss=Decimal("100.00"),
                profit_loss_rate=Decimal("0.21")
            ),
            Order(
                id="WIN-002",
                symbol="ETHUSDT",
                side=OrderSide.BUY,
                status=OrderStatus.CLOSED,
                open_price=Decimal("3000.00"),
                open_timestamp=1640995200000,
                close_price=Decimal("3100.00"),
                close_timestamp=1641081600000,
                quantity=Decimal("1.0"),
                position_value=Decimal("3000.00"),
                open_commission=Decimal("0.00"),
                close_commission=Decimal("0.00"),
                profit_loss=Decimal("100.00"),
                profit_loss_rate=Decimal("3.33")
            ),
            Order(
                id="LOSS-001",
                symbol="BNBUSDT",
                side=OrderSide.BUY,
                status=OrderStatus.CLOSED,
                open_price=Decimal("400.00"),
                open_timestamp=1640995200000,
                close_price=Decimal("350.00"),
                close_timestamp=1641081600000,
                quantity=Decimal("1.0"),
                position_value=Decimal("400.00"),
                open_commission=Decimal("0.00"),
                close_commission=Decimal("0.00"),
                profit_loss=Decimal("-50.00"),
                profit_loss_rate=Decimal("-12.50")
            ),
            Order(
                id="LOSS-002",
                symbol="ADAUSDT",
                side=OrderSide.BUY,
                status=OrderStatus.CLOSED,
                open_price=Decimal("1.00"),
                open_timestamp=1640995200000,
                close_price=Decimal("0.95"),
                close_timestamp=1641081600000,
                quantity=Decimal("1000.0"),
                position_value=Decimal("1000.00"),
                open_commission=Decimal("0.00"),
                close_commission=Decimal("0.00"),
                profit_loss=Decimal("-50.00"),
                profit_loss_rate=Decimal("-5.00")
            ),
        ]

        # Act
        payoff_ratio = calculator.calculate_payoff_ratio(orders)

        # Assert
        # 平均盈利 = (100+100) / 2 = 100
        # 平均亏损 = -(50+50) / 2 = -50
        # Payoff = 100 / 50 = 2.00
        expected_payoff = Decimal("2.00")
        self.assertEqual(payoff_ratio, expected_payoff)

    def test_payoff_ratio_high_payoff(self):
        """
        测试用例11：高盈亏比场景 - 平均盈利300，平均亏损100

        验收标准: Payoff = 300 / 100 = 3.00
        """
        # Arrange
        calculator = MetricsCalculator()

        orders = [
            Order(
                id="WIN-001",
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                status=OrderStatus.CLOSED,
                open_price=Decimal("47000.00"),
                open_timestamp=1640995200000,
                close_price=Decimal("47300.00"),
                close_timestamp=1641081600000,
                quantity=Decimal("1.0"),
                position_value=Decimal("47000.00"),
                open_commission=Decimal("0.00"),
                close_commission=Decimal("0.00"),
                profit_loss=Decimal("300.00"),
                profit_loss_rate=Decimal("0.64")
            ),
            Order(
                id="LOSS-001",
                symbol="ETHUSDT",
                side=OrderSide.BUY,
                status=OrderStatus.CLOSED,
                open_price=Decimal("3000.00"),
                open_timestamp=1640995200000,
                close_price=Decimal("2900.00"),
                close_timestamp=1641081600000,
                quantity=Decimal("1.0"),
                position_value=Decimal("3000.00"),
                open_commission=Decimal("0.00"),
                close_commission=Decimal("0.00"),
                profit_loss=Decimal("-100.00"),
                profit_loss_rate=Decimal("-3.33")
            ),
        ]

        # Act
        payoff_ratio = calculator.calculate_payoff_ratio(orders)

        # Assert
        expected_payoff = Decimal("3.00")
        self.assertEqual(payoff_ratio, expected_payoff)

    # === 除零保护测试 ===

    def test_payoff_ratio_no_losing_orders_returns_none(self):
        """
        测试用例12：除零保护 - 无亏损订单时返回None

        验收标准: 优雅降级，返回None
        """
        # Arrange
        calculator = MetricsCalculator()

        # 所有订单都盈利
        orders = [
            Order(
                id="WIN-001",
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                status=OrderStatus.CLOSED,
                open_price=Decimal("47000.00"),
                open_timestamp=1640995200000,
                close_price=Decimal("48000.00"),
                close_timestamp=1641081600000,
                quantity=Decimal("1.0"),
                position_value=Decimal("47000.00"),
                open_commission=Decimal("0.00"),
                close_commission=Decimal("0.00"),
                profit_loss=Decimal("1000.00"),
                profit_loss_rate=Decimal("2.13")
            ),
        ]

        # Act
        payoff_ratio = calculator.calculate_payoff_ratio(orders)

        # Assert
        self.assertIsNone(payoff_ratio)

    def test_payoff_ratio_empty_orders_returns_none(self):
        """
        测试用例13：边界场景 - 空订单列表返回None

        验收标准: 优雅降级，返回None
        """
        # Arrange
        calculator = MetricsCalculator()
        orders = []

        # Act
        payoff_ratio = calculator.calculate_payoff_ratio(orders)

        # Assert
        self.assertIsNone(payoff_ratio)


if __name__ == '__main__':
    unittest.main()
