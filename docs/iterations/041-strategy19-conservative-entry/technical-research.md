# 技术调研: 策略19-保守入场策略

## 文档信息

| 字段 | 值 |
|------|-----|
| 迭代编号 | 041 |
| 创建日期 | 2026-01-13 |

## 1. 架构兼容性评估

### 1.1 现有架构分析

**策略16核心结构** (`strategy_adapter/strategies/strategy16_limit_entry.py`):
- 继承`IStrategy`接口
- 核心方法: `run_backtest(klines_df, initial_capital)`
- 买入挂单创建位置: 第342-386行 (Step 3)
- 周期判断: 通过`current_indicators['cycle_phase']`获取

**策略工厂** (`strategy_adapter/core/strategy_factory.py`):
- 使用`_auto_register_strategies()`自动注册
- 策略类型通过`StrategyFactory.register(type, class)`注册

### 1.2 兼容性结论

| 评估项 | 结果 | 说明 |
|--------|------|------|
| 继承复用 | ✅ | 可继承Strategy16LimitEntry |
| 周期判断 | ✅ | cycle_phase已在run_backtest中计算 |
| 工厂注册 | ✅ | 复用现有注册模式 |
| 回测CLI | ✅ | 复用run_strategy_backtest命令 |

## 2. 技术选型

### 2.1 实现方式

**方案A: 继承Strategy16LimitEntry** (推荐)
- 优点: 最小化代码改动，复用所有现有逻辑
- 缺点: 需要复制run_backtest方法进行修改
- 改动量: ~50行

**方案B: 策略16添加参数**
- 优点: 无需新类
- 缺点: 增加策略16复杂度，参数耦合
- 改动量: ~30行，但污染原有代码

**选择**: 方案A - 继承并重写

### 2.2 关键修改点

1. **bear_warning禁止挂单** (第344行附近):
```python
# 原逻辑
if (self._available_capital >= self.position_size and
    len(self._holdings) < self.max_positions):

# 新增条件
cycle_phase = current_indicators.get('cycle_phase')
if cycle_phase == 'bear_warning':
    continue  # 跳过挂单
```

2. **震荡期金额倍增** (第361行附近):
```python
# 原逻辑
self._pending_order = PendingOrder(amount=self.position_size, ...)

# 新逻辑
actual_position_size = self.position_size
if cycle_phase == 'consolidation':
    actual_position_size = self.position_size * self.consolidation_multiplier
```

## 3. 技术风险

| 风险 | 级别 | 缓解措施 |
|------|------|----------|
| 继承后代码同步 | 低 | 策略16稳定，不频繁修改 |
| 资金不足 | 低 | 震荡期检查available_capital |

## Q-Gate 3 检查

- [x] 架构兼容性已评估
- [x] 技术选型已确认 (继承Strategy16)
- [x] 技术风险已识别

**Q-Gate 3 通过**: 可进入P4阶段
