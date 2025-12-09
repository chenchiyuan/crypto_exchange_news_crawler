"""
规则判定工具函数
Rule Utility Functions

提供MA计算、价格分布计算、K线连续性检测等工具函数
Feature: 001-price-alert-monitor
"""
import logging
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from decimal import Decimal

logger = logging.getLogger("grid_trading")


def calculate_ma(klines: List[Dict], period: int = 20) -> float:
    """
    计算移动平均线(MA)

    Args:
        klines: K线数据列表，每个元素为字典，至少包含'close'字段
        period: MA周期，默认20

    Returns:
        float: 最新的MA值，如果数据不足返回None

    Example:
        klines = [
            {'close': '100.5', 'open_time': '...'},
            {'close': '101.2', 'open_time': '...'},
            ...
        ]
        ma20 = calculate_ma(klines, period=20)
        print(f"MA20: {ma20:.2f}")

    Note:
        使用pandas rolling mean实现，自动处理边界情况
    """
    if not klines or len(klines) < period:
        logger.warning(f"K线数据不足: 需要{period}根，实际{len(klines)}根")
        return None

    try:
        # 转换为DataFrame
        df = pd.DataFrame(klines)

        # 确保close字段为float类型
        df['close'] = df['close'].astype(float)

        # 计算MA
        ma = df['close'].rolling(window=period).mean()

        # 返回最新的MA值
        latest_ma = float(ma.iloc[-1])

        if pd.isna(latest_ma):
            logger.warning(f"MA计算结果为NaN (period={period}, klines={len(klines)})")
            return None

        return latest_ma

    except Exception as e:
        logger.error(f"MA计算失败: {e}")
        return None


def calculate_price_distribution(
    klines: List[Dict],
    percentile: int = 90
) -> Tuple[float, float]:
    """
    计算价格分布区间

    Args:
        klines: K线数据列表，每个元素包含'high'和'low'字段
        percentile: 分位数(默认90，表示90%分位)

    Returns:
        (lower_bound, upper_bound): 价格区间下限和上限
        如果数据不足返回(None, None)

    Example:
        klines_7d = get_klines('BTCUSDT', '4h', limit=42)  # 7天=42根4h K线
        lower, upper = calculate_price_distribution(klines_7d, percentile=90)
        print(f"90%分位价格区间: [{lower:.2f}, {upper:.2f}]")

    Note:
        - 合并所有高点和低点作为价格样本
        - 计算分位数: 下限=(100-percentile)/2, 上限=100-(100-percentile)/2
        - 例如90%分位: 下限=5%, 上限=95%
    """
    if not klines or len(klines) < 2:
        logger.warning(f"K线数据不足: 至少需要2根，实际{len(klines)}根")
        return (None, None)

    try:
        # 提取所有高点和低点
        highs = [float(k['high']) for k in klines]
        lows = [float(k['low']) for k in klines]

        # 合并所有价格点
        all_prices = highs + lows

        # 计算分位数
        lower_percentile = (100 - percentile) / 2  # 例如90%分位: 5%
        upper_percentile = 100 - lower_percentile   # 例如90%分位: 95%

        lower_bound = np.percentile(all_prices, lower_percentile)
        upper_bound = np.percentile(all_prices, upper_percentile)

        return (float(lower_bound), float(upper_bound))

    except Exception as e:
        logger.error(f"价格分布计算失败: {e}")
        return (None, None)


def validate_kline_continuity(
    klines: List[Dict],
    interval: str,
    tolerance_pct: float = 10.0
) -> Dict:
    """
    检测K线数据的连续性

    Args:
        klines: K线数据列表，每个元素包含'open_time'和'close_time'字段
        interval: K线周期('1m', '15m', '4h'等)
        tolerance_pct: 容忍的缺失百分比，默认10%(即允许缺失10%的数据)

    Returns:
        dict: {
            'is_continuous': bool,        # 是否连续
            'total_klines': int,          # 总K线数
            'gaps_count': int,            # 缺口数量
            'missing_pct': float,         # 缺失百分比
            'gaps': List[Tuple],          # 缺口列表[(start_time, end_time), ...]
            'message': str                # 检测结果描述
        }

    Example:
        klines = get_klines('BTCUSDT', '4h', limit=42)
        result = validate_kline_continuity(klines, '4h')
        if not result['is_continuous']:
            print(f"警告: K线数据不连续，缺失{result['missing_pct']:.1f}%")
    """
    # K线周期到分钟数的映射
    interval_minutes = {
        '1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30,
        '1h': 60, '2h': 120, '4h': 240, '6h': 360, '8h': 480, '12h': 720,
        '1d': 1440, '3d': 4320, '1w': 10080
    }

    if interval not in interval_minutes:
        logger.error(f"不支持的K线周期: {interval}")
        return {
            'is_continuous': False,
            'total_klines': 0,
            'gaps_count': 0,
            'missing_pct': 100.0,
            'gaps': [],
            'message': f'不支持的K线周期: {interval}'
        }

    if not klines or len(klines) < 2:
        return {
            'is_continuous': True,
            'total_klines': len(klines),
            'gaps_count': 0,
            'missing_pct': 0.0,
            'gaps': [],
            'message': 'K线数据不足2根，无需检测连续性'
        }

    try:
        delta = timedelta(minutes=interval_minutes[interval])
        gaps = []

        # 检测相邻K线之间的缺口
        for i in range(len(klines) - 1):
            current_kline = klines[i]
            next_kline = klines[i + 1]

            # 解析时间戳(假设为毫秒时间戳或datetime对象)
            if isinstance(current_kline['close_time'], (int, float)):
                current_close = datetime.fromtimestamp(current_kline['close_time'] / 1000)
            else:
                current_close = current_kline['close_time']

            if isinstance(next_kline['open_time'], (int, float)):
                next_open = datetime.fromtimestamp(next_kline['open_time'] / 1000)
            else:
                next_open = next_kline['open_time']

            # 预期下一根K线的开始时间
            expected_next = current_close + timedelta(milliseconds=1)

            # 检查是否有缺口(允许1秒的误差)
            time_diff = (next_open - expected_next).total_seconds()
            if time_diff > delta.total_seconds() + 1:
                gaps.append((expected_next, next_open))

        # 计算缺失百分比
        gaps_count = len(gaps)
        total_klines = len(klines)
        missing_pct = (gaps_count / total_klines * 100) if total_klines > 0 else 0.0

        # 判断是否连续
        is_continuous = missing_pct <= tolerance_pct

        # 生成结果描述
        if is_continuous:
            if gaps_count == 0:
                message = 'K线数据完全连续'
            else:
                message = f'K线数据基本连续(缺失{missing_pct:.1f}%，在容忍范围内)'
        else:
            message = f'K线数据不连续(缺失{missing_pct:.1f}%，超过容忍阈值{tolerance_pct}%)'

        return {
            'is_continuous': is_continuous,
            'total_klines': total_klines,
            'gaps_count': gaps_count,
            'missing_pct': missing_pct,
            'gaps': gaps,
            'message': message
        }

    except Exception as e:
        logger.error(f"K线连续性检测失败: {e}")
        return {
            'is_continuous': False,
            'total_klines': len(klines),
            'gaps_count': 0,
            'missing_pct': 0.0,
            'gaps': [],
            'message': f'检测失败: {str(e)}'
        }


def get_7d_high_low(klines: List[Dict]) -> Tuple[float, float]:
    """
    获取7天内的最高价和最低价

    Args:
        klines: K线数据列表(4h周期，7天=42根)

    Returns:
        (max_high, min_low): 最高价和最低价
        如果数据不足返回(None, None)

    Example:
        klines_7d = get_klines('BTCUSDT', '4h', limit=42)
        high, low = get_7d_high_low(klines_7d)
        print(f"7天内最高: {high:.2f}, 最低: {low:.2f}")
    """
    if not klines:
        logger.warning("K线数据为空，无法计算7天高低价")
        return (None, None)

    try:
        highs = [float(k['high']) for k in klines]
        lows = [float(k['low']) for k in klines]

        max_high = max(highs)
        min_low = min(lows)

        return (max_high, min_low)

    except Exception as e:
        logger.error(f"7天高低价计算失败: {e}")
        return (None, None)


def check_price_in_range(
    price: Decimal,
    target: Decimal,
    threshold_pct: float = 0.5
) -> bool:
    """
    检查价格是否在目标价的阈值范围内

    Args:
        price: 当前价格
        target: 目标价格(如MA20)
        threshold_pct: 阈值百分比，默认0.5%

    Returns:
        True: 价格在目标价的±threshold_pct范围内
        False: 价格不在范围内

    Example:
        # 检查价格是否触及MA20(±0.5%)
        current_price = Decimal('1000.0')
        ma20 = Decimal('1003.0')
        is_touch = check_price_in_range(current_price, ma20, threshold_pct=0.5)
        # 1000.0 在 1003.0 ± 0.5% [997.985, 1008.015] 范围内? False
    """
    try:
        price_float = float(price)
        target_float = float(target)

        # 计算阈值范围
        threshold = target_float * (threshold_pct / 100)
        lower_bound = target_float - threshold
        upper_bound = target_float + threshold

        # 检查价格是否在范围内
        return lower_bound <= price_float <= upper_bound

    except Exception as e:
        logger.error(f"价格范围检查失败: {e}")
        return False


def format_klines_for_display(klines: List[Dict], limit: int = 5) -> str:
    """
    格式化K线数据用于日志显示

    Args:
        klines: K线数据列表
        limit: 显示前N根K线，默认5

    Returns:
        格式化后的字符串

    Example:
        klines = get_klines('BTCUSDT', '4h', limit=10)
        print(format_klines_for_display(klines, limit=3))
        # 输出:
        # K线数据(共10根，显示前3根):
        #   [1] 2025-12-08 00:00 O:43000.0 H:43500.0 L:42800.0 C:43200.0
        #   [2] 2025-12-08 04:00 O:43200.0 H:43800.0 L:43100.0 C:43600.0
        #   [3] 2025-12-08 08:00 O:43600.0 H:44000.0 L:43500.0 C:43900.0
    """
    if not klines:
        return "K线数据为空"

    lines = [f"K线数据(共{len(klines)}根，显示前{min(limit, len(klines))}根):"]

    for i, k in enumerate(klines[:limit]):
        # 解析时间
        if isinstance(k['open_time'], (int, float)):
            open_time = datetime.fromtimestamp(k['open_time'] / 1000).strftime('%Y-%m-%d %H:%M')
        else:
            open_time = k['open_time'].strftime('%Y-%m-%d %H:%M')

        # 格式化OHLC
        line = (
            f"  [{i+1}] {open_time} "
            f"O:{float(k['open']):.1f} "
            f"H:{float(k['high']):.1f} "
            f"L:{float(k['low']):.1f} "
            f"C:{float(k['close']):.1f}"
        )
        lines.append(line)

    if len(klines) > limit:
        lines.append(f"  ... (还有{len(klines) - limit}根)")

    return "\n".join(lines)
