"""
策略5: 强势上涨周期EMA25回调策略

本模块实现BullCycleEMAPullbackStrategy，在强势上涨周期中捕捉EMA25回调买入机会。

核心逻辑：
- 入场条件: cycle_phase == 'bull_strong' AND low <= ema25 <= high
- 出场条件: P95止盈 OR 5%止损

迭代编号: 019
创建日期: 2026-01-07
关联需求: docs/iterations/019-bull-cycle-ema-pullback-strategy/prd.md
"""

from decimal import Decimal
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
import logging

from strategy_adapter.interfaces import IStrategy
from strategy_adapter.models import Order

logger = logging.getLogger(__name__)


class BullCycleEMAPullbackStrategy(IStrategy):
    """
    策略5: 强势上涨周期EMA25回调策略

    职责：
    - 在强势上涨周期（bull_strong）中捕捉EMA25回调买入机会
    - 使用P95作为止盈目标
    - 使用5%固定止损

    设计原则：
    - 无状态设计：不保存任何订单或持仓信息
    - 趋势跟随：只在强势上涨周期中交易

    Example:
        >>> strategy = BullCycleEMAPullbackStrategy()
        >>> klines = pd.DataFrame({'open': [...], 'close': [...]})
        >>> indicators = {
        ...     'ema25': pd.Series([...]),
        ...     'p95': pd.Series([...]),
        ...     'cycle_phase': ['consolidation', 'bull_strong', ...]
        ... }
        >>> buy_signals = strategy.generate_buy_signals(klines, indicators)
    """

    def __init__(
        self,
        position_size: Decimal = Decimal("100"),
        stop_loss_pct: float = 5.0,
        target_cycle_phase: str = "bull_strong"
    ):
        """
        初始化策略5

        Args:
            position_size (Decimal): 单笔买入金额（USDT），默认100 USDT
            stop_loss_pct (float): 止损百分比，默认5%
            target_cycle_phase (str): 目标周期阶段，默认 'bull_strong'
        """
        self.buy_amount_usdt = position_size
        self.stop_loss_pct = stop_loss_pct
        self.target_cycle_phase = target_cycle_phase

        logger.info(
            f"初始化BullCycleEMAPullbackStrategy: "
            f"单笔仓位={position_size} USDT, "
            f"止损={stop_loss_pct}%, "
            f"目标周期={target_cycle_phase}"
        )

    def get_strategy_name(self) -> str:
        """返回策略名称"""
        return "Bull-Cycle-EMA-Pullback"

    def get_strategy_version(self) -> str:
        """返回策略版本"""
        return "1.0"

    def generate_buy_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series]
    ) -> List[Dict]:
        """
        生成买入信号

        入场条件：
        1. cycle_phase == 'bull_strong' (强势上涨周期)
        2. low <= ema25 <= high (K线包含EMA25，价格回调触及EMA25)

        Args:
            klines (pd.DataFrame): K线数据，index为pd.DatetimeIndex
                必须包含列：['open_time', 'open', 'high', 'low', 'close', 'volume']
            indicators (Dict[str, pd.Series]): 技术指标字典
                必须包含：'ema25', 'cycle_phase'

        Returns:
            List[Dict]: 买入信号列表
        """
        # Guard Clause: 验证klines非空
        if klines.empty:
            raise ValueError("klines不能为空DataFrame")

        # Guard Clause: 验证必要指标
        required_indicators = ['ema25', 'cycle_phase']
        for indicator in required_indicators:
            if indicator not in indicators:
                available = list(indicators.keys())
                raise KeyError(
                    f"indicators缺少必要指标: '{indicator}'。"
                    f"可用指标: {available}"
                )

        buy_signals = []
        ema25 = indicators['ema25']
        cycle_phase = indicators['cycle_phase']

        for i in range(len(klines)):
            kline = klines.iloc[i]
            current_ema = ema25.iloc[i]
            current_phase = cycle_phase.iloc[i] if hasattr(cycle_phase, 'iloc') else cycle_phase[i]

            # 跳过无效数据
            if pd.isna(current_ema):
                continue

            # 检查入场条件
            # 条件1: 强势上涨周期
            if current_phase != self.target_cycle_phase:
                continue

            # 条件2: K线包含EMA25（回调触及）
            if not (kline['low'] <= current_ema <= kline['high']):
                continue

            # 生成买入信号
            timestamp = int(klines.index[i].timestamp() * 1000)
            buy_signals.append({
                'timestamp': timestamp,
                'price': Decimal(str(kline['close'])),  # 以收盘价买入
                'reason': f'强势上涨EMA回调 (phase={current_phase})',
                'confidence': 0.8,
                'strategy_id': '5',
                'direction': 'long'
            })

            logger.debug(
                f"策略5买入信号: {klines.index[i]}, "
                f"close={kline['close']:.2f}, ema25={current_ema:.2f}"
            )

        logger.info(f"策略5生成买入信号: {len(buy_signals)}个")
        return buy_signals

    def generate_sell_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series],
        open_orders: List[Order]
    ) -> List[Dict]:
        """
        生成卖出信号

        出场条件（按优先级）：
        1. 止损: price <= buy_price * (1 - stop_loss_pct/100)
        2. 止盈: high >= P95

        Args:
            klines (pd.DataFrame): K线数据
            indicators (Dict[str, pd.Series]): 技术指标字典
                必须包含：'p95'
            open_orders (List[Order]): 当前持仓订单列表

        Returns:
            List[Dict]: 卖出信号列表
        """
        # Guard Clause: 验证p95指标
        if 'p95' not in indicators:
            available = list(indicators.keys())
            raise KeyError(
                f"indicators缺少必要指标: 'p95'。"
                f"可用指标: {available}"
            )

        # 边界处理：无持仓订单时返回空列表
        if not open_orders:
            logger.debug("无持仓订单，跳过卖出信号生成")
            return []

        sell_signals = []
        p95 = indicators['p95']
        stop_loss_rate = Decimal(str(1 - self.stop_loss_pct / 100))

        # 对每个持仓订单生成卖出信号
        for order in open_orders:
            # 找到订单买入时间对应的K线索引
            buy_time = pd.Timestamp(order.open_timestamp, unit='ms', tz='UTC')

            if buy_time not in klines.index:
                logger.warning(
                    f"订单 {order.id} 买入时间 {buy_time} 不在K线范围内，跳过"
                )
                continue

            buy_idx = klines.index.get_loc(buy_time)

            # 计算止损价格
            stop_loss_price = order.entry_price * stop_loss_rate

            # 从买入后的下一根K线开始检查出场条件
            for i in range(buy_idx + 1, len(klines)):
                kline = klines.iloc[i]
                p95_value = p95.iloc[i]
                timestamp = int(klines.index[i].timestamp() * 1000)

                # 优先检查止损（价格跌破止损线）
                if kline['low'] <= float(stop_loss_price):
                    sell_signals.append({
                        'timestamp': timestamp,
                        'price': stop_loss_price,
                        'order_id': order.id,
                        'reason': f'{self.stop_loss_pct}%止损',
                        'strategy_id': 'stop_loss'
                    })
                    logger.debug(
                        f"订单 {order.id} 在 {klines.index[i]} 触发{self.stop_loss_pct}%止损, "
                        f"止损价={stop_loss_price:.2f}"
                    )
                    break

                # 检查P95止盈
                if not pd.isna(p95_value) and kline['high'] >= p95_value:
                    sell_signals.append({
                        'timestamp': timestamp,
                        'price': Decimal(str(p95_value)),
                        'order_id': order.id,
                        'reason': 'P95止盈',
                        'strategy_id': 'p95_take_profit'
                    })
                    logger.debug(
                        f"订单 {order.id} 在 {klines.index[i]} 触发P95止盈, "
                        f"P95={p95_value:.2f}"
                    )
                    break

        logger.info(f"策略5生成卖出信号: {len(sell_signals)}个")
        return sell_signals

    def calculate_position_size(
        self,
        signal: Dict,
        available_capital: Decimal,
        current_price: Decimal
    ) -> Decimal:
        """
        计算仓位大小（固定金额策略）

        Returns:
            Decimal: 返回 self.buy_amount_usdt
        """
        return self.buy_amount_usdt

    def should_stop_loss(
        self,
        order: Order,
        current_price: Decimal,
        current_timestamp: int
    ) -> bool:
        """
        检查是否需要止损

        注意：实际止损逻辑在 generate_sell_signals 中处理，
        此方法仅用于兼容接口。
        """
        stop_loss_price = order.entry_price * Decimal(str(1 - self.stop_loss_pct / 100))
        return current_price <= stop_loss_price

    def should_take_profit(
        self,
        order: Order,
        current_price: Decimal,
        current_timestamp: int
    ) -> bool:
        """
        检查是否需要止盈

        注意：实际止盈逻辑在 generate_sell_signals 中处理，
        此方法仅用于兼容接口。
        """
        return False

    def get_required_indicators(self) -> List[str]:
        """
        返回所需的技术指标列表

        策略5需要的指标：
        - ema25: EMA25均线（用于入场判断）
        - p95: P95静态阈值（用于止盈）
        - cycle_phase: β宏观周期状态（用于入场判断）
        """
        return ['ema25', 'p95', 'cycle_phase']

    def generate_short_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series]
    ) -> List[Dict]:
        """
        策略5不支持做空，返回空列表
        """
        logger.debug("策略5不支持做空")
        return []

    def generate_cover_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series],
        open_short_orders: List[Order]
    ) -> List[Dict]:
        """
        策略5不支持做空，返回空列表
        """
        logger.debug("策略5不支持平空")
        return []
