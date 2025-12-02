"""
简单止盈执行器 - Grid V4
SimpleTakeProfitExecutor

实现一次性全平止盈逻辑：
- 多单到达R1后全部平仓
- 空单到达S1后全部平仓
"""
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class SimpleTakeProfitExecutor:
    """简单止盈执行器 - 一次性全平"""

    def __init__(self, position_manager, fee_rate: float = 0.001):
        """
        初始化止盈执行器

        Args:
            position_manager: BidirectionalPositionManager实例
            fee_rate: 手续费率（默认0.1%）
        """
        self.position_manager = position_manager
        self.fee_rate = fee_rate
        self.events = []

        logger.info(f"简单止盈执行器初始化: 手续费={self.fee_rate*100:.2f}%")

    def check_and_execute(self, current_price: float, grid_levels: Dict) -> List[Dict]:
        """
        检查并执行止盈（统一接口）

        Args:
            current_price: 当前价格
            grid_levels: 网格层级信息

        Returns:
            事件列表
        """
        self.events = []

        # 检查多单止盈
        self.check_long_take_profit(current_price, grid_levels)

        # 检查空单止盈
        self.check_short_take_profit(current_price, grid_levels)

        return self.events

    def check_long_take_profit(self, current_price: float, grid_levels: Dict):
        """
        检查多单止盈条件
        所有多单（S1/S2）到达R1全部平仓

        Args:
            current_price: 当前价格
            grid_levels: 网格层级信息
        """
        r1_price = grid_levels['resistance_1']['price']

        # 价格到达或超过R1
        if current_price >= r1_price:
            long_positions = self.position_manager.get_open_long_positions()

            if long_positions.exists():
                logger.info(
                    f"🎯 触发多单止盈: 价格={current_price:.2f} >= R1={r1_price:.2f}, "
                    f"待平仓={long_positions.count()}笔"
                )

                for pos in long_positions:
                    self.execute_long_take_profit(pos, current_price)

    def check_short_take_profit(self, current_price: float, grid_levels: Dict):
        """
        检查空单止盈条件
        所有空单（R1/R2）到达S1全部平仓

        Args:
            current_price: 当前价格
            grid_levels: 网格层级信息
        """
        s1_price = grid_levels['support_1']['price']

        # 价格到达或跌破S1
        if current_price <= s1_price:
            short_positions = self.position_manager.get_open_short_positions()

            if short_positions.exists():
                logger.info(
                    f"🎯 触发空单止盈: 价格={current_price:.2f} <= S1={s1_price:.2f}, "
                    f"待平仓={short_positions.count()}笔"
                )

                for pos in short_positions:
                    self.execute_short_take_profit(pos, current_price)

    def execute_long_take_profit(self, position, price: float):
        """
        执行多单止盈 - 全部卖出

        Args:
            position: GridPosition对象
            price: 卖出价格
        """
        # 计算剩余持仓
        remaining = float(position.buy_amount - position.total_sold_amount)

        if remaining <= 0.00000001:
            return  # 已经平仓完毕

        # 执行平仓
        revenue = self.position_manager.close_long_position(
            position=position,
            price=price,
            amount=remaining,
            reason='take_profit'
        )

        # 记录事件
        self.events.append({
            'type': 'sell',
            'direction': 'long',
            'position_id': position.id,
            'level': position.buy_level,
            'price': price,
            'amount': remaining,
            'revenue': revenue,
            'pnl': float(position.pnl),
            'is_complete': True  # Grid V4一次性全部卖出
        })

        logger.info(
            f"✅ 多单止盈: position#{position.id} ({position.buy_level}), "
            f"卖出={remaining:.6f} @ {price:.2f}, "
            f"盈亏=${float(position.pnl):.2f}"
        )

    def execute_short_take_profit(self, position, price: float):
        """
        执行空单止盈 - 买币还债

        Args:
            position: GridPosition对象
            price: 买入价格
        """
        # 计算剩余持仓
        remaining = float(position.buy_amount - position.total_sold_amount)

        if remaining <= 0.00000001:
            return  # 已经平仓完毕

        # 执行平仓
        cost = self.position_manager.close_short_position(
            position=position,
            price=price,
            amount=remaining,
            reason='take_profit'
        )

        # 记录事件
        self.events.append({
            'type': 'buy_to_cover',
            'direction': 'short',
            'position_id': position.id,
            'level': position.buy_level,
            'price': price,
            'amount': remaining,
            'cost': cost,
            'pnl': float(position.pnl),
            'is_complete': True  # Grid V4一次性全部平仓
        })

        logger.info(
            f"✅ 空单止盈: position#{position.id} ({position.buy_level}), "
            f"买入={remaining:.6f} @ {price:.2f}, "
            f"盈亏=${float(position.pnl):.2f}"
        )

    def get_events(self) -> List[Dict]:
        """获取事件列表"""
        return self.events

    def clear_events(self):
        """清空事件列表"""
        self.events = []
