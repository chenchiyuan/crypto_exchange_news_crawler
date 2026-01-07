"""
止损卖出条件

Purpose:
    当亏损达到指定百分比时触发止损卖出。

关联任务: TASK-017-006
关联功能点: FP-017-009

Classes:
    - StopLossExit: 止损卖出条件
"""

import logging
from decimal import Decimal
from typing import Optional, Dict, Any

from strategy_adapter.exits.base import IExitCondition, ExitSignal

logger = logging.getLogger(__name__)


class StopLossExit(IExitCondition):
    """
    止损卖出条件

    当K线最低价达到或低于止损价时触发。
    止损价 = 买入价 * (1 - 止损百分比)

    Attributes:
        percentage: 止损百分比（如5表示5%）
    """

    def __init__(self, percentage: float = 5.0):
        """
        初始化止损条件

        Args:
            percentage: 止损百分比，如5表示亏损5%时止损
        """
        if percentage <= 0 or percentage >= 100:
            raise ValueError(f"止损百分比必须在0-100之间: {percentage}")
        self.percentage = Decimal(str(percentage)) / Decimal("100")

    def check(
        self,
        order: 'Order',
        kline: Dict[str, Any],
        indicators: Dict[str, Any],
        current_timestamp: int
    ) -> Optional[ExitSignal]:
        """
        检查是否触发止损

        Args:
            order: 持仓订单
            kline: K线数据
            indicators: 技术指标（止损不使用）
            current_timestamp: 当前时间戳

        Returns:
            ExitSignal: 如果触发止损则返回信号
        """
        open_price = order.open_price
        stop_loss_price = open_price * (Decimal("1") - self.percentage)

        low = Decimal(str(kline['low']))

        # 检查K线最低价是否触及止损价
        if low <= stop_loss_price:
            return ExitSignal(
                timestamp=current_timestamp,
                price=stop_loss_price,  # 以止损价成交（非收盘价）
                reason=f"止损触发 ({self.percentage * 100:.1f}%)",
                exit_type=self.get_type()
            )

        return None

    def get_type(self) -> str:
        return "stop_loss"

    def get_priority(self) -> int:
        # 止损优先级最高
        return 10
