# 24小时资金流分析功能 - 完成总结

## 📋 功能概述

为`/screening/daily/`筛选结果页面新增**24小时资金流分析**功能，通过分析1440根1分钟K线，定量展示资金流入流出情况。

**实施方案**: 分层级资金流 (Tiered Money Flow) - 方案C

---

## ✅ 已完成内容

### 1. 核心算法实现

**文件**: `grid_trading/services/money_flow_calculator.py`

**核心功能**:
- 按成交量P50/P90分位数分层统计（小单/中单/大单）
- 计算3个核心指标:
  - **大单净流入**: 大额订单的买入减卖出金额（USDT）
  - **资金流强度**: 整体主动买入占比（0-1）
  - **大单主导度**: 大单对资金流的影响程度（0-1）

**算法流程**:
```python
1. 计算成交量分位数阈值
   P50 = 中位数(Volume)  # 小单上限
   P90 = 90分位数(Volume)  # 中单上限

2. 分层统计买卖金额
   各层级分别计算:
   - 买入金额 = Σ (Close × TakerBuyVolume)
   - 卖出金额 = Σ (Close × (Volume - TakerBuyVolume))

3. 输出指标
   - large_net_flow = 大单买入 - 大单卖出
   - money_flow_strength = 总买入 / (总买入 + 总卖出)
   - large_dominance = |大单净| / (|小单净| + |中单净| + |大单净|)
```

### 2. 数据模型扩展

**文件**: `grid_trading/services/simple_scoring.py`

**新增字段**:
```python
@dataclass
class SimpleScore:
    # ... 现有字段 ...

    # 24小时资金流分析（新增）
    money_flow_large_net: float = 0.0        # 大单净流入金额 (USDT)
    money_flow_strength: float = 0.5         # 资金流强度 (0-1)
    money_flow_large_dominance: float = 0.0  # 大单主导度 (0-1)
```

### 3. 集成到筛选流程

**修改文件**:
- `grid_trading/services/indicator_calculator.py`
  - `calculate_all_indicators()` 返回值增加 `money_flow_metrics`

- `grid_trading/services/screening_engine.py`
  - 第198行和第373行：更新返回值解包

- `grid_trading/services/simple_scoring.py`
  - `score_and_rank()` 参数增加 `money_flow_metrics`
  - 创建 `SimpleScore` 时填充资金流字段

### 4. 前端展示

**文件**: `grid_trading/services/html_report.py`

**表格新增3列**:
| 列名 | 显示格式 | 颜色标识 |
|-----|---------|---------|
| 大单净流入 | $XX.XK | 正值绿色/负值红色 |
| 资金流强度 | 0.XXX | >0.55绿色/<0.45红色/中间灰色 |
| 大单主导度 | 0.XXX | 默认颜色 |

**示例展示**:
```
大单净流入: +$500.5K (绿色)
资金流强度: 0.642 (绿色，买盘主导)
大单主导度: 0.723 (72.3%的资金流由大单主导)
```

---

## 🎯 指标含义说明

### 1. 大单净流入 (Large Net Flow)

**定义**: 成交量位于P90以上（前10%）的订单，其买入金额与卖出金额之差。

**含义**:
- **正值**: 大额资金流入（机构/巨鲸在买入）
- **负值**: 大额资金流出（机构/巨鲸在卖出）
- **绝对值大**: 大资金活跃度高

**适用场景**:
- 判断主力资金动向
- 识别潜在的机构建仓/出货

### 2. 资金流强度 (Money Flow Strength)

**定义**: 全部主动买入成交额占总成交额的比例。

**含义**:
- **> 0.55**: 买盘主导（流入强）
- **0.45 - 0.55**: 买卖平衡
- **< 0.45**: 卖盘主导（流出强）

**适用场景**:
- 判断整体市场情绪
- 识别买卖力量对比

### 3. 大单主导度 (Large Dominance)

**定义**: 大单净流入的绝对值占所有层级净流入绝对值总和的比例。

**含义**:
- **> 0.7**: 大单高度主导（机构影响大）
- **0.3 - 0.7**: 大单与散户共同影响
- **< 0.3**: 散户主导（机构影响小）

**适用场景**:
- 判断主力资金参与程度
- 评估市场主导力量

---

## 📊 实际应用示例

### 示例1: 机构建仓信号
```
代币: XYZUSDT
大单净流入: +$2.5M (绿色) ← 大资金流入
资金流强度: 0.68 (绿色) ← 整体买盘主导
大单主导度: 0.85 ← 85%的资金流由大单驱动

分析: 机构可能在积极建仓，短期看涨
```

### 示例2: 散户情绪高涨
```
代币: ABCUSDT
大单净流入: +$300K (绿色) ← 大资金小幅流入
资金流强度: 0.72 (绿色) ← 整体买盘强劲
大单主导度: 0.15 ← 只有15%由大单驱动

分析: 散户FOMO情绪高涨，但缺乏机构支持，警惕回调
```

### 示例3: 主力出货警示
```
代币: DEFUSDT
大单净流入: -$1.8M (红色) ← 大资金流出
资金流强度: 0.45 (灰色) ← 买卖平衡
大单主导度: 0.92 ← 92%由大单驱动

分析: 机构在出货，但散户接盘力量尚可，需谨慎
```

---

## 🧪 测试验证

### 测试文件
`test_money_flow.py`

### 测试结果
```
✅ 测试成功！资金流计算器工作正常
✅ 边界情况测试通过
🎉 所有测试通过！功能正常！
```

### 测试覆盖
- ✅ 核心算法正确性
- ✅ 空数据处理
- ✅ 数据不足降级
- ✅ 极端情况（全部买入/卖出）
- ✅ 成交量分布统计

---

## 📝 使用方法

### 方式1: 日常筛选自动包含

运行日常筛选脚本时，资金流指标会自动计算并显示：

```bash
python manage.py run_daily_screening
```

查看生成的HTML报告：
```
screening_reports/daily_YYYY-MM-DD.html
```

### 方式2: 编程调用

```python
from grid_trading.services.money_flow_calculator import calculate_tiered_money_flow

# 假设已获取1440根1分钟K线
klines_1m = [...]

# 计算资金流指标
money_flow = calculate_tiered_money_flow(klines_1m)

print(f"大单净流入: ${money_flow['large_net_flow']:,.2f}")
print(f"资金流强度: {money_flow['money_flow_strength']:.3f}")
print(f"大单主导度: {money_flow['large_dominance']:.3f}")
```

---

## ⚙️ 参数配置

### 分层阈值

当前使用**自适应阈值**（推荐）:
- **P50 (中位数)**: 小单上限
- **P90 (90分位数)**: 中单上限

如需调整，修改 `money_flow_calculator.py`:
```python
def calculate_tiered_money_flow(klines_1m):
    # 修改分位数
    p50 = np.percentile(volumes, 50)  # 可改为40/60
    p90 = np.percentile(volumes, 90)  # 可改为85/95
```

### 数据降级

当1分钟K线数据不足100根时，自动返回默认值：
```python
{
    'large_net_flow': 0.0,
    'money_flow_strength': 0.5,  # 中性
    'large_dominance': 0.0
}
```

---

## 🚀 未来扩展（可选）

### 1. 历史对比
```python
# 显示与昨日对比
大单净流入: +$500K (↑20% vs昨日)
```

### 2. 可视化图表
```html
<!-- 三层级资金流柱状图 -->
<canvas id="money-flow-chart"></canvas>
```

### 3. 过滤条件
```python
# 筛选时添加条件
min_large_net_flow = 100000  # 只显示大单净流入>$100K的代币
```

### 4. 时间序列分析
```python
# 计算最近6小时、12小时、24小时的资金流趋势
money_flow_6h = calculate_tiered_money_flow(klines_1m[-360:])
money_flow_12h = calculate_tiered_money_flow(klines_1m[-720:])
money_flow_24h = calculate_tiered_money_flow(klines_1m)
```

---

## 📚 相关文档

- [方案设计文档](./MONEY_FLOW_ANALYSIS_SOLUTION.md)
- [实施计划](../../IMPLEMENTATION_PLAN.md)
- [网格策略算法](../GRID_STRATEGY_ALGORITHM.md)

---

**功能状态**: ✅ 已完成并通过测试
**版本**: v1.0
**完成日期**: 2025-12-10
**维护者**: 加密货币网格交易系统开发团队
