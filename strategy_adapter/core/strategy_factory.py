"""
策略工厂

Purpose:
    根据配置动态创建策略实例。

关联任务: TASK-017-009
关联功能点: FP-017-012

Classes:
    - StrategyFactory: 策略工厂类
"""

import logging
from typing import Dict, Type, Optional

from strategy_adapter.interfaces.strategy import IStrategy
from strategy_adapter.models.project_config import StrategyConfig

logger = logging.getLogger(__name__)


class StrategyFactory:
    """
    策略工厂

    根据配置文件中的策略类型创建对应的策略实例。
    支持通过register方法注册新的策略类型。

    Usage:
        factory = StrategyFactory()
        strategy = factory.create(strategy_config)
    """

    # 类级别的策略注册表
    _registry: Dict[str, Type[IStrategy]] = {}

    @classmethod
    def register(cls, strategy_type: str, strategy_class: Type[IStrategy]):
        """
        注册策略类型

        Args:
            strategy_type: 策略类型标识（如 "ddps-z"）
            strategy_class: 策略类

        Examples:
            >>> StrategyFactory.register("ddps-z", DDPSZStrategy)
        """
        cls._registry[strategy_type] = strategy_class
        logger.debug(f"注册策略类型: {strategy_type} -> {strategy_class.__name__}")

    @classmethod
    def create(cls, config: StrategyConfig) -> IStrategy:
        """
        根据配置创建策略实例

        Args:
            config: 策略配置

        Returns:
            IStrategy: 策略实例

        Raises:
            ValueError: 未知的策略类型
        """
        strategy_type = config.type.lower()

        if strategy_type not in cls._registry:
            available = list(cls._registry.keys())
            raise ValueError(
                f"未知的策略类型: {strategy_type}，可用类型: {available}"
            )

        strategy_class = cls._registry[strategy_type]

        # 根据策略类型构造参数
        if strategy_type == "ddps-z":
            # DDPS-Z策略需要enabled_strategies参数（列表形式）
            strategy_id = config.entry.get("strategy_id", 1)
            # 支持单个ID或列表形式
            if isinstance(strategy_id, list):
                enabled_strategies = strategy_id
            else:
                enabled_strategies = [strategy_id]
            strategy = strategy_class(enabled_strategies=enabled_strategies)
        else:
            # 其他策略使用默认构造
            strategy = strategy_class()

        logger.info(
            f"创建策略: {config.id} ({config.name}), "
            f"类型: {strategy_type}, 入场参数: {config.entry}"
        )

        return strategy

    @classmethod
    def get_available_types(cls) -> list:
        """获取所有可用的策略类型"""
        return list(cls._registry.keys())

    @classmethod
    def is_registered(cls, strategy_type: str) -> bool:
        """检查策略类型是否已注册"""
        return strategy_type.lower() in cls._registry


def _auto_register_strategies():
    """
    自动注册内置策略

    在模块加载时自动注册所有内置策略类型。
    """
    try:
        from strategy_adapter.adapters.ddpsz_adapter import DDPSZStrategy
        StrategyFactory.register("ddps-z", DDPSZStrategy)
    except ImportError as e:
        logger.warning(f"无法注册DDPS-Z策略: {e}")


# 模块加载时自动注册
_auto_register_strategies()
