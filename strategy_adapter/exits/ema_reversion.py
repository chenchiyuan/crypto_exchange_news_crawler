"""
EMA回归卖出条件

Purpose:
    当价格回归到指定EMA线时触发卖出。

关联任务: TASK-017-005
关联功能点: FP-017-008

Classes:
    - EmaReversionExit: EMA回归卖出条件
"""

import logging
from decimal import Decimal
from typing import Optional, Dict, Any

from strategy_adapter.exits.base import IExitCondition, ExitSignal

logger = logging.getLogger(__name__)


class EmaReversionExit(IExitCondition):
    """
    EMA回归卖出条件

    当K线价格范围触及指定EMA值时触发卖出。
    检查逻辑: K线low <= EMA <= K线high

    Attributes:
        ema_period: EMA周期（7, 25, 99）
    """

    def __init__(self, ema_period: int = 25):
        """
        初始化EMA回归条件

        Args:
            ema_period: EMA周期，支持 7, 25, 99
        """
        if ema_period not in (7, 25, 99):
            raise ValueError(f"不支持的EMA周期: {ema_period}，仅支持7, 25, 99")
        self.ema_period = ema_period
        self._indicator_key = f"ema{ema_period}"

    def check(
        self,
        order: 'Order',
        kline: Dict[str, Any],
        indicators: Dict[str, Any],
        current_timestamp: int
    ) -> Optional[ExitSignal]:
        """
        检查是否触及EMA

        Args:
            order: 持仓订单
            kline: K线数据
            indicators: 技术指标（必须包含对应的ema值）
            current_timestamp: 当前时间戳

        Returns:
            ExitSignal: 如果触及EMA则返回信号
        """
        # 获取EMA值
        ema_value = indicators.get(self._indicator_key)
        if ema_value is None:
            logger.warning(f"指标中缺少{self._indicator_key}")
            return None

        ema_value = Decimal(str(ema_value))
        low = Decimal(str(kline['low']))
        high = Decimal(str(kline['high']))

        # 检查K线是否触及EMA
        if low <= ema_value <= high:
            return ExitSignal(
                timestamp=current_timestamp,
                price=ema_value,  # 以EMA价格成交
                reason=f"价格回归EMA{self.ema_period}",
                exit_type=self.get_type()
            )

        return None

    def get_type(self) -> str:
        return "ema_reversion"

    def get_priority(self) -> int:
        # EMA回归优先级最低
        return 30
