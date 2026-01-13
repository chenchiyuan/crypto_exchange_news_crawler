"""
DDPS-Z API Views

动态偏离概率空间2.0系统的API视图。

Related:
    - PRD: docs/iterations/009-ddps-z-probability-engine/prd.md
    - Architecture: docs/iterations/009-ddps-z-probability-engine/architecture.md
    - TASK: TASK-009-009, TASK-009-010, TASK-009-011
"""

import logging
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from monitor.models import FuturesContract
from ddps_z.services.ddps_service import DDPSService
from ddps_z.services.chart_data_service import ChartDataService

logger = logging.getLogger(__name__)


class ContractListAPIView(APIView):
    """
    合约列表API

    GET /api/ddps-z/contracts/
    返回当前活跃的合约列表，按市值排序。

    Query Parameters:
        - search: 关键字搜索（可选）
        - market_type: 市场类型，'futures'或'spot'（默认'futures'）

    Response:
        {
            "contracts": [
                {
                    "symbol": "BTCUSDT",
                    "base_asset": "BTC",
                    "quote_asset": "USDT",
                    "market_cap": 1234567890.0
                },
                ...
            ],
            "total": 100
        }
    """

    def get(self, request):
        search = request.query_params.get('search', '').strip().upper()
        market_type = request.query_params.get('market_type', 'futures')

        try:
            # 查询活跃合约
            queryset = FuturesContract.objects.filter(status='active')

            # 关键字搜索
            if search:
                queryset = queryset.filter(symbol__icontains=search)

            # 按市值排序（如果有市值字段）
            # 注意：FuturesContract模型可能没有market_cap字段，需要根据实际情况调整
            if hasattr(FuturesContract, 'market_cap'):
                queryset = queryset.order_by('-market_cap')
            else:
                queryset = queryset.order_by('symbol')

            # 构建响应数据
            contracts = []
            for contract in queryset:
                contracts.append({
                    'symbol': contract.symbol,
                    'base_asset': contract.base_asset if hasattr(contract, 'base_asset') else contract.symbol.replace('USDT', ''),
                    'quote_asset': contract.quote_asset if hasattr(contract, 'quote_asset') else 'USDT',
                    'market_cap': float(contract.market_cap) if hasattr(contract, 'market_cap') and contract.market_cap else None,
                })

            return Response({
                'contracts': contracts,
                'total': len(contracts),
            })

        except Exception as e:
            logger.exception('合约列表查询失败')
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DDPSCalculateAPIView(APIView):
    """
    DDPS计算API

    GET /api/ddps-z/calculate/
    实时计算指定合约的DDPS指标。

    Query Parameters:
        - symbol: 交易对符号（必填）
        - interval: K线周期（可选，默认'4h'）
        - market_type: 市场类型（可选，默认'futures'）

    Response:
        {
            "symbol": "BTCUSDT",
            "interval": "4h",
            "market_type": "futures",
            "success": true,
            "data": {
                "current_price": 50000.0,
                "current_ema": 49500.0,
                "current_deviation": 0.0101,
                "zscore": 1.5,
                "percentile": 93.32,
                "zone": "overbought",
                "zone_label": "超买 (90-95%)",
                "rvol": 2.5,
                "signal": {...}
            }
        }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ddps_service = DDPSService()

    def get(self, request):
        symbol = request.query_params.get('symbol')
        interval = request.query_params.get('interval', settings.DDPS_CONFIG['DEFAULT_INTERVAL'])
        market_type = request.query_params.get('market_type', 'futures')

        # 参数验证
        if not symbol:
            return Response(
                {'error': 'symbol参数必填'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 执行DDPS计算
        result = self.ddps_service.calculate(symbol, interval, market_type)

        if result['success']:
            return Response(result)
        else:
            return Response(
                result,
                status=status.HTTP_400_BAD_REQUEST if 'K线数据不足' in str(result.get('error', ''))
                else status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class KLineChartAPIView(APIView):
    """
    K线图表API

    GET /api/ddps-z/chart/
    返回K线数据、EMA线和概率带，用于前端图表绘制。

    Query Parameters:
        - symbol: 交易对符号（必填）
        - interval: K线周期（可选，默认'4h'）
        - market_type: 市场类型（可选，默认'futures'）
        - limit: 返回K线数量（可选，默认500，最大5000）
        - start_time: 开始时间戳（毫秒，可选）
        - end_time: 结束时间戳（毫秒，可选）
        - range: 快捷时间范围（可选）: '1w', '1m', '3m', '6m', '1y', 'all'

    Response:
        {
            "symbol": "BTCUSDT",
            "interval": "4h",
            "success": true,
            "chart": {
                "candles": [...],
                "ema": [...],
                "bands": {...},
                "zscore": [...],
                "current": {...}
            },
            "meta": {
                "total_available": 2396,
                "returned": 500,
                "earliest_time": 1701504000000,
                "latest_time": 1736078400000,
                "has_more": true
            }
        }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.chart_service = ChartDataService()

    def get(self, request):
        symbol = request.query_params.get('symbol')
        interval = request.query_params.get('interval', settings.DDPS_CONFIG['DEFAULT_INTERVAL'])
        market_type = request.query_params.get('market_type', 'futures')
        limit = request.query_params.get('limit', 500)
        start_time = request.query_params.get('start_time')
        end_time = request.query_params.get('end_time')
        time_range = request.query_params.get('range')
        # 🆕 策略模式参数 (迭代037)
        strategy_mode = request.query_params.get('strategy_mode', 'strategy16')

        # 🆕 周期阈值参数 (迭代039)
        cycle_threshold_pct = request.query_params.get('cycle_threshold_pct')
        cycle_slope_window = request.query_params.get('cycle_slope_window')
        cycle_window = request.query_params.get('cycle_window')

        # 参数验证
        if not symbol:
            return Response(
                {'error': 'symbol参数必填'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 验证strategy_mode参数
        if strategy_mode not in ('strategy16', 'legacy'):
            strategy_mode = 'strategy16'

        # 🆕 解析周期阈值参数 (迭代039)
        cycle_params = {}
        if cycle_threshold_pct:
            try:
                cycle_params['threshold_pct'] = float(cycle_threshold_pct)
            except (ValueError, TypeError):
                pass
        if cycle_slope_window:
            try:
                cycle_params['slope_window'] = int(cycle_slope_window)
            except (ValueError, TypeError):
                pass
        if cycle_window:
            try:
                cycle_params['cycle_window'] = int(cycle_window)
            except (ValueError, TypeError):
                pass

        try:
            limit = int(limit)
            if limit < 1:
                limit = 500
            elif limit > 5000:
                limit = 5000
        except (ValueError, TypeError):
            limit = 500

        # 解析时间参数
        start_ts = None
        end_ts = None

        if start_time:
            try:
                start_ts = int(start_time)
            except (ValueError, TypeError):
                pass

        if end_time:
            try:
                end_ts = int(end_time)
            except (ValueError, TypeError):
                pass

        # 获取图表数据
        result = self.chart_service.get_chart_data(
            symbol=symbol,
            interval=interval,
            market_type=market_type,
            limit=limit,
            start_time=start_ts,
            end_time=end_ts,
            time_range=time_range,
            strategy_mode=strategy_mode,  # 🆕 传递策略模式参数
            cycle_params=cycle_params  # 🆕 传递周期阈值参数 (迭代039)
        )

        if result['success']:
            return Response(result)
        else:
            return Response(
                result,
                status=status.HTTP_400_BAD_REQUEST if 'K线数据不足' in str(result.get('error', ''))
                else status.HTTP_500_INTERNAL_SERVER_ERROR
            )
