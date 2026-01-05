"""
Z-Score计算器

负责计算标准化Z值，并映射到概率分位区间。

Related:
    - PRD: docs/iterations/009-ddps-z-probability-engine/prd.md (Section 3.3)
    - TASK: TASK-009-005
"""

from typing import Optional
import math

import numpy as np
from django.conf import settings


class ZScoreCalculator:
    """Z-Score计算器 - 计算标准化Z值和分位区间"""

    # Z-Score到分位的映射（基于正态分布）
    QUANTILE_THRESHOLDS = {
        'oversold_5': -1.64,      # 5%分位
        'oversold_10': -1.28,     # 10%分位
        'neutral': 0,              # 50%分位
        'overbought_90': 1.28,    # 90%分位
        'overbought_95': 1.64,    # 95%分位
    }

    # 区间标签
    ZONE_LABELS = {
        'extreme_oversold': '极度超卖 (0-5%)',
        'oversold': '超卖 (5-10%)',
        'neutral_bearish': '中性偏空 (10-50%)',
        'neutral_bullish': '中性偏多 (50-90%)',
        'overbought': '超买 (90-95%)',
        'extreme_overbought': '极度超买 (95-100%)',
    }

    def __init__(self):
        """初始化Z-Score计算器"""
        self.z_oversold = settings.DDPS_CONFIG['Z_SCORE_OVERSOLD']
        self.z_overbought = settings.DDPS_CONFIG['Z_SCORE_OVERBOUGHT']

    def calculate_zscore_series(
        self,
        deviation_series: np.ndarray,
        ewma_mean: np.ndarray,
        ewma_std: np.ndarray
    ) -> np.ndarray:
        """
        计算Z-Score序列

        公式:
            Z_t = (D_t - μ_t) / σ_t

        Args:
            deviation_series: 偏离率序列D_t
            ewma_mean: EWMA均值序列μ_t
            ewma_std: EWMA标准差序列σ_t

        Returns:
            Z-Score序列
        """
        # 避免除零
        with np.errstate(divide='ignore', invalid='ignore'):
            zscore = (deviation_series - ewma_mean) / ewma_std
            # 处理σ=0的情况（初始阶段）
            zscore = np.where(ewma_std == 0, 0, zscore)
            # 将inf和-inf替换为边界值
            zscore = np.clip(zscore, -10, 10)  # 限制在±10σ范围内

        return zscore

    def zscore_to_percentile(self, zscore: float) -> float:
        """
        将Z-Score转换为百分位数

        使用正态分布CDF近似计算（误差<0.1%）

        Args:
            zscore: Z-Score值

        Returns:
            百分位数 (0-100)
        """
        if np.isnan(zscore):
            return 50.0  # 中性

        # 使用误差函数实现正态分布CDF
        # CDF(x) = 0.5 * (1 + erf(x / sqrt(2)))
        return 0.5 * (1 + math.erf(zscore / math.sqrt(2))) * 100

    def get_zone(self, zscore: float) -> str:
        """
        获取Z-Score所在的分位区间

        Args:
            zscore: Z-Score值

        Returns:
            区间标识符
        """
        if np.isnan(zscore):
            return 'neutral_bullish'

        if zscore <= self.QUANTILE_THRESHOLDS['oversold_5']:
            return 'extreme_oversold'
        elif zscore <= self.QUANTILE_THRESHOLDS['oversold_10']:
            return 'oversold'
        elif zscore <= self.QUANTILE_THRESHOLDS['neutral']:
            return 'neutral_bearish'
        elif zscore <= self.QUANTILE_THRESHOLDS['overbought_90']:
            return 'neutral_bullish'
        elif zscore <= self.QUANTILE_THRESHOLDS['overbought_95']:
            return 'overbought'
        else:
            return 'extreme_overbought'

    def get_zone_label(self, zone: str) -> str:
        """获取区间的可读标签"""
        return self.ZONE_LABELS.get(zone, '未知')

    def calculate_quantile_bands(self) -> dict:
        """
        计算分位带的Z值边界

        Returns:
            {
                'p5': -1.64,   # 5%分位
                'p10': -1.28,  # 10%分位
                'p50': 0,      # 50%分位
                'p90': 1.28,   # 90%分位
                'p95': 1.64,   # 95%分位
            }
        """
        return {
            'p5': self.QUANTILE_THRESHOLDS['oversold_5'],
            'p10': self.QUANTILE_THRESHOLDS['oversold_10'],
            'p50': self.QUANTILE_THRESHOLDS['neutral'],
            'p90': self.QUANTILE_THRESHOLDS['overbought_90'],
            'p95': self.QUANTILE_THRESHOLDS['overbought_95'],
        }

    def calculate(
        self,
        deviation_series: np.ndarray,
        ewma_mean: np.ndarray,
        ewma_std: np.ndarray
    ) -> dict:
        """
        完整的Z-Score计算

        Args:
            deviation_series: 偏离率序列D_t
            ewma_mean: EWMA均值序列μ_t
            ewma_std: EWMA标准差序列σ_t

        Returns:
            {
                'zscore_series': np.ndarray,  # Z-Score序列
                'current_zscore': float,      # 当前Z-Score
                'current_percentile': float,  # 当前百分位
                'current_zone': str,          # 当前区间
                'current_zone_label': str,    # 区间可读标签
                'quantile_bands': dict,       # 分位带边界
            }
        """
        zscore_series = self.calculate_zscore_series(
            deviation_series, ewma_mean, ewma_std
        )

        # 当前值
        current_zscore = zscore_series[-1] if not np.isnan(zscore_series[-1]) else 0.0
        current_percentile = self.zscore_to_percentile(current_zscore)
        current_zone = self.get_zone(current_zscore)

        return {
            'zscore_series': zscore_series,
            'current_zscore': float(current_zscore),
            'current_percentile': float(current_percentile),
            'current_zone': current_zone,
            'current_zone_label': self.get_zone_label(current_zone),
            'quantile_bands': self.calculate_quantile_bands(),
        }
