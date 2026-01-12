"""
滚动经验CDF信号策略

本模块实现基于滚动经验CDF的非参数化交易策略：
- 入场信号：Prob≤q_in（左尾极端超卖）
- 出场信号：Prob≥q_out（概率回归）或风控触发
- 执行机制：GFOB限价单（仅下一根K线有效）
- 因果一致性：信号在t，成交最早在t+1

迭代编号: 034 (滚动经验CDF信号策略)
创建日期: 2026-01-12
关联任务: TASK-034-009, TASK-034-010, TASK-034-011, TASK-034-012
关联需求: FP-034-006~018 (function-points.md)
关联架构: architecture.md#4.3.3 EmpiricalCDFStrategy
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Any
from enum import Enum

import pandas as pd

from strategy_adapter.interfaces import IStrategy
from strategy_adapter.models import Order
from strategy_adapter.calculators import EmpiricalCDFCalculator
from strategy_adapter.core.gfob_order_manager import GFOBOrderManager

logger = logging.getLogger(__name__)


class PositionState(Enum):
    """仓位状态"""
    FLAT = "FLAT"      # 空仓
    LONG = "LONG"      # 持仓


class ExitReason(Enum):
    """出场原因"""
    PROB_REVERSION = "PROB_REVERSION"  # 概率回归
    TIME_STOP = "TIME_STOP"            # 时间止损
    DISASTER_STOP = "DISASTER_STOP"    # 灾难止损


class EmpiricalCDFStrategy(IStrategy):
    """
    滚动经验CDF信号策略

    核心逻辑：
    - 入场：Prob≤q_in（默认5）时挂限价买单
    - 出场：Prob≥q_out（默认50）或风控触发时挂限价卖单
    - 执行：GFOB限价单，下一根K线撮合

    工作流程（每根K线）：
    1. 撮合阶段：撮合t-1收盘挂出的订单
    2. 计算阶段：计算Prob_t
    3. 信号阶段：判断入场/出场
    4. 挂单阶段：创建GFOB订单
    5. 日志阶段：记录日志

    参数：
    - q_in: 入场阈值（默认5）
    - q_out: 出场阈值（默认50）
    - max_holding_bars: 时间止损bar数（默认48）
    - stop_loss_threshold: 灾难止损阈值（默认0.05）

    Example:
        >>> strategy = EmpiricalCDFStrategy(q_in=5, q_out=50)
        >>> result = strategy.run_backtest(klines_df, initial_capital=Decimal("10000"))
    """

    # 策略配置
    STRATEGY_ID = 'empirical_cdf'
    STRATEGY_NAME = '滚动经验CDF策略'
    STRATEGY_VERSION = '1.0'

    def __init__(
        self,
        q_in: float = 5.0,
        q_out: float = 50.0,
        max_holding_bars: int = 48,
        stop_loss_threshold: float = 0.05,
        position_size: Decimal = Decimal("100"),
        delta_in: float = 0.001,
        delta_out: float = 0.0,
        delta_out_fast: float = 0.001,
        ema_period: int = 25,
        ewma_period: int = 50,
        cdf_window: int = 100
    ):
        """
        初始化滚动经验CDF策略

        Args:
            q_in: 入场阈值，Prob≤q_in时触发入场（默认5）
            q_out: 出场阈值，Prob≥q_out时触发概率回归出场（默认50）
            max_holding_bars: 时间止损bar数（默认48）
            stop_loss_threshold: 灾难止损阈值，亏损超过此比例触发（默认0.05，即5%）
            position_size: 单笔挂单金额（USDT），默认100
            delta_in: 入场限价折扣，默认0.001（0.1%）
            delta_out: 正常出场折扣，默认0.0
            delta_out_fast: 快速出场折扣，默认0.001（0.1%）
            ema_period: EMA周期，默认25
            ewma_period: EWMA周期，默认50
            cdf_window: 经验CDF窗口大小M，默认100
        """
        # 策略参数
        self._q_in = q_in
        self._q_out = q_out
        self._max_holding_bars = max_holding_bars
        self._stop_loss_threshold = Decimal(str(stop_loss_threshold))
        self._position_size = position_size

        # 初始化组件
        self._calculator = EmpiricalCDFCalculator(
            ema_period=ema_period,
            ewma_period=ewma_period,
            cdf_window=cdf_window
        )
        self._order_manager = GFOBOrderManager(
            position_size=position_size,
            delta_in=delta_in,
            delta_out=delta_out,
            delta_out_fast=delta_out_fast
        )

        # 仓位状态
        self._position_state = PositionState.FLAT
        self._holding: Optional[Dict] = None  # 当前持仓信息

        # 交易记录
        self._completed_orders: List[Dict] = []

        # 日志记录
        self._bar_logs: List[Dict] = []
        self._order_logs: List[Dict] = []
        self._trade_logs: List[Dict] = []

        # 冷启动标记
        self._cdf_window = cdf_window

        logger.info(
            f"初始化EmpiricalCDFStrategy: q_in={q_in}, q_out={q_out}, "
            f"max_holding_bars={max_holding_bars}, stop_loss={stop_loss_threshold}, "
            f"position_size={position_size}"
        )

    def initialize(self, initial_capital: Decimal) -> None:
        """
        初始化策略（回测开始前调用）

        Args:
            initial_capital: 初始资金
        """
        self._order_manager.initialize(initial_capital)
        self._calculator.reset()
        self._position_state = PositionState.FLAT
        self._holding = None
        self._completed_orders.clear()
        self._bar_logs.clear()
        self._order_logs.clear()
        self._trade_logs.clear()

        logger.info(f"EmpiricalCDFStrategy初始化完成，初始资金: {initial_capital}")

    def get_strategy_name(self) -> str:
        return self.STRATEGY_NAME

    def get_strategy_version(self) -> str:
        return self.STRATEGY_VERSION

    def get_required_indicators(self) -> List[str]:
        """
        返回所需的技术指标

        Returns:
            List[str]: 空列表（本策略自行计算所有指标）
        """
        return []

    def process_kline(
        self,
        kline_index: int,
        kline: Dict[str, Any],
        timestamp: int
    ) -> Dict:
        """
        处理单根K线（核心方法）

        执行顺序：
        1. 撮合阶段：撮合t-1挂出的订单
        2. 计算阶段：计算Prob_t
        3. 信号阶段：判断入场/出场
        4. 挂单阶段：创建GFOB订单
        5. 日志阶段：记录日志

        Args:
            kline_index: K线索引
            kline: K线数据 {'open', 'high', 'low', 'close', 'open_time'}
            timestamp: 当前时间戳（毫秒）

        Returns:
            Dict: {
                'buy_fills': List[Dict],     # 成交的买入订单
                'sell_fills': List[Dict],    # 成交的卖出订单
                'orders_placed': Dict,       # 新挂订单信息
                'indicators': Dict,          # 计算的指标
                'expired_orders': List[str]  # 过期订单ID
            }
        """
        result = {
            'buy_fills': [],
            'sell_fills': [],
            'orders_placed': {},
            'indicators': {},
            'expired_orders': []
        }

        low = Decimal(str(kline['low']))
        high = Decimal(str(kline['high']))
        close = Decimal(str(kline['close']))

        # === Step 1: 撮合阶段 ===
        match_result = self._order_manager.match_orders(
            kline_index=kline_index,
            low=low,
            high=high,
            timestamp=timestamp
        )

        result['expired_orders'] = match_result['expired_orders']

        # 处理卖出成交
        for fill in match_result['sell_fills']:
            self._handle_sell_fill(fill, kline_index, timestamp)
            result['sell_fills'].append(fill)

        # 处理买入成交
        for fill in match_result['buy_fills']:
            self._handle_buy_fill(fill, kline_index, timestamp)
            result['buy_fills'].append(fill)

        # === Step 2: 计算阶段 ===
        calc_result = self._calculator.update(close)
        result['indicators'] = calc_result

        prob = calc_result['prob']
        ema = calc_result['ema']

        # === Step 3: 信号判断 ===
        entry_signal = False
        exit_signal = False
        exit_reason = None

        # 冷启动期检查
        if prob is None:
            # 冷启动期，不产生信号
            pass
        elif self._position_state == PositionState.FLAT:
            # 空仓状态：检查入场信号
            if prob <= self._q_in:
                entry_signal = True
        else:
            # 持仓状态：检查出场信号
            exit_signal, exit_reason = self._check_exit_conditions(
                prob, close, kline_index
            )

        # === Step 4: 挂单阶段 ===
        if entry_signal and not self._order_manager.has_pending_buy():
            # 创建入场限价买单
            order = self._order_manager.create_buy_order(
                close_price=close,
                kline_index=kline_index,
                timestamp=timestamp
            )
            if order:
                result['orders_placed']['buy'] = order
                self._log_order_event('BUY_PLACED', order, kline_index, timestamp)
                logger.debug(
                    f"Bar {kline_index}: 入场信号 Prob={prob:.2f}≤{self._q_in}, "
                    f"挂买单 L={order['price']}"
                )

        if exit_signal and self._holding and not self._order_manager.has_pending_sell():
            # 创建出场限价卖单
            reason_str = exit_reason.value if exit_reason else 'PROB_REVERSION'
            order = self._order_manager.create_sell_order(
                close_price=close,
                parent_order_id=self._holding['order_id'],
                quantity=self._holding['quantity'],
                reason=reason_str,
                kline_index=kline_index,
                timestamp=timestamp
            )
            result['orders_placed']['sell'] = order
            self._log_order_event('SELL_PLACED', order, kline_index, timestamp)
            logger.debug(
                f"Bar {kline_index}: 出场信号 reason={reason_str}, "
                f"挂卖单 U={order['price']}"
            )

        # === Step 5: 日志阶段 ===
        self._log_bar(kline_index, kline, calc_result, timestamp)

        return result

    def _check_exit_conditions(
        self,
        prob: float,
        close: Decimal,
        kline_index: int
    ) -> tuple:
        """
        检查出场条件

        Args:
            prob: 当前Prob值
            close: 当前收盘价
            kline_index: 当前K线索引

        Returns:
            tuple: (exit_signal: bool, exit_reason: ExitReason or None)
        """
        if not self._holding:
            return False, None

        # 1. 概率回归出场：Prob≥q_out
        if prob >= self._q_out:
            return True, ExitReason.PROB_REVERSION

        # 2. 时间止损：持仓超过max_holding_bars
        holding_bars = kline_index - self._holding['entry_bar']
        if holding_bars >= self._max_holding_bars:
            return True, ExitReason.TIME_STOP

        # 3. 灾难止损：亏损超过stop_loss_threshold
        buy_price = self._holding['buy_price']
        loss_rate = (buy_price - close) / buy_price
        if loss_rate >= self._stop_loss_threshold:
            return True, ExitReason.DISASTER_STOP

        return False, None

    def _handle_buy_fill(self, fill: Dict, kline_index: int, timestamp: int) -> None:
        """
        处理买入成交

        Args:
            fill: 成交信息
            kline_index: K线索引
            timestamp: 时间戳
        """
        # 更新仓位状态
        self._position_state = PositionState.LONG
        self._holding = {
            'order_id': fill['order_id'],
            'buy_price': fill['price'],
            'quantity': fill['quantity'],
            'amount': fill['amount'],
            'entry_bar': kline_index,
            'entry_timestamp': timestamp,
        }

        # 记录交易日志
        self._log_trade('BUY_FILL', fill, kline_index, timestamp)

        logger.debug(
            f"Bar {kline_index}: 买入成交 {fill['order_id']}, "
            f"价格={fill['price']}, 数量={fill['quantity']}"
        )

    def _handle_sell_fill(self, fill: Dict, kline_index: int, timestamp: int) -> None:
        """
        处理卖出成交

        Args:
            fill: 成交信息
            kline_index: K线索引
            timestamp: 时间戳
        """
        if not self._holding:
            logger.warning(f"卖出成交但无持仓记录: {fill['order_id']}")
            return

        # 计算盈亏
        buy_price = self._holding['buy_price']
        sell_price = fill['price']
        quantity = fill['quantity']
        profit_loss = (sell_price - buy_price) * quantity
        profit_rate = float(profit_loss / (buy_price * quantity) * 100)

        # 释放资金
        self._order_manager.release_sell_capital(buy_price, quantity, profit_loss)

        # 记录完成的交易
        completed_order = {
            'buy_order_id': self._holding['order_id'],
            'sell_order_id': fill['order_id'],
            'buy_price': float(buy_price),
            'sell_price': float(sell_price),
            'quantity': float(quantity),
            'profit_loss': float(profit_loss),
            'profit_rate': profit_rate,
            'entry_bar': self._holding['entry_bar'],
            'exit_bar': kline_index,
            'holding_bars': kline_index - self._holding['entry_bar'],
            'entry_timestamp': self._holding['entry_timestamp'],
            'exit_timestamp': timestamp,
            'exit_reason': fill.get('reason', 'UNKNOWN'),
        }
        self._completed_orders.append(completed_order)

        # 记录交易日志
        self._log_trade('SELL_FILL', fill, kline_index, timestamp, profit_loss, profit_rate)

        # 清空持仓状态
        self._position_state = PositionState.FLAT
        self._holding = None

        logger.debug(
            f"Bar {kline_index}: 卖出成交 {fill['order_id']}, "
            f"盈亏={profit_loss:.4f} ({profit_rate:.2f}%)"
        )

    def _log_bar(
        self,
        kline_index: int,
        kline: Dict,
        indicators: Dict,
        timestamp: int
    ) -> None:
        """
        记录Bar日志

        Args:
            kline_index: K线索引
            kline: K线数据
            indicators: 指标数据
            timestamp: 时间戳
        """
        log_entry = {
            'bar_index': kline_index,
            'timestamp': timestamp,
            'open': float(kline['open']),
            'high': float(kline['high']),
            'low': float(kline['low']),
            'close': float(kline['close']),
            'ema': float(indicators.get('ema', 0)),
            'd': float(indicators.get('d', 0)),
            'mu': float(indicators.get('mu', 0)),
            'sigma': float(indicators.get('sigma', 0)),
            'x': float(indicators.get('x', 0)),
            'prob': indicators.get('prob'),
            'position': self._position_state.value,
            'has_pending_buy': self._order_manager.has_pending_buy(),
            'has_pending_sell': self._order_manager.has_pending_sell(),
        }
        self._bar_logs.append(log_entry)

    def _log_order_event(
        self,
        event_type: str,
        order: Dict,
        kline_index: int,
        timestamp: int
    ) -> None:
        """
        记录订单日志

        Args:
            event_type: 事件类型
            order: 订单信息
            kline_index: K线索引
            timestamp: 时间戳
        """
        log_entry = {
            'event': event_type,
            'order_id': order.get('order_id'),
            'price': float(order.get('price', 0)),
            'quantity': float(order.get('quantity', 0)) if order.get('quantity') else None,
            'amount': float(order.get('amount', 0)) if order.get('amount') else None,
            'reason': order.get('reason'),
            'bar_index': kline_index,
            'valid_bar': order.get('valid_bar'),
            'timestamp': timestamp,
        }
        self._order_logs.append(log_entry)

    def _log_trade(
        self,
        event_type: str,
        fill: Dict,
        kline_index: int,
        timestamp: int,
        profit_loss: Optional[Decimal] = None,
        profit_rate: Optional[float] = None
    ) -> None:
        """
        记录交易日志

        Args:
            event_type: 事件类型
            fill: 成交信息
            kline_index: K线索引
            timestamp: 时间戳
            profit_loss: 盈亏（卖出时）
            profit_rate: 盈亏率（卖出时）
        """
        log_entry = {
            'event': event_type,
            'order_id': fill.get('order_id'),
            'price': float(fill.get('price', 0)),
            'quantity': float(fill.get('quantity', 0)) if fill.get('quantity') else None,
            'bar_index': kline_index,
            'timestamp': timestamp,
        }
        if profit_loss is not None:
            log_entry['profit_loss'] = float(profit_loss)
            log_entry['profit_rate'] = profit_rate
        self._trade_logs.append(log_entry)

    def run_backtest(
        self,
        klines_df: pd.DataFrame,
        initial_capital: Decimal = Decimal("10000")
    ) -> Dict:
        """
        执行完整回测

        Args:
            klines_df: K线数据DataFrame
            initial_capital: 初始资金

        Returns:
            Dict: 回测结果
        """
        # 初始化
        self.initialize(initial_capital)

        total_buy_fills = 0
        total_sell_fills = 0
        all_buy_fills = []
        all_sell_fills = []

        logger.info(
            f"开始滚动经验CDF策略回测: {len(klines_df)}根K线, "
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

            # 获取时间戳
            if hasattr(idx, 'timestamp'):
                timestamp = int(idx.timestamp() * 1000)
            else:
                timestamp = int(idx)

            # 处理K线
            result = self.process_kline(i, kline, timestamp)

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
                    f"当前持仓: {'有' if self._holding else '无'}, "
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

        backtest_result = {
            'total_trades': len(completed_orders),
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': winning_trades / len(completed_orders) * 100 if completed_orders else 0,
            'total_profit_loss': total_profit_loss,
            'final_capital': float(final_capital),
            'return_rate': return_rate,
            'total_buy_fills': total_buy_fills,
            'total_sell_fills': total_sell_fills,
            'remaining_holdings': 1 if self._holding else 0,
            'orders': completed_orders,
            'buy_fills': all_buy_fills,
            'sell_fills': all_sell_fills,
            'statistics': final_stats,
            'bar_logs': self._bar_logs,
            'order_logs': self._order_logs,
            'trade_logs': self._trade_logs,
        }

        logger.info(
            f"回测完成: 总交易数={backtest_result['total_trades']}, "
            f"胜率={backtest_result['win_rate']:.2f}%, "
            f"总盈亏={backtest_result['total_profit_loss']:.4f}, "
            f"收益率={backtest_result['return_rate']:.2f}%"
        )

        return backtest_result

    def get_statistics(self) -> Dict:
        """
        获取策略统计信息

        Returns:
            Dict: 统计数据
        """
        order_stats = self._order_manager.get_statistics()

        # 计算盈亏统计
        total_profit_loss = sum(
            order.get('profit_loss', 0) for order in self._completed_orders
        )
        winning_trades = sum(
            1 for order in self._completed_orders
            if order.get('profit_loss', 0) > 0
        )
        total_completed = len(self._completed_orders)
        win_rate = winning_trades / total_completed * 100 if total_completed > 0 else 0

        return {
            **order_stats,
            'position_state': self._position_state.value,
            'has_holding': self._holding is not None,
            'completed_trades': total_completed,
            'total_profit_loss': total_profit_loss,
            'winning_trades': winning_trades,
            'win_rate': win_rate,
            'calculator_bar_count': self._calculator.bar_count,
            'calculator_warmed_up': self._calculator.is_warmed_up,
        }

    def get_completed_orders(self) -> List[Dict]:
        """
        获取已完成的交易记录

        Returns:
            List[Dict]: 交易记录列表
        """
        return self._completed_orders.copy()

    def get_holding(self) -> Optional[Dict]:
        """
        获取当前持仓

        Returns:
            Optional[Dict]: 持仓信息
        """
        return self._holding.copy() if self._holding else None

    def get_bar_logs(self) -> List[Dict]:
        """获取Bar日志"""
        return self._bar_logs.copy()

    def get_order_logs(self) -> List[Dict]:
        """获取订单日志"""
        return self._order_logs.copy()

    def get_trade_logs(self) -> List[Dict]:
        """获取交易日志"""
        return self._trade_logs.copy()

    # === IStrategy 接口实现（用于兼容性）===

    def generate_buy_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series]
    ) -> List[Dict]:
        """
        生成买入信号（IStrategy接口）

        注意：此策略使用process_kline逐K线处理模式。
        """
        logger.warning(
            "EmpiricalCDFStrategy.generate_buy_signals被调用，"
            "但此策略应使用run_backtest方法"
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

        注意：此策略使用process_kline逐K线处理模式。
        """
        logger.warning(
            "EmpiricalCDFStrategy.generate_sell_signals被调用，"
            "但此策略应使用run_backtest方法"
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
        return self._position_size

    def should_stop_loss(
        self,
        order: Order,
        current_price: Decimal,
        current_timestamp: int
    ) -> bool:
        """
        检查止损（IStrategy接口）

        此策略使用内置风控，不使用此方法。
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

        此策略使用概率回归出场，不使用此方法。
        """
        return False
