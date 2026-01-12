"""
CSV文件K线数据获取器

实现KLineFetcher接口，从本地CSV文件加载K线数据。

Related:
    - Architecture: docs/iterations/025-csv-datasource/architecture.md
    - TASK: TASK-025-005, TASK-025-006, TASK-025-008
"""

import bisect
import logging
from typing import List, Optional

from ddps_z.datasources.base import KLineFetcher
from ddps_z.datasources.csv_parser import CSVParser
from ddps_z.models import StandardKLine

logger = logging.getLogger(__name__)


class CSVFetcher(KLineFetcher):
    """
    CSV文件K线数据获取器

    实现KLineFetcher接口，从本地CSV文件加载K线数据。
    采用实例级缓存，首次调用时全量加载到内存。

    Attributes:
        SUPPORTED_INTERVALS: 支持的K线周期列表

    Example:
        >>> fetcher = CSVFetcher(
        ...     csv_path='/path/to/ETHUSDT-1s-2025-12.csv',
        ...     interval='1s'
        ... )
        >>> klines = fetcher.fetch('ETHUSDT', '1s', limit=1000)
        >>> len(klines)
        1000
    """

    # 支持所有常见K线周期，CSV文件解析与interval无关
    SUPPORTED_INTERVALS = ['1s', '1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M']

    def __init__(
        self,
        csv_path: str,
        interval: str = '1s',
        market_type: str = 'csv_local',
        timestamp_unit: str = 'microseconds'
    ):
        """
        初始化CSVFetcher

        Args:
            csv_path: CSV文件绝对路径（必填）
            interval: K线周期，支持常见周期如 '1s', '1m', '5m', '1h', '4h' 等（默认'1s'）
            market_type: 市场类型标识（默认'csv_local'）
            timestamp_unit: 时间戳单位（默认'microseconds'）

        Raises:
            ValueError: 不支持的interval
        """
        if interval not in self.SUPPORTED_INTERVALS:
            raise ValueError(
                f"不支持的K线周期: {interval}，支持: {self.SUPPORTED_INTERVALS}"
            )

        self._csv_path = csv_path
        self._interval = interval
        self._market_type = market_type
        self._timestamp_unit = timestamp_unit
        self._cache: Optional[List[StandardKLine]] = None
        self._timestamps: Optional[List[int]] = None  # 用于二分查找
        self._parser = CSVParser(timestamp_unit=timestamp_unit)

    @property
    def market_type(self) -> str:
        """返回 'csv_local'"""
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
        从CSV加载K线数据

        首次调用时会触发CSV文件加载，后续调用使用缓存。
        支持时间范围过滤和limit限制。

        Args:
            symbol: 交易对（CSV场景下仅用于日志）
            interval: K线周期
            limit: 返回数量限制，默认500
            start_time: 起始时间戳（毫秒），可选
            end_time: 结束时间戳（毫秒），可选

        Returns:
            List[StandardKLine]: 时间正序排列的K线列表
        """
        # 1. 懒加载：首次调用时加载CSV
        if self._cache is None:
            logger.info(f"首次加载CSV: {self._csv_path}")
            self._cache = self._parser.parse(self._csv_path)
            # 预计算时间戳列表用于二分查找
            self._timestamps = [k.timestamp for k in self._cache]
            logger.info(f"加载完成，共 {len(self._cache)} 根K线")

        # 2. 时间范围过滤（使用二分查找优化）
        result = self._filter_by_time(start_time, end_time)

        # 3. 应用limit（取最后limit根）
        if limit and len(result) > limit:
            result = result[-limit:]

        return result

    def _filter_by_time(
        self,
        start_time: Optional[int],
        end_time: Optional[int]
    ) -> List[StandardKLine]:
        """
        使用二分查找优化时间过滤

        Args:
            start_time: 起始时间戳（毫秒）
            end_time: 结束时间戳（毫秒）

        Returns:
            过滤后的K线列表
        """
        if start_time is None and end_time is None:
            return self._cache.copy()

        # 二分查找起始位置
        start_idx = 0
        if start_time is not None:
            start_idx = bisect.bisect_left(self._timestamps, start_time)

        # 二分查找结束位置
        end_idx = len(self._cache)
        if end_time is not None:
            end_idx = bisect.bisect_right(self._timestamps, end_time)

        return self._cache[start_idx:end_idx]

    def supports_interval(self, interval: str) -> bool:
        """检查是否支持指定周期，支持所有常见K线周期"""
        return interval in self.SUPPORTED_INTERVALS

    @property
    def csv_path(self) -> str:
        """返回CSV文件路径"""
        return self._csv_path

    @property
    def is_loaded(self) -> bool:
        """检查数据是否已加载"""
        return self._cache is not None

    @property
    def kline_count(self) -> int:
        """返回已加载的K线数量"""
        return len(self._cache) if self._cache else 0
