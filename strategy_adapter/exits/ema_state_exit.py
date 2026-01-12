"""
EMA状态止盈策略

基于EMA7/EMA25/EMA99三线关系判断市场状态，实现状态自适应止盈。

市场状态定义：
- 强势上涨: EMA7 >= EMA25 >= EMA99，止盈于EMA7下穿EMA25
- 强势下跌: EMA7 <= EMA25 <= EMA99，止盈于high突破EMA25
- 震荡下跌: EMA25 < EMA99，止盈于high突破EMA99
- 震荡上涨: EMA25 >= EMA99 且不满足上述条件，挂单止盈2%

关联任务: TASK-035-001
关联功能点: FP-035-002, FP-035-003, FP-035-004
"""

import logging
from decimal import Decimal
from typing import Optional, Dict, Any, TYPE_CHECKING

from strategy_adapter.exits.base import IExitCondition, ExitSignal

if TYPE_CHECKING:
    from strategy_adapter.models.order import Order

logger = logging.getLogger(__name__)


class EmaStateExit(IExitCondition):
    """
    EMA状态止盈策略

    根据EMA7/EMA25/EMA99的相对关系判断市场状态，执行对应的止盈逻辑。

    状态判断：
    - bull_strong: EMA7 >= EMA25 >= EMA99（强势上涨）
    - bear_strong: EMA7 <= EMA25 <= EMA99（强势下跌）
    - consolidation_down: EMA25 < EMA99（震荡下跌）
    - consolidation_up: 其他情况（震荡上涨，挂单止盈）

    止盈逻辑：
    - bull_strong: EMA7下穿EMA25时触发，收盘价标记，下一根开盘价卖出
    - bear_strong: high突破EMA25时触发，收盘价标记，下一根开盘价卖出
    - consolidation_down: high突破EMA99时触发，收盘价标记，下一根开盘价卖出
    - consolidation_up: 挂单止盈，目标价=买入价×(1+2%)，下根K线high>=目标价时成交
    """

    def __init__(self, consolidation_up_take_profit_pct: float = 2.0):
        """
        初始化EMA状态止盈策略

        Args:
            consolidation_up_take_profit_pct: 震荡上涨止盈比例，默认2%
        """
        self.consolidation_up_take_profit_pct = Decimal(str(consolidation_up_take_profit_pct))
        logger.info(
            f"EmaStateExit 初始化完成: 基于EMA状态判断的止盈策略, "
            f"震荡上涨止盈比例={consolidation_up_take_profit_pct}%"
        )

    def check(
        self,
        order: 'Order',
        kline: Dict[str, Any],
        indicators: Dict[str, Any],
        current_timestamp: int
    ) -> Optional[ExitSignal]:
        """
        检查是否触发EMA状态止盈

        Args:
            order: 持仓订单
            kline: 当前K线数据，包含 open, high, low, close
            indicators: 技术指标，必须包含 ema7, ema25, ema99
            current_timestamp: 当前时间戳

        Returns:
            ExitSignal: 如果触发止盈则返回信号，否则返回None
        """
        # 获取EMA指标
        ema7 = indicators.get('ema7')
        ema25 = indicators.get('ema25')
        ema99 = indicators.get('ema99')

        if ema7 is None or ema25 is None or ema99 is None:
            return None

        ema7 = Decimal(str(ema7))
        ema25 = Decimal(str(ema25))
        ema99 = Decimal(str(ema99))
        high = Decimal(str(kline['high']))
        close = Decimal(str(kline['close']))

        # 获取买入价格
        buy_price = Decimal(str(order.open_price))

        # 获取订单当前状态（从metadata中读取）
        ema_cross_triggered = order.metadata.get('ema_cross_triggered', False)
        ema_high_triggered = order.metadata.get('ema_high_triggered', False)

        # === Step 1: 检查是否有待成交的震荡上涨止盈单 ===
        consolidation_up_pending = order.metadata.get('consolidation_up_take_profit_pending', False)
        if consolidation_up_pending:
            target_price = Decimal(str(order.metadata.get('consolidation_up_target_price', 0)))
            if target_price > 0 and high >= target_price:
                # 止盈单成交
                order.metadata['consolidation_up_take_profit_pending'] = False
                logger.info(
                    f"EMA状态止盈成交 [震荡上涨] - 订单ID: {order.id}, "
                    f"High: {high}, 目标价: {target_price}, 买入价: {buy_price}"
                )
                return ExitSignal(
                    timestamp=current_timestamp,
                    price=target_price,  # 以目标价成交
                    reason=f"EMA状态止盈: 震荡上涨，触发{self.consolidation_up_take_profit_pct}%止盈",
                    exit_type=self.get_type()
                )
            # 未成交，清除挂单标记（状态可能已变化，下面会重新判断）
            order.metadata['consolidation_up_take_profit_pending'] = False

        # === Step 2: 判断当前EMA状态 ===
        state = self._get_ema_state(ema7, ema25, ema99)

        # 强势上涨: EMA7 >= EMA25 >= EMA99
        if state == 'bull_strong':
            # 检查EMA7是否下穿EMA25
            if ema7 <= ema25 and not ema_cross_triggered:
                # 标记触发，下一根K线卖出
                order.metadata['ema_cross_triggered'] = True
                logger.info(
                    f"EMA状态止盈触发 [强势上涨] - 订单ID: {order.id}, "
                    f"EMA7: {ema7}, EMA25: {ema25}, 收盘价: {close}"
                )
                return ExitSignal(
                    timestamp=current_timestamp,
                    price=close,  # 收盘价标记
                    reason="EMA状态止盈: 强势上涨，EMA7下穿EMA25",
                    exit_type=self.get_type()
                )

        # 强势下跌: EMA7 <= EMA25 <= EMA99
        elif state == 'bear_strong':
            # 检查high是否突破EMA25
            if high > ema25 and not ema_high_triggered:
                order.metadata['ema_high_triggered'] = True
                logger.info(
                    f"EMA状态止盈触发 [强势下跌] - 订单ID: {order.id}, "
                    f"High: {high}, EMA25: {ema25}, 收盘价: {close}"
                )
                return ExitSignal(
                    timestamp=current_timestamp,
                    price=close,
                    reason="EMA状态止盈: 强势下跌，High突破EMA25",
                    exit_type=self.get_type()
                )

        # 震荡下跌: EMA25 < EMA99
        elif state == 'consolidation_down':
            # 检查high是否突破EMA99
            if high > ema99 and not ema_high_triggered:
                order.metadata['ema_high_triggered'] = True
                logger.info(
                    f"EMA状态止盈触发 [震荡下跌] - 订单ID: {order.id}, "
                    f"High: {high}, EMA99: {ema99}, 收盘价: {close}"
                )
                return ExitSignal(
                    timestamp=current_timestamp,
                    price=close,
                    reason="EMA状态止盈: 震荡下跌，High突破EMA99",
                    exit_type=self.get_type()
                )

        # 震荡上涨: EMA25 >= EMA99 且不满足上述条件
        elif state == 'consolidation_up':
            # 挂止盈单，目标价 = 买入价 × (1 + 止盈比例)
            target_price = buy_price * (1 + self.consolidation_up_take_profit_pct / 100)
            order.metadata['consolidation_up_take_profit_pending'] = True
            order.metadata['consolidation_up_target_price'] = float(target_price)
            logger.debug(
                f"EMA状态止盈挂单 [震荡上涨] - 订单ID: {order.id}, "
                f"买入价: {buy_price}, 目标价: {target_price}"
            )

        return None

    def _get_ema_state(self, ema7: Decimal, ema25: Decimal, ema99: Decimal) -> str:
        """
        判断EMA状态

        Args:
            ema7: EMA7值
            ema25: EMA25值
            ema99: EMA99值

        Returns:
            str: 状态标识
                - bull_strong: 强势上涨
                - bear_strong: 强势下跌
                - consolidation_down: 震荡下跌
                - consolidation_up: 震荡上涨
        """
        if ema7 >= ema25 >= ema99:
            return 'bull_strong'
        elif ema7 <= ema25 <= ema99:
            return 'bear_strong'
        elif ema25 < ema99:
            return 'consolidation_down'
        else:
            return 'consolidation_up'

    def get_type(self) -> str:
        return "ema_state_take_profit"

    def get_priority(self) -> int:
        # 止盈优先级低于止损（止损优先级10）
        return 50
