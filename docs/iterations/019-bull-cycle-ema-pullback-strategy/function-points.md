# 功能点清单: 策略5 - 强势上涨周期EMA25回调策略

**迭代编号**: 019
**创建时间**: 2026-01-07

---

## 功能点列表

### 后端功能

| ID | 功能点 | 优先级 | 描述 |
|----|--------|--------|------|
| BE-001 | 创建策略类 | P0 | 新建 BullCycleEMAPullbackStrategy 策略类 |
| BE-002 | 入场信号生成 | P0 | 实现 generate_buy_signals 方法 |
| BE-003 | 止盈信号生成 | P0 | 实现 P95 止盈逻辑 |
| BE-004 | 止损信号生成 | P0 | 实现 5% 止损逻辑 |
| BE-005 | 策略工厂注册 | P0 | 在 StrategyFactory 中注册新策略类型 |
| BE-006 | 指标计算集成 | P0 | 集成 cycle_phase 指标计算 |

### 配置功能

| ID | 功能点 | 优先级 | 描述 |
|----|--------|--------|------|
| CFG-001 | 策略配置文件 | P0 | 创建策略5的项目配置文件 |

### 回测功能

| ID | 功能点 | 优先级 | 描述 |
|----|--------|--------|------|
| BT-001 | 运行回测 | P0 | 执行 2025-01-01 至今的 ETHUSDT 回测 |

---

## 功能点详情

### BE-001: 创建策略类

**位置**: `strategy_adapter/adapters/bull_cycle_ema_pullback.py`（新建）

**类定义**:
```python
class BullCycleEMAPullbackStrategy(IStrategy):
    """
    策略5: 强势上涨周期EMA25回调策略

    入场: cycle_phase == 'bull_strong' AND low <= ema25 <= high
    出场: P95止盈 OR 5%止损
    """
```

**验收条件**:
- [ ] 实现 IStrategy 接口
- [ ] 正确处理 cycle_phase 指标

---

### BE-002: 入场信号生成

**方法**: `generate_buy_signals(klines, indicators)`

**逻辑**:
```python
for i in range(len(klines)):
    if (indicators['cycle_phase'][i] == 'bull_strong' and
        klines['low'][i] <= indicators['ema25'][i] <= klines['high'][i]):
        # 生成买入信号，价格为 close
        signals.append({
            'timestamp': klines['open_time'][i],
            'price': klines['close'][i],
            'reason': '强势上涨EMA回调',
            'strategy_id': '5'
        })
```

---

### BE-003: 止盈信号生成

**方法**: `generate_sell_signals(klines, indicators, open_orders)`

**逻辑**:
```python
for order in open_orders:
    for i in range(buy_idx + 1, len(klines)):
        if klines['high'][i] >= indicators['p95'][i]:
            # 触发P95止盈
            signals.append({
                'timestamp': klines['open_time'][i],
                'price': indicators['p95'][i],
                'order_id': order.id,
                'reason': 'P95止盈',
                'strategy_id': 'p95_take_profit'
            })
            break
```

---

### BE-004: 止损信号生成

**逻辑**:
```python
for order in open_orders:
    stop_loss_price = order.entry_price * Decimal("0.95")
    for i in range(buy_idx + 1, len(klines)):
        if klines['low'][i] <= stop_loss_price:
            # 触发5%止损
            signals.append({
                'timestamp': klines['open_time'][i],
                'price': stop_loss_price,
                'order_id': order.id,
                'reason': '5%止损',
                'strategy_id': 'stop_loss'
            })
            break
```

---

### BE-005: 策略工厂注册

**位置**: `strategy_adapter/core/strategy_factory.py`

**修改**:
```python
def _auto_register_strategies():
    # ... 现有代码 ...

    # 注册策略5
    try:
        from strategy_adapter.adapters.bull_cycle_ema_pullback import (
            BullCycleEMAPullbackStrategy
        )
        StrategyFactory.register("bull-cycle-ema-pullback", BullCycleEMAPullbackStrategy)
    except ImportError as e:
        logger.warning(f"无法注册策略5: {e}")
```

---

### BE-006: 指标计算集成

**需求**: 在回测执行时计算 cycle_phase 指标

**修改位置**: `strategy_adapter/core/strategy_adapter.py`

**逻辑**:
- 调用 `BetaCycleCalculator` 计算 cycle_phase
- 将 cycle_phase 添加到 indicators 字典

---

### CFG-001: 策略配置文件

**位置**: `strategy_adapter/configs/strategy5_bull_cycle.json`

**内容**:
```json
{
  "project_name": "策略5-强势上涨EMA回调",
  "description": "在强势上涨周期中捕捉EMA25回调买入机会",
  "version": "1.0",

  "backtest_config": {
    "symbol": "ETHUSDT",
    "interval": "4h",
    "market_type": "futures",
    "start_date": "2025-01-01",
    "end_date": null,
    "initial_cash": 10000,
    "commission_rate": 0.001
  },

  "capital_management": {
    "mode": "shared",
    "position_size_mode": "fixed",
    "position_size": 100,
    "max_positions": 10
  },

  "strategies": [
    {
      "id": "strategy_5",
      "name": "强势上涨EMA回调",
      "type": "bull-cycle-ema-pullback",
      "enabled": true,
      "entry": {
        "cycle_phase": "bull_strong",
        "ema_period": 25
      },
      "exits": [
        {
          "type": "p95_take_profit",
          "params": {}
        },
        {
          "type": "stop_loss",
          "params": {"percentage": 5}
        }
      ]
    }
  ]
}
```

---

## 依赖关系

```
BE-006 (指标计算) ──► BE-001 (策略类)
                          │
                          ├──► BE-002 (入场)
                          │
                          ├──► BE-003 (止盈)
                          │
                          └──► BE-004 (止损)
                                  │
BE-005 (工厂注册) ◄────────────────┘
                                  │
CFG-001 (配置) ◄──────────────────┘
                                  │
BT-001 (回测) ◄───────────────────┘
```

---

**创建人**: PowerBy Product
**最后更新**: 2026-01-07
