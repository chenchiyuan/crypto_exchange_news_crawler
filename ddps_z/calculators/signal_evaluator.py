"""
信号评估器

负责结合Z-Score和RVOL评估交易信号强度。

Related:
    - PRD: docs/iterations/009-ddps-z-probability-engine/prd.md (Section 3.4)
    - TASK: TASK-009-006
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
