"""
DDPS-Z 数据模型

本模块定义DDPS-Z系统使用的数据模型和数据类。

Related:
    - PRD: docs/iterations/023-ddps-price-monitor/prd.md
    - Architecture: docs/iterations/023-ddps-price-monitor/architecture.md
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, List
import uuid

from django.db import models


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
class PriceStatus:
    """
    价格状态数据类

    包含单个交易对的完整价格状态信息。

    Attributes:
        symbol: 交易对
        current_price: 当前价格
        cycle_phase: 周期阶段
        p5: P5价格（下界）
        p95: P95价格（上界）
        ema25: EMA25均线
        inertia_mid: 惯性中值
        probability: 概率位置（0-100）
    """
    symbol: str
    current_price: Decimal
    cycle_phase: str
    p5: Decimal
    p95: Decimal
    ema25: Decimal
    inertia_mid: Decimal
    probability: int  # 0-100


@dataclass
class BuySignal:
    """
    买入信号数据类

    当价格满足买入条件时生成。

    Attributes:
        symbol: 交易对
        price: 当前价格
        cycle_phase: 周期阶段
        p5: P5价格
        trigger_condition: 触发条件描述
    """
    symbol: str
    price: Decimal
    cycle_phase: str
    p5: Decimal
    trigger_condition: str  # e.g., "价格<=P5"


@dataclass
class ExitSignal:
    """
    卖出信号数据类

    当持仓订单满足退出条件时生成。

    Attributes:
        order_id: 订单ID
        symbol: 交易对
        open_price: 开仓价格
        exit_price: 退出价格
        exit_type: 退出类型
        profit_rate: 盈利率
        cycle_phase: 当前周期阶段
    """
    order_id: str
    symbol: str
    open_price: Decimal
    exit_price: Decimal
    exit_type: str  # ema_reversion / consolidation_mid / p95_take_profit
    profit_rate: Decimal
    cycle_phase: str


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
