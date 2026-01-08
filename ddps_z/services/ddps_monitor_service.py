"""
DDPS价格监控核心服务
DDPS Monitor Service

核心监控服务类，提供DDPS指标计算和信号检测能力，可被多个命令复用。

功能特性:
    - calculate_all: 计算所有交易对的完整DDPS指标
    - get_buy_signals: 检测满足买入条件的交易对
    - get_exit_signals: 检查订单的卖出条件
    - get_cycle_warnings: 获取周期预警信息
    - get_price_status: 获取所有交易对的价格状态
    - 虚拟订单管理（内存管理）

使用示例:
    from ddps_z.services import DDPSMonitorService

    service = DDPSMonitorService(
        symbols=['ETHUSDT', 'BTCUSDT'],
        strategy_id=7
    )
    result = service.calculate_all()

    print(f"买入信号: {len(result.buy_signals)}")
    print(f"周期预警: {result.cycle_warnings}")

Related:
    - PRD: docs/iterations/023-ddps-price-monitor/prd.md
    - Architecture: docs/iterations/023-ddps-price-monitor/architecture.md
    - Task: TASK-023-005, TASK-023-006, TASK-023-007, TASK-023-008
"""

import logging
from decimal import Decimal
from typing import List, Dict, Optional
from scipy.stats import norm
import numpy as np
import pandas as pd

from django.conf import settings

from ddps_z.models import (
    VirtualOrder,
    PriceStatus,
    BuySignal,
    ExitSignal,
    CycleWarning,
    DDPSMonitorResult,
)
from ddps_z.calculators import (
    EMACalculator,
    EWMACalculator,
    BetaCycleCalculator,
)
from ddps_z.calculators.inertia_calculator import InertiaCalculator
from ddps_z.calculators.adx_calculator import ADXCalculator
from backtest.models import KLine

logger = logging.getLogger(__name__)


class DDPSMonitorService:
    """
    DDPS价格监控核心服务

    提供DDPS指标计算和策略信号检测能力。
    复用现有计算器确保计算结果与详情页一致。

    Attributes:
        symbols: 监控的交易对列表
        strategy_id: 策略ID（默认7）
        interval: K线周期
        market_type: 市场类型
        _orders: 虚拟订单列表（内存管理）
        _indicators_cache: 指标缓存
    """

    def __init__(
        self,
        symbols: List[str],
        strategy_id: int = 7,
        interval: str = '4h',
        market_type: str = 'futures'
    ):
        """
        初始化监控服务

        Args:
            symbols: 交易对列表，如['ETHUSDT', 'BTCUSDT']
            strategy_id: 策略ID，默认7（动态周期自适应）
            interval: K线周期，默认'4h'
            market_type: 市场类型，默认'futures'
        """
        self.symbols = [s.upper() for s in symbols]
        self.strategy_id = strategy_id
        self.interval = interval
        self.market_type = market_type

        # 虚拟订单管理（内存）
        self._orders: List[VirtualOrder] = []

        # 指标缓存
        self._indicators_cache: Dict[str, dict] = {}

        # 初始化计算器
        self._ema_calc = EMACalculator(period=25)
        self._ewma_calc = EWMACalculator(window_n=50)
        self._cycle_calc = BetaCycleCalculator()
        self._inertia_calc = InertiaCalculator(base_period=5)
        self._adx_calc = ADXCalculator(period=14)

        logger.info(
            f"DDPSMonitorService初始化: symbols={symbols}, "
            f"strategy_id={strategy_id}, interval={interval}"
        )

    def calculate_all(self) -> DDPSMonitorResult:
        """
        计算所有交易对的完整DDPS指标

        Returns:
            DDPSMonitorResult: 包含买入信号、卖出信号、周期预警、价格状态的完整结果

        Side Effects:
            更新_indicators_cache缓存
        """
        logger.info(f"开始计算{len(self.symbols)}个交易对的DDPS指标...")

        # 清空缓存
        self._indicators_cache = {}

        # 计算每个交易对的指标
        for symbol in self.symbols:
            try:
                indicators = self._calculate_symbol_indicators(symbol)
                if indicators:
                    self._indicators_cache[symbol] = indicators
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
                'total_symbols': len(self.symbols),
                'calculated_symbols': len(self._indicators_cache),
                'failed_symbols': len(self.symbols) - len(self._indicators_cache),
            }
        )

        logger.info(
            f"计算完成: 成功={len(self._indicators_cache)}, "
            f"买入信号={len(result.buy_signals)}, "
            f"卖出信号={len(result.exit_signals)}"
        )

        return result

    def _calculate_symbol_indicators(self, symbol: str) -> Optional[dict]:
        """
        计算单个交易对的所有指标

        Args:
            symbol: 交易对

        Returns:
            dict: 包含所有指标的字典，计算失败返回None
        """
        # 加载K线数据
        klines = self._load_klines(symbol)
        if klines is None or len(klines) < 180:
            logger.warning(f"{symbol}: K线数据不足(需要>=180)")
            return None

        # 提取价格序列
        prices = klines['close'].values
        high = klines['high'].values
        low = klines['low'].values
        timestamps_ms = np.array([
            int(ts.timestamp() * 1000) for ts in klines.index
        ])

        # 计算EMA
        ema_array = self._ema_calc.calculate_ema_series(prices)

        # 计算偏离率和EWMA标准差
        deviation = self._ema_calc.calculate_deviation_series(prices)
        ewma_mean, ewma_std_series = self._ewma_calc.calculate_ewma_stats(deviation)

        # 计算P5和P95
        z_p5 = -1.645
        z_p95 = +1.645
        p5_array = ema_array * (1 + z_p5 * ewma_std_series)
        p95_array = ema_array * (1 + z_p95 * ewma_std_series)

        # 计算ADX
        adx_result = self._adx_calc.calculate(high, low, prices)
        adx_series = adx_result['adx']

        # 计算惯性扇面
        fan_result = self._inertia_calc.calculate_historical_fan_series(
            timestamps=timestamps_ms,
            ema_series=ema_array,
            sigma_series=ewma_std_series,
            adx_series=adx_series
        )
        beta_array = fan_result['beta']
        inertia_mid_array = fan_result['mid']

        # 计算β宏观周期
        beta_list = [
            b if not np.isnan(b) else None
            for b in beta_array
        ]
        cycle_phases, current_cycle_info = self._cycle_calc.calculate(
            beta_list=beta_list,
            timestamps=timestamps_ms.tolist(),
            prices=prices.tolist(),
            interval_hours=4.0
        )

        # 获取最新值
        current_price = Decimal(str(prices[-1]))
        current_ema25 = Decimal(str(ema_array[-1]))
        current_p5 = Decimal(str(p5_array[-1]))
        current_p95 = Decimal(str(p95_array[-1]))
        current_inertia_mid = Decimal(str(inertia_mid_array[-1]))
        current_cycle_phase = cycle_phases[-1] if cycle_phases else 'consolidation'
        current_ewma_std = ewma_std_series[-1] if len(ewma_std_series) > 0 else 0

        # 计算概率位置
        probability = self._calculate_probability(
            current_price, current_ema25, Decimal(str(current_ewma_std))
        )

        return {
            'symbol': symbol,
            'current_price': current_price,
            'ema25': current_ema25,
            'p5': current_p5,
            'p95': current_p95,
            'inertia_mid': current_inertia_mid,
            'cycle_phase': current_cycle_phase,
            'probability': probability,
            'ewma_std': current_ewma_std,
            'klines': klines,
        }

    def _load_klines(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        从数据库加载K线数据

        Args:
            symbol: 交易对

        Returns:
            pd.DataFrame: K线数据，失败返回None
        """
        try:
            # 按时间倒序获取最新的500根K线
            queryset = KLine.objects.filter(
                symbol=symbol,
                interval=self.interval,
                market_type=self.market_type
            ).order_by('-open_time')[:500]

            if not queryset.exists():
                return None

            data = list(queryset.values(
                'open_time', 'open_price', 'high_price',
                'low_price', 'close_price', 'volume'
            ))

            # 反转为时间正序（计算需要正序数据）
            data.reverse()

            df = pd.DataFrame(data)
            df = df.rename(columns={
                'open_price': 'open',
                'high_price': 'high',
                'low_price': 'low',
                'close_price': 'close',
                'volume': 'volume'
            })

            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)

            df = df.set_index('open_time')
            return df

        except Exception as e:
            logger.error(f"加载{symbol} K线失败: {e}")
            return None

    def _calculate_probability(
        self,
        price: Decimal,
        ema: Decimal,
        ewma_std: Decimal
    ) -> int:
        """
        计算当前价格的概率位置（0-100）

        基于Z-Score和正态分布CDF计算。

        Args:
            price: 当前价格
            ema: EMA均线值
            ewma_std: EWMA标准差

        Returns:
            int: 概率位置（0-100）
        """
        if ema == 0 or ewma_std == 0:
            return 50

        # 计算偏离率
        deviation = (float(price) - float(ema)) / float(ema)

        # 计算Z-Score
        z_score = deviation / float(ewma_std)

        # 使用正态分布CDF转换为概率
        probability = norm.cdf(z_score) * 100

        return int(min(100, max(0, probability)))

    def get_buy_signals(self) -> List[BuySignal]:
        """
        获取满足买入条件的信号

        买入条件（策略7）：价格 <= P5

        Returns:
            List[BuySignal]: 买入信号列表
        """
        signals = []

        for symbol, indicators in self._indicators_cache.items():
            current_price = indicators['current_price']
            p5 = indicators['p5']
            cycle_phase = indicators['cycle_phase']

            # 策略7买入条件：价格 <= P5
            if current_price <= p5:
                signal = BuySignal(
                    symbol=symbol,
                    price=current_price,
                    cycle_phase=cycle_phase,
                    p5=p5,
                    trigger_condition=f"价格({current_price:.2f})<=P5({p5:.2f})"
                )
                signals.append(signal)
                logger.info(f"检测到买入信号: {symbol} @ {current_price}")

        return signals

    def get_exit_signals(self) -> List[ExitSignal]:
        """
        检查持仓订单的卖出条件

        策略7退出条件：
        - 下跌期（bear_warning, bear_strong）：EMA25回归止盈
        - 震荡期（consolidation）：(P95+EMA25)/2 止盈
        - 上涨期（bull_warning, bull_strong）：P95止盈

        Returns:
            List[ExitSignal]: 卖出信号列表
        """
        signals = []

        for order in self._orders:
            if not order.is_open:
                continue

            symbol = order.symbol
            if symbol not in self._indicators_cache:
                continue

            indicators = self._indicators_cache[symbol]
            current_price = indicators['current_price']
            ema25 = indicators['ema25']
            p95 = indicators['p95']
            cycle_phase = indicators['cycle_phase']

            # 检查退出条件
            exit_signal = self._check_exit_condition(
                order=order,
                current_price=current_price,
                ema25=ema25,
                p95=p95,
                cycle_phase=cycle_phase
            )

            if exit_signal:
                signals.append(exit_signal)

        return signals

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

        Returns:
            List[PriceStatus]: 价格状态列表
        """
        status_list = []

        for symbol, indicators in self._indicators_cache.items():
            status = PriceStatus(
                symbol=symbol,
                current_price=indicators['current_price'],
                cycle_phase=indicators['cycle_phase'],
                p5=indicators['p5'],
                p95=indicators['p95'],
                ema25=indicators['ema25'],
                inertia_mid=indicators['inertia_mid'],
                probability=indicators['probability']
            )
            status_list.append(status)

        return status_list

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

    def format_push_message(self, result: DDPSMonitorResult) -> tuple:
        """
        格式化推送消息

        Args:
            result: DDPSMonitorResult监控结果

        Returns:
            tuple: (title, content) 格式化后的推送标题和内容

        标题格式: MM-DD HH:MM: 买入(N) 卖出(N) 上涨预警(N) 下跌预警(N)
        """
        from datetime import datetime

        # 时间格式: MM-DD HH:MM
        time_short = datetime.now().strftime('%m-%d %H:%M')
        time_full = datetime.now().strftime('%Y-%m-%d %H:%M')

        # 统计数量
        buy_count = len(result.buy_signals)
        exit_count = len(result.exit_signals)
        warning = result.cycle_warnings
        bull_warning_count = len(warning.bull_warning)
        bear_warning_count = len(warning.bear_warning)

        # 构建标题: MM-DD HH:MM: 买入(N) 卖出(N) 上涨预警(N) 下跌预警(N)
        title = (
            f"{time_short}: "
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
                lines.append(
                    f"  - {signal.symbol} @ {signal.price:.2f} ({cycle_label})"
                )
        else:
            lines.append("  无")
        lines.append("")

        # 卖出信号
        lines.append(f"卖出信号 ({exit_count}个):")
        if result.exit_signals:
            for signal in result.exit_signals:
                exit_label = self._get_exit_label(signal.exit_type)
                lines.append(
                    f"  - 订单#{signal.order_id} {signal.symbol}: "
                    f"{exit_label} @ {signal.exit_price:.2f} "
                    f"(开仓{signal.open_price:.2f}, {signal.profit_rate:+.2f}%)"
                )
        else:
            lines.append("  无")
        lines.append("")

        # 周期预警（只显示 bull_warning 和 bear_warning）
        if warning.bull_warning:
            lines.append(f"上涨预警: {', '.join(warning.bull_warning)}")
        else:
            lines.append("上涨预警: 无")

        if warning.bear_warning:
            lines.append(f"下跌预警: {', '.join(warning.bear_warning)}")
        else:
            lines.append("下跌预警: 无")
        lines.append("")

        # 价格状态（完整格式）
        lines.append("价格状态:")
        for status in result.price_status:
            cycle_label = self._get_cycle_label(status.cycle_phase)
            # 第一行：交易对 现价 (周期)
            lines.append(f"  {status.symbol}: {status.current_price:.2f} ({cycle_label})")
            # 第二行：P5/P95
            lines.append(f"    P5={status.p5:.2f} P95={status.p95:.2f}")
            # 第三行：惯性预测范围（使用EMA25和惯性中值近似）
            inertia_lower = min(status.ema25, status.inertia_mid)
            inertia_upper = max(status.ema25, status.inertia_mid)
            lines.append(f"    惯性范围: {inertia_lower:.2f}~{inertia_upper:.2f}")
            # 第四行：概率位置
            lines.append(f"    概率: P{status.probability}")

        content = "\n".join(lines)
        return (title, content)

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

    def _get_exit_label(self, exit_type: str) -> str:
        """获取退出类型的中文标签"""
        labels = {
            'ema_reversion': 'EMA25回归止盈',
            'consolidation_mid': '震荡期止盈',
            'p95_take_profit': 'P95止盈',
        }
        return labels.get(exit_type, exit_type)
