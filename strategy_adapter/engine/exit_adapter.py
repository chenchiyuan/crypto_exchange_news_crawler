"""
基于条件的Exit适配器

包含：
- ConditionBasedExit: 将ICondition适配为IExitCondition
"""

from decimal import Decimal
from typing import Any, Dict, Optional, TYPE_CHECKING

from strategy_adapter.conditions.base import ICondition, ConditionContext
from strategy_adapter.exits.base import ExitSignal, IExitCondition

if TYPE_CHECKING:
    from strategy_adapter.models.order import Order


class ConditionBasedExit(IExitCondition):
    """基于条件的Exit适配器

    将ICondition适配为IExitCondition接口，使其可与ExitConditionCombiner配合使用。

    Args:
        condition: 原子条件
        priority: 优先级（数值越小优先级越高）

    Examples:
        >>> # 创建基于EMA回归条件的Exit
        >>> exit_condition = ConditionBasedExit(
        ...     condition=PriceInRange('ema25'),
        ...     priority=30
        ... )
        >>>
        >>> # 与现有combiner配合使用
        >>> combiner = ExitConditionCombiner([exit_condition, stop_loss])
    """

    def __init__(self, condition: ICondition, priority: int = 50):
        self.condition = condition
        self._priority = priority

    def check(
        self,
        order: 'Order',
        kline: Dict[str, Any],
        indicators: Dict[str, Any],
        current_timestamp: int
    ) -> Optional[ExitSignal]:
        """检查是否满足卖出条件

        Args:
            order: 持仓订单对象
            kline: 当前K线数据
            indicators: 技术指标字典
            current_timestamp: 当前K线时间戳

        Returns:
            ExitSignal: 如果满足条件则返回卖出信号，否则返回None
        """
        # 构建条件上下文
        ctx = ConditionContext(
            kline=kline,
            indicators=indicators,
            timestamp=current_timestamp,
            order=order
        )

        # 评估条件
        result = self.condition.evaluate(ctx)

        if result.triggered:
            # 确定卖出价格
            if result.price is not None:
                price = result.price
            else:
                close = kline.get('close')
                if isinstance(close, Decimal):
                    price = close
                else:
                    price = Decimal(str(close)) if close else Decimal('0')

            return ExitSignal(
                timestamp=current_timestamp,
                price=price,
                reason=result.reason or self.condition.get_description(),
                exit_type=self.condition.get_name()
            )

        return None

    def get_type(self) -> str:
        """返回条件类型标识"""
        return self.condition.get_name()

    def get_priority(self) -> int:
        """返回条件优先级"""
        return self._priority
