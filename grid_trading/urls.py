"""
Grid Trading URL Configuration
网格交易系统URL配置
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views_price_monitor import (
    MonitoredContractViewSet,
    PriceAlertRuleViewSet,
    AlertTriggerLogViewSet,
    DataUpdateLogViewSet,
    SystemConfigViewSet,
    price_monitor_dashboard
)

app_name = 'grid_trading'

# REST API Router for Price Monitor
price_monitor_router = DefaultRouter()
price_monitor_router.register(r'contracts', MonitoredContractViewSet, basename='monitored-contract')
price_monitor_router.register(r'rules', PriceAlertRuleViewSet, basename='price-alert-rule')
price_monitor_router.register(r'logs', AlertTriggerLogViewSet, basename='alert-trigger-log')
price_monitor_router.register(r'data-updates', DataUpdateLogViewSet, basename='data-update-log')
price_monitor_router.register(r'configs', SystemConfigViewSet, basename='system-config')

urlpatterns = [
    # 主页
    path('screening/', views.screening_index, name='screening_index'),

    # API endpoints
    path('screening/api/latest/', views.get_latest_screening, name='latest_screening'),
    path('screening/api/history/', views.get_screening_history, name='screening_history'),
    path('screening/api/history/<int:record_id>/', views.get_screening_detail, name='screening_detail'),
    path('screening/api/dates/', views.get_screening_dates, name='screening_dates'),

    # Daily Screening Dashboard
    path('screening/daily/', views.daily_screening_dashboard, name='daily_screening_dashboard'),
    path('screening/daily/api/dates/', views.get_daily_screening_dates, name='daily_screening_dates'),
    path('screening/daily/api/<str:date_str>/', views.get_daily_screening_detail, name='daily_screening_detail'),

    # Contract Detail Pages (Feature: 007-contract-detail-page)
    path('screening/daily/<str:date>/', views.screening_daily_detail, name='screening_daily_detail'),
    path('screening/daily/<str:date>/<str:symbol>/', views.contract_detail, name='contract_detail'),

    # K-line Data API for Contract Detail
    path('api/screening/<str:date>/<str:symbol>/klines/', views.api_klines, name='api_klines'),

    # Backtest Dashboard
    path('backtest/dashboard/', views.backtest_dashboard, name='backtest_dashboard'),
    path('backtest/data/', views.backtest_data, name='backtest_data'),

    # Grid Dashboard
    path('grids/', views.grid_dashboard, name='grid_dashboard'),
    path('grids/<int:config_id>/', views.grid_detail_page, name='grid_detail_page'),

    # Grid API
    path('api/grids/', views.get_grids_list, name='grids_list'),
    path('api/grids/<int:config_id>/', views.get_grid_detail, name='grid_detail'),

    # Trade Logs API
    path('trade-logs/<int:config_id>/', views.get_trade_logs, name='trade_logs'),
    path('trade-logs/<int:config_id>/summary/', views.get_trade_logs_summary, name='trade_logs_summary'),

    # Price Monitor Dashboard
    path('price-monitor/', price_monitor_dashboard, name='price_monitor_dashboard'),

    # Price Monitor API
    path('price-monitor/api/', include(price_monitor_router.urls)),
]
