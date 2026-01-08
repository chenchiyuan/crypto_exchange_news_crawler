"""
P95止盈卖出条件

Purpose:
    当K线价格达到P95静态阈值时触发止盈卖出。
    P95是DDPS-Z策略的上界阈值，计算公式为：P95 = EMA25 * (1 + 1.645 * EWMA_STD)

关联任务: TASK-019 (Bug-021修复)
关联功能点: 策略5 - 强势上涨周期EMA25回调策略

Classes:
    - P95TakeProfitExit: P95止盈卖出条件
"""

import logging
import pandas as pd
from decimal import Decimal
from typing import Optional, Dict, Any

from strategy_adapter.exits.base import IExitCondition, ExitSignal

logger = logging.getLogger(__name__)


class P95TakeProfitExit(IExitCondition):
    """
    P95止盈卖出条件

    当K线最高价达到或超过P95阈值时触发止盈。
    P95是DDPS-Z策略的统计上界，基于EMA和EWMA标准差动态计算。

    Example:
        >>> exit_condition = P95TakeProfitExit()
        >>> signal = exit_condition.check(order, kline, indicators, timestamp)
        >>> if signal:
        ...     print(f"触发P95止盈: {signal.price}")
    """

    def __init__(self):
        """初始化P95止盈条件"""
        pass

    def check(
        self,
        order: 'Order',
        kline: Dict[str, Any],
        indicators: Dict[str, Any],
        current_timestamp: int
    ) -> Optional[ExitSignal]:
        """
        检查是否触发P95止盈

        使用收盘价计算成交价，避免盘中波动误触发。

        触发逻辑：
        - 触发条件：K线最高价 >= P95（价格触及上界）
        - 成交价格：K线收盘价（更符合回测合理性）

        🔧 策略6需求：K线最高价触及P95，使用close卖出
        🔧 与Bug-024修复保持一致：止损和止盈均使用close价格

        Args:
            order: 持仓订单
            kline: K线数据（包含high和close字段）
            indicators: 技术指标字典（必须包含'p95'）
            current_timestamp: 当前时间戳

        Returns:
            ExitSignal: 如果触发止盈则返回信号，否则返回None
        """
        # Guard Clause: 验证indicators中包含p95
        if 'p95' not in indicators:
            logger.warning(f"indicators缺少p95指标，无法检查P95止盈")
            return None

        # 获取当前K线的P95值
        p95_value = indicators['p95']

        # Guard Clause: 跳过NaN值
        if pd.isna(p95_value):
            return None

        # 将P95值转换为Decimal
        p95_price = Decimal(str(p95_value))
        high = Decimal(str(kline['high']))
        close = Decimal(str(kline['close']))

        # 检查K线最高价是否触及P95
        if high >= p95_price:
            return ExitSignal(
                timestamp=current_timestamp,
                price=close,  # 以收盘价成交（更符合回测合理性）
                reason=f"P95止盈 (P95={float(p95_price):.2f}, 收盘价={float(close):.2f})",
                exit_type=self.get_type()
            )

        return None

    def get_type(self) -> str:
        """返回条件类型标识"""
        return "p95_take_profit"

    def get_priority(self) -> int:
        """
        返回优先级（数值越小优先级越高）

        P95止盈优先级设为9，高于止损的10。
        确保先检查止盈条件，避免在接近P95时被止损提前平仓。

        优先级说明：
        - EMA回归: 5（最高优先级）
        - P95止盈: 9
        - 止损: 10
        - 固定百分比止盈: 20
        """
        return 9
