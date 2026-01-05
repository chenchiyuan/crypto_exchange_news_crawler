"""
DDPS-Z URL Configuration

动态偏离概率空间2.0系统的URL路由配置。

Routes:
    - /ddps-z/ - Dashboard页面
    - /ddps-z/detail/<symbol>/ - 合约详情页
    - /api/ddps-z/contracts/ - 合约列表API
    - /api/ddps-z/calculate/ - DDPS计算API
    - /api/ddps-z/chart/ - K线图表API
"""

from django.urls import path

from . import views
from . import api_views

app_name = 'ddps_z'

urlpatterns = [
    # 页面路由
    path('', views.dashboard, name='dashboard'),
    path('detail/<str:symbol>/', views.detail, name='detail'),

    # API路由
    path('api/contracts/', api_views.ContractListAPIView.as_view(), name='api_contracts'),
    path('api/calculate/', api_views.DDPSCalculateAPIView.as_view(), name='api_calculate'),
    path('api/chart/', api_views.KLineChartAPIView.as_view(), name='api_chart'),
]
