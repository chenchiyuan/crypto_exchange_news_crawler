"""
共享资金池管理器

Purpose:
    管理多策略共享的资金池，控制资金分配和回收。

关联任务: TASK-017-010
关联功能点: FP-017-016, FP-017-017

Classes:
    - SharedCapitalManager: 共享资金池管理器
"""

import logging
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)


class SharedCapitalManager:
    """
    共享资金池管理器

    管理多策略之间共享的资金池，实现"先到先得"的资金分配策略。
    同时控制最大持仓数限制。

    Features:
        - 资金扣减和回收
        - 最大持仓数限制
        - 资金守恒检查

    Usage:
        manager = SharedCapitalManager(
            initial_cash=Decimal("10000"),
            max_positions=10,
            position_size=Decimal("100")
        )
        if manager.can_allocate(Decimal("100")):
            manager.allocate(Decimal("100"))
    """

    def __init__(
        self,
        initial_cash: Decimal,
        max_positions: int = 10,
        position_size: Decimal = Decimal("100")
    ):
        """
        初始化资金管理器

        Args:
            initial_cash: 初始资金
            max_positions: 最大持仓数
            position_size: 单笔仓位金额
        """
        self._initial_cash = initial_cash
        self._available_cash = initial_cash
        self._max_positions = max_positions
        self._position_size = position_size
        self._open_position_count = 0
        self._total_allocated = Decimal("0")
        self._total_released = Decimal("0")

        logger.info(
            f"初始化资金管理器: 初始资金={initial_cash}, "
            f"最大持仓={max_positions}, 单笔仓位={position_size}"
        )

    def can_allocate(self, amount: Optional[Decimal] = None) -> bool:
        """
        检查是否可以分配资金

        Args:
            amount: 请求分配的金额，默认使用position_size

        Returns:
            bool: 是否可以分配
        """
        if amount is None:
            amount = self._position_size

        # 检查持仓数限制
        if self._open_position_count >= self._max_positions:
            logger.debug(
                f"持仓已满: {self._open_position_count}/{self._max_positions}"
            )
            return False

        # 检查资金是否充足
        if self._available_cash < amount:
            logger.debug(
                f"资金不足: 可用={self._available_cash}, 需要={amount}"
            )
            return False

        return True

    def allocate(self, amount: Optional[Decimal] = None) -> Decimal:
        """
        分配资金（开仓）

        Args:
            amount: 分配金额，默认使用position_size

        Returns:
            Decimal: 实际分配的金额

        Raises:
            ValueError: 资金不足或持仓已满
        """
        if amount is None:
            amount = self._position_size

        if not self.can_allocate(amount):
            raise ValueError(
                f"无法分配资金: 可用={self._available_cash}, "
                f"需要={amount}, 持仓={self._open_position_count}/{self._max_positions}"
            )

        self._available_cash -= amount
        self._open_position_count += 1
        self._total_allocated += amount

        logger.debug(
            f"分配资金: {amount}, 剩余可用: {self._available_cash}, "
            f"持仓数: {self._open_position_count}"
        )

        return amount

    def release(self, amount: Decimal, pnl: Decimal = Decimal("0")):
        """
        释放资金（平仓）

        Args:
            amount: 释放的本金
            pnl: 盈亏金额（正为盈利，负为亏损）
        """
        total_return = amount + pnl
        self._available_cash += total_return
        self._open_position_count -= 1
        self._total_released += total_return

        logger.debug(
            f"释放资金: 本金={amount}, 盈亏={pnl}, "
            f"总回收={total_return}, 可用: {self._available_cash}, "
            f"持仓数: {self._open_position_count}"
        )

    def get_available(self) -> Decimal:
        """获取可用资金"""
        return self._available_cash

    def get_open_position_count(self) -> int:
        """获取当前持仓数"""
        return self._open_position_count

    def get_max_positions(self) -> int:
        """获取最大持仓数限制"""
        return self._max_positions

    def get_position_size(self) -> Decimal:
        """获取单笔仓位金额"""
        return self._position_size

    def get_initial_cash(self) -> Decimal:
        """获取初始资金"""
        return self._initial_cash

    def get_statistics(self) -> dict:
        """
        获取资金统计信息

        Returns:
            dict: 统计信息字典
        """
        return {
            'initial_cash': self._initial_cash,
            'available_cash': self._available_cash,
            'total_allocated': self._total_allocated,
            'total_released': self._total_released,
            'open_positions': self._open_position_count,
            'max_positions': self._max_positions,
            'position_size': self._position_size,
        }

    def reset(self):
        """重置资金管理器状态"""
        self._available_cash = self._initial_cash
        self._open_position_count = 0
        self._total_allocated = Decimal("0")
        self._total_released = Decimal("0")
        logger.info("资金管理器已重置")
