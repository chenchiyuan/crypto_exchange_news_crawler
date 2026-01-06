"""
代币列表组件集成测试

测试代币列表组件的完整功能，包括：
- API数据加载
- 列表渲染
- 状态显示
- 数据格式化

Related:
    - PRD: docs/iterations/006-volume-trap-dashboard/prd.md (F1.1)
    - Architecture: docs/iterations/006-volume-trap-dashboard/architecture.md (6.2)
    - Task: TASK-006-008
"""

from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone as django_timezone

from monitor.models import Exchange, FuturesContract, SpotContract
from volume_trap.models import VolumeTrapMonitor


class TokenListComponentTest(TestCase):
    """测试代币列表组件。"""

    def setUp(self):
        """设置测试环境。"""
        self.client = Client()
        self.now = django_timezone.now()

        # 创建交易所
        self.exchange = Exchange.objects.create(name="Test Exchange", code="TEST", enabled=True)

        # 创建合约
        self.futures_contract = FuturesContract.objects.create(
            symbol="BTCUSDT",
            exchange=self.exchange,
            contract_type="perpetual",
            status="active",
            current_price=50000.00,
            first_seen=self.now,
        )

        # 创建监控记录
        self.monitor = VolumeTrapMonitor.objects.create(
            futures_contract=self.futures_contract,
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

    def test_dashboard_page_loads(self):
        """测试Dashboard页面正常加载。"""
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)

    def test_dashboard_contains_token_list_container(self):
        """测试Dashboard包含代币列表容器。"""
        response = self.client.get("/dashboard/")
        content = response.content.decode("utf-8")

        # 验证包含代币列表容器
        self.assertIn("monitor-list", content)
        self.assertIn("token-table", content)
        self.assertIn("token-list-body", content)

    def test_dashboard_contains_filter_elements(self):
        """测试Dashboard包含筛选器元素。"""
        response = self.client.get("/dashboard/")
        content = response.content.decode("utf-8")

        # 验证包含筛选器
        self.assertIn("status-filter", content)
        self.assertIn("interval-filter", content)
        self.assertIn("start-date", content)
        self.assertIn("end-date", content)

    def test_dashboard_contains_pagination(self):
        """测试Dashboard包含分页组件。"""
        response = self.client.get("/dashboard/")
        content = response.content.decode("utf-8")

        # 验证包含分页
        self.assertIn("pagination", content)

    def test_api_returns_monitor_data(self):
        """测试API返回监控数据。"""
        response = self.client.get("/api/volume-trap/monitors/")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("results", data)
        self.assertIn("count", data)
        self.assertGreaterEqual(data["count"], 1)

    def test_api_monitor_data_structure(self):
        """测试API返回的监控数据结构。"""
        response = self.client.get("/api/volume-trap/monitors/")
        data = response.json()

        # 验证数据结构
        if data["results"]:
            monitor = data["results"][0]
            self.assertIn("id", monitor)
            self.assertIn("symbol", monitor)
            self.assertIn("interval", monitor)
            self.assertIn("status", monitor)
            self.assertIn("trigger_time", monitor)
            self.assertIn("trigger_price", monitor)

    def test_dashboard_contains_javascript_config(self):
        """测试Dashboard包含JavaScript配置。"""
        response = self.client.get("/dashboard/")
        content = response.content.decode("utf-8")

        # 验证包含JavaScript配置
        self.assertIn("Dashboard", content)
        self.assertIn("apiBaseUrl", content)
        self.assertIn("/api/volume-trap", content)

    def test_dashboard_context_contains_default_filters(self):
        """测试Dashboard上下文包含默认筛选条件。"""
        response = self.client.get("/dashboard/")

        # 验证上下文包含默认筛选条件
        self.assertIn("default_filters", response.context)
        default_filters = response.context["default_filters"]

        self.assertIn("status", default_filters)
        self.assertIn("interval", default_filters)
        self.assertIn("start_date", default_filters)
        self.assertIn("end_date", default_filters)


class TokenListAPIIntegrationTest(TestCase):
    """测试代币列表API集成。"""

    def setUp(self):
        """设置测试环境。"""
        self.client = Client()
        self.now = django_timezone.now()

        # 创建交易所
        self.exchange = Exchange.objects.create(name="Test Exchange", code="TEST", enabled=True)

        # 创建多个监控记录用于测试筛选和分页
        for i in range(25):
            contract = FuturesContract.objects.create(
                symbol=f"TOKEN{i}USDT",
                exchange=self.exchange,
                contract_type="perpetual",
                status="active",
                current_price=100.00 * (i + 1),
                first_seen=self.now,
            )

            status = ["pending", "suspected_abandonment", "confirmed_abandonment", "invalidated"][
                i % 4
            ]
            interval = ["1h", "4h", "1d"][i % 3]

            VolumeTrapMonitor.objects.create(
                futures_contract=contract,
                interval=interval,
                status=status,
                trigger_time=self.now - timedelta(hours=i),
                trigger_price=Decimal(str(100.00 * (i + 1))),
                trigger_volume=Decimal("1000.00"),
                trigger_kline_high=Decimal(str(110.00 * (i + 1))),
                trigger_kline_low=Decimal(str(90.00 * (i + 1))),
                market_type="futures",
                phase_1_passed=False,
                phase_2_passed=False,
                phase_3_passed=False,
            )

    def test_pagination_default_page_size(self):
        """测试默认分页大小。"""
        response = self.client.get("/api/volume-trap/monitors/")
        data = response.json()

        # 默认每页20条
        self.assertEqual(len(data["results"]), 20)
        self.assertEqual(data["count"], 25)

    def test_pagination_custom_page_size(self):
        """测试自定义分页大小。"""
        response = self.client.get("/api/volume-trap/monitors/?page_size=10")
        data = response.json()

        self.assertEqual(len(data["results"]), 10)

    def test_pagination_second_page(self):
        """测试第二页。"""
        response = self.client.get("/api/volume-trap/monitors/?page=2")
        data = response.json()

        # 第二页应该有5条（25 - 20 = 5）
        self.assertEqual(len(data["results"]), 5)

    def test_filter_by_status(self):
        """测试按状态筛选。"""
        response = self.client.get("/api/volume-trap/monitors/?status=pending")
        data = response.json()

        # 验证所有结果都是pending状态
        for monitor in data["results"]:
            self.assertEqual(monitor["status"], "pending")

    def test_filter_by_interval(self):
        """测试按周期筛选。"""
        response = self.client.get("/api/volume-trap/monitors/?interval=4h")
        data = response.json()

        # 验证所有结果都是4h周期
        for monitor in data["results"]:
            self.assertEqual(monitor["interval"], "4h")

    def test_filter_combined(self):
        """测试组合筛选。"""
        response = self.client.get("/api/volume-trap/monitors/?status=pending&interval=4h")
        data = response.json()

        # 验证所有结果都满足组合条件
        for monitor in data["results"]:
            self.assertEqual(monitor["status"], "pending")
            self.assertEqual(monitor["interval"], "4h")

    def test_order_by_created_at_desc(self):
        """测试按创建时间倒序排列。"""
        response = self.client.get("/api/volume-trap/monitors/")
        data = response.json()

        # 验证结果按创建时间倒序（最新的在前）
        if len(data["results"]) > 1:
            for i in range(len(data["results"]) - 1):
                # 通过ID判断创建顺序（ID越大创建越晚）
                self.assertGreater(data["results"][i]["id"], data["results"][i + 1]["id"])
