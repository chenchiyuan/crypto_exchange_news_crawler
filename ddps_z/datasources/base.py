"""
K线数据获取器抽象接口

定义所有数据源Fetcher必须实现的接口。

Related:
    - Architecture: docs/iterations/024-ddps-multi-market-support/architecture.md
    - TASK: TASK-024-003
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from ddps_z.models import StandardKLine


class KLineFetcher(ABC):
    """
    K线数据获取器抽象基类

    所有具体的数据源实现都必须继承此类并实现fetch方法。
    Fetcher负责从外部API获取数据并转换为StandardKLine格式。

    Attributes:
        market_type: 市场类型标识

    Example:
        >>> class MyFetcher(KLineFetcher):
        ...     @property
        ...     def market_type(self) -> str:
        ...         return 'my_market'
        ...
        ...     def fetch(self, symbol, interval, limit):
        ...         # 实现获取逻辑
        ...         pass
    """

    @property
    @abstractmethod
    def market_type(self) -> str:
        """
        返回此Fetcher支持的市场类型

        Returns:
            市场类型字符串，如 'crypto_spot', 'crypto_futures'
        """
        pass

    @abstractmethod
    def fetch(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[StandardKLine]:
        """
        从外部API获取K线数据

        Args:
            symbol: 交易对，如 'BTCUSDT'
            interval: K线周期，如 '4h', '1d'
            limit: 获取数量，默认500
            start_time: 起始时间戳（毫秒），可选
            end_time: 结束时间戳（毫秒），可选

        Returns:
            标准K线列表，按时间正序排列

        Raises:
            FetchError: 获取数据失败时抛出
        """
        pass

    def supports_symbol(self, symbol: str) -> bool:
        """
        检查是否支持指定交易对

        默认实现返回True，子类可覆盖以添加验证逻辑。

        Args:
            symbol: 交易对

        Returns:
            是否支持
        """
        return True

    def supports_interval(self, interval: str) -> bool:
        """
        检查是否支持指定周期

        默认实现返回True，子类可覆盖以添加验证逻辑。

        Args:
            interval: K线周期

        Returns:
            是否支持
        """
        return True


class FetchError(Exception):
    """
    数据获取异常

    当Fetcher无法从外部API获取数据时抛出。

    Attributes:
        message: 错误信息
        symbol: 相关交易对
        interval: 相关周期
        cause: 原始异常
    """

    def __init__(
        self,
        message: str,
        symbol: Optional[str] = None,
        interval: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        self.message = message
        self.symbol = symbol
        self.interval = interval
        self.cause = cause
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """格式化错误信息"""
        parts = [self.message]
        if self.symbol:
            parts.append(f"symbol={self.symbol}")
        if self.interval:
            parts.append(f"interval={self.interval}")
        if self.cause:
            parts.append(f"cause={self.cause}")
        return " | ".join(parts)
