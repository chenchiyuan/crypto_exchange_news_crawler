"""
InvalidationDetector单元测试

测试失效检测器的所有功能，包括：
- Guard Clauses异常路径
- 价格收复检测逻辑
- 状态更新正确性
- StateTransition日志创建

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md
    - Task: TASK-002-022
"""

import unittest
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from backtest.models import KLine
from monitor.models import Exchange, FuturesContract
from volume_trap.models import VolumeTrapMonitor, VolumeTrapStateTransition
from volume_trap.services.invalidation_detector import InvalidationDetector


class InvalidationDetectorGuardClausesTest(TestCase):
    """测试InvalidationDetector的Guard Clauses异常路径。

    验证所有边界检查和异常处理是否按预期工作。
    """

    def setUp(self):
        """测试前准备：创建测试用的交易所和合约数据。"""
        self.exchange = Exchange.objects.create(name="Binance", code="binance", enabled=True)

        self.contract = FuturesContract.objects.create(
            exchange=self.exchange,
            symbol="BTCUSDT",
            contract_type="perpetual",
            status="active",
            current_price=Decimal("50000.00"),
            first_seen=timezone.now(),
        )
        self.detector = InvalidationDetector()

    def test_guard_clause_invalid_interval(self):
        """测试interval参数检查：无效interval应抛出ValueError。"""
        with self.assertRaises(ValueError) as context:
            self.detector.check_all(interval="invalid")

        self.assertIn("interval参数错误", str(context.exception))

    def test_guard_clause_trigger_price_zero(self):
        """测试P_trigger=0场景：应跳过并记录错误。

        业务规则：P_trigger=0属于数据异常，应跳过该监控记录。
        """
        # 创建Monitor记录，P_trigger=0
        monitor = VolumeTrapMonitor.objects.create(
            futures_contract=self.contract,
            interval="4h",
            trigger_time=timezone.now() - timedelta(hours=4),
            trigger_price=Decimal("0"),  # 异常值
            trigger_volume=Decimal("1000.00"),
            trigger_kline_high=Decimal("51000.00"),
            trigger_kline_low=Decimal("49000.00"),
            status="pending",
            phase_1_passed=True,
        )

        # 创建最新K线
        self._create_kline("BTCUSDT", "4h", close_price=Decimal("52000.00"))

        # 执行检测
        result = self.detector.check_all(interval="4h")

        # 验证：应跳过该记录，记录错误
        self.assertEqual(result["checked_count"], 1)
        self.assertEqual(result["invalidated_count"], 0)
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("P_trigger不能为0", result["errors"][0])

    def _create_kline(self, symbol: str, interval: str, close_price: Decimal):
        """辅助方法：创建K线数据。"""
        now = timezone.now()
        return KLine.objects.create(
            symbol=symbol,
            interval=interval,
            open_time=now - timedelta(hours=1),
            close_time=now,
            open_price=close_price,
            high_price=close_price,
            low_price=close_price,
            close_price=close_price,
            volume=Decimal("1000.00"),
            quote_volume=Decimal("50000000.00"),
        )


class InvalidationDetectorFunctionalTest(TestCase):
    """测试InvalidationDetector的核心功能。

    验证价格收复检测逻辑、状态更新、日志创建的正确性。
    """

    def setUp(self):
        """测试前准备：创建测试用的交易所和合约数据。"""
        self.exchange = Exchange.objects.create(
            name="Binance Test", code="binance_test", enabled=True
        )

        self.contract = FuturesContract.objects.create(
            exchange=self.exchange,
            symbol="ETHUSDT",
            contract_type="perpetual",
            status="active",
            current_price=Decimal("3000.00"),
            first_seen=timezone.now(),
        )
        self.detector = InvalidationDetector()

    def test_price_not_recovered(self):
        """测试价格未收复场景：current_close <= P_trigger。

        场景：
        - P_trigger = 3000
        - current_close = 2900 (未收复)
        - 预期：status保持不变
        """
        # 创建Monitor记录
        monitor = VolumeTrapMonitor.objects.create(
            futures_contract=self.contract,
            interval="4h",
            trigger_time=timezone.now() - timedelta(hours=4),
            trigger_price=Decimal("3000.00"),
            trigger_volume=Decimal("5000.00"),
            trigger_kline_high=Decimal("3100.00"),
            trigger_kline_low=Decimal("2900.00"),
            status="pending",
            phase_1_passed=True,
        )

        # 创建最新K线：价格未收复
        self._create_kline("ETHUSDT", "4h", close_price=Decimal("2900.00"))

        # 执行检测
        result = self.detector.check_all(interval="4h")

        # 验证：status保持pending
        monitor.refresh_from_db()
        self.assertEqual(monitor.status, "pending")
        self.assertEqual(result["invalidated_count"], 0)

    def test_price_recovered(self):
        """测试价格收复场景：current_close > P_trigger。

        场景：
        - P_trigger = 3000
        - current_close = 3100 (收复)
        - 预期：status更新为invalidated
        """
        # 创建Monitor记录
        monitor = VolumeTrapMonitor.objects.create(
            futures_contract=self.contract,
            interval="4h",
            trigger_time=timezone.now() - timedelta(hours=4),
            trigger_price=Decimal("3000.00"),
            trigger_volume=Decimal("5000.00"),
            trigger_kline_high=Decimal("3100.00"),
            trigger_kline_low=Decimal("2900.00"),
            status="pending",
            phase_1_passed=True,
        )

        # 创建最新K线：价格收复
        self._create_kline("ETHUSDT", "4h", close_price=Decimal("3100.00"))

        # 执行检测
        result = self.detector.check_all(interval="4h")

        # 验证：status更新为invalidated
        monitor.refresh_from_db()
        self.assertEqual(monitor.status, "invalidated")
        self.assertEqual(result["invalidated_count"], 1)

    def test_state_transition_log_created(self):
        """测试StateTransition日志创建。

        验证价格收复时是否正确创建StateTransition日志。
        """
        # 创建Monitor记录
        monitor = VolumeTrapMonitor.objects.create(
            futures_contract=self.contract,
            interval="4h",
            trigger_time=timezone.now() - timedelta(hours=4),
            trigger_price=Decimal("3000.00"),
            trigger_volume=Decimal("5000.00"),
            trigger_kline_high=Decimal("3100.00"),
            trigger_kline_low=Decimal("2900.00"),
            status="suspected_abandonment",
            phase_1_passed=True,
            phase_2_passed=True,
        )

        # 创建最新K线：价格收复
        self._create_kline("ETHUSDT", "4h", close_price=Decimal("3200.00"))

        # 执行检测
        self.detector.check_all(interval="4h")

        # 验证：StateTransition日志已创建
        transition = VolumeTrapStateTransition.objects.filter(
            monitor=monitor, to_status="invalidated"
        ).first()

        self.assertIsNotNone(transition, "StateTransition日志应已创建")
        self.assertEqual(transition.from_status, "suspected_abandonment")
        self.assertEqual(transition.to_status, "invalidated")
        self.assertIn("reason", transition.trigger_condition)
        self.assertEqual(transition.trigger_condition["reason"], "price_recovery")
        self.assertIn("current_close", transition.trigger_condition)
        self.assertIn("trigger_price", transition.trigger_condition)

    def test_multiple_monitors_batch_check(self):
        """测试批量检测多个监控记录。

        场景：
        - 创建3个监控记录：1个收复，2个未收复
        - 预期：只有1个被标记为invalidated
        """
        # 监控记录1：价格收复
        monitor1 = VolumeTrapMonitor.objects.create(
            futures_contract=self.contract,
            interval="4h",
            trigger_time=timezone.now() - timedelta(hours=4),
            trigger_price=Decimal("3000.00"),
            trigger_volume=Decimal("5000.00"),
            trigger_kline_high=Decimal("3100.00"),
            trigger_kline_low=Decimal("2900.00"),
            status="pending",
            phase_1_passed=True,
        )

        # 创建另一个合约
        contract2 = FuturesContract.objects.create(
            exchange=self.exchange,
            symbol="BTCUSDT",
            contract_type="perpetual",
            status="active",
            current_price=Decimal("50000.00"),
            first_seen=timezone.now(),
        )

        # 监控记录2：价格未收复
        monitor2 = VolumeTrapMonitor.objects.create(
            futures_contract=contract2,
            interval="4h",
            trigger_time=timezone.now() - timedelta(hours=4),
            trigger_price=Decimal("50000.00"),
            trigger_volume=Decimal("1000.00"),
            trigger_kline_high=Decimal("51000.00"),
            trigger_kline_low=Decimal("49000.00"),
            status="pending",
            phase_1_passed=True,
        )

        # 监控记录3：价格未收复
        monitor3 = VolumeTrapMonitor.objects.create(
            futures_contract=contract2,
            interval="4h",
            trigger_time=timezone.now() - timedelta(hours=8),
            trigger_price=Decimal("52000.00"),
            trigger_volume=Decimal("2000.00"),
            trigger_kline_high=Decimal("53000.00"),
            trigger_kline_low=Decimal("51000.00"),
            status="suspected_abandonment",
            phase_1_passed=True,
            phase_2_passed=True,
        )

        # 创建最新K线
        self._create_kline("ETHUSDT", "4h", close_price=Decimal("3100.00"))  # 收复
        self._create_kline("BTCUSDT", "4h", close_price=Decimal("49500.00"))  # 未收复

        # 执行检测
        result = self.detector.check_all(interval="4h")

        # 验证：只有monitor1被标记为invalidated
        monitor1.refresh_from_db()
        monitor2.refresh_from_db()
        monitor3.refresh_from_db()

        self.assertEqual(monitor1.status, "invalidated")
        self.assertEqual(monitor2.status, "pending")
        self.assertEqual(monitor3.status, "suspected_abandonment")
        self.assertEqual(result["checked_count"], 3)
        self.assertEqual(result["invalidated_count"], 1)

    def test_no_kline_data(self):
        """测试无K线数据场景。

        场景：
        - 监控记录存在，但没有最新K线数据
        - 预期：跳过该记录，status保持不变
        """
        # 创建Monitor记录
        monitor = VolumeTrapMonitor.objects.create(
            futures_contract=self.contract,
            interval="4h",
            trigger_time=timezone.now() - timedelta(hours=4),
            trigger_price=Decimal("3000.00"),
            trigger_volume=Decimal("5000.00"),
            trigger_kline_high=Decimal("3100.00"),
            trigger_kline_low=Decimal("2900.00"),
            status="pending",
            phase_1_passed=True,
        )

        # 不创建K线数据

        # 执行检测
        result = self.detector.check_all(interval="4h")

        # 验证：status保持pending
        monitor.refresh_from_db()
        self.assertEqual(monitor.status, "pending")
        self.assertEqual(result["invalidated_count"], 0)

    def test_already_invalidated_skipped(self):
        """测试已失效记录被跳过。

        场景：
        - 监控记录status='invalidated'
        - 预期：不应被检测
        """
        # 创建Monitor记录：已失效
        monitor = VolumeTrapMonitor.objects.create(
            futures_contract=self.contract,
            interval="4h",
            trigger_time=timezone.now() - timedelta(hours=4),
            trigger_price=Decimal("3000.00"),
            trigger_volume=Decimal("5000.00"),
            trigger_kline_high=Decimal("3100.00"),
            trigger_kline_low=Decimal("2900.00"),
            status="invalidated",  # 已失效
            phase_1_passed=True,
        )

        # 创建最新K线
        self._create_kline("ETHUSDT", "4h", close_price=Decimal("3200.00"))

        # 执行检测
        result = self.detector.check_all(interval="4h")

        # 验证：不应被检测
        self.assertEqual(result["checked_count"], 0)
        self.assertEqual(result["invalidated_count"], 0)

    def _create_kline(self, symbol: str, interval: str, close_price: Decimal):
        """辅助方法：创建K线数据。"""
        now = timezone.now()
        return KLine.objects.create(
            symbol=symbol,
            interval=interval,
            open_time=now - timedelta(hours=1),
            close_time=now,
            open_price=close_price,
            high_price=close_price,
            low_price=close_price,
            close_price=close_price,
            volume=Decimal("1000.00"),
            quote_volume=Decimal(str(float(close_price) * 1000.0)),
        )


if __name__ == "__main__":
    unittest.main()
