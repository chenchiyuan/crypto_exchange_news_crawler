# 任务清单 - 策略17

## 任务概览

| 任务ID | 任务名称 | 依赖 | 状态 |
|--------|----------|------|------|
| TASK-038-001 | 实现Strategy17BullWarningEntry类 | - | ✅ 已完成 |
| TASK-038-002 | 注册策略到__init__.py | TASK-038-001 | ✅ 已完成 |
| TASK-038-003 | 编写单元测试 | TASK-038-001 | ✅ 已完成 |
| TASK-038-004 | 回测验证 | TASK-038-002 | ✅ 已完成 |

---

## TASK-038-001: 实现Strategy17BullWarningEntry类

### 目标
创建`strategy_adapter/strategies/strategy17_bull_warning_entry.py`

### 验收标准
- [ ] 实现IStrategy接口
- [ ] 入场信号：检测consolidation→bull_warning，下一根K线open买入
- [ ] 止盈：复用EmaStateExit
- [ ] 止损：5%固定止损
- [ ] run_backtest()返回格式与策略16一致

### 实现要点

1. **指标计算**（复用策略16的`_calculate_indicators`）:
   - EMA7/25/99
   - P5、inertia_mid
   - β值、cycle_phase

2. **入场逻辑**:
   ```python
   # 检测入场信号
   if prev_phase == 'consolidation' and curr_phase == 'bull_warning':
       pending_entry_at_next_open = True

   # 执行入场
   if pending_entry_at_next_open:
       buy_price = kline['open']
       # 创建持仓记录
   ```

3. **止盈止损**（复用策略16逻辑）:
   - 止损：`low <= buy_price * 0.95`
   - 止盈：调用`EmaStateExit.check()`

---

## TASK-038-002: 注册策略到__init__.py

### 目标
在`strategy_adapter/strategies/__init__.py`中导出Strategy17

### 验收标准
- [ ] 可通过`from strategy_adapter.strategies import Strategy17BullWarningEntry`导入

### 实现要点
```python
from .strategy17_bull_warning_entry import Strategy17BullWarningEntry

__all__ = [
    # ... existing exports
    "Strategy17BullWarningEntry",
]
```

---

## TASK-038-003: 编写单元测试

### 目标
创建`strategy_adapter/tests/test_strategy17_bull_warning_entry.py`

### 验收标准
- [ ] 测试入场信号检测（consolidation→bull_warning触发，其他不触发）
- [ ] 测试买入价格为下一根K线的open
- [ ] 测试止损触发（low <= buy_price * 0.95）
- [ ] 测试止盈触发（EMA状态变化）

### 测试用例

1. `test_entry_signal_detection`: 验证仅consolidation→bull_warning触发入场
2. `test_buy_at_next_open`: 验证买入价格为下一根K线的open
3. `test_stop_loss`: 验证5%止损逻辑
4. `test_no_duplicate_entry`: 验证bull_warning持续期间不重复买入

---

## TASK-038-004: 回测验证

### 目标
使用真实数据验证策略17的正确性

### 验收标准
- [ ] 回测BTCUSDT 4h数据（2025年至今）
- [ ] 验证入场时机与预期一致
- [ ] 验证止盈止损触发正确
- [ ] 输出回测统计指标

### 执行命令
```bash
python manage.py run_strategy_backtest --strategy=strategy_17 --symbol=BTCUSDT --interval=4h
```

---

## 依赖关系图

```
TASK-038-001 (实现策略类)
      ↓
TASK-038-002 (注册导出)
      ↓
TASK-038-003 (单元测试) ←──→ TASK-038-004 (回测验证)
```

---

**创建时间**: 2026-01-12
**迭代编号**: 038
