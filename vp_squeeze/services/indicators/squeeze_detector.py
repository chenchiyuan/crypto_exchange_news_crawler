"""Squeeze检测模块"""
from typing import Dict, List
from vp_squeeze.dto import SqueezeStatus
from vp_squeeze.constants import SQUEEZE_CONSECUTIVE_BARS


def detect_squeeze(
    bb: Dict[str, List],
    kc: Dict[str, List],
    consecutive_required: int = SQUEEZE_CONSECUTIVE_BARS
) -> SqueezeStatus:
    """
    检测Squeeze状态（低波动率盘整）

    Squeeze条件: BB收缩进入KC内部
        BB_Upper < KC_Upper AND BB_Lower > KC_Lower

    Args:
        bb: Bollinger Bands数据 {'upper': [], 'middle': [], 'lower': []}
        kc: Keltner Channels数据 {'upper': [], 'middle': [], 'lower': []}
        consecutive_required: 需要连续满足条件的K线数，默认3

    Returns:
        SqueezeStatus对象
    """
    bb_upper = bb.get('upper', [])
    bb_lower = bb.get('lower', [])
    kc_upper = kc.get('upper', [])
    kc_lower = kc.get('lower', [])

    # 确保所有列表长度一致
    length = min(len(bb_upper), len(bb_lower), len(kc_upper), len(kc_lower))

    squeeze_signals = []
    for i in range(length):
        bb_u = bb_upper[i]
        bb_l = bb_lower[i]
        kc_u = kc_upper[i]
        kc_l = kc_lower[i]

        # 检查是否所有值都有效
        if all(v is not None for v in [bb_u, bb_l, kc_u, kc_l]):
            # Squeeze条件: BB在KC内部
            is_squeeze = (bb_u < kc_u) and (bb_l > kc_l)
            squeeze_signals.append(is_squeeze)
        else:
            squeeze_signals.append(False)

    # 计算连续满足Squeeze条件的K线数
    consecutive_count = 0
    for s in reversed(squeeze_signals):
        if s:
            consecutive_count += 1
        else:
            break

    # 检查最近N根K线是否连续满足Squeeze条件
    is_active = consecutive_count >= consecutive_required

    # 确定可靠度
    reliability = 'high' if is_active else 'low'

    return SqueezeStatus(
        active=is_active,
        consecutive_bars=consecutive_count,
        reliability=reliability,
        signals=squeeze_signals
    )
