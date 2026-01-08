"""
指标状态管理器 (Indicator State Manager)

Purpose:
    为Strategy 7提供无状态的指标计算，确保回测中无未来函数。

关联任务: TASK-021-005
关联功能点: FP-021-005
关联迭代: 021 - 动态周期自适应策略

Classes:
    - IndicatorStateManager: 无状态指标计算器
"""

import logging
from typing import Any, Dict, List

import numpy as np

from ddps_z.calculators.ema_calculator import EMACalculator
from ddps_z.calculators.ewma_calculator import EWMACalculator
from ddps_z.calculators.inertia_calculator import InertiaCalculator
from ddps_z.calculators.beta_cycle_calculator import BetaCycleCalculator

logger = logging.getLogger(__name__)


class IndicatorStateManager:
    """
    指标状态管理器 - 无状态设计

    职责：
    - 基于历史K线缓冲区计算所有必要指标
    - 返回当前K线的指标值
    - 确保计算仅使用历史+当前数据（无未来函数）

    设计原则：
    - 无状态：每次调用calculate_indicators()都是独立计算
    - 无缓存：不保存历史计算结果
    - 纯函数：相同输入产生相同输出

    🔧 TASK-021-005: 核心实现
    🔧 关联功能点: FP-021-005
    🔧 关联迭代: 021 - 动态周期自适应策略

    Attributes:
        ema_calculator: EMA25计算器
        ewma_calculator: EWMA统计量计算器
        inertia_calculator: 惯性计算器
        beta_cycle_calculator: β周期计算器
    """

    # 常量定义
    EMA_PERIOD = 25
    EWMA_WINDOW = 500
    Z_PERCENTILE = 1.645  # 95% 分位数对应的 Z 值

    def __init__(self):
        """
        初始化各Calculator实例

        Note:
            所有Calculator都是无状态的，仅用于计算逻辑复用。
        """
        self.ema_calculator = EMACalculator(period=self.EMA_PERIOD)
        self.ewma_calculator = EWMACalculator(window_n=self.EWMA_WINDOW)
        self.inertia_calculator = InertiaCalculator()
        self.beta_cycle_calculator = BetaCycleCalculator()

    def calculate_indicators(
        self,
        historical_klines: List[Dict]
    ) -> Dict[str, Any]:
        """
        计算当前K线的所有指标

        基于历史K线缓冲区计算当前时刻的指标值，确保无未来函数。

        计算流程：
        1. 提取价格序列
        2. 计算EMA25序列
        3. 计算偏离率序列
        4. 计算EWMA统计量(sigma)
        5. 计算P5/P95静态阈值
        6. 计算beta序列（EMA斜率）
        7. 计算inertia_mid（惯性中值）
        8. 计算cycle_phase（周期状态）

        Args:
            historical_klines: 从回测开始到当前K线的完整历史
                格式: [k0, k1, ..., ki]
                每个kline必须包含: 'open_time', 'high', 'low', 'close'

        Returns:
            当前K线的指标字典:
            {
                'ema25': float,           # EMA25值
                'p5': float,              # P5静态阈值
                'p95': float,             # P95静态阈值
                'beta': float,            # EMA斜率
                'inertia_mid': float,     # 惯性中值
                'cycle_phase': str        # 周期状态
            }

        Raises:
            ValueError: 当数据不足或格式错误时抛出

        重要：
            所有计算都基于historical_klines，不访问未来数据。
            这是Strategy 7无未来函数的核心保证。
        """
        # Guard Clause: 检查输入数据
        if not historical_klines:
            raise ValueError("historical_klines为空")

        # Guard Clause: 检查数据长度
        if len(historical_klines) < self.EMA_PERIOD:
            raise ValueError(
                f"数据不足: 需要至少{self.EMA_PERIOD}根K线，"
                f"实际只有{len(historical_klines)}根"
            )

        # === 1. 提取价格序列 ===
        prices = np.array([float(k['close']) for k in historical_klines])

        # === 2. 计算EMA25序列 ===
        ema_series = self.ema_calculator.calculate_ema_series(prices)
        current_ema = ema_series[-1]

        # === 3. 计算偏离率序列 ===
        deviation_series = self.ema_calculator.calculate_deviation_series(prices)

        # === 4. 计算EWMA统计量(sigma) ===
        ewma_result = self.ewma_calculator.calculate(deviation_series)
        ewma_std_series = ewma_result['ewma_std']
        current_sigma = ewma_std_series[-1]

        # === 5. 计算P5/P95静态阈值 ===
        # 公式: P95 = EMA × (1 + 1.645 × σ), P5 = EMA × (1 - 1.645 × σ)
        if np.isnan(current_ema) or np.isnan(current_sigma):
            current_p5 = np.nan
            current_p95 = np.nan
        else:
            current_p95 = current_ema * (1 + self.Z_PERCENTILE * current_sigma)
            current_p5 = current_ema * (1 - self.Z_PERCENTILE * current_sigma)

        # === 6. 计算beta序列（EMA斜率） ===
        # 公式: beta[t] = EMA[t] - EMA[t-1]
        beta_series = np.full(len(ema_series), np.nan)
        for i in range(1, len(ema_series)):
            if not np.isnan(ema_series[i]) and not np.isnan(ema_series[i-1]):
                beta_series[i] = ema_series[i] - ema_series[i-1]
        current_beta = beta_series[-1]

        # === 7. 计算inertia_mid（惯性中值） ===
        # 使用InertiaCalculator的calculate_fan方法
        if np.isnan(current_ema) or np.isnan(current_beta) or np.isnan(current_sigma):
            current_inertia_mid = np.nan
        else:
            # 使用默认T=5计算扇面
            t_adj = self.inertia_calculator.DEFAULT_T
            fan = self.inertia_calculator.calculate_fan(
                current_ema=current_ema,
                beta=current_beta,
                sigma=current_sigma,
                t_adj=t_adj
            )
            current_inertia_mid = fan['mid']

        # === 8. 计算cycle_phase（周期状态） ===
        # 提取时间戳
        timestamps = []
        for k in historical_klines:
            ts = k['open_time']
            if hasattr(ts, 'timestamp'):
                timestamps.append(int(ts.timestamp() * 1000))
            else:
                timestamps.append(int(ts))

        # 使用BetaCycleCalculator计算周期状态
        try:
            cycle_phases, _ = self.beta_cycle_calculator.calculate(
                beta_list=beta_series.tolist(),
                timestamps=timestamps,
                prices=prices.tolist(),
                interval_hours=4.0  # 4h K线
            )
            current_cycle_phase = cycle_phases[-1]
        except Exception as e:
            logger.warning(f"周期状态计算失败: {e}")
            current_cycle_phase = 'unknown'

        # === 返回当前指标 ===
        return {
            'ema25': current_ema,
            'p5': current_p5,
            'p95': current_p95,
            'beta': current_beta,
            'inertia_mid': current_inertia_mid,
            'cycle_phase': current_cycle_phase
        }
