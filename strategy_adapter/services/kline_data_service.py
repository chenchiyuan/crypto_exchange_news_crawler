"""
K线数据服务

Purpose:
    为回测系统提供历史K线数据，独立于DDPS-Z模块。
    调用币安API获取OHLCV数据，并计算技术指标（EMA、MACD）。

关联任务: TASK-016-001
关联功能点: F1.1, F1.2, F1.3

Example:
    >>> service = KlineDataService()
    >>> klines = service.get_klines(
    ...     symbol="ETHUSDT",
    ...     interval="4h",
    ...     start_time=1704067200000,  # 2024-01-01 00:00:00 UTC
    ...     end_time=1735689600000     # 2025-01-01 00:00:00 UTC
    ... )
    >>> print(klines[0])
    {'t': 1704067200000, 'o': 2200.5, 'h': 2250.0, 'l': 2180.0, 'c': 2230.0, 'v': 15000.5}
"""

import logging
from typing import List, Optional, Dict, Any

import requests

logger = logging.getLogger(__name__)


class KlineDataService:
    """
    独立的K线数据服务

    Attributes:
        BASE_URL: 币安K线API端点
        MAX_LIMIT: 单次请求最大数量（币安限制1000）
        timeout: HTTP请求超时时间（秒）
    """

    BASE_URL = "https://api.binance.com/api/v3/klines"
    MAX_LIMIT = 1000

    def __init__(self, timeout: int = 10):
        """
        初始化K线数据服务

        Args:
            timeout: HTTP请求超时时间（秒），默认10秒
        """
        self.timeout = timeout

    def get_klines_with_indicators(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: int
    ) -> Dict[str, Any]:
        """
        获取K线数据及技术指标（EMA7, EMA25, EMA99, MACD）

        Args:
            symbol: 交易对，如 "ETHUSDT"
            interval: K线周期，如 "4h", "1d"
            start_time: 开始时间戳（毫秒）
            end_time: 结束时间戳（毫秒）

        Returns:
            包含K线和指标的字典:
            {
                'candles': [...],
                'ema7': [{'t': 时间戳, 'v': 值}, ...],
                'ema25': [...],
                'ema99': [...],
                'macd': {
                    'macd': [{'t': 时间戳, 'v': 值}, ...],
                    'signal': [...],
                    'histogram': [...]
                }
            }
        """
        # 获取K线数据
        candles = self.get_klines(symbol, interval, start_time, end_time)

        if not candles:
            return {
                'candles': [],
                'ema7': [],
                'ema25': [],
                'ema99': [],
                'macd': {'macd': [], 'signal': [], 'histogram': []}
            }

        # 提取收盘价序列
        closes = [c['c'] for c in candles]
        timestamps = [c['t'] for c in candles]

        # 计算EMA
        ema7 = self._calculate_ema(closes, 7)
        ema25 = self._calculate_ema(closes, 25)
        ema99 = self._calculate_ema(closes, 99)

        # 计算MACD (12, 26, 9)
        macd_data = self._calculate_macd(closes, 12, 26, 9)

        # 格式化输出
        def format_series(values, timestamps):
            return [
                {'t': t, 'v': round(v, 8) if v is not None else None}
                for t, v in zip(timestamps, values)
            ]

        return {
            'candles': candles,
            'ema7': format_series(ema7, timestamps),
            'ema25': format_series(ema25, timestamps),
            'ema99': format_series(ema99, timestamps),
            'macd': {
                'macd': format_series(macd_data['macd'], timestamps),
                'signal': format_series(macd_data['signal'], timestamps),
                'histogram': format_series(macd_data['histogram'], timestamps)
            }
        }

    def _calculate_ema(self, prices: List[float], period: int) -> List[Optional[float]]:
        """
        计算指数移动平均线（EMA）

        Args:
            prices: 价格序列
            period: EMA周期

        Returns:
            EMA值列表，前period-1个值为None
        """
        if len(prices) < period:
            return [None] * len(prices)

        ema = [None] * len(prices)
        multiplier = 2 / (period + 1)

        # 第一个EMA值为前period个价格的SMA
        sma = sum(prices[:period]) / period
        ema[period - 1] = sma

        # 计算后续EMA值
        for i in range(period, len(prices)):
            ema[i] = (prices[i] - ema[i - 1]) * multiplier + ema[i - 1]

        return ema

    def _calculate_macd(
        self,
        prices: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Dict[str, List[Optional[float]]]:
        """
        计算MACD指标

        Args:
            prices: 价格序列
            fast_period: 快线周期，默认12
            slow_period: 慢线周期，默认26
            signal_period: 信号线周期，默认9

        Returns:
            {
                'macd': MACD线 (快线EMA - 慢线EMA),
                'signal': 信号线 (MACD的EMA),
                'histogram': 柱状图 (MACD - Signal)
            }
        """
        # 计算快慢EMA
        fast_ema = self._calculate_ema(prices, fast_period)
        slow_ema = self._calculate_ema(prices, slow_period)

        # 计算MACD线
        macd_line = []
        for f, s in zip(fast_ema, slow_ema):
            if f is not None and s is not None:
                macd_line.append(f - s)
            else:
                macd_line.append(None)

        # 计算信号线（MACD的EMA）
        # 只对非None的MACD值计算EMA
        valid_macd = [v for v in macd_line if v is not None]
        if len(valid_macd) >= signal_period:
            signal_ema = self._calculate_ema(valid_macd, signal_period)

            # 将信号线映射回原始长度
            signal_line = [None] * len(macd_line)
            valid_idx = 0
            for i, v in enumerate(macd_line):
                if v is not None:
                    signal_line[i] = signal_ema[valid_idx]
                    valid_idx += 1
        else:
            signal_line = [None] * len(macd_line)

        # 计算柱状图
        histogram = []
        for m, s in zip(macd_line, signal_line):
            if m is not None and s is not None:
                histogram.append(m - s)
            else:
                histogram.append(None)

        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }

    def get_klines(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: int
    ) -> List[dict]:
        """
        获取指定时间范围的K线数据

        Args:
            symbol: 交易对，如 "ETHUSDT"
            interval: K线周期，如 "4h", "1d"
            start_time: 开始时间戳（毫秒）
            end_time: 结束时间戳（毫秒）

        Returns:
            K线数据列表，每个元素格式:
            {
                't': int,    # 时间戳（毫秒）
                'o': float,  # 开盘价
                'h': float,  # 最高价
                'l': float,  # 最低价
                'c': float,  # 收盘价
                'v': float   # 成交量
            }

        Raises:
            requests.RequestException: 网络请求失败
            ValueError: 参数无效
        """
        if not symbol or not interval:
            raise ValueError("symbol和interval参数不能为空")

        if start_time >= end_time:
            raise ValueError("start_time必须小于end_time")

        all_klines = []
        current_start = start_time

        # 分页获取（单次最多1000条）
        while current_start < end_time:
            batch = self._fetch_klines_batch(
                symbol=symbol,
                interval=interval,
                start_time=current_start,
                end_time=end_time,
                limit=self.MAX_LIMIT
            )

            if not batch:
                break

            all_klines.extend(batch)

            # 更新下一批次的开始时间（最后一条K线的开盘时间 + 1ms）
            last_kline_time = batch[-1]['t']
            current_start = last_kline_time + 1

            # 防止无限循环
            if len(batch) < self.MAX_LIMIT:
                break

        logger.info(
            f"获取K线数据完成: symbol={symbol}, interval={interval}, "
            f"count={len(all_klines)}"
        )

        return all_klines

    def _fetch_klines_batch(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: int,
        limit: int
    ) -> List[dict]:
        """
        获取单批次K线数据

        Args:
            symbol: 交易对
            interval: K线周期
            start_time: 开始时间戳（毫秒）
            end_time: 结束时间戳（毫秒）
            limit: 请求数量限制

        Returns:
            标准化的K线数据列表
        """
        params = {
            'symbol': symbol,
            'interval': interval,
            'startTime': start_time,
            'endTime': end_time,
            'limit': limit
        }

        try:
            response = requests.get(
                self.BASE_URL,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()

            raw_klines = response.json()
            return [self._format_kline(k) for k in raw_klines]

        except requests.Timeout:
            logger.error(f"K线API请求超时: symbol={symbol}, interval={interval}")
            raise

        except requests.RequestException as e:
            logger.error(f"K线API请求失败: {e}")
            raise

    def _format_kline(self, raw_kline: list) -> dict:
        """
        将币安原始K线数据转换为标准格式

        币安K线响应格式（数组）:
        [
            0: 开盘时间 (毫秒时间戳)
            1: 开盘价 (string)
            2: 最高价 (string)
            3: 最低价 (string)
            4: 收盘价 (string)
            5: 成交量 (string)
            6: 收盘时间
            7: 成交额
            8: 成交笔数
            9: 主动买入成交量
            10: 主动买入成交额
            11: 忽略
        ]

        Args:
            raw_kline: 币安原始K线数据（列表格式）

        Returns:
            标准化K线数据:
            {
                't': int,    # 时间戳（毫秒）
                'o': float,  # 开盘价
                'h': float,  # 最高价
                'l': float,  # 最低价
                'c': float,  # 收盘价
                'v': float   # 成交量
            }
        """
        return {
            't': int(raw_kline[0]),      # 开盘时间（毫秒）
            'o': float(raw_kline[1]),    # 开盘价
            'h': float(raw_kline[2]),    # 最高价
            'l': float(raw_kline[3]),    # 最低价
            'c': float(raw_kline[4]),    # 收盘价
            'v': float(raw_kline[5])     # 成交量
        }
