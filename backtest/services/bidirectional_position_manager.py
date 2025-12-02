"""
双向仓位管理器 - Grid V4
BidirectionalPositionManager

管理多单和空单两个独立的仓位池
"""
import logging
from decimal import Decimal
from typing import Optional, Dict
from django.utils import timezone

from backtest.models import GridPosition

logger = logging.getLogger(__name__)


class BidirectionalPositionManager:
    """双向仓位管理器 - 管理多单和空单"""

    def __init__(
        self,
        backtest_result_id: int,
        initial_cash: float,
        fee_rate: float = 0.001
    ):
        """
        初始化双向仓位管理器

        Args:
            backtest_result_id: 回测结果ID
            initial_cash: 初始资金
            fee_rate: 手续费率（默认0.1%）
        """
        self.backtest_result_id = backtest_result_id
        self.initial_cash = initial_cash
        self.current_cash = initial_cash
        self.fee_rate = fee_rate

        # 固定仓位比例
        self.support_1_size_pct = 0.20  # 20%
        self.support_2_size_pct = 0.30  # 30%
        self.resistance_1_size_pct = 0.20  # 20%
        self.resistance_2_size_pct = 0.30  # 30%

        logger.info(
            f"双向仓位管理器初始化: "
            f"初始资金={self.initial_cash:.2f}, "
            f"支撑位1={self.support_1_size_pct*100}%, "
            f"支撑位2={self.support_2_size_pct*100}%, "
            f"压力位1={self.resistance_1_size_pct*100}%, "
            f"压力位2={self.resistance_2_size_pct*100}%"
        )

    def open_long_position(
        self,
        level: str,
        price: float,
        amount: float,
        grid_levels: Dict
    ) -> Optional[GridPosition]:
        """
        开多单

        Args:
            level: 买入层级（support_1 或 support_2）
            price: 买入价格
            amount: 买入数量
            grid_levels: 网格层级信息

        Returns:
            GridPosition对象，如果资金不足则返回None
        """
        cost = price * amount * (1 + self.fee_rate)

        if self.current_cash < cost:
            logger.warning(
                f"开多单失败：资金不足 "
                f"(需要={cost:.2f}, 可用={self.current_cash:.2f})"
            )
            return None

        # 创建多单仓位
        position = GridPosition.objects.create(
            backtest_result_id=self.backtest_result_id,
            direction='long',
            buy_level=level,
            buy_price=Decimal(str(price)),
            buy_time=timezone.now(),
            buy_amount=Decimal(str(amount)),
            buy_cost=Decimal(str(cost)),
            buy_zone_weight=Decimal('1.0'),
            stop_loss_price=Decimal(str(grid_levels['support_2']['price'] * 0.97)),  # S2-3%
            sell_target_r1_price=Decimal(str(grid_levels['resistance_1']['price'])),
            sell_target_r1_pct=Decimal('100.00'),  # 100%全平
            sell_target_r1_zone_low=Decimal(str(grid_levels['resistance_1']['price'])),
            sell_target_r1_zone_high=Decimal(str(grid_levels['resistance_1']['price'])),
            sell_target_r2_price=Decimal(str(grid_levels['resistance_2']['price'])),
            sell_target_r2_pct=Decimal('0.00'),
            sell_target_r2_zone_low=Decimal(str(grid_levels['resistance_2']['price'])),
            sell_target_r2_zone_high=Decimal(str(grid_levels['resistance_2']['price']))
        )

        self.current_cash -= cost

        logger.info(
            f"✅ 开多单: {level} @ {price:.2f}, "
            f"数量={amount:.6f}, 成本=${cost:.2f}, "
            f"剩余现金=${self.current_cash:.2f}"
        )

        return position

    def open_short_position(
        self,
        level: str,
        price: float,
        amount: float,
        grid_levels: Dict
    ) -> Optional[GridPosition]:
        """
        开空单（借币卖出）

        Args:
            level: 开仓层级（resistance_1 或 resistance_2）
            price: 开空价格
            amount: 开空数量
            grid_levels: 网格层级信息

        Returns:
            GridPosition对象
        """
        revenue = price * amount * (1 - self.fee_rate)

        # 创建空单仓位
        position = GridPosition.objects.create(
            backtest_result_id=self.backtest_result_id,
            direction='short',
            buy_level=level,  # 记录开空的压力位
            buy_price=Decimal(str(price)),  # 开空价格
            buy_time=timezone.now(),
            buy_amount=Decimal(str(amount)),
            buy_cost=Decimal(str(revenue)),  # 开空收入
            buy_zone_weight=Decimal('1.0'),
            stop_loss_price=Decimal(str(grid_levels['resistance_2']['price'] * 1.03)),  # R2+3%
            sell_target_r1_price=Decimal(str(grid_levels['support_1']['price'])),  # 空单到S1平仓
            sell_target_r1_pct=Decimal('100.00'),  # 100%全平
            sell_target_r1_zone_low=Decimal(str(grid_levels['support_1']['price'])),
            sell_target_r1_zone_high=Decimal(str(grid_levels['support_1']['price'])),
            sell_target_r2_price=Decimal(str(grid_levels['support_2']['price'])),
            sell_target_r2_pct=Decimal('0.00'),
            sell_target_r2_zone_low=Decimal(str(grid_levels['support_2']['price'])),
            sell_target_r2_zone_high=Decimal(str(grid_levels['support_2']['price']))
        )

        self.current_cash += revenue  # 卖币获得资金

        logger.info(
            f"✅ 开空单: {level} @ {price:.2f}, "
            f"数量={amount:.6f}, 收入=${revenue:.2f}, "
            f"剩余现金=${self.current_cash:.2f}"
        )

        return position

    def close_long_position(
        self,
        position: GridPosition,
        price: float,
        amount: float,
        reason: str = 'take_profit'
    ) -> float:
        """
        平多单（卖出）

        Args:
            position: 仓位对象
            price: 卖出价格
            amount: 卖出数量
            reason: 平仓原因（'take_profit' 或 'stop_loss'）

        Returns:
            卖出收入（扣除手续费后）
        """
        revenue = price * amount * (1 - self.fee_rate)

        position.total_sold_amount += Decimal(str(amount))
        position.total_revenue += Decimal(str(revenue))

        remaining = position.buy_amount - position.total_sold_amount
        if remaining <= Decimal('0.00000001'):  # 全部卖完
            position.total_sold_amount = position.buy_amount  # 确保精确为0
            position.status = 'closed'
        else:
            position.status = 'partial'

        # 计算盈亏
        position.pnl = position.total_revenue - position.buy_cost
        position.save()

        self.current_cash += revenue

        logger.info(
            f"✅ 平多单: position#{position.id}, "
            f"{reason}, 价格={price:.2f}, "
            f"数量={amount:.6f}, 收入=${revenue:.2f}, "
            f"盈亏=${float(position.pnl):.2f}"
        )

        return revenue

    def close_short_position(
        self,
        position: GridPosition,
        price: float,
        amount: float,
        reason: str = 'take_profit'
    ) -> float:
        """
        平空单（买入还债）

        Args:
            position: 仓位对象
            price: 买入价格
            amount: 买入数量
            reason: 平仓原因（'take_profit' 或 'stop_loss'）

        Returns:
            买入成本（含手续费）
        """
        cost = price * amount * (1 + self.fee_rate)

        position.total_sold_amount += Decimal(str(amount))
        position.total_revenue += Decimal(str(cost))  # 记录平仓成本

        remaining = position.buy_amount - position.total_sold_amount
        if remaining <= Decimal('0.00000001'):  # 全部平仓
            position.total_sold_amount = position.buy_amount  # 确保精确为0
            position.status = 'closed'
        else:
            position.status = 'partial'

        # 空单盈亏 = 开仓收入 - 平仓成本
        position.pnl = position.buy_cost - position.total_revenue
        position.save()

        self.current_cash -= cost  # 买入扣除现金

        logger.info(
            f"✅ 平空单: position#{position.id}, "
            f"{reason}, 价格={price:.2f}, "
            f"数量={amount:.6f}, 成本=${cost:.2f}, "
            f"盈亏=${float(position.pnl):.2f}"
        )

        return cost

    def get_long_positions(self):
        """获取所有多单（包括持仓中和已平仓）"""
        return GridPosition.objects.filter(
            backtest_result_id=self.backtest_result_id,
            direction='long'
        )

    def get_short_positions(self):
        """获取所有空单（包括持仓中和已平仓）"""
        return GridPosition.objects.filter(
            backtest_result_id=self.backtest_result_id,
            direction='short'
        )

    def get_open_long_positions(self):
        """获取持仓中的多单"""
        return self.get_long_positions().filter(status__in=['open', 'partial'])

    def get_open_short_positions(self):
        """获取持仓中的空单"""
        return self.get_short_positions().filter(status__in=['open', 'partial'])

    def get_account_value(self, current_price: float) -> float:
        """
        计算账户总价值

        Args:
            current_price: 当前币价

        Returns:
            账户总价值 = 现金 + 多单价值 + 空单价值
        """
        # 多单价值
        long_value = sum(
            float(pos.buy_amount - pos.total_sold_amount) * current_price
            for pos in self.get_open_long_positions()
        )

        # 空单价值（负债）
        # 空单价值 = 持仓量 * (2 * 开仓价 - 当前价)
        short_value = sum(
            float(pos.buy_amount - pos.total_sold_amount) * (2 * float(pos.buy_price) - current_price)
            for pos in self.get_open_short_positions()
        )

        total_value = self.current_cash + long_value + short_value

        return total_value

    @property
    def remaining(self) -> Decimal:
        """获取多单持仓总数量（兼容接口）"""
        total = sum(
            pos.buy_amount - pos.total_sold_amount
            for pos in self.get_open_long_positions()
        )
        return total if total else Decimal('0')
