# 开发任务计划 (Development Tasks)

**迭代编号**: 013
**迭代名称**: 策略适配层 (Strategy Adapter Layer)
**分支**: 013-strategy-adapter-layer
**创建日期**: 2026-01-06
**生命周期阶段**: P5 - 开发规划

---

## 任务统计

| 优先级 | 任务数 | 预估总工时 |
|-------|-------|-----------|
| P0 (核心功能) | 13个 | 19小时 |
| P1 (重要功能) | 5个 | 14小时 |
| P2 (优化功能) | 2个 | 4小时 |
| **总计** | **20个** | **37小时 (约5天)** |

---

## P0 核心功能 (Must Have)

### 阶段1：模块基础设施 (4小时)

#### TASK-013-001: 创建strategy_adapter模块结构
- **关联需求**: FP-013-001 (prd.md)
- **关联架构**: architecture.md#4.1 模块结构
- **任务描述**:
  - 创建顶层模块 `strategy_adapter/`
  - 创建子模块目录：`interfaces/`, `core/`, `models/`, `adapters/`, `tests/`
  - 创建所有 `__init__.py` 文件
  - 配置模块导入路径

- **验收标准**:
  - [ ] 目录结构符合PRD 4.1设计
  - [ ] 所有子模块包含 `__init__.py`
  - [ ] 模块可正常导入：`from strategy_adapter import interfaces`
  - [ ] 遵循现有项目的目录组织方式

- **边界检查**:
  - 输入边界: 无（模块创建）
  - 资源状态: 文件系统权限检查

- **预估工时**: 0.5小时
- **依赖关系**: 无
- **测试策略**: 手动导入测试
- **文档要求**:
  - **接口契约注释**: `__init__.py` 模块级文档
  - **逻辑上下文注释**: 无（简单模块创建）
- **状态**: 待开始

---

#### TASK-013-002: 定义OrderStatus和OrderSide枚举
- **关联需求**: FP-013-004 (prd.md)
- **关联架构**: architecture.md#2.2 数据模型模块
- **任务描述**:
  - 创建 `strategy_adapter/models/enums.py`
  - 定义 `OrderStatus` 枚举：`PENDING`, `FILLED`, `CLOSED`, `CANCELLED`
  - 定义 `OrderSide` 枚举：`BUY`, `SELL`
  - 使用Python `Enum` 类

- **验收标准**:
  - [ ] OrderStatus包含4个状态：`pending`, `filled`, `closed`, `cancelled`
  - [ ] OrderSide包含2个方向：`buy`, `sell`
  - [ ] 使用Python标准 `Enum` 类
  - [ ] 包含完整的docstring（符合PEP 257标准）
  - [ ] **异常路径验证**: 无效枚举值访问时抛出 AttributeError
  - [ ] **文档化标准合规**: 枚举类注释符合项目文档规范

- **边界检查**:
  - 输入边界: 枚举值固定，无动态输入
  - 资源状态: 无

- **预估工时**: 0.5小时
- **依赖关系**: TASK-013-001
- **测试策略**: 单元测试（枚举值访问、字符串转换）
  - **异常测试**: 测试无效枚举值访问

- **文档要求**:
  - **接口契约注释**: 枚举类docstring，说明每个值的含义
  - **逻辑上下文注释**: 无（简单枚举定义）

- **状态**: 待开始

---

#### TASK-013-003: 实现Order数据类
- **关联需求**: FP-013-003 (prd.md)
- **关联架构**: architecture.md#4.2 数据模型模块
- **任务描述**:
  - 创建 `strategy_adapter/models/order.py`
  - 使用 `@dataclass` 装饰器定义 `Order` 类
  - 包含完整的开平仓信息（参考 prd.md#2.2.2）
  - 实现 `calculate_pnl()` 方法（自动计算盈亏）
  - 实现 `to_dict()` 方法（用于API响应）
  - 支持现货和合约（通过 `metadata` 扩展）

- **验收标准**:
  - [ ] 使用 `@dataclass` 装饰器
  - [ ] 包含所有必要字段（19个核心字段）
  - [ ] `calculate_pnl()` 正确计算做多和做空盈亏
  - [ ] 支持手续费扣除
  - [ ] `to_dict()` 返回完整的字典表示
  - [ ] metadata字段支持策略特定数据
  - [ ] 包含完整的docstring（类级别和方法级别）
  - [ ] **异常路径验证**: close_price为None时调用calculate_pnl()不报错
  - [ ] **文档化标准合规**: Order类注释符合项目文档规范

- **边界检查**:
  - 输入边界: Decimal类型的价格和数量不能为负
  - 资源状态: 无

- **预估工时**: 1小时
- **依赖关系**: TASK-013-002
- **测试策略**: 单元测试（盈亏计算、边界条件）
  - **异常测试**:
    - 测试close_price为None时calculate_pnl()的行为
    - 测试position_value为0时的除零处理

- **文档要求**:
  - **接口契约注释**: Order类docstring，包含Attributes、Example
  - **逻辑上下文注释**: calculate_pnl()方法的盈亏计算逻辑

- **状态**: 待开始

---

#### TASK-013-004: 定义IStrategy接口
- **关联需求**: FP-013-002 (prd.md)
- **关联架构**: architecture.md#2.1 接口定义模块
- **任务描述**:
  - 创建 `strategy_adapter/interfaces/strategy.py`
  - 使用 `ABC` 和 `@abstractmethod` 定义 `IStrategy` 接口
  - 定义8个核心方法（参考 prd.md#2.2.1）
  - 包含完整的类型提示（typing）
  - 提供详细的docstring（Args, Returns, Raises）

- **验收标准**:
  - [ ] 使用 `ABC` 抽象基类
  - [ ] 8个方法全部使用 `@abstractmethod` 装饰
  - [ ] 所有方法包含完整的类型提示
  - [ ] 每个方法包含详细的docstring（包含Args、Returns、Example）
  - [ ] `get_required_indicators()` 为可选方法（有默认实现）
  - [ ] 包含"无状态设计"原则说明
  - [ ] **异常路径验证**: 未实现抽象方法时实例化抛出 TypeError
  - [ ] **文档化标准合规**: IStrategy接口注释符合项目文档规范

- **边界检查**:
  - 输入边界: 接口定义，无运行时输入
  - 资源状态: 无

- **预估工时**: 1小时
- **依赖关系**: TASK-013-001
- **测试策略**: 单元测试（接口定义正确性、抽象方法强制实现）
  - **异常测试**: 测试未实现抽象方法时的TypeError

- **文档要求**:
  - **接口契约注释**: IStrategy类docstring，重要原则说明（无状态设计）
  - **逻辑上下文注释**: 每个方法的业务价值和使用场景

- **状态**: 待开始

---

### 阶段2：核心组件实现 (8小时)

#### TASK-013-005: 实现UnifiedOrderManager
- **关联需求**: FP-013-005 (prd.md)
- **关联架构**: architecture.md#4.3 核心组件模块
- **任务描述**:
  - 创建 `strategy_adapter/core/unified_order_manager.py`
  - 实现 `UnifiedOrderManager` 类
  - 核心方法：
    - `create_order()`: 从信号创建订单
    - `update_order()`: 更新订单（平仓）
    - `get_open_orders()`: 获取持仓订单
    - `get_closed_orders()`: 获取已平仓订单
    - `calculate_statistics()`: 计算统计指标
  - 参考 `ddps_z/calculators/order_tracker.py` 的实现逻辑
  - 使用 `Decimal` 精度计算

- **验收标准**:
  - [ ] `create_order()` 正确创建订单并分配唯一ID
  - [ ] `update_order()` 正确更新订单状态和盈亏
  - [ ] `get_open_orders()` 正确筛选持仓订单
  - [ ] `calculate_statistics()` 正确计算胜率、总盈亏、平均收益率
  - [ ] 支持按策略名称筛选订单
  - [ ] 使用 `Decimal` 类型进行金融计算
  - [ ] 包含完整的docstring（类级别和方法级别）
  - [ ] **异常路径验证**:
    - 测试update_order()时order_id不存在的KeyError
    - 测试create_order()时signal缺少必要字段的KeyError
  - [ ] **文档化标准合规**: UnifiedOrderManager类注释符合项目文档规范

- **边界检查**:
  - 输入边界:
    - signal必须包含timestamp和price字段
    - current_price必须 > 0
    - available_capital必须 >= 0
  - 资源状态: 内存订单字典大小（MVP无限制）

- **预估工时**: 3小时
- **依赖关系**: TASK-013-003, TASK-013-004
- **测试策略**: 单元测试（订单创建、更新、查询、统计计算）
  - **异常测试**:
    - 测试无效signal触发KeyError
    - 测试无效order_id触发KeyError
    - 测试无效价格触发ValueError

- **文档要求**:
  - **接口契约注释**: UnifiedOrderManager类和所有公共方法
  - **逻辑上下文注释**:
    - calculate_statistics()的统计算法说明
    - create_order()的订单ID生成规则

- **状态**: ✅ 已完成 (2026-01-06)

**实际成果**：
- 创建 `strategy_adapter/core/unified_order_manager.py` (384行)
- 实现所有订单管理方法（创建、更新、查询、统计）
- 通过全部7项单元测试，覆盖正常流程和异常路径
- 符合Fail-Fast钢铁纪律和文档化标准

---

#### TASK-013-006: 实现SignalConverter
- **关联需求**: FP-013-006 (prd.md)
- **关联架构**: architecture.md#4.3 核心组件模块 + 决策点二
- **任务描述**:
  - 创建 `strategy_adapter/core/signal_converter.py`
  - 实现 `SignalConverter` 类（静态方法）
  - 核心方法：
    - `to_vectorbt_signals()`: 转换为vectorbt格式
  - **关键**：采用精确匹配策略（Exact Match）
  - 处理时间对齐：毫秒时间戳 → pd.Timestamp
  - 验证信号有效性（时间戳在K线范围内）
  - 返回 `(entries: pd.Series, exits: pd.Series)`

- **验收标准**:
  - [ ] `to_vectorbt_signals()` 正确转换信号格式
  - [ ] 精确匹配：信号时间戳必须在K线index中存在
  - [ ] 时间戳不存在时抛出 `ValueError`（含详细错误信息）
  - [ ] 返回的 `entries` 和 `exits` 为 `pd.Series`，index与klines一致
  - [ ] 支持空信号列表（返回全False的Series）
  - [ ] 包含完整的docstring（参考 architecture.md中的示例）
  - [ ] **异常路径验证**:
    - 测试信号时间戳不存在时抛出ValueError
    - 测试klines.index不是DatetimeIndex时抛出TypeError
  - [ ] **文档化标准合规**: SignalConverter类注释符合项目文档规范

- **边界检查**:
  - 输入边界:
    - klines.index 必须为 pd.DatetimeIndex
    - 信号时间戳必须在klines时间范围内
  - 资源状态: 无

- **预估工时**: 2小时
- **依赖关系**: TASK-013-001
- **测试策略**: 单元测试（精确匹配、时间对齐、边界条件）
  - **异常测试**:
    - 测试无效时间戳触发ValueError
    - 测试无效index类型触发TypeError
    - 测试空信号列表的边界情况

- **文档要求**:
  - **接口契约注释**: SignalConverter类和to_vectorbt_signals()方法
  - **逻辑上下文注释**:
    - 精确匹配策略的原因和优势（参考architecture.md决策点二）
    - 时间戳转换的关键步骤

- **状态**: ✅ 已完成 (2026-01-06)

**实际成果**：
- 创建 `strategy_adapter/core/signal_converter.py` (156行)
- 实现精确匹配时间对齐策略（Exact Match）
- 通过全部异常处理测试（ValueError, TypeError）
- 符合Fail-Fast钢铁纪律，提供详细错误信息

---

#### TASK-013-007: 实现StrategyAdapter
- **关联需求**: FP-013-007 (prd.md)
- **关联架构**: architecture.md#4.3 核心组件模块
- **任务描述**:
  - 创建 `strategy_adapter/core/strategy_adapter.py`
  - 实现 `StrategyAdapter` 类
  - 核心方法：
    - `adapt_for_backtest()`: 适配策略用于回测
  - 编排协调：
    - 调用策略的 `generate_buy_signals()` 和 `generate_sell_signals()`
    - 使用 `UnifiedOrderManager` 管理订单
    - 使用 `SignalConverter` 转换信号
  - 返回：`{'entries': pd.Series, 'exits': pd.Series, 'orders': List[Order], 'statistics': Dict}`

- **验收标准**:
  - [ ] `adapt_for_backtest()` 正确编排整个适配流程
  - [ ] 正确调用策略的信号生成方法
  - [ ] 正确使用UnifiedOrderManager创建和管理订单
  - [ ] 正确使用SignalConverter转换信号格式
  - [ ] 返回完整的回测数据结构
  - [ ] 支持初始资金参数（默认10000 USDT）
  - [ ] 包含日志记录（开始、信号数量、完成）
  - [ ] 包含完整的docstring
  - [ ] **异常路径验证**:
    - 测试策略未实现IStrategy接口时的错误
    - 测试信号转换失败时的传播
  - [ ] **文档化标准合规**: StrategyAdapter类注释符合项目文档规范

- **边界检查**:
  - 输入边界:
    - strategy必须实现IStrategy接口
    - klines必须为非空DataFrame
    - initial_cash必须 > 0
  - 资源状态: 无

- **预估工时**: 2小时
- **依赖关系**: TASK-013-004, TASK-013-005, TASK-013-006
- **测试策略**: 单元测试（编排流程、返回数据结构）
  - **异常测试**:
    - 测试无效策略实例触发TypeError
    - 测试空klines触发ValueError

- **文档要求**:
  - **接口契约注释**: StrategyAdapter类和adapt_for_backtest()方法
  - **逻辑上下文注释**:
    - 适配流程的7个步骤说明（参考architecture.md）
    - 状态管理职责分配

- **状态**: ✅ 已完成 (2026-01-06)

**实际成果**：
- 创建 `strategy_adapter/core/strategy_adapter.py` (218行)
- 实现完整的8步适配流程（生成信号→创建订单→平仓→转换→统计）
- 通过全部6项测试（类型验证、边界检查、完整流程）
- 符合Fail-Fast钢铁纪律和文档化标准

---

### 阶段3：DDPS-Z适配 (4小时)

#### TASK-013-008: 实现DDPSZStrategy
- **关联需求**: FP-013-008 (prd.md)
- **关联架构**: architecture.md#4.4 应用适配模块
- **任务描述**:
  - 创建 `strategy_adapter/adapters/ddpsz_adapter.py`
  - 实现 `DDPSZStrategy` 类（实现IStrategy接口）
  - `generate_buy_signals()`: 直接调用 `BuySignalCalculator.calculate()`
  - `generate_sell_signals()`: 实现EMA25回归卖出逻辑
  - `calculate_position_size()`: 返回固定100 USDT
  - `should_stop_loss()` 和 `should_take_profit()`: MVP阶段返回False
  - 信号格式转换：`BuySignalCalculator返回` → `IStrategy要求`

- **验收标准**:
  - [ ] 实现IStrategy接口的所有8个方法
  - [ ] `generate_buy_signals()` 正确调用BuySignalCalculator
  - [ ] 信号格式正确转换（提取timestamp、price、reason、strategy_id）
  - [ ] `generate_sell_signals()` 正确实现EMA25回归逻辑
  - [ ] EMA25卖出条件：`low <= ema25 <= high`
  - [ ] `calculate_position_size()` 返回固定100 USDT
  - [ ] `get_required_indicators()` 返回 `['ema25']`
  - [ ] 包含完整的docstring
  - [ ] **异常路径验证**:
    - 测试indicators缺少ema25时的KeyError
    - 测试open_orders为空时generate_sell_signals()正常返回空列表
  - [ ] **文档化标准合规**: DDPSZStrategy类注释符合项目文档规范

- **边界检查**:
  - 输入边界:
    - indicators必须包含'ema25'
    - klines必须为非空DataFrame
    - open_orders可为空列表
  - 资源状态: 无

- **预估工时**: 2小时
- **依赖关系**: TASK-013-004
- **测试策略**: 单元测试（信号生成、格式转换、EMA25逻辑）
  - **异常测试**:
    - 测试缺少indicators触发KeyError
    - 测试空klines的边界情况

- **文档要求**:
  - **接口契约注释**: DDPSZStrategy类和所有实现的方法
  - **逻辑上下文注释**:
    - EMA25回归卖出条件的业务逻辑说明
    - BuySignalCalculator复用策略

- **状态**: ✅ 已完成 (2026-01-06)

**实际成果**：
- 创建 `strategy_adapter/adapters/ddpsz_adapter.py` (375行)
- 实现IStrategy接口的全部8个方法
- 复用BuySignalCalculator生成买入信号，信号格式正确转换
- 实现EMA25回归卖出逻辑（K线[low, high]包含EMA25）
- 通过全部9项单元测试，覆盖正常流程和异常路径
- 符合Fail-Fast钢铁纪律和文档化标准

---

#### TASK-013-009: DDPS-Z回测集成
- **关联需求**: FP-013-009 (prd.md)
- **关联架构**: architecture.md#回测层组件
- **任务描述**:
  - 创建集成测试脚本或Django management command
  - 流程：
    1. 从数据库加载ETHUSDT 4h K线数据（180天）
    2. 计算EMA25指标
    3. 创建DDPSZStrategy实例
    4. 使用StrategyAdapter适配策略
    5. 调用BacktestEngine.run_backtest()
    6. 输出回测结果
  - 验证结果与OrderTracker的一致性（±5%容差）

- **验收标准**:
  - [ ] 成功加载K线数据和指标
  - [ ] 成功创建DDPSZStrategy和StrategyAdapter实例
  - [ ] 成功调用BacktestEngine.run_backtest()
  - [ ] 返回完整的BacktestResult对象
  - [ ] 结果包含夏普比率、最大回撤等vectorbt指标
  - [ ] 与OrderTracker结果对比，订单数量差异 < 5%
  - [ ] 与OrderTracker结果对比，总盈亏差异 < 5%
  - [ ] 与OrderTracker结果对比，胜率差异 < 5%
  - [ ] 包含完整的docstring（集成测试说明）
  - [ ] **异常路径验证**:
    - 测试K线数据不足时的错误处理
    - 测试回测失败时的异常传播
  - [ ] **文档化标准合规**: 集成测试代码注释符合项目文档规范

- **边界检查**:
  - 输入边界:
    - K线数据至少180天
    - EMA25指标计算需要至少25个数据点
  - 资源状态: 数据库连接可用

- **预估工时**: 1小时
- **依赖关系**: TASK-013-007, TASK-013-008
- **测试策略**: 端到端集成测试
  - **异常测试**:
    - 测试数据库无数据时的错误处理
    - 测试回测引擎故障时的传播

- **文档要求**:
  - **接口契约注释**: 集成测试脚本的主函数
  - **逻辑上下文注释**:
    - 完整的测试流程说明（6个步骤）
    - 验收标准和容差说明

- **状态**: ✅ 已完成 (2026-01-06)

**实际成果**：
- 创建 `test_ddpsz_integration.py` (283行)
- 端到端集成测试成功（K线准备→策略创建→适配执行→结果验证）
- 成功生成39个买入信号，4个卖出信号
- 回测结果完整（胜率41.03%，总盈亏-59.64 USDT）
- 异常路径测试通过（空K线、缺少指标）
- 符合Fail-Fast钢铁纪律和文档化标准

---

### 阶段4：测试验证 (7小时)

#### TASK-013-010: UnifiedOrderManager单元测试
- **关联需求**: FP-013-010 (prd.md)
- **关联架构**: 测试策略
- **任务描述**:
  - 创建 `strategy_adapter/tests/test_unified_order_manager.py`
  - 测试用例：
    - `test_create_order()`: 测试订单创建
    - `test_update_order()`: 测试订单更新（平仓）
    - `test_get_open_orders()`: 测试持仓订单查询
    - `test_get_closed_orders()`: 测试已平仓订单查询
    - `test_calculate_statistics()`: 测试统计计算
    - `test_pnl_calculation_accuracy()`: 测试盈亏计算准确性
    - `test_invalid_order_id()`: 测试无效订单ID处理
  - 覆盖率目标：> 80%

- **验收标准**:
  - [ ] 所有测试用例通过
  - [ ] 测试覆盖UnifiedOrderManager的所有公共方法
  - [ ] 测试盈亏计算的准确性（多个场景）
  - [ ] 测试边界条件（空订单列表、单个订单、多个订单）
  - [ ] 测试异常处理（无效order_id）
  - [ ] 单元测试覆盖率 > 80%
  - [ ] 所有测试包含清晰的docstring
  - [ ] **异常路径验证**:
    - 测试update_order()时order_id不存在触发KeyError
    - 测试create_order()时signal缺少字段触发KeyError
  - [ ] **文档化标准合规**: 测试用例注释符合项目文档规范

- **边界检查**:
  - 输入边界: 测试各种边界情况（0订单、1订单、N订单）
  - 资源状态: 无

- **预估工时**: 2小时
- **依赖关系**: TASK-013-005
- **测试策略**: pytest框架
  - **异常测试**:
    - test_invalid_order_id_raises_key_error()
    - test_invalid_signal_raises_key_error()

- **文档要求**:
  - **接口契约注释**: 每个测试用例的docstring（测试目的、步骤、验收）
  - **逻辑上下文注释**: 复杂测试场景的说明

- **状态**: 待开始

---

#### TASK-013-011: SignalConverter单元测试
- **关联需求**: FP-013-011 (prd.md)
- **关联架构**: 测试策略
- **任务描述**:
  - 创建 `strategy_adapter/tests/test_signal_converter.py`
  - 测试用例：
    - `test_to_vectorbt_signals_success()`: 测试正常转换
    - `test_exact_match_failure()`: 测试精确匹配失败（时间戳不存在）
    - `test_empty_signals()`: 测试空信号列表
    - `test_time_alignment()`: 测试时间对齐逻辑
    - `test_invalid_klines_index()`: 测试无效klines index类型
  - 覆盖率目标：> 80%

- **验收标准**:
  - [ ] 所有测试用例通过
  - [ ] 测试精确匹配成功和失败场景
  - [ ] 测试时间对齐逻辑（毫秒时间戳 → pd.Timestamp）
  - [ ] 测试空信号列表返回全False的Series
  - [ ] 测试ValueError错误信息的清晰度
  - [ ] 单元测试覆盖率 > 80%
  - [ ] 所有测试包含清晰的docstring
  - [ ] **异常路径验证**:
    - 测试时间戳不存在时抛出ValueError
    - 测试klines.index不是DatetimeIndex时抛出TypeError
  - [ ] **文档化标准合规**: 测试用例注释符合项目文档规范

- **边界检查**:
  - 输入边界: 测试各种时间戳格式、空信号、无效index
  - 资源状态: 无

- **预估工时**: 1小时
- **依赖关系**: TASK-013-006
- **测试策略**: pytest框架
  - **异常测试**:
    - test_exact_match_failure_raises_value_error()
    - test_invalid_index_raises_type_error()

- **文档要求**:
  - **接口契约注释**: 每个测试用例的docstring
  - **逻辑上下文注释**: 精确匹配策略的验证逻辑

- **状态**: 待开始

---

#### TASK-013-012: DDPSZStrategy单元测试
- **关联需求**: FP-013-012 (prd.md)
- **关联架构**: 测试策略
- **任务描述**:
  - 创建 `strategy_adapter/tests/test_ddpsz_strategy.py`
  - 测试用例：
    - `test_generate_buy_signals()`: 测试买入信号生成
    - `test_generate_sell_signals()`: 测试卖出信号生成（EMA25）
    - `test_calculate_position_size()`: 测试仓位计算（固定100U）
    - `test_signal_format_conversion()`: 测试信号格式转换
    - `test_ema25_reversion_logic()`: 测试EMA25回归逻辑
    - `test_missing_indicators()`: 测试缺少indicators处理
  - 覆盖率目标：> 80%

- **验收标准**:
  - [ ] 所有测试用例通过
  - [ ] 测试买入信号格式转换正确性
  - [ ] 测试EMA25回归卖出条件（low <= ema25 <= high）
  - [ ] 测试calculate_position_size()返回固定100 USDT
  - [ ] 测试与BuySignalCalculator的集成
  - [ ] 测试缺少indicators时的错误处理
  - [ ] 单元测试覆盖率 > 80%
  - [ ] 所有测试包含清晰的docstring
  - [ ] **异常路径验证**:
    - 测试indicators缺少'ema25'时触发KeyError
    - 测试空klines的边界情况
  - [ ] **文档化标准合规**: 测试用例注释符合项目文档规范

- **边界检查**:
  - 输入边界: 测试空指标、缺少指标、空订单列表
  - 资源状态: 无

- **预估工时**: 1小时
- **依赖关系**: TASK-013-008
- **测试策略**: pytest框架，使用mock模拟BuySignalCalculator
  - **异常测试**:
    - test_missing_indicators_raises_key_error()
    - test_empty_klines_boundary()

- **文档要求**:
  - **接口契约注释**: 每个测试用例的docstring
  - **逻辑上下文注释**: EMA25回归逻辑的验证说明

- **状态**: 待开始

---

#### TASK-013-013: 端到端集成测试
- **关联需求**: FP-013-013 (prd.md)
- **关联架构**: 集成测试策略
- **任务描述**:
  - 创建 `strategy_adapter/tests/test_integration.py`
  - 测试用例：
    - `test_ddpsz_full_backtest_flow()`: 完整回测流程
    - `test_result_accuracy_vs_ordertracker()`: 与OrderTracker结果对比
    - `test_backtest_result_structure()`: 验证回测结果结构
  - 测试场景：使用ETHUSDT 4h数据（180天）
  - 验证：订单数量、总盈亏、胜率（±5%容差）

- **验收标准**:
  - [ ] 端到端流程测试通过（策略 → 适配器 → 回测引擎）
  - [ ] 回测结果结构完整（entries, exits, orders, statistics）
  - [ ] 与OrderTracker结果对比：
    - 订单数量差异 < 5%
    - 总盈亏差异 < 5%
    - 胜率差异 < 5%
  - [ ] 测试数据准备自动化（加载K线、计算指标）
  - [ ] 所有测试包含清晰的docstring
  - [ ] **异常路径验证**:
    - 测试K线数据不足时的错误处理
    - 测试回测失败时的传播
  - [ ] **文档化标准合规**: 集成测试代码注释符合项目文档规范

- **边界检查**:
  - 输入边界: 测试数据量不足、指标缺失等情况
  - 资源状态: 数据库连接可用

- **预估工时**: 2小时
- **依赖关系**: TASK-013-009
- **测试策略**: Django TestCase，使用测试数据库
  - **异常测试**:
    - test_insufficient_data_handling()
    - test_backtest_engine_failure_propagation()

- **文档要求**:
  - **接口契约注释**: 每个集成测试用例的docstring
  - **逻辑上下文注释**: 完整的测试流程和验收标准说明

- **状态**: 待开始

---

## P1 重要功能 (Should Have)

### P1任务列表

#### TASK-013-101: 实现SimpleMAStrategy（双均线策略）
- **关联需求**: FP-013-014 (function-points.md)
- **任务描述**:
  - 创建 `strategy_adapter/adapters/simple_ma_strategy.py`
  - 实现IStrategy接口
  - 买入：快线上穿慢线（Golden Cross）
  - 卖出：快线下穿慢线（Death Cross）
  - 支持可配置参数（快慢周期）
- **预估工时**: 2小时
- **依赖关系**: TASK-013-004
- **优先级**: P1（MVP后）
- **状态**: 待开始

---

#### TASK-013-102: 实现RSIStrategy（RSI超买超卖策略）
- **关联需求**: FP-013-015 (function-points.md)
- **任务描述**:
  - 创建 `strategy_adapter/adapters/rsi_strategy.py`
  - 实现IStrategy接口
  - 买入：RSI < 30（超卖）
  - 卖出：RSI > 70（超买）
  - 支持可配置阈值
- **预估工时**: 2小时
- **依赖关系**: TASK-013-004
- **优先级**: P1（MVP后）
- **状态**: 待开始

---

#### TASK-013-103: 策略组合功能（StrategyComposer）
- **关联需求**: FP-013-016 (function-points.md)
- **任务描述**:
  - 创建 `strategy_adapter/core/strategy_composer.py`
  - 支持多策略并行运行
  - 资金分配管理
  - 汇总统计
- **预估工时**: 4小时
- **依赖关系**: TASK-013-007
- **优先级**: P1（MVP后）
- **状态**: 待开始

---

#### TASK-013-104: 动态仓位管理
- **关联需求**: FP-013-017 (function-points.md)
- **任务描述**:
  - 增强UnifiedOrderManager
  - 基于信号confidence调整买入金额
  - 风险控制（最大仓位限制）
- **预估工时**: 3小时
- **依赖关系**: TASK-013-005
- **优先级**: P1（MVP后）
- **状态**: 待开始

---

#### TASK-013-105: 订单持久化
- **关联需求**: FP-013-018 (function-points.md)
- **任务描述**:
  - 创建OrderModel（Django模型）
  - UnifiedOrderManager支持持久化
  - 支持历史查询
- **预估工时**: 3小时
- **依赖关系**: TASK-013-005
- **优先级**: P1（MVP后）
- **状态**: 待开始

---

## P2 优化功能 (Could Have)

### P2任务列表

#### TASK-013-201: 信号转换性能优化
- **关联需求**: FP-013-019 (function-points.md)
- **任务描述**:
  - 优化SignalConverter.to_vectorbt_signals()
  - 批量时间戳转换
  - 目标：1000条信号 < 50ms
- **预估工时**: 2小时
- **依赖关系**: TASK-013-006
- **优先级**: P2（性能优化）
- **状态**: 待开始

---

#### TASK-013-202: 订单查询缓存
- **关联需求**: FP-013-020 (function-points.md)
- **任务描述**:
  - UnifiedOrderManager查询结果缓存
  - 使用@lru_cache装饰器
  - 订单更新时失效缓存
- **预估工时**: 2小时
- **依赖关系**: TASK-013-005
- **优先级**: P2（性能优化）
- **状态**: 待开始

---

## 技术任务

### 环境搭建
- [ ] **文档风格定义** ✅ **已完成**
  - [x] 已确定项目文档化标准（PEP 257 + Google Style）
  - [x] 注释模板已存在（`docs/comment-templates.md`）
  - [ ] 配置 `interrogate` 工具（文档覆盖率检查）
  - [ ] 配置 `mypy` 工具（类型检查）
  - [ ] CI/CD包含文档化验证步骤

- [ ] 开发环境配置
  - [ ] Python虚拟环境设置
  - [ ] 依赖安装（vectorbt, pandas, numpy）

- [ ] 代码规范配置
  - [ ] 配置 `black` 代码格式化（已有）
  - [ ] 配置 `isort` 导入排序（已有）
  - [ ] 配置 `pytest` 测试框架（已有）

### 基础设施
- [ ] 测试数据准备
  - [ ] 准备ETHUSDT 4h K线数据（180天）
  - [ ] 计算EMA25指标数据
  - [ ] 准备测试用例数据集

- [ ] CI/CD流水线
  - [ ] 单元测试自动运行
  - [ ] 代码覆盖率报告
  - [ ] 文档化覆盖率检查 ⭐ **新增**

---

## 开发里程碑

| 里程碑 | 包含任务 | 预计完成时间 | 验收标准 |
|-------|---------|------------|---------|
| **M1: 模块基础设施完成** | TASK-001 ~ TASK-004 | Day 1 上午 | 所有接口和数据类定义完成，可导入 |
| **M2: 核心组件完成** | TASK-005 ~ TASK-007 | Day 2 中午 | UnifiedOrderManager、SignalConverter、StrategyAdapter功能正常 |
| **M3: DDPS-Z适配完成** | TASK-008 ~ TASK-009 | Day 2 下午 | DDPSZStrategy实现完成，可生成信号 |
| **M4: 回测集成成功** | TASK-009 | Day 2 晚上 | DDPS-Z通过适配层运行vectorbt回测 |
| **M5: 测试全部通过** | TASK-010 ~ TASK-013 | Day 3 下午 | 单元测试覆盖率>80%，集成测试通过 |
| **M6: 结果验证通过** | TASK-013 | Day 3 晚上 | 与OrderTracker对比，差异<5% |

---

## 风险评估

### 高风险任务

#### 风险1：信号转换时间对齐
- **任务**: TASK-013-006 (SignalConverter)
- **风险**:
  - K线数据缺失导致精确匹配失败
  - 时间戳格式不一致（datetime vs int）
- **缓解措施**:
  - 充分测试精确匹配逻辑
  - 提供清晰的错误信息和修复建议
  - 使用时间戳转换辅助函数统一格式

#### 风险2：DDPS-Z结果一致性
- **任务**: TASK-013-009 (DDPS-Z回测集成)
- **风险**:
  - 适配层回测结果与OrderTracker差异超过5%
  - 信号格式转换遗漏或错误
- **缓解措施**:
  - 详细的单元测试验证信号转换
  - 逐步对比中间结果（信号数量、订单数量）
  - 使用相同的测试数据进行对比

#### 风险3：盈亏计算精度
- **任务**: TASK-013-005 (UnifiedOrderManager)
- **风险**:
  - Decimal精度处理错误
  - 手续费计算遗漏
- **缓解措施**:
  - 参考OrderTracker的已验证逻辑
  - 充分的单元测试覆盖盈亏计算
  - 使用相同的计算公式

### 技术依赖

#### 依赖1：BuySignalCalculator稳定性
- **依赖**: ddps_z.calculators.BuySignalCalculator
- **风险**: BuySignalCalculator接口或返回格式变化
- **应对**:
  - 在DDPSZStrategy中做薄包装，隔离变化
  - 单元测试验证格式转换正确性

#### 依赖2：vectorbt版本兼容性
- **依赖**: vectorbt库
- **风险**: vectorbt API变化导致BacktestEngine失败
- **应对**:
  - 锁定vectorbt版本（requirements.txt）
  - 适配层隔离vectorbt变化

#### 依赖3：数据库K线数据
- **依赖**: backtest.models.KLine
- **风险**: K线数据不完整或缺失
- **应对**:
  - 集成测试前验证数据完整性
  - 提供数据修复脚本（update_klines命令）

---

## 开发顺序建议

### 阶段1：基础设施（Day 1 上午，4小时）
1. TASK-013-001: 创建模块结构
2. TASK-013-002: 定义枚举类型
3. TASK-013-003: 实现Order数据类
4. TASK-013-004: 定义IStrategy接口

**检查点**：所有接口和数据类可导入，类型检查通过

---

### 阶段2：核心组件（Day 1 下午 + Day 2 上午，8小时）
5. TASK-013-006: 实现SignalConverter（先做，无依赖）
6. TASK-013-005: 实现UnifiedOrderManager
7. TASK-013-007: 实现StrategyAdapter

**检查点**：核心组件单元测试通过，可编排策略

---

### 阶段3：DDPS-Z适配（Day 2 下午，4小时）
8. TASK-013-008: 实现DDPSZStrategy
9. TASK-013-009: DDPS-Z回测集成

**检查点**：DDPS-Z通过适配层成功运行回测

---

### 阶段4：测试验证（Day 3，7小时）
10. TASK-013-010: UnifiedOrderManager单元测试
11. TASK-013-011: SignalConverter单元测试
12. TASK-013-012: DDPSZStrategy单元测试
13. TASK-013-013: 端到端集成测试

**检查点**：所有测试通过，覆盖率>80%，结果验证通过

---

## 验收检查清单

### 功能完整性
- [ ] 所有P0功能点已实现（13个）
- [ ] IStrategy接口定义完整（8个方法）
- [ ] UnifiedOrderManager功能正常
- [ ] DDPS-Z策略成功适配
- [ ] 回测流程端到端打通

### 代码质量
- [ ] 单元测试覆盖率 > 80%
- [ ] 所有公开API包含docstring
- [ ] 类型提示完整
- [ ] 代码通过black格式化
- [ ] 代码通过mypy类型检查
- [ ] **文档化率 ≥ 80%** ⭐ **新增硬性标准**
  - [ ] 公共接口注释覆盖率 100%
  - [ ] 复杂逻辑注释完整
  - [ ] 通过interrogate工具验证

### 性能指标
- [ ] 信号转换延迟 < 50ms（1000条信号）
- [ ] 订单管理延迟 < 10ms（100个订单查询）
- [ ] 回测执行时间 < 5s（180天数据）

### 结果准确性
- [ ] DDPS-Z适配层回测与OrderTracker结果对比：
  - [ ] 订单数量差异 < 5%
  - [ ] 总盈亏差异 < 5%
  - [ ] 胜率差异 < 5%

### 异常处理合规 ⚡ **新增**
- [ ] 代码无空catch块
- [ ] 无静默返回错误标记
- [ ] 异常携带上下文信息
- [ ] Linter强制检查异常处理

---

## Gate 5 检查清单

在进入P6阶段前，必须确保以下标准都已满足：

- [ ] **现有代码分析已完成** ⭐
  - [x] 代码库扫描已完成
  - [x] 复用能力评估已完成
  - [x] 规范识别已完成
  - [x] 现有代码分析报告已输出

- [ ] **任务分解完整性**
  - [ ] 所有P0功能都有对应的开发任务
  - [ ] 任务分解粒度合适（1-2天可完成）
  - [ ] 依赖关系清晰合理

- [ ] **验收标准可验证性**
  - [ ] 每个任务包含可量化的验收标准
  - [ ] 验收标准可通过测试验证

- [ ] **异常路径覆盖完整** ⚡
  - [ ] 每个P0任务都包含异常路径验证
  - [ ] 边界检查已明确定义
  - [ ] 失败用例已规划

- [ ] **文档化标准合规** 📝
  - [x] 项目已有文档化标准（PEP 257）
  - [x] 注释模板已存在
  - [ ] 自动化工具配置待完成

- [ ] **工作量估算合理性**
  - [ ] 总工时估算：19小时（P0）
  - [ ] 工时估算基于现有代码分析

- [ ] **技术方案可行性**
  - [ ] 技术方案已在architecture.md中确认
  - [ ] 依赖的第三方库可用（vectorbt, pandas）

---

**文档状态**: ✅ 开发任务计划已完成
**关联文档**:
- PRD: docs/iterations/013-strategy-adapter-layer/prd.md
- Architecture: docs/iterations/013-strategy-adapter-layer/architecture.md
- Function Points: docs/iterations/013-strategy-adapter-layer/function-points.md
- Comment Templates: docs/comment-templates.md
**下一阶段**: P6 - 开发实现（待Gate 5通过）
