"""Keltner Channels计算模块"""
from typing import Dict, List, Optional
from .utils import ema, atr
from vp_squeeze.constants import KC_EMA_PERIOD, KC_ATR_PERIOD, KC_MULTIPLIER


def calculate_keltner_channels(
    high: List[float],
    low: List[float],
    close: List[float],
    ema_period: int = KC_EMA_PERIOD,
    atr_period: int = KC_ATR_PERIOD,
    multiplier: float = KC_MULTIPLIER
) -> Dict[str, List[Optional[float]]]:
    """
    计算Keltner Channels (肯特纳通道)

    公式:
        中轨 = EMA(close, ema_period)
        上轨 = 中轨 + ATR(atr_period) × multiplier
        下轨 = 中轨 - ATR(atr_period) × multiplier

    Args:
        high: 最高价列表
        low: 最低价列表
        close: 收盘价列表
        ema_period: EMA周期，默认20
        atr_period: ATR周期，默认10
        multiplier: ATR倍数，默认1.5

    Returns:
        {
            'upper': 上轨列表,
            'middle': 中轨列表,
            'lower': 下轨列表
        }
    """
    middle = ema(close, ema_period)
    atr_values = atr(high, low, close, atr_period)

    upper = []
    lower = []

    for m, a in zip(middle, atr_values):
        if m is not None and a is not None:
            upper.append(m + multiplier * a)
            lower.append(m - multiplier * a)
        else:
            upper.append(None)
            lower.append(None)

    return {
        'upper': upper,
        'middle': middle,
        'lower': lower
    }
