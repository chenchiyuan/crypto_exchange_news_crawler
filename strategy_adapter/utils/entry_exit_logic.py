"""
买卖逻辑工具函数模块

从策略16中提取的核心买卖逻辑，供多个策略复用。

核心函数：
- calculate_base_price: 计算基准价格
- calculate_order_price: 计算挂单价格
- calculate_sell_price: 计算卖出挂单价格
- should_skip_entry: 判断是否跳过入场

迭代编号: 045 (策略20-多交易对共享资金池)
创建日期: 2026-01-14
复用来源: strategy16_limit_entry.py
"""

from decimal import Decimal
from typing import Optional, Tuple


def calculate_base_price(
    p5: Decimal,
    close: Decimal,
    inertia_mid: Decimal
) -> Decimal:
    """
    计算基准价格

    公式: base_price = min(p5, close, (p5+mid)/2)

    Args:
        p5: P5支撑价格
        close: 收盘价
        inertia_mid: 惯性中值

    Returns:
        Decimal: 基准价格

    Example:
        >>> base = calculate_base_price(
        ...     Decimal("3200"), Decimal("3250"), Decimal("3180")
        ... )
        >>> base == Decimal("3190")  # (3200+3180)/2 = 3190
        True
    """
    mid_p5 = (p5 + inertia_mid) / 2
    return min(p5, close, mid_p5)


def calculate_order_price(
    base_price: Decimal,
    discount: Decimal
) -> Decimal:
    """
    计算挂单价格

    公式: order_price = base_price × (1 - discount)

    Args:
        base_price: 基准价格
        discount: 折扣比例（如 0.001 表示 0.1%）

    Returns:
        Decimal: 挂单价格

    Example:
        >>> price = calculate_order_price(Decimal("3200"), Decimal("0.001"))
        >>> price == Decimal("3196.8")  # 3200 * 0.999
        True
    """
    return base_price * (1 - discount)


def calculate_sell_price(
    cycle_phase: str,
    ema25: Decimal,
    p95: Decimal
) -> Tuple[Decimal, str]:
    """
    根据周期计算卖出挂单价和原因

    卖出价格规则（复用策略16）：
    - 下跌期（bear_warning, bear_strong）: 挂单价 = EMA25
    - 震荡期（consolidation）: 挂单价 = (P95 + EMA25) / 2
    - 上涨期（bull_warning, bull_strong）: 挂单价 = P95

    Args:
        cycle_phase: 周期状态
        ema25: EMA25值
        p95: P95压力价格

    Returns:
        Tuple[Decimal, str]: (卖出挂单价, 原因说明)

    Example:
        >>> price, reason = calculate_sell_price(
        ...     "consolidation", Decimal("3200"), Decimal("3400")
        ... )
        >>> price == Decimal("3300")  # (3400+3200)/2
        True
    """
    if cycle_phase in ('bear_warning', 'bear_strong'):
        sell_price = ema25
        reason = f"EMA25挂单止盈 (EMA25={float(ema25):.2f})"
    elif cycle_phase == 'consolidation':
        sell_price = (p95 + ema25) / 2
        reason = f"震荡期挂单止盈 ((P95+EMA25)/2={float(sell_price):.2f})"
    else:  # bull_warning, bull_strong
        sell_price = p95
        reason = f"P95挂单止盈 (P95={float(p95):.2f})"

    return sell_price, reason


def should_skip_entry(cycle_phase: Optional[str]) -> bool:
    """
    判断是否跳过入场

    跳过条件：bear_warning 周期

    Args:
        cycle_phase: 当前周期状态

    Returns:
        bool: True表示跳过入场，False表示允许入场

    Example:
        >>> should_skip_entry("bear_warning")
        True
        >>> should_skip_entry("consolidation")
        False
        >>> should_skip_entry(None)
        False
    """
    return cycle_phase == 'bear_warning'


def is_buy_order_filled(low: Decimal, order_price: Decimal) -> bool:
    """
    判断买入挂单是否成交

    成交条件: low <= order_price

    Args:
        low: K线最低价
        order_price: 挂单价格

    Returns:
        bool: True表示成交
    """
    return low <= order_price


def is_sell_order_filled(high: Decimal, order_price: Decimal) -> bool:
    """
    判断卖出挂单是否成交

    成交条件: high >= order_price

    Args:
        high: K线最高价
        order_price: 挂单价格

    Returns:
        bool: True表示成交
    """
    return high >= order_price


def calculate_profit(
    sell_price: Decimal,
    buy_price: Decimal,
    quantity: Decimal
) -> Tuple[Decimal, Decimal]:
    """
    计算订单盈亏

    Args:
        sell_price: 卖出价格
        buy_price: 买入价格
        quantity: 数量

    Returns:
        Tuple[Decimal, Decimal]: (盈亏金额, 盈亏率%)
    """
    profit_loss = (sell_price - buy_price) * quantity
    profit_rate = (sell_price / buy_price - 1) * 100
    return profit_loss, profit_rate
