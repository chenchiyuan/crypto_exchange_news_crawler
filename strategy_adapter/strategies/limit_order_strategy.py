"""
限价挂单策略（策略11）

本模块实现策略11的限价挂单买卖机制：
- 每根K线取消未成交挂单，重新计算并挂新单
- 买入挂单：从(P5+mid)/2开始，按0.5%递减挂N笔单
- 卖出挂单：取min(买入价×1.05, EMA25)
- 资金管理：挂单即冻结资金

迭代编号: 027 (策略11-限价挂单买卖机制)
创建日期: 2026-01-10
关联任务: TASK-027-006
关联需求: FP-027-001~018 (function-points.md)
关联架构: architecture.md#5.4 LimitOrderStrategy
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Any

import pandas as pd
import numpy as np

from strategy_adapter.interfaces import IStrategy
from strategy_adapter.models import Order, PendingOrder, PendingOrderStatus
from strategy_adapter.core.limit_order_manager import LimitOrderManager
from strategy_adapter.core.limit_order_price_calculator import LimitOrderPriceCalculator
from strategy_adapter.exits.limit_order_exit import LimitOrderExit

logger = logging.getLogger(__name__)


class LimitOrderStrategy(IStrategy):
    """
    限价挂单策略（策略11）

    与传统策略的核心差异：
    - 传统策略：一次性生成所有买入/卖出信号，由OrderManager执行
    - 限价挂单：逐K线处理，每根K线重新挂单，下根K线判断成交

    工作流程：
    1. 每根K线结束时：
       - 取消所有未成交的买入挂单
       - 根据当前P5和mid计算新的挂单价格
       - 创建新的买入挂单（冻结资金）
    2. 下根K线开始时：
       - 检查买入挂单是否成交（low <= price <= high）
       - 成交的挂单转为持仓，创建对应的卖出挂单
    3. 卖出挂单处理：
       - 每根K线更新卖出挂单价格（min(5%止盈, EMA25)）
       - 检查卖出挂单是否成交

    Attributes:
        position_size: 单笔挂单金额（USDT）
        order_count: 每根K线挂单数量
        order_interval: 挂单间隔比例
        take_profit_rate: 止盈比例
        ema_period: EMA周期
        order_manager: 限价挂单管理器
        price_calculator: 价格计算器
        exit_calculator: 卖出价格计算器

    Example:
        >>> strategy = LimitOrderStrategy(
        ...     position_size=Decimal("100"),
        ...     order_count=10,
        ...     order_interval=0.005
        ... )
        >>> strategy.initialize(Decimal("10000"))
        >>> # 逐K线处理
        >>> for i, kline in enumerate(klines):
        ...     signals = strategy.process_kline(i, kline, indicators)
    """

    # 策略配置
    STRATEGY_ID = 'strategy_11'
    STRATEGY_NAME = '限价挂单策略'
    STRATEGY_VERSION = '1.0'
    FUTURE_PERIODS = 6  # 未来EMA预测周期数

    def __init__(
        self,
        position_size: Decimal = Decimal("100"),
        order_count: int = 10,
        order_interval: float = 0.005,
        take_profit_rate: float = 0.05,
        ema_period: int = 25,
        first_order_discount: float = 0.01
    ):
        """
        初始化限价挂单策略

        Args:
            position_size: 单笔挂单金额（USDT），默认100
            order_count: 每根K线挂单数量，默认10
            order_interval: 挂单间隔比例，默认0.005（0.5%）
            take_profit_rate: 止盈比例，默认0.05（5%）
            ema_period: EMA周期，默认25
            first_order_discount: mid>=P5时首笔挂单折扣，默认0.01（1%）
        """
        self.position_size = position_size
        self.order_count = order_count
        self.order_interval = order_interval
        self.take_profit_rate = take_profit_rate
        self.ema_period = ema_period
        self.first_order_discount = first_order_discount

        # 初始化组件
        self.order_manager = LimitOrderManager(position_size=position_size)
        self.price_calculator = LimitOrderPriceCalculator(
            order_count=order_count,
            order_interval=order_interval,
            first_order_discount=first_order_discount
        )
        self.exit_calculator = LimitOrderExit(
            take_profit_rate=take_profit_rate,
            ema_period=ema_period
        )

        # 持仓管理（已成交的买入挂单 -> 等待卖出）
        self._holdings: Dict[str, Dict] = {}  # order_id -> {buy_price, quantity, ...}
        self._completed_orders: List[Dict] = []  # 已完成的交易记录

        logger.info(
            f"初始化LimitOrderStrategy: position_size={position_size}, "
            f"order_count={order_count}, order_interval={order_interval}, "
            f"first_order_discount={first_order_discount}"
        )

    def initialize(self, initial_capital: Decimal) -> None:
        """
        初始化策略（回测开始前调用）

        Args:
            initial_capital: 初始资金
        """
        self.order_manager.initialize(initial_capital)
        self._holdings.clear()
        self._completed_orders.clear()
        logger.info(f"LimitOrderStrategy初始化完成，初始资金: {initial_capital}")

    def get_strategy_name(self) -> str:
        return self.STRATEGY_NAME

    def get_strategy_version(self) -> str:
        return self.STRATEGY_VERSION

    def get_required_indicators(self) -> List[str]:
        """
        返回所需的技术指标

        Returns:
            List[str]: ['ema25', 'p5', 'inertia_mid']
        """
        return ['ema25', 'p5', 'inertia_mid']

    def process_kline(
        self,
        kline_index: int,
        kline: Dict[str, Any],
        indicators: Dict[str, Any],
        timestamp: int
    ) -> Dict[str, List[Dict]]:
        """
        处理单根K线（策略11的核心方法）

        策略11的核心逻辑：
        1. 检查上一根K线的买入挂单是否成交
        2. 检查卖出挂单是否成交
        3. 取消未成交的买入挂单
        4. 创建新的买入挂单
        5. 更新卖出挂单价格

        Args:
            kline_index: K线索引
            kline: K线数据 {'open', 'high', 'low', 'close', 'open_time'}
            indicators: 当前K线的技术指标 {'ema25', 'p5', 'inertia_mid'}
            timestamp: 当前时间戳（毫秒）

        Returns:
            Dict: {
                'buy_fills': List[Dict],    # 成交的买入订单
                'sell_fills': List[Dict],   # 成交的卖出订单
                'orders_placed': int,       # 新挂买入订单数
                'orders_cancelled': int,    # 取消订单数
                'insufficient_capital_count': int  # 资金不足次数
            }
        """
        result = {
            'buy_fills': [],
            'sell_fills': [],
            'orders_placed': 0,
            'orders_cancelled': 0,
            'insufficient_capital_count': 0,
        }

        low = Decimal(str(kline['low']))
        high = Decimal(str(kline['high']))

        # === Step 1: 检查买入挂单是否成交 ===
        pending_buy_orders = self.order_manager.get_pending_buy_orders()
        for order in pending_buy_orders:
            if self.order_manager.check_buy_order_fill(order, low, high):
                # 买入挂单成交
                filled_order = self.order_manager.fill_buy_order(order.order_id, timestamp)
                if filled_order:
                    # 记录持仓
                    self._holdings[filled_order.order_id] = {
                        'buy_price': filled_order.price,
                        'quantity': filled_order.quantity,
                        'amount': filled_order.amount,
                        'buy_timestamp': timestamp,
                        'kline_index': kline_index,
                    }

                    result['buy_fills'].append({
                        'order_id': filled_order.order_id,
                        'price': filled_order.price,
                        'quantity': filled_order.quantity,
                        'amount': filled_order.amount,
                        'timestamp': timestamp,
                        'kline_index': kline_index,
                    })

                    # 为成交的买入订单创建卖出挂单
                    ema_value = Decimal(str(indicators.get('ema25', 0)))
                    sell_price = self.exit_calculator.calculate_sell_price(
                        filled_order.price, ema_value
                    )
                    self.order_manager.create_sell_order(
                        parent_order_id=filled_order.order_id,
                        sell_price=sell_price,
                        quantity=filled_order.quantity,
                        kline_index=kline_index,
                        timestamp=timestamp
                    )

                    logger.debug(
                        f"买入成交: {filled_order.order_id}, 价格: {filled_order.price}, "
                        f"数量: {filled_order.quantity}, 卖出挂单价格: {sell_price}"
                    )

        # === Step 2: 检查卖出挂单是否成交 ===
        pending_sell_orders = self.order_manager.get_pending_sell_orders()
        for order in pending_sell_orders:
            if self.order_manager.check_sell_order_fill(order, low, high):
                # 获取买入信息
                parent_id = order.parent_order_id
                holding = self._holdings.get(parent_id)
                if holding:
                    buy_price = holding['buy_price']

                    # 卖出挂单成交
                    fill_result = self.order_manager.fill_sell_order(
                        order.order_id, timestamp, buy_price
                    )
                    if fill_result:
                        result['sell_fills'].append({
                            'order_id': order.order_id,
                            'parent_order_id': parent_id,
                            'buy_price': buy_price,
                            'sell_price': order.price,
                            'quantity': order.quantity,
                            'profit_loss': fill_result['profit_loss'],
                            'profit_rate': fill_result['profit_rate'],
                            'timestamp': timestamp,
                            'kline_index': kline_index,
                        })

                        # 移除持仓记录
                        del self._holdings[parent_id]

                        # 记录完成的交易
                        self._completed_orders.append({
                            'buy_order_id': parent_id,
                            'sell_order_id': order.order_id,
                            'buy_price': float(buy_price),
                            'sell_price': float(order.price),
                            'quantity': float(order.quantity),
                            'profit_loss': float(fill_result['profit_loss']),
                            'profit_rate': float(fill_result['profit_rate']),
                            'buy_timestamp': holding['buy_timestamp'],
                            'sell_timestamp': timestamp,
                        })

                        logger.debug(
                            f"卖出成交: {order.order_id}, "
                            f"盈亏: {fill_result['profit_loss']:.4f} "
                            f"({fill_result['profit_rate']:.2f}%)"
                        )

        # === Step 3: 更新未成交卖出挂单的价格 ===
        ema_value = Decimal(str(indicators.get('ema25', 0)))
        for order in self.order_manager.get_pending_sell_orders():
            parent_id = order.parent_order_id
            holding = self._holdings.get(parent_id)
            if holding:
                new_sell_price = self.exit_calculator.calculate_sell_price(
                    holding['buy_price'], ema_value
                )
                self.order_manager.update_sell_order_price(order.order_id, new_sell_price)

        # === Step 4: 取消所有未成交的买入挂单 ===
        pending_before = len(self.order_manager.get_pending_buy_orders())
        self.order_manager.cancel_all_buy_orders()
        result['orders_cancelled'] = pending_before

        # === Step 5: 创建新的买入挂单 ===
        p5 = Decimal(str(indicators.get('p5', 0)))
        inertia_mid = Decimal(str(indicators.get('inertia_mid', 0)))
        ema25 = Decimal(str(indicators.get('ema25', 0)))
        beta = Decimal(str(indicators.get('beta', 0)))

        if p5 > 0 and inertia_mid > 0:
            # 计算挂单价格列表
            buy_prices = self.price_calculator.calculate_buy_prices(p5, inertia_mid)

            # 盈利预判：计算未来EMA，只有预期盈利时才挂单
            # future_ema = ema25 + beta * FUTURE_PERIODS
            future_ema = ema25 + beta * Decimal(self.FUTURE_PERIODS)
            first_buy_price = buy_prices[0] if buy_prices else Decimal(0)

            # 只有当 future_ema > 第一笔挂单价 时才创建挂单（预期盈利）
            if future_ema > first_buy_price:
                for price in buy_prices:
                    order = self.order_manager.create_buy_order(
                        price=price,
                        kline_index=kline_index,
                        timestamp=timestamp
                    )
                    if order:
                        result['orders_placed'] += 1

                result['insufficient_capital_count'] = (
                    self.order_manager.insufficient_capital_count
                )
            else:
                # 跳过挂单，记录原因
                result['skip_reason'] = 'future_ema_not_profitable'
                logger.debug(
                    f"跳过挂单: future_ema ({future_ema:.2f}) <= "
                    f"first_buy_price ({first_buy_price:.2f}), 预期不盈利"
                )

        return result

    def get_statistics(self) -> Dict:
        """
        获取策略统计信息

        Returns:
            Dict: 统计数据
        """
        manager_stats = self.order_manager.get_statistics()

        # 计算持仓统计
        total_holdings = len(self._holdings)
        total_completed = len(self._completed_orders)

        # 计算盈亏统计
        total_profit_loss = sum(
            order.get('profit_loss', 0) for order in self._completed_orders
        )
        winning_trades = sum(
            1 for order in self._completed_orders
            if order.get('profit_loss', 0) > 0
        )
        win_rate = winning_trades / total_completed * 100 if total_completed > 0 else 0

        return {
            **manager_stats,
            'holdings_count': total_holdings,
            'completed_trades': total_completed,
            'total_profit_loss': total_profit_loss,
            'winning_trades': winning_trades,
            'win_rate': win_rate,
        }

    def get_completed_orders(self) -> List[Dict]:
        """
        获取已完成的交易记录

        Returns:
            List[Dict]: 交易记录列表
        """
        return self._completed_orders.copy()

    def get_holdings(self) -> Dict[str, Dict]:
        """
        获取当前持仓

        Returns:
            Dict: 持仓字典
        """
        return self._holdings.copy()

    # === IStrategy 接口实现（用于兼容性）===

    def generate_buy_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series]
    ) -> List[Dict]:
        """
        生成买入信号（IStrategy接口）

        注意：策略11不使用传统的信号生成方式。
        此方法为兼容IStrategy接口而实现，实际逻辑在process_kline中。

        对于策略11的回测，应使用run_limit_order_backtest方法。
        """
        logger.warning(
            "LimitOrderStrategy.generate_buy_signals被调用，"
            "但策略11应使用process_kline逐K线处理"
        )
        return []

    def generate_sell_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series],
        open_orders: List[Order]
    ) -> List[Dict]:
        """
        生成卖出信号（IStrategy接口）

        注意：策略11不使用传统的信号生成方式。
        """
        logger.warning(
            "LimitOrderStrategy.generate_sell_signals被调用，"
            "但策略11应使用process_kline逐K线处理"
        )
        return []

    def calculate_position_size(
        self,
        signal: Dict,
        available_capital: Decimal,
        current_price: Decimal
    ) -> Decimal:
        """
        计算仓位大小（IStrategy接口）

        Returns:
            Decimal: 单笔挂单金额
        """
        return self.position_size

    def should_stop_loss(
        self,
        order: Order,
        current_price: Decimal,
        current_timestamp: int
    ) -> bool:
        """
        检查止损（IStrategy接口）

        策略11不使用止损，固定返回False。
        """
        return False

    def should_take_profit(
        self,
        order: Order,
        current_price: Decimal,
        current_timestamp: int
    ) -> bool:
        """
        检查止盈（IStrategy接口）

        策略11使用限价卖出，不使用此方法。
        """
        return False

    def run_limit_order_backtest(
        self,
        klines_df: pd.DataFrame,
        indicators: Dict[str, pd.Series],
        initial_capital: Decimal = Decimal("10000")
    ) -> Dict:
        """
        执行限价挂单回测（策略11专用）

        Args:
            klines_df: K线数据DataFrame
            indicators: 技术指标字典
            initial_capital: 初始资金

        Returns:
            Dict: 回测结果
                {
                    'total_trades': int,
                    'winning_trades': int,
                    'losing_trades': int,
                    'win_rate': float,
                    'total_profit_loss': float,
                    'final_capital': float,
                    'return_rate': float,
                    'orders': List[Dict],
                    'statistics': Dict
                }
        """
        # 初始化
        self.initialize(initial_capital)

        total_buy_fills = 0
        total_sell_fills = 0
        all_buy_fills = []
        all_sell_fills = []

        logger.info(
            f"开始限价挂单回测: {len(klines_df)}根K线, "
            f"初始资金: {initial_capital}"
        )

        # 逐K线处理
        for i, (idx, row) in enumerate(klines_df.iterrows()):
            # 构建kline字典
            kline = {
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'open_time': idx,
            }

            # 获取当前K线的指标值
            current_indicators = {}
            for name, series in indicators.items():
                if i < len(series):
                    value = series.iloc[i]
                    if not pd.isna(value):
                        current_indicators[name] = value

            # 获取时间戳
            if hasattr(idx, 'timestamp'):
                timestamp = int(idx.timestamp() * 1000)
            else:
                timestamp = int(idx)

            # 处理K线
            result = self.process_kline(i, kline, current_indicators, timestamp)

            total_buy_fills += len(result['buy_fills'])
            total_sell_fills += len(result['sell_fills'])
            all_buy_fills.extend(result['buy_fills'])
            all_sell_fills.extend(result['sell_fills'])

            # 进度日志（每1000根K线输出一次）
            if (i + 1) % 1000 == 0:
                stats = self.get_statistics()
                logger.info(
                    f"进度: {i+1}/{len(klines_df)}, "
                    f"买入成交: {total_buy_fills}, 卖出成交: {total_sell_fills}, "
                    f"当前持仓: {stats['holdings_count']}, "
                    f"可用资金: {stats['available_capital']:.2f}"
                )

        # 生成最终统计
        final_stats = self.get_statistics()
        completed_orders = self.get_completed_orders()

        winning_trades = sum(1 for o in completed_orders if o.get('profit_loss', 0) > 0)
        losing_trades = sum(1 for o in completed_orders if o.get('profit_loss', 0) <= 0)
        total_profit_loss = sum(o.get('profit_loss', 0) for o in completed_orders)
        final_capital = final_stats['total_capital']
        return_rate = (float(final_capital) - float(initial_capital)) / float(initial_capital) * 100

        result = {
            'total_trades': len(completed_orders),
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': winning_trades / len(completed_orders) * 100 if completed_orders else 0,
            'total_profit_loss': total_profit_loss,
            'final_capital': float(final_capital),
            'return_rate': return_rate,
            'total_buy_fills': total_buy_fills,
            'total_sell_fills': total_sell_fills,
            'remaining_holdings': len(self.get_holdings()),
            'orders': completed_orders,
            'buy_fills': all_buy_fills,
            'sell_fills': all_sell_fills,
            'statistics': final_stats,
        }

        logger.info(
            f"回测完成: 总交易数={result['total_trades']}, "
            f"胜率={result['win_rate']:.2f}%, "
            f"总盈亏={result['total_profit_loss']:.4f}, "
            f"收益率={result['return_rate']:.2f}%"
        )

        return result
