"""置信率计算器 - 多因子综合评分"""
from dataclasses import dataclass
from typing import Optional

from vp_squeeze.constants import SQUEEZE_CONSECUTIVE_BARS


@dataclass
class BoxRange:
    """箱体范围"""
    support: float       # 支撑位 (VAL)
    resistance: float    # 压力位 (VAH)
    midpoint: float      # 中点 (VPOC)
    range_pct: float     # 箱体宽度百分比


@dataclass
class ConfidenceResult:
    """置信率计算结果"""
    confidence: float           # 综合置信率 0-1
    confidence_pct: int         # 置信率百分比 0-100

    # 各因子得分 (0-1)
    squeeze_score: float        # Squeeze状态得分
    volume_concentration: float # 成交量集中度得分
    volatility_score: float     # 价格波动率得分
    range_score: float          # 价值区域宽度得分

    # 因子权重
    weights: dict


# 因子权重配置
FACTOR_WEIGHTS = {
    'squeeze': 0.30,           # Squeeze状态 30%
    'volume_concentration': 0.35,  # 成交量集中度 35%
    'volatility': 0.20,        # 价格波动率 20%
    'range_width': 0.15,       # 价值区域宽度 15%
}


def calculate_box_range(
    val: float,
    vah: float,
    vpoc: float
) -> BoxRange:
    """
    计算箱体范围

    Args:
        val: Value Area Low (支撑位)
        vah: Value Area High (压力位)
        vpoc: Volume Point of Control (成交量重心)

    Returns:
        BoxRange对象
    """
    midpoint = vpoc
    range_pct = ((vah - val) / midpoint) * 100 if midpoint > 0 else 0

    return BoxRange(
        support=val,
        resistance=vah,
        midpoint=midpoint,
        range_pct=round(range_pct, 2)
    )


def calculate_squeeze_score(
    active: bool,
    consecutive_bars: int
) -> float:
    """
    计算Squeeze状态得分

    规则:
        - 未激活: 0
        - 3根K线: 0.6
        - 5根K线: 0.8
        - 7根+: 1.0
        - 线性插值中间值
    """
    if not active:
        return 0.0

    if consecutive_bars <= SQUEEZE_CONSECUTIVE_BARS:
        return 0.6
    elif consecutive_bars <= 5:
        # 3-5根之间线性插值 0.6 -> 0.8
        return 0.6 + (consecutive_bars - 3) * 0.1
    elif consecutive_bars <= 7:
        # 5-7根之间线性插值 0.8 -> 1.0
        return 0.8 + (consecutive_bars - 5) * 0.1
    else:
        return 1.0


def calculate_volume_concentration(
    val: float,
    vah: float,
    profile: dict,
    total_volume: float
) -> float:
    """
    计算成交量集中度得分

    规则: VAL-VAH区间内成交量占总成交量的比例
    - 70%以下: 低集中度，得分按比例
    - 70%-85%: 中等集中度
    - 85%+: 高集中度
    """
    if total_volume <= 0 or not profile:
        return 0.5  # 无数据时返回中等得分

    # 计算VAL-VAH区间内的成交量
    box_volume = 0.0
    for price_bucket, volume in profile.items():
        try:
            price = float(price_bucket)
            if val <= price <= vah:
                box_volume += volume
        except (ValueError, TypeError):
            continue

    concentration = box_volume / total_volume if total_volume > 0 else 0

    # 归一化到0-1分数
    # Volume Profile的value area默认覆盖70%，所以70%是基准
    if concentration >= 0.85:
        return 1.0
    elif concentration >= 0.70:
        # 70%-85%之间线性映射到0.7-1.0
        return 0.7 + (concentration - 0.70) / 0.15 * 0.3
    else:
        # 70%以下线性映射到0-0.7
        return concentration / 0.70 * 0.7


def calculate_volatility_score(
    bb_upper: Optional[float],
    bb_lower: Optional[float],
    current_price: float
) -> float:
    """
    计算价格波动率得分

    规则: BB宽度相对于价格的比例，越窄得分越高
    - BB宽度/价格 < 2%: 高分 (0.9-1.0)
    - BB宽度/价格 2-5%: 中分 (0.6-0.9)
    - BB宽度/价格 > 5%: 低分 (0-0.6)
    """
    if bb_upper is None or bb_lower is None or current_price <= 0:
        return 0.5  # 无数据时返回中等得分

    bb_width = bb_upper - bb_lower
    width_pct = (bb_width / current_price) * 100

    if width_pct <= 2:
        # 非常窄，高分
        return 0.9 + (2 - width_pct) / 2 * 0.1
    elif width_pct <= 5:
        # 中等宽度
        return 0.9 - (width_pct - 2) / 3 * 0.3
    elif width_pct <= 10:
        # 较宽
        return 0.6 - (width_pct - 5) / 5 * 0.3
    else:
        # 很宽，低分
        return max(0.1, 0.3 - (width_pct - 10) / 10 * 0.2)


def calculate_range_score(
    val: float,
    vah: float,
    vpoc: float
) -> float:
    """
    计算价值区域宽度得分

    规则: (VAH-VAL)/VPOC，越窄越高分（箱体更明确）
    - < 3%: 高分 (0.9-1.0)
    - 3-8%: 中分 (0.5-0.9)
    - > 8%: 低分 (0-0.5)
    """
    if vpoc <= 0:
        return 0.5

    range_pct = ((vah - val) / vpoc) * 100

    if range_pct <= 3:
        return 0.9 + (3 - range_pct) / 3 * 0.1
    elif range_pct <= 8:
        return 0.9 - (range_pct - 3) / 5 * 0.4
    elif range_pct <= 15:
        return 0.5 - (range_pct - 8) / 7 * 0.3
    else:
        return max(0.1, 0.2 - (range_pct - 15) / 15 * 0.1)


def calculate_confidence(
    squeeze_active: bool,
    squeeze_consecutive_bars: int,
    val: float,
    vah: float,
    vpoc: float,
    profile: dict,
    total_volume: float,
    bb_upper: Optional[float] = None,
    bb_lower: Optional[float] = None,
    current_price: Optional[float] = None
) -> ConfidenceResult:
    """
    计算综合置信率

    Args:
        squeeze_active: Squeeze是否激活
        squeeze_consecutive_bars: 连续满足Squeeze条件的K线数
        val: Value Area Low
        vah: Value Area High
        vpoc: Volume Point of Control
        profile: 价格桶->成交量映射
        total_volume: 总成交量
        bb_upper: Bollinger Band上轨
        bb_lower: Bollinger Band下轨
        current_price: 当前价格（用于波动率计算）

    Returns:
        ConfidenceResult对象
    """
    # 如果没有current_price，使用VPOC作为参考价格
    if current_price is None:
        current_price = vpoc

    # 计算各因子得分
    squeeze_score = calculate_squeeze_score(squeeze_active, squeeze_consecutive_bars)
    volume_score = calculate_volume_concentration(val, vah, profile, total_volume)
    volatility_score = calculate_volatility_score(bb_upper, bb_lower, current_price)
    range_score = calculate_range_score(val, vah, vpoc)

    # 加权综合得分
    confidence = (
        squeeze_score * FACTOR_WEIGHTS['squeeze'] +
        volume_score * FACTOR_WEIGHTS['volume_concentration'] +
        volatility_score * FACTOR_WEIGHTS['volatility'] +
        range_score * FACTOR_WEIGHTS['range_width']
    )

    return ConfidenceResult(
        confidence=round(confidence, 4),
        confidence_pct=round(confidence * 100),
        squeeze_score=round(squeeze_score, 4),
        volume_concentration=round(volume_score, 4),
        volatility_score=round(volatility_score, 4),
        range_score=round(range_score, 4),
        weights=FACTOR_WEIGHTS.copy()
    )
