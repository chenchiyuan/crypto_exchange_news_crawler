"""
Fetcher工厂

根据市场类型创建对应的KLineFetcher实例。

Related:
    - Architecture: docs/iterations/024-ddps-multi-market-support/architecture.md
    - Architecture: docs/iterations/025-csv-datasource/architecture.md
    - TASK: TASK-024-005, TASK-025-009
"""

import logging
from typing import Dict, Type

from ddps_z.models import MarketType
from ddps_z.datasources.base import KLineFetcher
from ddps_z.datasources.binance_fetcher import BinanceFetcher
from ddps_z.datasources.csv_fetcher import CSVFetcher

logger = logging.getLogger(__name__)


class FetcherFactory:
    """
    Fetcher工厂类

    根据市场类型创建对应的KLineFetcher实例。
    支持注册自定义Fetcher以扩展新市场。

    Class Attributes:
        _registry: Fetcher注册表，映射market_type到Fetcher类

    Example:
        >>> fetcher = FetcherFactory.create('crypto_futures')
        >>> klines = fetcher.fetch('BTCUSDT', '4h')

        # 注册自定义Fetcher
        >>> FetcherFactory.register('us_stock', MyStockFetcher)
    """

    # 默认注册的Fetcher
    _registry: Dict[str, Type[KLineFetcher]] = {
        MarketType.CRYPTO_SPOT.value: BinanceFetcher,
        MarketType.CRYPTO_FUTURES.value: BinanceFetcher,
        'csv_local': CSVFetcher,  # CSV数据源
    }

    @classmethod
    def create(cls, market_type: str, **kwargs) -> KLineFetcher:
        """
        创建指定市场类型的Fetcher实例

        Args:
            market_type: 市场类型，支持新旧格式和csv_local
            **kwargs: 传递给Fetcher构造函数的参数
                - csv_local需要: csv_path, interval, timestamp_unit等

        Returns:
            对应的KLineFetcher实例

        Raises:
            ValueError: 不支持的市场类型

        Example:
            >>> # 创建BinanceFetcher
            >>> fetcher = FetcherFactory.create('crypto_futures')

            >>> # 创建CSVFetcher
            >>> fetcher = FetcherFactory.create(
            ...     'csv_local',
            ...     csv_path='/path/to/data.csv',
            ...     interval='1s'
            ... )
        """
        # csv_local特殊处理，不走标准化
        if market_type == 'csv_local':
            normalized = 'csv_local'
        else:
            # 标准化market_type（向后兼容）
            normalized = MarketType.normalize(market_type)

        fetcher_class = cls._registry.get(normalized)

        if fetcher_class is None:
            supported = list(cls._registry.keys())
            raise ValueError(
                f"不支持的市场类型: {market_type}. "
                f"支持的类型: {supported}"
            )

        logger.debug(f"创建Fetcher: {normalized} -> {fetcher_class.__name__}")

        # 根据类型决定构造方式
        if normalized == 'csv_local':
            # CSVFetcher需要kwargs参数
            return fetcher_class(**kwargs)
        else:
            # BinanceFetcher等使用market_type参数
            return fetcher_class(market_type=normalized)

    @classmethod
    def register(
        cls,
        market_type: str,
        fetcher_class: Type[KLineFetcher]
    ) -> None:
        """
        注册新的Fetcher类型

        Args:
            market_type: 市场类型
            fetcher_class: Fetcher类（必须继承KLineFetcher）

        Raises:
            TypeError: fetcher_class不是KLineFetcher的子类
        """
        if not issubclass(fetcher_class, KLineFetcher):
            raise TypeError(
                f"{fetcher_class.__name__} 必须继承 KLineFetcher"
            )

        cls._registry[market_type] = fetcher_class
        logger.info(f"注册Fetcher: {market_type} -> {fetcher_class.__name__}")

    @classmethod
    def unregister(cls, market_type: str) -> bool:
        """
        取消注册Fetcher类型

        Args:
            market_type: 市场类型

        Returns:
            是否成功取消注册
        """
        if market_type in cls._registry:
            del cls._registry[market_type]
            logger.info(f"取消注册Fetcher: {market_type}")
            return True
        return False

    @classmethod
    def supported_markets(cls) -> list:
        """
        获取所有支持的市场类型

        Returns:
            支持的市场类型列表
        """
        return list(cls._registry.keys())

    @classmethod
    def is_supported(cls, market_type: str) -> bool:
        """
        检查是否支持指定市场类型

        Args:
            market_type: 市场类型（支持旧格式）

        Returns:
            是否支持
        """
        normalized = MarketType.normalize(market_type)
        return normalized in cls._registry
