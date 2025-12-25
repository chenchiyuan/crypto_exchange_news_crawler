"""
MonitorListAPIView时间范围筛选功能测试

测试扩展MonitorListAPIView后的时间范围筛选功能，包括：
- start_date参数筛选
- end_date参数筛选
- 时间范围与状态筛选组合
- 参数验证
- 异常情况处理

Related:
    - PRD: docs/iterations/006-volume-trap-dashboard/prd.md (F3.3)
    - Architecture: docs/iterations/006-volume-trap-dashboard/architecture.md (5.2)
    - Task: TASK-006-001
"""

from datetime import datetime, timezone
from django.test import TestCase, override_settings
from django.urls import path, include, reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.utils import timezone as django_timezone

from volume_trap.models import VolumeTrapMonitor
from monitor.models import FuturesContract


@override_settings(ROOT_URLCONF=__name__)
class MonitorListAPITimeFilterTest(APITestCase):
    """测试MonitorListAPIView的时间范围筛选功能。"""

    def setUp(self):
        """测试前准备：创建测试数据。"""
        # 创建交易所
        from monitor.models import Exchange
        self.exchange = Exchange.objects.create(
            name='Test Exchange',
            code='TEST',
            enabled=True
        )

        # 创建测试合约
        self.contract1 = FuturesContract.objects.create(
            symbol='BTCUSDT',
            exchange=self.exchange,
            contract_type='perpetual',
            status='active',
            current_price=50000.00,
            first_seen=django_timezone.now()
        )

        self.contract2 = FuturesContract.objects.create(
            symbol='ETHUSDT',
            exchange=self.exchange,
            contract_type='perpetual',
            status='active',
            current_price=2000.00,
            first_seen=django_timezone.now()
        )

        # 创建测试监控记录
        self.now = django_timezone.now()

        self.monitor1 = VolumeTrapMonitor.objects.create(
            futures_contract=self.contract1,
            market_type='futures',
            interval='4h',
            trigger_time=self.now,
            trigger_price=50000.00,
            trigger_volume=1000.00,
            trigger_kline_high=51000.00,
            trigger_kline_low=49000.00,
            status='pending'
        )

        self.monitor2 = VolumeTrapMonitor.objects.create(
            futures_contract=self.contract2,
            market_type='futures',
            interval='4h',
            trigger_time=self.now,  # 同一时间
            trigger_price=2000.00,
            trigger_volume=500.00,
            trigger_kline_high=2100.00,
            trigger_kline_low=1900.00,
            status='confirmed_abandonment'
        )

    def test_time_filter_start_date_only(self):
        """测试仅使用start_date参数筛选。"""
        url = '/api/volume-trap/monitors/'
        start_date_str = self.now.strftime('%Y-%m-%d')

        response = self.client.get(url, {'start_date': start_date_str})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_time_filter_end_date_only(self):
        """测试仅使用end_date参数筛选。"""
        url = '/api/volume-trap/monitors/'
        end_date_str = self.now.strftime('%Y-%m-%d')

        response = self.client.get(url, {'end_date': end_date_str})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_time_filter_start_and_end_date(self):
        """测试同时使用start_date和end_date参数。"""
        url = '/api/volume-trap/monitors/'
        start_date_str = self.now.strftime('%Y-%m-%d')
        end_date_str = self.now.strftime('%Y-%m-%d')

        response = self.client.get(url, {
            'start_date': start_date_str,
            'end_date': end_date_str
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_time_filter_with_status_filter(self):
        """测试时间筛选与状态筛选组合（AND逻辑）。"""
        url = '/api/volume-trap/monitors/'
        start_date_str = self.now.strftime('%Y-%m-%d')

        # 筛选pending状态，应该返回1条记录
        response = self.client.get(url, {
            'start_date': start_date_str,
            'status': 'pending'
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['status'], 'pending')

    def test_time_filter_start_date_greater_than_end_date(self):
        """测试start_date > end_date时应返回400错误。"""
        url = '/api/volume-trap/monitors/'

        response = self.client.get(url, {
            'start_date': '2025-12-26',
            'end_date': '2025-12-24'
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_time_filter_invalid_start_date_format(self):
        """测试无效的start_date格式应返回400错误。"""
        url = '/api/volume-trap/monitors/'

        response = self.client.get(url, {'start_date': 'invalid-date'})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_time_filter_invalid_end_date_format(self):
        """测试无效的end_date格式应返回400错误。"""
        url = '/api/volume-trap/monitors/'

        response = self.client.get(url, {'end_date': 'invalid-date'})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_time_filter_no_date_parameters(self):
        """测试不传日期参数时应返回所有记录（向后兼容）。"""
        url = '/api/volume-trap/monitors/'

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_time_filter_boundary_date_range(self):
        """测试边界日期范围（当天开始到当天结束）。"""
        url = '/api/volume-trap/monitors/'

        # 使用同一天的开始和结束
        response = self.client.get(url, {
            'start_date': self.now.strftime('%Y-%m-%d'),
            'end_date': self.now.strftime('%Y-%m-%d')
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)


# 测试用的URL配置
urlpatterns = [
    path('api/volume-trap/', include('volume_trap.urls')),
]
