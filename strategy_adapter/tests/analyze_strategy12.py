#!/usr/bin/env python
"""
策略12 阶梯挂单成交分析脚本

分析内容：
1. 阶梯挂单的成交单数（基于订单金额判断）
2. 止盈单的平均涨幅
3. 后续平均涨幅

注意：分析基于回测输出的订单数据，不重新计算任何逻辑
"""

import os
import sys
import json

# 设置项目路径
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_DIR)
os.chdir(PROJECT_DIR)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')
django.setup()

import pandas as pd
from decimal import Decimal
from collections import defaultdict
from strategy_adapter.strategies.doubling_position_strategy import DoublingPositionStrategy


# 金额到阶梯的映射
AMOUNT_TO_LADDER = {
    100: 1,
    200: 2,
    400: 3,
    800: 4,
    1600: 5,
}


def get_ladder_from_amount(amount: float) -> int:
    """根据金额判断是哪一档挂单"""
    amount_int = int(round(amount))
    return AMOUNT_TO_LADDER.get(amount_int, 0)


def calculate_indicators(klines_df: pd.DataFrame) -> dict:
    """计算DDPS-Z策略所需的技术指标"""
    from strategy_adapter.management.commands.run_strategy_backtest import Command

    cmd = Command()
    indicators = cmd._calculate_indicators(klines_df, 'ETHUSDT', '5m', 'csv_local', verbose=False)
    return indicators


def run_backtest_and_save(csv_paths: list, interval: str, config: dict, output_path: str = None):
    """运行回测并保存订单数据"""
    from strategy_adapter.management.commands.run_strategy_backtest import Command
    cmd = Command()

    # 加载数据
    print(f"加载数据: {len(csv_paths)} 个文件")
    klines_df = cmd._load_klines_from_csv(csv_paths[0], interval, 'microseconds')
    for csv_path_extra in csv_paths[1:]:
        df_extra = cmd._load_klines_from_csv(csv_path_extra, interval, 'microseconds')
        klines_df = pd.concat([klines_df, df_extra], ignore_index=True)

    klines_df['open_time'] = pd.to_datetime(klines_df.index.astype('int64'), unit='ms')
    klines_df.set_index('open_time', inplace=True)
    klines_df.sort_index(inplace=True)
    print(f"合并后数据量: {len(klines_df)} 根K线")

    # 计算指标
    indicators = calculate_indicators(klines_df)
    for name, series in indicators.items():
        klines_df[name] = series

    # 运行回测
    entry_config = config['strategies'][0]['entry']
    strategy = DoublingPositionStrategy(
        base_amount=Decimal(str(entry_config.get('base_amount', 100))),
        multiplier=entry_config.get('multiplier', 2.0),
        order_count=entry_config.get('order_count', 5),
        order_interval=entry_config.get('order_interval', 0.01),
        first_order_discount=entry_config.get('first_order_discount', 0.003),
        take_profit_rate=entry_config.get('take_profit_rate', 0.02),
        stop_loss_rate=entry_config.get('stop_loss_rate', 0.06)
    )

    result = strategy.run_doubling_backtest(klines_df, indicators, Decimal("10000"))

    # 保存订单数据
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                'completed_orders': result['orders'],
                'buy_fills': result['buy_fills'],
                'sell_fills': result['sell_fills'],
                'statistics': {
                    'total_trades': result['total_trades'],
                    'winning_trades': result['winning_trades'],
                    'losing_trades': result['losing_trades'],
                    'win_rate': result['win_rate'],
                    'total_profit_loss': result['total_profit_loss'],
                    'return_rate': result['return_rate'],
                }
            }, f, indent=2, default=str)
        print(f"订单数据已保存到: {output_path}")

    return result


def analyze_orders(result: dict):
    """分析回测订单数据"""
    completed_orders = result['orders']
    buy_fills = result['buy_fills']

    print("\n" + "=" * 70)
    print("策略12 阶梯挂单成交分析报告")
    print("=" * 70)

    # ============ 1. 基于金额分析阶梯成交 ============
    print("\n" + "=" * 70)
    print("【1. 阶梯挂单成交统计（基于金额判断）】")
    print("=" * 70)

    # 统计buy_fills中各阶梯成交次数
    ladder_fills = defaultdict(list)
    for fill in buy_fills:
        amount = float(fill.get('amount', 0))
        ladder = get_ladder_from_amount(amount)
        ladder_fills[ladder].append(fill)

    print(f"\n买入成交总数: {len(buy_fills)}")
    print(f"\n各阶梯买入成交:")
    print(f"{'阶梯':<10} {'金额(USDT)':<12} {'成交次数':<10} {'占比':<10}")
    print("-" * 50)

    amounts = [100, 200, 400, 800, 1600]
    for ladder in range(1, 6):
        fills = ladder_fills.get(ladder, [])
        count = len(fills)
        pct = count / len(buy_fills) * 100 if buy_fills else 0
        print(f"第{ladder}单      {amounts[ladder-1]:<12} {count:<10} {pct:.1f}%")

    # ============ 2. 基于金额分析完成订单 ============
    print("\n" + "=" * 70)
    print("【2. 完成订单统计（基于金额判断）】")
    print("=" * 70)

    ladder_orders = defaultdict(list)
    for order in completed_orders:
        # 从buy_price和quantity反推金额
        buy_price = order.get('buy_price', 0)
        quantity = order.get('quantity', 0)
        amount = buy_price * quantity
        ladder = get_ladder_from_amount(amount)
        ladder_orders[ladder].append(order)

    print(f"\n完成订单总数: {len(completed_orders)}")
    print(f"\n{'阶梯':<10} {'金额(USDT)':<12} {'成交次数':<10} {'止盈':<8} {'止损':<8} {'胜率':<10} {'平均盈亏':<15}")
    print("-" * 80)

    for ladder in range(1, 6):
        orders = ladder_orders.get(ladder, [])
        count = len(orders)
        tp = sum(1 for o in orders if o.get('close_reason') == 'take_profit')
        sl = sum(1 for o in orders if o.get('close_reason') == 'stop_loss')
        win_rate = tp / count * 100 if count > 0 else 0
        avg_pnl = sum(o.get('profit_loss', 0) for o in orders) / count if count > 0 else 0
        print(f"第{ladder}单      {amounts[ladder-1]:<12} {count:<10} {tp:<8} {sl:<8} {win_rate:.1f}%      {avg_pnl:.2f}")

    # ============ 3. 止盈单详细分析 ============
    print("\n" + "=" * 70)
    print("【3. 止盈单详细分析】")
    print("=" * 70)

    take_profit_orders = [o for o in completed_orders if o.get('close_reason') == 'take_profit']
    stop_loss_orders = [o for o in completed_orders if o.get('close_reason') == 'stop_loss']

    print(f"止盈单数: {len(take_profit_orders)}")
    print(f"止损单数: {len(stop_loss_orders)}")
    print(f"总胜率: {len(take_profit_orders)/len(completed_orders)*100:.1f}%")

    if take_profit_orders:
        tp_profits = [o.get('profit_rate', 0) for o in take_profit_orders]
        print(f"\n止盈单涨幅统计:")
        print(f"  - 平均涨幅: {sum(tp_profits)/len(tp_profits):.4f}%")
        print(f"  - 最大涨幅: {max(tp_profits):.4f}%")
        print(f"  - 最小涨幅: {min(tp_profits):.4f}%")

    # ============ 4. 综合统计 ============
    print("\n" + "=" * 70)
    print("【4. 综合统计】")
    print("=" * 70)
    print(f"总成交订单: {len(completed_orders)}")
    print(f"止盈订单: {len(take_profit_orders)} ({len(take_profit_orders)/len(completed_orders)*100:.1f}%)")
    print(f"止损订单: {len(stop_loss_orders)} ({len(stop_loss_orders)/len(completed_orders)*100:.1f}%)")
    total_pnl = sum(o.get('profit_loss', 0) for o in completed_orders)
    print(f"平均订单盈亏: {total_pnl/len(completed_orders):.4f} USDT")
    print(f"总净利润: {total_pnl:.2f} USDT")
    print(f"收益率: {result['return_rate']:.2f}%")

    # ============ 5. 验证：打印前20个买入成交订单 ============
    print("\n" + "=" * 70)
    print("【5. 验证：前20个买入成交订单】")
    print("=" * 70)
    print(f"{'序号':<6} {'订单ID':<40} {'金额':<10} {'阶梯':<8} {'价格':<12}")
    print("-" * 80)
    for i, fill in enumerate(buy_fills[:20]):
        order_id = fill.get('order_id', '')
        amount = float(fill.get('amount', 0))
        ladder = get_ladder_from_amount(amount)
        price = float(fill.get('price', 0))
        print(f"{i+1:<6} {order_id:<40} {amount:<10.0f} 第{ladder}单     {price:<12.2f}")


if __name__ == '__main__':
    import glob

    # 加载配置
    config_path = 'strategy_adapter/configs/strategy12_doubling_position.json'
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    interval = config['data_source']['interval']

    # 获取全年数据 - 优先使用5分钟K线
    csv_paths_5m = sorted(glob.glob('data/eth5m/ETHUSDT-5m-2025-*.csv'))

    if csv_paths_5m:
        csv_paths = csv_paths_5m
        print(f"使用5分钟K线数据，找到 {len(csv_paths)} 个月的数据文件:")
    else:
        print("错误: 未找到5分钟K线数据文件")
        sys.exit(1)

    for p in csv_paths:
        print(f"  - {p}")

    # 运行回测并保存订单
    output_path = 'strategy_adapter/tests/strategy12_orders.json'
    result = run_backtest_and_save(csv_paths, interval, config, output_path)

    # 分析订单数据
    analyze_orders(result)
