"""
挂单管理器
管理挂单的创建、成交和过期
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List

from backtest.models import PendingOrder, GridPosition
from backtest.services.dynamic_grid_calculator import GridLevels
from backtest.services.position_manager import PositionManager

logger = logging.getLogger(__name__)


class PendingOrderManager:
    """挂单管理器 - Grid V3"""

    def __init__(
        self,
        backtest_result_id: int,
        position_manager: PositionManager,
        order_validity_days: int = 3,
        stop_loss_pct: float = 0.03,
        fee_rate: float = 0.001
    ):
        """
        初始化挂单管理器

        Args:
            backtest_result_id: 回测结果ID
            position_manager: 仓位管理器实例
            order_validity_days: 挂单有效期（天）
            stop_loss_pct: 止损百分比
            fee_rate: 手续费率
        """
        self.backtest_result_id = backtest_result_id
        self.position_manager = position_manager
        self.order_validity_days = order_validity_days
        self.stop_loss_pct = stop_loss_pct
        self.fee_rate = fee_rate

        logger.info(
            f"挂单管理器初始化: "
            f"有效期={order_validity_days}天, "
            f"止损={stop_loss_pct*100}%, "
            f"手续费={fee_rate*100}%"
        )

    def create_buy_order(
        self,
        grid_level: str,
        target_price: float,
        zone_low: float,
        zone_high: float,
        current_time: datetime
    ) -> Optional[PendingOrder]:
        """
        创建买入挂单（带资金锁定）

        流程：
        1. 计算可用资金（已考虑理论上限、持仓、挂单锁定）
        2. 确定挂单金额
        3. 创建挂单，标记资金为locked
        4. ✨ 关键：不扣除current_cash（因为还未成交）

        Args:
            grid_level: 'support_1' / 'support_2'
            target_price: 挂单目标价格
            zone_low: 区间下界
            zone_high: 区间上界
            current_time: 当前时间

        Returns:
            PendingOrder对象，如果资金不足返回None
        """
        # 1. 计算可用金额（已经考虑了锁定资金）
        available = self.position_manager.get_available_buy_amount(grid_level)

        if available < 10.0:
            logger.debug(f"{grid_level}可用资金不足: {available:.2f}")
            return None

        # 2. 确定挂单金额（Simple模式：全部挂单）
        order_amount = available

        # 3. 创建挂单
        expire_time = current_time + timedelta(days=self.order_validity_days)

        order = PendingOrder.objects.create(
            backtest_result_id=self.backtest_result_id,
            order_type='buy',
            grid_level=grid_level,
            target_price=Decimal(str(target_price)),
            zone_low=Decimal(str(zone_low)),
            zone_high=Decimal(str(zone_high)),
            locked_amount_usdt=Decimal(str(order_amount)),  # ✨ 锁定金额
            created_time=current_time,
            expire_time=expire_time,
            status='pending',
            fund_status='locked'  # ✨ 标记为锁定
        )

        # ✨ 注意：不扣除current_cash！
        # 资金只是"锁定"，还没有真正花出去

        logger.info(
            f"✨ 创建买入挂单: {grid_level} @ {target_price:.2f}, "
            f"锁定金额={order_amount:.2f}, "
            f"有效期至={expire_time.date()}"
        )

        return order

    def fill_buy_order(
        self,
        order: PendingOrder,
        current_price: float,
        current_time: datetime,
        grid_levels: GridLevels
    ) -> Optional[GridPosition]:
        """
        挂单成交处理

        流程：
        1. 执行买入（创建仓位）
        2. ✨ 扣除current_cash（资金从locked → invested）
        3. 更新挂单状态为filled
        4. 释放资金锁定

        Args:
            order: 待成交的挂单
            current_price: 当前价格
            current_time: 当前时间
            grid_levels: 当前网格（用于计算止盈目标）

        Returns:
            创建的GridPosition对象
        """
        # 1. 执行买入
        locked_amount = float(order.locked_amount_usdt)
        fee = locked_amount * self.fee_rate
        actual_buy_usdt = locked_amount - fee
        buy_amount_eth = actual_buy_usdt / current_price

        # 2. 创建仓位
        position = self.position_manager.create_position(
            buy_level=order.grid_level,
            buy_price=current_price,
            buy_time=current_time,
            buy_amount_usdt=locked_amount,
            buy_amount_eth=buy_amount_eth,
            buy_zone_weight=1.0,
            grid_levels=grid_levels,
            stop_loss_pct=self.stop_loss_pct
        )

        # 注意：create_position已经扣除了current_cash

        # 3. 更新挂单状态
        order.status = 'filled'
        order.fund_status = 'released'  # ✨ 锁定已释放（转为投入）
        order.filled_time = current_time
        order.filled_price = Decimal(str(current_price))
        order.filled_amount = Decimal(str(locked_amount))
        order.created_position = position
        order.save()

        logger.info(
            f"✅ 挂单成交: {order.grid_level} @ {current_price:.2f}, "
            f"挂单价={float(order.target_price):.2f}, "
            f"金额={locked_amount:.2f}, "
            f"锁定→投入，剩余现金={self.position_manager.current_cash:.2f}"
        )

        return position

    def check_and_fill_orders(
        self,
        current_price: float,
        current_time: datetime,
        grid_levels: GridLevels
    ) -> List[GridPosition]:
        """
        检查挂单是否触发成交

        逻辑：
        1. 查询所有pending状态的买入挂单
        2. 检查：price <= target_price（价格跌到挂单价）
        3. 触发后执行成交，更新挂单状态

        Args:
            current_price: 当前价格
            current_time: 当前时间
            grid_levels: 当前网格

        Returns:
            成交创建的仓位列表
        """
        # 买入挂单触发检查
        buy_orders = PendingOrder.objects.filter(
            backtest_result_id=self.backtest_result_id,
            order_type='buy',
            status='pending',
            target_price__gte=current_price,  # 价格跌到挂单价
            expire_time__gt=current_time  # 未过期
        )

        positions = []
        for order in buy_orders:
            position = self.fill_buy_order(
                order=order,
                current_price=current_price,
                current_time=current_time,
                grid_levels=grid_levels
            )
            if position:
                positions.append(position)

        return positions

    def expire_orders(self, current_time: datetime):
        """
        过期挂单处理

        流程：
        1. 查询过期的pending挂单
        2. ✨ 释放锁定资金（资金回到可用状态）
        3. 更新挂单状态

        Args:
            current_time: 当前时间
        """
        expired = PendingOrder.objects.filter(
            backtest_result_id=self.backtest_result_id,
            status='pending',
            fund_status='locked',
            expire_time__lte=current_time
        )

        count = 0
        for order in expired:
            # ✨ 释放锁定资金（不需要增加current_cash，因为从未扣除）
            order.status = 'expired'
            order.fund_status = 'released'
            order.save()

            logger.info(
                f"🗑 挂单过期: {order.grid_level} @ {float(order.target_price):.2f}, "
                f"释放锁定资金={float(order.locked_amount_usdt):.2f}"
            )
            count += 1

        if count > 0:
            logger.info(f"清理过期挂单: {count}个")

    def has_pending_order(self, grid_level: str, current_time: datetime) -> bool:
        """
        检查某个网格层级是否已有未过期的挂单

        Args:
            grid_level: 网格层级
            current_time: 当前时间

        Returns:
            True表示已有挂单，False表示无挂单
        """
        return PendingOrder.objects.filter(
            backtest_result_id=self.backtest_result_id,
            order_type='buy',
            grid_level=grid_level,
            status='pending',
            expire_time__gt=current_time
        ).exists()
