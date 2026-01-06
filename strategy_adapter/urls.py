"""
策略适配层URL配置

Purpose:
    定义回测结果页面的URL路由。

关联任务: TASK-014-016, TASK-014-017
关联需求: FP-014-021, FP-014-022（prd.md）

URL Patterns:
    - /results/: 回测结果列表页
    - /results/<int:pk>/: 回测结果详情页
"""

from django.urls import path
from . import views

app_name = 'strategy_adapter'

urlpatterns = [
    path('results/', views.BacktestResultListView.as_view(), name='result_list'),
    path('results/<int:pk>/', views.BacktestResultDetailView.as_view(), name='result_detail'),
]
