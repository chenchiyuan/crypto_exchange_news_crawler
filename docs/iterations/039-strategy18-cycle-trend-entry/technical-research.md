# 技术调研 - 策略18：周期趋势入场策略

## 文档信息
- **迭代编号**: 039
- **创建日期**: 2026-01-13

---

## 1. 架构兼容性评估

### 1.1 现有架构分析

策略18基于现有策略框架开发，完全兼容现有架构：

| 组件 | 兼容性 | 说明 |
|-----|--------|-----|
| IStrategy接口 | ✅ 完全兼容 | 实现标准策略接口 |
| 回测框架 | ✅ 完全兼容 | 使用run_backtest模式 |
| 指标计算器 | ✅ 完全兼容 | 复用EMA/EWMA/ADX/Inertia计算器 |
| 挂单模型 | ✅ 完全兼容 | 复用PendingOrder数据结构 |
| 配置文件 | ✅ 完全兼容 | JSON配置格式 |

### 1.2 可复用组件

| 组件 | 来源文件 | 复用方式 |
|-----|---------|---------|
| `BetaCycleCalculator` | ddps_z/calculators/beta_cycle_calculator.py | 直接调用calculate()获取cycle_phases |
| `_calculate_cycle_distribution()` | ddps_z/services/ddps_monitor_service.py | 提取为独立方法或内联实现 |
| `EMACalculator` | ddps_z/calculators/ema_calculator.py | 计算EMA7/EMA25/EMA99 |
| `EWMACalculator` | ddps_z/calculators/ewma_calculator.py | 计算波动率 |
| `ADXCalculator` | ddps_z/calculators/adx_calculator.py | 计算ADX |
| `InertiaCalculator` | ddps_z/calculators/inertia_calculator.py | 计算β值 |
| `PendingOrder` | strategy_adapter/models/pending_order.py | 挂单数据结构 |

---

## 2. 技术选型

### 2.1 策略实现方式

**选择**: 独立策略类（参考Strategy16/17模式）

**理由**:
- 策略18有独特的周期状态判断逻辑
- 双挂单机制与现有策略不同
- 便于独立测试和维护

### 2.2 周期占比计算

**选择**: 内联实现（复制_calculate_cycle_distribution逻辑）

**理由**:
- 避免引入DDPSMonitorService依赖
- 代码简单（约20行）
- 保持策略类独立性

### 2.3 EMA25斜率计算

**选择**: 使用numpy向量化计算

```python
# 计算斜率序列
slopes = np.diff(ema25_series)  # slopes[i] = ema25[i+1] - ema25[i]

# 判断当前斜率是否为近6根最高
def is_slope_highest(slopes, window=6):
    if len(slopes) < window:
        return False
    recent = slopes[-window:]
    return slopes[-1] == np.max(recent)
```

---

## 3. 技术风险

### 3.1 风险识别

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| 双挂单资金管理复杂 | 中 | 每笔挂单独立管理，冻结/释放逻辑清晰 |
| 周期状态止盈时机 | 低 | 使用metadata标记，避免重复触发 |
| 指标计算顺序 | 低 | 复用策略16/17的指标计算流程 |

### 3.2 边界情况

1. **数据不足42根K线**: 使用实际数量计算占比
2. **数据不足6根K线**: 斜率判断返回False，不触发买入
3. **两笔挂单同时成交**: 独立处理，各自记录持仓

---

## 4. 性能评估

| 指标 | 预期值 | 依据 |
|-----|-------|-----|
| 单根K线处理时间 | <10ms | 参考策略16性能 |
| 1年4h数据回测 | <30s | 约2190根K线 |
| 内存占用 | <500MB | 纯内存计算 |

---

## 5. 结论

策略18完全兼容现有架构，可复用大量现有组件，技术风险可控。建议采用独立策略类实现，参考Strategy16/17的代码结构。
