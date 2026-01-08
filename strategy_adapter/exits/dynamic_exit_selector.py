"""
动态Exit选择器

Purpose:
    根据市场周期（cycle_phase）动态选择合适的卖出条件，实现策略7的自适应退出策略。

关联任务: TASK-021-006
关联功能点: FP-021-006
关联迭代: 021 - 动态周期自适应策略

Classes:
    - DynamicExitSelector: 动态Exit Condition选择器
"""

import logging
from typing import Optional, Dict, Any

from strategy_adapter.exits.base import IExitCondition, ExitSignal
from strategy_adapter.exits.p95_take_profit import P95TakeProfitExit
from strategy_adapter.exits.ema_reversion import EmaReversionExit
from strategy_adapter.exits.consolidation_mid_take_profit import ConsolidationMidTakeProfitExit
from strategy_adapter.exits.stop_loss import StopLossExit

logger = logging.getLogger(__name__)


class DynamicExitSelector(IExitCondition):
    """
    动态Exit Condition选择器（策略7专用）

    根据当前市场周期（cycle_phase）动态选择合适的Exit Condition：
    - 震荡期（consolidation）: P95止盈 + 5%止损
    - 下跌期（bear_warning, bear_strong）: EMA25回归 + 5%止损
    - 上涨期（bull_warning, bull_strong）: Mid止盈 + 5%止损

    设计原则：
    - 实现IExitCondition接口，无缝集成到现有架构
    - 内部持有三种Exit Conditions，根据cycle_phase动态选择
    - 优先级由内部Exit Condition决定（P95=9, EMA=5, Mid=5, 止损=10）

    关联文档：
    - PRD: docs/iterations/021-adaptive-exit-strategy/prd.md
    - 架构: docs/iterations/021-adaptive-exit-strategy/architecture.md
    - 任务: docs/iterations/021-adaptive-exit-strategy/tasks.md (TASK-021-006)

    🔧 TASK-021-006: 动态Exit选择逻辑核心实现
    🔧 关联功能点: FP-021-006

    Attributes:
        p95_exit: P95止盈Exit Condition（震荡期使用）
        ema_exit: EMA25回归Exit Condition（下跌期使用）
        mid_exit: 震荡中值止盈Exit Condition（上涨期使用）
        stop_loss_exit: 5%止损Exit Condition（所有周期共用）
    """

    def __init__(self, stop_loss_percentage: float = 5.0):
        """
        初始化动态Exit选择器

        Args:
            stop_loss_percentage: 止损百分比（默认5%）

        注意：
            - P95止盈、EMA25回归、Mid止盈都使用默认参数
            - 止损百分比可配置，默认5%
        """
        # 震荡期：P95止盈
        self.p95_exit = P95TakeProfitExit()

        # 下跌期：EMA25回归
        self.ema_exit = EmaReversionExit(ema_period=25)

        # 上涨期：Mid止盈
        self.mid_exit = ConsolidationMidTakeProfitExit()

        # 通用：止损（所有周期共用）
        self.stop_loss_exit = StopLossExit(percentage=stop_loss_percentage)

        logger.info(
            f"DynamicExitSelector初始化完成: "
            f"P95止盈（震荡期）, EMA25回归（下跌期）, Mid止盈（上涨期）, "
            f"{stop_loss_percentage}%止损（通用）"
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

        检查顺序（符合优先级）：
        1. 周期特定的止盈条件（priority=5或9）
        2. 止损条件（priority=10，最低优先级）

        🔧 TASK-021-006核心逻辑：动态Exit选择
        🔧 Bug-025修复：止损优先级最低，确保先检查止盈

        Args:
            order: 持仓订单
            kline: K线数据（必须包含'high', 'low', 'close'）
            indicators: 技术指标字典（必须包含'cycle_phase'）
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
            selected_exit = self.p95_exit
            cycle_phase = 'unknown'
        else:
            cycle_phase = indicators['cycle_phase']

            # 根据cycle_phase选择Exit Condition
            if cycle_phase == 'consolidation':
                # 震荡期：P95止盈
                selected_exit = self.p95_exit
                logger.debug(f"订单 {order.id}: 震荡期，使用P95止盈")

            elif cycle_phase in ('bear_warning', 'bear_strong'):
                # 下跌期：EMA25回归
                selected_exit = self.ema_exit
                logger.debug(f"订单 {order.id}: 下跌期（{cycle_phase}），使用EMA25回归")

            elif cycle_phase in ('bull_warning', 'bull_strong'):
                # 上涨期：Mid止盈
                selected_exit = self.mid_exit
                logger.debug(f"订单 {order.id}: 上涨期（{cycle_phase}），使用Mid止盈")

            else:
                # 未知周期：降级使用P95止盈（保守策略）
                logger.warning(
                    f"未知的cycle_phase: {cycle_phase}。"
                    f"降级处理：使用P95止盈"
                )
                selected_exit = self.p95_exit

        # 1. 检查周期特定的止盈条件（优先级高）
        take_profit_signal = selected_exit.check(order, kline, indicators, current_timestamp)
        if take_profit_signal:
            logger.info(
                f"订单 {order.id} 触发止盈: "
                f"cycle_phase={cycle_phase}, "
                f"exit_type={take_profit_signal.exit_type}, "
                f"price={take_profit_signal.price}, "
                f"reason={take_profit_signal.reason}"
            )
            return take_profit_signal

        # 2. 检查止损条件（优先级最低）
        stop_loss_signal = self.stop_loss_exit.check(order, kline, indicators, current_timestamp)
        if stop_loss_signal:
            logger.info(
                f"订单 {order.id} 触发止损: "
                f"cycle_phase={cycle_phase}, "
                f"price={stop_loss_signal.price}, "
                f"reason={stop_loss_signal.reason}"
            )
            return stop_loss_signal

        # 无Exit触发
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
