"""
多策略适配器

Purpose:
    编排多个策略的回测执行，管理共享资金池和卖出条件。

关联任务: TASK-017-013, TASK-017-014
关联功能点: FP-017-013~015

Classes:
    - MultiStrategyAdapter: 多策略适配器
"""

import logging
from decimal import Decimal
from typing import List, Dict, Any, Tuple, Optional

import pandas as pd

from strategy_adapter.interfaces.strategy import IStrategy
from strategy_adapter.models.order import Order
from strategy_adapter.models.enums import OrderStatus, OrderSide
from strategy_adapter.exits import ExitConditionCombiner, ExitSignal
from strategy_adapter.core.shared_capital_manager import SharedCapitalManager
from strategy_adapter.core.unified_order_manager import UnifiedOrderManager

logger = logging.getLogger(__name__)


class MultiStrategyAdapter:
    """
    多策略适配器

    编排多个策略的回测执行，实现：
    - 多策略信号收集和合并
    - 共享资金池管理
    - 自定义卖出条件检查

    Usage:
        adapter = MultiStrategyAdapter(
            strategies=[(id1, strategy1), (id2, strategy2)],
            exit_combiners={id1: combiner1, id2: combiner2},
            capital_manager=capital_manager,
            order_manager=order_manager
        )
        result = adapter.adapt_for_backtest(klines, indicators, initial_cash, symbol)
    """

    def __init__(
        self,
        strategies: List[Tuple[str, IStrategy]],
        exit_combiners: Dict[str, ExitConditionCombiner],
        capital_manager: SharedCapitalManager,
        order_manager: UnifiedOrderManager,
        commission_rate: Decimal = Decimal("0.001")
    ):
        """
        初始化多策略适配器

        Args:
            strategies: 策略列表，每个元素为 (config_strategy_id, strategy_instance)
            exit_combiners: 卖出条件组合器字典，key为config_strategy_id
            capital_manager: 共享资金管理器
            order_manager: 订单管理器
            commission_rate: 手续费率
        """
        self._strategies = strategies
        self._exit_combiners = exit_combiners
        self._capital_manager = capital_manager
        self._order_manager = order_manager
        self._commission_rate = commission_rate

        logger.info(
            f"初始化多策略适配器: {len(strategies)}个策略, "
            f"策略IDs: {[s[0] for s in strategies]}"
        )

    def adapt_for_backtest(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series],
        initial_cash: Decimal,
        symbol: str
    ) -> Dict:
        """
        执行多策略回测

        Args:
            klines: K线数据DataFrame，包含open, high, low, close, volume
            indicators: 技术指标字典
            initial_cash: 初始资金
            symbol: 交易对

        Returns:
            Dict: 回测结果
                - entries: 买入信号Series
                - exits: 卖出信号Series
                - orders: 订单列表
                - statistics: 统计信息
                - strategy_statistics: 按策略分组的统计
        """
        # 重置状态
        self._capital_manager.reset()
        self._order_manager.reset()

        # 初始化结果
        entries = pd.Series(0, index=klines.index)
        exits = pd.Series(0, index=klines.index)

        # Step 0: 预先收集所有策略的买入信号（按时间戳索引）
        all_signals_by_timestamp = self._collect_all_signals(klines, indicators, symbol)
        logger.info(f"预收集信号完成: {sum(len(v) for v in all_signals_by_timestamp.values())}个信号")

        # 遍历每根K线
        for idx in range(len(klines)):
            row = klines.iloc[idx]
            timestamp = int(row.name) if isinstance(row.name, (int, float)) else int(row.name.timestamp() * 1000)

            # 构建当前K线数据
            kline_data = {
                'open': Decimal(str(row['open'])),
                'high': Decimal(str(row['high'])),
                'low': Decimal(str(row['low'])),
                'close': Decimal(str(row['close'])),
                'volume': Decimal(str(row['volume'])) if 'volume' in row else Decimal("0"),
            }

            # 构建当前指标数据
            current_indicators = {}
            for key, series in indicators.items():
                if idx < len(series):
                    value = series.iloc[idx]
                    if pd.notna(value):
                        current_indicators[key] = value

            # Step 1: 检查卖出条件（先平仓后开仓）
            exit_count = self._check_exit_conditions(
                kline_data, current_indicators, timestamp
            )
            exits.iloc[idx] = exit_count

            # Step 2: 获取当前时间戳的买入信号
            buy_signals = all_signals_by_timestamp.get(timestamp, [])

            # Step 3: 处理买入信号
            entry_count = self._process_buy_signals(
                buy_signals, kline_data, timestamp, symbol
            )
            entries.iloc[idx] = entry_count

        # 构建结果
        orders = self._order_manager.get_all_orders()
        statistics = self._calculate_statistics(orders, initial_cash)
        strategy_statistics = self._calculate_strategy_statistics(orders, initial_cash)

        return {
            'entries': entries,
            'exits': exits,
            'orders': orders,
            'statistics': statistics,
            'strategy_statistics': strategy_statistics,
        }

    def _collect_all_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series],
        symbol: str
    ) -> Dict[int, List[Dict[str, Any]]]:
        """
        预先收集所有策略的买入/做空信号

        调用每个策略的generate_buy_signals()和generate_short_signals()方法，
        将结果按时间戳索引存储。

        Args:
            klines: K线数据
            indicators: 指标数据
            symbol: 交易对

        Returns:
            Dict[int, List]: 按时间戳索引的信号列表
        """
        signals_by_timestamp: Dict[int, List[Dict[str, Any]]] = {}

        for config_strategy_id, strategy in self._strategies:
            # 收集做多信号
            try:
                buy_signals = strategy.generate_buy_signals(klines, indicators)
                for signal in buy_signals:
                    ts = signal['timestamp']
                    if ts not in signals_by_timestamp:
                        signals_by_timestamp[ts] = []
                    signals_by_timestamp[ts].append({
                        'config_strategy_id': config_strategy_id,
                        'strategy': strategy,
                        'timestamp': ts,
                        'price': signal.get('price'),
                        'reason': signal.get('reason', ''),
                        'direction': signal.get('direction', 'long'),
                        'symbol': symbol,
                    })
                logger.debug(
                    f"策略 {config_strategy_id} 生成 {len(buy_signals)} 个做多信号"
                )
            except Exception as e:
                logger.warning(f"策略 {config_strategy_id} 生成做多信号失败: {e}")

            # 收集做空信号（如果策略支持）
            if hasattr(strategy, 'generate_short_signals'):
                try:
                    short_signals = strategy.generate_short_signals(klines, indicators)
                    for signal in short_signals:
                        ts = signal['timestamp']
                        if ts not in signals_by_timestamp:
                            signals_by_timestamp[ts] = []
                        signals_by_timestamp[ts].append({
                            'config_strategy_id': config_strategy_id,
                            'strategy': strategy,
                            'timestamp': ts,
                            'price': signal.get('price'),
                            'reason': signal.get('reason', ''),
                            'direction': signal.get('direction', 'short'),
                            'symbol': symbol,
                        })
                    logger.debug(
                        f"策略 {config_strategy_id} 生成 {len(short_signals)} 个做空信号"
                    )
                except Exception as e:
                    logger.warning(f"策略 {config_strategy_id} 生成做空信号失败: {e}")

        return signals_by_timestamp

    def _process_buy_signals(
        self,
        signals: List[Dict[str, Any]],
        kline_data: Dict[str, Any],
        timestamp: int,
        symbol: str
    ) -> int:
        """
        处理买入/做空信号

        Args:
            signals: 买入/做空信号列表
            kline_data: K线数据
            timestamp: 时间戳
            symbol: 交易对

        Returns:
            int: 成功创建的订单数
        """
        created_count = 0
        position_size = self._capital_manager.get_position_size()

        for signal in signals:
            # 检查是否可以分配资金
            if not self._capital_manager.can_allocate(position_size):
                logger.warning(
                    f"资金不足或持仓已满，跳过信号: strategy={signal['config_strategy_id']}"
                )
                continue

            # 获取开仓价格
            price = signal.get('price')
            if price is None:
                price = kline_data['close']
            price = Decimal(str(price))

            # 计算数量
            quantity = position_size / price

            # 计算手续费
            commission = position_size * self._commission_rate

            # 确定交易方向
            direction = signal.get('direction', 'long')
            order_side = OrderSide.BUY if direction == 'long' else OrderSide.SELL

            # 创建订单
            strategy = signal['strategy']
            order = Order(
                id=f"order_{timestamp}_{signal['config_strategy_id']}",
                symbol=symbol,
                side=order_side,
                status=OrderStatus.FILLED,
                open_timestamp=timestamp,
                open_price=price,
                quantity=quantity,
                position_value=position_size,
                strategy_name=strategy.get_strategy_name(),
                strategy_id=signal.get('strategy_id', ''),
                config_strategy_id=signal['config_strategy_id'],
                entry_reason=signal.get('reason', ''),
                open_commission=commission,
                direction=direction,
            )

            # 添加到订单管理器
            self._order_manager.add_order(order)

            # 分配资金
            self._capital_manager.allocate(position_size)

            created_count += 1
            direction_str = '做多' if direction == 'long' else '做空'
            logger.debug(
                f"创建订单: {order.id}, 策略={signal['config_strategy_id']}, "
                f"方向={direction_str}, 价格={price}, 数量={quantity}"
            )

        return created_count

    def _check_exit_conditions(
        self,
        kline_data: Dict[str, Any],
        indicators: Dict[str, Any],
        timestamp: int
    ) -> int:
        """
        检查所有持仓订单的卖出条件

        Args:
            kline_data: K线数据
            indicators: 指标数据
            timestamp: 时间戳

        Returns:
            int: 平仓订单数
        """
        closed_count = 0
        open_orders = self._order_manager.get_open_orders()

        for order in open_orders:
            # 获取该订单策略的卖出条件组合器
            config_strategy_id = order.config_strategy_id
            combiner = self._exit_combiners.get(config_strategy_id)

            if combiner is None:
                # 如果没有配置卖出条件，使用收盘价检查默认条件
                continue

            # 检查卖出条件
            exit_signal = combiner.check_all(order, kline_data, indicators, timestamp)

            if exit_signal:
                # 平仓
                self._close_order(order, exit_signal, timestamp)
                closed_count += 1

        return closed_count

    def _close_order(self, order: Order, exit_signal: ExitSignal, timestamp: int):
        """
        平仓订单

        Args:
            order: 订单
            exit_signal: 卖出信号
            timestamp: 时间戳
        """
        # 计算平仓手续费
        close_value = order.quantity * exit_signal.price
        close_commission = close_value * self._commission_rate

        # 更新订单
        order.status = OrderStatus.CLOSED
        order.close_timestamp = timestamp
        order.close_price = exit_signal.price
        order.close_reason = exit_signal.exit_type
        order.close_commission = close_commission

        # 计算盈亏
        order.calculate_pnl()

        # 释放资金
        pnl = order.profit_loss or Decimal("0")
        self._capital_manager.release(order.position_value, pnl)

        logger.debug(
            f"平仓订单: {order.id}, 原因={exit_signal.reason}, "
            f"价格={exit_signal.price}, 盈亏={pnl}"
        )

    def _calculate_statistics(
        self,
        orders: List[Order],
        initial_cash: Decimal
    ) -> Dict[str, Any]:
        """
        计算整体统计信息

        Args:
            orders: 订单列表
            initial_cash: 初始资金

        Returns:
            Dict: 统计信息
        """
        total_orders = len(orders)
        closed_orders = [o for o in orders if o.status == OrderStatus.CLOSED]
        open_orders = [o for o in orders if o.status == OrderStatus.FILLED]

        # 盈亏统计
        winning_orders = [o for o in closed_orders if o.profit_loss and o.profit_loss > 0]
        losing_orders = [o for o in closed_orders if o.profit_loss and o.profit_loss < 0]

        total_profit = sum(o.profit_loss for o in winning_orders)
        total_loss = sum(abs(o.profit_loss) for o in losing_orders)
        net_profit = total_profit - total_loss

        # 胜率
        win_rate = len(winning_orders) / len(closed_orders) * 100 if closed_orders else 0

        return {
            'total_orders': total_orders,
            'closed_orders': len(closed_orders),
            'open_orders': len(open_orders),
            'winning_orders': len(winning_orders),
            'losing_orders': len(losing_orders),
            'total_profit': float(total_profit),
            'total_loss': float(total_loss),
            'net_profit': float(net_profit),
            'win_rate': win_rate,
            'return_rate': float(net_profit / initial_cash * 100) if initial_cash else 0,
        }

    def _calculate_strategy_statistics(
        self,
        orders: List[Order],
        initial_cash: Decimal
    ) -> Dict[str, Dict[str, Any]]:
        """
        按策略分组计算统计信息

        Args:
            orders: 订单列表
            initial_cash: 初始资金

        Returns:
            Dict: 按策略ID分组的统计信息
        """
        strategy_orders: Dict[str, List[Order]] = {}

        for order in orders:
            strategy_id = order.config_strategy_id or 'unknown'
            if strategy_id not in strategy_orders:
                strategy_orders[strategy_id] = []
            strategy_orders[strategy_id].append(order)

        result = {}
        for strategy_id, orders_list in strategy_orders.items():
            closed = [o for o in orders_list if o.status == OrderStatus.CLOSED]
            winning = [o for o in closed if o.profit_loss and o.profit_loss > 0]
            losing = [o for o in closed if o.profit_loss and o.profit_loss < 0]

            total_profit = sum(o.profit_loss for o in winning)
            total_loss = sum(abs(o.profit_loss) for o in losing)

            result[strategy_id] = {
                'total_orders': len(orders_list),
                'closed_orders': len(closed),
                'winning_orders': len(winning),
                'losing_orders': len(losing),
                'total_profit': float(total_profit),
                'total_loss': float(total_loss),
                'net_profit': float(total_profit - total_loss),
                'win_rate': len(winning) / len(closed) * 100 if closed else 0,
            }

        return result
