"""
网格订单生成器
Grid Order Generator

功能:
1. 根据入场价格和网格步长生成网格订单
2. 计算每个价格档位的订单数量
3. 生成上下各N层的buy/sell订单
"""
import logging
from typing import List, Tuple
from decimal import Decimal
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GridOrderPlan:
    """网格订单计划"""
    order_type: str  # 'buy' or 'sell'
    price: Decimal
    quantity: Decimal
    level: int  # 网格层级，0为入场价，正数为上方，负数为下方


class GridOrderGenerator:
    """网格订单生成器"""

    def generate_grid_orders(
        self,
        entry_price: float,
        grid_step: float,
        grid_levels: int,
        order_size_usdt: float,
        strategy_type: str = 'long'
    ) -> List[GridOrderPlan]:
        """
        生成网格订单计划

        Args:
            entry_price: 入场价格
            grid_step: 网格步长（绝对价格）
            grid_levels: 网格层数（上下各N层）
            order_size_usdt: 每格金额（USDT）
            strategy_type: 策略类型 'long'或'short'

        Returns:
            List[GridOrderPlan]: 订单计划列表

        Example:
            >>> generator = GridOrderGenerator()
            >>> orders = generator.generate_grid_orders(
            ...     entry_price=50000.0,
            ...     grid_step=500.0,
            ...     grid_levels=5,
            ...     order_size_usdt=100.0,
            ...     strategy_type='long'
            ... )
            >>> print(f"生成订单数: {len(orders)}")
            生成订单数: 10  # 上方5层卖单 + 下方5层买单
        """
        orders = []

        if strategy_type == 'long':
            # 做多网格: 下方买单，上方卖单

            # 下方买单（负向层级）
            for level in range(1, grid_levels + 1):
                buy_price = entry_price - (grid_step * level)
                if buy_price <= 0:
                    logger.warning(f"买单价格<=0，跳过层级 -{level}")
                    continue

                quantity = order_size_usdt / buy_price

                orders.append(GridOrderPlan(
                    order_type='buy',
                    price=Decimal(str(buy_price)),
                    quantity=Decimal(str(quantity)),
                    level=-level  # 负数表示下方
                ))

            # 上方卖单（正向层级）
            for level in range(1, grid_levels + 1):
                sell_price = entry_price + (grid_step * level)
                quantity = order_size_usdt / sell_price

                orders.append(GridOrderPlan(
                    order_type='sell',
                    price=Decimal(str(sell_price)),
                    quantity=Decimal(str(quantity)),
                    level=level  # 正数表示上方
                ))

        elif strategy_type == 'short':
            # 做空网格: 上方卖单，下方买单

            # 上方卖单（正向层级）
            for level in range(1, grid_levels + 1):
                sell_price = entry_price + (grid_step * level)
                quantity = order_size_usdt / sell_price

                orders.append(GridOrderPlan(
                    order_type='sell',
                    price=Decimal(str(sell_price)),
                    quantity=Decimal(str(quantity)),
                    level=level
                ))

            # 下方买单（负向层级）
            for level in range(1, grid_levels + 1):
                buy_price = entry_price - (grid_step * level)
                if buy_price <= 0:
                    logger.warning(f"买单价格<=0，跳过层级 -{level}")
                    continue

                quantity = order_size_usdt / buy_price

                orders.append(GridOrderPlan(
                    order_type='buy',
                    price=Decimal(str(buy_price)),
                    quantity=Decimal(str(quantity)),
                    level=-level
                ))

        else:
            raise ValueError(f"不支持的策略类型: {strategy_type}")

        logger.info(
            f"生成网格订单: entry_price={entry_price}, step={grid_step}, "
            f"levels={grid_levels}, total_orders={len(orders)}"
        )

        return orders

    def calculate_grid_step_percentage(
        self,
        entry_price: float,
        grid_step: float
    ) -> float:
        """
        计算网格步长百分比

        Args:
            entry_price: 入场价格
            grid_step: 网格步长（绝对价格）

        Returns:
            float: 步长百分比（如0.01表示1%）
        """
        return grid_step / entry_price

    def estimate_max_position_value(
        self,
        grid_levels: int,
        order_size_usdt: float,
        strategy_type: str = 'long'
    ) -> float:
        """
        估算最大仓位价值

        Args:
            grid_levels: 网格层数
            order_size_usdt: 每格金额
            strategy_type: 策略类型

        Returns:
            float: 最大仓位价值（USDT）

        Note:
            做多网格: 最多买入grid_levels * order_size_usdt
            做空网格: 最多卖出grid_levels * order_size_usdt
        """
        max_position = grid_levels * order_size_usdt

        logger.info(
            f"最大仓位估算: levels={grid_levels}, "
            f"size_per_grid={order_size_usdt}, max={max_position}"
        )

        return max_position
