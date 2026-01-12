"""
基于条件的信号计算器

包含：
- ConditionBasedSignalCalculator: 基于策略定义生成交易信号
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

import numpy as np

from strategy_adapter.conditions.base import ConditionContext
from strategy_adapter.definitions.base import StrategyDefinition
from strategy_adapter.definitions.registry import StrategyRegistry


class ConditionBasedSignalCalculator:
    """基于条件的信号计算器

    根据注册的策略定义，遍历K线数据并生成交易信号。

    Attributes:
        registry: 策略注册表（默认使用全局注册表）

    Examples:
        >>> calculator = ConditionBasedSignalCalculator()
        >>> result = calculator.calculate(
        ...     klines=klines,
        ...     indicators={'ema25': ema_arr, 'p5': p5_arr, 'beta': beta_arr},
        ...     enabled_strategies=['strategy_1', 'strategy_2']
        ... )
        >>> long_signals = result['long_signals']
        >>> short_signals = result['short_signals']
    """

    def __init__(self, registry: Optional[StrategyRegistry] = None):
        self.registry = registry or StrategyRegistry

    def calculate(
        self,
        klines: List[Dict[str, Any]],
        indicators: Dict[str, np.ndarray],
        enabled_strategies: Optional[List[str]] = None
    ) -> Dict[str, List[Dict]]:
        """计算交易信号

        Args:
            klines: K线数据列表，每项包含 open, high, low, close, volume, open_time
            indicators: 指标数据字典，键为指标名，值为np.ndarray
            enabled_strategies: 启用的策略ID列表，为None时使用所有注册策略

        Returns:
            包含 'long_signals' 和 'short_signals' 的字典
        """
        strategies = self._get_strategies(enabled_strategies)
        long_signals: List[Dict] = []
        short_signals: List[Dict] = []

        for i, kline in enumerate(klines):
            # 构建当前K线的指标字典
            current_indicators = self._extract_indicators(indicators, i)

            # 构建上下文
            ctx = ConditionContext(
                kline=kline,
                indicators=current_indicators,
                timestamp=kline.get('open_time', 0)
            )

            # 评估每个策略
            for strategy in strategies:
                result = strategy.entry_condition.evaluate(ctx)
                if result.triggered:
                    signal = self._create_signal(strategy, result, ctx, i)
                    if strategy.direction == 'long':
                        long_signals.append(signal)
                    else:
                        short_signals.append(signal)

        return {
            'long_signals': long_signals,
            'short_signals': short_signals
        }

    def _get_strategies(
        self,
        enabled_strategies: Optional[List[str]]
    ) -> List[StrategyDefinition]:
        """获取启用的策略列表"""
        if enabled_strategies is None:
            return self.registry.list_all()

        strategies = []
        for strategy_id in enabled_strategies:
            strategy = self.registry.get(strategy_id)
            if strategy:
                strategies.append(strategy)
        return strategies

    def _extract_indicators(
        self,
        indicators: Dict[str, np.ndarray],
        index: int
    ) -> Dict[str, Any]:
        """提取指定索引的指标值"""
        current = {}
        for name, arr in indicators.items():
            if isinstance(arr, np.ndarray) and index < len(arr):
                value = arr[index]
                # 处理numpy数值类型
                if isinstance(value, (np.floating, np.integer)):
                    value = float(value)
                current[name] = value
            else:
                current[name] = arr  # 非数组情况，直接使用
        return current

    def _create_signal(
        self,
        strategy: StrategyDefinition,
        result,  # ConditionResult
        ctx: ConditionContext,
        index: int
    ) -> Dict[str, Any]:
        """创建信号字典"""
        # 确定入场价格
        if result.price is not None:
            entry_price = result.price
        else:
            close = ctx.get_kline_value('close')
            entry_price = close if close else Decimal('0')

        return {
            'index': index,
            'timestamp': ctx.timestamp,
            'strategy_id': strategy.id,
            'strategy_name': strategy.name,
            'direction': strategy.direction,
            'entry_price': entry_price,
            'reason': result.reason,
            'condition_name': result.condition_name,
            'kline': ctx.kline,
            'metadata': result.metadata,
        }


def create_calculator() -> ConditionBasedSignalCalculator:
    """创建信号计算器的便捷函数"""
    return ConditionBasedSignalCalculator()
