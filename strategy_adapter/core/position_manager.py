"""
仓位管理器模块

提供可插拔的仓位计算策略，支持动态复利仓位管理。

核心组件：
- IPositionManager: 仓位管理器接口协议
- DynamicPositionManager: 动态复利仓位管理器实现

迭代编号: 043 (动态复利仓位管理)
创建日期: 2026-01-13
"""

import logging
from decimal import Decimal
from typing import Protocol

logger = logging.getLogger(__name__)


class IPositionManager(Protocol):
    """
    仓位管理器接口协议

    定义仓位计算的标准接口，支持不同的仓位管理策略实现。

    Example:
        >>> class CustomPositionManager:
        ...     def calculate_position_size(
        ...         self, available_cash, max_positions, current_positions
        ...     ) -> Decimal:
        ...         return available_cash / max_positions
    """

    def calculate_position_size(
        self,
        available_cash: Decimal,
        max_positions: int,
        current_positions: int
    ) -> Decimal:
        """
        计算单笔仓位金额

        Args:
            available_cash: 当前可用现金
            max_positions: 最大持仓数量
            current_positions: 当前持仓数量

        Returns:
            Decimal: 单笔仓位金额，0表示跳过挂单
        """
        ...


class DynamicPositionManager:
    """
    动态复利仓位管理器

    根据可用资金和剩余仓位槽位动态计算单笔仓位金额。

    核心公式:
        position_size = available_cash / (max_positions - current_positions)

    特性:
        - 复利效应：盈利后可用现金增加，单笔金额自动增大
        - 风控效应：亏损后可用现金减少，单笔金额自动减小

    Attributes:
        min_position: 最小仓位金额（可选），低于此值返回0跳过挂单

    Example:
        >>> pm = DynamicPositionManager()
        >>> pm.calculate_position_size(Decimal("10000"), 10, 0)
        Decimal('1000')
        >>> pm.calculate_position_size(Decimal("11000"), 10, 1)
        Decimal('1222.222222222222222222222222')
    """

    def __init__(self, min_position: Decimal = Decimal("0")):
        """
        初始化动态仓位管理器

        Args:
            min_position: 最小仓位金额（可选），低于此值跳过挂单，默认为0（不限制）
        """
        self.min_position = min_position
        logger.info(f"初始化DynamicPositionManager: min_position={min_position}")

    def calculate_position_size(
        self,
        available_cash: Decimal,
        max_positions: int,
        current_positions: int
    ) -> Decimal:
        """
        计算单笔仓位金额

        使用动态复利公式计算：available_cash / (max_positions - current_positions)

        Args:
            available_cash: 当前可用现金
            max_positions: 最大持仓数量
            current_positions: 当前持仓数量

        Returns:
            Decimal: 单笔仓位金额，以下情况返回0：
                - 可用现金 ≤ 0
                - 持仓已满（current_positions >= max_positions）
                - 计算结果低于最小金额限制
        """
        # 边界检查1: 可用现金不足
        if available_cash <= 0:
            logger.debug(
                f"可用现金不足，跳过挂单: available_cash={available_cash}"
            )
            return Decimal("0")

        # 边界检查2: 持仓已满
        available_slots = max_positions - current_positions
        if available_slots <= 0:
            logger.debug(
                f"持仓已满，跳过挂单: max_positions={max_positions}, "
                f"current_positions={current_positions}"
            )
            return Decimal("0")

        # 计算仓位金额
        position_size = available_cash / Decimal(str(available_slots))

        # 边界检查3: 低于最小金额限制
        if self.min_position > 0 and position_size < self.min_position:
            logger.debug(
                f"仓位金额低于最小限制，跳过挂单: position_size={position_size}, "
                f"min_position={self.min_position}"
            )
            return Decimal("0")

        logger.debug(
            f"计算仓位金额: available_cash={available_cash}, "
            f"available_slots={available_slots}, position_size={position_size}"
        )

        return position_size
