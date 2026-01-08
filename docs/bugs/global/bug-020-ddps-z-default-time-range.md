# Bug-020: DDPS-Z 详情页默认时间范围过短

## 问题描述

**页面**: `/ddps-z/detail/<symbol>/`

**现象**: 页面默认只显示最近3个月的数据，导致买卖点、阈值、惯性预测等分析功能受限。

**期望**: 默认显示从 2025-01-01 到最新K线的数据。

## 根因分析

### 前端配置

`ddps_z/templates/ddps_z/detail.html`:

```javascript
config: {
    symbol: '{{ symbol }}',
    apiBaseUrl: '/ddps-z/api',
    currentInterval: '4h',
    currentRange: '3m',  // <-- 默认3个月
    // ...
}
```

### 后端时间范围映射

`ddps_z/services/chart_data_service.py`:

```python
TIME_RANGE_DAYS = {
    '1w': 7,
    '1m': 30,
    '3m': 90,
    '6m': 180,
    '1y': 365,
    'all': None,  # None表示全部数据
}
```

当前不支持 "从2025年开始" 的时间范围。

## 修复方案

采用方案1: 添加 '2025' 时间范围

### 后端改动

`ddps_z/services/chart_data_service.py`:

1. 在 `TIME_RANGE_DAYS` 中添加:
```python
'2025': 'fixed_date',  # 固定日期：从2025-01-01开始
```

2. 在 `_parse_time_range` 方法中添加处理逻辑:
```python
elif days == 'fixed_date':  # '2025' - 固定日期范围
    # 从2025-01-01 00:00:00 UTC开始
    start_dt = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
```

### 前端改动

`ddps_z/templates/ddps_z/detail.html`:

1. 将默认配置改为:
```javascript
currentRange: '2025',
```

2. 添加 '2025' 按钮:
```html
<button type="button" class="btn btn-outline-secondary btn-sm active" data-range="2025">2025</button>
```

---

**创建时间**: 2026-01-07
**修复时间**: 2026-01-07
**状态**: ✅ 已修复
