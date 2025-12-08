"""
GRVT WebSocket 连接管理器
GRVT WebSocket Connection Manager

参考 ritmex-bot 实现的 WebSocket 连接、重连和异常处理
"""
import os
import logging
import asyncio
import aiohttp
import time
from typing import Optional, Callable, Dict, Any
from decimal import Decimal
from datetime import datetime

logger = logging.getLogger(__name__)

# 环境配置
ENVIRONMENT_HOSTS = {
    "prod": {
        "trades": "https://trades.grvt.io",
        "market": "https://market-data.grvt.io",
        "edge": "https://edge.grvt.io",
    },
    "testnet": {
        "trades": "https://trades.testnet.grvt.io",
        "market": "https://market-data.testnet.grvt.io",
        "edge": "https://edge.testnet.grvt.io",
    },
}


class SessionInfo:
    """会话信息"""
    def __init__(self, cookie: str, account_id: str, expires_at: Optional[int] = None):
        self.cookie = cookie
        self.account_id = account_id
        self.expires_at = expires_at


class GRVTWebSocketManager:
    """GRVT WebSocket 管理器

    功能:
    - Cookie 认证
    - 自动重连 (指数退避)
    - 异常处理
    - 连接状态管理
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        env: str = "testnet",
        on_error: Optional[Callable[[str, Exception], None]] = None,
    ):
        """
        初始化 WebSocket 管理器

        Args:
            api_key: GRVT API Key
            env: 环境 (testnet/prod)
            on_error: 错误回调函数 on_error(context, error)
        """
        self.api_key = api_key or os.getenv("GRVT_API_KEY")
        self.env = env or os.getenv("GRVT_ENV", "testnet")

        if not self.api_key:
            raise ValueError("Missing GRVT_API_KEY")

        # 获取环境配置
        self.hosts = ENVIRONMENT_HOSTS.get(self.env, ENVIRONMENT_HOSTS["testnet"])

        # 会话信息
        self.session_info: Optional[SessionInfo] = None
        self.session_promise: Optional[asyncio.Task] = None

        # WebSocket 状态
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.ws_session: Optional[aiohttp.ClientSession] = None
        self.ws_connected = False
        self.ws_reconnecting = False
        self.retry_count = 0
        self.max_retries = 10

        # 回调函数
        self.on_error = on_error or self._default_error_handler
        self.on_message: Optional[Callable] = None
        self.on_connect: Optional[Callable] = None
        self.on_disconnect: Optional[Callable] = None

        # 数据缓存
        self.last_price: Optional[Decimal] = None
        self.ticker_data: Dict[str, Any] = {}

        logger.info(f"初始化GRVT WebSocket管理器: env={self.env}, host={self.hosts['edge']}")

    def _default_error_handler(self, context: str, error: Exception):
        """默认错误处理器"""
        logger.error(f"[{context}] {type(error).__name__}: {str(error)}")

    def is_session_expired(self) -> bool:
        """检查会话是否过期"""
        if not self.session_info:
            return True

        if not self.session_info.expires_at:
            return False

        # 提前 5 秒视为过期
        return time.time() > (self.session_info.expires_at / 1000 - 5)

    async def ensure_session(self):
        """确保会话有效"""
        if self.session_info and not self.is_session_expired():
            return

        if self.session_promise:
            await self.session_promise
            return

        if not self.api_key:
            if not self.session_info:
                raise ValueError("GRVT authentication requires GRVT_API_KEY or existing session")
            return

        # 创建认证任务
        async def auth_task():
            try:
                await self.authenticate()
            finally:
                self.session_promise = None

        self.session_promise = asyncio.create_task(auth_task())
        await self.session_promise

    async def authenticate(self):
        """
        使用 API Key 进行认证

        参考 ritmex-bot 实现:
        https://github.com/xxx/ritmex-bot/blob/main/src/exchanges/grvt/gateway.ts#L774-L806
        """
        if not self.api_key:
            raise ValueError("GRVT_API_KEY is not configured")

        logger.info("正在认证 GRVT API...")

        try:
            url = f"{self.hosts['edge']}/auth/api_key/login"
            headers = {
                "Content-Type": "application/json",
                "Cookie": "rm=true;",
            }
            payload = {"api_key": self.api_key}

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"认证失败 [{response.status}]: {error_text}")

                    # 解析 Set-Cookie
                    set_cookie = response.headers.get("Set-Cookie", "")
                    account_id = response.headers.get("x-grvt-account-id") or response.headers.get("X-Grvt-Account-Id")

                    if not set_cookie or not account_id:
                        raise Exception("认证响应缺少 cookie 或 account_id")

                    # 解析 cookie 和过期时间
                    cookie_info = self._parse_set_cookie(set_cookie)

                    if not cookie_info["cookie"]:
                        raise Exception("无法解析认证 cookie")

                    self.session_info = SessionInfo(
                        cookie=cookie_info["cookie"],
                        account_id=account_id.strip(),
                        expires_at=cookie_info.get("expires_at"),
                    )

                    logger.info(f"✓ GRVT 认证成功, account_id={self.session_info.account_id}")

        except Exception as e:
            self.on_error("authenticate", e)
            raise Exception(f"Failed to authenticate with GRVT: {str(e)}")

    def _parse_set_cookie(self, header: str) -> Dict[str, Any]:
        """
        解析 Set-Cookie 头

        参考 ritmex-bot:
        https://github.com/xxx/ritmex-bot/blob/main/src/exchanges/grvt/gateway.ts#L948-L967
        """
        result = {"cookie": None, "expires_at": None}

        if not header:
            return result

        # 分割多个 cookie
        entries = header.split(",") if "," in header else [header]

        for entry in entries:
            segments = [s.strip() for s in entry.split(";") if s.strip()]

            if not segments:
                continue

            # 查找 gravity cookie
            cookie_segment = None
            for seg in segments:
                if seg.lower().startswith("gravity"):
                    cookie_segment = seg
                    break

            if not cookie_segment:
                cookie_segment = segments[0]

            # 查找过期时间
            expires_segment = None
            for seg in segments:
                if seg.lower().startswith("expires="):
                    expires_segment = seg
                    break

            if cookie_segment:
                result["cookie"] = cookie_segment

            if expires_segment:
                try:
                    # 解析过期时间
                    expires_str = expires_segment[8:]  # 去掉 "expires="
                    # 转为时间戳 (毫秒)
                    from email.utils import parsedate_to_datetime
                    dt = parsedate_to_datetime(expires_str)
                    result["expires_at"] = int(dt.timestamp() * 1000)
                except Exception as e:
                    logger.warning(f"解析cookie过期时间失败: {e}")

            break

        return result

    async def connect_websocket(self, url: str):
        """
        建立 WebSocket 连接

        参考 ritmex-bot:
        https://github.com/xxx/ritmex-bot/blob/main/src/exchanges/grvt/gateway.ts#L514-L583
        """
        try:
            # 确保会话有效
            await self.ensure_session()

            if not self.session_info:
                raise Exception("No valid session for WebSocket connection")

            # 创建 WebSocket session
            if not self.ws_session:
                self.ws_session = aiohttp.ClientSession()

            # 设置请求头
            headers = {
                "Cookie": self.session_info.cookie,
                "X-Grvt-Account-Id": self.session_info.account_id,
            }

            logger.info(f"正在连接 WebSocket: {url}")

            self.ws = await self.ws_session.ws_connect(
                url,
                headers=headers,
                heartbeat=30,
                timeout=aiohttp.ClientTimeout(total=10),
            )

            self.ws_connected = True
            self.retry_count = 0  # 重置重试计数

            logger.info("✓ WebSocket 连接成功")

            # 触发连接回调
            if self.on_connect:
                await self.on_connect()

        except Exception as e:
            self.ws_connected = False
            self.on_error("connect_websocket", e)
            raise

    async def subscribe_ticker(self, symbol: str):
        """订阅 Ticker 数据"""
        if not self.ws or not self.ws_connected:
            raise Exception("WebSocket not connected")

        # 构造订阅请求
        subscribe_msg = {
            "method": "subscribe",
            "params": {
                "channel": "ticker",
                "symbol": symbol,
            }
        }

        await self.ws.send_json(subscribe_msg)
        logger.info(f"✓ 订阅Ticker: {symbol}")

    async def start_listening(self):
        """开始监听消息"""
        if not self.ws:
            raise Exception("WebSocket not connected")

        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.json()
                    await self._handle_message(data)

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    self.on_error("websocket_error", Exception(f"WebSocket error: {msg}"))
                    break

                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    logger.warning("WebSocket 连接已关闭")
                    break

        except Exception as e:
            self.on_error("start_listening", e)

        finally:
            self.ws_connected = False

            # 触发断开回调
            if self.on_disconnect:
                await self.on_disconnect()

            # 尝试重连
            if not self.ws_reconnecting and self.retry_count < self.max_retries:
                await self._schedule_reconnect()

    async def _handle_message(self, data: Dict[str, Any]):
        """处理接收到的消息"""
        try:
            # 解析 ticker 数据
            if "channel" in data and data["channel"] == "ticker":
                ticker = data.get("data", {})

                if "last" in ticker:
                    self.last_price = Decimal(str(ticker["last"]))

                self.ticker_data = ticker

                # 触发消息回调
                if self.on_message:
                    await self.on_message(data)

        except Exception as e:
            self.on_error("handle_message", e)

    async def _schedule_reconnect(self):
        """
        安排重连

        使用指数退避算法 (参考 ritmex-bot)
        https://github.com/xxx/ritmex-bot/blob/main/src/exchanges/grvt/gateway.ts#L530-L535
        """
        if self.ws_reconnecting:
            return

        self.ws_reconnecting = True
        self.retry_count += 1

        # 指数退避: 1s, 2s, 4s, 8s, ..., 最大30s
        base_delay = 1000 * (2 ** min(8, self.retry_count - 1))
        jitter = int(time.time() * 250) % 250  # 抖动
        delay_ms = min(30000, base_delay + jitter)

        logger.info(f"计划重连... (第{self.retry_count}次, 延迟{delay_ms}ms)")

        await asyncio.sleep(delay_ms / 1000)

        try:
            # 重新连接
            url = self._get_websocket_url()
            await self.connect_websocket(url)
            await self.start_listening()

        except Exception as e:
            self.on_error("reconnect", e)

        finally:
            self.ws_reconnecting = False

    def _get_websocket_url(self) -> str:
        """获取 WebSocket URL"""
        base_url = self.hosts["trades"]
        ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")
        return f"{ws_url}/ws/lite"

    async def close(self):
        """关闭连接"""
        logger.info("关闭 GRVT WebSocket 连接...")

        self.ws_connected = False
        self.ws_reconnecting = False

        if self.ws:
            await self.ws.close()
            self.ws = None

        if self.ws_session:
            await self.ws_session.close()
            self.ws_session = None

        logger.info("✓ WebSocket 连接已关闭")

    def get_last_price(self) -> Optional[Decimal]:
        """获取最后价格"""
        return self.last_price

    def get_ticker(self) -> Dict[str, Any]:
        """获取 Ticker 数据"""
        return self.ticker_data.copy()


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
