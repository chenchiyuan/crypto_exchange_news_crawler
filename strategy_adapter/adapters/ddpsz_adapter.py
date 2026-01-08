"""
DDPS-Z策略适配器

本模块实现DDPSZStrategy，将DDPS-Z应用层策略适配为IStrategy接口，
复用现有的SignalCalculator和EMA25卖出/平空逻辑。

核心功能：
- 买入信号生成：策略1（EMA斜率未来预测做多）、策略2（惯性下跌中值突破做多）、
  策略6（震荡期P5买入）、策略7（动态周期自适应P5买入）
- 做空信号生成：策略3（EMA斜率未来预测做空）、策略4（惯性上涨中值突破做空）
- 卖出信号生成：EMA25回归逻辑（K线[low, high]包含EMA25）
- 平空信号生成：EMA25回归逻辑（K线[low, high]包含EMA25）
- 仓位管理：固定100 USDT仓位（MVP阶段）
- 止盈止损：MVP阶段不启用

复用策略说明：
- SignalCalculator：直接调用现有逻辑，转换信号格式
- EMA25回归：基于DDPS-Z经验规则，K线回归EMA25时平仓

迭代编号: 015 (做空策略扩展), 018 (震荡期P5买入), 021 (动态周期自适应)
创建日期: 2026-01-06
关联任务: TASK-015-009, TASK-015-010, TASK-015-011, TASK-018-008, TASK-021-008
关联需求: FP-015-008, FP-015-009, FP-018-008, FP-021-008 (prd.md)
关联架构: architecture.md#DDPSZStrategy
"""

from decimal import Decimal
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
import logging

from strategy_adapter.interfaces import IStrategy
from strategy_adapter.models import Order
from ddps_z.calculators import SignalCalculator

logger = logging.getLogger(__name__)


class DDPSZStrategy(IStrategy):
    """
    DDPS-Z策略适配器（DDPS-Z Strategy Adapter）

    职责：
    - 实现IStrategy接口，将DDPS-Z策略适配为统一接口
    - 复用SignalCalculator生成多空信号
    - 实现EMA25回归平仓逻辑（做多卖出、做空平仓）
    - 提供DDPS-Z特定的参数配置（固定100 USDT仓位）

    设计原则：
    - 无状态设计：不保存任何订单或持仓信息
    - 复用优先：直接调用现有的SignalCalculator
    - 信号转换：将SignalCalculator返回格式转换为IStrategy要求格式

    策略说明：
    - 策略1: EMA斜率未来预测做多（low < P5 且 future_ema > close）
    - 策略2: 惯性下跌中值突破做多（β < 0 且 mid < P5 且 low < midline）
    - 策略3: EMA斜率未来预测做空（high >= P95 且 future_ema < close）
    - 策略4: 惯性上涨中值突破做空（β > 0 且 mid > P95 且 high > midline）
    - 策略6: 震荡期P5买入（cycle_phase == consolidation 且 low <= P5）
    - 策略7: 动态周期自适应P5买入（任意周期 且 low <= P5，使用动态Exit）

    Example:
        >>> strategy = DDPSZStrategy(enabled_strategies=[1, 2, 3, 4, 6, 7])
        >>> klines = pd.DataFrame({'open': [...], 'close': [...]})
        >>> indicators = {
        ...     'ema25': pd.Series([...]),
        ...     'p5': pd.Series([...]),
        ...     'p95': pd.Series([...]),
        ...     'beta': pd.Series([...]),
        ...     'inertia_mid': pd.Series([...]),
        ...     'cycle_phase': pd.Series([...])
        ... }
        >>> buy_signals = strategy.generate_buy_signals(klines, indicators)
        >>> short_signals = strategy.generate_short_signals(klines, indicators)
    """

    def __init__(
        self,
        position_size: Decimal = Decimal("100"),
        enabled_strategies: Optional[List[int]] = None
    ):
        """
        初始化DDPS-Z策略

        Args:
            position_size (Decimal): 单笔买入金额（USDT），默认100 USDT
            enabled_strategies (List[int]): 启用的策略ID列表，默认[1, 2]
                - 1: EMA斜率未来预测做多
                - 2: 惯性下跌中值突破做多
                - 3: EMA斜率未来预测做空
                - 4: 惯性上涨中值突破做空
                - 6: 震荡期P5买入
                - 7: 动态周期自适应P5买入

        配置：
        - buy_amount_usdt: 单笔买入金额（可配置）
        - enabled_strategies: 启用的策略列表
        - calculator: SignalCalculator实例

        Example:
            >>> strategy = DDPSZStrategy(
            ...     position_size=Decimal("200"),
            ...     enabled_strategies=[1, 2, 3, 4, 6, 7]
            ... )
            >>> print(strategy.enabled_strategies)  # [1, 2, 3, 4, 6, 7]
        """
        self.buy_amount_usdt = position_size
        self.enabled_strategies = enabled_strategies if enabled_strategies else [1, 2]
        self.calculator = SignalCalculator()

        strategies_str = ', '.join(str(s) for s in self.enabled_strategies)
        logger.info(
            f"初始化DDPSZStrategy: 单笔仓位={position_size} USDT, "
            f"启用策略=[{strategies_str}]"
        )

    def get_strategy_name(self) -> str:
        """
        返回策略名称

        Returns:
            str: "DDPS-Z"

        Example:
            >>> strategy = DDPSZStrategy()
            >>> strategy.get_strategy_name()
            'DDPS-Z'
        """
        return "DDPS-Z"

    def get_strategy_version(self) -> str:
        """
        返回策略版本

        Returns:
            str: "1.0"

        Example:
            >>> strategy = DDPSZStrategy()
            >>> strategy.get_strategy_version()
            '1.0'
        """
        return "1.0"

    def generate_buy_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series]
    ) -> List[Dict]:
        """
        生成买入信号（复用SignalCalculator策略1、2逻辑）

        调用现有的SignalCalculator，将其返回格式转换为IStrategy要求的格式。

        Args:
            klines (pd.DataFrame): K线数据，index为pd.DatetimeIndex
                必须包含列：['open_time', 'open', 'high', 'low', 'close', 'volume']
            indicators (Dict[str, pd.Series]): 技术指标字典
                必须包含：'ema25', 'p5', 'beta', 'inertia_mid'

        Returns:
            List[Dict]: 买入信号列表，格式：
                [{
                    'timestamp': int,          # 买入时间戳（毫秒）
                    'price': Decimal,          # 买入价格
                    'reason': str,             # 买入理由（触发的策略名称）
                    'confidence': float,       # 信号强度
                    'strategy_id': str,        # 触发策略ID
                    'direction': str           # 'long'
                }, ...]

        Raises:
            KeyError: 当indicators缺少必要指标时抛出
            ValueError: 当klines为空时抛出
        """
        # Guard Clause: 检查是否启用了做多策略
        if not any(s in self.enabled_strategies for s in [1, 2, 6, 7]):
            logger.debug(f"未启用做多策略(1,2,6,7)，跳过买入信号生成，当前启用: {self.enabled_strategies}")
            return []

        # Guard Clause: 验证klines非空
        if klines.empty:
            raise ValueError(
                "klines不能为空DataFrame。\n"
                "请确保K线数据已正确加载。"
            )

        # Guard Clause: 验证indicators包含必要字段
        required_indicators = ['ema25', 'p5', 'beta', 'inertia_mid']
        for indicator in required_indicators:
            if indicator not in indicators:
                available = list(indicators.keys())
                raise KeyError(
                    f"indicators缺少必要指标: '{indicator}'。\n"
                    f"可用指标: {available}\n"
                    f"请确保已计算所有DDPS-Z所需指标。"
                )

        # 准备输入数据（转换格式）
        kline_dicts = klines.reset_index().to_dict('records')

        # 提取numpy数组格式的指标序列
        ema_series = indicators['ema25'].values
        p5_series = indicators['p5'].values
        beta_series = indicators['beta'].values
        inertia_mid_series = indicators['inertia_mid'].values

        # 过滤做多策略
        long_strategies = [s for s in self.enabled_strategies if s in [1, 2, 6, 7]]

        # 调用SignalCalculator
        logger.debug(f"调用SignalCalculator: {len(kline_dicts)}根K线, 策略{long_strategies}")
        result = self.calculator.calculate(
            klines=kline_dicts,
            ema_series=ema_series,
            p5_series=p5_series,
            beta_series=beta_series,
            inertia_mid_series=inertia_mid_series,
            enabled_strategies=long_strategies
        )

        raw_signals = result.get('long_signals', [])

        # 转换返回格式
        converted_signals = []
        for signal in raw_signals:
            # 提取触发的策略信息
            triggered_strategy = None
            for strategy_info in signal.get('strategies', []):
                if strategy_info.get('triggered', False):
                    triggered_strategy = strategy_info
                    break

            if not triggered_strategy:
                logger.warning(f"信号 {signal['timestamp']} 无触发策略，跳过")
                continue

            converted_signals.append({
                'timestamp': signal['timestamp'],
                'price': Decimal(str(signal['price'])),
                'reason': triggered_strategy.get('name', 'Unknown'),
                'confidence': 0.8,
                'strategy_id': triggered_strategy.get('id', 'unknown'),
                'direction': 'long'
            })

        logger.info(f"生成买入信号: {len(converted_signals)}个")
        return converted_signals

    def generate_sell_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series],
        open_orders: List[Order]
    ) -> List[Dict]:
        """
        生成卖出信号（EMA25回归逻辑）

        基于DDPS-Z经验规则：当K线回归EMA25时卖出。
        判断条件：K线的[low, high]区间包含EMA25值。

        Args:
            klines (pd.DataFrame): K线数据，index为pd.DatetimeIndex
            indicators (Dict[str, pd.Series]): 技术指标字典
                必须包含：'ema25'
            open_orders (List[Order]): 当前持仓订单列表

        Returns:
            List[Dict]: 卖出信号列表，格式：
                [{
                    'timestamp': int,      # 卖出时间戳（毫秒）
                    'price': Decimal,      # 卖出价格（EMA25值）
                    'order_id': str,       # 关联订单ID
                    'reason': str,         # 卖出理由
                    'strategy_id': str     # 触发策略ID
                }, ...]

        Raises:
            KeyError: 当indicators缺少'ema25'时抛出

        Business Logic:
            - 对每个持仓订单，从买入后的下一根K线开始检查
            - 检查条件：kline['low'] <= ema25 <= kline['high']
            - 找到第一个满足条件的K线即生成卖出信号
            - 卖出价格为EMA25值（回归点）

        Example:
            >>> klines = pd.DataFrame({
            ...     'low': [2290, 2295, 2285],
            ...     'high': [2310, 2315, 2305]
            ... }, index=pd.DatetimeIndex(['2026-01-06 00:00', '04:00', '08:00'], tz='UTC'))
            >>> indicators = {'ema25': pd.Series([2305, 2308, 2300])}
            >>> order = Order(id='order_123', open_timestamp=int(klines.index[0].timestamp()*1000), ...)
            >>> signals = strategy.generate_sell_signals(klines, indicators, [order])
            >>> print(signals[0]['reason'])  # 'EMA25回归'
        """
        # Guard Clause: 验证indicators包含ema25
        if 'ema25' not in indicators:
            available = list(indicators.keys())
            raise KeyError(
                f"indicators缺少必要指标: 'ema25'。\n"
                f"可用指标: {available}\n"
                f"请确保已计算EMA25指标。"
            )

        # 边界处理：无持仓订单时返回空列表
        if not open_orders:
            logger.debug("无持仓订单，跳过卖出信号生成")
            return []

        sell_signals = []
        ema25 = indicators['ema25']

        # 对每个持仓订单生成卖出信号
        for order in open_orders:
            # 找到订单买入时间对应的K线索引
            buy_time = pd.Timestamp(order.open_timestamp, unit='ms', tz='UTC')

            # Guard Clause: 买入时间不在K线范围内（理论上不应发生）
            if buy_time not in klines.index:
                logger.warning(
                    f"订单 {order.id} 买入时间 {buy_time} 不在K线范围内，跳过"
                )
                continue

            buy_idx = klines.index.get_loc(buy_time)

            # 从买入后的下一根K线开始检查EMA25回归
            for i in range(buy_idx + 1, len(klines)):
                kline = klines.iloc[i]
                ema_value = ema25.iloc[i]

                # 跳过NaN值
                if pd.isna(ema_value):
                    continue

                # 检查K线是否包含EMA25（回归条件）
                # 业务逻辑：K线的[low, high]区间包含EMA25值
                if kline['low'] <= ema_value <= kline['high']:
                    sell_signals.append({
                        'timestamp': int(klines.index[i].timestamp() * 1000),
                        'price': Decimal(str(ema_value)),  # 以EMA25值作为卖出价格
                        'order_id': order.id,
                        'reason': 'EMA25回归',
                        'strategy_id': 'ema25_reversion'
                    })
                    logger.debug(
                        f"订单 {order.id} 在 {klines.index[i]} 触发EMA25回归卖出"
                    )
                    break  # 找到第一个满足条件的K线后停止

        logger.info(f"生成卖出信号: {len(sell_signals)}个")
        return sell_signals

    def calculate_position_size(
        self,
        signal: Dict,
        available_capital: Decimal,
        current_price: Decimal
    ) -> Decimal:
        """
        计算仓位大小（固定金额策略）

        返回配置的单笔买入金额（buy_amount_usdt）。

        Args:
            signal (Dict): 买入信号（未使用）
            available_capital (Decimal): 可用资金（未使用）
            current_price (Decimal): 当前价格（未使用）

        Returns:
            Decimal: 返回 self.buy_amount_usdt（初始化时配置的金额）

        Example:
            >>> strategy = DDPSZStrategy(position_size=Decimal("200"))
            >>> size = strategy.calculate_position_size({}, Decimal("10000"), Decimal("2300"))
            >>> print(size)  # Decimal('200')
        """
        return self.buy_amount_usdt

    def should_stop_loss(
        self,
        order: Order,
        current_price: Decimal,
        current_timestamp: int
    ) -> bool:
        """
        检查是否需要止损（MVP阶段不启用）

        Args:
            order (Order): 订单对象（未使用）
            current_price (Decimal): 当前价格（未使用）
            current_timestamp (int): 当前时间戳（未使用）

        Returns:
            bool: 固定返回False（MVP阶段不启用止损）

        Example:
            >>> strategy = DDPSZStrategy()
            >>> should_stop = strategy.should_stop_loss(order, Decimal("2200"), 123456)
            >>> print(should_stop)  # False
        """
        return False

    def should_take_profit(
        self,
        order: Order,
        current_price: Decimal,
        current_timestamp: int
    ) -> bool:
        """
        检查是否需要止盈（MVP阶段不启用）

        Args:
            order (Order): 订单对象（未使用）
            current_price (Decimal): 当前价格（未使用）
            current_timestamp (int): 当前时间戳（未使用）

        Returns:
            bool: 固定返回False（MVP阶段不启用止盈）

        Example:
            >>> strategy = DDPSZStrategy()
            >>> should_profit = strategy.should_take_profit(order, Decimal("2400"), 123456)
            >>> print(should_profit)  # False
        """
        return False

    def get_required_indicators(self) -> List[str]:
        """
        返回所需的技术指标列表

        DDPS-Z策略需要的指标：
        - ema25: EMA25均线（用于买入/卖出/做空/平空）
        - p5: P5静态阈值（用于做多策略）
        - p95: P95静态阈值（用于做空策略）
        - beta: EMA斜率（用于买入和做空）
        - inertia_mid: 惯性中值（用于买入和做空）

        Returns:
            List[str]: 所需指标列表，根据enabled_strategies动态返回
        """
        indicators = ['ema25', 'p5', 'beta', 'inertia_mid']
        # 如果启用了做空策略，需要p95
        if any(s in self.enabled_strategies for s in [3, 4]):
            indicators.append('p95')
        return indicators

    def generate_short_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series]
    ) -> List[Dict]:
        """
        生成做空信号（策略3、4）

        调用SignalCalculator生成做空信号。

        Args:
            klines (pd.DataFrame): K线数据
            indicators (Dict[str, pd.Series]): 技术指标字典
                必须包含：'ema25', 'p95', 'beta', 'inertia_mid'

        Returns:
            List[Dict]: 做空信号列表，格式：
                [{
                    'timestamp': int,          # 做空时间戳（毫秒）
                    'price': Decimal,          # 做空价格
                    'reason': str,             # 做空理由
                    'confidence': float,       # 信号强度
                    'strategy_id': str,        # 触发策略ID
                    'direction': str           # 'short'
                }, ...]
        """
        # Guard Clause: 检查是否启用了做空策略
        if not any(s in self.enabled_strategies for s in [3, 4]):
            logger.debug("未启用做空策略(3,4)，跳过做空信号生成")
            return []

        # Guard Clause: 验证klines非空
        if klines.empty:
            raise ValueError("klines不能为空DataFrame")

        # Guard Clause: 验证p95指标存在
        required_indicators = ['ema25', 'p95', 'beta', 'inertia_mid']

        for indicator in required_indicators:
            if indicator not in indicators:
                available = list(indicators.keys())
                raise KeyError(
                    f"indicators缺少必要指标: '{indicator}'。\n"
                    f"可用指标: {available}"
                )

        # 准备输入数据
        kline_dicts = klines.reset_index().to_dict('records')

        ema_series = indicators['ema25'].values
        p5_series = indicators.get('p5', pd.Series([np.nan] * len(klines))).values
        p95_series = indicators['p95'].values
        beta_series = indicators['beta'].values
        inertia_mid_series = indicators['inertia_mid'].values

        # 过滤做空策略
        short_strategies = [s for s in self.enabled_strategies if s in [3, 4]]

        # 调用SignalCalculator
        logger.debug(f"调用SignalCalculator做空: {len(kline_dicts)}根K线, 策略{short_strategies}")
        result = self.calculator.calculate(
            klines=kline_dicts,
            ema_series=ema_series,
            p5_series=p5_series,
            beta_series=beta_series,
            inertia_mid_series=inertia_mid_series,
            p95_series=p95_series,
            enabled_strategies=short_strategies
        )

        raw_signals = result.get('short_signals', [])

        # 转换返回格式
        converted_signals = []
        for signal in raw_signals:
            triggered_strategy = None
            for strategy_info in signal.get('strategies', []):
                if strategy_info.get('triggered', False):
                    triggered_strategy = strategy_info
                    break

            if not triggered_strategy:
                continue

            converted_signals.append({
                'timestamp': signal['timestamp'],
                'price': Decimal(str(signal['price'])),
                'reason': triggered_strategy.get('name', 'Unknown'),
                'confidence': 0.8,
                'strategy_id': triggered_strategy.get('id', 'unknown'),
                'direction': 'short'
            })

        logger.info(f"生成做空信号: {len(converted_signals)}个")
        return converted_signals

    def generate_cover_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series],
        open_short_orders: List[Order]
    ) -> List[Dict]:
        """
        生成平空信号（EMA25回归逻辑）

        基于DDPS-Z经验规则：当K线回归EMA25时平仓。
        与做多卖出逻辑镜像：K线的[low, high]区间包含EMA25值。

        Args:
            klines (pd.DataFrame): K线数据
            indicators (Dict[str, pd.Series]): 技术指标字典
                必须包含：'ema25'
            open_short_orders (List[Order]): 当前做空持仓订单列表

        Returns:
            List[Dict]: 平空信号列表，格式：
                [{
                    'timestamp': int,      # 平空时间戳（毫秒）
                    'price': Decimal,      # 平空价格（EMA25值）
                    'order_id': str,       # 关联订单ID
                    'reason': str,         # 平空理由
                    'strategy_id': str     # 触发策略ID
                }, ...]
        """
        # Guard Clause: 验证indicators包含ema25
        if 'ema25' not in indicators:
            available = list(indicators.keys())
            raise KeyError(
                f"indicators缺少必要指标: 'ema25'。\n"
                f"可用指标: {available}"
            )

        # 边界处理：无做空持仓订单时返回空列表
        if not open_short_orders:
            logger.debug("无做空持仓订单，跳过平空信号生成")
            return []

        cover_signals = []
        ema25 = indicators['ema25']

        # 对每个做空持仓订单生成平空信号
        for order in open_short_orders:
            # 找到订单开仓时间对应的K线索引
            open_time = pd.Timestamp(order.open_timestamp, unit='ms', tz='UTC')

            if open_time not in klines.index:
                logger.warning(
                    f"订单 {order.id} 开仓时间 {open_time} 不在K线范围内，跳过"
                )
                continue

            open_idx = klines.index.get_loc(open_time)

            # 从开仓后的下一根K线开始检查EMA25回归
            for i in range(open_idx + 1, len(klines)):
                kline = klines.iloc[i]
                ema_value = ema25.iloc[i]

                # 跳过NaN值
                if pd.isna(ema_value):
                    continue

                # 检查K线是否包含EMA25（回归条件）
                if kline['low'] <= ema_value <= kline['high']:
                    cover_signals.append({
                        'timestamp': int(klines.index[i].timestamp() * 1000),
                        'price': Decimal(str(ema_value)),
                        'order_id': order.id,
                        'reason': 'EMA25回归',
                        'strategy_id': 'ema25_reversion'
                    })
                    logger.debug(
                        f"做空订单 {order.id} 在 {klines.index[i]} 触发EMA25回归平仓"
                    )
                    break

        logger.info(f"生成平空信号: {len(cover_signals)}个")
        return cover_signals
