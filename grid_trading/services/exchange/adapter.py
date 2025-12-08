"""
交易所适配器抽象基类
Exchange Adapter Abstract Base Class
"""
from abc import ABC, abstractmethod
from typing import Callable, Optional
import logging

from .types import (
    CreateOrderParams,
    ExchangeOrder,
    AccountSnapshot,
    OrderBookDepth,
    Ticker,
    Kline,
    ExchangePrecision
)

logger = logging.getLogger(__name__)


# 回调函数类型定义
AccountListener = Callable[[AccountSnapshot], None]
OrderListener = Callable[[list[ExchangeOrder]], None]
DepthListener = Callable[[OrderBookDepth], None]
TickerListener = Callable[[Ticker], None]
KlineListener = Callable[[list[Kline]], None]


class ExchangeAdapter(ABC):
    """交易所适配器抽象基类

    定义了与交易所交互的标准接口，所有具体的交易所适配器都必须实现这些方法。
    """

    @property
    @abstractmethod
    def id(self) -> str:
        """交易所标识符"""
        pass

    @abstractmethod
    def supports_trailing_stops(self) -> bool:
        """是否支持追踪止损"""
        pass

    @abstractmethod
    def watch_account(self, callback: AccountListener) -> None:
        """监听账户变化

        Args:
            callback: 账户变化回调函数
        """
        pass

    @abstractmethod
    def watch_orders(self, callback: OrderListener) -> None:
        """监听订单变化

        Args:
            callback: 订单变化回调函数
        """
        pass

    @abstractmethod
    def watch_depth(self, symbol: str, callback: DepthListener) -> None:
        """监听订单簿深度

        Args:
            symbol: 交易对
            callback: 深度变化回调函数
        """
        pass

    @abstractmethod
    def watch_ticker(self, symbol: str, callback: TickerListener) -> None:
        """监听ticker行情

        Args:
            symbol: 交易对
            callback: ticker变化回调函数
        """
        pass

    @abstractmethod
    def watch_klines(self, symbol: str, interval: str, callback: KlineListener) -> None:
        """监听K线数据

        Args:
            symbol: 交易对
            interval: K线周期 (1m, 5m, 15m, 1h, 4h, 1d等)
            callback: K线更新回调函数
        """
        pass

    @abstractmethod
    async def create_order(self, params: CreateOrderParams) -> ExchangeOrder:
        """创建订单

        Args:
            params: 订单参数

        Returns:
            创建的订单信息

        Raises:
            Exception: 订单创建失败
        """
        pass

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> None:
        """撤销单个订单

        Args:
            symbol: 交易对
            order_id: 订单ID

        Raises:
            Exception: 订单撤销失败
        """
        pass

    @abstractmethod
    async def cancel_orders(self, symbol: str, order_ids: list[str]) -> None:
        """批量撤销订单

        Args:
            symbol: 交易对
            order_ids: 订单ID列表

        Raises:
            Exception: 订单撤销失败
        """
        pass

    @abstractmethod
    async def cancel_all_orders(self, symbol: str) -> None:
        """撤销指定交易对的所有订单

        Args:
            symbol: 交易对

        Raises:
            Exception: 订单撤销失败
        """
        pass

    async def get_precision(self, symbol: str) -> Optional[ExchangePrecision]:
        """获取交易对精度信息

        Args:
            symbol: 交易对

        Returns:
            精度信息，如果不支持则返回None
        """
        return None

    async def get_balance(self) -> dict:
        """获取账户余额

        Returns:
            账户余额信息
        """
        raise NotImplementedError("get_balance not implemented")

    async def get_positions(self) -> list[dict]:
        """获取当前持仓

        Returns:
            持仓列表
        """
        raise NotImplementedError("get_positions not implemented")

    async def get_orders(self, symbol: str, limit: int = 100) -> list[ExchangeOrder]:
        """获取当前活跃订单

        Args:
            symbol: 交易对
            limit: 返回数量限制

        Returns:
            订单列表
        """
        raise NotImplementedError("get_orders not implemented")
