#!/usr/bin/env python
"""
四峰分析独立脚本

基于成交量聚类识别4个密集区间,并从8个边界价格中提取距离当前价格最近的4个关键价位。

用法:
    python example_four_peaks.py --symbol eth --interval 4h --price-range 0.15
    python example_four_peaks.py --symbol btc --interval 1h --price-range 0.10
    python example_four_peaks.py --symbol eth --interval 4h  # 使用默认15%
"""
import sys
import os
import argparse
from typing import List, Dict, Tuple
from dataclasses import dataclass

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vp_squeeze.services.binance_kline_service import fetch_klines
from vp_squeeze.services.indicators.volume_profile import calculate_volume_profile


@dataclass
class VolumeCluster:
    """成交量区间"""
    buckets: List[int]
    bucket_prices: List[float]
    price_low: float
    price_high: float
    price_center: float
    total_volume: float
    bucket_count: int
    width_pct: float
    volume_pct: float


@dataclass
class PriceLevel:
    """价格点"""
    price: float
    cluster_index: int
    boundary_type: str
    cluster: VolumeCluster
    distance_to_current: float
    distance_pct: float
    position: str


@dataclass
class KeyLevel:
    """关键价位"""
    price: float
    level_type: str
    distance: float
    distance_pct: float
    volume: float
    volume_pct: float
    cluster_range: str
    boundary_type: str
    cluster_index: int


def find_volume_clusters_by_continuity(
    heatmap: Dict[float, float],
    current_price: float,
    volume_threshold_factor: float = 1.3,
    min_bucket_count: int = 3,
    max_gap_buckets: int = 2,
    min_cluster_width_pct: float = 0.003,
    price_range_pct: float = 0.15
) -> List[VolumeCluster]:
    """
    基于连续性的成交量区间聚类

    Args:
        heatmap: 价格→成交量的字典
        current_price: 当前价格
        volume_threshold_factor: 成交量阈值系数
        min_bucket_count: 区间最小桶数
        max_gap_buckets: 允许的最大低量桶间隔数
        min_cluster_width_pct: 区间最小宽度百分比
        price_range_pct: 价格范围过滤百分比(±)

    Returns:
        按成交量降序排序的区间列表
    """
    if not heatmap:
        return []

    # 步骤1: 计算阈值
    volumes = list(heatmap.values())
    total_volume = sum(volumes)
    avg_volume = total_volume / len(volumes)
    threshold = avg_volume * volume_threshold_factor

    # 步骤2: 标记高量桶
    sorted_prices = sorted(heatmap.keys())
    high_volume_indices = set()

    for idx, price in enumerate(sorted_prices):
        volume = heatmap[price]
        if volume >= threshold:
            high_volume_indices.add(idx)

    # 步骤3: 合并连续区间
    clusters = []
    current_cluster = None
    gap_count = 0

    for idx in range(len(sorted_prices)):
        price = sorted_prices[idx]
        volume = heatmap[price]
        is_high_volume = idx in high_volume_indices

        if is_high_volume:
            if current_cluster is None:
                # 开始新区间
                current_cluster = {
                    'start_idx': idx,
                    'end_idx': idx,
                    'buckets': [idx],
                    'volumes': [volume],
                    'prices': [price]
                }
                gap_count = 0
            else:
                # 扩展当前区间
                current_cluster['end_idx'] = idx
                current_cluster['buckets'].append(idx)
                current_cluster['volumes'].append(volume)
                current_cluster['prices'].append(price)
                gap_count = 0
        else:
            # 低量桶
            if current_cluster is not None:
                gap_count += 1
                if gap_count > max_gap_buckets:
                    # 间隔过多,结束当前区间
                    _finalize_cluster(
                        current_cluster, clusters, sorted_prices, heatmap,
                        min_bucket_count, min_cluster_width_pct,
                        current_price, price_range_pct, total_volume
                    )
                    current_cluster = None
                    gap_count = 0

    # 处理最后一个未完成的区间
    if current_cluster is not None:
        _finalize_cluster(
            current_cluster, clusters, sorted_prices, heatmap,
            min_bucket_count, min_cluster_width_pct,
            current_price, price_range_pct, total_volume
        )

    # 步骤4: 按成交量排序
    clusters.sort(key=lambda c: c.total_volume, reverse=True)

    return clusters


def _finalize_cluster(
    cluster_data: dict,
    clusters: List[VolumeCluster],
    sorted_prices: List[float],
    heatmap: Dict[float, float],
    min_bucket_count: int,
    min_cluster_width_pct: float,
    current_price: float,
    price_range_pct: float,
    total_volume: float
) -> None:
    """完成并验证一个区间"""
    bucket_count = len(cluster_data['buckets'])

    # 过滤1: 桶数量
    if bucket_count < min_bucket_count:
        return

    # 计算区间属性
    prices = cluster_data['prices']
    price_low = min(prices)
    price_high = max(prices)
    price_center = (price_low + price_high) / 2
    cluster_total_volume = sum(cluster_data['volumes'])
    width_pct = (price_high - price_low) / current_price

    # 过滤2: 价格宽度
    if width_pct < min_cluster_width_pct:
        return

    # 过滤3: 价格范围
    price_deviation = abs(price_center - current_price) / current_price
    if price_deviation > price_range_pct:
        return

    # 创建区间对象
    cluster = VolumeCluster(
        buckets=cluster_data['buckets'],
        bucket_prices=prices,
        price_low=price_low,
        price_high=price_high,
        price_center=price_center,
        total_volume=cluster_total_volume,
        bucket_count=bucket_count,
        width_pct=width_pct,
        volume_pct=cluster_total_volume / total_volume * 100
    )

    clusters.append(cluster)


def extract_key_levels(
    clusters: List[VolumeCluster],
    current_price: float
) -> Dict[str, KeyLevel]:
    """
    从4个区间的8个边界价格中，选出距离当前价格最近的4个

    Returns:
        {
            'support1': KeyLevel,    # 下方最近
            'support2': KeyLevel,    # 下方次近
            'resistance1': KeyLevel, # 上方最近
            'resistance2': KeyLevel  # 上方次近
        }
    """
    # 步骤1: 收集所有边界价格
    all_prices = []

    for i, cluster in enumerate(clusters):
        # 添加区间底部价格
        distance_low = abs(cluster.price_low - current_price)
        all_prices.append(PriceLevel(
            price=cluster.price_low,
            cluster_index=i,
            boundary_type='low',
            cluster=cluster,
            distance_to_current=distance_low,
            distance_pct=distance_low / current_price,
            position='below' if cluster.price_low < current_price else 'above'
        ))

        # 添加区间顶部价格
        distance_high = abs(cluster.price_high - current_price)
        all_prices.append(PriceLevel(
            price=cluster.price_high,
            cluster_index=i,
            boundary_type='high',
            cluster=cluster,
            distance_to_current=distance_high,
            distance_pct=distance_high / current_price,
            position='below' if cluster.price_high < current_price else 'above'
        ))

    # 步骤2: 分类
    below_prices = [p for p in all_prices if p.position == 'below']
    above_prices = [p for p in all_prices if p.position == 'above']

    # 步骤3: 按距离排序(升序,最近的在前)
    below_prices.sort(key=lambda p: p.distance_to_current)
    above_prices.sort(key=lambda p: p.distance_to_current)

    # 步骤4: 选出最近的2个
    result = {}

    # 支撑位1: 下方最近
    if len(below_prices) >= 1:
        p = below_prices[0]
        result['support1'] = KeyLevel(
            price=p.price,
            level_type='support',
            distance=p.price - current_price,
            distance_pct=-p.distance_pct * 100,
            volume=p.cluster.total_volume,
            volume_pct=p.cluster.volume_pct,
            cluster_range=f"${p.cluster.price_low:.2f}-${p.cluster.price_high:.2f}",
            boundary_type=p.boundary_type,
            cluster_index=p.cluster_index
        )

    # 支撑位2: 下方次近
    if len(below_prices) >= 2:
        p = below_prices[1]
        result['support2'] = KeyLevel(
            price=p.price,
            level_type='support',
            distance=p.price - current_price,
            distance_pct=-p.distance_pct * 100,
            volume=p.cluster.total_volume,
            volume_pct=p.cluster.volume_pct,
            cluster_range=f"${p.cluster.price_low:.2f}-${p.cluster.price_high:.2f}",
            boundary_type=p.boundary_type,
            cluster_index=p.cluster_index
        )

    # 压力位1: 上方最近
    if len(above_prices) >= 1:
        p = above_prices[0]
        result['resistance1'] = KeyLevel(
            price=p.price,
            level_type='resistance',
            distance=p.price - current_price,
            distance_pct=p.distance_pct * 100,
            volume=p.cluster.total_volume,
            volume_pct=p.cluster.volume_pct,
            cluster_range=f"${p.cluster.price_low:.2f}-${p.cluster.price_high:.2f}",
            boundary_type=p.boundary_type,
            cluster_index=p.cluster_index
        )

    # 压力位2: 上方次近
    if len(above_prices) >= 2:
        p = above_prices[1]
        result['resistance2'] = KeyLevel(
            price=p.price,
            level_type='resistance',
            distance=p.price - current_price,
            distance_pct=p.distance_pct * 100,
            volume=p.cluster.total_volume,
            volume_pct=p.cluster.volume_pct,
            cluster_range=f"${p.cluster.price_low:.2f}-${p.cluster.price_high:.2f}",
            boundary_type=p.boundary_type,
            cluster_index=p.cluster_index
        )

    return result


def analyze_four_peaks(
    symbol: str,
    interval: str = '4h',
    price_range_pct: float = 0.15,
    limit: int = 100
) -> Tuple[List[VolumeCluster], Dict[str, KeyLevel], float]:
    """
    执行四峰分析

    Args:
        symbol: 交易对符号(如'eth', 'btc')
        interval: 时间周期(如'15m', '1h', '4h')
        price_range_pct: 价格范围过滤百分比(默认0.15即±15%)
        limit: K线数量

    Returns:
        (clusters, key_levels, current_price)
    """
    # 1. 获取K线数据
    klines = fetch_klines(symbol=symbol, interval=interval, limit=limit)
    if not klines:
        raise ValueError(f"获取{symbol}的K线数据失败")

    current_price = klines[-1].close

    # 2. 计算Volume Profile
    vp_result = calculate_volume_profile(
        klines=klines,
        resolution_pct=0.001  # 0.1%精度
    )
    heatmap = vp_result.profile

    # 3. 使用连续性聚类识别区间
    clusters = find_volume_clusters_by_continuity(
        heatmap=heatmap,
        current_price=current_price,
        volume_threshold_factor=1.3,
        min_bucket_count=3,
        max_gap_buckets=2,
        min_cluster_width_pct=0.003,
        price_range_pct=price_range_pct
    )

    # 4. 从区间中提取4个关键价位
    key_levels = {}
    if len(clusters) >= 1:
        key_levels = extract_key_levels(clusters, current_price)

    return clusters, key_levels, current_price


def print_results(
    symbol: str,
    interval: str,
    clusters: List[VolumeCluster],
    key_levels: Dict[str, KeyLevel],
    current_price: float,
    price_range_pct: float
):
    """打印分析结果"""
    print(f"\n{'='*80}")
    print(f"{symbol.upper()} 四峰分析结果 ({interval})")
    print(f"{'='*80}")

    print(f"\n【分析参数】")
    print(f"  时间周期: {interval}")
    print(f"  价格范围过滤: ±{price_range_pct*100:.0f}%")
    print(f"  当前价格: ${current_price:.2f}")

    # 显示识别的区间
    print(f"\n【识别的成交密集区间】")
    print(f"  共识别出 {len(clusters)} 个区间\n")

    for i, cluster in enumerate(clusters, 1):
        print(f"  区间{i}: [${cluster.price_low:.2f}, ${cluster.price_high:.2f}]")
        print(f"         成交量: {cluster.total_volume:,.0f} ({cluster.volume_pct:.1f}%)")
        print(f"         宽度: ${cluster.price_high - cluster.price_low:.2f} ({cluster.width_pct*100:.2f}%)")
        print(f"         桶数: {cluster.bucket_count}")
        deviation = (cluster.price_center - current_price) / current_price * 100
        position = "上方" if cluster.price_center > current_price else "下方"
        print(f"         位置: {position} (偏离 {deviation:+.2f}%)")
        print()

    # 显示关键价位
    if key_levels:
        print(f"【关键价位】")
        print(f"  从 {len(clusters)} 个区间的 {len(clusters)*2} 个边界价格中，选出距离最近的4个:\n")

        # 压力位
        print(f"  📈 压力位:")
        if 'resistance2' in key_levels:
            r2 = key_levels['resistance2']
            print(f"     R2: ${r2.price:.2f} ({r2.distance_pct:+.2f}%)")
            print(f"         来源: 区间{r2.cluster_index+1} 的 {r2.boundary_type} 边界")
            print(f"         区间: {r2.cluster_range}")
            print(f"         成交量: {r2.volume:,.0f} ({r2.volume_pct:.1f}%)")
            print()

        if 'resistance1' in key_levels:
            r1 = key_levels['resistance1']
            print(f"     R1: ${r1.price:.2f} ({r1.distance_pct:+.2f}%)")
            print(f"         来源: 区间{r1.cluster_index+1} 的 {r1.boundary_type} 边界")
            print(f"         区间: {r1.cluster_range}")
            print(f"         成交量: {r1.volume:,.0f} ({r1.volume_pct:.1f}%)")
            print()

        # 当前价格
        print(f"  💰 当前价格: ${current_price:.2f}")
        print()

        # 支撑位
        print(f"  📉 支撑位:")
        if 'support1' in key_levels:
            s1 = key_levels['support1']
            print(f"     S1: ${s1.price:.2f} ({s1.distance_pct:.2f}%)")
            print(f"         来源: 区间{s1.cluster_index+1} 的 {s1.boundary_type} 边界")
            print(f"         区间: {s1.cluster_range}")
            print(f"         成交量: {s1.volume:,.0f} ({s1.volume_pct:.1f}%)")
            print()

        if 'support2' in key_levels:
            s2 = key_levels['support2']
            print(f"     S2: ${s2.price:.2f} ({s2.distance_pct:.2f}%)")
            print(f"         来源: 区间{s2.cluster_index+1} 的 {s2.boundary_type} 边界")
            print(f"         区间: {s2.cluster_range}")
            print(f"         成交量: {s2.volume:,.0f} ({s2.volume_pct:.1f}%)")

        # 简洁摘要
        print(f"\n【摘要】")
        print(f"  当前价格: ${current_price:.2f}")
        print(f"  支撑位: ", end="")
        if 'support1' in key_levels:
            print(f"${key_levels['support1'].price:.2f}", end="")
        if 'support2' in key_levels:
            print(f", ${key_levels['support2'].price:.2f}", end="")
        print()

        print(f"  压力位: ", end="")
        if 'resistance1' in key_levels:
            print(f"${key_levels['resistance1'].price:.2f}", end="")
        if 'resistance2' in key_levels:
            print(f", ${key_levels['resistance2'].price:.2f}", end="")
        print()

    else:
        print(f"\n⚠️  未识别出足够的成交密集区间")

    print(f"\n{'='*80}\n")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='四峰分析 - 基于成交量聚类识别关键价位',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  %(prog)s --symbol eth --interval 4h
  %(prog)s --symbol btc --interval 1h --price-range 0.10
  %(prog)s --symbol eth --interval 15m --price-range 0.20
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
        help='价格范围过滤百分比,超出此范围的区间将被忽略 (默认: 0.15 即±15%%)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='K线数量 (默认: 100)'
    )

    args = parser.parse_args()

    try:
        # 执行分析
        clusters, key_levels, current_price = analyze_four_peaks(
            symbol=args.symbol,
            interval=args.interval,
            price_range_pct=args.price_range,
            limit=args.limit
        )

        # 打印结果
        print_results(
            symbol=args.symbol,
            interval=args.interval,
            clusters=clusters,
            key_levels=key_levels,
            current_price=current_price,
            price_range_pct=args.price_range
        )

    except Exception as e:
        print(f"\n❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
