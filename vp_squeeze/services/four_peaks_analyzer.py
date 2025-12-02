"""4峰值点位分析器 - 成交量峰值 + MA均线调整"""
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import logging

from vp_squeeze.dto import KLineData
from vp_squeeze.services.multi_timeframe_analyzer import TimeframeAnalysis
from vp_squeeze.services.indicators.utils import sma

logger = logging.getLogger(__name__)


@dataclass
class VolumePeak:
    """成交量峰值/区间（复用数据结构）"""
    price: float              # 峰值价格 或 区间中心价格
    volume: float             # 峰值成交量 或 区间总成交量
    volume_strength: float    # 成交量强度（归一化）
    prominence: float         # 显著性（与周围的差异）
    timeframes: List[str]     # 来源周期
    # 区间模式下的额外字段
    price_low: Optional[float] = None   # 区间下界
    price_high: Optional[float] = None  # 区间上界


@dataclass
class KeyLevel:
    """关键点位"""
    price: float              # 最终价格
    original_peak: float      # 原始峰值价格
    volume: float             # 成交量
    volume_strength: int      # 成交量强度 0-100
    ma_adjusted: bool         # 是否被MA调整过
    nearest_ma: Optional[float]  # 最近的MA
    ma_type: Optional[str]    # MA类型 (MA20/MA50/MA200)
    confidence: int           # 置信度 0-100
    level_type: str           # 类型: support1/support2/resistance1/resistance2


@dataclass
class FourPeaksBox:
    """4峰值箱体"""
    symbol: str

    # 4个关键点位
    support2: KeyLevel        # 支撑位2（大箱体下界）
    support1: KeyLevel        # 支撑位1（小箱体下界）
    resistance1: KeyLevel     # 压力位1（小箱体上界）
    resistance2: KeyLevel     # 压力位2（大箱体上界）

    # 箱体定义
    small_box: Dict           # 小箱体 {support, resistance, midpoint, width_pct}
    large_box: Dict           # 大箱体 {support, resistance, midpoint, width_pct}

    # 当前价格位置
    current_price: float
    position_in_box: str      # below_large/in_large/in_small/above_large

    # 综合评分
    overall_score: int        # 0-100
    volume_quality: int       # 成交量质量
    ma_alignment: int         # MA对齐度


def aggregate_volume_heatmap(
    analyses: List[TimeframeAnalysis],
    weights: Dict[str, float] = None
) -> Dict[float, float]:
    """
    聚合所有周期的成交量到统一热力图

    Args:
        analyses: 多周期分析结果
        weights: 周期权重，默认 {'4h': 1.5, '1h': 1.2, '15m': 1.0}

    Returns:
        {price: total_volume} 字典
    """
    if weights is None:
        weights = {'4h': 1.5, '1h': 1.2, '15m': 1.0}

    heatmap = {}

    for analysis in analyses:
        tf = analysis.timeframe
        vp = analysis.volume_profile
        weight = weights.get(tf, 1.0)

        for price, volume in vp.profile.items():
            if price not in heatmap:
                heatmap[price] = 0.0
            heatmap[price] += volume * weight

    return heatmap


def find_volume_clusters_by_window(
    heatmap: Dict[float, float],
    current_price: float,
    window_size: int = 5,
    price_range_pct: float = 0.15
) -> List[VolumePeak]:
    """
    使用滑动窗口识别成交量集中区间（不找峰值点）

    Args:
        heatmap: 成交量热力图
        current_price: 当前价格
        window_size: 窗口大小（价格桶数量）
        price_range_pct: 价格范围限制（15%）

    Returns:
        按总成交量排序的VolumePeak列表（复用数据结构，price存中心价）
    """
    prices = sorted(heatmap.keys())

    # 计算有效价格范围：当前价格±15%
    price_min = current_price * (1 - price_range_pct)
    price_max = current_price * (1 + price_range_pct)

    clusters = []

    # 滑动窗口扫描
    for i in range(len(prices) - window_size + 1):
        window_prices = prices[i:i+window_size]

        # 计算区间中心价格
        price_low = window_prices[0]
        price_high = window_prices[-1]
        price_center = (price_low + price_high) / 2

        # 过滤：忽略超出15%范围的区间
        if price_center < price_min or price_center > price_max:
            continue

        # 计算区间统计
        window_volumes = [heatmap[p] for p in window_prices]
        total_volume = sum(window_volumes)
        peak_volume = max(window_volumes)

        # 存储为VolumePeak结构（复用，但语义改为区间）
        clusters.append(VolumePeak(
            price=price_center,  # 存储中心价格
            volume=total_volume,  # 总成交量
            volume_strength=0,  # 后续计算
            prominence=0,  # 不再需要
            timeframes=[],
            price_low=price_low,  # 区间下界
            price_high=price_high  # 区间上界
        ))

    if not clusters:
        return []

    # 按总成交量降序排序
    clusters.sort(key=lambda c: c.volume, reverse=True)

    # 归一化成交量强度
    max_volume = clusters[0].volume
    for cluster in clusters:
        cluster.volume_strength = cluster.volume / max_volume

    return clusters


def find_volume_peaks(
    heatmap: Dict[float, float],
    min_prominence: float = 0.30
) -> List[VolumePeak]:
    """
    识别显著的成交量峰值

    Args:
        heatmap: 成交量热力图
        min_prominence: 最小显著性（峰值需要比周围高30%）

    Returns:
        VolumePeak列表，按成交量强度排序
    """
    if not heatmap:
        return []

    prices = sorted(heatmap.keys())
    volumes = [heatmap[p] for p in prices]
    max_volume = max(volumes)

    peaks = []

    # 窗口大小：前后各5个价格桶
    window = 5

    for i in range(window, len(volumes) - window):
        current_vol = volumes[i]

        # 检查是否为局部最大值
        is_local_max = all(current_vol >= volumes[j] for j in range(i - window, i + window + 1) if j != i)

        if not is_local_max:
            continue

        # 计算显著性
        nearby_vols = [volumes[j] for j in range(i - window, i + window + 1) if j != i]
        avg_nearby = sum(nearby_vols) / len(nearby_vols) if nearby_vols else 0

        if avg_nearby > 0:
            prominence = (current_vol - avg_nearby) / avg_nearby
        else:
            prominence = 0

        # 筛选显著峰值
        if prominence >= min_prominence:
            peaks.append(VolumePeak(
                price=prices[i],
                volume=current_vol,
                volume_strength=current_vol / max_volume,
                prominence=prominence,
                timeframes=[]  # 后续补充
            ))

    # 按成交量强度排序
    peaks.sort(key=lambda p: p.volume_strength, reverse=True)

    return peaks


def calculate_ma25(klines: List[KLineData]) -> Optional[float]:
    """
    计算MA25均线当前值

    Args:
        klines: K线数据

    Returns:
        MA25值，如果数据不足返回None
    """
    closes = [k.close for k in klines]
    ma_values = sma(closes, 25)

    if ma_values and ma_values[-1] is not None:
        return ma_values[-1]

    return None


def calculate_ma_levels(
    klines: List[KLineData],
    periods: List[int] = [20, 50, 200]
) -> Dict[str, float]:
    """
    计算MA均线当前值（旧函数，保留兼容性）

    Args:
        klines: K线数据
        periods: MA周期列表

    Returns:
        {'MA20': value, 'MA50': value, 'MA200': value}
    """
    closes = [k.close for k in klines]
    ma_levels = {}

    for period in periods:
        ma_values = sma(closes, period)
        if ma_values and ma_values[-1] is not None:
            ma_levels[f'MA{period}'] = ma_values[-1]

    return ma_levels


def adjust_price_with_ma25(
    price: float,
    ma25: Optional[float],
    adjustment_threshold: float = 0.02
) -> Tuple[float, bool]:
    """
    使用MA25调整价格（仅MA25）

    Args:
        price: 原始价格
        ma25: MA25值
        adjustment_threshold: 调整阈值（2%）

    Returns:
        (调整后价格, 是否调整)
    """
    if ma25 is None:
        return price, False

    distance_pct = abs(price - ma25) / price

    if distance_pct < adjustment_threshold:
        return ma25, True
    else:
        return price, False


def adjust_peak_with_ma(
    peak_price: float,
    ma_levels: Dict[str, float],
    adjustment_threshold: float = 0.02
) -> Tuple[float, bool, Optional[float], Optional[str]]:
    """
    使用MA调整峰值价格

    规则：如果峰值距离某条MA < 2%，调整到MA位置
    优先级：MA20 > MA50 > MA200

    Args:
        peak_price: 原始峰值价格
        ma_levels: MA均线字典
        adjustment_threshold: 调整阈值（2%）

    Returns:
        (调整后价格, 是否调整, 最近MA值, MA类型)
    """
    # 按优先级检查：MA20 > MA50 > MA200
    priority_mas = [
        ('MA20', ma_levels.get('MA20')),
        ('MA50', ma_levels.get('MA50')),
        ('MA200', ma_levels.get('MA200'))
    ]

    # 记录最近的MA（用于未调整时的参考）
    min_distance = float('inf')
    nearest_ma = None
    nearest_ma_type = None

    for ma_type, ma_value in priority_mas:
        if ma_value is None:
            continue

        distance_pct = abs(peak_price - ma_value) / peak_price

        # 记录最近的MA
        if distance_pct < min_distance:
            min_distance = distance_pct
            nearest_ma = ma_value
            nearest_ma_type = ma_type

        # 优先级调整：满足阈值就立即使用
        if distance_pct < adjustment_threshold:
            return ma_value, True, ma_value, ma_type

    # 没有任何MA在阈值内
    return peak_price, False, nearest_ma, nearest_ma_type


def select_four_clusters(
    clusters: List[VolumePeak],
    current_price: float,
    min_distance_pct: float = 0.05
) -> Tuple[List[VolumePeak], List[VolumePeak]]:
    """
    从成交量区间列表中选择4个（上下各2个）

    规则：
        1. clusters已按总成交量降序排序
        2. 分为上下两组
        3. 每组选2个，满足5%最小间距

    Args:
        clusters: 成交量区间列表（已排序）
        current_price: 当前价格
        min_distance_pct: 最小间距百分比（5%）

    Returns:
        (下方区间列表, 上方区间列表)
    """
    # 分类：按中心价格
    below_clusters = [c for c in clusters if c.price < current_price]
    above_clusters = [c for c in clusters if c.price > current_price]

    # 筛选满足间距要求的
    def filter_by_distance(cluster_list, reverse=False):
        selected = []
        # 按中心价格排序
        sorted_clusters = sorted(cluster_list, key=lambda c: c.price, reverse=reverse)

        for cluster in sorted_clusters:
            # 检查与已选区间的距离
            too_close = False
            for sel in selected:
                distance_pct = abs(cluster.price - sel.price) / current_price
                if distance_pct < min_distance_pct:
                    too_close = True
                    break

            if not too_close:
                selected.append(cluster)

            if len(selected) >= 2:
                break

        return selected

    # 选择下方2个区间（从低到高）
    selected_below = filter_by_distance(below_clusters, reverse=False)

    # 选择上方2个区间（从高到低）
    selected_above = filter_by_distance(above_clusters, reverse=True)

    # 确保至少有2个
    if len(selected_below) < 2 or len(selected_above) < 2:
        logger.warning(f"区间不足！下方={len(selected_below)}, 上方={len(selected_above)}")

    # 排序：从低到高
    selected_below.sort(key=lambda c: c.price)
    selected_above.sort(key=lambda c: c.price)

    return selected_below, selected_above


def select_flexible_clusters(
    clusters: List[VolumePeak],
    current_price: float,
    min_distance_pct: float = 0.05
) -> Tuple[List[VolumePeak], List[VolumePeak]]:
    """
    灵活选择支撑位和压力位（0-4个）

    与select_four_clusters的区别：
    - 不强制要求4个区间
    - 允许0-2个支撑位，0-2个压力位
    - 至少返回1个区间（否则调用方应该已经过滤）

    Args:
        clusters: 成交量区间列表（已排序）
        current_price: 当前价格
        min_distance_pct: 最小间距百分比（5%）

    Returns:
        (下方区间列表, 上方区间列表)
        - 下方区间列表: 0-2个支撑位（按价格从低到高排序）
        - 上方区间列表: 0-2个压力位（按价格从低到高排序）
    """
    # 分类：按中心价格
    below_clusters = [c for c in clusters if c.price < current_price]
    above_clusters = [c for c in clusters if c.price > current_price]

    # 筛选满足间距要求的（最多2个）
    def filter_by_distance(cluster_list, reverse=False):
        selected = []
        # 按中心价格排序
        sorted_clusters = sorted(cluster_list, key=lambda c: c.price, reverse=reverse)

        for cluster in sorted_clusters:
            # 检查与已选区间的距离
            too_close = False
            for sel in selected:
                distance_pct = abs(cluster.price - sel.price) / current_price
                if distance_pct < min_distance_pct:
                    too_close = True
                    break

            if not too_close:
                selected.append(cluster)

            # ⭐⭐⭐ 关键：最多选2个，但允许少于2个
            if len(selected) >= 2:
                break

        return selected

    # 选择下方区间（支撑位，0-2个）
    selected_below = filter_by_distance(below_clusters, reverse=False)

    # 选择上方区间（压力位，0-2个）
    selected_above = filter_by_distance(above_clusters, reverse=True)

    # ⭐⭐⭐ 关键：不要求必须有2个，只记录日志
    if len(selected_below) < 2:
        logger.debug(f"支撑位不足2个: {len(selected_below)}")
    if len(selected_above) < 2:
        logger.debug(f"压力位不足2个: {len(selected_above)}")

    # 排序：从低到高
    selected_below.sort(key=lambda c: c.price)
    selected_above.sort(key=lambda c: c.price)

    return selected_below, selected_above


def select_four_peaks(
    peaks: List[VolumePeak],
    current_price: float,
    min_distance_pct: float = 0.05,
    fallback_vp: Dict = None
) -> Tuple[List[VolumePeak], List[VolumePeak]]:
    """
    选择4个峰值：当前价上下各2个（旧函数，保留兼容性）

    规则：
        1. 相邻峰值至少相距5%
        2. 上下各选2个成交量最强的
        3. 如果不足，使用VP边界补齐

    Args:
        peaks: 所有峰值列表
        current_price: 当前价格
        min_distance_pct: 最小间距百分比
        fallback_vp: 兜底VP数据 {val, vah, vpoc}

    Returns:
        (下方峰值列表, 上方峰值列表)
    """
    # 分类
    below_peaks = [p for p in peaks if p.price < current_price * 0.98]  # 下方（留2%缓冲）
    above_peaks = [p for p in peaks if p.price > current_price * 1.02]  # 上方

    # 已按成交量强度排序，现在筛选满足间距要求的
    def filter_by_distance(peak_list, reverse=False):
        selected = []
        sorted_peaks = sorted(peak_list, key=lambda p: p.price, reverse=reverse)

        for peak in sorted_peaks:
            # 检查与已选峰值的距离
            too_close = False
            for sel in selected:
                distance_pct = abs(peak.price - sel.price) / current_price
                if distance_pct < min_distance_pct:
                    too_close = True
                    break

            if not too_close:
                selected.append(peak)

            if len(selected) >= 2:
                break

        return selected

    # 选择下方2个峰值（从低到高）
    selected_below = filter_by_distance(below_peaks, reverse=False)

    # 选择上方2个峰值（从高到低）
    selected_above = filter_by_distance(above_peaks, reverse=True)

    # 如果不足，使用VP边界补齐
    if fallback_vp:
        while len(selected_below) < 2:
            if len(selected_below) == 0:
                # 第一个用VAL
                price = fallback_vp.get('val', current_price * 0.95)
            else:
                # 第二个在第一个和VAL之间取中点
                existing_price = selected_below[0].price
                val_price = fallback_vp.get('val', current_price * 0.95)
                price = (existing_price + val_price) / 2
                # 确保不重复
                if abs(price - existing_price) / current_price < 0.02:
                    price = existing_price * 0.95  # 往下偏移5%

            selected_below.insert(0, VolumePeak(
                price=price,
                volume=0,
                volume_strength=0.3,  # 兜底强度
                prominence=0,
                timeframes=['fallback']
            ))

        while len(selected_above) < 2:
            if len(selected_above) == 0:
                # 第一个用VAH
                price = fallback_vp.get('vah', current_price * 1.05)
            else:
                # 第二个在第一个和VAH之间取中点
                existing_price = selected_above[-1].price
                vah_price = fallback_vp.get('vah', current_price * 1.05)
                price = (existing_price + vah_price) / 2
                # 确保不重复
                if abs(price - existing_price) / current_price < 0.02:
                    price = existing_price * 1.05  # 往上偏移5%

            selected_above.append(VolumePeak(
                price=price,
                volume=0,
                volume_strength=0.3,
                prominence=0,
                timeframes=['fallback']
            ))

    # 排序：下方从低到高，上方从低到高
    selected_below.sort(key=lambda p: p.price)
    selected_above.sort(key=lambda p: p.price)

    return selected_below, selected_above


def create_key_level_from_cluster(
    cluster: VolumePeak,
    ma25: Optional[float],
    level_type: str,
    max_volume: float
) -> KeyLevel:
    """
    从成交量区间创建关键点位（新函数）

    规则：
    - resistance: 使用区间低价
    - support: 使用区间高价
    - 然后用MA25调整

    Args:
        cluster: 成交量区间（VolumePeak结构）
        ma25: MA25值
        level_type: 点位类型
        max_volume: 最大成交量

    Returns:
        KeyLevel对象
    """
    # 选择边界
    if level_type in ['resistance1', 'resistance2']:
        base_price = cluster.price_low if cluster.price_low else cluster.price
    else:
        base_price = cluster.price_high if cluster.price_high else cluster.price

    # MA25调整
    adjusted_price, was_adjusted = adjust_price_with_ma25(base_price, ma25)

    # 计算置信度
    volume_strength = (cluster.volume / max_volume) * 100
    base_confidence = int(volume_strength * 0.70)  # 成交量贡献70%

    # MA25调整加成
    ma_bonus = 25 if was_adjusted else 0

    # 区间宽度加成（区间越宽越可靠，最多5分）
    if cluster.price_low and cluster.price_high:
        width_pct = (cluster.price_high - cluster.price_low) / cluster.price
        width_bonus = min(int(width_pct * 500), 5)
    else:
        width_bonus = 0

    confidence = min(base_confidence + ma_bonus + width_bonus, 100)

    return KeyLevel(
        price=adjusted_price,
        original_peak=base_price,
        volume=cluster.volume,
        volume_strength=int(volume_strength),
        ma_adjusted=was_adjusted,
        nearest_ma=ma25 if ma25 else None,
        ma_type='MA25' if was_adjusted else None,
        confidence=confidence,
        level_type=level_type
    )


def create_key_level(
    peak: VolumePeak,
    ma_levels: Dict[str, float],
    level_type: str,
    max_volume: float
) -> KeyLevel:
    """
    创建关键点位（包含MA调整）

    Args:
        peak: 成交量峰值
        ma_levels: MA均线字典
        level_type: 点位类型
        max_volume: 最大成交量（用于归一化）

    Returns:
        KeyLevel对象
    """
    # MA调整
    adjusted_price, was_adjusted, nearest_ma, ma_type = adjust_peak_with_ma(
        peak.price, ma_levels
    )

    # 计算置信度
    base_confidence = int(peak.volume_strength * 70)  # 成交量贡献70%

    # MA贡献20%（优先级：MA20=30分, MA50=20分, MA200=10分）
    if was_adjusted:
        if ma_type == 'MA20':
            ma_bonus = 30
        elif ma_type == 'MA50':
            ma_bonus = 20
        else:  # MA200
            ma_bonus = 10
    else:
        ma_bonus = 5 if nearest_ma else 0  # 有MA参考但未调整，给5分

    prominence_bonus = min(int(peak.prominence * 10), 10)  # 显著性贡献10%

    confidence = min(base_confidence + ma_bonus + prominence_bonus, 100)

    return KeyLevel(
        price=adjusted_price,
        original_peak=peak.price,
        volume=peak.volume,
        volume_strength=int(peak.volume_strength * 100),
        ma_adjusted=was_adjusted,
        nearest_ma=nearest_ma,
        ma_type=ma_type,
        confidence=confidence,
        level_type=level_type
    )


def analyze_four_peaks(
    analyses: List[TimeframeAnalysis],
    symbol: str,
    verbose: bool = False
) -> FourPeaksBox:
    """
    执行4成交量区间箱体分析（优化算法）

    算法：
    1. 聚合多周期成交量
    2. 滑动窗口识别成交量集中区间（不找峰值）
    3. 过滤：只保留距当前价±15%范围的区间
    4. 选择成交量最大的4个区间
    5. 区间边界提取：压力用下界，支撑用上界
    6. MA25调整

    Args:
        analyses: 多周期分析结果
        symbol: 交易对
        verbose: 是否详细日志

    Returns:
        FourPeaksBox对象
    """
    if not analyses:
        raise ValueError("No analyses provided")

    current_price = analyses[0].klines[-1].close

    # 1. 聚合成交量热力图
    heatmap = aggregate_volume_heatmap(analyses)

    if verbose:
        logger.info(f"聚合成交量热力图: {len(heatmap)}个价格桶")

    # 2. 识别成交量集中区间（不找峰值！）
    clusters = find_volume_clusters_by_window(
        heatmap,
        current_price,
        window_size=5,
        price_range_pct=0.15  # 忽略超出±15%的区间
    )

    if verbose:
        logger.info(f"识别到 {len(clusters)} 个成交量区间（±15%范围内）")
        if clusters:
            logger.info(f"Top 4区间总成交量: {[int(c.volume) for c in clusters[:4]]}")

    if len(clusters) < 4:
        raise ValueError(f"成交量区间不足4个，仅识别到 {len(clusters)} 个")

    max_volume = clusters[0].volume if clusters else 1

    # 3. 计算MA25
    longest_tf_analysis = max(analyses, key=lambda a: len(a.klines))
    ma25 = calculate_ma25(longest_tf_analysis.klines)

    if verbose and ma25:
        logger.info(f"MA25: ${ma25:.2f}")

    # 4. 选择4个区间
    below_clusters, above_clusters = select_four_clusters(
        clusters,
        current_price,
        min_distance_pct=0.05
    )

    if len(below_clusters) < 2 or len(above_clusters) < 2:
        raise ValueError(
            f"区间数量不足！下方={len(below_clusters)}, 上方={len(above_clusters)}"
        )

    # 5. 创建4个关键点位（从区间边界）
    support2 = create_key_level_from_cluster(
        below_clusters[0], ma25, 'support2', max_volume
    )
    support1 = create_key_level_from_cluster(
        below_clusters[1], ma25, 'support1', max_volume
    )
    resistance1 = create_key_level_from_cluster(
        above_clusters[0], ma25, 'resistance1', max_volume
    )
    resistance2 = create_key_level_from_cluster(
        above_clusters[1], ma25, 'resistance2', max_volume
    )

    # 6. 定义箱体
    small_box = {
        'support': support1.price,
        'resistance': resistance1.price,
        'midpoint': (support1.price + resistance1.price) / 2,
        'width_pct': ((resistance1.price - support1.price) / support1.price) * 100
    }

    large_box = {
        'support': support2.price,
        'resistance': resistance2.price,
        'midpoint': (support2.price + resistance2.price) / 2,
        'width_pct': ((resistance2.price - support2.price) / support2.price) * 100
    }

    # 7. 判断当前价格位置
    if current_price < support2.price:
        position = 'below_large'
    elif current_price < support1.price:
        position = 'in_large_lower'
    elif current_price < resistance1.price:
        position = 'in_small'
    elif current_price < resistance2.price:
        position = 'in_large_upper'
    else:
        position = 'above_large'

    # 8. 综合评分
    volume_quality = int((
        support1.volume_strength * 0.25 +
        support2.volume_strength * 0.25 +
        resistance1.volume_strength * 0.25 +
        resistance2.volume_strength * 0.25
    ))

    # MA对齐度评分（只有MA25）
    ma_alignment_score = 0
    for level in [support1, support2, resistance1, resistance2]:
        if level.ma_adjusted and level.ma_type == 'MA25':
            ma_alignment_score += 25  # MA25调整加25分
    ma_alignment = min(ma_alignment_score, 100)  # 最高100分

    # 综合评分：成交量55% + MA对齐35% + 区间数量10%
    overall_score = int((
        volume_quality * 0.55 +
        ma_alignment * 0.35 +
        min(len(clusters) / 10, 1.0) * 10
    ))

    return FourPeaksBox(
        symbol=symbol,
        support2=support2,
        support1=support1,
        resistance1=resistance1,
        resistance2=resistance2,
        small_box=small_box,
        large_box=large_box,
        current_price=current_price,
        position_in_box=position,
        overall_score=overall_score,
        volume_quality=volume_quality,
        ma_alignment=ma_alignment
    )
