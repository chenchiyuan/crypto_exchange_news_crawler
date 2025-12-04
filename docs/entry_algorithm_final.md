# 做空网格挂单算法 - 最终版

**版本**: v3.0
**状态**: ✅ **已实施**
**实现文件**: `grid_trading/services/entry_optimizer.py`
**创建时间**: 2025-12-04

> **提示**: 本文档为最终版本，已完整实现。历史版本(v1.0/v2.0)已归档至 `archive/entry-optimization-evolution/`

---

## 算法总览

**核心思路**：RSI判断反弹空间 + 历史统计验证触发概率

```
Step 1: 用RSI计算理论反弹幅度（预测价格可能涨多少）
Step 2: 用历史统计计算触发概率（验证这个涨幅在过去7天出现的频率）
Step 3: 生成3个候选价格，计算期望收益，推荐最优方案
```

---

## 完整算法流程

### Step 1: 计算理论反弹幅度（基于RSI）

```python
def calculate_rebound_potential(rsi_15m, ema99_slope, natr):
    """
    基于RSI + 趋势 + 波动率，计算理论反弹幅度

    Args:
        rsi_15m: 15分钟K线的RSI(14)
        ema99_slope: 4小时EMA99斜率
        natr: 归一化ATR（日线）

    Returns:
        理论反弹幅度（小数，如0.02表示2%）
    """

    # 1.1 基础反弹幅度（基于RSI）
    if rsi_15m >= 75:
        # 极度超买，反弹空间极小
        base_rebound = 0.003  # 0.3%
    elif rsi_15m >= 70:
        # 超买，反弹空间很小
        base_rebound = 0.005  # 0.5%
    elif rsi_15m >= 65:
        # 偏强，小幅反弹空间
        base_rebound = 0.01   # 1.0%
    elif rsi_15m >= 60:
        # 偏强，中等反弹空间
        base_rebound = 0.015  # 1.5%
    elif rsi_15m >= 55:
        # 中性偏强
        base_rebound = 0.02   # 2.0%
    elif rsi_15m >= 50:
        # 中性
        base_rebound = 0.025  # 2.5%
    elif rsi_15m >= 45:
        # 中性偏弱
        base_rebound = 0.03   # 3.0%
    elif rsi_15m >= 40:
        # 偏弱
        base_rebound = 0.04   # 4.0%
    else:
        # RSI < 40，超卖，反弹空间大但风险高
        base_rebound = 0.05   # 5.0%

    # 1.2 趋势修正系数
    if ema99_slope < -100:
        # 极强下跌趋势，反弹严重受限
        trend_factor = 0.5
    elif ema99_slope < -50:
        # 强下跌趋势，反弹受限
        trend_factor = 0.7
    elif ema99_slope < -20:
        # 中等下跌趋势
        trend_factor = 0.85
    elif ema99_slope < 0:
        # 弱下跌趋势
        trend_factor = 1.0
    elif ema99_slope < 20:
        # 弱上涨趋势
        trend_factor = 1.15
    elif ema99_slope < 50:
        # 中等上涨趋势
        trend_factor = 1.3
    else:
        # 强上涨趋势（不建议做空）
        trend_factor = 1.5

    # 1.3 波动率修正系数
    if natr < 2:
        # 极低波动
        volatility_factor = 0.6
    elif natr < 4:
        # 低波动
        volatility_factor = 0.8
    elif natr < 6:
        # 中等波动
        volatility_factor = 1.0
    elif natr < 8:
        # 高波动
        volatility_factor = 1.2
    else:
        # 极高波动
        volatility_factor = 1.5

    # 1.4 综合计算
    adjusted_rebound = base_rebound * trend_factor * volatility_factor

    # 1.5 上限保护（最多不超过8%反弹）
    adjusted_rebound = min(adjusted_rebound, 0.08)

    return adjusted_rebound


# 示例计算
rsi = 65
ema99 = 18.61
natr = 5.5

base = 0.01  # RSI=65 → 1%
trend = 1.15  # EMA99=18.61 → 弱上涨
vol = 1.0  # NATR=5.5 → 中等波动

理论反弹 = 0.01 × 1.15 × 1.0 = 1.15%
```

---

### Step 2: 计算触发概率（基于历史统计）

```python
def calculate_trigger_probability_from_history(
    current_price,
    target_gain_pct,  # 目标涨幅（如0.0115表示1.15%）
    klines_15m,       # 最近7天的15分钟K线数据
    time_window_hours=24
):
    """
    统计过去7天，价格从任意点反弹到target_gain_pct的频率

    Args:
        current_price: 当前价格
        target_gain_pct: 目标涨幅（小数形式）
        klines_15m: 15分钟K线列表（至少672根，7天×24小时×4）
        time_window_hours: 时间窗口（默认24小时）

    Returns:
        {
            'probability': 触发概率（0-1），
            'trigger_count': 触发次数,
            'total_windows': 总窗口数,
            'avg_time_to_trigger': 平均触发时间（小时）
        }
    """

    # 2.1 参数校验
    if len(klines_15m) < 672:
        raise ValueError("历史数据不足7天")

    # 取最近7天数据（672根15分钟K线）
    recent_klines = klines_15m[-672:]

    # 2.2 时间窗口参数
    bars_per_window = time_window_hours * 4  # 15分钟K线，1小时=4根

    # 2.3 滑动窗口统计
    trigger_count = 0
    total_windows = 0
    trigger_times = []  # 记录触发所需时间（用于计算平均）

    # 遍历每个可能的起点（留出time_window的空间）
    for i in range(len(recent_klines) - bars_per_window):
        base_close = recent_klines[i]['close']

        # 计算未来time_window_hours内的价格波动
        future_bars = recent_klines[i+1 : i+1+bars_per_window]

        # 检查是否触发
        triggered = False
        trigger_bar_index = None

        for j, bar in enumerate(future_bars):
            gain = (bar['high'] - base_close) / base_close

            if gain >= target_gain_pct:
                triggered = True
                trigger_bar_index = j
                break

        if triggered:
            trigger_count += 1
            trigger_time_hours = (trigger_bar_index + 1) * 0.25  # 15分钟 = 0.25小时
            trigger_times.append(trigger_time_hours)

        total_windows += 1

    # 2.4 计算统计结果
    probability = trigger_count / total_windows if total_windows > 0 else 0.0
    avg_time = sum(trigger_times) / len(trigger_times) if trigger_times else 0.0

    return {
        'probability': probability,
        'trigger_count': trigger_count,
        'total_windows': total_windows,
        'avg_time_to_trigger': avg_time
    }


# 示例计算
current_price = 0.2693
target_gain = 0.0115  # 1.15%
klines_15m = [...]  # 7天历史数据

result = calculate_trigger_probability_from_history(
    current_price, target_gain, klines_15m, time_window_hours=24
)

# 输出：
# {
#     'probability': 0.78,  # 78%触发概率
#     'trigger_count': 520,
#     'total_windows': 672,
#     'avg_time_to_trigger': 8.5  # 平均8.5小时触发
# }
```

---

### Step 3: 生成候选价格并评分

```python
def generate_entry_recommendations(
    symbol,
    current_price,
    grid_lower,  # 网格下限（止盈目标）
    rsi_15m,
    ema99_slope,
    natr,
    klines_15m
):
    """
    生成3个候选挂单价格，并推荐最优方案

    Returns:
        {
            'candidates': [候选方案列表],
            'recommended': 推荐方案
        }
    """

    # 3.1 计算理论反弹幅度
    theoretical_rebound = calculate_rebound_potential(rsi_15m, ema99_slope, natr)

    # 3.2 生成3个候选价格
    candidates = []

    # 候选1: 立即入场（0%反弹）
    candidates.append({
        'label': '立即入场',
        'rebound_pct': 0.0,
        'entry_price': current_price
    })

    # 候选2: 保守反弹（理论反弹的50%）
    conservative_rebound = theoretical_rebound * 0.5
    candidates.append({
        'label': '保守反弹',
        'rebound_pct': conservative_rebound,
        'entry_price': current_price * (1 + conservative_rebound)
    })

    # 候选3: 理论反弹（100%理论值）
    candidates.append({
        'label': '理论反弹',
        'rebound_pct': theoretical_rebound,
        'entry_price': current_price * (1 + theoretical_rebound)
    })

    # 3.3 对每个候选价格计算触发概率和盈利空间
    for candidate in candidates:
        entry_price = candidate['entry_price']

        # 3.3.1 计算触发概率（24小时和72小时）
        trigger_24h = calculate_trigger_probability_from_history(
            current_price, candidate['rebound_pct'], klines_15m, time_window_hours=24
        )
        trigger_72h = calculate_trigger_probability_from_history(
            current_price, candidate['rebound_pct'], klines_15m, time_window_hours=72
        )

        candidate['trigger_prob_24h'] = trigger_24h['probability']
        candidate['trigger_prob_72h'] = trigger_72h['probability']
        candidate['avg_trigger_time'] = trigger_24h['avg_time_to_trigger']

        # 3.3.2 计算盈利空间
        profit_potential = (entry_price - grid_lower) / entry_price
        candidate['profit_potential'] = profit_potential

        # 3.3.3 计算期望收益（24小时和72小时）
        candidate['expected_return_24h'] = profit_potential * trigger_24h['probability']
        candidate['expected_return_72h'] = profit_potential * trigger_72h['probability']

    # 3.4 选择推荐方案（基于24小时期望收益）
    candidates_sorted = sorted(candidates, key=lambda x: x['expected_return_24h'], reverse=True)

    # 3.5 应用触发概率过滤（至少要60%以上）
    valid_candidates = [c for c in candidates_sorted if c['trigger_prob_24h'] >= 0.6]

    if not valid_candidates:
        # 如果没有满足条件的，推荐立即入场
        recommended = candidates[0]
    else:
        recommended = valid_candidates[0]

    return {
        'symbol': symbol,
        'current_price': current_price,
        'market_state': {
            'rsi_15m': rsi_15m,
            'ema99_slope': ema99_slope,
            'natr': natr,
            'theoretical_rebound': theoretical_rebound
        },
        'candidates': candidates,
        'recommended': recommended
    }
```

---

## 完整算法示例

### 输入数据（BATUSDT）

```python
symbol = "BATUSDT"
current_price = 0.2693
grid_lower = 0.1868  # 网格下限（止盈目标）
rsi_15m = 65
ema99_slope = 18.61
natr = 5.5
klines_15m = [...]  # 7天历史数据（672根）
```

### 执行过程

#### Step 1: 计算理论反弹

```python
base_rebound = 0.01  # RSI=65 → 1%
trend_factor = 1.15  # EMA99=18.61 → 弱上涨
volatility_factor = 1.0  # NATR=5.5 → 中等波动

theoretical_rebound = 0.01 × 1.15 × 1.0 = 0.0115 (1.15%)
```

#### Step 2: 生成候选价格

```python
候选1: 立即入场
  - 反弹幅度: 0%
  - 入场价: $0.2693

候选2: 保守反弹
  - 反弹幅度: 0.575% (理论的50%)
  - 入场价: $0.2708

候选3: 理论反弹
  - 反弹幅度: 1.15%
  - 入场价: $0.2724
```

#### Step 3: 统计触发概率

假设统计结果：

```python
候选1（立即入场）:
  - 24h触发概率: 100% (当前价)
  - 72h触发概率: 100%
  - 平均触发时间: 0小时

候选2（保守反弹 +0.575%）:
  - 24h触发概率: 88%
  - 72h触发概率: 95%
  - 平均触发时间: 5.2小时

候选3（理论反弹 +1.15%）:
  - 24h触发概率: 76%
  - 72h触发概率: 89%
  - 平均触发时间: 9.8小时
```

#### Step 4: 计算盈利空间和期望收益

```python
网格下限 = $0.1868

候选1:
  - 盈利空间 = (0.2693 - 0.1868) / 0.2693 = 30.6%
  - 期望收益(24h) = 30.6% × 100% = 30.6%
  - 期望收益(72h) = 30.6% × 100% = 30.6%

候选2:
  - 盈利空间 = (0.2708 - 0.1868) / 0.2708 = 31.0%
  - 期望收益(24h) = 31.0% × 88% = 27.3%
  - 期望收益(72h) = 31.0% × 95% = 29.5%

候选3:
  - 盈利空间 = (0.2724 - 0.1868) / 0.2724 = 31.4%
  - 期望收益(24h) = 31.4% × 76% = 23.9%
  - 期望收益(72h) = 31.4% × 89% = 28.0%
```

#### Step 5: 推荐决策

基于24小时期望收益排序：

| 排名 | 方案 | 入场价 | 触发概率 | 盈利空间 | 期望收益 |
|------|------|--------|---------|---------|---------|
| 🥇 | 立即入场 | $0.2693 | 100% | 30.6% | **30.6%** |
| 🥈 | 保守反弹 | $0.2708 | 88% | 31.0% | **27.3%** |
| 🥉 | 理论反弹 | $0.2724 | 76% | 31.4% | **23.9%** |

**推荐方案**：立即入场（期望收益最高）

**但如果考虑72小时**：

| 排名 | 方案 | 期望收益(72h) |
|------|------|--------------|
| 🥇 | 立即入场 | 30.6% |
| 🥈 | **保守反弹** | **29.5%** ← 仅差1.1% |
| 🥉 | 理论反弹 | 28.0% |

**结论**：
- 如果用户能容忍5.2小时等待，**保守反弹方案**在损失极小期望收益的情况下，获得了更好的入场位置
- 系统可以推荐"保守反弹"，并备注"触发概率88%，平均5.2小时触发"

---

## 边界情况处理

### 情况1: RSI极度超买（>75）

```python
if rsi_15m > 75:
    # 立即做空，不等反弹
    return {
        'recommended': {
            'label': '立即入场（极度超买）',
            'entry_price': current_price,
            'trigger_prob_24h': 1.0,
            'reason': 'RSI>75极度超买，可能即将回调'
        }
    }
```

### 情况2: RSI超卖（<30）且下跌趋势

```python
if rsi_15m < 30 and ema99_slope < 0:
    # 警告：反弹风险大
    return {
        'recommended': {
            'label': '等待反弹至RSI>40',
            'entry_price': None,
            'trigger_prob_24h': None,
            'reason': '⚠️ RSI<30超卖，反弹动能强，建议等待RSI回升后再考虑'
        }
    }
```

### 情况3: 强上涨趋势（EMA99>50）

```python
if ema99_slope > 50:
    return {
        'warning': '⚠️ 强上涨趋势，不建议做空',
        'recommended': None
    }
```

### 情况4: 历史数据不足

```python
if len(klines_15m) < 672:
    # 降级策略：仅推荐立即入场
    return {
        'recommended': {
            'label': '立即入场',
            'entry_price': current_price,
            'trigger_prob_24h': 1.0,
            'reason': '历史数据不足，无法计算反弹概率，建议立即入场'
        }
    }
```

### 情况5: 所有候选概率都低于60%

```python
if all(c['trigger_prob_24h'] < 0.6 for c in candidates):
    # 降级为立即入场
    return {
        'recommended': candidates[0],  # 立即入场
        'reason': '所有反弹方案触发概率偏低（<60%），推荐立即入场'
    }
```

---

## 算法参数汇总

### 核心参数

| 参数名 | 默认值 | 说明 | 可调范围 |
|--------|-------|------|---------|
| **rsi_period** | 14 | RSI计算周期 | 12-21 |
| **history_days** | 7 | 统计历史天数 | 5-14 |
| **time_window_24h** | 24小时 | 短期触发概率窗口 | 12-48 |
| **time_window_72h** | 72小时 | 长期触发概率窗口 | 48-168 |
| **min_trigger_prob** | 60% | 最小可接受触发概率 | 50-80% |
| **max_rebound** | 8% | 最大反弹上限 | 5-10% |

### RSI反弹映射表

| RSI区间 | 基础反弹幅度 | 说明 |
|---------|------------|------|
| 75+ | 0.3% | 极度超买 |
| 70-75 | 0.5% | 超买 |
| 65-70 | 1.0% | 偏强 |
| 60-65 | 1.5% | 中性偏强 |
| 55-60 | 2.0% | 中性 |
| 50-55 | 2.5% | 中性偏弱 |
| 45-50 | 3.0% | 偏弱 |
| 40-45 | 4.0% | 较弱 |
| <40 | 5.0% | 超卖 |

### 趋势修正系数表

| EMA99斜率 | 修正系数 | 说明 |
|-----------|---------|------|
| <-100 | 0.5 | 极强下跌 |
| -100 ~ -50 | 0.7 | 强下跌 |
| -50 ~ -20 | 0.85 | 中等下跌 |
| -20 ~ 0 | 1.0 | 弱下跌 |
| 0 ~ 20 | 1.15 | 弱上涨 |
| 20 ~ 50 | 1.3 | 中等上涨 |
| >50 | 1.5 | 强上涨（不建议做空） |

### 波动率修正系数表

| NATR区间 | 修正系数 | 说明 |
|----------|---------|------|
| <2 | 0.6 | 极低波动 |
| 2-4 | 0.8 | 低波动 |
| 4-6 | 1.0 | 中等波动 |
| 6-8 | 1.2 | 高波动 |
| >8 | 1.5 | 极高波动 |

---

## 输出格式

### JSON格式

```json
{
  "symbol": "BATUSDT",
  "current_price": 0.2693,
  "market_state": {
    "rsi_15m": 65,
    "ema99_slope": 18.61,
    "natr": 5.5,
    "theoretical_rebound_pct": 1.15,
    "interpretation": "中性偏强，弱上涨趋势，中等波动"
  },
  "candidates": [
    {
      "label": "立即入场",
      "entry_price": 0.2693,
      "rebound_pct": 0.0,
      "trigger_prob_24h": 1.0,
      "trigger_prob_72h": 1.0,
      "profit_potential": 0.306,
      "expected_return_24h": 0.306,
      "expected_return_72h": 0.306,
      "avg_trigger_time": 0.0
    },
    {
      "label": "保守反弹",
      "entry_price": 0.2708,
      "rebound_pct": 0.00575,
      "trigger_prob_24h": 0.88,
      "trigger_prob_72h": 0.95,
      "profit_potential": 0.310,
      "expected_return_24h": 0.273,
      "expected_return_72h": 0.295,
      "avg_trigger_time": 5.2
    },
    {
      "label": "理论反弹",
      "entry_price": 0.2724,
      "rebound_pct": 0.0115,
      "trigger_prob_24h": 0.76,
      "trigger_prob_72h": 0.89,
      "profit_potential": 0.314,
      "expected_return_24h": 0.239,
      "expected_return_72h": 0.280,
      "avg_trigger_time": 9.8
    }
  ],
  "recommended": {
    "label": "保守反弹",
    "entry_price": 0.2708,
    "reason": "触发概率88%且期望收益仅比立即入场低3.3%，平均5.2小时触发",
    "risk_level": "低"
  }
}
```

---

## 算法验证清单

### 单元测试用例

1. **正常场景**：RSI=60, EMA99=-10, NATR=5 → 应推荐保守反弹
2. **极度超买**：RSI=78, EMA99=-30 → 应推荐立即入场
3. **超卖场景**：RSI=25, EMA99=-40 → 应警告不建议做空或延后
4. **强上涨趋势**：RSI=55, EMA99=60 → 应警告不建议做空
5. **低波动场景**：RSI=55, NATR=1.5 → 反弹预期应降低
6. **历史数据不足**：klines_15m长度<672 → 应降级到立即入场

### 回测验证

使用过去3个月数据：
- 对比"立即入场" vs "算法推荐" vs "理论反弹"
- 统计实际触发率与预测触发概率的误差
- 计算综合收益率差异

---

## 总结

### 算法核心优势

✅ **双重验证**：RSI预测反弹空间 + 历史统计验证可行性
✅ **数据驱动**：基于真实7天历史数据，不是理论假设
✅ **多方案对比**：提供3个候选价格，用户可根据风险偏好选择
✅ **期望收益量化**：清晰计算每个方案的期望收益
✅ **边界保护**：处理极端RSI、强趋势、数据不足等情况

### 与v1.0/v2.0的区别

| 维度 | v1.0 | v2.0 | **最终版** |
|------|------|------|----------|
| 核心方法 | 布林带+评分 | RSI+历史统计 | **RSI+历史统计** |
| 算法明确度 | 模糊 | 中等 | **完全明确** ✅ |
| 参数可调性 | 低 | 中 | **高（9个参数）** ✅ |
| 边界处理 | 不完整 | 基本 | **完善** ✅ |
| 输出格式 | 不清晰 | 清晰 | **标准化JSON** ✅ |

---

**文档版本**：v3.0 最终版
**创建时间**：2025-12-04
**状态**：算法定稿，待实施
