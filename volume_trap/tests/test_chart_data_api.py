"""
图表数据API端点单元测试

测试GET /api/volume-trap/chart-data/{monitor_id}/端点，包括：
- 路径参数验证（monitor_id）
- 集成ChartDataFormatter测试
- 响应格式验证
- 异常情况处理（monitor_id不存在等）

Related:
    - PRD: docs/iterations/006-volume-trap-dashboard/prd.md (F2.2)
    - Architecture: docs/iterations/006-volume-trap-dashboard/architecture.md (5.4)
    - Task: TASK-006-005
"""

from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import include, path, reverse
from django.utils import timezone as django_timezone

from rest_framework import status
from rest_framework.test import APITestCase

from backtest.models import KLine
from monitor.models import Exchange, FuturesContract, SpotContract
from volume_trap.exceptions import DataFormatError, SymbolNotFoundError
from volume_trap.models import VolumeTrapMonitor


@override_settings(ROOT_URLCONF=__name__)
class ChartDataAPITest(APITestCase):
    """测试图表数据API端点。"""

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

        # 创建监控记录
        self.now = django_timezone.now()
        self.monitor = VolumeTrapMonitor.objects.create(
            futures_contract=self.futures_contract,
            interval="4h",
            status="pending",
            trigger_time=self.now,
            trigger_price=50000.00,
            trigger_volume=1000.00,
            trigger_kline_high=50100.00,
            trigger_kline_low=49900.00,
            market_type="futures",
            phase_1_passed=False,
            phase_2_passed=False,
            phase_3_passed=False,
        )

        # 创建K线数据
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

    def test_get_chart_data_valid_request(self):
        """测试有效请求：应返回200和图表数据。"""
        response = self.client.get(f"/api/volume-trap/chart-data/{self.monitor.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("data", response.data)
        self.assertIn("trigger_marker", response.data)

        # 验证返回结构
        self.assertIsInstance(response.data["data"], dict)
        self.assertIn("labels", response.data["data"])
        self.assertIn("datasets", response.data["data"])
        self.assertIn("trigger_marker", response.data)

        # 验证触发点标记
        trigger_marker = response.data["trigger_marker"]
        self.assertIn("time", trigger_marker)
        self.assertIn("price", trigger_marker)
        self.assertEqual(trigger_marker["time"], self.monitor.trigger_time.timestamp())
        self.assertEqual(trigger_marker["price"], float(self.monitor.trigger_price))

    def test_get_chart_data_monitor_not_found(self):
        """测试monitor_id不存在：应返回404错误。"""
        non_existent_id = 99999
        response = self.client.get(f"/api/volume-trap/chart-data/{non_existent_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)

    def test_get_chart_data_response_structure(self):
        """测试响应结构：应包含所有必要字段。"""
        response = self.client.get(f"/api/volume-trap/chart-data/{self.monitor.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 验证顶级字段
        self.assertIn("data", response.data)
        self.assertIn("trigger_marker", response.data)

        # 验证data字段结构
        data = response.data["data"]
        self.assertIn("labels", data)
        self.assertIn("datasets", data)

        # 验证datasets结构
        datasets = data["datasets"]
        self.assertIsInstance(datasets, list)
        self.assertGreater(len(datasets), 0)

        # 验证至少有一个数据集包含价格数据
        has_price_data = any(
            "price" in ds.get("label", "").lower() or "close" in ds.get("label", "").lower()
            for ds in datasets
        )
        self.assertTrue(has_price_data, "应包含价格数据集")

    def test_get_chart_data_trigger_marker_accuracy(self):
        """测试触发点标记准确性：应准确标记触发时间和价格。"""
        response = self.client.get(f"/api/volume-trap/chart-data/{self.monitor.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        trigger_marker = response.data["trigger_marker"]
        expected_time = self.monitor.trigger_time.timestamp()
        expected_price = float(self.monitor.trigger_price)

        # 验证触发时间（允许小的浮点误差）
        self.assertAlmostEqual(
            trigger_marker["time"], expected_time, places=5, msg="触发时间标记不准确"
        )

        # 验证触发价格（允许小的浮点误差）
        self.assertAlmostEqual(
            trigger_marker["price"], expected_price, places=5, msg="触发价格标记不准确"
        )

    def test_get_chart_data_data_type_conversion(self):
        """测试数据类型转换：确保所有数值转换为JavaScript兼容格式。"""
        response = self.client.get(f"/api/volume-trap/chart-data/{self.monitor.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 验证labels为字符串（JavaScript时间戳）
        labels = response.data["data"]["labels"]
        for label in labels:
            self.assertIsInstance(label, str)

        # 验证datasets中的数值为float
        datasets = response.data["data"]["datasets"]
        for dataset in datasets:
            if "data" in dataset:
                for data_point in dataset["data"]:
                    if isinstance(data_point, (list, tuple)) and len(data_point) >= 2:
                        # y值应该是float
                        self.assertIsInstance(data_point[1], (int, float))

    def test_get_chart_data_empty_kline_data(self):
        """测试无K线数据场景：应返回500错误（数据格式化失败）。"""
        # 创建另一个合约，但没有对应的K线数据
        eth_contract = FuturesContract.objects.create(
            symbol="ETHUSDT",
            exchange=self.exchange,
            contract_type="perpetual",
            status="active",
            current_price=3000.00,
            first_seen=django_timezone.now(),
        )

        empty_monitor = VolumeTrapMonitor.objects.create(
            futures_contract=eth_contract,
            interval="4h",
            status="pending",
            trigger_time=self.now,
            trigger_price=3000.00,
            trigger_volume=1000.00,
            trigger_kline_high=3100.00,
            trigger_kline_low=2900.00,
            market_type="futures",
            phase_1_passed=False,
            phase_2_passed=False,
            phase_3_passed=False,
        )

        response = self.client.get(f"/api/volume-trap/chart-data/{empty_monitor.id}/")

        # 当没有K线数据时，ChartDataFormatter会抛出DataFormatError，导致500错误
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("error", response.data)

    def test_get_chart_data_spot_market_type(self):
        """测试现货市场类型：应返回spot数据。"""
        # 创建现货合约
        spot_contract = SpotContract.objects.create(
            symbol="BTCUSDT",
            exchange=self.exchange,
            status="active",
            current_price=50000.00,
            first_seen=django_timezone.now(),
        )

        # 创建现货监控记录
        spot_monitor = VolumeTrapMonitor.objects.create(
            spot_contract=spot_contract,
            interval="4h",
            status="pending",
            trigger_time=self.now,
            trigger_price=50000.00,
            trigger_volume=1000.00,
            trigger_kline_high=50100.00,
            trigger_kline_low=49900.00,
            market_type="spot",
            phase_1_passed=False,
            phase_2_passed=False,
            phase_3_passed=False,
        )

        # 创建现货K线数据
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
            open_time=self.now,
            close_time=self.now + django_timezone.timedelta(hours=4),
        )

        response = self.client.get(f"/api/volume-trap/chart-data/{spot_monitor.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("data", response.data)

    def test_get_chart_data_performance(self):
        """测试性能：应在1秒内完成查询。"""
        import time

        start = time.time()
        response = self.client.get(f"/api/volume-trap/chart-data/{self.monitor.id}/")
        elapsed = time.time() - start

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLess(elapsed, 1.0, f"API响应时间{elapsed:.2f}秒，超过1秒限制")

    # 注意：无效monitor_id测试已移除，因为Django的URL模式<int:monitor_id>
    # 会在到达视图之前就拒绝非正整数，这是正确的URL路由行为
    # monitor_not_found测试已经覆盖了不存在的ID的情况


# 测试用的URL配置
urlpatterns = [
    path("api/volume-trap/", include("volume_trap.urls")),
]
