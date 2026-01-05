"""
DDPS服务（DDPSService）

业务编排服务，协调各个计算器完成完整的DDPS计算流程。

Related:
    - PRD: docs/iterations/009-ddps-z-probability-engine/prd.md
    - Architecture: docs/iterations/009-ddps-z-probability-engine/architecture.md
    - TASK: TASK-009-007
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np
from django.conf import settings

from backtest.models import KLine
from ddps_z.calculators.ema_calculator import EMACalculator
from ddps_z.calculators.ewma_calculator import EWMACalculator
from ddps_z.calculators.zscore_calculator import ZScoreCalculator
from ddps_z.calculators.signal_evaluator import SignalEvaluator

logger = logging.getLogger(__name__)


class DDPSService:
    """DDPS计算服务 - 编排完整的DDPS计算流程"""

    def __init__(self):
        """初始化DDPS服务"""
        config = settings.DDPS_CONFIG
        self.ema_period = config['EMA_PERIOD']
        self.ewma_window_n = config['EWMA_WINDOW_N']
        self.min_klines = config['MIN_KLINES_REQUIRED']
        self.default_interval = config['DEFAULT_INTERVAL']

        # 初始化计算器
        self.ema_calc = EMACalculator(period=self.ema_period)
        self.ewma_calc = EWMACalculator(window_n=self.ewma_window_n)
        self.zscore_calc = ZScoreCalculator()
        self.signal_eval = SignalEvaluator()

    def calculate(
        self,
        symbol: str,
        interval: Optional[str] = None,
        market_type: str = 'futures'
    ) -> Dict[str, Any]:
        """
        执行完整的DDPS计算

        Args:
            symbol: 交易对符号，如'BTCUSDT'
            interval: K线周期，默认'4h'
            market_type: 市场类型，'futures'或'spot'

        Returns:
            {
                'symbol': str,
                'interval': str,
                'market_type': str,
                'success': bool,
                'error': str | None,
                'data': {
                    'current_price': float,
                    'current_ema': float,
                    'current_deviation': float,
                    'ewma_mean': float,
                    'ewma_std': float,
                    'zscore': float,
                    'percentile': float,
                    'zone': str,
                    'zone_label': str,
                    'rvol': float | None,
                    'signal': dict,
                    'kline_count': int,
                } | None
            }
        """
        interval = interval or self.default_interval

        try:
            # Step 1: 获取K线数据
            klines = self._fetch_klines(symbol, interval, market_type)

            if len(klines) < self.min_klines:
                return {
                    'symbol': symbol,
                    'interval': interval,
                    'market_type': market_type,
                    'success': False,
                    'error': f'K线数据不足: 需要{self.min_klines}根，实际{len(klines)}根',
                    'data': None,
                }

            # Step 2: 提取价格和成交量序列
            prices = np.array([float(k.close_price) for k in klines])
            volumes = np.array([float(k.volume) for k in klines])

            # Step 3: EMA和偏离率计算
            deviation = self.ema_calc.calculate_deviation_series(prices)
            ema_series = self.ema_calc.calculate_ema_series(prices)

            # Step 4: EWMA均值和方差计算
            ewma_result = self.ewma_calc.calculate(deviation)

            # Step 5: Z-Score计算
            zscore_result = self.zscore_calc.calculate(
                deviation,
                ewma_result['ewma_mean'],
                ewma_result['ewma_std']
            )

            # Step 6: RVOL计算
            rvol = self.signal_eval.calculate_rvol(volumes)

            # Step 7: 信号评估
            signal = self.signal_eval.evaluate(
                zscore_result['current_zscore'],
                zscore_result['current_percentile'],
                zscore_result['current_zone'],
                rvol
            )

            # 构建返回数据
            return {
                'symbol': symbol,
                'interval': interval,
                'market_type': market_type,
                'success': True,
                'error': None,
                'data': {
                    'current_price': float(prices[-1]),
                    'current_ema': float(ema_series[-1]) if not np.isnan(ema_series[-1]) else None,
                    'current_deviation': float(deviation[-1]) if not np.isnan(deviation[-1]) else None,
                    'ewma_mean': ewma_result['current_mean'],
                    'ewma_std': ewma_result['current_std'],
                    'zscore': zscore_result['current_zscore'],
                    'percentile': zscore_result['current_percentile'],
                    'zone': zscore_result['current_zone'],
                    'zone_label': zscore_result['current_zone_label'],
                    'rvol': rvol,
                    'signal': self.signal_eval.to_dict(signal),
                    'kline_count': len(klines),
                },
            }

        except Exception as e:
            logger.exception(f'DDPS计算失败: {symbol}')
            return {
                'symbol': symbol,
                'interval': interval,
                'market_type': market_type,
                'success': False,
                'error': str(e),
                'data': None,
            }

    def calculate_series(
        self,
        symbol: str,
        interval: Optional[str] = None,
        market_type: str = 'futures',
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        获取完整的时间序列数据（用于图表绘制）

        Args:
            symbol: 交易对符号
            interval: K线周期
            market_type: 市场类型
            limit: K线数量限制（None表示获取全部）

        Returns:
            {
                'symbol': str,
                'interval': str,
                'success': bool,
                'error': str | None,
                'series': {
                    'timestamps': List[float],  # 时间戳序列
                    'prices': List[float],      # 价格序列
                    'ema': List[float],         # EMA序列
                    'deviation': List[float],   # 偏离率序列
                    'zscore': List[float],      # Z-Score序列
                    'volumes': List[float],     # 成交量序列
                    'quantile_bands': dict,     # 分位带
                } | None
            }
        """
        interval = interval or self.default_interval

        try:
            # 获取K线数据
            klines = self._fetch_klines(symbol, interval, market_type, limit=limit)

            if len(klines) < self.min_klines:
                return {
                    'symbol': symbol,
                    'interval': interval,
                    'success': False,
                    'error': f'K线数据不足: 需要{self.min_klines}根，实际{len(klines)}根',
                    'series': None,
                }

            # 提取数据
            timestamps = [k.open_time.timestamp() for k in klines]
            prices = np.array([float(k.close_price) for k in klines])
            volumes = np.array([float(k.volume) for k in klines])

            # 计算序列
            ema_series = self.ema_calc.calculate_ema_series(prices)
            deviation = self.ema_calc.calculate_deviation_series(prices)
            ewma_result = self.ewma_calc.calculate(deviation)
            zscore_result = self.zscore_calc.calculate(
                deviation,
                ewma_result['ewma_mean'],
                ewma_result['ewma_std']
            )

            # 将NaN转换为None（JSON兼容）
            def to_list(arr):
                return [None if np.isnan(v) else float(v) for v in arr]

            return {
                'symbol': symbol,
                'interval': interval,
                'success': True,
                'error': None,
                'series': {
                    'timestamps': timestamps,
                    'prices': prices.tolist(),
                    'ema': to_list(ema_series),
                    'deviation': to_list(deviation),
                    'zscore': to_list(zscore_result['zscore_series']),
                    'volumes': volumes.tolist(),
                    'quantile_bands': zscore_result['quantile_bands'],
                },
            }

        except Exception as e:
            logger.exception(f'DDPS序列计算失败: {symbol}')
            return {
                'symbol': symbol,
                'interval': interval,
                'success': False,
                'error': str(e),
                'series': None,
            }

    def _fetch_klines(
        self,
        symbol: str,
        interval: str,
        market_type: str,
        limit: Optional[int] = None
    ) -> List[KLine]:
        """
        从数据库获取K线数据

        Args:
            symbol: 交易对符号
            interval: K线周期
            market_type: 市场类型
            limit: K线数量限制（None表示使用默认限制）

        Returns:
            K线数据列表（按时间升序）
        """
        # 查询K线，按时间升序排列
        queryset = KLine.objects.filter(
            symbol=symbol,
            interval=interval,
            market_type=market_type
        ).order_by('open_time')

        # 限制查询数量
        if limit is None:
            # 默认限制：用于实时计算场景
            max_klines = self.min_klines + 100
        else:
            # 自定义限制：用于图表显示场景，需要更多历史数据
            max_klines = limit

        klines = list(queryset.order_by('-open_time')[:max_klines])

        # 反转为时间升序
        klines.reverse()

        logger.debug(f'获取K线: {symbol} {interval} {market_type}, 数量={len(klines)}')

        return klines
