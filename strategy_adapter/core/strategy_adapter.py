"""
策略适配器

本模块实现StrategyAdapter，负责编排协调策略方法、订单管理器、信号转换器，
将应用层策略适配为vectorbt回测引擎所需的格式。

核心功能：
- 编排协调：调用策略的generate_buy_signals()和generate_sell_signals()
- 订单管理：使用UnifiedOrderManager管理订单生命周期
- 信号转换：使用SignalConverter转换信号格式
- 统计计算：生成完整的回测统计数据

适配流程（8个步骤）：
1. 生成买入信号（调用strategy.generate_buy_signals()）
2. 创建订单（调用order_manager.create_order()）
3. 获取持仓订单（调用order_manager.get_open_orders()）
4. 生成卖出信号（调用strategy.generate_sell_signals()，传入open_orders）
5. 更新订单（调用order_manager.update_order()）
6. 转换信号（调用SignalConverter.to_vectorbt_signals()）
7. 获取所有订单（包括持仓和已平仓）
8. 计算统计（调用order_manager.calculate_statistics()）

状态管理职责分配：
- StrategyAdapter：负责管理持仓订单列表（open_orders），作为参数传递给策略
- IStrategy：无状态设计，不保存任何订单或持仓信息
- UnifiedOrderManager：负责订单存储和查询

迭代编号: 013 (策略适配层)
创建日期: 2026-01-06
关联任务: TASK-013-007
关联需求: FP-013-007 (prd.md)
关联架构: architecture.md#4.3 核心组件模块
"""

from typing import Dict, List, Optional
from decimal import Decimal
import pandas as pd
import logging

from strategy_adapter.interfaces import IStrategy
from strategy_adapter.core.unified_order_manager import UnifiedOrderManager
from strategy_adapter.core.signal_converter import SignalConverter
from strategy_adapter.models import Order

logger = logging.getLogger(__name__)


class StrategyAdapter:
    """
    策略适配器（Strategy Adapter）

    职责：
    - 编排协调策略、订单管理器、信号转换器
    - 管理持仓订单列表状态
    - 生成vectorbt所需的完整回测数据

    设计原则：
    - StrategyAdapter是有状态的（持有order_manager）
    - 调用的策略IStrategy是无状态的（通过参数传递状态）

    Example:
        >>> strategy = DDPSZStrategy()
        >>> adapter = StrategyAdapter(strategy)
        >>> result = adapter.adapt_for_backtest(klines, indicators, Decimal("10000"))
        >>> print(result['statistics']['win_rate'])  # 65.0
    """

    def __init__(
        self,
        strategy: IStrategy,
        order_manager: Optional[UnifiedOrderManager] = None
    ):
        """
        初始化策略适配器

        Args:
            strategy (IStrategy): 策略实例（必须实现IStrategy接口）
            order_manager (Optional[UnifiedOrderManager]): 订单管理器（可选，默认创建新实例）

        Raises:
            TypeError: 当strategy未实现IStrategy接口时抛出

        Example:
            >>> strategy = DDPSZStrategy()
            >>> adapter = StrategyAdapter(strategy)
            >>> print(adapter.strategy.get_strategy_name())  # "DDPS-Z"
        """
        # Guard Clause: 验证策略实例类型
        if not isinstance(strategy, IStrategy):
            raise TypeError(
                f"strategy必须实现IStrategy接口，当前类型: {type(strategy).__name__}。\n"
                f"请确保策略类继承自IStrategy并实现所有抽象方法。"
            )

        self.strategy = strategy
        self.order_manager = order_manager or UnifiedOrderManager()

        logger.info(f"初始化StrategyAdapter: 策略={strategy.get_strategy_name()}, "
                   f"版本={strategy.get_strategy_version()}")

    def adapt_for_backtest(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series],
        initial_cash: Decimal = Decimal("10000"),
        symbol: str = "ETHUSDT"
    ) -> Dict:
        """
        适配策略用于回测

        编排整个适配流程：生成信号 → 创建订单 → 平仓订单 → 转换信号 → 计算统计。

        Args:
            klines (pd.DataFrame): K线DataFrame，index必须为pd.DatetimeIndex
                必须包含列：['open', 'high', 'low', 'close', 'volume']
            indicators (Dict[str, pd.Series]): 技术指标字典
                例如：{'ema25': pd.Series, 'rsi': pd.Series}
            initial_cash (Decimal): 初始资金（USDT），默认10000
            symbol (str): 交易对符号，默认"ETHUSDT"

        Returns:
            Dict: 完整的回测数据结构
                {
                    'entries': pd.Series,      # vectorbt买入信号（布尔序列）
                    'exits': pd.Series,        # vectorbt卖出信号（布尔序列）
                    'orders': List[Order],     # 所有订单列表（持仓 + 已平仓）
                    'statistics': Dict         # 统计信息（胜率、总盈亏等）
                }

        Raises:
            ValueError: 当klines为空DataFrame时抛出
            ValueError: 当initial_cash <= 0时抛出
            KeyError: 当indicators缺少策略所需指标时抛出（由strategy抛出）
            ValueError: 当信号时间戳不在K线范围内时抛出（由SignalConverter抛出）

        Side Effects:
            - 调用order_manager创建和更新订单
            - 记录日志（开始、信号数量、完成）

        Example:
            >>> klines = pd.DataFrame({'open': [...], 'close': [...]},
            ...     index=pd.DatetimeIndex(['2026-01-06 00:00', ...], tz='UTC'))
            >>> indicators = {'ema25': pd.Series([...])}
            >>> adapter = StrategyAdapter(DDPSZStrategy())
            >>> result = adapter.adapt_for_backtest(klines, indicators)
            >>> print(result['statistics']['total_orders'])  # 10
            >>> print(result['statistics']['win_rate'])  # 65.0
        """
        # Guard Clause: 验证K线数据
        if klines.empty:
            raise ValueError(
                "klines不能为空DataFrame。\n"
                "请确保K线数据已正确加载（使用update_klines命令）。"
            )

        # Guard Clause: 验证初始资金
        if initial_cash <= 0:
            raise ValueError(f"initial_cash必须大于0，当前值: {initial_cash}")

        logger.info(f"开始适配策略: {self.strategy.get_strategy_name()}")
        logger.info(f"K线数据: {len(klines)}根, 时间范围: {klines.index[0]} ~ {klines.index[-1]}")
        logger.info(f"初始资金: {initial_cash} USDT")

        # === 步骤1: 生成所有买入信号 ===
        all_buy_signals = self.strategy.generate_buy_signals(klines, indicators)
        logger.info(f"生成买入信号: {len(all_buy_signals)}个")

        # 🆕 Bug-016修复：按时间排序买入信号（确保时序正确）
        sorted_buy_signals = sorted(all_buy_signals, key=lambda s: s['timestamp'])

        # === 步骤2: 时序模拟 - 按时间顺序处理买卖信号 ===
        # 核心逻辑：每次处理买入信号前，先检查并平仓到期订单，释放资金
        available_capital = initial_cash
        created_orders = 0
        skipped_signals = 0

        for buy_signal in sorted_buy_signals:
            # 2.1 先处理卖出信号（时间 <= 当前买入信号时间）
            open_orders = self.order_manager.get_open_orders()
            if open_orders:
                # 生成卖出信号
                sell_signals = self.strategy.generate_sell_signals(
                    klines, indicators, open_orders
                )

                # 只处理时间早于或等于当前买入信号的卖出
                for sell_signal in sell_signals:
                    if sell_signal['timestamp'] <= buy_signal['timestamp']:
                        order = self.order_manager._orders[sell_signal['order_id']]
                        self.order_manager.update_order(sell_signal['order_id'], sell_signal)

                        # 释放资金（归还本金 + 盈亏）
                        available_capital += order.position_value + (order.profit_loss or Decimal("0"))

                        # 改进日志
                        buy_time = pd.Timestamp(order.open_timestamp, unit='ms', tz='UTC')
                        sell_time = pd.Timestamp(sell_signal['timestamp'], unit='ms', tz='UTC')
                        holding_hours = (sell_signal['timestamp'] - order.open_timestamp) / 3600000
                        total_commission = order.open_commission + order.close_commission

                        logger.info(
                            f"平仓订单: {sell_signal['order_id']}, "
                            f"买入时间: {buy_time.strftime('%Y-%m-%d %H:%M')}, "
                            f"卖出时间: {sell_time.strftime('%Y-%m-%d %H:%M')}, "
                            f"持仓: {holding_hours:.1f}小时, "
                            f"盈亏: {order.profit_loss:.2f} USDT ({order.profit_loss_rate:.2f}%), "
                            f"手续费: {total_commission:.2f} USDT (开仓{order.open_commission:.2f} + 平仓{order.close_commission:.2f}), "
                            f"剩余资金: {available_capital:.2f} USDT"
                        )

            # 2.2 尝试创建买入订单
            current_price = Decimal(str(buy_signal['price']))
            position_size = self.strategy.calculate_position_size(
                buy_signal, available_capital, current_price
            )

            # 资金不足时跳过
            if position_size <= 0 or available_capital < position_size:
                logger.warning(
                    f"资金不足，跳过买入信号: timestamp={buy_signal['timestamp']}, "
                    f"所需资金={position_size:.2f}, 可用资金={available_capital:.2f}"
                )
                skipped_signals += 1
                continue

            # 创建订单
            order = self.order_manager.create_order(
                buy_signal, self.strategy, current_price, available_capital, symbol
            )
            available_capital -= order.position_value
            created_orders += 1
            logger.debug(f"创建订单: {order.id}, 剩余资金: {available_capital:.2f}")

        logger.info(f"买入信号处理完成: 创建{created_orders}个订单, 跳过{skipped_signals}个信号")

        # === 步骤3: 处理剩余的未平仓订单 ===
        open_orders = self.order_manager.get_open_orders()
        logger.info(f"剩余持仓订单: {len(open_orders)}个")

        if open_orders:
            # 生成卖出信号
            sell_signals = self.strategy.generate_sell_signals(
                klines, indicators, open_orders
            )
            logger.info(f"生成卖出信号: {len(sell_signals)}个")

            # 平仓所有剩余订单
            for sell_signal in sell_signals:
                order = self.order_manager._orders[sell_signal['order_id']]
                self.order_manager.update_order(sell_signal['order_id'], sell_signal)

                # 释放资金
                available_capital += order.position_value + (order.profit_loss or Decimal("0"))

                # 改进日志
                buy_time = pd.Timestamp(order.open_timestamp, unit='ms', tz='UTC')
                sell_time = pd.Timestamp(sell_signal['timestamp'], unit='ms', tz='UTC')
                holding_hours = (sell_signal['timestamp'] - order.open_timestamp) / 3600000
                total_commission = order.open_commission + order.close_commission

                logger.info(
                    f"平仓订单: {sell_signal['order_id']}, "
                    f"买入时间: {buy_time.strftime('%Y-%m-%d %H:%M')}, "
                    f"卖出时间: {sell_time.strftime('%Y-%m-%d %H:%M')}, "
                    f"持仓: {holding_hours:.1f}小时, "
                    f"盈亏: {order.profit_loss:.2f} USDT ({order.profit_loss_rate:.2f}%), "
                    f"手续费: {total_commission:.2f} USDT (开仓{order.open_commission:.2f} + 平仓{order.close_commission:.2f}), "
                    f"剩余资金: {available_capital:.2f} USDT"
                )

        # === 步骤4: 转换信号为vectorbt格式 ===
        # 收集所有成功创建的买入信号和卖出信号
        all_orders = list(self.order_manager._orders.values())
        actual_buy_signals = [
            {'timestamp': o.open_timestamp, 'price': o.open_price}
            for o in all_orders
        ]
        actual_sell_signals = [
            {'timestamp': o.close_timestamp, 'price': o.close_price, 'order_id': o.id}
            for o in all_orders if o.close_timestamp
        ]

        entries, exits = SignalConverter.to_vectorbt_signals(
            actual_buy_signals, actual_sell_signals, klines
        )
        logger.info(f"信号转换完成: entries={entries.sum()}个, exits={exits.sum()}个")

        # === 步骤7: 获取所有订单 ===
        # 包括持仓订单和已平仓订单
        all_orders = list(self.order_manager._orders.values())

        # === 步骤8: 计算统计 ===
        # 计算胜率、总盈亏、平均收益率等指标
        statistics = self.order_manager.calculate_statistics(all_orders)
        logger.info(f"适配完成: {statistics['total_orders']}个订单, "
                   f"胜率={statistics['win_rate']:.2f}%, "
                   f"总盈亏={statistics['total_profit']}")

        # 返回完整的回测数据结构
        return {
            'entries': entries,
            'exits': exits,
            'orders': all_orders,
            'statistics': statistics
        }
