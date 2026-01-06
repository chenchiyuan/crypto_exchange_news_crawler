"""
OBVDivergenceAnalyzer单元测试

测试OBV背离分析器的所有功能，包括：
- Guard Clauses异常路径
- OBV计算准确性
- 底背离检测准确性
- 单边下滑判断准确性
- 边界条件

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md
    - Task: TASK-002-016
"""

import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from backtest.models import KLine
from monitor.models import Exchange, FuturesContract
from volume_trap.detectors.obv_divergence_analyzer import OBVDivergenceAnalyzer
from volume_trap.exceptions import DataInsufficientError


class OBVDivergenceAnalyzerGuardClausesTest(TestCase):
    """测试OBVDivergenceAnalyzer的Guard Clauses异常路径。

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
        self.analyzer = OBVDivergenceAnalyzer(lookback_period=30, divergence_window=5)

    def test_guard_clause_insufficient_klines(self):
        """测试K线数量检查：少于30根应抛出DataInsufficientError。"""
        # 只创建20根K线（需要至少30根）
        klines = self._create_klines("BTCUSDT", "4h", 20)

        with self.assertRaises(DataInsufficientError) as context:
            self.analyzer.analyze(klines=klines)

        exc = context.exception
        self.assertEqual(exc.required, 30)
        self.assertEqual(exc.actual, 20)

    def _create_klines(
        self,
        symbol: str,
        interval: str,
        count: int,
        base_price: float = 50000.0,
        base_volume: float = 1000.0,
    ):
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
                open_price=Decimal(str(base_price)),
                high_price=Decimal(str(base_price + 1000)),
                low_price=Decimal(str(base_price - 1000)),
                close_price=Decimal(str(base_price)),
                volume=Decimal(str(base_volume)),
                quote_volume=Decimal(str(base_volume * base_price)),
            )
            klines.append(kline)

        return klines


class OBVDivergenceAnalyzerAccuracyTest(TestCase):
    """测试OBV计算和背离检测准确性。

    验证OBV计算公式、底背离检测、单边下滑判断是否正确。
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
        self.analyzer = OBVDivergenceAnalyzer(lookback_period=10, divergence_window=5)

    def test_obv_calculation_accuracy_rising_prices(self):
        """测试OBV计算准确性（价格上涨场景）。

        场景：
        - 10根K线，价格从100连续上涨到109
        - volume全部为1000
        - 预期OBV持续上升
        """
        # 创建10根K线，价格从100到109（每根+1）
        prices = [100.0 + i for i in range(10)]
        klines = self._create_klines_with_prices(
            symbol="TESTUSDT", interval="4h", count=10, prices=prices, volume=1000.0
        )

        result = self.analyzer.analyze(klines=klines)

        # 验证OBV序列长度
        self.assertEqual(len(result["obv_series"]), 10)

        # 验证OBV计算：价格上涨时，OBV应累加volume
        # OBV[0] = 0（第一根K线）
        # OBV[1] = 0 + 1000 × 1 = 1000（价格上涨）
        # OBV[2] = 1000 + 1000 × 1 = 2000
        # ...
        # OBV[9] = 8000
        expected_obv = [0.0, 1000.0, 2000.0, 3000.0, 4000.0, 5000.0, 6000.0, 7000.0, 8000.0, 9000.0]

        for i, expected in enumerate(expected_obv):
            actual = float(result["obv_series"][i])
            self.assertAlmostEqual(
                actual,
                expected,
                delta=0.01,
                msg=f"OBV[{i}]计算误差: expected={expected}, actual={actual}",
            )

        # 验证当前OBV值
        self.assertAlmostEqual(float(result["obv_current"]), 9000.0, delta=0.01)

    def test_obv_calculation_accuracy_falling_prices(self):
        """测试OBV计算准确性（价格下跌场景）。

        场景：
        - 10根K线，价格从100连续下跌到91
        - volume全部为1000
        - 预期OBV持续下降
        """
        # 创建10根K线，价格从100到91（每根-1）
        prices = [100.0 - i for i in range(10)]
        klines = self._create_klines_with_prices(
            symbol="TESTUSDT", interval="4h", count=10, prices=prices, volume=1000.0
        )

        result = self.analyzer.analyze(klines=klines)

        # 验证OBV计算：价格下跌时，OBV应减去volume
        # OBV[0] = 0
        # OBV[1] = 0 + 1000 × (-1) = -1000
        # OBV[2] = -1000 + 1000 × (-1) = -2000
        # ...
        # OBV[9] = -9000
        expected_obv = [
            0.0,
            -1000.0,
            -2000.0,
            -3000.0,
            -4000.0,
            -5000.0,
            -6000.0,
            -7000.0,
            -8000.0,
            -9000.0,
        ]

        for i, expected in enumerate(expected_obv):
            actual = float(result["obv_series"][i])
            self.assertAlmostEqual(
                actual,
                expected,
                delta=0.01,
                msg=f"OBV[{i}]计算误差: expected={expected}, actual={actual}",
            )

    def test_obv_calculation_with_flat_prices(self):
        """测试OBV计算准确性（价格平盘场景）。

        场景：
        - 10根K线，价格全部为100
        - volume全部为1000
        - 预期OBV保持0（无变化）
        """
        # 创建10根K线，价格全部为100
        prices = [100.0] * 10
        klines = self._create_klines_with_prices(
            symbol="TESTUSDT", interval="4h", count=10, prices=prices, volume=1000.0
        )

        result = self.analyzer.analyze(klines=klines)

        # 验证OBV全部为0（平盘时sign=0，OBV不变）
        expected_obv = [0.0] * 10

        for i, expected in enumerate(expected_obv):
            actual = float(result["obv_series"][i])
            self.assertAlmostEqual(
                actual,
                expected,
                delta=0.01,
                msg=f"OBV[{i}]计算误差: expected={expected}, actual={actual}",
            )

    def test_bottom_divergence_detection(self):
        """测试底背离检测准确性。

        场景（正确的底背离模式）：
        - 检测窗口：最后5根K线（klines 5-9）
        - 关键：OBV最低点在kline 6，价格最低点在kline 9
        - Kline 4: close=102 (为kline 5提供基准)
        - Kline 5: close=100 (跌), OBV=-5000
        - Kline 6: close=98 (跌), OBV=-6000 【OBV最低点】
        - Kline 7: close=99 (涨), OBV=-5000
        - Kline 8: close=99 (平), OBV=-5000
        - Kline 9: close=97 (跌), OBV=-5500 【价格最低点,但OBV > -6000】
        - 底背离：price_min=97在kline9, obv_min=-6000在kline6
        """
        klines = []
        now = timezone.now()

        # Klines 0-3: 填充数据（4根）
        base_prices = [106.0, 105.0, 104.0, 103.0]
        for i, price in enumerate(base_prices):
            open_time = now - timedelta(hours=4 * (10 - i))
            kline = KLine.objects.create(
                symbol="TESTUSDT",
                interval="4h",
                open_time=open_time,
                close_time=open_time + timedelta(hours=4),
                open_price=Decimal(str(price)),
                high_price=Decimal(str(price + 1)),
                low_price=Decimal(str(price - 1)),
                close_price=Decimal(str(price)),
                volume=Decimal("1000.00"),
                quote_volume=Decimal(str(price * 1000.0)),
            )
            klines.append(kline)

        # Kline 4: close=102 (为kline 5提供对比基准)
        kline = KLine.objects.create(
            symbol="TESTUSDT",
            interval="4h",
            open_time=now - timedelta(hours=4 * 6),
            close_time=now - timedelta(hours=4 * 5),
            open_price=Decimal("103.00"),
            high_price=Decimal("103.00"),
            low_price=Decimal("102.00"),
            close_price=Decimal("102.00"),
            volume=Decimal("1000.00"),
            quote_volume=Decimal("102000.00"),
        )
        klines.append(kline)

        # Klines 5-9: 检测窗口，设计底背离模式

        # Kline 5: close=100 (从102跌), volume=1000, OBV-=1000
        kline = KLine.objects.create(
            symbol="TESTUSDT",
            interval="4h",
            open_time=now - timedelta(hours=4 * 5),
            close_time=now - timedelta(hours=4 * 4),
            open_price=Decimal("102.00"),
            high_price=Decimal("102.00"),
            low_price=Decimal("100.00"),
            close_price=Decimal("100.00"),
            volume=Decimal("1000.00"),
            quote_volume=Decimal("100000.00"),
        )
        klines.append(kline)

        # Kline 6: close=98 (从100跌), volume=1000, OBV-=1000 【OBV最低点】
        kline = KLine.objects.create(
            symbol="TESTUSDT",
            interval="4h",
            open_time=now - timedelta(hours=4 * 4),
            close_time=now - timedelta(hours=4 * 3),
            open_price=Decimal("100.00"),
            high_price=Decimal("100.00"),
            low_price=Decimal("98.00"),
            close_price=Decimal("98.00"),
            volume=Decimal("1000.00"),
            quote_volume=Decimal("98000.00"),
        )
        klines.append(kline)

        # Kline 7: close=99 (从98涨), volume=1000, OBV+=1000
        kline = KLine.objects.create(
            symbol="TESTUSDT",
            interval="4h",
            open_time=now - timedelta(hours=4 * 3),
            close_time=now - timedelta(hours=4 * 2),
            open_price=Decimal("98.00"),
            high_price=Decimal("99.00"),
            low_price=Decimal("98.00"),
            close_price=Decimal("99.00"),
            volume=Decimal("1000.00"),
            quote_volume=Decimal("99000.00"),
        )
        klines.append(kline)

        # Kline 8: close=99 (平盘), volume=1000, OBV+=0
        kline = KLine.objects.create(
            symbol="TESTUSDT",
            interval="4h",
            open_time=now - timedelta(hours=4 * 2),
            close_time=now - timedelta(hours=4 * 1),
            open_price=Decimal("99.00"),
            high_price=Decimal("99.00"),
            low_price=Decimal("99.00"),
            close_price=Decimal("99.00"),
            volume=Decimal("1000.00"),
            quote_volume=Decimal("99000.00"),
        )
        klines.append(kline)

        # Kline 9: close=97 (从99跌), volume=500, OBV-=500 【价格最低点】
        kline = KLine.objects.create(
            symbol="TESTUSDT",
            interval="4h",
            open_time=now - timedelta(hours=4 * 1),
            close_time=now,
            open_price=Decimal("99.00"),
            high_price=Decimal("99.00"),
            low_price=Decimal("97.00"),
            close_price=Decimal("97.00"),
            volume=Decimal("500.00"),
            quote_volume=Decimal("48500.00"),
        )
        klines.append(kline)

        result = self.analyzer.analyze(klines=klines)

        # 打印调试信息
        print(f"\n=== 底背离检测调试 ===")
        print(f"OBV序列: {[float(obv) for obv in result['obv_series']]}")
        print(f"当前OBV: {float(result['obv_current'])}")
        print(f"底背离检测: {result['divergence_detected']}")

        # 验证是否检测到底背离
        # 在klines 5-9窗口中：
        # - 价格最低=97 (kline 9)
        # - OBV最低应该在kline 6 (值为-6000)
        # - kline 9的OBV应该=-5500，高于-6000
        self.assertTrue(result["divergence_detected"], "应检测到底背离")

    def test_single_side_decline_detection(self):
        """测试单边下滑检测准确性。

        场景：
        - 10根K线，价格从100持续跌到91
        - volume全部为1000，OBV同步下滑
        - 预期：连续10根无底背离，触发单边下滑
        """
        # 创建10根K线，价格持续下跌，volume一致
        prices = [100.0 - i for i in range(10)]
        klines = self._create_klines_with_prices(
            symbol="TESTUSDT", interval="4h", count=10, prices=prices, volume=1000.0
        )

        result = self.analyzer.analyze(klines=klines)

        # 验证单边下滑
        self.assertTrue(result["single_side_decline"], "应检测到单边下滑")
        self.assertGreaterEqual(result["consecutive_no_divergence"], 5, "连续无底背离数量应≥5")

    def test_no_single_side_decline_with_divergence(self):
        """测试有底背离时不触发单边下滑。

        场景（与test_bottom_divergence_detection相同，复用底背离模式）：
        - 应检测到底背离，不触发单边下滑
        """
        klines = []
        now = timezone.now()

        # Klines 0-3: 填充数据（4根）
        base_prices = [106.0, 105.0, 104.0, 103.0]
        for i, price in enumerate(base_prices):
            open_time = now - timedelta(hours=4 * (10 - i))
            kline = KLine.objects.create(
                symbol="TESTUSDT",
                interval="4h",
                open_time=open_time,
                close_time=open_time + timedelta(hours=4),
                open_price=Decimal(str(price)),
                high_price=Decimal(str(price + 1)),
                low_price=Decimal(str(price - 1)),
                close_price=Decimal(str(price)),
                volume=Decimal("1000.00"),
                quote_volume=Decimal(str(price * 1000.0)),
            )
            klines.append(kline)

        # Kline 4: close=102
        kline = KLine.objects.create(
            symbol="TESTUSDT",
            interval="4h",
            open_time=now - timedelta(hours=4 * 6),
            close_time=now - timedelta(hours=4 * 5),
            open_price=Decimal("103.00"),
            high_price=Decimal("103.00"),
            low_price=Decimal("102.00"),
            close_price=Decimal("102.00"),
            volume=Decimal("1000.00"),
            quote_volume=Decimal("102000.00"),
        )
        klines.append(kline)

        # Klines 5-9: 底背离模式（与test_bottom_divergence_detection相同）
        divergence_data = [
            ("102.00", "100.00", "1000.00"),  # kline 5
            ("100.00", "98.00", "1000.00"),  # kline 6: OBV最低点
            ("98.00", "99.00", "1000.00"),  # kline 7
            ("99.00", "99.00", "1000.00"),  # kline 8
            ("99.00", "97.00", "500.00"),  # kline 9: 价格最低点
        ]

        for i, (open_p, close_p, vol) in enumerate(divergence_data):
            idx = 5 + i
            open_time = now - timedelta(hours=4 * (9 - idx))
            kline = KLine.objects.create(
                symbol="TESTUSDT",
                interval="4h",
                open_time=open_time,
                close_time=open_time + timedelta(hours=4),
                open_price=Decimal(open_p),
                high_price=max(Decimal(open_p), Decimal(close_p)) + Decimal("1.00"),
                low_price=min(Decimal(open_p), Decimal(close_p)) - Decimal("1.00"),
                close_price=Decimal(close_p),
                volume=Decimal(vol),
                quote_volume=Decimal(close_p) * Decimal(vol),
            )
            klines.append(kline)

        result = self.analyzer.analyze(klines=klines)

        # 验证底背离已检测到
        self.assertTrue(result["divergence_detected"], "应检测到底背离")

        # 验证不触发单边下滑（因为检测到底背离）
        self.assertFalse(result["single_side_decline"], "有底背离时不应触发单边下滑")

    def _create_klines_with_prices(
        self, symbol: str, interval: str, count: int, prices: list, volume: float
    ):
        """辅助方法：根据指定价格和成交量创建K线数据。"""
        now = timezone.now()
        interval_hours = {"1h": 1, "4h": 4, "1d": 24}.get(interval, 4)
        klines = []

        for i, price in enumerate(prices):
            open_time = now - timedelta(hours=interval_hours * (count - i))
            kline = KLine.objects.create(
                symbol=symbol,
                interval=interval,
                open_time=open_time,
                close_time=open_time + timedelta(hours=interval_hours),
                open_price=Decimal(str(price)),
                high_price=Decimal(str(price + 1)),
                low_price=Decimal(str(price - 1)),
                close_price=Decimal(str(price)),
                volume=Decimal(str(volume)),
                quote_volume=Decimal(str(volume * price)),
            )
            klines.append(kline)

        return klines


class OBVDivergenceAnalyzerBoundaryTest(TestCase):
    """测试OBVDivergenceAnalyzer的边界条件。"""

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
        self.analyzer = OBVDivergenceAnalyzer(lookback_period=10, divergence_window=5)

    def test_minimal_klines(self):
        """测试最小K线数量（恰好10根）。"""
        # 恰好10根K线
        klines = self._create_klines("BOUNDARYUSDT", "4h", 10, base_price=100.0)

        result = self.analyzer.analyze(klines=klines)

        # 验证返回结果不为空
        self.assertIsNotNone(result)
        self.assertIn("obv_series", result)
        self.assertIn("obv_current", result)
        self.assertIn("divergence_detected", result)
        self.assertIn("single_side_decline", result)
        self.assertEqual(len(result["obv_series"]), 10)

    def test_more_than_required_klines(self):
        """测试超过10根K线的情况（使用所有数据）。"""
        # 创建15根K线
        klines = self._create_klines("BOUNDARYUSDT", "4h", 15, base_price=100.0)

        result = self.analyzer.analyze(klines=klines)

        # 验证返回结果不为空
        self.assertIsNotNone(result)
        self.assertEqual(len(result["obv_series"]), 15)

    def test_custom_divergence_window(self):
        """测试自定义底背离检测窗口参数。"""
        # 自定义窗口：3根K线
        analyzer = OBVDivergenceAnalyzer(lookback_period=10, divergence_window=3)

        # 创建10根K线
        klines = self._create_klines("BOUNDARYUSDT", "4h", 10, base_price=100.0)

        result = analyzer.analyze(klines=klines)

        # 验证返回结果不为空
        self.assertIsNotNone(result)

    def _create_klines(self, symbol: str, interval: str, count: int, base_price: float):
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
                open_price=Decimal(str(base_price)),
                high_price=Decimal(str(base_price + 1)),
                low_price=Decimal(str(base_price - 1)),
                close_price=Decimal(str(base_price)),
                volume=Decimal("1000.00"),
                quote_volume=Decimal(str(base_price * 1000.0)),
            )
            klines.append(kline)

        return klines


if __name__ == "__main__":
    unittest.main()
