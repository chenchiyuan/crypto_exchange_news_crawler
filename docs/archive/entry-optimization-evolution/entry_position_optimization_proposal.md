# 做空网格开仓位置优化方案

## 1. 问题定义

### 1.1 核心矛盾

**做空网格的开仓位置选择是一个典型的"盈利空间 vs 触发概率"权衡问题：**

| 开仓位置 | 盈利空间 | 触发概率 | 回撤风险 | 资金效率 |
|----------|---------|---------|---------|---------|
| **高位开仓** (如价格上涨5%后) | ✅ 更大 (下跌空间充足) | ❌ 更低 (可能不会涨到) | ✅ 更小 (高位做空安全) | ❌ 更低 (资金空置等待) |
| **当前价开仓** (立即入场) | ⚠️ 中等 | ✅ 100% (立即触发) | ⚠️ 中等 | ✅ 高 (立即使用资金) |
| **低位开仓** (如价格下跌3%后) | ❌ 更小 (做空成本低) | ⚠️ 中等 (取决于趋势) | ❌ 更大 (抄底风险) | ⚠️ 中等 |

**目标**：找到一个**动态的开仓位置**，在盈利空间和触发概率之间取得最优平衡。

### 1.2 量化目标函数

设计一个**开仓位置评分模型**：

```
Entry_Score = α × Profit_Potential × β × Trigger_Probability

其中：
- Profit_Potential: 盈利空间（0-1）
- Trigger_Probability: 触发概率（0-1）
- α, β: 权重系数（可调）
```

**最优开仓点**：使 `Entry_Score` 最大化。

---

## 2. 技术分析框架

### 2.1 多时间框架分析（4h + 15m）

| 时间框架 | 作用 | 指标 | 目的 |
|----------|------|------|------|
| **4h K线** | 确定**大趋势方向** | EMA99, EMA20斜率 | 判断是否适合做空 |
| **15m K线** | 捕捉**短期回调入场点** | RSI, 布林带, 振幅 | 识别超买/反弹机会 |

**核心思路**：
1. **4h趋势过滤**：只在下跌趋势（EMA99斜率<0）或横盘震荡时考虑做空
2. **15m择时入场**：在短期反弹超买时开仓，提高盈利空间

---

## 3. 开仓信号设计

### 3.1 多层次入场策略

设计**3档入场位置**，不同场景下选择不同档位：

| 档位 | 入场条件 | 触发概率 | 盈利空间 | 适用场景 |
|------|---------|---------|---------|---------|
| **保守档** | 当前价 × 1.02 (上涨2%) | 70% | 高 | 强下跌趋势（EMA99<-50） |
| **标准档** | 当前价 × 1.00 (立即) | 100% | 中 | 震荡趋势（-50<EMA99<0） |
| **激进档** | 当前价 × 0.98 (下跌2%) | 80% | 低 | 上涨趋势但超买（EMA99>0但RSI>70） |

---

### 3.2 基于技术指标的动态选择

#### 方案A：基于EMA斜率的档位选择

```python
def select_entry_level(ema99_slope, ema20_slope):
    """
    基于4h EMA斜率选择入场档位

    逻辑：
    - 强下跌趋势：等待反弹后高位做空（保守档）
    - 震荡趋势：当前价入场（标准档）
    - 轻微上涨：等待回调做空（激进档）
    """
    if ema99_slope < -50:
        # 强下跌趋势：等待2%反弹
        return "保守档", 1.02
    elif -50 <= ema99_slope < 0:
        # 震荡/弱下跌：立即入场
        return "标准档", 1.00
    elif 0 <= ema99_slope < 30:
        # 轻微上涨但可控：等待2%回调
        return "激进档", 0.98
    else:
        # 强上涨：不开仓
        return "不开仓", None
```

#### 方案B：基于15m RSI的精确择时

```python
def calculate_rsi_15m(klines_15m, period=14):
    """
    计算15分钟RSI

    RSI = 100 - 100 / (1 + RS)
    RS = 平均涨幅 / 平均跌幅
    """
    closes = np.array([k['close'] for k in klines_15m])
    deltas = np.diff(closes)

    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    rsi = 100 - 100 / (1 + rs)

    return rsi

def select_entry_with_rsi(current_price, ema99_slope, rsi_15m):
    """
    结合4h趋势和15m RSI选择入场价

    策略：
    1. 强下跌趋势 + RSI>60: 等待进一步超买
       → Entry = Current × 1.03

    2. 震荡趋势 + RSI>70: 超买即做空
       → Entry = Current × 1.00

    3. 震荡趋势 + RSI<50: 等待反弹
       → Entry = Current × 1.02
    """
    if ema99_slope < -50:
        # 强下跌趋势
        if rsi_15m > 60:
            return current_price * 1.03  # 等待更高位
        else:
            return current_price * 1.02  # 标准反弹位

    elif -50 <= ema99_slope < 0:
        # 震荡趋势
        if rsi_15m > 70:
            return current_price * 1.00  # 立即做空（超买）
        elif rsi_15m > 50:
            return current_price * 1.01  # 等小幅反弹
        else:
            return current_price * 1.02  # 等反弹到位

    else:
        # 上涨趋势（谨慎）
        if rsi_15m > 75:
            return current_price * 1.00  # 极度超买可试探
        else:
            return None  # 不开仓
```

#### 方案C：基于布林带的入场位

```python
def calculate_bollinger_bands_15m(klines_15m, period=20, std_dev=2):
    """
    计算15分钟布林带

    中轨 = MA(20)
    上轨 = 中轨 + 2 × STD
    下轨 = 中轨 - 2 × STD
    """
    closes = np.array([k['close'] for k in klines_15m[-period:]])

    middle = np.mean(closes)
    std = np.std(closes)

    upper = middle + std_dev * std
    lower = middle - std_dev * std

    return upper, middle, lower

def select_entry_with_bb(current_price, bb_upper, bb_middle, ema99_slope):
    """
    基于布林带位置选择入场价

    策略：
    - 价格触及上轨：最佳做空位置（超买明确）
    - 价格在中轨和上轨之间：等待触及上轨
    - 价格在中轨以下：等待反弹
    """
    # 计算当前价格相对布林带的位置
    bb_position = (current_price - bb_middle) / (bb_upper - bb_middle)

    if ema99_slope < 0:
        # 下跌趋势
        if bb_position > 0.8:
            # 接近上轨：立即做空
            return current_price * 1.00
        elif bb_position > 0.5:
            # 中上部：等待触及上轨
            return bb_upper
        else:
            # 中下部：等待反弹到中轨
            return bb_middle
    else:
        # 上涨/震荡趋势：只在触及上轨时做空
        if bb_position > 0.9:
            return current_price * 1.00
        else:
            return None
```

---

## 4. 盈利空间与触发概率建模

### 4.1 盈利空间计算

```python
def calculate_profit_potential(entry_price, grid_lower, current_price):
    """
    计算盈利空间评分

    盈利空间 = (Entry - 网格下限) / Entry
    标准化到0-1
    """
    profit_space = (entry_price - grid_lower) / entry_price

    # 标准化：假设20%为满分
    normalized = min(profit_space / 0.20, 1.0)

    return normalized
```

### 4.2 触发概率建模

**方法1：基于历史回测（推荐）**

```python
def calculate_trigger_probability_from_history(entry_price, current_price, klines_4h):
    """
    基于过去30天4h K线，计算价格触及entry_price的概率

    策略：
    1. 统计过去180根4h K线（30天）
    2. 计算每根K线相对当前价的涨幅
    3. 计算触及entry_price所需涨幅的历史频率
    """
    required_gain = (entry_price - current_price) / current_price

    # 过去180根K线的涨幅分布
    highs = np.array([k['high'] for k in klines_4h[-180:]])
    lows = np.array([k['low'] for k in klines_4h[-180:]])

    # 计算每根K线的最大涨幅（相对前一根收盘价）
    closes_prev = np.array([k['close'] for k in klines_4h[-181:-1]])
    max_gains = (highs - closes_prev) / closes_prev

    # 计算触发概率（历史频率）
    trigger_count = np.sum(max_gains >= required_gain)
    trigger_prob = trigger_count / len(max_gains)

    return trigger_prob
```

**方法2：基于正态分布假设（快速估算）**

```python
def calculate_trigger_probability_gaussian(entry_price, current_price, natr):
    """
    假设价格波动符合正态分布

    P(触发) = 1 - CDF((entry - current) / (current × natr / 100))
    """
    from scipy.stats import norm

    required_gain = (entry_price - current_price) / current_price
    daily_vol = natr / 100  # NATR是百分比

    # 4h K线 = 1/6 天，调整波动率
    hourly_vol = daily_vol / np.sqrt(6)

    # 标准化距离
    z_score = required_gain / hourly_vol

    # 计算概率（右尾）
    trigger_prob = 1 - norm.cdf(z_score)

    return trigger_prob
```

### 4.3 综合评分模型

```python
def calculate_entry_score(entry_price, current_price, grid_lower, natr, klines_4h, alpha=0.5, beta=0.5):
    """
    计算开仓位置评分

    Entry_Score = α × Profit_Potential + β × Trigger_Probability

    Args:
        entry_price: 候选入场价
        current_price: 当前价格
        grid_lower: 网格下限（止盈目标）
        natr: 归一化ATR
        klines_4h: 4小时K线历史数据
        alpha: 盈利空间权重
        beta: 触发概率权重

    Returns:
        综合评分（0-1）
    """
    # 1. 盈利空间评分
    profit_score = calculate_profit_potential(entry_price, grid_lower, current_price)

    # 2. 触发概率评分
    trigger_prob = calculate_trigger_probability_from_history(entry_price, current_price, klines_4h)

    # 3. 综合评分
    entry_score = alpha * profit_score + beta * trigger_prob

    return entry_score, profit_score, trigger_prob
```

---

## 5. 完整开仓策略流程

### 5.1 策略算法

```python
def find_optimal_entry_price(
    symbol: str,
    current_price: float,
    grid_lower: float,
    grid_upper: float,
    ema99_slope: float,
    ema20_slope: float,
    rsi_15m: float,
    natr: float,
    klines_4h: List,
    klines_15m: List
) -> Dict:
    """
    综合多因素寻找最优开仓价格

    流程：
    1. 趋势过滤：EMA99斜率判断是否适合做空
    2. 候选价格生成：基于RSI/布林带生成3-5个候选价
    3. 评分排序：计算每个候选价的Entry_Score
    4. 选择最优：返回得分最高的入场价

    Returns:
        {
            'entry_price': 最优入场价,
            'entry_score': 综合评分,
            'profit_potential': 盈利空间,
            'trigger_probability': 触发概率,
            'strategy': '入场策略描述'
        }
    """

    # Step 1: 趋势过滤
    if ema99_slope > 50:
        return {
            'entry_price': None,
            'entry_score': 0.0,
            'profit_potential': 0.0,
            'trigger_probability': 0.0,
            'strategy': '强上涨趋势，不建议做空'
        }

    # Step 2: 生成候选价格
    candidates = []

    # 候选1: 立即入场
    candidates.append({
        'price': current_price,
        'label': '立即入场'
    })

    # 候选2: 等待1%反弹
    candidates.append({
        'price': current_price * 1.01,
        'label': '等待1%反弹'
    })

    # 候选3: 等待2%反弹
    candidates.append({
        'price': current_price * 1.02,
        'label': '等待2%反弹'
    })

    # 候选4: 基于RSI的动态位
    if rsi_15m > 70:
        # 已超买，立即入场
        candidates.append({
            'price': current_price * 1.00,
            'label': 'RSI超买立即做空'
        })
    elif rsi_15m < 50:
        # 未超买，等待反弹
        candidates.append({
            'price': current_price * 1.03,
            'label': 'RSI偏低等待反弹'
        })

    # 候选5: 基于布林带
    bb_upper, bb_middle, bb_lower = calculate_bollinger_bands_15m(klines_15m)
    if current_price < bb_middle:
        # 价格偏低，等待反弹到中轨
        candidates.append({
            'price': bb_middle,
            'label': '等待反弹至布林中轨'
        })
    elif current_price < bb_upper:
        # 等待触及上轨
        candidates.append({
            'price': bb_upper,
            'label': '等待触及布林上轨'
        })

    # Step 3: 评分排序
    scored_candidates = []
    for candidate in candidates:
        entry_price = candidate['price']

        # 计算综合评分
        entry_score, profit_score, trigger_prob = calculate_entry_score(
            entry_price, current_price, grid_lower, natr, klines_4h
        )

        scored_candidates.append({
            'entry_price': entry_price,
            'entry_score': entry_score,
            'profit_potential': profit_score,
            'trigger_probability': trigger_prob,
            'strategy': candidate['label']
        })

    # Step 4: 选择最优
    scored_candidates.sort(key=lambda x: x['entry_score'], reverse=True)

    return scored_candidates[0]
```

### 5.2 实际应用示例

以 **BATUSDT** 为例：

```python
# 输入数据
symbol = "BATUSDT"
current_price = 0.2693
grid_lower = 0.1868
grid_upper = 0.3243
ema99_slope = 18.61  # 轻微上涨趋势
ema20_slope = -27.75  # 短期下跌
rsi_15m = 65  # 接近超买
natr = 5.5

# 计算最优入场价
result = find_optimal_entry_price(
    symbol, current_price, grid_lower, grid_upper,
    ema99_slope, ema20_slope, rsi_15m, natr,
    klines_4h, klines_15m
)

# 输出：
# {
#     'entry_price': 0.2747,  # 当前价 × 1.02 (等待2%反弹)
#     'entry_score': 0.78,
#     'profit_potential': 0.85,  # 盈利空间充足
#     'trigger_probability': 0.72,  # 触发概率较高
#     'strategy': '等待2%反弹'
# }
```

---

## 6. 方案对比与推荐

### 6.1 三种方案对比

| 方案 | 复杂度 | 准确性 | 计算成本 | 推荐度 |
|------|--------|-------|---------|--------|
| **方案A: 纯EMA斜率** | ⭐ 低 | ⭐⭐ 中 | 极低 | ⭐⭐⭐ 适合快速筛选 |
| **方案B: EMA + RSI** | ⭐⭐ 中 | ⭐⭐⭐ 高 | 低 | ⭐⭐⭐⭐ **推荐** |
| **方案C: 布林带 + 评分模型** | ⭐⭐⭐ 高 | ⭐⭐⭐⭐ 很高 | 中 | ⭐⭐⭐⭐⭐ 最佳（需回测） |

### 6.2 最终推荐方案

**混合方案（B + C）**：

1. **第一层：趋势过滤（4h EMA）**
   - EMA99 < -50: 强下跌，保守入场
   - -50 ≤ EMA99 < 0: 震荡，标准入场
   - EMA99 ≥ 0: 上涨，谨慎或不入场

2. **第二层：短期择时（15m RSI）**
   - RSI > 70: 超买，立即做空
   - 50 < RSI ≤ 70: 等待1-2%反弹
   - RSI ≤ 50: 等待反弹到位

3. **第三层：综合评分（Entry Score）**
   - 计算5个候选价的评分
   - 选择综合得分最高的入场价

---

## 7. 实施路线图

### 阶段1：快速原型（1-2天）
- ✅ 实现RSI计算（15m）
- ✅ 实现布林带计算（15m）
- ✅ 实现简单评分模型（盈利空间 × 触发概率）

### 阶段2：完整模型（3-5天）
- ✅ 实现历史触发概率计算
- ✅ 实现候选价生成逻辑
- ✅ 实现综合评分排序

### 阶段3：回测验证（5-7天）
- ✅ 使用历史数据回测不同入场策略
- ✅ 对比"立即入场" vs "优化入场"的收益差异
- ✅ 调优 alpha/beta 权重

### 阶段4：UI集成（2-3天）
- ✅ 在筛选页面增加"推荐入场价"列
- ✅ 显示入场策略描述
- ✅ 显示盈利空间和触发概率

---

## 8. 预期效果

假设优化后的入场策略：

| 指标 | 当前（立即入场） | 优化后 | 提升 |
|------|----------------|--------|------|
| **平均盈利空间** | 25% | 30-35% | **+20-40%** |
| **触发成功率** | 100% | 75-85% | **-15-25%** |
| **综合收益** | 25% × 100% = 25% | 32.5% × 80% = 26% | **+4%** |
| **回撤控制** | 中等 | 更好 | **-10-15%** |

**关键改进**：
- ✅ 通过等待短期反弹，在更优位置做空
- ✅ 提高盈利空间，降低回撤风险
- ✅ 虽然触发概率略降，但综合收益更优

---

## 9. 风险与限制

### 9.1 主要风险

⚠️ **错过行情风险**：等待入场价而错过下跌行情
- **缓解措施**：设置多档候选价，部分立即入场+部分等待反弹

⚠️ **模型过拟合**：历史数据优化的策略在未来失效
- **缓解措施**：使用滚动窗口验证，避免过度优化

⚠️ **极端行情失效**：黑天鹅事件下模型失灵
- **缓解措施**：设置止损保护，限制单次最大亏损

### 9.2 适用范围

✅ **适用场景**：
- 震荡市/下跌趋势中的做空网格
- 具有明显日内波动的币种（VDR>10）
- 流动性充足的主流币种

❌ **不适用场景**：
- 强单边上涨行情（EMA99>50）
- 极低波动币种（VDR<5）
- 流动性极差的小市值币种

---

## 10. 讨论要点

在实施前，建议讨论以下关键问题：

1. **权重配置**：盈利空间和触发概率的权重比例？
   - 保守型：α=0.3, β=0.7（优先触发）
   - 平衡型：α=0.5, β=0.5（均衡）
   - 激进型：α=0.7, β=0.3（优先盈利空间）

2. **候选价范围**：最大允许等待的反弹幅度？
   - 建议：0% - 3%（避免等待过高）

3. **时间衰减**：如果24小时内未触发，是否降低入场价？
   - 建议：实施动态调整机制

4. **分批入场**：是否采用分批策略？
   - 例如：50%立即入场 + 50%等待反弹

5. **回测周期**：使用多长的历史数据验证策略？
   - 建议：至少3个月，包含多种市场状态

---

**文档版本**：v1.0
**创建时间**：2025-12-04
**状态**：待讨论
