# 策略18：周期趋势入场策略

## 文档信息
- **迭代编号**: 039
- **迭代名称**: 策略18-周期趋势入场
- **创建日期**: 2026-01-13
- **状态**: 需求定义中
- **优先级**: P0

---

## 1. 核心价值（一句话）

基于42周期占比和EMA25斜率双重确认的趋势跟踪策略，在上涨周期使用EMA7/EMA25双挂单入场，配合周期状态止盈和固定比例止盈止损。

---

## 2. 背景与动机

### 2.1 问题陈述
现有策略（如策略16、17）主要基于单一入场条件，缺乏对宏观周期趋势的综合判断。需要一个能够：
1. 综合判断市场周期状态（上涨/下跌/震荡）
2. 在趋势确认后才入场
3. 使用多价位挂单提高成交概率

### 2.2 目标用户
量化交易回测系统用户

### 2.3 预期收益
- 通过周期占比过滤，减少震荡期的无效交易
- 通过EMA斜率确认，提高趋势判断准确性
- 通过双挂单机制，提高入场成交率

---

## 3. 功能需求

### 3.1 周期状态判断

#### FP-039-001: 42周期占比计算
**描述**: 统计最近42根K线的周期状态分布

**周期状态类别**（复用现有BetaCycleCalculator）:
- `bull_strong`: 强势上涨
- `bull_warning`: 上涨预警
- `consolidation`: 震荡
- `bear_warning`: 下跌预警
- `bear_strong`: 强势下跌

**计算方式**: 复用 `DDPSMonitorService._calculate_cycle_distribution()` 方法

#### FP-039-002: EMA25斜率判断
**描述**: 判断EMA25斜率是否为近6根K线最高

**判断逻辑**:
```python
# 计算EMA25斜率（当前值与前一根的差值）
slope[i] = ema25[i] - ema25[i-1]

# 判断当前斜率是否为近6根最高
is_highest = slope[i] == max(slope[i-5:i+1])
```

#### FP-039-003: 周期状态标记
**描述**: 根据占比和斜率综合判断当前周期状态

| 周期状态 | 判断条件 |
|---------|---------|
| **上涨周期** | 强势上涨占比 > 40% **且** EMA25斜率为近6根最高 |
| **下跌周期** | 强势下跌占比 > 40% **且** EMA25斜率为近6根最低 |
| **震荡周期** | 不满足上述条件 |

### 3.2 买入策略

#### FP-039-004: 买入条件
**描述**: 只有上涨周期才可买入

**前置条件**:
- 当前周期状态 = 上涨周期
- 有可用资金
- 持仓未满

#### FP-039-005: 双挂单机制
**描述**: 当前K线结束时，在EMA7和EMA25价格各挂一笔限价买单

**挂单逻辑**:
```python
# 当前K线结束时
order_price_1 = ema7  # 第一笔挂单价格
order_price_2 = ema25  # 第二笔挂单价格

# 下根K线判断成交
if next_kline.low <= order_price_1:
    # 第一笔挂单成交，买入价 = order_price_1
if next_kline.low <= order_price_2:
    # 第二笔挂单成交，买入价 = order_price_2
```

**资金管理**:
- 每笔挂单金额：position_size（默认1000 USDT）
- 两笔挂单独立计算，可同时成交
- 挂单时冻结资金，未成交则释放

### 3.3 卖出策略

#### FP-039-006: 周期状态止盈
**描述**: 当前状态非上涨周期时，遇到第一根EMA7下穿EMA25，在第二根K线open止盈

**触发条件**:
1. 当前周期状态 ≠ 上涨周期
2. EMA7 下穿 EMA25（当前K线 EMA7 < EMA25 且 前一根K线 EMA7 >= EMA25）
3. 标记触发，下一根K线以open价格卖出

**实现逻辑**:
```python
# 检测EMA7下穿EMA25
cross_down = (ema7[i] < ema25[i]) and (ema7[i-1] >= ema25[i-1])

# 非上涨周期 + 首次下穿
if cycle_state != 'bull' and cross_down and not order.metadata.get('cross_triggered'):
    order.metadata['cross_triggered'] = True
    # 标记下一根K线以open卖出
```

#### FP-039-007: 固定比例止盈
**描述**: 盈利超过10%时止盈

**触发条件**:
```python
profit_rate = (current_price - buy_price) / buy_price * 100
if profit_rate >= 10:
    # 触发止盈，以当前价格卖出
```

#### FP-039-008: 固定比例止损
**描述**: 亏损超过3%时止损

**触发条件**:
```python
loss_rate = (buy_price - current_price) / buy_price * 100
if loss_rate >= 3:
    # 触发止损，以止损价卖出
    sell_price = buy_price * (1 - 0.03)
```

### 3.4 卖出优先级

**优先级顺序**（先到先触发）:
1. **止损**（3%）- 最高优先级，保护本金
2. **止盈**（10%）- 锁定利润
3. **周期状态止盈** - 趋势反转信号

---

## 4. 配置参数

| 参数名 | 类型 | 默认值 | 说明 |
|-------|------|-------|------|
| `position_size` | Decimal | 1000 | 单笔仓位金额（USDT） |
| `max_positions` | int | 10 | 最大持仓数量 |
| `cycle_window` | int | 42 | 周期占比统计窗口 |
| `bull_threshold` | float | 40 | 上涨周期占比阈值（%） |
| `bear_threshold` | float | 40 | 下跌周期占比阈值（%） |
| `slope_window` | int | 6 | EMA25斜率比较窗口 |
| `take_profit_pct` | float | 10 | 止盈比例（%） |
| `stop_loss_pct` | float | 3 | 止损比例（%） |

---

## 5. 范围边界

### 5.1 In-Scope（本迭代实现）
- [x] 42周期占比计算（复用现有方法）
- [x] EMA25斜率判断
- [x] 周期状态标记（上涨/下跌/震荡）
- [x] 双挂单买入机制（EMA7 + EMA25）
- [x] 周期状态止盈
- [x] 固定比例止盈（10%）
- [x] 固定比例止损（3%）
- [x] 回测支持

### 5.2 Out-of-Scope（本迭代不实现）
- [ ] 实盘交易支持
- [ ] 做空策略
- [ ] 动态止盈止损
- [ ] Web界面展示

---

## 6. 验收标准

### AC-039-001: 周期状态判断正确
- 给定42根K线的cycle_phases，能正确计算各状态占比
- 给定EMA25序列，能正确判断斜率是否为近6根最高
- 综合判断周期状态符合预期

### AC-039-002: 买入逻辑正确
- 只有上涨周期才触发买入信号
- 双挂单价格分别为EMA7和EMA25
- 下根K线low <= 挂单价时成交

### AC-039-003: 卖出逻辑正确
- 止损优先级最高（3%）
- 止盈次之（10%）
- 周期状态止盈：非上涨周期 + EMA7下穿EMA25 + 下根K线open卖出

### AC-039-004: 回测结果正确
- 回测统计指标计算正确
- 订单记录完整

---

## 7. 技术约束

- 复用现有 `BetaCycleCalculator` 计算cycle_phases
- 复用现有 `DDPSMonitorService._calculate_cycle_distribution()` 计算占比
- 遵循现有策略类接口 `IStrategy`
- 配置文件格式与现有策略一致

---

## 8. 相关文档

- 策略16实现: `strategy_adapter/strategies/strategy16_limit_entry.py`
- 策略17实现: `strategy_adapter/strategies/strategy17_bull_warning_entry.py`
- 周期计算器: `ddps_z/calculators/beta_cycle_calculator.py`
- 周期占比计算: `ddps_z/services/ddps_monitor_service.py:363`
