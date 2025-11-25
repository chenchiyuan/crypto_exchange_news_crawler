#!/usr/bin/env python
"""
四峰分析推送通知脚本

基于成交量聚类识别4个密集区间和关键价位，并发送推送通知。

推送标题格式: "价格-最近压力-最近支撑（时间）"
推送内容: 关键价位分析和区间分布详情

用法:
    python push_four_peaks_notification.py --symbol eth --interval 4h
    python push_four_peaks_notification.py --symbol btc --interval 1h --price-range 0.10
"""
import sys
import os
import argparse
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Django环境配置
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')
import django
django.setup()

from example_four_peaks import analyze_four_peaks
from monitor.services.notifier import AlertPushService


def format_title(current_price: float,
                 s1_price: float, s1_distance_pct: float,
                 s2_price: float, s2_distance_pct: float,
                 r1_price: float, r1_distance_pct: float,
                 symbol: str) -> str:
    """
    格式化推送标题

    格式: "BTC $87,599 (⚠️紧贴支撑 0.2%) | 🟢撑 $87,424 / $86,110 | 🔴压 $91,103"

    Args:
        current_price: 当前价格
        s1_price: 最近支撑位价格
        s1_distance_pct: 最近支撑位距离百分比
        s2_price: 次近支撑位价格
        s2_distance_pct: 次近支撑位距离百分比
        r1_price: 最近压力位价格
        r1_distance_pct: 最近压力位距离百分比
        symbol: 交易对符号

    Returns:
        推送标题字符串
    """
    # 判断当前价格更接近支撑还是压力
    abs_s1 = abs(s1_distance_pct)
    abs_r1 = abs(r1_distance_pct)

    if abs_s1 < abs_r1:
        # 更接近支撑位
        status = f"⚠️紧贴支撑 {abs_s1:.1f}%"
        s1_str = f"{s1_price:,.0f}"
        s2_str = f"{s2_price:,.0f}" if s2_price != current_price else ""
        r1_str = f"{r1_price:,.0f}"
        return f"{symbol.upper()} ${current_price:,.0f} ({status}) | 🟢撑 ${s1_str}" + (f"/${s2_str}" if s2_str else "") + f" | 🔴压 ${r1_str}"
    else:
        # 更接近压力位
        status = f"⚠️紧贴压力 {abs_r1:.1f}%"
        s1_str = f"{s1_price:,.0f}"
        s2_str = f"{s2_price:,.0f}" if s2_price != current_price else ""
        r1_str = f"{r1_price:,.0f}"
        return f"{symbol.upper()} ${current_price:,.0f} ({status}) | 🟢撑 ${s1_str}" + (f"/${s2_str}" if s2_str else "") + f" | 🔴压 ${r1_str}"


def format_content(
    symbol: str,
    interval: str,
    current_price: float,
    key_levels: dict,
    clusters: list,
    price_range_pct: float
) -> str:
    """
    格式化推送内容

    按照买卖墙格式展示4个价位:
    🔴 压力墙 (Sell Wall) - R2
       $价格 ┐
       ▒▒▒▒▒▒▒ │ 成交量 (百分比%)
       $价格 ┘

    🔴 压力墙 (Sell Wall) - R1
       $价格 ┐
       ▒▒▒▒▒▒▒ │ 成交量 (百分比%)
       $价格 ┘

       现价和距离

    🟢 支撑垫 (Buy Zone) - S1
       $价格 ┐
       ▓▓▓▓▓▓▓ │ 成交量 (百分比%)
       $价格 ┘

    🟢 支撑垫 (Buy Zone) - S2
       $价格 ┐
       ▓▓▓▓▓▓▓ │ 成交量 (百分比%)
       $价格 ┘

    Args:
        symbol: 交易对符号
        interval: 时间周期
        current_price: 当前价格
        key_levels: 关键价位字典
        clusters: 成交密集区间列表
        price_range_pct: 价格范围过滤百分比

    Returns:
        推送内容字符串（多行）
    """
    lines = []

    # 获取关键价位数据
    r1 = key_levels.get('resistance1')
    r2 = key_levels.get('resistance2')
    s1 = key_levels.get('support1')
    s2 = key_levels.get('support2')

    # 辅助函数：获取cluster价格区间
    def get_cluster_range(level, clusters):
        """获取level对应的cluster价格区间"""
        if level and 0 <= level.cluster_index < len(clusters):
            cluster = clusters[level.cluster_index]
            return cluster.price_high, cluster.price_low
        elif level:
            # fallback: 找不到cluster时显示该level的单个价格
            return level.price, level.price
        return None, None

    # 🔴 压力墙
    # 检查R1和R2是否来自同一个cluster
    if r1 and r2 and r1.cluster_index == r2.cluster_index:
        # 同一个cluster，显示一个压力墙，标注R1和R2位置
        r1_cluster = clusters[r1.cluster_index]
        lines.append(f"🔴 压力墙 (Sell Wall) - R1/R2")
        lines.append(f"   ${r1_cluster.price_high:,.0f} ┐")
        bar_length = int(r1.volume_pct / 2)
        bars = "▒" * min(bar_length, 20)
        lines.append(f"   {bars} │ {r1.volume:,.0f} Vol ({r1.volume_pct:.1f}%)")
        lines.append(f"   ${r1_cluster.price_low:,.0f} ┘")
        lines.append(f"      ⬆")
        lines.append(f"      │ R1: ${r1.price:,.0f} (+{r1.distance_pct:.1f}%) / R2: ${r2.price:,.0f} (+{r2.distance_pct:.1f}%)")
        lines.append("")
    elif r1 or r2:
        # 来自不同cluster，分别显示
        if r2:
            lines.append(f"🔴 压力墙 (Sell Wall) - R2")
            r2_cluster = clusters[r2.cluster_index]
            lines.append(f"   ${r2_cluster.price_high:,.0f} ┐")
            bar_length = int(r2.volume_pct / 2)
            bars = "▒" * min(bar_length, 20)
            lines.append(f"   {bars} │ {r2.volume:,.0f} Vol ({r2.volume_pct:.1f}%)")
            lines.append(f"   ${r2_cluster.price_low:,.0f} ┘")
            lines.append("")

        if r1:
            lines.append(f"🔴 压力墙 (Sell Wall) - R1")
            r1_cluster = clusters[r1.cluster_index]
            lines.append(f"   ${r1_cluster.price_high:,.0f} ┐")
            bar_length = int(r1.volume_pct / 2)
            bars = "▒" * min(bar_length, 20)
            lines.append(f"   {bars} │ {r1.volume:,.0f} Vol ({r1.volume_pct:.1f}%)")
            lines.append(f"   ${r1_cluster.price_low:,.0f} ┘")
            lines.append(f"      ⬆")
            lines.append(f"      │ 空间 +{r1.distance_pct:.1f}%")
            lines.append("")

    # 现价标记
    lines.append(f"👉 ${current_price:,.0f} (现价)")
    lines.append("")

    # 🟢 支撑垫
    # 检查S1和S2是否来自同一个cluster
    if s1 and s2 and s1.cluster_index == s2.cluster_index:
        # 同一个cluster，显示一个支撑垫，标注S1和S2位置
        s1_cluster = clusters[s1.cluster_index]
        lines.append(f"🟢 支撑垫 (Buy Zone) - S1/S2")
        lines.append(f"   ${s1_cluster.price_high:,.0f} ┐")
        bar_length = int(s1.volume_pct / 2)
        bars = "▓" * min(bar_length, 20)
        lines.append(f"   {bars} │ {s1.volume:,.0f} Vol ({s1.volume_pct:.1f}%)")
        lines.append(f"   ${s1_cluster.price_low:,.0f} ┘")
        lines.append(f"      ⬇")
        lines.append(f"      │ S1: ${s1.price:,.0f} ({s1.distance_pct:.1f}%) / S2: ${s2.price:,.0f} ({s2.distance_pct:.1f}%)")
    elif s1 or s2:
        # 来自不同cluster，分别显示
        if s1:
            lines.append(f"🟢 支撑垫 (Buy Zone) - S1")
            s1_cluster = clusters[s1.cluster_index]
            lines.append(f"   ${s1_cluster.price_high:,.0f} ┐")
            bar_length = int(s1.volume_pct / 2)
            bars = "▓" * min(bar_length, 20)
            lines.append(f"   {bars} │ {s1.volume:,.0f} Vol ({s1.volume_pct:.1f}%)")
            lines.append(f"   ${s1_cluster.price_low:,.0f} ┘")
            lines.append(f"      ⬇")
            lines.append(f"      │ 缓冲 -{abs(s1.distance_pct):.1f}%")
            lines.append("")

        if s2:
            lines.append(f"🟢 支撑垫 (Buy Zone) - S2")
            s2_cluster = clusters[s2.cluster_index]
            lines.append(f"   ${s2_cluster.price_high:,.0f} ┐")
            bar_length = int(s2.volume_pct / 2)
            bars = "▓" * min(bar_length, 20)
            lines.append(f"   {bars} │ {s2.volume:,.0f} Vol ({s2.volume_pct:.1f}%)")
            lines.append(f"   ${s2_cluster.price_low:,.0f} ┘")
            lines.append(f"      ⬇")
            lines.append(f"      │ 缓冲 -{abs(s2.distance_pct):.1f}%")

    # 添加基本信息
    lines.append("")
    lines.append(f"【基本信息】")
    lines.append(f"交易对: {symbol.upper()}")
    lines.append(f"周期: {interval}")
    lines.append(f"价格范围: ±{price_range_pct*100:.0f}%")

    return "\n".join(lines)


def send_four_peaks_notification(
    symbol: str,
    interval: str = '4h',
    price_range_pct: float = 0.15,
    limit: int = 100,
    token: str = "6020867bc6334c609d4f348c22f90f14",
    channel: str = "symbal_rate"
) -> bool:
    """
    执行四峰分析并发送推送通知

    Args:
        symbol: 交易对符号
        interval: 时间周期
        price_range_pct: 价格范围过滤百分比
        limit: K线数量
        token: 推送服务token
        channel: 推送渠道

    Returns:
        True=推送成功, False=推送失败
    """
    try:
        # 1. 执行四峰分析
        print(f"\n执行 {symbol.upper()} ({interval}) 四峰分析...")
        clusters, key_levels, current_price = analyze_four_peaks(
            symbol=symbol,
            interval=interval,
            price_range_pct=price_range_pct,
            limit=limit
        )

        # 2. 检查是否有足够的关键价位
        if not key_levels:
            print(f"❌ 未识别出足够的关键价位，无法发送推送")
            return False

        if 'resistance1' not in key_levels or 'support1' not in key_levels:
            print(f"⚠️  警告: 缺少最近的压力位或支撑位")

        # 3. 格式化推送内容
        # 提取关键价位数据
        s1_price = key_levels.get('support1').price if 'support1' in key_levels else current_price
        s1_distance_pct = key_levels.get('support1').distance_pct if 'support1' in key_levels else 0
        s2_price = key_levels.get('support2').price if 'support2' in key_levels else current_price
        s2_distance_pct = key_levels.get('support2').distance_pct if 'support2' in key_levels else 0
        r1_price = key_levels.get('resistance1').price if 'resistance1' in key_levels else current_price
        r1_distance_pct = key_levels.get('resistance1').distance_pct if 'resistance1' in key_levels else 0

        title = format_title(
            current_price,
            s1_price, s1_distance_pct,
            s2_price, s2_distance_pct,
            r1_price, r1_distance_pct,
            symbol
        )
        content = format_content(
            symbol=symbol,
            interval=interval,
            current_price=current_price,
            key_levels=key_levels,
            clusters=clusters,
            price_range_pct=price_range_pct
        )

        # 4. 发送推送
        print(f"\n发送推送通知...")
        push_service = AlertPushService(token=token, channel=channel)

        # 直接调用API发送
        import requests
        payload = {
            "token": token,
            "title": title,
            "content": content,
            "channel": channel
        }

        response = requests.post(
            push_service.api_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )

        response_data = response.json()

        if response_data.get('errcode') == 0:
            print(f"✅ 推送成功")
            print(f"\n推送标题: {title}")
            print(f"\n推送内容预览:")
            print(content[:300] + "..." if len(content) > 300 else content)
            return True
        else:
            error_msg = response_data.get('msg', '未知错误')
            print(f"❌ 推送失败: {error_msg}")
            return False

    except Exception as e:
        print(f"\n❌ 错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='四峰分析推送通知 - 基于成交量聚类识别关键价位并推送',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  %(prog)s --symbol eth --interval 4h
  %(prog)s --symbol btc --interval 1h --price-range 0.10
  %(prog)s --symbol eth --interval 15m --token YOUR_TOKEN --channel YOUR_CHANNEL
        '''
    )

    parser.add_argument(
        '--symbol',
        type=str,
        required=True,
        help='交易对符号 (如: eth, btc, bnb)'
    )

    parser.add_argument(
        '--interval',
        type=str,
        default='4h',
        choices=['15m', '1h', '4h', '1d'],
        help='时间周期 (默认: 4h)'
    )

    parser.add_argument(
        '--price-range',
        type=float,
        default=0.15,
        help='价格范围过滤百分比 (默认: 0.15 即±15%%)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='K线数量 (默认: 100)'
    )

    parser.add_argument(
        '--token',
        type=str,
        default="6020867bc6334c609d4f348c22f90f14",
        help='推送服务token (默认使用项目配置)'
    )

    parser.add_argument(
        '--channel',
        type=str,
        default="symbal_rate",
        help='推送渠道 (默认: symbal_rate)'
    )

    args = parser.parse_args()

    # 执行分析并推送
    success = send_four_peaks_notification(
        symbol=args.symbol,
        interval=args.interval,
        price_range_pct=args.price_range,
        limit=args.limit,
        token=args.token,
        channel=args.channel
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
