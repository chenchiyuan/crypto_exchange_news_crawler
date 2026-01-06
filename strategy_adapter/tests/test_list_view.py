"""
测试文件：BacktestResultListView 视图测试

Purpose:
    验证回测结果列表视图的功能，包括列表展示、筛选和分页。

关联任务: TASK-014-016
关联需求: FP-014-021（prd.md）

测试策略:
    - 单元测试（使用 RequestFactory 直接测试视图）
    - 覆盖列表访问、筛选功能、分页功能
"""

import datetime
from decimal import Decimal

from django.test import TestCase, RequestFactory

from strategy_adapter.models.db_models import BacktestResult
from strategy_adapter.views import BacktestResultListView


class TestBacktestResultListView(TestCase):
    """BacktestResultListView 视图测试套件"""

    def setUp(self):
        """创建测试数据"""
        self.factory = RequestFactory()

        # 创建多条测试记录
        for i in range(25):  # 超过一页（20条）
            BacktestResult.objects.create(
                strategy_name="DDPS-Z" if i % 2 == 0 else "OTHER",
                symbol="BTCUSDT" if i % 3 == 0 else "ETHUSDT",
                interval="4h",
                market_type="futures" if i % 2 == 0 else "spot",
                start_date=datetime.date(2025, 1, 1),
                end_date=datetime.date(2025, 12, 31),
                initial_cash=Decimal("10000.00"),
                position_size=Decimal("100.00"),
                commission_rate=Decimal("0.001"),
                risk_free_rate=Decimal("3.00"),
                metrics={
                    "apr": "12.00",
                    "mdd": "-5.00",
                    "win_rate": "60.00",
                    "sharpe_ratio": "1.50"
                }
            )

    def test_list_view_returns_200(self):
        """
        测试用例1：列表页正常访问

        验收标准: 返回HTTP 200状态码
        """
        request = self.factory.get('/strategy-adapter/results/')
        response = BacktestResultListView.as_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_list_view_pagination(self):
        """
        测试用例2：分页功能

        验收标准: 每页显示20条，第一页有20条记录
        """
        request = self.factory.get('/strategy-adapter/results/')
        response = BacktestResultListView.as_view()(request)
        self.assertTrue(response.context_data['is_paginated'])
        self.assertEqual(len(response.context_data['results']), 20)
        self.assertEqual(response.context_data['page_obj'].paginator.count, 25)

    def test_list_view_second_page(self):
        """
        测试用例3：第二页访问

        验收标准: 第二页有5条记录
        """
        request = self.factory.get('/strategy-adapter/results/', {'page': '2'})
        response = BacktestResultListView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context_data['results']), 5)

    def test_list_view_filter_by_strategy(self):
        """
        测试用例4：按策略筛选

        验收标准: 筛选结果只包含指定策略
        """
        request = self.factory.get('/strategy-adapter/results/', {'strategy': 'DDPS-Z'})
        response = BacktestResultListView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        for result in response.context_data['results']:
            self.assertEqual(result.strategy_name, 'DDPS-Z')

    def test_list_view_filter_by_symbol(self):
        """
        测试用例5：按交易对筛选

        验收标准: 筛选结果只包含指定交易对
        """
        request = self.factory.get('/strategy-adapter/results/', {'symbol': 'BTCUSDT'})
        response = BacktestResultListView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        for result in response.context_data['results']:
            self.assertEqual(result.symbol, 'BTCUSDT')

    def test_list_view_filter_by_market_type(self):
        """
        测试用例6：按市场类型筛选

        验收标准: 筛选结果只包含指定市场类型
        """
        request = self.factory.get('/strategy-adapter/results/', {'market_type': 'futures'})
        response = BacktestResultListView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        for result in response.context_data['results']:
            self.assertEqual(result.market_type, 'futures')

    def test_list_view_combined_filters(self):
        """
        测试用例7：组合筛选

        验收标准: 多个筛选条件同时生效
        """
        request = self.factory.get('/strategy-adapter/results/', {
            'strategy': 'DDPS-Z',
            'symbol': 'BTCUSDT',
            'market_type': 'futures'
        })
        response = BacktestResultListView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        for result in response.context_data['results']:
            self.assertEqual(result.strategy_name, 'DDPS-Z')
            self.assertEqual(result.symbol, 'BTCUSDT')
            self.assertEqual(result.market_type, 'futures')

    def test_list_view_empty_result(self):
        """
        测试用例8：筛选无结果

        验收标准: 返回空列表
        """
        request = self.factory.get('/strategy-adapter/results/', {'strategy': 'NONEXISTENT'})
        response = BacktestResultListView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context_data['results']), 0)

    def test_list_view_ordering(self):
        """
        测试用例9：按创建时间倒序排列

        验收标准: 最新的记录排在前面
        """
        request = self.factory.get('/strategy-adapter/results/')
        response = BacktestResultListView.as_view()(request)
        results = list(response.context_data['results'])
        # 验证按创建时间倒序
        for i in range(len(results) - 1):
            self.assertGreaterEqual(
                results[i].created_at,
                results[i + 1].created_at
            )

    def test_list_view_context_has_filter_options(self):
        """
        测试用例10：上下文包含筛选选项

        验收标准: 上下文包含策略列表、交易对列表
        """
        request = self.factory.get('/strategy-adapter/results/')
        response = BacktestResultListView.as_view()(request)
        self.assertIn('strategies', response.context_data)
        self.assertIn('symbols', response.context_data)
        self.assertIn('market_types', response.context_data)


class TestBacktestResultListViewEmpty(TestCase):
    """空数据情况下的列表视图测试"""

    def test_list_view_no_records(self):
        """
        测试用例11：无记录时返回空列表

        验收标准: 返回空的结果列表
        """
        factory = RequestFactory()
        request = factory.get('/strategy-adapter/results/')
        response = BacktestResultListView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context_data['results']), 0)
