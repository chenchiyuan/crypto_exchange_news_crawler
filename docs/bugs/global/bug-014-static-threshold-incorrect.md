# Bug-014: 静态阈值显示不正确

**Bug ID**: bug-014-static-threshold-incorrect
**创建时间**: 2026-01-06
**状态**: 需求对齐中
**相关迭代**: 010 - DDPS-Z 惯性预测扇面系统

---

## 阶段1：需求对齐与澄清 🔍

### 1.1 问题背景

在实现Bug-013修复（历史扇面线条显示）和hover动态显示功能后，用户发现HUD面板中的静态阈值显示不正确：
- **当前表现**：P95固定显示为1.6400，P5固定显示为-1.6400
- **用户期望**：P95和P5应该显示实际的价格阈值

### 1.2 相关文档

**PRD 需求**（docs/iterations/010-ddps-z-inertia-fan/prd.md）：

```markdown
### 2.3 静态阈值线

**作用**：
- P95（95%分位数）：长期历史极值上界
- P5（5%分位数）：长期历史极值下界
```

**Architecture 设计**（docs/iterations/010-ddps-z-inertia-fan/architecture.md）：

```markdown
### 3.1 静态阈值计算

P95 = EMA × (1 + Z_p95 × σ)
P5 = EMA × (1 + Z_p5 × σ)

其中：
- Z_p95 = 1.645（95%分位数对应的Z值）
- Z_p5 = -1.645（5%分位数对应的Z值）
- σ 是偏离率的EWMA标准差
```

### 1.3 需求理解确认

#### 正确情况的量化表达

**功能表现**：
- P95和P5应该是**价格值**（如：P95: 3233.72, P5: 2978.99）
- 而不是**Z-Score值**（1.6400, -1.6400）

**业务逻辑**：
- P95 = EMA × (1 + 1.645 × σ)
- P5 = EMA × (1 - 1.645 × σ)
- 这是基于当前EMA和历史波动率计算的价格区间

**数据状态**：
- 每根K线应该有独立的P95/P5值（因为EMA和σ随时间变化）
- Hover时应显示该K线对应时刻的P95/P5

**边界条件**：
- 数据不足时（前180根K线）：可能无法计算，显示N/A
- σ=0时：P95=P5=EMA

**异常处理**：
- EMA为null：无法计算，显示N/A
- σ为null：无法计算，显示N/A

### 1.4 用户确认需求理解

**请确认**：

1. ✅ P95和P5应该显示的是**价格值**（如3233.72），而不是Z-Score值（1.6400）？
2. ✅ 每根K线应该有独立的P95/P5值，hover时动态显示？

---

## 阶段2：问题现象描述

### 2.1 复现步骤

1. 启动Django服务器：`python manage.py runserver`
2. 访问：`http://127.0.0.1:8000/ddps-z/detail/?symbol=BTCUSDT&interval=4h&market_type=futures`
3. 观察右上角HUD面板的"静态阈值"部分

### 2.2 实际表现

- ❌ P95: 1.6400（固定值）
- ❌ P5: -1.6400（固定值）
- ❌ Hover到不同K线时，P95/P5不变化

### 2.3 预期表现

- ✅ P95: 价格值（如3233.72）
- ✅ P5: 价格值（如2978.99）
- ✅ Hover到不同K线时，P95/P5应随之变化

### 2.4 影响范围

- **严重程度**：中等（显示错误，但不影响核心计算）
- **用户体验**：高（误导用户对价格区间的判断）
- **数据准确性**：无影响（计算本身正确，只是显示错误）

---

## 阶段3：三层立体诊断分析 🔬

### 3.1 表现层诊断

**前端渲染逻辑检查**：

📝 **文件**: `ddps_z/templates/ddps_z/detail.html:1087-1097`

```javascript
// 更新静态阈值
if (klineData.p95 !== null && klineData.p95 !== undefined) {
    document.getElementById('hud-p95').textContent = this.formatPrice(klineData.p95);
} else {
    document.getElementById('hud-p95').textContent = 'N/A';
}

if (klineData.p5 !== null && klineData.p5 !== undefined) {
    document.getElementById('hud-p5').textContent = this.formatPrice(klineData.p5);
} else {
    document.getElementById('hud-p5').textContent = 'N/A';
}
```

**诊断结论**：
- ✅ 前端正确渲染了接收到的 `klineData.p95` 和 `klineData.p5`
- ✅ 格式化函数 `formatPrice()` 正常工作
- ❌ 但接收到的数据本身就是错误的（1.6400, -1.6400）

### 3.2 逻辑层诊断

**服务层逻辑检查**：

📝 **文件**: `ddps_z/services/chart_data_service.py:688-690`

```python
# 获取静态分位带
quantile_bands = series.get('quantile_bands', {})
p95_value = quantile_bands.get('p95')  # ← 得到 1.64（Z-Score值）
p5_value = quantile_bands.get('p5')    # ← 得到 -1.64（Z-Score值）
```

**然后在第778-779行**：

```python
kline_data.append({
    't': fan_timestamps[i],
    'p95': p95_value if p95_value is not None else None,  # ← 直接使用1.64
    'p5': p5_value if p5_value is not None else None,      # ← 直接使用-1.64
    # ...
})
```

**诊断结论**：
- ❌ 服务层直接使用了 `quantile_bands` 中的 Z-Score 值（1.64, -1.64）
- ❌ 没有将 Z-Score 转换为实际价格
- ❌ 所有K线使用同一个固定值（没有基于各自的EMA和σ计算）

### 3.3 数据层诊断

**数据可用性检查**：

📝 **文件**: `ddps_z/calculators/zscore_calculator.py:124-143`

```python
def calculate_quantile_bands(self) -> dict:
    """
    计算分位带的Z值边界

    Returns:
        {
            'p5': -1.64,   # 5%分位
            'p10': -1.28,  # 10%分位
            'p50': 0,      # 50%分位
            'p90': 1.28,   # 90%分位
            'p95': 1.64,   # 95%分位
        }
    """
    return {
        'p5': self.QUANTILE_THRESHOLDS['oversold_5'],    # -1.64
        'p10': self.QUANTILE_THRESHOLDS['oversold_10'],  # -1.28
        'p50': self.QUANTILE_THRESHOLDS['neutral'],      # 0
        'p90': self.QUANTILE_THRESHOLDS['overbought_90'], # 1.28
        'p95': self.QUANTILE_THRESHOLDS['overbought_95'], # 1.64
    }
```

**诊断结论**：
- ✅ `quantile_bands` 返回的是**常量Z-Score值**（用于概率带计算）
- ✅ 这些值在整个系统中是固定的（基于正态分布）
- ❌ 但这些值不是价格，不应该直接用于HUD显示

**可用数据检查**：

在 `_generate_fan_data()` 方法中，我们已经有了计算P95/P5所需的所有数据：
- ✅ `ema_series[i]`：每根K线的EMA值
- ✅ `ewma_std_series[i]`：每根K线的σ值
- ✅ Z-Score常量：1.645（95%分位）、-1.645（5%分位）

### 3.4 三层联动验证

#### 跨层一致性检查
- 前端期望：接收价格值（如3233.72）
- 服务层提供：Z-Score值（1.64）
- 数据层返回：Z-Score常量
- **结论**：❌ 数据提供与前端需求不一致

#### 反向排除验证
- ✅ 不是前端渲染问题（前端正确显示了接收到的数据）
- ✅ 不是数据不足问题（EMA和σ数据都存在）
- ❌ **根因**：服务层误将Z-Score常量当作价格值使用

#### 整体检查
- ✅ 系统按现有代码正确运行
- ❌ 现有代码逻辑错误（混淆了Z-Score和价格）

### 3.5 根因定位

**诊断结论**：

这是一个**数据类型混淆**导致的逻辑错误：

1. **数据层设计意图**：`quantile_bands` 返回Z-Score常量（1.64, -1.64），用于概率带计算
   - 在 `chart_data_service.py:467-532` 的 `_calculate_probability_bands()` 方法中正确使用

2. **Bug引入点**：在 Bug-013 修复和hover功能实现时，错误地将这些Z-Score常量直接赋值给 `kline_data.p95/p5`
   - 应该为每根K线计算实际的价格阈值

3. **修复方向**：在 `_generate_fan_data()` 方法的循环中，为每根K线计算真实的P95/P5价格：
   ```python
   p95_price = ema_series[i] * (1 + 1.645 * ewma_std_series[i])
   p5_price = ema_series[i] * (1 - 1.645 * ewma_std_series[i])
   ```

---

## 阶段4：修复方案确认

### 4.1 方案选项

#### 方案A：在循环中逐K线计算P95/P5价格（推荐）

**实现思路**：
在 `chart_data_service.py:_generate_fan_data()` 的循环中（第758行开始），为每根K线计算真实的P95/P5价格值。

**代码修改**：

```python
# ddps_z/services/chart_data_service.py:756-787

# 获取Z-Score常量
z_p95 = 1.645  # 95%分位对应的Z值
z_p5 = -1.645  # 5%分位对应的Z值

# 构建每根K线的完整数据（用于hover显示）
kline_data = []
for i in range(len(fan_timestamps)):
    # 🆕 计算当前K线的静态阈值（价格）
    p95_price = None
    p5_price = None
    if (not np.isnan(ema_series[i]) and
        not np.isnan(ewma_std_series[i])):
        p95_price = ema_series[i] * (1 + z_p95 * ewma_std_series[i])
        p5_price = ema_series[i] * (1 + z_p5 * ewma_std_series[i])

    # 判断状态
    state_label = '数据不足'
    if (upper_values[i] is not None and not np.isnan(upper_values[i]) and
        mid_values[i] is not None and not np.isnan(mid_values[i]) and
        lower_values[i] is not None and not np.isnan(lower_values[i]) and
        i < len(prices)):

        current_price = prices[i]
        # 判断是否在扇面内
        if lower_values[i] <= current_price <= upper_values[i]:
            state_label = '惯性保护中'
        elif abs(current_price - upper_values[i]) / upper_values[i] < 0.005 or \
             abs(current_price - lower_values[i]) / lower_values[i] < 0.005:
            state_label = '惯性衰减'
        else:
            state_label = '信号触发'

    kline_data.append({
        't': fan_timestamps[i],
        'p95': p95_price,  # 🆕 改为实际价格
        'p5': p5_price,     # 🆕 改为实际价格
        'fan_upper': upper_values[i] if upper_values[i] is not None and not np.isnan(upper_values[i]) else None,
        'fan_mid': mid_values[i] if mid_values[i] is not None and not np.isnan(mid_values[i]) else None,
        'fan_lower': lower_values[i] if lower_values[i] is not None and not np.isnan(lower_values[i]) else None,
        'state': state_label,
        'adx': adx_series[i] if i < len(adx_series) and not np.isnan(adx_series[i]) else None,
        'beta': beta_values[i] if beta_values[i] is not None and not np.isnan(beta_values[i]) else None,
        't_adj': t_adj_values[i] if t_adj_values[i] is not None and not np.isnan(t_adj_values[i]) else None,
    })
```

**优点**：
- ✅ 完全满足需求（每根K线独立的P95/P5价格）
- ✅ 实现简单直接（只修改10行代码）
- ✅ 计算准确（基于当前K线的EMA和σ）
- ✅ 性能优秀（在现有循环中计算，无额外开销）

**缺点**：
- ⚠️ 需要确保EMA和σ数据有效（已有检查）

---

#### 方案B：预先批量计算P95/P5序列

**实现思路**：
在循环前，批量计算所有K线的P95/P5价格序列，然后在循环中直接使用。

**代码修改**：

```python
# ddps_z/services/chart_data_service.py

# 🆕 批量计算P95/P5价格序列
z_p95 = 1.645
z_p5 = -1.645
p95_series = ema_series * (1 + z_p95 * ewma_std_series)
p5_series = ema_series * (1 + z_p5 * ewma_std_series)

# 构建每根K线的完整数据
kline_data = []
for i in range(len(fan_timestamps)):
    kline_data.append({
        't': fan_timestamps[i],
        'p95': p95_series[i] if not np.isnan(p95_series[i]) else None,
        'p5': p5_series[i] if not np.isnan(p5_series[i]) else None,
        # ... 其他字段
    })
```

**优点**：
- ✅ 代码更简洁（利用NumPy向量化）
- ✅ 理论上性能更好（向量化计算）

**缺点**：
- ❌ 实际性能提升微乎其微（数据量小）
- ❌ 需要额外的NaN处理逻辑
- ❌ 可读性略差（计算逻辑分离）

---

### 4.2 方案对比

| 维度 | 方案A | 方案B |
|------|-------|-------|
| **需求满足度** | ✅✅✅ 完全满足 | ✅✅✅ 完全满足 |
| **实现复杂度** | ✅ 简单 | ✅ 简单 |
| **代码可读性** | ✅✅ 逻辑集中 | ⚠️ 逻辑分散 |
| **维护成本** | ✅ 低 | ✅ 低 |
| **性能** | ✅ 优秀 | ✅ 优秀 |
| **代码变更量** | 📝 +10行 | 📝 +15行 |

### 4.3 推荐方案

**推荐：方案A - 在循环中逐K线计算P95/P5价格**

**理由**：
1. 代码逻辑更集中（计算和使用在同一位置）
2. 可读性更好（一眼看出P95/P5是如何计算的）
3. 修改量最小（只需修改循环中的两行）
4. 性能无差异（数据量小，向量化优势不明显）

### 4.4 实现细节

#### 修改文件
📝 `ddps_z/services/chart_data_service.py:756-787`

#### 关键修改点
1. **删除错误的代码** (第688-690行)：
   ```python
   # quantile_bands = series.get('quantile_bands', {})
   # p95_value = quantile_bands.get('p95')
   # p5_value = quantile_bands.get('p5')
   # ← 这三行不再需要
   ```

2. **在循环中添加计算逻辑**（第758行之后）：
   ```python
   # 计算当前K线的静态阈值（价格）
   p95_price = None
   p5_price = None
   if (not np.isnan(ema_series[i]) and
       not np.isnan(ewma_std_series[i])):
       p95_price = ema_series[i] * (1 + 1.645 * ewma_std_series[i])
       p5_price = ema_series[i] * (1 - 1.645 * ewma_std_series[i])
   ```

3. **修改kline_data赋值**（第778-779行）：
   ```python
   'p95': p95_price,  # 改为使用计算的价格
   'p5': p5_price,     # 改为使用计算的价格
   ```

#### 预期效果
- ✅ 每根K线显示独立的P95/P5价格值
- ✅ Hover时动态更新为当前K线的值
- ✅ 数据不足时显示None（前端显示为N/A）

---

## 阶段5：用户确认

**用户确认时间**: 2026-01-06

✅ 用户确认采用**方案A：在循环中逐K线计算P95/P5价格**

---

## 阶段6：实施修复

**修复时间**: 2026-01-06
**修复方案**: 方案A - 在循环中逐K线计算P95/P5价格

### 6.1 代码修改

📝 **文件**: `ddps_z/services/chart_data_service.py`

#### 修改1：删除错误的quantile_bands获取代码（第687-690行）

**修改前**：
```python
# 获取静态分位带
quantile_bands = series.get('quantile_bands', {})
p95_value = quantile_bands.get('p95')  # ← 错误：得到1.64
p5_value = quantile_bands.get('p5')    # ← 错误：得到-1.64
```

**修改后**：
```python
# 🔧 Bug-014修复：静态阈值Z-Score常量（用于价格计算）
z_p95 = 1.645   # 95%分位对应的Z值
z_p5 = -1.645   # 5%分位对应的Z值
```

**变更理由**：
- 删除获取Z-Score常量的错误代码
- 直接定义Z-Score常量用于后续计算

---

#### 修改2：在循环中计算P95/P5价格（第758-764行）

**修改前**：
```python
# 🆕 构建每根K线的完整数据（用于hover显示）
kline_data = []
for i in range(len(fan_timestamps)):
    # 判断状态
    state_label = '数据不足'
    # ...
```

**修改后**：
```python
# 🆕 构建每根K线的完整数据（用于hover显示）
kline_data = []
for i in range(len(fan_timestamps)):
    # 🔧 Bug-014修复：计算当前K线的静态阈值（价格）
    p95_price = None
    p5_price = None
    if (not np.isnan(ema_series[i]) and
        not np.isnan(ewma_std_series[i])):
        p95_price = ema_series[i] * (1 + z_p95 * ewma_std_series[i])
        p5_price = ema_series[i] * (1 + z_p5 * ewma_std_series[i])

    # 判断状态
    state_label = '数据不足'
    # ...
```

**变更理由**：
- 为每根K线独立计算P95/P5价格
- 基于当前K线的EMA和σ计算真实价格阈值
- 数据不足时返回None

---

#### 修改3：修改kline_data赋值（第785-786行）

**修改前**：
```python
kline_data.append({
    't': fan_timestamps[i],
    'p95': p95_value if p95_value is not None else None,  # ← 错误：使用1.64
    'p5': p5_value if p5_value is not None else None,      # ← 错误：使用-1.64
    # ...
})
```

**修改后**：
```python
kline_data.append({
    't': fan_timestamps[i],
    'p95': p95_price,  # 🔧 Bug-014修复：改为实际价格
    'p5': p5_price,     # 🔧 Bug-014修复：改为实际价格
    # ...
})
```

**变更理由**：
- 使用计算出的实际价格值
- 移除不必要的None检查（已在计算时处理）

---

### 6.2 修改汇总

| 修改点 | 行号 | 变更类型 | 说明 |
|--------|------|----------|------|
| quantile_bands获取 | 687-690 | 🔄 重写 | 删除错误代码，改为定义Z-Score常量 |
| P95/P5计算逻辑 | 758-764 | 🆕 新增 | 在循环中计算每根K线的价格阈值 |
| kline_data赋值 | 785-786 | 📝 修改 | 使用计算的价格值替代Z-Score |

**总计**: 约15行代码变更

---

## 阶段7：验证交付

**验证时间**: 2026-01-06

### 7.1 后端验证

#### 测试场景：BTCUSDT 4h, 50根K线

**执行命令**：
```bash
DJANGO_SETTINGS_MODULE=listing_monitor_project.settings python -c "..."
```

**验证结果**：

```
【Bug-014 修复验证】

✅ kline_data存在，共 50 个数据点

【前3个K线的P95/P5值】
1. P95: 89973.21912954103, P5: 85487.50762349539
2. P95: 89966.9140746648, P5: 85504.1721589073
3. P95: 89935.09744570611, P5: 85497.99753912969

【最后3个K线的P95/P5值】
48. P95: 92544.01908421543, P5: 88193.40386353972
49. P95: 92784.35214389712, P5: 88372.23826941532
50. P95: 92943.64520824252, P5: 88513.17671173823

【数据验证】
有效价格数据点: 50
无效数据点: 0
空值数据点: 0

✅ 验证通过：P95/P5已正确转换为价格值！
```

**分析**：
- ✅ 所有50个K线都有有效的P95/P5价格值
- ✅ P95值范围：89935 ~ 92943 USDT（符合BTCUSDT价格水平）
- ✅ P5值范围：85487 ~ 88513 USDT（符合BTCUSDT价格水平）
- ✅ P95 > P5（逻辑正确）
- ✅ 每根K线的P95/P5都不同（符合预期，因为EMA和σ随时间变化）

---

### 7.2 前端验证（待用户测试）

**验证步骤**：

1. 启动服务器：
   ```bash
   python manage.py runserver
   ```

2. 访问DDPS-Z详情页：
   ```
   http://127.0.0.1:8000/ddps-z/detail/?symbol=BTCUSDT&interval=4h&market_type=futures
   ```

3. 验证内容：
   - ✅ 右上角HUD面板应显示价格值（如：P95: 92943.65, P5: 88513.18）
   - ✅ Hover到不同K线时，P95/P5应动态变化
   - ✅ P95和P5的值应该在合理的价格范围内（不是1.64/-1.64）

---

### 7.3 边界条件验证

#### 测试1：数据不足的K线

**场景**: 前26根K线（ADX数据不足）

**预期**:
- ✅ P95/P5可能为None（EMA或σ不足）
- ✅ 前端显示为"N/A"

**结果**: ⏳ 待前端测试确认

---

#### 测试2：不同交易对

**场景**: ETHUSDT, BNBUSDT

**预期**:
- ✅ P95/P5应符合各自的价格水平
- ✅ ETHUSDT: P95约3000+, P5约2800+
- ✅ BNBUSDT: P95约600+, P5约550+

**结果**: ⏳ 待测试

---

## 修复总结

### ✅ 已完成

1. ✅ 需求对齐与澄清
2. ✅ 问题诊断与根因定位
3. ✅ 修复方案设计与确认
4. ✅ 代码实施（3处修改，15行代码）
5. ✅ 后端验证通过

### ⏳ 待完成

1. ⏳ 前端验证（需用户测试）
2. ⏳ 边界条件测试

### 📊 修复效果

**修复前**：
- ❌ P95固定显示：1.6400（Z-Score值）
- ❌ P5固定显示：-1.6400（Z-Score值）
- ❌ Hover时不变化

**修复后**：
- ✅ P95显示实际价格（如：92943.65 USDT）
- ✅ P5显示实际价格（如：88513.18 USDT）
- ✅ 每根K线有独立的P95/P5值
- ✅ Hover时动态更新

### 🎯 根因回顾

**问题根因**：数据类型混淆
- `quantile_bands` 返回的是用于概率带计算的Z-Score常量（1.64, -1.64）
- 代码错误地将这些常量直接用作价格显示
- 应该基于每根K线的EMA和σ计算真实价格阈值

**修复方法**：
- 在循环中为每根K线计算：`P95 = EMA × (1 + 1.645 × σ)`
- 在循环中为每根K线计算：`P5 = EMA × (1 - 1.645 × σ)`

---

## 后续建议

1. **代码规范**（可选）：
   - 将Z-Score常量提取为类常量或配置项
   - 添加单元测试验证P95/P5计算逻辑

2. **功能增强**（可选）：
   - 在HUD面板添加P95/P5的说明文字
   - 高亮显示当前价格是否在P95/P5区间内

3. **文档更新**：
   - 更新API文档说明P95/P5字段
   - 添加用户指南说明静态阈值的含义

---

## 附录

### A. 相关代码位置

- `ddps_z/services/chart_data_service.py:687-690` - Z-Score常量定义
- `ddps_z/services/chart_data_service.py:758-764` - P95/P5价格计算
- `ddps_z/services/chart_data_service.py:785-786` - kline_data赋值

### B. 相关文档

- PRD: `docs/iterations/010-ddps-z-inertia-fan/prd.md`
- Architecture: `docs/iterations/010-ddps-z-inertia-fan/architecture.md`

### C. 测试场景

- [x] BTCUSDT 4h - 50根K线（验证通过）
- [ ] ETHUSDT 4h - 不同价格水平
- [ ] BNBUSDT 4h - 不同价格水平
- [ ] 数据不足场景（前26根K线）
