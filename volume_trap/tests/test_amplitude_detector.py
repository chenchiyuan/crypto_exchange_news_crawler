"""
AmplitudeDetector单元测试

测试振幅异常检测器的所有功能，包括：
- Guard Clauses异常路径
- 正常计算路径
- 边界条件
- 计算准确性验证

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md
    - Task: TASK-002-011
"""

import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from backtest.models import KLine
from monitor.models import Exchange, FuturesContract
from volume_trap.detectors.amplitude_detector import AmplitudeDetector
from volume_trap.exceptions import DataInsufficientError, InvalidDataError


class AmplitudeDetectorGuardClausesTest(TestCase):
    """测试AmplitudeDetector的Guard Clauses异常路径。

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
        self.detector = AmplitudeDetector(lookback_period=30)

    def test_guard_clause_lookback_period_too_small(self):
        """测试lookback_period下界检查：小于5应抛出ValueError。"""
        with self.assertRaises(ValueError) as context:
            AmplitudeDetector(lookback_period=3)

        self.assertIn("lookback_period参数边界错误", str(context.exception))
        self.assertIn("预期范围=[5, 100]", str(context.exception))
        self.assertIn("实际值=3", str(context.exception))

    def test_guard_clause_lookback_period_too_large(self):
        """测试lookback_period上界检查：大于100应抛出ValueError。"""
        with self.assertRaises(ValueError) as context:
            AmplitudeDetector(lookback_period=150)

        self.assertIn("lookback_period参数边界错误", str(context.exception))
        self.assertIn("预期范围=[5, 100]", str(context.exception))
        self.assertIn("实际值=150", str(context.exception))

    def test_guard_clause_invalid_interval(self):
        """测试interval合法性检查：非法周期应抛出ValueError。"""
        # 创建足够的K线数据
        self._create_klines("BTCUSDT", "4h", 35)

        with self.assertRaises(ValueError) as context:
            self.detector.calculate("BTCUSDT", "5m")

        self.assertIn("interval参数错误", str(context.exception))
        self.assertIn("expected=['1h', '4h', '1d']", str(context.exception))
        self.assertIn("actual='5m'", str(context.exception))

    def test_guard_clause_negative_amplitude_threshold(self):
        """测试amplitude_threshold边界检查：负数阈值应抛出ValueError。"""
        self._create_klines("BTCUSDT", "4h", 35)

        with self.assertRaises(ValueError) as context:
            self.detector.calculate("BTCUSDT", "4h", amplitude_threshold=-1.0)

        self.assertIn("amplitude_threshold参数边界错误", str(context.exception))
        self.assertIn("预期>0", str(context.exception))

    def test_guard_clause_invalid_upper_shadow_threshold_negative(self):
        """测试upper_shadow_threshold边界检查：负数应抛出ValueError。"""
        self._create_klines("BTCUSDT", "4h", 35)

        with self.assertRaises(ValueError) as context:
            self.detector.calculate("BTCUSDT", "4h", upper_shadow_threshold=-0.1)

        self.assertIn("upper_shadow_threshold参数边界错误", str(context.exception))
        self.assertIn("预期范围=[0, 1]", str(context.exception))

    def test_guard_clause_invalid_upper_shadow_threshold_too_large(self):
        """测试upper_shadow_threshold边界检查：大于1应抛出ValueError。"""
        self._create_klines("BTCUSDT", "4h", 35)

        with self.assertRaises(ValueError) as context:
            self.detector.calculate("BTCUSDT", "4h", upper_shadow_threshold=1.5)

        self.assertIn("upper_shadow_threshold参数边界错误", str(context.exception))
        self.assertIn("预期范围=[0, 1]", str(context.exception))

    def test_guard_clause_insufficient_data(self):
        """测试数据完整性检查：K线数据不足应抛出DataInsufficientError。"""
        # 只创建20根K线（需要31根）
        self._create_klines("BTCUSDT", "4h", 20)

        with self.assertRaises(DataInsufficientError) as context:
            self.detector.calculate("BTCUSDT", "4h")

        exc = context.exception
        self.assertEqual(exc.required, 31)  # lookback_period(30) + 1
        self.assertEqual(exc.actual, 20)
        self.assertEqual(exc.symbol, "BTCUSDT")
        self.assertEqual(exc.interval, "4h")

    def test_guard_clause_zero_low_price(self):
        """测试low_price检查：低价为0应抛出InvalidDataError（除零错误）。"""
        # 创建30根正常K线
        self._create_klines("BTCUSDT", "4h", 30)

        # 最新一根K线low_price=0
        now = timezone.now()
        KLine.objects.create(
            symbol="BTCUSDT",
            interval="4h",
            open_time=now,
            close_time=now + timedelta(hours=4),
            open_price=Decimal("50000.00"),
            high_price=Decimal("51000.00"),
            low_price=Decimal("0.00"),  # 异常：low=0
            close_price=Decimal("50500.00"),
            volume=Decimal("1000.00"),
            quote_volume=Decimal("50000000.00"),
        )

        with self.assertRaises(InvalidDataError) as context:
            self.detector.calculate("BTCUSDT", "4h")

        exc = context.exception
        self.assertEqual(exc.field, "low_price")
        self.assertEqual(exc.value, 0.0)
        self.assertIn("除零错误", exc.context)

    def test_guard_clause_high_less_than_low(self):
        """测试high<low检查：最高价小于最低价应抛出InvalidDataError。"""
        # 创建30根正常K线
        self._create_klines("BTCUSDT", "4h", 30)

        # 最新一根K线high<low（数据异常）
        now = timezone.now()
        KLine.objects.create(
            symbol="BTCUSDT",
            interval="4h",
            open_time=now,
            close_time=now + timedelta(hours=4),
            open_price=Decimal("50000.00"),
            high_price=Decimal("49000.00"),  # 异常：high < low
            low_price=Decimal("51000.00"),
            close_price=Decimal("50500.00"),
            volume=Decimal("1000.00"),
            quote_volume=Decimal("50000000.00"),
        )

        with self.assertRaises(InvalidDataError) as context:
            self.detector.calculate("BTCUSDT", "4h")

        exc = context.exception
        self.assertEqual(exc.field, "high_price")
        self.assertIn("数据异常：high_price < low_price", exc.context)

    def _create_klines(self, symbol: str, interval: str, count: int):
        """辅助方法：创建测试用K线数据。"""
        now = timezone.now()
        interval_hours = {"1h": 1, "4h": 4, "1d": 24}.get(interval, 4)

        for i in range(count):
            open_time = now - timedelta(hours=interval_hours * (count - i))
            KLine.objects.create(
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


class AmplitudeDetectorAccuracyTest(TestCase):
    """测试振幅计算准确性。

    验证振幅、振幅倍数、上影线比例的计算是否正确。
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
        self.detector = AmplitudeDetector(lookback_period=30)

    def test_amplitude_calculation_accuracy_normal_case(self):
        """测试正常情况下的振幅计算准确性。

        场景：
        - 前30根K线：low=100, high=110, amplitude=(110-100)/100×100=10%
        - 当前K线：low=100, high=130, amplitude=(130-100)/100×100=30%
        - 预期振幅倍数：30% / 10% = 3.0
        """
        # 创建30根历史K线，振幅均为10%
        self._create_klines_with_prices(
            symbol="TESTUSDT", interval="4h", count=30, low=100.0, high=110.0, close=105.0
        )

        # 创建当前K线，振幅为30%
        now = timezone.now()
        KLine.objects.create(
            symbol="TESTUSDT",
            interval="4h",
            open_time=now,
            close_time=now + timedelta(hours=4),
            open_price=Decimal("100.00"),
            high_price=Decimal("130.00"),
            low_price=Decimal("100.00"),
            close_price=Decimal("115.00"),
            volume=Decimal("1000.00"),
            quote_volume=Decimal("110000.00"),
        )

        # 执行计算
        result = self.detector.calculate("TESTUSDT", "4h", amplitude_threshold=3.0)

        # 验证MA振幅 = 10%
        expected_ma_amplitude = 10.0
        actual_ma_amplitude = float(result["ma_amplitude"])
        self.assertAlmostEqual(
            actual_ma_amplitude,
            expected_ma_amplitude,
            delta=0.01,
            msg=f"MA振幅计算误差: expected={expected_ma_amplitude}, actual={actual_ma_amplitude}",
        )

        # 验证当前振幅 = 30%
        expected_current_amplitude = 30.0
        actual_current_amplitude = float(result["current_amplitude"])
        self.assertAlmostEqual(
            actual_current_amplitude,
            expected_current_amplitude,
            delta=0.01,
            msg=f"当前振幅计算误差: expected={expected_current_amplitude}, actual={actual_current_amplitude}",
        )

        # 验证振幅倍数 = 3.0
        expected_amplitude_ratio = 3.0
        actual_amplitude_ratio = float(result["amplitude_ratio"])
        self.assertAlmostEqual(
            actual_amplitude_ratio,
            expected_amplitude_ratio,
            delta=0.01,
            msg=f"振幅倍数计算误差: expected={expected_amplitude_ratio}, actual={actual_amplitude_ratio}",
        )

    def test_upper_shadow_calculation_accuracy(self):
        """测试上影线比例计算准确性。

        场景：
        - K线：low=100, high=120, close=105
        - 上影线 = high - close = 120 - 105 = 15
        - 整根K线 = high - low = 120 - 100 = 20
        - 预期上影线比例 = 15 / 20 × 100 = 75%
        """
        # 创建30根历史K线
        self._create_klines_with_prices(
            symbol="TESTUSDT", interval="4h", count=30, low=100.0, high=110.0, close=105.0
        )

        # 创建当前K线，上影线比例=75%
        now = timezone.now()
        KLine.objects.create(
            symbol="TESTUSDT",
            interval="4h",
            open_time=now,
            close_time=now + timedelta(hours=4),
            open_price=Decimal("100.00"),
            high_price=Decimal("120.00"),
            low_price=Decimal("100.00"),
            close_price=Decimal("105.00"),
            volume=Decimal("1000.00"),
            quote_volume=Decimal("110000.00"),
        )

        # 执行计算
        result = self.detector.calculate("TESTUSDT", "4h")

        # 验证上影线比例 = 75%
        expected_upper_shadow = 75.0
        actual_upper_shadow = float(result["upper_shadow_ratio"])
        self.assertAlmostEqual(
            actual_upper_shadow,
            expected_upper_shadow,
            delta=0.01,
            msg=f"上影线比例计算误差: expected={expected_upper_shadow}, actual={actual_upper_shadow}",
        )

    def test_upper_shadow_boundary_high_equals_low(self):
        """测试上影线边界：high=low时应返回0。

        场景：
        - K线：low=100, high=100, close=100（十字星）
        - 预期上影线比例 = 0%
        """
        # 创建30根历史K线
        self._create_klines_with_prices(
            symbol="TESTUSDT", interval="4h", count=30, low=100.0, high=110.0, close=105.0
        )

        # 创建当前K线，十字星（high=low）
        now = timezone.now()
        KLine.objects.create(
            symbol="TESTUSDT",
            interval="4h",
            open_time=now,
            close_time=now + timedelta(hours=4),
            open_price=Decimal("100.00"),
            high_price=Decimal("100.00"),  # high = low
            low_price=Decimal("100.00"),
            close_price=Decimal("100.00"),
            volume=Decimal("1000.00"),
            quote_volume=Decimal("100000.00"),
        )

        # 执行计算
        result = self.detector.calculate("TESTUSDT", "4h")

        # 验证上影线比例 = 0%
        self.assertEqual(float(result["upper_shadow_ratio"]), 0.0)

    def test_trigger_condition_both_met(self):
        """测试触发条件：振幅倍数>=3 AND 上影线>=50%，应触发。"""
        # 创建30根历史K线，振幅=10%
        self._create_klines_with_prices(
            symbol="TESTUSDT", interval="4h", count=30, low=100.0, high=110.0, close=105.0
        )

        # 创建当前K线：振幅=30%（3倍），上影线=60%
        now = timezone.now()
        KLine.objects.create(
            symbol="TESTUSDT",
            interval="4h",
            open_time=now,
            close_time=now + timedelta(hours=4),
            open_price=Decimal("100.00"),
            high_price=Decimal("130.00"),
            low_price=Decimal("100.00"),
            close_price=Decimal("112.00"),  # 上影线=(130-112)/(130-100)=60%
            volume=Decimal("1000.00"),
            quote_volume=Decimal("112000.00"),
        )

        # 执行计算
        result = self.detector.calculate(
            "TESTUSDT", "4h", amplitude_threshold=3.0, upper_shadow_threshold=0.5
        )

        # 验证触发
        self.assertTrue(result["triggered"], "振幅倍数=3.0且上影线=60%应触发")

    def test_trigger_condition_amplitude_only(self):
        """测试触发条件：仅振幅达标，上影线不足，不应触发。"""
        # 创建30根历史K线，振幅=10%
        self._create_klines_with_prices(
            symbol="TESTUSDT", interval="4h", count=30, low=100.0, high=110.0, close=105.0
        )

        # 创建当前K线：振幅=30%（3倍），但上影线=33%（不足50%）
        now = timezone.now()
        KLine.objects.create(
            symbol="TESTUSDT",
            interval="4h",
            open_time=now,
            close_time=now + timedelta(hours=4),
            open_price=Decimal("100.00"),
            high_price=Decimal("130.00"),
            low_price=Decimal("100.00"),
            close_price=Decimal("120.00"),  # 上影线=(130-120)/(130-100)=33%
            volume=Decimal("1000.00"),
            quote_volume=Decimal("120000.00"),
        )

        # 执行计算
        result = self.detector.calculate(
            "TESTUSDT", "4h", amplitude_threshold=3.0, upper_shadow_threshold=0.5
        )

        # 验证未触发
        self.assertFalse(result["triggered"], "上影线=33%<50%，不应触发")

    def test_trigger_condition_upper_shadow_only(self):
        """测试触发条件：仅上影线达标，振幅倍数不足，不应触发。"""
        # 创建30根历史K线，振幅=10%
        self._create_klines_with_prices(
            symbol="TESTUSDT", interval="4h", count=30, low=100.0, high=110.0, close=105.0
        )

        # 创建当前K线：振幅=20%（2倍，不足3倍），但上影线=60%
        now = timezone.now()
        KLine.objects.create(
            symbol="TESTUSDT",
            interval="4h",
            open_time=now,
            close_time=now + timedelta(hours=4),
            open_price=Decimal("100.00"),
            high_price=Decimal("120.00"),
            low_price=Decimal("100.00"),
            close_price=Decimal("108.00"),  # 振幅=20%, 上影线=60%
            volume=Decimal("1000.00"),
            quote_volume=Decimal("108000.00"),
        )

        # 执行计算
        result = self.detector.calculate(
            "TESTUSDT", "4h", amplitude_threshold=3.0, upper_shadow_threshold=0.5
        )

        # 验证未触发
        self.assertFalse(result["triggered"], "振幅倍数=2.0<3.0，不应触发")

    def _create_klines_with_prices(
        self, symbol: str, interval: str, count: int, low: float, high: float, close: float
    ):
        """辅助方法：根据指定价格创建K线数据。"""
        now = timezone.now()
        interval_hours = {"1h": 1, "4h": 4, "1d": 24}.get(interval, 4)

        for i in range(count):
            open_time = now - timedelta(hours=interval_hours * (count - i))
            KLine.objects.create(
                symbol=symbol,
                interval=interval,
                open_time=open_time,
                close_time=open_time + timedelta(hours=interval_hours),
                open_price=Decimal(str(low)),
                high_price=Decimal(str(high)),
                low_price=Decimal(str(low)),
                close_price=Decimal(str(close)),
                volume=Decimal("1000.00"),
                quote_volume=Decimal(str(close * 1000.0)),
            )


class AmplitudeDetectorBoundaryTest(TestCase):
    """测试AmplitudeDetector的边界条件。"""

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

    def test_minimum_lookback_period(self):
        """测试最小回溯周期（5根K线）。"""
        detector = AmplitudeDetector(lookback_period=5)

        # 创建6根K线（5根历史 + 1根当前）
        self._create_klines("BOUNDARYUSDT", "4h", 6)

        result = detector.calculate("BOUNDARYUSDT", "4h")

        self.assertIsNotNone(result)
        self.assertGreater(float(result["ma_amplitude"]), 0)

    def test_maximum_lookback_period(self):
        """测试最大回溯周期（100根K线）。"""
        detector = AmplitudeDetector(lookback_period=100)

        # 创建101根K线（100根历史 + 1根当前）
        self._create_klines("BOUNDARYUSDT", "4h", 101)

        result = detector.calculate("BOUNDARYUSDT", "4h")

        self.assertIsNotNone(result)
        self.assertGreater(float(result["ma_amplitude"]), 0)

    def test_different_intervals(self):
        """测试不同K线周期的计算。"""
        detector = AmplitudeDetector(lookback_period=30)

        for interval in ["1h", "4h", "1d"]:
            with self.subTest(interval=interval):
                symbol = f"TEST_{interval}_USDT"

                # 创建独立的交易所和合约
                exchange = Exchange.objects.create(
                    name=f"Binance_{interval}", code=f"binance_{interval}", enabled=True
                )

                FuturesContract.objects.create(
                    exchange=exchange,
                    symbol=symbol,
                    contract_type="perpetual",
                    status="active",
                    current_price=Decimal("100.00"),
                    first_seen=timezone.now(),
                )

                self._create_klines(symbol, interval, 31)

                result = detector.calculate(symbol, interval)

                self.assertIsNotNone(result, f"{interval}周期计算失败")
                self.assertGreater(float(result["ma_amplitude"]), 0)

    def _create_klines(self, symbol: str, interval: str, count: int):
        """辅助方法：创建K线数据。"""
        now = timezone.now()
        interval_hours = {"1h": 1, "4h": 4, "1d": 24}.get(interval, 4)

        for i in range(count):
            open_time = now - timedelta(hours=interval_hours * (count - i))
            KLine.objects.create(
                symbol=symbol,
                interval=interval,
                open_time=open_time,
                close_time=open_time + timedelta(hours=interval_hours),
                open_price=Decimal("100.00"),
                high_price=Decimal("110.00"),
                low_price=Decimal("100.00"),
                close_price=Decimal("105.00"),
                volume=Decimal("1000.00"),
                quote_volume=Decimal("105000.00"),
            )


if __name__ == "__main__":
    unittest.main()
