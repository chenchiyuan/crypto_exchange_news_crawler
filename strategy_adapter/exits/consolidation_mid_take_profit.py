"""
震荡中值止盈卖出条件

Purpose:
    当K线价格达到震荡中值（P95与inertia_mid的中点）时触发止盈卖出。
    适用于策略7的上涨期（bull_warning, bull_strong）场景。

关联任务: TASK-021-001
关联功能点: FP-021-001
关联迭代: 021 - 动态周期自适应策略

Classes:
    - ConsolidationMidTakeProfitExit: 震荡中值止盈卖出条件
"""

import logging
import pandas as pd
from decimal import Decimal
from typing import Optional, Dict, Any

from strategy_adapter.exits.base import IExitCondition, ExitSignal

logger = logging.getLogger(__name__)


class ConsolidationMidTakeProfitExit(IExitCondition):
    """
    震荡中值止盈卖出条件（上涨期使用）

    当K线最高价达到或超过震荡中值阈值时触发止盈。
    震荡中值定义为：threshold = (P95 + inertia_mid) / 2

    触发逻辑：
    - 触发条件：K线最高价 >= (P95 + inertia_mid) / 2
    - 成交价格：K线收盘价（保守估计，符合回测合理性）

    适用场景：
        策略7 - 动态周期自适应策略
        上涨期（bull_warning, bull_strong）的止盈条件

    优先级：
        priority = 5（与EmaReversionExit一致，高于P95的9和StopLoss的10）

    关联文档：
        - PRD: docs/iterations/021-adaptive-exit-strategy/prd.md
        - 架构: docs/iterations/021-adaptive-exit-strategy/architecture.md (Line 466-589)
        - 决策点2: 上涨期止盈的mid定义为inertia_mid

    Example:
        >>> exit_condition = ConsolidationMidTakeProfitExit()
        >>> signal = exit_condition.check(order, kline, indicators, timestamp)
        >>> if signal:
        ...     print(f"触发震荡中值止盈: {signal.price}")
    """

    def __init__(self):
        """初始化震荡中值止盈条件"""
        pass

    def check(
        self,
        order: 'Order',
        kline: Dict[str, Any],
        indicators: Dict[str, Any],
        current_timestamp: int
    ) -> Optional[ExitSignal]:
        """
        检查是否触发震荡中值止盈

        使用K线极值价格（high）判断是否触及阈值，使用收盘价（close）成交。

        触发逻辑：
        - 触发判断: K线最高价 >= (P95 + inertia_mid) / 2
        - 成交价格: K线收盘价（保守估计，避免使用最优价格）

        🔧 策略7需求：上涨期使用Mid止盈
        🔧 与Bug-025修复保持一致：触发价和成交价分离

        Args:
            order: 持仓订单
            kline: K线数据（必须包含'high', 'close'）
            indicators: 技术指标字典（必须包含'p95', 'inertia_mid'）
            current_timestamp: 当前时间戳（毫秒）

        Returns:
            ExitSignal: 如果触发止盈则返回信号，否则返回None

        Raises:
            KeyError: 当indicators缺少必要指标时抛出（由Guard Clause处理）
        """
        # Guard Clause: 验证indicators包含必要字段
        required_indicators = ['p95', 'inertia_mid']
        for indicator in required_indicators:
            if indicator not in indicators:
                logger.warning(
                    f"indicators缺少必要指标: '{indicator}'。"
                    f"可用指标: {list(indicators.keys())}。"
                    f"请确保IndicatorStateManager已计算p95和inertia_mid。"
                )
                return None

        # 提取指标和价格
        p95 = indicators['p95']
        inertia_mid = indicators['inertia_mid']

        # Guard Clause: 检查指标有效性（跳过NaN值）
        if pd.isna(p95) or pd.isna(inertia_mid):
            logger.debug(
                f"指标值为NaN，跳过震荡中值止盈检查: "
                f"p95={p95}, inertia_mid={inertia_mid}"
            )
            return None

        # 转换为Decimal类型（避免浮点数精度问题）
        high = Decimal(str(kline['high']))
        close = Decimal(str(kline['close']))
        p95_price = Decimal(str(p95))
        inertia_mid_price = Decimal(str(inertia_mid))

        # 计算阈值：(P95 + inertia_mid) / 2
        threshold = (p95_price + inertia_mid_price) / Decimal('2')

        # 检查触发条件：K线最高价是否触及阈值
        if high >= threshold:
            logger.info(
                f"订单 {order.id} 触发震荡中值止盈: "
                f"high={high}, threshold={threshold} "
                f"(P95={p95_price}, inertia_mid={inertia_mid_price})"
            )

            return ExitSignal(
                timestamp=current_timestamp,
                price=close,  # 使用收盘价成交（保守估计）
                reason=f"震荡中值止盈 (阈值={float(threshold):.2f}, 收盘价={float(close):.2f})",
                exit_type=self.get_type()
            )

        return None

    def get_type(self) -> str:
        """
        返回条件类型标识

        Returns:
            str: "consolidation_mid_take_profit"
        """
        return "consolidation_mid_take_profit"

    def get_priority(self) -> int:
        """
        返回优先级（数值越小优先级越高）

        优先级设为5，与EmaReversionExit一致，高于P95的9和StopLoss的10。
        确保在上涨期优先检查Mid止盈，再检查止损。

        优先级说明：
        - EMA回归/Mid止盈: 5（最高优先级）
        - P95止盈: 9
        - 止损: 10
        - 固定百分比止盈: 20

        Returns:
            int: 优先级数值5
        """
        return 5
