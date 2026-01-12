"""
Binance K线数据获取器

实现从Binance API获取K线数据的Fetcher。

Related:
    - Architecture: docs/iterations/024-ddps-multi-market-support/architecture.md
    - TASK: TASK-024-004
"""

import logging
from typing import List, Optional

import requests

from ddps_z.models import StandardKLine, MarketType
from ddps_z.datasources.base import KLineFetcher, FetchError

logger = logging.getLogger(__name__)

# Binance API配置
BINANCE_SPOT_BASE_URL = 'https://api.binance.com'
BINANCE_SPOT_KLINES_ENDPOINT = '/api/v3/klines'
BINANCE_FUTURES_BASE_URL = 'https://fapi.binance.com'
BINANCE_FUTURES_KLINES_ENDPOINT = '/fapi/v1/klines'
BINANCE_REQUEST_TIMEOUT = 30

# 有效的时间周期
VALID_INTERVALS = [
    '1m', '3m', '5m', '15m', '30m',
    '1h', '2h', '4h', '6h', '8h', '12h',
    '1d', '3d', '1w', '1M'
]


class BinanceFetcher(KLineFetcher):
    """
    Binance K线数据获取器

    支持从Binance现货和合约市场获取K线数据。

    Attributes:
        _market_type: 市场类型（crypto_spot或crypto_futures）

    Example:
        >>> fetcher = BinanceFetcher(market_type='crypto_futures')
        >>> klines = fetcher.fetch('BTCUSDT', '4h', limit=100)
        >>> len(klines)
        100
    """

    def __init__(self, market_type: str = 'crypto_futures'):
        """
        初始化Binance Fetcher

        Args:
            market_type: 市场类型，支持 'crypto_spot', 'crypto_futures',
                        以及旧格式 'spot', 'futures'
        """
        # 标准化market_type
        self._market_type = MarketType.normalize(market_type)

        if self._market_type == MarketType.CRYPTO_SPOT.value:
            self._base_url = BINANCE_SPOT_BASE_URL
            self._endpoint = BINANCE_SPOT_KLINES_ENDPOINT
        elif self._market_type == MarketType.CRYPTO_FUTURES.value:
            self._base_url = BINANCE_FUTURES_BASE_URL
            self._endpoint = BINANCE_FUTURES_KLINES_ENDPOINT
        else:
            raise ValueError(
                f"BinanceFetcher不支持市场类型: {market_type}. "
                f"仅支持 'crypto_spot' 或 'crypto_futures'"
            )

    @property
    def market_type(self) -> str:
        """返回此Fetcher支持的市场类型"""
        return self._market_type

    def fetch(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[StandardKLine]:
        """
        从Binance API获取K线数据

        Args:
            symbol: 交易对，如 'BTCUSDT'
            interval: K线周期，如 '4h', '1d'
            limit: 获取数量，默认500，最大1500
            start_time: 起始时间戳（毫秒），可选
            end_time: 结束时间戳（毫秒），可选

        Returns:
            标准K线列表，按时间正序排列

        Raises:
            FetchError: 获取数据失败时抛出
        """
        # 验证参数
        if not self.supports_interval(interval):
            raise FetchError(
                f"不支持的K线周期: {interval}",
                symbol=symbol,
                interval=interval
            )

        # 限制范围
        limit = max(1, min(limit, 1500))

        # 构建请求
        url = f"{self._base_url}{self._endpoint}"
        params = {
            'symbol': symbol.upper(),
            'interval': interval,
            'limit': limit
        }

        if start_time is not None:
            params['startTime'] = start_time
        if end_time is not None:
            params['endTime'] = end_time

        logger.debug(
            f"Binance API请求: {symbol} {interval} limit={limit} "
            f"market={self._market_type}"
        )

        try:
            response = requests.get(
                url,
                params=params,
                timeout=BINANCE_REQUEST_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()

        except requests.exceptions.Timeout:
            raise FetchError(
                "请求超时",
                symbol=symbol,
                interval=interval
            )
        except requests.exceptions.HTTPError as e:
            raise FetchError(
                f"HTTP错误: {e}",
                symbol=symbol,
                interval=interval,
                cause=e
            )
        except requests.exceptions.RequestException as e:
            raise FetchError(
                f"请求失败: {e}",
                symbol=symbol,
                interval=interval,
                cause=e
            )
        except ValueError as e:
            raise FetchError(
                f"JSON解析失败: {e}",
                symbol=symbol,
                interval=interval,
                cause=e
            )

        # 转换为StandardKLine
        klines = [self._parse_kline(item) for item in data]

        logger.debug(f"获取到 {len(klines)} 根K线: {symbol} {interval}")

        return klines

    def _parse_kline(self, data: list) -> StandardKLine:
        """
        解析Binance K线响应

        Binance K线数据格式:
        [
            0: 开盘时间 (timestamp ms),
            1: 开盘价 (string),
            2: 最高价 (string),
            3: 最低价 (string),
            4: 收盘价 (string),
            5: 成交量 (string),
            6: 收盘时间 (timestamp ms),
            7: 成交额 (string),
            8: 成交笔数 (int),
            9: 主动买入成交量 (string),
            10: 主动买入成交额 (string),
            11: 忽略
        ]

        Args:
            data: Binance API返回的K线数组

        Returns:
            StandardKLine实例
        """
        return StandardKLine(
            timestamp=int(data[0]),
            open=float(data[1]),
            high=float(data[2]),
            low=float(data[3]),
            close=float(data[4]),
            volume=float(data[5])
        )

    def supports_interval(self, interval: str) -> bool:
        """检查是否支持指定周期"""
        return interval in VALID_INTERVALS
