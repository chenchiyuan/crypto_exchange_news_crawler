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

    按照专业买卖墙格式展示4个成交密集区间：
    🔴 压力墙 (Sell Wall) - 区间4
       $2,978 ┐
       ▒▒   │ 17.1万 Vol (1.6% 薄弱)
       $2,959 ┘
          ⬆
          │ R1: $2,959 (+1.2%) / R2: $2,978 (+1.9%)

    👉 $2,923 (现价)

    🟢 支撑垫 (Buy Zone) - 区间1
       $2,847 ┐
       ▓▓▓▓ │ 99.9万 Vol (9.1% 强支撑)
       $2,791 ┘
          ⬇
          │ S1: $2,847 (-2.6%) / S2: $2,791 (-4.5%)

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

    # 辅助函数：格式化成交量显示
    def format_volume(vol):
        """格式化成交量显示（万为单位）"""
        if vol >= 10000:
            return f"{vol/10000:.1f}万"
        else:
            return f"{vol:.0f}"

    # 辅助函数：获取区间标签
    def get_cluster_tag(vol_pct, is_above):
        """根据成交量占比获取描述性标签"""
        if vol_pct >= 10:
            return "最厚"
        elif vol_pct >= 7:
            return "强支撑" if not is_above else "强压力"
        elif vol_pct >= 5:
            return "中支撑" if not is_above else "中压力"
        elif vol_pct >= 3:
            return "轻支撑" if not is_above else "轻压力"
        else:
            return "薄弱"

    # 显示前4个最大的成交密集区间
    if clusters:
        lines.append(f"【成交量分布】")
        lines.append(f"共识别出 {len(clusters)} 个成交密集区间，显示前4个最大\n")

        # 获取包含关键价位的cluster
        key_level_cluster_indices = set()
        r1_level = key_levels.get('resistance1')
        r2_level = key_levels.get('resistance2')
        s1_level = key_levels.get('support1')
        s2_level = key_levels.get('support2')

        if r1_level:
            key_level_cluster_indices.add(r1_level.cluster_index)
        if r2_level:
            key_level_cluster_indices.add(r2_level.cluster_index)
        if s1_level:
            key_level_cluster_indices.add(s1_level.cluster_index)
        if s2_level:
            key_level_cluster_indices.add(s2_level.cluster_index)

        # 优先选择包含关键价位的cluster
        key_clusters = [c for i, c in enumerate(clusters) if i in key_level_cluster_indices]
        other_clusters = [c for i, c in enumerate(clusters) if i not in key_level_cluster_indices]

        # 按成交量排序，其他cluster取前(4-len(key_clusters))个
        other_clusters_sorted = sorted(other_clusters, key=lambda c: c.total_volume, reverse=True)[:4-len(key_clusters)]

        # 合并并排序
        sorted_clusters = key_clusters + other_clusters_sorted

        # 按价格从高到低排序（压力区间在上，支撑区间在下）
        sorted_clusters = sorted(sorted_clusters, key=lambda c: c.price_center, reverse=True)

        # 分组：压力区间和支撑区间
        resistance_clusters = [c for c in sorted_clusters if c.price_low > current_price]
        support_clusters = [c for c in sorted_clusters if c.price_low <= current_price]

        # 显示压力区间（价格从高到低）
        for i, cluster in enumerate(resistance_clusters, 1):
            emoji = "🔴"
            wall_type = "压力墙 (Sell Wall)"

            # 获取该区间的关键价位信息
            cluster_index = clusters.index(cluster)

            # 检查这个区间是否包含关键价位
            level_info = ""
            title_info = ""
            has_r1 = r1_level and r1_level.cluster_index == cluster_index
            has_r2 = r2_level and r2_level.cluster_index == cluster_index


            if has_r1 or has_r2:
                r1_price = r1_level.price if has_r1 else "N/A"
                r1_dist = r1_level.distance_pct if has_r1 else 0
                r2_price = r2_level.price if has_r2 else "N/A"
                r2_dist = r2_level.distance_pct if has_r2 else 0

                if has_r1 and has_r2:
                    level_info = f"          │ R1: ${r1_price:,.0f} (+{r1_dist:.1f}%) / R2: ${r2_price:,.0f} (+{r2_dist:.1f}%)"
                    title_info = f" - R1: ${r1_price:,.0f} (+{r1_dist:.1f}%) / R2: ${r2_price:,.0f} (+{r2_dist:.1f}%)"
                elif has_r1:
                    level_info = f"          │ R1: ${r1_price:,.0f} (+{r1_dist:.1f}%)"
                    title_info = f" - R1: ${r1_price:,.0f} (+{r1_dist:.1f}%)"
                elif has_r2:
                    level_info = f"          │ R2: ${r2_price:,.0f} (+{r2_dist:.1f}%)"
                    title_info = f" - R2: ${r2_price:,.0f} (+{r2_dist:.1f}%)"
            else:
                # 没有关键价位时，显示区间价格范围
                title_info = f" - ${cluster.price_low:,.0f} - ${cluster.price_high:,.0f}"

            # 显示区间信息
            lines.append(f"{emoji} {wall_type}{title_info}")
            lines.append(f"   ${cluster.price_high:,.0f} ┐")

            # 成交量柱状图
            bar_length = int(cluster.volume_pct / 2)
            bars = "▒" * min(bar_length, 20)

            tag = get_cluster_tag(cluster.volume_pct, True)
            lines.append(f"   {bars} │ {format_volume(cluster.total_volume)} Vol ({cluster.volume_pct:.1f}% {tag})")
            lines.append(f"   ${cluster.price_low:,.0f} ┘")

            # 添加关键价位信息
            if level_info:
                lines.append(f"      ⬆")
                lines.append(level_info)

            lines.append("")

        # 👉 当前价格（在压力区间和支撑区间之间）
        lines.append(f"👉 ${current_price:,.0f} (现价)")
        lines.append("")
        lines.append("")

        # 显示支撑区间（价格从高到低）
        for i, cluster in enumerate(support_clusters, 1):
            emoji = "🟢"
            wall_type = "支撑垫 (Buy Zone)"

            # 获取该区间的关键价位信息
            cluster_index = clusters.index(cluster)

            # 检查这个区间是否包含关键价位
            level_info = ""
            title_info = ""
            has_s1 = s1_level and s1_level.cluster_index == cluster_index
            has_s2 = s2_level and s2_level.cluster_index == cluster_index
            if has_s1 or has_s2:
                s1_price = s1_level.price if has_s1 else "N/A"
                s1_dist = s1_level.distance_pct if has_s1 else 0
                s2_price = s2_level.price if has_s2 else "N/A"
                s2_dist = s2_level.distance_pct if has_s2 else 0

                if has_s1 and has_s2:
                    level_info = f"          │ S1: ${s1_price:,.0f} ({s1_dist:.1f}%) / S2: ${s2_price:,.0f} ({s2_dist:.1f}%)"
                    title_info = f" - S1: ${s1_price:,.0f} ({s1_dist:.1f}%) / S2: ${s2_price:,.0f} ({s2_dist:.1f}%)"
                elif has_s1:
                    level_info = f"          │ S1: ${s1_price:,.0f} ({s1_dist:.1f}%)"
                    title_info = f" - S1: ${s1_price:,.0f} ({s1_dist:.1f}%)"
                elif has_s2:
                    level_info = f"          │ S2: ${s2_price:,.0f} ({s2_dist:.1f}%)"
                    title_info = f" - S2: ${s2_price:,.0f} ({s2_dist:.1f}%)"
            else:
                # 没有关键价位时，显示区间价格范围
                title_info = f" - ${cluster.price_low:,.0f} - ${cluster.price_high:,.0f}"

            # 显示区间信息
            lines.append(f"{emoji} {wall_type}{title_info}")
            lines.append(f"   ${cluster.price_high:,.0f} ┐")

            # 成交量柱状图
            bar_length = int(cluster.volume_pct / 2)
            bars = "▓" * min(bar_length, 20)

            tag = get_cluster_tag(cluster.volume_pct, False)
            lines.append(f"   {bars} │ {format_volume(cluster.total_volume)} Vol ({cluster.volume_pct:.1f}% {tag})")
            lines.append(f"   ${cluster.price_low:,.0f} ┘")

            # 添加关键价位信息
            if level_info:
                lines.append(f"      ⬇")
                lines.append(level_info)

            lines.append("")

    # 添加基本信息
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

        # 预览格式化的内容（不实际发送）
        print(f"\n{'='*60}")
        print(f"推送标题:")
        print(f"{title}")
        print(f"\n{'='*60}")
        print(f"推送内容:")
        print(f"{content}")
        print(f"{'='*60}\n")

        # 如果是测试token（"test"），不实际发送推送
        if token == "test" or channel == "test":
            print(f"✅ 推送格式预览完成（测试模式，未实际发送）")
            return True

        # 实际发送推送
        push_service = AlertPushService(token=token, channel=channel)
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
