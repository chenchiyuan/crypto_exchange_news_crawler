"""
DDPS-Z Views

动态偏离概率空间2.0系统的前端视图。
"""

from django.shortcuts import render
from django.views import View


def dashboard(request):
    """Dashboard页面 - 显示合约列表"""
    return render(request, 'ddps_z/dashboard.html')


def detail(request, symbol):
    """合约详情页 - 显示K线图和概率带"""
    context = {
        'symbol': symbol,
    }
    return render(request, 'ddps_z/detail.html', context)
