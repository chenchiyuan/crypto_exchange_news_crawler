"""
图表数据服务（ChartDataService）

负责将DDPS计算结果格式化为前端Chart.js所需的数据格式。
支持时间范围查询和动态加载。

Related:
    - PRD: docs/iterations/009-ddps-z-probability-engine/prd.md
    - Architecture: docs/iterations/009-ddps-z-probability-engine/architecture.md
    - TASK: TASK-009-008
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

import numpy as np
from django.conf import settings
from django.utils import timezone

from backtest.models import KLine
from ddps_z.services.ddps_service import DDPSService

logger = logging.getLogger(__name__)


# 时间范围映射（天数）
TIME_RANGE_DAYS = {
    '1w': 7,
    '1m': 30,
    '3m': 90,
    '6m': 180,
    '1y': 365,
    'all': None,  # None表示全部数据
}


class ChartDataService:
    """图表数据服务 - 格式化DDPS数据供前端图表使用"""

    # 分位带颜色配置
    BAND_COLORS = {
        'p5': 'rgba(220, 53, 69, 0.3)',      # 红色 - 超卖区
        'p10': 'rgba(255, 193, 7, 0.2)',     # 黄色 - 弱超卖
        'p50': 'rgba(108, 117, 125, 0.1)',   # 灰色 - 中性
        'p90': 'rgba(255, 193, 7, 0.2)',     # 黄色 - 弱超买
        'p95': 'rgba(40, 167, 69, 0.3)',     # 绿色 - 超买区
    }

    def __init__(self):
        """初始化图表数据服务"""
        self.ddps_service = DDPSService()
        self.config = settings.DDPS_CONFIG

    def get_chart_data(
        self,
        symbol: str,
        interval: Optional[str] = None,
        market_type: str = 'futures',
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        time_range: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取K线图表数据（包含概率带）

        Args:
            symbol: 交易对符号
            interval: K线周期
            market_type: 市场类型
            limit: 返回K线数量限制（默认500，最大5000）
            start_time: 开始时间戳（毫秒）
            end_time: 结束时间戳（毫秒）
            time_range: 快捷时间范围 ('1w', '1m', '3m', '6m', '1y', 'all')

        Returns:
            {
                'symbol': str,
                'interval': str,
                'success': bool,
                'error': str | None,
                'chart': {
                    'candles': [...],      # K线数据
                    'ema': [...],          # EMA线数据
                    'bands': {...},        # 概率带数据
                    'zscore': [...],       # Z-Score序列
                    'current': {...},      # 当前指标值
                } | None,
                'meta': {
                    'total_available': int,  # 可用K线总数
                    'returned': int,         # 返回的K线数
                    'earliest_time': int,    # 最早K线时间戳
                    'latest_time': int,      # 最新K线时间戳
                    'has_more': bool,        # 是否还有更早数据
                }
            }
        """
        interval = interval or self.config['DEFAULT_INTERVAL']

        try:
            # 获取数据库中该交易对的K线元信息
            meta_info = self._get_kline_meta(symbol, interval, market_type)

            # 解析时间范围
            start_dt, end_dt = self._parse_time_range(
                start_time, end_time, time_range, meta_info
            )

            # 获取DDPS序列数据
            # 传递足够大的limit确保获取所有需要的历史数据用于计算EMA和Z-Score
            series_limit = meta_info['total_available'] if meta_info['total_available'] else 10000
            series_result = self.ddps_service.calculate_series(
                symbol, interval, market_type, limit=series_limit
            )

            if not series_result['success']:
                return {
                    'symbol': symbol,
                    'interval': interval,
                    'success': False,
                    'error': series_result['error'],
                    'chart': None,
                    'meta': meta_info,
                }

            series = series_result['series']

            # 先获取K线数据（OHLC格式）- 这是实际要显示的数据
            klines = self._fetch_klines_ohlc_range(
                symbol, interval, market_type, start_dt, end_dt, limit
            )

            if not klines:
                return {
                    'symbol': symbol,
                    'interval': interval,
                    'success': False,
                    'error': '未找到K线数据',
                    'chart': None,
                    'meta': meta_info,
                }

            # 根据实际获取的K线时间范围来切片series数据
            # 确保概率带等指标与K线数据完全对齐
            kline_start_ts = klines[0]['t'] / 1000  # 转为秒
            kline_end_ts = klines[-1]['t'] / 1000

            # 在series中找到对应的索引范围
            start_idx, end_idx = self._get_indices_by_timestamp_range(
                series['timestamps'], kline_start_ts, kline_end_ts
            )

            # 构建EMA线数据
            ema_data = self._format_line_data(
                series['timestamps'][start_idx:end_idx],
                series['ema'][start_idx:end_idx]
            )

            # 构建概率带数据
            bands = self._calculate_probability_bands(
                series['timestamps'][start_idx:end_idx],
                series['prices'][start_idx:end_idx],
                series['ema'][start_idx:end_idx],
                series['quantile_bands']
            )

            # 构建Z-Score序列
            zscore_data = self._format_line_data(
                series['timestamps'][start_idx:end_idx],
                series['zscore'][start_idx:end_idx]
            )

            # 获取当前指标
            current_result = self.ddps_service.calculate(symbol, interval, market_type)
            current = current_result['data'] if current_result['success'] else None

            # 计算返回的元信息
            returned_count = len(klines)
            # has_more: 判断是否还有更早的数据
            # 如果K线的最早时间大于数据库中的最早时间，说明还有更多数据
            has_more = False
            if meta_info['earliest_time'] and klines:
                earliest_kline_time = klines[0]['t']
                has_more = earliest_kline_time > meta_info['earliest_time']

            return {
                'symbol': symbol,
                'interval': interval,
                'success': True,
                'error': None,
                'chart': {
                    'candles': klines,
                    'ema': ema_data,
                    'bands': bands,
                    'zscore': zscore_data,
                    'current': current,
                },
                'meta': {
                    'total_available': meta_info['total_available'],
                    'returned': returned_count,
                    'earliest_time': meta_info['earliest_time'],
                    'latest_time': meta_info['latest_time'],
                    'has_more': has_more,
                    'current_start': int(start_dt.timestamp() * 1000) if start_dt else None,
                    'current_end': int(end_dt.timestamp() * 1000) if end_dt else None,
                },
            }

        except Exception as e:
            logger.exception(f'图表数据获取失败: {symbol}')
            return {
                'symbol': symbol,
                'interval': interval,
                'success': False,
                'error': str(e),
                'chart': None,
                'meta': None,
            }

    def _get_kline_meta(
        self,
        symbol: str,
        interval: str,
        market_type: str
    ) -> Dict[str, Any]:
        """获取K线元信息"""
        total = KLine.objects.filter(
            symbol=symbol,
            interval=interval,
            market_type=market_type
        ).count()

        earliest = None
        latest = None

        if total > 0:
            first = KLine.objects.filter(
                symbol=symbol,
                interval=interval,
                market_type=market_type
            ).order_by('open_time').first()

            last = KLine.objects.filter(
                symbol=symbol,
                interval=interval,
                market_type=market_type
            ).order_by('-open_time').first()

            if first:
                earliest = int(first.open_time.timestamp() * 1000)
            if last:
                latest = int(last.open_time.timestamp() * 1000)

        return {
            'total_available': total,
            'earliest_time': earliest,
            'latest_time': latest,
        }

    def _parse_time_range(
        self,
        start_time: Optional[int],
        end_time: Optional[int],
        time_range: Optional[str],
        meta_info: Dict[str, Any]
    ) -> tuple:
        """
        解析时间范围参数

        Returns:
            (start_datetime, end_datetime) - None表示不限制
        """
        now = timezone.now()
        end_dt = now

        # 如果指定了end_time
        if end_time:
            end_dt = datetime.fromtimestamp(end_time / 1000, tz=timezone.utc)

        # 优先使用快捷时间范围
        if time_range and time_range in TIME_RANGE_DAYS:
            days = TIME_RANGE_DAYS[time_range]
            if days is None:  # 'all'
                # 使用数据库中最早的时间
                if meta_info['earliest_time']:
                    start_dt = datetime.fromtimestamp(
                        meta_info['earliest_time'] / 1000, tz=timezone.utc
                    )
                else:
                    start_dt = None
            else:
                start_dt = end_dt - timedelta(days=days)
            return start_dt, end_dt

        # 使用start_time参数
        if start_time:
            start_dt = datetime.fromtimestamp(start_time / 1000, tz=timezone.utc)
            return start_dt, end_dt

        # 默认：不限制开始时间（由limit控制数量）
        return None, end_dt

    def _get_time_range_indices(
        self,
        timestamps: List[float],
        start_dt: Optional[datetime],
        end_dt: Optional[datetime]
    ) -> tuple:
        """
        获取时间范围对应的数组索引

        Returns:
            (start_idx, end_idx)
        """
        if not timestamps:
            return 0, 0

        start_idx = 0
        end_idx = len(timestamps)

        if start_dt:
            start_ts = start_dt.timestamp()
            for i, ts in enumerate(timestamps):
                if ts >= start_ts:
                    start_idx = i
                    break

        if end_dt:
            end_ts = end_dt.timestamp()
            for i in range(len(timestamps) - 1, -1, -1):
                if timestamps[i] <= end_ts:
                    end_idx = i + 1
                    break

        return start_idx, end_idx

    def _get_indices_by_timestamp_range(
        self,
        timestamps: List[float],
        start_ts: float,
        end_ts: float
    ) -> tuple:
        """
        根据精确的时间戳范围获取数组索引

        Args:
            timestamps: 时间戳列表（秒）
            start_ts: 开始时间戳（秒）
            end_ts: 结束时间戳（秒）

        Returns:
            (start_idx, end_idx) - 包含start_idx，不包含end_idx
        """
        if not timestamps:
            return 0, 0

        start_idx = 0
        end_idx = len(timestamps)

        # 找到第一个 >= start_ts 的索引
        for i, ts in enumerate(timestamps):
            if ts >= start_ts:
                start_idx = i
                break

        # 找到最后一个 <= end_ts 的索引（+1因为切片不包含end）
        for i in range(len(timestamps) - 1, -1, -1):
            if timestamps[i] <= end_ts:
                end_idx = i + 1
                break

        return start_idx, end_idx

    def _fetch_klines_ohlc_range(
        self,
        symbol: str,
        interval: str,
        market_type: str,
        start_dt: Optional[datetime],
        end_dt: Optional[datetime],
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        获取指定时间范围的OHLC格式K线数据

        Returns:
            [{
                't': timestamp_ms,
                'o': open,
                'h': high,
                'l': low,
                'c': close,
                'v': volume
            }, ...]
        """
        queryset = KLine.objects.filter(
            symbol=symbol,
            interval=interval,
            market_type=market_type
        )

        # 应用时间范围过滤
        if start_dt:
            queryset = queryset.filter(open_time__gte=start_dt)
        if end_dt:
            queryset = queryset.filter(open_time__lte=end_dt)

        # 获取最新的limit条数据
        klines = queryset.order_by('-open_time')[:limit]

        # 反转为时间升序
        klines = list(klines)
        klines.reverse()

        return [
            {
                't': int(k.open_time.timestamp() * 1000),  # 毫秒时间戳
                'o': float(k.open_price),
                'h': float(k.high_price),
                'l': float(k.low_price),
                'c': float(k.close_price),
                'v': float(k.volume),
            }
            for k in klines
        ]

    def _format_line_data(
        self,
        timestamps: List[float],
        values: List[Optional[float]]
    ) -> List[Dict[str, Any]]:
        """
        格式化线图数据

        Returns:
            [{'t': timestamp_ms, 'y': value}, ...]
        """
        return [
            {
                't': int(t * 1000),  # 毫秒时间戳
                'y': v,
            }
            for t, v in zip(timestamps, values)
            if v is not None
        ]

    def _calculate_probability_bands(
        self,
        timestamps: List[float],
        prices: List[float],
        ema_values: List[Optional[float]],
        quantile_bands: Dict[str, float]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        计算概率带数据

        概率带 = EMA × (1 + Z × σ_deviation)

        由于我们使用的是偏离率的EWMA，概率带实际上是基于历史偏离率分布的。
        简化处理：使用固定的偏离率区间来绘制。

        Returns:
            {
                'p5': [{'t': ts, 'y': price}, ...],   # 5%分位线
                'p10': [...],                         # 10%分位线
                'p50': [...],                         # 50%分位线（EMA）
                'p90': [...],
                'p95': [...],
            }
        """
        bands = {
            'p5': [],
            'p10': [],
            'p50': [],
            'p90': [],
            'p95': [],
        }

        # 使用历史波动率估算带宽
        # 简化：假设偏离率标准差约为2-3%
        avg_volatility = 0.025  # 2.5%的典型偏离率标准差

        for i, (ts, price, ema) in enumerate(zip(timestamps, prices, ema_values)):
            if ema is None:
                continue

            t = int(ts * 1000)  # 转换为毫秒时间戳

            # 计算各分位带的价格水平
            # Band = EMA × (1 + Z × σ)
            bands['p5'].append({
                't': t,
                'y': ema * (1 + quantile_bands['p5'] * avg_volatility)
            })
            bands['p10'].append({
                't': t,
                'y': ema * (1 + quantile_bands['p10'] * avg_volatility)
            })
            bands['p50'].append({
                't': t,
                'y': ema  # 50%分位就是EMA本身
            })
            bands['p90'].append({
                't': t,
                'y': ema * (1 + quantile_bands['p90'] * avg_volatility)
            })
            bands['p95'].append({
                't': t,
                'y': ema * (1 + quantile_bands['p95'] * avg_volatility)
            })

        return bands

    def get_zscore_chart_data(
        self,
        symbol: str,
        interval: Optional[str] = None,
        market_type: str = 'futures',
        limit: int = 500
    ) -> Dict[str, Any]:
        """
        获取Z-Score图表数据（独立面板）

        Returns:
            {
                'symbol': str,
                'success': bool,
                'chart': {
                    'zscore': [...],        # Z-Score序列
                    'thresholds': {...},    # 阈值线
                } | None
            }
        """
        interval = interval or self.config['DEFAULT_INTERVAL']

        try:
            series_result = self.ddps_service.calculate_series(
                symbol, interval, market_type
            )

            if not series_result['success']:
                return {
                    'symbol': symbol,
                    'success': False,
                    'error': series_result['error'],
                    'chart': None,
                }

            series = series_result['series']
            total = len(series['timestamps'])
            start_idx = max(0, total - limit)

            zscore_data = [
                {
                    't': int(series['timestamps'][i] * 1000),
                    'y': series['zscore'][i],
                }
                for i in range(start_idx, total)
                if series['zscore'][i] is not None
            ]

            return {
                'symbol': symbol,
                'success': True,
                'error': None,
                'chart': {
                    'zscore': zscore_data,
                    'thresholds': {
                        'oversold_5': self.config['Z_SCORE_OVERSOLD'],
                        'oversold_10': -1.28,
                        'neutral': 0,
                        'overbought_90': 1.28,
                        'overbought_95': self.config['Z_SCORE_OVERBOUGHT'],
                    },
                },
            }

        except Exception as e:
            logger.exception(f'Z-Score图表数据获取失败: {symbol}')
            return {
                'symbol': symbol,
                'success': False,
                'error': str(e),
                'chart': None,
            }
