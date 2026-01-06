"""
信号评估器

负责结合Z-Score和RVOL评估交易信号强度。
扩展: 支持惯性双重阈值信号评估。

Related:
    - PRD: docs/iterations/009-ddps-z-probability-engine/prd.md (Section 3.4)
    - PRD: docs/iterations/010-ddps-z-inertia-fan/prd.md
    - TASK: TASK-009-006, TASK-010-005, TASK-010-006, TASK-010-007
"""

from typing import Optional, List
from dataclasses import dataclass
from enum import Enum

import numpy as np
from django.conf import settings


class SignalStrength(Enum):
    """信号强度枚举"""
    STRONG = 'strong'      # 强信号
    WEAK = 'weak'          # 弱信号
    NONE = 'none'          # 无信号


class SignalType(Enum):
    """信号类型枚举"""
    OVERSOLD = 'oversold'      # 超卖信号
    OVERBOUGHT = 'overbought'  # 超买信号
    NEUTRAL = 'neutral'        # 中性


@dataclass
class Signal:
    """信号数据类"""
    signal_type: SignalType
    strength: SignalStrength
    zscore: float
    percentile: float
    zone: str
    rvol: Optional[float] = None
    volume_confirmed: bool = False
    description: str = ''


# ============================================================
# 🆕 惯性信号扩展 (TASK-010-005)
# ============================================================

class InertiaState(Enum):
    """惯性状态枚举"""
    PROTECTED = 'protected'          # 惯性保护中：价格在扇面范围内
    DECAYING = 'decaying'            # 惯性衰减：价格接近扇面边界
    SIGNAL_TRIGGERED = 'signal'      # 信号触发：空间+时间准则同时满足


@dataclass
class InertiaSignal:
    """惯性信号数据类"""
    signal_type: SignalType          # 复用现有枚举
    state: InertiaState              # 惯性状态
    space_triggered: bool            # 空间准则触发 (Z-Score突破分位带)
    time_triggered: bool             # 时间准则触发 (价格突破扇面边界)
    adx: float                       # ADX 值
    beta: float                      # 趋势斜率
    t_adj: float                     # 动态惯性周期
    fan_upper: float                 # 扇面上边界
    fan_lower: float                 # 扇面下边界
    description: str = ''            # 信号描述


class SignalEvaluator:
    """信号评估器 - 结合Z-Score和RVOL评估信号"""

    def __init__(
        self,
        rvol_threshold: Optional[float] = None,
        z_oversold: Optional[float] = None,
        z_overbought: Optional[float] = None
    ):
        """
        初始化信号评估器

        Args:
            rvol_threshold: RVOL阈值，默认从配置获取
            z_oversold: 超卖Z值阈值
            z_overbought: 超买Z值阈值
        """
        config = settings.DDPS_CONFIG
        self.rvol_threshold = rvol_threshold or config['RVOL_THRESHOLD']
        self.z_oversold = z_oversold or config['Z_SCORE_OVERSOLD']
        self.z_overbought = z_overbought or config['Z_SCORE_OVERBOUGHT']

    def calculate_rvol(
        self,
        volumes: np.ndarray,
        lookback: Optional[int] = None
    ) -> Optional[float]:
        """
        计算相对成交量RVOL

        RVOL = 当前成交量 / MA(N)成交量

        Args:
            volumes: 成交量序列
            lookback: 回溯周期，默认从配置获取

        Returns:
            RVOL值，数据不足返回None
        """
        lookback = lookback or settings.DDPS_CONFIG['RVOL_LOOKBACK_PERIOD']

        if len(volumes) < lookback + 1:
            return None

        current_volume = volumes[-1]
        ma_volume = np.mean(volumes[-(lookback + 1):-1])

        if ma_volume == 0:
            return None

        return current_volume / ma_volume

    def evaluate(
        self,
        zscore: float,
        percentile: float,
        zone: str,
        rvol: Optional[float] = None
    ) -> Signal:
        """
        评估信号

        信号判定规则:
        - 强超卖: Z ≤ -1.64 且 RVOL ≥ 2
        - 强超买: Z ≥ 1.64 且 RVOL ≥ 2
        - 弱超卖: Z ≤ -1.28 或 (Z ≤ -1.64 且 RVOL < 2)
        - 弱超买: Z ≥ 1.28 或 (Z ≥ 1.64 且 RVOL < 2)

        Args:
            zscore: Z-Score值
            percentile: 百分位数
            zone: 分位区间
            rvol: 相对成交量，可选

        Returns:
            Signal对象
        """
        # 判断RVOL是否达标
        volume_confirmed = rvol is not None and rvol >= self.rvol_threshold

        # 判断信号类型和强度
        if zscore <= self.z_oversold:
            # 超卖区域
            if volume_confirmed:
                signal = Signal(
                    signal_type=SignalType.OVERSOLD,
                    strength=SignalStrength.STRONG,
                    zscore=zscore,
                    percentile=percentile,
                    zone=zone,
                    rvol=rvol,
                    volume_confirmed=True,
                    description=f'强超卖信号: Z={zscore:.2f} ({percentile:.1f}%), RVOL={rvol:.1f}x'
                )
            else:
                signal = Signal(
                    signal_type=SignalType.OVERSOLD,
                    strength=SignalStrength.WEAK,
                    zscore=zscore,
                    percentile=percentile,
                    zone=zone,
                    rvol=rvol,
                    volume_confirmed=False,
                    description=f'弱超卖信号: Z={zscore:.2f} ({percentile:.1f}%), 成交量未放大'
                )

        elif zscore >= self.z_overbought:
            # 超买区域
            if volume_confirmed:
                signal = Signal(
                    signal_type=SignalType.OVERBOUGHT,
                    strength=SignalStrength.STRONG,
                    zscore=zscore,
                    percentile=percentile,
                    zone=zone,
                    rvol=rvol,
                    volume_confirmed=True,
                    description=f'强超买信号: Z={zscore:.2f} ({percentile:.1f}%), RVOL={rvol:.1f}x'
                )
            else:
                signal = Signal(
                    signal_type=SignalType.OVERBOUGHT,
                    strength=SignalStrength.WEAK,
                    zscore=zscore,
                    percentile=percentile,
                    zone=zone,
                    rvol=rvol,
                    volume_confirmed=False,
                    description=f'弱超买信号: Z={zscore:.2f} ({percentile:.1f}%), 成交量未放大'
                )

        elif zscore <= -1.28:
            # 10%分位附近，弱超卖
            signal = Signal(
                signal_type=SignalType.OVERSOLD,
                strength=SignalStrength.WEAK,
                zscore=zscore,
                percentile=percentile,
                zone=zone,
                rvol=rvol,
                volume_confirmed=volume_confirmed,
                description=f'弱超卖信号: Z={zscore:.2f} ({percentile:.1f}%)'
            )

        elif zscore >= 1.28:
            # 90%分位附近，弱超买
            signal = Signal(
                signal_type=SignalType.OVERBOUGHT,
                strength=SignalStrength.WEAK,
                zscore=zscore,
                percentile=percentile,
                zone=zone,
                rvol=rvol,
                volume_confirmed=volume_confirmed,
                description=f'弱超买信号: Z={zscore:.2f} ({percentile:.1f}%)'
            )

        else:
            # 中性区域
            signal = Signal(
                signal_type=SignalType.NEUTRAL,
                strength=SignalStrength.NONE,
                zscore=zscore,
                percentile=percentile,
                zone=zone,
                rvol=rvol,
                volume_confirmed=volume_confirmed,
                description=f'中性: Z={zscore:.2f} ({percentile:.1f}%)'
            )

        return signal

    def to_dict(self, signal: Signal) -> dict:
        """将Signal转换为字典"""
        return {
            'signal_type': signal.signal_type.value,
            'strength': signal.strength.value,
            'zscore': signal.zscore,
            'percentile': signal.percentile,
            'zone': signal.zone,
            'rvol': signal.rvol,
            'volume_confirmed': signal.volume_confirmed,
            'description': signal.description,
        }

    # ============================================================
    # 🆕 惯性信号评估扩展 (TASK-010-006, TASK-010-007)
    # ============================================================

    # 惯性衰减阈值: 价格距扇面边界 < 0.5% 时判定为衰减
    DECAY_THRESHOLD = 0.005

    def _determine_inertia_state(
        self,
        current_price: float,
        fan_upper: float,
        fan_lower: float,
        space_triggered: bool,
        time_triggered: bool
    ) -> InertiaState:
        """
        判定惯性状态

        规则:
        - 信号触发 (SIGNAL_TRIGGERED): 空间+时间准则同时满足
        - 惯性衰减 (DECAYING): 价格距扇面边界 < 0.5%
        - 惯性保护中 (PROTECTED): 其他情况

        Args:
            current_price: 当前价格
            fan_upper: 扇面上边界
            fan_lower: 扇面下边界
            space_triggered: 空间准则是否触发
            time_triggered: 时间准则是否触发

        Returns:
            InertiaState 枚举值
        """
        # 双重阈值同时满足 -> 信号触发
        if space_triggered and time_triggered:
            return InertiaState.SIGNAL_TRIGGERED

        # 判断是否接近边界
        if fan_upper > 0:
            upper_distance = abs(current_price - fan_upper) / fan_upper
        else:
            upper_distance = float('inf')

        if fan_lower > 0:
            lower_distance = abs(current_price - fan_lower) / fan_lower
        else:
            lower_distance = float('inf')

        min_distance = min(upper_distance, lower_distance)

        if min_distance < self.DECAY_THRESHOLD:
            return InertiaState.DECAYING

        return InertiaState.PROTECTED

    def evaluate_inertia_signal(
        self,
        current_price: float,
        zscore: float,
        percentile: float,
        fan_upper: float,
        fan_lower: float,
        adx: float,
        beta: float,
        t_adj: float
    ) -> InertiaSignal:
        """
        评估惯性双重阈值信号

        卖出信号 (空间+时间):
            - 空间准则: Z-Score ≥ 1.645 (95%分位)
            - 时间准则: current_price > fan_upper

        买入信号 (空间+时间):
            - 空间准则: Z-Score ≤ -1.645 (5%分位)
            - 时间准则: current_price < fan_lower

        Args:
            current_price: 当前价格
            zscore: 当前 Z-Score 值
            percentile: 当前百分位数
            fan_upper: 扇面上边界
            fan_lower: 扇面下边界
            adx: 当前 ADX 值
            beta: 当前趋势斜率
            t_adj: 动态惯性周期

        Returns:
            InertiaSignal 对象
        """
        Z_THRESHOLD = 1.645  # 95% 分位数

        # 空间准则判定
        space_overbought = zscore >= Z_THRESHOLD
        space_oversold = zscore <= -Z_THRESHOLD
        space_triggered = space_overbought or space_oversold

        # 时间准则判定
        time_overbought = current_price > fan_upper
        time_oversold = current_price < fan_lower
        time_triggered = time_overbought or time_oversold

        # 判定信号类型
        if space_overbought and time_overbought:
            signal_type = SignalType.OVERBOUGHT
        elif space_oversold and time_oversold:
            signal_type = SignalType.OVERSOLD
        else:
            signal_type = SignalType.NEUTRAL

        # 判定惯性状态
        state = self._determine_inertia_state(
            current_price, fan_upper, fan_lower,
            space_triggered, time_triggered
        )

        # 生成描述
        description = self._generate_inertia_description(
            signal_type, state, zscore, percentile,
            current_price, fan_upper, fan_lower,
            space_triggered, time_triggered
        )

        return InertiaSignal(
            signal_type=signal_type,
            state=state,
            space_triggered=space_triggered,
            time_triggered=time_triggered,
            adx=adx,
            beta=beta,
            t_adj=t_adj,
            fan_upper=fan_upper,
            fan_lower=fan_lower,
            description=description
        )

    def _generate_inertia_description(
        self,
        signal_type: SignalType,
        state: InertiaState,
        zscore: float,
        percentile: float,
        current_price: float,
        fan_upper: float,
        fan_lower: float,
        space_triggered: bool,
        time_triggered: bool
    ) -> str:
        """生成惯性信号描述"""

        if state == InertiaState.SIGNAL_TRIGGERED:
            if signal_type == SignalType.OVERBOUGHT:
                return (
                    f'双重阈值卖出信号: '
                    f'Z={zscore:.2f} (>{1.645:.2f}), '
                    f'价格={current_price:.4f} (>上边界{fan_upper:.4f})'
                )
            elif signal_type == SignalType.OVERSOLD:
                return (
                    f'双重阈值买入信号: '
                    f'Z={zscore:.2f} (<{-1.645:.2f}), '
                    f'价格={current_price:.4f} (<下边界{fan_lower:.4f})'
                )

        if state == InertiaState.DECAYING:
            return (
                f'惯性衰减: '
                f'Z={zscore:.2f}, 价格接近扇面边界'
            )

        # PROTECTED
        return (
            f'惯性保护中: '
            f'Z={zscore:.2f} ({percentile:.1f}%), '
            f'价格在扇面范围内'
        )

    def inertia_signal_to_dict(self, signal: InertiaSignal) -> dict:
        """将 InertiaSignal 转换为字典"""
        return {
            'signal_type': signal.signal_type.value,
            'state': signal.state.value,
            'space_triggered': signal.space_triggered,
            'time_triggered': signal.time_triggered,
            'adx': signal.adx,
            'beta': signal.beta,
            't_adj': signal.t_adj,
            'fan_upper': signal.fan_upper,
            'fan_lower': signal.fan_lower,
            'description': signal.description,
        }
