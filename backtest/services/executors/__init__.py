"""
交易执行器模块 - 服务插件模式
支持多种交易执行策略的灵活切换
"""
from .base import BaseExecutor
from .simple_executor import SimpleExecutor
from .progressive_executor import ProgressiveExecutor

__all__ = [
    'BaseExecutor',
    'SimpleExecutor',
    'ProgressiveExecutor',
]


def create_executor(executor_type: str, **kwargs):
    """
    工厂函数：根据类型创建执行器实例

    Args:
        executor_type: 执行器类型 ('simple' / 'progressive')
        **kwargs: 执行器初始化参数

    Returns:
        BaseExecutor实例

    Example:
        executor = create_executor(
            executor_type='simple',
            position_manager=position_manager,
            fee_rate=0.001
        )
    """
    executors = {
        'simple': SimpleExecutor,
        'progressive': ProgressiveExecutor,
    }

    executor_class = executors.get(executor_type)
    if not executor_class:
        raise ValueError(
            f"未知的执行器类型: {executor_type}. "
            f"可用类型: {list(executors.keys())}"
        )

    return executor_class(**kwargs)
