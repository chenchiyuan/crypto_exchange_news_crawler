"""
卖出条件模块

Purpose:
    提供多种卖出条件实现及其工厂函数。

关联任务: TASK-017-004~008, TASK-017-012
关联功能点: FP-017-007~011

Exports:
    - ExitSignal: 卖出信号数据类
    - IExitCondition: 卖出条件抽象基类
    - EmaReversionExit: EMA回归卖出
    - StopLossExit: 止损卖出
    - TakeProfitExit: 止盈卖出
    - ExitConditionCombiner: 条件组合器
    - create_exit_condition: 工厂函数
"""

from strategy_adapter.exits.base import ExitSignal, IExitCondition
from strategy_adapter.exits.ema_reversion import EmaReversionExit
from strategy_adapter.exits.stop_loss import StopLossExit
from strategy_adapter.exits.take_profit import TakeProfitExit
from strategy_adapter.exits.combiner import ExitConditionCombiner
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

    else:
        raise ValueError(f"未知的卖出条件类型: {exit_type}")


__all__ = [
    'ExitSignal',
    'IExitCondition',
    'EmaReversionExit',
    'StopLossExit',
    'TakeProfitExit',
    'ExitConditionCombiner',
    'create_exit_condition',
]
