"""
限价卖出条件

Purpose:
    限价挂单策略的卖出条件，计算卖出价格并判断是否成交。
    卖出价格 = min(买入价×(1+take_profit_rate), EMA25)

关联迭代: 027 (策略11-限价挂单买卖机制)
关联任务: TASK-027-005
关联功能点: FP-027-012, FP-027-013, FP-027-014, FP-027-015

Classes:
    - LimitOrderExit: 限价卖出条件
"""

import logging
from decimal import Decimal
from typing import Optional, Dict, Any

from strategy_adapter.exits.base import IExitCondition, ExitSignal
from strategy_adapter.core.limit_order_price_calculator import LimitOrderPriceCalculator

logger = logging.getLogger(__name__)


class LimitOrderExit(IExitCondition):
    """
    限价卖出条件

    计算卖出挂单价格并判断是否成交。
    - 正常情况：卖出价格 = min(买入价×(1+take_profit_rate), EMA25)
    - 防亏损：如果正常卖出价格 < 买入价，则：
      卖出价格 = min(EMA25×(1+min_profit_rate), 买入价×(1+commission_rate))
    - 成交条件: low <= 卖出价 <= high

    与传统Exit条件的区别：
    - 传统Exit：检查条件是否满足，满足则以该价格成交
    - LimitOrderExit：先计算挂单价格，再判断该价格是否在K线范围内

    Attributes:
        take_profit_rate: 止盈比例，默认0.05（5%）
        ema_period: EMA周期，默认25
        commission_rate: 手续费率，默认0.001（0.1%）
        min_profit_rate: 保底收益率，默认0.02（2%）
        price_calculator: 价格计算器
    """

    def __init__(
        self,
        take_profit_rate: float = 0.05,
        ema_period: int = 25,
        commission_rate: float = 0.001,
        min_profit_rate: float = 0.02
    ):
        """
        初始化限价卖出条件

        Args:
            take_profit_rate: 止盈比例，默认0.05（5%）
            ema_period: EMA周期，默认25
            commission_rate: 手续费率，默认0.001（0.1%）
            min_profit_rate: 保底收益率，默认0.02（2%），防亏损时EMA的加成比例
        """
        self.take_profit_rate = take_profit_rate
        self.ema_period = ema_period
        self.commission_rate = commission_rate
        self.min_profit_rate = min_profit_rate
        self._indicator_key = f"ema{ema_period}"
        self.price_calculator = LimitOrderPriceCalculator()

    def check(
        self,
        order: 'Order',
        kline: Dict[str, Any],
        indicators: Dict[str, Any],
        current_timestamp: int
    ) -> Optional[ExitSignal]:
        """
        检查卖出挂单是否成交

        计算卖出价格 = min(买入价×1.05, EMA25)，
        判断该价格是否在K线的[low, high]范围内。

        Args:
            order: 持仓订单（需要order.open_price）
            kline: K线数据
            indicators: 技术指标（需要ema25）
            current_timestamp: 当前时间戳

        Returns:
            ExitSignal: 如果成交则返回信号，否则返回None
        """
        # 获取EMA值
        ema_value = indicators.get(self._indicator_key)
        if ema_value is None:
            logger.warning(f"指标中缺少{self._indicator_key}")
            return None

        ema_value = Decimal(str(ema_value))
        buy_price = order.open_price

        # 计算卖出价格（含防亏损逻辑）
        sell_price = self.price_calculator.calculate_sell_price(
            buy_price=buy_price,
            ema25=ema_value,
            take_profit_rate=self.take_profit_rate,
            commission_rate=self.commission_rate,
            min_profit_rate=self.min_profit_rate
        )

        # 获取K线价格范围
        low = Decimal(str(kline['low']))
        high = Decimal(str(kline['high']))

        # 成交条件: low <= 卖出价 <= high
        if low <= sell_price <= high:
            # 判断触发类型
            take_profit_price = buy_price * (Decimal("1") + Decimal(str(self.take_profit_rate)))
            normal_sell_price = min(take_profit_price, ema_value)

            # 判断是否触发了防亏损逻辑
            if normal_sell_price < buy_price:
                # 防亏损触发
                ema_floor = ema_value * (Decimal("1") + Decimal(str(self.min_profit_rate)))
                commission_floor = buy_price * (Decimal("1") + Decimal(str(self.commission_rate)))
                if sell_price == ema_floor:
                    reason = f"限价卖出: 防亏损(EMA+{self.min_profit_rate*100:.1f}%) ({sell_price:.2f})"
                else:
                    reason = f"限价卖出: 防亏损(成本+手续费) ({sell_price:.2f})"
            elif sell_price == ema_value:
                reason = f"限价卖出: EMA{self.ema_period}回归 ({sell_price:.2f})"
            else:
                reason = f"限价卖出: {self.take_profit_rate*100:.1f}%止盈 ({sell_price:.2f})"

            return ExitSignal(
                timestamp=current_timestamp,
                price=sell_price,
                reason=reason,
                exit_type=self.get_type()
            )

        return None

    def calculate_sell_price(
        self,
        buy_price: Decimal,
        ema_value: Decimal
    ) -> Decimal:
        """
        计算卖出价格（便捷方法）

        用于策略中获取挂单价格，而不进行成交判断。
        包含防亏损逻辑。

        Args:
            buy_price: 买入价格
            ema_value: 当前EMA25值

        Returns:
            Decimal: 卖出挂单价格（含防亏损逻辑）
        """
        return self.price_calculator.calculate_sell_price(
            buy_price=buy_price,
            ema25=ema_value,
            take_profit_rate=self.take_profit_rate,
            commission_rate=self.commission_rate,
            min_profit_rate=self.min_profit_rate
        )

    def get_type(self) -> str:
        return "limit_order_exit"

    def get_priority(self) -> int:
        # 限价卖出优先级较低（让止损等条件优先）
        return 50
