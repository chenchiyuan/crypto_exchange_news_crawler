# 任务规划: 多策略组合回测系统

> **迭代编号**: 017
> **创建时间**: 2026-01-07
> **状态**: ✅ 已完成
> **关联架构**: [architecture.md](./architecture.md)
> **关联功能点**: [function-points.md](./function-points.md)

---

## 任务总览

| 阶段 | 任务数 | 预估复杂度 |
|------|--------|------------|
| Phase 1: 配置与卖出条件 | 8 | 中 |
| Phase 2: 多策略核心 | 6 | 高 |
| Phase 3: CLI集成 | 3 | 低 |
| Phase 4: 测试验收 | 3 | 中 |
| **总计** | **20** | |

---

## Phase 1: 配置与卖出条件模块

### TASK-017-001: 创建ProjectConfig数据类
**功能点**: FP-017-001~005
**状态**: [ ] 未开始

**目标**: 定义JSON配置的Python数据类结构

**实现步骤**:
1. 创建 `strategy_adapter/models/project_config.py`
2. 定义以下dataclass:
   - `ExitConfig`: 卖出条件配置
   - `StrategyConfig`: 单个策略配置
   - `CapitalManagementConfig`: 资金管理配置
   - `BacktestConfig`: 回测配置
   - `ProjectConfig`: 项目总配置

**验收标准**:
- [ ] 所有dataclass定义完整
- [ ] 包含类型注解
- [ ] 支持默认值

---

### TASK-017-002: 实现ProjectLoader配置加载器
**功能点**: FP-017-006
**状态**: [ ] 未开始
**依赖**: TASK-017-001

**目标**: 实现JSON配置文件的加载和解析

**实现步骤**:
1. 创建 `strategy_adapter/core/project_loader.py`
2. 实现 `ProjectLoader` 类:
   - `load(path: str) -> ProjectConfig`
   - `_parse_backtest_config(data: dict) -> BacktestConfig`
   - `_parse_strategies(data: list) -> List[StrategyConfig]`
   - `_parse_exits(data: list) -> List[ExitConfig]`

**验收标准**:
- [ ] 能正确加载示例JSON配置
- [ ] 解析错误时抛出明确异常
- [ ] 单元测试通过

---

### TASK-017-003: 创建示例配置文件
**功能点**: FP-017-001
**状态**: [ ] 未开始

**目标**: 创建可用的示例JSON配置文件

**实现步骤**:
1. 创建 `strategy_adapter/configs/example_project.json`
2. 包含2个策略配置（strategy_1和strategy_2）
3. 每个策略配置多个卖出条件

**验收标准**:
- [ ] JSON格式正确
- [ ] 可被ProjectLoader正确解析

---

### TASK-017-004: 实现IExitCondition接口
**功能点**: FP-017-007
**状态**: [ ] 未开始

**目标**: 定义卖出条件的抽象接口

**实现步骤**:
1. 创建 `strategy_adapter/exits/__init__.py`
2. 创建 `strategy_adapter/exits/base.py`
3. 定义:
   - `ExitSignal` dataclass
   - `IExitCondition` ABC

**验收标准**:
- [ ] 接口定义符合架构文档
- [ ] 包含完整类型注解

---

### TASK-017-005: 实现EmaReversionExit
**功能点**: FP-017-008
**状态**: [ ] 未开始
**依赖**: TASK-017-004

**目标**: 实现EMA回归卖出条件

**实现步骤**:
1. 创建 `strategy_adapter/exits/ema_reversion.py`
2. 实现 `EmaReversionExit` 类
3. 检查逻辑: K线low <= EMA <= K线high

**验收标准**:
- [ ] 正确检测EMA回归
- [ ] 单元测试覆盖边界情况

---

### TASK-017-006: 实现StopLossExit
**功能点**: FP-017-009
**状态**: [ ] 未开始
**依赖**: TASK-017-004

**目标**: 实现止损卖出条件

**实现步骤**:
1. 创建 `strategy_adapter/exits/stop_loss.py`
2. 实现 `StopLossExit` 类
3. 检查逻辑: K线low <= 止损价 (open_price * (1 - pct))

**验收标准**:
- [ ] 正确计算止损价格
- [ ] 以止损价成交（非收盘价）
- [ ] 单元测试通过

---

### TASK-017-007: 实现TakeProfitExit
**功能点**: FP-017-010
**状态**: [ ] 未开始
**依赖**: TASK-017-004

**目标**: 实现止盈卖出条件

**实现步骤**:
1. 创建 `strategy_adapter/exits/take_profit.py`
2. 实现 `TakeProfitExit` 类
3. 检查逻辑: K线high >= 止盈价 (open_price * (1 + pct))

**验收标准**:
- [ ] 正确计算止盈价格
- [ ] 以止盈价成交（非收盘价）
- [ ] 单元测试通过

---

### TASK-017-008: 实现ExitConditionCombiner
**功能点**: FP-017-011
**状态**: [ ] 未开始
**依赖**: TASK-017-005, TASK-017-006, TASK-017-007

**目标**: 实现卖出条件组合器

**实现步骤**:
1. 创建 `strategy_adapter/exits/combiner.py`
2. 实现 `ExitConditionCombiner` 类:
   - `add_condition(condition: IExitCondition)`
   - `check_all(order, kline, indicators, timestamp) -> Optional[ExitSignal]`
3. 实现K线内模拟逻辑（根据阳线/阴线判断触发顺序）

**验收标准**:
- [ ] 正确组合多个条件
- [ ] 返回最先触发的信号
- [ ] K线内优先级正确（止损 > 止盈 > EMA回归）

---

## Phase 2: 多策略核心模块

### TASK-017-009: 实现StrategyFactory
**功能点**: FP-017-012
**状态**: [ ] 未开始
**依赖**: TASK-017-001

**目标**: 实现策略工厂，动态创建策略实例

**实现步骤**:
1. 创建 `strategy_adapter/core/strategy_factory.py`
2. 实现 `StrategyFactory` 类:
   - `register(type: str, cls: Type[IStrategy])`
   - `create(config: StrategyConfig) -> IStrategy`
3. 预注册 `ddps-z` 类型

**验收标准**:
- [ ] 能根据配置创建DDPSZStrategy
- [ ] 未知类型抛出明确异常

---

### TASK-017-010: 实现SharedCapitalManager
**功能点**: FP-017-016, FP-017-017
**状态**: [ ] 未开始

**目标**: 实现共享资金池管理

**实现步骤**:
1. 创建 `strategy_adapter/core/shared_capital_manager.py`
2. 实现 `SharedCapitalManager` 类:
   - `__init__(initial_cash, max_positions, position_size)`
   - `can_allocate(amount) -> bool`
   - `allocate(amount)`
   - `release(amount)`
   - `get_available() -> Decimal`
   - `get_open_position_count() -> int`

**验收标准**:
- [ ] 资金扣减和回收正确
- [ ] 持仓数限制正确
- [ ] 资金不足时返回False

---

### TASK-017-011: 扩展Order模型
**功能点**: FP-017-015
**状态**: [ ] 未开始

**目标**: 为Order添加strategy_id字段

**实现步骤**:
1. 修改 `strategy_adapter/models/order.py`
2. 添加 `strategy_id: Optional[str] = None`
3. 修改 `strategy_adapter/models/db_models.py` BacktestOrder
4. 创建迁移文件

**验收标准**:
- [ ] Order支持strategy_id
- [ ] 数据库迁移成功
- [ ] 向后兼容（默认None）

---

### TASK-017-012: 实现ExitConditionFactory
**功能点**: FP-017-008~010
**状态**: [ ] 未开始
**依赖**: TASK-017-005~007

**目标**: 根据配置创建卖出条件实例

**实现步骤**:
1. 在 `strategy_adapter/exits/__init__.py` 添加工厂函数
2. 实现 `create_exit_condition(config: ExitConfig) -> IExitCondition`
3. 支持: ema_reversion, stop_loss, take_profit

**验收标准**:
- [ ] 能根据配置创建正确的条件实例
- [ ] 参数正确传递

---

### TASK-017-013: 实现MultiStrategyAdapter核心
**功能点**: FP-017-013, FP-017-014
**状态**: [ ] 未开始
**依赖**: TASK-017-008~012

**目标**: 实现多策略适配器主体

**实现步骤**:
1. 创建 `strategy_adapter/core/multi_strategy_adapter.py`
2. 实现 `MultiStrategyAdapter` 类:
   - `__init__(strategies, exit_combiners, capital_manager, order_manager)`
   - `adapt_for_backtest(klines, indicators, initial_cash, symbol) -> Dict`
3. 实现信号收集和合并排序
4. 实现卖出条件检查循环

**验收标准**:
- [ ] 多策略信号正确合并
- [ ] 按时间顺序处理
- [ ] 卖出条件正确触发

---

### TASK-017-014: 集成MultiStrategyAdapter到回测流程
**功能点**: FP-017-013~017
**状态**: [ ] 未开始
**依赖**: TASK-017-013

**目标**: 将多策略适配器集成到完整回测流程

**实现步骤**:
1. 修改 `strategy_adapter/core/__init__.py` 导出新类
2. 实现回测结果统计（整体+按策略分组）
3. 与EquityCurveBuilder和MetricsCalculator集成

**验收标准**:
- [ ] 完整回测流程可运行
- [ ] 结果统计正确
- [ ] 权益曲线正确生成

---

## Phase 3: CLI集成

### TASK-017-015: 扩展CLI添加--config参数
**功能点**: FP-017-018
**状态**: [ ] 未开始
**依赖**: TASK-017-014

**目标**: CLI支持--config参数加载配置文件

**实现步骤**:
1. 修改 `strategy_adapter/management/commands/run_strategy_backtest.py`
2. 添加 `--config` 参数
3. 实现配置文件加载逻辑
4. 保持向后兼容（无--config时使用原有参数）

**验收标准**:
- [ ] --config参数可用
- [ ] 能加载并执行多策略回测
- [ ] 无--config时行为不变

---

### TASK-017-016: CLI结果输出增强
**功能点**: FP-017-022 (P1)
**状态**: [ ] 未开始
**依赖**: TASK-017-015

**目标**: 输出按策略分组的统计信息

**实现步骤**:
1. 修改CLI输出格式
2. 添加每个策略的独立统计（胜率、盈亏）
3. 添加整体组合统计

**验收标准**:
- [ ] 输出包含策略分组统计
- [ ] 格式清晰易读

---

### TASK-017-017: 数据库保存增强
**功能点**: FP-017-024 (P1)
**状态**: [ ] 未开始
**依赖**: TASK-017-015

**目标**: 保存多策略配置到数据库

**实现步骤**:
1. 修改BacktestResult模型（如需要）
2. 保存strategy_config JSON字段
3. 保存每个订单的strategy_id

**验收标准**:
- [ ] 配置正确保存
- [ ] 订单strategy_id正确关联

---

## Phase 4: 测试与验收

### TASK-017-018: 单元测试
**状态**: [ ] 未开始
**依赖**: Phase 1, Phase 2

**目标**: 为所有新模块编写单元测试

**测试范围**:
1. `test_project_config.py` - 配置解析测试
2. `test_exit_conditions.py` - 卖出条件测试
3. `test_shared_capital_manager.py` - 资金管理测试
4. `test_strategy_factory.py` - 策略工厂测试

**验收标准**:
- [ ] 测试覆盖核心逻辑
- [ ] 所有测试通过

---

### TASK-017-019: 集成测试
**状态**: [ ] 未开始
**依赖**: Phase 3

**目标**: 端到端多策略回测测试

**测试场景**:
1. 2个策略组合回测
2. 资金不足跳过订单
3. 止损/止盈触发
4. 单策略模式兼容性

**验收标准**:
- [ ] 完整流程可运行
- [ ] 结果正确

---

### TASK-017-020: 回归测试
**状态**: [ ] 未开始
**依赖**: TASK-017-019

**目标**: 确保不破坏现有功能

**测试范围**:
1. 原有CLI参数回测
2. 数据库保存
3. Web界面展示

**验收标准**:
- [ ] 所有现有测试通过
- [ ] 无--config时行为完全不变

---

## 执行顺序

```
Phase 1 (配置+卖出条件)
    │
    ├── TASK-017-001 (ProjectConfig) ──┬── TASK-017-002 (ProjectLoader)
    │                                  └── TASK-017-003 (示例配置)
    │
    └── TASK-017-004 (IExitCondition) ──┬── TASK-017-005 (EMA回归)
                                        ├── TASK-017-006 (止损)
                                        ├── TASK-017-007 (止盈)
                                        └── TASK-017-008 (组合器)

Phase 2 (多策略核心)
    │
    ├── TASK-017-009 (StrategyFactory)
    ├── TASK-017-010 (SharedCapitalManager)
    ├── TASK-017-011 (Order扩展)
    ├── TASK-017-012 (ExitConditionFactory)
    └── TASK-017-013~014 (MultiStrategyAdapter)

Phase 3 (CLI集成)
    │
    └── TASK-017-015~017

Phase 4 (测试)
    │
    └── TASK-017-018~020
```

---

## 风险与注意事项

1. **K线内模拟复杂度**: TASK-017-008的K线内价格路径模拟需要仔细实现
2. **向后兼容**: 所有修改必须确保无--config时行为不变
3. **资金守恒**: SharedCapitalManager必须确保资金正确回收
4. **策略ID传递**: 确保从信号到订单的strategy_id正确传递
