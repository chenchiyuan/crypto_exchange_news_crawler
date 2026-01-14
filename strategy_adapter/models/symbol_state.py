"""
交易对状态数据类

存储单个交易对的所有状态信息，用于多交易对策略。

核心功能：
- 存储挂单信息（买入/卖出）
- 存储持仓信息
- 存储已完成订单
- 缓存指标计算结果
- 统计交易数据

迭代编号: 045 (策略20-多交易对共享资金池)
创建日期: 2026-01-14
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Dict, List, Any

from .pending_order import PendingOrder


@dataclass
class SymbolState:
    """
    单交易对状态容器

    存储该交易对的所有状态信息，包括挂单、持仓、已完成订单和指标缓存。

    Attributes:
        symbol: 交易对符号（如 ETHUSDT）
        pending_buy_order: 当前买入挂单（每次只挂1笔）
        pending_sell_orders: 卖出挂单字典 {order_id: sell_order_dict}
        holdings: 持仓字典 {order_id: holding_dict}
        completed_orders: 已完成订单列表
        indicators_cache: 指标缓存（避免重复计算）
        total_orders: 总订单数
        winning_orders: 盈利订单数
        total_profit_loss: 总盈亏

    Example:
        >>> state = SymbolState(symbol="ETHUSDT")
        >>> state.holdings["order_001"] = {
        ...     "buy_price": Decimal("3200"),
        ...     "quantity": Decimal("0.1"),
        ...     "amount": Decimal("320"),
        ...     "buy_timestamp": 1704067200000
        ... }
        >>> len(state.holdings)
        1
    """

    # 交易对标识
    symbol: str

    # 挂单状态
    pending_buy_order: Optional[PendingOrder] = None
    pending_sell_orders: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # 持仓状态
    holdings: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # 已完成订单
    completed_orders: List[Dict[str, Any]] = field(default_factory=list)

    # 指标缓存
    indicators_cache: Dict[str, Any] = field(default_factory=dict)

    # 统计字段
    total_orders: int = 0
    winning_orders: int = 0
    total_profit_loss: Decimal = field(default_factory=lambda: Decimal("0"))

    def get_holding_count(self) -> int:
        """获取当前持仓数量"""
        return len(self.holdings)

    def get_pending_buy_count(self) -> int:
        """获取买入挂单数量（0或1）"""
        return 1 if self.pending_buy_order is not None else 0

    def get_pending_sell_count(self) -> int:
        """获取卖出挂单数量"""
        return len(self.pending_sell_orders)

    def get_win_rate(self) -> float:
        """
        获取胜率

        Returns:
            float: 胜率百分比（0-100），无订单时返回0
        """
        if self.total_orders == 0:
            return 0.0
        return self.winning_orders / self.total_orders * 100

    def add_completed_order(self, order: Dict[str, Any]):
        """
        添加已完成订单并更新统计

        Args:
            order: 订单字典，必须包含 profit_loss 字段
        """
        self.completed_orders.append(order)
        self.total_orders += 1

        profit_loss = order.get('profit_loss', 0)
        if isinstance(profit_loss, (int, float)):
            profit_loss = Decimal(str(profit_loss))
        self.total_profit_loss += profit_loss

        if profit_loss > 0:
            self.winning_orders += 1

    def reset(self):
        """重置状态（重新回测时调用）"""
        self.pending_buy_order = None
        self.pending_sell_orders.clear()
        self.holdings.clear()
        self.completed_orders.clear()
        self.indicators_cache.clear()
        self.total_orders = 0
        self.winning_orders = 0
        self.total_profit_loss = Decimal("0")

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典（用于结果输出）

        Returns:
            Dict: 状态字典
        """
        return {
            'symbol': self.symbol,
            'holdings_count': self.get_holding_count(),
            'pending_buy_count': self.get_pending_buy_count(),
            'pending_sell_count': self.get_pending_sell_count(),
            'total_orders': self.total_orders,
            'winning_orders': self.winning_orders,
            'win_rate': self.get_win_rate(),
            'total_profit_loss': float(self.total_profit_loss),
        }
