"""
ADX 计算器 (Average Directional Index)

负责计算 14 周期 ADX 指标，用于衡量趋势强度。

Related:
    - PRD: docs/iterations/010-ddps-z-inertia-fan/prd.md
    - Architecture: docs/iterations/010-ddps-z-inertia-fan/architecture.md
    - TASK: TASK-010-001
"""

import logging
from typing import Any, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)


class ADXCalculator:
    """
    ADX 计算器 - 计算 Average Directional Index

    ADX 用于衡量趋势的强度，范围 [0, 100]。
    - ADX > 25: 趋势较强
    - ADX < 20: 趋势较弱或震荡
    """

    def __init__(self, period: int = 14):
        """
        初始化 ADX 计算器

        Args:
            period: ADX 周期，默认 14
        """
        if period < 2:
            raise ValueError(f"ADX 周期必须 >= 2，当前值: {period}")
        self.period = period

    def calculate(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray
    ) -> Dict[str, Any]:
        """
        计算 ADX 指标

        计算公式:
            +DM = High[t] - High[t-1]  (若为正且 > -DM，否则为 0)
            -DM = Low[t-1] - Low[t]    (若为正且 > +DM，否则为 0)
            TR = max(High - Low, |High - Close[t-1]|, |Low - Close[t-1]|)

            +DI = 100 × Smoothed(+DM) / Smoothed(TR)
            -DI = 100 × Smoothed(-DM) / Smoothed(TR)
            DX = 100 × |+DI - -DI| / (+DI + -DI)
            ADX = Smoothed(DX)

        Args:
            high: 最高价序列
            low: 最低价序列
            close: 收盘价序列

        Returns:
            {
                'plus_di': np.ndarray,   # +DI 序列
                'minus_di': np.ndarray,  # -DI 序列
                'dx': np.ndarray,        # DX 序列
                'adx': np.ndarray,       # ADX 序列
                'current_adx': float | None,  # 当前 ADX 值
                'current_plus_di': float | None,
                'current_minus_di': float | None,
            }

        Raises:
            ValueError: 数据不足时抛出
        """
        n = len(high)
        min_required = self.period * 2  # ADX 需要至少 2 倍周期的数据

        if n < min_required:
            logger.warning(
                f"ADX 计算数据不足: 需要至少 {min_required} 根K线，"
                f"实际只有 {n} 根"
            )
            return {
                'plus_di': np.full(n, np.nan),
                'minus_di': np.full(n, np.nan),
                'dx': np.full(n, np.nan),
                'adx': np.full(n, np.nan),
                'current_adx': None,
                'current_plus_di': None,
                'current_minus_di': None,
            }

        # Step 1: 计算 +DM 和 -DM
        plus_dm, minus_dm = self._calculate_dm(high, low)

        # Step 2: 计算 True Range (TR)
        tr = self._calculate_tr(high, low, close)

        # Step 3: 计算平滑后的 +DM, -DM, TR (使用 Wilder 平滑)
        smoothed_plus_dm = self._wilder_smooth(plus_dm, self.period)
        smoothed_minus_dm = self._wilder_smooth(minus_dm, self.period)
        smoothed_tr = self._wilder_smooth(tr, self.period)

        # Step 4: 计算 +DI 和 -DI
        plus_di = np.full(n, np.nan)
        minus_di = np.full(n, np.nan)

        # 避免除零
        valid_tr = smoothed_tr != 0
        plus_di[valid_tr] = 100 * smoothed_plus_dm[valid_tr] / smoothed_tr[valid_tr]
        minus_di[valid_tr] = 100 * smoothed_minus_dm[valid_tr] / smoothed_tr[valid_tr]

        # Step 5: 计算 DX
        dx = np.full(n, np.nan)
        di_sum = plus_di + minus_di
        valid_di = di_sum != 0
        dx[valid_di] = 100 * np.abs(plus_di[valid_di] - minus_di[valid_di]) / di_sum[valid_di]

        # Step 6: 计算 ADX (对 DX 进行 Wilder 平滑)
        adx = self._wilder_smooth(dx, self.period)

        # 获取当前值
        current_adx = adx[-1] if not np.isnan(adx[-1]) else None
        current_plus_di = plus_di[-1] if not np.isnan(plus_di[-1]) else None
        current_minus_di = minus_di[-1] if not np.isnan(minus_di[-1]) else None

        return {
            'plus_di': plus_di,
            'minus_di': minus_di,
            'dx': dx,
            'adx': adx,
            'current_adx': current_adx,
            'current_plus_di': current_plus_di,
            'current_minus_di': current_minus_di,
        }

    def _calculate_dm(
        self,
        high: np.ndarray,
        low: np.ndarray
    ) -> tuple:
        """
        计算 Directional Movement (+DM 和 -DM)

        规则:
        - +DM = High[t] - High[t-1] (若为正)
        - -DM = Low[t-1] - Low[t] (若为正)
        - 如果 +DM > -DM，则 -DM = 0
        - 如果 -DM > +DM，则 +DM = 0
        - 如果相等，则两者都为 0

        Returns:
            (plus_dm, minus_dm) 两个 numpy 数组
        """
        n = len(high)
        plus_dm = np.zeros(n)
        minus_dm = np.zeros(n)

        for i in range(1, n):
            up_move = high[i] - high[i - 1]
            down_move = low[i - 1] - low[i]

            if up_move > down_move and up_move > 0:
                plus_dm[i] = up_move
            if down_move > up_move and down_move > 0:
                minus_dm[i] = down_move

        return plus_dm, minus_dm

    def _calculate_tr(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray
    ) -> np.ndarray:
        """
        计算 True Range (TR)

        TR = max(
            High - Low,
            |High - Close[t-1]|,
            |Low - Close[t-1]|
        )

        Returns:
            True Range 序列
        """
        n = len(high)
        tr = np.zeros(n)

        # 第一根 K 线的 TR = High - Low
        tr[0] = high[0] - low[0]

        for i in range(1, n):
            hl = high[i] - low[i]
            hc = abs(high[i] - close[i - 1])
            lc = abs(low[i] - close[i - 1])
            tr[i] = max(hl, hc, lc)

        return tr

    def _wilder_smooth(
        self,
        data: np.ndarray,
        period: int
    ) -> np.ndarray:
        """
        Wilder 平滑（用于 ADX 计算）

        公式:
            First = AVERAGE(data, period)
            Smoothed[t] = Smoothed[t-1] + (data[t] - Smoothed[t-1]) / period

        等价于:
            Smoothed[t] = (1 - 1/period) * Smoothed[t-1] + (1/period) * data[t]
            Smoothed[t] = Smoothed[t-1] - Smoothed[t-1]/period + data[t]/period

        这是 EMA(data, period) 的 Wilder 变体（α = 1/period）

        Returns:
            平滑后的序列
        """
        n = len(data)
        smoothed = np.full(n, np.nan)

        # 找到第一个有效数据的起始索引
        first_valid = period - 1

        # 处理含有 NaN 的数据
        if np.any(np.isnan(data[:period])):
            # 找到足够多有效数据的起始点
            valid_count = 0
            for i in range(n):
                if not np.isnan(data[i]):
                    valid_count += 1
                    if valid_count == period:
                        first_valid = i
                        break
            else:
                # 数据不足
                return smoothed

        # 初始值: 前 period 个有效数据的平均值
        if first_valid >= n:
            return smoothed

        # 计算初始和
        initial_sum = 0
        count = 0
        start_idx = 0
        for i in range(n):
            if not np.isnan(data[i]):
                if count == 0:
                    start_idx = i
                initial_sum += data[i]
                count += 1
                if count == period:
                    first_valid = i
                    break

        if count < period:
            return smoothed

        # 初始值是平均值
        smoothed[first_valid] = initial_sum / period

        # 🔧 修复：递推计算（data[i]也需要除以period）
        # 正确公式: Smoothed[t] = Smoothed[t-1] + (data[t] - Smoothed[t-1]) / period
        for i in range(first_valid + 1, n):
            if np.isnan(data[i]):
                smoothed[i] = smoothed[i - 1]
            else:
                smoothed[i] = smoothed[i - 1] + (data[i] - smoothed[i - 1]) / period

        return smoothed

    def get_current_adx(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray
    ) -> Optional[float]:
        """
        便捷方法: 只获取当前 ADX 值

        Returns:
            当前 ADX 值，数据不足返回 None
        """
        result = self.calculate(high, low, close)
        return result['current_adx']
