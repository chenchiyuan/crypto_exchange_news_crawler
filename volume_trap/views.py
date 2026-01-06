"""
Volume Trap 视图集合

包含以下视图：
1. MonitorListAPIView - 监控池列表API（REST API）
2. DashboardView - Dashboard页面视图（前端页面）
3. BacktestListPageView - 回测结果列表页面视图
4. BacktestStatisticsPageView - 回测统计页面视图
5. BacktestDetailPageView - 回测详情页面视图

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md (第五部分-7.1 监控池列表API)
    - PRD: docs/iterations/006-volume-trap-dashboard/prd.md (F1.1 - 代币列表展示)
    - PRD: docs/iterations/008-volume-trap-backtest-frontend/prd.md (回测结果前端展示)
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md (API服务层)
    - Architecture: docs/iterations/006-volume-trap-dashboard/architecture.md (6.1 - 前端组件结构)
    - Task: TASK-002-040, TASK-006-006
"""

import logging
from datetime import datetime, timedelta

from django.db.models import Prefetch
from django.utils import timezone as django_timezone
from django.views.generic import TemplateView

from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from volume_trap.models import VolumeTrapIndicators, VolumeTrapMonitor
from volume_trap.serializers import VolumeTrapMonitorSerializer

logger = logging.getLogger(__name__)


class MonitorListPagination(PageNumberPagination):
    """监控池列表分页器。

    配置分页参数，支持自定义每页数量。

    业务逻辑：
        - 默认每页20条
        - 允许客户端自定义每页数量（1-100）
        - 返回分页元数据（总数、下一页、上一页）

    Examples:
        # 获取第1页，每页20条（默认）
        GET /api/volume-trap/monitors/

        # 获取第2页，每页50条
        GET /api/volume-trap/monitors/?page=2&page_size=50

    Related:
        - PRD: 第五部分-7.1 监控池列表API
        - Architecture: API服务层 - Pagination
        - Task: TASK-002-040
    """

    page_size = 20  # 默认每页20条
    page_size_query_param = "page_size"
    max_page_size = 100  # 最大每页100条


class MonitorListAPIView(generics.ListAPIView):
    """监控池列表API。

    提供GET接口，查询监控池记录列表，支持筛选和分页。

    业务逻辑：
        - 查询所有VolumeTrapMonitor记录
        - 支持按status、interval筛选
        - 支持分页（page、page_size）
        - 返回Monitor记录 + 最新Indicators快照
        - 使用prefetch_related优化性能

    查询参数：
        - status (str): 状态筛选（pending/suspected/confirmed/invalidated）
        - interval (str): 周期筛选（1h/4h/1d）
        - market_type (str): 市场类型筛选（spot/futures/all），默认all
        - page (int): 页码，从1开始
        - page_size (int): 每页数量，默认20，最大100

    响应格式：
        {
            "count": 100,  // 总记录数
            "next": "http://api/volume-trap/monitors/?page=2",  // 下一页URL
            "previous": null,  // 上一页URL
            "results": [  // 当前页数据
                {
                    "id": 1,
                    "symbol": "BTCUSDT",
                    "interval": "4h",
                    "status": "pending",
                    "trigger_time": "2024-12-24T12:00:00+08:00",
                    "trigger_price": 50000.0,
                    "latest_indicators": {...},
                    ...
                },
                ...
            ]
        }

    错误响应：
        - 400 Bad Request: 参数错误（如invalid status）
        - 404 Not Found: 页码超出范围

    Examples:
        # 获取所有监控记录（所有市场类型）
        GET /api/volume-trap/monitors/

        # 筛选pending状态的4h周期记录
        GET /api/volume-trap/monitors/?status=pending&interval=4h

        # 筛选现货市场记录
        GET /api/volume-trap/monitors/?market_type=spot

        # 筛选合约市场记录
        GET /api/volume-trap/monitors/?market_type=futures

        # 获取第2页，每页50条
        GET /api/volume-trap/monitors/?page=2&page_size=50

    Related:
        - PRD: 第五部分-7.1 监控池列表API
        - Architecture: API服务层 - MonitorListAPIView
        - Task: TASK-002-040

    Performance:
        - 使用select_related优化FuturesContract/SpotContract外键查询
        - 使用prefetch_related优化Indicators关联查询
        - 响应时间<1秒（500条记录）
    """

    serializer_class = VolumeTrapMonitorSerializer
    pagination_class = MonitorListPagination

    def get_queryset(self):
        """构建查询集，支持筛选和性能优化。

        业务逻辑：
            1. 基础查询：所有VolumeTrapMonitor记录
            2. 应用筛选条件（status、interval、market_type、start_date、end_date）
            3. 优化性能：select_related、prefetch_related
            4. 按创建时间倒序排列

        筛选参数：
            - status (str, 可选): 状态筛选（pending/suspected_abandonment/confirmed_abandonment/invalidated）
            - interval (str, 可选): 周期筛选（1h/4h/1d）
            - market_type (str, 可选): 市场类型筛选（spot/futures/all），默认all
            - start_date (str, 可选): 开始日期筛选（YYYY-MM-DD格式）
            - end_date (str, 可选): 结束日期筛选（YYYY-MM-DD格式）

        Returns:
            QuerySet: 优化后的查询集，包含所有筛选条件

        Side Effects:
            - 查询数据库
            - 应用筛选条件
            - 优化数据库查询（避免N+1查询）

        Raises:
            无（参数验证在list()方法中处理）

        Examples:
            >>> request = self.request
            >>> request.query_params = {'status': 'pending', 'start_date': '2025-12-01'}
            >>> queryset = self.get_queryset()
            >>> # 返回pending状态且触发时间>=2025-12-01的记录

        Related:
            - Task: TASK-006-001
            - Architecture: docs/iterations/006-volume-trap-dashboard/architecture.md (MonitorQueryService)
        """
        # === Step 1: 基础查询 ===
        queryset = VolumeTrapMonitor.objects.all()

        # === Step 2: 应用筛选条件 ===
        # 状态筛选
        status_param = self.request.query_params.get("status", None)
        if status_param:
            queryset = queryset.filter(status=status_param)

        # 周期筛选
        interval_param = self.request.query_params.get("interval", None)
        if interval_param:
            queryset = queryset.filter(interval=interval_param)

        # 市场类型筛选
        market_type_param = self.request.query_params.get("market_type", "all")
        if market_type_param and market_type_param != "all":
            queryset = queryset.filter(market_type=market_type_param)

        # 时间范围筛选 - 新增功能
        start_date_param = self.request.query_params.get("start_date", None)
        end_date_param = self.request.query_params.get("end_date", None)

        if start_date_param:
            # 将日期字符串转换为DateTime（当天开始）
            from datetime import datetime

            try:
                start_date = datetime.strptime(start_date_param, "%Y-%m-%d").date()
                queryset = queryset.filter(trigger_time__date__gte=start_date)
            except ValueError:
                # 日期格式错误，将在list()方法中处理
                pass

        if end_date_param:
            # 将日期字符串转换为DateTime（当天结束）
            from datetime import datetime

            try:
                end_date = datetime.strptime(end_date_param, "%Y-%m-%d").date()
                # 添加一天并减去1秒，得到当天结束时间
                from datetime import timedelta

                end_date = end_date + timedelta(days=1) - timedelta(seconds=1)
                queryset = queryset.filter(trigger_time__date__lte=end_date)
            except ValueError:
                # 日期格式错误，将在list()方法中处理
                pass

        # === Step 3: 性能优化 ===
        # 使用select_related优化FuturesContract/SpotContract外键查询（减少SQL查询）
        queryset = queryset.select_related("futures_contract", "spot_contract")

        # 使用prefetch_related优化Indicators关联查询
        # 只预取最新的1个Indicators快照（减少数据传输）
        # 修复：先获取QuerySet，不进行slice操作
        queryset = queryset.prefetch_related(
            Prefetch("indicators", queryset=VolumeTrapIndicators.objects.order_by("-snapshot_time"))
        )

        # === Step 4: 排序 ===
        # 按触发时间倒序（最新的异常事件在前）
        queryset = queryset.order_by("-trigger_time")

        return queryset

    def list(self, request, *args, **kwargs):
        """处理GET请求，返回监控池列表。

        Args:
            request: HTTP请求对象
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            Response: DRF响应对象，包含分页数据

        Side Effects:
            - 查询数据库
            - 记录日志

        Raises:
            ValueError: 当start_date > end_date时抛出
            ValueError: 当日期格式无效时抛出

        Examples:
            # 获取所有pending状态的记录
            GET /api/volume-trap/monitors/?status=pending

            # 获取2025年12月的记录
            GET /api/volume-trap/monitors/?start_date=2025-12-01&end_date=2025-12-31

            # 组合筛选：pending状态且2025年12月
            GET /api/volume-trap/monitors/?status=pending&start_date=2025-12-01&end_date=2025-12-31

        Related:
            - Task: TASK-006-001
            - Architecture: docs/iterations/006-volume-trap-dashboard/architecture.md (5.2)
        """
        from datetime import datetime

        from django.core.exceptions import ValidationError

        # === 参数获取 ===
        status_param = request.query_params.get("status", None)
        interval_param = request.query_params.get("interval", None)
        market_type_param = request.query_params.get("market_type", "all")
        start_date_param = request.query_params.get("start_date", None)
        end_date_param = request.query_params.get("end_date", None)

        # === 参数验证 ===
        # 验证status参数
        valid_statuses = [
            "pending",
            "suspected_abandonment",
            "confirmed_abandonment",
            "invalidated",
        ]
        if status_param and status_param not in valid_statuses:
            return Response(
                {
                    "error": "Invalid status parameter",
                    "detail": f"status must be one of: {valid_statuses}",
                    "received": status_param,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 验证interval参数
        valid_intervals = ["1h", "4h", "1d"]
        if interval_param and interval_param not in valid_intervals:
            return Response(
                {
                    "error": "Invalid interval parameter",
                    "detail": f"interval must be one of: {valid_intervals}",
                    "received": interval_param,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 验证market_type参数
        valid_market_types = ["spot", "futures", "all"]
        if market_type_param and market_type_param not in valid_market_types:
            return Response(
                {
                    "error": "Invalid market_type parameter",
                    "detail": f"market_type must be one of: {valid_market_types}",
                    "received": market_type_param,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 验证时间范围参数
        start_date = None
        end_date = None

        # 验证start_date格式
        if start_date_param:
            try:
                start_date = datetime.strptime(start_date_param, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {
                        "error": "Invalid start_date parameter",
                        "detail": "start_date must be in YYYY-MM-DD format",
                        "received": start_date_param,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # 验证end_date格式
        if end_date_param:
            try:
                end_date = datetime.strptime(end_date_param, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {
                        "error": "Invalid end_date parameter",
                        "detail": "end_date must be in YYYY-MM-DD format",
                        "received": end_date_param,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # 验证start_date <= end_date
        if start_date and end_date and start_date > end_date:
            return Response(
                {
                    "error": "Invalid date range",
                    "detail": "start_date cannot be greater than end_date",
                    "start_date": start_date_param,
                    "end_date": end_date_param,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # === 执行查询 ===
        logger.info(
            f"监控池列表查询: status={status_param or 'all'}, "
            f"interval={interval_param or 'all'}, "
            f"market_type={market_type_param or 'all'}, "
            f"start_date={start_date_param or 'all'}, "
            f"end_date={end_date_param or 'all'}, "
            f"page={request.query_params.get('page', 1)}"
        )

        # 调用父类的list方法，执行查询和分页
        return super().list(request, *args, **kwargs)


class DashboardView(TemplateView):
    """Dashboard页面视图。

    渲染Dashboard主页面模板，提供默认筛选条件。

    业务逻辑：
        - 继承Django的TemplateView
        - 设置模板名称为dashboard/index.html
        - 提供默认筛选条件作为上下文数据
        - 支持GET请求，不允许POST请求

    模板变量：
        - default_filters: 默认筛选条件（status、interval、start_date、end_date）
        - request: HTTP请求对象
        - user: 当前用户信息

    默认筛选条件：
        - status: ['pending', 'suspected_abandonment', 'confirmed_abandonment', 'invalidated'] (所有状态)
        - interval: '4h' (默认4小时周期)
        - start_date: 当前日期前7天
        - end_date: 当前日期

    Examples:
        # 访问Dashboard页面
        GET /dashboard/

        # 获取默认筛选条件
        >>> view = DashboardView()
        >>> view.setup(request)
        >>> context = view.get_context_data()
        >>> print(context['default_filters']['interval'])
        '4h'

    Related:
        - Task: TASK-006-006
        - Architecture: docs/iterations/006-volume-trap-dashboard/architecture.md (6.1)

    Attributes:
        template_name (str): 模板文件路径
    """

    template_name = "dashboard/index.html"

    def get_context_data(self, **kwargs):
        """获取上下文数据，包含默认筛选条件。

        Args:
            **kwargs: 关键字参数

        Returns:
            dict: 上下文数据，包含default_filters、request、user等

        Examples:
            >>> view = DashboardView()
            >>> view.setup(request)
            >>> context = view.get_context_data()
            >>> 'default_filters' in context
            True

        Side Effects:
            - 无（只读取数据，不修改数据库）

        Related:
            - Task: TASK-006-006
        """
        context = super().get_context_data(**kwargs)

        # 添加默认筛选条件
        context["default_filters"] = self.get_default_filters()

        # request和user会自动添加到上下文中
        # 无需显式添加

        return context

    def get_default_filters(self):
        """获取默认筛选条件。

        返回Dashboard页面加载时的默认筛选条件，包括状态、周期和时间范围。

        Returns:
            dict: 默认筛选条件字典，包含：
                - status (list): 疑似弃盘和确认弃盘状态列表
                - interval (str): 默认周期 '4h'
                - start_date (str): 2025-01-01 (YYYY-MM-DD格式)
                - end_date (str): 当前日期 (YYYY-MM-DD格式)

        Examples:
            >>> view = DashboardView()
            >>> filters = view.get_default_filters()
            >>> filters['interval']
            '4h'
            >>> filters['status']
            ['suspected_abandonment', 'confirmed_abandonment']

        Side Effects:
            - 使用django_timezone.now()获取当前时间

        Related:
            - Task: TASK-006-006
        """
        now = django_timezone.now()

        # 设置开始日期为2025-01-01
        start_date_2025 = datetime(2025, 1, 1, tzinfo=django_timezone.get_current_timezone())

        return {
            "status": ["pending", "suspected_abandonment", "confirmed_abandonment"],
            "interval": "4h",
            "market_type": "spot",  # 默认只显示现货市场数据，与历史扫描结果一致
            "start_date": start_date_2025.strftime("%Y-%m-%d"),
            "end_date": now.strftime("%Y-%m-%d"),
        }


class BacktestListPageView(TemplateView):
    """回测结果列表页面视图。

    渲染回测结果列表页面模板，提供筛选、排序、分页功能。

    Related:
        - PRD: docs/iterations/008-volume-trap-backtest-frontend/prd.md (F1.1-F1.4)
        - Architecture: docs/iterations/008-volume-trap-backtest-frontend/architecture.md
    """

    template_name = "backtest/list.html"


class BacktestStatisticsPageView(TemplateView):
    """回测统计页面视图。

    渲染回测统计页面模板，展示整体策略表现。

    Related:
        - PRD: docs/iterations/008-volume-trap-backtest-frontend/prd.md (F2.1-F2.4)
        - Architecture: docs/iterations/008-volume-trap-backtest-frontend/architecture.md
    """

    template_name = "backtest/statistics.html"


class BacktestDetailPageView(TemplateView):
    """回测详情页面视图。

    渲染回测详情页面模板，展示K线图和关键点位。

    Related:
        - PRD: docs/iterations/008-volume-trap-backtest-frontend/prd.md (F3.1-F3.4)
        - Architecture: docs/iterations/008-volume-trap-backtest-frontend/architecture.md
    """

    template_name = "backtest/detail.html"

    def get_context_data(self, **kwargs):
        """获取上下文数据，包含回测ID。

        Args:
            **kwargs: 关键字参数，包含backtest_id

        Returns:
            dict: 上下文数据
        """
        context = super().get_context_data(**kwargs)
        context["backtest_id"] = self.kwargs.get("backtest_id")
        context["symbol"] = "Loading..."  # Will be populated by JS
        return context
