"""
策略适配层视图模块

Purpose:
    提供回测结果的Web界面视图，包括列表页和详情页。

关联任务: TASK-014-016, TASK-014-017
关联需求: FP-014-021, FP-014-022（prd.md）

Views:
    - BacktestResultListView: 回测结果列表页（支持筛选、排序、分页）
    - BacktestResultDetailView: 回测结果详情页（含权益曲线图）
"""

from django.views.generic import ListView, DetailView
from django.db.models import Q

from strategy_adapter.models.db_models import BacktestResult, BacktestOrder


class BacktestResultListView(ListView):
    """
    回测结果列表视图

    Purpose:
        展示所有回测结果，支持筛选、排序和分页功能。
        用户可以按策略名称、交易对和市场类型筛选记录。

    Features:
        - 筛选：支持按 strategy_name、symbol、market_type 筛选
        - 排序：按 created_at 倒序排列（最新优先）
        - 分页：每页显示 20 条记录

    Template:
        strategy_adapter/backtest_list.html

    Context Variables:
        - object_list: 回测结果列表
        - page_obj: 分页对象
        - is_paginated: 是否分页
        - filter_strategy: 当前策略筛选值
        - filter_symbol: 当前交易对筛选值
        - filter_market_type: 当前市场类型筛选值
        - strategies: 可用的策略列表（用于筛选下拉框）
        - symbols: 可用的交易对列表（用于筛选下拉框）

    URL:
        /strategy-adapter/results/

    Example:
        访问 /strategy-adapter/results/?strategy=DDPS-Z&symbol=BTCUSDT
        将显示所有 DDPS-Z 策略在 BTCUSDT 上的回测结果

    Context:
        关联任务：TASK-014-016
        关联需求：FP-014-021
    """

    model = BacktestResult
    template_name = 'strategy_adapter/backtest_list.html'
    context_object_name = 'results'
    paginate_by = 20
    ordering = ['-created_at']

    def get_queryset(self):
        """
        获取查询集，应用筛选条件

        Returns:
            QuerySet: 过滤后的回测结果查询集
        """
        queryset = super().get_queryset()

        # 获取筛选参数
        strategy = self.request.GET.get('strategy', '')
        symbol = self.request.GET.get('symbol', '')
        market_type = self.request.GET.get('market_type', '')

        # 应用筛选条件
        if strategy:
            queryset = queryset.filter(strategy_name=strategy)
        if symbol:
            queryset = queryset.filter(symbol=symbol)
        if market_type:
            queryset = queryset.filter(market_type=market_type)

        return queryset

    def get_context_data(self, **kwargs):
        """
        添加额外的上下文变量

        Returns:
            dict: 包含筛选选项和当前筛选值的上下文
        """
        context = super().get_context_data(**kwargs)

        # 当前筛选值
        context['filter_strategy'] = self.request.GET.get('strategy', '')
        context['filter_symbol'] = self.request.GET.get('symbol', '')
        context['filter_market_type'] = self.request.GET.get('market_type', '')

        # 可用的筛选选项
        context['strategies'] = BacktestResult.objects.values_list(
            'strategy_name', flat=True
        ).distinct().order_by('strategy_name')

        context['symbols'] = BacktestResult.objects.values_list(
            'symbol', flat=True
        ).distinct().order_by('symbol')

        context['market_types'] = [
            ('futures', '合约'),
            ('spot', '现货'),
        ]

        return context


class BacktestResultDetailView(DetailView):
    """
    回测结果详情视图

    Purpose:
        展示单个回测结果的详细信息，包括权益曲线图、量化指标和订单列表。

    Template:
        strategy_adapter/backtest_detail.html

    Context Variables:
        - object: 回测结果对象
        - orders: 关联的订单列表
        - equity_curve_json: 权益曲线数据（JSON格式，用于Chart.js）
        - metrics: 量化指标字典

    URL:
        /strategy-adapter/results/<pk>/

    Context:
        关联任务：TASK-014-017
        关联需求：FP-014-022
    """

    model = BacktestResult
    template_name = 'strategy_adapter/backtest_detail.html'
    context_object_name = 'result'

    def get_context_data(self, **kwargs):
        """
        添加订单列表和权益曲线数据到上下文

        Returns:
            dict: 包含订单和图表数据的上下文
        """
        import json
        context = super().get_context_data(**kwargs)

        # 获取关联的订单列表
        context['orders'] = self.object.orders.all()

        # 准备权益曲线数据（用于Chart.js）
        equity_curve = self.object.equity_curve or []
        context['equity_curve_json'] = json.dumps(equity_curve)

        # 量化指标
        context['metrics'] = self.object.metrics or {}

        return context
