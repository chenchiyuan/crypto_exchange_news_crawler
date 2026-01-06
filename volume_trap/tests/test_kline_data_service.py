"""
KLineDataService单元测试

测试KLineDataService核心功能，包括：
- get_kline_data方法基本查询
- 参数验证（symbol、interval、market_type、start_time、end_time）
- 异常情况处理（symbol不存在、日期范围无效等）
- 性能优化验证

Related:
    - PRD: docs/iterations/006-volume-trap-dashboard/prd.md (F2.1)
    - Architecture: docs/iterations/006-volume-trap-dashboard/architecture.md (3.3)
    - Task: TASK-006-002
"""

import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone as django_timezone

from backtest.models import KLine
from monitor.models import Exchange, FuturesContract, SpotContract
from volume_trap.exceptions import DateRangeInvalidError, SymbolNotFoundError
from volume_trap.services.kline_data_service import KLineDataService


class KLineDataServiceInitTest(TestCase):
    """测试KLineDataService初始化。"""

    def test_init_success(self):
        """测试服务初始化成功。"""
        service = KLineDataService()

        self.assertIsNotNone(service)


class KLineDataServiceGetKLineDataTest(TestCase):
    """测试get_kline_data方法。"""

    def setUp(self):
        """测试前准备：创建测试数据。"""
        self.service = KLineDataService()

        # 创建交易所
        self.exchange = Exchange.objects.create(name="Test Exchange", code="TEST", enabled=True)

        # 创建合约
        self.contract = FuturesContract.objects.create(
            symbol="BTCUSDT",
            exchange=self.exchange,
            contract_type="perpetual",
            status="active",
            current_price=50000.00,
            first_seen=django_timezone.now(),
        )

        # 创建现货合约（用于现货市场测试）
        self.spot_contract = SpotContract.objects.create(
            symbol="BTCUSDT",
            exchange=self.exchange,
            status="active",
            current_price=50000.00,
            first_seen=django_timezone.now(),
        )

        # 创建K线数据
        self.now = django_timezone.now()
        self.kline_data = []

        # 创建30条K线数据
        for i in range(30):
            open_time = self.now - timedelta(hours=i)
            close_time = open_time + timedelta(hours=4)
            volume = Decimal(str(1000 + i * 10))
            quote_volume = volume * Decimal(str(50000 + i * 100))  # 计算报价量
            kline = KLine.objects.create(
                symbol="BTCUSDT",
                interval="4h",
                market_type="futures",
                open_price=Decimal(str(50000 + i * 100)),
                high_price=Decimal(str(50100 + i * 100)),
                low_price=Decimal(str(49900 + i * 100)),
                close_price=Decimal(str(50050 + i * 100)),
                volume=volume,
                quote_volume=quote_volume,
                trade_count=100 + i,
                taker_buy_volume=volume * Decimal("0.5"),
                taker_buy_quote_volume=quote_volume * Decimal("0.5"),
                open_time=open_time,
                close_time=close_time,
            )
            self.kline_data.append(kline)

    def test_get_kline_data_valid_parameters(self):
        """测试有效参数：应返回K线数据列表。"""
        start_time = self.now - timedelta(hours=50)
        end_time = self.now

        result = self.service.get_kline_data(
            symbol="BTCUSDT",
            interval="4h",
            market_type="futures",
            start_time=start_time,
            end_time=end_time,
        )

        # 验证返回结构
        self.assertIsInstance(result, dict)
        self.assertIn("data", result)
        self.assertIn("total_count", result)

        # 验证数据格式
        self.assertIsInstance(result["data"], list)
        self.assertIsInstance(result["total_count"], int)

        # 验证数据内容
        self.assertGreater(len(result["data"]), 0)
        self.assertEqual(result["total_count"], len(result["data"]))

        # 验证字段结构
        first_item = result["data"][0]
        self.assertIn("time", first_item)
        self.assertIn("open", first_item)
        self.assertIn("high", first_item)
        self.assertIn("low", first_item)
        self.assertIn("close", first_item)
        self.assertIn("volume", first_item)

        # 验证数据类型
        self.assertIsInstance(first_item["open"], float)
        self.assertIsInstance(first_item["high"], float)
        self.assertIsInstance(first_item["low"], float)
        self.assertIsInstance(first_item["close"], float)
        self.assertIsInstance(first_item["volume"], float)

    def test_get_kline_data_symbol_not_found(self):
        """测试symbol不存在：应抛出SymbolNotFoundError。"""
        start_time = self.now - timedelta(hours=50)
        end_time = self.now

        with self.assertRaises(SymbolNotFoundError) as context:
            self.service.get_kline_data(
                symbol="NONEXISTENT",
                interval="4h",
                market_type="futures",
                start_time=start_time,
                end_time=end_time,
            )

        self.assertIn("NONEXISTENT", str(context.exception))

    def test_get_kline_data_invalid_date_range(self):
        """测试无效日期范围（start_time > end_time）：应抛出DateRangeInvalidError。"""
        start_time = self.now
        end_time = self.now - timedelta(hours=50)

        with self.assertRaises(DateRangeInvalidError) as context:
            self.service.get_kline_data(
                symbol="BTCUSDT",
                interval="4h",
                market_type="futures",
                start_time=start_time,
                end_time=end_time,
            )

        self.assertIn("start_time", str(context.exception))
        self.assertIn("end_time", str(context.exception))

    def test_get_kline_data_empty_date_range(self):
        """测试空日期范围（无数据）：应返回空列表。"""
        start_time = self.now + timedelta(hours=100)
        end_time = self.now + timedelta(hours=200)

        result = self.service.get_kline_data(
            symbol="BTCUSDT",
            interval="4h",
            market_type="futures",
            start_time=start_time,
            end_time=end_time,
        )

        # 验证返回空结果
        self.assertEqual(result["total_count"], 0)
        self.assertEqual(len(result["data"]), 0)

    def test_get_kline_data_limit_parameter(self):
        """测试limit参数：应限制返回数据数量。"""
        start_time = self.now - timedelta(hours=50)
        end_time = self.now

        result = self.service.get_kline_data(
            symbol="BTCUSDT",
            interval="4h",
            market_type="futures",
            start_time=start_time,
            end_time=end_time,
            limit=10,
        )

        # 验证返回数量不超过limit
        self.assertLessEqual(len(result["data"]), 10)
        # total_count应该是实际总数（30），而不是限制数（10）
        self.assertEqual(result["total_count"], 30)

    def test_get_kline_data_performance(self):
        """测试性能：应在1秒内完成查询。"""
        import time

        start_time = self.now - timedelta(hours=50)
        end_time = self.now

        start = time.time()
        result = self.service.get_kline_data(
            symbol="BTCUSDT",
            interval="4h",
            market_type="futures",
            start_time=start_time,
            end_time=end_time,
        )
        elapsed = time.time() - start

        # 验证性能要求（小于1秒）
        self.assertLess(elapsed, 1.0)
        self.assertGreater(len(result["data"]), 0)

    def test_get_kline_data_with_spot_market_type(self):
        """测试现货市场类型：应返回spot数据。"""
        # 创建现货K线数据
        open_time = self.now
        close_time = open_time + timedelta(hours=4)
        volume = Decimal("1000")
        quote_volume = volume * Decimal("50000")
        KLine.objects.create(
            symbol="BTCUSDT",
            interval="4h",
            market_type="spot",
            open_price=Decimal("50000"),
            high_price=Decimal("50100"),
            low_price=Decimal("49900"),
            close_price=Decimal("50050"),
            volume=volume,
            quote_volume=quote_volume,
            trade_count=100,
            taker_buy_volume=volume * Decimal("0.5"),
            taker_buy_quote_volume=quote_volume * Decimal("0.5"),
            open_time=open_time,
            close_time=close_time,
        )

        start_time = self.now - timedelta(hours=50)
        end_time = self.now

        result = self.service.get_kline_data(
            symbol="BTCUSDT",
            interval="4h",
            market_type="spot",
            start_time=start_time,
            end_time=end_time,
        )

        # 验证返回spot数据
        self.assertGreater(len(result["data"]), 0)
        # 验证所有数据都是spot类型
        for item in result["data"]:
            self.assertEqual(item["market_type"], "spot")
