#!/usr/bin/env python
"""
ETH网格交易启动脚本
Start ETH Grid Trading
"""
import os
import sys
import django
import asyncio
from decimal import Decimal

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')
django.setup()

from grid_trading.models import GridConfig
from grid_trading.services.grid.engine import GridEngine
from grid_trading.services.exchange.factory import create_adapter


def check_env_vars():
    """检查必需的环境变量"""
    required_vars = [
        "GRVT_API_KEY",
        "GRVT_PRIVATE_KEY",
        "GRVT_TRADING_ACCOUNT_ID",
    ]

    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)

    if missing:
        print("❌ 缺少必需的环境变量:")
        for var in missing:
            print(f"   - {var}")
        print("\n请设置环境变量:")
        print("export GRVT_API_KEY=your_api_key")
        print("export GRVT_PRIVATE_KEY=0x...")
        print("export GRVT_TRADING_ACCOUNT_ID=your_account_id")
        print("export GRVT_ENV=testnet  # optional, defaults to testnet")
        return False

    print("✓ 环境变量检查通过")
    print(f"  - GRVT_API_KEY: {os.getenv('GRVT_API_KEY')[:10]}...")
    print(f"  - GRVT_PRIVATE_KEY: {os.getenv('GRVT_PRIVATE_KEY')[:10]}...")
    print(f"  - GRVT_TRADING_ACCOUNT_ID: {os.getenv('GRVT_TRADING_ACCOUNT_ID')}")
    print(f"  - GRVT_ENV: {os.getenv('GRVT_ENV', 'testnet')}")
    return True


async def test_adapter_connection():
    """测试适配器连接"""
    print("\n测试GRVT适配器连接...")
    try:
        adapter = create_adapter("grvt")
        # 测试初始化
        await adapter._ensure_initialized()

        # 获取市场信息
        if adapter._markets:
            print(f"✓ 成功连接GRVT，加载了 {len(adapter._markets)} 个交易对")

            # 查找ETH相关交易对
            eth_pairs = [symbol for symbol in adapter._markets.keys() if 'ETH' in symbol]
            if eth_pairs:
                print(f"  可用的ETH交易对: {', '.join(eth_pairs[:5])}")
        else:
            print("⚠ 已连接但未加载市场信息")

        await adapter.close()
        return True

    except Exception as e:
        print(f"❌ 适配器连接失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 60)
    print("ETH网格交易启动脚本")
    print("=" * 60)

    # 1. 检查环境变量
    if not check_env_vars():
        return

    # 2. 测试适配器连接
    print("\n" + "=" * 60)
    if not asyncio.run(test_adapter_connection()):
        return

    # 3. 查找配置
    print("\n" + "=" * 60)
    print("查找网格配置...")

    config_name = "ETH_SHORT_GRID_TEST"
    config = GridConfig.objects.filter(name=config_name, is_active=True).first()

    if not config:
        print(f"❌ 未找到激活的配置: {config_name}")
        print("\n请先运行配置脚本:")
        print("  python scripts/setup_eth_grid.py")
        return

    print(f"✓ 找到配置: {config.name}")
    print(f"  - 交易对: {config.symbol}")
    print(f"  - 价格区间: {config.lower_price} - {config.upper_price}")
    print(f"  - 网格层数: {config.grid_levels}")
    print(f"  - 网格间距: {config.grid_spacing}%")

    # 4. 启动确认
    print("\n" + "=" * 60)
    print("准备启动网格交易")
    print("=" * 60)
    print("\n⚠ 重要提示:")
    print("  1. 这是实盘交易模式，将连接真实交易所")
    print("  2. 确保您的账户有足够的ETH余额")
    print("  3. 建议先用小金额测试")
    print("  4. 按Ctrl+C可以随时停止")

    response = input("\n确认启动？(yes/no): ")
    if response.lower() != 'yes':
        print("已取消")
        return

    # 5. 启动网格引擎
    print("\n" + "=" * 60)
    print("启动网格引擎...")
    print("=" * 60)

    try:
        # 创建适配器
        adapter = create_adapter("grvt")

        # 创建引擎
        engine = GridEngine(config, exchange_adapter=adapter)

        # 启动引擎
        engine.start()

        print("\n✓ 网格引擎启动成功")
        print("\n开始运行，按Ctrl+C停止...\n")

        # 主循环
        import time
        tick_count = 0
        tick_interval = 5  # 5秒

        while True:
            try:
                tick_count += 1
                print(f"\n[Tick #{tick_count}] {time.strftime('%Y-%m-%d %H:%M:%S')}")

                # 执行一次同步
                result = engine.tick()

                # 输出统计信息
                print(f"  持仓: {result['current_position']}")
                print(f"  理想订单: {result['ideal_orders_count']}")
                print(f"  创建订单: {result['created_orders_count']}")
                print(f"  撤销订单: {result['cancelled_orders_count']}")

                if result['filtered_orders_count'] > 0:
                    print(f"  ⚠ {result['filtered_orders_count']} 个订单因持仓限制被过滤")

                time.sleep(tick_interval)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"  ❌ Tick执行出错: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(tick_interval)

    except KeyboardInterrupt:
        print("\n\n收到停止信号...")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()
        return
    finally:
        # 停止引擎
        if 'engine' in locals() and engine.running:
            print("正在停止网格引擎...")
            engine.stop()
            print("✓ 网格引擎已停止")

        # 关闭适配器
        if 'adapter' in locals():
            asyncio.run(adapter.close())


if __name__ == "__main__":
    main()
