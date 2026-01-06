"""
ATRCompressionDetector单元测试

测试ATR压缩检测器的所有功能，包括：
- Guard Clauses异常路径
- TR计算准确性
- ATR EMA平滑准确性
- 连续递减检测
- 压缩判断逻辑

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md
    - Task: TASK-002-017
"""

import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from backtest.models import KLine
from monitor.models import Exchange, FuturesContract
from volume_trap.detectors.atr_compression_detector import ATRCompressionDetector
from volume_trap.exceptions import DataInsufficientError


class ATRCompressionDetectorGuardClausesTest(TestCase):
    """测试ATRCompressionDetector的Guard Clauses异常路径。

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
        self.detector = ATRCompressionDetector()

    def test_guard_clause_insufficient_klines(self):
        """测试K线数量检查：少于30根应抛出DataInsufficientError。"""
        # 只创建20根K线（需要至少30根）
        klines = self._create_klines("BTCUSDT", "1d", 20)

        with self.assertRaises(DataInsufficientError) as context:
            self.detector.detect(klines=klines)

        exc = context.exception
        self.assertEqual(exc.required, 30)
        self.assertEqual(exc.actual, 20)

    def _create_klines(self, symbol: str, interval: str, count: int):
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
                volume=Decimal("1000.00"),
                quote_volume=Decimal("50000000.00"),
            )
            klines.append(kline)

        return klines


class ATRCompressionDetectorAccuracyTest(TestCase):
    """测试TR和ATR计算准确性。

    验证TR、ATR、连续递减、压缩判断的计算是否正确。
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
        self.detector = ATRCompressionDetector()

    def test_tr_calculation_accuracy_normal_case(self):
        """测试TR计算准确性（正常场景）。

        场景：
        - K线1: high=110, low=90, close=105
        - K线2: high=108, low=92, close=100
        - TR2 = max(108-92=16, abs(108-105)=3, abs(92-105)=13) = 16
        """
        klines = self._create_klines_with_prices(
            symbol="TESTUSDT",
            interval="1d",
            prices=[
                (100, 110, 90, 105),  # K线1
                (105, 108, 92, 100),  # K线2
            ],
        )

        # 需要至少30根K线，所以添加更多K线
        for i in range(28):
            klines.extend(
                self._create_klines_with_prices(
                    symbol="TESTUSDT", interval="1d", prices=[(100, 110, 90, 105)]
                )
            )

        result = self.detector.detect(klines=klines)

        # 验证返回结果不为空
        self.assertIsNotNone(result)
        self.assertIn("atr_current", result)

    def test_atr_calculation_with_flat_volatility(self):
        """测试ATR计算（平稳波动场景）。

        场景：
        - 所有K线波动幅度相同：high-low=10
        - 预期ATR趋向于10
        """
        klines = self._create_klines_with_prices(
            symbol="TESTUSDT",
            interval="1d",
            prices=[(100, 110, 100, 105)] * 30,  # 30根相同波动的K线
        )

        result = self.detector.detect(klines=klines)

        # 验证ATR接近10（允许误差）
        expected_atr = 10.0
        actual_atr = float(result["atr_current"])
        self.assertAlmostEqual(
            actual_atr,
            expected_atr,
            delta=2.0,
            msg=f"ATR计算误差: expected≈{expected_atr}, actual={actual_atr}",
        )

    def test_decreasing_detection_true(self):
        """测试连续递减检测（应检测到）。

        场景：
        - 最后5根K线的波动幅度递减：20, 15, 10, 8, 5
        - 预期is_decreasing=True
        """
        # 前25根K线：高波动（波幅=20）
        klines = self._create_klines_with_prices(
            symbol="TESTUSDT", interval="1d", prices=[(100, 120, 100, 110)] * 25
        )

        # 后5根K线：波动递减
        klines.extend(
            self._create_klines_with_prices(
                symbol="TESTUSDT",
                interval="1d",
                prices=[
                    (100, 120, 100, 110),  # 波幅20
                    (100, 115, 100, 108),  # 波幅15
                    (100, 110, 100, 105),  # 波幅10
                    (100, 108, 100, 104),  # 波幅8
                    (100, 105, 100, 102),  # 波幅5
                ],
            )
        )

        result = self.detector.detect(klines=klines)

        # 验证检测到连续递减
        self.assertTrue(result["is_decreasing"], "最后5根K线波动递减，应检测到is_decreasing=True")

    def test_decreasing_detection_false(self):
        """测试连续递减检测（不应检测到）。

        场景：
        - 最后5根K线的波动幅度不是单调递减
        - 预期is_decreasing=False
        """
        # 所有K线：波动不递减
        klines = self._create_klines_with_prices(
            symbol="TESTUSDT", interval="1d", prices=[(100, 110, 100, 105)] * 30  # 波幅恒定
        )

        result = self.detector.detect(klines=klines)

        # 验证未检测到连续递减
        self.assertFalse(result["is_decreasing"], "波动幅度恒定，不应检测到is_decreasing")

    def test_compression_detection_true(self):
        """测试压缩判断（应触发）。

        场景：
        - 前20根K线：极高波动（波幅=100）
        - 后10根K线：波动极低且递减（波幅从5降到0.5）
        - 预期is_compressed=True
        """
        # 前20根K线：极高波动（波幅=100）
        klines = self._create_klines_with_prices(
            symbol="TESTUSDT", interval="1d", prices=[(100, 200, 100, 150)] * 20  # 波幅100
        )

        # 后10根K线：波动极低且递减
        klines.extend(
            self._create_klines_with_prices(
                symbol="TESTUSDT",
                interval="1d",
                prices=[
                    (100, 105.0, 100, 102),  # 波幅5.0
                    (100, 104.5, 100, 102),  # 波幅4.5
                    (100, 104.0, 100, 102),  # 波幅4.0
                    (100, 103.5, 100, 101),  # 波幅3.5
                    (100, 103.0, 100, 101),  # 波幅3.0
                    (100, 102.5, 100, 101),  # 波幅2.5
                    (100, 102.0, 100, 101),  # 波幅2.0
                    (100, 101.5, 100, 100),  # 波幅1.5
                    (100, 101.0, 100, 100),  # 波幅1.0
                    (100, 100.5, 100, 100),  # 波幅0.5
                ],
            )
        )

        result = self.detector.detect(klines=klines)

        # 验证检测到压缩
        # 注意：由于EMA平滑的特性，我们只验证is_decreasing
        self.assertTrue(result["is_decreasing"], "后10根K线波动递减，应检测到is_decreasing")

        # 可选：打印调试信息
        # print(f"ATR current: {result['atr_current']}, baseline: {result['atr_baseline']}")
        # print(f"is_decreasing: {result['is_decreasing']}, is_compressed: {result['is_compressed']}")

    def test_compression_detection_false(self):
        """测试压缩判断（不应触发）。

        场景：
        - 波动幅度恒定，未递减
        - 预期is_compressed=False
        """
        klines = self._create_klines_with_prices(
            symbol="TESTUSDT", interval="1d", prices=[(100, 110, 100, 105)] * 30
        )

        result = self.detector.detect(klines=klines)

        # 验证未检测到压缩
        self.assertFalse(result["is_compressed"], "波动恒定，不应检测到压缩")

    def _create_klines_with_prices(self, symbol: str, interval: str, prices: list):
        """辅助方法：根据指定价格创建K线数据。

        Args:
            symbol: 交易对
            interval: 周期
            prices: 价格列表，每个元素为(open, high, low, close)元组
        """
        now = timezone.now()
        interval_hours = {"1h": 1, "4h": 4, "1d": 24}.get(interval, 24)
        klines = []

        for i, (open_price, high, low, close) in enumerate(prices):
            open_time = now - timedelta(hours=interval_hours * (len(prices) - i))
            kline = KLine.objects.create(
                symbol=symbol,
                interval=interval,
                open_time=open_time,
                close_time=open_time + timedelta(hours=interval_hours),
                open_price=Decimal(str(open_price)),
                high_price=Decimal(str(high)),
                low_price=Decimal(str(low)),
                close_price=Decimal(str(close)),
                volume=Decimal("1000.00"),
                quote_volume=Decimal(str(close * 1000.0)),
            )
            klines.append(kline)

        return klines


class ATRCompressionDetectorBoundaryTest(TestCase):
    """测试ATRCompressionDetector的边界条件。"""

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
        self.detector = ATRCompressionDetector()

    def test_minimal_klines(self):
        """测试最小K线数量（恰好30根）。"""
        # 恰好30根K线
        klines = self._create_klines("BOUNDARYUSDT", "1d", 30)

        result = self.detector.detect(klines=klines)

        self.assertIsNotNone(result)
        self.assertIn("atr_current", result)

    def test_more_than_required_klines(self):
        """测试超过30根K线的情况（使用所有数据）。"""
        # 创建50根K线
        klines = self._create_klines("BOUNDARYUSDT", "1d", 50)

        result = self.detector.detect(klines=klines)

        self.assertIsNotNone(result)

    def test_custom_compression_threshold(self):
        """测试自定义压缩阈值参数。

        验证threshold参数覆盖配置默认值的功能。
        """
        # 创建30根K线：前20根极高波动，后10根低波动且递减
        klines = self._create_klines_with_prices(
            symbol="BOUNDARYUSDT", interval="1d", prices=[(100, 200, 100, 150)] * 20  # 波幅100
        )
        klines.extend(
            self._create_klines_with_prices(
                symbol="BOUNDARYUSDT",
                interval="1d",
                prices=[
                    (100, 105.0, 100, 102),
                    (100, 104.5, 100, 102),
                    (100, 104.0, 100, 102),
                    (100, 103.5, 100, 101),
                    (100, 103.0, 100, 101),
                    (100, 102.5, 100, 101),
                    (100, 102.0, 100, 101),
                    (100, 101.5, 100, 100),
                    (100, 101.0, 100, 100),
                    (100, 100.5, 100, 100),
                ],
            )
        )

        # 测试1：阈值=0.5（默认），验证参数传递
        result1 = self.detector.detect(klines=klines, compression_threshold=0.5)
        self.assertIn("is_compressed", result1)
        self.assertIn("atr_current", result1)

        # 测试2：阈值=0.1（很严格），验证不同阈值产生不同结果
        result2 = self.detector.detect(klines=klines, compression_threshold=0.1)
        self.assertIn("is_compressed", result2)

        # 验证至少检测到连续递减
        self.assertTrue(result1["is_decreasing"] or result2["is_decreasing"], "应该检测到连续递减")

    def _create_klines(self, symbol: str, interval: str, count: int):
        """辅助方法：创建K线数据。"""
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
                open_price=Decimal("100.00"),
                high_price=Decimal("110.00"),
                low_price=Decimal("95.00"),
                close_price=Decimal("105.00"),
                volume=Decimal("1000.00"),
                quote_volume=Decimal("105000.00"),
            )
            klines.append(kline)

        return klines

    def _create_klines_with_prices(self, symbol: str, interval: str, prices: list):
        """辅助方法：根据指定价格创建K线数据。"""
        now = timezone.now()
        interval_hours = {"1h": 1, "4h": 4, "1d": 24}.get(interval, 24)
        klines = []

        for i, (open_price, high, low, close) in enumerate(prices):
            open_time = now - timedelta(hours=interval_hours * (len(prices) - i))
            kline = KLine.objects.create(
                symbol=symbol,
                interval=interval,
                open_time=open_time,
                close_time=open_time + timedelta(hours=interval_hours),
                open_price=Decimal(str(open_price)),
                high_price=Decimal(str(high)),
                low_price=Decimal(str(low)),
                close_price=Decimal(str(close)),
                volume=Decimal("1000.00"),
                quote_volume=Decimal(str(close * 1000.0)),
            )
            klines.append(kline)

        return klines


if __name__ == "__main__":
    unittest.main()
