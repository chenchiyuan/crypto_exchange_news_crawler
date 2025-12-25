"""
Volume Trap API视图

用途：提供REST API接口，查询监控池数据

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md (第五部分-7.1 监控池列表API)
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md (API服务层)
    - Task: TASK-002-040
"""

import logging
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Prefetch

from volume_trap.models import VolumeTrapMonitor, VolumeTrapIndicators
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
    page_size_query_param = 'page_size'
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
        status_param = self.request.query_params.get('status', None)
        if status_param:
            queryset = queryset.filter(status=status_param)

        # 周期筛选
        interval_param = self.request.query_params.get('interval', None)
        if interval_param:
            queryset = queryset.filter(interval=interval_param)

        # 市场类型筛选
        market_type_param = self.request.query_params.get('market_type', 'all')
        if market_type_param and market_type_param != 'all':
            queryset = queryset.filter(market_type=market_type_param)

        # 时间范围筛选 - 新增功能
        start_date_param = self.request.query_params.get('start_date', None)
        end_date_param = self.request.query_params.get('end_date', None)

        if start_date_param:
            # 将日期字符串转换为DateTime（当天开始）
            from datetime import datetime
            try:
                start_date = datetime.strptime(start_date_param, '%Y-%m-%d').date()
                queryset = queryset.filter(trigger_time__date__gte=start_date)
            except ValueError:
                # 日期格式错误，将在list()方法中处理
                pass

        if end_date_param:
            # 将日期字符串转换为DateTime（当天结束）
            from datetime import datetime
            try:
                end_date = datetime.strptime(end_date_param, '%Y-%m-%d').date()
                # 添加一天并减去1秒，得到当天结束时间
                from datetime import timedelta
                end_date = end_date + timedelta(days=1) - timedelta(seconds=1)
                queryset = queryset.filter(trigger_time__date__lte=end_date)
            except ValueError:
                # 日期格式错误，将在list()方法中处理
                pass

        # === Step 3: 性能优化 ===
        # 使用select_related优化FuturesContract/SpotContract外键查询（减少SQL查询）
        queryset = queryset.select_related('futures_contract', 'spot_contract')

        # 使用prefetch_related优化Indicators关联查询
        # 只预取最新的1个Indicators快照（减少数据传输）
        # 修复：先获取QuerySet，不进行slice操作
        queryset = queryset.prefetch_related(
            Prefetch(
                'indicators',
                queryset=VolumeTrapIndicators.objects.order_by('-snapshot_time')
            )
        )

        # === Step 4: 排序 ===
        # 按创建时间倒序（最新的记录在前）
        queryset = queryset.order_by('-created_at')

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
        status_param = request.query_params.get('status', None)
        interval_param = request.query_params.get('interval', None)
        market_type_param = request.query_params.get('market_type', 'all')
        start_date_param = request.query_params.get('start_date', None)
        end_date_param = request.query_params.get('end_date', None)

        # === 参数验证 ===
        # 验证status参数
        valid_statuses = ['pending', 'suspected_abandonment', 'confirmed_abandonment', 'invalidated']
        if status_param and status_param not in valid_statuses:
            return Response(
                {
                    'error': 'Invalid status parameter',
                    'detail': f'status must be one of: {valid_statuses}',
                    'received': status_param
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # 验证interval参数
        valid_intervals = ['1h', '4h', '1d']
        if interval_param and interval_param not in valid_intervals:
            return Response(
                {
                    'error': 'Invalid interval parameter',
                    'detail': f'interval must be one of: {valid_intervals}',
                    'received': interval_param
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # 验证market_type参数
        valid_market_types = ['spot', 'futures', 'all']
        if market_type_param and market_type_param not in valid_market_types:
            return Response(
                {
                    'error': 'Invalid market_type parameter',
                    'detail': f'market_type must be one of: {valid_market_types}',
                    'received': market_type_param
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # 验证时间范围参数
        start_date = None
        end_date = None

        # 验证start_date格式
        if start_date_param:
            try:
                start_date = datetime.strptime(start_date_param, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {
                        'error': 'Invalid start_date parameter',
                        'detail': 'start_date must be in YYYY-MM-DD format',
                        'received': start_date_param
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        # 验证end_date格式
        if end_date_param:
            try:
                end_date = datetime.strptime(end_date_param, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {
                        'error': 'Invalid end_date parameter',
                        'detail': 'end_date must be in YYYY-MM-DD format',
                        'received': end_date_param
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        # 验证start_date <= end_date
        if start_date and end_date and start_date > end_date:
            return Response(
                {
                    'error': 'Invalid date range',
                    'detail': 'start_date cannot be greater than end_date',
                    'start_date': start_date_param,
                    'end_date': end_date_param
                },
                status=status.HTTP_400_BAD_REQUEST
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
