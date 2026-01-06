"""
统一订单管理器

本模块实现统一订单管理器UnifiedOrderManager，整合应用层（OrderTracker）和
回测层（PositionManager）的订单管理能力。

核心功能：
- 订单创建：从信号创建Order对象，分配唯一ID
- 订单更新：更新订单状态（平仓），自动计算盈亏
- 订单查询：查询持仓/已平仓订单，支持按策略名称筛选
- 统计计算：计算胜率、总盈亏、平均收益率等指标

设计决策：
完全新建独立实现（architecture.md 决策点一），而非复用OrderTracker：
- 职责清晰：专门为适配层设计
- 无历史包袱：代码简洁
- 不影响现有功能：OrderTracker继续工作
- 易于测试：无外部依赖

迭代编号: 013 (策略适配层)
创建日期: 2026-01-06
关联任务: TASK-013-005
关联需求: FP-013-005 (prd.md)
关联架构: architecture.md#4.3 核心组件模块 + 决策点一
"""

from typing import Dict, List, Optional
from decimal import Decimal
import logging

from strategy_adapter.models import Order, OrderStatus, OrderSide
from strategy_adapter.interfaces import IStrategy

logger = logging.getLogger(__name__)


class UnifiedOrderManager:
    """
    统一订单管理器

    职责：
    - 订单创建：从信号创建Order对象
    - 订单更新：更新订单状态和盈亏
    - 订单查询：查询持仓/已平仓订单
    - 统计计算：计算胜率、总盈亏等

    Example:
        >>> manager = UnifiedOrderManager()
        >>> signal = {'timestamp': 1736164800000, 'price': 2300, 'reason': '...'}
        >>> order = manager.create_order(signal, strategy, Decimal("2300"), Decimal("10000"))
        >>> print(order.id)  # "order_1736164800000"
        >>> manager.update_order(order.id, {'timestamp': 1736230800000, 'price': 2350})
    """

    def __init__(self):
        """
        初始化订单管理器

        创建空的订单字典，用于存储所有订单（持仓 + 已平仓）。
        """
        self._orders: Dict[str, Order] = {}  # 订单字典 {order_id: Order}

    def create_order(
        self,
        signal: Dict,
        strategy: IStrategy,
        current_price: Decimal,
        available_capital: Decimal,
        symbol: str = "ETHUSDT"
    ) -> Order:
        """
        从信号创建订单

        基于买入信号创建Order对象，分配唯一ID，计算数量，并存储到订单字典。

        Args:
            signal (Dict): 买入信号
                必需字段：
                - timestamp (int): 买入时间戳（毫秒）
                - price (Decimal/float): 买入价格
                可选字段：
                - reason (str): 买入理由
                - confidence (float): 信号强度
                - strategy_id (str): 触发策略ID
            strategy (IStrategy): 策略实例
                用于调用calculate_position_size()和get_strategy_name()
            current_price (Decimal): 当前价格（用于计算仓位）
            available_capital (Decimal): 可用资金（USDT）
            symbol (str): 交易对符号，默认"ETHUSDT"

        Returns:
            Order: 创建的订单对象，状态为FILLED（已成交）

        Raises:
            KeyError: 当signal缺少必需字段时抛出
                错误信息包含缺失字段名称
            ValueError: 当current_price <= 0或available_capital < 0时抛出

        Example:
            >>> manager = UnifiedOrderManager()
            >>> signal = {
            ...     'timestamp': 1736164800000,
            ...     'price': 2300.50,
            ...     'reason': 'EMA斜率未来预测',
            ...     'confidence': 0.85
            ... }
            >>> order = manager.create_order(
            ...     signal, strategy, Decimal("2300.50"), Decimal("10000")
            ... )
            >>> print(order.id)  # "order_1736164800000"
            >>> print(order.status)  # OrderStatus.FILLED
        """
        # Guard Clause: 验证必需字段
        if 'timestamp' not in signal:
            raise KeyError("signal缺少必需字段: 'timestamp'")
        if 'price' not in signal:
            raise KeyError("signal缺少必需字段: 'price'")

        # Guard Clause: 验证价格和资金
        if current_price <= 0:
            raise ValueError(f"current_price必须大于0，当前值: {current_price}")
        if available_capital < 0:
            raise ValueError(f"available_capital不能为负，当前值: {available_capital}")

        # 计算仓位大小（策略决定）
        position_size = strategy.calculate_position_size(
            signal, available_capital, current_price
        )

        # 计算数量
        signal_price = Decimal(str(signal['price']))
        quantity = position_size / signal_price

        # 计算手续费（假设0.1%）
        commission_rate = Decimal("0.001")
        open_commission = position_size * commission_rate

        # 创建订单
        order = Order(
            id=f"order_{signal['timestamp']}",
            symbol=symbol,
            side=OrderSide.BUY,  # MVP阶段仅支持做多
            status=OrderStatus.FILLED,
            open_timestamp=signal['timestamp'],
            open_price=signal_price,
            quantity=quantity,
            position_value=position_size,
            strategy_name=strategy.get_strategy_name(),
            strategy_id=signal.get('strategy_id', 'unknown'),
            entry_reason=signal.get('reason', ''),
            open_commission=open_commission,
            metadata={'confidence': signal.get('confidence', 0.0)}
        )

        # 存储订单
        self._orders[order.id] = order

        logger.info(f"创建订单: {order.id}, 策略: {order.strategy_name}, "
                   f"价格: {order.open_price}, 数量: {order.quantity}")

        return order

    def update_order(
        self,
        order_id: str,
        close_signal: Dict
    ) -> Order:
        """
        更新订单（平仓）

        根据卖出信号更新订单状态，设置平仓价格和时间，自动计算盈亏。

        Args:
            order_id (str): 订单ID
            close_signal (Dict): 卖出信号
                必需字段：
                - timestamp (int): 卖出时间戳（毫秒）
                - price (Decimal/float): 卖出价格
                可选字段：
                - reason (str): 卖出理由
                - strategy_id (str): 触发策略ID

        Returns:
            Order: 更新后的订单对象，状态为CLOSED（已平仓）

        Raises:
            KeyError: 当order_id不存在时抛出
                错误信息包含订单ID和可用订单列表

        Side Effects:
            - 更新订单的close_timestamp、close_price、close_reason、status
            - 调用order.calculate_pnl()自动计算盈亏

        Example:
            >>> close_signal = {
            ...     'timestamp': 1736230800000,
            ...     'price': 2350.00,
            ...     'reason': 'EMA25回归'
            ... }
            >>> order = manager.update_order("order_1736164800000", close_signal)
            >>> print(order.status)  # OrderStatus.CLOSED
            >>> print(order.profit_loss)  # Decimal('1.972')
        """
        # Guard Clause: 验证订单ID存在
        if order_id not in self._orders:
            available_ids = list(self._orders.keys())[:5]  # 显示前5个
            raise KeyError(
                f"订单 {order_id} 不存在。\\n"
                f"可用订单示例: {available_ids}\\n"
                f"总订单数: {len(self._orders)}"
            )

        order = self._orders[order_id]

        # 更新平仓信息
        order.status = OrderStatus.CLOSED
        order.close_timestamp = close_signal['timestamp']
        order.close_price = Decimal(str(close_signal['price']))
        order.close_reason = close_signal.get('reason', 'strategy_signal')

        # 计算平仓手续费
        commission_rate = Decimal("0.001")
        close_value = order.close_price * order.quantity
        order.close_commission = close_value * commission_rate

        # 计算盈亏（调用Order的calculate_pnl方法）
        order.calculate_pnl()

        logger.info(f"平仓订单: {order_id}, 平仓价: {order.close_price}, "
                   f"盈亏: {order.profit_loss} ({order.profit_loss_rate}%)")

        return order

    def get_open_orders(
        self,
        strategy_name: Optional[str] = None
    ) -> List[Order]:
        """
        获取持仓订单

        返回所有状态为FILLED的订单（已成交但未平仓）。

        Args:
            strategy_name (Optional[str]): 策略名称筛选（可选）
                如果提供，只返回该策略的持仓订单

        Returns:
            List[Order]: 持仓订单列表，按开仓时间排序

        Example:
            >>> open_orders = manager.get_open_orders()
            >>> print(len(open_orders))  # 2
            >>> ddps_orders = manager.get_open_orders(strategy_name="DDPS-Z")
            >>> print(len(ddps_orders))  # 1
        """
        orders = [
            order for order in self._orders.values()
            if order.status == OrderStatus.FILLED
        ]

        # 按策略名称筛选
        if strategy_name:
            orders = [o for o in orders if o.strategy_name == strategy_name]

        # 按开仓时间排序
        orders.sort(key=lambda o: o.open_timestamp)

        return orders

    def get_closed_orders(
        self,
        strategy_name: Optional[str] = None
    ) -> List[Order]:
        """
        获取已平仓订单

        返回所有状态为CLOSED的订单（已平仓，有盈亏数据）。

        Args:
            strategy_name (Optional[str]): 策略名称筛选（可选）

        Returns:
            List[Order]: 已平仓订单列表，按平仓时间排序

        Example:
            >>> closed_orders = manager.get_closed_orders()
            >>> print(len(closed_orders))  # 5
            >>> for order in closed_orders:
            ...     print(f"{order.id}: {order.profit_loss}")
        """
        orders = [
            order for order in self._orders.values()
            if order.status == OrderStatus.CLOSED
        ]

        # 按策略名称筛选
        if strategy_name:
            orders = [o for o in orders if o.strategy_name == strategy_name]

        # 按平仓时间排序
        orders.sort(key=lambda o: o.close_timestamp if o.close_timestamp else 0)

        return orders

    def calculate_statistics(self, orders: List[Order]) -> Dict:
        """
        计算统计指标

        基于订单列表计算聚合统计指标，包括胜率、总盈亏、平均收益率等。

        Args:
            orders (List[Order]): 订单列表（可以是全部订单或筛选后的订单）

        Returns:
            Dict: 统计指标字典
                {
                    'total_orders': int,       # 总订单数
                    'open_orders': int,        # 持仓订单数
                    'closed_orders': int,      # 已平仓订单数
                    'win_orders': int,         # 盈利订单数
                    'lose_orders': int,        # 亏损订单数
                    'win_rate': float,         # 胜率（%）
                    'total_profit': Decimal,   # 总盈亏（USDT）
                    'avg_profit_rate': Decimal,# 平均收益率（%）
                    'max_profit': Decimal,     # 最大盈利（USDT）
                    'max_loss': Decimal        # 最大亏损（USDT）
                }

        Example:
            >>> all_orders = list(manager._orders.values())
            >>> stats = manager.calculate_statistics(all_orders)
            >>> print(f"胜率: {stats['win_rate']:.2f}%")
            >>> print(f"总盈亏: {stats['total_profit']} USDT")
        """
        closed_orders = [o for o in orders if o.status == OrderStatus.CLOSED]
        open_orders = [o for o in orders if o.status == OrderStatus.FILLED]

        # 边界处理：无已平仓订单
        if not closed_orders:
            return {
                'total_orders': len(orders),
                'open_orders': len(open_orders),
                'closed_orders': 0,
                'win_orders': 0,
                'lose_orders': 0,
                'win_rate': 0.0,
                'total_profit': Decimal("0"),
                'avg_profit_rate': Decimal("0"),
                'max_profit': Decimal("0"),
                'max_loss': Decimal("0"),
            }

        # 计算盈利/亏损订单
        win_orders = [o for o in closed_orders if o.profit_loss and o.profit_loss > 0]
        lose_orders = [o for o in closed_orders if o.profit_loss and o.profit_loss <= 0]

        # 计算胜率
        win_rate = len(win_orders) / len(closed_orders) * 100

        # 计算总盈亏
        total_profit = sum(o.profit_loss for o in closed_orders if o.profit_loss)

        # 计算平均收益率
        profit_rates = [o.profit_loss_rate for o in closed_orders if o.profit_loss_rate]
        avg_profit_rate = sum(profit_rates) / len(profit_rates) if profit_rates else Decimal("0")

        # 计算最大盈利和最大亏损
        profits = [o.profit_loss for o in closed_orders if o.profit_loss]
        max_profit = max(profits) if profits else Decimal("0")
        max_loss = min(profits) if profits else Decimal("0")

        return {
            'total_orders': len(orders),
            'open_orders': len(open_orders),
            'closed_orders': len(closed_orders),
            'win_orders': len(win_orders),
            'lose_orders': len(lose_orders),
            'win_rate': win_rate,
            'total_profit': total_profit,
            'avg_profit_rate': avg_profit_rate,
            'max_profit': max_profit,
            'max_loss': max_loss,
        }
