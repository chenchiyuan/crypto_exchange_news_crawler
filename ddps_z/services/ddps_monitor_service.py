"""
DDPS价格监控核心服务
DDPS Monitor Service

核心监控服务类，提供DDPS指标计算和信号检测能力，可被多个命令复用。
迭代024重构：使用Repository加载数据，使用Calculator计算指标。
迭代038升级：集成Strategy16Runner，使用策略16进行信号检测。

功能特性:
    - calculate_all: 计算所有交易对的完整DDPS指标
    - monitor: 监控方法（新增，支持多市场多周期）
    - get_buy_signals: 检测满足买入条件的交易对（迭代038升级为策略16）
    - get_exit_signals: 检查订单的卖出条件（迭代038升级为策略16）
    - get_cycle_warnings: 获取周期预警信息
    - get_price_status: 获取所有交易对的价格状态（迭代038扩展字段）

使用示例:
    from ddps_z.services import DDPSMonitorService
    from ddps_z.datasources import KLineRepository
    from ddps_z.calculators import DDPSCalculator

    # 新用法（迭代024）
    service = DDPSMonitorService()
    result = service.monitor(
        symbols=['ETHUSDT', 'BTCUSDT'],
        interval='4h',
        market_type='crypto_futures'
    )

    # 旧用法（向后兼容）
    service = DDPSMonitorService(
        symbols=['ETHUSDT', 'BTCUSDT'],
        strategy_id=7
    )
    result = service.calculate_all()

Related:
    - PRD: docs/iterations/023-ddps-price-monitor/prd.md
    - Architecture: docs/iterations/024-ddps-multi-market-support/architecture.md
    - Architecture: docs/iterations/038-ddps-monitor-strategy16-upgrade/architecture.md
    - Task: TASK-023-005, TASK-023-006, TASK-023-007, TASK-023-008, TASK-024-007
    - Task: TASK-038-003, TASK-038-004, TASK-038-005, TASK-038-006, TASK-038-007, TASK-038-008
"""

import logging
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Any

from ddps_z.models import (
    VirtualOrder,
    PriceStatus,
    BuySignal,
    ExitSignal,
    CycleWarning,
    DDPSMonitorResult,
    Interval,
    HoldingInfo,
)
from ddps_z.calculators import DDPSCalculator, DDPSResult
from ddps_z.datasources import KLineRepository

logger = logging.getLogger(__name__)


class DDPSMonitorService:
    """
    DDPS价格监控核心服务

    提供DDPS指标计算和策略信号检测能力。
    迭代024重构：通过Repository加载数据，通过Calculator计算指标。
    迭代038升级：集成Strategy16Runner进行精准信号检测。

    Attributes:
        repository: K线数据仓库（可选，默认创建新实例）
        calculator: DDPS计算器（可选，默认创建新实例）
        _orders: 虚拟订单列表（内存管理）
        _indicators_cache: 指标缓存
        _strategy16_cache: 策略16结果缓存（迭代038新增）

    向后兼容:
        仍然支持旧的 __init__(symbols, strategy_id, interval, market_type) 调用方式
    """

    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        strategy_id: int = 16,  # 迭代038: 默认使用策略16
        interval: str = '4h',
        market_type: str = 'futures',
        repository: Optional[KLineRepository] = None,
        calculator: Optional[DDPSCalculator] = None
    ):
        """
        初始化监控服务

        Args:
            symbols: 交易对列表（向后兼容，新代码建议使用monitor方法）
            strategy_id: 策略ID，默认16（迭代038升级）
            interval: K线周期，默认'4h'（向后兼容）
            market_type: 市场类型，默认'futures'（向后兼容）
            repository: K线数据仓库（迭代024新增）
            calculator: DDPS计算器（迭代024新增）
        """
        # 依赖注入
        self.repository = repository or KLineRepository()
        self.calculator = calculator or DDPSCalculator()

        # 向后兼容属性
        self.symbols = [s.upper() for s in symbols] if symbols else []
        self.strategy_id = strategy_id
        self.interval = interval
        self.market_type = market_type

        # 虚拟订单管理（内存）
        self._orders: List[VirtualOrder] = []

        # 指标缓存
        self._indicators_cache: Dict[str, dict] = {}

        # 🆕 迭代038: 策略16结果缓存
        self._strategy16_cache: Dict[str, Dict[str, Any]] = {}

        if symbols:
            logger.info(
                f"DDPSMonitorService初始化: symbols={symbols}, "
                f"strategy_id={strategy_id}, interval={interval}"
            )
        else:
            logger.info("DDPSMonitorService初始化（新模式）")

    def calculate_all(self) -> DDPSMonitorResult:
        """
        计算所有交易对的完整DDPS指标（向后兼容方法）

        Returns:
            DDPSMonitorResult: 包含买入信号、卖出信号、周期预警、价格状态的完整结果

        Side Effects:
            更新_indicators_cache缓存
        """
        return self.monitor(
            symbols=self.symbols,
            interval=self.interval,
            market_type=self.market_type,
            strategy_id=self.strategy_id
        )

    def monitor(
        self,
        symbols: List[str],
        interval: str = '4h',
        market_type: str = 'crypto_futures',
        strategy_id: int = 16  # 迭代038: 默认使用策略16
    ) -> DDPSMonitorResult:
        """
        监控交易对（迭代024新增，迭代038升级为策略16）

        使用Repository加载数据，使用Calculator计算指标。
        迭代038: 集成Strategy16Runner进行信号检测。

        Args:
            symbols: 交易对列表
            interval: K线周期，如'4h', '1h', '1d'
            market_type: 市场类型，如'crypto_futures', 'crypto_spot'
            strategy_id: 策略ID，默认16

        Returns:
            DDPSMonitorResult: 完整监控结果
        """
        logger.info(
            f"开始监控 {len(symbols)} 个交易对: "
            f"interval={interval}, market_type={market_type}, strategy_id={strategy_id}"
        )

        # 清空缓存
        self._indicators_cache = {}
        self._strategy16_cache = {}  # 🆕 迭代038

        # 获取interval_hours用于周期持续时间计算
        interval_hours = Interval.to_hours(interval)

        # 计算每个交易对的指标
        for symbol in symbols:
            try:
                indicators = self._calculate_symbol_indicators(
                    symbol=symbol,
                    interval=interval,
                    market_type=market_type,
                    interval_hours=interval_hours
                )
                if indicators:
                    self._indicators_cache[symbol] = indicators

                    # 🆕 迭代038: 运行策略16获取holdings和pending_order
                    strategy16_result = self._run_strategy16(
                        symbol=symbol,
                        interval=interval,
                        market_type=market_type
                    )
                    if strategy16_result:
                        self._strategy16_cache[symbol] = strategy16_result

            except Exception as e:
                logger.error(f"计算{symbol}指标失败: {e}")
                continue

        # 汇总结果
        result = DDPSMonitorResult(
            buy_signals=self.get_buy_signals(),
            exit_signals=self.get_exit_signals(),
            cycle_warnings=self.get_cycle_warnings(),
            price_status=self.get_price_status(),
            update_stats={
                'total_symbols': len(symbols),
                'calculated_symbols': len(self._indicators_cache),
                'failed_symbols': len(symbols) - len(self._indicators_cache),
                'interval': interval,
                'market_type': market_type,
            }
        )

        logger.info(
            f"计算完成: 成功={len(self._indicators_cache)}, "
            f"买入信号={len(result.buy_signals)}, "
            f"卖出信号={len(result.exit_signals)}"
        )

        return result

    def _calculate_symbol_indicators(
        self,
        symbol: str,
        interval: str,
        market_type: str,
        interval_hours: float
    ) -> Optional[dict]:
        """
        计算单个交易对的所有指标

        使用Repository加载数据，使用Calculator计算。

        Args:
            symbol: 交易对
            interval: K线周期
            market_type: 市场类型
            interval_hours: K线周期小时数

        Returns:
            dict: 包含所有指标的字典，计算失败返回None
        """
        # 使用Repository加载K线数据
        klines = self.repository.load(
            symbol=symbol,
            interval=interval,
            market_type=market_type,
            limit=500
        )

        if not klines or len(klines) < 180:
            logger.warning(
                f"{symbol}: K线数据不足 ({len(klines) if klines else 0}/180)"
            )
            return None

        # 使用Calculator计算DDPS指标
        result: Optional[DDPSResult] = self.calculator.calculate(
            klines=klines,
            interval_hours=interval_hours
        )

        if result is None:
            logger.warning(f"{symbol}: 计算失败")
            return None

        return {
            'symbol': symbol,
            'current_price': result.current_price,
            'ema25': result.ema25,
            'p5': result.p5,
            'p95': result.p95,
            'inertia_mid': result.inertia_mid,
            'inertia_upper': result.inertia_upper,
            'inertia_lower': result.inertia_lower,
            'cycle_phase': result.cycle_phase,
            'probability': result.probability,
            'ewma_std': result.ewma_std,
            'beta': result.beta,
            'cycle_duration_bars': result.cycle_duration_bars,
            'cycle_duration_hours': result.cycle_duration_hours,
            # 🆕 迭代038新增字段
            'adx': result.adx,
            'cycle_phases': result.cycle_phases,
            # 🆕 Bug-031新增字段：最新K线时间戳
            'kline_timestamp': klines[-1].timestamp if klines else None,
        }

    def _run_strategy16(
        self,
        symbol: str,
        interval: str,
        market_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        运行策略16获取回测结果（限制最近3个月）

        迭代038新增：集成Strategy16Runner，获取holdings和pending_order。

        Args:
            symbol: 交易对
            interval: K线周期
            market_type: 市场类型

        Returns:
            {
                'holdings': List[Dict],      # 未平仓订单
                'pending_order': Dict,       # 当前挂单
                'statistics': Dict           # 统计数据
            }
            计算失败返回None
        """
        try:
            from ddps_z.services.strategy16_runner import Strategy16Runner

            # 计算最近3个月的起始时间
            end_time = datetime.now()
            start_time = end_time - timedelta(days=90)
            start_ts = int(start_time.timestamp() * 1000)
            end_ts = int(end_time.timestamp() * 1000)

            # 🆕 迭代038修复：市场类型映射（数据库存储格式 vs API格式）
            # 数据库中存储的是 'futures'/'spot'，但配置中使用的是 'crypto_futures'/'crypto_spot'
            db_market_type_mapping = {
                'crypto_futures': 'futures',
                'crypto_spot': 'spot',
            }
            db_market_type = db_market_type_mapping.get(market_type, market_type)

            # 运行策略16
            runner = Strategy16Runner()
            result = runner.run(
                symbol=symbol,
                interval=interval,
                market_type=db_market_type,
                start_time=start_ts,
                end_time=end_ts
            )

            if result:
                logger.debug(
                    f"策略16运行完成: {symbol}, "
                    f"持仓={len(result.get('holdings', []))}, "
                    f"挂单={'有' if result.get('pending_order') else '无'}"
                )

            return result

        except Exception as e:
            logger.error(f"运行策略16失败 {symbol}: {e}")
            return None

    def _calculate_cycle_distribution(
        self,
        cycle_phases: List[str],
        window: int = 42
    ) -> Dict[str, float]:
        """
        计算周期占比

        迭代038新增：统计最近42根K线的周期状态分布。

        Args:
            cycle_phases: 周期状态列表（时间升序，最新在后）
            window: 统计窗口大小，默认42

        Returns:
            各周期状态的占比（百分比，整数）
            {
                'bull_strong': 30,
                'bull_warning': 10,
                'consolidation': 40,
                'bear_warning': 10,
                'bear_strong': 10
            }
        """
        # 取最近window根K线
        recent_phases = cycle_phases[-window:] if len(cycle_phases) >= window else cycle_phases

        if not recent_phases:
            return {}

        # 统计各周期数量
        counter = Counter(recent_phases)
        total = len(recent_phases)

        # 计算占比（整数百分比）
        distribution = {}
        for phase in ['bull_strong', 'bull_warning', 'consolidation', 'bear_warning', 'bear_strong']:
            count = counter.get(phase, 0)
            distribution[phase] = round(count / total * 100)

        return distribution

    def get_buy_signals(self) -> List[BuySignal]:
        """
        获取满足买入条件的信号

        Bug-031修复：买入信号来自策略16的holdings中最近成交的订单。
        只有当前K线触发了上根K线的挂单（真实成交），才算买入信号。

        Returns:
            List[BuySignal]: 买入信号列表
        """
        signals = []

        for symbol, strategy16_result in self._strategy16_cache.items():
            if not strategy16_result:
                continue

            # 获取当前指标
            indicators = self._indicators_cache.get(symbol)
            if not indicators:
                continue

            cycle_phase = indicators['cycle_phase']
            current_price = indicators['current_price']
            p5 = indicators['p5']

            # 从holdings中查找最近成交的订单
            holdings = strategy16_result.get('holdings', [])
            if not holdings:
                continue

            # 检查是否有最近一个K线周期内成交的订单
            # 使用24小时作为判断窗口
            now_ts = int(datetime.now().timestamp() * 1000)
            time_window = 24 * 60 * 60 * 1000  # 24小时的毫秒数

            for holding in holdings:
                buy_timestamp = holding.get('buy_timestamp', 0)
                if buy_timestamp > 0 and (now_ts - buy_timestamp) < time_window:
                    # 找到最近成交的订单，生成买入信号
                    signal = BuySignal(
                        symbol=symbol,
                        price=Decimal(str(holding.get('buy_price', current_price))),
                        cycle_phase=cycle_phase,
                        p5=p5,
                        trigger_condition=f"策略16挂单成交",
                        signal_timestamp=buy_timestamp
                    )
                    signals.append(signal)
                    logger.info(
                        f"检测到买入信号(策略16成交): {symbol} @ {holding.get('buy_price')}, "
                        f"成交时间={datetime.fromtimestamp(buy_timestamp/1000)}"
                    )

        # 按时间倒序排序（越新越靠前）
        signals.sort(key=lambda x: x.signal_timestamp or 0, reverse=True)
        return signals

    def _convert_pending_order_to_buy_signal(
        self,
        symbol: str,
        pending_order: Optional[Dict],
        cycle_phase: str,
        current_price: Decimal,
        p5: Decimal,
        kline_timestamp: Optional[int] = None  # 🆕 Bug-031新增参数
    ) -> Optional[BuySignal]:
        """
        将策略16的pending_order转换为BuySignal格式

        迭代038新增：买入信号的数据来源从价格判断改为策略16挂单。
        Bug-031修复：添加signal_timestamp字段。

        Args:
            symbol: 交易对
            pending_order: 策略16的挂单信息
            cycle_phase: 周期阶段
            current_price: 当前价格
            p5: P5价格
            kline_timestamp: K线时间戳(毫秒)

        Returns:
            BuySignal: 如果有挂单返回买入信号，否则None
        """
        if not pending_order:
            return None

        order_price = pending_order.get('price', 0)
        if order_price <= 0:
            return None

        return BuySignal(
            symbol=symbol,
            price=current_price,
            cycle_phase=cycle_phase,
            p5=p5,
            trigger_condition=f"策略16挂单 @ {order_price:.2f}",
            # 🆕 Bug-031: 添加信号产生时间
            signal_timestamp=kline_timestamp
        )

    def get_exit_signals(self) -> List[ExitSignal]:
        """
        检查持仓订单的卖出条件

        迭代038升级：基于策略16回测结果检测卖出信号。
        从策略16返回的orders中查找最近24小时内平仓的订单。

        Returns:
            List[ExitSignal]: 卖出信号列表（按时间倒序，越新越靠前）
        """
        signals = []

        now_ts = int(datetime.now().timestamp() * 1000)
        time_window = 24 * 60 * 60 * 1000  # 24小时的毫秒数

        for symbol, strategy16_result in self._strategy16_cache.items():
            if not strategy16_result:
                continue

            # 从策略16结果获取已完成订单
            orders = strategy16_result.get('orders', [])
            if not orders:
                continue

            # 获取当前指标
            indicators = self._indicators_cache.get(symbol)
            if not indicators:
                continue

            cycle_phase = indicators['cycle_phase']

            # 查找所有在时间窗口内平仓的订单
            for order in orders:
                sell_timestamp = order.get('sell_timestamp', 0)
                if sell_timestamp > 0 and (now_ts - sell_timestamp) < time_window:
                    exit_signal = self._convert_order_to_exit_signal(
                        order=order,
                        symbol=symbol,
                        cycle_phase=cycle_phase
                    )
                    if exit_signal:
                        signals.append(exit_signal)
                        logger.info(
                            f"检测到卖出信号(策略16): {symbol}, "
                            f"类型={exit_signal.exit_type}, "
                            f"盈亏={exit_signal.profit_rate:.2f}%"
                        )

        # 按时间倒序排序（越新越靠前）
        signals.sort(key=lambda x: x.sell_timestamp or 0, reverse=True)
        return signals

    def _convert_order_to_exit_signal(
        self,
        order: Dict,
        symbol: str,
        cycle_phase: str
    ) -> Optional[ExitSignal]:
        """
        将策略16的已完成订单转换为ExitSignal格式

        迭代038新增：从策略16回测结果转换卖出信号。
        Bug-031修复：添加holding_hours字段。

        Args:
            order: 策略16的已完成订单
            symbol: 交易对
            cycle_phase: 当前周期阶段

        Returns:
            ExitSignal: 卖出信号
        """
        exit_reason = order.get('exit_reason', '')

        # 退出类型映射（策略16 -> 监控服务）
        exit_type_mapping = {
            'ema_cross_bull': 'ema_state_bull',
            'ema_break_bear': 'ema_state_bear',
            'ema_break_consolidation': 'ema_state_consolidation',
            'limit_take_profit': 'limit_take_profit',
            'stop_loss': 'stop_loss',
        }

        exit_type = exit_type_mapping.get(exit_reason, exit_reason)

        # 🆕 Bug-031: 计算持仓时长（小时）
        buy_timestamp = order.get('buy_timestamp', 0)
        sell_timestamp = order.get('sell_timestamp', 0)
        holding_hours = None
        if buy_timestamp > 0 and sell_timestamp > 0:
            holding_hours = (sell_timestamp - buy_timestamp) / (1000 * 60 * 60)

        return ExitSignal(
            order_id=order.get('id', ''),
            symbol=symbol,
            open_price=Decimal(str(order.get('buy_price', 0))),
            exit_price=Decimal(str(order.get('sell_price', 0))),
            exit_type=exit_type,
            profit_rate=Decimal(str(order.get('profit_rate', 0))),
            cycle_phase=cycle_phase,
            holding_hours=holding_hours,  # 🆕 Bug-031
            sell_timestamp=sell_timestamp,  # 🆕 Bug-031: 卖出时间戳
            buy_timestamp=buy_timestamp  # 🆕 Bug-031: 买入时间戳
        )

    def _check_exit_condition(
        self,
        order: VirtualOrder,
        current_price: Decimal,
        ema25: Decimal,
        p95: Decimal,
        cycle_phase: str
    ) -> Optional[ExitSignal]:
        """
        检查单个订单的退出条件

        Args:
            order: 虚拟订单
            current_price: 当前价格
            ema25: EMA25值
            p95: P95值
            cycle_phase: 当前周期阶段

        Returns:
            ExitSignal: 如果满足退出条件返回信号，否则None
        """
        exit_type = None
        exit_price = current_price

        if cycle_phase in ('bear_warning', 'bear_strong'):
            # 下跌期：EMA25回归止盈
            if current_price >= ema25:
                exit_type = 'ema_reversion'

        elif cycle_phase == 'consolidation':
            # 震荡期：(P95+EMA25)/2 止盈
            threshold = (p95 + ema25) / Decimal('2')
            if current_price >= threshold:
                exit_type = 'consolidation_mid'

        elif cycle_phase in ('bull_warning', 'bull_strong'):
            # 上涨期：P95止盈
            if current_price >= p95:
                exit_type = 'p95_take_profit'

        if exit_type:
            # 计算盈亏率
            profit_rate = (
                (current_price - order.open_price) / order.open_price * Decimal('100')
            ) if order.open_price > 0 else Decimal('0')

            return ExitSignal(
                order_id=order.id,
                symbol=order.symbol,
                open_price=order.open_price,
                exit_price=exit_price,
                exit_type=exit_type,
                profit_rate=profit_rate,
                cycle_phase=cycle_phase
            )

        return None

    def get_cycle_warnings(self) -> CycleWarning:
        """
        获取周期预警信息

        根据各交易对的cycle_phase分类。

        Returns:
            CycleWarning: 周期预警汇总
        """
        warning = CycleWarning()

        for symbol, indicators in self._indicators_cache.items():
            cycle_phase = indicators['cycle_phase']

            if cycle_phase == 'bull_warning':
                warning.bull_warning.append(symbol)
            elif cycle_phase == 'bull_strong':
                warning.bull_strong.append(symbol)
            elif cycle_phase == 'bear_warning':
                warning.bear_warning.append(symbol)
            elif cycle_phase == 'bear_strong':
                warning.bear_strong.append(symbol)
            elif cycle_phase == 'consolidation':
                warning.consolidation.append(symbol)

        return warning

    def get_price_status(self) -> List[PriceStatus]:
        """
        获取所有交易对的价格状态

        迭代038升级：填充所有新增字段，包括策略16数据。

        Returns:
            List[PriceStatus]: 价格状态列表
        """
        status_list = []

        for symbol, indicators in self._indicators_cache.items():
            # 🆕 迭代038: 获取策略16结果
            strategy16_result = self._strategy16_cache.get(symbol)
            order_price = None
            holdings_list = None

            if strategy16_result:
                # 获取挂单价格
                pending_order = strategy16_result.get('pending_order')
                if pending_order:
                    order_price = Decimal(str(pending_order.get('price', 0)))

                # 转换持仓订单为HoldingInfo列表
                holdings = strategy16_result.get('holdings', [])
                if holdings:
                    holdings_list = self._convert_holdings_to_holding_info(holdings)

            # 🆕 迭代038: 计算周期占比（使用cycle_phases）
            cycle_phases = indicators.get('cycle_phases', [])
            cycle_distribution = None
            if cycle_phases:
                cycle_distribution = self._calculate_cycle_distribution(cycle_phases)

            status = PriceStatus(
                symbol=symbol,
                current_price=indicators['current_price'],
                cycle_phase=indicators['cycle_phase'],
                p5=indicators['p5'],
                p95=indicators['p95'],
                ema25=indicators['ema25'],
                inertia_mid=indicators['inertia_mid'],
                probability=indicators['probability'],
                # 🆕 迭代038新增字段
                order_price=order_price,
                adx=indicators.get('adx'),  # 从DDPSCalculator获取
                beta=indicators.get('beta'),
                cycle_duration_hours=indicators.get('cycle_duration_hours'),
                inertia_lower=indicators.get('inertia_lower'),
                inertia_upper=indicators.get('inertia_upper'),
                cycle_distribution=cycle_distribution,
                holdings=holdings_list,
                # 🆕 Bug-031新增字段
                kline_timestamp=indicators.get('kline_timestamp')
            )
            status_list.append(status)

        return status_list

    def _convert_holdings_to_holding_info(
        self,
        holdings: List[Dict]
    ) -> List[HoldingInfo]:
        """
        将策略16的holdings转换为HoldingInfo列表

        迭代038新增：转换持仓数据格式。

        Args:
            holdings: 策略16返回的持仓列表

        Returns:
            List[HoldingInfo]: 转换后的持仓信息列表
        """
        result = []
        now_ts = int(datetime.now().timestamp() * 1000)

        for holding in holdings:
            buy_timestamp = holding.get('buy_timestamp', 0)
            # 计算持仓时长（小时）
            holding_hours = (now_ts - buy_timestamp) / (1000 * 60 * 60) if buy_timestamp > 0 else 0

            info = HoldingInfo(
                order_id=holding.get('id', ''),
                buy_price=Decimal(str(holding.get('buy_price', 0))),
                buy_timestamp=buy_timestamp,
                holding_hours=round(holding_hours, 1)
            )
            result.append(info)

        # 按买入时间倒序（最新在前）- 策略16已排序，但确保一致性
        result.sort(key=lambda x: x.buy_timestamp, reverse=True)

        return result

    # =========================================================================
    # 虚拟订单管理
    # =========================================================================

    def add_order(self, order: VirtualOrder) -> None:
        """
        添加虚拟订单

        Args:
            order: 虚拟订单
        """
        self._orders.append(order)
        logger.info(f"添加虚拟订单: {order.id} {order.symbol} @ {order.open_price}")

    def get_open_orders(self) -> List[VirtualOrder]:
        """
        获取未平仓订单

        Returns:
            List[VirtualOrder]: 未平仓订单列表
        """
        return [o for o in self._orders if o.is_open]

    def get_orders_by_symbol(self, symbol: str) -> List[VirtualOrder]:
        """
        获取指定交易对的订单

        Args:
            symbol: 交易对

        Returns:
            List[VirtualOrder]: 订单列表
        """
        return [o for o in self._orders if o.symbol == symbol]

    def close_order(
        self,
        order_id: str,
        close_price: Decimal,
        close_timestamp: int,
        exit_type: str
    ) -> bool:
        """
        平仓订单

        Args:
            order_id: 订单ID
            close_price: 平仓价格
            close_timestamp: 平仓时间戳
            exit_type: 退出类型

        Returns:
            bool: 是否成功平仓
        """
        for order in self._orders:
            if order.id == order_id and order.is_open:
                order.close(close_price, close_timestamp, exit_type)
                logger.info(
                    f"平仓订单: {order_id} @ {close_price}, "
                    f"盈亏={order.profit_loss}, 类型={exit_type}"
                )
                return True

        logger.warning(f"未找到订单或订单已平仓: {order_id}")
        return False

    def clear_orders(self) -> None:
        """清空所有订单"""
        self._orders.clear()
        logger.info("已清空所有虚拟订单")

    # =========================================================================
    # 消息格式化
    # =========================================================================

    def format_push_message(
        self,
        result: DDPSMonitorResult,
        market_type: str = 'crypto_futures',
        interval: str = '4h'
    ) -> tuple:
        """
        格式化推送消息

        迭代038升级：新增市场/周期标识，扩展价格状态显示字段。

        Args:
            result: DDPSMonitorResult监控结果
            market_type: 市场类型
            interval: K线周期

        Returns:
            tuple: (title, content) 格式化后的推送标题和内容

        标题格式: [市场/周期] MM-DD HH:MM: 买入(N) 卖出(N) 上涨预警(N) 下跌预警(N)
        """
        # 时间格式: MM-DD HH:MM
        time_short = datetime.now().strftime('%m-%d %H:%M')
        time_full = datetime.now().strftime('%Y-%m-%d %H:%M')

        # 统计数量
        buy_count = len(result.buy_signals)
        exit_count = len(result.exit_signals)
        warning = result.cycle_warnings
        bull_warning_count = len(warning.bull_warning)
        bear_warning_count = len(warning.bear_warning)

        # 🆕 迭代038: 构建标题，增加市场/周期标识
        title = (
            f"[{market_type}/{interval}] {time_short}: "
            f"买入({buy_count}) 卖出({exit_count}) "
            f"上涨预警({bull_warning_count}) 下跌预警({bear_warning_count})"
        )

        # 构建内容
        lines = []
        lines.append(f"时间: {time_full}")
        lines.append("")

        # 买入信号
        lines.append(f"买入信号 ({buy_count}个):")
        if result.buy_signals:
            for signal in result.buy_signals:
                cycle_label = self._get_cycle_label(signal.cycle_phase)
                # 🆕 Bug-031: 显示触发时间和触发条件
                time_str = ""
                if signal.signal_timestamp:
                    signal_time = datetime.fromtimestamp(signal.signal_timestamp / 1000)
                    time_str = signal_time.strftime('%m-%d %H:%M')

                # 第一行：交易对、价格、周期、时间
                if time_str:
                    lines.append(f"  - {signal.symbol} @ {signal.price:.2f} ({cycle_label})")
                    lines.append(f"    触发时间: {time_str}")
                else:
                    lines.append(f"  - {signal.symbol} @ {signal.price:.2f} ({cycle_label})")

                # 第二行：触发条件（推送原因）
                if signal.trigger_condition:
                    lines.append(f"    触发条件: {signal.trigger_condition}")
        else:
            lines.append("  无")
        lines.append("")

        # 卖出信号
        lines.append(f"卖出信号 ({exit_count}个):")
        if result.exit_signals:
            for signal in result.exit_signals:
                # 🆕 Bug-031: 显示触发时间、买入时间和退出原因
                sell_time_str = ""
                buy_time_str = ""
                if signal.sell_timestamp:
                    sell_time = datetime.fromtimestamp(signal.sell_timestamp / 1000)
                    sell_time_str = sell_time.strftime('%m-%d %H:%M')
                if signal.buy_timestamp:
                    buy_time = datetime.fromtimestamp(signal.buy_timestamp / 1000)
                    buy_time_str = buy_time.strftime('%m-%d %H:%M')

                # 第一行：交易对、卖出价格、盈亏
                profit_sign = "+" if signal.profit_rate >= 0 else ""
                lines.append(
                    f"  - {signal.symbol} @ {signal.exit_price:.2f} "
                    f"(开仓{signal.open_price:.2f}, {profit_sign}{signal.profit_rate:.2f}%)"
                )

                # 第二行：触发时间（卖出时间）
                if sell_time_str:
                    lines.append(f"    触发时间: {sell_time_str}")

                # 第三行：买入时间
                if buy_time_str:
                    lines.append(f"    买入时间: {buy_time_str}")

                # 第四行：退出原因和持仓时长
                exit_info_parts = []
                if signal.exit_type:
                    exit_info_parts.append(f"退出原因: {signal.exit_type}")
                if signal.holding_hours is not None:
                    exit_info_parts.append(f"持仓{signal.holding_hours:.0f}小时")
                if exit_info_parts:
                    lines.append(f"    {', '.join(exit_info_parts)}")
        else:
            lines.append("  无")
        lines.append("")

        # 周期预警（只显示 bull_warning 和 bear_warning）
        if warning.bull_warning:
            lines.append(f"✅✅✅ 上涨预警（观察做多）: {', '.join(warning.bull_warning)}")
        else:
            lines.append("上涨预警: 无")

        if warning.bear_warning:
            lines.append(f"❌❌❌ 下跌预警（谨慎开单）: {', '.join(warning.bear_warning)}")
        else:
            lines.append("下跌预警: 无")
        lines.append("")

        # 🆕 迭代038: 价格状态（扩展格式）
        lines.append("价格状态:")
        for status in result.price_status:
            self._format_price_status_lines(status, lines)

        content = "\n".join(lines)
        return (title, content)

    def _format_price_status_lines(
        self,
        status: PriceStatus,
        lines: List[str]
    ) -> None:
        """
        格式化单个价格状态的显示行

        迭代038新增：扩展显示策略16相关信息。
        Bug-031修复：添加K线时间、贝塔百分比、周期占比排序。
        Bug-033优化：首行集中显示概率和挂单价格。

        Args:
            status: 价格状态
            lines: 输出行列表（直接追加）
        """
        cycle_label = self._get_cycle_label(status.cycle_phase)

        # 计算位置标记（基于probability）
        position_emoji = self._get_position_emoji(status.probability)

        # 计算周期趋势标记（基于当前周期和42周期占比第一）
        trend_emoji = self._get_trend_emoji(status.cycle_phase, status.cycle_distribution)

        # 🆕 Bug-033: 首行集中显示关键信息（代币、时间、价格、周期、概率、挂单）
        first_line_parts = []

        # 基础信息：位置emoji + 趋势emoji + 代币 (时间): 价格 (周期)
        emoji_prefix = f"{position_emoji}{trend_emoji}" if position_emoji or trend_emoji else "💲"
        if status.kline_timestamp:
            kline_time = datetime.fromtimestamp(status.kline_timestamp / 1000)
            time_str = kline_time.strftime('%m-%d %H:%M')
            first_line_parts.append(f"{emoji_prefix}{status.symbol} ({time_str}): {status.current_price:.2f} ({cycle_label})")
        else:
            first_line_parts.append(f"{emoji_prefix}{status.symbol}: {status.current_price:.2f} ({cycle_label})")

        # 概率
        first_line_parts.append(f"P{status.probability}")

        # 挂单价格（含与现价的距离百分比）
        if status.order_price and status.order_price > 0:
            price_diff_pct = (status.order_price - status.current_price) / status.current_price * 100
            first_line_parts.append(f"挂单({status.order_price:.2f})({price_diff_pct:+.1f}%)")

        lines.append(f"  {' - '.join(first_line_parts)}")

        # 第二行：P5/P95
        lines.append(f"    P5={status.p5:.2f} P95={status.p95:.2f}")

        # 第三行：惯性预测范围（含与现价距离百分比）
        if status.inertia_lower and status.inertia_upper:
            lower_diff_pct = (status.inertia_lower - status.current_price) / status.current_price * 100
            upper_diff_pct = (status.inertia_upper - status.current_price) / status.current_price * 100
            lines.append(f"    惯性范围: {status.inertia_lower:.2f}~{status.inertia_upper:.2f}（{lower_diff_pct:+.0f}% {upper_diff_pct:+.0f}%）")
        else:
            inertia_lower = min(status.ema25, status.inertia_mid)
            inertia_upper = max(status.ema25, status.inertia_mid)
            lower_diff_pct = (inertia_lower - status.current_price) / status.current_price * 100
            upper_diff_pct = (inertia_upper - status.current_price) / status.current_price * 100
            lines.append(f"    惯性范围: {inertia_lower:.2f}~{inertia_upper:.2f}（{lower_diff_pct:+.0f}% {upper_diff_pct:+.0f}%）")

        # 🆕 迭代038新增行: 所处周期详情（Bug-031: 贝塔乘以100显示为百分比）
        cycle_details = []
        cycle_details.append(cycle_label)
        if status.adx is not None:
            cycle_details.append(f"ADX({status.adx:.0f})")
        if status.beta is not None:
            # 🆕 Bug-031: 贝塔值乘以100，与页面保持一致
            beta_pct = status.beta * 100
            cycle_details.append(f"贝塔({beta_pct:.1f}%)")
        if status.cycle_duration_hours is not None:
            cycle_details.append(f"连续{status.cycle_duration_hours:.0f}小时")
        if len(cycle_details) > 1:
            lines.append(f"    所处周期: {' - '.join(cycle_details)}")

        # 🆕 迭代038新增行: 42周期占比（Bug-031: 显示全部5种类型，按占比排序）
        if status.cycle_distribution:
            dist_labels = {
                'bull_strong': '强势上涨',
                'bull_warning': '上涨预警',
                'consolidation': '震荡',
                'bear_warning': '下跌预警',
                'bear_strong': '强势下跌',
            }
            # 🆕 Bug-031: 收集所有周期类型并按占比降序排序
            dist_items = []
            for key, label in dist_labels.items():
                pct = status.cycle_distribution.get(key, 0)
                if pct > 0:  # 只显示占比>0的类型
                    dist_items.append((label, pct))
            # 按占比降序排序
            dist_items.sort(key=lambda x: x[1], reverse=True)
            if dist_items:
                dist_parts = [f"{label}({pct:.0f}%)" for label, pct in dist_items]
                lines.append(f"    最近42周期占比: {', '.join(dist_parts)}")

        # 🆕 迭代038新增行: 持仓订单列表
        if status.holdings:
            lines.append(f"    持仓订单 ({len(status.holdings)}个):")
            for holding in status.holdings:
                # 格式化买入时间
                buy_time = datetime.fromtimestamp(holding.buy_timestamp / 1000)
                buy_time_str = buy_time.strftime('%m-%d %H:%M')
                # 计算涨幅百分比
                pnl_rate = 0.0
                if holding.buy_price > 0:
                    pnl_rate = float(
                        (status.current_price - holding.buy_price)
                        / holding.buy_price * 100
                    )
                pnl_str = f"{pnl_rate:+.1f}%"  # +号表示正数也显示符号
                lines.append(
                    f"      {buy_time_str} @ {holding.buy_price:.2f}({pnl_str}) → "
                    f"持仓{holding.holding_hours:.0f}小时"
                )

    def _get_cycle_label(self, cycle_phase: str) -> str:
        """获取周期阶段的中文标签"""
        labels = {
            'bull_warning': '上涨预警',
            'bull_strong': '上涨强势',
            'bear_warning': '下跌预警',
            'bear_strong': '下跌强势',
            'consolidation': '震荡期',
        }
        return labels.get(cycle_phase, cycle_phase)

    def _get_position_emoji(self, probability: int) -> str:
        """
        获取位置标记emoji

        基于probability值判断当前价格所处位置：
        - P10以下（低位）：🔴🔴🔴
        - P80以上（高位）：🟢🟢🟢
        - 其他：空字符串

        Args:
            probability: 概率值（0-100）

        Returns:
            str: 位置标记emoji
        """
        if probability < 10:
            return "🔴🔴🔴"
        elif probability >= 80:
            return "🟢🟢🟢"
        return ""

    def _get_trend_emoji(
        self,
        cycle_phase: str,
        cycle_distribution: Optional[Dict[str, float]]
    ) -> str:
        """
        获取周期趋势标记emoji

        基于当前周期和42周期占比第一的综合判断：
        - 当前周期和42周期占比第一均为强势上涨：🟢
        - 当前周期和42周期占比第一均为强势下跌：🔴
        - 其他情况：🟡

        Args:
            cycle_phase: 当前周期阶段
            cycle_distribution: 42周期占比分布

        Returns:
            str: 趋势标记emoji
        """
        if not cycle_distribution:
            return "🟡"

        # 找出42周期占比第一的类型
        top_phase = max(cycle_distribution.keys(), key=lambda k: cycle_distribution.get(k, 0))

        # 判断趋势
        if cycle_phase == 'bull_strong' and top_phase == 'bull_strong':
            return "🟢"
        elif cycle_phase == 'bear_strong' and top_phase == 'bear_strong':
            return "🔴"
        else:
            return "🟡"

    def _get_exit_label(self, exit_type: str) -> str:
        """
        获取退出类型的中文标签

        迭代038升级：增加策略16退出类型映射。
        """
        labels = {
            # 策略7原有类型
            'ema_reversion': 'EMA25回归止盈',
            'consolidation_mid': '震荡期止盈',
            'p95_take_profit': 'P95止盈',
            # 🆕 策略16新类型
            'ema_state_bull': 'EMA状态止盈(强势上涨)',
            'ema_state_bear': 'EMA状态止盈(强势下跌)',
            'ema_state_consolidation': 'EMA状态止盈(震荡下跌)',
            'limit_take_profit': '2%限价止盈(震荡上涨)',
            'stop_loss': '止损',
        }
        return labels.get(exit_type, exit_type)
