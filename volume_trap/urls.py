"""
Volume Trap API URL配置

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md (第五部分-7.1 监控池列表API)
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md (API服务层)
    - Task: TASK-002-040, TASK-006-004, TASK-006-005
"""

from django.urls import path

from volume_trap.api_views import (
    BacktestDetailView,
    BacktestListView,
    BacktestSearchView,
    ChartDataAPIView,
    ChartDataView,
    KLineDataAPIView,
    StatisticsSummaryView,
    StatisticsView,
)
from volume_trap.views import MonitorListAPIView

app_name = "volume_trap"

urlpatterns = [
    # 监控池列表API
    path("monitors/", MonitorListAPIView.as_view(), name="monitor-list"),
    # K线数据API
    path("kline/<str:symbol>/", KLineDataAPIView.as_view(), name="kline-data"),
    # 图表数据API
    path("chart-data/<int:monitor_id>/", ChartDataAPIView.as_view(), name="chart-data"),
    # 回测相关API
    path("backtest/", BacktestListView.as_view(), name="backtest-list"),
    path("backtest/<int:backtest_id>/", BacktestDetailView.as_view(), name="backtest-detail"),
    path("backtest/search/", BacktestSearchView.as_view(), name="backtest-search"),
    path("statistics/", StatisticsView.as_view(), name="statistics"),
    path("statistics/summary/", StatisticsSummaryView.as_view(), name="statistics-summary"),
    path("chart/<int:backtest_id>/", ChartDataView.as_view(), name="chart-data-backtest"),
]
