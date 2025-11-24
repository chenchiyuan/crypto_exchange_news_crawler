"""多周期成交量分析器 - 以成交量为核心"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import logging

from vp_squeeze.dto import KLineData, VolumeProfileResult
from vp_squeeze.services.binance_kline_service import fetch_klines
from vp_squeeze.services.indicators.volume_profile import calculate_volume_profile

logger = logging.getLogger(__name__)


@dataclass
class EnhancedHVN:
    """增强的高量节点"""
    price_low: float           # 价格下界
    price_high: float          # 价格上界
    price_center: float        # 价格中心
    volume: float              # 总成交量
    volume_density: float      # 成交量密度 = 成交量 / 价格宽度
    volume_ratio: float        # 成交量占比
    is_consecutive: bool       # 是否连续（3+个价格桶）
    bucket_count: int          # 包含的价格桶数量
    timeframe: str             # 所属周期


@dataclass
class VolumeResonanceZone:
    """成交量共振区"""
    price_low: float           # 区间下界
    price_high: float          # 区间上界
    price_center: float        # 区间中心
    total_volume: float        # 总成交量
    timeframes: List[str]      # 参与的周期
    hvn_count: int             # HVN重叠数量
    strength: float            # 共振强度 0-100
    zone_type: str             # 类型: 'support' or 'resistance' or 'neutral'


@dataclass
class TimeframeAnalysis:
    """单周期分析结果"""
    timeframe: str
    klines: List[KLineData]
    volume_profile: VolumeProfileResult
    enhanced_hvns: List[EnhancedHVN]
    total_volume: float
    volume_concentration: float  # 成交量集中度（VAL-VAH区间）
    avg_volume_density: float    # 平均成交量密度


def calculate_enhanced_hvn(
    volume_profile: VolumeProfileResult,
    total_volume: float,
    timeframe: str,
    min_consecutive: int = 3,
    min_volume_ratio: float = 0.15
) -> List[EnhancedHVN]:
    """
    增强的HVN识别 - 多维度筛选

    Args:
        volume_profile: Volume Profile结果
        total_volume: 总成交量
        timeframe: 时间周期
        min_consecutive: 最少连续价格桶数
        min_volume_ratio: 最小成交量占比阈值

    Returns:
        EnhancedHVN列表
    """
    if not volume_profile.hvn:
        return []

    enhanced_hvns = []

    # 1. 按价格排序
    sorted_hvns = sorted(volume_profile.hvn, key=lambda x: x['low'])

    # 2. 合并连续的HVN
    i = 0
    while i < len(sorted_hvns):
        current_hvn = sorted_hvns[i]

        # 初始化聚合数据
        price_low = current_hvn['low']
        price_high = current_hvn['high']
        total_hvn_volume = current_hvn['volume']
        bucket_count = 1

        # 向后查找连续的HVN（容差2%）
        j = i + 1
        while j < len(sorted_hvns):
            next_hvn = sorted_hvns[j]
            gap = (next_hvn['low'] - price_high) / price_high

            if gap < 0.02:  # 2%容差内认为连续
                price_high = next_hvn['high']
                total_hvn_volume += next_hvn['volume']
                bucket_count += 1
                j += 1
            else:
                break

        # 计算指标
        price_width = price_high - price_low
        volume_density = total_hvn_volume / price_width if price_width > 0 else 0
        volume_ratio = total_hvn_volume / total_volume if total_volume > 0 else 0
        is_consecutive = bucket_count >= min_consecutive

        # 筛选：必须满足连续性或成交量占比
        if is_consecutive or volume_ratio >= min_volume_ratio:
            enhanced_hvns.append(EnhancedHVN(
                price_low=price_low,
                price_high=price_high,
                price_center=(price_low + price_high) / 2,
                volume=total_hvn_volume,
                volume_density=volume_density,
                volume_ratio=volume_ratio,
                is_consecutive=is_consecutive,
                bucket_count=bucket_count,
                timeframe=timeframe
            ))

        i = j if j > i else i + 1

    return enhanced_hvns


def analyze_single_timeframe(
    symbol: str,
    timeframe: str,
    limit: int = 100,
    resolution_pct: float = 0.0005  # 0.05%更细分辨率
) -> TimeframeAnalysis:
    """
    单周期成交量分析

    Args:
        symbol: 交易对
        timeframe: 时间周期
        limit: K线数量
        resolution_pct: Volume Profile分辨率

    Returns:
        TimeframeAnalysis对象
    """
    # 获取K线数据
    klines = fetch_klines(symbol, timeframe, limit)

    # 计算Volume Profile（更细分辨率）
    vp = calculate_volume_profile(klines, resolution_pct=resolution_pct)

    # 增强HVN识别
    total_volume = sum(k.volume for k in klines)
    enhanced_hvns = calculate_enhanced_hvn(vp, total_volume, timeframe)

    # 计算成交量集中度
    val_vah_volume = sum(
        vol for price, vol in vp.profile.items()
        if vp.val <= price <= vp.vah
    )
    volume_concentration = val_vah_volume / total_volume if total_volume > 0 else 0

    # 计算平均成交量密度
    if enhanced_hvns:
        avg_density = sum(hvn.volume_density for hvn in enhanced_hvns) / len(enhanced_hvns)
    else:
        avg_density = 0

    return TimeframeAnalysis(
        timeframe=timeframe,
        klines=klines,
        volume_profile=vp,
        enhanced_hvns=enhanced_hvns,
        total_volume=total_volume,
        volume_concentration=volume_concentration,
        avg_volume_density=avg_density
    )


def detect_volume_resonance(
    analyses: List[TimeframeAnalysis],
    price_tolerance: float = 0.02  # 2%价格容差
) -> List[VolumeResonanceZone]:
    """
    检测跨周期成交量共振区

    算法：
        1. 收集所有周期的HVN
        2. 按价格聚类（±2%容差）
        3. 计算每个簇的总成交量和周期数
        4. 评估共振强度

    Args:
        analyses: 多周期分析结果
        price_tolerance: 价格容差

    Returns:
        VolumeResonanceZone列表（按强度排序）
    """
    # 1. 收集所有HVN
    all_hvns = []
    for analysis in analyses:
        all_hvns.extend(analysis.enhanced_hvns)

    if not all_hvns:
        return []

    # 2. 价格聚类
    clusters: List[List[EnhancedHVN]] = []
    used = set()

    for i, hvn in enumerate(all_hvns):
        if i in used:
            continue

        cluster = [hvn]
        used.add(i)

        # 查找与当前HVN价格接近的其他HVN
        for j, other_hvn in enumerate(all_hvns):
            if j in used or j == i:
                continue

            # 计算价格重叠度
            overlap_low = max(hvn.price_low, other_hvn.price_low)
            overlap_high = min(hvn.price_high, other_hvn.price_high)

            if overlap_high > overlap_low:
                # 有重叠
                overlap_ratio = (overlap_high - overlap_low) / (hvn.price_high - hvn.price_low)
                if overlap_ratio >= 0.3:  # 至少30%重叠
                    cluster.append(other_hvn)
                    used.add(j)
            else:
                # 无重叠，检查距离
                distance = min(
                    abs(hvn.price_center - other_hvn.price_center),
                    abs(hvn.price_low - other_hvn.price_low),
                    abs(hvn.price_high - other_hvn.price_high)
                )
                distance_pct = distance / hvn.price_center

                if distance_pct <= price_tolerance:
                    cluster.append(other_hvn)
                    used.add(j)

        if len(cluster) > 0:
            clusters.append(cluster)

    # 3. 计算每个簇的共振区域
    resonance_zones = []

    for cluster in clusters:
        # 计算簇的边界
        price_low = min(hvn.price_low for hvn in cluster)
        price_high = max(hvn.price_high for hvn in cluster)
        price_center = (price_low + price_high) / 2

        # 计算总成交量
        total_volume = sum(hvn.volume for hvn in cluster)

        # 参与的周期
        timeframes = list(set(hvn.timeframe for hvn in cluster))

        # HVN数量
        hvn_count = len(cluster)

        # 计算共振强度
        # 因子1: 周期数量（最多3个）
        timeframe_score = len(timeframes) / 3.0  # 0-1

        # 因子2: 成交量（归一化）
        max_volume = max(sum(hvn.volume for hvn in c) for c in clusters)
        volume_score = total_volume / max_volume if max_volume > 0 else 0

        # 因子3: HVN密度
        density_score = min(hvn_count / 5.0, 1.0)  # 5个以上满分

        # 综合强度（成交量权重最高）
        strength = (
            volume_score * 0.5 +      # 50%成交量
            timeframe_score * 0.35 +  # 35%周期数
            density_score * 0.15      # 15%密度
        ) * 100

        # 判断类型（基于价格位置）
        current_price = analyses[0].klines[-1].close
        if price_center < current_price * 0.98:
            zone_type = 'support'
        elif price_center > current_price * 1.02:
            zone_type = 'resistance'
        else:
            zone_type = 'neutral'

        resonance_zones.append(VolumeResonanceZone(
            price_low=price_low,
            price_high=price_high,
            price_center=price_center,
            total_volume=total_volume,
            timeframes=sorted(timeframes),
            hvn_count=hvn_count,
            strength=round(strength, 2),
            zone_type=zone_type
        ))

    # 按强度排序
    resonance_zones.sort(key=lambda z: z.strength, reverse=True)

    return resonance_zones


def analyze_multi_timeframe(
    symbol: str,
    timeframes: List[str] = ['15m', '1h', '4h'],
    limit: int = 100,
    verbose: bool = False
) -> Tuple[List[TimeframeAnalysis], List[VolumeResonanceZone]]:
    """
    多周期成交量分析

    Args:
        symbol: 交易对
        timeframes: 时间周期列表
        limit: K线数量
        verbose: 是否输出详细日志

    Returns:
        (周期分析列表, 共振区列表)
    """
    if verbose:
        logger.info(f"开始多周期分析: {symbol}, 周期: {timeframes}")

    # 1. 分别分析每个周期
    analyses = []
    for tf in timeframes:
        try:
            analysis = analyze_single_timeframe(symbol, tf, limit)
            analyses.append(analysis)

            if verbose:
                logger.info(f"{tf}: HVN数量={len(analysis.enhanced_hvns)}, "
                           f"成交量集中度={analysis.volume_concentration:.2%}")
        except Exception as e:
            logger.error(f"分析{tf}周期失败: {e}")

    if not analyses:
        return [], []

    # 2. 检测成交量共振区
    resonance_zones = detect_volume_resonance(analyses)

    if verbose:
        logger.info(f"发现 {len(resonance_zones)} 个成交量共振区")
        for i, zone in enumerate(resonance_zones[:3], 1):
            logger.info(f"共振区{i}: {zone.price_center:.2f}, "
                       f"强度={zone.strength:.0f}, 周期={zone.timeframes}")

    return analyses, resonance_zones
