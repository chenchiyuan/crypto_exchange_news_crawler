#!/usr/bin/env python
"""
ETH网格模拟测试脚本
ETH Grid Simulation Test Script

使用GRVT实时行情数据，在本地模拟网格交易逻辑
不执行真实下单，仅测试网格策略
"""
import os
import sys
import django
import asyncio
import time
from decimal import Decimal
from datetime import datetime

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')
django.setup()

from grid_trading.models import GridConfig, GridLevel, GridLevelStatus, TradeLog
from grid_trading.services.simulation.market_data import (
    GRVTMarketDataSubscriber,
    SimulatedOrderEngine
)
from asgiref.sync import sync_to_async


class SimulatedGridTrader:
    """模拟网格交易器"""

    def __init__(self, config: GridConfig):
        self.config = config
        self.market_data = None
        self.order_engine = SimulatedOrderEngine()
        self.grid_levels = []
        self.running = False

        # 统计数据
        self.stats = {
            "total_fills": 0,
            "entry_fills": 0,
            "exit_fills": 0,
            "total_pnl": Decimal("0"),
        }

    async def initialize(self):
        """初始化"""
        print("\n" + "=" * 60)
        print("初始化模拟网格交易器")
        print("=" * 60)

        # 1. 初始化市场数据订阅
        print("\n1. 初始化GRVT市场数据订阅...")
        self.market_data = GRVTMarketDataSubscriber()
        await self.market_data.initialize()
        print("✓ 市场数据订阅器初始化完成")

        # 2. 加载网格层级
        print("\n2. 加载网格层级...")
        self.grid_levels = await sync_to_async(list)(
            GridLevel.objects.filter(config=self.config).order_by('level_index')
        )

        if not self.grid_levels:
            print("  未找到网格层级，创建新层级...")
            await self._initialize_grid_levels()

        print(f"✓ 加载了 {len(self.grid_levels)} 个网格层级")

        # 3. 订阅行情
        print(f"\n3. 订阅 {self.config.symbol} 实时行情...")

        # 注册价格更新回调
        self.market_data.on_price_update(self._on_price_update)

        # 订阅ticker
        await self.market_data.subscribe_ticker(self.config.symbol)
        print(f"✓ 成功订阅 {self.config.symbol} Ticker数据")

        # 等待首次价格
        print("\n等待首次价格数据...")
        for i in range(30):  # 最多等待30秒
            await asyncio.sleep(1)
            if self.market_data.get_last_price():
                break

        current_price = self.market_data.get_last_price()
        if current_price:
            print(f"✓ 接收到首次价格: {current_price}")
        else:
            print("⚠ 未能获取价格数据，将继续等待...")

    async def _initialize_grid_levels(self):
        """初始化网格层级（使用sync_to_async）"""
        def _create_levels():
            from grid_trading.services.grid.engine import GridEngine
            engine = GridEngine(self.config)
            return engine.initialize_grid()

        self.grid_levels = await sync_to_async(_create_levels)()
        print(f"✓ 创建了 {len(self.grid_levels)} 个网格层级")

    def _on_price_update(self, price: Decimal):
        """价格更新回调"""
        # 检查订单是否成交
        filled_orders = self.order_engine.check_fills(price)

        for order in filled_orders:
            self._handle_order_filled(order)

    def _handle_order_filled(self, order: dict):
        """处理订单成交（同步函数，避免async/ORM冲突）"""
        # 从client_order_id中提取level_index
        # 格式: "grid_{level_index}_{entry|exit}"
        parts = order["client_order_id"].split("_")
        if len(parts) < 3:
            return

        level_index = int(parts[1])
        intent = parts[2]  # 'entry' or 'exit'

        # 查找对应的GridLevel
        level = next((l for l in self.grid_levels if l.level_index == level_index), None)
        if not level:
            return

        # 更新统计
        self.stats["total_fills"] += 1

        # 根据意图更新层级状态
        if intent == "entry":
            # 开仓成交
            level.status = GridLevelStatus.POSITION_OPEN
            level.entry_filled_price = order["filled_price"]
            level.save()

            self.stats["entry_fills"] += 1

            # 记录事件
            TradeLog.log_fill(
                self.config,
                f"[模拟] 开仓成交: 层级={level_index}, 价格={order['filled_price']}",
                level_index=level_index
            )

            print(f"\n✓ [开仓成交] 层级{level_index}: {order['side']} {order['quantity']} @ {order['filled_price']}")

            # 自动创建平仓订单
            self._create_exit_order(level)

        elif intent == "exit":
            # 平仓成交
            entry_price = level.entry_filled_price or level.price
            exit_price = order["filled_price"]

            # 计算盈亏
            if self.config.grid_mode == "SHORT":
                pnl = (entry_price - exit_price) * order["quantity"]
            else:
                pnl = (exit_price - entry_price) * order["quantity"]

            self.stats["exit_fills"] += 1
            self.stats["total_pnl"] += pnl

            # 重置层级状态
            level.status = GridLevelStatus.IDLE
            level.entry_filled_price = None
            level.save()

            # 记录事件
            TradeLog.log_fill(
                self.config,
                f"[模拟] 平仓成交: 层级={level_index}, 价格={exit_price}, 盈亏={pnl:.4f}",
                level_index=level_index
            )

            print(f"\n✓ [平仓成交] 层级{level_index}: {order['side']} {order['quantity']} @ {exit_price}, PnL={pnl:.4f} USDT")

            # 重新创建开仓订单
            self._create_entry_order(level)

    def _create_entry_order(self, level: GridLevel):
        """创建开仓订单"""
        order_id = f"grid_{level.level_index}_entry"

        self.order_engine.create_order(
            client_order_id=order_id,
            symbol=self.config.symbol,
            side=level.side,
            price=level.price,
            quantity=self.config.trade_amount,
        )

        level.status = GridLevelStatus.ENTRY_WORKING
        level.save()

    def _create_exit_order(self, level: GridLevel):
        """创建平仓订单"""
        order_id = f"grid_{level.level_index}_exit"

        # 计算平仓价格（网格间距的对侧）
        spacing = self.config.grid_spacing_pct / Decimal("100")

        if self.config.grid_mode == "SHORT":
            # 做空: 在下方平仓
            exit_price = level.price * (Decimal("1") - spacing)
            exit_side = "BUY"
        else:
            # 做多: 在上方平仓
            exit_price = level.price * (Decimal("1") + spacing)
            exit_side = "SELL"

        self.order_engine.create_order(
            client_order_id=order_id,
            symbol=self.config.symbol,
            side=exit_side,
            price=exit_price,
            quantity=self.config.trade_amount,
        )

        level.status = GridLevelStatus.EXIT_WORKING
        level.save()

    def place_initial_orders(self):
        """放置初始订单"""
        print("\n放置初始网格订单...")

        current_price = self.market_data.get_last_price()
        if not current_price:
            print("⚠ 无法获取当前价格，跳过初始订单")
            return

        print(f"当前价格: {current_price}")

        count = 0
        for level in self.grid_levels:
            # 只在空闲层级创建开仓订单
            if level.status == GridLevelStatus.IDLE:
                self._create_entry_order(level)
                count += 1

        print(f"✓ 创建了 {count} 个初始订单")

    async def run(self):
        """运行模拟交易"""
        self.running = True

        print("\n" + "=" * 60)
        print("开始模拟网格交易")
        print("=" * 60)
        print("\n按Ctrl+C停止\n")

        # 放置初始订单
        self.place_initial_orders()

        tick_count = 0

        try:
            while self.running:
                tick_count += 1
                await asyncio.sleep(5)  # 每5秒检查一次

                # 获取当前状态
                current_price = self.market_data.get_last_price()
                order_stats = self.order_engine.get_stats()

                # 显示状态
                if tick_count % 6 == 0:  # 每30秒显示一次详细信息
                    print("\n" + "-" * 60)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 网格状态")
                    print("-" * 60)
                    print(f"当前价格: {current_price}")
                    print(f"挂单数量: {order_stats['pending_count']}")
                    print(f"总成交次数: {self.stats['total_fills']}")
                    print(f"  - 开仓: {self.stats['entry_fills']}")
                    print(f"  - 平仓: {self.stats['exit_fills']}")
                    print(f"累计盈亏: {self.stats['total_pnl']:.4f} USDT")
                    print("-" * 60)

        except KeyboardInterrupt:
            print("\n\n收到停止信号...")
        finally:
            self.running = False
            await self.cleanup()

    async def cleanup(self):
        """清理资源"""
        print("\n清理资源...")

        # 显示最终统计
        print("\n" + "=" * 60)
        print("最终统计")
        print("=" * 60)
        print(f"总成交次数: {self.stats['total_fills']}")
        print(f"开仓成交: {self.stats['entry_fills']}")
        print(f"平仓成交: {self.stats['exit_fills']}")
        print(f"累计盈亏: {self.stats['total_pnl']:.4f} USDT")
        print("=" * 60)

        # 关闭市场数据订阅
        if self.market_data:
            await self.market_data.close()

        print("✓ 清理完成")


async def main():
    """主函数"""
    print("=" * 60)
    print("ETH网格模拟测试")
    print("=" * 60)

    # 检查API KEY
    if not os.getenv("GRVT_API_KEY"):
        print("\n❌ 缺少环境变量: GRVT_API_KEY")
        print("\n请设置:")
        print("export GRVT_API_KEY=your_api_key")
        print("export GRVT_ENV=testnet  # optional")
        return

    print(f"✓ GRVT_API_KEY: {os.getenv('GRVT_API_KEY')[:10]}...")
    print(f"✓ GRVT_ENV: {os.getenv('GRVT_ENV', 'testnet')}")

    # 加载网格配置（同步操作）
    config_name = "ETH_SHORT_GRID_TEST"
    config = await sync_to_async(GridConfig.objects.filter(name=config_name).first)()

    if not config:
        print(f"\n❌ 未找到配置: {config_name}")
        print("\n请先运行: python scripts/setup_eth_grid.py")
        return

    print(f"\n✓ 找到配置: {config.name}")
    print(f"  - 交易对: {config.symbol}")
    print(f"  - 价格区间: {config.lower_price} - {config.upper_price}")
    print(f"  - 网格层数: {config.grid_levels}")
    print(f"  - 网格模式: {config.grid_mode}")

    # 创建并运行模拟交易器
    trader = SimulatedGridTrader(config)
    await trader.initialize()
    await trader.run()


if __name__ == "__main__":
    asyncio.run(main())
