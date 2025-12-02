"""
渐进式交易执行器
实现指数衰减权重函数的渐进式买入/卖出算法
"""
import logging
import math
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict

from backtest.models import GridPosition
from backtest.services.position_manager import PositionManager
from backtest.services.dynamic_grid_calculator import GridLevels

logger = logging.getLogger(__name__)


class ProgressiveExecutor:
    """渐进式交易执行器 - 越接近边界买入/卖出越多"""

    def __init__(
        self,
        position_manager: PositionManager,
        fee_rate: float = 0.001,
        decay_k: float = 3.0,
        stop_loss_pct: float = 0.03
    ):
        """
        初始化渐进式执行器

        Args:
            position_manager: 仓位管理器
            fee_rate: 手续费率（默认0.1%）
            decay_k: 衰减系数（默认3.0）
            stop_loss_pct: 止损百分比（默认3%）
        """
        self.position_manager = position_manager
        self.fee_rate = fee_rate
        self.decay_k = decay_k
        self.stop_loss_pct = stop_loss_pct

        logger.info(
            f"渐进式执行器初始化: "
            f"手续费={fee_rate*100:.2f}%, "
            f"衰减系数={decay_k}, "
            f"止损={stop_loss_pct*100:.1f}%"
        )

    def calculate_buy_weight(
        self,
        current_price: float,
        zone_low: float,
        zone_high: float
    ) -> float:
        """
        计算买入权重（指数衰减函数）

        公式: weight = exp(-k * distance_pct)
        越接近zone_low（支撑位底部），权重越大（买入越多）
        越接近zone_high（支撑位顶部），权重越小（买入越少）

        Args:
            current_price: 当前价格
            zone_low: 区间下界
            zone_high: 区间上界

        Returns:
            权重 0.0 ~ 1.0（完全由价格位置决定，无人为限制）
        """
        # 计算距离下界的百分比（0=底部, 1=顶部）
        distance_pct = (current_price - zone_low) / (zone_high - zone_low)
        distance_pct = max(0.0, min(1.0, distance_pct))

        # 指数衰减：越接近底部权重越大
        weight = math.exp(-self.decay_k * distance_pct)

        # 只限制最大值为1.0，不设最小值限制
        # 权重完全由价格位置自然决定
        return min(1.0, weight)

    def calculate_sell_weight(
        self,
        current_price: float,
        zone_low: float,
        zone_high: float
    ) -> float:
        """
        计算卖出权重（反向指数衰减函数）

        公式: weight = exp(-k * (1 - distance_pct))
        越接近zone_high（压力位顶部），权重越大（卖出越多）
        越接近zone_low（压力位底部），权重越小（卖出越少）

        Args:
            current_price: 当前价格
            zone_low: 区间下界
            zone_high: 区间上界

        Returns:
            权重 0.0 ~ 1.0（完全由价格位置决定，无人为限制）
        """
        # 计算距离下界的百分比（0=底部, 1=顶部）
        distance_pct = (current_price - zone_low) / (zone_high - zone_low)
        distance_pct = max(0.0, min(1.0, distance_pct))

        # 反向指数衰减：越接近顶部权重越大
        weight = math.exp(-self.decay_k * (1 - distance_pct))

        # 只限制最大值为1.0，不设最小值限制
        # 权重完全由价格位置自然决定
        return min(1.0, weight)

    def execute_buy(
        self,
        level_name: str,
        current_price: float,
        current_time: datetime,
        level_info: Dict[str, float],
        grid_levels: GridLevels
    ) -> Optional[float]:
        """
        执行渐进式买入

        Args:
            level_name: 'support_1' / 'support_2'
            current_price: 当前价格
            current_time: 当前时间
            level_info: {'zone_low': 2880, 'zone_high': 2920}
            grid_levels: 完整网格信息（用于记录卖出目标）

        Returns:
            买入金额（USDT），如果无法买入返回None
        """
        # 1. 检查可用金额
        available = self.position_manager.get_available_buy_amount(level_name)

        if available <= 10.0:  # 至少10 USDT
            logger.debug(f"{level_name}可用金额不足: {available:.2f}")
            return None

        # 2. 计算买入权重
        weight = self.calculate_buy_weight(
            current_price=current_price,
            zone_low=level_info['zone_low'],
            zone_high=level_info['zone_high']
        )

        # 3. 计算本次买入金额
        buy_amount_usdt = available * weight

        if buy_amount_usdt < 10.0:
            logger.debug(
                f"{level_name}买入金额太小: "
                f"可用={available:.2f}, 权重={weight:.2%}, "
                f"买入={buy_amount_usdt:.2f}"
            )
            return None

        # 4. 扣除手续费
        fee = buy_amount_usdt * self.fee_rate
        actual_buy_usdt = buy_amount_usdt - fee

        # 5. 计算买入数量
        buy_amount_eth = actual_buy_usdt / current_price

        # 6. 创建仓位
        position = self.position_manager.create_position(
            buy_level=level_name,
            buy_price=current_price,
            buy_time=current_time,
            buy_amount_usdt=buy_amount_usdt,  # 含手续费
            buy_amount_eth=buy_amount_eth,
            buy_zone_weight=weight,
            grid_levels=grid_levels,
            stop_loss_pct=self.stop_loss_pct
        )

        logger.info(
            f"买入成功: {level_name} "
            f"价格={current_price:.2f}, "
            f"金额={buy_amount_usdt:.2f} USDT, "
            f"数量={buy_amount_eth:.6f} ETH, "
            f"权重={weight:.2%}, "
            f"手续费={fee:.2f}"
        )

        return buy_amount_usdt

    def execute_sell(
        self,
        position: GridPosition,
        target_level: str,
        current_price: float,
        current_time: datetime
    ) -> Optional[float]:
        """
        执行渐进式卖出

        Args:
            position: 仓位对象
            target_level: 'resistance_1' / 'resistance_2'
            current_price: 当前价格
            current_time: 当前时间

        Returns:
            卖出收入（USDT），如果无法卖出返回None
        """
        # 1. 确定目标信息
        if target_level == 'resistance_1':
            target_pct = float(position.sell_target_r1_pct)
            sold_amount = float(position.sell_target_r1_sold)
            zone_low = float(position.sell_target_r1_zone_low)
            zone_high = float(position.sell_target_r1_zone_high)
        elif target_level == 'resistance_2':
            target_pct = float(position.sell_target_r2_pct)
            sold_amount = float(position.sell_target_r2_sold)
            zone_low = float(position.sell_target_r2_zone_low)
            zone_high = float(position.sell_target_r2_zone_high)
        else:
            logger.warning(f"未知压力位层级: {target_level}")
            return None

        # 2. 计算目标数量和剩余数量
        buy_amount = float(position.buy_amount)
        target_amount = buy_amount * (target_pct / 100.0)
        remaining = target_amount - sold_amount

        if remaining <= 0.0001:
            logger.debug(f"仓位{position.id}在{target_level}已卖完")
            return None

        # 3. 计算卖出权重（反向）
        weight = self.calculate_sell_weight(
            current_price=current_price,
            zone_low=zone_low,
            zone_high=zone_high
        )

        # 4. 计算本次卖出数量
        sell_amount = remaining * weight

        if sell_amount < 0.0001:
            return None

        # 5. 计算卖出收入
        sell_revenue_before_fee = sell_amount * current_price
        fee = sell_revenue_before_fee * self.fee_rate
        sell_revenue = sell_revenue_before_fee - fee

        # 6. 更新仓位记录
        if target_level == 'resistance_1':
            position.sell_target_r1_sold = Decimal(str(sold_amount + sell_amount))
        else:
            position.sell_target_r2_sold = Decimal(str(sold_amount + sell_amount))

        position.total_sold_amount += Decimal(str(sell_amount))
        position.total_revenue += Decimal(str(sell_revenue))
        position.pnl = position.total_revenue - position.buy_cost

        # 7. 更新状态
        total_sold_amount = float(position.total_sold_amount)
        if total_sold_amount >= buy_amount * 0.9999:  # 允许微小误差
            position.status = 'closed'
            logger.info(f"仓位{position.id}已全部平仓")
        elif total_sold_amount > 0:
            position.status = 'partial'

        position.save()

        # 8. 增加现金
        self.position_manager.update_cash(sell_revenue)

        logger.info(
            f"卖出成功: 仓位{position.id} {target_level} "
            f"价格={current_price:.2f}, "
            f"数量={sell_amount:.6f} ETH, "
            f"收入={sell_revenue:.2f} USDT, "
            f"权重={weight:.2%}, "
            f"手续费={fee:.2f}, "
            f"剩余={remaining-sell_amount:.6f}"
        )

        return sell_revenue

    def execute_stop_loss(
        self,
        positions: list,
        current_price: float,
        current_time: datetime,
        reason: str = "多头止损"
    ) -> float:
        """
        执行止损（全部平仓）

        Args:
            positions: 仓位列表
            current_price: 当前价格
            current_time: 当前时间
            reason: 止损原因

        Returns:
            总卖出收入（USDT）
        """
        total_revenue = 0.0

        for pos in positions:
            remaining_amount = float(pos.buy_amount - pos.total_sold_amount)

            if remaining_amount <= 0.0001:
                continue

            # 按当前市价卖出
            sell_revenue_before_fee = remaining_amount * current_price
            fee = sell_revenue_before_fee * self.fee_rate
            sell_revenue = sell_revenue_before_fee - fee

            # 更新仓位
            pos.total_sold_amount = pos.buy_amount
            pos.total_revenue += Decimal(str(sell_revenue))
            pos.pnl = pos.total_revenue - pos.buy_cost
            pos.status = 'closed'
            pos.save()

            # 增加现金
            self.position_manager.update_cash(sell_revenue)
            total_revenue += sell_revenue

            logger.warning(
                f"{reason}: 仓位{pos.id} "
                f"卖出{remaining_amount:.6f} ETH @ {current_price:.2f}, "
                f"收入={sell_revenue:.2f}, "
                f"亏损={float(pos.pnl):.2f}"
            )

        return total_revenue
