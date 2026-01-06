"""
测试文件：风险指标计算测试

Purpose:
    验证 MetricsCalculator 的风险指标计算方法的正确性（MDD、波动率）

关联任务: TASK-014-005
关联需求: FP-014-005, FP-014-006, FP-014-007（prd.md）
关联架构: architecture.md#4.2 MetricsCalculator

测试策略:
    - 单元测试
    - 覆盖正常场景、边界场景、异常场景
    - 优雅降级：空权益曲线返回默认值，不抛出异常
"""

import unittest
from decimal import Decimal
from strategy_adapter.core.metrics_calculator import MetricsCalculator
from strategy_adapter.models.equity_point import EquityPoint


class TestMDDCalculation(unittest.TestCase):
    """MDD（最大回撤）计算测试套件"""

    def test_mdd_calculation_standard_drawdown(self):
        """
        测试用例1：标准回撤场景 - 从10000跌到9000

        验收标准: MDD = -10.00%，正确识别回撤开始和结束时间
        """
        # Arrange
        calculator = MetricsCalculator()

        # 构建权益曲线：10000 → 11000 → 9000 → 10500
        equity_curve = [
            EquityPoint(
                timestamp=1640995200000,
                cash=Decimal("10000.00"),
                position_value=Decimal("0.00"),
                equity=Decimal("10000.00"),
                equity_rate=Decimal("0.00")
            ),
            EquityPoint(
                timestamp=1641081600000,
                cash=Decimal("11000.00"),
                position_value=Decimal("0.00"),
                equity=Decimal("11000.00"),
                equity_rate=Decimal("10.00")
            ),
            EquityPoint(
                timestamp=1641168000000,
                cash=Decimal("9000.00"),
                position_value=Decimal("0.00"),
                equity=Decimal("9000.00"),
                equity_rate=Decimal("-10.00")
            ),
            EquityPoint(
                timestamp=1641254400000,
                cash=Decimal("10500.00"),
                position_value=Decimal("0.00"),
                equity=Decimal("10500.00"),
                equity_rate=Decimal("5.00")
            ),
        ]

        # Act
        mdd_result = calculator.calculate_mdd(equity_curve)

        # Assert
        self.assertEqual(mdd_result['mdd'], Decimal("-18.18"))  # (9000-11000)/11000 = -18.18%
        self.assertEqual(mdd_result['mdd_start_time'], 1641081600000)  # 峰值时间
        self.assertEqual(mdd_result['mdd_end_time'], 1641168000000)  # 谷底时间
        self.assertIsNone(mdd_result['recovery_time'])  # 未恢复（10500 < 11000）

    def test_mdd_calculation_no_drawdown(self):
        """
        测试用例2：无回撤场景 - 持续盈利

        验收标准: MDD = 0.00%
        """
        # Arrange
        calculator = MetricsCalculator()

        # 构建权益曲线：10000 → 11000 → 12000 → 13000
        equity_curve = [
            EquityPoint(
                timestamp=1640995200000,
                cash=Decimal("10000.00"),
                position_value=Decimal("0.00"),
                equity=Decimal("10000.00"),
                equity_rate=Decimal("0.00")
            ),
            EquityPoint(
                timestamp=1641081600000,
                cash=Decimal("11000.00"),
                position_value=Decimal("0.00"),
                equity=Decimal("11000.00"),
                equity_rate=Decimal("10.00")
            ),
            EquityPoint(
                timestamp=1641168000000,
                cash=Decimal("12000.00"),
                position_value=Decimal("0.00"),
                equity=Decimal("12000.00"),
                equity_rate=Decimal("20.00")
            ),
        ]

        # Act
        mdd_result = calculator.calculate_mdd(equity_curve)

        # Assert
        self.assertEqual(mdd_result['mdd'], Decimal("0.00"))
        self.assertIsNone(mdd_result['mdd_start_time'])
        self.assertIsNone(mdd_result['mdd_end_time'])
        self.assertIsNone(mdd_result['recovery_time'])

    def test_mdd_calculation_recovered(self):
        """
        测试用例2.5：已恢复场景 - 回撤后完全恢复到峰值

        验收标准: recovery_time 正确识别恢复时间
        """
        # Arrange
        calculator = MetricsCalculator()

        # 构建权益曲线：10000 → 11000 → 9000 → 11000（完全恢复）
        equity_curve = [
            EquityPoint(
                timestamp=1640995200000,
                cash=Decimal("10000.00"),
                position_value=Decimal("0.00"),
                equity=Decimal("10000.00"),
                equity_rate=Decimal("0.00")
            ),
            EquityPoint(
                timestamp=1641081600000,
                cash=Decimal("11000.00"),
                position_value=Decimal("0.00"),
                equity=Decimal("11000.00"),
                equity_rate=Decimal("10.00")
            ),
            EquityPoint(
                timestamp=1641168000000,
                cash=Decimal("9000.00"),
                position_value=Decimal("0.00"),
                equity=Decimal("9000.00"),
                equity_rate=Decimal("-10.00")
            ),
            EquityPoint(
                timestamp=1641254400000,
                cash=Decimal("11000.00"),
                position_value=Decimal("0.00"),
                equity=Decimal("11000.00"),
                equity_rate=Decimal("10.00")
            ),
        ]

        # Act
        mdd_result = calculator.calculate_mdd(equity_curve)

        # Assert
        self.assertEqual(mdd_result['mdd'], Decimal("-18.18"))
        self.assertEqual(mdd_result['mdd_start_time'], 1641081600000)
        self.assertEqual(mdd_result['mdd_end_time'], 1641168000000)
        self.assertEqual(mdd_result['recovery_time'], 1641254400000)  # 恢复到11000

    def test_mdd_calculation_not_recovered(self):
        """
        测试用例3：未恢复场景 - 回撤后未回到峰值

        验收标准: recovery_time = None
        """
        # Arrange
        calculator = MetricsCalculator()

        # 构建权益曲线：10000 → 11000 → 9000 → 9500（未恢复到11000）
        equity_curve = [
            EquityPoint(
                timestamp=1640995200000,
                cash=Decimal("10000.00"),
                position_value=Decimal("0.00"),
                equity=Decimal("10000.00"),
                equity_rate=Decimal("0.00")
            ),
            EquityPoint(
                timestamp=1641081600000,
                cash=Decimal("11000.00"),
                position_value=Decimal("0.00"),
                equity=Decimal("11000.00"),
                equity_rate=Decimal("10.00")
            ),
            EquityPoint(
                timestamp=1641168000000,
                cash=Decimal("9000.00"),
                position_value=Decimal("0.00"),
                equity=Decimal("9000.00"),
                equity_rate=Decimal("-10.00")
            ),
            EquityPoint(
                timestamp=1641254400000,
                cash=Decimal("9500.00"),
                position_value=Decimal("0.00"),
                equity=Decimal("9500.00"),
                equity_rate=Decimal("-5.00")
            ),
        ]

        # Act
        mdd_result = calculator.calculate_mdd(equity_curve)

        # Assert
        self.assertEqual(mdd_result['mdd'], Decimal("-18.18"))
        self.assertEqual(mdd_result['mdd_start_time'], 1641081600000)
        self.assertEqual(mdd_result['mdd_end_time'], 1641168000000)
        self.assertIsNone(mdd_result['recovery_time'])  # 未恢复

    def test_mdd_calculation_multiple_drawdowns(self):
        """
        测试用例4：多次回撤场景 - 取最大回撤

        验收标准: 正确识别最大回撤
        """
        # Arrange
        calculator = MetricsCalculator()

        # 构建权益曲线：10000 → 11000 → 10500 → 12000 → 9000（第二次回撤更大）
        equity_curve = [
            EquityPoint(timestamp=1640995200000, cash=Decimal("10000.00"), position_value=Decimal("0.00"), equity=Decimal("10000.00"), equity_rate=Decimal("0.00")),
            EquityPoint(timestamp=1641081600000, cash=Decimal("11000.00"), position_value=Decimal("0.00"), equity=Decimal("11000.00"), equity_rate=Decimal("10.00")),
            EquityPoint(timestamp=1641168000000, cash=Decimal("10500.00"), position_value=Decimal("0.00"), equity=Decimal("10500.00"), equity_rate=Decimal("5.00")),
            EquityPoint(timestamp=1641254400000, cash=Decimal("12000.00"), position_value=Decimal("0.00"), equity=Decimal("12000.00"), equity_rate=Decimal("20.00")),
            EquityPoint(timestamp=1641340800000, cash=Decimal("9000.00"), position_value=Decimal("0.00"), equity=Decimal("9000.00"), equity_rate=Decimal("-10.00")),
        ]

        # Act
        mdd_result = calculator.calculate_mdd(equity_curve)

        # Assert
        # 最大回撤：从12000跌到9000，回撤 = (9000-12000)/12000 = -25.00%
        self.assertEqual(mdd_result['mdd'], Decimal("-25.00"))
        self.assertEqual(mdd_result['mdd_start_time'], 1641254400000)
        self.assertEqual(mdd_result['mdd_end_time'], 1641340800000)

    # === 异常场景测试 ===

    def test_mdd_empty_equity_curve_returns_default(self):
        """
        测试用例5：异常场景 - 空权益曲线

        验收标准: 返回默认值 MDD=0，不抛出异常（优雅降级）
        """
        # Arrange
        calculator = MetricsCalculator()
        equity_curve = []

        # Act
        mdd_result = calculator.calculate_mdd(equity_curve)

        # Assert
        self.assertEqual(mdd_result['mdd'], Decimal("0.00"))
        self.assertIsNone(mdd_result['mdd_start_time'])
        self.assertIsNone(mdd_result['mdd_end_time'])
        self.assertIsNone(mdd_result['recovery_time'])

    def test_mdd_single_point_equity_curve_returns_zero(self):
        """
        测试用例6：边界场景 - 单点权益曲线

        验收标准: MDD = 0.00%（无法计算回撤）
        """
        # Arrange
        calculator = MetricsCalculator()
        equity_curve = [
            EquityPoint(
                timestamp=1640995200000,
                cash=Decimal("10000.00"),
                position_value=Decimal("0.00"),
                equity=Decimal("10000.00"),
                equity_rate=Decimal("0.00")
            ),
        ]

        # Act
        mdd_result = calculator.calculate_mdd(equity_curve)

        # Assert
        self.assertEqual(mdd_result['mdd'], Decimal("0.00"))
        self.assertIsNone(mdd_result['mdd_start_time'])


class TestVolatilityCalculation(unittest.TestCase):
    """波动率计算测试套件"""

    def test_volatility_calculation_standard_case(self):
        """
        测试用例7：标准场景 - 有波动的权益曲线

        验收标准: 公式 = std(daily_returns) × sqrt(252)
        """
        # Arrange
        calculator = MetricsCalculator()

        # 构建权益曲线：10000 → 11000 (+10%) → 10500 (-4.55%) → 12000 (+14.29%)
        equity_curve = [
            EquityPoint(timestamp=1640995200000, cash=Decimal("10000.00"), position_value=Decimal("0.00"), equity=Decimal("10000.00"), equity_rate=Decimal("0.00")),
            EquityPoint(timestamp=1641081600000, cash=Decimal("11000.00"), position_value=Decimal("0.00"), equity=Decimal("11000.00"), equity_rate=Decimal("10.00")),
            EquityPoint(timestamp=1641168000000, cash=Decimal("10500.00"), position_value=Decimal("0.00"), equity=Decimal("10500.00"), equity_rate=Decimal("5.00")),
            EquityPoint(timestamp=1641254400000, cash=Decimal("12000.00"), position_value=Decimal("0.00"), equity=Decimal("12000.00"), equity_rate=Decimal("20.00")),
        ]

        # Act
        volatility = calculator.calculate_volatility(equity_curve)

        # Assert
        # 日收益率: [10%, -4.55%, 14.29%]
        # std = sqrt(((0.1-0.0658)^2 + (-0.0455-0.0658)^2 + (0.1429-0.0658)^2) / 2)
        # volatility = std × sqrt(252)
        # 预期波动率应大于0
        self.assertIsInstance(volatility, Decimal)
        self.assertGreater(volatility, Decimal("0.00"))
        # 验证精度（2位小数）
        self.assertEqual(volatility, volatility.quantize(Decimal("0.01")))

    def test_volatility_calculation_no_volatility(self):
        """
        测试用例8：无波动场景 - 所有收益率相同

        验收标准: 波动率 = 0.00%
        """
        # Arrange
        calculator = MetricsCalculator()

        # 构建权益曲线：10000 → 10000 → 10000 → 10000（无变化）
        equity_curve = [
            EquityPoint(timestamp=1640995200000, cash=Decimal("10000.00"), position_value=Decimal("0.00"), equity=Decimal("10000.00"), equity_rate=Decimal("0.00")),
            EquityPoint(timestamp=1641081600000, cash=Decimal("10000.00"), position_value=Decimal("0.00"), equity=Decimal("10000.00"), equity_rate=Decimal("0.00")),
            EquityPoint(timestamp=1641168000000, cash=Decimal("10000.00"), position_value=Decimal("0.00"), equity=Decimal("10000.00"), equity_rate=Decimal("0.00")),
        ]

        # Act
        volatility = calculator.calculate_volatility(equity_curve)

        # Assert
        self.assertEqual(volatility, Decimal("0.00"))

    # === 异常场景测试 ===

    def test_volatility_empty_equity_curve_returns_zero(self):
        """
        测试用例9：异常场景 - 空权益曲线

        验收标准: 返回 0.00%，不抛出异常（优雅降级）
        """
        # Arrange
        calculator = MetricsCalculator()
        equity_curve = []

        # Act
        volatility = calculator.calculate_volatility(equity_curve)

        # Assert
        self.assertEqual(volatility, Decimal("0.00"))

    def test_volatility_single_point_returns_zero(self):
        """
        测试用例10：异常场景 - 单点权益曲线

        验收标准: 返回 0.00%（无法计算收益率）
        """
        # Arrange
        calculator = MetricsCalculator()
        equity_curve = [
            EquityPoint(
                timestamp=1640995200000,
                cash=Decimal("10000.00"),
                position_value=Decimal("0.00"),
                equity=Decimal("10000.00"),
                equity_rate=Decimal("0.00")
            ),
        ]

        # Act
        volatility = calculator.calculate_volatility(equity_curve)

        # Assert
        self.assertEqual(volatility, Decimal("0.00"))

    def test_volatility_two_points_can_calculate(self):
        """
        测试用例11：边界场景 - 两点权益曲线

        验收标准: 可计算波动率（仅一个收益率点，标准差=0）
        """
        # Arrange
        calculator = MetricsCalculator()
        equity_curve = [
            EquityPoint(timestamp=1640995200000, cash=Decimal("10000.00"), position_value=Decimal("0.00"), equity=Decimal("10000.00"), equity_rate=Decimal("0.00")),
            EquityPoint(timestamp=1641081600000, cash=Decimal("11000.00"), position_value=Decimal("0.00"), equity=Decimal("11000.00"), equity_rate=Decimal("10.00")),
        ]

        # Act
        volatility = calculator.calculate_volatility(equity_curve)

        # Assert
        # 只有一个收益率，标准差=0，波动率=0
        self.assertEqual(volatility, Decimal("0.00"))


if __name__ == '__main__':
    unittest.main()
