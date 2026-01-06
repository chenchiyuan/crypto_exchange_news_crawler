"""
DDPS-Z策略适配器

本模块实现DDPSZStrategy，将DDPS-Z应用层策略适配为IStrategy接口，
复用现有的BuySignalCalculator和EMA25卖出逻辑。

核心功能：
- 买入信号生成：复用BuySignalCalculator（策略1: EMA斜率未来预测，策略2: 惯性下跌中值突破）
- 卖出信号生成：EMA25回归逻辑（K线[low, high]包含EMA25）
- 仓位管理：固定100 USDT仓位（MVP阶段）
- 止盈止损：MVP阶段不启用

复用策略说明：
- BuySignalCalculator：直接调用现有逻辑，转换信号格式
- EMA25卖出：基于DDPS-Z经验规则，K线回归EMA25时卖出

迭代编号: 013 (策略适配层)
创建日期: 2026-01-06
关联任务: TASK-013-008
关联需求: FP-013-008 (prd.md)
关联架构: architecture.md#4.4 应用适配模块
"""

from decimal import Decimal
from typing import Dict, List
import pandas as pd
import numpy as np
import logging

from strategy_adapter.interfaces import IStrategy
from strategy_adapter.models import Order
from ddps_z.calculators import BuySignalCalculator

logger = logging.getLogger(__name__)


class DDPSZStrategy(IStrategy):
    """
    DDPS-Z策略适配器（DDPS-Z Strategy Adapter）

    职责：
    - 实现IStrategy接口，将DDPS-Z策略适配为统一接口
    - 复用BuySignalCalculator生成买入信号
    - 实现EMA25回归卖出逻辑
    - 提供DDPS-Z特定的参数配置（固定100 USDT仓位）

    设计原则：
    - 无状态设计：不保存任何订单或持仓信息
    - 复用优先：直接调用现有的BuySignalCalculator
    - 信号转换：将BuySignalCalculator返回格式转换为IStrategy要求格式

    Example:
        >>> strategy = DDPSZStrategy()
        >>> klines = pd.DataFrame({'open': [...], 'close': [...]})
        >>> indicators = {
        ...     'ema25': pd.Series([...]),
        ...     'p5': pd.Series([...]),
        ...     'beta': pd.Series([...]),
        ...     'inertia_mid': pd.Series([...])
        ... }
        >>> buy_signals = strategy.generate_buy_signals(klines, indicators)
        >>> print(len(buy_signals))  # 5个买入信号
    """

    def __init__(self):
        """
        初始化DDPS-Z策略

        配置：
        - buy_amount_usdt: 固定100 USDT仓位（MVP阶段）
        - calculator: BuySignalCalculator实例
        """
        self.buy_amount_usdt = Decimal("100")  # 固定100U
        self.calculator = BuySignalCalculator()

        logger.info("初始化DDPSZStrategy: 固定仓位=100 USDT")

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
        生成买入信号（复用BuySignalCalculator逻辑）

        调用现有的BuySignalCalculator，将其返回格式转换为IStrategy要求的格式。

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
                    'strategy_id': str         # 触发策略ID
                }, ...]

        Raises:
            KeyError: 当indicators缺少必要指标时抛出
                错误信息包含缺失的指标名称
            ValueError: 当klines为空时抛出

        Side Effects:
            - 调用BuySignalCalculator.calculate()
            - 记录日志（发现的信号数量）

        Example:
            >>> klines = pd.DataFrame({
            ...     'open_time': pd.DatetimeIndex(['2026-01-06 00:00'], tz='UTC'),
            ...     'close': [2300.0]
            ... })
            >>> indicators = {
            ...     'ema25': pd.Series([2280.0]),
            ...     'p5': pd.Series([2310.0]),
            ...     'beta': pd.Series([5.0]),
            ...     'inertia_mid': pd.Series([2290.0])
            ... }
            >>> signals = strategy.generate_buy_signals(klines, indicators)
            >>> print(signals[0]['reason'])  # 'EMA斜率未来预测'
        """
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
        # BuySignalCalculator需要List[Dict]格式的klines
        kline_dicts = klines.reset_index().to_dict('records')

        # 提取numpy数组格式的指标序列
        ema_series = indicators['ema25'].values
        p5_series = indicators['p5'].values
        beta_series = indicators['beta'].values
        inertia_mid_series = indicators['inertia_mid'].values

        # 调用现有BuySignalCalculator逻辑
        logger.debug(f"调用BuySignalCalculator: {len(kline_dicts)}根K线")
        raw_signals = self.calculator.calculate(
            klines=kline_dicts,
            ema_series=ema_series,
            p5_series=p5_series,
            beta_series=beta_series,
            inertia_mid_series=inertia_mid_series
        )

        # 转换返回格式（BuySignalCalculator格式 → IStrategy格式）
        converted_signals = []
        for signal in raw_signals:
            # 提取触发的策略信息（strategies列表中第一个triggered=True的策略）
            triggered_strategy = None
            for strategy_info in signal.get('strategies', []):
                if strategy_info.get('triggered', False):
                    triggered_strategy = strategy_info
                    break

            # 如果没有触发策略（理论上不应该发生，因为BuySignalCalculator已筛选）
            if not triggered_strategy:
                logger.warning(f"信号 {signal['timestamp']} 无触发策略，跳过")
                continue

            # 构建IStrategy格式的信号
            converted_signals.append({
                'timestamp': signal['timestamp'],
                'price': Decimal(str(signal['buy_price'])),
                'reason': triggered_strategy.get('name', 'Unknown'),
                'confidence': 0.8,  # DDPS-Z策略默认信号强度
                'strategy_id': triggered_strategy.get('id', 'unknown')
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
        计算仓位大小（固定100 USDT）

        MVP阶段采用固定仓位策略，不考虑可用资金和风险管理。

        Args:
            signal (Dict): 买入信号（未使用）
            available_capital (Decimal): 可用资金（未使用）
            current_price (Decimal): 当前价格（未使用）

        Returns:
            Decimal: 固定返回 Decimal("100")

        Example:
            >>> strategy = DDPSZStrategy()
            >>> size = strategy.calculate_position_size({}, Decimal("10000"), Decimal("2300"))
            >>> print(size)  # Decimal('100')
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

        DDPS-Z策略需要4个指标：
        - ema25: EMA25均线（用于买入和卖出）
        - p5: P5静态阈值（用于买入）
        - beta: EMA斜率（用于买入）
        - inertia_mid: 惯性中值（用于买入）

        Returns:
            List[str]: ['ema25', 'p5', 'beta', 'inertia_mid']

        Example:
            >>> strategy = DDPSZStrategy()
            >>> indicators = strategy.get_required_indicators()
            >>> print(indicators)  # ['ema25', 'p5', 'beta', 'inertia_mid']
        """
        return ['ema25', 'p5', 'beta', 'inertia_mid']
