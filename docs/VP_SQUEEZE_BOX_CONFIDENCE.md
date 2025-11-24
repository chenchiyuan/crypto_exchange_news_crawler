# VP-Squeeze 箱体范围和置信率使用指南

## 概述

VP-Squeeze服务现在支持直接获取**箱体范围**和**置信率**，帮助你更准确地判断交易机会。

## 核心概念

### 📦 箱体范围 (Box Range)

- **支撑位 (Support)**: VAL（Value Area Low），价格下方的强支撑位
- **压力位 (Resistance)**: VAH（Value Area High），价格上方的强阻力位
- **中点 (Midpoint)**: VPOC（Volume Point of Control），成交量重心
- **箱体宽度**: (VAH - VAL) / VPOC × 100%，表示价格波动范围

### 📊 置信率 (Confidence Score)

综合多因子评分（0-100%），评估箱体的可靠性：

| 因子 | 权重 | 说明 |
|------|------|------|
| **Squeeze状态** | 30% | 连续满足条件的K线数，越多越可靠 |
| **成交量集中度** | 35% | 箱体内成交量占比，越高越可靠 |
| **价格波动率** | 20% | BB宽度相对价格，越窄越可靠 |
| **区间宽度** | 15% | 箱体宽度占价格比例，越窄越可靠 |

**置信率分级**：
- ≥70%: 高置信，建议交易
- 50-70%: 中等置信，谨慎交易
- <50%: 低置信，不建议交易

## 使用方式

### 1. 命令行文本输出

```bash
python manage.py vp_analysis --symbol eth --interval 4h
```

**输出示例**：
```
═════════════════════════════════════════════════════════════════
VP-Squeeze Analysis: ETHUSDT (4h) | 2025-11-24 10:52 UTC
═════════════════════════════════════════════════════════════════

─────────────────────────────────────────────────────────────────
📦 箱体范围
─────────────────────────────────────────────────────────────────
   支撑位:   $2,625.12
   压力位:   $3,345.13
   中点:     $3,189.64
   箱体宽度: 22.57%

─────────────────────────────────────────────────────────────────
📊 置信率
─────────────────────────────────────────────────────────────────
   综合置信率: 37% [███░░░░░░░]
   ├─ Squeeze状态:   0% (权重30%)
   ├─ 成交量集中度: 70% (权重35%)
   ├─ 价格波动率:   51% (权重20%)
   └─ 区间宽度:     15% (权重15%)
```

### 2. JSON格式输出

```bash
python manage.py vp_analysis --symbol eth --interval 4h --json
```

**JSON结构**：
```json
{
  "symbol": "ETHUSDT",
  "interval": "4h",
  "timestamp": "2025-11-24T10:52:47+00:00",
  "box": {
    "support": 2625.17,      // 支撑位
    "resistance": 3345.21,   // 压力位
    "midpoint": 3189.71,     // 中点
    "range_pct": 22.57       // 箱体宽度百分比
  },
  "confidence": {
    "value": 0.3693,         // 置信率 0-1
    "pct": 37,               // 置信率百分比
    "factors": {             // 各因子得分
      "squeeze": 0.0,
      "volume_concentration": 0.701,
      "volatility": 0.5075,
      "range_width": 0.1495
    }
  }
}
```

### 3. 批量分析

```bash
python manage.py vp_analysis --group major --interval 1h
```

**输出示例**：
```
═══════════════════════════════════════════════════════════════════════════════════════════════
VP-Squeeze 批量分析结果 | 2025-11-24 10:53 UTC
共分析 4 个交易对
═══════════════════════════════════════════════════════════════════════════════════════════════

交易对          周期     支撑位            压力位            箱体宽度       置信率      Squeeze
───────────────────────────────────────────────────────────────────────────────────────────────
BTCUSDT      1h     $83,338.90     $87,811.17       5.15%     53%     ✗无效
ETHUSDT      1h     $2,718.58      $2,858.57        4.95%     82%     ✓有效
BNBUSDT      1h     $807.86        $855.93          5.80%     83%     ✓有效
SOLUSDT      1h     $125.46        $133.34          6.18%     49%     ✗无效

═══════════════════════════════════════════════════════════════════════════════════════════════

🎯 发现 2 个高置信率（≥60%）交易对:
   • BNBUSDT: 支撑=$807.86, 压力=$855.93, 置信率=83%
   • ETHUSDT: 支撑=$2,718.58, 压力=$2,858.57, 置信率=82%
```

### 4. Python代码调用

```python
import os
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')
django.setup()

from vp_squeeze.services.vp_squeeze_analyzer import analyze

# 执行分析
result = analyze(symbol='eth', interval='4h', limit=100)

# 获取箱体范围
if result.box:
    print(f"支撑位: ${result.box.support:.2f}")
    print(f"压力位: ${result.box.resistance:.2f}")
    print(f"中点: ${result.box.midpoint:.2f}")
    print(f"箱体宽度: {result.box.range_pct:.2f}%")

# 获取置信率
if result.confidence:
    print(f"置信率: {result.confidence.confidence_pct}%")
    print(f"Squeeze得分: {result.confidence.squeeze_score * 100:.0f}%")
    print(f"成交量集中度: {result.confidence.volume_concentration * 100:.0f}%")
    print(f"价格波动率: {result.confidence.volatility_score * 100:.0f}%")
    print(f"区间宽度得分: {result.confidence.range_score * 100:.0f}%")

# 转为字典（用于API响应）
data = result.to_dict()
box = data['box']
confidence = data['confidence']
```

### 5. 数据库查询

```python
from vp_squeeze.models import VPSqueezeResult
from vp_squeeze.services.vp_squeeze_analyzer import analyze, save_result

# 先保存结果
result = analyze('eth', '4h')
save_result(result)

# 从数据库查询
latest = VPSqueezeResult.objects.filter(
    symbol='ETHUSDT',
    interval='4h'
).order_by('-analyzed_at').first()

if latest:
    print(f"支撑位: ${float(latest.val):.2f}")
    print(f"压力位: ${float(latest.vah):.2f}")

    # 箱体和置信率存储在raw_result JSON字段
    box = latest.raw_result.get('box', {})
    confidence = latest.raw_result.get('confidence', {})

    print(f"箱体宽度: {box.get('range_pct')}%")
    print(f"置信率: {confidence.get('pct')}%")
```

## 交易策略示例

```python
result = analyze('eth', '4h')

# 判断是否适合交易
if result.confidence and result.confidence.confidence_pct >= 70:
    print(f"✅ 高置信率 ({result.confidence.confidence_pct}%)，建议交易")
    print(f"入场区间: ${result.box.support:.2f} - ${result.box.resistance:.2f}")

    # 设置止损和止盈
    stop_loss = result.box.support * 0.98  # 支撑位下2%
    take_profit = result.box.resistance * 1.02  # 压力位上2%

    print(f"止损: ${stop_loss:.2f}")
    print(f"止盈: ${take_profit:.2f}")

elif result.confidence and result.confidence.confidence_pct >= 50:
    print(f"⚠️  中等置信率 ({result.confidence.confidence_pct}%)，谨慎交易")
    print(f"箱体宽度 {result.box.range_pct:.2f}% 可能较大，注意风险控制")

else:
    print(f"❌ 低置信率，不建议交易")
    print("等待更明确的信号")
```

## 置信率计算细节

### Squeeze状态得分

```
连续K线数 <= 3: 60%
连续K线数 = 5:  80%
连续K线数 >= 7: 100%
中间值线性插值
```

### 成交量集中度得分

```
VAL-VAH区间内成交量 / 总成交量
>= 85%: 100分
70-85%: 70-100分（线性）
< 70%:  按比例降低
```

### 价格波动率得分

```
BB宽度 / 价格
<= 2%:  90-100分
2-5%:   60-90分
5-10%:  30-60分
> 10%:  10-30分
```

### 区间宽度得分

```
(VAH - VAL) / VPOC
<= 3%:  90-100分
3-8%:   50-90分
8-15%:  20-50分
> 15%:  10-20分
```

## 常见问题

**Q: 置信率很低怎么办？**
- 等待更明确的市场信号
- 尝试更换时间周期（如1h → 4h）
- 关注Squeeze状态是否即将激活

**Q: 箱体宽度很大怎么办？**
- 说明价格波动范围大，风险较高
- 考虑减少仓位或等待箱体收窄
- 可能需要更大的止损空间

**Q: 如何选择时间周期？**
- 短线交易：1h, 4h
- 中线交易：1d
- 长线交易：1w
- 不同周期可以互相验证

**Q: 高置信率一定赚钱吗？**
- 不保证，只是提高胜率
- 仍需配合其他技术指标
- 风险管理永远是第一位

## 更多示例

完整示例代码请查看项目根目录的 `example_box_confidence.py`。
