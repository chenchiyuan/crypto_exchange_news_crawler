"""Bollinger Bands计算模块"""
from typing import Dict, List, Optional
from .utils import sma, std
from vp_squeeze.constants import BB_PERIOD, BB_MULTIPLIER


def calculate_bollinger_bands(
    close: List[float],
    period: int = BB_PERIOD,
    multiplier: float = BB_MULTIPLIER
) -> Dict[str, List[Optional[float]]]:
    """
    计算Bollinger Bands (布林带)

    公式:
        中轨 = SMA(close, period)
        上轨 = 中轨 + std(close, period) × multiplier
        下轨 = 中轨 - std(close, period) × multiplier

    Args:
        close: 收盘价列表
        period: 计算周期，默认20
        multiplier: 标准差倍数，默认2.0

    Returns:
        {
            'upper': 上轨列表,
            'middle': 中轨列表,
            'lower': 下轨列表
        }
    """
    middle = sma(close, period)
    std_values = std(close, period)

    upper = []
    lower = []

    for m, s in zip(middle, std_values):
        if m is not None and s is not None:
            upper.append(m + multiplier * s)
            lower.append(m - multiplier * s)
        else:
            upper.append(None)
            lower.append(None)

    return {
        'upper': upper,
        'middle': middle,
        'lower': lower
    }
