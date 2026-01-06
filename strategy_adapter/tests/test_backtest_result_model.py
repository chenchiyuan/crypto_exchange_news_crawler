"""
测试文件：BacktestResult 和 BacktestOrder 模型测试

Purpose:
    验证回测结果数据模型的字段定义、约束和关联关系

关联任务: TASK-014-012, TASK-014-013
关联需求: FP-014-018, FP-014-019（prd.md）

测试策略:
    - 单元测试
    - 覆盖创建、查询、字段约束和关联关系
"""

import datetime
from decimal import Decimal

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from strategy_adapter.models.db_models import BacktestResult, BacktestOrder


class TestBacktestResultModel(TestCase):
    """BacktestResult 模型测试套件"""

    def test_create_backtest_result_with_all_fields(self):
        """
        测试用例1：创建完整的回测结果记录

        验收标准: 所有字段正确存储
        """
        # Arrange
        result = BacktestResult(
            strategy_name="DDPS-Z",
            symbol="BTCUSDT",
            interval="4h",
            market_type="futures",
            start_date=datetime.date(2025, 1, 1),
            end_date=datetime.date(2025, 12, 31),
            initial_cash=Decimal("10000.00"),
            position_size=Decimal("100.00"),
            commission_rate=Decimal("0.001"),
            risk_free_rate=Decimal("3.00"),
            equity_curve=[
                {"timestamp": 1, "cash": "10000.00", "position_value": "0.00", "equity": "10000.00", "equity_rate": "0.00"}
            ],
            metrics={
                "apr": "12.00",
                "mdd": "-5.00",
                "sharpe_ratio": "1.50"
            }
        )

        # Act
        result.save()

        # Assert
        saved_result = BacktestResult.objects.get(pk=result.pk)
        self.assertEqual(saved_result.strategy_name, "DDPS-Z")
        self.assertEqual(saved_result.symbol, "BTCUSDT")
        self.assertEqual(saved_result.interval, "4h")
        self.assertEqual(saved_result.market_type, "futures")
        self.assertEqual(saved_result.initial_cash, Decimal("10000.00"))
        self.assertEqual(saved_result.position_size, Decimal("100.00"))
        self.assertEqual(saved_result.commission_rate, Decimal("0.001"))
        self.assertEqual(len(saved_result.equity_curve), 1)
        self.assertEqual(saved_result.metrics["apr"], "12.00")

    def test_backtest_result_str_representation(self):
        """
        测试用例2：验证字符串表示

        验收标准: __str__方法返回可读格式
        """
        # Arrange
        result = BacktestResult(
            strategy_name="DDPS-Z",
            symbol="BTCUSDT",
            interval="4h",
            market_type="futures",
            start_date=datetime.date(2025, 1, 1),
            end_date=datetime.date(2025, 12, 31),
            initial_cash=Decimal("10000.00"),
            position_size=Decimal("100.00"),
            commission_rate=Decimal("0.001"),
            risk_free_rate=Decimal("3.00"),
        )

        # Act
        str_repr = str(result)

        # Assert
        self.assertIn("DDPS-Z", str_repr)
        self.assertIn("BTCUSDT", str_repr)
        self.assertIn("2025-01-01", str_repr)

    def test_backtest_result_created_at_auto_set(self):
        """
        测试用例3：验证 created_at 自动设置

        验收标准: 创建时自动记录时间
        """
        # Arrange
        result = BacktestResult.objects.create(
            strategy_name="DDPS-Z",
            symbol="BTCUSDT",
            interval="4h",
            market_type="futures",
            start_date=datetime.date(2025, 1, 1),
            end_date=datetime.date(2025, 12, 31),
            initial_cash=Decimal("10000.00"),
            position_size=Decimal("100.00"),
            commission_rate=Decimal("0.001"),
            risk_free_rate=Decimal("3.00"),
        )

        # Assert
        self.assertIsNotNone(result.created_at)

    def test_backtest_result_default_values(self):
        """
        测试用例4：验证默认值

        验收标准: equity_curve 默认为空列表，metrics 默认为空字典
        """
        # Arrange
        result = BacktestResult.objects.create(
            strategy_name="DDPS-Z",
            symbol="BTCUSDT",
            interval="4h",
            market_type="futures",
            start_date=datetime.date(2025, 1, 1),
            end_date=datetime.date(2025, 12, 31),
            initial_cash=Decimal("10000.00"),
            position_size=Decimal("100.00"),
            commission_rate=Decimal("0.001"),
            risk_free_rate=Decimal("3.00"),
        )

        # Assert
        self.assertEqual(result.equity_curve, [])
        self.assertEqual(result.metrics, {})


class TestBacktestOrderModel(TestCase):
    """BacktestOrder 模型测试套件"""

    def setUp(self):
        """创建测试用的 BacktestResult"""
        self.result = BacktestResult.objects.create(
            strategy_name="DDPS-Z",
            symbol="BTCUSDT",
            interval="4h",
            market_type="futures",
            start_date=datetime.date(2025, 1, 1),
            end_date=datetime.date(2025, 12, 31),
            initial_cash=Decimal("10000.00"),
            position_size=Decimal("100.00"),
            commission_rate=Decimal("0.001"),
            risk_free_rate=Decimal("3.00"),
        )

    def test_create_backtest_order_with_all_fields(self):
        """
        测试用例5：创建完整的回测订单记录

        验收标准: 所有字段正确存储
        """
        # Arrange
        order = BacktestOrder(
            backtest_result=self.result,
            order_id="DDPS-Z-001",
            status="closed",
            buy_price=Decimal("50000.00"),
            buy_timestamp=1640995200000,
            sell_price=Decimal("52000.00"),
            sell_timestamp=1641081600000,
            quantity=Decimal("0.002"),
            position_value=Decimal("100.00"),
            commission=Decimal("0.20"),
            profit_loss=Decimal("3.80"),
            profit_loss_rate=Decimal("3.80"),
            holding_periods=6
        )

        # Act
        order.save()

        # Assert
        saved_order = BacktestOrder.objects.get(pk=order.pk)
        self.assertEqual(saved_order.order_id, "DDPS-Z-001")
        self.assertEqual(saved_order.status, "closed")
        self.assertEqual(saved_order.buy_price, Decimal("50000.00"))
        self.assertEqual(saved_order.sell_price, Decimal("52000.00"))
        self.assertEqual(saved_order.profit_loss, Decimal("3.80"))

    def test_backtest_order_foreign_key_relation(self):
        """
        测试用例6：验证外键关联

        验收标准: orders 反向关联可正确查询
        """
        # Arrange
        BacktestOrder.objects.create(
            backtest_result=self.result,
            order_id="DDPS-Z-001",
            status="closed",
            buy_price=Decimal("50000.00"),
            buy_timestamp=1640995200000,
            quantity=Decimal("0.002"),
            position_value=Decimal("100.00"),
            commission=Decimal("0.20"),
        )
        BacktestOrder.objects.create(
            backtest_result=self.result,
            order_id="DDPS-Z-002",
            status="filled",
            buy_price=Decimal("51000.00"),
            buy_timestamp=1641168000000,
            quantity=Decimal("0.002"),
            position_value=Decimal("102.00"),
            commission=Decimal("0.10"),
        )

        # Act
        orders = self.result.orders.all()

        # Assert
        self.assertEqual(orders.count(), 2)
        self.assertEqual(orders[0].order_id, "DDPS-Z-001")  # 按 buy_timestamp 排序
        self.assertEqual(orders[1].order_id, "DDPS-Z-002")

    def test_backtest_order_cascade_delete(self):
        """
        测试用例7：验证级联删除

        验收标准: 删除回测结果时自动删除关联订单
        """
        # Arrange
        BacktestOrder.objects.create(
            backtest_result=self.result,
            order_id="DDPS-Z-001",
            status="closed",
            buy_price=Decimal("50000.00"),
            buy_timestamp=1640995200000,
            quantity=Decimal("0.002"),
            position_value=Decimal("100.00"),
            commission=Decimal("0.20"),
        )

        # Act
        self.result.delete()

        # Assert
        self.assertEqual(BacktestOrder.objects.count(), 0)

    def test_backtest_order_holding_order_nullable_fields(self):
        """
        测试用例8：验证持仓订单可空字段

        验收标准: 持仓订单的 sell_price, sell_timestamp, profit_loss 等可为空
        """
        # Arrange
        order = BacktestOrder.objects.create(
            backtest_result=self.result,
            order_id="DDPS-Z-003",
            status="filled",
            buy_price=Decimal("50000.00"),
            buy_timestamp=1640995200000,
            quantity=Decimal("0.002"),
            position_value=Decimal("100.00"),
            commission=Decimal("0.10"),
            # sell_price, sell_timestamp, profit_loss, profit_loss_rate, holding_periods 全部为空
        )

        # Assert
        self.assertIsNone(order.sell_price)
        self.assertIsNone(order.sell_timestamp)
        self.assertIsNone(order.profit_loss)
        self.assertIsNone(order.profit_loss_rate)
        self.assertIsNone(order.holding_periods)

    def test_backtest_order_str_representation(self):
        """
        测试用例9：验证字符串表示

        验收标准: __str__方法返回可读格式
        """
        # Arrange
        order = BacktestOrder(
            backtest_result=self.result,
            order_id="DDPS-Z-001",
            status="closed",
            buy_price=Decimal("50000.00"),
            buy_timestamp=1640995200000,
            quantity=Decimal("0.002"),
            position_value=Decimal("100.00"),
            commission=Decimal("0.20"),
        )

        # Act
        str_repr = str(order)

        # Assert
        self.assertIn("DDPS-Z-001", str_repr)
        self.assertIn("closed", str_repr)
