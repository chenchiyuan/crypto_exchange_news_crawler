# 任务计划: 回测结果协议抽象

## 文档信息

| 字段 | 值 |
|------|-----|
| 迭代编号 | 042 |
| 创建日期 | 2026-01-13 |

## 任务列表

### TASK-042-001: 创建BacktestResult数据类

| 属性 | 值 |
|------|-----|
| 优先级 | P0 |
| 状态 | 待开始 |
| 预估复杂度 | 低 |

**描述**: 创建`strategy_adapter/models/backtest_result.py`

**交付物**:
- [x] BacktestResult dataclass定义
- [x] to_dict()方法实现
- [x] 在models/__init__.py导出

**验收标准**:
```python
from strategy_adapter.models import BacktestResult
result = BacktestResult(total_orders=10, win_rate=60.0)
assert result.to_dict()['total_orders'] == 10
```

---

### TASK-042-002: Strategy16使用BacktestResult

| 属性 | 值 |
|------|-----|
| 优先级 | P0 |
| 状态 | 待开始 |
| 依赖 | TASK-042-001 |

**描述**: 修改Strategy16LimitEntry._generate_result()

**交付物**:
- [x] 导入BacktestResult
- [x] 构建BacktestResult实例
- [x] 调用to_dict()返回

**验收标准**:
- 现有回测命令正常工作
- 返回Dict格式与修改前兼容

---

### TASK-042-003: IStrategy添加get_extra_csv_headers

| 属性 | 值 |
|------|-----|
| 优先级 | P1 |
| 状态 | 待开始 |

**描述**: 在IStrategy中添加可选方法

**交付物**:
- [x] get_extra_csv_headers()方法定义
- [x] 默认返回空列表

---

### TASK-042-004: run_batch_backtest支持扩展字段

| 属性 | 值 |
|------|-----|
| 优先级 | P0 |
| 状态 | 待开始 |
| 依赖 | TASK-042-003 |

**描述**: 修改run_batch_backtest支持动态表头

**交付物**:
- [x] 获取策略的extra_csv_headers
- [x] 动态合并CSV表头
- [x] _format_row处理extra_stats

**验收标准**:
- 基础CSV格式不变
- 扩展字段正确输出

---

### TASK-042-005: Strategy19实现扩展字段

| 属性 | 值 |
|------|-----|
| 优先级 | P1 |
| 状态 | 待开始 |
| 依赖 | TASK-042-004 |

**描述**: Strategy19实现get_extra_csv_headers并使用extra_stats

**交付物**:
- [x] get_extra_csv_headers返回['skipped_bear_warning', 'consolidation_multiplier']
- [x] run_backtest填充extra_stats

**验收标准**:
```bash
python manage.py run_batch_backtest \
  --config strategy_adapter/configs/strategy19_conservative_entry.json \
  --symbols ETHUSDT
# CSV应包含skipped_bear_warning和consolidation_multiplier列
```

---

### TASK-042-006: 验证与文档

| 属性 | 值 |
|------|-----|
| 优先级 | P1 |
| 状态 | 待开始 |
| 依赖 | TASK-042-005 |

**描述**: 完整验证并创建实现报告

**交付物**:
- [x] Strategy16回测验证
- [x] Strategy19回测验证
- [x] implementation-report.md

## 执行顺序

```
TASK-042-001 (BacktestResult)
    │
    └──▶ TASK-042-002 (Strategy16适配)
              │
    ┌─────────┘
    │
TASK-042-003 (IStrategy方法)
    │
    └──▶ TASK-042-004 (run_batch_backtest)
              │
              └──▶ TASK-042-005 (Strategy19)
                        │
                        └──▶ TASK-042-006 (验证)
```
