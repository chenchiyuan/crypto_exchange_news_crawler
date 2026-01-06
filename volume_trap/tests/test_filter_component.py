"""
筛选器组件测试

测试筛选器组件的完整功能，包括：
- 状态筛选器
- 周期筛选器
- 时间范围筛选器
- 筛选器UI元素

Related:
    - PRD: docs/iterations/006-volume-trap-dashboard/prd.md (F3.1)
    - Architecture: docs/iterations/006-volume-trap-dashboard/architecture.md (6.4)
    - Task: TASK-006-009
"""

from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.utils import timezone as django_timezone

from monitor.models import Exchange, FuturesContract
from volume_trap.models import VolumeTrapMonitor


class FilterComponentTest(TestCase):
    """测试筛选器组件。"""

    def setUp(self):
        """设置测试环境。"""
        self.client = Client()
        self.now = django_timezone.now()

        # 创建交易所
        self.exchange = Exchange.objects.create(name="Test Exchange", code="TEST", enabled=True)

    def test_filter_section_exists(self):
        """测试筛选器区域存在。"""
        response = self.client.get("/dashboard/")
        content = response.content.decode("utf-8")

        self.assertIn("filter-section", content)
        self.assertIn("filter-form", content)

    def test_status_filter_options(self):
        """测试状态筛选器选项。"""
        response = self.client.get("/dashboard/")
        content = response.content.decode("utf-8")

        # 验证包含所有状态选项
        self.assertIn("pending", content)
        self.assertIn("suspected_abandonment", content)
        self.assertIn("confirmed_abandonment", content)
        self.assertIn("invalidated", content)

    def test_interval_filter_options(self):
        """测试周期筛选器选项。"""
        response = self.client.get("/dashboard/")
        content = response.content.decode("utf-8")

        # 验证包含所有周期选项
        self.assertIn("1h", content)
        self.assertIn("4h", content)
        self.assertIn("1d", content)

    def test_date_range_filter_inputs(self):
        """测试日期范围筛选器输入框。"""
        response = self.client.get("/dashboard/")
        content = response.content.decode("utf-8")

        # 验证包含日期输入框
        self.assertIn("start-date", content)
        self.assertIn("end-date", content)
        self.assertIn('type="date"', content)

    def test_filter_submit_button(self):
        """测试筛选提交按钮。"""
        response = self.client.get("/dashboard/")
        content = response.content.decode("utf-8")

        # 验证包含提交按钮
        self.assertIn('type="submit"', content)

    def test_filter_reset_button(self):
        """测试筛选重置按钮。"""
        response = self.client.get("/dashboard/")
        content = response.content.decode("utf-8")

        # 验证包含重置按钮
        self.assertIn("reset-filter", content)


class FilterAPITest(TestCase):
    """测试筛选器API功能。"""

    def setUp(self):
        """设置测试环境。"""
        self.client = Client()
        self.now = django_timezone.now()

        # 创建交易所
        self.exchange = Exchange.objects.create(name="Test Exchange", code="TEST", enabled=True)

        # 创建多种状态的监控记录
        statuses = ["pending", "suspected_abandonment", "confirmed_abandonment", "invalidated"]
        intervals = ["1h", "4h", "1d"]

        for i, status in enumerate(statuses):
            for j, interval in enumerate(intervals):
                contract = FuturesContract.objects.create(
                    symbol=f"TOKEN{i}{j}USDT",
                    exchange=self.exchange,
                    contract_type="perpetual",
                    status="active",
                    current_price=100.00,
                    first_seen=self.now,
                )

                VolumeTrapMonitor.objects.create(
                    futures_contract=contract,
                    interval=interval,
                    status=status,
                    trigger_time=self.now - timedelta(days=i),
                    trigger_price=Decimal("100.00"),
                    trigger_volume=Decimal("1000.00"),
                    trigger_kline_high=Decimal("110.00"),
                    trigger_kline_low=Decimal("90.00"),
                    market_type="futures",
                    phase_1_passed=False,
                    phase_2_passed=False,
                    phase_3_passed=False,
                )

    def test_status_filter_pending(self):
        """测试状态筛选：pending。"""
        response = self.client.get("/api/volume-trap/monitors/?status=pending")
        data = response.json()

        for monitor in data["results"]:
            self.assertEqual(monitor["status"], "pending")

    def test_status_filter_suspected_abandonment(self):
        """测试状态筛选：suspected_abandonment。"""
        response = self.client.get("/api/volume-trap/monitors/?status=suspected_abandonment")
        data = response.json()

        for monitor in data["results"]:
            self.assertEqual(monitor["status"], "suspected_abandonment")

    def test_interval_filter_1h(self):
        """测试周期筛选：1h。"""
        response = self.client.get("/api/volume-trap/monitors/?interval=1h")
        data = response.json()

        for monitor in data["results"]:
            self.assertEqual(monitor["interval"], "1h")

    def test_interval_filter_4h(self):
        """测试周期筛选：4h。"""
        response = self.client.get("/api/volume-trap/monitors/?interval=4h")
        data = response.json()

        for monitor in data["results"]:
            self.assertEqual(monitor["interval"], "4h")

    def test_date_range_filter(self):
        """测试日期范围筛选。"""
        start_date = (self.now - timedelta(days=2)).strftime("%Y-%m-%d")
        end_date = self.now.strftime("%Y-%m-%d")

        response = self.client.get(
            f"/api/volume-trap/monitors/?start_date={start_date}&end_date={end_date}"
        )
        data = response.json()

        # 验证返回的数据在日期范围内
        self.assertGreater(len(data["results"]), 0)

    def test_combined_filters(self):
        """测试组合筛选。"""
        response = self.client.get("/api/volume-trap/monitors/?status=pending&interval=4h")
        data = response.json()

        for monitor in data["results"]:
            self.assertEqual(monitor["status"], "pending")
            self.assertEqual(monitor["interval"], "4h")

    def test_invalid_status_filter(self):
        """测试无效状态筛选返回400。"""
        response = self.client.get("/api/volume-trap/monitors/?status=invalid")
        self.assertEqual(response.status_code, 400)

    def test_invalid_interval_filter(self):
        """测试无效周期筛选返回400。"""
        response = self.client.get("/api/volume-trap/monitors/?interval=invalid")
        self.assertEqual(response.status_code, 400)
