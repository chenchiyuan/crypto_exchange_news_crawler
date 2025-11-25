#!/usr/bin/env python
"""
价格分析与VWAP综合分析脚本

结合四峰分析和VWAP分析，为交易决策提供综合参考。

用法:
    python price_vwap_analysis.py --symbol eth --interval 4h --limit 100
"""
import sys
import os
import argparse
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from example_four_peaks import analyze_four_peaks
from calculate_vwap import VWAPCalculator
from vp_squeeze.services.binance_kline_service import fetch_klines


def analyze_price_and_vwap(symbol: str, interval: str = '4h', limit: int = 100):
    """
    综合分析价格位置和VWAP

    Args:
        symbol: 交易对符号
        interval: 时间周期
        limit: K线数量

    Returns:
        分析结果字典
    """
    # 获取K线数据
    klines = fetch_klines(symbol=symbol, interval=interval, limit=limit)
    if not klines:
        raise ValueError(f"获取{symbol}的K线数据失败")

    # 四峰分析
    clusters, key_levels, current_price = analyze_four_peaks(
        symbol=symbol,
        interval=interval,
        limit=limit
    )

    # VWAP分析
    vwap_calculator = VWAPCalculator(klines)
    vwap_data = vwap_calculator.calculate_vwap(limit=limit)

    return {
        'symbol': symbol,
        'interval': interval,
        'current_price': current_price,
        'vwap': vwap_data['vwap'],
        'vwap_deviation': vwap_data['deviation_pct'],
        'key_levels': key_levels,
        'clusters': clusters,
        'total_volume': vwap_data['total_volume'],
        'daily_vwap': vwap_data['daily_vwap']
    }


def print_analysis_report(analysis: dict):
    """打印分析报告"""
    symbol = analysis['symbol'].upper()
    interval = analysis['interval']

    print(f"\n{'='*80}")
    print(f"{symbol} 综合价格分析报告 ({interval})")
    print(f"{'='*80}")

    # 当前价格和VWAP
    print(f"\n【价格位置分析】")
    print(f"  当前价格: ${analysis['current_price']:.2f}")
    print(f"  VWAP成本: ${analysis['vwap']:.2f}")
    print(f"  偏离VWAP: {analysis['vwap_deviation']:+.2f}%")

    # 价格位置判断
    vwap_status = "💰 价格低于成本 (多头有利)" if analysis['vwap_deviation'] > 0 else "📈 价格高于成本 (空头有利)"
    print(f"  VWAP状态: {vwap_status}")

    # 关键价位分析
    print(f"\n【关键价位分析】")
    key_levels = analysis['key_levels']
    if key_levels:
        if 'resistance1' in key_levels:
            r1 = key_levels['resistance1']
            print(f"  压力位R1: ${r1.price:.2f} ({r1.distance_pct:+.1f}%)")
        if 'resistance2' in key_levels:
            r2 = key_levels['resistance2']
            print(f"  压力位R2: ${r2.price:.2f} ({r2.distance_pct:+.1f}%)")
        if 'support1' in key_levels:
            s1 = key_levels['support1']
            print(f"  支撑位S1: ${s1.price:.2f} ({s1.distance_pct:.1f}%)")
        if 'support2' in key_levels:
            s2 = key_levels['support2']
            print(f"  支撑位S2: ${s2.price:.2f} ({s2.distance_pct:.1f}%)")

    # 交易建议
    print(f"\n【交易建议】")

    # 基于VWAP的建议
    if analysis['vwap_deviation'] > 3:
        vwap_advice = "价格显著高于成本，可以考虑空头仓位"
    elif analysis['vwap_deviation'] < -3:
        vwap_advice = "价格显著低于成本，可以考虑多头仓位"
    else:
        vwap_advice = "价格接近VWAP，建议观望"
    print(f"  基于VWAP: {vwap_advice}")

    # 基于关键价位的建议
    if 'support1' in key_levels:
        s1_dist = abs(key_levels['support1'].distance_pct)
        if s1_dist < 1:
            advice = "接近支撑位，注意反弹机会"
        else:
            advice = f"距离支撑位还有{s1_dist:.1f}%"
        print(f"  基于支撑位: {advice}")

    # 成交量分析
    print(f"\n【成交量分析】")
    print(f"  总成交量: {analysis['total_volume']:,.0f}")
    print(f"  平均成交量: {analysis['total_volume']/len(analysis['daily_vwap']):,.0f}/天")

    # 最近7天VWAP趋势
    print(f"\n【VWAP趋势 (最近7天)】")
    sorted_daily = sorted(analysis['daily_vwap'].items(), reverse=True)[:7]
    for date, vwap in sorted_daily:
        print(f"  {date}: ${vwap:.2f}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='价格分析与VWAP综合分析',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  %(prog)s --symbol eth --interval 4h --limit 100
  %(prog)s --symbol btc --interval 1h --limit 200
        '''
    )

    parser.add_argument('--symbol', type=str, required=True,
                       help='交易对符号 (如: eth, btc, bnb)')
    parser.add_argument('--interval', type=str, default='4h',
                       choices=['15m', '1h', '4h', '1d'],
                       help='时间周期 (默认: 4h)')
    parser.add_argument('--limit', type=int, default=100,
                       help='K线数量限制 (默认: 100)')

    args = parser.parse_args()

    try:
        # 执行分析
        print(f"执行 {args.symbol.upper()} 综合分析...")
        analysis = analyze_price_and_vwap(
            symbol=args.symbol,
            interval=args.interval,
            limit=args.limit
        )

        # 打印报告
        print_analysis_report(analysis)

        print(f"\n{'='*80}\n")

    except Exception as e:
        print(f"\n❌ 错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
