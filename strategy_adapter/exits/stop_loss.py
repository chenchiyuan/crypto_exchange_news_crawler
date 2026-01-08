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

    使用K线极值价格判断止损触发，使用收盘价成交。
    支持做多和做空两种订单类型。

    止损逻辑：
    - 做多订单:
      - 触发判断: 亏损率 = (开仓价 - 最低价) / 开仓价，超过阈值时触发
      - 成交价格: 使用收盘价（保守估计）
    - 做空订单:
      - 触发判断: 亏损率 = (最高价 - 开仓价) / 开仓价，超过阈值时触发
      - 成交价格: 使用收盘价（保守估计）

    🔧 Bug-024修复: 支持做空订单
    🔧 Bug-025修复: 使用low/high判断触发，close价格成交，避免止损延迟

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

        使用K线极值价格判断止损触发，使用收盘价成交：
        - 做多: 使用最低价判断触发（亏损率 = (开仓价 - 最低价) / 开仓价）
        - 做空: 使用最高价判断触发（亏损率 = (最高价 - 开仓价) / 开仓价）
        - 成交: 两种方向都使用收盘价成交（保守估计）

        🔧 Bug-024修复: 支持做空订单
        🔧 Bug-025修复: 分离触发价格和成交价格，避免止损延迟导致亏损超预期

        Args:
            order: 持仓订单
            kline: K线数据（必须包含high, low, close）
            indicators: 技术指标（止损不使用）
            current_timestamp: 当前时间戳

        Returns:
            ExitSignal: 如果触发止损则返回信号，否则返回None
        """
        open_price = order.open_price
        close_price = Decimal(str(kline['close']))
        direction = getattr(order, 'direction', 'long')  # 默认做多（向后兼容）

        # 根据订单方向选择触发价格
        if direction == 'short':
            # 做空：使用最高价判断止损触发
            # 当价格上涨触及止损价时，最高价会显示出来
            trigger_price = Decimal(str(kline['high']))
            loss_rate = (trigger_price - open_price) / open_price
        else:
            # 做多：使用最低价判断止损触发
            # 当价格下跌触及止损价时，最低价会显示出来
            trigger_price = Decimal(str(kline['low']))
            loss_rate = (open_price - trigger_price) / open_price

        # 检查是否触发止损（亏损率超过阈值）
        if loss_rate > self.percentage:
            logger.info(
                f"止损触发 - 订单ID: {order.id}, 方向: {direction}, "
                f"开仓价: {open_price}, 触发价: {trigger_price}, 成交价: {close_price}, "
                f"亏损率: {loss_rate*100:.2f}%, 阈值: {self.percentage*100:.1f}%"
            )

            return ExitSignal(
                timestamp=current_timestamp,
                price=close_price,  # 使用收盘价成交（保守估计）
                reason=f"止损触发 ({self.percentage * 100:.1f}%)",
                exit_type=self.get_type()
            )

        return None

    def get_type(self) -> str:
        return "stop_loss"

    def get_priority(self) -> int:
        # 止损优先级最高
        return 10
