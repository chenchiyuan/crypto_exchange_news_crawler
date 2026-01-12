# 技术调研: 策略15-分批止盈优化策略

## 文档信息
- **版本**: 1.0
- **创建日期**: 2026-01-11
- **迭代编号**: 031

---

## 1. 架构兼容性评估

### 1.1 现有组件复用

| 组件 | 复用方式 | 说明 |
|------|----------|------|
| OptimizedEntryStrategy | 继承扩展 | 基于策略14代码结构 |
| LimitOrderManager | 完全复用 | 买入挂单管理 |
| LimitOrderPriceCalculator | 完全复用 | 价格计算逻辑 |

### 1.2 需要新增的组件

| 组件 | 职责 | 复杂度 |
|------|------|--------|
| SplitTakeProfitManager | 分批止盈挂单管理 | 中 |
| HoldingMerger | 持仓合并逻辑 | 低 |

### 1.3 代码结构

```
strategy_adapter/strategies/
├── optimized_entry_strategy.py     # 策略14（基础）
└── split_take_profit_strategy.py   # 策略15（新增）
```

---

## 2. 技术选型

### 2.1 分批止盈实现

**方案**: 在持仓数据结构中增加止盈档位追踪

```python
# 持仓数据结构扩展
holding = {
    'buy_price': Decimal,
    'quantity': Decimal,
    'remaining_quantity': Decimal,  # 剩余未止盈数量
    'tp_levels_filled': [False] * 5,  # 各档位是否已成交
    'tp_sell_orders': [],  # 挂出的止盈卖单
}
```

### 2.2 持仓合并实现

**方案**: 使用字典按价格分组

```python
def merge_holdings(self):
    """合并同价持仓"""
    price_groups = defaultdict(list)
    for order_id, holding in self._holdings.items():
        price_key = str(holding['buy_price'])
        price_groups[price_key].append((order_id, holding))

    # 合并同价持仓
    merged = {}
    for price_key, holdings in price_groups.items():
        if len(holdings) > 1:
            merged_holding = self._merge_group(holdings)
            merged[merged_holding['order_id']] = merged_holding
        else:
            merged[holdings[0][0]] = holdings[0][1]

    self._holdings = merged
```

---

## 3. 技术风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 止盈卖单数量过多 | 内存占用增加 | 每个持仓最多5个���单，可控 |
| 持仓合并时机问题 | 逻辑复杂度 | 每根K线结束时统一处理 |
| 精度问题 | 计算误差 | 使用Decimal全程计算 |

---

## 4. 性能考量

### 4.1 内存占用

- 策略14: 每个持仓1个数据结构
- 策略15: 每个持仓1个数据结构 + 最多5个卖单记录
- 增量: 约5倍卖单记录，但总量仍可控

### 4.2 计算复杂度

- 持仓合并: O(n)，n为持仓数量
- 止盈检查: O(n*5)，n为持仓数，5为止盈档位
- 整体: O(n)，线性复杂度

---

## Q-Gate 3: 通过

- [x] 架构兼容性已评估
- [x] 技术选型已确认
- [x] 技术风险已识别
