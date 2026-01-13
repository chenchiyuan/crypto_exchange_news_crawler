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
from decimal import Decimal
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
    def create(
        cls,
        config: StrategyConfig,
        position_size: Decimal = None
    ) -> IStrategy:
        """
        根据配置创建策略实例

        Args:
            config: 策略配置
            position_size: 单笔仓位金额（可选，来自capital_management）

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

            # 策略11: 限价挂单策略 - 使用LimitOrderStrategy
            if strategy_id == 11 or enabled_strategies == [11]:
                from strategy_adapter.strategies import LimitOrderStrategy
                order_count = config.entry.get("order_count", 10)
                order_interval = config.entry.get("order_interval", 0.005)
                first_order_discount = config.entry.get("first_order_discount", 0.01)

                # position_size 优先使用传入参数（来自capital_management）
                # 如果未传入，则从entry配置读取，最后使用默认值100
                if position_size is None:
                    position_size = config.entry.get("position_size", Decimal("100"))

                # 从exits中获取限价卖出参数
                take_profit_rate = 0.05
                ema_period = 25
                for exit_config in config.exits:
                    if exit_config.type == 'limit_order_exit':
                        take_profit_rate = exit_config.params.get('take_profit_rate', 0.05)
                        ema_period = exit_config.params.get('ema_period', 25)
                        break

                strategy = LimitOrderStrategy(
                    position_size=Decimal(str(position_size)),
                    order_count=order_count,
                    order_interval=order_interval,
                    take_profit_rate=take_profit_rate,
                    ema_period=ema_period,
                    first_order_discount=first_order_discount
                )
                logger.info(
                    f"创建策略11 LimitOrderStrategy: "
                    f"position_size={position_size}, order_count={order_count}, "
                    f"order_interval={order_interval}, first_order_discount={first_order_discount}"
                )
                return strategy

            # 策略12: 倍增仓位限价挂单策略 - 使用DoublingPositionStrategy
            if strategy_id == 12 or enabled_strategies == [12]:
                from strategy_adapter.strategies import DoublingPositionStrategy
                order_count = config.entry.get("order_count", 5)
                order_interval = config.entry.get("order_interval", 0.01)
                first_order_discount = config.entry.get("first_order_discount", 0.01)
                base_amount = Decimal(str(config.entry.get("base_amount", 100)))
                multiplier = float(config.entry.get("multiplier", 2.0))
                take_profit_rate = float(config.entry.get("take_profit_rate", 0.02))
                stop_loss_rate = float(config.entry.get("stop_loss_rate", 0.10))

                strategy = DoublingPositionStrategy(
                    base_amount=base_amount,
                    multiplier=multiplier,
                    order_count=order_count,
                    order_interval=order_interval,
                    first_order_discount=first_order_discount,
                    take_profit_rate=take_profit_rate,
                    stop_loss_rate=stop_loss_rate
                )
                logger.info(
                    f"创建策略12 DoublingPositionStrategy: "
                    f"base_amount={base_amount}, multiplier={multiplier}, "
                    f"order_count={order_count}, take_profit_rate={take_profit_rate}, "
                    f"stop_loss_rate={stop_loss_rate}"
                )
                return strategy

            # 策略13: 分批止盈策略 - 使用SplitTakeProfitStrategy
            if strategy_id == 13 or enabled_strategies == [13]:
                from strategy_adapter.strategies import SplitTakeProfitStrategy
                order_count = config.entry.get("order_count", 5)
                order_interval = config.entry.get("order_interval", 0.01)
                first_order_discount = config.entry.get("first_order_discount", 0.01)
                base_amount = Decimal(str(config.entry.get("base_amount", 100)))
                multiplier = float(config.entry.get("multiplier", 2.0))
                stop_loss_rate = float(config.entry.get("stop_loss_rate", 0.03))
                take_profit_count = int(config.entry.get("take_profit_count", 5))
                first_take_profit_rate = float(config.entry.get("first_take_profit_rate", 0.02))
                take_profit_interval = float(config.entry.get("take_profit_interval", 0.01))

                strategy = SplitTakeProfitStrategy(
                    base_amount=base_amount,
                    multiplier=multiplier,
                    order_count=order_count,
                    order_interval=order_interval,
                    first_order_discount=first_order_discount,
                    stop_loss_rate=stop_loss_rate,
                    take_profit_count=take_profit_count,
                    first_take_profit_rate=first_take_profit_rate,
                    take_profit_interval=take_profit_interval
                )
                logger.info(
                    f"创建策略13 SplitTakeProfitStrategy: "
                    f"base_amount={base_amount}, multiplier={multiplier}, "
                    f"order_count={order_count}, stop_loss_rate={stop_loss_rate}, "
                    f"take_profit_count={take_profit_count}, first_take_profit_rate={first_take_profit_rate}"
                )
                return strategy

            # 策略14: 优化买入策略 - 使用OptimizedEntryStrategy
            if strategy_id == 14 or enabled_strategies == [14]:
                from strategy_adapter.strategies import OptimizedEntryStrategy
                order_count = config.entry.get("order_count", 5)
                first_gap = float(config.entry.get("first_gap", 0.04))
                interval = float(config.entry.get("interval", 0.01))
                first_order_discount = config.entry.get("first_order_discount", 0.003)
                base_amount = Decimal(str(config.entry.get("base_amount", 100)))
                multiplier = float(config.entry.get("multiplier", 3.0))
                take_profit_rate = float(config.entry.get("take_profit_rate", 0.02))
                stop_loss_rate = float(config.entry.get("stop_loss_rate", 0.06))

                strategy = OptimizedEntryStrategy(
                    base_amount=base_amount,
                    multiplier=multiplier,
                    order_count=order_count,
                    first_gap=first_gap,
                    interval=interval,
                    first_order_discount=first_order_discount,
                    take_profit_rate=take_profit_rate,
                    stop_loss_rate=stop_loss_rate
                )
                logger.info(
                    f"创建策略14 OptimizedEntryStrategy: "
                    f"base_amount={base_amount}, multiplier={multiplier}, "
                    f"order_count={order_count}, first_gap={first_gap}, interval={interval}, "
                    f"take_profit_rate={take_profit_rate}, stop_loss_rate={stop_loss_rate}"
                )
                return strategy

            # 策略15: 分批止盈优化策略 - 使用SplitTakeProfitStrategy (策略15版本)
            if strategy_id == 15 or enabled_strategies == [15]:
                from strategy_adapter.strategies.split_take_profit_strategy import SplitTakeProfitStrategy
                order_count = config.entry.get("order_count", 5)
                first_gap = float(config.entry.get("first_gap", 0.04))
                interval = float(config.entry.get("interval", 0.01))
                first_order_discount = config.entry.get("first_order_discount", 0.003)
                base_amount = Decimal(str(config.entry.get("base_amount", 100)))
                multiplier = float(config.entry.get("multiplier", 3.0))
                stop_loss_rate = float(config.entry.get("stop_loss_rate", 0.03))
                tp_levels = int(config.entry.get("tp_levels", 5))
                first_tp_rate = float(config.entry.get("first_tp_rate", 0.02))
                tp_interval = float(config.entry.get("tp_interval", 0.01))

                strategy = SplitTakeProfitStrategy(
                    base_amount=base_amount,
                    multiplier=multiplier,
                    order_count=order_count,
                    first_gap=first_gap,
                    interval=interval,
                    first_order_discount=first_order_discount,
                    stop_loss_rate=stop_loss_rate,
                    tp_levels=tp_levels,
                    first_tp_rate=first_tp_rate,
                    tp_interval=tp_interval
                )
                logger.info(
                    f"创建策略15 SplitTakeProfitStrategy: "
                    f"base_amount={base_amount}, multiplier={multiplier}, "
                    f"order_count={order_count}, first_gap={first_gap}, interval={interval}, "
                    f"stop_loss_rate={stop_loss_rate}, tp_levels={tp_levels}, "
                    f"first_tp_rate={first_tp_rate}, tp_interval={tp_interval}"
                )
                return strategy

            strategy = strategy_class(enabled_strategies=enabled_strategies)
        elif strategy_type == "empirical-cdf":
            # 滚动经验CDF策略 (迭代034)
            from strategy_adapter.strategies import EmpiricalCDFStrategy
            q_in = float(config.entry.get("q_in", 5.0))
            q_out = float(config.entry.get("q_out", 50.0))
            max_holding_bars = int(config.entry.get("max_holding_bars", 48))
            stop_loss_threshold = float(config.entry.get("stop_loss_threshold", 0.05))
            delta_in = float(config.entry.get("delta_in", 0.001))
            delta_out = float(config.entry.get("delta_out", 0.0))
            delta_out_fast = float(config.entry.get("delta_out_fast", 0.001))
            ema_period = int(config.entry.get("ema_period", 25))
            ewma_period = int(config.entry.get("ewma_period", 50))
            cdf_window = int(config.entry.get("cdf_window", 100))

            # position_size 优先使用传入参数（来自capital_management）
            if position_size is None:
                position_size = Decimal(str(config.entry.get("position_size", 100)))

            strategy = EmpiricalCDFStrategy(
                q_in=q_in,
                q_out=q_out,
                max_holding_bars=max_holding_bars,
                stop_loss_threshold=stop_loss_threshold,
                position_size=position_size,
                delta_in=delta_in,
                delta_out=delta_out,
                delta_out_fast=delta_out_fast,
                ema_period=ema_period,
                ewma_period=ewma_period,
                cdf_window=cdf_window
            )
            logger.info(
                f"创建EmpiricalCDFStrategy: "
                f"q_in={q_in}, q_out={q_out}, max_holding_bars={max_holding_bars}, "
                f"stop_loss={stop_loss_threshold}, position_size={position_size}, "
                f"cdf_window={cdf_window}"
            )
            return strategy

        elif strategy_type == "empirical-cdf-v01":
            # Empirical CDF V01 策略 (迭代035) - EMA状态止盈止损
            from strategy_adapter.strategies import EmpiricalCDFV01Strategy
            from strategy_adapter.exits import create_exit_condition

            q_in = float(config.entry.get("q_in", 5.0))
            max_holding_bars = int(config.entry.get("max_holding_bars", 48))
            stop_loss_threshold = float(config.entry.get("stop_loss_threshold", 0.10))
            delta_in = float(config.entry.get("delta_in", 0.001))
            delta_out = float(config.entry.get("delta_out", 0.0))
            delta_out_fast = float(config.entry.get("delta_out_fast", 0.001))
            ema_period = int(config.entry.get("ema_period", 25))
            ewma_period = int(config.entry.get("ewma_period", 50))
            cdf_window = int(config.entry.get("cdf_window", 100))

            # position_size 优先使用传入参数（来自capital_management）
            if position_size is None:
                position_size = Decimal(str(config.entry.get("position_size", 100)))

            # 创建Exit条件列表
            exits = []
            for exit_config in config.exits:
                condition = create_exit_condition(exit_config)
                exits.append(condition)

            strategy = EmpiricalCDFV01Strategy(
                q_in=q_in,
                max_holding_bars=max_holding_bars,
                stop_loss_threshold=stop_loss_threshold,
                position_size=position_size,
                delta_in=delta_in,
                delta_out=delta_out,
                delta_out_fast=delta_out_fast,
                ema_period=ema_period,
                ewma_period=ewma_period,
                cdf_window=cdf_window,
                exits=exits
            )
            logger.info(
                f"创建EmpiricalCDFV01Strategy: "
                f"q_in={q_in}, max_holding_bars={max_holding_bars}, "
                f"stop_loss={stop_loss_threshold}, position_size={position_size}, "
                f"cdf_window={cdf_window}, exits_count={len(exits)}"
            )
            return strategy
        elif strategy_type == "strategy-16-limit-entry":
            # 策略16: P5限价挂单入场 + 策略7动态止盈
            from strategy_adapter.strategies import Strategy16LimitEntry

            discount = float(config.entry.get("discount", 0.001))

            # position_size 优先使用传入参数（来自capital_management）
            if position_size is None:
                position_size = Decimal(str(config.entry.get("position_size", 1000)))

            max_positions = int(config.entry.get("max_positions", 10))

            strategy = Strategy16LimitEntry(
                position_size=position_size,
                discount=discount,
                max_positions=max_positions
            )
            logger.info(
                f"创建Strategy16LimitEntry: "
                f"position_size={position_size}, discount={discount}, "
                f"max_positions={max_positions}, 止盈=策略7动态止盈, 止损=无"
            )
            return strategy
        elif strategy_type == "strategy-19-conservative-entry":
            # 策略19: 保守入场策略 (迭代041, 043动态仓位管理)
            from strategy_adapter.strategies import Strategy19ConservativeEntry
            from strategy_adapter.core.position_manager import DynamicPositionManager

            discount = float(config.entry.get("discount", 0.001))
            consolidation_multiplier = int(config.entry.get("consolidation_multiplier", 1))
            max_positions = int(config.entry.get("max_positions", 10))

            # 创建动态仓位管理器（可选配置min_position）
            min_position = Decimal(str(config.entry.get("min_position", 0)))
            position_manager = DynamicPositionManager(min_position=min_position)

            strategy = Strategy19ConservativeEntry(
                position_manager=position_manager,
                discount=discount,
                max_positions=max_positions,
                consolidation_multiplier=consolidation_multiplier
            )
            logger.info(
                f"创建Strategy19ConservativeEntry: "
                f"position_manager=DynamicPositionManager(min_position={min_position}), "
                f"discount={discount}, max_positions={max_positions}, "
                f"consolidation_multiplier={consolidation_multiplier}"
            )
            return strategy
        elif strategy_type == "strategy-17-bull-warning":
            # 策略17: 上涨预警入场 (迭代038)
            from strategy_adapter.strategies import Strategy17BullWarningEntry

            stop_loss_pct = 5.0  # 默认5%止损
            # 从exits中获取止损参数
            for exit_config in config.exits:
                if exit_config.type == 'stop_loss':
                    stop_loss_pct = exit_config.params.get('percentage', 5.0)
                    break

            # position_size 优先使用传入参数（来自capital_management）
            if position_size is None:
                position_size = Decimal(str(config.entry.get("position_size", 1000)))

            max_positions = int(config.entry.get("max_positions", 10))

            strategy = Strategy17BullWarningEntry(
                position_size=position_size,
                stop_loss_pct=stop_loss_pct,
                max_positions=max_positions
            )
            logger.info(
                f"创建Strategy17BullWarningEntry: "
                f"position_size={position_size}, stop_loss_pct={stop_loss_pct}, "
                f"max_positions={max_positions}"
            )
            return strategy
        elif strategy_type == "strategy-18-cycle-trend":
            # 策略18: 周期趋势入场 (迭代039)
            from strategy_adapter.strategies import Strategy18CycleTrendEntry

            # 从exits中获取止盈止损参数
            take_profit_pct = 10.0  # 默认10%止盈
            stop_loss_pct = 3.0  # 默认3%止损
            for exit_config in config.exits:
                if exit_config.type == 'take_profit':
                    take_profit_pct = exit_config.params.get('percentage', 10.0)
                elif exit_config.type == 'stop_loss':
                    stop_loss_pct = exit_config.params.get('percentage', 3.0)

            # position_size 优先使用传入参数（来自capital_management）
            if position_size is None:
                position_size = Decimal(str(config.entry.get("position_size", 1000)))

            max_positions = int(config.entry.get("max_positions", 10))
            cycle_window = int(config.entry.get("cycle_window", 42))
            bull_threshold = float(config.entry.get("bull_threshold", 24.0))
            bear_threshold = float(config.entry.get("bear_threshold", 24.0))
            slope_window = int(config.entry.get("slope_window", 2))

            strategy = Strategy18CycleTrendEntry(
                position_size=position_size,
                max_positions=max_positions,
                cycle_window=cycle_window,
                bull_threshold=bull_threshold,
                bear_threshold=bear_threshold,
                slope_window=slope_window,
                take_profit_pct=take_profit_pct,
                stop_loss_pct=stop_loss_pct
            )
            logger.info(
                f"创建Strategy18CycleTrendEntry: "
                f"position_size={position_size}, max_positions={max_positions}, "
                f"cycle_window={cycle_window}, bull_threshold={bull_threshold}, "
                f"take_profit_pct={take_profit_pct}, stop_loss_pct={stop_loss_pct}"
            )
            return strategy
        elif strategy_type == "bull-cycle-ema-pullback":
            # 策略5: 强势上涨周期EMA回调
            stop_loss_pct = 5.0  # 默认5%止损
            # 从exits中获取止损参数
            for exit_config in config.exits:
                # exit_config是ExitConfig对象，使用属性访问
                if exit_config.type == 'stop_loss':
                    stop_loss_pct = exit_config.params.get('percentage', 5.0)
                    break
            target_phase = config.entry.get('cycle_phase', 'bull_strong')
            strategy = strategy_class(
                stop_loss_pct=stop_loss_pct,
                target_cycle_phase=target_phase
            )
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

    # 注册策略5: 强势上涨周期EMA回调
    try:
        from strategy_adapter.adapters.bull_cycle_ema_pullback import (
            BullCycleEMAPullbackStrategy
        )
        StrategyFactory.register("bull-cycle-ema-pullback", BullCycleEMAPullbackStrategy)
    except ImportError as e:
        logger.warning(f"无法注册策略5: {e}")

    # 注册滚动经验CDF策略 (迭代034)
    try:
        from strategy_adapter.strategies import EmpiricalCDFStrategy
        StrategyFactory.register("empirical-cdf", EmpiricalCDFStrategy)
    except ImportError as e:
        logger.warning(f"无法注册EmpiricalCDF策略: {e}")

    # 注册Empirical CDF V01策略 (迭代035)
    try:
        from strategy_adapter.strategies import EmpiricalCDFV01Strategy
        StrategyFactory.register("empirical-cdf-v01", EmpiricalCDFV01Strategy)
    except ImportError as e:
        logger.warning(f"无法注册EmpiricalCDFV01策略: {e}")

    # 注册策略16: P5限价挂单入场 (Bug-Fix)
    try:
        from strategy_adapter.strategies import Strategy16LimitEntry
        StrategyFactory.register("strategy-16-limit-entry", Strategy16LimitEntry)
    except ImportError as e:
        logger.warning(f"无法注册策略16: {e}")

    # 注册策略17: 上涨预警入场 (迭代038)
    try:
        from strategy_adapter.strategies import Strategy17BullWarningEntry
        StrategyFactory.register("strategy-17-bull-warning", Strategy17BullWarningEntry)
    except ImportError as e:
        logger.warning(f"无法注册策略17: {e}")

    # 注册策略18: 周期趋势入场 (迭代039)
    try:
        from strategy_adapter.strategies import Strategy18CycleTrendEntry
        StrategyFactory.register("strategy-18-cycle-trend", Strategy18CycleTrendEntry)
    except ImportError as e:
        logger.warning(f"无法注册策略18: {e}")

    # 注册策略19: 保守入场策略 (迭代041)
    try:
        from strategy_adapter.strategies import Strategy19ConservativeEntry
        StrategyFactory.register("strategy-19-conservative-entry", Strategy19ConservativeEntry)
    except ImportError as e:
        logger.warning(f"无法注册策略19: {e}")


# 模块加载时自动注册
_auto_register_strategies()
