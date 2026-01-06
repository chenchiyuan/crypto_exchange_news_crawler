"""
VolumeRetentionAnalyzer单元测试

测试成交量留存分析器的所有功能，包括：
- Guard Clauses异常路径
- 正常计算路径
- 边界条件
- 计算准确性验证

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md
    - Task: TASK-002-012
"""

import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from backtest.models import KLine
from monitor.models import Exchange, FuturesContract
from volume_trap.detectors.volume_retention_analyzer import VolumeRetentionAnalyzer
from volume_trap.exceptions import DataInsufficientError, InvalidDataError


class VolumeRetentionAnalyzerGuardClausesTest(TestCase):
    """测试VolumeRetentionAnalyzer的Guard Clauses异常路径。

    验证所有边界检查和异常处理是否按预期工作。
    """

    def setUp(self):
        """测试前准备：创建测试用的合约数据。"""
        # 创建交易所
        self.exchange = Exchange.objects.create(name="Binance", code="binance", enabled=True)

        # 创建合约
        self.contract = FuturesContract.objects.create(
            exchange=self.exchange,
            symbol="BTCUSDT",
            contract_type="perpetual",
            status="active",
            current_price=Decimal("50000.00"),
            first_seen=timezone.now(),
        )
        self.analyzer = VolumeRetentionAnalyzer()

    def test_guard_clause_trigger_volume_zero(self):
        """测试trigger_volume检查：成交量为0应抛出InvalidDataError。"""
        # 创建3根后续K线
        post_klines = self._create_klines("BTCUSDT", "4h", 3)

        with self.assertRaises(InvalidDataError) as context:
            self.analyzer.analyze(
                trigger_volume=Decimal("0.00"), post_klines=post_klines  # 异常：V_trigger=0
            )

        exc = context.exception
        self.assertEqual(exc.field, "trigger_volume")
        self.assertEqual(exc.value, 0.0)
        self.assertIn("触发成交量必须>0", exc.context)

    def test_guard_clause_trigger_volume_negative(self):
        """测试trigger_volume检查：负数应抛出InvalidDataError。"""
        # 创建3根后续K线
        post_klines = self._create_klines("BTCUSDT", "4h", 3)

        with self.assertRaises(InvalidDataError) as context:
            self.analyzer.analyze(
                trigger_volume=Decimal("-100.00"), post_klines=post_klines  # 异常：负数
            )

        exc = context.exception
        self.assertEqual(exc.field, "trigger_volume")

    def test_guard_clause_insufficient_klines(self):
        """测试后续K线数量检查：少于3根应抛出DataInsufficientError。"""
        # 只创建2根K线（需要至少3根）
        post_klines = self._create_klines("BTCUSDT", "4h", 2)

        with self.assertRaises(DataInsufficientError) as context:
            self.analyzer.analyze(trigger_volume=Decimal("8000.00"), post_klines=post_klines)

        exc = context.exception
        self.assertEqual(exc.required, 3)
        self.assertEqual(exc.actual, 2)

    def test_guard_clause_zero_retention_threshold(self):
        """测试retention_threshold边界检查：零阈值应抛出ValueError。"""
        # 创建3根后续K线
        post_klines = self._create_klines("BTCUSDT", "4h", 3)

        with self.assertRaises(ValueError) as context:
            self.analyzer.analyze(
                trigger_volume=Decimal("8000.00"),
                post_klines=post_klines,
                retention_threshold=0,  # 异常：阈值=0
            )

        self.assertIn("retention_threshold参数边界错误", str(context.exception))
        self.assertIn("预期范围=(0, 100]", str(context.exception))

    def test_guard_clause_negative_retention_threshold(self):
        """测试retention_threshold边界检查：负数阈值应抛出ValueError。"""
        # 创建3根后续K线
        post_klines = self._create_klines("BTCUSDT", "4h", 3)

        with self.assertRaises(ValueError) as context:
            self.analyzer.analyze(
                trigger_volume=Decimal("8000.00"),
                post_klines=post_klines,
                retention_threshold=-10.0,  # 异常：负数
            )

        self.assertIn("retention_threshold参数边界错误", str(context.exception))

    def test_guard_clause_retention_threshold_too_large(self):
        """测试retention_threshold边界检查：大于100应抛出ValueError。"""
        # 创建3根后续K线
        post_klines = self._create_klines("BTCUSDT", "4h", 3)

        with self.assertRaises(ValueError) as context:
            self.analyzer.analyze(
                trigger_volume=Decimal("8000.00"),
                post_klines=post_klines,
                retention_threshold=150.0,  # 异常：>100
            )

        self.assertIn("retention_threshold参数边界错误", str(context.exception))
        self.assertIn("预期范围=(0, 100]", str(context.exception))

    def _create_klines(self, symbol: str, interval: str, count: int, base_volume: float = 1000.0):
        """辅助方法：创建测试用K线数据。"""
        now = timezone.now()
        interval_hours = {"1h": 1, "4h": 4, "1d": 24}.get(interval, 4)
        klines = []

        for i in range(count):
            open_time = now - timedelta(hours=interval_hours * (count - i))
            kline = KLine.objects.create(
                symbol=symbol,
                interval=interval,
                open_time=open_time,
                close_time=open_time + timedelta(hours=interval_hours),
                open_price=Decimal("50000.00"),
                high_price=Decimal("51000.00"),
                low_price=Decimal("49000.00"),
                close_price=Decimal("50500.00"),
                volume=Decimal(str(base_volume)),
                quote_volume=Decimal(str(base_volume * 50000.0)),
            )
            klines.append(kline)

        return klines


class VolumeRetentionAnalyzerAccuracyTest(TestCase):
    """测试留存率计算准确性。

    验证留存率、平均成交量的计算是否正确。
    """

    def setUp(self):
        """测试前准备：创建测试用合约数据。"""
        self.exchange = Exchange.objects.create(
            name="Binance Test", code="binance_test", enabled=True
        )

        self.contract = FuturesContract.objects.create(
            exchange=self.exchange,
            symbol="TESTUSDT",
            contract_type="perpetual",
            status="active",
            current_price=Decimal("100.00"),
            first_seen=timezone.now(),
        )
        self.analyzer = VolumeRetentionAnalyzer()

    def test_retention_calculation_accuracy_normal_case(self):
        """测试正常情况下的留存率计算准确性。

        场景：
        - 触发成交量 = 8000
        - 后续3根K线成交量 = [1000, 1000, 1000]
        - 平均成交量 = 1000
        - 预期留存率 = 1000 / 8000 × 100 = 12.5%
        """
        # 创建3根后续K线，成交量均为1000
        post_klines = self._create_klines_with_volumes(
            symbol="TESTUSDT", interval="4h", volumes=[1000.0, 1000.0, 1000.0]
        )

        # 执行计算
        result = self.analyzer.analyze(
            trigger_volume=Decimal("8000.00"), post_klines=post_klines, retention_threshold=15.0
        )

        # 验证平均成交量 = 1000
        expected_avg_volume = 1000.0
        actual_avg_volume = float(result["avg_volume_post"])
        self.assertAlmostEqual(
            actual_avg_volume,
            expected_avg_volume,
            delta=0.01,
            msg=f"平均成交量计算误差: expected={expected_avg_volume}, actual={actual_avg_volume}",
        )

        # 验证留存率 = 12.5%
        expected_retention = 12.5
        actual_retention = float(result["retention_ratio"])
        self.assertAlmostEqual(
            actual_retention,
            expected_retention,
            delta=0.01,
            msg=f"留存率计算误差: expected={expected_retention}, actual={actual_retention}",
        )

        # 验证触发状态（12.5% < 15%，应该触发）
        self.assertTrue(result["triggered"], "留存率=12.5% < 15%应该触发")

    def test_retention_calculation_with_5_klines(self):
        """测试使用5根K线计算留存率。

        场景：
        - 触发成交量 = 10000
        - 后续5根K线成交量 = [1200, 1000, 800, 1100, 900]
        - 平均成交量 = (1200+1000+800+1100+900)/5 = 1000
        - 预期留存率 = 1000 / 10000 × 100 = 10%
        """
        # 创建5根后续K线
        post_klines = self._create_klines_with_volumes(
            symbol="TESTUSDT", interval="4h", volumes=[1200.0, 1000.0, 800.0, 1100.0, 900.0]
        )

        # 执行计算
        result = self.analyzer.analyze(
            trigger_volume=Decimal("10000.00"), post_klines=post_klines, retention_threshold=15.0
        )

        # 验证平均成交量 = 1000
        expected_avg_volume = 1000.0
        actual_avg_volume = float(result["avg_volume_post"])
        self.assertAlmostEqual(
            actual_avg_volume,
            expected_avg_volume,
            delta=0.01,
            msg=f"平均成交量计算误差: expected={expected_avg_volume}, actual={actual_avg_volume}",
        )

        # 验证留存率 = 10%
        expected_retention = 10.0
        actual_retention = float(result["retention_ratio"])
        self.assertAlmostEqual(
            actual_retention,
            expected_retention,
            delta=0.01,
            msg=f"留存率计算误差: expected={expected_retention}, actual={actual_retention}",
        )

        # 验证K线数量
        self.assertEqual(result["post_kline_count"], 5)

    def test_retention_calculation_with_3_klines(self):
        """测试使用最小数量（3根）K线计算留存率。

        场景：
        - 触发成交量 = 5000
        - 后续3根K线成交量 = [500, 600, 700]
        - 平均成交量 = (500+600+700)/3 = 600
        - 预期留存率 = 600 / 5000 × 100 = 12%
        """
        # 创建3根后续K线
        post_klines = self._create_klines_with_volumes(
            symbol="TESTUSDT", interval="4h", volumes=[500.0, 600.0, 700.0]
        )

        # 执行计算
        result = self.analyzer.analyze(
            trigger_volume=Decimal("5000.00"), post_klines=post_klines, retention_threshold=15.0
        )

        # 验证平均成交量 = 600
        expected_avg_volume = 600.0
        actual_avg_volume = float(result["avg_volume_post"])
        self.assertAlmostEqual(actual_avg_volume, expected_avg_volume, delta=0.01)

        # 验证留存率 = 12%
        expected_retention = 12.0
        actual_retention = float(result["retention_ratio"])
        self.assertAlmostEqual(actual_retention, expected_retention, delta=0.01)

        # 验证K线数量
        self.assertEqual(result["post_kline_count"], 3)

    def test_triggered_condition_below_threshold(self):
        """测试触发条件：留存率<15%，应触发。"""
        # 留存率 = 10% < 15%
        post_klines = self._create_klines_with_volumes(
            symbol="TESTUSDT", interval="4h", volumes=[1000.0, 1000.0, 1000.0]
        )

        result = self.analyzer.analyze(
            trigger_volume=Decimal("10000.00"),  # 留存率 = 1000/10000*100 = 10%
            post_klines=post_klines,
            retention_threshold=15.0,
        )

        self.assertTrue(result["triggered"], "留存率=10% < 15%应该触发")

    def test_not_triggered_condition_above_threshold(self):
        """测试触发条件：留存率>=15%，不应触发。"""
        # 留存率 = 20% > 15%
        post_klines = self._create_klines_with_volumes(
            symbol="TESTUSDT", interval="4h", volumes=[1000.0, 1000.0, 1000.0]
        )

        result = self.analyzer.analyze(
            trigger_volume=Decimal("5000.00"),  # 留存率 = 1000/5000*100 = 20%
            post_klines=post_klines,
            retention_threshold=15.0,
        )

        self.assertFalse(result["triggered"], "留存率=20% > 15%不应触发")

    def _create_klines_with_volumes(self, symbol: str, interval: str, volumes: list):
        """辅助方法：根据指定成交量列表创建K线数据。"""
        now = timezone.now()
        interval_hours = {"1h": 1, "4h": 4, "1d": 24}.get(interval, 4)
        klines = []

        for i, volume in enumerate(volumes):
            open_time = now - timedelta(hours=interval_hours * (len(volumes) - i))
            kline = KLine.objects.create(
                symbol=symbol,
                interval=interval,
                open_time=open_time,
                close_time=open_time + timedelta(hours=interval_hours),
                open_price=Decimal("100.00"),
                high_price=Decimal("110.00"),
                low_price=Decimal("95.00"),
                close_price=Decimal("105.00"),
                volume=Decimal(str(volume)),
                quote_volume=Decimal(str(volume * 105.0)),
            )
            klines.append(kline)

        return klines


class VolumeRetentionAnalyzerBoundaryTest(TestCase):
    """测试VolumeRetentionAnalyzer的边界条件。"""

    def setUp(self):
        """测试前准备。"""
        self.exchange = Exchange.objects.create(
            name="Binance Boundary", code="binance_boundary", enabled=True
        )

        self.contract = FuturesContract.objects.create(
            exchange=self.exchange,
            symbol="BOUNDARYUSDT",
            contract_type="perpetual",
            status="active",
            current_price=Decimal("100.00"),
            first_seen=timezone.now(),
        )
        self.analyzer = VolumeRetentionAnalyzer()

    def test_boundary_retention_equals_threshold(self):
        """测试留存率恰好等于阈值的情况。

        验证 "<" 判断逻辑是否正确（留存率=15%不应触发）。
        """
        # 留存率 = 15% (恰好等于阈值)
        post_klines = self._create_klines_with_volumes(
            symbol="BOUNDARYUSDT", interval="4h", volumes=[1500.0, 1500.0, 1500.0]
        )

        result = self.analyzer.analyze(
            trigger_volume=Decimal("10000.00"),  # 留存率 = 1500/10000*100 = 15%
            post_klines=post_klines,
            retention_threshold=15.0,
        )

        # 留存率=15%，threshold=15%，不应触发（<）
        self.assertFalse(result["triggered"], "留存率=15%不应触发（threshold=15%）")

    def test_boundary_minimal_klines(self):
        """测试最小K线数量（恰好3根）。"""
        # 恰好3根K线
        post_klines = self._create_klines("BOUNDARYUSDT", "4h", 3, base_volume=1000.0)

        result = self.analyzer.analyze(
            trigger_volume=Decimal("10000.00"), post_klines=post_klines, retention_threshold=15.0
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["post_kline_count"], 3)

    def test_boundary_maximal_klines(self):
        """测试超过5根K线的情况（只使用前5根）。"""
        # 创建7根K线，但只使用前5根
        post_klines = self._create_klines_with_volumes(
            symbol="BOUNDARYUSDT",
            interval="4h",
            volumes=[1000.0, 1100.0, 900.0, 1200.0, 800.0, 1300.0, 700.0],
        )

        result = self.analyzer.analyze(
            trigger_volume=Decimal("10000.00"), post_klines=post_klines, retention_threshold=15.0
        )

        # 验证只使用了前5根K线
        self.assertEqual(result["post_kline_count"], 5)

        # 验证平均成交量 = (1000+1100+900+1200+800)/5 = 1000
        expected_avg_volume = 1000.0
        actual_avg_volume = float(result["avg_volume_post"])
        self.assertAlmostEqual(actual_avg_volume, expected_avg_volume, delta=0.01)

    def test_custom_retention_threshold(self):
        """测试自定义阈值参数。

        验证threshold参数覆盖配置默认值的功能。
        """
        # 留存率 = 10%
        post_klines = self._create_klines_with_volumes(
            symbol="BOUNDARYUSDT", interval="4h", volumes=[1000.0, 1000.0, 1000.0]
        )

        # 测试1：阈值=8%，应该不触发
        result = self.analyzer.analyze(
            trigger_volume=Decimal("10000.00"),  # 留存率 = 10%
            post_klines=post_klines,
            retention_threshold=8.0,
        )
        self.assertFalse(result["triggered"], "留存率=10% > 8%，不应触发")

        # 测试2：阈值=12%，应该触发
        result = self.analyzer.analyze(
            trigger_volume=Decimal("10000.00"),  # 留存率 = 10%
            post_klines=post_klines,
            retention_threshold=12.0,
        )
        self.assertTrue(result["triggered"], "留存率=10% < 12%，应该触发")

    def _create_klines(self, symbol: str, interval: str, count: int, base_volume: float):
        """辅助方法：创建K线数据。"""
        now = timezone.now()
        interval_hours = {"1h": 1, "4h": 4, "1d": 24}.get(interval, 4)
        klines = []

        for i in range(count):
            open_time = now - timedelta(hours=interval_hours * (count - i))
            kline = KLine.objects.create(
                symbol=symbol,
                interval=interval,
                open_time=open_time,
                close_time=open_time + timedelta(hours=interval_hours),
                open_price=Decimal("100.00"),
                high_price=Decimal("110.00"),
                low_price=Decimal("95.00"),
                close_price=Decimal("105.00"),
                volume=Decimal(str(base_volume)),
                quote_volume=Decimal(str(base_volume * 105.0)),
            )
            klines.append(kline)

        return klines

    def _create_klines_with_volumes(self, symbol: str, interval: str, volumes: list):
        """辅助方法：根据指定成交量列表创建K线数据。"""
        now = timezone.now()
        interval_hours = {"1h": 1, "4h": 4, "1d": 24}.get(interval, 4)
        klines = []

        for i, volume in enumerate(volumes):
            open_time = now - timedelta(hours=interval_hours * (len(volumes) - i))
            kline = KLine.objects.create(
                symbol=symbol,
                interval=interval,
                open_time=open_time,
                close_time=open_time + timedelta(hours=interval_hours),
                open_price=Decimal("100.00"),
                high_price=Decimal("110.00"),
                low_price=Decimal("95.00"),
                close_price=Decimal("105.00"),
                volume=Decimal(str(volume)),
                quote_volume=Decimal(str(volume * 105.0)),
            )
            klines.append(kline)

        return klines


if __name__ == "__main__":
    unittest.main()
