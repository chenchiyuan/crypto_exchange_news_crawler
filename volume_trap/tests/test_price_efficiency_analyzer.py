"""
PriceEfficiencyAnalyzer单元测试

测试价差效率分析器的所有功能，包括：
- Guard Clauses异常路径
- 正常计算路径
- 边界条件
- 计算准确性验证

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md
    - Task: TASK-002-014
"""

import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from backtest.models import KLine
from monitor.models import Exchange, FuturesContract
from volume_trap.detectors.price_efficiency_analyzer import PriceEfficiencyAnalyzer
from volume_trap.exceptions import DataInsufficientError


class PriceEfficiencyAnalyzerGuardClausesTest(TestCase):
    """测试PriceEfficiencyAnalyzer的Guard Clauses异常路径。

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
        self.analyzer = PriceEfficiencyAnalyzer()

    def test_guard_clause_efficiency_multiplier_zero(self):
        """测试efficiency_multiplier检查：零倍数应抛出ValueError。"""
        # 创建足够的K线数据
        recent_klines = self._create_klines("BTCUSDT", "1d", 5)
        historical_klines = self._create_klines("BTCUSDT", "1d", 30)

        with self.assertRaises(ValueError) as context:
            self.analyzer.analyze(
                recent_klines=recent_klines,
                historical_klines=historical_klines,
                efficiency_multiplier=0,  # 异常：倍数=0
            )

        self.assertIn("efficiency_multiplier参数边界错误", str(context.exception))
        self.assertIn("预期>0", str(context.exception))

    def test_guard_clause_efficiency_multiplier_negative(self):
        """测试efficiency_multiplier检查：负数倍数应抛出ValueError。"""
        # 创建足够的K线数据
        recent_klines = self._create_klines("BTCUSDT", "1d", 5)
        historical_klines = self._create_klines("BTCUSDT", "1d", 30)

        with self.assertRaises(ValueError) as context:
            self.analyzer.analyze(
                recent_klines=recent_klines,
                historical_klines=historical_klines,
                efficiency_multiplier=-1.0,  # 异常：负数
            )

        self.assertIn("efficiency_multiplier参数边界错误", str(context.exception))

    def test_guard_clause_insufficient_historical_data(self):
        """测试历史数据完整性检查：历史K线不足30根应抛出DataInsufficientError。"""
        # 创建足够的当前K线，但历史K线不足
        recent_klines = self._create_klines("BTCUSDT", "1d", 5)
        historical_klines = self._create_klines("BTCUSDT", "1d", 20)  # 只有20根（需要30根）

        with self.assertRaises(DataInsufficientError) as context:
            self.analyzer.analyze(recent_klines=recent_klines, historical_klines=historical_klines)

        exc = context.exception
        self.assertEqual(exc.required, 30)
        self.assertEqual(exc.actual, 20)

    def _create_klines(self, symbol: str, interval: str, count: int, base_volume: float = 1000.0):
        """辅助方法：创建测试用K线数据。"""
        now = timezone.now()
        interval_hours = {"1h": 1, "4h": 4, "1d": 24}.get(interval, 24)
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


class PriceEfficiencyAnalyzerAccuracyTest(TestCase):
    """测试PE计算准确性。

    验证PE、历史均值的计算是否正确。
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
        self.analyzer = PriceEfficiencyAnalyzer()

    def test_pe_calculation_accuracy_normal_case(self):
        """测试正常情况下的PE计算准确性。

        场景：
        - 历史30根K线：open=100, close=101, volume=1000
        - PE = |101-100|/1000 = 0.001
        - 历史PE均值 = 0.001
        - 当前5根K线：open=100, close=103, volume=1000
        - PE = |103-100|/1000 = 0.003
        - 当前PE = 0.003
        - 触发条件：0.003 > 0.001 × 2 = 0.002（应触发）
        """
        # 创建30根历史K线：PE = 0.001
        historical_klines = self._create_klines_with_prices(
            symbol="TESTUSDT", interval="1d", count=30, open=100.0, close=101.0, volume=1000.0
        )

        # 创建5根当前K线：PE = 0.003
        recent_klines = self._create_klines_with_prices(
            symbol="TESTUSDT", interval="1d", count=5, open=100.0, close=103.0, volume=1000.0
        )

        # 执行计算
        result = self.analyzer.analyze(
            recent_klines=recent_klines,
            historical_klines=historical_klines,
            efficiency_multiplier=2.0,
        )

        # 验证历史PE均值 = 0.001
        expected_historical_pe = 0.001
        actual_historical_pe = float(result["historical_pe_mean"])
        self.assertAlmostEqual(
            actual_historical_pe,
            expected_historical_pe,
            delta=0.00001,
            msg=f"历史PE均值计算误差: expected={expected_historical_pe}, actual={actual_historical_pe}",
        )

        # 验证当前PE = 0.003
        expected_current_pe = 0.003
        actual_current_pe = float(result["current_pe"])
        self.assertAlmostEqual(
            actual_current_pe,
            expected_current_pe,
            delta=0.00001,
            msg=f"当前PE计算误差: expected={expected_current_pe}, actual={actual_current_pe}",
        )

        # 验证触发状态（0.003 > 0.001 × 2）
        self.assertTrue(result["triggered"], "PE=0.003 > 0.001×2应该触发")

    def test_pe_calculation_with_price_drop(self):
        """测试价格下跌时的PE计算。

        场景：
        - open=100, close=97, volume=1000
        - PE = |97-100|/1000 = 0.003
        """
        # 历史K线：PE = 0.001
        historical_klines = self._create_klines_with_prices(
            symbol="TESTUSDT", interval="1d", count=30, open=100.0, close=101.0, volume=1000.0
        )

        # 当前K线：价格下跌，PE = 0.003
        recent_klines = self._create_klines_with_prices(
            symbol="TESTUSDT",
            interval="1d",
            count=5,
            open=100.0,
            close=97.0,  # 下跌3个点
            volume=1000.0,
        )

        result = self.analyzer.analyze(
            recent_klines=recent_klines,
            historical_klines=historical_klines,
            efficiency_multiplier=2.0,
        )

        # 验证PE计算使用绝对值：|97-100|/1000 = 0.003
        expected_current_pe = 0.003
        actual_current_pe = float(result["current_pe"])
        self.assertAlmostEqual(actual_current_pe, expected_current_pe, delta=0.00001)

    def test_triggered_condition_above_threshold(self):
        """测试触发条件：当前PE > 历史PE × 2，应触发。"""
        # 历史PE = 0.001
        historical_klines = self._create_klines_with_prices(
            symbol="TESTUSDT", interval="1d", count=30, open=100.0, close=101.0, volume=1000.0
        )

        # 当前PE = 0.003 > 0.001 × 2
        recent_klines = self._create_klines_with_prices(
            symbol="TESTUSDT", interval="1d", count=5, open=100.0, close=103.0, volume=1000.0
        )

        result = self.analyzer.analyze(
            recent_klines=recent_klines,
            historical_klines=historical_klines,
            efficiency_multiplier=2.0,
        )

        self.assertTrue(result["triggered"], "PE=0.003 > 0.001×2应该触发")

    def test_not_triggered_condition_below_threshold(self):
        """测试触发条件：当前PE <= 历史PE × 2，不应触发。"""
        # 历史PE = 0.001
        historical_klines = self._create_klines_with_prices(
            symbol="TESTUSDT", interval="1d", count=30, open=100.0, close=101.0, volume=1000.0
        )

        # 当前PE = 0.0015 < 0.001 × 2
        recent_klines = self._create_klines_with_prices(
            symbol="TESTUSDT", interval="1d", count=5, open=100.0, close=101.5, volume=1000.0
        )

        result = self.analyzer.analyze(
            recent_klines=recent_klines,
            historical_klines=historical_klines,
            efficiency_multiplier=2.0,
        )

        self.assertFalse(result["triggered"], "PE=0.0015 < 0.001×2不应触发")

    def _create_klines_with_prices(
        self, symbol: str, interval: str, count: int, open: float, close: float, volume: float
    ):
        """辅助方法：根据指定价格和成交量创建K线数据。"""
        now = timezone.now()
        interval_hours = {"1h": 1, "4h": 4, "1d": 24}.get(interval, 24)
        klines = []

        for i in range(count):
            open_time = now - timedelta(hours=interval_hours * (count - i))
            kline = KLine.objects.create(
                symbol=symbol,
                interval=interval,
                open_time=open_time,
                close_time=open_time + timedelta(hours=interval_hours),
                open_price=Decimal(str(open)),
                high_price=Decimal(str(max(open, close) + 1)),
                low_price=Decimal(str(min(open, close) - 1)),
                close_price=Decimal(str(close)),
                volume=Decimal(str(volume)),
                quote_volume=Decimal(str(volume * close)),
            )
            klines.append(kline)

        return klines


class PriceEfficiencyAnalyzerBoundaryTest(TestCase):
    """测试PriceEfficiencyAnalyzer的边界条件。"""

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
        self.analyzer = PriceEfficiencyAnalyzer()

    def test_volume_zero_handling(self):
        """测试volume=0的K线处理。

        场景：
        - 部分K线volume=0，应跳过这些K线
        - 只计算volume>0的K线的PE
        """
        # 创建30根历史K线，其中10根volume=0
        historical_klines = []
        now = timezone.now()

        for i in range(30):
            volume = 1000.0 if i % 3 != 0 else 0.0  # 每3根有1根volume=0
            kline = KLine.objects.create(
                symbol="BOUNDARYUSDT",
                interval="1d",
                open_time=now - timedelta(days=30 - i),
                close_time=now - timedelta(days=29 - i),
                open_price=Decimal("100.00"),
                high_price=Decimal("102.00"),
                low_price=Decimal("98.00"),
                close_price=Decimal("101.00"),
                volume=Decimal(str(volume)),
                quote_volume=Decimal(str(volume * 101.0)),
            )
            historical_klines.append(kline)

        # 创建5根当前K线，全部volume>0
        recent_klines = self._create_klines_with_prices(
            symbol="BOUNDARYUSDT", interval="1d", count=5, open=100.0, close=103.0, volume=1000.0
        )

        result = self.analyzer.analyze(
            recent_klines=recent_klines,
            historical_klines=historical_klines,
            efficiency_multiplier=2.0,
        )

        # 验证历史K线中只有20根参与计算（跳过10根volume=0）
        self.assertEqual(result["historical_count"], 20)

        # 验证当前K线全部参与计算
        self.assertEqual(result["recent_count"], 5)

    def test_all_volume_zero_historical(self):
        """测试所有历史K线volume=0的情况。

        应返回None（无法计算PE）。
        """
        # 创建30根历史K线，全部volume=0
        historical_klines = self._create_klines_with_prices(
            symbol="BOUNDARYUSDT",
            interval="1d",
            count=30,
            open=100.0,
            close=101.0,
            volume=0.0,  # 全部volume=0
        )

        # 创建5根当前K线
        recent_klines = self._create_klines_with_prices(
            symbol="BOUNDARYUSDT", interval="1d", count=5, open=100.0, close=103.0, volume=1000.0
        )

        result = self.analyzer.analyze(
            recent_klines=recent_klines,
            historical_klines=historical_klines,
            efficiency_multiplier=2.0,
        )

        # 验证返回None（无法计算）
        self.assertIsNone(result)

    def test_all_volume_zero_recent(self):
        """测试所有当前K线volume=0的情况。

        应返回None（无法计算PE）。
        """
        # 创建30根历史K线
        historical_klines = self._create_klines_with_prices(
            symbol="BOUNDARYUSDT", interval="1d", count=30, open=100.0, close=101.0, volume=1000.0
        )

        # 创建5根当前K线，全部volume=0
        recent_klines = self._create_klines_with_prices(
            symbol="BOUNDARYUSDT",
            interval="1d",
            count=5,
            open=100.0,
            close=103.0,
            volume=0.0,  # 全部volume=0
        )

        result = self.analyzer.analyze(
            recent_klines=recent_klines,
            historical_klines=historical_klines,
            efficiency_multiplier=2.0,
        )

        # 验证返回None（无法计算）
        self.assertIsNone(result)

    def test_minimal_historical_data(self):
        """测试最小历史数据量（恰好30根）。"""
        # 恰好30根历史K线
        historical_klines = self._create_klines_with_prices(
            symbol="BOUNDARYUSDT", interval="1d", count=30, open=100.0, close=101.0, volume=1000.0
        )

        # 5根当前K线
        recent_klines = self._create_klines_with_prices(
            symbol="BOUNDARYUSDT", interval="1d", count=5, open=100.0, close=103.0, volume=1000.0
        )

        result = self.analyzer.analyze(
            recent_klines=recent_klines,
            historical_klines=historical_klines,
            efficiency_multiplier=2.0,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["historical_count"], 30)

    def test_custom_efficiency_multiplier(self):
        """测试自定义异常倍数参数。"""
        # 历史PE = 0.001
        historical_klines = self._create_klines_with_prices(
            symbol="BOUNDARYUSDT", interval="1d", count=30, open=100.0, close=101.0, volume=1000.0
        )

        # 当前PE = 0.0025
        recent_klines = self._create_klines_with_prices(
            symbol="BOUNDARYUSDT", interval="1d", count=5, open=100.0, close=102.5, volume=1000.0
        )

        # 测试1：倍数=2，应该触发（0.0025 > 0.001×2）
        result = self.analyzer.analyze(
            recent_klines=recent_klines,
            historical_klines=historical_klines,
            efficiency_multiplier=2.0,
        )
        self.assertTrue(result["triggered"], "PE=0.0025 > 0.001×2应该触发")

        # 测试2：倍数=3，不应触发（0.0025 < 0.001×3）
        result = self.analyzer.analyze(
            recent_klines=recent_klines,
            historical_klines=historical_klines,
            efficiency_multiplier=3.0,
        )
        self.assertFalse(result["triggered"], "PE=0.0025 < 0.001×3不应触发")

    def _create_klines_with_prices(
        self, symbol: str, interval: str, count: int, open: float, close: float, volume: float
    ):
        """辅助方法：根据指定价格和成交量创建K线数据。"""
        now = timezone.now()
        interval_hours = {"1h": 1, "4h": 4, "1d": 24}.get(interval, 24)
        klines = []

        for i in range(count):
            open_time = now - timedelta(hours=interval_hours * (count - i))
            kline = KLine.objects.create(
                symbol=symbol,
                interval=interval,
                open_time=open_time,
                close_time=open_time + timedelta(hours=interval_hours),
                open_price=Decimal(str(open)),
                high_price=Decimal(str(max(open, close) + 1)),
                low_price=Decimal(str(min(open, close) - 1)),
                close_price=Decimal(str(close)),
                volume=Decimal(str(volume)),
                quote_volume=Decimal(str(volume * close)),
            )
            klines.append(kline)

        return klines


if __name__ == "__main__":
    unittest.main()
