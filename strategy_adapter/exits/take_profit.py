"""
止盈卖出条件

Purpose:
    当盈利达到指定百分比时触发止盈卖出。

关联任务: TASK-017-007
关联功能点: FP-017-010

Classes:
    - TakeProfitExit: 止盈卖出条件
"""

import logging
from decimal import Decimal
from typing import Optional, Dict, Any

from strategy_adapter.exits.base import IExitCondition, ExitSignal

logger = logging.getLogger(__name__)


class TakeProfitExit(IExitCondition):
    """
    止盈卖出条件

    当K线最高价达到或超过止盈价时触发。
    止盈价 = 买入价 * (1 + 止盈百分比)

    Attributes:
        percentage: 止盈百分比（如10表示10%）
    """

    def __init__(self, percentage: float = 10.0):
        """
        初始化止盈条件

        Args:
            percentage: 止盈百分比，如10表示盈利10%时止盈
        """
        if percentage <= 0:
            raise ValueError(f"止盈百分比必须大于0: {percentage}")
        self.percentage = Decimal(str(percentage)) / Decimal("100")

    def check(
        self,
        order: 'Order',
        kline: Dict[str, Any],
        indicators: Dict[str, Any],
        current_timestamp: int
    ) -> Optional[ExitSignal]:
        """
        检查是否触发止盈

        Args:
            order: 持仓订单
            kline: K线数据
            indicators: 技术指标（止盈不使用）
            current_timestamp: 当前时间戳

        Returns:
            ExitSignal: 如果触发止盈则返回信号
        """
        open_price = order.open_price
        take_profit_price = open_price * (Decimal("1") + self.percentage)

        high = Decimal(str(kline['high']))

        # 检查K线最高价是否触及止盈价
        if high >= take_profit_price:
            return ExitSignal(
                timestamp=current_timestamp,
                price=take_profit_price,  # 以止盈价成交（非收盘价）
                reason=f"止盈触发 ({self.percentage * 100:.1f}%)",
                exit_type=self.get_type()
            )

        return None

    def get_type(self) -> str:
        return "take_profit"

    def get_priority(self) -> int:
        # 止盈优先级次高
        return 20
