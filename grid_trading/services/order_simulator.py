"""
订单模拟撮合引擎
Order Simulation Engine

功能:
1. 模拟订单撮合（基于当前市场价格）
2. 模拟滑点和手续费
3. 更新订单状态
"""
import logging
from typing import List, Optional
from decimal import Decimal
from django.utils import timezone

from grid_trading.models import GridOrder
from grid_trading.services.config_loader import load_global_config

logger = logging.getLogger(__name__)


class OrderSimulator:
    """订单模拟撮合器"""

    def __init__(self):
        """初始化撮合器，加载全局配置"""
        global_config = load_global_config()
        sim_config = global_config.get('simulation', {})

        self.slippage_pct = sim_config.get('slippage_pct', 0.0005)  # 默认0.05%
        self.taker_fee_pct = sim_config.get('taker_fee_pct', 0.001)  # 默认0.1%
        self.maker_fee_pct = sim_config.get('maker_fee_pct', 0.001)  # 默认0.1%

        logger.info(
            f"订单模拟器初始化: slippage={self.slippage_pct*100:.2f}%, "
            f"taker_fee={self.taker_fee_pct*100:.2f}%"
        )

    def check_and_fill_orders(
        self,
        orders: List[GridOrder],
        current_price: float
    ) -> List[GridOrder]:
        """
        检查并撮合订单

        Args:
            orders: 待检查的订单列表（status='pending'）
            current_price: 当前市场价格

        Returns:
            List[GridOrder]: 成交的订单列表
        """
        filled_orders = []

        for order in orders:
            if order.status != 'pending':
                continue

            # 检查是否触发成交
            if self._should_fill(order, current_price):
                self._fill_order(order, current_price)
                filled_orders.append(order)

        if filled_orders:
            logger.info(
                f"订单撮合完成: current_price={current_price:.2f}, "
                f"filled_count={len(filled_orders)}"
            )

        return filled_orders

    def _should_fill(self, order: GridOrder, current_price: float) -> bool:
        """
        判断订单是否应该成交

        规则:
            - 买单: 当前价格 <= 挂单价格
            - 卖单: 当前价格 >= 挂单价格

        Args:
            order: 订单
            current_price: 当前价格

        Returns:
            bool: 是否应该成交
        """
        order_price = float(order.price)

        if order.order_type == 'buy':
            # 买单: 价格下跌到挂单价格或以下时成交
            return current_price <= order_price
        elif order.order_type == 'sell':
            # 卖单: 价格上涨到挂单价格或以上时成交
            return current_price >= order_price
        else:
            logger.error(f"未知订单类型: {order.order_type}")
            return False

    def _fill_order(self, order: GridOrder, current_price: float) -> None:
        """
        执行订单撮合（模拟）

        Args:
            order: 订单
            current_price: 当前价格
        """
        order_price = float(order.price)
        quantity = float(order.quantity)

        # 1. 计算实际成交价（模拟滑点）
        if order.order_type == 'buy':
            # 买单: 价格向上滑点（买贵了）
            simulated_price = order_price * (1 + self.slippage_pct)
        else:  # sell
            # 卖单: 价格向下滑点（卖便宜了）
            simulated_price = order_price * (1 - self.slippage_pct)

        # 2. 计算手续费（Taker费率）
        cost = simulated_price * quantity
        fee = cost * self.taker_fee_pct

        # 3. 更新订单
        order.status = 'filled'
        order.filled_at = timezone.now()
        order.simulated_price = Decimal(str(simulated_price))
        order.simulated_fee = Decimal(str(fee))
        order.save()

        logger.info(
            f"订单成交: {order.get_order_type_display()} "
            f"price={order_price:.2f} → simulated={simulated_price:.2f}, "
            f"quantity={quantity:.6f}, fee=${fee:.2f}"
        )

    def cancel_order(self, order: GridOrder) -> None:
        """
        撤销订单

        Args:
            order: 订单
        """
        if order.status != 'pending':
            logger.warning(f"订单状态非pending，无法撤销: status={order.status}")
            return

        order.status = 'cancelled'
        order.save()

        logger.info(f"订单已撤销: order_id={order.id}, price={order.price}")

    def cancel_all_orders(self, strategy_id: int) -> int:
        """
        撤销策略的所有pending订单

        Args:
            strategy_id: 策略ID

        Returns:
            int: 撤销的订单数量
        """
        from grid_trading.models import GridStrategy

        try:
            strategy = GridStrategy.objects.get(id=strategy_id)
        except GridStrategy.DoesNotExist:
            logger.error(f"策略不存在: strategy_id={strategy_id}")
            return 0

        pending_orders = strategy.gridorder_set.filter(status='pending')
        count = pending_orders.count()

        pending_orders.update(status='cancelled')

        logger.info(f"批量撤销订单: strategy_id={strategy_id}, count={count}")

        return count
