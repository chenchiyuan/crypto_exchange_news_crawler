"""
策略声明式定义数据结构

包含：
- StrategyDefinition: 策略的声明式定义
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from strategy_adapter.conditions.base import ICondition


@dataclass
class StrategyDefinition:
    """策略声明式定义

    将策略定义为原子条件的组合，支持声明式配置。

    Attributes:
        id: 策略唯一标识（如 'strategy_1', 'strategy_2'）
        name: 策略名称（人类可读）
        version: 版本号
        direction: 交易方向 ('long' 或 'short')
        entry_condition: 入场条件（ICondition，可组合）
        exit_conditions: 出场条件列表，每项为 (条件, 优先级) 元组
        position_calculator: 仓位计算函数（可选）
        metadata: 额外配置元数据

    Examples:
        >>> strategy_1 = StrategyDefinition(
        ...     id='strategy_1',
        ...     name='EMA斜率未来预测做多',
        ...     version='2.0',
        ...     direction='long',
        ...     entry_condition=(
        ...         PriceTouchesLevel('p5', 'below') &
        ...         FutureEmaPrediction(periods=6, above_close=True)
        ...     ),
        ...     exit_conditions=[
        ...         (PriceInRange('ema25'), 30),
        ...     ]
        ... )
    """

    id: str
    name: str
    direction: str
    entry_condition: 'ICondition'
    version: str = "1.0"
    exit_conditions: List[Tuple['ICondition', int]] = field(default_factory=list)
    position_calculator: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.direction not in ('long', 'short'):
            raise ValueError(f"direction must be 'long' or 'short', got '{self.direction}'")

    def get_required_indicators(self) -> List[str]:
        """获取策略所需的全部指标列表"""
        indicators = list(self.entry_condition.get_required_indicators())
        for condition, _ in self.exit_conditions:
            indicators.extend(condition.get_required_indicators())
        return list(set(indicators))

    def __repr__(self) -> str:
        return (
            f"StrategyDefinition(id='{self.id}', name='{self.name}', "
            f"direction='{self.direction}', version='{self.version}')"
        )
