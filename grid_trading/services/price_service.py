"""
价格查询服务
Price Service

功能:
1. 获取币安现货当前价格
2. 简化价格查询接口
3. API异常重试机制
"""
import logging
import requests
import time
from decimal import Decimal
from typing import Optional

from vp_squeeze.services.binance_kline_service import normalize_symbol
from vp_squeeze.constants import (
    BINANCE_SPOT_BASE_URL,
    BINANCE_REQUEST_TIMEOUT,
)

logger = logging.getLogger(__name__)


class PriceService:
    """价格查询服务"""

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        """
        初始化价格服务

        Args:
            max_retries: 最大重试次数
            retry_delay: 重试延迟(秒)
        """
        self.base_url = BINANCE_SPOT_BASE_URL
        self.timeout = BINANCE_REQUEST_TIMEOUT
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def get_current_price(self, symbol: str) -> float:
        """
        获取当前市场价格

        Args:
            symbol: 交易对，如'btc'或'BTCUSDT'

        Returns:
            float: 当前价格

        Raises:
            Exception: API请求失败

        Example:
            >>> service = PriceService()
            >>> price = service.get_current_price('btc')
            >>> print(f"BTC价格: ${price:.2f}")
        """
        # 标准化交易对
        symbol_full = normalize_symbol(symbol)

        # 使用币安ticker/price API
        url = f"{self.base_url}/api/v3/ticker/price"
        params = {'symbol': symbol_full}

        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()

                data = response.json()
                price = float(data['price'])

                if attempt > 1:
                    logger.info(
                        f"获取价格成功(重试{attempt-1}次后): {symbol_full} = ${price:.2f}"
                    )
                else:
                    logger.info(f"获取价格成功: {symbol_full} = ${price:.2f}")

                return price

            except requests.exceptions.RequestException as e:
                last_error = e
                logger.warning(
                    f"获取价格失败(尝试{attempt}/{self.max_retries}): "
                    f"symbol={symbol_full}, error={e}"
                )

                if attempt < self.max_retries:
                    # 指数退避
                    delay = self.retry_delay * (2 ** (attempt - 1))
                    logger.info(f"等待{delay:.1f}秒后重试...")
                    time.sleep(delay)
                else:
                    logger.error(
                        f"获取价格失败(已达最大重试次数): "
                        f"symbol={symbol_full}, error={last_error}"
                    )

        raise Exception(f"获取价格失败(重试{self.max_retries}次后): {last_error}")

    def get_current_price_decimal(self, symbol: str) -> Decimal:
        """
        获取当前价格（Decimal格式）

        Args:
            symbol: 交易对

        Returns:
            Decimal: 当前价格
        """
        price = self.get_current_price(symbol)
        return Decimal(str(price))


# 全局单例
_price_service = None


def get_price_service() -> PriceService:
    """
    获取价格服务单例

    Returns:
        PriceService: 服务实例
    """
    global _price_service
    if _price_service is None:
        _price_service = PriceService()
    return _price_service


def get_current_price(symbol: str) -> float:
    """
    便捷函数：获取当前价格

    Args:
        symbol: 交易对

    Returns:
        float: 当前价格
    """
    service = get_price_service()
    return service.get_current_price(symbol)
