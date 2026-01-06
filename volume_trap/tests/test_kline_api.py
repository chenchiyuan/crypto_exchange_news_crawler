"""
K线数据API端点单元测试

测试GET /api/volume-trap/kline/{symbol}/端点，包括：
- 路径参数验证（symbol）
- 查询参数验证（interval、market_type、start_time、end_time、limit）
- 响应格式验证
- 集成KLineDataService测试
- 异常情况处理（参数缺失、无效参数、symbol不存在等）

Related:
    - PRD: docs/iterations/006-volume-trap-dashboard/prd.md (F2.1)
    - Architecture: docs/iterations/006-volume-trap-dashboard/architecture.md (5.3)
    - Task: TASK-006-004
"""

from datetime import datetime
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import include, path, reverse
from django.utils import timezone as django_timezone

from rest_framework import status
from rest_framework.test import APITestCase

from backtest.models import KLine
from monitor.models import Exchange, FuturesContract, SpotContract
from volume_trap.exceptions import DateRangeInvalidError, SymbolNotFoundError
from volume_trap.models import VolumeTrapMonitor


@override_settings(ROOT_URLCONF=__name__)
class KLineDataAPITest(APITestCase):
    """测试K线数据API端点。"""

    def setUp(self):
        """测试前准备：创建测试数据。"""
        # 创建交易所
        self.exchange = Exchange.objects.create(name="Test Exchange", code="TEST", enabled=True)

        # 创建合约
        self.futures_contract = FuturesContract.objects.create(
            symbol="BTCUSDT",
            exchange=self.exchange,
            contract_type="perpetual",
            status="active",
            current_price=50000.00,
            first_seen=django_timezone.now(),
        )

        self.spot_contract = SpotContract.objects.create(
            symbol="BTCUSDT",
            exchange=self.exchange,
            status="active",
            current_price=50000.00,
            first_seen=django_timezone.now(),
        )

        # 创建K线数据
        self.now = django_timezone.now()
        for i in range(30):
            open_time = self.now - django_timezone.timedelta(hours=i * 4)
            close_time = open_time + django_timezone.timedelta(hours=4)
            volume = Decimal(str(1000 + i * 10))
            quote_volume = volume * Decimal(str(50000 + i * 100))
            KLine.objects.create(
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

        # 创建现货K线数据
        open_time = self.now
        close_time = open_time + django_timezone.timedelta(hours=4)
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

    def test_get_kline_data_valid_request(self):
        """测试有效请求：应返回200和K线数据。"""
        start_time = self.now - django_timezone.timedelta(hours=50)
        end_time = self.now

        response = self.client.get(
            "/api/volume-trap/kline/BTCUSDT/",
            {
                "interval": "4h",
                "market_type": "futures",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "limit": 10,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("data", response.data)
        self.assertIn("total_count", response.data)
        self.assertIsInstance(response.data["data"], list)
        self.assertLessEqual(len(response.data["data"]), 10)

    def test_get_kline_data_missing_required_parameter(self):
        """测试缺少必填参数：应返回400错误。"""
        response = self.client.get(
            "/api/volume-trap/kline/BTCUSDT/",
            {
                "interval": "4h",
                # 缺少 market_type
                "start_time": self.now.isoformat(),
                "end_time": self.now.isoformat(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_get_kline_data_invalid_interval(self):
        """测试无效interval值：应返回400错误。"""
        response = self.client.get(
            "/api/volume-trap/kline/BTCUSDT/",
            {
                "interval": "invalid_interval",  # 无效值
                "market_type": "futures",
                "start_time": self.now.isoformat(),
                "end_time": self.now.isoformat(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_get_kline_data_invalid_market_type(self):
        """测试无效market_type值：应返回400错误。"""
        response = self.client.get(
            "/api/volume-trap/kline/BTCUSDT/",
            {
                "interval": "4h",
                "market_type": "invalid_market",  # 无效值
                "start_time": self.now.isoformat(),
                "end_time": self.now.isoformat(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_get_kline_data_symbol_not_found(self):
        """测试symbol不存在：应返回404错误。"""
        response = self.client.get(
            "/api/volume-trap/kline/NONEXISTENT/",
            {
                "interval": "4h",
                "market_type": "futures",
                "start_time": self.now.isoformat(),
                "end_time": self.now.isoformat(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)

    def test_get_kline_data_invalid_date_format(self):
        """测试无效日期格式：应返回400错误。"""
        response = self.client.get(
            "/api/volume-trap/kline/BTCUSDT/",
            {
                "interval": "4h",
                "market_type": "futures",
                "start_time": "invalid_date",  # 无效日期格式
                "end_time": self.now.isoformat(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_get_kline_data_invalid_date_range(self):
        """测试无效日期范围（start_time > end_time）：应返回400错误。"""
        start_time = self.now
        end_time = self.now - django_timezone.timedelta(hours=50)

        response = self.client.get(
            "/api/volume-trap/kline/BTCUSDT/",
            {
                "interval": "4h",
                "market_type": "futures",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_get_kline_data_spot_market_type(self):
        """测试现货市场类型：应返回spot数据。"""
        response = self.client.get(
            "/api/volume-trap/kline/BTCUSDT/",
            {
                "interval": "4h",
                "market_type": "spot",
                "start_time": (self.now - django_timezone.timedelta(hours=10)).isoformat(),
                "end_time": self.now.isoformat(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data["data"]), 0)
        # 验证所有数据都是spot类型
        for item in response.data["data"]:
            self.assertEqual(item["market_type"], "spot")

    def test_get_kline_data_without_limit(self):
        """测试不传limit参数：应返回所有匹配数据。"""
        response = self.client.get(
            "/api/volume-trap/kline/BTCUSDT/",
            {
                "interval": "4h",
                "market_type": "futures",
                "start_time": (self.now - django_timezone.timedelta(hours=120)).isoformat(),
                "end_time": self.now.isoformat(),
                # 没有limit参数
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 应该返回所有30条数据
        self.assertGreaterEqual(response.data["total_count"], 30)

    def test_get_kline_data_response_structure(self):
        """测试响应结构：应包含所有必要字段。"""
        start_time = self.now - django_timezone.timedelta(hours=50)
        end_time = self.now

        response = self.client.get(
            "/api/volume-trap/kline/BTCUSDT/",
            {
                "interval": "4h",
                "market_type": "futures",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "limit": 5,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 验证顶级字段
        self.assertIn("data", response.data)
        self.assertIn("total_count", response.data)

        # 验证data数组结构
        data = response.data["data"]
        if len(data) > 0:
            first_item = data[0]
            required_fields = ["time", "open", "high", "low", "close", "volume", "market_type"]
            for field in required_fields:
                self.assertIn(field, first_item)

            # 验证数据类型
            self.assertIsInstance(first_item["time"], (int, float))
            self.assertIsInstance(first_item["open"], (int, float))
            self.assertIsInstance(first_item["high"], (int, float))
            self.assertIsInstance(first_item["low"], (int, float))
            self.assertIsInstance(first_item["close"], (int, float))
            self.assertIsInstance(first_item["volume"], (int, float))
            self.assertIsInstance(first_item["market_type"], str)

    def test_get_kline_data_performance(self):
        """测试性能：应在1秒内完成查询。"""
        import time

        start_time = self.now - django_timezone.timedelta(hours=120)
        end_time = self.now

        start = time.time()
        response = self.client.get(
            "/api/volume-trap/kline/BTCUSDT/",
            {
                "interval": "4h",
                "market_type": "futures",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "limit": 100,
            },
        )
        elapsed = time.time() - start

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLess(elapsed, 1.0, f"API响应时间{elapsed:.2f}秒，超过1秒限制")

    def test_get_kline_data_empty_result(self):
        """测试空结果（日期范围无数据）：应返回空数组。"""
        future_start = self.now + django_timezone.timedelta(hours=100)
        future_end = self.now + django_timezone.timedelta(hours=200)

        response = self.client.get(
            "/api/volume-trap/kline/BTCUSDT/",
            {
                "interval": "4h",
                "market_type": "futures",
                "start_time": future_start.isoformat(),
                "end_time": future_end.isoformat(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]), 0)
        self.assertEqual(response.data["total_count"], 0)


# 测试用的URL配置
urlpatterns = [
    path("api/volume-trap/", include("volume_trap.urls")),
]
