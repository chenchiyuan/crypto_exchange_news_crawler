# 功能点清单：策略适配层

**迭代编号**: 013
**迭代名称**: 策略适配层
**文档版本**: 1.0
**创建日期**: 2026-01-06

---

## 功能点分级说明

- **P0**：MVP核心功能，必须实现
- **P1**：增强功能，可推迟到下一迭代
- **P2**：优化功能，视情况实现

---

## P0 核心功能点

### 1. 模块结构搭建

#### FP-013-001: 创建strategy_adapter模块
- **描述**：创建顶层模块目录和子模块结构
- **优先级**：P0
- **验收标准**：
  - [ ] 目录结构符合PRD 4.1设计
  - [ ] 所有子模块包含`__init__.py`
  - [ ] 模块可正常导入

**目录结构**：
```
strategy_adapter/
├── __init__.py
├── interfaces/
├── core/
├── models/
├── adapters/
└── tests/
```

---

### 2. 接口定义

#### FP-013-002: IStrategy接口定义
- **描述**：定义标准化策略接口，包含8个核心方法
- **优先级**：P0
- **依赖**：FP-013-001
- **验收标准**：
  - [ ] 所有方法包含完整的类型提示
  - [ ] 每个方法包含详细的docstring
  - [ ] 使用ABC抽象基类
  - [ ] 参数和返回值类型明确

**核心方法**：
1. `get_strategy_name()` - 返回策略名称
2. `get_strategy_version()` - 返回策略版本
3. `generate_buy_signals()` - 生成买入信号
4. `generate_sell_signals()` - 生成卖出信号
5. `calculate_position_size()` - 计算仓位大小
6. `should_stop_loss()` - 检查止损条件
7. `should_take_profit()` - 检查止盈条件
8. `get_required_indicators()` - 返回所需指标列表（可选）

**文件位置**：`strategy_adapter/interfaces/strategy.py`

---

### 3. 数据模型

#### FP-013-003: Order数据类
- **描述**：定义统一的订单数据结构
- **优先级**：P0
- **依赖**：FP-013-001
- **验收标准**：
  - [ ] 使用dataclass装饰器
  - [ ] 包含完整的开平仓信息
  - [ ] 自动计算盈亏方法`calculate_pnl()`
  - [ ] 支持现货和合约
  - [ ] 包含策略元数据字段

**核心字段**：
- 基础信息：id, symbol, side, status
- 开仓信息：open_timestamp, open_price, quantity, position_value
- 平仓信息：close_timestamp, close_price, close_reason
- 策略信息：strategy_name, strategy_id, entry_reason
- 盈亏信息：profit_loss, profit_loss_rate, holding_periods
- 手续费：open_commission, close_commission
- 扩展字段：metadata (dict)

**文件位置**：`strategy_adapter/models/order.py`

---

#### FP-013-004: 枚举类型定义
- **描述**：定义OrderStatus和OrderSide枚举
- **优先级**：P0
- **依赖**：FP-013-001
- **验收标准**：
  - [ ] OrderStatus包含：pending, filled, closed, cancelled
  - [ ] OrderSide包含：buy, sell
  - [ ] 使用Python Enum类

**文件位置**：`strategy_adapter/models/enums.py`

---

### 4. 核心组件

#### FP-013-005: UnifiedOrderManager实现
- **描述**：统一订单管理器，整合应用层和回测层的订单管理能力
- **优先级**：P0
- **依赖**：FP-013-003, FP-013-004
- **验收标准**：
  - [ ] `create_order()` - 从信号创建订单
  - [ ] `update_order()` - 更新订单（平仓）
  - [ ] `get_open_orders()` - 获取持仓订单
  - [ ] `get_closed_orders()` - 获取已平仓订单
  - [ ] `calculate_statistics()` - 计算统计指标
  - [ ] 支持按策略名称筛选
  - [ ] 使用Decimal精度计算

**统计指标**：
- 总订单数、持仓数、已平仓数
- 胜率、总盈亏、平均盈亏率
- 最大盈利、最大亏损
- 平均持仓周期

**文件位置**：`strategy_adapter/core/unified_order_manager.py`

---

#### FP-013-006: SignalConverter实现
- **描述**：将应用层信号转换为vectorbt格式
- **优先级**：P0
- **依赖**：FP-013-001
- **验收标准**：
  - [ ] `to_vectorbt_signals()` - 转换信号为pd.Series
  - [ ] 正确处理时间对齐
  - [ ] 验证信号有效性（时间戳在K线范围内）
  - [ ] 支持买入和卖出信号
  - [ ] 返回entries和exits两个pd.Series

**核心逻辑**：
```python
# 输入：应用层信号
buy_signals = [
    {'timestamp': 1736078400000, 'price': 2300.50, ...},
    ...
]

# 输出：vectorbt信号
entries = pd.Series([False, True, False, ...], index=klines.index)
exits = pd.Series([False, False, True, ...], index=klines.index)
```

**文件位置**：`strategy_adapter/core/signal_converter.py`

---

#### FP-013-007: StrategyAdapter实现
- **描述**：策略适配器，整合IStrategy、UnifiedOrderManager和SignalConverter
- **优先级**：P0
- **依赖**：FP-013-002, FP-013-005, FP-013-006
- **验收标准**：
  - [ ] `adapt_for_backtest()` - 适配策略用于回测
  - [ ] 调用策略的`generate_buy_signals()`和`generate_sell_signals()`
  - [ ] 使用UnifiedOrderManager管理订单
  - [ ] 使用SignalConverter转换信号
  - [ ] 返回entries, exits, orders, statistics

**返回数据结构**：
```python
{
    'entries': pd.Series,      # vectorbt买入信号
    'exits': pd.Series,        # vectorbt卖出信号
    'orders': List[Order],     # 订单列表
    'statistics': Dict         # 统计信息
}
```

**文件位置**：`strategy_adapter/core/strategy_adapter.py`

---

### 5. DDPS-Z策略适配

#### FP-013-008: DDPSZStrategy实现
- **描述**：DDPS-Z策略适配器，实现IStrategy接口
- **优先级**：P0
- **依赖**：FP-013-002
- **验收标准**：
  - [ ] 实现所有IStrategy接口方法
  - [ ] 复用BuySignalCalculator（迭代011）
  - [ ] 复用EMA25卖出逻辑（迭代012）
  - [ ] 固定100 USDT买入金额
  - [ ] MVP阶段不启用止盈止损

**核心逻辑**：
- `generate_buy_signals()`: 调用`ddps_z.calculators.BuySignalCalculator`
- `generate_sell_signals()`: 实现EMA25回归卖出逻辑
- `calculate_position_size()`: 返回固定100 USDT

**文件位置**：`strategy_adapter/adapters/ddpsz_adapter.py`

---

#### FP-013-009: DDPS-Z回测集成
- **描述**：将DDPSZStrategy接入BacktestEngine进行回测
- **优先级**：P0
- **依赖**：FP-013-007, FP-013-008
- **验收标准**：
  - [ ] 使用StrategyAdapter适配DDPSZStrategy
  - [ ] 调用BacktestEngine.run_backtest()
  - [ ] 成功生成BacktestResult
  - [ ] 包含夏普比率、最大回撤等vectorbt指标
  - [ ] 结果与OrderTracker对比（±5%容差）

**示例代码位置**：PRD附录或单独的使用示例文件

---

### 6. 测试

#### FP-013-010: UnifiedOrderManager单元测试
- **描述**：测试订单管理器的核心功能
- **优先级**：P0
- **依赖**：FP-013-005
- **验收标准**：
  - [ ] 测试create_order()
  - [ ] 测试update_order()
  - [ ] 测试get_open_orders()
  - [ ] 测试calculate_statistics()
  - [ ] 测试盈亏计算准确性
  - [ ] 覆盖率 > 80%

**文件位置**：`strategy_adapter/tests/test_order_manager.py`

---

#### FP-013-011: SignalConverter单元测试
- **描述**：测试信号转换器
- **优先级**：P0
- **依赖**：FP-013-006
- **验收标准**：
  - [ ] 测试to_vectorbt_signals()
  - [ ] 测试时间对齐逻辑
  - [ ] 测试信号验证
  - [ ] 测试边界情况（空信号、重复信号）
  - [ ] 覆盖率 > 80%

**文件位置**：`strategy_adapter/tests/test_signal_converter.py`

---

#### FP-013-012: DDPSZStrategy单元测试
- **描述**：测试DDPS-Z策略适配器
- **优先级**：P0
- **依赖**：FP-013-008
- **验收标准**：
  - [ ] 测试generate_buy_signals()
  - [ ] 测试generate_sell_signals()
  - [ ] 测试calculate_position_size()
  - [ ] 验证与原OrderTracker逻辑一致
  - [ ] 覆盖率 > 80%

**文件位置**：`strategy_adapter/tests/test_ddpsz_strategy.py`

---

#### FP-013-013: 端到端集成测试
- **描述**：完整的回测流程集成测试
- **优先级**：P0
- **依赖**：FP-013-009
- **验收标准**：
  - [ ] 测试完整回测流程（策略 → 适配器 → 回测引擎）
  - [ ] 验证结果准确性
  - [ ] 对比OrderTracker和StrategyAdapter结果
  - [ ] 容差在±5%以内

**测试场景**：
1. 使用ETHUSDT 4h数据（180天）
2. 运行DDPS-Z策略
3. 对比适配层和OrderTracker的：
   - 订单数量
   - 总盈亏
   - 胜率

**文件位置**：`strategy_adapter/tests/test_integration.py`

---

## P1 增强功能点

### 7. 内置策略库

#### FP-013-014: SimpleMAStrategy实现
- **描述**：双均线策略参考实现
- **优先级**：P1
- **验收标准**：
  - [ ] 实现IStrategy接口
  - [ ] 支持可配置参数（快慢周期）
  - [ ] 提供单元测试

**策略逻辑**：
- 买入：快线上穿慢线
- 卖出：快线下穿慢线

---

#### FP-013-015: RSIStrategy实现
- **描述**：RSI超买超卖策略
- **优先级**：P1
- **验收标准**：
  - [ ] 实现IStrategy接口
  - [ ] 支持可配置阈值（超买/超卖）
  - [ ] 提供单元测试

**策略逻辑**：
- 买入：RSI < 30（超卖）
- 卖出：RSI > 70（超买）

---

### 8. 高级功能

#### FP-013-016: 策略组合支持
- **描述**：StrategyComposer，支持多策略并行
- **优先级**：P1
- **验收标准**：
  - [ ] 支持多个策略同时运行
  - [ ] 资金分配管理
  - [ ] 汇总统计

---

#### FP-013-017: 动态仓位管理
- **描述**：基于信号强度动态调整仓位
- **优先级**：P1
- **验收标准**：
  - [ ] 根据信号confidence调整买入金额
  - [ ] 风险控制（最大仓位限制）

---

### 9. 持久化

#### FP-013-018: 订单持久化
- **描述**：将订单保存到数据库
- **优先级**：P1
- **验收标准**：
  - [ ] 创建OrderModel（Django模型）
  - [ ] UnifiedOrderManager支持持久化
  - [ ] 支持历史查询

---

## P2 优化功能点

### 10. 性能优化

#### FP-013-019: 信号转换性能优化
- **描述**：优化SignalConverter的转换速度
- **优先级**：P2
- **验收标准**：
  - [ ] 转换1000条信号 < 50ms
  - [ ] 使用numpy向量化

---

#### FP-013-020: 订单查询缓存
- **描述**：UnifiedOrderManager查询结果缓存
- **优先级**：P2
- **验收标准**：
  - [ ] 缓存get_open_orders()结果
  - [ ] 订单更新时失效缓存

---

## 功能点汇总表

| 编号 | 功能点 | 优先级 | 预计工时 | 依赖 |
|------|--------|--------|----------|------|
| FP-013-001 | 创建strategy_adapter模块 | P0 | 0.5h | - |
| FP-013-002 | IStrategy接口定义 | P0 | 1h | FP-013-001 |
| FP-013-003 | Order数据类 | P0 | 1h | FP-013-001 |
| FP-013-004 | 枚举类型定义 | P0 | 0.5h | FP-013-001 |
| FP-013-005 | UnifiedOrderManager实现 | P0 | 3h | FP-013-003, 004 |
| FP-013-006 | SignalConverter实现 | P0 | 2h | FP-013-001 |
| FP-013-007 | StrategyAdapter实现 | P0 | 2h | FP-013-002, 005, 006 |
| FP-013-008 | DDPSZStrategy实现 | P0 | 2h | FP-013-002 |
| FP-013-009 | DDPS-Z回测集成 | P0 | 1h | FP-013-007, 008 |
| FP-013-010 | UnifiedOrderManager单元测试 | P0 | 2h | FP-013-005 |
| FP-013-011 | SignalConverter单元测试 | P0 | 1h | FP-013-006 |
| FP-013-012 | DDPSZStrategy单元测试 | P0 | 1h | FP-013-008 |
| FP-013-013 | 端到端集成测试 | P0 | 2h | FP-013-009 |
| **P0小计** | **13个功能点** | **P0** | **19h (约3天)** | - |
| FP-013-014 | SimpleMAStrategy实现 | P1 | 2h | FP-013-002 |
| FP-013-015 | RSIStrategy实现 | P1 | 2h | FP-013-002 |
| FP-013-016 | 策略组合支持 | P1 | 4h | FP-013-007 |
| FP-013-017 | 动态仓位管理 | P1 | 3h | FP-013-005 |
| FP-013-018 | 订单持久化 | P1 | 3h | FP-013-005 |
| **P1小计** | **5个功能点** | **P1** | **14h (约2天)** | - |
| FP-013-019 | 信号转换性能优化 | P2 | 2h | FP-013-006 |
| FP-013-020 | 订单查询缓存 | P2 | 2h | FP-013-005 |
| **P2小计** | **2个功能点** | **P2** | **4h (约0.5天)** | - |

---

## 开发顺序建议

### 阶段1：基础设施（Day 1上午）
1. FP-013-001: 创建模块结构
2. FP-013-004: 枚举类型定义
3. FP-013-003: Order数据类
4. FP-013-002: IStrategy接口定义

### 阶段2：核心组件（Day 1下午 + Day 2上午）
5. FP-013-006: SignalConverter实现
6. FP-013-005: UnifiedOrderManager实现
7. FP-013-007: StrategyAdapter实现

### 阶段3：DDPS-Z适配（Day 2下午）
8. FP-013-008: DDPSZStrategy实现
9. FP-013-009: DDPS-Z回测集成

### 阶段4：测试验证（Day 3）
10. FP-013-010: UnifiedOrderManager单元测试
11. FP-013-011: SignalConverter单元测试
12. FP-013-012: DDPSZStrategy单元测试
13. FP-013-013: 端到端集成测试

---

## 验收检查清单

### 功能完整性
- [ ] 所有P0功能点已实现
- [ ] IStrategy接口定义完整
- [ ] UnifiedOrderManager功能正常
- [ ] DDPS-Z策略成功适配
- [ ] 回测流程端到端打通

### 代码质量
- [ ] 单元测试覆盖率 > 80%
- [ ] 所有公开API包含docstring
- [ ] 类型提示完整
- [ ] 代码通过black格式化
- [ ] 代码通过mypy类型检查

### 性能指标
- [ ] 信号转换延迟 < 50ms（1000条信号）
- [ ] 订单管理延迟 < 10ms（100个订单查询）
- [ ] 回测执行时间 < 5s（180天数据）

### 结果准确性
- [ ] DDPS-Z适配层回测与OrderTracker结果对比
- [ ] 订单数量差异 < 5%
- [ ] 总盈亏差异 < 5%
- [ ] 胜率差异 < 5%

---

**文档状态**: ✅ 功能点清单完成
**总功能点**: 20个（P0: 13, P1: 5, P2: 2）
**预计总工时**: 约3天（仅P0功能）
