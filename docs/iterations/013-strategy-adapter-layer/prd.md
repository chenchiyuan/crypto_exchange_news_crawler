# PRD: 策略适配层 (Strategy Adapter Layer)

**迭代编号**: 013
**迭代名称**: 策略适配层
**文档版本**: 1.0
**创建日期**: 2026-01-06
**状态**: 需求定义
**优先级**: P0

---

## 第一部分：需求原始输入

### 1.1 原始需求

> 接下来请研究目前已有的项目需求情况：
> 已知有一套基础的回测系统：backtest和vectorbt，其为系统中的回测层。
> 应用层有不少需求：比如最近实现的DDPS-Z系统，有清晰的买入，卖出条件。
>
> 我需要新建一个适配层：
> 1. 标准化数据结构和存储：订单管理，买入，卖出，记录
> 2. 分析系统：基于订单管理和backtest做数据回测
> 3. 方便接入应用层的策略，主要是买入，卖出，止盈，止损策略。也可以自己提供标准的策略供选择。从我的角度，我觉得可以定义策略实现的interface，应用层实现，接入此适配层直接配置调用。
>
> 适配层实现之后，将DDPS-Z适配并完成回测。

### 1.2 核心问题

**现状分析**：

当前系统存在三层架构，但缺少中间适配层：

```
┌─────────────────────────────────────────────┐
│ 应用层 (ddps_z/, volume_trap/, etc.)        │
│ - OrderTracker（迭代012）                    │
│ - 独立的订单追踪逻辑                         │
│ - 固定100U买入 + EMA25卖出                   │
│ ❌ 无法直接使用vectorbt回测                  │
├─────────────────────────────────────────────┤
│ ❌ 缺失：策略适配层                          │
│ - 无统一策略接口                             │
│ - 订单管理逻辑重复                           │
│ - 应用层策略与回测层割裂                     │
├─────────────────────────────────────────────┤
│ 回测层 (backtest/)                          │
│ - BacktestEngine (基于vectorbt)             │
│ - PositionManager                           │
│ - GridStrategy (4个版本)                    │
│ ✅ 功能完善，但应用层无法复用                 │
└─────────────────────────────────────────────┘
```

**核心矛盾**：

1. **重复建设**：OrderTracker（应用层）与PositionManager（回测层）功能重叠
2. **割裂状态**：DDPS-Z的买卖逻辑无法使用vectorbt进行专业回测
3. **扩展困难**：每个新策略都需要重新实现订单管理和回测逻辑

### 1.3 目标用户

- 主要用户：产品开发者本人
- 使用场景：
  - 开发新策略时，快速接入回测系统
  - 对现有策略（如DDPS-Z）进行专业回测分析
  - 统一管理不同策略的订单和交易记录

### 1.4 预期效果

实现适配层后：

1. **开发新策略**：只需实现IStrategy接口，无需关心回测细节
2. **DDPS-Z回测**：通过适配器直接使用vectorbt回测，获得专业指标（夏普比率、最大回撤等）
3. **订单管理统一**：应用层和回测层共享同一套订单数据结构
4. **可扩展性强**：未来策略可快速接入，复用适配层能力

---

## 第二部分：功能规格框架

### 2.1 系统架构

#### 2.1.1 三层架构设计

```
┌──────────────────────────────────────────────────────────────┐
│ 应用层 (Application Layer)                                   │
│                                                              │
│ ddps_z/                  volume_trap/          [其他策略]    │
│ ├─ DDPSZStrategy ────┐   ├─ VolumeTrapStrategy              │
│ │  implements         │   │  implements                      │
│ │  IStrategy          │   │  IStrategy                       │
│ └─────────────────────┼───┴──────────────────────────────────│
│                       │                                      │
└───────────────────────┼──────────────────────────────────────┘
                        │
                        ↓ 调用适配层
┌───────────────────────┼──────────────────────────────────────┐
│ 适配层 (Adapter Layer) │                                      │
│                       │                                      │
│ strategy_adapter/     │                                      │
│ ├─ interfaces/        │                                      │
│ │  └─ strategy.py ────┘ (IStrategy接口定义)                 │
│ │                                                            │
│ ├─ core/                                                     │
│ │  ├─ unified_order_manager.py  (统一订单管理)              │
│ │  ├─ strategy_adapter.py       (策略适配器)                │
│ │  └─ signal_converter.py       (信号转换器)                │
│ │                                                            │
│ ├─ models/                                                   │
│ │  ├─ order.py          (标准化订单数据结构)                │
│ │  ├─ trade_record.py   (交易记录)                          │
│ │  └─ strategy_config.py (策略配置)                         │
│ │                                                            │
│ └─ adapters/                                                 │
│    └─ ddpsz_adapter.py    (DDPS-Z策略适配器)                │
│                                    │                         │
└────────────────────────────────────┼─────────────────────────┘
                                     │
                                     ↓ 转换为vectorbt信号
┌────────────────────────────────────┼─────────────────────────┐
│ 回测层 (Backtest Layer)            │                         │
│                                    │                         │
│ backtest/                          │                         │
│ ├─ BacktestEngine ─────────────────┘                         │
│ │  (接收entries/exits信号)                                   │
│ │                                                            │
│ ├─ vectorbt (底层回测框架)                                   │
│ │  └─ Portfolio.from_signals()                              │
│ │                                                            │
│ └─ 性能指标计算                                              │
│    ├─ 夏普比率                                               │
│    ├─ 最大回撤                                               │
│    └─ 胜率、盈亏比等                                         │
└──────────────────────────────────────────────────────────────┘
```

#### 2.1.2 数据流转

```
1. 策略实现
   DDPSZStrategy.generate_signals()
   ↓
   返回 {buy_signals: [...], sell_signals: [...]}

2. 适配转换
   StrategyAdapter.adapt(DDPSZStrategy)
   ↓
   SignalConverter.to_vectorbt_signals()
   ↓
   生成 {entries: pd.Series, exits: pd.Series}

3. 回测执行
   BacktestEngine.run_backtest(entries, exits)
   ↓
   vectorbt.Portfolio.from_signals()
   ↓
   返回 BacktestResult (包含所有性能指标)

4. 订单管理
   UnifiedOrderManager.track_orders(signals, klines)
   ↓
   创建标准化Order对象
   ↓
   记录TradeRecord
```

---

### 2.2 核心接口定义

#### 2.2.1 IStrategy接口

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from decimal import Decimal
import pandas as pd

class IStrategy(ABC):
    """
    策略接口（所有应用层策略必须实现）

    职责：
    - 定义买入条件
    - 定义卖出条件
    - 定义止盈止损规则
    - 生成交易信号
    """

    @abstractmethod
    def get_strategy_name(self) -> str:
        """返回策略名称"""
        pass

    @abstractmethod
    def get_strategy_version(self) -> str:
        """返回策略版本"""
        pass

    @abstractmethod
    def generate_buy_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series]
    ) -> List[Dict]:
        """
        生成买入信号

        Args:
            klines: K线数据 (OHLCV)
            indicators: 技术指标字典 (如 {'ema25': Series, 'rsi': Series})

        Returns:
            买入信号列表
            [
                {
                    'timestamp': int,      # 买入时间戳
                    'price': Decimal,      # 买入价格
                    'reason': str,         # 买入理由
                    'confidence': float    # 信号强度 [0-1]
                },
                ...
            ]
        """
        pass

    @abstractmethod
    def generate_sell_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series],
        open_orders: List['Order']
    ) -> List[Dict]:
        """
        生成卖出信号

        Args:
            klines: K线数据
            indicators: 技术指标字典
            open_orders: 当前持仓订单列表

        Returns:
            卖出信号列表
            [
                {
                    'timestamp': int,      # 卖出时间戳
                    'price': Decimal,      # 卖出价格
                    'order_id': str,       # 关联订单ID
                    'reason': str,         # 卖出理由
                    'strategy_id': str     # 触发策略ID
                },
                ...
            ]
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
            signal: 买入信号
            available_capital: 可用资金
            current_price: 当前价格

        Returns:
            买入金额（USDT）
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
            order: 订单对象
            current_price: 当前价格
            current_timestamp: 当前时间戳

        Returns:
            是否触发止损
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
            order: 订单对象
            current_price: 当前价格
            current_timestamp: 当前时间戳

        Returns:
            是否触发止盈
        """
        pass
```

#### 2.2.2 标准化订单数据结构

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from enum import Enum

class OrderStatus(Enum):
    """订单状态枚举"""
    PENDING = "pending"      # 待成交
    FILLED = "filled"        # 已成交（持仓中）
    CLOSED = "closed"        # 已平仓
    CANCELLED = "cancelled"  # 已取消

class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"

@dataclass
class Order:
    """
    统一订单数据结构

    复用性：
    - 应用层（OrderTracker）和回测层（PositionManager）共享
    - 支持现货和合约
    - 支持多种策略
    """
    # 基础信息
    id: str
    symbol: str
    side: OrderSide
    status: OrderStatus

    # 开仓信息
    open_timestamp: int
    open_price: Decimal
    quantity: Decimal
    position_value: Decimal      # 开仓金额

    # 平仓信息（可选）
    close_timestamp: Optional[int] = None
    close_price: Optional[Decimal] = None
    close_reason: Optional[str] = None  # "take_profit" | "stop_loss" | "strategy_signal"

    # 策略信息
    strategy_name: str = ""
    strategy_id: str = ""
    entry_reason: str = ""       # 入场理由

    # 盈亏计算
    profit_loss: Optional[Decimal] = None
    profit_loss_rate: Optional[Decimal] = None
    holding_periods: Optional[int] = None  # 持仓K线数

    # 手续费
    open_commission: Decimal = Decimal("0")
    close_commission: Decimal = Decimal("0")

    # 扩展字段（策略特定数据）
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def calculate_pnl(self) -> None:
        """计算盈亏"""
        if self.status == OrderStatus.CLOSED and self.close_price:
            if self.side == OrderSide.BUY:
                self.profit_loss = (self.close_price - self.open_price) * self.quantity
            else:  # SELL (做空)
                self.profit_loss = (self.open_price - self.close_price) * self.quantity

            # 扣除手续费
            self.profit_loss -= (self.open_commission + self.close_commission)

            # 计算收益率
            if self.position_value > 0:
                self.profit_loss_rate = (self.profit_loss / self.position_value * Decimal("100"))
```

---

### 2.3 适配层核心组件

#### 2.3.1 UnifiedOrderManager（统一订单管理器）

**职责**：
- 统一OrderTracker和PositionManager的功能
- 管理订单生命周期（创建、更新、平仓）
- 计算订单盈亏和统计指标
- 提供订单查询接口

**核心方法**：

```python
class UnifiedOrderManager:
    """统一订单管理器"""

    def create_order(
        self,
        signal: Dict,
        strategy: IStrategy
    ) -> Order:
        """从信号创建订单"""
        pass

    def update_order(
        self,
        order_id: str,
        close_signal: Dict
    ) -> Order:
        """更新订单（平仓）"""
        pass

    def get_open_orders(
        self,
        strategy_name: Optional[str] = None
    ) -> List[Order]:
        """获取持仓订单"""
        pass

    def calculate_statistics(
        self,
        orders: List[Order]
    ) -> Dict:
        """计算统计指标（胜率、总盈亏等）"""
        pass
```

#### 2.3.2 StrategyAdapter（策略适配器）

**职责**：
- 将IStrategy转换为vectorbt可用的格式
- 调用UnifiedOrderManager管理订单
- 生成回测所需的entries/exits信号

**核心方法**：

```python
class StrategyAdapter:
    """策略适配器"""

    def __init__(
        self,
        strategy: IStrategy,
        order_manager: UnifiedOrderManager
    ):
        self.strategy = strategy
        self.order_manager = order_manager

    def adapt_for_backtest(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series]
    ) -> Dict:
        """
        适配策略用于回测

        Returns:
            {
                'entries': pd.Series,  # vectorbt买入信号
                'exits': pd.Series,    # vectorbt卖出信号
                'orders': List[Order], # 订单列表
                'statistics': Dict     # 统计信息
            }
        """
        pass
```

#### 2.3.3 SignalConverter（信号转换器）

**职责**：
- 将应用层信号格式转换为vectorbt格式
- 处理信号时间对齐
- 验证信号有效性

```python
class SignalConverter:
    """信号转换器"""

    @staticmethod
    def to_vectorbt_signals(
        buy_signals: List[Dict],
        sell_signals: List[Dict],
        klines: pd.DataFrame
    ) -> tuple[pd.Series, pd.Series]:
        """
        转换为vectorbt信号

        Returns:
            (entries, exits): 买入和卖出信号（pd.Series of bool）
        """
        pass
```

---

### 2.4 DDPS-Z策略适配

#### 2.4.1 DDPSZStrategy实现

```python
class DDPSZStrategy(IStrategy):
    """
    DDPS-Z策略实现

    复用现有逻辑：
    - BuySignalCalculator（迭代011）
    - OrderTracker的EMA25卖出逻辑（迭代012）
    """

    def __init__(self):
        self.buy_amount_usdt = Decimal("100")  # 固定100U

    def get_strategy_name(self) -> str:
        return "DDPS-Z"

    def get_strategy_version(self) -> str:
        return "1.0"

    def generate_buy_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series]
    ) -> List[Dict]:
        """
        复用BuySignalCalculator逻辑

        条件：
        - 策略1: EMA斜率未来预测
        - 策略2: K线突破EMA
        - 策略3: 惯性扇形扩张
        """
        # 调用现有BuySignalCalculator
        from ddps_z.calculators import BuySignalCalculator

        calculator = BuySignalCalculator()
        signals = calculator.calculate(klines, indicators)

        return signals

    def generate_sell_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series],
        open_orders: List[Order]
    ) -> List[Dict]:
        """
        EMA25回归卖出逻辑

        条件：K线 [low, high] 包含 EMA25
        """
        sell_signals = []
        ema25 = indicators['ema25']

        for order in open_orders:
            # 找到订单买入后的K线
            buy_idx = self._find_kline_index(klines, order.open_timestamp)

            for i in range(buy_idx + 1, len(klines)):
                kline = klines.iloc[i]
                ema_value = ema25.iloc[i]

                if pd.isna(ema_value):
                    continue

                if kline['low'] <= ema_value <= kline['high']:
                    sell_signals.append({
                        'timestamp': int(kline.name.timestamp() * 1000),
                        'price': Decimal(str(ema_value)),
                        'order_id': order.id,
                        'reason': 'EMA25回归',
                        'strategy_id': 'ema25_reversion'
                    })
                    break

        return sell_signals

    def calculate_position_size(
        self,
        signal: Dict,
        available_capital: Decimal,
        current_price: Decimal
    ) -> Decimal:
        """固定100 USDT"""
        return self.buy_amount_usdt

    def should_stop_loss(
        self,
        order: Order,
        current_price: Decimal,
        current_timestamp: int
    ) -> bool:
        """MVP阶段不启用止损"""
        return False

    def should_take_profit(
        self,
        order: Order,
        current_price: Decimal,
        current_timestamp: int
    ) -> bool:
        """MVP阶段不启用止盈"""
        return False
```

#### 2.4.2 DDPS-Z回测示例

```python
# 使用示例
from strategy_adapter.core import StrategyAdapter, UnifiedOrderManager
from strategy_adapter.adapters import DDPSZStrategy
from backtest.services import BacktestEngine

# 1. 创建策略实例
strategy = DDPSZStrategy()

# 2. 创建订单管理器
order_manager = UnifiedOrderManager()

# 3. 创建适配器
adapter = StrategyAdapter(strategy, order_manager)

# 4. 准备数据
klines = ...  # 从数据库加载
indicators = {
    'ema25': calculate_ema(klines, 25),
    # ... 其他指标
}

# 5. 适配策略
adapted_result = adapter.adapt_for_backtest(klines, indicators)

# 6. 运行vectorbt回测
engine = BacktestEngine(
    symbol="ETHUSDT",
    interval="4h",
    initial_cash=10000
)

backtest_result = engine.run_backtest(
    entries=adapted_result['entries'],
    exits=adapted_result['exits'],
    strategy_name="DDPS-Z",
    strategy_params={'version': '1.0'}
)

# 7. 输出结果
print(f"总收益率: {backtest_result.total_return:.2%}")
print(f"夏普比率: {backtest_result.sharpe_ratio:.2f}")
print(f"最大回撤: {backtest_result.max_drawdown:.2%}")
print(f"胜率: {backtest_result.win_rate:.2f}%")
```

---

## 第三部分：MVP功能点清单

### 3.1 P0功能（必须实现）

#### 📦 模块结构

- **[P0] 创建strategy_adapter模块**
  - 目录结构：`strategy_adapter/`
  - 子模块：interfaces/, core/, models/, adapters/

#### 🔌 接口定义

- **[P0] IStrategy接口**
  - 定义8个核心方法
  - 包含完整的类型提示
  - 提供详细的docstring

#### 📊 数据模型

- **[P0] Order数据类**
  - 支持现货和合约
  - 包含完整的开平仓信息
  - 自动计算盈亏

- **[P0] OrderStatus/OrderSide枚举**
  - 订单状态：pending/filled/closed/cancelled
  - 订单方向：buy/sell

#### ⚙️ 核心组件

- **[P0] UnifiedOrderManager**
  - 订单创建：create_order()
  - 订单更新：update_order()
  - 订单查询：get_open_orders()
  - 统计计算：calculate_statistics()

- **[P0] StrategyAdapter**
  - 策略适配：adapt_for_backtest()
  - 调用UnifiedOrderManager
  - 集成SignalConverter

- **[P0] SignalConverter**
  - 信号转换：to_vectorbt_signals()
  - 时间对齐处理
  - 信号验证

#### 🎯 DDPS-Z适配

- **[P0] DDPSZStrategy实现**
  - 实现IStrategy接口
  - 复用BuySignalCalculator
  - 复用EMA25卖出逻辑

- **[P0] DDPS-Z回测验证**
  - 使用StrategyAdapter适配
  - 运行vectorbt回测
  - 验证结果与OrderTracker一致性

#### 📝 文档与测试

- **[P0] 单元测试**
  - UnifiedOrderManager测试
  - SignalConverter测试
  - DDPSZStrategy测试

- **[P0] 集成测试**
  - 端到端回测流程
  - 结果准确性验证

---

### 3.2 P1功能（可推迟）

#### 🔄 策略库

- **[P1] 内置策略**
  - SimpleMAStrategy（双均线策略）
  - RSIStrategy（RSI超买超卖）
  - 提供参考实现

#### 📈 高级功能

- **[P1] 策略组合**
  - StrategyComposer
  - 支持多策略并行
  - 资金分配管理

- **[P1] 动态仓位管理**
  - 基于信号强度调整仓位
  - 风险控制

#### 🗄️ 持久化

- **[P1] 订单持久化**
  - 保存到数据库
  - 支持历史查询

---

## 第四部分：技术实现

### 4.1 模块结构

```
strategy_adapter/
├── __init__.py
├── interfaces/
│   ├── __init__.py
│   └── strategy.py              # IStrategy接口定义
├── core/
│   ├── __init__.py
│   ├── unified_order_manager.py # 统一订单管理器
│   ├── strategy_adapter.py      # 策略适配器
│   └── signal_converter.py      # 信号转换器
├── models/
│   ├── __init__.py
│   ├── order.py                 # Order数据类
│   ├── trade_record.py          # 交易记录
│   └── enums.py                 # 枚举类型
├── adapters/
│   ├── __init__.py
│   └── ddpsz_adapter.py         # DDPS-Z适配器
└── tests/
    ├── test_order_manager.py
    ├── test_signal_converter.py
    └── test_ddpsz_strategy.py
```

### 4.2 关键决策点

#### ✅ 决策1：订单管理统一方式

**采用方案**：创建新的UnifiedOrderManager，逐步迁移

- 优点：
  - 不破坏现有代码
  - 应用层和回测层可逐步接入
  - 支持平滑过渡

- 替代方案（未采用）：
  - 直接修改PositionManager：风险高，影响现有回测
  - 扩展OrderTracker：无法与vectorbt集成

#### ✅ 决策2：接口设计粒度

**采用方案**：IStrategy定义8个核心方法

- 优点：
  - 覆盖完整生命周期（买入、卖出、止盈止损）
  - 足够灵活，支持各种策略
  - 接口清晰，易于实现

- 替代方案（未采用）：
  - 简化为2个方法（generate_signals）：灵活性不足
  - 扩展为15+方法：过于复杂，实现成本高

#### ✅ 决策3：DDPS-Z适配方式

**采用方案**：包装现有逻辑，不修改原代码

- 优点：
  - 保持迭代011/012的独立性
  - DDPSZStrategy作为薄适配层
  - 原有功能不受影响

- 替代方案（未采用）：
  - 重构DDPS-Z：工作量大，风险高
  - 完全重写：丢失现有验证结果

---

## 第五部分：验收标准

### 5.1 功能验收

| 功能点 | 验收标准 |
|--------|----------|
| IStrategy接口 | 8个方法定义完整，包含类型提示和docstring |
| UnifiedOrderManager | 创建、更新、查询订单功能正常，统计计算准确 |
| SignalConverter | 正确转换为vectorbt信号，时间对齐无误 |
| DDPSZStrategy | 实现所有接口方法，复用现有逻辑 |
| 回测集成 | DDPS-Z通过适配层运行vectorbt回测成功 |
| 结果一致性 | 适配层回测结果与OrderTracker结果一致（±5%容差） |

### 5.2 性能指标

| 指标 | 目标值 |
|------|--------|
| 信号转换延迟 | < 50ms（1000条信号） |
| 订单管理延迟 | < 10ms（100个订单查询） |
| 回测执行时间 | < 5s（180天数据） |

### 5.3 代码质量

| 指标 | 目标值 |
|------|--------|
| 单元测试覆盖率 | > 80% |
| 类型提示覆盖率 | 100%（核心模块） |
| Docstring覆盖率 | 100%（公开API） |

---

## 第六部分：风险与缓解

### 6.1 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 信号转换精度损失 | 回测结果不准确 | 1. 充分测试时间对齐逻辑；2. 对比OrderTracker结果 |
| 现有代码兼容性 | 破坏DDPS-Z功能 | 1. 不修改原代码；2. 仅包装复用；3. 充分回归测试 |
| vectorbt版本兼容 | 升级后API变化 | 1. 锁定版本；2. 适配器隔离变化 |

### 6.2 业务风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 接口过于复杂 | 新策略接入成本高 | 1. 提供DDPSZStrategy作为参考实现；2. 详细文档 |
| 订单管理逻辑重复 | 后续维护成本高 | 1. 逐步迁移到UnifiedOrderManager；2. 弃用旧实现 |

---

## 第七部分：排期建议

**总计工作量**: 约3天

| 阶段 | 任务 | 工作量 |
|------|------|--------|
| 接口与模型定义 | IStrategy接口 + Order数据类 | 0.5天 |
| 核心组件开发 | UnifiedOrderManager + StrategyAdapter + SignalConverter | 1天 |
| DDPS-Z适配 | DDPSZStrategy实现 + 回测集成 | 0.5天 |
| 测试验证 | 单元测试 + 集成测试 + 结果验证 | 1天 |

---

## 附录

### A. 术语表

| 术语 | 说明 |
|------|------|
| 适配层 | 连接应用层策略和回测层的中间层 |
| IStrategy | 策略接口，定义标准化的策略行为 |
| UnifiedOrderManager | 统一订单管理器，整合OrderTracker和PositionManager |
| StrategyAdapter | 策略适配器，将IStrategy转换为vectorbt可用格式 |
| SignalConverter | 信号转换器，转换应用层信号为vectorbt信号 |
| entries/exits | vectorbt术语，表示买入和卖出信号（pd.Series） |

### B. 参考资料

- vectorbt文档：https://vectorbt.dev/
- 迭代011 PRD：`docs/iterations/011-buy-signal-markers/prd.md`
- 迭代012 PRD：`docs/iterations/012-buy-sell-order-tracking/prd.md`
- OrderTracker实现：`ddps_z/calculators/order_tracker.py`
- BacktestEngine实现：`backtest/services/backtest_engine.py`

---

**文档状态**: ✅ MVP需求定稿完成
**Gate 1检查**: ✅ 已通过
**下一阶段**: 技术调研与架构设计（P3-P4）
