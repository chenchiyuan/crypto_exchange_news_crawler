# PRD: 原子策略组合框架

**迭代编号**: 033
**迭代名称**: 原子策略组合框架
**文档版本**: 1.0
**创建日期**: 2025-01-12
**状态**: 需求定义
**优先级**: P0

---

## 第一部分：需求原始输入

### 1.1 原始需求

> 接下来我们做一个架构升级：
> 我觉得回测策略抽象复用不够，开发尝试新策略需要较大的开发量。
> 其实很多策略都是基于原子策略的组合：
> 举例：
> 卖出：ema25回归或 涨幅2%
>
> 这些条件应该都是一个个原子实现，实际的条件是原子条件的逻辑组合。
>
> 此外，行为上也应该抽象：比如数据获取，买入，卖出，持有策略，分析等等
>
> 我希望适配中间层是定义好框架之后的原子策略组合，而不是一堆if判断的迭代。
>
> 请结合已有实现的分析，完成此次架构层面的升级。

### 1.2 核心问题

**现状分析**：

当前回测策略系统存在以下问题：

```
┌─────────────────────────────────────────────────────────────┐
│ 问题1: 条件判断逻辑分散                                       │
├─────────────────────────────────────────────────────────────┤
│ SignalCalculator                                             │
│ ├─ _calculate_strategy1(): EMA斜率 + P5判断                 │
│ ├─ _calculate_strategy2(): Beta + 中值 + P5判断             │
│ ├─ _calculate_strategy3(): P95 + 未来EMA判断                │
│ ├─ _calculate_strategy4(): 周期 + P95 + 未来EMA             │
│ ├─ ... (策略6,7,8,10)                                        │
│ └─ 每个策略都是硬编码的 if-else 堆砌                          │
│                                                              │
│ ❌ 同一条件在多处重复实现（如EMA25回归出现3次）               │
│ ❌ 新增策略需要大量重复代码                                   │
│ ❌ 条件组合逻辑无法复用                                       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 问题2: 新策略开发成本高                                       │
├─────────────────────────────────────────────────────────────┤
│ 添加新策略需要：                                              │
│ 1. 在SignalCalculator添加 _calculate_strategyN() 方法       │
│ 2. 在DDPSZStrategy中处理新策略                               │
│ 3. 如需新Exit条件，实现IExitCondition接口                    │
│ 4. 修改配置(enabled_strategies等)                            │
│                                                              │
│ ❌ 至少修改3个文件，10+处代码                                 │
│ ❌ 策略逻辑与执行逻辑耦合                                     │
│ ❌ 无法快速验证新策略想法                                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 问题3: 缺乏原子条件抽象                                       │
├─────────────────────────────────────────────────────────────┤
│ 现有条件判断直接硬编码：                                       │
│                                                              │
│   if kline['low'] <= p5:           # P5触及                  │
│   if kline['high'] >= p95:         # P95触及                 │
│   if low <= ema <= high:           # EMA回归                 │
│   if beta < 0:                     # Beta为负                │
│   if cycle_phase == 'bear_strong': # 周期判断                │
│                                                              │
│ ❌ 无法独立测试单个条件                                       │
│ ❌ 无法组合条件（AND/OR/NOT）                                 │
│ ❌ 入场条件与出场条件使用不同模式                              │
└─────────────────────────────────────────────────────────────┘
```

**核心矛盾**：

策略逻辑 = **硬编码的 if-else 堆砌** → 期望：策略逻辑 = **原子条件的声明式组合**

### 1.3 目标用户

- 主要用户：策略开发者（产品开发者本人）
- 使用场景：
  - 快速验证新策略想法（声明式定义，无需写大量if判断）
  - 复用已有条件组合新策略
  - 统一入场/出场条件的测试和管理

### 1.4 预期效果

实现原子策略组合框架后：

1. **新策略开发效率提升80%**：只需声明条件组合，无需修改多个文件
2. **条件可复用**：相同的原子条件（如P5触及、EMA回归）只实现一次
3. **入场/出场统一**：使用同一套条件接口，减少概念负担
4. **可测试性提升**：每个原子条件可独立单元测试

---

## 第二部分：功能规格框架

### 2.1 系统架构

#### 2.1.1 目标架构设计

```
┌──────────────────────────────────────────────────────────────┐
│ 策略定义层 (Strategy Definitions)                             │
│                                                              │
│ strategy_1 = StrategyDefinition(                             │
│     name="EMA斜率未来预测做多",                                │
│     entry_condition = PriceBelowP5() & FutureEmaAboveClose(),│
│     exit_conditions = [EmaReversion(25), StopLoss(5%)]       │
│ )                                                            │
└──────────────────────────────────────────────────────────────┘
                            │
                            ↓ 声明式组合
┌──────────────────────────────────────────────────────────────┐
│ 原子条件层 (Atomic Conditions)                                │
│                                                              │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│ │PriceBelowP5 │ │PriceAboveP95│ │EmaReversion │              │
│ └─────────────┘ └─────────────┘ └─────────────┘              │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│ │BetaNegative │ │CyclePhaseIs │ │FutureEma... │              │
│ └─────────────┘ └─────────────┘ └─────────────┘              │
│                                                              │
│ 组合器: AndCondition, OrCondition, NotCondition              │
│ 运算符: condition1 & condition2, condition1 | condition2     │
└──────────────────────────────────────────────────────────────┘
                            │
                            ↓ 统一接口
┌──────────────────────────────────────────────────────────────┐
│ 执行引擎层 (Strategy Engine)                                  │
│                                                              │
│ - 入场信号生成：遍历K线，评估entry_condition                  │
│ - 出场信号生成：遍历持仓，评估exit_conditions                 │
│ - 订单管理：创建、更新、统计                                  │
└────────────────────────���─────────────────────────────────────┘
                            │
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ 现有系统 (保持兼容)                                            │
│                                                              │
│ - StrategyAdapter                                            │
│ - UnifiedOrderManager                                        │
│ - BacktestEngine (vectorbt)                                  │
└──────────────────────────────────────────────────────────────┘
```

#### 2.1.2 核心接口设计

**ICondition - 统一条件接口**

```python
class ICondition(ABC):
    """
    原子条件抽象接口

    设计原则:
    - 无状态: evaluate() 仅依赖传入的 ConditionContext
    - 可组合: 通过 &, |, ~ 运算符组合多个条件
    - 统一: 入场条件和出场条件使用同一接口
    """

    @abstractmethod
    def evaluate(self, ctx: ConditionContext) -> ConditionResult:
        """评估条件是否满足"""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """返回条件名称"""
        pass

    def __and__(self, other: 'ICondition') -> 'AndCondition':
        """AND组合: condition1 & condition2"""
        return AndCondition(self, other)

    def __or__(self, other: 'ICondition') -> 'OrCondition':
        """OR组合: condition1 | condition2"""
        return OrCondition(self, other)

    def __invert__(self) -> 'NotCondition':
        """NOT取反: ~condition"""
        return NotCondition(self)
```

**ConditionContext - 条件评估上下文**

```python
@dataclass
class ConditionContext:
    """条件评估所需的所有信息"""
    kline: Dict[str, Any]           # 当前K线 (open, high, low, close)
    indicators: Dict[str, Any]       # 技术指标 (ema25, p5, p95, beta, ...)
    timestamp: int                   # 当前时间戳
    order: Optional[Order] = None    # 持仓订单（出场时有值）
```

**ConditionResult - 条件评估结果**

```python
@dataclass
class ConditionResult:
    """条件评估结果"""
    triggered: bool                  # 是否触发
    price: Optional[Decimal] = None  # 触发价格
    reason: Optional[str] = None     # 触发原因
```

---

### 2.2 原子条件清单

#### 2.2.1 价格条件

| 条件名称 | 描述 | 现有使用位置 |
|---------|------|-------------|
| `PriceTouchesLevel(level, direction)` | 价格触及某级别 | 策略1,2,6,7,10的P5判断; 策略3,4,8的P95判断 |
| `PriceInRange(indicator)` | 价格在指标范围内 | EmaReversionExit的EMA25回归 |
| `PriceCrossUp(indicator)` | 价格上穿指标 | 止盈条件 |
| `PriceCrossDown(indicator)` | 价格下穿指标 | 止损条件 |

#### 2.2.2 指标条件

| 条件名称 | 描述 | 现有使用位置 |
|---------|------|-------------|
| `IndicatorCompare(ind1, op, ind2)` | 指标比较 | 策略2的inertia_mid < P5 |
| `BetaNegative()` | Beta斜率为负 | 策略2前置条件 |
| `FutureEmaPrediction(periods, direction)` | 未来EMA预测 | 策略1,3,4的核心条件 |

#### 2.2.3 周期条件

| 条件名称 | 描述 | 现有使用位置 |
|---------|------|-------------|
| `CyclePhaseIs(phase)` | 当前周期等于指定阶段 | 策略4,6,8的前置条件 |
| `CyclePhaseIn(phases)` | 当前周期在指定阶段列表内 | 策略4的非上涨区间判断 |

#### 2.2.4 持仓条件

| 条件名称 | 描述 | 现有使用位置 |
|---------|------|-------------|
| `ProfitPercentage(threshold)` | 盈利达到百分比 | 止盈条件 |
| `LossPercentage(threshold)` | 亏损达到百分比 | 止损条件 |
| `HoldingPeriod(min_periods)` | 持仓周期数 | 时间止损 |

#### 2.2.5 组合条件

| 条件名称 | 描述 | 用法示例 |
|---------|------|---------|
| `AndCondition(c1, c2, ...)` | 所有条件都满足 | `c1 & c2` |
| `OrCondition(c1, c2, ...)` | 任一条件满足 | `c1 \| c2` |
| `NotCondition(c)` | 条件取反 | `~c` |

---

### 2.3 策略迁移示例

#### 现有策略1 → 声明式定义

**现有实现（SignalCalculator._calculate_strategy1）**：
```python
def _calculate_strategy1(self, kline, ema, p5, beta):
    low = float(kline['low'])
    close = float(kline['close'])

    if np.isnan(ema) or np.isnan(p5) or np.isnan(beta):
        return {'triggered': False, ...}

    future_ema = ema + (beta * 6)

    condition1 = low < p5           # 价格跌破P5
    condition2 = future_ema > close  # 未来EMA高于当前收盘价

    triggered = condition1 and condition2
    ...
```

**声明式定义**：
```python
strategy_1 = StrategyDefinition(
    id='strategy_1',
    name='EMA斜率未来预测做多',
    direction='long',

    entry_condition=(
        PriceTouchesLevel('p5', 'below') &
        FutureEmaPrediction(periods=6, above_close=True)
    ),

    exit_conditions=[
        (EmaReversion('ema25'), 30),      # 优先级30
        (StopLossPercent(5.0), 10),       # 优先级10
    ]
)
```

#### 现有策略7 → 声明式定义

**现有实现**：
```python
def _calculate_strategy7(self, kline, p5):
    low = float(kline['low'])
    if low <= p5:
        return {'triggered': True, ...}
```

**声明式定义**：
```python
strategy_7 = StrategyDefinition(
    id='strategy_7',
    name='动态周期自适应做多',
    direction='long',

    entry_condition=PriceTouchesLevel('p5', 'below'),

    exit_conditions=[
        # 根据周期动态选择Exit（复用DynamicExitSelector逻辑）
        (DynamicCycleExit(), 20),
    ]
)
```

---

## 第三部分：MVP功能点清单

### 3.1 P0功能（必须实现）

#### 原子条件层

- **[P0] ICondition接口定义**
  - evaluate(ctx) → ConditionResult
  - get_name() → str
  - 运算符重载（&, |, ~）

- **[P0] ConditionContext数据类**
  - kline, indicators, timestamp, order

- **[P0] ConditionResult数据类**
  - triggered, price, reason

- **[P0] 价格条件实现**
  - PriceTouchesLevel(level, direction)
  - PriceInRange(indicator)

- **[P0] 指标条件实现**
  - BetaNegative()
  - FutureEmaPrediction(periods, direction)

- **[P0] 周期条件实现**
  - CyclePhaseIs(phase)
  - CyclePhaseIn(phases)

- **[P0] 组合条件实现**
  - AndCondition
  - OrCondition
  - NotCondition

#### 策略定义层

- **[P0] StrategyDefinition数据结构**
  - id, name, direction
  - entry_condition: ICondition
  - exit_conditions: List[(ICondition, priority)]

- **[P0] 策略注册表**
  - register_strategy(definition)
  - get_strategy(id)
  - list_strategies()

- **[P0] 现有策略迁移**
  - 策略1-2迁移（做多基础策略）
  - 策略7迁移（动态周期策略）

#### 执行引擎

- **[P0] ConditionBasedSignalCalculator**
  - 基于策略定义生成入场信号
  - 替代现有SignalCalculator的核心逻辑

- **[P0] ConditionBasedExit适配器**
  - 将ICondition适配为IExitCondition
  - 兼容现有ExitConditionCombiner

### 3.2 P1功能（可推迟）

- **[P1] 完整策略迁移**
  - 策略3,4,8（做空策略）
  - 策略6,10（其他做多策略）

- **[P1] 高级条件**
  - ProfitPercentage / LossPercentage
  - HoldingPeriod
  - IndicatorCompare（通用比较）

- **[P1] 策略配置文件**
  - YAML/JSON格式定义策略
  - 动态加载策略

- **[P1] 可视化工具**
  - 条件组合树可视化
  - 策略定义预览

---

## 第四部分：验收标准

### 4.1 功能验收

| 功能点 | 验收标准 |
|--------|----------|
| ICondition接口 | 支持 &, \|, ~ 运算符组合 |
| 原子条件 | 价格、指标、周期条件各至少2个实现 |
| 策略定义 | 可声明式定义策略1,2,7 |
| 信号生成 | 基于策略定义生成的信号与原实现一致 |
| Exit适配 | ICondition可无缝用于出场条件 |

### 4.2 性能指标

| 指标 | 目标值 |
|------|--------|
| 条件评估延迟 | < 1ms（单个条件） |
| 策略匹配延迟 | < 10ms（1000条K线） |
| 内存占用 | < 50MB（10个策略定义） |

### 4.3 代码质量

| 指标 | 目标值 |
|------|--------|
| 单元测试覆盖率 | > 80%（原子条件层） |
| 类型提示覆盖率 | 100%（公开接口） |

---

## 第五部分：风险与缓解

### 5.1 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 条件组合性能 | 大量条件组合可能影响回测速度 | 使用短路评估；必要时缓存结果 |
| 与现有系统兼容 | 破坏现有回测功能 | 渐进式迁移；保留原有实现直到验证完成 |
| 边界条件处理 | NaN/None值导致异常 | 在ConditionContext层统一处理 |

### 5.2 业务风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 抽象过度 | 简单策略变复杂 | 提供常用条件的快捷方式 |
| 学习成本 | 需要理解新框架 | 详细文档 + 迁移示例 |

---

## 第六部分：排期建议

**总计工作量**: 约5-7天

| 阶段 | 任务 | 工作量 |
|------|------|--------|
| 阶段1: 原子条件层 | ICondition接口 + 核心条件实现 | 2天 |
| 阶段2: 策略定义层 | StrategyDefinition + 注册表 | 1天 |
| 阶段3: 执行引擎 | ConditionBasedSignalCalculator | 1.5天 |
| 阶段4: 策略迁移 | 策略1,2,7迁移 + Exit适配 | 1.5天 |
| 阶段5: 测试验证 | 单元测试 + 回测结果对比 | 1天 |

---

**文档状态**: ✅ MVP需求定稿完成
**下一阶段**: 技术调研与架构设计（P3-P4）
