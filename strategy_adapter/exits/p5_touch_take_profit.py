"""
P5触及止盈卖出条件

Purpose:
    当K线价格触及P5静态阈值时触发止盈平仓（主要用于做空订单）。
    P5是DDPS-Z策略的下界阈值，计算公式为：P5 = EMA25 * (1 - 1.645 * EWMA_STD)

关联任务: TASK-022-001
关联功能点: FP-022-004 - 策略8强势下跌区间做空策略
关联架构: architecture.md 2.1节 - P5TouchTakeProfitExit组件

Classes:
    - P5TouchTakeProfitExit: P5触及止盈卖出条件（做空订单专用）
"""

import logging
import pandas as pd
from decimal import Decimal
from typing import Optional, Dict, Any

from strategy_adapter.exits.base import IExitCondition, ExitSignal

logger = logging.getLogger(__name__)


class P5TouchTakeProfitExit(IExitCondition):
    """
    P5触及止盈卖出条件（策略8专用）

    当K线最低价触及或低于P5支撑位时触发止盈平仓。
    P5是DDPS-Z策略的统计下界，基于EMA和EWMA标准差动态计算。
    主要用于做空订单的止盈。

    设计对标：P95TakeProfitExit（镜像关系）
    逻辑差异：检查low <= P5（而非high >= P95）
    成交价格：使用close（与P95保持一致，避免理想化假设）

    Example:
        >>> exit_condition = P5TouchTakeProfitExit()
        >>> signal = exit_condition.check(order, kline, indicators, timestamp)
        >>> if signal:
        ...     print(f"触发P5止盈: {signal.price}")
    """

    def __init__(self):
        """
        初始化P5触及止盈条件

        无需参数，P5值从indicators中动态获取
        """
        pass

    def check(
        self,
        order: 'Order',
        kline: Dict[str, Any],
        indicators: Dict[str, Any],
        current_timestamp: int
    ) -> Optional[ExitSignal]:
        """
        检查是否触发P5触及止盈

        使用收盘价计算成交价，避免理想化假设（使用low会过于乐观）。

        触发逻辑：
        - 触发条件：K线最低价 <= P5（价格触及下界支撑位）
        - 成交价格：K线收盘价（更符合实际交易逻辑）

        🔧 策略8需求：做空订单在K线low触及P5时，使用当根close止盈
        🔧 与P95TakeProfitExit镜像对称：P95检查high，P5检查low
        🔧 与BUG-024修复保持一致：止损和止盈均使用close价格

        为什么使用close而非low：
        1. 避免理想化假设（low是当根K线最优价格，实际难以成交）
        2. 与P95TakeProfitExit保持一致（P95使用close而非high）
        3. 符合实际交易逻辑，接受合理的1-2%滑点
        4. 与BUG-024修复保持架构一致性

        Args:
            order: 持仓订单（做空订单）
            kline: K线数据（包含low和close字段）
            indicators: 技术指标字典（必须包含'p5'）
            current_timestamp: 当前时间戳

        Returns:
            ExitSignal: 如果触发止盈则返回信号，否则返回None

        Raises:
            KeyError: 如果kline缺少'low'或'close'字段
        """
        # Guard Clause: 验证indicators中包含p5
        if 'p5' not in indicators:
            logger.warning(f"indicators缺少p5指标，无法检查P5触及止盈")
            return None

        # 获取当前K线的P5值
        p5_value = indicators['p5']

        # Guard Clause: 跳过NaN值
        if pd.isna(p5_value):
            return None

        # 将P5值转换为Decimal（确保精度）
        p5_price = Decimal(str(p5_value))
        low = Decimal(str(kline['low']))
        close = Decimal(str(kline['close']))

        # 检查K线最低价是否触及P5支撑位
        if low <= p5_price:
            return ExitSignal(
                timestamp=current_timestamp,
                price=close,  # 以收盘价成交（避免理想化假设）
                reason=f"P5触及止盈 (P5={float(p5_price):.2f}, 收盘价={float(close):.2f})",
                exit_type=self.get_type()
            )

        return None

    def get_type(self) -> str:
        """
        返回条件类型标识

        Returns:
            str: Exit类型标识 "p5_touch_take_profit"
        """
        return "p5_touch_take_profit"

    def get_priority(self) -> int:
        """
        返回优先级（数值越小优先级越高）

        P5触及止盈优先级设为9，与P95TakeProfitExit保持一致。
        确保止盈优先于止损检查。

        优先级说明：
        - EMA回归: 5（最高优先级）
        - P95/P5止盈: 9（高优先级止盈）
        - 止损: 10
        - 固定百分比止盈: 20

        Returns:
            int: 优先级值9
        """
        return 9
