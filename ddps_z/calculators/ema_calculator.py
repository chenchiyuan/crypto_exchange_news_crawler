"""
EMA计算器

负责计算指数移动平均线(EMA)及偏离率序列。

Related:
    - PRD: docs/iterations/009-ddps-z-probability-engine/prd.md (Section 3.1)
    - TASK: TASK-009-003
"""

from typing import List, Optional
from decimal import Decimal

import numpy as np
from django.conf import settings


class EMACalculator:
    """EMA计算器 - 计算EMA均线和偏离率"""

    def __init__(self, period: Optional[int] = None):
        """
        初始化EMA计算器

        Args:
            period: EMA周期，默认从settings.DDPS_CONFIG获取
        """
        self.period = period or settings.DDPS_CONFIG['EMA_PERIOD']

    def calculate_ema_series(self, prices: np.ndarray) -> np.ndarray:
        """
        计算EMA序列

        公式:
            k = 2 / (N + 1)  # 平滑系数
            EMA_0 = SMA(前N期)
            EMA_t = k × Price_t + (1 - k) × EMA_{t-1}

        Args:
            prices: 收盘价序列 (numpy array)

        Returns:
            EMA序列，前period-1个值为NaN

        Raises:
            ValueError: 数据不足时抛出
        """
        if len(prices) < self.period:
            raise ValueError(
                f"数据不足: 需要至少{self.period}根K线，"
                f"实际只有{len(prices)}根"
            )

        # 平滑系数
        k = 2.0 / (self.period + 1)

        # 初始化EMA数组，前period-1个值设为NaN
        ema_values = np.full(len(prices), np.nan)

        # 初值: 使用前period期的SMA
        ema_values[self.period - 1] = np.mean(prices[:self.period])

        # 递推计算EMA
        for i in range(self.period, len(prices)):
            ema_values[i] = k * prices[i] + (1 - k) * ema_values[i - 1]

        return ema_values

    def calculate_deviation_series(self, prices: np.ndarray) -> np.ndarray:
        """
        计算偏离率序列 D_t

        公式:
            D_t = (Price_t - EMA_t) / EMA_t

        Args:
            prices: 收盘价序列 (numpy array)

        Returns:
            偏离率序列，前period-1个值为NaN

        Raises:
            ValueError: 数据不足时抛出
        """
        ema_series = self.calculate_ema_series(prices)

        # 计算偏离率
        # 避免除零：EMA为0的位置保持NaN
        with np.errstate(divide='ignore', invalid='ignore'):
            deviation = (prices - ema_series) / ema_series
            # 将inf和-inf替换为NaN
            deviation = np.where(np.isinf(deviation), np.nan, deviation)

        return deviation

    def calculate_from_klines(
        self,
        klines: List[dict],
        price_field: str = 'close_price'
    ) -> dict:
        """
        从K线数据计算EMA和偏离率

        Args:
            klines: K线数据列表，每个元素需包含价格字段
            price_field: 价格字段名称，默认'close_price'

        Returns:
            {
                'prices': np.ndarray,  # 价格序列
                'ema': np.ndarray,     # EMA序列
                'deviation': np.ndarray,  # 偏离率序列
                'current_ema': float,  # 当前EMA值
                'current_deviation': float,  # 当前偏离率
            }

        Raises:
            ValueError: 数据不足或格式错误时抛出
        """
        if not klines:
            raise ValueError("K线数据为空")

        # 提取价格序列
        prices = []
        for kline in klines:
            price = kline.get(price_field)
            if price is None:
                # 尝试其他常见字段名
                price = kline.get('close') or kline.get('close_price')
            if price is None:
                raise ValueError(f"K线数据缺少价格字段: {price_field}")
            prices.append(float(price))

        prices = np.array(prices)

        # 计算EMA和偏离率
        ema_series = self.calculate_ema_series(prices)
        deviation_series = self.calculate_deviation_series(prices)

        # 获取当前值（最后一个有效值）
        current_ema = ema_series[-1] if not np.isnan(ema_series[-1]) else None
        current_deviation = deviation_series[-1] if not np.isnan(deviation_series[-1]) else None

        return {
            'prices': prices,
            'ema': ema_series,
            'deviation': deviation_series,
            'current_ema': current_ema,
            'current_deviation': current_deviation,
        }
