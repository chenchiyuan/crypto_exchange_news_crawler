"""
DDPS配置解析器

解析DDPS监控服务的配置，支持多市场多周期。

Related:
    - Architecture: docs/iterations/024-ddps-multi-market-support/architecture.md
    - TASK: TASK-024-009
"""

import logging
from typing import List, Optional

from django.conf import settings

from ddps_z.models import MarketType, Interval

logger = logging.getLogger(__name__)


class DDPSConfigParser:
    """
    DDPS配置解析器

    解析DDPS_MONITOR_CONFIG配置，提供多市场多周期支持。

    配置格式（新版）:
        DDPS_MONITOR_CONFIG = {
            'default_market': 'crypto_futures',
            'default_interval': '4h',
            'markets': {
                'crypto_futures': {
                    'symbols': ['ETHUSDT', 'BTCUSDT'],
                    'interval': '4h',
                },
                'crypto_spot': {
                    'symbols': ['ETHUSDT', 'BTCUSDT'],
                    'interval': '4h',
                },
            },
            'push_channel': 'price_ddps',
            'push_token': '...',
        }

    配置格式（旧版，向后兼容）:
        DDPS_MONITOR_CONFIG = {
            'default_symbols': ['ETHUSDT', 'BTCUSDT'],
            'interval': '4h',
            'market_type': 'futures',
            'push_channel': 'price_ddps',
            'push_token': '...',
        }

    Example:
        >>> parser = DDPSConfigParser()
        >>> symbols = parser.get_symbols('crypto_futures')
        >>> interval = parser.get_interval()
    """

    def __init__(self, config: Optional[dict] = None):
        """
        初始化配置解析器

        Args:
            config: 配置字典，默认从settings.DDPS_MONITOR_CONFIG读取
        """
        self._config = config or getattr(settings, 'DDPS_MONITOR_CONFIG', {})
        self._is_new_format = 'markets' in self._config

    def get_default_market(self) -> str:
        """
        获取默认市场类型

        Returns:
            默认市场类型
        """
        if self._is_new_format:
            return self._config.get('default_market', MarketType.CRYPTO_FUTURES.value)

        # 旧格式兼容
        old_market = self._config.get('market_type', 'futures')
        return MarketType.normalize(old_market)

    def get_default_interval(self) -> str:
        """
        获取默认K线周期

        Returns:
            默认K线周期
        """
        if self._is_new_format:
            return self._config.get('default_interval', '4h')

        # 旧格式兼容
        return self._config.get('interval', '4h')

    def get_symbols(self, market_type: Optional[str] = None) -> List[str]:
        """
        获取指定市场的交易对列表

        Args:
            market_type: 市场类型，默认使用default_market

        Returns:
            交易对列表
        """
        market = market_type or self.get_default_market()
        market = MarketType.normalize(market)

        if self._is_new_format:
            markets_config = self._config.get('markets', {})
            market_config = markets_config.get(market, {})
            return market_config.get('symbols', [])

        # 旧格式兼容
        return self._config.get('default_symbols', [])

    def get_interval(self, market_type: Optional[str] = None) -> str:
        """
        获取指定市场的K线周期

        Args:
            market_type: 市场类型，默认使用default_market

        Returns:
            K线周期
        """
        market = market_type or self.get_default_market()
        market = MarketType.normalize(market)

        if self._is_new_format:
            markets_config = self._config.get('markets', {})
            market_config = markets_config.get(market, {})
            return market_config.get('interval', self.get_default_interval())

        # 旧格式兼容
        return self._config.get('interval', '4h')

    def get_interval_hours(self, interval: Optional[str] = None) -> float:
        """
        获取K线周期小时数

        Args:
            interval: K线周期字符串，默认使用配置的周期

        Returns:
            小时数
        """
        interval = interval or self.get_default_interval()
        return Interval.to_hours(interval)

    def get_market_config(self, market_type: str) -> dict:
        """
        获取指定市场的完整配置

        Args:
            market_type: 市场类型

        Returns:
            市场配置字典
        """
        market = MarketType.normalize(market_type)

        if self._is_new_format:
            markets_config = self._config.get('markets', {})
            return markets_config.get(market, {})

        # 旧格式兼容：构造伪配置
        return {
            'symbols': self._config.get('default_symbols', []),
            'interval': self._config.get('interval', '4h'),
        }

    def get_all_markets(self) -> List[str]:
        """
        获取所有配置的市场类型

        Returns:
            市场类型列表
        """
        if self._is_new_format:
            return list(self._config.get('markets', {}).keys())

        # 旧格式兼容：只有一个市场
        old_market = self._config.get('market_type', 'futures')
        return [MarketType.normalize(old_market)]

    def get_push_channel(self) -> str:
        """
        获取推送渠道

        Returns:
            推送渠道名称
        """
        return self._config.get('push_channel', 'price_ddps')

    def get_push_token(self) -> str:
        """
        获取推送令牌

        Returns:
            推送令牌
        """
        return self._config.get('push_token', '')

    def is_market_supported(self, market_type: str) -> bool:
        """
        检查是否支持指定市场

        Args:
            market_type: 市场类型

        Returns:
            是否支持
        """
        market = MarketType.normalize(market_type)
        return market in self.get_all_markets()

    @property
    def is_new_format(self) -> bool:
        """是否为新配置格式"""
        return self._is_new_format
