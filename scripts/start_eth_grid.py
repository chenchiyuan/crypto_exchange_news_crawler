#!/usr/bin/env python
"""
ETH 网格交易模拟器 - 基于 GRVT API
ETH Grid Trading Simulator - Using GRVT API

功能:
1. 从数据库加载网格配置
2. 实时获取 GRVT ETH 价格
3. 本地模拟网格订单成交
4. 记录交易日志
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

from django.db import transaction
from asgiref.sync import sync_to_async
from grid_trading.models import GridConfig, GridLevel, TradeLog
from pysdk.grvt_ccxt_pro import GrvtCcxtPro
from pysdk.grvt_ccxt_env import GrvtEnv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class ETHGridSimulator:
    """ETH 网格模拟器"""

    def __init__(self, config_name: str = "ETH_SHORT_GRID_TEST"):
        self.config_name = config_name
        self.config = None
        self.grid_levels = []

        # GRVT 配置
        self.api_key = os.getenv("GRVT_API_KEY")
        self.env = os.getenv("GRVT_ENV", "prod")
        self.instrument = os.getenv("GRVT_INSTRUMENT", "ETH_USDT_Perp")
        self.symbol = "ETHUSDT"

        self.client = None

        # 统计
        self.stats = {
            "price_updates": 0,
            "total_fills": 0,
            "buy_fills": 0,
            "sell_fills": 0,
        }

    async def initialize(self):
        """初始化"""
        print("=" * 70)
        print("ETH 网格交易模拟器")
        print("=" * 70)
        print(f"\n配置: {self.config_name}")
        print(f"环境: {self.env}")
        print(f"交易对: {self.symbol} ({self.instrument})")

        # 加载配置
        print("\n[1] 加载网格配置...")
        self.config = await sync_to_async(
            lambda: GridConfig.objects.filter(name=self.config_name).first()
        )()

        if not self.config:
            raise Exception(f"未找到配置: {self.config_name}")

        print(f"    ✓ 配置: {self.config.name}")
        print(f"    ✓ 价格区间: {self.config.lower_price} - {self.config.upper_price}")
        print(f"    ✓ 网格层数: {self.config.grid_levels}")
        print(f"    ✓ 每格数量: {self.config.quantity_per_grid}")

        # 初始化网格层级
        print("\n[2] 初始化网格层级...")
        await self._initialize_grid_levels()
        print(f"    ✓ 创建了 {len(self.grid_levels)} 个网格层级")

        # 连接 GRVT API
        print("\n[3] 连接 GRVT API...")
        env_config = GrvtEnv.PROD if self.env == "prod" else GrvtEnv.TESTNET
        parameters = {"api_key": self.api_key}
        self.client = GrvtCcxtPro(env=env_config, parameters=parameters, logger=logger)
        print("    ✓ API 连接成功")

    async def _initialize_grid_levels(self):
        """初始化网格层级"""
        # 删除旧的层级
        await sync_to_async(
            lambda: GridLevel.objects.filter(grid_config=self.config).delete()
        )()

        lower = float(self.config.lower_price)
        upper = float(self.config.upper_price)
        levels = self.config.grid_levels

        # 计算网格间距
        grid_step = (upper - lower) / levels

        # 创建网格层级
        for i in range(levels + 1):
            price = Decimal(str(lower + i * grid_step))

            level = await sync_to_async(GridLevel.objects.create)(
                grid_config=self.config,
                level_index=i - levels // 2,  # 中心为0
                price=price,
                quantity=self.config.quantity_per_grid,
                status='PENDING'
            )
            self.grid_levels.append(level)

    async def run(self, duration: int = 300):
        """运行模拟"""
        print("\n" + "=" * 70)
        print(f"开始网格模拟 (运行 {duration} 秒)")
        print("=" * 70)
        print("\n按 Ctrl+C 提前停止\n")

        # 获取初始价格
        print("[1] 获取当前ETH价格...")
        ticker = await self.client.fetch_ticker(self.instrument)
        current_price = Decimal(str(ticker.get("last_price", "0")))

        print(f"    当前价格: {current_price} USDT")
        print(f"    买一: {ticker.get('best_bid_price')}")
        print(f"    卖一: {ticker.get('best_ask_price')}")

        # 创建初始挂单
        print("\n[2] 根据当前价格创建挂单...")
        await self._create_initial_orders(current_price)

        # 开始监控
        print("\n[3] 开始监控价格变化...\n")
        print(f"{'时间':<12} {'价格':<12} {'挂单':<8} {'已成交':<8} {'说明'}")
        print("-" * 70)

        start_time = datetime.now()

        try:
            iteration = 0
            while True:
                # 检查是否超时
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed >= duration:
                    break

                iteration += 1

                # 获取价格
                ticker = await self.client.fetch_ticker(self.instrument)
                price = Decimal(str(ticker.get("last_price", "0")))

                self.stats["price_updates"] += 1

                # 检查成交
                filled = await self._check_fills(price)

                # 每5秒显示一次
                if iteration % 5 == 0:
                    pending_count = GridLevel.objects.filter(
                        grid_config=self.config,
                        status='PENDING'
                    ).count()

                    filled_count = GridLevel.objects.filter(
                        grid_config=self.config,
                        status='FILLED'
                    ).count()

                    time_str = datetime.now().strftime('%H:%M:%S')

                    desc = f"买{self.stats['buy_fills']}/卖{self.stats['sell_fills']}" if filled else ""

                    print(f"{time_str:<12} {price:<12} {pending_count:<8} {filled_count:<8} {desc}")

                await asyncio.sleep(1)

        except KeyboardInterrupt:
            print("\n\n收到停止信号")

        finally:
            await self.cleanup()

    async def _create_initial_orders(self, current_price: Decimal):
        """根据当前价格创建初始挂单"""
        created = 0

        for level in self.grid_levels:
            # 价格高于当前价 -> 卖单
            # 价格低于当前价 -> 买单

            if level.price > current_price:
                level.side = 'SELL'
                level.status = 'PENDING'
                level.save()
                created += 1
            elif level.price < current_price:
                level.side = 'BUY'
                level.status = 'PENDING'
                level.save()
                created += 1

        print(f"    ✓ 创建了 {created} 个挂单")

        # 显示部分挂单
        buy_orders = GridLevel.objects.filter(
            grid_config=self.config,
            side='BUY',
            status='PENDING'
        ).order_by('-price')[:3]

        sell_orders = GridLevel.objects.filter(
            grid_config=self.config,
            side='SELL',
            status='PENDING'
        ).order_by('price')[:3]

        if buy_orders:
            print(f"\n    买单示例 (最接近当前价的3个):")
            for order in buy_orders:
                print(f"      BUY  {order.quantity} @ {order.price}")

        if sell_orders:
            print(f"\n    卖单示例 (最接近当前价的3个):")
            for order in sell_orders:
                print(f"      SELL {order.quantity} @ {order.price}")

    async def _check_fills(self, current_price: Decimal) -> bool:
        """检查订单成交"""
        filled = False

        # 检查卖单
        sell_orders = GridLevel.objects.filter(
            grid_config=self.config,
            side='SELL',
            status='PENDING'
        ).filter(price__lte=current_price)

        for order in sell_orders:
            order.status = 'FILLED'
            order.filled_price = current_price
            order.filled_time = datetime.now()
            order.save()

            # 记录交易日志
            TradeLog.objects.create(
                grid_config=self.config,
                log_type='FILL',
                side=order.side,
                price=current_price,
                quantity=order.quantity,
                level_index=order.level_index,
                message=f"卖单成交 @ {current_price}"
            )

            self.stats['total_fills'] += 1
            self.stats['sell_fills'] += 1
            filled = True

            # 创建对冲买单 (价格更低)
            await self._create_hedge_order(order, current_price)

        # 检查买单
        buy_orders = GridLevel.objects.filter(
            grid_config=self.config,
            side='BUY',
            status='PENDING'
        ).filter(price__gte=current_price)

        for order in buy_orders:
            order.status = 'FILLED'
            order.filled_price = current_price
            order.filled_time = datetime.now()
            order.save()

            # 记录交易日志
            TradeLog.objects.create(
                grid_config=self.config,
                log_type='FILL',
                side=order.side,
                price=current_price,
                quantity=order.quantity,
                level_index=order.level_index,
                message=f"买单成交 @ {current_price}"
            )

            self.stats['total_fills'] += 1
            self.stats['buy_fills'] += 1
            filled = True

            # 创建对冲卖单 (价格更高)
            await self._create_hedge_order(order, current_price)

        return filled

    async def _create_hedge_order(self, filled_order: GridLevel, current_price: Decimal):
        """创建对冲订单"""
        # 卖单成交后,在更低价格创建买单
        # 买单成交后,在更高价格创建卖单

        if filled_order.side == 'SELL':
            # 找下一个未成交的买单层级
            lower_level = GridLevel.objects.filter(
                grid_config=self.config,
                price__lt=filled_order.price,
                side='BUY',
                status='PENDING'
            ).order_by('-price').first()

            if lower_level:
                logger.info(f"    → 对冲: 在 {lower_level.price} 等待买入")

        else:  # BUY
            # 找下一个未成交的卖单层级
            higher_level = GridLevel.objects.filter(
                grid_config=self.config,
                price__gt=filled_order.price,
                side='SELL',
                status='PENDING'
            ).order_by('price').first()

            if higher_level:
                logger.info(f"    → 对冲: 在 {higher_level.price} 等待卖出")

    async def cleanup(self):
        """清理并显示结果"""
        print("\n" + "=" * 70)
        print("模拟结果")
        print("=" * 70)

        # 统计
        print(f"\n价格更新次数: {self.stats['price_updates']}")
        print(f"总成交笔数: {self.stats['total_fills']}")
        print(f"  买入: {self.stats['buy_fills']}")
        print(f"  卖出: {self.stats['sell_fills']}")

        # 当前状态
        pending = GridLevel.objects.filter(
            grid_config=self.config,
            status='PENDING'
        ).count()

        filled = GridLevel.objects.filter(
            grid_config=self.config,
            status='FILLED'
        ).count()

        print(f"\n当前挂单: {pending}")
        print(f"已成交: {filled}")

        # 显示最近成交
        recent_trades = TradeLog.objects.filter(
            grid_config=self.config,
            log_type='FILL'
        ).order_by('-created_at')[:5]

        if recent_trades:
            print(f"\n最近5笔成交:")
            for trade in recent_trades:
                print(f"  {trade.created_at.strftime('%H:%M:%S')} | "
                      f"{trade.side:<4} {trade.quantity} @ {trade.price} | "
                      f"Level {trade.level_index}")

        print("=" * 70)
        print("\n✅ 模拟完成!")


async def main():
    """主函数"""
    # 检查环境变量
    required_vars = ["GRVT_API_KEY", "GRVT_INSTRUMENT"]

    for var in required_vars:
        if not os.getenv(var):
            print(f"\n❌ 缺少环境变量: {var}")
            print("\n请设置:")
            print("export GRVT_API_KEY=your_key")
            print("export GRVT_INSTRUMENT=ETH_USDT_Perp")
            print("export GRVT_ENV=prod")
            return

    simulator = ETHGridSimulator(config_name="ETH_SHORT_GRID_TEST")

    try:
        await simulator.initialize()
        await simulator.run(duration=300)  # 运行5分钟

    except KeyboardInterrupt:
        print("\n\n收到停止信号")

    except Exception as e:
        logger.error(f"模拟失败: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
