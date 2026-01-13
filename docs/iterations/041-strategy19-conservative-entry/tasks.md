# 任务清单: 策略19-保守入场策略

## 文档信息

| 字段 | 值 |
|------|-----|
| 迭代编号 | 041 |
| 创建日期 | 2026-01-13 |
| 预估总工时 | 2小时 |

## 任务列表

### Phase 1: 核心实现 (1.5小时)

#### TASK-041-001: 创建Strategy19ConservativeEntry类
**状态**: 待开始
**预估**: 1小时

**描述**:
创建策略19核心类，继承Strategy16LimitEntry，实现保守入场逻辑

**验收标准**:
- [ ] 文件 `strategy_adapter/strategies/strategy19_conservative_entry.py` 已创建
- [ ] 继承 Strategy16LimitEntry
- [ ] 新增 consolidation_multiplier 参数（默认3）
- [ ] bear_warning 周期跳过买入挂单
- [ ] consolidation 周期使用 position_size × multiplier
- [ ] STRATEGY_ID = 'strategy_19'

**实现要点**:
1. 复制 Strategy16LimitEntry.run_backtest() 方法
2. 在 Step 3 (创建买入挂单) 前添加 bear_warning 检查
3. 在创建 PendingOrder 时使用动态金额

---

#### TASK-041-002: 策略注册和导出
**状态**: 待开始
**预估**: 15分钟
**依赖**: TASK-041-001

**描述**:
将策略19注册到策略工厂，并在模块中导出

**验收标准**:
- [ ] `strategy_adapter/strategies/__init__.py` 导出 Strategy19ConservativeEntry
- [ ] `strategy_adapter/core/strategy_factory.py` 注册 strategy-19-conservative-entry
- [ ] 工厂创建逻辑支持 consolidation_multiplier 参数

---

### Phase 2: 验证测试 (30分钟)

#### TASK-041-003: 回测验证
**状态**: 待开始
**预估**: 30分钟
**依赖**: TASK-041-002

**描述**:
使用回测命令验证策略19功能正确性

**验收标准**:
- [ ] `run_strategy_backtest --strategy=strategy_19` 可正常执行
- [ ] bear_warning 周期无新买入订单（通过日志验证）
- [ ] consolidation 周期订单金额为 3 倍（通过日志验证）
- [ ] 与策略16对比，确认行为差异符合预期

**验证命令**:
```bash
python manage.py run_strategy_backtest \
  --symbol=BTCUSDT \
  --strategy=strategy_19 \
  --start=2025-01-01 \
  --end=2025-01-31
```

---

## 任务依赖图

```
TASK-041-001 (核心实现)
      │
      ▼
TASK-041-002 (注册导出)
      │
      ▼
TASK-041-003 (回测验证)
```

## 完成标准

| 检查项 | 标准 |
|--------|------|
| 代码质量 | 无 linter 警告 |
| 功能完整 | 4个P0功能点全部实现 |
| 回测可用 | CLI命令可正常执行 |

## Q-Gate 5 检查

- [x] 任务分解已完成（3个任务）
- [x] 任务粒度合适（每个任务≤1小时）
- [x] 依赖关系已明确
- [x] 验收标准已定义

**Q-Gate 5 通过**: 可交付开发实现
