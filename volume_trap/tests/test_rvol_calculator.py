"""
RVOLCalculator单元测试

测试相对成交量计算器的所有功能，包括：
- Guard Clauses异常路径
- 正常计算路径
- 边界条件
- 计算准确性验证（与Excel公式对比）

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md
    - Task: TASK-002-010
"""

import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from backtest.models import KLine
from monitor.models import FuturesContract
from volume_trap.detectors.rvol_calculator import RVOLCalculator
from volume_trap.exceptions import DataInsufficientError, InvalidDataError


class RVOLCalculatorGuardClausesTest(TestCase):
    """测试RVOLCalculator的Guard Clauses异常路径。

    验证所有边界检查和异常处理是否按预期工作。
    """

    def setUp(self):
        """测试前准备：创建测试用的合约数据。"""
        from decimal import Decimal

        from monitor.models import Exchange

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
        self.calculator = RVOLCalculator(lookback_period=20)

    def test_guard_clause_lookback_period_too_small(self):
        """测试lookback_period下界检查：小于5应抛出ValueError。"""
        with self.assertRaises(ValueError) as context:
            RVOLCalculator(lookback_period=3)

        self.assertIn("lookback_period参数边界错误", str(context.exception))
        self.assertIn("预期范围=[5, 100]", str(context.exception))
        self.assertIn("实际值=3", str(context.exception))

    def test_guard_clause_lookback_period_too_large(self):
        """测试lookback_period上界检查：大于100应抛出ValueError。"""
        with self.assertRaises(ValueError) as context:
            RVOLCalculator(lookback_period=150)

        self.assertIn("lookback_period参数边界错误", str(context.exception))
        self.assertIn("预期范围=[5, 100]", str(context.exception))
        self.assertIn("实际值=150", str(context.exception))

    def test_guard_clause_invalid_interval(self):
        """测试interval合法性检查：非法周期应抛出ValueError。"""
        # 创建足够的K线数据
        self._create_klines("BTCUSDT", "4h", 25)

        with self.assertRaises(ValueError) as context:
            self.calculator.calculate("BTCUSDT", "5m", threshold=8.0)

        self.assertIn("interval参数错误", str(context.exception))
        self.assertIn("expected=['1h', '4h', '1d']", str(context.exception))
        self.assertIn("actual='5m'", str(context.exception))

    def test_guard_clause_negative_threshold(self):
        """测试threshold边界检查：负数阈值应抛出ValueError。"""
        # 创建足够的K线数据
        self._create_klines("BTCUSDT", "4h", 25)

        with self.assertRaises(ValueError) as context:
            self.calculator.calculate("BTCUSDT", "4h", threshold=-1.0)

        self.assertIn("threshold参数边界错误", str(context.exception))
        self.assertIn("预期>0", str(context.exception))
        self.assertIn("实际值=-1.0", str(context.exception))

    def test_guard_clause_zero_threshold(self):
        """测试threshold边界检查：零阈值应抛出ValueError。"""
        # 创建足够的K线数据
        self._create_klines("BTCUSDT", "4h", 25)

        with self.assertRaises(ValueError) as context:
            self.calculator.calculate("BTCUSDT", "4h", threshold=0)

        self.assertIn("threshold参数边界错误", str(context.exception))
        self.assertIn("预期>0", str(context.exception))

    def test_guard_clause_insufficient_data(self):
        """测试数据完整性检查：K线数据不足应抛出DataInsufficientError。"""
        # 只创建10根K线（需要21根）
        self._create_klines("BTCUSDT", "4h", 10)

        with self.assertRaises(DataInsufficientError) as context:
            self.calculator.calculate("BTCUSDT", "4h", threshold=8.0)

        exc = context.exception
        self.assertEqual(exc.required, 21)  # lookback_period(20) + 1
        self.assertEqual(exc.actual, 10)
        self.assertEqual(exc.symbol, "BTCUSDT")
        self.assertEqual(exc.interval, "4h")
        self.assertIn("K线数据不足", str(exc))

    def test_guard_clause_zero_volume(self):
        """测试当前K线volume检查：成交量为0应抛出InvalidDataError。"""
        # 创建21根K线，最新一根volume=0
        self._create_klines("BTCUSDT", "4h", 20, base_volume=1000.0)

        # 最新一根K线volume=0
        now = timezone.now()
        KLine.objects.create(
            symbol="BTCUSDT",
            interval="4h",
            open_time=now,
            close_time=now + timedelta(hours=4),
            open_price=Decimal("50000.00"),
            high_price=Decimal("51000.00"),
            low_price=Decimal("49000.00"),
            close_price=Decimal("50500.00"),
            volume=Decimal("0.00"),  # 异常：volume=0
            quote_volume=Decimal("0.00"),
        )

        with self.assertRaises(InvalidDataError) as context:
            self.calculator.calculate("BTCUSDT", "4h", threshold=8.0)

        exc = context.exception
        self.assertEqual(exc.field, "volume")
        self.assertEqual(exc.value, 0.0)
        self.assertIn("当前K线成交量必须>0", exc.context)

    def _create_klines(self, symbol: str, interval: str, count: int, base_volume: float = 1000.0):
        """辅助方法：创建测试用K线数据。

        Args:
            symbol: 交易对符号
            interval: K线周期
            count: K线数量
            base_volume: 基础成交量
        """
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
                volume=Decimal(str(base_volume)),
                quote_volume=Decimal(str(base_volume * 50000.0)),  # 添加quote_volume字段
            )


class RVOLCalculatorAccuracyTest(TestCase):
    """测试RVOL计算准确性，对比Excel公式验证结果。

    验证计算结果与手工Excel计算一致（误差<0.01%）。
    """

    def setUp(self):
        """测试前准备：创建测试用合约数据。"""
        from monitor.models import Exchange

        # 创建交易所
        self.exchange = Exchange.objects.create(
            name="Binance Test", code="binance_test", enabled=True
        )

        # 创建合约
        self.contract = FuturesContract.objects.create(
            exchange=self.exchange,
            symbol="TESTUSDT",
            contract_type="perpetual",
            status="active",
            current_price=Decimal("100.00"),
            first_seen=timezone.now(),
        )
        self.calculator = RVOLCalculator(lookback_period=20)

    def test_rvol_calculation_accuracy_normal_case(self):
        """测试正常情况下的RVOL计算准确性。

        场景：
        - 前20根K线成交量均为1000
        - 当前K线成交量为8000
        - 预期RVOL = 8000 / 1000 = 8.0
        """
        # 创建20根历史K线，成交量均为1000
        self._create_klines_with_volumes(symbol="TESTUSDT", interval="4h", volumes=[1000.0] * 20)

        # 创建当前K线，成交量为8000
        now = timezone.now()
        KLine.objects.create(
            symbol="TESTUSDT",
            interval="4h",
            open_time=now,
            close_time=now + timedelta(hours=4),
            open_price=Decimal("100.00"),
            high_price=Decimal("110.00"),
            low_price=Decimal("95.00"),
            close_price=Decimal("105.00"),
            volume=Decimal("8000.00"),
            quote_volume=Decimal(str(8000.00 * 105.0)),
        )

        # 执行计算
        result = self.calculator.calculate("TESTUSDT", "4h", threshold=8.0)

        # 验证结果
        self.assertIsNotNone(result)

        # Excel公式验证：MA(V,20) = 1000.0
        expected_ma_volume = 1000.0
        actual_ma_volume = float(result["ma_volume"])
        self.assertAlmostEqual(
            actual_ma_volume,
            expected_ma_volume,
            delta=expected_ma_volume * 0.0001,  # 误差<0.01%
            msg=f"MA(V,20)计算误差: expected={expected_ma_volume}, actual={actual_ma_volume}",
        )

        # Excel公式验证：RVOL = 8000 / 1000 = 8.0
        expected_rvol = 8.0
        actual_rvol = float(result["rvol_ratio"])
        self.assertAlmostEqual(
            actual_rvol,
            expected_rvol,
            delta=expected_rvol * 0.0001,  # 误差<0.01%
            msg=f"RVOL计算误差: expected={expected_rvol}, actual={actual_rvol}",
        )

        # 验证触发状态
        self.assertTrue(result["triggered"], "RVOL=8.0应该触发阈值(≥8.0)")

        # 验证当前成交量
        self.assertEqual(float(result["current_volume"]), 8000.0)

    def test_rvol_calculation_accuracy_below_threshold(self):
        """测试RVOL未触发阈值的情况。

        场景：
        - 前20根K线成交量均为1000
        - 当前K线成交量为7500
        - 预期RVOL = 7500 / 1000 = 7.5 < 8.0（未触发）
        """
        # 创建20根历史K线，成交量均为1000
        self._create_klines_with_volumes(symbol="TESTUSDT", interval="4h", volumes=[1000.0] * 20)

        # 创建当前K线，成交量为7500
        now = timezone.now()
        KLine.objects.create(
            symbol="TESTUSDT",
            interval="4h",
            open_time=now,
            close_time=now + timedelta(hours=4),
            open_price=Decimal("100.00"),
            high_price=Decimal("110.00"),
            low_price=Decimal("95.00"),
            close_price=Decimal("105.00"),
            volume=Decimal("7500.00"),
            quote_volume=Decimal(str(7500.00 * 105.0)),
        )

        # 执行计算
        result = self.calculator.calculate("TESTUSDT", "4h", threshold=8.0)

        # 验证RVOL = 7.5
        expected_rvol = 7.5
        actual_rvol = float(result["rvol_ratio"])
        self.assertAlmostEqual(
            actual_rvol,
            expected_rvol,
            delta=expected_rvol * 0.0001,
            msg=f"RVOL计算误差: expected={expected_rvol}, actual={actual_rvol}",
        )

        # 验证未触发
        self.assertFalse(result["triggered"], "RVOL=7.5不应触发阈值(≥8.0)")

    def test_rvol_calculation_accuracy_variable_volumes(self):
        """测试历史成交量波动情况下的RVOL计算准确性。

        场景：
        - 前20根K线成交量递增：500, 600, 700, ..., 2400
        - MA(V,20) = (500+600+...+2400)/20 = 1450
        - 当前K线成交量为11600
        - 预期RVOL = 11600 / 1450 = 8.0
        """
        # 创建20根历史K线，成交量递增
        volumes = [500 + i * 100 for i in range(20)]  # [500, 600, ..., 2400]
        self._create_klines_with_volumes(symbol="TESTUSDT", interval="4h", volumes=volumes)

        # 创建当前K线，成交量为11600
        now = timezone.now()
        KLine.objects.create(
            symbol="TESTUSDT",
            interval="4h",
            open_time=now,
            close_time=now + timedelta(hours=4),
            open_price=Decimal("100.00"),
            high_price=Decimal("110.00"),
            low_price=Decimal("95.00"),
            close_price=Decimal("105.00"),
            volume=Decimal("11600.00"),
            quote_volume=Decimal(str(11600.00 * 105.0)),
        )

        # 执行计算
        result = self.calculator.calculate("TESTUSDT", "4h", threshold=8.0)

        # Excel公式验证：MA(V,20) = sum(500..2400)/20 = 1450.0
        expected_ma_volume = sum(volumes) / 20.0  # 1450.0
        actual_ma_volume = float(result["ma_volume"])
        self.assertAlmostEqual(
            actual_ma_volume,
            expected_ma_volume,
            delta=expected_ma_volume * 0.0001,
            msg=f"MA(V,20)计算误差: expected={expected_ma_volume}, actual={actual_ma_volume}",
        )

        # Excel公式验证：RVOL = 11600 / 1450 = 8.0
        expected_rvol = 11600.0 / expected_ma_volume
        actual_rvol = float(result["rvol_ratio"])
        self.assertAlmostEqual(
            actual_rvol,
            expected_rvol,
            delta=expected_rvol * 0.0001,
            msg=f"RVOL计算误差: expected={expected_rvol}, actual={actual_rvol}",
        )

        # 验证触发状态
        self.assertTrue(result["triggered"], "RVOL=8.0应该触发阈值(≥8.0)")

    def test_rvol_calculation_with_custom_threshold(self):
        """测试自定义阈值参数。

        验证threshold参数覆盖配置默认值的功能。
        """
        # 创建20根历史K线 + 1根当前K线
        self._create_klines_with_volumes(symbol="TESTUSDT", interval="4h", volumes=[1000.0] * 20)

        now = timezone.now()
        KLine.objects.create(
            symbol="TESTUSDT",
            interval="4h",
            open_time=now,
            close_time=now + timedelta(hours=4),
            open_price=Decimal("100.00"),
            high_price=Decimal("110.00"),
            low_price=Decimal("95.00"),
            close_price=Decimal("105.00"),
            volume=Decimal("5000.00"),  # RVOL = 5.0
            quote_volume=Decimal(str(5000.00 * 105.0)),
        )

        # 测试1：阈值=4.0，应该触发
        result = self.calculator.calculate("TESTUSDT", "4h", threshold=4.0)
        self.assertTrue(result["triggered"], "RVOL=5.0 >= 4.0，应该触发")

        # 测试2：阈值=6.0，不应触发
        result = self.calculator.calculate("TESTUSDT", "4h", threshold=6.0)
        self.assertFalse(result["triggered"], "RVOL=5.0 < 6.0，不应触发")

    def _create_klines_with_volumes(self, symbol: str, interval: str, volumes: list):
        """辅助方法：根据指定成交量列表创建K线数据。

        Args:
            symbol: 交易对符号
            interval: K线周期
            volumes: 成交量列表
        """
        now = timezone.now()
        interval_hours = {"1h": 1, "4h": 4, "1d": 24}.get(interval, 4)

        for i, volume in enumerate(volumes):
            open_time = now - timedelta(hours=interval_hours * (len(volumes) - i))
            KLine.objects.create(
                symbol=symbol,
                interval=interval,
                open_time=open_time,
                close_time=open_time + timedelta(hours=interval_hours),
                open_price=Decimal("100.00"),
                high_price=Decimal("110.00"),
                low_price=Decimal("95.00"),
                close_price=Decimal("105.00"),
                volume=Decimal(str(volume)),
                quote_volume=Decimal(str(volume * 105.0)),  # 添加quote_volume字段
            )


class RVOLCalculatorBoundaryTest(TestCase):
    """测试RVOL计算器的边界条件。

    验证极端情况下的行为是否符合预期。
    """

    def setUp(self):
        """测试前准备。"""
        from monitor.models import Exchange

        # 创建交易所
        self.exchange = Exchange.objects.create(
            name="Binance Boundary", code="binance_boundary", enabled=True
        )

        # 创建合约
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
        calculator = RVOLCalculator(lookback_period=5)

        # 创建6根K线（5根历史 + 1根当前）
        self._create_klines("BOUNDARYUSDT", "4h", 6, base_volume=1000.0)

        result = calculator.calculate("BOUNDARYUSDT", "4h", threshold=8.0)

        self.assertIsNotNone(result)
        self.assertEqual(float(result["ma_volume"]), 1000.0)

    def test_maximum_lookback_period(self):
        """测试最大回溯周期（100根K线）。"""
        calculator = RVOLCalculator(lookback_period=100)

        # 创建101根K线（100根历史 + 1根当前）
        self._create_klines("BOUNDARYUSDT", "4h", 101, base_volume=2000.0)

        result = calculator.calculate("BOUNDARYUSDT", "4h", threshold=8.0)

        self.assertIsNotNone(result)
        self.assertEqual(float(result["ma_volume"]), 2000.0)

    def test_exact_threshold_value(self):
        """测试RVOL恰好等于阈值的情况。

        验证 ">=" 判断逻辑是否正确。
        """
        calculator = RVOLCalculator(lookback_period=20)

        # 创建20根历史K线，成交量均为1000
        self._create_klines("BOUNDARYUSDT", "4h", 20, base_volume=1000.0)

        # 当前K线成交量恰好=8000（RVOL=8.0）
        now = timezone.now()
        KLine.objects.create(
            symbol="BOUNDARYUSDT",
            interval="4h",
            open_time=now,
            close_time=now + timedelta(hours=4),
            open_price=Decimal("100.00"),
            high_price=Decimal("110.00"),
            low_price=Decimal("95.00"),
            close_price=Decimal("105.00"),
            volume=Decimal("8000.00"),
            quote_volume=Decimal(str(8000.00 * 105.0)),
        )

        result = calculator.calculate("BOUNDARYUSDT", "4h", threshold=8.0)

        # RVOL=8.0，threshold=8.0，应该触发（>=）
        self.assertTrue(result["triggered"], "RVOL=8.0应该触发阈值(threshold=8.0)")

    def test_different_intervals(self):
        """测试不同K线周期的计算。"""
        from monitor.models import Exchange

        calculator = RVOLCalculator(lookback_period=20)

        for interval in ["1h", "4h", "1d"]:
            with self.subTest(interval=interval):
                # 为每个周期创建独立的K线数据
                symbol = f"TEST_{interval}_USDT"

                # 创建独立的交易所
                exchange = Exchange.objects.create(
                    name=f"Binance_{interval}", code=f"binance_{interval}", enabled=True
                )

                # 创建独立的合约
                FuturesContract.objects.create(
                    exchange=exchange,
                    symbol=symbol,
                    contract_type="perpetual",
                    status="active",
                    current_price=Decimal("100.00"),
                    first_seen=timezone.now(),
                )

                self._create_klines(symbol, interval, 21, base_volume=1000.0)

                result = calculator.calculate(symbol, interval, threshold=8.0)

                self.assertIsNotNone(result, f"{interval}周期计算失败")
                self.assertEqual(float(result["ma_volume"]), 1000.0)

    def _create_klines(self, symbol: str, interval: str, count: int, base_volume: float):
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
                low_price=Decimal("95.00"),
                close_price=Decimal("105.00"),
                volume=Decimal(str(base_volume)),
                quote_volume=Decimal(str(base_volume * 105.0)),  # 添加quote_volume字段
            )


class RVOLCalculatorPerformanceTest(TestCase):
    """测试RVOL计算器的性能。

    验证pandas向量化计算的性能优势。
    """

    def setUp(self):
        """测试前准备。"""
        from monitor.models import Exchange

        # 创建交易所
        self.exchange = Exchange.objects.create(
            name="Binance Perf", code="binance_perf", enabled=True
        )

        # 创建合约
        self.contract = FuturesContract.objects.create(
            exchange=self.exchange,
            symbol="PERFUSDT",
            contract_type="perpetual",
            status="active",
            current_price=Decimal("1000.00"),
            first_seen=timezone.now(),
        )
        self.calculator = RVOLCalculator(lookback_period=20)

    def test_performance_benchmark(self):
        """性能基准测试：验证pandas向量化计算的效率。

        预期：21根K线的计算应该在10ms内完成。
        """
        import time

        # 创建21根K线
        self._create_klines("PERFUSDT", "4h", 21, base_volume=1000.0)

        # 预热（避免首次Django ORM查询的开销）
        self.calculator.calculate("PERFUSDT", "4h", threshold=8.0)

        # 性能测试：执行100次计算
        start_time = time.time()
        for _ in range(100):
            self.calculator.calculate("PERFUSDT", "4h", threshold=8.0)
        end_time = time.time()

        avg_time_ms = (end_time - start_time) / 100 * 1000

        # 验证：平均每次计算应在10ms内完成
        self.assertLess(
            avg_time_ms, 10.0, f"性能不达标: 平均每次计算耗时{avg_time_ms:.2f}ms > 10ms"
        )

    def _create_klines(self, symbol: str, interval: str, count: int, base_volume: float):
        """辅助方法：创建K线数据。"""
        now = timezone.now()
        interval_hours = 4

        for i in range(count):
            open_time = now - timedelta(hours=interval_hours * (count - i))
            KLine.objects.create(
                symbol=symbol,
                interval=interval,
                open_time=open_time,
                close_time=open_time + timedelta(hours=interval_hours),
                open_price=Decimal("100.00"),
                high_price=Decimal("110.00"),
                low_price=Decimal("95.00"),
                close_price=Decimal("105.00"),
                volume=Decimal(str(base_volume)),
                quote_volume=Decimal(str(base_volume * 105.0)),  # 添加quote_volume字段
            )


if __name__ == "__main__":
    unittest.main()
