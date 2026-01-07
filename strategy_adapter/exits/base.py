"""
卖出条件基类和数据结构

Purpose:
    定义卖出条件的抽象接口和信号数据结构。

关联任务: TASK-017-004
关联功能点: FP-017-007

Classes:
    - ExitSignal: 卖出信号数据类
    - IExitCondition: 卖出条件抽象基类
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from strategy_adapter.models.order import Order


@dataclass
class ExitSignal:
    """
    卖出信号

    当卖出条件满足时生成此信号。

    Attributes:
        timestamp: 触发时间戳（毫秒）
        price: 卖出价格
        reason: 触发原因描述
        exit_type: 条件类型标识 (ema_reversion, stop_loss, take_profit)
    """
    timestamp: int
    price: Decimal
    reason: str
    exit_type: str


class IExitCondition(ABC):
    """
    卖出条件抽象接口

    所有卖出条件类型都必须实现此接口。

    Usage:
        class MyExitCondition(IExitCondition):
            def check(self, order, kline, indicators, current_timestamp):
                # 检查逻辑
                return ExitSignal(...) if triggered else None

            def get_type(self) -> str:
                return "my_exit"
    """

    @abstractmethod
    def check(
        self,
        order: 'Order',
        kline: Dict[str, Any],
        indicators: Dict[str, Any],
        current_timestamp: int
    ) -> Optional[ExitSignal]:
        """
        检查是否满足卖出条件

        Args:
            order: 持仓订单对象
            kline: 当前K线数据，包含:
                - open: 开盘价 (Decimal)
                - high: 最高价 (Decimal)
                - low: 最低价 (Decimal)
                - close: 收盘价 (Decimal)
                - volume: 成交量 (Decimal)
            indicators: 技术指标字典，包含:
                - ema7: EMA7值 (Decimal)
                - ema25: EMA25值 (Decimal)
                - ema99: EMA99值 (Decimal)
            current_timestamp: 当前K线时间戳（毫秒）

        Returns:
            ExitSignal: 如果满足条件则返回卖出信号，否则返回None
        """
        pass

    @abstractmethod
    def get_type(self) -> str:
        """
        返回条件类型标识

        Returns:
            str: 类型标识，如 "ema_reversion", "stop_loss", "take_profit"
        """
        pass

    def get_priority(self) -> int:
        """
        返回条件优先级

        在同一K线内多个条件同时触发时，优先级高的先执行。
        数值越小优先级越高。

        Returns:
            int: 优先级数值（默认100）
        """
        return 100
