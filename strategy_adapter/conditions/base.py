"""
原子条件基础接口和数据结构

本模块定义：
- ICondition: 统一的原子条件接口
- ConditionContext: 条件评估上下文
- ConditionResult: 条件评估结果
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import math

if TYPE_CHECKING:
    from strategy_adapter.models import Order


@dataclass
class ConditionResult:
    """条件评估结果

    Attributes:
        triggered: 条件是否触发
        price: 触发价格（可选）
        reason: 触发原因描述
        condition_name: 触发的条件名称
        metadata: 额外元数据
    """
    triggered: bool
    price: Optional[Decimal] = None
    reason: Optional[str] = None
    condition_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def not_triggered(cls) -> 'ConditionResult':
        """创建未触发的结果"""
        return cls(triggered=False)

    @classmethod
    def triggered_with(
        cls,
        price: Optional[Decimal] = None,
        reason: Optional[str] = None,
        condition_name: Optional[str] = None,
        **metadata: Any
    ) -> 'ConditionResult':
        """创建触发的结果"""
        return cls(
            triggered=True,
            price=price,
            reason=reason,
            condition_name=condition_name,
            metadata=metadata
        )


@dataclass
class ConditionContext:
    """条件评估上下文

    封装条件评估所需的全部数据，包括K线、指标、时间戳和订单信息。

    Attributes:
        kline: K线数据字典，包含 open, high, low, close, volume, open_time 等
        indicators: 指标数据字典，如 ema25, p5, p95, beta, cycle_phase 等
        timestamp: 当前时间戳（毫秒）
        order: 持仓订单（出场条件评估时使用）
        metadata: 额外元数据
    """
    kline: Dict[str, Any]
    indicators: Dict[str, Any]
    timestamp: int = 0
    order: Optional['Order'] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_indicator(self, name: str, default: Any = None) -> Any:
        """安全获取指标值

        自动处理NaN值，返回default。

        Args:
            name: 指标名称
            default: 默认值

        Returns:
            指标值或默认值
        """
        value = self.indicators.get(name, default)
        if value is None:
            return default
        # 处理NaN
        if isinstance(value, float) and math.isnan(value):
            return default
        return value

    def get_kline_value(self, field_name: str) -> Optional[Decimal]:
        """获取K线字段值并转换为Decimal

        Args:
            field_name: 字段名称（open, high, low, close等）

        Returns:
            Decimal值或None
        """
        value = self.kline.get(field_name)
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    def get_kline_float(self, field_name: str) -> Optional[float]:
        """获取K线字段值作为float

        Args:
            field_name: 字段名称

        Returns:
            float值或None
        """
        value = self.kline.get(field_name)
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        return float(value)


class ICondition(ABC):
    """原子条件统一接口

    所有条件类必须实现此接口。支持通过运算符组合条件：
    - condition1 & condition2 -> AndCondition
    - condition1 | condition2 -> OrCondition
    - ~condition -> NotCondition
    """

    @abstractmethod
    def evaluate(self, ctx: ConditionContext) -> ConditionResult:
        """评估条件是否满足

        Args:
            ctx: 评估上下文

        Returns:
            评估结果
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """获取条件名称

        Returns:
            条件的唯一标识名称
        """
        pass

    def get_description(self) -> str:
        """获取条件描述

        Returns:
            条件的人类可读描述
        """
        return self.get_name()

    def get_required_indicators(self) -> List[str]:
        """获取条件所需的指标列表

        Returns:
            指标名称列表
        """
        return []

    def __and__(self, other: 'ICondition') -> 'ICondition':
        """与运算符重载: condition1 & condition2"""
        from .logic import AndCondition
        return AndCondition(self, other)

    def __or__(self, other: 'ICondition') -> 'ICondition':
        """或运算符重载: condition1 | condition2"""
        from .logic import OrCondition
        return OrCondition(self, other)

    def __invert__(self) -> 'ICondition':
        """取反运算符重载: ~condition"""
        from .logic import NotCondition
        return NotCondition(self)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.get_name()}>"
