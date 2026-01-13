# 功能点清单: 回测结果协议抽象

## 文档信息

| 字段 | 值 |
|------|-----|
| 迭代编号 | 042 |
| 创建日期 | 2026-01-13 |

## 功能点列表

### FP-042-001: BacktestResult数据类

| 属性 | 值 |
|------|-----|
| 优先级 | P0 |
| 复杂度 | 低 |
| 依赖 | 无 |

**描述**: 在`strategy_adapter/models/`中创建BacktestResult数据类

**字段分组**:
1. 核心统计 (7个): total_orders, winning_orders, losing_orders, open_positions, win_rate, net_profit, return_rate
2. 资金统计 (6个): initial_capital, total_equity, available_capital, frozen_capital, holding_cost, holding_value
3. 交易统计 (2个): total_volume, total_commission
4. 年化指标 (5个): static_apr, weighted_apy, backtest_days, start_date, end_date
5. 扩展字段 (2个): extra_stats, orders

**验收标准**:
- [ ] dataclass可正常实例化
- [ ] 提供to_dict()方法转换为字典
- [ ] 提供from_dict()类方法从字典构建

---

### FP-042-002: Strategy16返回BacktestResult

| 属性 | 值 |
|------|-----|
| 优先级 | P0 |
| 复杂度 | 中 |
| 依赖 | FP-042-001 |

**描述**: 修改Strategy16LimitEntry的_generate_result方法

**变更**:
1. 导入BacktestResult
2. 构建BacktestResult实例
3. 调用to_dict()返回（保持向后兼容）

**验收标准**:
- [ ] 返回结果与原格式完全兼容
- [ ] 现有回测命令正常工作
- [ ] 单元测试通过

---

### FP-042-003: run_batch_backtest适配

| 属性 | 值 |
|------|-----|
| 优先级 | P0 |
| 复杂度 | 中 |
| 依赖 | FP-042-001 |

**描述**: 修改run_batch_backtest支持extra_stats输出

**变更**:
1. 检测策略是否有get_extra_csv_headers方法
2. 动态扩展CSV_HEADERS
3. _format_row处理extra_stats字段

**验收标准**:
- [ ] 基础CSV格式不变
- [ ] extra_stats字段正确输出
- [ ] Strategy19的bear_warning跳过次数出现在CSV

---

### FP-042-004: get_extra_csv_headers方法

| 属性 | 值 |
|------|-----|
| 优先级 | P1 |
| 复杂度 | 低 |
| 依赖 | 无 |

**描述**: 在IStrategy中添加可选方法

**变更**:
1. IStrategy添加get_extra_csv_headers默认实现（返回空列表）
2. 文档说明用法

**验收标准**:
- [ ] 方法有默认实现
- [ ] 不破坏现有策略

---

### FP-042-005: Strategy19实现扩展字段

| 属性 | 值 |
|------|-----|
| 优先级 | P1 |
| 复杂度 | 低 |
| 依赖 | FP-042-003, FP-042-004 |

**描述**: Strategy19实现get_extra_csv_headers并填充extra_stats

**扩展字段**:
- skipped_bear_warning: bear_warning跳过次数
- consolidation_multiplier: 震荡期倍数配置

**验收标准**:
- [ ] CSV输出包含Strategy19特有字段
- [ ] 字段值正确

## 依赖关系图

```
FP-042-001 (BacktestResult)
    │
    ├──▶ FP-042-002 (Strategy16适配)
    │
    └──▶ FP-042-003 (run_batch_backtest)
              │
              └──▶ FP-042-005 (Strategy19扩展)
                        │
FP-042-004 ─────────────┘
(IStrategy方法)
```
