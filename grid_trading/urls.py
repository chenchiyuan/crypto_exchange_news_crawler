"""
Grid Trading URL Configuration
网格交易系统URL配置
"""
from django.urls import path
from . import views

app_name = 'grid_trading'

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
]
