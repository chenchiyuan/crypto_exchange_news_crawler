#!/usr/bin/env python
"""
GRVT WebSocket 测试脚本
Test GRVT WebSocket Connection

测试改进的 WebSocket 连接功能:
- Cookie 认证
- 自动重连
- 异常处理
"""
import os
import sys
import asyncio
import logging
from decimal import Decimal

# 添加项目根目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')

import django
django.setup()

from grid_trading.services.simulation.grvt_websocket import (
    GRVTWebSocketManager,
    SimulatedOrderEngine
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class GridSimulationTester:
    """网格模拟测试器"""

    def __init__(self, symbol: str = "ETHUSDT"):
        self.symbol = symbol
        self.ws_manager: Optional[GRVTWebSocketManager] = None
        self.order_engine = SimulatedOrderEngine()

        # 统计数据
        self.stats = {
            "total_fills": 0,
            "entry_fills": 0,
            "exit_fills": 0,
            "price_updates": 0,
        }

    async def initialize(self):
        """初始化"""
        print("\n" + "=" * 60)
        print("初始化 GRVT WebSocket 测试")
        print("=" * 60)

        # 创建 WebSocket 管理器
        self.ws_manager = GRVTWebSocketManager(
            on_error=self._on_error
        )

        # 注册回调
        self.ws_manager.on_connect = self._on_connect
        self.ws_manager.on_disconnect = self._on_disconnect
        self.ws_manager.on_message = self._on_message

        # 连接 WebSocket
        url = self.ws_manager._get_websocket_url()
        await self.ws_manager.connect_websocket(url)

        # 订阅 ticker
        await self.ws_manager.subscribe_ticker(self.symbol)

        print(f"\n✓ 订阅了 {self.symbol} Ticker 数据")
        print("\n等待价格数据...")

    async def _on_connect(self):
        """连接建立回调"""
        logger.info("✓ WebSocket 连接已建立")

    async def _on_disconnect(self):
        """连接断开回调"""
        logger.warning("⚠ WebSocket 连接已断开")

    async def _on_message(self, data: dict):
        """消息回调"""
        self.stats["price_updates"] += 1

        # 获取价格
        price = self.ws_manager.get_last_price()

        if not price:
            return

        # 每10次价格更新显示一次
        if self.stats["price_updates"] % 10 == 0:
            print(f"[{self.stats['price_updates']:4d}] 价格: {price} USDT")

        # 检查订单成交
        filled = self.order_engine.check_fills(price)

        for order in filled:
            self.stats["total_fills"] += 1
            print(f"\n✓ [成交] {order['client_order_id']}: "
                  f"{order['side']} {order['quantity']} @ {order['filled_price']}")

    def _on_error(self, context: str, error: Exception):
        """错误回调"""
        logger.error(f"[{context}] {type(error).__name__}: {str(error)}")

    def create_test_orders(self):
        """创建测试订单"""
        print("\n创建测试订单...")

        # 获取当前价格
        current_price = self.ws_manager.get_last_price()

        if not current_price:
            print("⚠ 无法获取当前价格")
            return

        print(f"当前价格: {current_price}")

        # 创建网格订单
        orders = [
            {"id": "grid_1", "side": "SELL", "offset": 10},
            {"id": "grid_2", "side": "SELL", "offset": 20},
            {"id": "grid_3", "side": "SELL", "offset": 30},
        ]

        for order in orders:
            price = current_price + Decimal(str(order["offset"]))
            self.order_engine.create_order(
                client_order_id=order["id"],
                symbol=self.symbol,
                side=order["side"],
                price=price,
                quantity=Decimal("0.01"),
            )
            print(f"  ✓ {order['id']}: {order['side']} 0.01 @ {price}")

    async def run(self, duration: int = 60):
        """运行测试"""
        print("\n" + "=" * 60)
        print(f"开始测试 (运行 {duration} 秒)")
        print("=" * 60)
        print("\n按 Ctrl+C 提前停止\n")

        # 等待首次价格
        for i in range(30):
            await asyncio.sleep(1)
            if self.ws_manager.get_last_price():
                break

        if not self.ws_manager.get_last_price():
            print("❌ 未能获取价格数据")
            return

        print(f"✓ 接收到首次价格: {self.ws_manager.get_last_price()}")

        # 创建测试订单
        self.create_test_orders()

        # 启动监听任务
        listen_task = asyncio.create_task(self.ws_manager.start_listening())

        try:
            # 运行指定时长
            await asyncio.sleep(duration)

        except KeyboardInterrupt:
            print("\n\n收到停止信号...")

        finally:
            # 停止监听
            listen_task.cancel()

            await self.cleanup()

    async def cleanup(self):
        """清理资源"""
        print("\n清理资源...")

        # 显示最终统计
        print("\n" + "=" * 60)
        print("最终统计")
        print("=" * 60)
        print(f"价格更新: {self.stats['price_updates']} 次")
        print(f"总成交: {self.stats['total_fills']} 笔")

        order_stats = self.order_engine.get_stats()
        print(f"挂单数: {order_stats['pending_count']}")
        print(f"已成交: {order_stats['filled_count']}")
        print("=" * 60)

        # 关闭 WebSocket
        if self.ws_manager:
            await self.ws_manager.close()

        print("\n✓ 清理完成")


async def main():
    """主函数"""
    print("=" * 60)
    print("GRVT WebSocket 测试")
    print("=" * 60)

    # 检查 API KEY
    if not os.getenv("GRVT_API_KEY"):
        print("\n❌ 缺少环境变量: GRVT_API_KEY")
        print("\n请设置:")
        print("export GRVT_API_KEY=your_api_key")
        return

    print(f"\n✓ GRVT_API_KEY: {os.getenv('GRVT_API_KEY')[:10]}...")
    print(f"✓ GRVT_ENV: {os.getenv('GRVT_ENV', 'testnet')}")

    # 创建测试器
    tester = GridSimulationTester(symbol="ETHUSDT")

    try:
        # 初始化
        await tester.initialize()

        # 运行测试 (60秒)
        await tester.run(duration=60)

    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
