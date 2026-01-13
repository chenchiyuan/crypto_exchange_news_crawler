"""
DDPS-Z 数据模型

本模块定义DDPS-Z系统使用的数据模型和数据类。

Related:
    - PRD: docs/iterations/023-ddps-price-monitor/prd.md
    - PRD: docs/iterations/024-ddps-multi-market-support/prd.md
    - Architecture: docs/iterations/024-ddps-multi-market-support/architecture.md
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Tuple, Dict
import uuid

from django.db import models


# =============================================================================
# 标准K线和类型枚举 - 迭代024
# =============================================================================

@dataclass
class StandardKLine:
    """
    标准K线数据结构 - 与数据源无关

    所有数据源获取的K线都转换为此格式，
    DDPS计算层只接受此格式的数据。

    Attributes:
        timestamp: 开盘时间，毫秒时间戳
        open: 开盘价
        high: 最高价
        low: 最低价
        close: 收盘价
        volume: 成交量
    """
    timestamp: int      # 毫秒时间戳
    open: float         # 开盘价
    high: float         # 最高价
    low: float          # 最低价
    close: float        # 收盘价
    volume: float       # 成交量


class MarketType(str, Enum):
    """
    市场类型枚举

    定义支持的市场类型，包括加密货币和传统金融市场。
    """
    CRYPTO_SPOT = 'crypto_spot'          # 加密货币现货
    CRYPTO_FUTURES = 'crypto_futures'    # 加密货币合约
    US_STOCK = 'us_stock'                # 美股
    A_STOCK = 'a_stock'                  # A股
    HK_STOCK = 'hk_stock'                # 港股

    @classmethod
    def choices(cls) -> List[Tuple[str, str]]:
        """返回Django模型choices格式"""
        labels = {
            cls.CRYPTO_SPOT: '加密货币现货',
            cls.CRYPTO_FUTURES: '加密货币合约',
            cls.US_STOCK: '美股',
            cls.A_STOCK: 'A股',
            cls.HK_STOCK: '港股',
        }
        return [(m.value, labels[m]) for m in cls]

    def is_crypto(self) -> bool:
        """判断是否为加密货币市场"""
        return self in (MarketType.CRYPTO_SPOT, MarketType.CRYPTO_FUTURES)

    def is_stock(self) -> bool:
        """判断是否为股票市场"""
        return self in (MarketType.US_STOCK, MarketType.A_STOCK, MarketType.HK_STOCK)

    @classmethod
    def normalize(cls, value: str) -> str:
        """
        标准化market_type值（向后兼容）

        Args:
            value: 原始值，可能是旧格式

        Returns:
            标准化后的值
        """
        legacy_mapping = {
            'spot': cls.CRYPTO_SPOT.value,
            'futures': cls.CRYPTO_FUTURES.value,
        }
        return legacy_mapping.get(value, value)


class Interval(str, Enum):
    """
    K线周期枚举

    定义支持的K线时间周期。
    """
    M1 = '1m'       # 1分钟
    M5 = '5m'       # 5分钟
    M15 = '15m'     # 15分钟
    M30 = '30m'     # 30分钟
    H1 = '1h'       # 1小时
    H4 = '4h'       # 4小时
    D1 = '1d'       # 1天
    W1 = '1w'       # 1周

    @classmethod
    def choices(cls) -> List[Tuple[str, str]]:
        """返回Django模型choices格式"""
        labels = {
            cls.M1: '1分钟',
            cls.M5: '5分钟',
            cls.M15: '15分钟',
            cls.M30: '30分钟',
            cls.H1: '1小时',
            cls.H4: '4小时',
            cls.D1: '1天',
            cls.W1: '1周',
        }
        return [(i.value, labels[i]) for i in cls]

    @classmethod
    def to_hours(cls, interval: str) -> float:
        """
        将interval转换为小时数

        Args:
            interval: K线周期字符串，如 '4h', '1d'

        Returns:
            对应的小时数
        """
        mapping = {
            '1m': 1 / 60,
            '5m': 5 / 60,
            '15m': 0.25,
            '30m': 0.5,
            '1h': 1.0,
            '4h': 4.0,
            '1d': 24.0,
            '1w': 168.0,
        }
        return mapping.get(interval, 4.0)

    @classmethod
    def to_minutes(cls, interval: str) -> int:
        """将interval转换为分钟数"""
        return int(cls.to_hours(interval) * 60)

    @classmethod
    def to_seconds(cls, interval: str) -> int:
        """将interval转换为秒数"""
        return int(cls.to_hours(interval) * 3600)


# =============================================================================
# 虚拟订单数据类（内存管理）- 迭代023
# =============================================================================

@dataclass
class VirtualOrder:
    """
    虚拟订单数据类（内存管理）

    用于DDPS价格监控服务追踪策略信号产生的虚拟订单。
    MVP阶段使用内存管理，后续P1可扩展为数据库持久化。

    Attributes:
        id: 订单唯一标识
        symbol: 交易对，如'ETHUSDT'
        open_price: 开仓价格
        open_timestamp: 开仓时间戳（毫秒）
        quantity: 数量
        cycle_phase_at_open: 开仓时的周期阶段
        status: 订单状态 ('open' / 'closed')
        close_price: 平仓价格
        close_timestamp: 平仓时间戳（毫秒）
        exit_type: 退出类型
        profit_loss: 盈亏金额
        profit_loss_rate: 盈亏比例

    Example:
        >>> order = VirtualOrder(
        ...     symbol='ETHUSDT',
        ...     open_price=Decimal('3500.00'),
        ...     open_timestamp=1704067200000,
        ...     quantity=Decimal('0.1'),
        ...     cycle_phase_at_open='consolidation'
        ... )
        >>> order.status
        'open'
    """
    symbol: str
    open_price: Decimal
    open_timestamp: int
    quantity: Decimal
    cycle_phase_at_open: str
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: str = 'open'  # 'open' / 'closed'
    close_price: Optional[Decimal] = None
    close_timestamp: Optional[int] = None
    exit_type: Optional[str] = None
    profit_loss: Optional[Decimal] = None
    profit_loss_rate: Optional[Decimal] = None

    def close(
        self,
        close_price: Decimal,
        close_timestamp: int,
        exit_type: str
    ) -> None:
        """
        平仓订单

        Args:
            close_price: 平仓价格
            close_timestamp: 平仓时间戳
            exit_type: 退出类型

        Side Effects:
            更新订单状态为closed，计算盈亏
        """
        self.close_price = close_price
        self.close_timestamp = close_timestamp
        self.exit_type = exit_type
        self.status = 'closed'

        # 计算盈亏（做多）
        self.profit_loss = (close_price - self.open_price) * self.quantity
        if self.open_price > 0:
            self.profit_loss_rate = (
                (close_price - self.open_price) / self.open_price * Decimal('100')
            )
        else:
            self.profit_loss_rate = Decimal('0')

    @property
    def is_open(self) -> bool:
        """是否为未平仓订单"""
        return self.status == 'open'

    @property
    def position_value(self) -> Decimal:
        """持仓价值"""
        return self.open_price * self.quantity


# =============================================================================
# 监控服务数据类 - 迭代023
# =============================================================================

@dataclass
class HoldingInfo:
    """
    持仓订单信息 - 迭代038新增

    用于DDPS监控推送中展示当前持仓状态。

    Attributes:
        order_id: 订单ID
        buy_price: 买入价格
        buy_timestamp: 买入时间戳(毫秒)
        holding_hours: 持仓时长(小时)
        sell_order_price: 卖出挂单价格（可选）
    """
    order_id: str
    buy_price: Decimal
    buy_timestamp: int
    holding_hours: float
    sell_order_price: Optional[Decimal] = None


@dataclass
class PriceStatus:
    """
    价格状态数据类

    包含单个交易对的完整价格状态信息。
    迭代038扩展：新增策略16相关字段。
    Bug-031修复：新增kline_timestamp字段。

    Attributes:
        symbol: 交易对
        current_price: 当前价格
        cycle_phase: 周期阶段
        p5: P5价格（下界）
        p95: P95价格（上界）
        ema25: EMA25均线
        inertia_mid: 惯性中值
        probability: 概率位置（0-100）
        order_price: 策略16挂单价格（迭代038新增）
        adx: ADX指标值（迭代038新增）
        beta: 贝塔值（迭代038新增）
        cycle_duration_hours: 周期连续时长（迭代038新增）
        inertia_lower: 惯性下界（迭代038新增）
        inertia_upper: 惯性上界（迭代038新增）
        cycle_distribution: 42周期占比（迭代038新增）
        holdings: 持仓订单列表（迭代038新增）
        kline_timestamp: K线时间戳(毫秒)（Bug-031新增）
    """
    symbol: str
    current_price: Decimal
    cycle_phase: str
    p5: Decimal
    p95: Decimal
    ema25: Decimal
    inertia_mid: Decimal
    probability: int  # 0-100
    # 🆕 迭代038新增字段
    order_price: Optional[Decimal] = None
    adx: Optional[float] = None
    beta: Optional[float] = None
    cycle_duration_hours: Optional[float] = None
    inertia_lower: Optional[Decimal] = None
    inertia_upper: Optional[Decimal] = None
    cycle_distribution: Optional[Dict[str, float]] = None
    holdings: Optional[List[HoldingInfo]] = None
    # 🆕 Bug-031新增字段
    kline_timestamp: Optional[int] = None  # K线时间戳(毫秒)


@dataclass
class BuySignal:
    """
    买入信号数据类

    当价格满足买入条件时生成。
    Bug-031修复：新增signal_timestamp字段。

    Attributes:
        symbol: 交易对
        price: 当前价格
        cycle_phase: 周期阶段
        p5: P5价格
        trigger_condition: 触发条件描述
        signal_timestamp: 信号产生时间戳(毫秒)（Bug-031新增）
    """
    symbol: str
    price: Decimal
    cycle_phase: str
    p5: Decimal
    trigger_condition: str  # e.g., "价格<=P5"
    # 🆕 Bug-031新增字段
    signal_timestamp: Optional[int] = None  # 信号产生时间戳(毫秒)


@dataclass
class ExitSignal:
    """
    卖出信号数据类

    当持仓订单满足退出条件时生成。
    Bug-031修复：新增holding_hours、sell_timestamp、buy_timestamp字段。

    Attributes:
        order_id: 订单ID
        symbol: 交易对
        open_price: 开仓价格
        exit_price: 退出价格
        exit_type: 退出类型/原因
        profit_rate: 盈利率
        cycle_phase: 当前周期阶段
        holding_hours: 持仓时长(小时)（Bug-031新增）
        sell_timestamp: 卖出时间戳(毫秒)（Bug-031新增）
        buy_timestamp: 买入时间戳(毫秒)（Bug-031新增）
    """
    order_id: str
    symbol: str
    open_price: Decimal
    exit_price: Decimal
    exit_type: str  # 退出原因描述
    profit_rate: Decimal
    cycle_phase: str
    # 🆕 Bug-031新增字段
    holding_hours: Optional[float] = None  # 持仓时长(小时)
    sell_timestamp: Optional[int] = None  # 卖出时间戳(毫秒)
    buy_timestamp: Optional[int] = None  # 买入时间戳(毫秒)


@dataclass
class CycleWarning:
    """
    周期预警数据类

    汇总各周期状态的交易对列表。

    Attributes:
        bull_warning: 上涨预警交易对列表
        bull_strong: 上涨强势交易对列表
        bear_warning: 下跌预警交易对列表
        bear_strong: 下跌强势交易对列表
        consolidation: 震荡期交易对列表
    """
    bull_warning: List[str] = field(default_factory=list)
    bull_strong: List[str] = field(default_factory=list)
    bear_warning: List[str] = field(default_factory=list)
    bear_strong: List[str] = field(default_factory=list)
    consolidation: List[str] = field(default_factory=list)


@dataclass
class DDPSMonitorResult:
    """
    监控结果汇总数据类

    包含单次监控运行的所有结果。

    Attributes:
        buy_signals: 买入信号列表
        exit_signals: 卖出信号列表
        cycle_warnings: 周期预警
        price_status: 价格状态列表
        update_stats: 更新统计信息
    """
    buy_signals: List[BuySignal] = field(default_factory=list)
    exit_signals: List[ExitSignal] = field(default_factory=list)
    cycle_warnings: CycleWarning = field(default_factory=CycleWarning)
    price_status: List[PriceStatus] = field(default_factory=list)
    update_stats: dict = field(default_factory=dict)
