"""
ATR计算服务
ATR Calculator Service

功能:
1. 从币安获取K线数据
2. 计算ATR指标
3. 用于确定网格步长
"""
import logging
from typing import List
from decimal import Decimal

from vp_squeeze.services.binance_kline_service import fetch_klines
from vp_squeeze.services.indicators.utils import atr as calculate_atr
from vp_squeeze.dto import KLineData

logger = logging.getLogger(__name__)


class ATRCalculator:
    """ATR计算器"""

    def __init__(self):
        """初始化ATR计算器"""
        pass

    def calculate_atr(
        self,
        symbol: str,
        interval: str = '4h',
        period: int = 14,
        limit: int = 100
    ) -> float:
        """
        计算ATR

        Args:
            symbol: 交易对，如'btc'或'BTCUSDT'
            interval: 时间周期，默认4h
            period: ATR周期，默认14
            limit: K线数量，默认100

        Returns:
            float: 当前ATR值

        Raises:
            ValueError: 数据不足或计算失败
        """
        # 获取K线数据
        klines = fetch_klines(
            symbol=symbol,
            interval=interval,
            limit=limit
        )

        if not klines or len(klines) < period:
            raise ValueError(
                f"K线数据不足，需要至少{period}根，实际{len(klines)}根"
            )

        # 提取价格数据
        highs = [float(k.high) for k in klines]
        lows = [float(k.low) for k in klines]
        closes = [float(k.close) for k in klines]

        # 计算ATR
        atr_values = calculate_atr(highs, lows, closes, period)

        if not atr_values or len(atr_values) == 0:
            raise ValueError("ATR计算失败")

        # 返回最新值
        current_atr = atr_values[-1]

        logger.info(f"ATR计算完成: symbol={symbol}, interval={interval}, ATR={current_atr:.2f}")

        return current_atr

    def calculate_grid_step(
        self,
        symbol: str,
        atr_multiplier: float = 0.8,
        interval: str = '4h',
        period: int = 14
    ) -> float:
        """
        计算网格步长（基于ATR）

        Args:
            symbol: 交易对
            atr_multiplier: ATR倍数，默认0.8
            interval: 时间周期，默认4h
            period: ATR周期，默认14

        Returns:
            float: 网格步长（绝对价格）

        Example:
            >>> calculator = ATRCalculator()
            >>> step = calculator.calculate_grid_step('btc', atr_multiplier=0.8)
            >>> print(f"网格步长: ${step:.2f}")
            网格步长: $800.00
        """
        atr = self.calculate_atr(symbol, interval, period)
        grid_step = atr * atr_multiplier

        logger.info(
            f"网格步长计算: symbol={symbol}, ATR={atr:.2f}, "
            f"multiplier={atr_multiplier}, step={grid_step:.2f}"
        )

        return grid_step


def get_atr_calculator() -> ATRCalculator:
    """
    获取ATR计算器单例

    Returns:
        ATRCalculator: 计算器实例
    """
    global _atr_calculator
    if '_atr_calculator' not in globals():
        _atr_calculator = ATRCalculator()
    return _atr_calculator


def calculate_grid_step_for_symbol(symbol: str, atr_multiplier: float = 0.8) -> float:
    """
    便捷函数：计算指定交易对的网格步长

    Args:
        symbol: 交易对
        atr_multiplier: ATR倍数

    Returns:
        float: 网格步长

    Example:
        >>> step = calculate_grid_step_for_symbol('btc', 0.8)
        >>> print(f"BTC网格步长: ${step:.2f}")
    """
    calculator = get_atr_calculator()
    return calculator.calculate_grid_step(symbol, atr_multiplier)
