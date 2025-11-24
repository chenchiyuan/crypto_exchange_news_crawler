"""基础技术指标计算函数（纯Python实现）"""
from typing import List, Optional


def sma(prices: List[float], period: int) -> List[Optional[float]]:
    """
    简单移动平均 (Simple Moving Average)

    Args:
        prices: 价格列表
        period: 计算周期

    Returns:
        SMA值列表，前period-1个值为None
    """
    result = []
    for i in range(len(prices)):
        if i < period - 1:
            result.append(None)
        else:
            window = prices[i - period + 1:i + 1]
            result.append(sum(window) / period)
    return result


def ema(prices: List[float], period: int) -> List[float]:
    """
    指数移动平均 (Exponential Moving Average)

    Args:
        prices: 价格列表
        period: 计算周期

    Returns:
        EMA值列表
    """
    if not prices:
        return []

    result = []
    multiplier = 2 / (period + 1)

    for i, price in enumerate(prices):
        if i == 0:
            result.append(price)
        elif i < period:
            # 前period个值逐步收敛
            result.append((price - result[-1]) * multiplier + result[-1])
        else:
            result.append((price - result[-1]) * multiplier + result[-1])

    return result


def std(prices: List[float], period: int) -> List[Optional[float]]:
    """
    标准差 (Standard Deviation)

    Args:
        prices: 价格列表
        period: 计算周期

    Returns:
        标准差列表，前period-1个值为None
    """
    sma_values = sma(prices, period)
    result = []

    for i in range(len(prices)):
        if i < period - 1 or sma_values[i] is None:
            result.append(None)
        else:
            window = prices[i - period + 1:i + 1]
            mean = sma_values[i]
            variance = sum((x - mean) ** 2 for x in window) / period
            result.append(variance ** 0.5)

    return result


def true_range(high: List[float], low: List[float], close: List[float]) -> List[float]:
    """
    真实波幅 (True Range)

    Args:
        high: 最高价列表
        low: 最低价列表
        close: 收盘价列表

    Returns:
        真实波幅列表
    """
    result = []
    for i in range(len(high)):
        if i == 0:
            tr = high[i] - low[i]
        else:
            tr = max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1])
            )
        result.append(tr)
    return result


def atr(high: List[float], low: List[float], close: List[float], period: int) -> List[float]:
    """
    平均真实波幅 (Average True Range)

    Args:
        high: 最高价列表
        low: 最低价列表
        close: 收盘价列表
        period: 计算周期

    Returns:
        ATR值列表
    """
    tr = true_range(high, low, close)
    return ema(tr, period)


def format_price(price: float) -> str:
    """
    根据价格量级格式化显示

    规则:
        - 价格>100: 保留2位小数
        - 10-100: 保留3位小数
        - <10: 保留4位小数

    Args:
        price: 价格

    Returns:
        格式化后的价格字符串
    """
    if price >= 100:
        return f"{price:,.2f}"
    elif price >= 10:
        return f"{price:,.3f}"
    else:
        return f"{price:,.4f}"
