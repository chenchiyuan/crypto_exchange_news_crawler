"""
测试文件：风险调整收益指标计算测试

Purpose:
    验证 MetricsCalculator 的风险调整收益指标计算方法的正确性

关联任务: TASK-014-006
关联需求: FP-014-008, FP-014-009, FP-014-010, FP-014-011（prd.md）
关联架构: architecture.md#4.2 MetricsCalculator

测试策略:
    - 单元测试
    - 覆盖正常场景、异常场景（除零保护）
    - 优雅降级：除零时返回None，不抛出异常
"""

import unittest
from decimal import Decimal
from strategy_adapter.core.metrics_calculator import MetricsCalculator
from strategy_adapter.models.order import Order, OrderStatus, OrderSide


class TestSharpeRatioCalculation(unittest.TestCase):
    """夏普率计算测试套件"""

    def test_sharpe_ratio_standard_case(self):
        """
        测试用例1：标准场景 - APR=12%, 波动率=15%, risk_free_rate=3%

        验收标准: Sharpe = (APR - risk_free_rate) / Volatility = (12-3) / 15 = 0.60
        """
        # Arrange
        calculator = MetricsCalculator(risk_free_rate=Decimal("0.03"))
        apr = Decimal("12.00")  # 12%
        volatility = Decimal("15.00")  # 15%

        # Act
        sharpe = calculator.calculate_sharpe_ratio(apr, volatility)

        # Assert
        expected_sharpe = Decimal("0.60")
        self.assertEqual(sharpe, expected_sharpe)

    def test_sharpe_ratio_high_risk_high_return(self):
        """
        测试用例2：高风险高收益场景 - APR=30%, 波动率=25%

        验收标准: Sharpe = (30-3) / 25 = 1.08
        """
        # Arrange
        calculator = MetricsCalculator(risk_free_rate=Decimal("0.03"))
        apr = Decimal("30.00")
        volatility = Decimal("25.00")

        # Act
        sharpe = calculator.calculate_sharpe_ratio(apr, volatility)

        # Assert
        expected_sharpe = Decimal("1.08")
        self.assertEqual(sharpe, expected_sharpe)

    def test_sharpe_ratio_negative_excess_return(self):
        """
        测试用例3：负超额收益场景 - APR=2%, 低于无风险收益率3%

        验收标准: Sharpe = (2-3) / 10 = -0.10（负夏普率）
        """
        # Arrange
        calculator = MetricsCalculator(risk_free_rate=Decimal("0.03"))
        apr = Decimal("2.00")
        volatility = Decimal("10.00")

        # Act
        sharpe = calculator.calculate_sharpe_ratio(apr, volatility)

        # Assert
        expected_sharpe = Decimal("-0.10")
        self.assertEqual(sharpe, expected_sharpe)

    # === 除零保护测试 ===

    def test_sharpe_ratio_zero_volatility_returns_none(self):
        """
        测试用例4：除零保护 - 波动率=0时返回None

        验收标准: 优雅降级，返回None而非抛出异常
        """
        # Arrange
        calculator = MetricsCalculator(risk_free_rate=Decimal("0.03"))
        apr = Decimal("12.00")
        volatility = Decimal("0.00")

        # Act
        sharpe = calculator.calculate_sharpe_ratio(apr, volatility)

        # Assert
        self.assertIsNone(sharpe)


class TestCalmarRatioCalculation(unittest.TestCase):
    """卡玛比率计算测试套件"""

    def test_calmar_ratio_standard_case(self):
        """
        测试用例5：标准场景 - APR=12%, MDD=-10%

        验收标准: Calmar = APR / abs(MDD) = 12 / 10 = 1.20
        """
        # Arrange
        calculator = MetricsCalculator()
        apr = Decimal("12.00")
        mdd = Decimal("-10.00")

        # Act
        calmar = calculator.calculate_calmar_ratio(apr, mdd)

        # Assert
        expected_calmar = Decimal("1.20")
        self.assertEqual(calmar, expected_calmar)

    def test_calmar_ratio_high_drawdown(self):
        """
        测试用例6：大回撤场景 - APR=15%, MDD=-25%

        验收标准: Calmar = 15 / 25 = 0.60
        """
        # Arrange
        calculator = MetricsCalculator()
        apr = Decimal("15.00")
        mdd = Decimal("-25.00")

        # Act
        calmar = calculator.calculate_calmar_ratio(apr, mdd)

        # Assert
        expected_calmar = Decimal("0.60")
        self.assertEqual(calmar, expected_calmar)

    def test_calmar_ratio_negative_apr(self):
        """
        测试用例7：负收益场景 - APR=-5%, MDD=-10%

        验收标准: Calmar = -5 / 10 = -0.50（负卡玛比率）
        """
        # Arrange
        calculator = MetricsCalculator()
        apr = Decimal("-5.00")
        mdd = Decimal("-10.00")

        # Act
        calmar = calculator.calculate_calmar_ratio(apr, mdd)

        # Assert
        expected_calmar = Decimal("-0.50")
        self.assertEqual(calmar, expected_calmar)

    # === 除零保护测试 ===

    def test_calmar_ratio_zero_mdd_returns_none(self):
        """
        测试用例8：除零保护 - MDD=0时返回None

        验收标准: 优雅降级，返回None
        """
        # Arrange
        calculator = MetricsCalculator()
        apr = Decimal("12.00")
        mdd = Decimal("0.00")

        # Act
        calmar = calculator.calculate_calmar_ratio(apr, mdd)

        # Assert
        self.assertIsNone(calmar)


class TestMARRatioCalculation(unittest.TestCase):
    """MAR比率计算测试套件"""

    def test_mar_ratio_standard_case(self):
        """
        测试用例9：标准场景 - 累计收益率=20%, MDD=-15%

        验收标准: MAR = 20 / 15 = 1.33
        """
        # Arrange
        calculator = MetricsCalculator()
        cumulative_return = Decimal("20.00")
        mdd = Decimal("-15.00")

        # Act
        mar = calculator.calculate_mar_ratio(cumulative_return, mdd)

        # Assert
        expected_mar = Decimal("1.33")
        self.assertEqual(mar, expected_mar)

    def test_mar_ratio_low_drawdown(self):
        """
        测试用例10：低回撤场景 - 累计收益率=30%, MDD=-5%

        验收标准: MAR = 30 / 5 = 6.00
        """
        # Arrange
        calculator = MetricsCalculator()
        cumulative_return = Decimal("30.00")
        mdd = Decimal("-5.00")

        # Act
        mar = calculator.calculate_mar_ratio(cumulative_return, mdd)

        # Assert
        expected_mar = Decimal("6.00")
        self.assertEqual(mar, expected_mar)

    # === 除零保护测试 ===

    def test_mar_ratio_zero_mdd_returns_none(self):
        """
        测试用例11：除零保护 - MDD=0时返回None

        验收标准: 优雅降级，返回None
        """
        # Arrange
        calculator = MetricsCalculator()
        cumulative_return = Decimal("20.00")
        mdd = Decimal("0.00")

        # Act
        mar = calculator.calculate_mar_ratio(cumulative_return, mdd)

        # Assert
        self.assertIsNone(mar)


class TestProfitFactorCalculation(unittest.TestCase):
    """盈利因子计算测试套件"""

    def test_profit_factor_standard_case(self):
        """
        测试用例12：标准场景 - 总盈利2000，总亏损1000

        验收标准: Profit Factor = 2000 / 1000 = 2.00
        """
        # Arrange
        calculator = MetricsCalculator()

        # 创建订单列表：2笔盈利，1笔亏损
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
                open_commission=Decimal("47.00"),
                close_commission=Decimal("48.00"),
                profit_loss=Decimal("905.00"),  # 盈利
                profit_loss_rate=Decimal("1.93")
            ),
            Order(
                id="WIN-002",
                symbol="ETHUSDT",
                side=OrderSide.BUY,
                status=OrderStatus.CLOSED,
                open_price=Decimal("3000.00"),
                open_timestamp=1640995200000,
                close_price=Decimal("3200.00"),
                close_timestamp=1641081600000,
                quantity=Decimal("5.0"),
                position_value=Decimal("15000.00"),
                open_commission=Decimal("15.00"),
                close_commission=Decimal("16.00"),
                profit_loss=Decimal("969.00"),  # 盈利
                profit_loss_rate=Decimal("6.46")
            ),
            Order(
                id="LOSS-001",
                symbol="BNBUSDT",
                side=OrderSide.BUY,
                status=OrderStatus.CLOSED,
                open_price=Decimal("400.00"),
                open_timestamp=1640995200000,
                close_price=Decimal("380.00"),
                close_timestamp=1641081600000,
                quantity=Decimal("10.0"),
                position_value=Decimal("4000.00"),
                open_commission=Decimal("4.00"),
                close_commission=Decimal("3.80"),
                profit_loss=Decimal("-207.80"),  # 亏损
                profit_loss_rate=Decimal("-5.20")
            ),
        ]

        # Act
        profit_factor = calculator.calculate_profit_factor(orders)

        # Assert
        # 总盈利 = 905 + 969 = 1874
        # 总亏损 = -207.80
        # PF = 1874 / 207.80 ≈ 9.01
        self.assertGreater(profit_factor, Decimal("9.00"))
        self.assertLess(profit_factor, Decimal("9.10"))

    def test_profit_factor_balanced_case(self):
        """
        测试用例13：均衡场景 - 盈亏相等

        验收标准: Profit Factor = 1.00
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
                close_price=Decimal("48000.00"),
                close_timestamp=1641081600000,
                quantity=Decimal("1.0"),
                position_value=Decimal("47000.00"),
                open_commission=Decimal("0.00"),
                close_commission=Decimal("0.00"),
                profit_loss=Decimal("1000.00"),
                profit_loss_rate=Decimal("2.13")
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
                quantity=Decimal("10.0"),
                position_value=Decimal("30000.00"),
                open_commission=Decimal("0.00"),
                close_commission=Decimal("0.00"),
                profit_loss=Decimal("-1000.00"),
                profit_loss_rate=Decimal("-3.33")
            ),
        ]

        # Act
        profit_factor = calculator.calculate_profit_factor(orders)

        # Assert
        self.assertEqual(profit_factor, Decimal("1.00"))

    # === 除零保护测试 ===

    def test_profit_factor_no_losing_orders_returns_none(self):
        """
        测试用例14：除零保护 - 无亏损订单时返回None

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
        profit_factor = calculator.calculate_profit_factor(orders)

        # Assert
        self.assertIsNone(profit_factor)

    def test_profit_factor_empty_orders_returns_none(self):
        """
        测试用例15：边界场景 - 空订单列表返回None

        验收标准: 优雅降级，返回None
        """
        # Arrange
        calculator = MetricsCalculator()
        orders = []

        # Act
        profit_factor = calculator.calculate_profit_factor(orders)

        # Assert
        self.assertIsNone(profit_factor)


if __name__ == '__main__':
    unittest.main()
