"""
策略20：多交易对共享资金池

本策略实现多交易对共享资金池的回测机制：
- 入场：复用策略16的P5限价挂单入场逻辑
- 出场：复用策略16的动态挂单止盈逻辑
- 资金管理：全局共享资金池，所有交易对竞争同一资金
- 持仓限制：全局持仓数不超过 max_positions

核心特性：
- 支持多交易对（默认 ETH, BTC, HYPE, BNB）
- 全局资金池管理（GlobalCapitalManager）
- 全局持仓跟踪（GlobalPositionTracker）
- 分交易对独立统计 + 全局合并统计

迭代编号: 045 (策略20-多交易对共享资金池)
创建日期: 2026-01-14
基础策略: 策略16 (v4.0)
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Any

import numpy as np
import pandas as pd

from strategy_adapter.interfaces import IStrategy
from strategy_adapter.models import (
    PendingOrder, PendingOrderStatus, PendingOrderSide, SymbolState
)
from strategy_adapter.core.global_capital_manager import GlobalCapitalManager
from strategy_adapter.core.global_position_tracker import GlobalPositionTracker
from strategy_adapter.utils import (
    calculate_base_price,
    calculate_order_price,
    calculate_sell_price,
    should_skip_entry,
    is_buy_order_filled,
    is_sell_order_filled,
    calculate_profit,
    calculate_indicators,
)

logger = logging.getLogger(__name__)


class Strategy20MultiSymbol(IStrategy):
    """
    策略20：多交易对共享资金池

    在单一资金池下同时管理多个交易对的买卖，实现跨交易对的资金动态分配。

    核心约束：
    - 资金全局共享：所有交易对竞争同一资金池
    - 持仓全局限制：合计最多 max_positions 个持仓
    - 仓位动态计算：单笔金额 = available_cash / (max_positions - total_holdings)

    买卖逻辑（复用策略16）：
    - 入场：P5限价挂单入场，bear_warning 周期跳过
    - 出场：动态挂单止盈（根据 cycle_phase 计算卖出价）

    Attributes:
        symbols: 交易对列表
        discount: 挂单折扣比例
        max_positions: 最大持仓数量

    Example:
        >>> strategy = Strategy20MultiSymbol(
        ...     symbols=['ETHUSDT', 'BTCUSDT'],
        ...     discount=0.001,
        ...     max_positions=10
        ... )
        >>> result = strategy.run_backtest(klines_dict, initial_capital=10000)
    """

    STRATEGY_ID = 'strategy_20'
    STRATEGY_NAME = '多交易对共享资金池'
    STRATEGY_VERSION = '1.0'

    DEFAULT_SYMBOLS = ['ETHUSDT', 'BTCUSDT', 'HYPEUSDT', 'BNBUSDT']

    def __init__(
        self,
        symbols: List[str] = None,
        discount: float = 0.001,
        max_positions: int = 10,
        interval_hours: float = 4.0
    ):
        """
        初始化策略20

        Args:
            symbols: 交易对列表，默认为 DEFAULT_SYMBOLS
            discount: 挂单折扣比例，默认 0.001（0.1%）
            max_positions: 最大持仓数量（全局限制），默认 10
            interval_hours: K线周期（小时），默认 4.0
        """
        self.symbols = symbols or self.DEFAULT_SYMBOLS
        self.discount = Decimal(str(discount))
        self.max_positions = max_positions
        self.interval_hours = interval_hours

        # 全局管理器（run_backtest 时初始化）
        self._capital_manager: Optional[GlobalCapitalManager] = None
        self._position_tracker: Optional[GlobalPositionTracker] = None

        # 交易对状态
        self._symbol_states: Dict[str, SymbolState] = {}

        # 指标缓存
        self._indicators_cache: Dict[str, Dict[str, pd.Series]] = {}

        # 权益曲线
        self._equity_curve: List[Dict] = []

        logger.info(
            f"初始化Strategy20MultiSymbol: symbols={self.symbols}, "
            f"discount={discount}, max_positions={max_positions}"
        )

    def get_strategy_name(self) -> str:
        return self.STRATEGY_NAME

    def get_strategy_version(self) -> str:
        return self.STRATEGY_VERSION

    def get_required_indicators(self) -> List[str]:
        return ['ema7', 'ema25', 'ema99', 'p5', 'p95', 'inertia_mid', 'cycle_phase']

    def run_backtest(
        self,
        klines_dict: Dict[str, pd.DataFrame],
        initial_capital: Decimal = Decimal("10000")
    ) -> Dict:
        """
        执行多交易对回测

        Args:
            klines_dict: K线数据字典 {symbol: DataFrame}
            initial_capital: 初始资金

        Returns:
            Dict: 回测结果，包含 global, by_symbol, orders, equity_curve
        """
        # 1. 初始化
        self._initialize(initial_capital)

        # 2. 计算所有交易对的指标
        self._calculate_all_indicators(klines_dict)

        # 3. 获取对齐的时间戳列表
        timestamps = self._get_aligned_timestamps(klines_dict)

        logger.info(f"开始回测: {len(timestamps)} 根K线, {len(self.symbols)} 个交易对")

        # 4. 逐时间戳处理
        for i, ts in enumerate(timestamps):
            self._process_timestamp(i, ts, klines_dict)

            # 记录权益曲线（每根K线记录一次）
            self._record_equity(ts, klines_dict)

        # 5. 生成结果
        result = self._generate_result(
            initial_capital, timestamps, klines_dict
        )

        logger.info(
            f"回测完成: 总订单={result['global']['total_orders']}, "
            f"胜率={result['global']['win_rate']:.2f}%"
        )

        return result

    def _initialize(self, initial_capital: Decimal):
        """初始化回测状态"""
        # 初始化全局管理器
        self._capital_manager = GlobalCapitalManager(initial_capital)
        self._position_tracker = GlobalPositionTracker(self.max_positions)

        # 初始化交易对状态
        self._symbol_states.clear()
        for symbol in self.symbols:
            self._symbol_states[symbol] = SymbolState(symbol=symbol)

        # 清空缓存
        self._indicators_cache.clear()
        self._equity_curve.clear()

    def _calculate_all_indicators(self, klines_dict: Dict[str, pd.DataFrame]):
        """计算所有交易对的指标"""
        for symbol in self.symbols:
            if symbol not in klines_dict:
                logger.warning(f"交易对 {symbol} 无K线数据，跳过")
                continue

            klines_df = klines_dict[symbol]
            self._indicators_cache[symbol] = calculate_indicators(
                klines_df, self.interval_hours
            )

            logger.debug(f"计算 {symbol} 指标完成: {len(klines_df)} 根K线")

    def _get_aligned_timestamps(
        self,
        klines_dict: Dict[str, pd.DataFrame]
    ) -> List[int]:
        """获取对齐的时间戳列表"""
        all_timestamps = set()

        for symbol in self.symbols:
            if symbol in klines_dict:
                df = klines_dict[symbol]
                timestamps = [int(ts.timestamp() * 1000) for ts in df.index]
                all_timestamps.update(timestamps)

        return sorted(all_timestamps)

    def _process_timestamp(
        self,
        kline_index: int,
        timestamp: int,
        klines_dict: Dict[str, pd.DataFrame]
    ):
        """处理单个时间戳（所有交易对）"""
        for symbol in self.symbols:
            if symbol not in klines_dict:
                continue

            state = self._symbol_states[symbol]
            klines_df = klines_dict[symbol]
            indicators = self._indicators_cache.get(symbol, {})

            # 查找该时间戳对应的K线索引
            try:
                ts_datetime = pd.Timestamp(timestamp, unit='ms', tz='UTC')
                if ts_datetime not in klines_df.index:
                    continue
                idx = klines_df.index.get_loc(ts_datetime)
            except (KeyError, TypeError):
                continue

            if idx < 1:  # 至少需要前一根K线
                continue

            kline = klines_df.iloc[idx]
            low = Decimal(str(kline['low']))
            high = Decimal(str(kline['high']))
            close = Decimal(str(kline['close']))

            # 获取当前指标
            current_indicators = self._get_current_indicators(indicators, idx)

            # Step 1: 检查卖出挂单成交
            self._check_sell_orders(state, high, timestamp, symbol)

            # Step 2: 检查买入挂单成交
            self._check_buy_order(state, low, timestamp, symbol)

            # Step 3: 为持仓创建卖出挂单
            self._create_sell_orders(state, current_indicators, timestamp)

            # Step 4: 创建新的买入挂单
            self._create_buy_order(
                state, current_indicators, close, timestamp, idx, symbol
            )

    def _get_current_indicators(
        self,
        indicators: Dict[str, pd.Series],
        idx: int
    ) -> Dict[str, Any]:
        """获取指定索引的指标值"""
        result = {}
        for key, series in indicators.items():
            if idx < len(series):
                result[key] = series.iloc[idx]
            else:
                result[key] = None
        return result

    def _check_sell_orders(
        self,
        state: SymbolState,
        high: Decimal,
        timestamp: int,
        symbol: str
    ):
        """检查卖出挂单是否成交"""
        orders_to_remove = []

        for order_id, sell_order in state.pending_sell_orders.items():
            if order_id not in state.holdings:
                orders_to_remove.append(order_id)
                continue

            sell_price = Decimal(str(sell_order['price']))

            if is_sell_order_filled(high, sell_price):
                holding = state.holdings[order_id]
                buy_price = holding['buy_price']
                quantity = holding['quantity']

                profit_loss, profit_rate = calculate_profit(
                    sell_price, buy_price, quantity
                )

                logger.info(
                    f"[{symbol}] 卖出成交: {order_id}, "
                    f"卖价: {sell_price:.2f}, 盈亏: {profit_rate:.2f}%"
                )

                # 回收资金
                recovered = holding['amount'] + profit_loss
                self._capital_manager.add_profit(recovered, symbol, order_id, timestamp)

                # 减少持仓
                self._position_tracker.remove_holding(symbol)

                # 记录完成的订单
                completed = {
                    'buy_order_id': order_id,
                    'symbol': symbol,
                    'buy_price': float(buy_price),
                    'sell_price': float(sell_price),
                    'quantity': float(quantity),
                    'amount': float(holding['amount']),
                    'profit_loss': float(profit_loss),
                    'profit_rate': float(profit_rate),
                    'buy_timestamp': holding['buy_timestamp'],
                    'sell_timestamp': timestamp,
                    'exit_reason': sell_order['reason'],
                }
                state.add_completed_order(completed)

                del state.holdings[order_id]
                orders_to_remove.append(order_id)
            else:
                # 未成交，取消挂单（后续重新创建）
                orders_to_remove.append(order_id)

        for order_id in orders_to_remove:
            if order_id in state.pending_sell_orders:
                del state.pending_sell_orders[order_id]

    def _check_buy_order(
        self,
        state: SymbolState,
        low: Decimal,
        timestamp: int,
        symbol: str
    ):
        """检查买入挂单是否成交"""
        if state.pending_buy_order is None:
            return

        if not state.pending_buy_order.is_pending():
            state.pending_buy_order = None
            return

        order = state.pending_buy_order

        if is_buy_order_filled(low, order.price):
            # 成交
            order.mark_filled(timestamp)

            # 记录持仓
            state.holdings[order.order_id] = {
                'buy_price': order.price,
                'quantity': order.quantity,
                'amount': order.amount,
                'buy_timestamp': timestamp,
            }

            # 增加持仓计数
            self._position_tracker.add_holding(symbol)

            # 结算冻结资金
            self._capital_manager.settle(order.frozen_capital, symbol, order.order_id, timestamp)

            logger.info(
                f"[{symbol}] 买入成交: {order.order_id}, "
                f"价格: {order.price:.2f}, 数量: {order.quantity:.6f}"
            )
        else:
            # 未成交，取消挂单，解冻资金
            self._capital_manager.unfreeze(order.frozen_capital, symbol, order.order_id, timestamp)
            order.mark_cancelled()

        state.pending_buy_order = None

    def _create_sell_orders(
        self,
        state: SymbolState,
        indicators: Dict[str, Any],
        timestamp: int
    ):
        """为持仓创建卖出挂单"""
        ema25_val = indicators.get('ema25')
        p95_val = indicators.get('p95')
        cycle_phase = indicators.get('cycle_phase')

        if ema25_val is None or p95_val is None or cycle_phase is None:
            return
        if np.isnan(ema25_val) or np.isnan(p95_val):
            return

        ema25 = Decimal(str(ema25_val))
        p95 = Decimal(str(p95_val))

        for order_id, holding in state.holdings.items():
            if order_id in state.pending_sell_orders:
                continue

            sell_price, reason = calculate_sell_price(cycle_phase, ema25, p95)

            state.pending_sell_orders[order_id] = {
                'price': float(sell_price),
                'reason': reason,
                'cycle_phase': cycle_phase,
                'created_at': timestamp,
            }

    def _create_buy_order(
        self,
        state: SymbolState,
        indicators: Dict[str, Any],
        close: Decimal,
        timestamp: int,
        kline_index: int,
        symbol: str
    ):
        """创建买入挂单"""
        cycle_phase = indicators.get('cycle_phase')

        # bear_warning 跳过
        if should_skip_entry(cycle_phase):
            return

        # 检查全局持仓限制
        if not self._position_tracker.can_open_position():
            return

        # 计算动态仓位
        position_size = self._position_tracker.calculate_position_size(
            self._capital_manager.available_cash
        )
        if position_size <= 0:
            return

        # 检查可用资金
        if self._capital_manager.available_cash < position_size:
            return

        # 获取指标
        p5_val = indicators.get('p5')
        mid_val = indicators.get('inertia_mid')

        if p5_val is None or mid_val is None:
            return
        if np.isnan(p5_val) or np.isnan(mid_val):
            return

        p5 = Decimal(str(p5_val))
        inertia_mid = Decimal(str(mid_val))

        if p5 <= 0 or inertia_mid <= 0:
            return

        # 计算挂单价格
        base_price = calculate_base_price(p5, close, inertia_mid)
        order_price = calculate_order_price(base_price, self.discount)

        # 创建挂单
        quantity = position_size / order_price
        order_id = f"{symbol}_pending_{timestamp}_{kline_index}"

        order = PendingOrder(
            order_id=order_id,
            price=order_price,
            amount=position_size,
            quantity=quantity,
            status=PendingOrderStatus.PENDING,
            side=PendingOrderSide.BUY,
            frozen_capital=position_size,
            kline_index=kline_index,
            created_at=timestamp,
            metadata={
                'symbol': symbol,
                'base_price': float(base_price),
                'p5': float(p5),
                'close': float(close),
                'cycle_phase': cycle_phase,
            }
        )

        # 冻结资金
        if self._capital_manager.freeze(position_size, symbol, order_id, timestamp):
            state.pending_buy_order = order
            logger.debug(
                f"[{symbol}] 创建买入挂单: {order_id}, "
                f"价格: {order_price:.2f}, 金额: {position_size:.2f}"
            )

    def _record_equity(self, timestamp: int, klines_dict: Dict[str, pd.DataFrame]):
        """记录权益曲线点"""
        # 计算持仓市值
        holdings_value = Decimal("0")
        for symbol, state in self._symbol_states.items():
            if symbol not in klines_dict:
                continue
            df = klines_dict[symbol]
            try:
                ts_datetime = pd.Timestamp(timestamp, unit='ms', tz='UTC')
                if ts_datetime in df.index:
                    current_price = Decimal(str(df.loc[ts_datetime, 'close']))
                    for holding in state.holdings.values():
                        holdings_value += current_price * holding['quantity']
            except (KeyError, TypeError):
                pass

        equity = self._capital_manager.get_equity(holdings_value)

        self._equity_curve.append({
            'timestamp': timestamp,
            'equity': float(equity),
            'available_cash': float(self._capital_manager.available_cash),
            'frozen_cash': float(self._capital_manager.frozen_cash),
            'holdings_value': float(holdings_value),
        })

    def _generate_result(
        self,
        initial_capital: Decimal,
        timestamps: List[int],
        klines_dict: Dict[str, pd.DataFrame]
    ) -> Dict:
        """生成回测结果"""
        # 计算持仓市值（使用最后一个时间戳）
        holdings_value = Decimal("0")
        if timestamps:
            last_ts = timestamps[-1]
            for symbol, state in self._symbol_states.items():
                if symbol not in klines_dict:
                    continue
                df = klines_dict[symbol]
                try:
                    ts_datetime = pd.Timestamp(last_ts, unit='ms', tz='UTC')
                    if ts_datetime in df.index:
                        current_price = Decimal(str(df.loc[ts_datetime, 'close']))
                        for holding in state.holdings.values():
                            holdings_value += current_price * holding['quantity']
                except (KeyError, TypeError):
                    pass

        final_equity = self._capital_manager.get_equity(holdings_value)

        # 收集所有订单
        all_orders = []
        total_orders = 0
        winning_orders = 0
        total_profit = Decimal("0")

        by_symbol = {}
        for symbol, state in self._symbol_states.items():
            all_orders.extend(state.completed_orders)
            total_orders += state.total_orders
            winning_orders += state.winning_orders
            total_profit += state.total_profit_loss

            by_symbol[symbol] = {
                'orders': state.total_orders,
                'winning_orders': state.winning_orders,
                'win_rate': state.get_win_rate(),
                'profit_loss': float(state.total_profit_loss),
                'current_holdings': state.get_holding_count(),
            }

        # 计算统计指标
        win_rate = winning_orders / total_orders * 100 if total_orders > 0 else 0
        total_return = float(final_equity - initial_capital)
        total_return_rate = float(final_equity / initial_capital - 1) * 100

        # 计算回测天数
        trading_days = 1
        if timestamps and len(timestamps) >= 2:
            ms_per_day = 24 * 60 * 60 * 1000
            trading_days = max((timestamps[-1] - timestamps[0]) / ms_per_day, 1)

        # 计算APR和APY
        apr = total_return_rate / trading_days * 365 if trading_days > 0 else 0

        # 计算最大回撤
        max_drawdown = self._calculate_max_drawdown()

        return {
            'global': {
                'initial_capital': float(initial_capital),
                'final_capital': float(final_equity),
                'total_return': total_return,
                'total_return_rate': total_return_rate,
                'total_orders': total_orders,
                'winning_orders': winning_orders,
                'open_positions': self._position_tracker.total_holdings,
                'win_rate': win_rate,
                'max_drawdown': max_drawdown,
                'apr': apr,
                'trading_days': int(trading_days),
                'symbols': self.symbols,
            },
            'by_symbol': by_symbol,
            'orders': sorted(all_orders, key=lambda x: x.get('buy_timestamp', 0)),
            'equity_curve': self._equity_curve,
        }

    def _calculate_max_drawdown(self) -> float:
        """计算最大回撤"""
        if not self._equity_curve:
            return 0.0

        peak = 0.0
        max_dd = 0.0

        for point in self._equity_curve:
            equity = point['equity']
            if equity > peak:
                peak = equity
            if peak > 0:
                dd = (peak - equity) / peak
                if dd > max_dd:
                    max_dd = dd

        return max_dd * 100  # 转为百分比

    # === IStrategy 接口的其他方法（回测模式下不使用） ===

    def generate_buy_signals(self, klines, indicators):
        return []

    def generate_sell_signals(self, klines, indicators, open_orders):
        return []

    def calculate_position_size(self, signal, available_capital, current_price):
        return self._position_tracker.calculate_position_size(available_capital)

    def should_stop_loss(self, order, current_price, current_timestamp):
        return False

    def should_take_profit(self, order, current_price, current_timestamp):
        return False
