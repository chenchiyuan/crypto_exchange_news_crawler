# 筛选系统 - 高点回落指标实现

## 📋 概述

本文档记录在做空网格筛选系统中新增"高点回落指标"的完整实现过程。

**实现日期**: 2024-12-04
**需求来源**: 用户需求 - 增强标的筛选能力，识别从高点回落的标的
**相关迁移**: `0016_add_drawdown_indicator.py`

---

## 🎯 功能目标

### 核心指标

**高点回落比例 (Drawdown from High)**

- **计算基础**: 300根4小时K线（约50天历史）
- **公式**: `回落比例 = (最高价 - 当前价) / 最高价 × 100%`
- **解释**:
  - **正值**: 当前价格低于历史高点（已回落）
  - **负值**: 当前价格高于历史高点（创新高）
  - **0值**: 当前价格等于历史高点

### 使用场景

1. **做空入场判断**: 标的已从高点回落，可能进入下跌趋势
2. **风险评估**: 识别价格位置，避免追高
3. **筛选过滤**: 按回落幅度过滤，如"回落≥20%"

---

## 🏗️ 实现架构

### 数据流

```
K线数据 (4h, 300根)
    ↓
calculate_high_drawdown()  # 计算高点和回落比例
    ↓
calculate_all_indicators()  # 整合到指标计算
    ↓
SimpleScore / ScreeningResultModel  # 保存到结果
    ↓
前端展示 + 筛选功能
```

---

## 📁 修改的文件

### 1. 指标计算函数

**文件**: `grid_trading/services/indicator_calculator.py`

#### 新增函数: `calculate_high_drawdown()`

```python
def calculate_high_drawdown(klines: List[Dict[str, Any]], current_price: float) -> Tuple[float, float]:
    """
    计算300根4h K线的最高价及当前价格的回落比例

    Args:
        klines: K线数据列表（建议300根4h K线=50天历史）
        current_price: 当前价格

    Returns:
        (highest_price, drawdown_pct)
        - highest_price: K线内的最高价
        - drawdown_pct: 回落比例（%），正值=回落，负值=创新高
    """
    if not klines or len(klines) == 0:
        return current_price, 0.0

    highs = [float(k["high"]) for k in klines]
    highest_price = max(highs)

    if highest_price == 0:
        return current_price, 0.0

    drawdown_pct = ((highest_price - current_price) / highest_price) * 100
    return highest_price, drawdown_pct
```

#### 集成到主计算函数

**位置**: `calculate_all_indicators()` 函数末尾

```python
# ========== 高点回落指标 (用于筛选) ==========
highest_price_300, drawdown_pct = calculate_high_drawdown(
    klines_4h,
    float(market_symbol.current_price)
)

return (volatility_metrics, trend_metrics, microstructure_metrics,
        atr_daily, atr_hourly, rsi_15m,
        highest_price_300, drawdown_pct)  # 新增返回值
```

---

### 2. 数据模型

**文件**: `grid_trading/django_models.py`

#### ScreeningResultModel 新增字段

```python
class ScreeningResultModel(models.Model):
    # ... 现有字段 ...

    # 高点回落指标（新增）
    highest_price_300 = models.DecimalField(
        '300根4h高点',
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        help_text='300根4h K线内的最高价'
    )
    drawdown_from_high_pct = models.FloatField(
        '高点回落(%)',
        default=0.0,
        help_text='当前价格相对300根4h高点的回落比例，正值=已回落，负值=创新高'
    )
```

#### to_dict() 方法更新

```python
def to_dict(self):
    return {
        # ... 现有字段 ...

        # 高点回落指标
        'highest_price_300': float(self.highest_price_300) if self.highest_price_300 else 0.0,
        'drawdown_from_high_pct': round(safe_float(self.drawdown_from_high_pct), 2),
    }
```

---

### 3. 筛选引擎

**文件**: `grid_trading/services/screening_engine.py`

#### 更新返回值解包

```python
# 所有调用 calculate_all_indicators() 的地方都需要更新为8个返回值
vol, trend, micro, atr_daily, atr_hourly, rsi_15m, highest_price_300, drawdown_pct = future.result()

indicators_data.append(
    (market_symbol, vol, trend, micro, atr_daily, atr_hourly, rsi_15m,
     highest_price_300, drawdown_pct)  # 新增参数
)
```

---

### 4. 评分模型

**文件**: `grid_trading/services/simple_scoring.py`

#### SimpleScore 数据类

```python
@dataclass
class SimpleScore:
    # ... 现有字段 ...

    # 高点回落指标（新增）
    highest_price_300: Decimal = None
    drawdown_from_high_pct: float = 0.0
```

#### score_and_rank() 方法

```python
def score_and_rank(
    self,
    indicators_data: List[Tuple[
        MarketSymbol, VolatilityMetrics, TrendMetrics, MicrostructureMetrics,
        float, float, float, float, float  # 8个返回值
    ]],
    # ...
) -> List[SimpleScore]:
    for (market_symbol, vol, trend, micro, atr_daily, atr_hourly,
         rsi_15m, highest_price_300, drawdown_pct) in indicators_data:

        results.append(
            SimpleScore(
                # ... 现有字段 ...
                highest_price_300=Decimal(str(highest_price_300)),
                drawdown_from_high_pct=drawdown_pct,
            )
        )
```

---

### 5. 管理命令

**文件**: `grid_trading/management/commands/screen_simple.py`

#### 保存到数据库

```python
screening_results.append(
    ScreeningResultModel(
        # ... 现有字段 ...

        # 高点回落指标
        highest_price_300=score.highest_price_300,
        drawdown_from_high_pct=score.drawdown_from_high_pct,
    )
)
```

---

### 6. 前端模板

**文件**: `grid_trading/templates/grid_trading/screening_index.html`

#### 表头

```html
<th class="sortable" data-column="drawdown_from_high_pct" style="text-align:right">
    高点回落%<span class="sort-indicator"></span>
</th>
```

#### 数据单元格（带颜色编码）

```html
<td style="text-align:right; font-family:var(--font-mono);
    color: ${(item.drawdown_from_high_pct || 0) > 0 ? 'var(--danger)' :
            ((item.drawdown_from_high_pct || 0) < 0 ? 'var(--success)' : 'var(--text-sub)')}">
    ${item.drawdown_from_high_pct !== undefined && item.drawdown_from_high_pct !== null
      ? fmtPct(item.drawdown_from_high_pct)
      : '0.00%'}
</td>
```

**颜色规则**:
- 🔴 **红色**: 正值（已回落）
- 🟢 **绿色**: 负值（创新高）
- ⚪ **灰色**: 0值（等于高点）

#### 筛选输入

```html
<div class="input-group">
    <label>高点回落 ≥</label>
    <input type="number" id="filterDrawdown" placeholder="0" step="1">
    <span style="font-size:var(--text-xs); color:var(--text-sub);
          margin-left:var(--space-1);">%</span>
</div>
```

#### 筛选逻辑

```javascript
const drawdownVal = parseFloat(document.getElementById('filterDrawdown').value);

filteredResults = allResults.filter(item => {
    // 高点回落筛选: 回落比例 >= 阈值 (正值表示已回落)
    if (!isNaN(drawdownVal) && (item.drawdown_from_high_pct || 0) < drawdownVal) {
        return false;
    }
    return true;
});
```

---

## 🗃️ 数据库迁移

**文件**: `grid_trading/migrations/0016_add_drawdown_indicator.py`

```python
operations = [
    migrations.AddField(
        model_name='screeningresultmodel',
        name='drawdown_from_high_pct',
        field=models.FloatField(default=0.0, help_text='当前价格相对300根4h高点的回落比例，正值=已回落，负值=创新高', verbose_name='高点回落(%)'),
    ),
    migrations.AddField(
        model_name='screeningresultmodel',
        name='highest_price_300',
        field=models.DecimalField(blank=True, decimal_places=8, help_text='300根4h K线内的最高价', max_digits=20, null=True, verbose_name='300根4h高点'),
    ),
]
```

**执行命令**:
```bash
python manage.py makemigrations grid_trading --name add_drawdown_indicator
python manage.py migrate grid_trading
```

---

## ✅ 测试结果

### 样本数据验证

执行筛选后的样本结果：

| Symbol | 当前价格 | 300根4h高点 | 高点回落% | 解释 |
|--------|----------|-------------|-----------|------|
| ICPUSDT | $3.821 | $9.844 | **+61.18%** | 从高点回落61.18% |
| ZENUSDT | $9.30 | $25.00 | **+62.80%** | 从高点回落62.80% |
| QNTUSDT | $94.24 | $108.00 | **+12.74%** | 从高点回落12.74% |

### 功能验证

✅ **计算准确性**: 公式计算正确
✅ **数据持久化**: 成功保存到数据库
✅ **前端展示**: 正确显示并支持排序
✅ **筛选功能**: 按回落幅度过滤正常工作
✅ **颜色编码**: 正值红色、负值绿色显示正确

---

## 🔧 使用示例

### 命令行筛选

```bash
# 筛选所有标的（包含高点回落指标）
python manage.py screen_simple --min-volume 100000000

# 查看筛选结果（数据库）
python manage.py shell -c "
from grid_trading.models import ScreeningResultModel, ScreeningRecord
record = ScreeningRecord.objects.latest('created_at')
results = ScreeningResultModel.objects.filter(record=record).order_by('-drawdown_from_high_pct')[:5]

for r in results:
    print(f'{r.symbol}: 高点${r.highest_price_300} → 当前${r.current_price}, 回落{r.drawdown_from_high_pct:.2f}%')
"
```

### 前端使用

1. **访问**: http://127.0.0.1:8000/screening/
2. **查看高点回落列**: 表格中新增"高点回落%"列
3. **筛选**:
   - 输入框输入"20"
   - 点击"应用筛选"
   - 只显示回落≥20%的标的

---

## 📊 业务价值

### 对做空网格策略的意义

1. **入场时机判断**
   - 回落≥30%: 可能已进入下跌通道，适合做空
   - 回落10-30%: 观察期，需结合其他指标
   - 回落<10% 或 负值: 价格在高位/创新高，风险较高

2. **风险控制**
   - 避免在创新高时（负值）盲目做空
   - 识别"高位盘整"标的（回落5-15%）

3. **配合其他指标**
   - 高点回落 + VDR高 + KER低 = 震荡下跌
   - 高点回落 + EMA99负斜率 = 趋势性下跌

---

## ⚠️ 注意事项

### 数据要求

- **最低要求**: 168根4h K线（约28天）
- **推荐要求**: 300根4h K线（约50天）
- **数据不足时**: 返回当前价格作为最高价，回落比例=0

### 特殊情况处理

1. **新上市合约**
   - K线数量不足300根
   - 使用现有数据计算，但可能不准确

2. **长期上涨标的**
   - 回落比例可能为负值（当前价>历史高点）
   - 这是正常现象，代表创新高

3. **横盘标的**
   - 回落比例在±5%之间波动
   - 需配合震荡指标(VDR/KER)综合判断

---

## 🔄 后续优化方向

### 可能的改进

1. **多时间周期对比**
   - 添加"100根4h高点回落"（短期）
   - 添加"500根4h高点回落"（长期）

2. **回落速度指标**
   - 计算从高点到当前的天数
   - `回落速度 = 回落幅度 / 天数`

3. **反弹力度预测**
   - 统计历史上"回落X%后的反弹概率"
   - 辅助止盈位设置

---

## 📚 相关文档

- [筛选系统快速入门](./SCREENING_QUICKSTART.md)
- [筛选工作流程](./SCREENING_WORKFLOW.md)
- [网格参数详解](./GRID_PARAMETERS_EXPLAINED_SIMPLE.md)
- [入场算法最终版](./entry_algorithm_final.md)

---

## 📝 更新日志

| 日期 | 版本 | 变更内容 |
|------|------|----------|
| 2024-12-04 | v1.0 | 初始版本，实现高点回落指标 |

---

**文档维护**: Claude Code
**最后更新**: 2024-12-04
