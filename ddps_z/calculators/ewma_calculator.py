"""
EWMA计算器

负责计算指数加权移动平均(EWMA)的均值μ和方差σ²。
用于后续Z-Score标准化计算。

Related:
    - PRD: docs/iterations/009-ddps-z-probability-engine/prd.md (Section 3.2)
    - TASK: TASK-009-004
"""

from typing import Optional, Tuple

import numpy as np
from django.conf import settings


class EWMACalculator:
    """EWMA计算器 - 计算EWMA均值和方差"""

    def __init__(self, window_n: Optional[int] = None):
        """
        初始化EWMA计算器

        Args:
            window_n: EWMA窗口参数N，用于计算α = 2/(N+1)
                     默认从settings.DDPS_CONFIG获取
        """
        self.window_n = window_n or settings.DDPS_CONFIG['EWMA_WINDOW_N']
        self.alpha = 2.0 / (self.window_n + 1)

    def calculate_ewma_stats(
        self,
        deviation_series: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        计算EWMA均值和标准差序列

        公式:
            μ_t = α × D_t + (1-α) × μ_{t-1}
            σ²_t = α × (D_t - μ_t)² + (1-α) × σ²_{t-1}
            σ_t = √σ²_t

        Args:
            deviation_series: 偏离率序列D_t (可能包含NaN)

        Returns:
            (ewma_mean, ewma_std): EWMA均值序列和标准差序列
        """
        n = len(deviation_series)
        ewma_mean = np.full(n, np.nan)
        ewma_var = np.full(n, np.nan)

        # 找到第一个有效值的索引
        valid_mask = ~np.isnan(deviation_series)
        if not np.any(valid_mask):
            return ewma_mean, np.sqrt(ewma_var)

        first_valid_idx = np.argmax(valid_mask)

        # 初始化：使用第一个有效值
        ewma_mean[first_valid_idx] = deviation_series[first_valid_idx]
        ewma_var[first_valid_idx] = 0.0  # 初始方差为0

        # 递推计算EWMA
        alpha = self.alpha
        for i in range(first_valid_idx + 1, n):
            if np.isnan(deviation_series[i]):
                # 保持前一个值
                ewma_mean[i] = ewma_mean[i - 1]
                ewma_var[i] = ewma_var[i - 1]
            else:
                d_t = deviation_series[i]
                mu_prev = ewma_mean[i - 1]
                var_prev = ewma_var[i - 1]

                # EWMA均值更新
                ewma_mean[i] = alpha * d_t + (1 - alpha) * mu_prev

                # EWMA方差更新
                # 注意：使用更新后的均值计算方差
                ewma_var[i] = alpha * (d_t - ewma_mean[i]) ** 2 + (1 - alpha) * var_prev

        # 返回标准差
        ewma_std = np.sqrt(ewma_var)

        return ewma_mean, ewma_std

    def calculate(
        self,
        deviation_series: np.ndarray
    ) -> dict:
        """
        计算EWMA统计量

        Args:
            deviation_series: 偏离率序列D_t

        Returns:
            {
                'ewma_mean': np.ndarray,  # EWMA均值序列
                'ewma_std': np.ndarray,   # EWMA标准差序列
                'current_mean': float,    # 当前EWMA均值
                'current_std': float,     # 当前EWMA标准差
                'alpha': float,           # 衰减因子
            }
        """
        ewma_mean, ewma_std = self.calculate_ewma_stats(deviation_series)

        # 获取当前值
        current_mean = ewma_mean[-1] if not np.isnan(ewma_mean[-1]) else None
        current_std = ewma_std[-1] if not np.isnan(ewma_std[-1]) else None

        return {
            'ewma_mean': ewma_mean,
            'ewma_std': ewma_std,
            'current_mean': current_mean,
            'current_std': current_std,
            'alpha': self.alpha,
        }
