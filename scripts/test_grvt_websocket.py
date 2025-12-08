#!/usr/bin/env python
"""
使用 GRVT SDK HTTP Polling 测试
Test GRVT using HTTP API (bypassing IP whitelist for WebSocket)

基于 ritmex-bot 实现,使用 HTTP 轮询作为临时方案
"""
import os
import sys
import asyncio
import logging
from decimal import Decimal
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')

import django
django.setup()

from pysdk.grvt_ccxt_pro import GrvtCcxtPro
from pysdk.grvt_ccxt_env import GrvtEnv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class GridSimulator:
    """网格模拟器 - 使用HTTP轮询"""

    def __init__(self):
        self.api_key = os.getenv("GRVT_API_KEY")
        self.env = os.getenv("GRVT_ENV", "prod")
        self.instrument = os.getenv("GRVT_INSTRUMENT", "BTC_USDT_Perp")
        self.symbol = os.getenv("GRVT_SYMBOL", "BTCUSDT")

        self.client = None
        self.pending_orders = {}
        self.filled_orders = []

        self.stats = {
            "price_updates": 0,
            "total_fills": 0,
        }

    async def initialize(self):
        """初始化"""
        print("=" * 70)
        print("GRVT 网格模拟测试 (HTTP Polling)")
        print("=" * 70)
        print(f"\n配置:")
        print(f"  Environment: {self.env}")
        print(f"  Symbol: {self.symbol}")
        print(f"  Instrument: {self.instrument}")
        print(f"  API Key: {self.api_key[:10]}...")

        # 选择环境
        if self.env == "prod":
            env_config = GrvtEnv.PROD
        elif self.env == "testnet":
            env_config = GrvtEnv.TESTNET
        else:
            env_config = GrvtEnv.DEV

        # 创建客户端
        parameters = {"api_key": self.api_key}

        self.client = GrvtCcxtPro(
            env=env_config,
            parameters=parameters,
            logger=logger
        )

        print("\n✓ HTTP 客户端已创建")

    async def get_current_price(self) -> Decimal:
        """获取当前价格"""
        try:
            response = await self.client.fetch_ticker(self.instrument)

            # GRVT API 返回格式: {'result': {...}}
            ticker = response.get("result", {})

            # 提取价格: last_price
            last_price = ticker.get("last_price", ticker.get("last", "0"))
            price = Decimal(str(last_price))

            return price
        except Exception as e:
            logger.error(f"获取价格失败: {e}", exc_info=True)
            return None

    def create_test_orders(self, current_price: Decimal):
        """创建测试订单"""
        print(f"\n当前价格: {current_price}")
        print("\n创建网格订单:")

        # 创建3个SELL订单
        orders = [
            {"id": "grid_1", "side": "SELL", "offset": 100},
            {"id": "grid_2", "side": "SELL", "offset": 200},
            {"id": "grid_3", "side": "SELL", "offset": 300},
        ]

        for order in orders:
            price = current_price + Decimal(str(order["offset"]))
            self.pending_orders[order["id"]] = {
                "id": order["id"],
                "side": order["side"],
                "price": price,
                "quantity": Decimal("0.001"),
                "status": "PENDING",
                "create_time": datetime.now(),
            }
            print(f"  ✓ {order['id']}: {order['side']} 0.001 @ {price}")

    def check_fills(self, current_price: Decimal):
        """检查订单成交"""
        filled = []

        for order_id, order in list(self.pending_orders.items()):
            should_fill = False

            if order["side"] == "SELL":
                # 卖单: 价格 >= 订单价
                if current_price >= order["price"]:
                    should_fill = True
            else:  # BUY
                # 买单: 价格 <= 订单价
                if current_price <= order["price"]:
                    should_fill = True

            if should_fill:
                order["status"] = "FILLED"
                order["filled_price"] = current_price
                order["filled_time"] = datetime.now()

                self.pending_orders.pop(order_id)
                self.filled_orders.append(order)
                filled.append(order)

                self.stats["total_fills"] += 1

                print(f"\n✓ [成交] {order_id}: {order['side']} "
                      f"{order['quantity']} @ {current_price}")

        return filled

    async def run(self, duration: int = 60):
        """运行模拟"""
        print("\n" + "=" * 70)
        print(f"开始网格模拟 (运行 {duration} 秒)")
        print("=" * 70)
        print("\n按 Ctrl+C 提前停止\n")

        # 获取初始价格
        current_price = await self.get_current_price()

        if not current_price:
            print("❌ 无法获取价格")
            return

        # 创建测试订单
        self.create_test_orders(current_price)

        # 开始轮询
        print(f"\n开始监控价格变化...\n")

        start_time = datetime.now()

        try:
            while True:
                # 检查是否超时
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed >= duration:
                    break

                # 获取价格
                price = await self.get_current_price()

                if price:
                    self.stats["price_updates"] += 1

                    # 每10次显示一次
                    if self.stats["price_updates"] % 10 == 0:
                        print(f"[{self.stats['price_updates']:4d}] "
                              f"价格: {price} | "
                              f"挂单: {len(self.pending_orders)} | "
                              f"已成交: {len(self.filled_orders)}")

                    # 检查成交
                    self.check_fills(price)

                await asyncio.sleep(1)  # 1秒轮询一次

        except KeyboardInterrupt:
            print("\n\n收到停止信号")

        finally:
            await self.cleanup()

    async def cleanup(self):
        """清理资源"""
        print("\n" + "=" * 70)
        print("最终统计")
        print("=" * 70)
        print(f"价格更新: {self.stats['price_updates']} 次")
        print(f"总成交: {self.stats['total_fills']} 笔")
        print(f"挂单数: {len(self.pending_orders)}")
        print(f"已成交: {len(self.filled_orders)}")

        if self.filled_orders:
            print(f"\n已成交订单明细:")
            for order in self.filled_orders:
                print(f"  - {order['id']}: {order['side']} "
                      f"{order['quantity']} @ {order['filled_price']}")

        print("=" * 70)

        if self.client:
            await self.client.close()

        print("\n✓ 清理完成")


async def main():
    """主函数"""
    # 检查配置
    required_vars = ["GRVT_API_KEY", "GRVT_ENV", "GRVT_INSTRUMENT"]

    for var in required_vars:
        if not os.getenv(var):
            print(f"\n❌ 缺少环境变量: {var}")
            print("\n请设置:")
            print("export GRVT_API_KEY=your_api_key")
            print("export GRVT_ENV=prod")
            print("export GRVT_INSTRUMENT=BTC_USDT_Perp")
            print("export GRVT_SYMBOL=BTCUSDT")
            return

    simulator = GridSimulator()

    try:
        await simulator.initialize()
        await simulator.run(duration=60)

    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
