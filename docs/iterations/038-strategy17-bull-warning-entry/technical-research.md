# 技术调研 - 策略17

## 1. 架构兼容性评估

### 1.1 现有组件分析

| 组件 | 路径 | 复用方式 | 兼容性 |
|------|------|----------|--------|
| BetaCycleCalculator | `ddps_z/calculators/beta_cycle_calculator.py` | 直接调用calculate()方法 | ✅ 完全兼容 |
| EmaStateExit | `strategy_adapter/exits/ema_state_exit.py` | 实例化后调用check()方法 | ✅ 完全兼容 |
| Strategy16LimitEntry | `strategy_adapter/strategies/strategy16_limit_entry.py` | 参考架构模式 | ✅ 可复用模式 |
| IStrategy | `strategy_adapter/interfaces/strategy.py` | 实现接口 | ✅ 标准接口 |

### 1.2 关键代码复用

#### BetaCycleCalculator的cycle_phase状态

```python
# 状态定义 (beta_cycle_calculator.py:29-34)
PHASE_LABELS = {
    'consolidation': '震荡',
    'bull_warning': '上涨预警',  # ← 策略17的入场信号
    'bull_strong': '强势上涨',
    'bear_warning': '下跌预警',
    'bear_strong': '强势下跌',
}

# 状态转换逻辑 (beta_cycle_calculator.py:130-133)
# consolidation → bull_warning: β > 600 且 β正在增加
if beta_display > bull_warning and beta_increasing:
    self.state = 'bull_warning'
```

#### EmaStateExit的止盈逻辑

```python
# 四种市场状态止盈 (ema_state_exit.py:124-182)
# - bull_strong: EMA7下穿EMA25
# - bear_strong: high突破EMA25
# - consolidation_down: high突破EMA99
# - consolidation_up: 挂单止盈2%
```

## 2. 技术选型

### 2.1 策略实现方案

**选定方案**: 继承IStrategy接口，参考Strategy16LimitEntry的架构

**理由**:
- 与现有策略保持一致的代码结构
- 复用成熟的回测流程和结果格式
- 便于后续集成到多策略回测框架

### 2.2 入场信号检测

**方案**: 在回测循环中检测cycle_phase状态转变

```python
# 伪代码
for i in range(1, len(klines)):
    prev_phase = cycle_phases[i-1]
    curr_phase = cycle_phases[i]

    # 检测首次进入bull_warning
    if curr_phase == 'bull_warning' and prev_phase == 'consolidation':
        # 标记：下一根K线以open价格买入
        pending_entry = True
```

## 3. 技术风险

### 3.1 低风险

| 风险 | 描述 | 缓解措施 |
|------|------|----------|
| 指标计算顺序 | cycle_phase依赖β值，β依赖EMA/ADX | 复用Strategy16的指标计算流程 |
| 边界条件 | 首根K线无法判断状态转变 | 从第1根K线开始遍历 |

### 3.2 无高风险项

所有核心逻辑均有成熟组件可复用，无需新技术探索。

## 4. 结论

✅ **技术可行性: 高**

- 所有核心功能均可复用现有组件
- 代码结构与策略16高度相似
- 预计开发周期: 1-1.5天

---

**创建时间**: 2026-01-12
**迭代编号**: 038
