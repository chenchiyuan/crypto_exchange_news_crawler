# 技术调研: Empirical CDF V01 止盈止损策略

**迭代编号**: 035
**日期**: 2026-01-12
**状态**: P3完成

---

## 1. 架构兼容性评估

### 1.1 现有架构分析

```
strategy_adapter/
├── exits/                      # ✅ 可复用模块
│   ├── base.py                 # IExitCondition 接口
│   ├── stop_loss.py            # StopLossExit 参考实现
│   └── dynamic_exit_selector.py # 多状态Exit参考
├── strategies/
│   └── empirical_cdf_strategy.py # 现有入场逻辑
└── management/commands/
    └── run_strategy_backtest.py  # 回测入口
```

### 1.2 可复用组件

| 组件 | 复用方式 |
|------|----------|
| `IExitCondition` | 实现接口，继承抽象类 |
| `ExitSignal` | 使用现有数据结构 |
| `StopLossExit` | 参考实现模式 |
| `DynamicExitSelector` | 参考多状态判断模式 |

---

## 2. 技术选型

### 2.1 实现方案

**选择**: 继承 `IExitCondition` 接口，新建 `EmaStateExit` 类

**理由**:
- 与现有 Exit 组件保持一致
- 可组合使用（与 StopLossExit 配合）
- 支持动态切换逻辑

### 2.2 关键设计决策

| 决策点 | 选项 | 决策 | 理由 |
|--------|------|------|------|
| 状态跟踪 | 订单属性/独立类 | **订单属性** | 简化实现，避免复杂状态管理 |
| 信号触发 | 收盘价标记/即时成交 | **收盘价标记+开盘价成交** | 符合需求规范 |
| EMA 计算 | 复用/新建 | **复用现有** | ddps_z 已有的 EMA 计算 |

---

## 3. 关键实现点

### 3.1 EMA 状态判断

```python
def get_ema_state(ema7, ema25, ema99):
    if ema7 >= ema25 >= ema99:
        return 'bull_strong'
    elif ema7 <= ema25 <= ema99:
        return 'bear_strong'
    elif ema25 < ema99:
        return 'consolidation_down'
    else:
        return 'consolidation_up'
```

### 3.2 订单状态扩展

```python
# Order 模型需要添加
class Order:
    ema_state_at_entry: str      # 入场时的EMA状态
    ema_cross_triggered: bool    # EMA7下穿EMA25是否已触发
    ema_high_triggered: bool     # high突破EMA25/EMA99是否已触发
```

---

## 4. 技术风险

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| EMA 计算依赖外部服务 | 中 | 指标随K线数据一起传递 |
| 状态切换频繁 | 低 | 4h K线周期验证 |
| 回测性能 | 低 | 纯计算逻辑，无IO |

---

## 5. 结论

**技术可行性**: ✅ 可行
**架构兼容性**: ✅ 100%兼容
**预估开发时间**: ✅ 1-2天
