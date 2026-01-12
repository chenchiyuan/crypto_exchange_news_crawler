# 验收清单：滚动经验CDF信号策略

**迭代编号**: 034
**创建日期**: 2025-01-12
**状态**: Draft

---

## 一、因果与执行一致性 (Critical)

### 1.1 经验CDF因果性

- [ ] **CDF-001**: Prob_t 计算时，窗口 W_t = {X_{t-1}, X_{t-2}, ..., X_{t-M}}，**不含**当前样本 X_t
- [ ] **CDF-002**: 冷启动期（历史不足M）时，Prob_t = None，策略不得产生入场信号
- [ ] **CDF-003**: EMA25、EWMA μ/σ 均为因果计算，不使用未来数据

**验证方法**:
```python
# 测试用例：验证窗口排除当前样本
def test_cdf_excludes_current_sample():
    calc = EmpiricalCDFCalculator(cdf_window=100)
    # 更新100根K线
    for i in range(100):
        calc.update(Decimal(str(100 + i)))
    # 第101根时，prob应该有值（窗口满）
    result = calc.update(Decimal("200"))
    assert result['prob'] is not None
    # 窗口应该是前100个值，不含当前
```

---

### 1.2 订单时序一致性

- [ ] **ORD-001**: 所有订单在 bar t 收盘后挂出，最早在 bar t+1 成交
- [ ] **ORD-002**: 订单 valid_bar 正确设置为 placed_bar + 1
- [ ] **ORD-003**: 非 valid_bar 的订单自动过期撤销

**验证方法**:
```python
def test_order_validity_next_bar():
    manager = GFOBOrderManager()
    manager.initialize(Decimal("10000"))

    # bar 10 创建订单
    order = manager.create_buy_order(Decimal("100"), kline_index=10, timestamp=1000)

    # bar 10 不应该成交
    result = manager.match_orders(10, Decimal("95"), Decimal("105"), 1000)
    assert len(result['buy_fills']) == 0

    # bar 11 应该成交
    result = manager.match_orders(11, Decimal("95"), Decimal("105"), 1001)
    assert len(result['buy_fills']) == 1
```

---

### 1.3 撮合规则正确性

- [ ] **MATCH-001**: 买单撮合条件: `low[t] ≤ L` 即成交，成交价 = L
- [ ] **MATCH-002**: 卖单撮合条件: `high[t] ≥ U` 即成交，成交价 = U
- [ ] **MATCH-003**: 撮合顺序固定: 先撮合卖单，再撮合买单
- [ ] **MATCH-004**: 同bar不会出现买卖双成交（避免翻手套利）

**验证方法**:
```python
def test_buy_match_low_touch():
    # 买单价格 L = 100, K线 low = 98
    # 应该成交，因为 low (98) ≤ L (100)
    manager = GFOBOrderManager()
    manager.create_buy_order(close_price=Decimal("101"), ...)
    # L = 101 * 0.999 ≈ 100.9
    result = manager.match_orders(..., low=Decimal("100"), high=Decimal("110"))
    assert len(result['buy_fills']) == 1
    assert result['buy_fills'][0]['fill_price'] == Decimal("100.899")  # L

def test_sell_match_high_touch():
    # 卖单价格 U = 100, K线 high = 102
    # 应该成交，因为 high (102) ≥ U (100)
    pass

def test_match_order_sell_first():
    # 同时有买单和卖单待撮合
    # 应该先处理卖单
    pass
```

---

## 二、策略闭环正确性 (Critical)

### 2.1 入场逻辑

- [ ] **ENTRY-001**: 仅在 position = FLAT 时触发入场
- [ ] **ENTRY-002**: 仅在 Prob_t 有效（非None）时触发入场
- [ ] **ENTRY-003**: 仅在 Prob_t ≤ q_in（默认5）时触发入场
- [ ] **ENTRY-004**: 入场限价 L = close × (1 - δ_in)，δ_in 默认 0.001

**验证方法**:
```python
def test_entry_prob_threshold():
    strategy = EmpiricalCDFStrategy(q_in=5)
    # 模拟 Prob = 4 时应该触发入场
    # 模拟 Prob = 6 时不应该触发入场
    pass

def test_no_entry_when_long():
    # 已持仓时不应该触发入场
    pass

def test_no_entry_during_cold_start():
    # 冷启动期不应该触发入场
    pass
```

---

### 2.2 出场逻辑

- [ ] **EXIT-001**: 概率回归出场: position = LONG 且 Prob_t ≥ q_out（默认50）
- [ ] **EXIT-002**: 时间止损: 持仓bar数 ≥ H（默认48）
- [ ] **EXIT-003**: 灾难止损: 浮动收益率 ≤ -s（默认-5%）
- [ ] **EXIT-004**: 出场原因区分: PROB_REVERSION vs FAST_EXIT
- [ ] **EXIT-005**: FAST_EXIT 使用 δ_out_fast 定价，PROB_REVERSION 使用 δ_out

**验证方法**:
```python
def test_exit_prob_reversion():
    # Prob >= 50 时触发正常出场
    pass

def test_exit_time_stop():
    # 持仓 48 bar 后触发时间止损
    pass

def test_exit_disaster_stop():
    # 浮亏 5% 时触发灾难止损
    pass

def test_exit_pricing_modes():
    # FAST_EXIT 和 PROB_REVERSION 使用不同定价
    pass
```

---

## 三、指标计算正确性 (High)

### 3.1 EMA计算

- [ ] **EMA-001**: 第一根K线 EMA = close
- [ ] **EMA-002**: 增量更新公式: EMA_t = α × close + (1-α) × EMA_{t-1}，α = 2/(25+1)
- [ ] **EMA-003**: 计算结果与 pandas.ewm(span=25) 一致

**验证方法**:
```python
def test_ema_vs_pandas():
    import pandas as pd
    closes = [100, 101, 99, 102, ...]
    # 比较自实现 EMA 与 pd.ewm 结果
    df = pd.DataFrame({'close': closes})
    expected = df['close'].ewm(span=25, adjust=False).mean()
    # 误差 < 1e-8
```

---

### 3.2 EWMA均值/波动率

- [ ] **EWMA-001**: μ_t = α × D_t + (1-α) × μ_{t-1}，α = 2/(50+1)
- [ ] **EWMA-002**: σ²_t = α × (D_t - μ_t)² + (1-α) × σ²_{t-1}
- [ ] **EWMA-003**: σ_t = sqrt(max(σ²_t, 1e-12))，数值稳定
- [ ] **EWMA-004**: σ_t 始终 > 0

---

### 3.3 经验CDF

- [ ] **CDF-004**: Prob_t = 100 × (count(X_i ≤ X_t) / M)，范围 [0, 100]
- [ ] **CDF-005**: 窗口大小 M = 100
- [ ] **CDF-006**: X_t = (D_t - μ_t) / σ_t

---

## 四、日志审计完整性 (Medium)

### 4.1 Bar日志

- [ ] **LOG-001**: 每根K线记录完整字段: t, OHLC, EMA25, D, μ, σ, X, Prob, position, pending_buy, pending_sell
- [ ] **LOG-002**: 支持 CSV 输出
- [ ] **LOG-003**: 支持 JSON 输出

---

### 4.2 订单日志

- [ ] **LOG-004**: 每笔订单记录: order_id, type, placed_time, valid_bar, limit_price, reason, status
- [ ] **LOG-005**: 状态变更记录: PLACED → FILLED / EXPIRED
- [ ] **LOG-006**: 成交订单记录 fill_time, fill_price

---

### 4.3 交易日志

- [ ] **LOG-007**: 每笔闭环交易记录: entry_time, entry_price, exit_time, exit_price
- [ ] **LOG-008**: 信号追溯: entry_signal_time, entry_prob
- [ ] **LOG-009**: 出场原因: exit_reason (PROB_REVERSION / FAST_EXIT)
- [ ] **LOG-010**: 收益计算: gross_return = (exit_price - entry_price) / entry_price

---

## 五、资金管理正确性 (High)

- [ ] **FUND-001**: 挂买单时冻结资金
- [ ] **FUND-002**: 订单过期时解冻资金
- [ ] **FUND-003**: 卖出成交时释放资金（加上盈亏）
- [ ] **FUND-004**: 可用资金 + 冻结资金 = 总资金（不变式）
- [ ] **FUND-005**: 资金不足时不挂单

---

## 六、边界条件处理 (Medium)

- [ ] **EDGE-001**: 第一根K线正确初始化（EMA = close）
- [ ] **EDGE-002**: 冷启动期（前100根K线）Prob = None
- [ ] **EDGE-003**: 空数据集回测不崩溃
- [ ] **EDGE-004**: 单根K线回测正确
- [ ] **EDGE-005**: 持仓到回测结束时正确处理未平仓

---

## 七、性能指标 (Low)

- [ ] **PERF-001**: 10000根K线回测 < 5秒
- [ ] **PERF-002**: 内存占用稳定（无泄漏）
- [ ] **PERF-003**: X历史队列固定长度M（不无限增长）

---

## 验收签字

| 验收项 | 验收人 | 日期 | 状态 |
|--------|--------|------|------|
| 因果与执行一致性 | - | - | [ ] 待验收 |
| 策略闭环正确性 | - | - | [ ] 待验收 |
| 指标计算正确性 | - | - | [ ] 待验收 |
| 日志审计完整性 | - | - | [ ] 待验收 |
| 资金管理正确性 | - | - | [ ] 待验收 |
| 边界条件处理 | - | - | [ ] 待验收 |
| 性能指标 | - | - | [ ] 待验收 |

---

**验收标准**: 所有 Critical 和 High 优先级项必须通过，Medium 和 Low 允许部分延期。
