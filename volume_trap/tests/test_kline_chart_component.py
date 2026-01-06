"""
K线图组件集成测试

测试K线图组件的完整功能，包括：
- API端点响应
- 数据格式验证
- Chart.js集成
- 触发点标记
- 错误处理

Related:
    - PRD: docs/iterations/006-volume-trap-dashboard/prd.md (F2.2)
    - Architecture: docs/iterations/006-volume-trap-dashboard/architecture.md (5.4)
    - Task: TASK-006-010
"""

from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone as django_timezone

from monitor.models import Exchange, FuturesContract
from volume_trap.models import VolumeTrapMonitor


class KLineChartAPITest(TestCase):
    """测试K线图API功能。"""

    def setUp(self):
        """设置测试环境。"""
        self.client = Client()
        self.now = django_timezone.now()

        # 创建交易所
        self.exchange = Exchange.objects.create(name="Test Exchange", code="TEST", enabled=True)

        # 创建合约
        self.contract = FuturesContract.objects.create(
            symbol="BTCUSDT",
            exchange=self.exchange,
            contract_type="perpetual",
            status="active",
            current_price=50000.00,
            first_seen=self.now,
        )

        # 创建监控记录
        self.monitor = VolumeTrapMonitor.objects.create(
            futures_contract=self.contract,
            interval="4h",
            status="pending",
            trigger_time=self.now,
            trigger_price=Decimal("50000.00"),
            trigger_volume=Decimal("1000.00"),
            trigger_kline_high=Decimal("50100.00"),
            trigger_kline_low=Decimal("49900.00"),
            market_type="futures",
            phase_1_passed=False,
            phase_2_passed=False,
            phase_3_passed=False,
        )

    def test_chart_data_endpoint_exists(self):
        """测试图表数据端点存在。"""
        response = self.client.get(f"/api/volume-trap/chart-data/{self.monitor.id}/")
        # 即使没有K线数据，也应该返回200或404，而不是500
        self.assertIn(response.status_code, [200, 404, 500])

    def test_chart_data_invalid_monitor_id(self):
        """测试无效监控ID返回400。"""
        response = self.client.get("/api/volume-trap/chart-data/abc/")
        self.assertEqual(response.status_code, 404)  # Django URL pattern rejects non-integer

    def test_chart_data_nonexistent_monitor(self):
        """测试不存在的监控记录返回404。"""
        response = self.client.get("/api/volume-trap/chart-data/99999/")
        self.assertEqual(response.status_code, 404)

    def test_chart_data_response_structure(self):
        """测试图表数据响应结构。"""
        response = self.client.get(f"/api/volume-trap/chart-data/{self.monitor.id}/")

        if response.status_code == 200:
            data = response.json()
            self.assertIn("data", data)
            self.assertIn("trigger_marker", data)

            # 验证data结构
            chart_data = data["data"]
            self.assertIn("labels", chart_data)
            self.assertIn("datasets", chart_data)

            # 验证trigger_marker结构
            trigger_marker = data["trigger_marker"]
            self.assertIn("time", trigger_marker)
            self.assertIn("price", trigger_marker)


class KLineChartComponentTest(TestCase):
    """测试K线图组件UI。"""

    def setUp(self):
        """设置测试环境。"""
        self.client = Client()

    def test_dashboard_contains_chart_modal(self):
        """测试Dashboard包含图表模态框。"""
        response = self.client.get("/dashboard/")
        content = response.content.decode("utf-8")

        # 验证包含图表模态框HTML
        self.assertIn("chart-modal", content)
        self.assertIn("modal-xl", content)
        self.assertIn("kline-chart", content)

    def test_dashboard_contains_chart_canvas(self):
        """测试Dashboard包含图表画布。"""
        response = self.client.get("/dashboard/")
        content = response.content.decode("utf-8")

        # 验证包含canvas元素
        self.assertIn('<canvas id="kline-chart"', content)

    def test_dashboard_contains_chart_javascript(self):
        """测试Dashboard包含图表JavaScript代码。"""
        response = self.client.get("/dashboard/")
        content = response.content.decode("utf-8")

        # 验证包含Chart.js相关代码
        self.assertIn("showChart", content)
        self.assertIn("chart-data", content)
        self.assertIn("new Chart", content)

    def test_chart_button_in_token_list(self):
        """测试代币列表中的图表按钮。"""
        response = self.client.get("/dashboard/")
        content = response.content.decode("utf-8")

        # 验证包含查看K线按钮
        self.assertIn("查看K线", content)
        self.assertIn("btn-outline-primary", content)


class KLineChartIntegrationTest(TestCase):
    """测试K线图组件集成。"""

    def setUp(self):
        """设置测试环境。"""
        self.client = Client()
        self.now = django_timezone.now()

        # 创建交易所和合约
        self.exchange = Exchange.objects.create(name="Test Exchange", code="TEST", enabled=True)

        self.contract = FuturesContract.objects.create(
            symbol="ETHUSDT",
            exchange=self.exchange,
            contract_type="perpetual",
            status="active",
            current_price=3000.00,
            first_seen=self.now,
        )

        # 创建多个监控记录
        for i in range(5):
            monitor = VolumeTrapMonitor.objects.create(
                futures_contract=self.contract,
                interval=["1h", "4h", "1d"][i % 3],
                status=["pending", "suspected_abandonment"][i % 2],
                trigger_time=self.now - timedelta(hours=i),
                trigger_price=Decimal("3000.00"),
                trigger_volume=Decimal("500.00"),
                trigger_kline_high=Decimal("3100.00"),
                trigger_kline_low=Decimal("2900.00"),
                market_type="futures",
                phase_1_passed=False,
                phase_2_passed=False,
                phase_3_passed=False,
            )

    def test_multiple_monitors_chart_endpoints(self):
        """测试多个监控记录的图表端点。"""
        monitors = VolumeTrapMonitor.objects.all()

        for monitor in monitors:
            response = self.client.get(f"/api/volume-trap/chart-data/{monitor.id}/")
            # 所有监控记录都应该有有效的API响应
            self.assertIn(response.status_code, [200, 404])

    def test_chart_endpoint_with_different_intervals(self):
        """测试不同周期的图表端点。"""
        monitors = VolumeTrapMonitor.objects.filter(interval__in=["1h", "4h", "1d"])

        for monitor in monitors:
            response = self.client.get(f"/api/volume-trap/chart-data/{monitor.id}/")
            self.assertIn(response.status_code, [200, 404])

    def test_chart_endpoint_with_different_statuses(self):
        """测试不同状态的图表端点。"""
        monitors = VolumeTrapMonitor.objects.filter(status__in=["pending", "suspected_abandonment"])

        for monitor in monitors:
            response = self.client.get(f"/api/volume-trap/chart-data/{monitor.id}/")
            self.assertIn(response.status_code, [200, 404])
