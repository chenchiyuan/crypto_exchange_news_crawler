"""
卖出条件组合器

Purpose:
    组合多个卖出条件，根据K线内价格模拟返回最先触发的信号。

关联任务: TASK-017-008
关联功能点: FP-017-011

Classes:
    - ExitConditionCombiner: 卖出条件组合器
"""

import logging
from decimal import Decimal
from typing import List, Optional, Dict, Any

from strategy_adapter.exits.base import IExitCondition, ExitSignal

logger = logging.getLogger(__name__)


class ExitConditionCombiner:
    """
    卖出条件组合器

    组合多个卖出条件，在每根K线检查所有条件，
    根据K线内价格模拟和优先级返回最先触发的信号。

    K线内价格模拟假设：
    - 阳线（close > open）: O -> L -> H -> C
    - 阴线（close < open）: O -> H -> L -> C

    根据此假设，止损（在L触发）和止盈（在H触发）有明确顺序。

    Usage:
        combiner = ExitConditionCombiner()
        combiner.add_condition(StopLossExit(5))
        combiner.add_condition(TakeProfitExit(10))
        signal = combiner.check_all(order, kline, indicators, timestamp)
    """

    def __init__(self):
        self._conditions: List[IExitCondition] = []

    def add_condition(self, condition: IExitCondition) -> 'ExitConditionCombiner':
        """
        添加卖出条件

        Args:
            condition: 卖出条件实例

        Returns:
            self: 支持链式调用
        """
        self._conditions.append(condition)
        return self

    def check_all(
        self,
        order: 'Order',
        kline: Dict[str, Any],
        indicators: Dict[str, Any],
        current_timestamp: int
    ) -> Optional[ExitSignal]:
        """
        检查所有条件，返回最先触发的信号

        根据K线内价格模拟逻辑，确定多个条件触发时的优先级。

        Args:
            order: 持仓订单
            kline: K线数据
            indicators: 技术指标
            current_timestamp: 当前时间戳

        Returns:
            ExitSignal: 最先触发的信号，如果没有触发则返回None
        """
        if not self._conditions:
            return None

        # 收集所有触发的信号
        triggered_signals: List[ExitSignal] = []

        for condition in self._conditions:
            signal = condition.check(order, kline, indicators, current_timestamp)
            if signal:
                triggered_signals.append(signal)

        if not triggered_signals:
            return None

        if len(triggered_signals) == 1:
            return triggered_signals[0]

        # 多个信号触发时，根据K线内价格模拟确定顺序
        return self._determine_earliest_signal(triggered_signals, kline)

    def _determine_earliest_signal(
        self,
        signals: List[ExitSignal],
        kline: Dict[str, Any]
    ) -> ExitSignal:
        """
        根据K线内价格模拟确定最先触发的信号

        K线价格路径假设：
        - 阳线（close > open）: O -> L -> H -> C
          先到达low（止损可能触发），再到达high（止盈可能触发）
        - 阴线（close < open）: O -> H -> L -> C
          先到达high（止盈可能触发），再到达low（止损可能触发）

        Args:
            signals: 触发的信号列表
            kline: K线数据

        Returns:
            ExitSignal: 最先触发的信号
        """
        open_price = Decimal(str(kline['open']))
        close_price = Decimal(str(kline['close']))

        is_bullish = close_price > open_price  # 阳线

        # 根据K线类型定义价格到达顺序
        # 阳线: L -> H (止损先于止盈)
        # 阴线: H -> L (止盈先于止损)
        type_order = {
            'stop_loss': 1 if is_bullish else 2,  # 阳线先触发，阴线后触发
            'take_profit': 2 if is_bullish else 1,  # 阳线后触发，阴线先触发
            'ema_reversion': 3,  # EMA回归总是最后检查
        }

        # 按K线内触发顺序排序
        sorted_signals = sorted(
            signals,
            key=lambda s: type_order.get(s.exit_type, 99)
        )

        selected = sorted_signals[0]

        if len(signals) > 1:
            logger.debug(
                f"多条件触发: {[s.exit_type for s in signals]}, "
                f"K线类型: {'阳线' if is_bullish else '阴线'}, "
                f"选择: {selected.exit_type}"
            )

        return selected

    def get_conditions(self) -> List[IExitCondition]:
        """获取所有条件列表"""
        return self._conditions.copy()

    def clear(self):
        """清空所有条件"""
        self._conditions.clear()
