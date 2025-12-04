"""
挂单位置优化器

用途: 基于RSI和历史统计计算最优做空挂单价格
算法文档: docs/entry_algorithm_final.md
"""

import numpy as np
from typing import List, Dict, Any, Optional
from decimal import Decimal
import logging

logger = logging.getLogger("grid_trading")


def calculate_rebound_potential(rsi_15m: float, ema99_slope: float, natr: float) -> float:
    """
    基于RSI + 趋势 + 波动率，计算理论反弹幅度

    Args:
        rsi_15m: 15分钟K线的RSI(14)
        ema99_slope: 4小时EMA99斜率
        natr: 归一化ATR（日线）

    Returns:
        理论反弹幅度（小数，如0.02表示2%）
    """
    # 1. 基础反弹幅度（基于RSI）
    if rsi_15m >= 75:
        base_rebound = 0.003  # 0.3%
    elif rsi_15m >= 70:
        base_rebound = 0.005  # 0.5%
    elif rsi_15m >= 65:
        base_rebound = 0.01   # 1.0%
    elif rsi_15m >= 60:
        base_rebound = 0.015  # 1.5%
    elif rsi_15m >= 55:
        base_rebound = 0.02   # 2.0%
    elif rsi_15m >= 50:
        base_rebound = 0.025  # 2.5%
    elif rsi_15m >= 45:
        base_rebound = 0.03   # 3.0%
    elif rsi_15m >= 40:
        base_rebound = 0.04   # 4.0%
    else:
        base_rebound = 0.05   # 5.0%

    # 2. 趋势修正系数
    if ema99_slope < -100:
        trend_factor = 0.5
    elif ema99_slope < -50:
        trend_factor = 0.7
    elif ema99_slope < -20:
        trend_factor = 0.85
    elif ema99_slope < 0:
        trend_factor = 1.0
    elif ema99_slope < 20:
        trend_factor = 1.15
    elif ema99_slope < 50:
        trend_factor = 1.3
    else:
        trend_factor = 1.5

    # 3. 波动率修正系数
    if natr < 2:
        volatility_factor = 0.6
    elif natr < 4:
        volatility_factor = 0.8
    elif natr < 6:
        volatility_factor = 1.0
    elif natr < 8:
        volatility_factor = 1.2
    else:
        volatility_factor = 1.5

    # 4. 综合计算
    adjusted_rebound = base_rebound * trend_factor * volatility_factor

    # 5. 上限保护（最多不超过8%反弹）
    adjusted_rebound = min(adjusted_rebound, 0.08)

    return adjusted_rebound


def calculate_trigger_probability_from_history(
    target_gain_pct: float,
    klines_15m: List[Dict[str, Any]],
    time_window_hours: int = 24
) -> Dict[str, Any]:
    """
    统计过去7天，价格从任意点反弹到target_gain_pct的频率

    Args:
        target_gain_pct: 目标涨幅（小数形式，如0.0115表示1.15%）
        klines_15m: 15分钟K线列表（至少672根，7天×24小时×4）
        time_window_hours: 时间窗口（默认24小时）

    Returns:
        {
            'probability': 触发概率（0-1），
            'trigger_count': 触发次数,
            'total_windows': 总窗口数,
            'avg_time_to_trigger': 平均触发时间（小时）
        }
    """
    # 参数校验
    if len(klines_15m) < 672:
        # 数据不足，返回保守估计
        logger.warning(f"历史K线数据不足7天 (仅{len(klines_15m)}根)，无法精确计算触发概率")
        return {
            'probability': 1.0 if target_gain_pct == 0 else 0.5,  # 降级估计
            'trigger_count': 0,
            'total_windows': 0,
            'avg_time_to_trigger': 0.0
        }

    # 取最近7天数据
    recent_klines = klines_15m[-672:]

    # 时间窗口参数
    bars_per_window = time_window_hours * 4  # 15分钟K线，1小时=4根

    # 滑动窗口统计
    trigger_count = 0
    total_windows = 0
    trigger_times = []

    # 遍历每个可能的起点
    for i in range(len(recent_klines) - bars_per_window):
        base_close = float(recent_klines[i]['close'])

        # 计算未来time_window_hours内的价格波动
        future_bars = recent_klines[i+1 : i+1+bars_per_window]

        # 检查是否触发
        triggered = False
        trigger_bar_index = None

        for j, bar in enumerate(future_bars):
            gain = (float(bar['high']) - base_close) / base_close

            if gain >= target_gain_pct:
                triggered = True
                trigger_bar_index = j
                break

        if triggered:
            trigger_count += 1
            trigger_time_hours = (trigger_bar_index + 1) * 0.25  # 15分钟 = 0.25小时
            trigger_times.append(trigger_time_hours)

        total_windows += 1

    # 计算统计结果
    probability = trigger_count / total_windows if total_windows > 0 else 0.0
    avg_time = sum(trigger_times) / len(trigger_times) if trigger_times else 0.0

    return {
        'probability': probability,
        'trigger_count': trigger_count,
        'total_windows': total_windows,
        'avg_time_to_trigger': avg_time
    }


def generate_entry_recommendations(
    symbol: str,
    current_price: float,
    grid_lower: float,
    rsi_15m: float,
    ema99_slope: float,
    natr: float,
    klines_15m: List[Dict[str, Any]],
    min_trigger_prob: float = 0.6
) -> Dict[str, Any]:
    """
    生成3个候选挂单价格，并推荐最优方案

    Args:
        symbol: 标的代码
        current_price: 当前价格
        grid_lower: 网格下限（止盈目标）
        rsi_15m: 15分钟RSI
        ema99_slope: 4小时EMA99斜率
        natr: 归一化ATR
        klines_15m: 15分钟K线历史数据
        min_trigger_prob: 最小可接受触发概率（默认60%）

    Returns:
        {
            'symbol': 标的代码,
            'current_price': 当前价格,
            'market_state': 市场状态,
            'candidates': 候选方案列表,
            'recommended': 推荐方案
        }
    """
    # 边界情况1: 极度超买（RSI>75）
    if rsi_15m > 75:
        return {
            'symbol': symbol,
            'current_price': current_price,
            'market_state': {
                'rsi_15m': rsi_15m,
                'ema99_slope': ema99_slope,
                'interpretation': '极度超买，建议立即入场'
            },
            'candidates': [{
                'label': '立即入场',
                'entry_price': current_price,
                'rebound_pct': 0.0,
                'trigger_prob_24h': 1.0,
                'trigger_prob_72h': 1.0,
                'profit_potential': (current_price - grid_lower) / current_price,
                'expected_return_24h': (current_price - grid_lower) / current_price,
                'avg_trigger_time': 0.0
            }],
            'recommended': {
                'label': '立即入场',
                'entry_price': current_price,
                'reason': 'RSI>75极度超买，可能即将回调',
                'trigger_prob_24h': 1.0
            }
        }

    # 边界情况2: 强上涨趋势（EMA99>50）
    if ema99_slope > 50:
        return {
            'symbol': symbol,
            'current_price': current_price,
            'market_state': {
                'rsi_15m': rsi_15m,
                'ema99_slope': ema99_slope,
                'interpretation': '⚠️ 强上涨趋势，不建议做空'
            },
            'candidates': [],
            'recommended': None,
            'warning': '强上涨趋势（EMA99>50），不建议做空'
        }

    # 计算理论反弹幅度
    theoretical_rebound = calculate_rebound_potential(rsi_15m, ema99_slope, natr)

    # 生成3个候选价格
    candidates = []

    # 候选1: 立即入场（0%反弹）
    candidates.append({
        'label': '立即入场',
        'rebound_pct': 0.0,
        'entry_price': current_price
    })

    # 候选2: 保守反弹（理论反弹的50%）
    conservative_rebound = theoretical_rebound * 0.5
    candidates.append({
        'label': '保守反弹',
        'rebound_pct': conservative_rebound,
        'entry_price': current_price * (1 + conservative_rebound)
    })

    # 候选3: 理论反弹（100%理论值）
    candidates.append({
        'label': '理论反弹',
        'rebound_pct': theoretical_rebound,
        'entry_price': current_price * (1 + theoretical_rebound)
    })

    # 对每个候选价格计算触发概率和盈利空间
    for candidate in candidates:
        entry_price = candidate['entry_price']

        # 计算触发概率（24小时和72小时）
        trigger_24h = calculate_trigger_probability_from_history(
            candidate['rebound_pct'], klines_15m, time_window_hours=24
        )
        trigger_72h = calculate_trigger_probability_from_history(
            candidate['rebound_pct'], klines_15m, time_window_hours=72
        )

        candidate['trigger_prob_24h'] = trigger_24h['probability']
        candidate['trigger_prob_72h'] = trigger_72h['probability']
        candidate['avg_trigger_time'] = trigger_24h['avg_time_to_trigger']

        # 计算盈利空间
        profit_potential = (entry_price - grid_lower) / entry_price
        candidate['profit_potential'] = profit_potential

        # 计算期望收益
        candidate['expected_return_24h'] = profit_potential * trigger_24h['probability']
        candidate['expected_return_72h'] = profit_potential * trigger_72h['probability']

    # 选择推荐方案（基于24小时期望收益）
    candidates_sorted = sorted(candidates, key=lambda x: x['expected_return_24h'], reverse=True)

    # 应用触发概率过滤（至少要min_trigger_prob以上）
    valid_candidates = [c for c in candidates_sorted if c['trigger_prob_24h'] >= min_trigger_prob]

    if not valid_candidates:
        # 如果没有满足条件的，推荐立即入场
        recommended = candidates[0]
        recommended['reason'] = f'所有反弹方案触发概率偏低（<{min_trigger_prob*100:.0f}%），推荐立即入场'
    else:
        recommended = valid_candidates[0]
        if recommended['label'] == '立即入场':
            recommended['reason'] = '立即入场期望收益最高'
        else:
            prob_24h = recommended['trigger_prob_24h'] * 100
            avg_time = recommended['avg_trigger_time']
            recommended['reason'] = f"触发概率{prob_24h:.0f}%，平均{avg_time:.1f}小时触发"

    return {
        'symbol': symbol,
        'current_price': current_price,
        'market_state': {
            'rsi_15m': rsi_15m,
            'ema99_slope': ema99_slope,
            'natr': natr,
            'theoretical_rebound': theoretical_rebound
        },
        'candidates': candidates,
        'recommended': recommended
    }
