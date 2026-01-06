# 需求澄清记录：策略适配层

**迭代编号**: 013
**迭代名称**: 策略适配层
**文档版本**: 1.0
**创建日期**: 2026-01-06

---

## 澄清过程概述

本文档记录了从原始需求到MVP需求定稿过程中的所有关键澄清点和决策。

---

## 第一部分：需求理解与对齐

### 1.1 原始需求解析

**用户原始输入**：
> 我需要新建一个适配层：
> 1. 标准化数据结构和存储：订单管理，买入，卖出，记录
> 2. 分析系统：基于订单管理和backtest做数据回测
> 3. 方便接入应用层的策略，主要是买入，卖出，止盈，止损策略。也可以自己提供标准的策略供选择。从我的角度，我觉得可以定义策略实现的interface，应用层实现，接入此适配层直接配置调用。

**理解复述**：
用户希望创建一个中间层，解决以下问题：
1. **统一订单管理**：应用层（如DDPS-Z的OrderTracker）和回测层（PositionManager）的订单管理逻辑重复，需要统一
2. **策略标准化**：定义统一的策略接口（IStrategy），应用层策略只需实现接口即可接入回测系统
3. **回测集成**：应用层策略能够直接使用vectorbt进行专业回测分析
4. **可扩展性**：未来新策略可快速接入，无需重新实现订单管理和回测逻辑

**对齐结果**：✅ 理解正确

---

## 第二部分：关键澄清点

### 澄清点1：适配层的范围边界

**问题**：适配层应该包含哪些功能？边界在哪里？

**澄清过程**：
- **选项A**：仅做信号转换（应用层信号 → vectorbt信号）
  - 优点：实现简单，职责单一
  - 缺点：订单管理仍然重复，无法解决核心问题

- **选项B**：包含统一订单管理 + 信号转换 + 策略接口定义
  - 优点：彻底解决订单管理重复问题，提供完整解决方案
  - 缺点：实现复杂度较高

**决策**：✅ 采用选项B

**理由**：
1. 用户明确提到"标准化数据结构和存储：订单管理"
2. 仅做信号转换无法解决OrderTracker和PositionManager重复的根本问题
3. 完整的适配层能够提供更好的长期价值

---

### 澄清点2：IStrategy接口的设计粒度

**问题**：策略接口应该定义多少方法？粒度如何把握？

**澄清过程**：

**选项A：极简接口（2个方法）**
```python
class IStrategy(ABC):
    def generate_signals(self, klines, indicators) -> Dict
    def get_strategy_name(self) -> str
```
- 优点：简单易实现
- 缺点：灵活性不足，无法区分买入/卖出逻辑，无法支持止盈止损

**选项B：适中接口（8个方法）**
```python
class IStrategy(ABC):
    def get_strategy_name(self) -> str
    def get_strategy_version(self) -> str
    def generate_buy_signals(self, ...) -> List[Dict]
    def generate_sell_signals(self, ...) -> List[Dict]
    def calculate_position_size(self, ...) -> Decimal
    def should_stop_loss(self, ...) -> bool
    def should_take_profit(self, ...) -> bool
    def get_required_indicators(self) -> List[str]  # 可选
```
- 优点：覆盖完整生命周期，灵活性强
- 缺点：实现成本稍高

**选项C：详细接口（15+方法）**
- 优点：极度灵活
- 缺点：过于复杂，实现成本高，违反KISS原则

**决策**：✅ 采用选项B（8个核心方法）

**理由**：
1. 用户明确提到"买入，卖出，止盈，止损策略"，说明需要分离这些逻辑
2. 8个方法足以覆盖策略的完整生命周期
3. 符合单一职责原则，每个方法职责清晰
4. 参考成熟框架（如backtrader、freqtrade）的设计

---

### 澄清点3：订单管理的统一方式

**问题**：如何整合现有的OrderTracker和PositionManager？

**澄清过程**：

**选项A：直接修改PositionManager**
- 让应用层也使用PositionManager
- 优点：无需新建组件
- 缺点：
  - 破坏现有回测逻辑（高风险）
  - PositionManager与vectorbt深度耦合
  - 应用层（如DDPS-Z）不应依赖回测层

**选项B：扩展OrderTracker**
- 增强OrderTracker使其能与vectorbt集成
- 优点：复用现有代码
- 缺点：
  - OrderTracker设计时未考虑回测场景
  - 难以与vectorbt的Portfolio对接
  - 逻辑混乱（应用层组件承担回测职责）

**选项C：创建UnifiedOrderManager**
- 新建统一订单管理器，逐步迁移
- 优点：
  - 不破坏现有代码
  - 职责清晰（专门用于适配层）
  - 应用层和回测层可逐步接入
  - 支持平滑过渡
- 缺点：需要新建组件

**决策**：✅ 采用选项C（创建UnifiedOrderManager）

**理由**：
1. 符合开闭原则：对扩展开放，对修改关闭
2. 最小风险：不影响现有功能
3. 长期价值：提供清晰的职责分离

**过渡策略**：
- 阶段1（MVP）：创建UnifiedOrderManager，DDPS-Z先使用适配层
- 阶段2：应用层逐步迁移到UnifiedOrderManager
- 阶段3：弃用OrderTracker，统一使用UnifiedOrderManager

---

### 澄清点4：DDPS-Z的适配方式

**问题**：如何将现有DDPS-Z逻辑接入适配层？

**澄清过程**：

**选项A：重构DDPS-Z**
- 直接修改BuySignalCalculator和OrderTracker
- 优点：代码统一
- 缺点：
  - 工作量大（需要重写）
  - 风险高（可能破坏现有功能）
  - 丢失已有验证结果

**选项B：包装现有逻辑**
- 创建DDPSZStrategy适配器
- 内部调用BuySignalCalculator和OrderTracker的EMA25卖出逻辑
- 不修改原代码
- 优点：
  - 工作量小（薄包装层）
  - 零风险（原功能完全不变）
  - 保留已有验证结果
- 缺点：存在代码重复（短期内）

**决策**：✅ 采用选项B（包装现有逻辑）

**理由**：
1. 符合迭代012的增量更新原则
2. MVP阶段优先快速验证适配层可行性
3. 后续可逐步重构DDPS-Z内部实现

**实现方案**：
```python
class DDPSZStrategy(IStrategy):
    def generate_buy_signals(self, klines, indicators):
        # 直接调用现有BuySignalCalculator
        calculator = BuySignalCalculator()
        return calculator.calculate(klines, indicators)

    def generate_sell_signals(self, klines, indicators, open_orders):
        # 复用OrderTracker的EMA25卖出逻辑
        # 仅提取核心逻辑，不依赖OrderTracker类
        ...
```

---

### 澄清点5：回测结果验证标准

**问题**：如何确保适配层回测结果的准确性？

**澄清过程**：

**方案A：完全一致**
- 要求适配层结果与OrderTracker完全一致
- 优点：最严格
- 缺点：
  - 难以实现（计算方式可能有差异）
  - 过于严格（小数点精度问题）

**方案B：容差范围**
- 允许±5%容差
- 优点：
  - 合理（考虑精度和算法差异）
  - 易于验证
- 缺点：可能掩盖真正的错误

**决策**：✅ 采用方案B（±5%容差）

**验证指标**：
- 订单数量：允许±5%差异
- 总盈亏：允许±5%差异
- 胜率：允许±5%差异

**理由**：
1. OrderTracker使用纯内存计算
2. 适配层经过信号转换（时间对齐可能有细微差异）
3. vectorbt的Portfolio计算方式与OrderTracker不完全相同
4. 5%容差足以验证逻辑正确性

---

### 澄清点6：MVP范围确认

**问题**：哪些功能属于MVP，哪些可以推迟？

**MVP范围（P0）**：
- ✅ IStrategy接口定义
- ✅ Order数据类和枚举
- ✅ UnifiedOrderManager
- ✅ SignalConverter
- ✅ StrategyAdapter
- ✅ DDPSZStrategy实现
- ✅ DDPS-Z回测验证
- ✅ 单元测试和集成测试

**推迟到P1**：
- ❌ 内置策略库（SimpleMAStrategy, RSIStrategy）
  - 理由：MVP只需验证适配层可行性，一个策略（DDPS-Z）足够
- ❌ 策略组合功能
  - 理由：MVP聚焦单策略回测
- ❌ 动态仓位管理
  - 理由：固定100U足够验证
- ❌ 订单持久化
  - 理由：与OrderTracker保持一致（纯内存计算）

**决策依据**：
- MVP目标：验证适配层架构可行性
- 核心验证点：DDPS-Z能否通过适配层使用vectorbt回测
- 时间预算：3天内完成

---

## 第三部分：技术决策

### 决策1：编程语言特性选择

**使用特性**：
- ✅ `dataclass` - 简化数据类定义
- ✅ `ABC`和`abstractmethod` - 强制接口实现
- ✅ 类型提示 - 提高代码可读性
- ✅ `Decimal` - 金融计算精度

**避免使用**：
- ❌ 复杂的元编程 - 保持代码简单
- ❌ 过度抽象 - 遵循YAGNI原则

---

### 决策2：依赖管理

**新增依赖**：
- 无需新增第三方库（复用现有依赖）

**复用依赖**：
- pandas - K线数据处理
- numpy - 数值计算
- vectorbt - 回测引擎
- Decimal - 精度计算

---

### 决策3：模块命名

**模块名称**：`strategy_adapter`

**理由**：
- 清晰表达职责（适配策略）
- 符合Python命名规范（小写+下划线）
- 避免与现有模块冲突

**替代方案（未采用）**：
- `strategy_layer` - 不够具体
- `trading_adapter` - 范围太广
- `backtest_adapter` - 片面（不仅仅是回测）

---

## 第四部分：风险识别与缓解

### 风险1：信号转换精度损失

**风险描述**：
应用层信号（时间戳）转换为vectorbt信号（pd.Series index）时，可能存在时间对齐问题。

**缓解措施**：
1. SignalConverter实现严格的时间匹配逻辑
2. 验证每个信号都能找到对应的K线
3. 单元测试覆盖边界情况
4. 与OrderTracker结果对比验证

---

### 风险2：现有代码兼容性

**风险描述**：
适配层可能意外影响现有DDPS-Z功能。

**缓解措施**：
1. ✅ 不修改任何现有代码
2. ✅ DDPSZStrategy作为独立适配器
3. ✅ 迭代012的OrderTracker继续正常工作
4. ✅ 充分的回归测试

---

### 风险3：接口设计不灵活

**风险描述**：
IStrategy接口设计过于僵化，未来策略需求无法满足。

**缓解措施**：
1. ✅ Order.metadata字段支持扩展
2. ✅ IStrategy可通过继承扩展
3. ✅ MVP快速验证，及时调整
4. 预留版本号机制（get_strategy_version）

---

## 第五部分：术语对齐

| 术语 | 定义 | 示例 |
|------|------|------|
| 适配层 | 连接应用层策略和回测层的中间层 | strategy_adapter模块 |
| 应用层策略 | 具体业务策略实现 | DDPSZStrategy, VolumeTrapStrategy |
| 回测层 | 基于vectorbt的回测引擎 | BacktestEngine, Portfolio |
| 信号 | 买入或卖出的触发点 | `{'timestamp': 123, 'price': 100}` |
| 订单 | 交易执行记录 | Order对象（开仓+平仓信息） |
| 统一订单管理器 | UnifiedOrderManager | 整合OrderTracker和PositionManager |
| 策略适配器 | StrategyAdapter | 将IStrategy转换为vectorbt格式 |
| 信号转换器 | SignalConverter | 转换应用层信号为pd.Series |

---

## 第六部分：澄清时间线

| 时间点 | 澄清内容 | 决策 |
|--------|----------|------|
| T0 | 收到原始需求 | 开始需求分析 |
| T0+10分钟 | 澄清适配层范围边界 | 包含订单管理+信号转换+接口定义 |
| T0+20分钟 | 澄清IStrategy接口粒度 | 8个核心方法 |
| T0+30分钟 | 澄清订单管理统一方式 | 创建UnifiedOrderManager |
| T0+40分钟 | 澄清DDPS-Z适配方式 | 包装现有逻辑，不修改原代码 |
| T0+50分钟 | 澄清MVP范围 | 13个P0功能点 |
| T0+60分钟 | 完成PRD和功能点清单 | ✅ 需求定义完成 |

---

## 第七部分：未解决问题（预留）

当前所有核心问题已澄清，以下为未来可能需要考虑的扩展点：

### 待定1：策略参数配置化

**问题**：如何让策略参数可配置（如DDPS-Z的买入金额100U）？

**临时方案**：
- MVP阶段硬编码在策略类中
- P1阶段引入StrategyConfig数据类

---

### 待定2：多市场支持

**问题**：如何支持现货和合约的差异（如保证金、杠杆）？

**临时方案**：
- MVP阶段仅支持现货
- Order.metadata可存储市场特定信息
- P1阶段扩展Order数据类

---

## 附录：澄清问题模板

以下是用于未来澄清的问题模板：

### 问题澄清模板

**问题**：[描述问题]

**澄清过程**：
- 选项A：[方案描述]
  - 优点：[优点列表]
  - 缺点：[缺点列表]

- 选项B：[方案描述]
  - 优点：[优点列表]
  - 缺点：[缺点列表]

**决策**：✅ [采用方案]

**理由**：[决策理由]

---

**文档状态**: ✅ 需求澄清完成
**关键决策数**: 6个
**风险识别数**: 3个
**未解决问题**: 2个（可推迟到P1）
