"""
突破止损管理器 - Grid V4
BreakoutStopLossManager

实现突破关键位+3%止损逻辑：
- 多单：跌破S2后继续下跌3%触发止损
- 空单：涨破R2后继续上涨3%触发止损
"""
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class BreakoutStopLossManager:
    """突破止损管理器"""

    def __init__(
        self,
        position_manager,
        stop_loss_pct: float = 0.03,
        fee_rate: float = 0.001
    ):
        """
        初始化止损管理器

        Args:
            position_manager: BidirectionalPositionManager实例
            stop_loss_pct: 止损百分比（默认3%）
            fee_rate: 手续费率（默认0.1%）
        """
        self.position_manager = position_manager
        self.stop_loss_pct = stop_loss_pct
        self.fee_rate = fee_rate
        self.events = []

        logger.info(
            f"突破止损管理器初始化: "
            f"止损比例={self.stop_loss_pct*100:.1f}%, "
            f"手续费={self.fee_rate*100:.2f}%"
        )

    def check_and_execute(self, current_price: float, grid_levels: Dict) -> List[Dict]:
        """
        检查并执行止损（统一接口）

        Args:
            current_price: 当前价格
            grid_levels: 网格层级信息

        Returns:
            事件列表
        """
        self.events = []

        # 检查多单止损
        self.check_long_stop_loss(current_price, grid_levels)

        # 检查空单止损
        self.check_short_stop_loss(current_price, grid_levels)

        return self.events

    def check_long_stop_loss(self, current_price: float, grid_levels: Dict):
        """
        多单止损逻辑：
        检查每个多单持仓的固定止损价，触发则执行止损

        Args:
            current_price: 当前价格
            grid_levels: 网格层级信息（未使用，保留兼容性）
        """
        long_positions = self.position_manager.get_open_long_positions()

        if not long_positions.exists():
            return

        # 检查每个仓位的固定止损价
        positions_to_stop = []
        for pos in long_positions:
            stop_loss_price = float(pos.stop_loss_price)

            # 如果止损价无效（0或负数），跳过该仓位
            if stop_loss_price <= 0:
                continue

            # 价格跌破止损价
            if current_price <= stop_loss_price:
                positions_to_stop.append(pos)

        # 批量止损
        if positions_to_stop:
            logger.error(
                f"🛑 触发多单止损: 价格={current_price:.2f}, "
                f"待止损={len(positions_to_stop)}笔"
            )

            self.execute_stop_loss(
                positions_to_stop,
                current_price,
                'long'
            )

    def check_short_stop_loss(self, current_price: float, grid_levels: Dict):
        """
        空单止损逻辑：
        检查每个空单持仓的固定止损价，触发则执行止损

        Args:
            current_price: 当前价格
            grid_levels: 网格层级信息（未使用，保留兼容性）
        """
        short_positions = self.position_manager.get_open_short_positions()

        if not short_positions.exists():
            return

        # 检查每个仓位的固定止损价
        positions_to_stop = []
        for pos in short_positions:
            stop_loss_price = float(pos.stop_loss_price)

            # 如果止损价无效（0或负数），跳过该仓位
            if stop_loss_price <= 0:
                continue

            # 价格涨破止损价
            if current_price >= stop_loss_price:
                positions_to_stop.append(pos)

        # 批量止损
        if positions_to_stop:
            logger.error(
                f"🛑 触发空单止损: 价格={current_price:.2f}, "
                f"待止损={len(positions_to_stop)}笔"
            )

            self.execute_stop_loss(
                positions_to_stop,
                current_price,
                'short'
            )

    def execute_stop_loss(self, positions, price: float, direction: str):
        """
        批量止损

        Args:
            positions: List of GridPosition 或 QuerySet of GridPosition
            price: 止损价格
            direction: 方向（'long' 或 'short'）
        """
        # 兼容list和queryset
        if hasattr(positions, 'exists'):
            if not positions.exists():
                return
        elif not positions:
            return

        total_revenue = 0
        position_ids = []
        total_pnl = 0

        for pos in positions:
            # 计算剩余持仓
            remaining = float(pos.buy_amount - pos.total_sold_amount)

            if remaining <= 0.00000001:
                continue

            if direction == 'long':
                # 平多单
                revenue = self.position_manager.close_long_position(
                    position=pos,
                    price=price,
                    amount=remaining,
                    reason='stop_loss'
                )
                total_revenue += revenue
            else:  # short
                # 平空单
                cost = self.position_manager.close_short_position(
                    position=pos,
                    price=price,
                    amount=remaining,
                    reason='stop_loss'
                )
                total_revenue -= cost  # 空单平仓是支出

            position_ids.append(pos.id)
            total_pnl += float(pos.pnl)

        # 记录批量止损事件
        self.events.append({
            'type': 'stop_loss',
            'direction': direction,
            'position_ids': position_ids,
            'price': price,
            'total_pnl': total_pnl,
            'count': len(position_ids)
        })

        logger.error(
            f"🛑 批量止损完成: {direction.upper()}, "
            f"数量={len(position_ids)}笔, "
            f"价格={price:.2f}, "
            f"总盈亏=${total_pnl:.2f}"
        )

    def get_events(self) -> List[Dict]:
        """获取事件列表"""
        return self.events

    def clear_events(self):
        """清空事件列表"""
        self.events = []

    def reset(self):
        """重置状态（用于测试或新回测）"""
        self.events = []
        logger.info("止损管理器状态已重置")
