"""
全局持仓跟踪器

跟踪多交易对的持仓数量，实现全局持仓限制控制。

核心功能：
- 跟踪所有交易对的持仓总数
- 执行全局持仓上限检查
- 计算动态仓位金额

迭代编号: 045 (策略20-多交易对共享资金池)
创建日期: 2026-01-14
"""

import logging
from decimal import Decimal
from typing import Dict

logger = logging.getLogger(__name__)


class GlobalPositionTracker:
    """
    全局持仓跟踪器

    跟踪多交易对共享资金池场景下的全局持仓状态。

    核心约束：
        所有交易对的持仓数合计不超过 max_positions

    仓位计算公式：
        position_size = available_cash / (max_positions - total_holdings)

    Attributes:
        _max_positions: 最大持仓数量
        _holdings: 各交易对持仓数量 {symbol: count}

    Example:
        >>> tracker = GlobalPositionTracker(max_positions=10)
        >>> tracker.add_holding("ETHUSDT")
        >>> tracker.add_holding("BTCUSDT")
        >>> tracker.total_holdings
        2
        >>> tracker.can_open_position()
        True
        >>> tracker.calculate_position_size(Decimal("8000"))
        Decimal('1000')  # 8000 / (10-2) = 1000
    """

    def __init__(self, max_positions: int = 10):
        """
        初始化全局持仓跟踪器

        Args:
            max_positions: 最大持仓数量（所有交易对合计）
        """
        self._max_positions = max_positions
        self._holdings: Dict[str, int] = {}

        logger.info(f"初始化GlobalPositionTracker: max_positions={max_positions}")

    @property
    def max_positions(self) -> int:
        """最大持仓数量"""
        return self._max_positions

    @property
    def total_holdings(self) -> int:
        """总持仓数量（所有交易对合计）"""
        return sum(self._holdings.values())

    @property
    def holdings_by_symbol(self) -> Dict[str, int]:
        """各交易对持仓数量"""
        return self._holdings.copy()

    def get_holdings_count(self, symbol: str) -> int:
        """
        获取指定交易对的持仓数量

        Args:
            symbol: 交易对

        Returns:
            int: 持仓数量
        """
        return self._holdings.get(symbol, 0)

    def can_open_position(self) -> bool:
        """
        检查是否可以新建持仓

        Returns:
            bool: True表示可以新建，False表示已达上限
        """
        return self.total_holdings < self._max_positions

    def available_slots(self) -> int:
        """
        获取可用持仓槽位数

        Returns:
            int: 可用槽位数 = max_positions - total_holdings
        """
        return max(0, self._max_positions - self.total_holdings)

    def add_holding(self, symbol: str):
        """
        增加持仓（买入成交时调用）

        Args:
            symbol: 交易对
        """
        if symbol not in self._holdings:
            self._holdings[symbol] = 0
        self._holdings[symbol] += 1

        logger.debug(
            f"增加持仓: symbol={symbol}, count={self._holdings[symbol]}, "
            f"total={self.total_holdings}"
        )

    def remove_holding(self, symbol: str):
        """
        减少持仓（卖出成交时调用）

        Args:
            symbol: 交易对
        """
        if symbol in self._holdings and self._holdings[symbol] > 0:
            self._holdings[symbol] -= 1
            if self._holdings[symbol] == 0:
                del self._holdings[symbol]

            logger.debug(
                f"减少持仓: symbol={symbol}, count={self._holdings.get(symbol, 0)}, "
                f"total={self.total_holdings}"
            )

    def calculate_position_size(self, available_cash: Decimal) -> Decimal:
        """
        计算动态仓位金额

        公式: position_size = available_cash / (max_positions - total_holdings)

        Args:
            available_cash: 当前可用资金

        Returns:
            Decimal: 单笔仓位金额，0表示无法新建持仓
        """
        remaining_slots = self._max_positions - self.total_holdings
        if remaining_slots <= 0:
            logger.debug("持仓已满，无法计算仓位金额")
            return Decimal("0")

        if available_cash <= 0:
            logger.debug("可用资金不足，无法计算仓位金额")
            return Decimal("0")

        position_size = available_cash / Decimal(str(remaining_slots))

        logger.debug(
            f"计算仓位金额: available_cash={available_cash}, "
            f"remaining_slots={remaining_slots}, position_size={position_size}"
        )

        return position_size

    def reset(self):
        """重置持仓跟踪器（重新回测时调用）"""
        self._holdings.clear()
        logger.info(f"重置GlobalPositionTracker: max_positions={self._max_positions}")
