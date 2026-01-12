"""
GFOB限价单管理器

本模块实现Good-for-One-Bar限价单的完整生命周期管理：
- GFOB订单创建（有效期=下一根K线）
- 撮合判断（买单low≤L，卖单high≥U）
- 订单过期处理
- 资金管理（委托LimitOrderManager）

设计决策：采用组合模式，内部持有LimitOrderManager实例，
复用其资金管理逻辑，自行实现GFOB特有的撮合规则和有效期管理。

迭代编号: 034 (滚动经验CDF信号策略)
创建日期: 2026-01-12
关联任务: TASK-034-005, TASK-034-006, TASK-034-007
关联需求: FP-034-009~015 (function-points.md)
关联架构: architecture.md#4.3.2 GFOBOrderManager
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional
import uuid

from strategy_adapter.core.limit_order_manager import LimitOrderManager
from strategy_adapter.models import PendingOrder, PendingOrderStatus, PendingOrderSide

logger = logging.getLogger(__name__)


class GFOBOrderManager:
    """
    GFOB限价单管理器

    GFOB = Good-for-One-Bar：订单仅在下一根K线有效，未成交则自动过期。

    职责：
    - 创建GFOB限价单（有效期=下一根K线）
    - 撮合判断：买单 low ≤ L 成交；卖单 high ≥ U 成交
    - 订单过期处理
    - 资金管理（委托LimitOrderManager）

    关键差异（与LimitOrderManager撮合规则）：
    - 本管理器：买单 `low ≤ L` 即成交（不要求 L ≤ high）
    - 本管理器：卖单 `high ≥ U` 即成交（不要求 low ≤ U）
    - LimitOrderManager：要求 `low ≤ price ≤ high`

    设计：组合模式，内部持有LimitOrderManager用于资金管理

    Example:
        >>> manager = GFOBOrderManager(position_size=Decimal("100"))
        >>> manager.initialize(Decimal("10000"))
        >>> order = manager.create_buy_order(Decimal("3500"), kline_index=10, timestamp=1000)
        >>> # 下一根K线撮合
        >>> result = manager.match_orders(11, low=Decimal("3400"), high=Decimal("3600"), timestamp=1001)
    """

    def __init__(
        self,
        position_size: Decimal = Decimal("100"),
        delta_in: float = 0.001,
        delta_out: float = 0.0,
        delta_out_fast: float = 0.001
    ):
        """
        初始化GFOB订单管理器

        Args:
            position_size: 单笔挂单金额（USDT），默认100
            delta_in: 入场限价折扣，默认0.001（0.1%）
            delta_out: 正常出场折扣，默认0.0
            delta_out_fast: 快速出场折扣，默认0.001（0.1%）
        """
        # 参数配置
        self._position_size = position_size
        self._delta_in = Decimal(str(delta_in))
        self._delta_out = Decimal(str(delta_out))
        self._delta_out_fast = Decimal(str(delta_out_fast))

        # 组合模式：内部持有LimitOrderManager用于资金管理
        self._capital_manager = LimitOrderManager(position_size=position_size)

        # GFOB订单存储（单仓位模式：最多各一个）
        self._pending_buy: Optional[Dict] = None
        self._pending_sell: Optional[Dict] = None

        # 订单计数器
        self._order_counter: int = 0

        # 订单日志
        self._order_logs: List[Dict] = []

        logger.debug(
            f"初始化GFOBOrderManager: position_size={position_size}, "
            f"delta_in={delta_in}, delta_out={delta_out}, delta_out_fast={delta_out_fast}"
        )

    def initialize(self, initial_capital: Decimal) -> None:
        """
        初始化资金

        Args:
            initial_capital: 初始资金（USDT）
        """
        self._capital_manager.initialize(initial_capital)
        self._pending_buy = None
        self._pending_sell = None
        self._order_counter = 0
        self._order_logs.clear()

        logger.info(f"GFOBOrderManager初始化完成，初始资金: {initial_capital}")

    @property
    def available_capital(self) -> Decimal:
        """可用资金"""
        return self._capital_manager.available_capital

    @property
    def frozen_capital(self) -> Decimal:
        """冻结资金"""
        return self._capital_manager.frozen_capital

    @property
    def total_capital(self) -> Decimal:
        """总资金"""
        return self._capital_manager.total_capital

    def create_buy_order(
        self,
        close_price: Decimal,
        kline_index: int,
        timestamp: int
    ) -> Optional[Dict]:
        """
        创建入场限价买单

        价格计算: L = close × (1 - δ_in)
        有效期: 下一根K线（kline_index + 1）

        Args:
            close_price: 当前收盘价
            kline_index: 当前K线索引
            timestamp: 当前时间戳

        Returns:
            Optional[Dict]: 创建的订单信息，资金不足时返回None
        """
        # 计算限价: L = P × (1 - δ_in)
        limit_price = close_price * (1 - self._delta_in)

        # 生成订单ID
        self._order_counter += 1
        order_id = f"gfob_buy_{timestamp}_{self._order_counter}"

        # 委托LimitOrderManager创建订单（冻结资金）
        order = self._capital_manager.create_buy_order(
            price=limit_price,
            kline_index=kline_index,
            timestamp=timestamp
        )

        if order is None:
            logger.debug(f"资金不足，无法创建买入挂单")
            return None

        # 存储GFOB订单信息
        self._pending_buy = {
            'order_id': order_id,
            'internal_order_id': order.order_id,  # LimitOrderManager的订单ID
            'price': limit_price,
            'quantity': order.quantity,
            'amount': order.amount,
            'placed_bar': kline_index,
            'valid_bar': kline_index + 1,  # GFOB: 下一根K线有效
            'reason': 'ENTRY_TAIL',
            'status': 'PLACED',
            'created_at': timestamp,
        }

        # 记录订单日志
        self._log_order_event(self._pending_buy, 'PLACED')

        logger.debug(
            f"创建买入挂单: {order_id}, 价格: {limit_price}, "
            f"有效K线: {kline_index + 1}"
        )

        return self._pending_buy.copy()

    def create_sell_order(
        self,
        close_price: Decimal,
        parent_order_id: str,
        quantity: Decimal,
        reason: str,
        kline_index: int,
        timestamp: int
    ) -> Dict:
        """
        创建出场限价卖单

        价格计算:
        - 快速退出(FAST_EXIT): U = close × (1 - δ_out_fast)
        - 正常退出(PROB_REVERSION): U = close × (1 - δ_out)

        Args:
            close_price: 当前收盘价
            parent_order_id: 关联的买入订单ID
            quantity: 卖出数量
            reason: 出场原因 ('PROB_REVERSION' or 'FAST_EXIT')
            kline_index: 当前K线索引
            timestamp: 当前时间戳

        Returns:
            Dict: 创建的订单信息
        """
        # 根据原因选择定价模式
        if reason == 'FAST_EXIT':
            delta = self._delta_out_fast
        else:  # PROB_REVERSION
            delta = self._delta_out

        # 计算限价
        sell_price = close_price * (1 - delta)

        # 生成订单ID
        self._order_counter += 1
        order_id = f"gfob_sell_{timestamp}_{self._order_counter}"

        # 存储GFOB订单信息
        self._pending_sell = {
            'order_id': order_id,
            'parent_order_id': parent_order_id,
            'price': sell_price,
            'quantity': quantity,
            'amount': sell_price * quantity,
            'placed_bar': kline_index,
            'valid_bar': kline_index + 1,  # GFOB: 下一根K线有效
            'reason': reason,
            'status': 'PLACED',
            'created_at': timestamp,
        }

        # 记录订单日志
        self._log_order_event(self._pending_sell, 'PLACED')

        logger.debug(
            f"创建卖出挂单: {order_id}, 价格: {sell_price}, "
            f"原因: {reason}, 有效K线: {kline_index + 1}"
        )

        return self._pending_sell.copy()

    def match_orders(
        self,
        kline_index: int,
        low: Decimal,
        high: Decimal,
        timestamp: int
    ) -> Dict:
        """
        撮合订单（先卖后买）

        撮合规则：
        - 买单: low ≤ L 即成交，成交价 = L
        - 卖单: high ≥ U 即成交，成交价 = U
        - 顺序: 先撮合卖单，再撮合买单（避免同bar翻手套利）

        Args:
            kline_index: 当前K线索引
            low: K线最低价
            high: K线最高价
            timestamp: 当前时间戳

        Returns:
            Dict: {
                'sell_fills': List[Dict],     # 成交的卖单
                'buy_fills': List[Dict],      # 成交的买单
                'expired_orders': List[str]   # 过期的订单ID
            }
        """
        result = {
            'sell_fills': [],
            'buy_fills': [],
            'expired_orders': []
        }

        # Step 1: 过期非当前K线的订单
        expired = self._expire_stale_orders(kline_index, timestamp)
        result['expired_orders'] = expired

        # Step 2: 先撮合卖单（若有）
        if self._pending_sell and self._pending_sell['valid_bar'] == kline_index:
            sell_price = self._pending_sell['price']
            # 卖单撮合条件: high ≥ U
            if high >= sell_price:
                fill = self._fill_sell_order(timestamp)
                result['sell_fills'].append(fill)

        # Step 3: 再撮合买单（若有）
        if self._pending_buy and self._pending_buy['valid_bar'] == kline_index:
            buy_price = self._pending_buy['price']
            # 买单撮合条件: low ≤ L
            if low <= buy_price:
                fill = self._fill_buy_order(timestamp)
                result['buy_fills'].append(fill)

        return result

    def _fill_buy_order(self, timestamp: int) -> Dict:
        """
        确认买单成交

        Args:
            timestamp: 成交时间戳

        Returns:
            Dict: 成交信息
        """
        order = self._pending_buy

        # 更新状态
        order['status'] = 'FILLED'
        order['fill_time'] = timestamp
        order['fill_price'] = order['price']  # 成交价 = 限价

        # 委托LimitOrderManager确认成交
        self._capital_manager.fill_buy_order(order['internal_order_id'], timestamp)

        # 记录日志
        self._log_order_event(order, 'FILLED')

        logger.debug(f"买入挂单成交: {order['order_id']}, 价格: {order['price']}")

        # 清除待处理订单
        fill_info = order.copy()
        self._pending_buy = None

        return fill_info

    def _fill_sell_order(self, timestamp: int) -> Dict:
        """
        确认卖单成交

        Args:
            timestamp: 成交时间戳

        Returns:
            Dict: 成交信息
        """
        order = self._pending_sell

        # 更新状态
        order['status'] = 'FILLED'
        order['fill_time'] = timestamp
        order['fill_price'] = order['price']  # 成交价 = 限价

        # 记录日志
        self._log_order_event(order, 'FILLED')

        logger.debug(f"卖出挂单成交: {order['order_id']}, 价格: {order['price']}")

        # 清除待处理订单
        fill_info = order.copy()
        self._pending_sell = None

        return fill_info

    def _expire_stale_orders(self, current_kline_index: int, timestamp: int) -> List[str]:
        """
        过期非当前K线的订单（GFOB语义）

        Args:
            current_kline_index: 当前K线索引
            timestamp: 当前时间戳

        Returns:
            List[str]: 过期的订单ID列表
        """
        expired = []

        # 检查买单
        if self._pending_buy and self._pending_buy['valid_bar'] < current_kline_index:
            order = self._pending_buy
            order['status'] = 'EXPIRED'
            order['expire_time'] = timestamp

            # 解冻资金
            self._capital_manager.cancel_all_buy_orders()

            # 记录日志
            self._log_order_event(order, 'EXPIRED')

            expired.append(order['order_id'])
            logger.debug(f"买入挂单过期: {order['order_id']}")

            self._pending_buy = None

        # 检查卖单
        if self._pending_sell and self._pending_sell['valid_bar'] < current_kline_index:
            order = self._pending_sell
            order['status'] = 'EXPIRED'
            order['expire_time'] = timestamp

            # 记录日志
            self._log_order_event(order, 'EXPIRED')

            expired.append(order['order_id'])
            logger.debug(f"卖出挂单过期: {order['order_id']}")

            self._pending_sell = None

        return expired

    def cancel_pending_buy(self, timestamp: int) -> Optional[str]:
        """
        取消待处理的买单

        Args:
            timestamp: 取消时间戳

        Returns:
            Optional[str]: 取消的订单ID
        """
        if self._pending_buy is None:
            return None

        order = self._pending_buy
        order['status'] = 'CANCELLED'
        order['cancel_time'] = timestamp

        # 解冻资金
        self._capital_manager.cancel_all_buy_orders()

        # 记录日志
        self._log_order_event(order, 'CANCELLED')

        order_id = order['order_id']
        self._pending_buy = None

        return order_id

    def release_sell_capital(self, buy_price: Decimal, quantity: Decimal, profit_loss: Decimal) -> None:
        """
        释放卖出后的资金

        Args:
            buy_price: 买入价格
            quantity: 数量
            profit_loss: 盈亏金额
        """
        # 释放资金：原冻结资金 + 盈亏
        released_capital = buy_price * quantity + profit_loss
        self._capital_manager._frozen_capital -= buy_price * quantity
        self._capital_manager._available_capital += released_capital

    def _log_order_event(self, order: Dict, event: str) -> None:
        """
        记录订单事件日志

        Args:
            order: 订单信息
            event: 事件类型
        """
        log_entry = {
            'order_id': order['order_id'],
            'event': event,
            'timestamp': order.get('created_at') or order.get('fill_time') or order.get('expire_time'),
            'price': order['price'],
            'quantity': order.get('quantity'),
            'reason': order.get('reason'),
            'status': order['status'],
        }
        self._order_logs.append(log_entry)

    def get_pending_buy_price(self) -> Optional[Decimal]:
        """获取待处理买单的价格"""
        if self._pending_buy:
            return self._pending_buy['price']
        return None

    def get_pending_sell_price(self) -> Optional[Decimal]:
        """获取待处理卖单的价格"""
        if self._pending_sell:
            return self._pending_sell['price']
        return None

    def has_pending_buy(self) -> bool:
        """是否有待处理的买单"""
        return self._pending_buy is not None

    def has_pending_sell(self) -> bool:
        """是否有待处理的卖单"""
        return self._pending_sell is not None

    def get_order_logs(self) -> List[Dict]:
        """获取订单日志"""
        return self._order_logs.copy()

    def get_statistics(self) -> Dict:
        """
        获取统计信息

        Returns:
            Dict: 统计数据
        """
        capital_stats = self._capital_manager.get_statistics()
        return {
            **capital_stats,
            'has_pending_buy': self.has_pending_buy(),
            'has_pending_sell': self.has_pending_sell(),
            'pending_buy_price': float(self.get_pending_buy_price()) if self.get_pending_buy_price() else None,
            'pending_sell_price': float(self.get_pending_sell_price()) if self.get_pending_sell_price() else None,
            'total_order_events': len(self._order_logs),
        }
