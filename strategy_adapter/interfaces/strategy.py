"""
策略接口定义

本模块定义了标准化策略接口IStrategy，所有应用层策略必须实现此接口。

核心设计原则：
- 无状态设计：核心方法不依赖self的内部状态，状态通过参数传入
- 职责单一：每个方法负责一个明确的决策（买入、卖出、止盈、止损、仓位）
- 类型安全：所有参数和返回值都有完整的类型提示
- 文档完整：每个方法包含详细的docstring（Args、Returns、Example）

迭代编号: 013 (策略适配层)
创建日期: 2026-01-06
关联任务: TASK-013-004
关联需求: FP-013-002 (prd.md)
关联架构: architecture.md#2.1 接口定义模块
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from decimal import Decimal
import pandas as pd


class IStrategy(ABC):
    """
    策略接口（所有应用层策略必须实现）

    设计原则：
    - **无状态设计**：核心方法不依赖self的内部状态，持仓信息、订单历史等状态通过参数传入
    - **职责单一**：每个方法负责一个明确的决策
    - **类型安全**：所有参数和返回值都有完整的类型提示

    重要原则：无状态设计
    - 所有核心方法应该是无状态的（不依赖self的内部状态）
    - 持仓信息、订单历史等状态通过参数传入
    - 允许使用@lru_cache等装饰器优化性能，但不改变核心逻辑的无状态性

    Example:
        >>> class MyStrategy(IStrategy):
        ...     def get_strategy_name(self) -> str:
        ...         return "My Custom Strategy"
        ...
        ...     def generate_buy_signals(self, klines, indicators):
        ...         # 实现买入逻辑
        ...         return [{'timestamp': 123, 'price': 100, ...}]

    Raises:
        TypeError: 实例化抽象类或未实现抽象方法时抛出
    """

    @abstractmethod
    def get_strategy_name(self) -> str:
        """
        返回策略名称（用于识别和日志）

        Returns:
            str: 策略名称，如 "DDPS-Z" 或 "Simple MA Cross"

        Example:
            >>> strategy = DDPSZStrategy()
            >>> strategy.get_strategy_name()
            'DDPS-Z'
        """
        pass

    @abstractmethod
    def get_strategy_version(self) -> str:
        """
        返回策略版本（用于版本管理）

        Returns:
            str: 策略版本号，建议使用语义化版本，如 "1.0.0"

        Example:
            >>> strategy = DDPSZStrategy()
            >>> strategy.get_strategy_version()
            '1.0'
        """
        pass

    @abstractmethod
    def generate_buy_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series]
    ) -> List[Dict]:
        """
        生成买入信号

        注意：此方法应该是无状态的，不依赖self的内部状态。
        每次调用时，根据输入参数计算买入信号。

        Args:
            klines (pd.DataFrame): K线数据 (OHLCV)，index为pd.DatetimeIndex
                必须包含列：['open', 'high', 'low', 'close', 'volume']
            indicators (Dict[str, pd.Series]): 技术指标字典
                例如：{'ema25': pd.Series, 'rsi': pd.Series}

        Returns:
            List[Dict]: 买入信号列表，每个信号为字典：
                {
                    'timestamp': int,      # 买入时间戳（毫秒）
                    'price': Decimal,      # 买入价格
                    'reason': str,         # 买入理由
                    'confidence': float,   # 信号强度 [0-1]
                    'strategy_id': str     # 触发策略ID（可选）
                }

        Example:
            >>> klines = pd.DataFrame({'open': [...], 'close': [...]})
            >>> indicators = {'ema25': pd.Series([...])}
            >>> signals = strategy.generate_buy_signals(klines, indicators)
            >>> print(signals[0])
            {'timestamp': 1736164800000, 'price': Decimal('2300'), ...}

        Raises:
            KeyError: 当indicators缺少必要指标时抛出
        """
        pass

    @abstractmethod
    def generate_sell_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series],
        open_orders: List['Order']  # Forward reference
    ) -> List[Dict]:
        """
        生成卖出信号

        注意：此方法应该是无状态的，不依赖self的内部状态。
        持仓信息通过open_orders参数传入。

        Args:
            klines (pd.DataFrame): K线数据
            indicators (Dict[str, pd.Series]): 技术指标字典
            open_orders (List[Order]): 当前持仓订单列表（由StrategyAdapter管理）

        Returns:
            List[Dict]: 卖出信号列表，每个信号为字典：
                {
                    'timestamp': int,      # 卖出时间戳（毫秒）
                    'price': Decimal,      # 卖出价格
                    'order_id': str,       # 关联订单ID
                    'reason': str,         # 卖出理由
                    'strategy_id': str     # 触发策略ID
                }

        Example:
            >>> klines = pd.DataFrame({'open': [...], 'close': [...]})
            >>> indicators = {'ema25': pd.Series([...])}
            >>> open_orders = [Order(id='order_123', ...)]
            >>> signals = strategy.generate_sell_signals(klines, indicators, open_orders)
            >>> print(signals[0])
            {'timestamp': 1736230800000, 'order_id': 'order_123', ...}

        Raises:
            KeyError: 当indicators缺少必要指标时抛出
        """
        pass

    @abstractmethod
    def calculate_position_size(
        self,
        signal: Dict,
        available_capital: Decimal,
        current_price: Decimal
    ) -> Decimal:
        """
        计算仓位大小

        Args:
            signal (Dict): 买入信号，包含timestamp、price、reason等
            available_capital (Decimal): 可用资金（USDT）
            current_price (Decimal): 当前价格（USDT）

        Returns:
            Decimal: 买入金额（USDT），例如 Decimal("100")

        Example:
            >>> signal = {'timestamp': 123, 'price': Decimal('2300'), ...}
            >>> size = strategy.calculate_position_size(
            ...     signal, Decimal("10000"), Decimal("2300")
            ... )
            >>> print(size)  # Decimal("100") - 固定100 USDT

        Raises:
            ValueError: 当available_capital < 0或current_price <= 0时抛出
        """
        pass

    @abstractmethod
    def should_stop_loss(
        self,
        order: 'Order',
        current_price: Decimal,
        current_timestamp: int
    ) -> bool:
        """
        检查是否需要止损

        Args:
            order (Order): 订单对象
            current_price (Decimal): 当前价格
            current_timestamp (int): 当前时间戳（毫秒）

        Returns:
            bool: True表示触发止损，False表示不触发

        Example:
            >>> order = Order(open_price=Decimal("2300"), ...)
            >>> should_stop = strategy.should_stop_loss(
            ...     order, Decimal("2200"), 1736230800000
            ... )
            >>> print(should_stop)  # False (MVP阶段不启用止损)

        Raises:
            ValueError: 当current_price <= 0时抛出
        """
        pass

    @abstractmethod
    def should_take_profit(
        self,
        order: 'Order',
        current_price: Decimal,
        current_timestamp: int
    ) -> bool:
        """
        检查是否需要止盈

        Args:
            order (Order): 订单对象
            current_price (Decimal): 当前价格
            current_timestamp (int): 当前时间戳（毫秒）

        Returns:
            bool: True表示触发止盈，False表示不触发

        Example:
            >>> order = Order(open_price=Decimal("2300"), ...)
            >>> should_profit = strategy.should_take_profit(
            ...     order, Decimal("2400"), 1736230800000
            ... )
            >>> print(should_profit)  # False (MVP阶段不启用止盈)

        Raises:
            ValueError: 当current_price <= 0时抛出
        """
        pass

    def get_required_indicators(self) -> List[str]:
        """
        返回所需的技术指标列表（可选方法）

        此方法有默认实现，子类可以选择性覆盖。

        Returns:
            List[str]: 指标名称列表，例如 ['ema25', 'rsi', 'macd']
                     默认返回空列表，表示不依赖任何指标

        Example:
            >>> class DDPSZStrategy(IStrategy):
            ...     def get_required_indicators(self):
            ...         return ['ema25']
            >>> strategy = DDPSZStrategy()
            >>> print(strategy.get_required_indicators())
            ['ema25']
        """
        return []
