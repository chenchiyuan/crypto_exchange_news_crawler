# Bug-Fix Report #030 - KLineRepository normalize导致数据查询失败

## 一、问题报告

### 1.1 需求对齐与澄清

**相关需求**:
- PRD: docs/iterations/024-ddps-multi-market-support/prd.md
- Architecture: docs/iterations/024-ddps-multi-market-support/architecture.md

**正确状态定义**:
1. 当数据库有数据时，`result.price_status` 应不为空
2. `result.update_stats['calculated_symbols'] > 0`
3. 默认配置使用4h周期，数据库中有大量4h数据

### 1.2 问题描述

运行 `python manage.py ddps_monitor --dry-run` 时，返回的 `price_status` 为空，
但数据库中有大量4h周期的K线数据（838770条futures，794300条spot）。

### 1.3 证据链

**数据库数据**:
```
market_type='futures': 838770 条
market_type='spot': 794300 条
```

**normalize行为**:
```python
MarketType.normalize('futures') -> 'crypto_futures'
MarketType.normalize('spot') -> 'crypto_spot'
```

**查询结果**:
```
使用 'crypto_futures' 查询: 0 条
使用 'futures' 查询: 838770 条
```

---

## 二、诊断分析

### 2.1 三层立体诊断

#### 数据层诊断
- **代码分析**: `KLineRepository.load()` 调用 `_normalize_market_type()`
- **表现分析**: 将 'futures' 转换为 'crypto_futures' 后查询数据库
- **验证结论**:
  - ❌ 数据层存在问题：normalize后的值与数据库存储值不匹配

#### 逻辑层诊断
- **代码分析**: `DDPSMonitorService.monitor()` 调用 `repository.load()`
- **表现分析**: klines返回空列表，导致 `_calculate_symbol_indicators()` 返回None
- **验证结论**:
  - ✅ 逻辑层正确：正确处理空数据

#### 表现层诊断
- **代码分析**: `ddps_monitor` 命令显示结果
- **表现分析**: 显示"交易对数量"但无实际数据
- **验证结论**:
  - ✅ 表现层正确：正确反映了空数据

### 2.2 根因定位

**根因**: `MarketType.normalize()` 设计用于将旧格式（futures/spot）转换为新格式（crypto_futures/crypto_spot），
但 `KLineRepository` 错误地将此方法用于数据库查询，导致查询条件与数据库存储值不匹配。

**所在层**: 数据层 (`ddps_z/datasources/repository.py`)
**具体位置**: `KLineRepository._normalize_market_type()` 方法的使用
**触发机制**: 任何调用 `load()` 方法且传入 'futures' 或 'spot' 的场景

---

## 三、修复方案确认

### 3.1 方案分析

#### 方案A：修改normalize逻辑为反向映射
- **描述**: 让 `normalize('crypto_futures')` 返回 `'futures'`
- **优点**: 快速修复
- **缺点**: 语义混乱，normalize本意是标准化为新格式
- **风险**: 高 - 会影响其他使用normalize的地方

#### 方案B：KLineRepository使用反向映射（推荐）
- **描述**: 在 `KLineRepository` 中添加 `_to_db_format()` 方法，将新格式转回旧格式用于数据库查询
- **优点**: 保持normalize语义，仅在数据库交互层做适配
- **缺点**: 需要添加新方法
- **风险**: 低 - 仅影响Repository层

#### 方案C：迁移数据库数据
- **描述**: 将数据库中的 'futures' 更新为 'crypto_futures'
- **优点**: 数据规范化
- **缺点**: 需要数据迁移，影响面大
- **风险**: 高 - 可能影响其他依赖旧格式的代码

### 3.2 推荐方案

**推荐**: 方案B - KLineRepository使用反向映射

**理由**:
1. 保持 `MarketType.normalize()` 的语义（用于API层展示）
2. 仅在数据库交互层做适配，影响面最小
3. 向后兼容，不需要数据迁移

---

## 四、实施修复

### 4.1 修改明细

**文件**: `ddps_z/datasources/repository.py`

**修改内容**: 添加 `_to_db_format()` 方法，将新格式转回旧格式用于数据库查询

```python
def _to_db_format(self, market_type: str) -> str:
    """
    将market_type转换为数据库存储格式

    数据库中存储的是旧格式（futures/spot），
    需要将新格式转回旧格式用于查询。
    """
    db_mapping = {
        'crypto_futures': 'futures',
        'crypto_spot': 'spot',
    }
    return db_mapping.get(market_type, market_type)
```

---

## 五、验证测试

### 5.1 单元测试

**_to_db_format方法测试**:
```
_to_db_format测试:
  crypto_futures -> futures  ✓
  crypto_spot -> spot        ✓
  futures -> futures         ✓
  spot -> spot               ✓
```

**数据加载测试**:
```
数据加载测试 (ETHUSDT 4h crypto_futures):
  加载数量: 10 条  ✓
  第一条: timestamp=1767801600000, close=3144.37
  最后一条: timestamp=1767931200000, close=3117.47
```

### 5.2 集成测试

**DDPSMonitorService测试**:
```
监控结果:
  交易对数量: 1
  计算成功: 1     ✓
  计算失败: 0
  买入信号: 0
  卖出信号: 0
  价格状态数量: 1  ✓

价格状态详情:
  ETHUSDT:
    当前价格: 3117.47
    周期阶段: bear_warning
    P5: 3051.04
    P95: 3244.92
    概率: P30
```

**ddps_monitor命令测试**:
```
=== DDPS价格监控服务 ===
市场: crypto_futures
交易对: ETHUSDT
周期: 4h

[步骤2] 计算指标和检测信号
  交易对数量: 1
  买入信号: 0 个
  卖出信号: 0 个
  周期分布:
    下跌预警: ETHUSDT
  ✓ 指标计算完成

✓ 监控完成，耗时: 0.5秒
```

### 5.3 回归测试

- [x] 使用新格式 `crypto_futures` 可以正确加载数据
- [x] 使用旧格式 `futures` 也可以正确加载数据（兼容）
- [x] DDPSMonitorService正确返回价格状态
- [x] ddps_monitor命令正常工作

---

## 六、交付归档

### 6.1 修改文件

| 文件 | 修改内容 |
|------|----------|
| `ddps_z/datasources/repository.py` | 将 `_normalize_market_type()` 替换为 `_to_db_format()`，反向映射新格式到旧格式 |

### 6.2 代码差异

```diff
- def _normalize_market_type(self, market_type: str) -> str:
-     """
-     标准化market_type（向后兼容）
-     """
-     return MarketType.normalize(market_type)
+ def _to_db_format(self, market_type: str) -> str:
+     """
+     将market_type转换为数据库存储格式
+
+     数据库中存储的是旧格式（futures/spot），
+     需要将新格式转回旧格式用于数据库查询。
+
+     Bug-030: 修复normalize导致查询不匹配的问题
+     """
+     db_mapping = {
+         'crypto_futures': 'futures',
+         'crypto_spot': 'spot',
+     }
+     return db_mapping.get(market_type, market_type)
```

### 6.3 总结

- **修复时间**: 约15分钟
- **根因**: `MarketType.normalize()` 将旧格式转为新格式，但数据库存储的是旧格式，导致查询不匹配
- **解决方案**: 在 `KLineRepository` 中使用反向映射 `_to_db_format()` 将新格式转回旧格式用于数据库查询
- **影响范围**: 仅影响 `KLineRepository` 的数据库查询
- **预防措施**: 未来如需数据库迁移，应统一数据格式

### 6.4 状态

- **状态**: ✅ 已修复并验证
- **修复日期**: 2026-01-09
