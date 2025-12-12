"""
Grid Trading Screening Views
筛选系统视图
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator

from .models import TradeLog, GridConfig, ScreeningRecord, ScreeningResultModel


@require_http_methods(["GET"])
def screening_index(request):
    """
    筛选系统主页

    显示动态加载的筛选结果页面
    """
    return render(request, 'grid_trading/screening_index.html')


@require_http_methods(["GET"])
def get_screening_history(request):
    """
    获取历史筛选记录列表

    Query Parameters:
        page (int): 页码，默认1
        page_size (int): 每页数量，默认20

    Returns:
        {
            "records": [
                {
                    "id": 1,
                    "created_at": "2024-12-03 10:00:00",
                    "total_candidates": 61,
                    "execution_time": 1.2,
                    "weights": {
                        "vdr": 0.40,
                        "ker": 0.30,
                        "ovr": 0.20,
                        "cvd": 0.10
                    }
                },
                ...
            ],
            "pagination": {
                "page": 1,
                "page_size": 20,
                "total_pages": 5,
                "total_count": 100
            }
        }
    """
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))

    records = ScreeningRecord.objects.all().order_by('-created_at')
    paginator = Paginator(records, page_size)

    page_obj = paginator.get_page(page)

    data = {
        'records': [
            {
                'id': record.id,
                'created_at': record.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'total_candidates': record.total_candidates,
                'execution_time': round(record.execution_time, 2),
                'weights': {
                    'vdr': float(record.vdr_weight),
                    'ker': float(record.ker_weight),
                    'ovr': float(record.ovr_weight),
                    'cvd': float(record.cvd_weight),
                },
                'notes': record.notes,
            }
            for record in page_obj
        ],
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total_pages': paginator.num_pages,
            'total_count': paginator.count,
        }
    }

    return JsonResponse(data)


@require_http_methods(["GET"])
def get_screening_detail(request, record_id):
    """
    获取特定筛选记录的详细结果

    URL Parameters:
        record_id (int): 筛选记录ID

    Query Parameters:
        page (int): 页码，默认1
        page_size (int): 每页数量，默认50
        sort_by (str): 排序字段，默认'rank'
        sort_order (str): 排序方向，'asc'或'desc'，默认'asc'

    Returns:
        {
            "record": {
                "id": 1,
                "created_at": "2024-12-03 10:00:00",
                "total_candidates": 61,
                "execution_time": 1.2,
                "weights": {...}
            },
            "results": [
                {
                    "rank": 1,
                    "symbol": "ZENUSDT",
                    "price": 123.45,
                    "vdr": 12.5,
                    ...
                },
                ...
            ],
            "pagination": {...}
        }
    """
    try:
        record = ScreeningRecord.objects.get(id=record_id)
    except ScreeningRecord.DoesNotExist:
        return JsonResponse({'error': 'Record not found'}, status=404)

    # 分页参数
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 50))

    # 排序参数
    sort_by = request.GET.get('sort_by', 'rank')
    sort_order = request.GET.get('sort_order', 'asc')

    # 验证排序字段
    valid_sort_fields = [
        'rank', 'symbol', 'composite_index', 'vdr', 'ker', 'ovr',
        'amplitude_sum_15m', 'current_price', 'ma20_slope', 'ma99_slope',
        'drawdown_from_high_pct', 'annual_funding_rate', 'open_interest',
        'volume_24h_calculated', 'vol_oi_ratio', 'price_percentile_100'
    ]
    if sort_by not in valid_sort_fields:
        sort_by = 'rank'

    # 构建排序字符串
    order_prefix = '' if sort_order == 'asc' else '-'
    order_by = f'{order_prefix}{sort_by}'

    # 获取结果
    results = record.results.all().order_by(order_by)

    # 如果page_size为0或负数，返回所有结果不分页
    if page_size <= 0:
        total_count = results.count()
        results_list = [result.to_dict() for result in results]
        data = {
            'record': {
                'id': record.id,
                'created_at': record.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'total_candidates': record.total_candidates,
                'execution_time': round(record.execution_time, 2),
                'weights': {
                    'vdr': float(record.vdr_weight),
                    'ker': float(record.ker_weight),
                    'ovr': float(record.ovr_weight),
                    'cvd': float(record.cvd_weight),
                },
                'filters': {
                    'min_volume': float(record.min_volume),
                    'min_days': record.min_days,
                },
                'notes': record.notes,
            },
            'results': results_list,
            'pagination': {
                'page': 1,
                'page_size': total_count,
                'total_pages': 1,
                'total_count': total_count,
            },
            'sorting': {
                'sort_by': sort_by,
                'sort_order': sort_order,
            }
        }
    else:
        # 正常分页
        paginator = Paginator(results, page_size)
        page_obj = paginator.get_page(page)

        data = {
            'record': {
                'id': record.id,
                'created_at': record.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'total_candidates': record.total_candidates,
                'execution_time': round(record.execution_time, 2),
                'weights': {
                    'vdr': float(record.vdr_weight),
                    'ker': float(record.ker_weight),
                    'ovr': float(record.ovr_weight),
                    'cvd': float(record.cvd_weight),
                },
                'filters': {
                    'min_volume': float(record.min_volume),
                    'min_days': record.min_days,
                },
                'notes': record.notes,
            },
            'results': [result.to_dict() for result in page_obj],
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count,
            },
            'sorting': {
                'sort_by': sort_by,
                'sort_order': sort_order,
            }
        }

    return JsonResponse(data)


@require_http_methods(["GET"])
def get_latest_screening(request):
    """
    获取最新筛选结果

    Query Parameters:
        page (int): 页码，默认1
        page_size (int): 每页数量，默认50

    Returns:
        Same as get_screening_detail
    """
    try:
        latest_record = ScreeningRecord.objects.latest('created_at')
    except ScreeningRecord.DoesNotExist:
        return JsonResponse({'error': 'No screening records found'}, status=404)

    # 重定向到detail视图
    return get_screening_detail(request, latest_record.id)


@require_http_methods(["GET"])
def get_screening_dates(request):
    """
    获取所有筛选日期列表（按日期分组）

    Returns:
        {
            "dates": [
                {
                    "date": "2024-12-03",
                    "count": 5,
                    "latest_id": 100
                },
                ...
            ]
        }
    """
    from django.db.models import Count, Max
    from django.db.models.functions import TruncDate

    dates_data = (
        ScreeningRecord.objects
        .annotate(date=TruncDate('created_at'))
        .values('date')
        .annotate(
            count=Count('id'),
            latest_id=Max('id')
        )
        .order_by('-date')
    )

    data = {
        'dates': [
            {
                'date': item['date'].strftime('%Y-%m-%d'),
                'count': item['count'],
                'latest_id': item['latest_id'],
            }
            for item in dates_data
        ]
    }

    return JsonResponse(data)


@require_http_methods(["GET"])
def daily_screening_dashboard(request):
    """
    日历筛选Dashboard页面
    """
    return render(request, 'grid_trading/daily_screening.html')


@require_http_methods(["GET"])
def get_daily_screening_dates(request):
    """
    获取所有日历筛选的日期列表

    Returns:
        {
            "dates": [
                {
                    "date": "2024-12-05",
                    "record_id": 100,
                    "total_candidates": 531,
                    "filtered_candidates": 15,
                    "notes": "..."
                },
                ...
            ]
        }
    """
    from django.db.models import Count

    records = (
        ScreeningRecord.objects
        .filter(screening_date__isnull=False)
        .order_by('-screening_date')
    )

    dates_list = []
    for record in records:
        # 计算符合默认过滤条件的数量
        results_queryset = record.results.all()

        # 应用默认筛选条件（与前端state.filters一致）
        min_vdr = 6
        min_amplitude = 50
        max_ma99_slope = -10
        min_funding_rate = -10
        min_volume_millions = 5  # 5M USDT

        filtered_results = results_queryset.filter(
            vdr__gte=min_vdr,
            amplitude_sum_15m__gte=min_amplitude,
            ma99_slope__lte=max_ma99_slope,
            annual_funding_rate__gte=min_funding_rate,
            volume_24h_calculated__gte=min_volume_millions * 1000000
        )

        dates_list.append({
            'date': record.screening_date.strftime('%Y-%m-%d'),
            'record_id': record.id,
            'total_candidates': record.total_candidates,
            'filtered_candidates': filtered_results.count(),
            'execution_time': round(record.execution_time, 2),
            'notes': record.notes,
            'filters': {
                'min_vdr': record.filter_min_vdr,
                'min_ker': record.filter_min_ker,
                'min_amplitude': record.filter_min_amplitude,
                'min_funding_rate': record.filter_min_funding_rate,
                'max_ma99_slope': record.filter_max_ma99_slope,
            }
        })

    data = {'dates': dates_list}
    return JsonResponse(data)


@require_http_methods(["GET"])
def get_daily_screening_detail(request, date_str):
    """
    获取指定日期的筛选结果详情

    URL Parameters:
        date_str (str): 日期字符串，格式 YYYY-MM-DD

    Query Parameters:
        sort_by (str): 排序字段，默认'rank'
        sort_order (str): 排序方向，'asc'或'desc'，默认'asc'
        min_vdr (float): VDR最小值过滤
        min_amplitude (float): 振幅最小值过滤
        max_ma99_slope (float): EMA99斜率最大值过滤
        min_funding_rate (float): 资金费率最小值过滤

    Returns:
        {
            "record": {...},
            "results": [...],
            "date": "2024-12-05",
            "filter_stats": {
                "total": 531,
                "filtered": 65
            }
        }
    """
    from datetime import datetime

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format, use YYYY-MM-DD'}, status=400)

    try:
        record = ScreeningRecord.objects.get(screening_date=target_date)
    except ScreeningRecord.DoesNotExist:
        return JsonResponse({'error': f'No screening record found for {date_str}'}, status=404)

    # 排序参数
    sort_by = request.GET.get('sort_by', 'rank')
    sort_order = request.GET.get('sort_order', 'asc')

    # 验证排序字段
    valid_sort_fields = [
        'rank', 'symbol', 'composite_index', 'vdr', 'ker', 'ovr',
        'amplitude_sum_15m', 'current_price', 'ma20_slope', 'ma99_slope',
        'drawdown_from_high_pct', 'annual_funding_rate', 'open_interest',
        'volume_24h_calculated', 'vol_oi_ratio', 'price_percentile_100'
    ]
    if sort_by not in valid_sort_fields:
        sort_by = 'rank'

    # 构建排序字符串
    order_prefix = '' if sort_order == 'asc' else '-'
    order_by = f'{order_prefix}{sort_by}'

    # 获取所有结果
    results_queryset = record.results.all()
    total_count = results_queryset.count()

    # 应用前端过滤条件
    min_vdr = request.GET.get('min_vdr')
    min_amplitude = request.GET.get('min_amplitude')
    max_ma99_slope = request.GET.get('max_ma99_slope')
    min_funding_rate = request.GET.get('min_funding_rate')
    min_volume = request.GET.get('min_volume')

    if min_vdr:
        try:
            results_queryset = results_queryset.filter(vdr__gte=float(min_vdr))
        except (ValueError, TypeError):
            pass

    if min_amplitude:
        try:
            results_queryset = results_queryset.filter(amplitude_sum_15m__gte=float(min_amplitude))
        except (ValueError, TypeError):
            pass

    if max_ma99_slope:
        try:
            results_queryset = results_queryset.filter(ma99_slope__lte=float(max_ma99_slope))
        except (ValueError, TypeError):
            pass

    if min_funding_rate:
        try:
            results_queryset = results_queryset.filter(annual_funding_rate__gte=float(min_funding_rate))
        except (ValueError, TypeError):
            pass

    if min_volume:
        try:
            results_queryset = results_queryset.filter(volume_24h_calculated__gte=float(min_volume))
        except (ValueError, TypeError):
            pass

    # 排序
    results = results_queryset.order_by(order_by)
    filtered_count = results.count()

    # 查询上一次筛选记录（用于计算价格变化）
    previous_record = ScreeningRecord.objects.filter(
        screening_date__lt=target_date
    ).order_by('-screening_date').first()

    # 如果有上一次记录，获取价格映射
    previous_prices = {}
    previous_date = None
    if previous_record:
        previous_date = previous_record.screening_date.strftime('%Y-%m-%d')
        previous_results = previous_record.results.all()
        for prev_result in previous_results:
            previous_prices[prev_result.symbol] = prev_result.current_price

    # 构建结果，添加价格变化信息
    results_list = []
    for result in results:
        result_dict = result.to_dict()

        # 添加价格变化信息
        if result.symbol in previous_prices:
            prev_price = previous_prices[result.symbol]
            current_price = result.current_price
            if prev_price and prev_price > 0:
                price_change_pct = ((float(current_price) - float(prev_price)) / float(prev_price)) * 100
                result_dict['price_change'] = {
                    'previous_price': float(prev_price),
                    'change_pct': round(price_change_pct, 2),
                    'previous_date': previous_date
                }
            else:
                result_dict['price_change'] = None
        else:
            result_dict['price_change'] = None

        results_list.append(result_dict)

    data = {
        'record': {
            'id': record.id,
            'screening_date': record.screening_date.strftime('%Y-%m-%d'),
            'created_at': record.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'total_candidates': record.total_candidates,
            'execution_time': round(record.execution_time, 2),
            'weights': {
                'vdr': float(record.vdr_weight),
                'ker': float(record.ker_weight),
                'ovr': float(record.ovr_weight),
                'cvd': float(record.cvd_weight),
            },
            'filters': {
                'min_volume': float(record.min_volume),
                'min_days': record.min_days,
                'min_vdr': record.filter_min_vdr,
                'min_ker': record.filter_min_ker,
                'min_amplitude': record.filter_min_amplitude,
                'min_funding_rate': record.filter_min_funding_rate,
                'max_ma99_slope': record.filter_max_ma99_slope,
            },
            'notes': record.notes,
        },
        'results': results_list,
        'date': date_str,
        'previous_date': previous_date,  # 添加上一次日期信息
        'sorting': {
            'sort_by': sort_by,
            'sort_order': sort_order,
        },
        'filter_stats': {
            'total': total_count,
            'filtered': filtered_count,
        },
        'applied_filters': {
            'min_vdr': float(min_vdr) if min_vdr else None,
            'min_amplitude': float(min_amplitude) if min_amplitude else None,
            'max_ma99_slope': float(max_ma99_slope) if max_ma99_slope else None,
            'min_funding_rate': float(min_funding_rate) if min_funding_rate else None,
            'min_volume': float(min_volume) if min_volume else None,
        }
    }

    return JsonResponse(data)


@require_http_methods(["GET"])
def backtest_dashboard(request):
    """
    回测Dashboard页面
    """
    return render(request, 'backtest/dashboard.html')


@require_http_methods(["GET"])
def backtest_data(request):
    """
    获取回测数据API

    Returns:
        JSON格式的回测数据
    """
    import json
    import os

    # 读取最新的回测报告
    report_path = 'backtest_data/report_7d.json'

    if not os.path.exists(report_path):
        return JsonResponse({
            'error': '回测数据未找到，请先运行回测命令'
        }, status=404)

    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({
            'error': f'读取回测数据失败: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def get_trade_logs(request, config_id):
    """
    获取指定网格配置的交易日志

    URL Parameters:
        config_id (int): 网格配置ID

    Query Parameters:
        page (int): 页码，默认1
        page_size (int): 每页数量，默认100
        log_type (str): 日志类型过滤 (info/warn/error/order/fill)
        level_index (int): 网格层级过滤
        limit (int): 限制返回数量（优先于分页），默认无限制

    Returns:
        {
            "config": {
                "id": 1,
                "name": "test_btc_short"
            },
            "logs": [
                {
                    "id": 1,
                    "log_type": "order",
                    "detail": "挂开仓单: ...",
                    "timestamp": 1701234567890,
                    "order_id": "test_order_1",
                    "level_index": 5,
                    "created_at": "2024-12-03 10:00:00"
                },
                ...
            ],
            "pagination": {
                "page": 1,
                "page_size": 100,
                "total_pages": 5,
                "total_count": 500
            }
        }
    """
    try:
        config = GridConfig.objects.get(id=config_id)
    except GridConfig.DoesNotExist:
        return JsonResponse({'error': 'Grid config not found'}, status=404)

    # 获取查询参数
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 100))
    log_type = request.GET.get('log_type', None)
    level_index = request.GET.get('level_index', None)
    limit = request.GET.get('limit', None)

    # 构建查询
    logs = TradeLog.objects.filter(config=config).order_by('-timestamp')

    # 应用过滤
    if log_type:
        logs = logs.filter(log_type=log_type)
    if level_index is not None:
        logs = logs.filter(level_index=int(level_index))

    # 如果指定了limit，直接返回前N条
    if limit:
        limit = int(limit)
        logs = logs[:limit]
        logs_list = [
            {
                'id': log.id,
                'log_type': log.log_type,
                'detail': log.detail,
                'timestamp': log.timestamp,
                'order_id': log.order_id,
                'level_index': log.level_index,
                'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }
            for log in logs
        ]
        data = {
            'config': {
                'id': config.id,
                'name': config.name
            },
            'logs': logs_list,
            'pagination': {
                'page': 1,
                'page_size': len(logs_list),
                'total_pages': 1,
                'total_count': len(logs_list)
            }
        }
    else:
        # 分页
        paginator = Paginator(logs, page_size)
        page_obj = paginator.get_page(page)

        data = {
            'config': {
                'id': config.id,
                'name': config.name
            },
            'logs': [
                {
                    'id': log.id,
                    'log_type': log.log_type,
                    'detail': log.detail,
                    'timestamp': log.timestamp,
                    'order_id': log.order_id,
                    'level_index': log.level_index,
                    'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S')
                }
                for log in page_obj
            ],
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count
            }
        }

    return JsonResponse(data)


@require_http_methods(["GET"])
def grid_dashboard(request):
    """
    网格管理后台首页 - 网格列表
    """
    return render(request, 'grid_trading/grid_dashboard.html')


@require_http_methods(["GET"])
def grid_detail_page(request, config_id):
    """
    网格详情页面

    URL Parameters:
        config_id (int): 网格配置ID
    """
    try:
        config = GridConfig.objects.get(id=config_id)
        return render(request, 'grid_trading/grid_detail.html', {'config': config})
    except GridConfig.DoesNotExist:
        return JsonResponse({'error': 'Grid config not found'}, status=404)


@require_http_methods(["GET"])
def get_grids_list(request):
    """
    获取所有网格配置列表

    Returns:
        {
            "grids": [
                {
                    "id": 1,
                    "name": "MONUSDT_backtest_demo",
                    "symbol": "MONUSDT",
                    "grid_mode": "SHORT",
                    "grid_levels": 100,
                    "price_range": "0.01-0.05",
                    "is_active": false,
                    "stats": {
                        "total_events": 188,
                        "total_fills": 68,
                        "position_levels": 2
                    },
                    "created_at": "2024-12-03 10:00:00"
                }
            ]
        }
    """
    from grid_trading.models import GridLevel, GridLevelStatus
    from django.db.models import Count

    configs = GridConfig.objects.all().order_by('-created_at')

    grids_data = []
    for config in configs:
        # 统计事件数
        total_events = TradeLog.objects.filter(config=config).count()
        total_fills = TradeLog.objects.filter(config=config, log_type='fill').count()

        # 统计层级状态
        position_levels = GridLevel.objects.filter(
            config=config,
            status__in=[GridLevelStatus.POSITION_OPEN, GridLevelStatus.EXIT_WORKING]
        ).count()

        grids_data.append({
            'id': config.id,
            'name': config.name,
            'symbol': config.symbol,
            'grid_mode': config.grid_mode,
            'grid_levels': config.grid_levels,
            'price_range': f'{config.lower_price}-{config.upper_price}',
            'is_active': config.is_active,
            'stats': {
                'total_events': total_events,
                'total_fills': total_fills,
                'position_levels': position_levels
            },
            'created_at': config.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })

    return JsonResponse({'grids': grids_data})


@require_http_methods(["GET"])
def get_grid_detail(request, config_id):
    """
    获取网格详细信息

    URL Parameters:
        config_id (int): 网格配置ID

    Returns:
        {
            "config": {...},
            "stats": {
                "total_levels": 100,
                "idle": 98,
                "entry_working": 0,
                "position_open": 2,
                "exit_working": 0,
                "total_events": 188,
                "total_fills": 68,
                "entry_fills": 36,
                "exit_fills": 32
            },
            "levels": [
                {
                    "level_index": 1,
                    "price": 0.03020202,
                    "side": "SELL",
                    "status": "idle",
                    "entry_order_id": null,
                    "exit_order_id": null
                }
            ],
            "recent_events": [...]
        }
    """
    try:
        config = GridConfig.objects.get(id=config_id)
    except GridConfig.DoesNotExist:
        return JsonResponse({'error': 'Grid config not found'}, status=404)

    from grid_trading.models import GridLevel, GridLevelStatus
    from django.db.models import Count

    # 配置信息
    config_data = {
        'id': config.id,
        'name': config.name,
        'symbol': config.symbol,
        'grid_mode': config.grid_mode,
        'grid_levels': config.grid_levels,
        'upper_price': float(config.upper_price),
        'lower_price': float(config.lower_price),
        'grid_spacing': float(config.grid_spacing),
        'grid_spacing_pct': float(config.grid_spacing_pct),
        'trade_amount': float(config.trade_amount),
        'max_position_size': float(config.max_position_size),
        'is_active': config.is_active,
        'created_at': config.created_at.strftime('%Y-%m-%d %H:%M:%S')
    }

    # 层级统计
    levels = GridLevel.objects.filter(config=config)
    level_stats = levels.values('status').annotate(count=Count('id'))

    stats_dict = {
        'total_levels': levels.count(),
        'idle': 0,
        'entry_working': 0,
        'position_open': 0,
        'exit_working': 0
    }

    for stat in level_stats:
        status = stat['status']
        count = stat['count']
        if status == GridLevelStatus.IDLE:
            stats_dict['idle'] = count
        elif status == GridLevelStatus.ENTRY_WORKING:
            stats_dict['entry_working'] = count
        elif status == GridLevelStatus.POSITION_OPEN:
            stats_dict['position_open'] = count
        elif status == GridLevelStatus.EXIT_WORKING:
            stats_dict['exit_working'] = count

    # 事件统计
    stats_dict['total_events'] = TradeLog.objects.filter(config=config).count()
    stats_dict['total_fills'] = TradeLog.objects.filter(config=config, log_type='fill').count()
    stats_dict['entry_fills'] = TradeLog.objects.filter(
        config=config,
        log_type='fill',
        detail__contains='开仓成交'
    ).count()
    stats_dict['exit_fills'] = TradeLog.objects.filter(
        config=config,
        log_type='fill',
        detail__contains='平仓成交'
    ).count()

    # 层级列表（仅返回有订单的层级，限制50条）
    active_levels = levels.exclude(status=GridLevelStatus.IDLE).order_by('level_index')[:50]
    levels_data = [
        {
            'level_index': level.level_index,
            'price': float(level.price),
            'side': level.side,
            'status': level.status,
            'entry_order_id': level.entry_order_id,
            'exit_order_id': level.exit_order_id,
            'entry_client_id': level.entry_client_id,
            'exit_client_id': level.exit_client_id
        }
        for level in active_levels
    ]

    # 最近事件（限制20条）
    recent_events = TradeLog.objects.filter(config=config).order_by('-timestamp')[:20]
    events_data = [
        {
            'id': log.id,
            'log_type': log.log_type,
            'detail': log.detail,
            'timestamp': log.timestamp,
            'order_id': log.order_id,
            'level_index': log.level_index,
            'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
        for log in recent_events
    ]

    return JsonResponse({
        'config': config_data,
        'stats': stats_dict,
        'levels': levels_data,
        'recent_events': events_data
    })


@require_http_methods(["GET"])
def get_trade_logs_summary(request, config_id):
    """
    获取交易日志统计摘要

    URL Parameters:
        config_id (int): 网格配置ID

    Returns:
        {
            "config": {
                "id": 1,
                "name": "test_btc_short"
            },
            "summary": {
                "total_logs": 1000,
                "by_type": {
                    "info": 100,
                    "warn": 50,
                    "error": 10,
                    "order": 500,
                    "fill": 340
                },
                "latest_log": {
                    "log_type": "fill",
                    "detail": "...",
                    "timestamp": 1701234567890
                }
            }
        }
    """
    try:
        config = GridConfig.objects.get(id=config_id)
    except GridConfig.DoesNotExist:
        return JsonResponse({'error': 'Grid config not found'}, status=404)

    from django.db.models import Count
    from grid_trading.models.trade_log import LogType

    # 统计总数
    total_logs = TradeLog.objects.filter(config=config).count()

    # 按类型统计
    by_type_queryset = TradeLog.objects.filter(config=config).values('log_type').annotate(count=Count('id'))
    by_type = {item['log_type']: item['count'] for item in by_type_queryset}

    # 确保所有类型都有值（即使为0）
    for log_type in LogType.values:
        if log_type not in by_type:
            by_type[log_type] = 0

    # 获取最新日志
    latest_log = TradeLog.objects.filter(config=config).order_by('-timestamp').first()
    latest_log_data = None
    if latest_log:
        latest_log_data = {
            'log_type': latest_log.log_type,
            'detail': latest_log.detail,
            'timestamp': latest_log.timestamp,
            'created_at': latest_log.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

    data = {
        'config': {
            'id': config.id,
            'name': config.name
        },
        'summary': {
            'total_logs': total_logs,
            'by_type': by_type,
            'latest_log': latest_log_data
        }
    }

    return JsonResponse(data)


# ============================================================================
# Contract Detail Pages (Feature: 007-contract-detail-page)
# ============================================================================

@require_http_methods(["GET"])
def screening_daily_index(request):
    """
    日历筛选主页 - 显示所有筛选日期及其合约列表

    Returns:
        HTML: 渲染screening_daily.html模板，显示所有可用日期及合约
    """
    from grid_trading.services.detail_page_service import DetailPageService

    # 获取最近30个可用日期
    available_dates = DetailPageService.get_available_dates(limit=30)

    # 为每个日期获取合约列表（只获取前10个）
    dates_with_contracts = []
    for date in available_dates:
        contracts = DetailPageService.get_contracts_by_date(date)
        dates_with_contracts.append({
            'date': date,
            'contracts': contracts[:10],  # 只显示前10个合约
            'total_count': len(contracts)
        })

    context = {
        'dates_with_contracts': dates_with_contracts,
        'page_title': '筛选结果总览',
    }

    return render(request, 'grid_trading/screening_daily.html', context)


@require_http_methods(["GET"])
def screening_daily_detail(request, date):
    """
    某日筛选结果列表页

    Args:
        date: 筛选日期 (YYYY-MM-DD)

    Returns:
        HTML: 渲染screening_daily.html模板，显示该日期的所有合约
    """
    from grid_trading.services.detail_page_service import DetailPageService
    from grid_trading.django_models import ScreeningRecord

    # 查询该日期的筛选记录
    screening_record = ScreeningRecord.objects.filter(screening_date=date).first()

    if not screening_record:
        # 返回404页面
        available_dates = DetailPageService.get_available_dates(limit=5)
        context = {
            'error_detail': f'该日期({date})无筛选记录',
            'recent_dates': available_dates,
        }
        return render(request, '404.html', context, status=404)

    # 获取该日期的所有合约列表
    contracts = DetailPageService.get_contracts_by_date(date)

    context = {
        'screening_date': date,
        'contracts': contracts,
        'total_count': len(contracts),
        'page_title': f'{date} 筛选结果',
    }

    return render(request, 'grid_trading/screening_daily.html', context)


@require_http_methods(["GET"])
def contract_detail(request, date, symbol):
    """
    合约详情页

    Args:
        date: 筛选日期 (YYYY-MM-DD)
        symbol: 合约代码 (如BTCUSDT)

    Returns:
        HTML: 渲染screening_detail.html模板，显示合约完整分析数据
    """
    from grid_trading.services.detail_page_service import DetailPageService

    # 准备详情页数据
    detail_data = DetailPageService.prepare_detail_data(date, symbol)

    if not detail_data:
        # 返回404页面
        available_dates = DetailPageService.get_available_dates(limit=5)
        context = {
            'error_detail': f'该日期({date})的合约({symbol})无筛选记录',
            'recent_dates': available_dates,
            'back_url': f'/grid_trading/screening/daily/{date}/',
        }
        return render(request, '404.html', context, status=404)

    # 渲染详情页
    context = {
        'detail': detail_data,
        'page_title': f'{symbol} - {date} 详情',
    }

    return render(request, 'grid_trading/screening_detail.html', context)


@require_http_methods(["GET"])
def api_klines(request, date, symbol):
    """
    K线数据API - 为详情页前端提供K线数据

    Args:
        date: 筛选日期 (YYYY-MM-DD)
        symbol: 合约代码 (如BTCUSDT)

    Query Parameters:
        interval: 时间周期 (15m, 1h, 4h, 1d)，默认4h
        limit: K线数量，默认根据interval自动确定
        include_signals: 是否包含VPA和规则信号（true/false），默认false

    Returns:
        JSON: {
            "symbol": "BTCUSDT",
            "interval": "4h",
            "screening_date": "2024-12-05",
            "klines": [{open_time, open, high, low, close, volume}, ...],
            "ema99": [123.1, 123.2, ...],
            "ema20": [124.5, 124.6, ...],
            "warnings": ["数据不足，仅显示20根K线(需要300根)"],
            "vpa_signals": [{"time": 1638360000, "type": "stopping_volume", ...}],  # Optional
            "rule_signals": [{"time": 1638360000, "rule_id": 6, ...}]  # Optional
        }
    """
    from datetime import datetime
    from django.utils import timezone
    from decimal import Decimal
    import numpy as np
    from grid_trading.services.kline_cache import KlineCache
    from grid_trading.services.rule_engine import PriceRuleEngine

    # 获取查询参数
    interval = request.GET.get('interval', '4h')
    limit_str = request.GET.get('limit')
    include_signals = request.GET.get('include_signals', 'false').lower() == 'true'

    # 根据interval确定默认limit
    default_limits = {
        '15m': 100,
        '1h': 50,
        '4h': 300,
        '1d': 30,
    }
    limit = int(limit_str) if limit_str else default_limits.get(interval, 300)

    # 解析screening_date为datetime对象
    try:
        screening_datetime = datetime.strptime(date, '%Y-%m-%d')
        # 获取该日期结束时刻的K线数据（+1天）
        from datetime import timedelta
        end_time = timezone.make_aware(screening_datetime + timedelta(days=1))
    except ValueError:
        return JsonResponse({
            'error': 'Invalid date format. Expected YYYY-MM-DD'
        }, status=400)

    # 初始化KlineCache（不使用API client，仅从数据库获取）
    kline_cache = KlineCache(api_client=None)

    # 获取K线数据（历史模式，使用end_time）
    klines = kline_cache.get_klines(
        symbol=symbol,
        interval=interval,
        limit=limit,
        use_cache=True,
        end_time=end_time
    )

    # 检查数据是否充足
    warnings = []
    if len(klines) < limit:
        warnings.append(f'数据不足，仅显示{len(klines)}根K线(需要{limit}根)')

    # 辅助函数：计算EMA
    def calculate_ema(prices, period):
        """计算指数移动平均线"""
        prices_array = np.array(prices, dtype=float)
        alpha = 2 / (period + 1)
        ema = np.zeros_like(prices_array)
        ema[0] = prices_array[0]

        for i in range(1, len(prices_array)):
            ema[i] = alpha * prices_array[i] + (1 - alpha) * ema[i-1]

        # 前period-1个值设为None（不够准确）
        result = [None] * (period - 1) + list(ema[period-1:])
        return result

    # 计算EMA指标
    ema99 = []
    ema20 = []

    if klines:
        # 提取收盘价序列
        close_prices = [k['close'] for k in klines]

        # 计算EMA
        try:
            ema99_values = calculate_ema(close_prices, period=99)
            ema20_values = calculate_ema(close_prices, period=20)

            # 转换为列表
            ema99 = [float(v) if v is not None else None for v in ema99_values]
            ema20 = [float(v) if v is not None else None for v in ema20_values]

        except Exception as e:
            warnings.append(f'EMA计算失败: {str(e)}')

    # T037-T038: VPA和规则信号检测（仅在明确请求时执行）
    vpa_signals = []
    rule_signals = []

    if include_signals and len(klines) >= 50:
        try:
            # 初始化规则引擎
            rule_engine = PriceRuleEngine()

            # 获取当前价格（使用最后一根K线的收盘价）
            current_price = Decimal(str(klines[-1]['close']))

            # 获取多周期K线数据（用于规则6/7检测）
            klines_15m = kline_cache.get_klines(
                symbol=symbol,
                interval='15m',
                limit=100,
                use_cache=True,
                end_time=end_time
            )

            klines_1h = kline_cache.get_klines(
                symbol=symbol,
                interval='1h',
                limit=50,
                use_cache=True,
                end_time=end_time
            )

            # 批量检测所有规则（不推送，仅返回结果）
            triggered_rules = rule_engine.check_all_rules_batch(
                symbol=symbol,
                current_price=current_price,
                klines_4h=klines,
                klines_15m=klines_15m,
                klines_1h=klines_1h
            )

            # 处理规则触发结果
            for rule_result in triggered_rules:
                rule_id = rule_result['rule_id']
                extra_info = rule_result.get('extra_info', {})

                # 规则6和规则7包含VPA信号信息
                if rule_id in [6, 7]:
                    rule_signal = {
                        'time': int(klines[-1]['open_time'] / 1000),  # 转为秒级时间戳
                        'rule_id': rule_id,
                        'rule_name': rule_result['rule_name'],
                        'vpa_signal': extra_info.get('vpa_signal'),
                        'tech_signal': extra_info.get('tech_signal'),
                        'timeframe': extra_info.get('timeframe'),
                        'rsi_value': extra_info.get('rsi_value'),
                        'rsi_slope': extra_info.get('rsi_slope') if rule_id == 7 else None,
                    }
                    rule_signals.append(rule_signal)
                else:
                    # 其他规则（1-5）也记录
                    rule_signal = {
                        'time': int(klines[-1]['open_time'] / 1000),
                        'rule_id': rule_id,
                        'rule_name': rule_result['rule_name'],
                        'extra_info': extra_info
                    }
                    rule_signals.append(rule_signal)

            # TODO: VPA信号的详细位置标记（需要遍历K线历史识别每根K线的VPA模式）
            # 当前版本仅在最后一根K线上检测规则触发，VPA信号暂时为空
            # Phase 4增强: 可以扩展为遍历所有K线，标记每个VPA模式的出现位置

        except Exception as e:
            warnings.append(f'信号检测失败: {str(e)}')

    # 构建响应
    response_data = {
        'symbol': symbol,
        'interval': interval,
        'screening_date': date,
        'klines': klines,
        'ema99': ema99,
        'ema20': ema20,
        'warnings': warnings,
    }

    # 仅在请求时包含信号数据
    if include_signals:
        response_data['vpa_signals'] = vpa_signals
        response_data['rule_signals'] = rule_signals

    return JsonResponse(response_data)
