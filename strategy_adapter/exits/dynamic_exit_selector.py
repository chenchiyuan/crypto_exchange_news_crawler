"""
动态Exit选择器

Purpose:
    根据市场周期（cycle_phase）动态选择合适的卖出条件，实现策略7的自适应退出策略。

关联任务: TASK-021-006
关联功能点: FP-021-006
关联迭代: 021 - 动态周期自适应策略

策略7退出条件（Bug-027修改）：
    - 下跌期（bear_warning, bear_strong）: EMA25回归止盈，无止损
    - 震荡期（consolidation）: (P95 + EMA25) / 2 止盈，无止损
    - 上涨期（bull_warning, bull_strong）: P95止盈，无止损

Classes:
    - DynamicExitSelector: 动态Exit Condition选择器
"""

import logging
import pandas as pd
from decimal import Decimal
from typing import Optional, Dict, Any

from strategy_adapter.exits.base import IExitCondition, ExitSignal
from strategy_adapter.exits.p95_take_profit import P95TakeProfitExit
from strategy_adapter.exits.ema_reversion import EmaReversionExit

logger = logging.getLogger(__name__)


class DynamicExitSelector(IExitCondition):
    """
    动态Exit Condition选择器（策略7专用）

    根据当前市场周期（cycle_phase）动态选择合适的Exit Condition：
    - 下跌期（bear_warning, bear_strong）: EMA25回归止盈，无止损
    - 震荡期（consolidation）: (P95 + EMA25) / 2 止盈，无止损
    - 上涨期（bull_warning, bull_strong）: P95止盈，无止损

    🔧 Bug-027修改：
    - 所有周期移除止损保护
    - 震荡期止盈从P95改为(P95+EMA25)/2
    - 上涨期止盈从Mid改为P95

    设计原则：
    - 实现IExitCondition接口，无缝集成到现有架构
    - 内部持有两种Exit Conditions，根据cycle_phase动态选择
    - 震荡期止盈在check方法中直接计算

    关联文档：
    - PRD: docs/iterations/021-adaptive-exit-strategy/prd.md
    - 架构: docs/iterations/021-adaptive-exit-strategy/architecture.md
    - 任务: docs/iterations/021-adaptive-exit-strategy/tasks.md (TASK-021-006)

    🔧 TASK-021-006: 动态Exit选择逻辑核心实现
    🔧 关联功能点: FP-021-006

    Attributes:
        p95_exit: P95止盈Exit Condition（上涨期使用）
        ema_exit: EMA25回归Exit Condition（下跌期使用）
    """

    def __init__(self, stop_loss_percentage: float = 5.0):
        """
        初始化动态Exit选择器

        Args:
            stop_loss_percentage: 止损百分比（已弃用，保留参数兼容性）

        注意：
            - Bug-027修改：所有周期移除止损
            - stop_loss_percentage参数保留以保持接口兼容性
        """
        # 上涨期：P95止盈
        self.p95_exit = P95TakeProfitExit()

        # 下跌期：EMA25回归
        self.ema_exit = EmaReversionExit(ema_period=25)

        logger.info(
            f"DynamicExitSelector初始化完成: "
            f"下跌期=EMA25回归, 震荡期=(P95+EMA25)/2, 上涨期=P95止盈, "
            f"所有周期无止损"
        )

    def check(
        self,
        order: 'Order',
        kline: Dict[str, Any],
        indicators: Dict[str, Any],
        current_timestamp: int
    ) -> Optional[ExitSignal]:
        """
        检查是否触发卖出条件（动态选择）

        根据indicators中的cycle_phase，动态选择合适的Exit Condition进行检查。

        🔧 Bug-027修改：
        - 下跌期: EMA25回归止盈
        - 震荡期: (P95 + EMA25) / 2 止盈
        - 上涨期: P95止盈
        - 所有周期无止损

        Args:
            order: 持仓订单
            kline: K线数据（必须包含'high', 'low', 'close'）
            indicators: 技术指标字典（必须包含'cycle_phase', 'p95', 'ema25'）
            current_timestamp: 当前时间戳（毫秒）

        Returns:
            ExitSignal: 如果触发任何Exit Condition则返回信号，否则返回None

        Raises:
            KeyError: 当indicators缺少必要指标时抛出（由Guard Clause处理）
        """
        # Guard Clause: 验证indicators包含cycle_phase
        if 'cycle_phase' not in indicators:
            logger.warning(
                f"indicators缺少必要指标: 'cycle_phase'。"
                f"可用指标: {list(indicators.keys())}。"
                f"请确保IndicatorStateManager已计算cycle_phase。"
            )
            # 降级处理：如果没有cycle_phase，默认使用P95止盈（保守策略）
            logger.info("降级处理：使用P95止盈作为默认Exit Condition")
            return self.p95_exit.check(order, kline, indicators, current_timestamp)

        cycle_phase = indicators['cycle_phase']

        # 根据cycle_phase选择Exit Condition
        if cycle_phase in ('bear_warning', 'bear_strong'):
            # 下跌期：EMA25回归止盈
            signal = self.ema_exit.check(order, kline, indicators, current_timestamp)
            if signal:
                logger.info(
                    f"订单 {order.id} 触发下跌期止盈: "
                    f"cycle_phase={cycle_phase}, "
                    f"exit_type={signal.exit_type}, "
                    f"price={signal.price}, "
                    f"reason={signal.reason}"
                )
            return signal

        elif cycle_phase == 'consolidation':
            # 震荡期：(P95 + EMA25) / 2 止盈
            return self._check_consolidation_exit(order, kline, indicators, current_timestamp, cycle_phase)

        elif cycle_phase in ('bull_warning', 'bull_strong'):
            # 上涨期：P95止盈
            signal = self.p95_exit.check(order, kline, indicators, current_timestamp)
            if signal:
                logger.info(
                    f"订单 {order.id} 触发上涨期止盈: "
                    f"cycle_phase={cycle_phase}, "
                    f"exit_type={signal.exit_type}, "
                    f"price={signal.price}, "
                    f"reason={signal.reason}"
                )
            return signal

        else:
            # 未知周期：降级使用P95止盈（保守策略）
            logger.warning(
                f"未知的cycle_phase: {cycle_phase}。"
                f"降级处理：使用P95止盈"
            )
            return self.p95_exit.check(order, kline, indicators, current_timestamp)

    def _check_consolidation_exit(
        self,
        order: 'Order',
        kline: Dict[str, Any],
        indicators: Dict[str, Any],
        current_timestamp: int,
        cycle_phase: str
    ) -> Optional[ExitSignal]:
        """
        检查震荡期止盈条件：(P95 + EMA25) / 2

        触发逻辑：
        - 触发条件：K线最高价 >= (P95 + EMA25) / 2
        - 成交价格：K线收盘价（保守估计）

        Args:
            order: 持仓订单
            kline: K线数据
            indicators: 技术指标字典
            current_timestamp: 当前时间戳
            cycle_phase: 当前周期阶段

        Returns:
            ExitSignal: 如果触发止盈则返回信号，否则返回None
        """
        # Guard Clause: 验证indicators包含必要字段
        required_indicators = ['p95', 'ema25']
        for indicator in required_indicators:
            if indicator not in indicators:
                logger.warning(
                    f"indicators缺少必要指标: '{indicator}'。"
                    f"可用指标: {list(indicators.keys())}。"
                )
                return None

        p95 = indicators['p95']
        ema25 = indicators['ema25']

        # Guard Clause: 检查指标有效性（跳过NaN值）
        if pd.isna(p95) or pd.isna(ema25):
            logger.debug(
                f"指标值为NaN，跳过震荡期止盈检查: "
                f"p95={p95}, ema25={ema25}"
            )
            return None

        # 转换为Decimal类型（避免浮点数精度问题）
        high = Decimal(str(kline['high']))
        close = Decimal(str(kline['close']))
        p95_price = Decimal(str(p95))
        ema25_price = Decimal(str(ema25))

        # 计算阈值：(P95 + EMA25) / 2
        threshold = (p95_price + ema25_price) / Decimal('2')

        # 检查触发条件：K线最高价是否触及阈值
        if high >= threshold:
            logger.info(
                f"订单 {order.id} 触发震荡期止盈: "
                f"cycle_phase={cycle_phase}, "
                f"high={high}, threshold={threshold} "
                f"(P95={p95_price}, EMA25={ema25_price})"
            )

            return ExitSignal(
                timestamp=current_timestamp,
                price=close,  # 使用收盘价成交（保守估计）
                reason=f"震荡期止盈 ((P95+EMA25)/2={float(threshold):.2f}, 收盘价={float(close):.2f})",
                exit_type="consolidation_p95_ema25_take_profit"
            )

        return None

    def get_type(self) -> str:
        """
        返回条件类型标识

        Returns:
            str: "dynamic_exit_selector"
        """
        return "dynamic_exit_selector"

    def get_priority(self) -> int:
        """
        返回优先级（数值越小优先级越高）

        由于DynamicExitSelector是一个包装器，内部包含多个Exit Conditions，
        其实际优先级由内部选择的Exit Condition决定。

        为了确保在ExitConditionCombiner中正确排序，返回中等优先级7。
        实际检查时，会先检查高优先级的止盈（priority=5或9），再检查止损（priority=10）。

        Returns:
            int: 优先级数值7（中等优先级）
        """
        return 7
