# 功能点清单 - 策略18：周期趋势入场策略

## 文档信息
- **迭代编号**: 039
- **关联PRD**: docs/iterations/039-strategy18-cycle-trend-entry/prd.md
- **创建日期**: 2026-01-13
- **状态**: 待确认

---

## 功能点总览

| 编号 | 功能点 | 优先级 | 状态 |
|------|-------|--------|------|
| FP-039-001 | 42周期占比计算 | P0 | 待开发 |
| FP-039-002 | EMA25斜率判断 | P0 | 待开发 |
| FP-039-003 | 周期状态标记 | P0 | 待开发 |
| FP-039-004 | 买入条件判断 | P0 | 待开发 |
| FP-039-005 | 双挂单机制 | P0 | 待开发 |
| FP-039-006 | 周期状态止盈 | P0 | 待开发 |
| FP-039-007 | 固定比例止盈 | P0 | 待开发 |
| FP-039-008 | 固定比例止损 | P0 | 待开发 |

**P0功能点**: 8个
**P1功能点**: 0个

---

## P0 功能点详情

### FP-039-001: 42周期占比计算

**描述**: 统计最近42根K线的周期状态分布

**输入**:
- `cycle_phases`: List[str] - 周期状态列表（时间升序）

**输出**:
```python
{
    'bull_strong': 30,      # 强势上涨占比（%）
    'bull_warning': 10,     # 上涨预警占比（%）
    'consolidation': 40,    # 震荡占比（%）
    'bear_warning': 10,     # 下跌预警占比（%）
    'bear_strong': 10       # 强势下跌占比（%）
}
```

**实现方式**: 复用 `DDPSMonitorService._calculate_cycle_distribution()`

**验收标准**:
- [ ] 正确统计最近42根K线的各状态数量
- [ ] 占比计算为整数百分比
- [ ] 数据不足42根时使用实际数量

---

### FP-039-002: EMA25斜率判断

**描述**: 判断当前EMA25斜率是否为近6根K线最高/最低

**输入**:
- `ema25_series`: np.ndarray - EMA25序列

**输出**:
- `is_slope_highest`: bool - 斜率是否为近6根最高
- `is_slope_lowest`: bool - 斜率是否为近6根最低

**计算逻辑**:
```python
# 计算斜率序列
slopes = np.diff(ema25_series)  # slopes[i] = ema25[i+1] - ema25[i]

# 判断当前斜率是否为近6根最高
current_slope = slopes[-1]
recent_slopes = slopes[-6:]
is_slope_highest = current_slope == max(recent_slopes)
is_slope_lowest = current_slope == min(recent_slopes)
```

**验收标准**:
- [ ] 斜率计算正确（当前值 - 前一值）
- [ ] 窗口大小为6根K线
- [ ] 边界情况处理（数据不足6根）

---

### FP-039-003: 周期状态标记

**描述**: 根据占比和斜率综合判断当前周期状态

**输入**:
- `cycle_distribution`: Dict[str, float] - 周期占比
- `is_slope_highest`: bool - 斜率是否最高
- `is_slope_lowest`: bool - 斜率是否最低

**输出**:
- `cycle_state`: str - 'bull' | 'bear' | 'consolidation'

**判断逻辑**:
```python
bull_strong_pct = cycle_distribution.get('bull_strong', 0)
bear_strong_pct = cycle_distribution.get('bear_strong', 0)

if bull_strong_pct > 40 and is_slope_highest:
    return 'bull'  # 上涨周期
elif bear_strong_pct > 40 and is_slope_lowest:
    return 'bear'  # 下跌周期
else:
    return 'consolidation'  # 震荡周期
```

**验收标准**:
- [ ] 上涨周期：强势上涨占比>40% 且 斜率最高
- [ ] 下跌周期：强势下跌占比>40% 且 斜率最低
- [ ] 其他情况为震荡周期

---

### FP-039-004: 买入条件判断

**描述**: 判断是否满足买入条件

**前置条件**:
1. 当前周期状态 = 'bull'（上涨周期）
2. 可用资金 >= position_size × 2（两笔挂单）
3. 当前持仓数 < max_positions

**验收标准**:
- [ ] 只有上涨周期才允许买入
- [ ] 资金检查正确
- [ ] 持仓数量检查正确

---

### FP-039-005: 双挂单机制

**描述**: 在EMA7和EMA25价格各挂一笔限价买单

**挂单时机**: 当前K线结束时

**挂单价格**:
- 挂单1: `order_price_1 = ema7`
- 挂单2: `order_price_2 = ema25`

**成交判断**: 下根K线
```python
if next_kline.low <= order_price_1:
    # 挂单1成交
if next_kline.low <= order_price_2:
    # 挂单2成交
```

**资金管理**:
- 挂单时冻结 position_size
- 成交后扣除资金
- 未成交则释放冻结资金

**验收标准**:
- [ ] 两笔挂单价格分别为EMA7和EMA25
- [ ] 成交判断使用下根K线的low
- [ ] 资金冻结和释放逻辑正确
- [ ] 两笔挂单可同时成交

---

### FP-039-006: 周期状态止盈

**描述**: 非上涨周期时，EMA7下穿EMA25触发止盈

**触发条件**:
1. 当前周期状态 ≠ 'bull'
2. EMA7 下穿 EMA25（`ema7[i] < ema25[i]` 且 `ema7[i-1] >= ema25[i-1]`）
3. 该订单首次触发（避免重复）

**执行方式**:
- 标记触发，下一根K线以open价格卖出

**验收标准**:
- [ ] 只在非上涨周期检测
- [ ] 下穿判断逻辑正确
- [ ] 使用下一根K线的open价格卖出
- [ ] 每个订单只触发一次

---

### FP-039-007: 固定比例止盈

**描述**: 盈利超过10%时止盈

**触发条件**:
```python
profit_rate = (high - buy_price) / buy_price * 100
if profit_rate >= 10:
    sell_price = buy_price * 1.10  # 以10%止盈价卖出
```

**验收标准**:
- [ ] 使用K线high判断是否触及止盈价
- [ ] 止盈价 = 买入价 × 1.10
- [ ] 优先级高于周期状态止盈

---

### FP-039-008: 固定比例止损

**描述**: 亏损超过3%时止损

**触发条件**:
```python
loss_rate = (buy_price - low) / buy_price * 100
if loss_rate >= 3:
    sell_price = buy_price * 0.97  # 以3%止损价卖出
```

**验收标准**:
- [ ] 使用K线low判断是否触及止损价
- [ ] 止损价 = 买入价 × 0.97
- [ ] 优先级最高

---

## 卖出优先级

| 优先级 | 类型 | 触发条件 | 卖出价格 |
|-------|------|---------|---------|
| 1 | 止损 | low <= 买入价×0.97 | 买入价×0.97 |
| 2 | 止盈 | high >= 买入价×1.10 | 买入价×1.10 |
| 3 | 周期状态止盈 | 非上涨周期 + EMA7下穿EMA25 | 下根K线open |

---

## 依赖关系

```
FP-039-001 (42周期占比) ──┐
                         ├──► FP-039-003 (周期状态标记) ──► FP-039-004 (买入条件)
FP-039-002 (EMA25斜率) ──┘                                      │
                                                                 ▼
                                                          FP-039-005 (双挂单)
                                                                 │
                         ┌───────────────────────────────────────┘
                         ▼
              ┌──────────────────────┐
              │      持仓订单        │
              └──────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
   FP-039-008      FP-039-007      FP-039-006
    (止损3%)       (止盈10%)     (周期状态止盈)
```

---

## 复用组件

| 组件 | 来源 | 用途 |
|-----|------|-----|
| `BetaCycleCalculator` | ddps_z/calculators | 计算cycle_phases |
| `_calculate_cycle_distribution()` | DDPSMonitorService | 计算42周期占比 |
| `EMACalculator` | ddps_z/calculators | 计算EMA7/EMA25 |
| `PendingOrder` | strategy_adapter/models | 挂单数据结构 |
