# 开发任务计划

**迭代编号**: 014
**分支**: 014-quantitative-metrics
**创建日期**: 2026-01-06
**生命周期阶段**: P5 - 开发规划

---

## 1.3 现有代码分析报告

### 现有组件清单

| 组件名称 | 路径 | 职责 | 复用可能性 | 备注 |
|---------|------|------|-----------|------|
| **UnifiedOrderManager** | `strategy_adapter/core/unified_order_manager.py` | 订单创建、更新、查询、统计计算 | 高（直接复用） | 已有calculate_statistics()方法，可复用胜率、总盈亏等指标 |
| **Order数据类** | `strategy_adapter/models/order.py` | 订单数据结构，包含盈亏字段 | 高（直接复用） | 已有profit_loss, profit_loss_rate字段，完全满足需求 |
| **StrategyAdapter** | `strategy_adapter/core/strategy_adapter.py` | 策略回测流程编排 | 高（接口扩展） | 需扩展返回值增加'orders'字段（已在architecture.md规划） |
| **run_strategy_backtest** | `strategy_adapter/management/commands/run_strategy_backtest.py` | CLI命令行回测入口 | 高（参数扩展） | 需新增--risk-free-rate和--save-to-db参数 |
| **SignalConverter** | `strategy_adapter/core/signal_converter.py` | 信号格式转换工具类 | 中（参考模式） | 展示了独立工具类的设计模式，可参考实现EquityCurveBuilder |
| **KLine模型** | `backtest/models.py` | K线数据存储 | 高（直接复用） | 提供历史价格数据，用于权益曲线重建 |

### 编码规范总结

**代码风格**:
- **类型提示**: 完整使用typing模块（Decimal, Optional, List, Dict等）
- **Docstring格式**: Google风格，包含Args、Returns、Raises、Side Effects、Example
- **数据类**: 使用@dataclass装饰器定义数据结构（参考Order类）
- **错误处理**: Guard Clauses模式，在方法开头进行参数校验
- **日志记录**: 使用logger.info()、logger.warning()记录关键操作

**命名规范**:
- **方法命名**: `calculate_xxx()`, `get_xxx()`, `create_xxx()`, `update_xxx()`
- **变量命名**: snake_case（如`initial_cash`, `total_profit`）
- **常量命名**: UPPER_SNAKE_CASE（如`OrderStatus.FILLED`）
- **私有属性**: 单下划线前缀（如`self._orders`）

**测试模式**:
- **测试框架**: Django测试框架（unittest）
- **测试命名**: `test_xxx_yyy`格式
- **测试覆盖**: 单元测试为主，集成测试为辅

**注释规范**:
- **文件头注释**: 包含模块说明、核心功能、设计决策、迭代编号、关联任务
- **方法注释**: Google Docstring格式，必须包含Purpose、Parameters、Returns、Raises、Example
- **业务逻辑注释**: `# === 步骤N: xxx ===` 格式标注关键步骤

**精度计算**:
- **金额类型**: 所有金额使用Decimal类型（通过`Decimal(str(value))`转换）
- **百分比精度**: 保留2位小数（通过`.quantize(Decimal('0.01'))`）
- **除零保护**: 所有除法运算检查分母是否为0

### 复用建议

**可直接复用**:
- `UnifiedOrderManager.calculate_statistics()`：复用胜率、总盈亏、平均收益率计算
- `Order`数据类：直接使用profit_loss, profit_loss_rate等字段
- K线数据加载逻辑：复用`_load_klines()`方法
- CLI参数解析模式：参考`add_arguments()`方法

**可扩展复用**:
- `StrategyAdapter.adapt_for_backtest()`：返回值扩展增加'orders'字段
- `run_strategy_backtest._display_results()`：扩展报告输出，增加量化指标展示
- `run_strategy_backtest.add_arguments()`：新增--risk-free-rate、--save-to-db参数

**需全新开发**:
- `MetricsCalculator`模块（独立计算17个P0指标）
- `EquityCurveBuilder`工具类（权益曲线重建）
- `EquityPoint`数据类（权益曲线点结构）
- `BacktestResult`和`BacktestOrder`数据模型（持久化）
- Web展示视图和模板（列表页、详情页）

### 一致性建议

**风格参考**:
- 遵循`UnifiedOrderManager`的Docstring格式（包含完整的Args、Returns、Raises、Example）
- 遵循`Order`的dataclass定义模式（使用field(default_factory=dict)等）
- 遵循`StrategyAdapter`的编排模式（步骤化注释，logger记录关键节点）

**架构模式**:
- 工具类模式：参考`SignalConverter`，创建`EquityCurveBuilder`（静态方法）
- 计算类模式：参考`UnifiedOrderManager.calculate_statistics()`，创建`MetricsCalculator`（独立方法）
- 数据类模式：参考`Order`，创建`EquityPoint`（@dataclass）

**注意事项**:
- 避免修改`UnifiedOrderManager`核心逻辑（保持单一职责）
- 避免修改`StrategyAdapter`主流程（仅扩展返回值）
- 确保新增代码符合Fail-Fast纪律（Guard Clauses、异常上下文）
- 确保新增代码符合Document-Driven TDD（接口契约注释先行）

---

## 任务统计

| 优先级 | 任务数 | 预估总工时 |
|-------|-------|-----------|
| P0 | 18个 | 72小时 |
| P1 | 0个 | 0小时 |
| P2 | 0个 | 0小时 |
| **总计** | **18个** | **72小时** |

---

## 开发任务清单

### P0 核心功能 (Must Have)

#### TASK-014-001: EquityPoint数据类定义
- **关联需求**: FP-014-004（prd.md）
- **关联架构**: architecture.md#4.1 EquityCurveBuilder - 核心原子服务
- **任务描述**: 创建EquityPoint数据类，用于表示权益曲线中的单个时间点
- **验收标准**:
  - [x] 使用@dataclass定义EquityPoint
  - [x] 包含字段：timestamp (int), cash (Decimal), position_value (Decimal), equity (Decimal), equity_rate (Decimal)
  - [x] 所有金额字段类型为Decimal
  - [x] 符合项目编码规范（类型提示、Docstring）
  - [x] **异常路径验证**: 当timestamp为负数时抛出ValueError
  - [x] **文档化标准合规** 📝
    - [x] 类文档注释符合Google Docstring格式
    - [x] 包含Purpose、Attributes、Example章节
- **边界检查**:
  - 输入边界: timestamp必须为正整数，equity必须非负
  - 资源状态: N/A（纯数据类）
- **预估工时**: 2小时
- **实际工时**: 1小时
- **依赖关系**: 无
- **测试策略**: 单元测试（test_equity_point_data_class.py）
  - **异常测试**: 测试timestamp为负数时的边界检查
- **文档要求**: ⭐
  - **接口契约注释**: 类文档注释，包含所有字段说明
  - **逻辑上下文注释**: N/A（纯数据类）
- **状态**: ✅ 已完成
- **提交**: 78c1fe7 - feat(TASK-014-001): 实现 EquityPoint 数据类

---

#### TASK-014-002: EquityCurveBuilder工具类实现
- **关联需求**: FP-014-004（prd.md）
- **关联架构**: architecture.md#4.1 EquityCurveBuilder - 核心原子服务
- **任务描述**: 实现权益曲线重建工具类，从订单和K线数据重建账户净值时间序列
- **验收标准**:
  - [ ] 创建`EquityCurveBuilder`类（静态方法）
  - [ ] 实现`build_from_orders(orders, klines, initial_cash) -> List[EquityPoint]`方法
  - [ ] 算法正确性：权益曲线第一个点equity = initial_cash
  - [ ] 算法正确性：每个点的equity = cash + position_value
  - [ ] 权益曲线长度 = K线数量
  - [ ] 使用Decimal类型进行所有金额计算
  - [ ] **异常路径验证**:
    - [ ] 当initial_cash <= 0时立即抛出ValueError
    - [ ] 当klines为空DataFrame时立即抛出ValueError
    - [ ] 当klines缺少必需列时立即抛出ValueError（包含缺失列名）
  - [ ] **文档化标准合规** 📝
    - [ ] 方法注释包含完整的Args、Returns、Raises、Example
    - [ ] 算法逻辑注释清晰（业务上下文）
- **边界检查**:
  - 输入边界: initial_cash > 0, klines非空, klines包含必需列
  - 资源状态: 无资源依赖
- **预估工时**: 6小时
- **依赖关系**: TASK-014-001
- **测试策略**: 单元测试（test_equity_curve_builder.py）
  - 正常场景：标准订单列表+K线数据
  - 边界场景：无订单、所有订单未平仓、K线数量=1
  - **异常场景**: initial_cash=0, K线数据为空, K线缺少必需列
- **文档要求**: ⭐
  - **接口契约注释**: build_from_orders()方法完整Docstring
  - **逻辑上下文注释**: 权益曲线重建算法步骤注释
- **状态**: 待开始

---

#### TASK-014-003: MetricsCalculator框架类创建
- **关联需求**: FP-014-001至FP-014-015（prd.md）
- **关联架构**: architecture.md#4.2 MetricsCalculator - 核心原子服务
- **任务描述**: 创建MetricsCalculator类框架，包含构造函数和calculate_all_metrics()方法骨架
- **验收标准**:
  - [ ] 创建`MetricsCalculator`类
  - [ ] 实现构造函数`__init__(risk_free_rate=Decimal("0.03"))`
  - [ ] 定义`calculate_all_metrics(orders, equity_curve, initial_cash, days)`方法签名
  - [ ] 返回值结构定义：Dict[str, Decimal]，包含17个P0指标键
  - [ ] 符合项目编码规范（类型提示、Docstring）
  - [ ] **异常路径验证**:
    - [ ] 当risk_free_rate < 0或 > 1时立即抛出ValueError（包含预期范围）
  - [ ] **文档化标准合规** 📝
    - [ ] 类文档注释完整（Purpose、Example）
    - [ ] __init__方法注释包含参数约束说明
- **边界检查**:
  - 输入边界: risk_free_rate范围[0, 1]
  - 资源状态: N/A
- **预估工时**: 2小时
- **依赖关系**: 无
- **测试策略**: 单元测试（test_metrics_calculator_init.py）
  - **异常测试**: risk_free_rate超出范围时的边界检查
- **文档要求**: ⭐
  - **接口契约注释**: 类文档注释和__init__方法Docstring
  - **逻辑上下文注释**: N/A（框架类）
- **状态**: 待开始

---

#### TASK-014-004: 收益指标计算实现
- **关联需求**: FP-014-001, FP-014-002, FP-014-003（prd.md）
- **关联架构**: architecture.md#4.2 MetricsCalculator
- **任务描述**: 实现3个收益指标计算方法：APR、绝对收益、累计收益率
- **验收标准**:
  - [ ] 实现`calculate_apr(total_profit, initial_cash, days) -> Decimal`
    - [ ] 公式正确：APR = (total_profit / initial_cash) × (365 / days) × 100%
    - [ ] 测试通过：365天10%收益，APR=10.00%
    - [ ] 测试通过：182.5天10%收益，APR=20.00%
  - [ ] 实现`calculate_cumulative_return(total_profit, initial_cash) -> Decimal`
    - [ ] 公式正确：累计收益率 = (total_profit / initial_cash) × 100%
    - [ ] 测试通过：初始10000，收益1000，累计收益率=10.00%
  - [ ] 绝对收益复用UnifiedOrderManager.calculate_statistics()的total_profit
  - [ ] 所有计算使用Decimal类型，精度保留2位小数
  - [ ] **异常路径验证**:
    - [ ] 当initial_cash <= 0时立即抛出ValueError（包含当前值）
    - [ ] 当days <= 0时立即抛出ValueError（包含当前值）
  - [ ] **文档化标准合规** 📝
    - [ ] 每个方法Docstring包含公式说明、Args、Returns、Raises、Example
- **边界检查**:
  - 输入边界: initial_cash > 0, days > 0
  - 资源状态: N/A
- **预估工时**: 4小时
- **依赖关系**: TASK-014-003
- **测试策略**: 单元测试（test_revenue_metrics.py）
  - 正常场景：标准盈利、标准时间
  - 边界场景：负收益、短期回测（<7天）
  - **异常场景**: initial_cash=0, days=0
- **文档要求**: ⭐
  - **接口契约注释**: 每个方法完整Docstring
  - **逻辑上下文注释**: 公式来源和业务含义注释
- **状态**: 待开始

---

#### TASK-014-005: 风险指标计算实现（MDD + 波动率）
- **关联需求**: FP-014-005, FP-014-006, FP-014-007（prd.md）
- **关联架构**: architecture.md#4.2 MetricsCalculator
- **任务描述**: 实现MDD、恢复时间和波动率计算方法
- **验收标准**:
  - [ ] 实现`calculate_mdd(equity_curve) -> Dict`
    - [ ] 返回字段：mdd, mdd_start_time, mdd_end_time, recovery_time
    - [ ] 算法正确：持续盈利无回撤，MDD=0.00%
    - [ ] 算法正确：从10000跌到9000，MDD=-10.00%
    - [ ] 恢复时间计算正确（已恢复/未恢复）
  - [ ] 实现`calculate_volatility(equity_curve) -> Decimal`
    - [ ] 公式正确：std(daily_returns) × sqrt(252)
    - [ ] 测试通过：无波动（所有收益率=0），波动率=0.00%
  - [ ] 使用Decimal类型，精度保留2位小数
  - [ ] **异常路径验证**:
    - [ ] 当equity_curve为空列表时，返回默认值（MDD=0, volatility=0），不抛出异常
    - [ ] 当equity_curve长度<2时，volatility=0（无法计算，优雅降级）
  - [ ] **文档化标准合规** 📝
    - [ ] 方法Docstring包含算法说明、边界处理、Example
- **边界检查**:
  - 输入边界: equity_curve可为空，长度>=1
  - 资源状态: N/A
- **预估工时**: 6小时
- **依赖关系**: TASK-014-002
- **测试策略**: 单元测试（test_risk_metrics.py）
  - 正常场景：标准权益曲线
  - 边界场景：无回撤、未恢复、波动率=0
  - **异常场景**: 空权益曲线、单点权益曲线
- **文档要求**: ⭐
  - **接口契约注释**: 完整Docstring，包含算法步骤
  - **逻辑上下文注释**: MDD算法核心步骤注释
- **状态**: 待开始

---

#### TASK-014-006: 风险调整收益指标计算实现
- **关联需求**: FP-014-008, FP-014-009, FP-014-010, FP-014-011（prd.md）
- **关联架构**: architecture.md#4.2 MetricsCalculator
- **任务描述**: 实现4个风险调整收益指标：夏普率、卡玛比率、MAR比率、盈利因子
- **验收标准**:
  - [ ] 实现`calculate_sharpe_ratio(apr, volatility) -> Decimal`
    - [ ] 公式正确：Sharpe = (APR - risk_free_rate) / Volatility
    - [ ] 测试通过：APR=12%, 波动率=15%, Sharpe=0.60
    - [ ] 除零保护：波动率=0时返回None
  - [ ] 实现`calculate_calmar_ratio(apr, mdd) -> Decimal`
    - [ ] 公式正确：Calmar = APR / abs(MDD)
    - [ ] 测试通过：APR=12%, MDD=-10%, Calmar=1.20
    - [ ] 除零保护：MDD=0时返回None
  - [ ] 实现`calculate_mar_ratio(cumulative_return, mdd) -> Decimal`
    - [ ] 公式正确：MAR = 累计收益率 / abs(MDD)
    - [ ] 除零保护：MDD=0时返回None
  - [ ] 实现`calculate_profit_factor(orders) -> Decimal`
    - [ ] 公式正确：Profit Factor = sum(盈利) / abs(sum(亏损))
    - [ ] 测试通过：总盈利2000，总亏损1000，PF=2.00
    - [ ] 除零保护：无亏损订单时返回None
  - [ ] **异常路径验证**:
    - [ ] 所有除法运算进行除零保护，返回None而非抛出异常（优雅降级）
  - [ ] **文档化标准合规** 📝
    - [ ] 每个方法Docstring包含公式、除零保护说明、Example
- **边界检查**:
  - 输入边界: 可接受0值（触发除零保护）
  - 资源状态: N/A
- **预估工时**: 5小时
- **依赖关系**: TASK-014-004, TASK-014-005
- **测试策略**: 单元测试（test_risk_adjusted_metrics.py）
  - 正常场景：标准数值
  - **异常场景**: 波动率=0, MDD=0, 无亏损订单
- **文档要求**: ⭐
  - **接口契约注释**: 完整Docstring，重点说明除零保护
  - **逻辑上下文注释**: 公式来源和业务含义注释
- **状态**: 待开始

---

#### TASK-014-007: 交易效率指标计算实现
- **关联需求**: FP-014-012, FP-014-013, FP-014-015（prd.md）
- **关联架构**: architecture.md#4.2 MetricsCalculator
- **任务描述**: 实现3个交易效率指标：交易频率、成本占比、盈亏比
- **验收标准**:
  - [ ] 实现`calculate_trade_frequency(total_orders, days) -> Decimal`
    - [ ] 公式正确：交易频率 = total_orders / days
    - [ ] 测试通过：365天120笔，频率=0.33次/天
  - [ ] 实现`calculate_cost_percentage(total_commission, total_profit) -> Decimal`
    - [ ] 公式正确：Cost % = total_commission / total_profit × 100%
    - [ ] 测试通过：收益1000，手续费20，成本占比=2.00%
    - [ ] 除零保护：total_profit=0时返回None
  - [ ] 实现`calculate_payoff_ratio(orders) -> Decimal`
    - [ ] 公式正确：Payoff = avg(盈利订单) / abs(avg(亏损订单))
    - [ ] 测试通过：平均盈利100，平均亏损50，盈亏比=2.00
    - [ ] 除零保护：无亏损订单时返回None
  - [ ] **异常路径验证**:
    - [ ] days <= 0时立即抛出ValueError
    - [ ] total_profit=0时优雅降级返回None
  - [ ] **文档化标准合规** 📝
    - [ ] 每个方法Docstring包含公式、边界处理、Example
- **边界检查**:
  - 输入边界: days > 0, 其他参数可为0
  - 资源状态: N/A
- **预估工时**: 4小时
- **依赖关系**: TASK-014-003
- **测试策略**: 单元测试（test_efficiency_metrics.py）
  - 正常场景：标准数值
  - 边界场景：高频交易、低成本
  - **异常场景**: days=0, total_profit=0, 无亏损订单
- **文档要求**: ⭐
  - **接口契约注释**: 完整Docstring
  - **逻辑上下文注释**: 指标业务含义注释
- **状态**: 待开始

---

#### TASK-014-008: MetricsCalculator.calculate_all_metrics()集成
- **关联需求**: FP-014-001至FP-014-015（prd.md）
- **关联架构**: architecture.md#4.2 MetricsCalculator
- **任务描述**: 实现calculate_all_metrics()方法，集成调用所有17个P0指标计算方法
- **验收标准**:
  - [ ] 实现`calculate_all_metrics(orders, equity_curve, initial_cash, days)`方法
  - [ ] 返回字典包含17个P0指标键值对
  - [ ] 所有指标精度保留2位小数
  - [ ] 边界处理：无已平仓订单时，返回默认值（MDD=0, 夏普率=None等）
  - [ ] **异常路径验证**:
    - [ ] 当initial_cash <= 0时立即抛出ValueError
    - [ ] 当days <= 0时立即抛出ValueError
  - [ ] **文档化标准合规** 📝
    - [ ] 方法Docstring包含完整的输入输出说明、返回字典结构
- **边界检查**:
  - 输入边界: initial_cash > 0, days > 0, orders可为空, equity_curve可为空
  - 资源状态: N/A
- **预估工时**: 3小时
- **依赖关系**: TASK-014-004, TASK-014-005, TASK-014-006, TASK-014-007
- **测试策略**: 集成测试（test_metrics_calculator_integration.py）
  - 正常场景：标准订单列表+权益曲线
  - 边界场景：无已平仓订单、MDD=0、波动率=0
  - **异常场景**: initial_cash=0, days=0
- **文档要求**: ⭐
  - **接口契约注释**: 完整Docstring，包含返回字典示例
  - **逻辑上下文注释**: 集成调用流程注释
- **状态**: 待开始

---

#### TASK-014-009: StrategyAdapter返回值扩展
- **关联需求**: architecture.md#6.2 StrategyAdapter复用适配
- **关联架构**: architecture.md#6.2 StrategyAdapter - 接口扩展复用
- **任务描述**: 扩展StrategyAdapter.adapt_for_backtest()返回值，新增'orders'字段
- **验收标准**:
  - [ ] 修改`adapt_for_backtest()`方法返回值
  - [ ] 返回字典新增'orders'键，值为List[Order]（所有订单列表）
  - [ ] 保持现有返回字段不变：'entries', 'exits', 'statistics'
  - [ ] 回归测试通过：现有功能不受影响
  - [ ] **异常路径验证**: N/A（非破坏性扩展）
  - [ ] **文档化标准合规** 📝
    - [ ] 更新方法Docstring的Returns部分，说明新增'orders'字段
- **边界检查**:
  - 输入边界: N/A（仅修改返回值）
  - 资源状态: N/A
- **预估工时**: 1小时
- **依赖关系**: 无
- **测试策略**: 单元测试（test_strategy_adapter_extension.py）
  - 验证'orders'字段正确返回
  - 回归测试：现有返回字段不受影响
- **文档要求**: ⭐
  - **接口契约注释**: 更新Returns部分
  - **逻辑上下文注释**: 注释说明扩展理由（供MetricsCalculator使用）
- **状态**: 待开始

---

#### TASK-014-010: CLI参数扩展（--risk-free-rate）
- **关联需求**: FP-014-017（prd.md）
- **关联架构**: architecture.md#7 关键技术决策 - 决策点2
- **任务描述**: 在run_strategy_backtest命令中新增--risk-free-rate参数
- **验收标准**:
  - [ ] 在`add_arguments()`方法中新增--risk-free-rate参数
  - [ ] 参数类型：float，默认值：3.0
  - [ ] 参数help说明：无风险收益率（年化，百分比），默认3.0%
  - [ ] 参数传递给MetricsCalculator构造函数
  - [ ] 测试通过：未指定时使用默认值3%
  - [ ] 测试通过：指定--risk-free-rate 5.0时使用5%
  - [ ] **异常路径验证**:
    - [ ] 参数值超出合理范围[0, 100]时，显示警告（不阻止执行）
  - [ ] **文档化标准合规** 📝
    - [ ] 更新help文档，说明参数含义和常见值
- **边界检查**:
  - 输入边界: risk_free_rate范围建议[0, 100]
  - 资源状态: N/A
- **预估工时**: 2小时
- **依赖关系**: TASK-014-003
- **测试策略**: 单元测试（test_cli_parameters.py）
  - 测试默认值
  - 测试自定义值
  - **异常场景**: 超出合理范围值
- **文档要求**: ⭐
  - **接口契约注释**: 参数注释说明
  - **逻辑上下文注释**: 参数业务含义注释
- **状态**: 待开始

---

#### TASK-014-011: CLI报告输出重构（分层报告）
- **关联需求**: FP-014-016（prd.md）
- **关联架构**: architecture.md#2.2 报告输出流程
- **任务描述**: 重构_display_results()方法，实现分层报告输出（默认/--verbose模式）
- **验收标准**:
  - [ ] 默认模式：输出15个P0核心指标
    - [ ] 收益分析：APR、绝对收益、累计收益率
    - [ ] 风险分析：MDD、波动率、恢复时间
    - [ ] 风险调整收益：夏普率、卡玛比率、MAR比率、盈利因子
    - [ ] 交易效率：交易频率、成本占比、胜率、盈亏比
  - [ ] 详细模式（--verbose）：输出所有可用指标（P0为主）
  - [ ] 报告格式清晰：使用【分类】+ 缩进结构
  - [ ] 数值精度：保留2位小数
  - [ ] 颜色高亮：使用self.style.SUCCESS/ERROR/WARNING
  - [ ] **异常路径验证**: N/A（仅输出逻辑）
  - [ ] **文档化标准合规** 📝
    - [ ] 方法Docstring说明输出格式和分层逻辑
- **边界检查**:
  - 输入边界: metrics字典可能包含None值（需优雅处理）
  - 资源状态: N/A
- **预估工时**: 4小时
- **依赖关系**: TASK-014-008
- **测试策略**: 集成测试（test_report_output.py）
  - 测试默认模式输出格式
  - 测试详细模式输出格式
  - 边界场景：指标值为None时显示"N/A"
- **文档要求**: ⭐
  - **接口契约注释**: 方法Docstring说明输出格式
  - **逻辑上下文注释**: 分层逻辑注释
- **状态**: 待开始

---

#### TASK-014-012: BacktestResult数据模型创建
- **关联需求**: FP-014-018（prd.md）
- **关联架构**: architecture.md#7 关键技术决策 - 决策点4
- **任务描述**: 在strategy_adapter中创建BacktestResult数据模型
- **验收标准**:
  - [ ] 创建`strategy_adapter/models.py`文件（如果不存在）
  - [ ] 定义BacktestResult模型，继承models.Model
  - [ ] 基本信息字段：strategy_name, symbol, interval, market_type, start_date, end_date
  - [ ] 回测参数字段：initial_cash, position_size, commission_rate, risk_free_rate
  - [ ] 结果数据字段：equity_curve (JSONField), metrics (JSONField)
  - [ ] 元数据字段：created_at (auto_now_add=True)
  - [ ] 字段类型和精度正确（Decimal使用max_digits=20, decimal_places=2）
  - [ ] **异常路径验证**:
    - [ ] 字段长度限制验证（strategy_name ≤ 100等）
  - [ ] **文档化标准合规** 📝
    - [ ] 模型Docstring说明用途和字段含义
- **边界检查**:
  - 输入边界: 字段长度限制、JSON字段格式验证
  - 资源状态: 数据库连接正常
- **预估工时**: 3小时
- **依赖关系**: 无
- **测试策略**: 单元测试（test_backtest_result_model.py）
  - 测试创建记录
  - 测试字段类型和精度
  - **异常场景**: 字段长度超限、JSON格式错误
- **文档要求**: ⭐
  - **接口契约注释**: 模型Docstring和字段注释
  - **逻辑上下文注释**: 模型用途和设计理由注释
- **状态**: 待开始

---

#### TASK-014-013: BacktestOrder数据模型创建
- **关联需求**: FP-014-019（prd.md）
- **关联架构**: architecture.md#7 关键技术决策 - 决策点4
- **任务描述**: 在strategy_adapter中创建BacktestOrder数据模型
- **验收标准**:
  - [ ] 定义BacktestOrder模型，继承models.Model
  - [ ] 外键关联：backtest_result (ForeignKey, on_delete=CASCADE, related_name='orders')
  - [ ] 订单信息字段：order_id, status, buy_price, buy_timestamp, sell_price, sell_timestamp
  - [ ] 持仓信息字段：quantity, position_value, commission
  - [ ] 收益信息字段：profit_loss, profit_loss_rate, holding_periods
  - [ ] 字段类型和精度正确（价格保留8位小数，金额保留2位小数）
  - [ ] 可空字段正确：sell_price、sell_timestamp、profit_loss等仅在status='sold'时有值
  - [ ] **异常路径验证**:
    - [ ] 外键约束：backtest_result必须存在
  - [ ] **文档化标准合规** 📝
    - [ ] 模型Docstring说明用途和字段含义
- **边界检查**:
  - 输入边界: 外键存在性、状态枚举值
  - 资源状态: 数据库连接正常
- **预估工时**: 3小时
- **依赖关系**: TASK-014-012
- **测试策略**: 单元测试（test_backtest_order_model.py）
  - 测试创建记录
  - 测试外键关联
  - 测试反向查询（result.orders.all()）
  - **异常场景**: 外键不存在
- **文档要求**: ⭐
  - **接口契约注释**: 模型Docstring和字段注释
  - **逻辑上下文注释**: 外键关联说明注释
- **状态**: 待开始

---

#### TASK-014-014: CLI参数扩展（--save-to-db）+ 保存逻辑
- **关联需求**: FP-014-020（prd.md）
- **关联架构**: architecture.md#5 组件与需求映射
- **任务描述**: 新增--save-to-db参数，实现回测结果保存到数据库功能
- **验收标准**:
  - [ ] 在`add_arguments()`中新增--save-to-db参数（action='store_true'）
  - [ ] 实现`_save_backtest_result(result, klines_df, options)`方法
  - [ ] 创建BacktestResult记录（包含equity_curve和metrics的JSON数据）
  - [ ] 批量创建BacktestOrder记录（使用bulk_create提高性能）
  - [ ] 使用Django事务保证原子性（要么全部保存，要么全部回滚）
  - [ ] 输出保存成功信息（包含记录ID和访问URL）
  - [ ] 测试通过：指定--save-to-db时成功保存
  - [ ] 测试通过：未指定时不保存（保持向后兼容）
  - [ ] **异常路径验证**:
    - [ ] 数据库连接失败时捕获异常并友好提示
  - [ ] **文档化标准合规** 📝
    - [ ] _save_backtest_result方法完整Docstring
- **边界检查**:
  - 输入边界: equity_curve可能很大（数千个时间点）
  - 资源状态: 数据库连接正常，事务支持
- **预估工时**: 4小时
- **依赖关系**: TASK-014-012, TASK-014-013, TASK-014-002, TASK-014-008
- **测试策略**: 集成测试（test_save_to_db.py）
  - 测试保存成功
  - 测试不保存时无记录
  - **异常场景**: 数据库连接失败、事务回滚
- **文档要求**: ⭐
  - **接口契约注释**: _save_backtest_result方法Docstring
  - **逻辑上下文注释**: 事务管理和批量创建说明注释
- **状态**: 待开始

---

#### TASK-014-015: Django migration文件创建
- **关联需求**: FP-014-018, FP-014-019（prd.md）
- **关联架构**: architecture.md#8.5 技术影响分析 - 数据库变更
- **任务描述**: 创建Django migration文件，用于数据库表创建
- **验收标准**:
  - [ ] 运行`python manage.py makemigrations strategy_adapter`
  - [ ] 生成migration文件包含BacktestResult和BacktestOrder表定义
  - [ ] 运行`python manage.py migrate`成功创建表
  - [ ] 验证表结构正确（使用dbshell或Django shell）
  - [ ] **异常路径验证**:
    - [ ] migration冲突时提供解决方案
  - [ ] **文档化标准合规** 📝
    - [ ] migration文件包含注释说明表用途
- **边界检查**:
  - 输入边界: N/A
  - 资源状态: 数据库连接正常
- **预估工时**: 1小时
- **依赖关系**: TASK-014-012, TASK-014-013
- **测试策略**: 手动测试
  - 测试makemigrations
  - 测试migrate
  - 验证表结构
- **文档要求**: ⭐
  - **接口契约注释**: migration文件注释
  - **逻辑上下文注释**: 表用途说明注释
- **状态**: 待开始

---

#### TASK-014-016: BacktestResultListView实现
- **关联需求**: FP-014-021（prd.md）
- **关联架构**: architecture.md#5 组件与需求映射
- **任务描述**: 创建回测结果列表页视图和模板
- **验收标准**:
  - [ ] 创建`BacktestResultListView`类视图（继承ListView）
  - [ ] 支持筛选：按strategy_name、symbol、market_type筛选
  - [ ] 支持排序：按created_at倒序排列
  - [ ] 支持分页：每页20条记录
  - [ ] 创建模板`templates/backtest/list.html`
    - [ ] 表格展示：策略、交易对、周期、市场、时间范围、总收益、胜率、创建时间
    - [ ] 操作按钮：查看详情、删除记录
  - [ ] URL路由：`/backtest/results/`
  - [ ] 测试通过：列表正确展示所有回测记录
  - [ ] 测试通过：筛选功能正常工作
  - [ ] 测试通过：分页功能正常工作
  - [ ] **异常路径验证**:
    - [ ] 无记录时显示"暂无回测记录"提示
    - [ ] 筛选无结果时显示"无符合条件的记录"提示
  - [ ] **文档化标准合规** 📝
    - [ ] 视图类Docstring说明功能
- **边界检查**:
  - 输入边界: 筛选参数可为空
  - 资源状态: 数据库连接正常
- **预估工时**: 5小时
- **依赖关系**: TASK-014-015
- **测试策略**: 单元测试（test_list_view.py）
  - 测试列表访问
  - 测试筛选功能
  - 测试分页功能
  - **异常场景**: 无记录、筛选无结果
- **文档要求**: ⭐
  - **接口契约注释**: 视图类Docstring
  - **逻辑上下文注释**: 筛选和分页逻辑注释
- **状态**: 待开始

---

#### TASK-014-017: BacktestResultDetailView实现
- **关联需求**: FP-014-022（prd.md）
- **关联架构**: architecture.md#5 组件与需求映射
- **任务描述**: 创建回测结果详情页视图和模板
- **验收标准**:
  - [ ] 创建`BacktestResultDetailView`类视图（继承DetailView）
  - [ ] 创建模板`templates/backtest/detail.html`
    - [ ] 基本信息卡片：策略、交易对、时间范围、初始资金等
    - [ ] 量化指标卡片：4大模块17个P0指标
    - [ ] 订单列表表格：所有订单详情（分页50条）
  - [ ] URL路由：`/backtest/results/<id>/`
  - [ ] 测试通过：基本信息正确显示
  - [ ] 测试通过：所有量化指标正确显示（17个P0指标）
  - [ ] 测试通过：订单列表正确展示
  - [ ] **异常路径验证**:
    - [ ] 记录不存在时返回404错误
    - [ ] 无订单数据时显示"暂无订单"提示
    - [ ] 指标缺失时显示"N/A"
  - [ ] **文档化标准合规** 📝
    - [ ] 视图类Docstring说明功能
- **边界检查**:
  - 输入边界: id必须存在
  - 资源状态: 数据库连接正常
- **预估工时**: 6小时
- **依赖关系**: TASK-014-015
- **测试策略**: 单元测试（test_detail_view.py）
  - 测试详情页访问
  - 测试指标显示
  - 测试订单列表
  - **异常场景**: 记录不存在、无订单、指标缺失
- **文档要求**: ⭐
  - **接口契约注释**: 视图类Docstring
  - **逻辑上下文注释**: 数据处理逻辑注释
- **状态**: 待开始

---

#### TASK-014-018: Chart.js权益曲线图集成
- **关联需求**: FP-014-023（prd.md）
- **关联架构**: architecture.md#5 组件与需求映射
- **任务描述**: 在详情页集成Chart.js，绘制权益曲线图
- **验收标准**:
  - [ ] 在模板中引入Chart.js库（CDN）
  - [ ] 创建canvas元素（id="equityCurveChart"）
  - [ ] 编写JavaScript代码绘制折线图
    - [ ] X轴：时间戳（格式化为日期时间）
    - [ ] Y轴：账户净值（USDT）
    - [ ] 数据来源：backtest_result.equity_curve（JSON字段）
  - [ ] 交互功能：鼠标悬停显示时间点和净值
  - [ ] 响应式设计：适配不同屏幕尺寸
  - [ ] 测试通过：图表正确渲染
  - [ ] 测试通过：数据点对应关系正确
  - [ ] 测试通过：交互功能正常
  - [ ] **异常路径验证**:
    - [ ] 数据为空时显示"暂无数据"提示
  - [ ] **文档化标准合规** 📝
    - [ ] JavaScript代码注释说明图表配置
- **边界检查**:
  - 输入边界: equity_curve可能很大（>1000个点）
  - 资源状态: 浏览器兼容性
- **预估工时**: 4小时
- **依赖关系**: TASK-014-017
- **测试策略**: 手动测试
  - 测试图表渲染
  - 测试交互功能
  - 测试响应式布局
  - **异常场景**: 数据为空
- **文档要求**: ⭐
  - **接口契约注释**: N/A（前端代码）
  - **逻辑上下文注释**: Chart.js配置注释
- **状态**: 待开始

---

## 技术任务

### 环境搭建
- [x] 开发环境配置（已完成）
- [x] CI/CD流水线设置（已完成）
- [x] 代码规范配置（已完成）
- [ ] **文档风格定义** ⭐ **新增**
  - [ ] 已确定项目文档化标准（Python Docstrings - Google风格）
  - [ ] 注释模板已创建（`docs/comment-templates.md`）
  - [ ] 自动化文档生成工具已配置（待定）
  - [ ] CI/CD包含文档化验证步骤（待定）

### 基础设施
- [x] 数据库迁移脚本（通过Django makemigrations/migrate）
- [ ] API文档生成（如需要）
- [ ] 监控和日志系统（复用现有）

---

## 开发里程碑

| 里程碑 | 包含任务 | 预计完成时间 | 验收标准 |
|-------|---------|------------|---------|
| M1: 数据结构和基础工具完成 | TASK-001, TASK-002, TASK-003 | Day 3 | EquityPoint、EquityCurveBuilder、MetricsCalculator框架完成 |
| M2: 指标计算完成 | TASK-004, TASK-005, TASK-006, TASK-007, TASK-008 | Day 8 | 所有17个P0指标计算通过单元测试 |
| M3: CLI集成完成 | TASK-009, TASK-010, TASK-011 | Day 11 | CLI支持量化指标输出和--risk-free-rate参数 |
| M4: 数据持久化完成 | TASK-012, TASK-013, TASK-014, TASK-015 | Day 14 | 支持--save-to-db，数据库表创建完成 |
| M5: Web展示完成 | TASK-016, TASK-017, TASK-018 | Day 18 | 列表页、详情页、Chart.js图表全部完成 |

---

## 风险评估

### 高风险任务
- **任务**: TASK-014-002 (EquityCurveBuilder实现)
- **风险**: 权益曲线重建算法复杂，可能性能较慢（大规模K线数据）
- **缓解措施**:
  - 优先使用numpy向量化操作，避免Python循环
  - 仅在--save-to-db时执行重建，不影响普通回测
  - 如性能仍不足，可考虑优化为实时记录（architecture.md备选方案）

- **任务**: TASK-014-005 (MDD计算)
- **风险**: MDD算法边界情况多（无回撤、未恢复等），容易出错
- **缓解措施**:
  - 完整单元测试覆盖所有边界情况
  - 参考QuantStats等成熟库验证算法正确性
  - 使用真实历史数据进行集成测试

### 技术依赖
- **依赖**: Chart.js库
- **风险**: CDN不可用或浏览器兼容性问题
- **应对**:
  - 使用稳定的CDN源（如cdnjs.cloudflare.com）
  - 提供本地fallback方案
  - 测试主流浏览器兼容性

- **依赖**: Django JSONField
- **风险**: equity_curve可能很大（数千个时间点），JSONField容量限制
- **应对**:
  - 验证PostgreSQL JSONField支持大JSON（通常无问题）
  - 如遇到性能问题，考虑数据抽样或分页加载
  - 监控数据库存储和查询性能

---

**文档版本**: v1.0.0
**创建日期**: 2026-01-06
**P5阶段状态**: ✅ 已完成 Step 1-2，等待Gate 5检查
**下一步**: Gate 5检查 → P6阶段（开发实现）
