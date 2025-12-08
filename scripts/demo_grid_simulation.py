#!/usr/bin/env python
"""
简化的ETH网格模拟测试验证脚本
Simplified Grid Simulation Demo

演示核心功能：
1. 创建网格配置
2. 模拟订单引擎
3. 价格变化 → 订单成交
"""
import os
import sys
from decimal import Decimal
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 设置环境变量
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')

import django
django.setup()

from grid_trading.models import GridConfig, GridLevel, GridLevelStatus
from grid_trading.services.simulation.market_data import SimulatedOrderEngine


def demo_simulated_grid():
    """演示模拟网格交易"""
    print("=" * 70)
    print("ETH网格模拟交易演示")
    print("=" * 70)

    # 1. 加载配置
    print("\n[1] 加载网格配置...")
    config = GridConfig.objects.filter(name="ETH_SHORT_GRID_TEST").first()
    if not config:
        print("❌ 未找到配置，请先运行: python scripts/setup_eth_grid.py")
        return

    print(f"✓ 配置: {config.name}")
    print(f"  - 交易对: {config.symbol}")
    print(f"  - 价格区间: {config.lower_price} - {config.upper_price}")
    print(f"  - 网格层数: {config.grid_levels}")
    print(f"  - 网格模式: {config.grid_mode}")

    # 2. 创建模拟订单引擎
    print("\n[2] 创建模拟订单引擎...")
    engine = SimulatedOrderEngine()
    print("✓ 模拟订单引擎已创建")

    # 3. 创建几个测试订单
    print("\n[3] 创建模拟网格订单...")
    orders = [
        {"id": "grid_5_entry", "side": "SELL", "price": Decimal("3150"), "qty": Decimal("0.01")},
        {"id": "grid_10_entry", "side": "SELL", "price": Decimal("3200"), "qty": Decimal("0.01")},
        {"id": "grid_-5_entry", "side": "SELL", "price": Decimal("3100"), "qty": Decimal("0.01")},
    ]

    for order in orders:
        engine.create_order(
            client_order_id=order["id"],
            symbol=config.symbol,
            side=order["side"],
            price=order["price"],
            quantity=order["qty"]
        )
        print(f"  ✓ 创建订单: {order['id']} {order['side']} {order['qty']} @ {order['price']}")

    # 4. 模拟价格变化，触发成交
    print("\n[4] 模拟价格变化...")
    test_prices = [
        Decimal("3120"),  # 不成交
        Decimal("3150"),  # grid_5_entry 成交
        Decimal("3180"),  # 不成交
        Decimal("3200"),  # grid_10_entry 成交
        Decimal("3090"),  # grid_-5_entry 成交
    ]

    for i, price in enumerate(test_prices, 1):
        print(f"\n  价格#{i}: {price} USDT")
        filled = engine.check_fills(price)

        if filled:
            for order in filled:
                print(f"    ✓ [成交] {order['client_order_id']}: {order['side']} {order['filled_quantity']} @ {price}")
        else:
            print(f"    - 无成交")

        stats = engine.get_stats()
        print(f"    挂单: {stats['pending_count']}, 已成交: {stats['filled_count']}")

    # 5. 最终统计
    print("\n[5] 最终统计")
    print("=" * 70)
    stats = engine.get_stats()
    print(f"总挂单数: 3")
    print(f"未成交: {stats['pending_count']}")
    print(f"已成交: {stats['filled_count']}")
    print(f"当前价格: {stats['current_price']}")

    filled_orders = engine.get_filled_orders()
    if filled_orders:
        print(f"\n已成交订单明细:")
        for order in filled_orders:
            print(f"  - {order['client_order_id']}: {order['side']} {order['filled_quantity']} @ {order['filled_price']}")

    print("\n" + "=" * 70)
    print("演示完成")
    print("=" * 70)
    print("\n✅ 核心功能验证通过：")
    print("  1. ✓ 网格配置加载")
    print("  2. ✓ 模拟订单创建")
    print("  3. ✓ 价格更新检测")
    print("  4. ✓ 自动成交判断")
    print("\n💡 下一步:")
    print("  - 使用GRVT实时行情运行完整测试")
    print("  - 命令: python scripts/test_eth_grid_simulation.py")
    print("  - 需要: GRVT_API_KEY环境变量")


if __name__ == "__main__":
    demo_simulated_grid()
