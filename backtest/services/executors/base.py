"""
交易执行器抽象基类
定义所有执行器必须实现的接口
"""
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict, List

from backtest.models import GridPosition
from backtest.services.position_manager import PositionManager
from backtest.services.dynamic_grid_calculator import GridLevels

logger = logging.getLogger(__name__)


class BaseExecutor(ABC):
    """交易执行器抽象基类"""

    def __init__(
        self,
        position_manager: PositionManager,
        fee_rate: float = 0.001,
        stop_loss_pct: float = 0.03
    ):
        """
        初始化执行器

        Args:
            position_manager: 仓位管理器
            fee_rate: 手续费率（默认0.1%）
            stop_loss_pct: 止损百分比（默认3%）
        """
        self.position_manager = position_manager
        self.fee_rate = fee_rate
        self.stop_loss_pct = stop_loss_pct

        logger.info(
            f"{self.__class__.__name__}初始化: "
            f"手续费={fee_rate*100:.2f}%, "
            f"止损={stop_loss_pct*100:.1f}%"
        )

    @abstractmethod
    def execute_buy(
        self,
        level_name: str,
        current_price: float,
        current_time: datetime,
        level_info: Dict[str, float],
        grid_levels: GridLevels
    ) -> Optional[float]:
        """
        执行买入

        Args:
            level_name: 'support_1' / 'support_2'
            current_price: 当前价格
            current_time: 当前时间
            level_info: {'zone_low': 2000, 'zone_high': 2100}
            grid_levels: 完整网格信息

        Returns:
            买入金额（USDT），如果无法买入返回None
        """
        pass

    @abstractmethod
    def execute_sell(
        self,
        position: GridPosition,
        target_level: str,
        current_price: float,
        current_time: datetime
    ) -> Optional[float]:
        """
        执行卖出

        Args:
            position: 仓位对象
            target_level: 'resistance_1' / 'resistance_2'
            current_price: 当前价格
            current_time: 当前时间

        Returns:
            卖出收入（USDT），如果无法卖出返回None
        """
        pass

    def execute_stop_loss(
        self,
        positions: List[GridPosition],
        current_price: float,
        current_time: datetime,
        reason: str = "止损"
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
        from decimal import Decimal

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
                f"\033[90m✖ {reason}\033[0m: 仓位{pos.id} "
                f"卖出{remaining_amount:.6f} ETH @ {current_price:.2f}, "
                f"收入={sell_revenue:.2f}, "
                f"亏损={float(pos.pnl):.2f}"
            )

        return total_revenue

    def _calculate_fee(self, amount: float) -> float:
        """计算手续费"""
        return amount * self.fee_rate
