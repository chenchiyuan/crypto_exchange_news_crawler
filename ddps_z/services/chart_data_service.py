"""
图表数据服务（ChartDataService）

负责将DDPS计算结果格式化为前端Chart.js所需的数据格式。
支持时间范围查询和动态加载。
扩展: 支持惯性预测扇面数据。

Related:
    - PRD: docs/iterations/009-ddps-z-probability-engine/prd.md
    - PRD: docs/iterations/010-ddps-z-inertia-fan/prd.md
    - Architecture: docs/iterations/009-ddps-z-probability-engine/architecture.md
    - Architecture: docs/iterations/010-ddps-z-inertia-fan/architecture.md
    - TASK: TASK-009-008, TASK-010-009, TASK-010-010
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

import numpy as np
from django.conf import settings
from django.utils import timezone

from backtest.models import KLine
from ddps_z.services.ddps_service import DDPSService
# 🆕 惯性计算扩展
from ddps_z.calculators.inertia_calculator import InertiaCalculator
# 🆕 买入信号扩展 (迭代011)
from ddps_z.calculators.buy_signal_calculator import BuySignalCalculator
# 🆕 订单追踪扩展 (迭代012)
from ddps_z.calculators.order_tracker import OrderTracker

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
        # 🆕 惯性计算扩展
        self.inertia_calc = InertiaCalculator(base_period=5)
        # 🆕 买入信号扩展 (迭代011)
        self.buy_signal_calc = BuySignalCalculator()
        # 🆕 订单追踪扩展 (迭代012)
        self.order_tracker = OrderTracker()

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

            # 🆕 生成扇面数据 (TASK-010-009, Bug-013修复)
            fan_data = self._generate_fan_data(
                symbol=symbol,
                interval=interval,
                market_type=market_type,
                series=series,
                start_idx=start_idx,
                end_idx=end_idx
            )

            # 🆕 生成买入信号数据 (迭代011)
            buy_signals_data = self._generate_buy_signals_data(
                klines=klines,
                series=series,
                fan_data=fan_data,
                start_idx=start_idx,
                end_idx=end_idx
            )

            # 🆕 生成订单追踪数据 (迭代012)
            order_data = self._generate_order_data(
                buy_signals=buy_signals_data,
                klines=klines,
                ema_series=np.array([
                    v if v is not None else np.nan
                    for v in series['ema'][start_idx:end_idx]
                ])
            )

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
                    # 🆕 新增 fan 字段
                    'fan': fan_data,
                    # 🆕 新增 buy_signals 字段 (迭代011)
                    'buy_signals': buy_signals_data,
                    # 🆕 新增订单追踪字段 (迭代012)
                    'orders': order_data['orders'],
                    'order_statistics': order_data['statistics'],
                    'trade_events': order_data['trade_events'],
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

    # ============================================================
    # 🆕 惯性扇面扩展 (TASK-010-009, TASK-010-010)
    # ============================================================

    # 周期秒数映射
    INTERVAL_SECONDS = {
        '1m': 60,
        '5m': 300,
        '15m': 900,
        '30m': 1800,
        '1h': 3600,
        '4h': 14400,
        '1d': 86400,
    }

    def _get_interval_seconds(self, interval: str) -> int:
        """
        获取 K 线周期对应的秒数

        Args:
            interval: K 线周期 ('1h', '4h', '1d')

        Returns:
            秒数，默认 14400 (4h)
        """
        return self.INTERVAL_SECONDS.get(interval, 14400)

    def _generate_fan_data(
        self,
        symbol: str,
        interval: str,
        market_type: str,
        series: Dict[str, Any],
        start_idx: int,
        end_idx: int
    ) -> Optional[Dict[str, Any]]:
        """
        生成扇面数据（历史扇面通道 + 每根K线的惯性数据）

        Args:
            symbol: 交易对符号
            interval: K线周期
            market_type: 市场类型
            series: DDPS序列数据（包含timestamps, ema, ewma_std等）
            start_idx: 起始索引
            end_idx: 结束索引

        Returns:
            {
                'direction': 'up' | 'down',  # 当前β方向
                'lines': {
                    'upper': [{'t': timestamp_ms, 'y': price}, ...],
                    'mid': [{'t': timestamp_ms, 'y': price}, ...],
                    'lower': [{'t': timestamp_ms, 'y': price}, ...],
                },
                # 🆕 新增：每根K线的完整惯性数据（用于hover显示）
                'kline_data': [
                    {
                        't': timestamp_ms,
                        'p95': float,       # 静态阈值上界
                        'p5': float,        # 静态阈值下界
                        'fan_upper': float, # 扇面上界
                        'fan_mid': float,   # 扇面中轴
                        'fan_lower': float, # 扇面下界
                        'state': str,       # 状态标签
                        'adx': float,       # ADX值
                        'beta': float,      # β值
                        't_adj': float,     # 动态周期
                    },
                    ...
                ]
            } | None
        """
        try:
            # 获取切片后的序列数据
            timestamps = np.array(series['timestamps'][start_idx:end_idx])
            ema_series = np.array([v if v is not None else np.nan for v in series['ema'][start_idx:end_idx]])
            ewma_std_series = np.array([v if v is not None else np.nan for v in series['ewma_std'][start_idx:end_idx]])
            prices = np.array(series['prices'][start_idx:end_idx])

            # 🔧 Bug-014修复：静态阈值Z-Score常量（用于价格计算）
            z_p95 = 1.645   # 95%分位对应的Z值
            z_p5 = -1.645   # 5%分位对应的Z值

            n = len(timestamps)
            if n < 2:
                logger.warning('扇面数据生成失败: K线数量不足')
                return None

            # 获取K线数据（用于ADX计算）
            from backtest.models import KLine
            klines = list(KLine.objects.filter(
                symbol=symbol,
                interval=interval,
                market_type=market_type,
                open_time__gte=timezone.datetime.fromtimestamp(timestamps[0], tz=timezone.utc),
                open_time__lte=timezone.datetime.fromtimestamp(timestamps[-1], tz=timezone.utc)
            ).order_by('open_time'))

            if len(klines) != n:
                logger.warning(f'扇面数据生成失败: K线数量不匹配（期望{n}，实际{len(klines)}）')
                return None

            # 提取OHLC数据
            high = np.array([float(k.high_price) for k in klines])
            low = np.array([float(k.low_price) for k in klines])
            close = np.array([float(k.close_price) for k in klines])

            # 计算ADX序列
            from ddps_z.calculators.adx_calculator import ADXCalculator
            adx_calc = ADXCalculator(period=14)
            adx_result = adx_calc.calculate(high, low, close)
            adx_series = adx_result['adx']

            # 计算历史扇面序列
            fan_result = self.inertia_calc.calculate_historical_fan_series(
                timestamps=timestamps,
                ema_series=ema_series,
                sigma_series=ewma_std_series,
                adx_series=adx_series
            )

            # 格式化为前端需要的格式
            fan_timestamps = fan_result['timestamps']
            upper_values = fan_result['upper']
            mid_values = fan_result['mid']
            lower_values = fan_result['lower']
            beta_values = fan_result['beta']
            t_adj_values = fan_result['t_adj']

            # 构建线条数据（过滤掉NaN值，用于绘制）
            upper_line = []
            mid_line = []
            lower_line = []

            for i in range(len(fan_timestamps)):
                if (upper_values[i] is not None and not np.isnan(upper_values[i]) and
                    mid_values[i] is not None and not np.isnan(mid_values[i]) and
                    lower_values[i] is not None and not np.isnan(lower_values[i])):

                    upper_line.append({'t': fan_timestamps[i], 'y': upper_values[i]})
                    mid_line.append({'t': fan_timestamps[i], 'y': mid_values[i]})
                    lower_line.append({'t': fan_timestamps[i], 'y': lower_values[i]})

            if len(upper_line) == 0:
                logger.warning('扇面数据生成失败: 无有效数据点')
                return None

            # 🆕 构建每根K线的完整数据（用于hover显示）
            kline_data = []
            for i in range(len(fan_timestamps)):
                # 🔧 Bug-014修复：计算当前K线的静态阈值（价格）
                p95_price = None
                p5_price = None
                if (not np.isnan(ema_series[i]) and
                    not np.isnan(ewma_std_series[i])):
                    p95_price = ema_series[i] * (1 + z_p95 * ewma_std_series[i])
                    p5_price = ema_series[i] * (1 + z_p5 * ewma_std_series[i])

                # 判断状态
                state_label = '数据不足'
                if (upper_values[i] is not None and not np.isnan(upper_values[i]) and
                    mid_values[i] is not None and not np.isnan(mid_values[i]) and
                    lower_values[i] is not None and not np.isnan(lower_values[i]) and
                    i < len(prices)):

                    current_price = prices[i]
                    # 判断是否在扇面内
                    if lower_values[i] <= current_price <= upper_values[i]:
                        state_label = '惯性保护中'
                    elif abs(current_price - upper_values[i]) / upper_values[i] < 0.005 or \
                         abs(current_price - lower_values[i]) / lower_values[i] < 0.005:
                        state_label = '惯性衰减'
                    else:
                        state_label = '信号触发'

                kline_data.append({
                    't': fan_timestamps[i],
                    'p95': p95_price,  # 🔧 Bug-014修复：改为实际价格
                    'p5': p5_price,     # 🔧 Bug-014修复：改为实际价格
                    'fan_upper': upper_values[i] if upper_values[i] is not None and not np.isnan(upper_values[i]) else None,
                    'fan_mid': mid_values[i] if mid_values[i] is not None and not np.isnan(mid_values[i]) else None,
                    'fan_lower': lower_values[i] if lower_values[i] is not None and not np.isnan(lower_values[i]) else None,
                    'state': state_label,
                    'adx': adx_series[i] if i < len(adx_series) and not np.isnan(adx_series[i]) else None,
                    'beta': beta_values[i] if beta_values[i] is not None and not np.isnan(beta_values[i]) else None,
                    't_adj': t_adj_values[i] if t_adj_values[i] is not None and not np.isnan(t_adj_values[i]) else None,
                })

            # 确定当前方向（使用最后一个有效的β值）
            current_beta = None
            for beta in reversed(beta_values):
                if beta is not None and not np.isnan(beta):
                    current_beta = beta
                    break

            direction = 'up' if current_beta and current_beta > 0 else 'down'

            return {
                'direction': direction,
                'lines': {
                    'upper': upper_line,
                    'mid': mid_line,
                    'lower': lower_line,
                },
                # 🆕 新增：每根K线的完整数据
                'kline_data': kline_data,
            }

        except Exception as e:
            logger.exception(f'扇面数据生成失败: {e}')
            return None

    # ============================================================
    # 🆕 买入信号扩展 (迭代011)
    # ============================================================

    def _generate_buy_signals_data(
        self,
        klines: List[Dict[str, Any]],
        series: Dict[str, Any],
        fan_data: Optional[Dict[str, Any]],
        start_idx: int,
        end_idx: int
    ) -> List[Dict[str, Any]]:
        """
        生成买入信号数据

        基于策略1（EMA斜率未来预测）和策略2（惯性下跌中值突破）计算买入点。

        Args:
            klines: K线OHLC数据列表 [{'t': ms, 'o': float, 'h': float, 'l': float, 'c': float}, ...]
            series: DDPS序列数据（包含timestamps, ema, ewma_std等）
            fan_data: 扇面数据（包含kline_data，用于获取惯性mid和beta）
            start_idx: 起始索引
            end_idx: 结束索引

        Returns:
            买入信号列表，每个元素包含:
            - timestamp: int (毫秒时间戳)
            - kline_index: int (K线索引)
            - strategies: List[Dict] (策略触发信息)
            - buy_price: float (买入价格)
        """
        try:
            # 检查数据可用性
            if not klines or not fan_data or 'kline_data' not in fan_data:
                logger.warning('买入信号生成失败: 缺少必要数据')
                return []

            fan_kline_data = fan_data['kline_data']
            n = len(klines)

            # 验证数据长度
            if len(fan_kline_data) != n:
                logger.warning(
                    f'买入信号生成失败: 数据长度不匹配 '
                    f'(klines={n}, fan_kline_data={len(fan_kline_data)})'
                )
                return []

            # 准备计算器所需的数据
            # 转换klines格式为计算器需要的格式
            klines_for_calc = []
            for k in klines:
                klines_for_calc.append({
                    'open_time': k['t'],  # 毫秒时间戳
                    'high': k['h'],
                    'low': k['l'],
                    'close': k['c'],
                })

            # 从series中提取EMA序列（切片到对应范围）
            ema_series = np.array([
                v if v is not None else np.nan
                for v in series['ema'][start_idx:end_idx]
            ])

            # 从fan_kline_data中提取P5、beta、inertia_mid序列
            p5_series = np.array([
                fk['p5'] if fk['p5'] is not None else np.nan
                for fk in fan_kline_data
            ])

            beta_series = np.array([
                fk['beta'] if fk['beta'] is not None else np.nan
                for fk in fan_kline_data
            ])

            inertia_mid_series = np.array([
                fk['fan_mid'] if fk['fan_mid'] is not None else np.nan
                for fk in fan_kline_data
            ])

            # 调用买入信号计算器
            buy_signals = self.buy_signal_calc.calculate(
                klines=klines_for_calc,
                ema_series=ema_series,
                p5_series=p5_series,
                beta_series=beta_series,
                inertia_mid_series=inertia_mid_series
            )

            logger.info(
                f'买入信号生成完成: {len(buy_signals)}个买入点 / {n}根K线'
            )

            return buy_signals

        except Exception as e:
            logger.exception(f'买入信号生成失败: {e}')
            return []

    # ============================================================
    # 🆕 订单追踪扩展 (迭代012)
    # ============================================================

    def _generate_order_data(
        self,
        buy_signals: List[Dict[str, Any]],
        klines: List[Dict[str, Any]],
        ema_series: np.ndarray
    ) -> Dict[str, Any]:
        """
        生成订单追踪数据

        基于买入信号创建虚拟订单，检测EMA25回归卖出条件，计算盈亏和统计。

        Args:
            buy_signals: 买入信号列表（来自_generate_buy_signals_data）
            klines: K线OHLC数据列表 [{'t': ms, 'o': float, 'h': float, 'l': float, 'c': float}, ...]
            ema_series: EMA25序列

        Returns:
            {
                'orders': List[Dict],           # 订单列表
                'statistics': Dict,             # 统计信息
                'trade_events': List[Dict]      # 操作日志
            }
        """
        try:
            # 如果没有买入信号，返回空数据
            if not buy_signals:
                logger.info('订单追踪: 无买入信号，返回空数据')
                return {
                    'orders': [],
                    'statistics': {
                        'total_orders': 0,
                        'sold_orders': 0,
                        'holding_orders': 0,
                        'win_orders': 0,
                        'lose_orders': 0,
                        'win_rate': 0,
                        'total_invested': 0,
                        'total_profit': 0,
                        'total_profit_rate': 0,
                        'floating_profit': 0,
                        'avg_profit_rate': 0,
                        'avg_holding_periods': 0,
                    },
                    'trade_events': []
                }

            # 转换klines格式为OrderTracker需要的格式
            klines_for_tracker = []
            for k in klines:
                klines_for_tracker.append({
                    'open_time': k['t'],  # 毫秒时间戳
                    'high': k['h'],
                    'low': k['l'],
                    'close': k['c'],
                })

            # 获取当前价格（最后一根K线的收盘价）
            from decimal import Decimal
            current_price = Decimal(str(klines[-1]['c'])) if klines else None

            # 调用OrderTracker计算订单数据
            order_result = self.order_tracker.track(
                buy_signals=buy_signals,
                klines=klines_for_tracker,
                ema_series=ema_series,
                current_price=current_price
            )

            logger.info(
                f'订单追踪完成: 总订单{order_result["statistics"]["total_orders"]}, '
                f'已卖出{order_result["statistics"]["sold_orders"]}, '
                f'胜率{order_result["statistics"]["win_rate"]}%'
            )

            return order_result

        except Exception as e:
            logger.exception(f'订单追踪数据生成失败: {e}')
            return {
                'orders': [],
                'statistics': {
                    'total_orders': 0,
                    'sold_orders': 0,
                    'holding_orders': 0,
                    'win_orders': 0,
                    'lose_orders': 0,
                    'win_rate': 0,
                    'total_invested': 0,
                    'total_profit': 0,
                    'total_profit_rate': 0,
                    'floating_profit': 0,
                    'avg_profit_rate': 0,
                    'avg_holding_periods': 0,
                },
                'trade_events': []
            }
