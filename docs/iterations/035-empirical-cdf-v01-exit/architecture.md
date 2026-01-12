# 架构设计: Empirical CDF V01 止盈止损策略

**迭代编号**: 035
**日期**: 2026-01-12
**状态**: P4完成

---

## 1. 组件架构

```
strategy_adapter/
├── exits/
│   ├── __init__.py              # 导出 EmaStateExit
│   ├── base.py                  # (不变) IExitCondition
│   ├── stop_loss.py             # (不变) 10%止损
│   └── ema_state_exit.py        # 🆕 EMA状态止盈策略
├── strategies/
│   └── empirical_cdf_strategy.py # (修改) 支持自定义Exit
├── configs/
│   └── strategy_empirical_cdf_v01.json # 🆕 策略配置
```

---

## 2. EmaStateExit 组件设计

### 2.1 类图

```
IExitCondition
    ↑
    ├── check(kline, indicators) -> Optional[ExitSignal]
    ├── get_type() -> str
    └── get_priority() -> int
            ↑
            EmaStateExit
```

### 2.2 核心逻辑

```python
class EmaStateExit(IExitCondition):
    """EMA状态止盈策略"""

    def check(self, order, kline, indicators, current_timestamp):
        ema7 = indicators['ema7']
        ema25 = indicators['ema25']
        ema99 = indicators['ema99']
        high = kline['high']
        close = kline['close']

        state = self._get_ema_state(ema7, ema25, ema99)

        # 强势上涨: EMA7下穿EMA25触发
        if state == 'bull_strong':
            if ema7 <= ema25 and not order.ema_cross_triggered:
                order.ema_cross_triggered = True
                return ExitSignal(..., exit_type='ema_bull_take_profit')

        # 强势下跌/震荡下跌: high突破EMA
        elif state in ['bear_strong', 'consolidation_down']:
            threshold = ema99 if state == 'consolidation_down' else ema25
            if high > threshold and not order.ema_high_triggered:
                order.ema_high_triggered = True
                return ExitSignal(..., exit_type='ema_bear_take_profit')

        return None
```

---

## 3. 数据流

```
K线数据 → 指标计算 → EMA状态判断 → Exit检查
              ↓              ↓
         indicators    EmaStateExit.check()
              ↓              ↓
           ema7,        → ExitSignal
           ema25,       → StopLossExit (并行检查)
           ema99
```

---

## 4. Order 模型扩展

```python
# 在 Order 类中添加（如果不存在）
class Order:
    # ... 现有字段 ...

    # EMA状态跟踪字段
    ema_cross_triggered: bool = False   # EMA7下穿EMA25标记
    ema_high_triggered: bool = False    # high突破EMA标记
```

---

## 5. 配置示例

```json
{
  "strategies": [{
    "id": "empirical_cdf_v01",
    "type": "empirical-cdf",
    "exit": {
      "type": "ema_state",
      "stop_loss_pct": 10.0
    }
  }]
}
```

---

## 6. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `strategy_adapter/exits/ema_state_exit.py` | 新增 | EMA状态止盈策略 |
| `strategy_adapter/exits/__init__.py` | 修改 | 导出新组件 |
| `strategy_adapter/models/order.py` | 修改 | 添加状态跟踪字段 |
| `strategy_adapter/configs/strategy_empirical_cdf_v01.json` | 新增 | 策略配置 |
