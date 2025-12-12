#!/usr/bin/env python
"""
VWAP（成交量加权平均价格）计算脚本

基于K线数据计算平均持仓成本，支持多种时间周期和可视化。

用法:
    python calculate_vwap.py --symbol eth --interval 4h --limit 100
    python calculate_vwap.py --symbol btc --interval 1h --days 30 --output chart
"""
import sys
import os
import argparse
from typing import List, Tuple, Dict
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vp_squeeze.services.binance_kline_service import fetch_klines


class VWAPCalculator:
    """VWAP计算器"""

    def __init__(self, klines: List):
        self.klines = klines

    def calculate_vwap(self, days: int = None, limit: int = None) -> Dict:
        """
        计算VWAP（成交量加权平均价格）

        Args:
            days: 计算天数
            limit: K线数量限制

        Returns:
            包含VWAP信息的字典
        """
        # 过滤数据
        klines = self.klines
        if limit:
            klines = self.klines[-limit:]
        elif days:
            cutoff_time = datetime.now() - timedelta(days=days)
            if isinstance(self.klines[0].open_time, datetime):
                klines = [k for k in self.klines if k.open_time >= cutoff_time]
            else:
                klines = [k for k in self.klines if k.open_time >= cutoff_time.timestamp() * 1000]

        if not klines:
            raise ValueError("没有足够的数据计算VWAP")

        # 计算典型价格和成交量
        total_price_volume = 0.0
        total_volume = 0.0
        price_volume_by_day = {}

        for kline in klines:
            # 典型价格 (High + Low + Close) / 3
            typical_price = (kline.high + kline.low + kline.close) / 3
            volume = kline.volume

            # 累积计算
            total_price_volume += typical_price * volume
            total_volume += volume

            # 按日期分组
            if isinstance(kline.open_time, datetime):
                date_str = kline.open_time.strftime('%Y-%m-%d')
            else:
                # 如果是时间戳
                date_str = datetime.fromtimestamp(kline.open_time / 1000).strftime('%Y-%m-%d')
            if date_str not in price_volume_by_day:
                price_volume_by_day[date_str] = {'price_volume': 0, 'volume': 0}
            price_volume_by_day[date_str]['price_volume'] += typical_price * volume
            price_volume_by_day[date_str]['volume'] += volume

        # 总体VWAP
        vwap = total_price_volume / total_volume if total_volume > 0 else 0

        # 每日VWAP
        daily_vwap = {}
        for date, data in price_volume_by_day.items():
            daily_vwap[date] = data['price_volume'] / data['volume'] if data['volume'] > 0 else 0

        # 计算当前价格和偏离
        current_price = klines[-1].close
        deviation_pct = (current_price - vwap) / vwap * 100 if vwap > 0 else 0

        return {
            'vwap': vwap,
            'current_price': current_price,
            'deviation_pct': deviation_pct,
            'total_volume': total_volume,
            'total_price_volume': total_price_volume,
            'kline_count': len(klines),
            'daily_vwap': daily_vwap,
            'price_range': {
                'min': min(k.close for k in klines),
                'max': max(k.close for k in klines)
            },
            'avg_volume': total_volume / len(klines) if klines else 0
        }

    def calculate_vwap_trend(self, window_days: int = 7) -> List[Dict]:
        """
        计算VWAP趋势（滚动窗口）

        Args:
            window_days: 滚动窗口天数

        Returns:
            VWAP趋势数据列表
        """
        trend_data = []
        date_groups = {}

        # 按日期分组
        for kline in self.klines:
            if isinstance(kline.open_time, datetime):
                date_str = kline.open_time.strftime('%Y-%m-%d')
            else:
                date_str = datetime.fromtimestamp(kline.open_time / 1000).strftime('%Y-%m-%d')
            if date_str not in date_groups:
                date_groups[date_str] = []
            date_groups[date_str].append(kline)

        # 计算每日VWAP
        daily_data = []
        for date in sorted(date_groups.keys()):
            klines = date_groups[date]
            total_price_volume = sum(
                ((k.high + k.low + k.close) / 3) * k.volume for k in klines
            )
            total_volume = sum(k.volume for k in klines)
            daily_vwap = total_price_volume / total_volume if total_volume > 0 else 0
            daily_data.append({
                'date': date,
                'vwap': daily_vwap,
                'volume': total_volume
            })

        # 计算滚动平均VWAP
        for i in range(len(daily_data)):
            window = daily_data[max(0, i - window_days + 1):i + 1]
            window_vwap = sum(d['vwap'] * d['volume'] for d in window) / sum(d['volume'] for d in window)
            trend_data.append({
                'date': daily_data[i]['date'],
                'daily_vwap': daily_data[i]['vwap'],
                'rolling_vwap': window_vwap,
                'volume': daily_data[i]['volume']
            })

        return trend_data

    def print_vwap_analysis(self, vwap_data: Dict, symbol: str, interval: str):
        """打印VWAP分析结果"""
        print(f"\n{'='*80}")
        print(f"{symbol.upper()} VWAP分析 ({interval})")
        print(f"{'='*80}")

        print(f"\n【平均持仓成本】")
        print(f"  VWAP: ${vwap_data['vwap']:.2f}")
        print(f"  当前价格: ${vwap_data['current_price']:.2f}")
        print(f"  偏离: {vwap_data['deviation_pct']:+.2f}%")

        status = "💰 价格在成本下方" if vwap_data['deviation_pct'] > 0 else "📈 价格在成本上方"
        print(f"  状态: {status}")

        print(f"\n【数据统计】")
        print(f"  K线数量: {vwap_data['kline_count']}")
        print(f"  总成交量: {vwap_data['total_volume']:,.2f}")
        print(f"  平均成交量: {vwap_data['avg_volume']:,.2f}")
        print(f"  价格范围: ${vwap_data['price_range']['min']:.2f} - ${vwap_data['price_range']['max']:.2f}")

        print(f"\n【每日VWAP (最近7天)】")
        sorted_daily = sorted(vwap_data['daily_vwap'].items(), reverse=True)[:7]
        for date, vwap in sorted_daily:
            print(f"  {date}: ${vwap:.2f}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='VWAP计算 - 计算平均持仓成本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  %(prog)s --symbol eth --interval 4h --limit 100
  %(prog)s --symbol btc --interval 1h --days 30 --output chart
  %(prog)s --symbol eth --interval 4h --trend
        '''
    )

    parser.add_argument('--symbol', type=str, required=True,
                       help='交易对符号 (如: eth, btc, bnb)')
    parser.add_argument('--interval', type=str, default='4h',
                       choices=['15m', '1h', '4h', '1d'],
                       help='时间周期 (默认: 4h)')
    parser.add_argument('--limit', type=int, default=100,
                       help='K线数量限制 (默认: 100)')
    parser.add_argument('--days', type=int,
                       help='计算天数 (覆盖limit)')
    parser.add_argument('--trend', action='store_true',
                       help='显示VWAP趋势')
    parser.add_argument('--output', type=str,
                       choices=['text', 'json', 'chart'],
                       default='text',
                       help='输出格式 (默认: text)')

    args = parser.parse_args()

    try:
        # 获取K线数据
        print(f"获取 {args.symbol.upper()} {args.interval} K线数据...")
        klines = fetch_klines(symbol=args.symbol, interval=args.interval, limit=1000)
        if not klines:
            print(f"❌ 获取K线数据失败")
            return 1

        # 计算VWAP
        calculator = VWAPCalculator(klines)

        if args.trend:
            # VWAP趋势
            trend_data = calculator.calculate_vwap_trend()
            print(f"\n{'='*80}")
            print(f"{args.symbol.upper()} VWAP趋势")
            print(f"{'='*80}")
            print(f"{'日期':<12} {'日VWAP':<12} {'滚动VWAP':<12} {'成交量':<15}")
            print("-" * 60)
            for data in trend_data[-14:]:  # 显示最近14天
                print(f"{data['date']:<12} "
                      f"${data['daily_vwap']:.2f}      "
                      f"${data['rolling_vwap']:.2f}      "
                      f"{data['volume']:,.0f}")
        else:
            # 总体VWAP
            vwap_data = calculator.calculate_vwap(
                days=args.days,
                limit=args.limit if not args.days else None
            )

            calculator.print_vwap_analysis(vwap_data, args.symbol, args.interval)

            # 输出JSON格式
            if args.output == 'json':
                import json
                print(f"\n\n{json.dumps(vwap_data, indent=2)}")

        print(f"\n{'='*80}\n")

    except Exception as e:
        print(f"\n❌ 错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
