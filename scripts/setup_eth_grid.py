#!/usr/bin/env python
"""
ETH网格交易测试配置脚本
Setup ETH Grid Trading Test Configuration
"""
import os
import sys
import django
from decimal import Decimal

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')
django.setup()

from grid_trading.models import GridConfig


def create_eth_grid_config():
    """创建ETH网格配置

    配置参数：
    - 交易对: ETHUSDT
    - 价格范围: 3000 - 3300
    - 网格层数: 20
    - 单笔开仓数量: 0.01 ETH
    - 最大持仓: 0.2 ETH
    """
    print("=" * 60)
    print("创建ETH网格交易配置")
    print("=" * 60)

    config_name = "ETH_SHORT_GRID_TEST"

    # 检查是否已存在
    existing = GridConfig.objects.filter(name=config_name).first()
    if existing:
        print(f"⚠ 配置已存在: {config_name}")
        response = input("是否删除并重新创建？(y/N): ")
        if response.lower() != 'y':
            print("取消操作")
            return None
        existing.delete()
        print("✓ 已删除旧配置")

    # 创建配置
    config = GridConfig.objects.create(
        name=config_name,
        exchange="grvt",
        symbol="ETHUSDT",
        grid_mode="SHORT",
        upper_price=Decimal("3300"),
        lower_price=Decimal("3000"),
        grid_levels=20,
        trade_amount=Decimal("0.01"),
        max_position_size=Decimal("0.2"),
        price_tick=Decimal("0.1"),
        qty_step=Decimal("0.001"),
        stop_loss_buffer_pct=Decimal("0.005"),
        refresh_interval_ms=1000,
        is_active=True
    )

    print(f"\n✓ 配置创建成功!")
    print(f"  ID: {config.id}")
    print(f"  名称: {config.name}")
    print(f"  交易对: {config.symbol}")
    print(f"  网格模式: {config.grid_mode}")
    print(f"  价格区间: {config.lower_price} - {config.upper_price}")
    print(f"  网格层数: {config.grid_levels}")
    print(f"  网格间距: {config.grid_spacing}%")
    print(f"  单笔数量: {config.trade_amount} ETH")
    print(f"  最大持仓: {config.max_position_size} ETH")
    print(f"  状态: {'激活' if config.is_active else '未激活'}")

    return config


def main():
    config = create_eth_grid_config()

    if config:
        print("\n" + "=" * 60)
        print("下一步操作:")
        print("=" * 60)
        print("\n1. 设置环境变量 (必须):")
        print("   export GRVT_API_KEY=your_api_key")
        print("   export GRVT_PRIVATE_KEY=0x...")
        print("   export GRVT_TRADING_ACCOUNT_ID=your_account_id")
        print("   export GRVT_ENV=testnet")
        print("\n2. 启动网格交易:")
        print(f"   python manage.py start_grid --config-id {config.id}")
        print("\n   或者使用启动脚本:")
        print("   python scripts/start_eth_grid.py")
        print("\n3. 查看网格详情:")
        print(f"   python manage.py grid_status --config-id {config.id}")
        print("\n4. 访问Web后台:")
        print("   http://localhost:8000/grid-trading/grids/")
        print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
