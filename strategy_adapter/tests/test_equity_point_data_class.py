"""
测试文件：EquityPoint数据类测试

Purpose:
    验证EquityPoint数据类的定义正确性、类型安全性和边界检查

关联任务: TASK-014-001
关联需求: FP-014-004（prd.md）
关联架构: architecture.md#4.1 EquityCurveBuilder

测试策略:
    - 单元测试
    - 覆盖正常场景、边界场景、异常场景
    - Fail-Fast验证：负数时间戳应立即抛出异常
"""

import unittest
from decimal import Decimal
from strategy_adapter.models.equity_point import EquityPoint


class TestEquityPointDataClass(unittest.TestCase):
    """EquityPoint数据类测试套件"""

    def test_equity_point_creation_with_valid_data(self):
        """
        测试用例1：正常创建EquityPoint实例

        验收标准: 使用@dataclass定义EquityPoint
        """
        # Arrange
        timestamp = 1640995200000  # 2022-01-01 00:00:00 UTC
        cash = Decimal("8000.00")
        position_value = Decimal("2000.00")
        equity = Decimal("10000.00")
        equity_rate = Decimal("0.00")

        # Act
        point = EquityPoint(
            timestamp=timestamp,
            cash=cash,
            position_value=position_value,
            equity=equity,
            equity_rate=equity_rate
        )

        # Assert
        self.assertEqual(point.timestamp, timestamp)
        self.assertEqual(point.cash, cash)
        self.assertEqual(point.position_value, position_value)
        self.assertEqual(point.equity, equity)
        self.assertEqual(point.equity_rate, equity_rate)

    def test_equity_point_fields_are_decimal_type(self):
        """
        测试用例2：验证所有金额字段类型为Decimal

        验收标准: 所有金额字段类型为Decimal
        """
        # Arrange & Act
        point = EquityPoint(
            timestamp=1640995200000,
            cash=Decimal("8000.00"),
            position_value=Decimal("2000.00"),
            equity=Decimal("10000.00"),
            equity_rate=Decimal("0.00")
        )

        # Assert
        self.assertIsInstance(point.cash, Decimal)
        self.assertIsInstance(point.position_value, Decimal)
        self.assertIsInstance(point.equity, Decimal)
        self.assertIsInstance(point.equity_rate, Decimal)

    def test_equity_point_with_profit(self):
        """
        测试用例3：盈利场景（equity > initial_cash）

        验收标准: 正确表示盈利状态
        """
        # Arrange & Act
        point = EquityPoint(
            timestamp=1641081600000,
            cash=Decimal("9000.00"),
            position_value=Decimal("2200.00"),
            equity=Decimal("11200.00"),
            equity_rate=Decimal("12.00")  # 相对初始10000盈利12%
        )

        # Assert
        self.assertEqual(point.equity, Decimal("11200.00"))
        self.assertEqual(point.equity_rate, Decimal("12.00"))
        self.assertGreater(point.equity_rate, Decimal("0"))

    def test_equity_point_with_loss(self):
        """
        测试用例4：亏损场景（equity < initial_cash）

        验收标准: 正确表示亏损状态
        """
        # Arrange & Act
        point = EquityPoint(
            timestamp=1641081600000,
            cash=Decimal("7500.00"),
            position_value=Decimal("1600.00"),
            equity=Decimal("9100.00"),
            equity_rate=Decimal("-9.00")  # 相对初始10000亏损9%
        )

        # Assert
        self.assertEqual(point.equity, Decimal("9100.00"))
        self.assertEqual(point.equity_rate, Decimal("-9.00"))
        self.assertLess(point.equity_rate, Decimal("0"))

    def test_equity_point_equity_equals_cash_plus_position_value(self):
        """
        测试用例5：验证equity = cash + position_value恒等式

        验收标准: 每个点的equity = cash + position_value
        """
        # Arrange
        cash = Decimal("7000.00")
        position_value = Decimal("3000.00")
        expected_equity = cash + position_value

        # Act
        point = EquityPoint(
            timestamp=1640995200000,
            cash=cash,
            position_value=position_value,
            equity=expected_equity,
            equity_rate=Decimal("0.00")
        )

        # Assert
        self.assertEqual(point.equity, expected_equity)
        self.assertEqual(point.cash + point.position_value, point.equity)

    # === Fail-Fast异常测试 ===

    def test_equity_point_negative_timestamp_raises_valueerror(self):
        """
        测试用例6：Fail-Fast验证 - 负数时间戳应立即抛出ValueError

        验收标准: **异常路径验证** - 当timestamp为负数时抛出ValueError
        边界检查: timestamp必须为正整数
        """
        # Arrange
        invalid_timestamp = -1640995200000

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            EquityPoint(
                timestamp=invalid_timestamp,
                cash=Decimal("10000.00"),
                position_value=Decimal("0.00"),
                equity=Decimal("10000.00"),
                equity_rate=Decimal("0.00")
            )

        # 验证异常消息包含上下文信息（预期值 vs 实际值）
        self.assertIn("timestamp必须为正整数", str(context.exception))
        self.assertIn(str(invalid_timestamp), str(context.exception))

    def test_equity_point_zero_timestamp_raises_valueerror(self):
        """
        测试用例7：Fail-Fast验证 - 零时间戳应立即抛出ValueError

        验收标准: 边界检查验证
        """
        # Arrange
        invalid_timestamp = 0

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            EquityPoint(
                timestamp=invalid_timestamp,
                cash=Decimal("10000.00"),
                position_value=Decimal("0.00"),
                equity=Decimal("10000.00"),
                equity_rate=Decimal("0.00")
            )

        self.assertIn("timestamp必须为正整数", str(context.exception))

    def test_equity_point_negative_equity_raises_valueerror(self):
        """
        测试用例8：Fail-Fast验证 - 负数equity应立即抛出ValueError

        验收标准: 边界检查 - equity必须非负
        """
        # Arrange
        invalid_equity = Decimal("-1000.00")

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            EquityPoint(
                timestamp=1640995200000,
                cash=Decimal("10000.00"),
                position_value=Decimal("0.00"),
                equity=invalid_equity,
                equity_rate=Decimal("0.00")
            )

        self.assertIn("equity必须非负", str(context.exception))
        self.assertIn(str(invalid_equity), str(context.exception))


if __name__ == '__main__':
    unittest.main()
