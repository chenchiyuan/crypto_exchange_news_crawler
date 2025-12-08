#!/usr/bin/env python
"""
ETH 网格交易模拟器 - 简化同步版本
使用线程池运行Django ORM,避免async/sync冲突
"""
import os
import sys
import time
import logging
from decimal import Decimal
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')

import django
django.setup()

from grid_trading.models import GridConfig, GridLevel, TradeLog
from pysdk.grvt_ccxt_pro import GrvtCcxtPro
from pysdk.grvt_ccxt_env import GrvtEnv
import asyncio

logging.basicConfig(
    level=logging.WARNING,  # 减少日志
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)


def run_eth_grid_simulation(duration=60):
    """运行ETH网格模拟"""
    print("=" * 70)
    print("ETH 网格交易模拟器")
    print("=" * 70)

    # 检查环境变量
    api_key = os.getenv("GRVT_API_KEY")
    env = os.getenv("GRVT_ENV", "prod")
    instrument = os.getenv("GRVT_INSTRUMENT", "ETH_USDT_Perp")

    if not api_key:
        print("\n❌ 缺少 GRVT_API_KEY")
        return

    print(f"\n环境: {env}")
    print(f"交易对: {instrument}")

    # 加载配置
    print("\n[1] 加载网格配置...")
    config = GridConfig.objects.filter(name="ETH_SHORT_GRID_TEST").first()

    if not config:
        print("❌ 未找到配置")
        return

    print(f"    ✓ 配置: {config.name}")
    print(f"    ✓ 价格区间: {config.lower_price} - {config.upper_price}")
    print(f"    ✓ 网格层数: {config.grid_levels}")

    # 初始化网格
    print("\n[2] 初始化网格层级...")
    GridLevel.objects.filter(config=config).delete()

    lower = float(config.lower_price)
    upper = float(config.upper_price)
    levels = config.grid_levels
    grid_step = (upper - lower) / levels

    for i in range(levels + 1):
        price = Decimal(str(lower + i * grid_step))
        GridLevel.objects.create(
            config=config,
            level_index=i - levels // 2,
            price=price,
            quantity=config.trade_amount,
            status='PENDING'
        )

    print(f"    ✓ 创建了 {levels + 1} 个网格层级")

    # 连接API
    print("\n[3] 连接 GRVT API...")
    env_config = GrvtEnv.PROD if env == "prod" else GrvtEnv.TESTNET

    # 使用asyncio运行
    async def async_main():
        client = GrvtCcxtPro(
            env=env_config,
            parameters={"api_key": api_key}
        )

        try:
            # 获取当前价格
            ticker = await client.fetch_ticker(instrument)
            current_price = Decimal(str(ticker.get("last_price", "0")))

            print(f"    ✓ 当前价格: {current_price} USDT\n")

            # 根据当前价格创建挂单
            print("[4] 创建挂单...")
            created = 0
            for level in GridLevel.objects.filter(config=config):
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

            print(f"    ✓ 创建了 {created} 个挂单\n")

            # 监控
            print(f"[5] 开始监控 ({duration}秒)...\n")
            print(f"{'时间':<12} {'价格':<12} {'挂单':<8} {'成交':<8}")
            print("-" * 50)

            stats = {"fills": 0, "buy": 0, "sell": 0}

            for i in range(duration):
                # 获取价格
                ticker = await client.fetch_ticker(instrument)
                price = Decimal(str(ticker.get("last_price", "0")))

                # 检查成交 - 卖单
                sell_orders = GridLevel.objects.filter(
                    config=config,
                    side='SELL',
                    status='PENDING',
                    price__lte=price
                )

                for order in sell_orders:
                    order.status = 'FILLED'
                    order.filled_price = price
                    order.filled_time = datetime.now()
                    order.save()

                    TradeLog.objects.create(
                        config=config,
                        log_type='FILL',
                        side='SELL',
                        price=price,
                        quantity=order.quantity,
                        level_index=order.level_index,
                        message=f"卖单成交 @ {price}"
                    )

                    stats["fills"] += 1
                    stats["sell"] += 1

                # 检查成交 - 买单
                buy_orders = GridLevel.objects.filter(
                    config=config,
                    side='BUY',
                    status='PENDING',
                    price__gte=price
                )

                for order in buy_orders:
                    order.status = 'FILLED'
                    order.filled_price = price
                    order.filled_time = datetime.now()
                    order.save()

                    TradeLog.objects.create(
                        config=config,
                        log_type='FILL',
                        side='BUY',
                        price=price,
                        quantity=order.quantity,
                        level_index=order.level_index,
                        message=f"买单成交 @ {price}"
                    )

                    stats["fills"] += 1
                    stats["buy"] += 1

                # 每5秒显示
                if i % 5 == 0:
                    pending = GridLevel.objects.filter(
                        config=config,
                        status='PENDING'
                    ).count()

                    filled = GridLevel.objects.filter(
                        config=config,
                        status='FILLED'
                    ).count()

                    time_str = datetime.now().strftime('%H:%M:%S')
                    print(f"{time_str:<12} {price:<12} {pending:<8} {filled:<8}")

                await asyncio.sleep(1)

            # 结果
            print("\n" + "=" * 70)
            print("模拟结果")
            print("=" * 70)
            print(f"总成交: {stats['fills']} 笔")
            print(f"  买入: {stats['buy']}")
            print(f"  卖出: {stats['sell']}")

            pending = GridLevel.objects.filter(config=config, status='PENDING').count()
            filled = GridLevel.objects.filter(config=config, status='FILLED').count()
            print(f"\n挂单: {pending}, 已成交: {filled}")

            # 最近成交
            recent = TradeLog.objects.filter(
                config=config,
                log_type='FILL'
            ).order_by('-created_at')[:5]

            if recent:
                print(f"\n最近成交:")
                for trade in recent:
                    print(f"  {trade.created_at.strftime('%H:%M:%S')} | "
                          f"{trade.side} {trade.quantity} @ {trade.price}")

            print("=" * 70)
            print("\n✅ 模拟完成!")

        except KeyboardInterrupt:
            print("\n\n收到停止信号")

    # 运行
    asyncio.run(async_main())


if __name__ == "__main__":
    run_eth_grid_simulation(duration=60)
