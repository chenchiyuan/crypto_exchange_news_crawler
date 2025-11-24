"""两层箱体选择器 - 基于成交量优先"""
from dataclasses import dataclass
from typing import List, Optional, Tuple
import logging

from vp_squeeze.services.multi_timeframe_analyzer import (
    TimeframeAnalysis,
    VolumeResonanceZone
)

logger = logging.getLogger(__name__)


@dataclass
class BoxCandidate:
    """箱体候选"""
    timeframe: str
    support: float  # VAL
    resistance: float  # VAH
    midpoint: float  # VPOC
    range_pct: float  # 箱体宽度百分比

    # 成交量指标（优先级最高）
    volume_concentration: float  # 成交量集中度
    total_volume: float  # 总成交量
    hvn_count: int  # HVN数量
    volume_density: float  # 成交量密度

    # 其他指标
    squeeze_active: bool
    squeeze_bars: int
    confidence: float

    # 综合得分
    score: float = 0.0


@dataclass
class StrongLevel:
    """强支撑/压力位"""
    price_range: Tuple[float, float]  # (low, high)
    price_center: float
    level_type: str  # 'support' or 'resistance'

    # 成交量指标
    total_volume: float
    volume_strength: int  # 0-100分
    timeframes: List[str]  # 来源周期
    hvn_overlap: int  # HVN重叠数
    density_score: int  # 成交量密度得分


@dataclass
class DualBoxResult:
    """两层箱体结果"""
    symbol: str
    primary_box: BoxCandidate  # 主箱体
    secondary_box: BoxCandidate  # 次箱体

    # 强成交位
    strong_support: Optional[StrongLevel]
    strong_resistance: Optional[StrongLevel]

    # 共振区
    resonance_zones: List[VolumeResonanceZone]

    # 综合评分
    overall_score: float
    volume_factor: float
    position_factor: float
    squeeze_factor: float


def calculate_box_score(
    analysis: TimeframeAnalysis,
    current_price: float,
    is_primary: bool = True
) -> float:
    """
    计算箱体得分（成交量优先）

    Args:
        analysis: 单周期分析结果
        current_price: 当前价格
        is_primary: 是否作为主箱体评分

    Returns:
        综合得分 0-100
    """
    vp = analysis.volume_profile

    # 1. 成交量集中度得分（40%权重）
    volume_conc_score = min(analysis.volume_concentration / 0.70 * 100, 100)

    # 2. HVN数量得分（30%权重）
    hvn_score = min(len(analysis.enhanced_hvns) / 10 * 100, 100)

    # 3. 成交量密度得分（20%权重）
    max_density = 10000  # 经验值
    density_score = min(analysis.avg_volume_density / max_density * 100, 100)

    # 4. 箱体宽度得分（10%权重）
    # 主箱体：宽度适中为好（5-15%）
    # 次箱体：宽度窄为好（< 8%）
    box_width = ((vp.vah - vp.val) / vp.vpoc) * 100 if vp.vpoc > 0 else 0

    if is_primary:
        if 5 <= box_width <= 15:
            width_score = 100
        elif box_width < 5:
            width_score = box_width / 5 * 80
        else:
            width_score = max(0, 100 - (box_width - 15) * 5)
    else:
        if box_width <= 8:
            width_score = 100
        else:
            width_score = max(0, 100 - (box_width - 8) * 10)

    # 综合得分
    score = (
        volume_conc_score * 0.40 +
        hvn_score * 0.30 +
        density_score * 0.20 +
        width_score * 0.10
    )

    return round(score, 2)


def select_primary_box(
    analyses: List[TimeframeAnalysis],
    current_price: float
) -> BoxCandidate:
    """
    选择主箱体（成交量最密集的大范围区间）

    优先级：
        1. 成交量集中度 > 65%
        2. HVN数量多
        3. 成交量密度高
        4. 箱体宽度适中（5-15%）

    Args:
        analyses: 多周期分析结果
        current_price: 当前价格

    Returns:
        主箱体候选
    """
    candidates = []

    for analysis in analyses:
        vp = analysis.volume_profile

        # 基本筛选：成交量集中度至少55%
        if analysis.volume_concentration < 0.55:
            continue

        box_width_pct = ((vp.vah - vp.val) / vp.vpoc) * 100 if vp.vpoc > 0 else 0

        # 计算得分
        score = calculate_box_score(analysis, current_price, is_primary=True)

        candidates.append(BoxCandidate(
            timeframe=analysis.timeframe,
            support=vp.val,
            resistance=vp.vah,
            midpoint=vp.vpoc,
            range_pct=round(box_width_pct, 2),
            volume_concentration=analysis.volume_concentration,
            total_volume=analysis.total_volume,
            hvn_count=len(analysis.enhanced_hvns),
            volume_density=analysis.avg_volume_density,
            squeeze_active=False,  # 后续补充
            squeeze_bars=0,
            confidence=0.0,
            score=score
        ))

    if not candidates:
        # 降低标准：允许成交量集中度45%+
        for analysis in analyses:
            vp = analysis.volume_profile
            if analysis.volume_concentration < 0.45:
                continue

            box_width_pct = ((vp.vah - vp.val) / vp.vpoc) * 100 if vp.vpoc > 0 else 0
            score = calculate_box_score(analysis, current_price, is_primary=True) * 0.8  # 降权

            candidates.append(BoxCandidate(
                timeframe=analysis.timeframe,
                support=vp.val,
                resistance=vp.vah,
                midpoint=vp.vpoc,
                range_pct=round(box_width_pct, 2),
                volume_concentration=analysis.volume_concentration,
                total_volume=analysis.total_volume,
                hvn_count=len(analysis.enhanced_hvns),
                volume_density=analysis.avg_volume_density,
                squeeze_active=False,
                squeeze_bars=0,
                confidence=0.0,
                score=score
            ))

    # 选择得分最高的
    if candidates:
        return max(candidates, key=lambda x: x.score)

    # 兜底：选择成交量最大的
    return BoxCandidate(
        timeframe=analyses[0].timeframe,
        support=analyses[0].volume_profile.val,
        resistance=analyses[0].volume_profile.vah,
        midpoint=analyses[0].volume_profile.vpoc,
        range_pct=0,
        volume_concentration=analyses[0].volume_concentration,
        total_volume=analyses[0].total_volume,
        hvn_count=len(analyses[0].enhanced_hvns),
        volume_density=analyses[0].avg_volume_density,
        squeeze_active=False,
        squeeze_bars=0,
        confidence=0.0,
        score=0
    )


def select_secondary_box(
    analyses: List[TimeframeAnalysis],
    primary_box: BoxCandidate,
    current_price: float
) -> BoxCandidate:
    """
    选择次箱体（当前价格附近的强成交区）

    优先级：
        1. 成交量密度最高
        2. 距离当前价格近
        3. 箱体宽度窄（精确入场）
        4. 排除主箱体所在周期

    Args:
        analyses: 多周期分析结果
        primary_box: 已选的主箱体
        current_price: 当前价格

    Returns:
        次箱体候选
    """
    candidates = []

    for analysis in analyses:
        # 跳过主箱体的周期
        if analysis.timeframe == primary_box.timeframe:
            continue

        vp = analysis.volume_profile

        # 检查是否在当前价格附近（±10%）
        distance_to_vpoc = abs(vp.vpoc - current_price) / current_price
        if distance_to_vpoc > 0.10:
            continue

        box_width_pct = ((vp.vah - vp.val) / vp.vpoc) * 100 if vp.vpoc > 0 else 0

        # 计算得分
        base_score = calculate_box_score(analysis, current_price, is_primary=False)

        # 距离惩罚
        distance_penalty = distance_to_vpoc * 100  # 距离越远扣分越多
        score = max(0, base_score - distance_penalty)

        candidates.append(BoxCandidate(
            timeframe=analysis.timeframe,
            support=vp.val,
            resistance=vp.vah,
            midpoint=vp.vpoc,
            range_pct=round(box_width_pct, 2),
            volume_concentration=analysis.volume_concentration,
            total_volume=analysis.total_volume,
            hvn_count=len(analysis.enhanced_hvns),
            volume_density=analysis.avg_volume_density,
            squeeze_active=False,
            squeeze_bars=0,
            confidence=0.0,
            score=score
        ))

    if candidates:
        return max(candidates, key=lambda x: x.score)

    # 兜底：选择主箱体之外成交量密度最高的
    remaining = [a for a in analyses if a.timeframe != primary_box.timeframe]
    if remaining:
        best = max(remaining, key=lambda a: a.avg_volume_density)
        vp = best.volume_profile
        box_width_pct = ((vp.vah - vp.val) / vp.vpoc) * 100 if vp.vpoc > 0 else 0

        return BoxCandidate(
            timeframe=best.timeframe,
            support=vp.val,
            resistance=vp.vah,
            midpoint=vp.vpoc,
            range_pct=round(box_width_pct, 2),
            volume_concentration=best.volume_concentration,
            total_volume=best.total_volume,
            hvn_count=len(best.enhanced_hvns),
            volume_density=best.avg_volume_density,
            squeeze_active=False,
            squeeze_bars=0,
            confidence=0.0,
            score=0
        )

    # 最后兜底
    return primary_box


def identify_strong_levels(
    resonance_zones: List[VolumeResonanceZone],
    current_price: float
) -> Tuple[Optional[StrongLevel], Optional[StrongLevel]]:
    """
    识别强支撑/压力位（基于成交量共振）

    Args:
        resonance_zones: 成交量共振区列表
        current_price: 当前价格

    Returns:
        (强支撑位, 强压力位)
    """
    strong_support = None
    strong_resistance = None

    # 筛选支撑和压力
    support_zones = [z for z in resonance_zones if z.zone_type == 'support']
    resistance_zones = [z for z in resonance_zones if z.zone_type == 'resistance']

    # 选择最强的支撑位
    if support_zones:
        best_support = max(support_zones, key=lambda z: z.strength)
        strong_support = StrongLevel(
            price_range=(best_support.price_low, best_support.price_high),
            price_center=best_support.price_center,
            level_type='support',
            total_volume=best_support.total_volume,
            volume_strength=int(best_support.strength),
            timeframes=best_support.timeframes,
            hvn_overlap=best_support.hvn_count,
            density_score=min(int(best_support.hvn_count / 5 * 100), 100)
        )

    # 选择最强的压力位
    if resistance_zones:
        best_resistance = max(resistance_zones, key=lambda z: z.strength)
        strong_resistance = StrongLevel(
            price_range=(best_resistance.price_low, best_resistance.price_high),
            price_center=best_resistance.price_center,
            level_type='resistance',
            total_volume=best_resistance.total_volume,
            volume_strength=int(best_resistance.strength),
            timeframes=best_resistance.timeframes,
            hvn_overlap=best_resistance.hvn_count,
            density_score=min(int(best_resistance.hvn_count / 5 * 100), 100)
        )

    return strong_support, strong_resistance


def calculate_overall_score(
    primary_box: BoxCandidate,
    secondary_box: BoxCandidate,
    strong_support: Optional[StrongLevel],
    strong_resistance: Optional[StrongLevel]
) -> Tuple[float, float, float, float]:
    """
    计算综合评分

    Returns:
        (overall_score, volume_factor, position_factor, squeeze_factor)
    """
    # 1. 成交量因子（60%权重）
    primary_volume_score = primary_box.volume_concentration * 100
    secondary_volume_score = secondary_box.volume_concentration * 100
    level_strength = 0
    if strong_support:
        level_strength += strong_support.volume_strength
    if strong_resistance:
        level_strength += strong_resistance.volume_strength
    level_strength = min(level_strength / 2, 100)  # 平均并限制100

    volume_factor = (
        primary_volume_score * 0.4 +
        secondary_volume_score * 0.35 +
        level_strength * 0.25
    )

    # 2. 位置关系因子（20%权重）
    # 检查次箱体是否在主箱体内
    overlap = 0
    if (secondary_box.support >= primary_box.support and
        secondary_box.resistance <= primary_box.resistance):
        overlap = 100  # 完全包含
    elif (secondary_box.support < primary_box.resistance and
          secondary_box.resistance > primary_box.support):
        # 部分重叠
        overlap_range = min(secondary_box.resistance, primary_box.resistance) - \
                       max(secondary_box.support, primary_box.support)
        secondary_range = secondary_box.resistance - secondary_box.support
        overlap = (overlap_range / secondary_range * 100) if secondary_range > 0 else 0

    position_factor = overlap

    # 3. Squeeze因子（15%权重）
    squeeze_factor = 0
    if primary_box.squeeze_active:
        squeeze_factor += 50
    if secondary_box.squeeze_active:
        squeeze_factor += 50

    # 4. 综合得分
    overall_score = (
        volume_factor * 0.60 +
        position_factor * 0.20 +
        squeeze_factor * 0.15 +
        (primary_box.score + secondary_box.score) / 2 * 0.05
    )

    return (
        round(overall_score, 2),
        round(volume_factor, 2),
        round(position_factor, 2),
        round(squeeze_factor, 2)
    )


def select_dual_box(
    analyses: List[TimeframeAnalysis],
    resonance_zones: List[VolumeResonanceZone],
    symbol: str
) -> DualBoxResult:
    """
    选择两层箱体

    Args:
        analyses: 多周期分析结果
        resonance_zones: 成交量共振区
        symbol: 交易对

    Returns:
        DualBoxResult对象
    """
    if not analyses:
        raise ValueError("No timeframe analyses provided")

    current_price = analyses[0].klines[-1].close

    # 1. 选择主箱体
    primary_box = select_primary_box(analyses, current_price)

    # 2. 选择次箱体
    secondary_box = select_secondary_box(analyses, primary_box, current_price)

    # 3. 识别强支撑/压力位
    strong_support, strong_resistance = identify_strong_levels(
        resonance_zones, current_price
    )

    # 4. 计算综合评分
    overall, volume_f, position_f, squeeze_f = calculate_overall_score(
        primary_box, secondary_box, strong_support, strong_resistance
    )

    return DualBoxResult(
        symbol=symbol,
        primary_box=primary_box,
        secondary_box=secondary_box,
        strong_support=strong_support,
        strong_resistance=strong_resistance,
        resonance_zones=resonance_zones,
        overall_score=overall,
        volume_factor=volume_f,
        position_factor=position_f,
        squeeze_factor=squeeze_f
    )
