"""
Backtest URL Configuration
"""
from django.urls import path
from . import views

app_name = 'backtest'

urlpatterns = [
    path('', views.index, name='index'),
    path('player/', views.player_view, name='player'),
    path('api/run/', views.run_backtest_view, name='run_backtest'),
    path('api/symbols/', views.get_symbols, name='get_symbols'),
    path('api/intervals/', views.get_intervals, name='get_intervals'),

    # 新增快照相关API
    path('api/backtests/', views.get_backtest_list, name='backtest_list'),
    path('api/backtests/<int:backtest_id>/', views.get_backtest_detail, name='backtest_detail'),
    path('api/backtests/<int:backtest_id>/snapshots/', views.get_backtest_snapshots, name='backtest_snapshots'),
    path('api/backtests/<int:backtest_id>/snapshots/<int:kline_index>/', views.get_snapshot_detail, name='snapshot_detail'),
]
