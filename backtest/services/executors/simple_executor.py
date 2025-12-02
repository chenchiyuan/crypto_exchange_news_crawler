"""
简单执行器
在支撑位zone_high买满，在压力位zone_low卖光
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict

from backtest.models import GridPosition
from backtest.services.position_manager import PositionManager
from backtest.services.dynamic_grid_calculator import GridLevels
from .base import BaseExecutor

logger = logging.getLogger(__name__)


class SimpleExecutor(BaseExecutor):
    """简单执行器 - 支撑位上界买满，压力位下界卖光"""

    def execute_buy(
        self,
        level_name: str,
        current_price: float,
        current_time: datetime,
        level_info: Dict[str, float],
        grid_levels: GridLevels
    ) -> Optional[float]:
        """
        执行买入（一次买满）

        买入逻辑：
        - 触发条件：价格 >= zone_high（支撑位上界）
        - 买入金额：100%可用金额（一次买满）

        示例：
            支撑位: 2000 - 2100
            当前价格: 2100
            可用金额: 2000 USDT
            → 买入 2000 USDT（买满）

        Args:
            level_name: 'support_1' / 'support_2'
            current_price: 当前价格
            current_time: 当前时间
            level_info: {'zone_low': 2000, 'zone_high': 2100}
            grid_levels: 完整网格信息

        Returns:
            买入金额（USDT），如果无法买入返回None
        """
        # 1. 触发条件检查：价格必须 <= zone_high（在支撑位上界或以下）
        zone_high = level_info['zone_high']
        if current_price > zone_high:
            logger.debug(
                f"{level_name}未触发买入: "
                f"价格{current_price:.2f} > zone_high {zone_high:.2f}"
            )
            return None

        # 2. 检查可用金额
        available = self.position_manager.get_available_buy_amount(level_name)

        if available <= 10.0:  # 至少10 USDT
            logger.debug(f"{level_name}可用金额不足: {available:.2f}")
            return None

        # 3. 一次买满（100%可用金额）
        buy_amount_usdt = available

        # 4. 扣除手续费
        fee = self._calculate_fee(buy_amount_usdt)
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
            buy_zone_weight=1.0,  # 简单模式固定为100%
            grid_levels=grid_levels,
            stop_loss_pct=self.stop_loss_pct
        )

        logger.info(
            f"\033[92m⬆ 买入成功\033[0m（简单模式）: {level_name} @ zone_high "
            f"价格={current_price:.2f}, "
            f"金额={buy_amount_usdt:.2f} USDT (买满), "
            f"数量={buy_amount_eth:.6f} ETH, "
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
        执行限价单卖出（一次卖光）

        卖出逻辑：
        - 触发条件：价格 >= 目标价（R1/R2挂单价）
        - 卖出数量：100%剩余持仓（一次卖光）
        - 类比：交易所挂单成交

        示例：
            R1目标价: 2300
            当前价格: 2350
            剩余持仓: 1.0 ETH
            → 挂单成交，卖出 1.0 ETH（卖光）

        Args:
            position: 仓位对象
            target_level: 'resistance_1' / 'resistance_2'
            current_price: 当前价格
            current_time: 当前时间

        Returns:
            卖出收入（USDT），如果无法卖出返回None
        """
        # 1. 获取目标价格
        if target_level == 'resistance_1':
            target_price = float(position.sell_target_r1_price)
        elif target_level == 'resistance_2':
            target_price = float(position.sell_target_r2_price)
        else:
            logger.warning(f"未知压力位层级: {target_level}")
            return None

        # 2. 触发条件检查：价格必须 >= 目标价（限价单成交条件）
        if current_price < target_price:
            logger.debug(
                f"仓位{position.id} {target_level}未触发卖出: "
                f"价格{current_price:.2f} < 目标价{target_price:.2f}"
            )
            return None

        # 3. 计算剩余持仓
        buy_amount = float(position.buy_amount)
        total_sold = float(position.total_sold_amount)
        remaining = buy_amount - total_sold

        if remaining <= 0.0001:
            logger.debug(f"仓位{position.id}已无剩余持仓")
            return None

        # 4. 一次卖光（100%剩余持仓）
        sell_amount = remaining

        # 5. 计算卖出收入
        sell_revenue_before_fee = sell_amount * current_price
        fee = self._calculate_fee(sell_revenue_before_fee)
        sell_revenue = sell_revenue_before_fee - fee

        # 6. 更新仓位记录
        position.total_sold_amount = position.buy_amount  # 全部卖出
        position.total_revenue += Decimal(str(sell_revenue))
        position.pnl = position.total_revenue - position.buy_cost
        position.status = 'closed'  # 状态改为已平仓
        position.save()

        # 7. 增加现金
        self.position_manager.update_cash(sell_revenue)

        logger.info(
            f"\033[91m⬇ 限价单成交\033[0m（简单模式）: 仓位{position.id} {target_level} "
            f"挂单价={target_price:.2f}, "
            f"成交价={current_price:.2f}, "
            f"数量={sell_amount:.6f} ETH (卖光), "
            f"收入={sell_revenue:.2f} USDT, "
            f"手续费={fee:.2f}, "
            f"盈亏={float(position.pnl):.2f}"
        )

        return sell_revenue
