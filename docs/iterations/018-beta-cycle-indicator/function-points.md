# 功能点清单: β宏观周期指标

**迭代编号**: 018
**创建时间**: 2026-01-07

---

## 功能点列表

### 后端功能

| ID | 功能点 | 优先级 | 描述 |
|----|--------|--------|------|
| BE-001 | 阈值配置定义 | P0 | 在Django settings中定义β周期阈值配置 |
| BE-002 | 周期计算器 | P0 | 实现BetaCycleCalculator类，基于状态机计算周期 |
| BE-003 | 集成到chart_data_service | P0 | 在get_chart_data中调用周期计算，返回cycle_phase |
| BE-004 | 当前周期统计 | P0 | 计算当前周期状态、持续时间、起始价格等 |

### 前端功能

| ID | 功能点 | 优先级 | 描述 |
|----|--------|--------|------|
| FE-001 | HUD周期状态显示 | P0 | 在HUD区域显示当前周期状态（文字+颜色） |
| FE-002 | HUD周期持续时间 | P0 | 显示当前周期已持续的K线数量和时间 |
| FE-003 | Hover周期信息 | P0 | K线hover时显示该K线的周期标记 |
| FE-004 | K线背景色标记 | P1 | 根据周期在K线图上添加背景色区域 |

---

## 功能点详情

### BE-001: 阈值配置定义

**位置**: `listing_monitor_project/settings.py`

```python
DDPS_CONFIG = {
    # 现有配置...

    # β周期阈值配置（前端显示值，原始值需/100）
    'BETA_CYCLE_THRESHOLDS': {
        'bull_warning': 600,      # 上涨预警阈值
        'bull_strong': 1000,      # 强势上涨确认阈值
        'bear_warning': -600,     # 下跌预警阈值
        'bear_strong': -1000,     # 强势下跌确认阈值
        'cycle_end': 0,           # 周期结束阈值
    },
}
```

**验收条件**:
- [ ] 阈值定义在settings中
- [ ] 可通过环境变量覆盖

---

### BE-002: 周期计算器

**位置**: `ddps_z/calculators/beta_cycle_calculator.py`（新建）

**输入**:
- beta序列: List[float]（原始β值，非显示值）
- 阈值配置: Dict

**输出**:
- cycle_phases: List[str]（每根K线的周期标记）
- current_cycle: Dict（当前周期统计信息）

**状态机定义**:
```
状态: idle -> bull_warning -> bull_strong -> idle
状态: idle -> bear_warning -> bear_strong -> idle
```

**验收条件**:
- [ ] 状态机逻辑正确
- [ ] 边界条件处理完整
- [ ] 单元测试覆盖

---

### BE-003: 集成到chart_data_service

**位置**: `ddps_z/services/chart_data_service.py`

**修改点**:
1. 在`get_chart_data`方法末尾调用周期计算
2. 在`fan['kline_data']`中添加`cycle_phase`字段
3. 在返回数据中添加`current_cycle`统计

**验收条件**:
- [ ] API返回包含cycle_phase
- [ ] 每根K线都有周期标记

---

### BE-004: 当前周期统计

**输出字段**:
```python
current_cycle = {
    'phase': 'bull_strong',           # 当前周期状态
    'phase_label': '强势上涨',         # 中文标签
    'duration_bars': 25,              # 持续K线数
    'duration_hours': 100,            # 持续小时数
    'start_time': '2026-01-03 08:00', # 周期开始时间
    'start_price': 3500.00,           # 周期开始价格
    'current_beta': 1250,             # 当前β值（显示值）
    'max_beta': 1800,                 # 周期内最大β值
}
```

---

### FE-001: HUD周期状态显示

**位置**: `ddps_z/templates/ddps_z/detail.html` HUD区域

**显示内容**:
- 周期状态文字（强势上涨/强势下跌/震荡/上涨预警/下跌预警）
- 状态颜色（绿/红/灰）

**样式**:
```html
<div id="hud-cycle" class="badge bg-success">强势上涨</div>
```

---

### FE-002: HUD周期持续时间

**显示内容**:
- 已持续 X 根K线
- 已持续 X 小时/天

---

### FE-003: Hover周期信息

**修改位置**: `updateHUD` 方法

**显示内容**:
在现有hover信息中添加：
- 周期: 强势上涨

---

### FE-004: K线背景色标记 (P1)

**实现方式**:
- 使用TradingView轻量图表的区域标记功能
- 或使用半透明矩形覆盖

**颜色定义**:
- 强势上涨: rgba(40, 167, 69, 0.1)
- 强势下跌: rgba(220, 53, 69, 0.1)
- 震荡期: 无背景

---

## 依赖关系

```
BE-001 (配置)
   ↓
BE-002 (计算器)
   ↓
BE-003 (集成) → BE-004 (统计)
   ↓
FE-001/002/003 (前端显示)
   ↓
FE-004 (背景色)
```

---

## 测试要点

1. **状态机测试**
   - 完整上涨周期: idle → warning → strong → idle
   - 未确认周期: idle → warning → idle（未达1000）
   - 边界值测试: β恰好等于阈值

2. **前端测试**
   - 刷新页面后状态正确
   - 切换时间范围后状态更新
   - Hover信息显示正确

---

**创建人**: PowerBy Product
**最后更新**: 2026-01-07
