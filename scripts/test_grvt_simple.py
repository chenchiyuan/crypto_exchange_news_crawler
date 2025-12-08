#!/usr/bin/env python
"""
GRVT 网格模拟 - 简化版
使用 HTTP API 轮询价格并模拟网格交易
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
    level=logging.WARNING,  # 减少日志输出
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class SimpleGridSimulator:
    """简单网格模拟器"""

    def __init__(self):
        self.api_key = os.getenv("GRVT_API_KEY")
        self.env = os.getenv("GRVT_ENV", "prod")
        self.instrument = os.getenv("GRVT_INSTRUMENT", "BTC_USDT_Perp")
        self.symbol = os.getenv("GRVT_SYMBOL", "BTCUSDT")

        self.pending_orders = {}
        self.filled_orders = []

        self.stats = {
            "price_updates": 0,
            "total_fills": 0,
        }

    async def run(self):
        """运行模拟"""
        print("=" * 70)
        print("GRVT 网格模拟测试")
        print("=" * 70)
        print(f"\n环境: {self.env}")
        print(f"交易对: {self.symbol} ({self.instrument})")
        print(f"API Key: {self.api_key[:10]}...\n")

        # 创建客户端
        env_config = GrvtEnv.PROD if self.env == "prod" else GrvtEnv.TESTNET
        parameters = {"api_key": self.api_key}

        client = GrvtCcxtPro(env=env_config, parameters=parameters, logger=logger)

        try:
            print("✓ 连接GRVT API成功\n")

            # 获取初始价格
            print("[1] 获取当前价格...")
            ticker = await client.fetch_ticker(self.instrument)  # SDK已展开result字段
            current_price = Decimal(str(ticker.get("last_price", "0")))

            print(f"    当前价格: {current_price} USDT")
            print(f"    买一: {ticker.get('best_bid_price')}")
            print(f"    卖一: {ticker.get('best_ask_price')}")
            print(f"    24h成交量: {ticker.get('buy_volume_24h_b')}")

            # 创建网格订单
            print("\n[2] 创建网格订单...")
            self.create_grid_orders(current_price)

            # 开始监控
            print("\n[3] 开始监控价格变化... (30秒)\n")

            for i in range(30):
                try:
                    # 获取价格
                    ticker = await client.fetch_ticker(self.instrument)  # SDK已展开result字段
                    price = Decimal(str(ticker.get("last_price", "0")))

                    self.stats["price_updates"] += 1

                    # 每5次显示一次
                    if self.stats["price_updates"] % 5 == 0:
                        print(f"[{self.stats['price_updates']:3d}] "
                              f"价格: {price:>10} | "
                              f"挂单: {len(self.pending_orders)} | "
                              f"已成交: {len(self.filled_orders)}")

                    # 检查成交
                    self.check_fills(price)

                    await asyncio.sleep(1)

                except Exception as e:
                    logger.error(f"循环错误: {e}")
                    await asyncio.sleep(2)

        finally:
            # 注意: GrvtCcxtPro 没有close()方法
            pass

        # 显示结果
        self.show_results()

    def create_grid_orders(self, current_price: Decimal):
        """创建网格订单"""
        orders = [
            {"id": "grid_50", "side": "SELL", "offset": 50},
            {"id": "grid_100", "side": "SELL", "offset": 100},
            {"id": "grid_150", "side": "SELL", "offset": 150},
        ]

        for order in orders:
            price = current_price + Decimal(str(order["offset"]))
            self.pending_orders[order["id"]] = {
                "id": order["id"],
                "side": order["side"],
                "price": price,
                "quantity": Decimal("0.001"),
                "status": "PENDING",
            }
            print(f"    ✓ {order['id']}: {order['side']} 0.001 @ {price}")

    def check_fills(self, current_price: Decimal):
        """检查订单成交"""
        for order_id, order in list(self.pending_orders.items()):
            should_fill = False

            if order["side"] == "SELL":
                if current_price >= order["price"]:
                    should_fill = True
            else:  # BUY
                if current_price <= order["price"]:
                    should_fill = True

            if should_fill:
                order["status"] = "FILLED"
                order["filled_price"] = current_price
                order["filled_time"] = datetime.now()

                self.pending_orders.pop(order_id)
                self.filled_orders.append(order)
                self.stats["total_fills"] += 1

                print(f"\n✅ [成交] {order_id}: {order['side']} "
                      f"{order['quantity']} @ {current_price}\n")

    def show_results(self):
        """显示结果"""
        print("\n" + "=" * 70)
        print("测试结果")
        print("=" * 70)
        print(f"价格更新次数: {self.stats['price_updates']}")
        print(f"总成交笔数: {self.stats['total_fills']}")
        print(f"未成交订单: {len(self.pending_orders)}")

        if self.filled_orders:
            print(f"\n已成交订单:")
            for order in self.filled_orders:
                print(f"  - {order['id']}: {order['side']} "
                      f"{order['quantity']} @ {order['filled_price']}")
        else:
            print("\n无成交订单")

        if self.pending_orders:
            print(f"\n未成交订单:")
            for order in self.pending_orders.values():
                print(f"  - {order['id']}: {order['side']} "
                      f"{order['quantity']} @ {order['price']}")

        print("=" * 70)
        print("\n✅ 测试完成!")


async def main():
    """主函数"""
    # 检查配置
    if not os.getenv("GRVT_API_KEY"):
        print("\n❌ 缺少环境变量: GRVT_API_KEY")
        print("\n请设置:")
        print("export GRVT_API_KEY=your_key")
        print("export GRVT_ENV=prod")
        print("export GRVT_INSTRUMENT=BTC_USDT_Perp")
        print("export GRVT_SYMBOL=BTCUSDT")
        return

    simulator = SimpleGridSimulator()

    try:
        await simulator.run()
    except KeyboardInterrupt:
        print("\n\n收到停止信号")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
