"""
URL configuration for listing_monitor_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

from volume_trap.views import (
    DashboardView,
    BacktestListPageView,
    BacktestStatisticsPageView,
    BacktestDetailPageView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('backtest/', include('backtest.urls')),
    path('grid-trading/', include('grid_trading.urls')),
    # Volume Trap Dashboard
    path('dashboard/', DashboardView.as_view(), name='volume-trap-dashboard'),
    # Volume Trap Backtest Frontend Pages
    path('backtest/results/', BacktestListPageView.as_view(), name='backtest-list'),
    path('backtest/results/statistics/', BacktestStatisticsPageView.as_view(), name='backtest-statistics'),
    path('backtest/results/<int:backtest_id>/', BacktestDetailPageView.as_view(), name='backtest-detail-page'),
    # Volume Trap API
    path('api/volume-trap/', include('volume_trap.urls')),
    # DDPS-Z 动态偏离概率空间 (迭代009)
    path('ddps-z/', include('ddps_z.urls')),
    # Strategy Adapter 策略适配层 (迭代013/014)
    path('strategy-adapter/', include('strategy_adapter.urls')),
    # 向后兼容: screening 的直接访问路径 (不使用namespace避免冲突)
    path('', include(('grid_trading.urls', 'grid_trading_root'))),
]
