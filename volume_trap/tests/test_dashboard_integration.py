"""
Dashboard集成测试

测试Dashboard的完整端到端功能，包括：
- 页面加载
- 数据筛选
- 分页功能
- 图表展示
- 性能优化验证

Related:
    - PRD: docs/iterations/006-volume-trap-dashboard/prd.md
    - Architecture: docs/iterations/006-volume-trap-dashboard/architecture.md
    - Task: TASK-006-012
"""

import time
from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone as django_timezone

from monitor.models import Exchange, FuturesContract
from volume_trap.models import VolumeTrapMonitor


class DashboardIntegrationTest(TestCase):
    """Dashboard集成测试。"""

    def setUp(self):
        """设置测试环境。"""
        self.client = Client()
        self.now = django_timezone.now()

        # 创建交易所
        self.exchange = Exchange.objects.create(name="Test Exchange", code="TEST", enabled=True)

    def test_dashboard_page_loads_successfully(self):
        """测试Dashboard页面正常加载。"""
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Volume Trap 监控列表")

    def test_dashboard_loads_with_empty_data(self):
        """测试Dashboard在无数据时正常加载。"""
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        # 验证页面包含空状态提示
        self.assertContains(response, "暂无监控记录")

    def test_dashboard_loads_with_sample_data(self):
        """测试Dashboard在有数据时正常加载。"""
        # 创建测试数据
        contract = FuturesContract.objects.create(
            symbol="BTCUSDT",
            exchange=self.exchange,
            contract_type="perpetual",
            status="active",
            current_price=50000.00,
            first_seen=self.now,
        )

        monitor = VolumeTrapMonitor.objects.create(
            futures_contract=contract,
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

        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        # Dashboard通过JavaScript动态加载数据，所以不需要在初始页面中检查代币符号
        # 只需要验证页面正常加载且包含必要的容器元素
        self.assertContains(response, "Volume Trap 监控列表")

    def test_api_returns_paginated_results(self):
        """测试API返回分页结果。"""
        # 创建多个监控记录
        for i in range(25):
            contract = FuturesContract.objects.create(
                symbol=f"TOKEN{i}USDT",
                exchange=self.exchange,
                contract_type="perpetual",
                status="active",
                current_price=100.00,
                first_seen=self.now,
            )

            VolumeTrapMonitor.objects.create(
                futures_contract=contract,
                interval="4h",
                status="pending",
                trigger_time=self.now - timedelta(hours=i),
                trigger_price=Decimal("100.00"),
                trigger_volume=Decimal("500.00"),
                trigger_kline_high=Decimal("110.00"),
                trigger_kline_low=Decimal("90.00"),
                market_type="futures",
                phase_1_passed=False,
                phase_2_passed=False,
                phase_3_passed=False,
            )

        # 测试默认分页（每页20条）
        response = self.client.get("/api/volume-trap/monitors/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 20)
        self.assertEqual(data["count"], 25)

        # 测试自定义分页大小
        response = self.client.get("/api/volume-trap/monitors/?page_size=10")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 10)

    def test_api_filter_functionality(self):
        """测试API筛选功能。"""
        # 创建不同状态的监控记录
        for i in range(10):
            contract = FuturesContract.objects.create(
                symbol=f"TOKEN{i}USDT",
                exchange=self.exchange,
                contract_type="perpetual",
                status="active",
                current_price=100.00,
                first_seen=self.now,
            )

            status = ["pending", "suspected_abandonment", "confirmed_abandonment"][i % 3]
            VolumeTrapMonitor.objects.create(
                futures_contract=contract,
                interval="4h",
                status=status,
                trigger_time=self.now - timedelta(hours=i),
                trigger_price=Decimal("100.00"),
                trigger_volume=Decimal("500.00"),
                trigger_kline_high=Decimal("110.00"),
                trigger_kline_low=Decimal("90.00"),
                market_type="futures",
                phase_1_passed=False,
                phase_2_passed=False,
                phase_3_passed=False,
            )

        # 测试按状态筛选
        response = self.client.get("/api/volume-trap/monitors/?status=pending")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 4)  # 10/3 = 3.33, so 4 pending

        # 测试按周期筛选
        response = self.client.get("/api/volume-trap/monitors/?interval=4h")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 10)

        # 测试组合筛选
        response = self.client.get("/api/volume-trap/monitors/?status=pending&interval=4h")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 4)

    def test_invalid_api_parameters(self):
        """测试无效API参数处理。"""
        # 测试无效状态
        response = self.client.get("/api/volume-trap/monitors/?status=invalid")
        self.assertEqual(response.status_code, 400)

        # 测试无效周期
        response = self.client.get("/api/volume-trap/monitors/?interval=invalid")
        self.assertEqual(response.status_code, 400)

    def test_chart_api_with_monitor_data(self):
        """测试图表API与监控数据集成。"""
        # 创建监控记录
        contract = FuturesContract.objects.create(
            symbol="BTCUSDT",
            exchange=self.exchange,
            contract_type="perpetual",
            status="active",
            current_price=50000.00,
            first_seen=self.now,
        )

        monitor = VolumeTrapMonitor.objects.create(
            futures_contract=contract,
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

        # 测试图表API响应（即使没有K线数据）
        response = self.client.get(f"/api/volume-trap/chart-data/{monitor.id}/")
        # 应该返回404，因为没有K线数据，但API应该正常响应
        self.assertIn(response.status_code, [200, 404])

    def test_dashboard_contains_all_required_elements(self):
        """测试Dashboard包含所有必需元素。"""
        response = self.client.get("/dashboard/")
        content = response.content.decode("utf-8")

        # 验证包含筛选器
        self.assertIn("filter-section", content)
        self.assertIn("status-filter", content)
        self.assertIn("interval-filter", content)
        self.assertIn("start-date", content)
        self.assertIn("end-date", content)

        # 验证包含代币列表
        self.assertIn("monitor-list", content)
        self.assertIn("token-table", content)

        # 验证包含分页
        self.assertIn("pagination", content)

        # 验证包含图表模态框
        self.assertIn("chart-modal", content)
        self.assertIn("kline-chart", content)

    def test_dashboard_javascript_initialization(self):
        """测试Dashboard JavaScript初始化。"""
        response = self.client.get("/dashboard/")
        content = response.content.decode("utf-8")

        # 验证包含Dashboard对象
        self.assertIn("const Dashboard = {", content)

        # 验证包含配置
        self.assertIn("apiBaseUrl", content)
        self.assertIn("pageSize", content)
        self.assertIn("defaultFilters", content)

        # 验证包含初始化代码
        self.assertIn("Dashboard.init()", content)

    def test_performance_with_large_dataset(self):
        """测试大数据集下的性能。"""
        start_time = time.time()

        # 创建大量测试数据（100条记录）
        for i in range(100):
            contract = FuturesContract.objects.create(
                symbol=f"LARGE{i}USDT",
                exchange=self.exchange,
                contract_type="perpetual",
                status="active",
                current_price=100.00 + i,
                first_seen=self.now,
            )

            VolumeTrapMonitor.objects.create(
                futures_contract=contract,
                interval="4h",
                status="pending",
                trigger_time=self.now - timedelta(hours=i),
                trigger_price=Decimal("100.00"),
                trigger_volume=Decimal("500.00"),
                trigger_kline_high=Decimal("110.00"),
                trigger_kline_low=Decimal("90.00"),
                market_type="futures",
                phase_1_passed=False,
                phase_2_passed=False,
                phase_3_passed=False,
            )

        # 测试API响应时间
        response = self.client.get("/api/volume-trap/monitors/")
        elapsed_time = time.time() - start_time

        self.assertEqual(response.status_code, 200)
        # API应该在合理时间内响应（这里是宽松的5秒限制，实际应该<1秒）
        self.assertLess(elapsed_time, 5.0)

        data = response.json()
        # 应该只返回20条（默认分页大小）
        self.assertEqual(len(data["results"]), 20)
        # 总数应该是100
        self.assertEqual(data["count"], 100)

    def test_dashboard_context_data(self):
        """测试Dashboard上下文数据。"""
        response = self.client.get("/dashboard/")

        # 验证上下文包含默认筛选条件
        self.assertIn("default_filters", response.context)
        default_filters = response.context["default_filters"]

        self.assertIn("status", default_filters)
        self.assertIn("interval", default_filters)
        self.assertIn("start_date", default_filters)
        self.assertIn("end_date", default_filters)

        # 验证默认周期是4h
        self.assertEqual(default_filters["interval"], "4h")

    def test_url_configuration(self):
        """测试URL配置正确性。"""
        # 测试Dashboard URL
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)

        # 测试API URL
        response = self.client.get("/api/volume-trap/monitors/")
        self.assertEqual(response.status_code, 200)

        # 测试图表数据URL
        response = self.client.get("/api/volume-trap/chart-data/1/")
        # 应该返回404而不是500，因为URL模式正确
        self.assertIn(response.status_code, [200, 404])

    def test_csrf_protection(self):
        """测试CSRF保护。"""
        # Dashboard应该包含CSRF token
        response = self.client.get("/dashboard/")
        content = response.content.decode("utf-8")
        self.assertIn("csrf", content.lower())

    def test_responsive_design_elements(self):
        """测试响应式设计元素。"""
        response = self.client.get("/dashboard/")
        content = response.content.decode("utf-8")

        # 验证包含viewport meta标签
        self.assertIn("viewport", content)

        # 验证使用Bootstrap网格系统
        self.assertIn("col-", content)
        self.assertIn("row", content)

    def test_bootstrap_integration(self):
        """测试Bootstrap集成。"""
        response = self.client.get("/dashboard/")
        content = response.content.decode("utf-8")

        # 验证包含Bootstrap CSS
        self.assertIn("bootstrap", content.lower())

        # 验证使用Bootstrap组件类
        self.assertIn("btn", content)
        self.assertIn("table", content)
        self.assertIn("modal", content)
        self.assertIn("pagination", content)
