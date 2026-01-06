"""
惯性计算器 (Inertia Calculator)

负责计算趋势斜率 β、动态惯性周期 T_adj 和扇面边界。

Related:
    - PRD: docs/iterations/010-ddps-z-inertia-fan/prd.md
    - Architecture: docs/iterations/010-ddps-z-inertia-fan/architecture.md
    - TASK: TASK-010-002, TASK-010-003, TASK-010-004
"""

import logging
import math
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class InertiaCalculator:
    """
    惯性计算器 - 计算趋势斜率、动态周期和扇面边界

    核心公式:
        β = EMA[t] - EMA[t-1]
        T_adj = T × (1 + ADX/100), 范围 [5, 10]
        预测中轴: Ê(t+T) = EMA_t + (β × T)
        上边界: Upper = Ê(t+T) + (1.645 × σ × √T)
        下边界: Lower = Ê(t+T) - (1.645 × σ × √T)
    """

    # 默认配置
    DEFAULT_T = 5           # 默认惯性周期
    T_MIN = 5               # 最小惯性周期
    T_MAX = 10              # 最大惯性周期
    Z_PERCENTILE = 1.645    # 95% 分位数对应的 Z 值

    def __init__(self, base_period: int = 5):
        """
        初始化惯性计算器

        Args:
            base_period: 基础惯性周期 T，默认 5
        """
        self.base_period = base_period

    def calculate_beta(
        self,
        ema_series: np.ndarray
    ) -> np.ndarray:
        """
        计算趋势斜率 β 序列

        公式: β[t] = EMA[t] - EMA[t-1]

        Args:
            ema_series: EMA 序列

        Returns:
            β 序列，第一个值为 NaN
        """
        n = len(ema_series)
        beta = np.full(n, np.nan)

        for i in range(1, n):
            if not np.isnan(ema_series[i]) and not np.isnan(ema_series[i - 1]):
                beta[i] = ema_series[i] - ema_series[i - 1]

        return beta

    def calculate_t_adj(
        self,
        adx: Optional[float]
    ) -> float:
        """
        计算动态惯性周期 T_adj

        公式: T_adj = T × (1 + ADX/100)
        范围: [T_MIN, T_MAX] = [5, 10]

        Args:
            adx: 当前 ADX 值，None 时返回默认值

        Returns:
            动态惯性周期
        """
        if adx is None:
            return float(self.DEFAULT_T)

        # 公式计算
        t_adj = self.base_period * (1 + adx / 100)

        # 限制范围
        t_adj = max(self.T_MIN, min(self.T_MAX, t_adj))

        return t_adj

    def calculate_fan(
        self,
        current_ema: float,
        beta: float,
        sigma: float,
        t_adj: float
    ) -> Dict[str, float]:
        """
        计算扇面边界（基于静态阈值 + 惯性投影）

        🆕 新设计理念（基于用户需求）：
        - 当 β ≈ 0 时：扇面退化为静态阈值（upper=P95, mid=EMA, lower=P5）
        - 当 β > 0 时：在 P95 基础上叠加上涨惯性
        - 当 β < 0 时：在 P5 基础上叠加下跌惯性

        公式:
            P95 = EMA × (1 + 1.645 × σ)
            P5 = EMA × (1 - 1.645 × σ)

            若 β ≈ 0:
                mid = EMA, upper = P95, lower = P5
            若 β > 0 (上涨):
                mid = P95 + (β × T_adj)
                spread = 1.645 × σ × mid × √T_adj
                upper = mid + spread, lower = mid - spread
            若 β < 0 (下跌):
                mid = P5 + (β × T_adj)  # β<0，mid会低于P5
                spread = 1.645 × σ × |mid| × √T_adj
                upper = mid + spread, lower = mid - spread

        注意: σ 是偏离率的标准差（相对值），需要乘以价格转换为绝对价格

        Args:
            current_ema: 当前 EMA 值
            beta: 当前趋势斜率（β = EMA[t] - EMA[t-1]）
            sigma: 当前 EWMA 标准差（偏离率的标准差）
            t_adj: 动态惯性周期

        Returns:
            {
                'mid': float,      # 预测中轴
                'upper': float,    # 上边界
                'lower': float,    # 下边界
                't_adj': float,    # 动态周期
            }
        """
        # 计算静态阈值
        p95 = current_ema * (1 + self.Z_PERCENTILE * sigma)
        p5 = current_ema * (1 - self.Z_PERCENTILE * sigma)

        # β阈值：小于此值视为无明显趋势
        # 对于4h K线，价格可能在几万，β小于1可以视为基本平坦
        beta_threshold = current_ema * 0.0001  # 相对阈值：0.01%

        if abs(beta) < beta_threshold:
            # β ≈ 0，无明显趋势，扇面退化为静态阈值
            mid = current_ema
            upper = p95
            lower = p5
        elif beta > 0:
            # 上涨趋势：在 P95 基础上叠加惯性
            mid = p95 + (beta * t_adj)
            # spread 基于 mid 计算（因为价格水平已经上移）
            spread = self.Z_PERCENTILE * sigma * mid * math.sqrt(t_adj)
            upper = mid + spread
            lower = mid - spread
        else:  # beta < 0
            # 下跌趋势：在 P5 基础上叠加惯性（β<0会使mid低于P5）
            mid = p5 + (beta * t_adj)
            # spread 基于 |mid| 计算
            spread = self.Z_PERCENTILE * sigma * abs(mid) * math.sqrt(t_adj)
            upper = mid + spread
            lower = mid - spread

        return {
            'mid': mid,
            'upper': upper,
            'lower': lower,
            't_adj': t_adj,
        }

    def generate_fan_points(
        self,
        current_ema: float,
        beta: float,
        sigma: float,
        t_adj: float,
        current_time: float,
        interval_seconds: int
    ) -> List[Dict[str, Any]]:
        """
        生成扇面点序列（向未来延伸）

        每个周期生成一个点，共 int(t_adj) 个点。
        扇面随时间扩散：σ 随 √t 增长。

        Args:
            current_ema: 当前 EMA 值
            beta: 当前趋势斜率
            sigma: 当前 EWMA 标准差
            t_adj: 动态惯性周期
            current_time: 当前时间戳（秒）
            interval_seconds: K 线周期（秒）

        Returns:
            [
                {
                    't': int,        # 未来时间戳（毫秒）
                    'mid': float,    # 预测中轴
                    'upper': float,  # 上边界
                    'lower': float,  # 下边界
                },
                ... (共 int(t_adj) 个点)
            ]
        """
        points = []
        num_points = int(t_adj)

        for i in range(1, num_points + 1):
            # 未来第 i 个周期的时间戳
            future_time = current_time + (i * interval_seconds)
            future_time_ms = int(future_time * 1000)

            # 预测中轴：线性延伸
            mid = current_ema + (beta * i)

            # 扩散宽度：随 √t 增长
            spread = self.Z_PERCENTILE * sigma * current_ema * math.sqrt(i)

            # 上下边界
            upper = mid + spread
            lower = mid - spread

            points.append({
                't': future_time_ms,
                'mid': mid,
                'upper': upper,
                'lower': lower,
            })

        return points

    def calculate_full(
        self,
        current_ema: float,
        ema_series: np.ndarray,
        sigma: float,
        adx: Optional[float],
        current_time: float,
        interval_seconds: int
    ) -> Dict[str, Any]:
        """
        完整惯性计算（便捷方法）

        Args:
            current_ema: 当前 EMA 值
            ema_series: EMA 序列（用于计算 β）
            sigma: 当前 EWMA 标准差
            adx: 当前 ADX 值
            current_time: 当前时间戳（秒）
            interval_seconds: K 线周期（秒）

        Returns:
            {
                'beta': float,
                't_adj': float,
                'fan': {
                    'mid': float,
                    'upper': float,
                    'lower': float,
                },
                'fan_points': [...],
            } | None (如果数据不足)
        """
        # 计算 β
        beta_series = self.calculate_beta(ema_series)
        current_beta = beta_series[-1] if len(beta_series) > 0 and not np.isnan(beta_series[-1]) else None

        if current_beta is None:
            logger.warning("无法计算 β：EMA 数据不足")
            return None

        # 计算 T_adj
        t_adj = self.calculate_t_adj(adx)

        # 计算扇面边界
        fan = self.calculate_fan(current_ema, current_beta, sigma, t_adj)

        # 生成扇面点序列
        fan_points = self.generate_fan_points(
            current_ema, current_beta, sigma, t_adj,
            current_time, interval_seconds
        )

        return {
            'beta': current_beta,
            't_adj': t_adj,
            'fan': fan,
            'fan_points': fan_points,
        }

    def calculate_historical_fan_series(
        self,
        timestamps: np.ndarray,
        ema_series: np.ndarray,
        sigma_series: np.ndarray,
        adx_series: np.ndarray
    ) -> Dict[str, Any]:
        """
        计算历史扇面序列（每根K线的扇面边界）

        用于生成完整的扇面通道，而非单点预测。

        Args:
            timestamps: 时间戳序列（秒）
            ema_series: EMA 序列
            sigma_series: EWMA 标准差序列（相对偏离率的标准差）
            adx_series: ADX 序列

        Returns:
            {
                'timestamps': [...],      # 时间戳（毫秒）
                'upper': [...],           # 扇面上界序列
                'mid': [...],             # 扇面中轴序列
                'lower': [...],           # 扇面下界序列
                'beta': [...],            # β 序列
                't_adj': [...],           # T_adj 序列
            }
        """
        n = len(timestamps)

        if n != len(ema_series) or n != len(sigma_series) or n != len(adx_series):
            raise ValueError("输入序列长度不一致")

        # 计算 β 序列
        beta_series = self.calculate_beta(ema_series)

        # 初始化输出序列
        upper_series = np.full(n, np.nan)
        mid_series = np.full(n, np.nan)
        lower_series = np.full(n, np.nan)
        t_adj_series = np.full(n, np.nan)

        # 对每根K线计算扇面边界
        for i in range(n):
            # 跳过无效数据
            if (np.isnan(beta_series[i]) or
                np.isnan(ema_series[i]) or
                np.isnan(sigma_series[i]) or
                np.isnan(adx_series[i])):
                continue

            # 计算动态惯性周期
            t_adj = self.calculate_t_adj(adx_series[i])
            t_adj_series[i] = t_adj

            # 🔧 修复：调用 calculate_fan 方法，使用新的扇面计算逻辑
            # （基于静态阈值 + 惯性投影）
            fan = self.calculate_fan(
                current_ema=ema_series[i],
                beta=beta_series[i],
                sigma=sigma_series[i],
                t_adj=t_adj
            )

            upper_series[i] = fan['upper']
            mid_series[i] = fan['mid']
            lower_series[i] = fan['lower']

        return {
            'timestamps': (timestamps * 1000).astype(int).tolist(),  # 转为毫秒
            'upper': upper_series.tolist(),
            'mid': mid_series.tolist(),
            'lower': lower_series.tolist(),
            'beta': beta_series.tolist(),
            't_adj': t_adj_series.tolist(),
        }
