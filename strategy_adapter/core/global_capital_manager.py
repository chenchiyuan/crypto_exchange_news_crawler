"""
全局资金池管理器

管理多交易对共享的资金池，支持资金冻结、解冻和结算操作。

核心功能：
- 维护全局可用资金 (available_cash)
- 支持资金冻结（挂单）和解冻（取消/成交）
- 跟踪冻结资金总额
- 记录资金变动历史

迭代编号: 045 (策略20-多交易对共享资金池)
创建日期: 2026-01-14
"""

import logging
from decimal import Decimal
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class CapitalTransaction:
    """资金变动记录"""
    timestamp: int
    type: str  # 'freeze', 'unfreeze', 'settle', 'profit'
    amount: Decimal
    symbol: Optional[str] = None
    order_id: Optional[str] = None
    description: str = ""


class GlobalCapitalManager:
    """
    全局资金池管理器

    管理多交易对共享的资金池，确保资金分配的正确性和一致性。

    核心公式：
        total_capital = available_cash + frozen_cash + holdings_value

    工作流程：
        1. 挂单时：freeze() 冻结资金
        2. 挂单取消：unfreeze() 解冻资金
        3. 挂单成交：settle() 结算冻结资金
        4. 卖出成交：add_profit() 增加收益

    Attributes:
        _total_capital: 初始总资金
        _available_cash: 当前可用资金
        _frozen_cash: 冻结资金（挂单占用）
        _transactions: 资金变动历史

    Example:
        >>> manager = GlobalCapitalManager(Decimal("10000"))
        >>> manager.freeze(Decimal("1000"))  # 挂单冻结1000
        True
        >>> manager.available_cash
        Decimal('9000')
        >>> manager.settle(Decimal("1000"), Decimal("1000"))  # 成交结算
        >>> manager.add_profit(Decimal("50"))  # 卖出盈利50
        >>> manager.available_cash
        Decimal('9050')
    """

    def __init__(self, initial_capital: Decimal):
        """
        初始化全局资金管理器

        Args:
            initial_capital: 初始资金
        """
        self._initial_capital = initial_capital
        self._total_capital = initial_capital
        self._available_cash = initial_capital
        self._frozen_cash = Decimal("0")
        self._transactions: List[CapitalTransaction] = []

        logger.info(f"初始化GlobalCapitalManager: initial_capital={initial_capital}")

    @property
    def initial_capital(self) -> Decimal:
        """初始资金"""
        return self._initial_capital

    @property
    def available_cash(self) -> Decimal:
        """当前可用资金"""
        return self._available_cash

    @property
    def frozen_cash(self) -> Decimal:
        """冻结资金"""
        return self._frozen_cash

    @property
    def total_capital(self) -> Decimal:
        """总资金（含冻结）"""
        return self._available_cash + self._frozen_cash

    def freeze(
        self,
        amount: Decimal,
        symbol: str = None,
        order_id: str = None,
        timestamp: int = 0
    ) -> bool:
        """
        冻结资金（创建挂单时调用）

        Args:
            amount: 冻结金额
            symbol: 交易对（可选）
            order_id: 订单ID（可选）
            timestamp: 时间戳（可选）

        Returns:
            bool: True表示冻结成功，False表示资金不足
        """
        if amount <= 0:
            logger.warning(f"冻结金额无效: amount={amount}")
            return False

        if amount > self._available_cash:
            logger.debug(
                f"资金不足无法冻结: amount={amount}, available={self._available_cash}"
            )
            return False

        self._available_cash -= amount
        self._frozen_cash += amount

        self._transactions.append(CapitalTransaction(
            timestamp=timestamp,
            type='freeze',
            amount=amount,
            symbol=symbol,
            order_id=order_id,
            description=f"冻结资金 {amount}"
        ))

        logger.debug(
            f"冻结资金: amount={amount}, symbol={symbol}, "
            f"available={self._available_cash}, frozen={self._frozen_cash}"
        )
        return True

    def unfreeze(
        self,
        amount: Decimal,
        symbol: str = None,
        order_id: str = None,
        timestamp: int = 0
    ):
        """
        解冻资金（取消挂单时调用）

        Args:
            amount: 解冻金额
            symbol: 交易对（可选）
            order_id: 订单ID（可选）
            timestamp: 时间戳（可选）
        """
        if amount <= 0:
            return

        # 确保不超过冻结金额
        actual_unfreeze = min(amount, self._frozen_cash)
        if actual_unfreeze <= 0:
            return

        self._frozen_cash -= actual_unfreeze
        self._available_cash += actual_unfreeze

        self._transactions.append(CapitalTransaction(
            timestamp=timestamp,
            type='unfreeze',
            amount=actual_unfreeze,
            symbol=symbol,
            order_id=order_id,
            description=f"解冻资金 {actual_unfreeze}"
        ))

        logger.debug(
            f"解冻资金: amount={actual_unfreeze}, symbol={symbol}, "
            f"available={self._available_cash}, frozen={self._frozen_cash}"
        )

    def settle(
        self,
        frozen_amount: Decimal,
        symbol: str = None,
        order_id: str = None,
        timestamp: int = 0
    ):
        """
        结算（买入挂单成交时调用）

        买入成交时，冻结资金转为持仓成本，从frozen_cash中扣除。

        Args:
            frozen_amount: 冻结金额（成交金额）
            symbol: 交易对（可选）
            order_id: 订单ID（可选）
            timestamp: 时间戳（可选）
        """
        if frozen_amount <= 0:
            return

        # 确保不超过冻结金额
        actual_settle = min(frozen_amount, self._frozen_cash)
        if actual_settle <= 0:
            return

        self._frozen_cash -= actual_settle

        self._transactions.append(CapitalTransaction(
            timestamp=timestamp,
            type='settle',
            amount=actual_settle,
            symbol=symbol,
            order_id=order_id,
            description=f"结算冻结资金 {actual_settle}"
        ))

        logger.debug(
            f"结算冻结资金: amount={actual_settle}, symbol={symbol}, "
            f"frozen={self._frozen_cash}"
        )

    def add_profit(
        self,
        profit: Decimal,
        symbol: str = None,
        order_id: str = None,
        timestamp: int = 0
    ):
        """
        增加收益（卖出成交时调用）

        卖出成交后，回收本金+利润到可用资金。

        Args:
            profit: 收益金额（本金+盈亏）
            symbol: 交易对（可选）
            order_id: 订单ID（可选）
            timestamp: 时间戳（可选）
        """
        self._available_cash += profit

        self._transactions.append(CapitalTransaction(
            timestamp=timestamp,
            type='profit',
            amount=profit,
            symbol=symbol,
            order_id=order_id,
            description=f"回收资金 {profit}"
        ))

        logger.debug(
            f"回收资金: amount={profit}, symbol={symbol}, "
            f"available={self._available_cash}"
        )

    def get_equity(self, holdings_value: Decimal = Decimal("0")) -> Decimal:
        """
        获取账户总权益

        Args:
            holdings_value: 持仓市值

        Returns:
            Decimal: 总权益 = 可用资金 + 冻结资金 + 持仓市值
        """
        return self._available_cash + self._frozen_cash + holdings_value

    def get_transactions(self) -> List[CapitalTransaction]:
        """获取资金变动历史"""
        return self._transactions.copy()

    def reset(self):
        """重置资金管理器（重新回测时调用）"""
        self._available_cash = self._initial_capital
        self._frozen_cash = Decimal("0")
        self._transactions.clear()
        logger.info(f"重置GlobalCapitalManager: initial_capital={self._initial_capital}")
