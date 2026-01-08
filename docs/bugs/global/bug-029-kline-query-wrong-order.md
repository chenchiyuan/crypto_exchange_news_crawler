# Bug-029: K线查询顺序错误导致价格不准确

## 文档信息

| 属性 | 值 |
|------|-----|
| Bug编号 | 029 |
| 创建日期 | 2026-01-08 |
| 完成日期 | 2026-01-08 |
| 状态 | ✅ 已修复 |
| 严重程度 | 高 |
| 影响范围 | DDPS监控服务所有价格计算 |
| 关联迭代 | 023-ddps-price-monitor |

---

## 问题描述

推送的价格与实时价格差距非常大，例如：
- ETHUSDT 推送价格: 2783，实际价格: 3095
- BTCUSDT 推送价格: 83849，实际价格: 89687

---

## 根因分析

### 问题代码

`ddps_z/services/ddps_monitor_service.py` 第264-268行：

```python
queryset = KLine.objects.filter(
    symbol=symbol,
    interval=self.interval,
    market_type=self.market_type
).order_by('open_time')[:500]  # ← 错误：正序取前500
```

### 根因

`order_by('open_time')[:500]` 按时间**正序**排序后取前500条，实际获取的是**最早的500根K线**，而不是最新的。

### 证据

```
【错误查询】order_by("open_time")[:500]
第一条: 2024-12-02 08:00:00 - 收盘价: 3588.99
最后条: 2025-02-23 12:00:00 - 收盘价: 2783.00  ← 这就是推送的价格

【正确查询】order_by("-open_time")[:500]
最新K线: 2026-01-08 04:00:00 - 收盘价: 3095.25  ← 应该是这个价格
```

---

## 修复方案

### 修改内容

```python
# 修复前（错误）
queryset = KLine.objects.filter(...).order_by('open_time')[:500]

# 修复后（正确）
queryset = KLine.objects.filter(...).order_by('-open_time')[:500]
# 然后反转为时间正序
data.reverse()
```

### 修改文件

- `ddps_z/services/ddps_monitor_service.py`: `_load_klines` 方法

---

## 验证结果

```
【修复后价格一致性检查】
  ETHUSDT: 监控=3095.25, DB=3095.25 ✓ 一致
  BTCUSDT: 监控=89687.8, DB=89687.80 ✓ 一致
```

推送成功，价格正确：
```
标题: 01-08 15:39: 买入(1) 卖出(0) 上涨预警(0) 下跌预警(1)

价格状态:
  ETHUSDT: 3095.25 (下跌预警)
  BTCUSDT: 89687.80 (下跌强势)
  ...
```

---

## 经验教训

在使用 Django ORM 进行分页查询时，需要注意排序方向：
- `order_by('field')[:N]` 取的是最小的N条
- `order_by('-field')[:N]` 取的是最大的N条

如果需要"最新的N条按时间正序"，需要先倒序取，再反转结果。
