#!/usr/bin/env python
"""
策略14 卖出后上涨情况分析脚本

分析内容：
1. 卖出点之后的最高涨幅、最少涨幅、平均涨幅
2. 卖出后延续上涨的概率
3. 持续上涨的K线数量（最多、最少、平均）

注意：分析基于回测输出的订单数据，不重新计算任何逻辑
"""

import os
import sys
import json
import glob
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

# 设置项目路径
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_DIR)
os.chdir(PROJECT_DIR)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')
django.setup()

import pandas as pd
import numpy as np


def load_klines_from_csv(csv_path: str, interval: str, timestamp_unit: str = 'microseconds'):
    """从CSV加载K线数据"""
    from ddps_z.datasources.csv_fetcher import CSVFetcher

    fetcher = CSVFetcher(csv_path=csv_path, interval=interval, timestamp_unit=timestamp_unit)
    klines = fetcher.fetch(symbol='', interval=interval, limit=0)  # 0表示不限制

    # 转换为DataFrame
    data = []
    for kline in klines:
        data.append({
            'open_time': pd.Timestamp(kline.timestamp, unit='ms', tz='UTC'),
            'open': float(kline.open),
            'high': float(kline.high),
            'low': float(kline.low),
            'close': float(kline.close),
            'volume': float(kline.volume)
        })

    df = pd.DataFrame(data)
    df = df.set_index('open_time')
    return df


def load_all_klines(data_dir: str, interval: str):
    """加载目录下所有CSV文件的K线数据"""
    csv_files = sorted(glob.glob(os.path.join(data_dir, '*.csv')))
    if not csv_files:
        raise ValueError(f"目录下未找到CSV文件: {data_dir}")

    print(f"发现 {len(csv_files)} 个数据文件:")
    for f in csv_files:
        print(f"  - {os.path.basename(f)}")

    all_klines = []
    for csv_path in csv_files:
        df = load_klines_from_csv(csv_path, interval)
        print(f"  加载: {os.path.basename(csv_path)} - {len(df)} 根K线")
        all_klines.append(df)

    # 合并所有数据
    combined_df = pd.concat(all_klines, ignore_index=False)
    combined_df = combined_df[~combined_df.index.duplicated(keep='first')]
    combined_df = combined_df.sort_index()

    print(f"\n合并后总数据量: {len(combined_df)} 根K线")
    print(f"时间范围: {combined_df.index[0]} ~ {combined_df.index[-1]}")
    return combined_df


def calculate_indicators(klines_df: pd.DataFrame, symbol: str, interval: str, market_type: str):
    """计算DDPS-Z策略所需的技术指标"""
    from strategy_adapter.management.commands.run_strategy_backtest import Command

    cmd = Command()
    indicators = cmd._calculate_indicators(klines_df, symbol, interval, market_type, verbose=False)
    return indicators


def run_backtest(klines_df: pd.DataFrame, indicators: dict, config: dict):
    """运行策略14回测"""
    from strategy_adapter.strategies.optimized_entry_strategy import OptimizedEntryStrategy
    from decimal import Decimal

    entry_config = config['strategies'][0]['entry']
    strategy = OptimizedEntryStrategy(
        base_amount=Decimal(str(entry_config.get('base_amount', 100))),
        multiplier=entry_config.get('multiplier', 3.0),
        order_count=entry_config.get('order_count', 5),
        first_gap=entry_config.get('first_gap', 0.04),
        interval=entry_config.get('interval', 0.01),
        first_order_discount=entry_config.get('first_order_discount', 0.02),
        take_profit_rate=entry_config.get('take_profit_rate', 0.02),
        stop_loss_rate=entry_config.get('stop_loss_rate', 0.06)
    )

    result = strategy.run_optimized_backtest(
        klines_df=klines_df,
        indicators=indicators,
        initial_capital=Decimal("10000")
    )

    return result


def analyze_post_exit_movement(klines_df: pd.DataFrame, orders: list):
    """
    分析卖出后的上涨情况

    对于每个卖出订单：
    1. 找到卖出点对应的K线位置
    2. 查找后续K线，直到价格回落到卖出点以下
    3. 计算后续最高涨幅、最少涨幅、平均涨幅
    4. 统计延续上涨的概率和K线数量
    """
    # 将K线数据转为list便于索引
    klines_list = klines_df.reset_index()
    klines_list['open_time'] = pd.to_datetime(klines_list['open_time'])
    klines_list = klines_list.to_dict('records')

    # 建立时间戳到K线索引的映射
    timestamp_to_idx = {}
    for idx, kline in enumerate(klines_list):
        ts = int(kline['open_time'].timestamp() * 1000)
        timestamp_to_idx[ts] = idx

    results = {
        'take_profit_orders': [],  # 止盈订单分析结果
        'stop_loss_orders': [],    # 止损订单分析结果
        'all_orders': [],          # 所有订单分析结果
    }

    for order in orders:
        sell_timestamp = order.get('sell_timestamp')
        sell_price = order.get('sell_price')
        close_reason = order.get('close_reason', 'unknown')

        if not sell_timestamp or not sell_price:
            continue

        # 找到卖出点对应的K线索引
        # 使用最接近的时间戳
        sell_idx = None
        for idx, kline in enumerate(klines_list):
            ts = int(kline['open_time'].timestamp() * 1000)
            if ts <= sell_timestamp:
                sell_idx = idx

        if sell_idx is None or sell_idx >= len(klines_list) - 1:
            continue

        # 获取卖出价格
        sell_price = float(sell_price)

        # 分析后续K线
        post_exit_analysis = analyze_single_exit(
            klines_list=klines_list,
            sell_idx=sell_idx,
            sell_price=sell_price
        )

        if post_exit_analysis:
            order_analysis = {
                'order_id': order.get('buy_order_id', ''),
                'buy_price': order.get('buy_price', 0),
                'sell_price': sell_price,
                'sell_timestamp': sell_timestamp,
                'close_reason': close_reason,
                'profit_rate': order.get('profit_rate', 0),
                **post_exit_analysis
            }

            results['all_orders'].append(order_analysis)

            if close_reason == 'take_profit':
                results['take_profit_orders'].append(order_analysis)
            elif close_reason == 'stop_loss':
                results['stop_loss_orders'].append(order_analysis)

    return results


def analyze_single_exit(klines_list: list, sell_idx: int, sell_price: float):
    """
    分析单个卖出点之后的行情

    计算：
    1. 后续最高价相对于卖出价的涨幅
    2. 后续是否有延续上涨
    3. 延续上涨的K线数量
    """
    if sell_idx >= len(klines_list) - 1:
        return None

    # 查找后续K线，直到价格回落到卖出点以下
    # 或者达到数据末尾
    max_price = sell_price
    max_price_idx = sell_idx
    continued_rise_count = 0
    total_rise_klines = 0
    price_never_dropped = True

    for i in range(sell_idx + 1, len(klines_list)):
        kline = klines_list[i]
        high = kline['high']
        low = kline['low']
        close = kline['close']

        # 记录后续最高的high
        if high > max_price:
            max_price = high
            max_price_idx = i

        # 检查是否回落到卖出点以下
        if low <= sell_price and i > sell_idx + 1:
            price_never_dropped = False
            break

        # 检查是否延续上涨（close > sell_price）
        if close > sell_price:
            total_rise_klines += 1

        # 检查是否还有机会继续上涨
        if high > sell_price:
            continued_rise_count += 1

    # 计算最大涨幅
    max_increase_pct = (max_price - sell_price) / sell_price * 100 if max_price > sell_price else 0

    # 判断是否延续上涨
    # 条件：后续有任意K线的close > 卖出价
    continued_rise = max_price > sell_price

    # 持续上涨的K线数量（从卖出点开始，close连续高于卖出价的K线数）
    consecutive_rise_klines = 0
    for i in range(sell_idx + 1, len(klines_list)):
        kline = klines_list[i]
        close = kline['close']
        if close > sell_price:
            consecutive_rise_klines += 1
        else:
            break

    return {
        'max_price_after_exit': max_price,
        'max_increase_pct': max_increase_pct,
        'max_price_idx': max_price_idx,
        'max_price_klines_after': max_price_idx - sell_idx,
        'continued_rise': continued_rise,
        'consecutive_rise_klines': consecutive_rise_klines,
        'total_rise_klines': total_rise_klines,
        'price_never_dropped': price_never_dropped,
    }


def calculate_statistics(orders: list):
    """计算统计数据"""
    if not orders:
        return None

    # 提取数据
    max_increases = [o['max_increase_pct'] for o in orders]
    kline_counts = [o['max_price_klines_after'] for o in orders]
    consecutive_klines = [o['consecutive_rise_klines'] for o in orders]

    continued_rise_count = sum(1 for o in orders if o['continued_rise'])
    never_dropped_count = sum(1 for o in orders if o['price_never_dropped'])

    return {
        'total_orders': len(orders),
        'continued_rise_count': continued_rise_count,
        'continued_rise_rate': continued_rise_count / len(orders) * 100 if orders else 0,
        'never_dropped_count': never_dropped_count,
        'never_dropped_rate': never_dropped_count / len(orders) * 100 if orders else 0,
        'max_increase': {
            'max': max(max_increases) if max_increases else 0,
            'min': min(max_increases) if max_increases else 0,
            'avg': sum(max_increases) / len(max_increases) if max_increases else 0,
            'median': sorted(max_increases)[len(max_increases) // 2] if max_increases else 0,
        },
        'kline_count': {
            'max': max(kline_counts) if kline_counts else 0,
            'min': min(kline_counts) if kline_counts else 0,
            'avg': sum(kline_counts) / len(kline_counts) if kline_counts else 0,
            'median': sorted(kline_counts)[len(kline_counts) // 2] if kline_counts else 0,
        },
        'consecutive_klines': {
            'max': max(consecutive_klines) if consecutive_klines else 0,
            'min': min(consecutive_klines) if consecutive_klines else 0,
            'avg': sum(consecutive_klines) / len(consecutive_klines) if consecutive_klines else 0,
            'median': sorted(consecutive_klines)[len(consecutive_klines) // 2] if consecutive_klines else 0,
        },
    }


def generate_report(all_stats: dict, tp_stats: dict, sl_stats: dict, analysis: dict = None, output_path: str = None):
    """生成分析报告"""
    lines = []
    lines.append("=" * 80)
    lines.append("策略14 卖出后上涨情况分析报告")
    lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 80)

    # ============== 1. 整体统计 ==============
    lines.append("")
    lines.append("=" * 80)
    lines.append("【1. 整体统计（所有卖出订单）】")
    lines.append("=" * 80)

    if all_stats:
        lines.append(f"\n总卖出订单数: {all_stats['total_orders']}")
        lines.append(f"\n一、卖出后延续上涨情况:")
        lines.append(f"   - 延续上涨次数: {all_stats['continued_rise_count']} / {all_stats['total_orders']}")
        lines.append(f"   - 延续上涨概率: {all_stats['continued_rise_rate']:.2f}%")
        lines.append(f"   - 价格未跌破卖出点次数: {all_stats['never_dropped_count']} / {all_stats['total_orders']}")
        lines.append(f"   - 价格未跌破概率: {all_stats['never_dropped_rate']:.2f}%")

        lines.append(f"\n二、后续最高涨幅统计:")
        lines.append(f"   - 最大涨幅: {all_stats['max_increase']['max']:.4f}%")
        lines.append(f"   - 最小涨幅: {all_stats['max_increase']['min']:.4f}%")
        lines.append(f"   - 平均涨幅: {all_stats['max_increase']['avg']:.4f}%")
        lines.append(f"   - 中位数涨幅: {all_stats['max_increase']['median']:.4f}%")

        lines.append(f"\n三、达到最高点所需K线数:")
        lines.append(f"   - 最多: {all_stats['kline_count']['max']} 根K线")
        lines.append(f"   - 最少: {all_stats['kline_count']['min']} 根K线")
        lines.append(f"   - 平均: {all_stats['kline_count']['avg']:.2f} 根K线")
        lines.append(f"   - 中位数: {all_stats['kline_count']['median']:.1f} 根K线")

        lines.append(f"\n四、连续高于卖出价的K线数:")
        lines.append(f"   - 最多: {all_stats['consecutive_klines']['max']} 根K线")
        lines.append(f"   - 最少: {all_stats['consecutive_klines']['min']} 根K线")
        lines.append(f"   - 平均: {all_stats['consecutive_klines']['avg']:.2f} 根K线")
        lines.append(f"   - 中位数: {all_stats['consecutive_klines']['median']:.1f} 根K线")
    else:
        lines.append("无订单数据")

    # ============== 2. 止盈订单分析 ==============
    lines.append("")
    lines.append("=" * 80)
    lines.append("【2. 止盈订单（take_profit）分析】")
    lines.append("=" * 80)

    if tp_stats:
        lines.append(f"\n止盈订单数: {tp_stats['total_orders']}")
        lines.append(f"\n一、卖出后延续上涨情况:")
        lines.append(f"   - 延续上涨次数: {tp_stats['continued_rise_count']} / {tp_stats['total_orders']}")
        lines.append(f"   - 延续上涨概率: {tp_stats['continued_rise_rate']:.2f}%")
        lines.append(f"   - 价格未跌破卖出点次数: {tp_stats['never_dropped_count']} / {tp_stats['total_orders']}")
        lines.append(f"   - 价格未跌破概率: {tp_stats['never_dropped_rate']:.2f}%")

        lines.append(f"\n二、后续最高涨幅统计:")
        lines.append(f"   - 最大涨幅: {tp_stats['max_increase']['max']:.4f}%")
        lines.append(f"   - 最小涨幅: {tp_stats['max_increase']['min']:.4f}%")
        lines.append(f"   - 平均涨幅: {tp_stats['max_increase']['avg']:.4f}%")
        lines.append(f"   - 中位数涨幅: {tp_stats['max_increase']['median']:.4f}%")

        lines.append(f"\n三、达到最高点所需K线数:")
        lines.append(f"   - 最多: {tp_stats['kline_count']['max']} 根K线")
        lines.append(f"   - 最少: {tp_stats['kline_count']['min']} 根K线")
        lines.append(f"   - 平均: {tp_stats['kline_count']['avg']:.2f} 根K线")
    else:
        lines.append("无止盈订单数据")

    # ============== 3. 止损订单分析 ==============
    lines.append("")
    lines.append("=" * 80)
    lines.append("【3. 止损订单（stop_loss）分析】")
    lines.append("=" * 80)

    if sl_stats:
        lines.append(f"\n止损订单数: {sl_stats['total_orders']}")
        lines.append(f"\n一、卖出后延续上涨情况:")
        lines.append(f"   - 延续上涨次数: {sl_stats['continued_rise_count']} / {sl_stats['total_orders']}")
        lines.append(f"   - 延续上涨概率: {sl_stats['continued_rise_rate']:.2f}%")

        lines.append(f"\n二、后续最高涨幅统计:")
        lines.append(f"   - 最大涨幅: {sl_stats['max_increase']['max']:.4f}%")
        lines.append(f"   - 最小涨幅: {sl_stats['max_increase']['min']:.4f}%")
        lines.append(f"   - 平均涨幅: {sl_stats['max_increase']['avg']:.4f}%")
        lines.append(f"   - 中位数涨幅: {sl_stats['max_increase']['median']:.4f}%")
    else:
        lines.append("无止损订单数据")

    # ============== 4. 涨幅分布 ==============
    lines.append("")
    lines.append("=" * 80)
    lines.append("【4. 后续涨幅分布（止盈订单）】")
    lines.append("=" * 80)

    if all_stats and tp_stats and analysis:
        # 收集止盈订单的涨幅
        lines.append("\n后续涨幅分布:")

        # 计算各区间的订单数量
        tp_orders = tp_stats['total_orders']
        max_increases = [o['max_increase_pct'] for o in analysis.get('take_profit_orders', [])]

        range_0_05 = sum(1 for x in max_increases if 0 <= x < 0.5)
        range_05_1 = sum(1 for x in max_increases if 0.5 <= x < 1)
        range_1_2 = sum(1 for x in max_increases if 1 <= x < 2)
        range_2_3 = sum(1 for x in max_increases if 2 <= x < 3)
        range_3_plus = sum(1 for x in max_increases if x >= 3)

        lines.append(f"  0% ~ 0.5%:  {'*' * range_0_05} ({range_0_05}/{tp_orders} = {range_0_05/tp_orders*100:.1f}%)" if tp_orders > 0 else "  0% ~ 0.5%:  无数据")
        lines.append(f"  0.5% ~ 1%:  {'*' * range_05_1} ({range_05_1}/{tp_orders} = {range_05_1/tp_orders*100:.1f}%)" if tp_orders > 0 else "  0.5% ~ 1%:  无数据")
        lines.append(f"  1% ~ 2%:   {'*' * range_1_2} ({range_1_2}/{tp_orders} = {range_1_2/tp_orders*100:.1f}%)" if tp_orders > 0 else "  1% ~ 2%:   无数据")
        lines.append(f"  2% ~ 3%:   {'*' * range_2_3} ({range_2_3}/{tp_orders} = {range_2_3/tp_orders*100:.1f}%)" if tp_orders > 0 else "  2% ~ 3%:   无数据")
        lines.append(f"  3% 以上:   {'*' * range_3_plus} ({range_3_plus}/{tp_orders} = {range_3_plus/tp_orders*100:.1f}%)" if tp_orders > 0 else "  3% 以上:   无数据")

    # ============== 5. 结论与建议 ==============
    lines.append("")
    lines.append("=" * 80)
    lines.append("【5. 结论与建议】")
    lines.append("=" * 80)

    if all_stats:
        lines.append("")
        lines.append(f"基于 {all_stats['total_orders']} 个卖出订单的分析，得出以下结论：")
        lines.append("")
        lines.append(f"1. 卖出后延续上涨的概率: {all_stats['continued_rise_rate']:.2f}%")
        if all_stats['continued_rise_rate'] > 50:
            lines.append("   → 超过一半的情况会延续上涨，建议考虑提高止盈目标")
        elif all_stats['continued_rise_rate'] > 30:
            lines.append("   → 有一定概率延续上涨，可以考虑适度提高止盈")
        else:
            lines.append("   → 延续上涨概率较低，当前止盈设置合理")

        lines.append("")
        lines.append(f"2. 后续平均最高涨幅: {all_stats['max_increase']['avg']:.4f}%")
        if all_stats['max_increase']['avg'] > 3:
            lines.append("   → 平均有较大上涨空间，建议提高止盈至3%以上")
        elif all_stats['max_increase']['avg'] > 2:
            lines.append("   → 平均有一定上涨空间，可以考虑2.5%-3%的止盈")
        else:
            lines.append("   → 平均上涨空间有限，当前2%止盈合理")

        lines.append("")
        lines.append(f"3. 达到最高点平均需要: {all_stats['kline_count']['avg']:.2f} 根K线")
        lines.append(f"   → 中位数需要: {all_stats['kline_count']['median']:.1f} 根K线")
        lines.append("   → 约为: {:.1f} 小时（5分钟K线）".format(all_stats['kline_count']['avg'] * 5 / 60))

    # 输出报告
    report = "\n".join(lines)
    print(report)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n报告已保存到: {output_path}")

    return report


def main():
    import argparse

    parser = argparse.ArgumentParser(description='分析策略14卖出后的上涨情况')
    parser.add_argument('--data-dir', type=str, default='data/eth5m',
                        help='K线数据目录')
    parser.add_argument('--template', type=str,
                        default='strategy_adapter/configs/strategy14_optimized_entry.json',
                        help='策略配置文件路径')
    parser.add_argument('--output', type=str,
                        help='输出报告路径')

    args = parser.parse_args()

    # 加载配置
    print("=" * 80)
    print("策略14 卖出后上涨情况分析")
    print("=" * 80)
    print(f"\n配置模板: {args.template}")
    print(f"数据目录: {args.data_dir}")

    with open(args.template, 'r', encoding='utf-8') as f:
        config = json.load(f)

    interval = config['data_source']['interval']
    print(f"K线周期: {interval}")

    # 加载K线数据
    print("\n" + "-" * 40)
    print("加载K线数据...")
    klines_df = load_all_klines(args.data_dir, interval)

    # 计算指标
    print("\n" + "-" * 40)
    print("计算技术指标...")
    indicators = calculate_indicators(klines_df, 'ETHUSDT', interval, 'csv_local')
    for name, series in indicators.items():
        klines_df[name] = series
    print(f"指标计算完成: {len(indicators)} 个指标")

    # 运行回测
    print("\n" + "-" * 40)
    print("运行策略14回测...")
    result = run_backtest(klines_df, indicators, config)
    print(f"回测完成: {result['total_trades']} 个完成订单, {result['remaining_holdings']} 个持仓")

    # 分析卖出后上涨情况
    print("\n" + "-" * 40)
    print("分析卖出后上涨情况...")
    orders = result['orders']
    analysis = analyze_post_exit_movement(klines_df, orders)

    # 计算统计
    all_stats = calculate_statistics(analysis['all_orders'])
    tp_stats = calculate_statistics(analysis['take_profit_orders'])
    sl_stats = calculate_statistics(analysis['stop_loss_orders'])

    # 生成报告
    print("\n" + "=" * 80)
    generate_report(all_stats, tp_stats, sl_stats, analysis, args.output)

    # 保存详细数据
    detail_output = args.output.replace('.md', '_detail.json') if args.output else 'strategy_adapter/tests/exit_analysis_detail.json'
    with open(detail_output, 'w', encoding='utf-8') as f:
        json.dump({
            'all_orders_analysis': analysis['all_orders'],
            'take_profit_analysis': analysis['take_profit_orders'],
            'stop_loss_analysis': analysis['stop_loss_orders'],
        }, f, indent=2, ensure_ascii=False)
    print(f"\n详细数据已保存到: {detail_output}")


if __name__ == '__main__':
    main()
