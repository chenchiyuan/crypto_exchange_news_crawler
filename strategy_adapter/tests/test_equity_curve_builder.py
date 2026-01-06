"""
测试文件：EquityCurveBuilder工具类测试

Purpose:
    验证权益曲线重建工具类的算法正确性、边界检查和异常处理

关联任务: TASK-014-002
关联需求: FP-014-004（prd.md）
关联架构: architecture.md#4.1 EquityCurveBuilder

测试策略:
    - 单元测试
    - 覆盖正常场景、边界场景、异常场景
    - Fail-Fast验证：非法输入应立即抛出异常
"""

import unittest
from decimal import Decimal
import pandas as pd
from strategy_adapter.core.equity_curve_builder import EquityCurveBuilder
from strategy_adapter.models.equity_point import EquityPoint
from strategy_adapter.models.order import Order
from strategy_adapter.models.enums import OrderStatus, OrderSide


class TestEquityCurveBuilderNormalScenarios(unittest.TestCase):
    """EquityCurveBuilder 正常场景测试套件"""

    def test_build_equity_curve_with_no_orders(self):
        """
        测试用例1：无订单情况 - 权益曲线应全为初始资金

        验收标准: 权益曲线长度 = K线数量，所有点equity = initial_cash
        """
        # Arrange
        initial_cash = Decimal("10000.00")
        klines_data = {
            'open_time': [1640995200000, 1641081600000, 1641168000000],
            'open': [47000.0, 47500.0, 48000.0],
            'close': [47500.0, 48000.0, 48500.0]
        }
        klines = pd.DataFrame(klines_data)
        orders = []

        # Act
        equity_curve = EquityCurveBuilder.build_from_orders(orders, klines, initial_cash)

        # Assert
        self.assertEqual(len(equity_curve), 3)
        for point in equity_curve:
            self.assertIsInstance(point, EquityPoint)
            self.assertEqual(point.cash, initial_cash)
            self.assertEqual(point.position_value, Decimal("0.00"))
            self.assertEqual(point.equity, initial_cash)
            self.assertEqual(point.equity_rate, Decimal("0.00"))

    def test_build_equity_curve_first_point_equals_initial_cash(self):
        """
        测试用例2：验证权益曲线第一个点 equity = initial_cash

        验收标准: 算法正确性 - 权益曲线第一个点equity = initial_cash
        """
        # Arrange
        initial_cash = Decimal("10000.00")
        klines_data = {
            'open_time': [1640995200000, 1641081600000],
            'open': [47000.0, 47500.0],
            'close': [47500.0, 48000.0]
        }
        klines = pd.DataFrame(klines_data)
        orders = []

        # Act
        equity_curve = EquityCurveBuilder.build_from_orders(orders, klines, initial_cash)

        # Assert
        first_point = equity_curve[0]
        self.assertEqual(first_point.equity, initial_cash)
        self.assertEqual(first_point.timestamp, 1640995200000)

    def test_build_equity_curve_with_single_filled_order(self):
        """
        测试用例3：单笔已平仓订单 - 验证盈亏计算

        验收标准: equity = cash + position_value 恒等式成立
        """
        # Arrange
        initial_cash = Decimal("10000.00")
        klines_data = {
            'open_time': [1640995200000, 1641081600000, 1641168000000],
            'open': [47000.0, 47500.0, 48000.0],
            'close': [47500.0, 48000.0, 48500.0]
        }
        klines = pd.DataFrame(klines_data)

        # 创建一笔买入后卖出的订单
        order = Order(
            id="TEST-001",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            status=OrderStatus.CLOSED,
            open_price=Decimal("47000.00"),
            open_timestamp=1640995200000,
            close_price=Decimal("48000.00"),
            close_timestamp=1641081600000,
            quantity=Decimal("0.2"),
            position_value=Decimal("9400.00"),  # 47000 * 0.2
            open_commission=Decimal("9.40"),  # 买入手续费
            close_commission=Decimal("9.40"),  # 卖出手续费
            profit_loss=Decimal("181.20"),  # 200 - 18.8
            profit_loss_rate=Decimal("1.93")
        )
        orders = [order]

        # Act
        equity_curve = EquityCurveBuilder.build_from_orders(orders, klines, initial_cash)

        # Assert
        self.assertEqual(len(equity_curve), 3)

        # 第一个点：买入后，按当前K线close价格47500计算市值
        point1 = equity_curve[0]
        self.assertEqual(point1.cash, Decimal("590.60"))  # 10000 - 9400 - 9.4
        self.assertEqual(point1.position_value, Decimal("9500.00"))  # 47500 * 0.2
        self.assertEqual(point1.equity, Decimal("10090.60"))  # 590.60 + 9500

        # 第二个点：卖出后
        point2 = equity_curve[1]
        self.assertEqual(point2.cash, Decimal("10181.20"))  # 590.60 + 9600 - 9.4
        self.assertEqual(point2.position_value, Decimal("0.00"))
        self.assertEqual(point2.equity, Decimal("10181.20"))

        # 验证恒等式
        for point in equity_curve:
            self.assertEqual(point.cash + point.position_value, point.equity)

    def test_build_equity_curve_length_equals_klines_count(self):
        """
        测试用例4：权益曲线长度 = K线数量

        验收标准: 权益曲线长度 = K线数量
        """
        # Arrange
        initial_cash = Decimal("10000.00")
        klines_data = {
            'open_time': [1640995200000, 1641081600000, 1641168000000, 1641254400000, 1641340800000],
            'open': [47000.0, 47500.0, 48000.0, 48500.0, 49000.0],
            'close': [47500.0, 48000.0, 48500.0, 49000.0, 49500.0]
        }
        klines = pd.DataFrame(klines_data)
        orders = []

        # Act
        equity_curve = EquityCurveBuilder.build_from_orders(orders, klines, initial_cash)

        # Assert
        self.assertEqual(len(equity_curve), len(klines))

    def test_build_equity_curve_with_holding_order(self):
        """
        测试用例5：持仓订单 - 验证未平仓时的市值计算

        验收标准: 持仓订单的position_value随价格变化
        """
        # Arrange
        initial_cash = Decimal("10000.00")
        klines_data = {
            'open_time': [1640995200000, 1641081600000, 1641168000000],
            'open': [47000.0, 47500.0, 48000.0],
            'close': [47500.0, 48000.0, 48500.0]
        }
        klines = pd.DataFrame(klines_data)

        # 创建一笔持仓订单（未卖出）
        order = Order(
            id="TEST-002",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            status=OrderStatus.FILLED,
            open_price=Decimal("47000.00"),
            open_timestamp=1640995200000,
            quantity=Decimal("0.2"),
            position_value=Decimal("9400.00"),
            open_commission=Decimal("9.40")
        )
        orders = [order]

        # Act
        equity_curve = EquityCurveBuilder.build_from_orders(orders, klines, initial_cash)

        # Assert
        # 第一个点：买入后，按当前K线close价格47500计算市值
        point1 = equity_curve[0]
        self.assertEqual(point1.cash, Decimal("590.60"))  # 10000 - 9400 - 9.4
        self.assertEqual(point1.position_value, Decimal("9500.00"))  # 47500 * 0.2

        # 第二个点：持仓中，按当前价格48000计算
        point2 = equity_curve[1]
        self.assertEqual(point2.cash, Decimal("590.60"))
        expected_position_value = Decimal("48000.00") * Decimal("0.2")
        self.assertEqual(point2.position_value, expected_position_value)

    def test_build_equity_curve_equity_rate_calculation(self):
        """
        测试用例6：验证 equity_rate 计算正确性

        验收标准: equity_rate = (equity - initial_cash) / initial_cash × 100%
        """
        # Arrange
        initial_cash = Decimal("10000.00")
        klines_data = {
            'open_time': [1640995200000, 1641081600000],
            'open': [47000.0, 47500.0],
            'close': [47500.0, 50000.0]
        }
        klines = pd.DataFrame(klines_data)

        # 创建盈利订单
        order = Order(
            id="TEST-003",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            status=OrderStatus.CLOSED,
            open_price=Decimal("47000.00"),
            open_timestamp=1640995200000,
            close_price=Decimal("50000.00"),
            close_timestamp=1641081600000,
            quantity=Decimal("0.2"),
            position_value=Decimal("9400.00"),
            open_commission=Decimal("9.40"),
            close_commission=Decimal("9.40"),
            profit_loss=Decimal("581.20"),
            profit_loss_rate=Decimal("6.18")
        )
        orders = [order]

        # Act
        equity_curve = EquityCurveBuilder.build_from_orders(orders, klines, initial_cash)

        # Assert
        final_point = equity_curve[-1]
        expected_equity = initial_cash + Decimal("581.20")
        expected_rate = ((expected_equity - initial_cash) / initial_cash * Decimal("100")).quantize(Decimal("0.01"))

        self.assertEqual(final_point.equity, expected_equity)
        self.assertEqual(final_point.equity_rate, expected_rate)


class TestEquityCurveBuilderBoundaryScenarios(unittest.TestCase):
    """EquityCurveBuilder 边界场景测试套件"""

    def test_build_equity_curve_with_single_kline(self):
        """
        测试用例7：单根K线 - 边界场景

        验收标准: 权益曲线长度 = 1
        """
        # Arrange
        initial_cash = Decimal("10000.00")
        klines_data = {
            'open_time': [1640995200000],
            'open': [47000.0],
            'close': [47500.0]
        }
        klines = pd.DataFrame(klines_data)
        orders = []

        # Act
        equity_curve = EquityCurveBuilder.build_from_orders(orders, klines, initial_cash)

        # Assert
        self.assertEqual(len(equity_curve), 1)
        self.assertEqual(equity_curve[0].equity, initial_cash)

    def test_build_equity_curve_with_all_holding_orders(self):
        """
        测试用例8：所有订单未平仓 - 验证持仓市值计算

        验收标准: position_value 随当前价格变化
        """
        # Arrange
        initial_cash = Decimal("10000.00")
        klines_data = {
            'open_time': [1640995200000, 1641081600000],
            'open': [47000.0, 50000.0],
            'close': [47500.0, 51000.0]
        }
        klines = pd.DataFrame(klines_data)

        order = Order(
            id="TEST-004",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            status=OrderStatus.FILLED,
            open_price=Decimal("47000.00"),
            open_timestamp=1640995200000,
            quantity=Decimal("0.2"),
            position_value=Decimal("9400.00"),
            open_commission=Decimal("9.40")
        )
        orders = [order]

        # Act
        equity_curve = EquityCurveBuilder.build_from_orders(orders, klines, initial_cash)

        # Assert
        last_point = equity_curve[-1]
        expected_position_value = Decimal("51000.00") * Decimal("0.2")
        self.assertEqual(last_point.position_value, expected_position_value)


class TestEquityCurveBuilderFailFast(unittest.TestCase):
    """EquityCurveBuilder Fail-Fast 异常测试套件"""

    def test_build_equity_curve_zero_initial_cash_raises_valueerror(self):
        """
        测试用例9：Fail-Fast验证 - initial_cash = 0 应立即抛出 ValueError

        验收标准: 当 initial_cash <= 0 时立即抛出 ValueError
        """
        # Arrange
        invalid_initial_cash = Decimal("0")
        klines_data = {
            'open_time': [1640995200000],
            'open': [47000.0],
            'close': [47500.0]
        }
        klines = pd.DataFrame(klines_data)
        orders = []

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            EquityCurveBuilder.build_from_orders(orders, klines, invalid_initial_cash)

        self.assertIn("initial_cash必须大于0", str(context.exception))
        self.assertIn(str(invalid_initial_cash), str(context.exception))

    def test_build_equity_curve_negative_initial_cash_raises_valueerror(self):
        """
        测试用例10：Fail-Fast验证 - 负数 initial_cash 应立即抛出 ValueError

        验收标准: 边界检查验证
        """
        # Arrange
        invalid_initial_cash = Decimal("-10000.00")
        klines_data = {
            'open_time': [1640995200000],
            'open': [47000.0],
            'close': [47500.0]
        }
        klines = pd.DataFrame(klines_data)
        orders = []

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            EquityCurveBuilder.build_from_orders(orders, klines, invalid_initial_cash)

        self.assertIn("initial_cash必须大于0", str(context.exception))

    def test_build_equity_curve_empty_klines_raises_valueerror(self):
        """
        测试用例11：Fail-Fast验证 - 空K线数据应立即抛出 ValueError

        验收标准: 当 klines 为空 DataFrame 时立即抛出 ValueError
        """
        # Arrange
        initial_cash = Decimal("10000.00")
        klines = pd.DataFrame()  # 空DataFrame
        orders = []

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            EquityCurveBuilder.build_from_orders(orders, klines, initial_cash)

        self.assertIn("klines不能为空", str(context.exception))

    def test_build_equity_curve_missing_required_columns_raises_valueerror(self):
        """
        测试用例12：Fail-Fast验证 - K线缺少必需列应立即抛出 ValueError

        验收标准: 当 klines 缺少必需列时立即抛出 ValueError，包含缺失列名
        """
        # Arrange
        initial_cash = Decimal("10000.00")
        # 缺少 'close' 列
        klines_data = {
            'open_time': [1640995200000],
            'open': [47000.0]
        }
        klines = pd.DataFrame(klines_data)
        orders = []

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            EquityCurveBuilder.build_from_orders(orders, klines, initial_cash)

        self.assertIn("klines缺少必需列", str(context.exception))
        self.assertIn("close", str(context.exception))


if __name__ == '__main__':
    unittest.main()
