"""
经验CDF指标计算器

本模块实现滚动经验CDF策略所需的全部指标计算：
- EMA计算（因果，增量，支持多周期）
- 偏离率D计算
- EWMA均值μ和波动率σ计算
- 标准化偏离X计算
- 滚动经验CDF百分位Prob计算

迭代编号: 034 (滚动经验CDF信号策略)
创建日期: 2026-01-12
关联任务: TASK-034-001, TASK-034-002, TASK-034-003
关联需求: FP-034-001~005 (function-points.md)
关联架构: architecture.md#4.3.1 EmpiricalCDFCalculator
"""

import logging
from collections import deque
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional, Tuple, List

logger = logging.getLogger(__name__)


class EmpiricalCDFCalculator:
    """
    经验CDF指标计算器

    职责：
    - EMA计算（因果，增量，支持多周期EMA7/EMA25/EMA99）
    - 偏离率D计算: D = (close - EMA) / EMA
    - EWMA均值μ和波动率σ计算
    - 标准化偏离X计算: X = (D - μ) / σ
    - 滚动经验CDF百分位Prob计算

    状态：
    - _ema_values: 各周期EMA值字典 {period: value}
    - _mu: EWMA均值
    - _var: EWMA方差
    - _x_history: 历史X值队列（长度M）

    因果性保证：
    - Prob_t 的窗口 W_t = {X_{t-1}, X_{t-2}, ..., X_{t-M}}，不含当前样本 X_t
    - 所有计算均为增量更新，不使用未来数据

    Example:
        >>> calc = EmpiricalCDFCalculator(ema_period=25, cdf_window=100)
        >>> for close in closes:
        ...     result = calc.update(close)
        ...     print(f"Prob: {result['prob']}")
    """

    def __init__(
        self,
        ema_period: int = 25,
        ewma_period: int = 50,
        cdf_window: int = 100,
        epsilon: float = 1e-12,
        ema_periods: Optional[List[int]] = None
    ):
        """
        初始化经验CDF指标计算器

        Args:
            ema_period: 主EMA周期（用于偏离率计算），默认25
            ewma_period: EWMA周期（用于μ和σ），默认50
            cdf_window: 经验CDF窗口大小M，默认100
            epsilon: 数值稳定性常量，默认1e-12
            ema_periods: 额外计算的EMA周期列表，默认[7, 25, 99]
        """
        # 参数配置
        self._ema_period = ema_period
        self._ewma_period = ewma_period
        self._cdf_window = cdf_window
        self._epsilon = Decimal(str(epsilon))

        # 默认计算EMA7, EMA25, EMA99
        self._ema_periods = ema_periods if ema_periods else [7, 25, 99]

        # 计算各周期EMA的α值
        self._ema_alphas = {}
        for period in self._ema_periods:
            self._ema_alphas[period] = Decimal(2) / Decimal(period + 1)

        # EWMA的α值
        self._ewma_alpha = Decimal(2) / Decimal(ewma_period + 1)

        # 初始化状态
        self._reset_state()

        logger.debug(
            f"初始化EmpiricalCDFCalculator: "
            f"ema_period={ema_period}, ewma_period={ewma_period}, "
            f"cdf_window={cdf_window}"
        )

    def _reset_state(self) -> None:
        """重置内部状态"""
        # EMA状态（支持多周期）
        self._ema_values: Dict[int, Optional[Decimal]] = {}
        for period in self._ema_periods:
            self._ema_values[period] = None

        # EWMA状态
        self._mu: Optional[Decimal] = None
        self._var: Decimal = Decimal(0)

        # 历史X值队列（用于经验CDF计算）
        # 使用deque实现固定长度队列
        self._x_history: deque = deque(maxlen=self._cdf_window)

        # 计数器
        self._bar_count: int = 0

    def reset(self) -> None:
        """
        重置所有状态（回测开始时调用）

        Example:
            >>> calc.reset()
            >>> # 开始新的回测
        """
        self._reset_state()
        logger.debug("EmpiricalCDFCalculator状态已重置")

    def update(self, close: Decimal) -> Dict:
        """
        更新指标（每根K线调用一次）

        执行链式指标计算：
        close → EMA(多周期) → 偏离率D → EWMA(μ,σ) → 标准化X → 经验CDF Prob

        Args:
            close: 当前K线收盘价

        Returns:
            Dict: {
                'ema': Decimal,           # EMA25值
                'ema7': Decimal,          # EMA7值
                'ema25': Decimal,         # EMA25值
                'ema99': Decimal,         # EMA99值
                'd': Decimal,             # 偏离率
                'mu': Decimal,            # EWMA均值
                'sigma': Decimal,         # EWMA波动率
                'x': Decimal,             # 标准化偏离
                'prob': Optional[float]   # 经验CDF百分位（冷启动期为None）
            }

        Example:
            >>> result = calc.update(Decimal("3500.00"))
            >>> print(f"EMA: {result['ema']}, Prob: {result['prob']}")
        """
        # 确保输入为Decimal
        if not isinstance(close, Decimal):
            close = Decimal(str(close))

        self._bar_count += 1

        # Step 1: 更新多周期EMA
        ema_values = self._update_all_emas(close)

        # 使用主EMA周期计算偏离率
        ema = ema_values.get(self._ema_period, ema_values.get(25))

        # Step 2: 计算偏离率D
        d = self._calculate_deviation(close, ema)

        # Step 3: 更新EWMA均值μ和波动率σ
        mu, sigma = self._update_ewma(d)

        # Step 4: 计算标准化偏离X
        x = self._calculate_standardized_deviation(d, mu, sigma)

        # Step 5: 计算经验CDF百分位Prob
        # 注意：先计算Prob（使用历史窗口），再将X加入历史
        prob = self._calculate_prob(x)

        # Step 6: 将当前X加入历史队列（供下一次计算使用）
        self._x_history.append(x)

        # 构建结果
        result = {
            'ema': ema,
            'd': d,
            'mu': mu,
            'sigma': sigma,
            'x': x,
            'prob': prob,
            'bar_count': self._bar_count,
        }

        # 添加所有EMA值到结果
        for period, value in ema_values.items():
            result[f'ema{period}'] = value

        logger.debug(
            f"Bar {self._bar_count}: EMA={float(ema):.4f}, "
            f"D={float(d):.6f}, X={float(x):.4f}, Prob={prob}"
        )

        return result

    def _update_ema(self, close: Decimal) -> Decimal:
        """
        更新EMA25（因果计算）- 单周期版本（向后兼容）

        公式: EMA_t = α × close + (1 - α) × EMA_{t-1}
        其中: α = 2 / (N + 1)

        第一根K线时，EMA = close

        Args:
            close: 收盘价

        Returns:
            Decimal: 更新后的EMA值
        """
        if self._ema_values.get(self._ema_period) is None:
            # 第一根K线：EMA = close
            self._ema_values[self._ema_period] = close
        else:
            # 增量更新
            alpha = self._ema_alphas.get(self._ema_period, Decimal(2) / Decimal(self._ema_period + 1))
            self._ema_values[self._ema_period] = alpha * close + (1 - alpha) * self._ema_values[self._ema_period]

        return self._ema_values[self._ema_period]

    def _update_all_emas(self, close: Decimal) -> Dict[int, Decimal]:
        """
        更新所有配置的EMA周期（因果计算）

        为每个配置的EMA周期计算增量EMA值。

        Args:
            close: 收盘价

        Returns:
            Dict[int, Decimal]: 各周期EMA值字典 {period: value}
        """
        for period in self._ema_periods:
            if self._ema_values.get(period) is None:
                # 第一根K线：EMA = close
                self._ema_values[period] = close
            else:
                # 增量更新
                alpha = self._ema_alphas[period]
                self._ema_values[period] = alpha * close + (1 - alpha) * self._ema_values[period]

        return self._ema_values

    def _calculate_deviation(self, close: Decimal, ema: Decimal) -> Decimal:
        """
        计算偏离率D

        公式: D_t = (P_t - EMA_t) / EMA_t

        Args:
            close: 收盘价
            ema: EMA值

        Returns:
            Decimal: 偏离率
        """
        if ema == 0:
            return Decimal(0)

        return (close - ema) / ema

    def _update_ewma(self, d: Decimal) -> Tuple[Decimal, Decimal]:
        """
        更新EWMA均值μ和方差σ²

        公式:
        - μ_t = α × D_t + (1 - α) × μ_{t-1}
        - σ²_t = α × (D_t - μ_t)² + (1 - α) × σ²_{t-1}
        - σ_t = sqrt(max(σ²_t, ε))

        Args:
            d: 偏离率

        Returns:
            Tuple[Decimal, Decimal]: (μ, σ)
        """
        alpha = self._ewma_alpha

        if self._mu is None:
            # 第一根K线
            self._mu = d
            self._var = Decimal(0)
        else:
            # 增量更新均值
            self._mu = alpha * d + (1 - alpha) * self._mu

            # 增量更新方差
            diff_sq = (d - self._mu) ** 2
            self._var = alpha * diff_sq + (1 - alpha) * self._var

        # 数值稳定：确保方差至少为epsilon
        var_stable = max(self._var, self._epsilon)

        # 计算标准差
        sigma = var_stable.sqrt()

        return self._mu, sigma

    def _calculate_standardized_deviation(
        self,
        d: Decimal,
        mu: Decimal,
        sigma: Decimal
    ) -> Decimal:
        """
        计算标准化偏离X

        公式: X_t = (D_t - μ_t) / σ_t

        Args:
            d: 偏离率
            mu: EWMA均值
            sigma: EWMA波动率

        Returns:
            Decimal: 标准化偏离
        """
        if sigma == 0 or sigma < self._epsilon:
            return Decimal(0)

        return (d - mu) / sigma

    def _calculate_prob(self, x: Decimal) -> Optional[float]:
        """
        计算经验CDF百分位

        公式: Prob_t = 100 × (1/M) × Σ𝟙(X_{t-i} ≤ X_t)

        窗口: W_t = {X_{t-1}, X_{t-2}, ..., X_{t-M}}
        注意：**不含当前样本X_t**，保证因果性

        Args:
            x: 当前标准化偏离

        Returns:
            Optional[float]: 百分位值（0-100），冷启动期返回None
        """
        # 冷启动检查：历史不足M时返回None
        if len(self._x_history) < self._cdf_window:
            return None

        # 获取窗口内的历史值（不含当前）
        # deque已经是固定长度，直接使用全部历史
        window = list(self._x_history)

        # 计算百分位：有多少比例的历史值 <= 当前值
        count_le = sum(1 for x_i in window if x_i <= x)
        prob = 100.0 * count_le / len(window)

        return prob

    @property
    def bar_count(self) -> int:
        """已处理的K线数量"""
        return self._bar_count

    @property
    def is_warmed_up(self) -> bool:
        """是否已完成冷启动（历史足够计算Prob）"""
        return len(self._x_history) >= self._cdf_window

    @property
    def warmup_remaining(self) -> int:
        """冷启动期剩余K线数量"""
        remaining = self._cdf_window - len(self._x_history)
        return max(0, remaining)

    def get_state(self) -> Dict:
        """
        获取当前状态（用于调试和审计）

        Returns:
            Dict: 当前状态快照
        """
        return {
            'bar_count': self._bar_count,
            'ema': self._ema,
            'mu': self._mu,
            'var': self._var,
            'x_history_len': len(self._x_history),
            'is_warmed_up': self.is_warmed_up,
            'warmup_remaining': self.warmup_remaining,
        }
