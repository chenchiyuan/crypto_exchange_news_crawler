"""
数据源模块

提供K线数据的获取和存储服务。

Related:
    - Architecture: docs/iterations/024-ddps-multi-market-support/architecture.md
    - Architecture: docs/iterations/025-csv-datasource/architecture.md
"""

from ddps_z.datasources.base import KLineFetcher, FetchError
from ddps_z.datasources.binance_fetcher import BinanceFetcher
from ddps_z.datasources.csv_fetcher import CSVFetcher
from ddps_z.datasources.csv_parser import CSVParser
from ddps_z.datasources.fetcher_factory import FetcherFactory
from ddps_z.datasources.repository import KLineRepository

__all__ = [
    'KLineFetcher',
    'FetchError',
    'BinanceFetcher',
    'CSVFetcher',
    'CSVParser',
    'FetcherFactory',
    'KLineRepository',
]
