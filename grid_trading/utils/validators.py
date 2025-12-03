"""
参数验证器

用途: 验证命令行参数的合法性
关联FR: FR-027, FR-035
"""

import math
from decimal import Decimal
from django.core.management.base import CommandError


def validate_weights(weights_str: str) -> list:
    """
    验证权重参数 (FR-027)

    Args:
        weights_str: 权重字符串，格式为 "w1,w2,w3,w4"

    Returns:
        权重列表 [w1, w2, w3, w4]

    Raises:
        CommandError: 权重格式错误或总和≠1.0
    """
    try:
        weights = [float(w.strip()) for w in weights_str.split(",")]
    except ValueError:
        raise CommandError("权重格式错误,应为逗号分隔的浮点数,如'0.2,0.2,0.3,0.3'")

    if len(weights) != 4:
        raise CommandError(f"权重必须为4个数值,当前为{len(weights)}个")

    if not math.isclose(sum(weights), 1.0, abs_tol=1e-6):
        raise CommandError(f"权重总和必须=1.0,当前为{sum(weights):.4f}")

    return weights


def validate_top_n(top_n: int) -> int:
    """
    验证Top N参数 (FR-029, FR-035)

    Args:
        top_n: 输出Top N标的数量

    Returns:
        验证后的top_n值

    Raises:
        CommandError: 超出范围3-10
    """
    if not 3 <= top_n <= 10:
        raise CommandError(f"--top-n必须在3-10之间,当前为{top_n}")

    return top_n


def validate_min_volume(min_volume: float) -> Decimal:
    """
    验证流动性阈值参数 (FR-002, FR-035)

    Args:
        min_volume: 最小流动性阈值 (USDT)

    Returns:
        验证后的Decimal值

    Raises:
        CommandError: 负数或零
    """
    if min_volume <= 0:
        raise CommandError(f"--min-volume必须大于0,当前为{min_volume}")

    return Decimal(str(min_volume))


def validate_min_days(min_days: int) -> int:
    """
    验证上市天数参数 (FR-003, FR-035)

    Args:
        min_days: 最小上市天数

    Returns:
        验证后的min_days值

    Raises:
        CommandError: 负数或零
    """
    if min_days <= 0:
        raise CommandError(f"--min-days必须大于0,当前为{min_days}")

    return min_days
