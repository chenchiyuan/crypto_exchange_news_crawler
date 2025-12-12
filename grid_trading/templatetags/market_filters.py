"""Django template filters for market data formatting"""
from django import template
from decimal import Decimal


register = template.Library()


@register.filter(name='format_market_cap')
def format_market_cap(value):
    """格式化市值/FDV为K/M/B格式

    Args:
        value: Decimal或float类型的金额

    Returns:
        格式化后的字符串（如 $1.23B, $456.78M）

    Example:
        {{ result.market_cap|format_market_cap }}
        输出: $1.23B
    """
    if value is None:
        return "-"

    try:
        # 转换为float进行计算
        if isinstance(value, Decimal):
            value = float(value)
        elif not isinstance(value, (int, float)):
            return "-"

        # K/M/B格式化
        if value >= 1_000_000_000:
            return f"${value / 1_000_000_000:.2f}B"
        elif value >= 1_000_000:
            return f"${value / 1_000_000:.2f}M"
        elif value >= 1_000:
            return f"${value / 1_000:.2f}K"
        else:
            return f"${value:.2f}"

    except (ValueError, TypeError):
        return "-"


@register.filter(name='format_fdv')
def format_fdv(value):
    """格式化FDV（别名filter，复用format_market_cap逻辑）

    Args:
        value: Decimal或float类型的金额

    Returns:
        格式化后的字符串（如 $1.23B, $456.78M）

    Example:
        {{ result.fdv|format_fdv }}
        输出: $456.78M
    """
    return format_market_cap(value)
