"""
指标计算器模块

从策略16中提取的指标计算逻辑，供多个策略复用。

核心功能：
- 计算EMA系列指标（EMA7, EMA25, EMA99）
- 计算概率带（P5, P95）
- 计算惯性中值
- 计算周期状态

迭代编号: 045 (策略20-多交易对共享资金池)
创建日期: 2026-01-14
复用来源: strategy16_limit_entry.py._calculate_indicators
"""

import logging
from typing import Dict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def calculate_indicators(
    klines_df: pd.DataFrame,
    interval_hours: float = 4.0
) -> Dict[str, pd.Series]:
    """
    计算策略所需的技术指标

    从K线数据计算以下指标：
    - ema7: 7周期EMA
    - ema25: 25周期EMA
    - ema99: 99周期EMA
    - p5: 5%分位支撑
    - p95: 95%分位压力
    - inertia_mid: 惯性中值
    - cycle_phase: 周期状态

    Args:
        klines_df: K线数据DataFrame，index为DatetimeIndex
        interval_hours: K线周期（小时），默认4.0

    Returns:
        Dict: 指标字典，key为指标名，value为pd.Series

    Example:
        >>> indicators = calculate_indicators(klines_df)
        >>> indicators['ema25'].iloc[-1]  # 获取最后一根K线的EMA25
    """
    from ddps_z.calculators.ema_calculator import EMACalculator
    from ddps_z.calculators.ewma_calculator import EWMACalculator
    from ddps_z.calculators.inertia_calculator import InertiaCalculator
    from ddps_z.calculators.adx_calculator import ADXCalculator
    from ddps_z.calculators.beta_cycle_calculator import BetaCycleCalculator

    prices = klines_df['close'].values
    high = klines_df['high'].values
    low = klines_df['low'].values
    timestamps_ms = np.array([int(ts.timestamp() * 1000) for ts in klines_df.index])

    # EMA计算
    ema7_calc = EMACalculator(period=7)
    ema25_calc = EMACalculator(period=25)
    ema99_calc = EMACalculator(period=99)
    ewma_calc = EWMACalculator(window_n=50)

    ema7_array = ema7_calc.calculate_ema_series(prices)
    ema25_array = ema25_calc.calculate_ema_series(prices)
    ema99_array = ema99_calc.calculate_ema_series(prices)

    # P5和P95计算
    deviation = ema25_calc.calculate_deviation_series(prices)
    _, ewma_std_series = ewma_calc.calculate_ewma_stats(deviation)
    z_p5 = -1.645
    z_p95 = 1.645
    p5_array = ema25_array * (1 + z_p5 * ewma_std_series)
    p95_array = ema25_array * (1 + z_p95 * ewma_std_series)

    # 惯性计算
    adx_calc = ADXCalculator(period=14)
    inertia_calc = InertiaCalculator(base_period=5)

    adx_result = adx_calc.calculate(high, low, prices)
    adx_series = adx_result['adx']

    fan_result = inertia_calc.calculate_historical_fan_series(
        timestamps=timestamps_ms,
        ema_series=ema25_array,
        sigma_series=ewma_std_series,
        adx_series=adx_series
    )
    inertia_mid_array = fan_result['mid']
    beta_array = fan_result['beta']

    # 周期计算
    cycle_calc = BetaCycleCalculator()
    beta_list = [b if not np.isnan(b) else None for b in beta_array]
    cycle_phases, _ = cycle_calc.calculate(
        beta_list=beta_list,
        timestamps=timestamps_ms.tolist(),
        prices=prices.tolist(),
        interval_hours=interval_hours
    )

    return {
        'ema7': pd.Series(ema7_array, index=klines_df.index),
        'ema25': pd.Series(ema25_array, index=klines_df.index),
        'ema99': pd.Series(ema99_array, index=klines_df.index),
        'p5': pd.Series(p5_array, index=klines_df.index),
        'p95': pd.Series(p95_array, index=klines_df.index),
        'inertia_mid': pd.Series(inertia_mid_array, index=klines_df.index),
        'cycle_phase': pd.Series(cycle_phases, index=klines_df.index),
        'beta': pd.Series(beta_array, index=klines_df.index),
    }


def get_indicators_at_index(
    indicators: Dict[str, pd.Series],
    index: int
) -> Dict[str, any]:
    """
    获取指定索引位置的所有指标值

    Args:
        indicators: 指标字典
        index: K线索引

    Returns:
        Dict: 该索引位置的指标值字典
    """
    return {
        key: series.iloc[index] if index < len(series) else None
        for key, series in indicators.items()
    }
