"""Volume Profile计算模块"""
from typing import Dict, List
from vp_squeeze.dto import KLineData, VolumeProfileResult
from vp_squeeze.constants import VP_RESOLUTION_PCT, VP_VALUE_AREA_PCT, VP_HVN_PERCENTILE, VP_LVN_PERCENTILE


def calculate_volume_profile(
    klines: List[KLineData],
    resolution_pct: float = VP_RESOLUTION_PCT
) -> VolumeProfileResult:
    """
    计算Volume Profile (成交量剖面)

    算法:
        1. 确定价格范围和分辨率（当前价格的0.1%）
        2. 创建价格桶
        3. 将每根K线的成交量按价格范围比例分配到桶中
        4. 计算VPOC（最大成交量价格）
        5. 计算价值区域（70%成交量区间）
        6. 识别HVN/LVN（百分位数方式）

    Args:
        klines: K线数据列表
        resolution_pct: 价格分辨率百分比，默认0.001（0.1%）

    Returns:
        VolumeProfileResult对象
    """
    if not klines:
        return VolumeProfileResult(
            vpoc=0, vah=0, val=0, hvn=[], lvn=[], profile={}
        )

    # 1. 确定价格范围
    all_highs = [k.high for k in klines]
    all_lows = [k.low for k in klines]
    price_min = min(all_lows)
    price_max = max(all_highs)
    current_price = klines[-1].close

    # 使用当前价格的指定百分比作为桶大小
    bucket_size = current_price * resolution_pct
    if bucket_size <= 0:
        bucket_size = 1.0

    # 2. 创建价格桶
    buckets: Dict[float, float] = {}
    bucket_start = price_min - (price_min % bucket_size)
    while bucket_start <= price_max + bucket_size:
        buckets[bucket_start] = 0.0
        bucket_start += bucket_size

    # 3. 分配成交量到价格桶
    for k in klines:
        kline_range = k.high - k.low
        if kline_range <= 0:
            # 价格没有变化，全部成交量放入一个桶
            bucket_key = k.close - (k.close % bucket_size)
            if bucket_key in buckets:
                buckets[bucket_key] += k.volume
        else:
            # 按价格范围比例分配
            for bucket_price in buckets:
                bucket_high = bucket_price + bucket_size
                overlap_low = max(bucket_price, k.low)
                overlap_high = min(bucket_high, k.high)
                if overlap_high > overlap_low:
                    overlap_ratio = (overlap_high - overlap_low) / kline_range
                    buckets[bucket_price] += k.volume * overlap_ratio

    # 过滤掉零成交量的桶
    buckets = {k: v for k, v in buckets.items() if v > 0}

    if not buckets:
        return VolumeProfileResult(
            vpoc=current_price, vah=current_price, val=current_price,
            hvn=[], lvn=[], profile={}
        )

    # 4. 计算VPOC（最大成交量价格）
    vpoc_bucket = max(buckets, key=buckets.get)
    vpoc = vpoc_bucket + bucket_size / 2

    # 5. 计算价值区域（70%成交量区间）
    total_volume = sum(buckets.values())
    target_volume = total_volume * VP_VALUE_AREA_PCT

    sorted_buckets = sorted(buckets.items(), key=lambda x: x[0])
    bucket_prices = [b[0] for b in sorted_buckets]

    # 找到VPOC在排序后的索引
    try:
        vpoc_idx = bucket_prices.index(vpoc_bucket)
    except ValueError:
        vpoc_idx = len(bucket_prices) // 2

    included_volume = buckets.get(vpoc_bucket, 0)
    val_idx, vah_idx = vpoc_idx, vpoc_idx

    # 从VPOC向两侧扩展
    while included_volume < target_volume:
        left_vol = sorted_buckets[val_idx - 1][1] if val_idx > 0 else 0
        right_vol = sorted_buckets[vah_idx + 1][1] if vah_idx < len(sorted_buckets) - 1 else 0

        if left_vol == 0 and right_vol == 0:
            break

        if left_vol >= right_vol and val_idx > 0:
            val_idx -= 1
            included_volume += left_vol
        elif vah_idx < len(sorted_buckets) - 1:
            vah_idx += 1
            included_volume += right_vol
        else:
            break

    val = sorted_buckets[val_idx][0]
    vah = sorted_buckets[vah_idx][0] + bucket_size

    # 6. 识别HVN和LVN（百分位数方式）
    volumes = list(buckets.values())
    volumes_sorted = sorted(volumes)

    if len(volumes_sorted) > 0:
        p80_idx = int(len(volumes_sorted) * VP_HVN_PERCENTILE)
        p20_idx = int(len(volumes_sorted) * VP_LVN_PERCENTILE)
        p80 = volumes_sorted[min(p80_idx, len(volumes_sorted) - 1)]
        p20 = volumes_sorted[min(p20_idx, len(volumes_sorted) - 1)]
    else:
        p80 = 0
        p20 = 0

    hvn = [
        {'low': p, 'high': p + bucket_size, 'volume': v}
        for p, v in buckets.items() if v >= p80
    ]
    lvn = [
        {'low': p, 'high': p + bucket_size, 'volume': v}
        for p, v in buckets.items() if v <= p20 and v > 0
    ]

    return VolumeProfileResult(
        vpoc=vpoc,
        vah=vah,
        val=val,
        hvn=hvn,
        lvn=lvn,
        profile=buckets
    )
