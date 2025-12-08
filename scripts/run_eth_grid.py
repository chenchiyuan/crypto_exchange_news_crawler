#!/usr/bin/env python
"""
ETH 网格交易挂机测试
Long-running ETH Grid Simulation

专为挂机测试设计:
- 长时间运行 (默认24小时)
- 实时显示统计
- 自动保存日志
- 异常自动恢复
"""
import os
import sys
import time
import logging
from decimal import Decimal
from datetime import datetime
import signal

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')

import django
django.setup()

from asgiref.sync import sync_to_async
from grid_trading.models import GridConfig, GridLevel, TradeLog
from pysdk.grvt_ccxt_pro import GrvtCcxtPro
from pysdk.grvt_ccxt_env import GrvtEnv
import asyncio

# 配置日志到文件
log_file = f"logs/eth_grid_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 全局变量用于信号处理
running = True


def setup_signal_handlers():
    """设置信号处理"""
    global running

    def signal_handler(sig, frame):
        print("\n\n收到停止信号,正在优雅退出...")
        global running
        running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def run_grid_simulation(duration_hours=24):
    """运行ETH网格模拟"""
    global running
    duration_seconds = duration_hours * 3600

    # 统计数据
    stats = {
        "start_time": datetime.now(),
        "price_updates": 0,
        "total_fills": 0,
        "buy_fills": 0,
        "sell_fills": 0,
        "errors": 0,
    }

    # 环境变量
    api_key = os.getenv("GRVT_API_KEY")
    env = os.getenv("GRVT_ENV", "prod")
    instrument = os.getenv("GRVT_INSTRUMENT", "ETH_USDT_Perp")

    # 加载配置 (async包装)
    logger.info("加载网格配置...")
    config = await sync_to_async(GridConfig.objects.filter(name="ETH_SHORT_GRID_TEST").first)()

    if not config:
        raise Exception("未找到配置: ETH_SHORT_GRID_TEST")

    logger.info(f"✓ 加载配置: {config.name}")
    logger.info(f"  价格区间: {config.lower_price} - {config.upper_price}")
    logger.info(f"  网格层数: {config.grid_levels}")

    # 初始化网格 (async包装)
    logger.info("\n初始化网格层级...")
    await sync_to_async(GridLevel.objects.filter(config=config).delete)()

    lower = float(config.lower_price)
    upper = float(config.upper_price)
    levels = config.grid_levels
    grid_step = (upper - lower) / levels

    for i in range(levels + 1):
        price = Decimal(str(lower + i * grid_step))
        await sync_to_async(GridLevel.objects.create)(
            config=config,
            level_index=i - levels // 2,
            price=price,
            status='PENDING'
        )

    logger.info(f"✓ 创建了 {levels + 1} 个网格层级")

    # 连接API
    env_config = GrvtEnv.PROD if env == "prod" else GrvtEnv.TESTNET
    client = GrvtCcxtPro(env=env_config, parameters={"api_key": api_key})

    logger.info("✓ 连接 GRVT API 成功")

    # 获取初始价格
    ticker = await client.fetch_ticker(instrument)
    current_price = Decimal(str(ticker.get("last_price", "0")))

    # 创建挂单
    logger.info(f"\n当前价格: {current_price} USDT")
    logger.info("创建初始挂单...")

    # 获取所有levels
    levels_list = await sync_to_async(list)(GridLevel.objects.filter(config=config))

    created = 0
    for level in levels_list:
        if level.price > current_price:
            level.side = 'SELL'
            level.status = 'PENDING'
            await sync_to_async(level.save)()
            created += 1
        elif level.price < current_price:
            level.side = 'BUY'
            level.status = 'PENDING'
            await sync_to_async(level.save)()
            created += 1

    logger.info(f"✓ 创建了 {created} 个挂单")

    buy_count = await sync_to_async(GridLevel.objects.filter(config=config, side='BUY', status='PENDING').count)()
    sell_count = await sync_to_async(GridLevel.objects.filter(config=config, side='SELL', status='PENDING').count)()

    logger.info(f"  买单: {buy_count} 个")
    logger.info(f"  卖单: {sell_count} 个")

    # 开始监控
    logger.info(f"\n开始挂机测试 (运行 {duration_hours} 小时)")
    logger.info("按 Ctrl+C 停止\n")

    start_time = time.time()
    iteration = 0

    try:
        while running:
            # 检查运行时间
            if time.time() - start_time >= duration_seconds:
                logger.info(f"已达到运行时间 ({duration_hours} 小时),停止")
                break

            iteration += 1

            try:
                # 获取价格
                ticker = await client.fetch_ticker(instrument)
                price = Decimal(str(ticker.get("last_price", "0")))

                stats['price_updates'] += 1

                # 检查成交 - 卖单
                sell_orders = await sync_to_async(list)(
                    GridLevel.objects.filter(
                        config=config,
                        side='SELL',
                        status='PENDING',
                        price__lte=price
                    )
                )

                for order in sell_orders:
                    order.status = 'FILLED'
                    await sync_to_async(order.save)()

                    await sync_to_async(TradeLog.objects.create)(
                        config=config,
                        log_type='FILL',
                        detail={
                            'side': 'SELL',
                            'price': str(price),
                            'quantity': str(config.trade_amount),
                            'level_index': order.level_index
                        }
                    )

                    stats['total_fills'] += 1
                    stats['sell_fills'] += 1

                    logger.info(f"✓ [卖单成交] Level {order.level_index} @ {price}")

                # 检查成交 - 买单
                buy_orders = await sync_to_async(list)(
                    GridLevel.objects.filter(
                        config=config,
                        side='BUY',
                        status='PENDING',
                        price__gte=price
                    )
                )

                for order in buy_orders:
                    order.status = 'FILLED'
                    await sync_to_async(order.save)()

                    await sync_to_async(TradeLog.objects.create)(
                        config=config,
                        log_type='FILL',
                        detail={
                            'side': 'BUY',
                            'price': str(price),
                            'quantity': str(config.trade_amount),
                            'level_index': order.level_index
                        }
                    )

                    stats['total_fills'] += 1
                    stats['buy_fills'] += 1

                    logger.info(f"✓ [买单成交] Level {order.level_index} @ {price}")

                # 每60秒显示一次详细统计
                if iteration % 60 == 0:
                    elapsed = (datetime.now() - stats['start_time']).total_seconds()
                    hours = int(elapsed // 3600)
                    minutes = int((elapsed % 3600) // 60)

                    pending = await sync_to_async(GridLevel.objects.filter(config=config, status='PENDING').count)()
                    filled = await sync_to_async(GridLevel.objects.filter(config=config, status='FILLED').count)()

                    print("\n" + "=" * 70)
                    print(f"运行时间: {hours}h {minutes}m | 价格: {price} USDT")
                    print("-" * 70)
                    print(f"价格更新: {stats['price_updates']} 次")
                    print(f"总成交: {stats['total_fills']} 笔 (买: {stats['buy_fills']}, 卖: {stats['sell_fills']})")
                    print(f"挂单: {pending} | 已成交: {filled}")
                    print(f"错误: {stats['errors']} 次")
                    print("=" * 70 + "\n")

                # 每10秒简单显示
                elif iteration % 10 == 0:
                    pending = await sync_to_async(GridLevel.objects.filter(config=config, status='PENDING').count)()
                    filled = await sync_to_async(GridLevel.objects.filter(config=config, status='FILLED').count)()
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"价格: {price} | 挂单: {pending} | 已成交: {filled}")

                await asyncio.sleep(1)

            except Exception as e:
                stats['errors'] += 1
                logger.error(f"循环错误: {e}")
                await asyncio.sleep(5)

    except KeyboardInterrupt:
        logger.info("\n收到停止信号")

    finally:
        # 最终统计
        elapsed = (datetime.now() - stats['start_time']).total_seconds()
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)

        pending = await sync_to_async(GridLevel.objects.filter(config=config, status='PENDING').count)()
        filled = await sync_to_async(GridLevel.objects.filter(config=config, status='FILLED').count)()

        print("\n" + "=" * 70)
        print("最终统计")
        print("=" * 70)
        print(f"总运行时间: {hours}小时 {minutes}分钟")
        print(f"价格更新次数: {stats['price_updates']}")
        print(f"总成交笔数: {stats['total_fills']}")
        print(f"  买入: {stats['buy_fills']} 笔")
        print(f"  卖出: {stats['sell_fills']} 笔")
        print(f"当前挂单: {pending}")
        print(f"已成交: {filled}")
        print(f"错误次数: {stats['errors']}")

        # 最近成交
        recent = await sync_to_async(list)(
            TradeLog.objects.filter(
                config=config,
                log_type='FILL'
            ).order_by('-created_at')[:10]
        )

        if recent:
            print(f"\n最近10笔成交:")
            for trade in recent:
                detail = trade.detail
                print(f"  {trade.created_at.strftime('%H:%M:%S')} | "
                      f"{detail.get('side', 'N/A')} "
                      f"{detail.get('quantity', 'N/A')} @ "
                      f"{detail.get('price', 'N/A')}")

        print("=" * 70)
        print(f"\n日志已保存到: {log_file}")
        print("✅ 挂机测试完成!")


def main():
    """主函数"""
    print("=" * 70)
    print("ETH 网格交易挂机测试")
    print("=" * 70)

    # 检查环境变量
    if not os.getenv("GRVT_API_KEY"):
        print("\n❌ 缺少 GRVT_API_KEY")
        print("\n请设置:")
        print("export GRVT_API_KEY=your_key")
        print("export GRVT_ENV=prod")
        print("export GRVT_INSTRUMENT=ETH_USDT_Perp")
        return

    # 运行时间 (小时)
    duration = int(os.getenv("DURATION_HOURS", "24"))

    print(f"\n配置:")
    print(f"  环境: {os.getenv('GRVT_ENV', 'prod')}")
    print(f"  交易对: {os.getenv('GRVT_INSTRUMENT', 'ETH_USDT_Perp')}")
    print(f"  运行时间: {duration} 小时")
    print()

    # 设置信号处理
    setup_signal_handlers()

    try:
        asyncio.run(run_grid_simulation(duration_hours=duration))
    except Exception as e:
        logger.error(f"[ERROR] 运行失败: {e}", exc_info=True)


if __name__ == "__main__":
    main()
