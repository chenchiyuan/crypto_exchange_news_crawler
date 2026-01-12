# Bug修复: DDPS推送格式增强

## 文档信息

| 属性 | 值 |
|------|-----|
| Bug编号 | bug-031 |
| 创建日期 | 2026-01-12 |
| 严重程度 | 中 |
| 影响范围 | DDPS监控推送消息格式 |

---

## 阶段1: 需求对齐

### 问题列表

| # | 问题描述 | 当前表现 | 期望行为 |
|---|----------|----------|----------|
| 1 | 42周期占比统计不完整 | `强势上涨(10%), 震荡(26%)` 只显示部分、固定顺序 | 统计全部5种类型，按占比高低排序，总和100% |
| 2 | 贝塔值倍数不一致 | `贝塔(-0.226)` 原始值 | `贝塔(-22.6%)` 乘以100与页面一致 |
| 3 | 价格状态缺少K线时间 | `BNBUSDT - 902.00 (震荡期)` | `BNBUSDT (01-12 20:00): 902.00 (震荡期)` |
| 4 | 订单缺少时间信息 | 买入/卖出信号无时间标记 | 添加产生时间和持有时长 |

### 需求确认
- [x] 用户已确认需求理解正确

---

## 阶段2: 问题现象描述

### 当前推送示例
```
价格状态:
  ETHUSDT: 3116.68 (震荡期)
    P5=3042.72 P95=3196.06
    惯性范围: 3042.72~3196.06
    概率: P47
    挂单价格: 3039.68
    所处周期: 震荡期 - ADX(15) - 贝塔(-0.226) - 连续0小时
    最近42周期占比: 强势上涨(10%), 震荡(26%)
    持仓订单 (1个):
      01-08 20:00 @ 3060.31 → 持仓97小时

买入信号 (1个):
  - ETHUSDT @ 3116.68 (震荡期)

卖出信号 (0个):
  无
```

### 期望推送示例
```
价格状态:
  ETHUSDT (01-12 20:00): 3116.68 (震荡期)
    P5=3042.72 P95=3196.06
    惯性范围: 3042.72~3196.06
    概率: P47
    挂单价格: 3039.68
    所处周期: 震荡期 - ADX(15) - 贝塔(-22.6%) - 连续0小时
    最近42周期占比: 震荡(64%), 强势下跌(26%), 强势上涨(10%)
    持仓订单 (1个):
      01-08 20:00 @ 3060.31 → 持仓97小时

买入信号 (1个):
  - ETHUSDT @ 3116.68 (震荡期) [01-12 20:00]

卖出信号 (1个):
  - 订单#abc ETHUSDT: EMA止盈 @ 3500.00 (开仓3200.00, +9.38%, 持仓48小时)
```

---

## 阶段3: 三层立体诊断

### 3.1 表现层诊断
- **问题1**: `_format_price_status_lines` 方法只遍历 `['bull_strong', 'consolidation', 'bear_strong']` 三种类型
- **问题2**: `_format_price_status_lines` 方法直接显示 `status.beta` 未乘以100
- **问题3**: `_format_price_status_lines` 方法首行缺少K线时间信息
- **问题4**: `format_push_message` 中买入/卖出信号格式化缺少时间信息

### 3.2 逻辑层诊断
- 周期占比计算正确（`_calculate_cycle_distribution`），但格式化时过滤了部分类型
- 贝塔值在DDPSCalculator中计算正确，但输出时未统一显示格式
- K线时间戳存在于数据中，但未在格式化时使用
- 买入/卖出信号数据结构中有时间戳，但未格式化输出

### 3.3 数据层诊断
- `PriceStatus` 模型缺少 `kline_timestamp` 字段
- `BuySignal` 模型缺少 `signal_timestamp` 字段
- `ExitSignal` 模型有 `buy_timestamp` 但缺少持仓时长计算

---

## 阶段4: 修复方案

### 方案概述

1. **数据模型扩展**: 为 `PriceStatus` 添加 `kline_timestamp` 字段
2. **格式化修复**: 修改 `_format_price_status_lines` 方法
3. **信号格式修复**: 修改买入/卖出信号的格式化逻辑

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `ddps_z/models.py` | PriceStatus添加kline_timestamp字段 |
| `ddps_z/services/ddps_monitor_service.py` | 格式化逻辑修复 |

---

## 阶段5: 实施修复

### 修复记录

#### 5.1 数据模型扩展 (`ddps_z/models.py`)

```python
# PriceStatus 新增字段
kline_timestamp: Optional[int] = None  # K线时间戳(毫秒)

# BuySignal 新增字段
signal_timestamp: Optional[int] = None  # 信号产生时间戳(毫秒)

# ExitSignal 新增字段
holding_hours: Optional[float] = None  # 持仓时长(小时)
```

#### 5.2 格式化逻辑修复 (`ddps_z/services/ddps_monitor_service.py`)

**问题1修复 - 42周期占比完整统计并排序** (第1019-1029行):
```python
# 收集所有周期类型并按占比降序排序
dist_items = []
for key, label in dist_labels.items():
    pct = status.cycle_distribution.get(key, 0)
    if pct > 0:  # 只显示占比>0的类型
        dist_items.append((label, pct))
# 按占比降序排序
dist_items.sort(key=lambda x: x[1], reverse=True)
```

**问题2修复 - 贝塔值乘以100** (第1001-1004行):
```python
if status.beta is not None:
    beta_pct = status.beta * 100
    cycle_details.append(f"贝塔({beta_pct:.1f}%)")
```

**问题3修复 - 价格状态添加K线时间** (第970-976行):
```python
if status.kline_timestamp:
    kline_time = datetime.fromtimestamp(status.kline_timestamp / 1000)
    time_str = kline_time.strftime('%m-%d %H:%M')
    lines.append(f"  {status.symbol} ({time_str}): {status.current_price:.2f} ({cycle_label})")
```

**问题4修复 - 买入信号添加时间** (第895-905行):
```python
if signal.signal_timestamp:
    signal_time = datetime.fromtimestamp(signal.signal_timestamp / 1000)
    time_str = signal_time.strftime('%m-%d %H:%M')
    lines.append(f"  - {signal.symbol} @ {signal.price:.2f} ({cycle_label}) [{time_str}]")
```

**问题4修复 - 卖出信号添加持仓时长** (第573-588行 + 第915-928行):
```python
# 计算持仓时长
if buy_timestamp > 0 and sell_timestamp > 0:
    holding_hours = (sell_timestamp - buy_timestamp) / (1000 * 60 * 60)

# 格式化输出
lines.append(f"  - 订单#{signal.order_id} {signal.symbol}: "
    f"{exit_label} @ {signal.exit_price:.2f} "
    f"(开仓{signal.open_price:.2f}, {signal.profit_rate:+.2f}%, "
    f"持仓{signal.holding_hours:.0f}小时)")
```

---

## 阶段6: 验证交付

### 验证清单

- [x] 42周期占比显示全部5种类型
- [x] 42周期占比按占比高低排序
- [x] 贝塔值显示为百分比形式
- [x] 价格状态首行包含K线时间
- [x] 买入信号包含产生时间
- [x] 卖出信号包含持有时长

---

## 修复完成

**状态**: 已完成
**完成日期**: 2026-01-12
