"""
GRVT市场数据订阅器
GRVT Market Data Subscriber

仅订阅市场数据，不执行交易
用于本地网格模拟测试
"""
import os
import logging
import asyncio
from typing import Optional, Callable
from decimal import Decimal
from datetime import datetime

from pysdk.grvt_ccxt_ws import GrvtCcxtWS
from pysdk.grvt_ccxt_env import GrvtEnv

logger = logging.getLogger(__name__)


class GRVTMarketDataSubscriber:
    """GRVT市场数据订阅器

    只订阅市场数据，不进行交易操作
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        env: str = "testnet",
    ):
        """
        初始化市场数据订阅器

        Args:
            api_key: API密钥（只需要API key，不需要私钥）
            env: 环境 (testnet/prod)
        """
        self.api_key = api_key or os.getenv("GRVT_API_KEY")
        self.env = env or os.getenv("GRVT_ENV", "testnet")

        if not self.api_key:
            raise ValueError("Missing GRVT_API_KEY")

        # 创建WebSocket客户端
        self._client: Optional[GrvtCcxtWS] = None
        self._initialized = False

        # 数据缓存
        self._ticker_data = {}
        self._orderbook_data = {}
        self._last_price = None

        # 回调函数
        self._price_callback: Optional[Callable] = None
        self._ticker_callback: Optional[Callable] = None
        self._orderbook_callback: Optional[Callable] = None

        logger.info(
            f"初始化GRVT市场数据订阅器: env={self.env}"
        )

    def _get_env(self) -> GrvtEnv:
        """获取GRVT环境枚举"""
        env_map = {
            "testnet": GrvtEnv.TESTNET,
            "prod": GrvtEnv.PROD,
            "production": GrvtEnv.PROD,
            "dev": GrvtEnv.DEV,
            "staging": GrvtEnv.STAGING,
        }
        return env_map.get(self.env.lower(), GrvtEnv.TESTNET)

    async def initialize(self):
        """初始化WebSocket连接"""
        if self._initialized:
            return

        logger.info("初始化GRVT WebSocket客户端...")

        try:
            # 创建WebSocket客户端（不需要私钥，只订阅公开数据）
            parameters = {
                "api_key": self.api_key,
            }

            # 获取当前事件循环
            loop = asyncio.get_event_loop()

            self._client = GrvtCcxtWS(
                env=self._get_env(),
                parameters=parameters,
                logger=logger,
                loop=loop
            )

            self._initialized = True
            logger.info("GRVT WebSocket客户端初始化完成")

        except Exception as e:
            logger.error(f"WebSocket初始化失败: {e}", exc_info=True)
            raise

    async def subscribe_ticker(self, symbol: str, callback: Optional[Callable] = None):
        """
        订阅Ticker数据

        Args:
            symbol: 交易对符号 (如 'ETHUSDT')
            callback: 数据回调函数 callback(ticker_data)
        """
        await self.initialize()

        if not self._client:
            raise RuntimeError("WebSocket client not initialized")

        logger.info(f"订阅Ticker数据: {symbol}")

        if callback:
            self._ticker_callback = callback

        try:
            # 使用SDK的watch_ticker方法
            async def ticker_handler():
                async for ticker in self._client.watch_ticker(symbol):
                    self._ticker_data[symbol] = ticker

                    # 提取最新价格
                    if 'last' in ticker:
                        self._last_price = Decimal(str(ticker['last']))

                        # 触发价格回调
                        if self._price_callback:
                            self._price_callback(self._last_price)

                    # 触发ticker回调
                    if self._ticker_callback:
                        self._ticker_callback(ticker)

            # 启动异步任务
            asyncio.create_task(ticker_handler())
            logger.info(f"✓ 成功订阅Ticker: {symbol}")

        except Exception as e:
            logger.error(f"订阅Ticker失败: {e}", exc_info=True)
            raise

    async def subscribe_orderbook(self, symbol: str, callback: Optional[Callable] = None):
        """
        订阅订单簿数据

        Args:
            symbol: 交易对符号
            callback: 数据回调函数 callback(orderbook_data)
        """
        await self.initialize()

        if not self._client:
            raise RuntimeError("WebSocket client not initialized")

        logger.info(f"订阅订单簿数据: {symbol}")

        if callback:
            self._orderbook_callback = callback

        try:
            async def orderbook_handler():
                async for orderbook in self._client.watch_order_book(symbol):
                    self._orderbook_data[symbol] = orderbook

                    if self._orderbook_callback:
                        self._orderbook_callback(orderbook)

            asyncio.create_task(orderbook_handler())
            logger.info(f"✓ 成功订阅订单簿: {symbol}")

        except Exception as e:
            logger.error(f"订阅订单簿失败: {e}", exc_info=True)
            raise

    def on_price_update(self, callback: Callable):
        """
        注册价格更新回调

        Args:
            callback: 回调函数 callback(price: Decimal)
        """
        self._price_callback = callback

    def get_last_price(self) -> Optional[Decimal]:
        """获取最后价格"""
        return self._last_price

    def get_ticker(self, symbol: str) -> Optional[dict]:
        """获取Ticker数据"""
        return self._ticker_data.get(symbol)

    def get_orderbook(self, symbol: str) -> Optional[dict]:
        """获取订单簿数据"""
        return self._orderbook_data.get(symbol)

    async def close(self):
        """关闭连接"""
        if self._client:
            logger.info("关闭GRVT市场数据订阅器")
            # WebSocket客户端会自动关闭
            self._client = None
            self._initialized = False


class SimulatedOrderEngine:
    """模拟订单引擎

    基于实时价格在本地模拟订单成交
    """

    def __init__(self):
        self.pending_orders = {}  # {client_order_id: order_info}
        self.filled_orders = []
        self.current_price: Optional[Decimal] = None

        logger.info("初始化模拟订单引擎")

    def create_order(
        self,
        client_order_id: str,
        symbol: str,
        side: str,
        price: Decimal,
        quantity: Decimal,
    ) -> dict:
        """
        创建模拟订单

        Args:
            client_order_id: 客户端订单ID
            symbol: 交易对
            side: 方向 (BUY/SELL)
            price: 价格
            quantity: 数量

        Returns:
            订单信息
        """
        order = {
            "order_id": f"sim_{client_order_id}",
            "client_order_id": client_order_id,
            "symbol": symbol,
            "side": side,
            "price": price,
            "quantity": quantity,
            "filled_quantity": Decimal("0"),
            "status": "PENDING",
            "create_time": datetime.now(),
        }

        self.pending_orders[client_order_id] = order
        logger.info(
            f"创建模拟订单: {client_order_id} {side} {quantity} @ {price}"
        )
        return order

    def cancel_order(self, client_order_id: str):
        """撤销订单"""
        if client_order_id in self.pending_orders:
            order = self.pending_orders.pop(client_order_id)
            order["status"] = "CANCELLED"
            logger.info(f"撤销模拟订单: {client_order_id}")
            return order
        return None

    def check_fills(self, current_price: Decimal) -> list:
        """
        检查订单是否成交

        Args:
            current_price: 当前市场价格

        Returns:
            成交的订单列表
        """
        self.current_price = current_price
        filled = []

        for order_id, order in list(self.pending_orders.items()):
            should_fill = False

            # 检查成交条件
            if order["side"] == "BUY":
                # 买单: 市场价 <= 订单价
                if current_price <= order["price"]:
                    should_fill = True
            else:  # SELL
                # 卖单: 市场价 >= 订单价
                if current_price >= order["price"]:
                    should_fill = True

            if should_fill:
                # 标记为成交
                order["status"] = "FILLED"
                order["filled_quantity"] = order["quantity"]
                order["filled_price"] = current_price
                order["filled_time"] = datetime.now()

                # 从pending移到filled
                self.pending_orders.pop(order_id)
                self.filled_orders.append(order)
                filled.append(order)

                logger.info(
                    f"✓ 模拟订单成交: {order_id} {order['side']} "
                    f"{order['quantity']} @ {current_price}"
                )

        return filled

    def get_open_orders(self) -> list:
        """获取未成交订单"""
        return list(self.pending_orders.values())

    def get_filled_orders(self) -> list:
        """获取已成交订单"""
        return self.filled_orders

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "pending_count": len(self.pending_orders),
            "filled_count": len(self.filled_orders),
            "current_price": self.current_price,
        }
