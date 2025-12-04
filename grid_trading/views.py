"""
Grid Trading Screening Views
筛选系统视图
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator

from grid_trading.models import ScreeningRecord, ScreeningResultModel


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
    valid_sort_fields = ['rank', 'symbol', 'composite_index', 'vdr', 'ker', 'ovr', 'amplitude_sum_15m', 'current_price']
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
