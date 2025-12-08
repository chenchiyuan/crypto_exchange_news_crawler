"""
GRVT交易所适配器
GRVT Exchange Adapter

基于官方 grvt-pysdk 实现
"""
import os
import logging
import asyncio
from typing import Optional
from decimal import Decimal

from pysdk.grvt_ccxt_pro import GrvtCcxtPro
from pysdk.grvt_ccxt_env import GrvtEnv
from pysdk.grvt_ccxt_types import GrvtOrderSide, GrvtOrderType

from .adapter import (
    ExchangeAdapter,
    AccountListener,
    OrderListener,
    DepthListener,
    TickerListener,
    KlineListener,
)
from .types import (
    CreateOrderParams,
    ExchangeOrder,
    AccountSnapshot,
    OrderBookDepth,
    Ticker,
    Kline,
    ExchangePrecision,
)

logger = logging.getLogger(__name__)


class GRVTCredentials:
    """GRVT认证凭据"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        private_key: Optional[str] = None,
        trading_account_id: Optional[str] = None,
        env: str = "testnet",
    ):
        """
        初始化GRVT凭据

        Args:
            api_key: API密钥
            private_key: 私钥（用于签名订单）
            trading_account_id: 交易账户ID
            env: 环境 (testnet/prod)
        """
        self.api_key = api_key or os.getenv("GRVT_API_KEY")
        self.private_key = private_key or os.getenv("GRVT_PRIVATE_KEY")
        self.trading_account_id = trading_account_id or os.getenv("GRVT_TRADING_ACCOUNT_ID")
        self.env = env or os.getenv("GRVT_ENV", "testnet")

        self._validate()

    def _validate(self):
        """验证必填参数"""
        if not self.api_key:
            raise ValueError("Missing GRVT_API_KEY for authentication")

        if not self.private_key:
            raise ValueError("Missing GRVT_PRIVATE_KEY for order signing")

        if not self.trading_account_id:
            raise ValueError("Missing GRVT_TRADING_ACCOUNT_ID")

    def get_env(self) -> GrvtEnv:
        """获取GRVT环境枚举"""
        env_map = {
            "testnet": GrvtEnv.TESTNET,
            "prod": GrvtEnv.PROD,
            "production": GrvtEnv.PROD,
            "dev": GrvtEnv.DEV,
            "staging": GrvtEnv.STAGING,
        }
        return env_map.get(self.env.lower(), GrvtEnv.TESTNET)


class GRVTExchangeAdapter(ExchangeAdapter):
    """GRVT交易所适配器

    基于官方 grvt-pysdk 实现
    文档: https://api-docs.grvt.io/
    """

    def __init__(self, credentials: Optional[GRVTCredentials] = None):
        """初始化GRVT适配器

        Args:
            credentials: 认证凭据，如果为None则从环境变量读取
        """
        self.credentials = credentials or GRVTCredentials()
        self._initialized = False
        self._client: Optional[GrvtCcxtPro] = None

        # 回调监听器
        self._account_callback: Optional[AccountListener] = None
        self._orders_callback: Optional[OrderListener] = None
        self._depth_callback: Optional[DepthListener] = None
        self._ticker_callback: Optional[TickerListener] = None
        self._kline_callback: Optional[KlineListener] = None

        # 市场信息缓存
        self._markets = {}
        self._instruments = {}

        logger.info(
            f"初始化GRVT适配器: env={self.credentials.env}, "
            f"trading_account_id={self.credentials.trading_account_id}"
        )

    @property
    def id(self) -> str:
        return "grvt"

    def supports_trailing_stops(self) -> bool:
        return False

    async def _ensure_initialized(self):
        """确保SDK客户端已初始化"""
        if self._initialized and self._client:
            return

        logger.info("初始化GRVT SDK客户端...")

        try:
            # 创建GRVT CCXT Pro客户端
            parameters = {
                "trading_account_id": self.credentials.trading_account_id,
                "private_key": self.credentials.private_key,
                "api_key": self.credentials.api_key,
            }

            self._client = GrvtCcxtPro(
                env=self.credentials.get_env(),
                parameters=parameters,
                logger=logger
            )

            # 加载市场信息
            await self._load_markets()

            self._initialized = True
            logger.info("GRVT SDK客户端初始化完成")

        except Exception as e:
            logger.error(f"GRVT SDK初始化失败: {e}", exc_info=True)
            raise

    async def _load_markets(self):
        """加载市场信息"""
        if not self._client:
            return

        try:
            self._markets = await self._client.fetch_markets()
            logger.info(f"加载了 {len(self._markets)} 个交易对信息")
        except Exception as e:
            logger.error(f"加载市场信息失败: {e}", exc_info=True)

    def watch_account(self, callback: AccountListener) -> None:
        """监听账户变化"""
        self._account_callback = self._safe_invoke("watch_account", callback)
        logger.info("注册账户变化监听器")
        # TODO: 实现WebSocket订阅

    def watch_orders(self, callback: OrderListener) -> None:
        """监听订单变化"""
        self._orders_callback = self._safe_invoke("watch_orders", callback)
        logger.info("注册订单变化监听器")
        # TODO: 实现WebSocket订阅

    def watch_depth(self, symbol: str, callback: DepthListener) -> None:
        """监听订单簿深度"""
        self._depth_callback = self._safe_invoke("watch_depth", callback)
        logger.info(f"注册订单簿深度监听器: {symbol}")
        # TODO: 实现WebSocket订阅

    def watch_ticker(self, symbol: str, callback: TickerListener) -> None:
        """监听ticker行情"""
        self._ticker_callback = self._safe_invoke("watch_ticker", callback)
        logger.info(f"注册ticker监听器: {symbol}")
        # TODO: 实现WebSocket订阅

    def watch_klines(self, symbol: str, interval: str, callback: KlineListener) -> None:
        """监听K线数据"""
        self._kline_callback = self._safe_invoke("watch_klines", callback)
        logger.info(f"注册K线监听器: {symbol} {interval}")
        # TODO: 实现WebSocket订阅

    async def create_order(self, params: CreateOrderParams) -> ExchangeOrder:
        """创建订单

        Args:
            params: 订单参数

        Returns:
            创建的订单信息
        """
        await self._ensure_initialized()

        if not self._client:
            raise RuntimeError("GRVT client not initialized")

        symbol = params["symbol"]
        side = params["side"]
        order_type = params["type"]
        amount = float(params.get("quantity", 0))
        price = float(params.get("price")) if params.get("price") else None

        logger.info(
            f"创建订单: {symbol} {side} {order_type} "
            f"amount={amount} price={price}"
        )

        try:
            # 使用SDK的create_order方法
            result = await self._client.create_order(
                symbol=symbol,
                type=order_type.lower(),  # 'limit' or 'market'
                side=side.lower(),  # 'buy' or 'sell'
                amount=amount,
                price=price,
                params={
                    "client_order_id": params.get("client_order_id"),
                    "time_in_force": params.get("time_in_force", "GTC"),
                    "reduce_only": params.get("reduce_only", False),
                }
            )

            # 转换为标准格式
            order: ExchangeOrder = {
                "order_id": result.get("id", ""),
                "client_order_id": result.get("clientOrderId"),
                "symbol": result.get("symbol", symbol),
                "side": side,
                "type": order_type,
                "status": result.get("status", "NEW"),
                "quantity": str(result.get("amount", amount)),
                "price": str(result.get("price", price or 0)),
                "executed_qty": str(result.get("filled", 0)),
                "avg_price": str(result.get("average", 0)),
                "time_in_force": params.get("time_in_force", "GTC"),
                "reduce_only": params.get("reduce_only", False),
                "close_position": params.get("close_position", False),
                "create_time": result.get("timestamp", 0),
                "update_time": result.get("lastTradeTimestamp", 0),
            }

            logger.info(f"订单创建成功: order_id={order['order_id']}")
            return order

        except Exception as e:
            logger.error(f"创建订单失败: {e}", exc_info=True)
            raise

    async def cancel_order(self, symbol: str, order_id: str) -> None:
        """撤销订单"""
        await self._ensure_initialized()

        if not self._client:
            raise RuntimeError("GRVT client not initialized")

        logger.info(f"撤销订单: {symbol} order_id={order_id}")

        try:
            await self._client.cancel_order(order_id, symbol)
            logger.info(f"订单撤销成功: order_id={order_id}")
        except Exception as e:
            logger.error(f"撤销订单失败: {e}", exc_info=True)
            raise

    async def cancel_orders(self, symbol: str, order_ids: list[str]) -> None:
        """批量撤销订单"""
        await self._ensure_initialized()

        logger.info(f"批量撤销订单: {symbol} count={len(order_ids)}")

        # 并发撤销所有订单
        tasks = [self.cancel_order(symbol, order_id) for order_id in order_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def cancel_all_orders(self, symbol: str) -> None:
        """撤销所有订单"""
        await self._ensure_initialized()

        if not self._client:
            raise RuntimeError("GRVT client not initialized")

        logger.info(f"撤销所有订单: {symbol}")

        try:
            # 获取所有未成交订单
            open_orders = await self._client.fetch_open_orders(symbol)
            order_ids = [order["id"] for order in open_orders]

            if order_ids:
                await self.cancel_orders(symbol, order_ids)

            logger.info(f"撤销了 {len(order_ids)} 个订单")
        except Exception as e:
            logger.error(f"撤销所有订单失败: {e}", exc_info=True)
            raise

    async def get_precision(self, symbol: str) -> Optional[ExchangePrecision]:
        """获取交易对精度信息"""
        await self._ensure_initialized()

        if not self._markets:
            return None

        # 从市场信息中获取精度
        market = self._markets.get(symbol)
        if not market:
            logger.warning(f"未找到交易对信息: {symbol}")
            return None

        precision = market.get("precision", {})
        limits = market.get("limits", {})

        return {
            "price_tick": Decimal(str(precision.get("price", 0.01))),
            "qty_step": Decimal(str(precision.get("amount", 0.001))),
            "price_decimals": precision.get("price", 2),
            "size_decimals": precision.get("amount", 3),
            "min_notional": Decimal(str(limits.get("cost", {}).get("min", 10))),
            "min_qty": Decimal(str(limits.get("amount", {}).get("min", 0.001))),
        }

    async def get_balance(self) -> dict:
        """获取账户余额"""
        await self._ensure_initialized()

        if not self._client:
            raise RuntimeError("GRVT client not initialized")

        try:
            balance = await self._client.fetch_balance()
            return balance
        except Exception as e:
            logger.error(f"获取余额失败: {e}", exc_info=True)
            raise

    def _safe_invoke(self, context: str, callback):
        """安全调用回调函数，捕获异常"""

        def wrapped(*args, **kwargs):
            try:
                return callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"[GRVTAdapter] {context} callback failed: {e}", exc_info=True)

        return wrapped

    async def close(self):
        """关闭连接"""
        if self._client:
            # SDK会在__del__中自动关闭session
            logger.info("关闭GRVT适配器")
            self._client = None
            self._initialized = False
