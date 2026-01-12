"""
DDPS核心计算器 - 纯计算服务

只接收标准K线列表进行计算，不依赖任何数据库或外部数据源。
负责DDPS所有核心指标的计算。

Related:
    - Architecture: docs/iterations/024-ddps-multi-market-support/architecture.md
    - TASK: TASK-024-006
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

import numpy as np
from scipy.stats import norm

from ddps_z.models import StandardKLine, Interval
from ddps_z.calculators import EMACalculator, EWMACalculator, BetaCycleCalculator
from ddps_z.calculators.inertia_calculator import InertiaCalculator
from ddps_z.calculators.adx_calculator import ADXCalculator

logger = logging.getLogger(__name__)


@dataclass
class DDPSResult:
    """
    DDPS计算结果数据类

    包含所有DDPS核心指标的计算结果。

    Attributes:
        current_price: 当前价格
        ema25: EMA25均线值
        p5: P5价格（5%分位）
        p95: P95价格（95%分位）
        ewma_std: EWMA标准差
        probability: 概率位置（0-100）
        inertia_mid: 惯性中值
        inertia_upper: 惯性上界
        inertia_lower: 惯性下界
        beta: 当前Beta值
        cycle_phase: 周期阶段
        cycle_duration_bars: 周期持续K线数
        cycle_duration_hours: 周期持续小时数
        adx: ADX指标值（迭代038新增）
        cycle_phases: 最近N根K线的周期状态列表（迭代038新增）
    """
    current_price: Decimal
    ema25: Decimal
    p5: Decimal
    p95: Decimal
    ewma_std: float
    probability: int
    inertia_mid: Decimal
    inertia_upper: Decimal
    inertia_lower: Decimal
    beta: float
    cycle_phase: str
    cycle_duration_bars: int
    cycle_duration_hours: float
    # 🆕 迭代038新增字段
    adx: float = 0.0
    cycle_phases: List[str] = None


class DDPSCalculator:
    """
    DDPS核心计算器 - 纯计算服务

    只接收StandardKLine列表进行计算，不依赖任何外部数据源。
    复用现有计算器（EMA、EWMA、ADX、Inertia、BetaCycle）。

    Attributes:
        ema_period: EMA周期，默认25
        ewma_window: EWMA窗口，默认50
        adx_period: ADX周期，默认14
        inertia_base_period: 惯性基础周期，默认5

    Example:
        >>> calculator = DDPSCalculator()
        >>> klines = [StandardKLine(...), ...]
        >>> result = calculator.calculate(klines, interval_hours=4.0)
        >>> print(result.cycle_phase)
        'consolidation'
    """

    def __init__(
        self,
        ema_period: int = 25,
        ewma_window: int = 50,
        adx_period: int = 14,
        inertia_base_period: int = 5
    ):
        """
        初始化计算器

        Args:
            ema_period: EMA周期
            ewma_window: EWMA窗口
            adx_period: ADX周期
            inertia_base_period: 惯性基础周期
        """
        self._ema_calc = EMACalculator(period=ema_period)
        self._ewma_calc = EWMACalculator(window_n=ewma_window)
        self._cycle_calc = BetaCycleCalculator()
        self._inertia_calc = InertiaCalculator(base_period=inertia_base_period)
        self._adx_calc = ADXCalculator(period=adx_period)

        logger.debug(
            f"DDPSCalculator初始化: ema_period={ema_period}, "
            f"ewma_window={ewma_window}, adx_period={adx_period}"
        )

    def calculate(
        self,
        klines: List[StandardKLine],
        interval_hours: float = 4.0
    ) -> Optional[DDPSResult]:
        """
        计算DDPS所有核心指标

        Args:
            klines: 标准K线列表，必须按时间正序排列
            interval_hours: K线周期小时数（用于周期持续时间计算）

        Returns:
            DDPSResult: 计算结果，数据不足时返回None

        Note:
            - 需要至少180根K线才能进行有效计算
            - interval_hours只用于cycle_duration_hours计算，不影响核心指标
        """
        # 数据充足性检查
        if len(klines) < 180:
            logger.warning(f"K线数据不足: {len(klines)}/180")
            return None

        # 提取价格序列
        prices = np.array([k.close for k in klines])
        high = np.array([k.high for k in klines])
        low = np.array([k.low for k in klines])
        timestamps_ms = np.array([k.timestamp for k in klines])

        # 计算EMA
        ema_array = self._ema_calc.calculate_ema_series(prices)

        # 计算偏离率和EWMA标准差
        deviation = self._ema_calc.calculate_deviation_series(prices)
        ewma_mean, ewma_std_series = self._ewma_calc.calculate_ewma_stats(deviation)

        # 计算P5和P95
        z_p5 = -1.645
        z_p95 = +1.645
        p5_array = ema_array * (1 + z_p5 * ewma_std_series)
        p95_array = ema_array * (1 + z_p95 * ewma_std_series)

        # 计算ADX
        adx_result = self._adx_calc.calculate(high, low, prices)
        adx_series = adx_result['adx']

        # 计算惯性扇面
        fan_result = self._inertia_calc.calculate_historical_fan_series(
            timestamps=timestamps_ms,
            ema_series=ema_array,
            sigma_series=ewma_std_series,
            adx_series=adx_series
        )
        beta_array = fan_result['beta']
        inertia_mid_array = fan_result['mid']
        inertia_upper_array = fan_result['upper']
        inertia_lower_array = fan_result['lower']

        # 计算β宏观周期
        beta_list = [
            b if not np.isnan(b) else None
            for b in beta_array
        ]
        cycle_phases, current_cycle_info = self._cycle_calc.calculate(
            beta_list=beta_list,
            timestamps=timestamps_ms.tolist(),
            prices=prices.tolist(),
            interval_hours=interval_hours
        )

        # 获取最新值
        current_price = Decimal(str(prices[-1]))
        current_ema25 = Decimal(str(ema_array[-1]))
        current_p5 = Decimal(str(p5_array[-1]))
        current_p95 = Decimal(str(p95_array[-1]))
        current_inertia_mid = Decimal(str(inertia_mid_array[-1]))
        current_inertia_upper = Decimal(str(inertia_upper_array[-1]))
        current_inertia_lower = Decimal(str(inertia_lower_array[-1]))
        current_beta = beta_array[-1] if not np.isnan(beta_array[-1]) else 0.0
        current_cycle_phase = cycle_phases[-1] if cycle_phases else 'consolidation'
        current_ewma_std = ewma_std_series[-1] if len(ewma_std_series) > 0 else 0

        # 计算周期持续信息
        cycle_duration_bars = current_cycle_info.get('duration_bars', 0)
        cycle_duration_hours = cycle_duration_bars * interval_hours

        # 计算概率位置
        probability = self._calculate_probability(
            current_price, current_ema25, Decimal(str(current_ewma_std))
        )

        # 🆕 迭代038: 获取当前ADX值
        current_adx = adx_series[-1] if len(adx_series) > 0 and not np.isnan(adx_series[-1]) else 0.0

        # 🆕 迭代038: 获取最近42根K线的cycle_phases（用于周期占比计算）
        recent_cycle_phases = cycle_phases[-42:] if len(cycle_phases) >= 42 else cycle_phases

        return DDPSResult(
            current_price=current_price,
            ema25=current_ema25,
            p5=current_p5,
            p95=current_p95,
            ewma_std=current_ewma_std,
            probability=probability,
            inertia_mid=current_inertia_mid,
            inertia_upper=current_inertia_upper,
            inertia_lower=current_inertia_lower,
            beta=current_beta,
            cycle_phase=current_cycle_phase,
            cycle_duration_bars=cycle_duration_bars,
            cycle_duration_hours=cycle_duration_hours,
            # 🆕 迭代038新增
            adx=current_adx,
            cycle_phases=recent_cycle_phases,
        )

    def _calculate_probability(
        self,
        price: Decimal,
        ema: Decimal,
        ewma_std: Decimal
    ) -> int:
        """
        计算当前价格的概率位置（0-100）

        基于Z-Score和正态分布CDF计算。

        Args:
            price: 当前价格
            ema: EMA均线值
            ewma_std: EWMA标准差

        Returns:
            int: 概率位置（0-100）
        """
        if ema == 0 or ewma_std == 0:
            return 50

        # 计算偏离率
        deviation = (float(price) - float(ema)) / float(ema)

        # 计算Z-Score
        z_score = deviation / float(ewma_std)

        # 使用正态分布CDF转换为概率
        probability = norm.cdf(z_score) * 100

        return int(min(100, max(0, probability)))

    def calculate_with_interval(
        self,
        klines: List[StandardKLine],
        interval: str
    ) -> Optional[DDPSResult]:
        """
        使用interval字符串计算DDPS指标（便捷方法）

        Args:
            klines: 标准K线列表
            interval: K线周期字符串，如 '4h', '1d'

        Returns:
            DDPSResult: 计算结果
        """
        interval_hours = Interval.to_hours(interval)
        return self.calculate(klines, interval_hours)
