"""
卖出条件模块

Purpose:
    提供多种卖出条件实现及其工厂函数。

关联任务: TASK-017-004~008, TASK-017-012, TASK-021-006, TASK-022-003, TASK-027-005
关联功能点: FP-017-007~011, FP-021-006, FP-022-004, FP-027-012~015

Exports:
    - ExitSignal: 卖出信号数据类
    - IExitCondition: 卖出条件抽象基类
    - EmaReversionExit: EMA回归卖出
    - StopLossExit: 止损卖出
    - TakeProfitExit: 止盈卖出
    - P95TakeProfitExit: P95止盈卖出
    - P5TouchTakeProfitExit: P5触及止盈卖出（策略8专用）
    - ConsolidationMidTakeProfitExit: 震荡中值止盈卖出
    - DynamicExitSelector: 动态Exit选择器（策略7专用）
    - LimitOrderExit: 限价卖出（策略11专用）
    - ExitConditionCombiner: 条件组合器
    - create_exit_condition: 工厂函数
"""

from strategy_adapter.exits.base import ExitSignal, IExitCondition
from strategy_adapter.exits.ema_reversion import EmaReversionExit
from strategy_adapter.exits.stop_loss import StopLossExit
from strategy_adapter.exits.take_profit import TakeProfitExit
from strategy_adapter.exits.p95_take_profit import P95TakeProfitExit
from strategy_adapter.exits.p5_touch_take_profit import P5TouchTakeProfitExit
from strategy_adapter.exits.consolidation_mid_take_profit import ConsolidationMidTakeProfitExit
from strategy_adapter.exits.dynamic_exit_selector import DynamicExitSelector
from strategy_adapter.exits.limit_order_exit import LimitOrderExit
from strategy_adapter.exits.combiner import ExitConditionCombiner
from strategy_adapter.exits.ema_state_exit import EmaStateExit
from strategy_adapter.models.project_config import ExitConfig


def create_exit_condition(config: ExitConfig) -> IExitCondition:
    """
    根据配置创建卖出条件实例

    Factory function，根据ExitConfig创建对应的卖出条件对象。

    Args:
        config: 卖出条件配置

    Returns:
        IExitCondition: 卖出条件实例

    Raises:
        ValueError: 未知的条件类型

    Examples:
        >>> config = ExitConfig(type="stop_loss", params={"percentage": 5})
        >>> condition = create_exit_condition(config)
        >>> isinstance(condition, StopLossExit)
        True
    """
    exit_type = config.type
    params = config.params

    if exit_type == "ema_reversion":
        ema_period = params.get("ema_period", 25)
        return EmaReversionExit(ema_period=ema_period)

    elif exit_type == "stop_loss":
        percentage = params.get("percentage", 5.0)
        return StopLossExit(percentage=percentage)

    elif exit_type == "take_profit":
        percentage = params.get("percentage", 10.0)
        return TakeProfitExit(percentage=percentage)

    elif exit_type == "p95_take_profit":
        return P95TakeProfitExit()

    elif exit_type == "p5_touch_take_profit":
        return P5TouchTakeProfitExit()

    elif exit_type == "consolidation_mid_take_profit":
        return ConsolidationMidTakeProfitExit()

    elif exit_type == "dynamic_exit_selector":
        stop_loss_percentage = params.get("stop_loss_percentage", 5.0)
        return DynamicExitSelector(stop_loss_percentage=stop_loss_percentage)

    elif exit_type == "limit_order_exit":
        take_profit_rate = params.get("take_profit_rate", 0.05)
        ema_period = params.get("ema_period", 25)
        return LimitOrderExit(take_profit_rate=take_profit_rate, ema_period=ema_period)

    elif exit_type == "ema_state":
        return EmaStateExit()

    else:
        raise ValueError(f"未知的卖出条件类型: {exit_type}")


__all__ = [
    'ExitSignal',
    'IExitCondition',
    'EmaReversionExit',
    'StopLossExit',
    'TakeProfitExit',
    'P95TakeProfitExit',
    'P5TouchTakeProfitExit',
    'ConsolidationMidTakeProfitExit',
    'DynamicExitSelector',
    'LimitOrderExit',
    'EmaStateExit',
    'ExitConditionCombiner',
    'create_exit_condition',
]
