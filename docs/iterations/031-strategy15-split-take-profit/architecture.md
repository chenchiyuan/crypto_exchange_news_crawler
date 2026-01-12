# 架构设计: 策略15-分批止盈优化策略

## 文档信息
- **版本**: 1.0
- **创建日期**: 2026-01-11
- **迭代编号**: 031

---

## 1. 组件设计

### 1.1 SplitTakeProfitStrategy

```python
class SplitTakeProfitStrategy(IStrategy):
    """
    分批止盈优化策略（策略15）

    基于策略14，新增：
    - 快速止损(3%)
    - 分批止盈(5档: 2%~6%)
    - 持仓合并(同价合并)
    """

    STRATEGY_ID = 'strategy_15'
    STRATEGY_NAME = '分批止盈优化策略'
    STRATEGY_VERSION = '1.0'

    def __init__(
        self,
        # === 沿用策略14参数 ===
        base_amount: Decimal = Decimal("100"),
        multiplier: float = 3.0,
        order_count: int = 5,
        first_gap: float = 0.04,
        interval: float = 0.01,
        first_order_discount: float = 0.02,
        # === 策略15新增参数 ===
        stop_loss_rate: float = 0.03,      # 快速止损3%
        tp_levels: int = 5,                 # 止盈档位数
        first_tp_rate: float = 0.02,        # 首档止盈2%
        tp_interval: float = 0.01,          # 止盈间隔1%
    ):
        ...
```

### 1.2 持仓数据结构

```python
# 扩展的持仓数据结构
holding = {
    # === 基础信息（沿用策略14）===
    'order_id': str,              # 订单ID（合并后新生成）
    'buy_price': Decimal,         # 买入价格
    'quantity': Decimal,          # 总数量
    'amount': Decimal,            # 总金额
    'buy_timestamp': int,         # 买入时间
    'kline_index': int,           # 买入K线索引

    # === 策略15新增 ===
    'remaining_quantity': Decimal,     # 剩余未止盈数量
    'tp_quantity_per_level': Decimal,  # 每档止盈数量（总量/5）
    'tp_levels_filled': List[bool],    # 各档位是否已成交 [False]*5
    'merged_from': List[str],          # 合并来源订单ID列表
}
```

### 1.3 止盈卖单数据结构

```python
# 挂出的止盈卖单
tp_sell_order = {
    'order_id': str,           # 卖单ID
    'parent_order_id': str,    # 对应的买单ID
    'tp_level': int,           # 止盈档位(0-4)
    'price': Decimal,          # 挂单价格
    'quantity': Decimal,       # 挂单数量
    'status': str,             # 'pending' / 'filled'
    'created_kline': int,      # 创建时的K线索引
}
```

---

## 2. 核心方法

| 方法 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `_calculate_tp_prices()` | 计算5档止盈价格 | buy_price | List[Decimal] |
| `_merge_holdings()` | 合并同价持仓 | - | - |
| `_create_tp_sell_orders()` | 创建止盈卖单 | holding | List[tp_order] |
| `_check_tp_sell_fills()` | 检查止盈卖单成交 | high | List[fill] |
| `_check_stop_loss()` | 检查止损触发 | low | List[fill] |
| `process_kline()` | 处理单根K线 | kline, indicators | result |

---

## 3. 数据流

```
K线数据
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      process_kline()                            │
├─────────────────────────────────────────────────────────────────┤
│ Step 1: 检查买入挂单成交                                         │
│         └─► 成交的订单加入 _holdings                             │
│                                                                  │
│ Step 2: 合并同价持仓 (每根K线结束时)                              │
│         └─► _merge_holdings()                                    │
│         └─► 合并后重新计算止盈档位                                │
│                                                                  │
│ Step 3: 检查止盈卖单成交 (high >= tp_price)                       │
│         └─► 成交的卖单释放资金，更新 remaining_quantity           │
│         └─► 全部止盈后从 _holdings 移除                          │
│                                                                  │
│ Step 4: 检查止损触发 (low <= stop_loss_price)                    │
│         └─► 全仓止损，释放资金，从 _holdings 移除                 │
│                                                                  │
│ Step 5: 更新/创建止盈卖单                                        │
│         └─► 对每个持仓创建未成交档位的卖单                        │
│                                                                  │
│ Step 6: 取消旧买入挂单，创建新买入挂单                            │
│         └─► 复用策略14逻辑                                       │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
返回 result (buy_fills, sell_fills, orders_placed, etc.)
```

---

## 4. 关键决策

| 决策 | 选项 | 决定 | 理由 |
|------|------|------|------|
| 代码复用 | 继承/复制 | 复制修改 | 避免继承复杂性，便于独立调整 |
| 止盈卖单管理 | 内存/持久化 | 内存 | 回测场景无需持久化 |
| 合并粒度 | 精确匹配/容差 | 精确匹配 | 相同价格才合并 |
| 止盈顺序 | 从低到高/并行 | 从低到高 | 先触发低档位，符合逻辑 |

---

## 5. 文件结构

```diff
strategy_adapter/
├── strategies/
│   ├── optimized_entry_strategy.py      # 策略14（不修改）
+   └── split_take_profit_strategy.py    # 策略15（新增）
├── configs/
│   ├── strategy14_optimized_entry.json  # 策略14配置（不修改）
+   └── strategy15_split_take_profit.json # 策略15配置（新增）
└── tests/
+   └── test_split_take_profit_strategy.py # 策略15测试（新增）
```

---

## 6. 配置示例

```json
{
  "project_name": "策略15-分批止盈优化策略回测",
  "description": "基于策略14，快速止损3%，分批止盈2%~6%，持仓合并",
  "version": "1.0",
  "created_at": "2026-01-11",
  "iteration": "031",

  "data_source": {
    "type": "csv_local",
    "csv_path": "/path/to/ETHUSDT-5m-2025-12.csv",
    "interval": "5m",
    "timestamp_unit": "microseconds"
  },

  "backtest_config": {
    "symbol": "ETHUSDT",
    "interval": "5m",
    "market_type": "csv_local",
    "initial_cash": 10000,
    "commission_rate": 0.001
  },

  "capital_management": {
    "mode": "shared",
    "position_size_mode": "fixed",
    "position_size": 2000,
    "max_positions": 100
  },

  "strategies": [
    {
      "id": "strategy_15",
      "name": "分批止盈优化策略",
      "type": "ddps-z",
      "enabled": true,
      "entry": {
        "strategy_id": 15,
        "base_amount": 2000,
        "multiplier": 3.0,
        "order_count": 5,
        "first_order_discount": 0.02,
        "first_gap": 0.04,
        "interval": 0.01,
        "stop_loss_rate": 0.03,
        "tp_levels": 5,
        "first_tp_rate": 0.02,
        "tp_interval": 0.01
      },
      "exits": []
    }
  ]
}
```

---

## Q-Gate 4: 通过

- [x] 组件设计已完成
- [x] 数据流已明确
- [x] 关键决策已做出
- [x] 文件结构已定义
