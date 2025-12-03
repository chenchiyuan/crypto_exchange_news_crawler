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
]
