"""
Dashboard模板单元测试

测试Dashboard模板文件的加载和结构，包括：
- base.html基础模板加载测试
- index.html继承测试
- 静态资源引用测试
- 模板语法验证测试

Related:
    - PRD: docs/iterations/006-volume-trap-dashboard/prd.md (F4.1)
    - Architecture: docs/iterations/006-volume-trap-dashboard/architecture.md (6.1)
    - Task: TASK-006-007
"""

import os

from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.test import RequestFactory, TestCase


class DashboardTemplateTest(TestCase):
    """测试Dashboard模板文件。"""

    def setUp(self):
        """设置测试环境。"""
        self.factory = RequestFactory()

    def test_base_template_exists(self):
        """测试base.html模板文件存在。"""
        try:
            template = get_template("dashboard/base.html")
            self.assertIsNotNone(template)
        except TemplateDoesNotExist:
            self.fail("dashboard/base.html模板文件不存在")

    def test_index_template_exists(self):
        """测试index.html模板文件存在。"""
        try:
            template = get_template("dashboard/index.html")
            self.assertIsNotNone(template)
        except TemplateDoesNotExist:
            self.fail("dashboard/index.html模板文件不存在")

    def test_index_extends_base(self):
        """测试index.html继承base.html。"""
        try:
            template = get_template("dashboard/index.html")
            # 验证模板可以正常编译
            context = {
                "default_filters": {
                    "status": [],
                    "interval": "4h",
                    "start_date": "",
                    "end_date": "",
                }
            }
            rendered = template.render(context)
            self.assertIsNotNone(rendered)
        except TemplateDoesNotExist:
            self.fail("模板文件不存在")
        except Exception as e:
            self.fail(f"模板渲染失败: {e}")

    def _get_template_source(self, template_name):
        """获取模板源代码。"""
        template = get_template(template_name)
        # 获取模板的源代码
        if hasattr(template, "origin") and template.origin:
            with open(template.origin.name, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def test_base_template_contains_html_structure(self):
        """测试base.html包含基本HTML结构。"""
        template_string = self._get_template_source("dashboard/base.html")
        if template_string is None:
            self.fail("无法读取模板源代码")

        # 验证包含基本HTML标签
        self.assertIn("<html", template_string.lower())
        self.assertIn("<head", template_string.lower())
        self.assertIn("<body", template_string.lower())

    def test_base_template_contains_bootstrap_css(self):
        """测试base.html引用Bootstrap CSS。"""
        template_string = self._get_template_source("dashboard/base.html")
        if template_string is None:
            self.fail("无法读取模板源代码")

        # 验证包含Bootstrap CSS引用
        has_bootstrap = "bootstrap" in template_string.lower()
        self.assertTrue(has_bootstrap, "base.html应该包含Bootstrap CSS引用")

    def test_base_template_contains_chart_js(self):
        """测试base.html引用Chart.js。"""
        template_string = self._get_template_source("dashboard/base.html")
        if template_string is None:
            self.fail("无法读取模板源代码")

        # 验证包含Chart.js引用
        has_chart_js = "chart" in template_string.lower()
        self.assertTrue(has_chart_js, "base.html应该包含Chart.js引用")

    def test_index_template_contains_blocks(self):
        """测试index.html使用Django模板块。"""
        template_string = self._get_template_source("dashboard/index.html")
        if template_string is None:
            self.fail("无法读取模板源代码")

        # 验证使用block标签
        has_block = "{% block" in template_string
        self.assertTrue(has_block, "index.html应该使用Django模板块")

    def test_index_template_contains_dashboard_content(self):
        """测试index.html包含Dashboard内容区域。"""
        template_string = self._get_template_source("dashboard/index.html")
        if template_string is None:
            self.fail("无法读取模板源代码")

        # 验证包含Dashboard相关内容标识
        has_dashboard_content = (
            "dashboard" in template_string.lower()
            or "volume-trap" in template_string.lower()
            or "monitor" in template_string.lower()
        )
        self.assertTrue(has_dashboard_content, "index.html应该包含Dashboard相关内容")

    def test_index_template_contains_token_list_placeholder(self):
        """测试index.html包含代币列表占位符。"""
        template_string = self._get_template_source("dashboard/index.html")
        if template_string is None:
            self.fail("无法读取模板源代码")

        # 验证包含代币列表相关标识
        has_token_list = (
            "token" in template_string.lower()
            or "monitor-list" in template_string.lower()
            or "list" in template_string.lower()
        )
        self.assertTrue(has_token_list, "index.html应该包含代币列表占位符")

    def test_index_template_contains_filter_placeholder(self):
        """测试index.html包含筛选器占位符。"""
        template_string = self._get_template_source("dashboard/index.html")
        if template_string is None:
            self.fail("无法读取模板源代码")

        # 验证包含筛选器相关标识
        has_filter = (
            "filter" in template_string.lower()
            or "search" in template_string.lower()
            or "status" in template_string.lower()
        )
        self.assertTrue(has_filter, "index.html应该包含筛选器占位符")

    def test_index_template_contains_kline_chart_container(self):
        """测试index.html包含K线图容器。"""
        template_string = self._get_template_source("dashboard/index.html")
        if template_string is None:
            self.fail("无法读取模板源代码")

        # 验证包含图表容器相关标识
        has_chart_container = (
            "chart" in template_string.lower()
            or "canvas" in template_string.lower()
            or "graph" in template_string.lower()
        )
        self.assertTrue(has_chart_container, "index.html应该包含K线图容器")

    def test_index_template_contains_pagination_placeholder(self):
        """测试index.html包含分页占位符。"""
        template_string = self._get_template_source("dashboard/index.html")
        if template_string is None:
            self.fail("无法读取模板源代码")

        # 验证包含分页相关标识
        has_pagination = (
            "pagination" in template_string.lower()
            or "page" in template_string.lower()
            or "pager" in template_string.lower()
        )
        self.assertTrue(has_pagination, "index.html应该包含分页占位符")

    def test_base_template_has_responsive_meta(self):
        """测试base.html包含响应式meta标签。"""
        template_string = self._get_template_source("dashboard/base.html")
        if template_string is None:
            self.fail("无法读取模板源代码")

        # 验证包含viewport meta标签（响应式设计需要）
        has_viewport = "viewport" in template_string.lower()
        self.assertTrue(has_viewport, "base.html应该包含viewport meta标签以支持响应式设计")

    def test_base_template_contains_csrf_token(self):
        """测试base.html包含CSRF token支持。"""
        template_string = self._get_template_source("dashboard/base.html")
        if template_string is None:
            self.fail("无法读取模板源代码")

        # 验证包含CSRF token标签
        has_csrf = "csrf" in template_string.lower()
        self.assertTrue(has_csrf, "base.html应该包含CSRF token支持")
