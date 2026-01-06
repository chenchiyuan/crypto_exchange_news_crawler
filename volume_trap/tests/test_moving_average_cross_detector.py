"""
MovingAverageCrossDetector单元测试

测试均线交叉检测器的所有功能，包括：
- Guard Clauses异常路径
- 正常计算路径
- 边界条件
- 计算准确性验证

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md
    - Task: TASK-002-015
"""

import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

import pandas as pd

from backtest.models import KLine
from monitor.models import Exchange, FuturesContract
from volume_trap.detectors.moving_average_cross_detector import MovingAverageCrossDetector
from volume_trap.exceptions import DataInsufficientError, InvalidDataError


class MovingAverageCrossDetectorGuardClausesTest(TestCase):
    """测试MovingAverageCrossDetector的Guard Clauses异常路径。

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
        self.detector = MovingAverageCrossDetector()

    def test_guard_clause_insufficient_klines(self):
        """测试K线数量检查：少于26根应抛出DataInsufficientError。"""
        # 只创建20根K线（需要至少26根）
        klines = self._create_klines("BTCUSDT", "4h", 20)

        with self.assertRaises(DataInsufficientError) as context:
            self.detector.detect(klines=klines)

        exc = context.exception
        self.assertEqual(exc.required, 26)
        self.assertEqual(exc.actual, 20)

    def test_guard_clause_ma25_prev_zero(self):
        """测试MA25_prev=0检查：应抛出InvalidDataError（除零错误）。"""
        # 创建26根K线，前25根close_price=0（导致MA25_prev=0）
        klines = []
        now = timezone.now()

        # 前25根：close_price=0
        for i in range(25):
            open_time = now - timedelta(hours=4 * (26 - i))
            kline = KLine.objects.create(
                symbol="BTCUSDT",
                interval="4h",
                open_time=open_time,
                close_time=open_time + timedelta(hours=4),
                open_price=Decimal("0.00"),  # 全为0
                high_price=Decimal("0.00"),
                low_price=Decimal("0.00"),
                close_price=Decimal("0.00"),  # 导致MA25_prev=0
                volume=Decimal("1000.00"),
                quote_volume=Decimal("0.00"),
            )
            klines.append(kline)

        # 最后1根：close_price=50000（导致MA25_current>0）
        open_time = now - timedelta(hours=4)
        kline = KLine.objects.create(
            symbol="BTCUSDT",
            interval="4h",
            open_time=open_time,
            close_time=open_time + timedelta(hours=4),
            open_price=Decimal("50000.00"),
            high_price=Decimal("51000.00"),
            low_price=Decimal("49000.00"),
            close_price=Decimal("50000.00"),
            volume=Decimal("1000.00"),
            quote_volume=Decimal("50000000.00"),
        )
        klines.append(kline)

        with self.assertRaises(InvalidDataError) as context:
            self.detector.detect(klines=klines)

        exc = context.exception
        self.assertEqual(exc.field, "ma25_prev")
        self.assertEqual(exc.value, 0.0)
        self.assertIn("MA25前值为0", exc.context)
        self.assertIn("除零错误", exc.context)

    def _create_klines(self, symbol: str, interval: str, count: int, base_price: float = 50000.0):
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
                volume=Decimal("1000.00"),
                quote_volume=Decimal(str(base_price * 1000.0)),
            )
            klines.append(kline)

        return klines


class MovingAverageCrossDetectorAccuracyTest(TestCase):
    """测试MA计算和死叉判断准确性。

    验证MA(7)、MA(25)、MA25_slope、death_cross的计算是否正确。
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
        self.detector = MovingAverageCrossDetector()

    def test_ma_calculation_accuracy_flat_prices(self):
        """测试MA计算准确性（平盘场景）。

        场景：
        - 26根K线，close_price全部为100
        - 预期MA(7) = 100
        - 预期MA(25) = 100
        - 预期MA25_slope = 0
        """
        # 创建26根K线，close_price=100
        klines = self._create_klines_with_prices(
            symbol="TESTUSDT", interval="4h", count=26, prices=[100.0] * 26
        )

        result = self.detector.detect(klines=klines)

        # 验证MA(7) = 100
        expected_ma7 = 100.0
        actual_ma7 = float(result["ma7"])
        self.assertAlmostEqual(
            actual_ma7,
            expected_ma7,
            delta=0.01,
            msg=f"MA7计算误差: expected={expected_ma7}, actual={actual_ma7}",
        )

        # 验证MA(25) = 100
        expected_ma25 = 100.0
        actual_ma25 = float(result["ma25"])
        self.assertAlmostEqual(
            actual_ma25,
            expected_ma25,
            delta=0.01,
            msg=f"MA25计算误差: expected={expected_ma25}, actual={actual_ma25}",
        )

        # 验证MA25_slope = 0（平盘）
        expected_slope = 0.0
        actual_slope = float(result["ma25_slope"])
        self.assertAlmostEqual(
            actual_slope,
            expected_slope,
            delta=0.01,
            msg=f"MA25斜率计算误差: expected={expected_slope}, actual={actual_slope}",
        )

        # 验证无死叉（MA7 = MA25）
        self.assertFalse(result["death_cross"], "平盘时不应触发死叉")

    def test_ma_calculation_accuracy_rising_prices(self):
        """测试MA计算准确性（上涨场景）。

        场景：
        - 26根K线，close_price从100线性增长到125
        - 验证MA(7)和MA(25)的计算
        - 验证MA25_slope > 0
        """
        # 创建26根K线，价格从100到125
        prices = [100.0 + i for i in range(26)]  # [100, 101, ..., 125]
        klines = self._create_klines_with_prices(
            symbol="TESTUSDT", interval="4h", count=26, prices=prices
        )

        result = self.detector.detect(klines=klines)

        # 验证MA(7) > MA(25)（短期上涨快于长期）
        actual_ma7 = float(result["ma7"])
        actual_ma25 = float(result["ma25"])
        self.assertGreater(actual_ma7, actual_ma25, "上涨趋势中MA7应大于MA25")

        # 验证MA25_slope > 0
        actual_slope = float(result["ma25_slope"])
        self.assertGreater(actual_slope, 0, "上涨趋势中MA25斜率应为正")

        # 验证无死叉（MA7 > MA25）
        self.assertFalse(result["death_cross"], "上涨趋势中不应触发死叉")

    def test_death_cross_detection(self):
        """测试死叉检测准确性。

        场景：
        - 前12根：价格上涨（100-111），MA(7) > MA(25)
        - 后14根：价格下跌（111-97），MA(7) < MA(25), MA25_slope < 0
        - 应触发死叉
        """
        # 前12根：上涨（100-111）
        prices_up = [100.0 + i for i in range(12)]
        # 后14根：下跌（111-97）
        prices_down = [111.0 - i for i in range(14)]
        prices = prices_up + prices_down

        klines = self._create_klines_with_prices(
            symbol="TESTUSDT", interval="4h", count=26, prices=prices
        )

        result = self.detector.detect(klines=klines)

        # 验证MA(7) < MA(25)
        actual_ma7 = float(result["ma7"])
        actual_ma25 = float(result["ma25"])
        self.assertLess(actual_ma7, actual_ma25, "死叉时MA7应小于MA25")

        # 验证MA25_slope < 0
        actual_slope = float(result["ma25_slope"])
        self.assertLess(actual_slope, 0, "死叉时MA25斜率应为负")

        # 验证死叉触发
        self.assertTrue(result["death_cross"], "应触发死叉")

    def _create_klines_with_prices(self, symbol: str, interval: str, count: int, prices: list):
        """辅助方法：根据指定价格列表创建K线数据。"""
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
                volume=Decimal("1000.00"),
                quote_volume=Decimal(str(price * 1000.0)),
            )
            klines.append(kline)

        return klines


class MovingAverageCrossDetectorBoundaryTest(TestCase):
    """测试MovingAverageCrossDetector的边界条件。"""

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
        self.detector = MovingAverageCrossDetector()

    def test_minimal_klines(self):
        """测试最小K线数量（恰好26根）。"""
        # 恰好26根K线
        klines = self._create_klines("BOUNDARYUSDT", "4h", 26, base_price=100.0)

        result = self.detector.detect(klines=klines)

        # 验证返回结果不为空
        self.assertIsNotNone(result)
        self.assertIn("ma7", result)
        self.assertIn("ma25", result)
        self.assertIn("ma25_slope", result)
        self.assertIn("death_cross", result)

    def test_more_than_required_klines(self):
        """测试超过26根K线的情况（使用所有数据）。"""
        # 创建30根K线
        klines = self._create_klines("BOUNDARYUSDT", "4h", 30, base_price=100.0)

        result = self.detector.detect(klines=klines)

        # 验证返回结果不为空
        self.assertIsNotNone(result)

    def test_custom_periods(self):
        """测试自定义均线周期参数。"""
        # 自定义周期：MA(5)和MA(20)
        detector = MovingAverageCrossDetector(short_period=5, long_period=20)

        # 创建21根K线（满足长期周期20+1的要求）
        klines = self._create_klines("BOUNDARYUSDT", "4h", 21, base_price=100.0)

        result = detector.detect(klines=klines)

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
