"""
仓位管理器
管理独立仓位、现金约束和理论上限
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from django.db.models import Sum, Q, F

from backtest.models import GridPosition
from backtest.services.dynamic_grid_calculator import GridLevels

logger = logging.getLogger(__name__)


class PositionManager:
    """仓位管理器 - 独立仓位 + 现金约束"""

    def __init__(
        self,
        backtest_result_id: int,
        initial_cash: float,
        support_1_max_pct: float = 0.20,
        support_2_max_pct: float = 0.30
    ):
        """
        初始化仓位管理器

        Args:
            backtest_result_id: 回测结果ID
            initial_cash: 初始资金
            support_1_max_pct: 支撑位1最大投入比例（默认20%）
            support_2_max_pct: 支撑位2最大投入比例（默认30%）
        """
        self.backtest_result_id = backtest_result_id
        self.initial_cash = initial_cash
        self.current_cash = initial_cash

        # 理论上限
        self.support_1_max = initial_cash * support_1_max_pct
        self.support_2_max = initial_cash * support_2_max_pct

        logger.info(
            f"仓位管理器初始化: "
            f"初始资金={initial_cash:.2f}, "
            f"支撑1上限={self.support_1_max:.2f}, "
            f"支撑2上限={self.support_2_max:.2f}"
        )

    def get_locked_in_pending_orders(self, grid_level: Optional[str] = None) -> float:
        """
        查询锁定在pending挂单中的资金

        Args:
            grid_level: 如果指定，只查询该层级的锁定资金

        Returns:
            锁定金额（USDT）
        """
        from backtest.models import PendingOrder

        query = PendingOrder.objects.filter(
            backtest_result_id=self.backtest_result_id,
            order_type='buy',
            status='pending',
            fund_status='locked'
        )

        if grid_level:
            query = query.filter(grid_level=grid_level)

        locked = query.aggregate(
            total=Sum('locked_amount_usdt')
        )['total'] or Decimal('0')

        return float(locked)

    def get_available_buy_amount(self, grid_level: str) -> float:
        """
        计算某个网格层级的可用买入金额（增强版）

        考虑三重约束：
        1. 理论上限（support_1_max, support_2_max）
        2. 已投入仓位
        3. 锁定在pending挂单中的资金 ✨

        Args:
            grid_level: 'support_1' / 'support_2'

        Returns:
            可用金额（USDT），已考虑理论上限、现金约束和挂单锁定
        """
        # 1. 确定理论上限
        if grid_level == 'support_1':
            theoretical_max = self.support_1_max
        elif grid_level == 'support_2':
            theoretical_max = self.support_2_max
        else:
            logger.warning(f"未知网格层级: {grid_level}")
            return 0.0

        # 2. 查询该层级已投入金额（未平仓或部分平仓的）
        already_invested = GridPosition.objects.filter(
            backtest_result_id=self.backtest_result_id,
            buy_level=grid_level,
            status__in=['open', 'partial']
        ).aggregate(
            total=Sum('buy_cost')
        )['total'] or Decimal('0')

        already_invested = float(already_invested)

        # 3. ✨ 查询该层级锁定在挂单中的金额
        locked = self.get_locked_in_pending_orders(grid_level)

        # 4. 计算理论剩余额度
        theoretical_available = theoretical_max - already_invested - locked

        if theoretical_available <= 0:
            logger.debug(
                f"{grid_level}已达理论上限或资金已锁定: "
                f"上限={theoretical_max:.2f}, "
                f"已投入={already_invested:.2f}, "
                f"已锁定={locked:.2f}"
            )
            return 0.0

        # 5. 查询全局锁定资金
        total_locked = self.get_locked_in_pending_orders()  # 所有层级

        # 6. 三重约束: min(理论剩余, 实际现金 - 全局锁定)
        actual_available = self.current_cash - total_locked
        available = min(theoretical_available, actual_available)

        logger.debug(
            f"{grid_level}可用金额: "
            f"理论剩余={theoretical_available:.2f}, "
            f"现金={self.current_cash:.2f}, "
            f"全局锁定={total_locked:.2f}, "
            f"实际可用={actual_available:.2f}, "
            f"最终可用={available:.2f}"
        )

        return max(0.0, available)

    def create_position(
        self,
        buy_level: str,
        buy_price: float,
        buy_time: datetime,
        buy_amount_usdt: float,
        buy_amount_eth: float,
        buy_zone_weight: float,
        grid_levels: GridLevels,
        stop_loss_pct: float = 0.03
    ) -> GridPosition:
        """
        创建新仓位

        Args:
            buy_level: 'support_1' / 'support_2'
            buy_price: 买入价格
            buy_time: 买入时间
            buy_amount_usdt: 买入金额（USDT，含手续费）
            buy_amount_eth: 买入数量（ETH）
            buy_zone_weight: 买入权重（0.05-1.0）
            grid_levels: 当前网格（用于记录卖出目标）

        Returns:
            GridPosition对象
        """
        # 确定止盈比例
        if buy_level == 'support_1':
            r1_pct = 50.0
            r2_pct = 50.0
        elif buy_level == 'support_2':
            r1_pct = 70.0
            r2_pct = 30.0
        else:
            raise ValueError(f"未知买入层级: {buy_level}")

        # ⭐⭐⭐ 计算止损价格（处理support_2可能为None的情况）
        if grid_levels.support_2 is not None:
            # 标准情况：使用support_2的下界
            stop_loss_base = grid_levels.support_2.zone_low
        elif grid_levels.support_1 is not None:
            # 边界情况：只有support_1，使用其下界
            stop_loss_base = grid_levels.support_1.zone_low
        else:
            # 极端情况：没有支撑位，使用买入价
            stop_loss_base = buy_price

        stop_loss_price = stop_loss_base * (1 - stop_loss_pct)

        # ⭐⭐⭐ 准备R1目标（处理resistance_1可能为None的情况）
        if grid_levels.resistance_1 is not None:
            r1_price = Decimal(str(grid_levels.resistance_1.price))
            r1_zone_low = Decimal(str(grid_levels.resistance_1.zone_low))
            r1_zone_high = Decimal(str(grid_levels.resistance_1.zone_high))
        else:
            # 没有R1：设置为买入价的110%作为默认目标
            r1_price = Decimal(str(buy_price * 1.10))
            r1_zone_low = Decimal(str(buy_price * 1.08))
            r1_zone_high = Decimal(str(buy_price * 1.12))
            logger.warning(
                f"⚠️ 无压力位R1，使用默认目标: {r1_price:.2f}"
            )

        # ⭐⭐⭐ 准备R2目标（处理resistance_2可能为None的情况）
        if grid_levels.resistance_2 is not None:
            r2_price = Decimal(str(grid_levels.resistance_2.price))
            r2_zone_low = Decimal(str(grid_levels.resistance_2.zone_low))
            r2_zone_high = Decimal(str(grid_levels.resistance_2.zone_high))
        else:
            # 没有R2：设置为买入价的120%作为默认目标
            r2_price = Decimal(str(buy_price * 1.20))
            r2_zone_low = Decimal(str(buy_price * 1.18))
            r2_zone_high = Decimal(str(buy_price * 1.22))
            logger.warning(
                f"⚠️ 无压力位R2，使用默认目标: {r2_price:.2f}"
            )

        # 创建仓位记录
        position = GridPosition.objects.create(
            backtest_result_id=self.backtest_result_id,
            buy_level=buy_level,
            buy_price=Decimal(str(buy_price)),
            buy_time=buy_time,
            buy_amount=Decimal(str(buy_amount_eth)),
            buy_cost=Decimal(str(buy_amount_usdt)),
            buy_zone_weight=Decimal(str(buy_zone_weight)),
            stop_loss_price=Decimal(str(stop_loss_price)),
            # 压力位1目标
            sell_target_r1_price=r1_price,
            sell_target_r1_pct=Decimal(str(r1_pct)),
            sell_target_r1_sold=Decimal('0'),
            sell_target_r1_zone_low=r1_zone_low,
            sell_target_r1_zone_high=r1_zone_high,
            # 压力位2目标
            sell_target_r2_price=r2_price,
            sell_target_r2_pct=Decimal(str(r2_pct)),
            sell_target_r2_sold=Decimal('0'),
            sell_target_r2_zone_low=r2_zone_low,
            sell_target_r2_zone_high=r2_zone_high,
            # 初始状态
            total_sold_amount=Decimal('0'),
            total_revenue=Decimal('0'),
            pnl=Decimal('0'),
            status='open'
        )

        # 扣除现金
        self.current_cash -= buy_amount_usdt

        logger.info(
            f"创建仓位: {buy_level} "
            f"买入={buy_amount_eth:.4f} ETH @ {buy_price:.2f}, "
            f"成本={buy_amount_usdt:.2f}, "
            f"目标R1={float(r1_price):.2f}({r1_pct}%), "
            f"目标R2={float(r2_price):.2f}({r2_pct}%), "
            f"剩余现金={self.current_cash:.2f}"
        )

        return position

    def get_positions_to_sell(
        self,
        current_price: float,
        target_level: str  # 'resistance_1' / 'resistance_2'
    ) -> List[GridPosition]:
        """
        查询需要卖出的仓位（限价单触发模型）

        逻辑：
        - 价格 >= R1目标价 → 触发R1卖出（类比：挂单成交）
        - 价格 >= R2目标价 → 触发R2卖出
        - 不要求价格在zone区间内，只要触及或超过目标价即触发

        Args:
            current_price: 当前价格
            target_level: 'resistance_1' / 'resistance_2'

        Returns:
            价格触及目标价且该层级未卖完的仓位列表
        """
        if target_level == 'resistance_1':
            # ✅ 修复：只要价格 >= R1目标价，就触发卖出
            positions = GridPosition.objects.filter(
                backtest_result_id=self.backtest_result_id,
                status__in=['open', 'partial'],
                sell_target_r1_price__lte=current_price  # 价格触及或超过R1目标
            ).exclude(
                # 排除R1已全部卖完的仓位
                sell_target_r1_sold__gte=F('buy_amount') * F('sell_target_r1_pct') / 100
            )
        elif target_level == 'resistance_2':
            # ✅ 修复：只要价格 >= R2目标价，就触发卖出
            positions = GridPosition.objects.filter(
                backtest_result_id=self.backtest_result_id,
                status__in=['open', 'partial'],
                sell_target_r2_price__lte=current_price  # 价格触及或超过R2目标
            ).exclude(
                # 排除R2已全部卖完的仓位
                sell_target_r2_sold__gte=F('buy_amount') * F('sell_target_r2_pct') / 100
            )
        else:
            logger.warning(f"未知压力位层级: {target_level}")
            return []

        return list(positions)

    def get_all_open_positions(self) -> List[GridPosition]:
        """获取所有未平仓的仓位"""
        return list(
            GridPosition.objects.filter(
                backtest_result_id=self.backtest_result_id,
                status__in=['open', 'partial']
            )
        )

    def update_cash(self, amount: float):
        """
        更新现金余额

        Args:
            amount: 变化金额（正数=增加，负数=减少）
        """
        self.current_cash += amount

        if self.current_cash < 0:
            logger.warning(f"现金余额为负: {self.current_cash:.2f}")

    def get_cash_balance(self) -> float:
        """获取当前现金余额"""
        return self.current_cash

    def get_total_position_value(self, current_price: float) -> float:
        """
        计算当前持仓总价值

        Args:
            current_price: 当前价格

        Returns:
            持仓总价值（USDT）
        """
        positions = self.get_all_open_positions()

        total_value = 0.0
        for pos in positions:
            remaining = float(pos.buy_amount - pos.total_sold_amount)
            total_value += remaining * current_price

        return total_value

    def get_account_value(self, current_price: float) -> float:
        """
        计算账户总价值（现金 + 持仓）

        Args:
            current_price: 当前价格

        Returns:
            账户总价值（USDT）
        """
        return self.current_cash + self.get_total_position_value(current_price)
