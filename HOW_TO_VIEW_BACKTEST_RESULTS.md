# 如何查看回测结果 - 完整指南

## 📊 三种查看方式对比

| 方式 | 适用场景 | 优点 | 缺点 |
|------|---------|------|------|
| **Web播放器** | 可视化分析、演示 | 直观、交互式、动画播放 | 需要启动服务 |
| **命令行查询** | 快速查看、脚本使用 | 快速、灵活、可编程 | 不够直观 |
| **生成报告** | 深度分析、存档 | 完整、专业、可分享 | 生成时间较长 |

---

## 方式1：Web可视化播放器（推荐）⭐⭐⭐⭐⭐

### 1.1 启动服务

```bash
# 启动Django服务（如果还没启动）
python manage.py runserver 8001
```

### 1.2 访问播放器

在浏览器中打开：**http://127.0.0.1:8001/backtest/player/**

### 1.3 使用步骤

1. **选择回测记录**
   - 在顶部下拉菜单中选择一个回测记录
   - 显示策略名称、交易对、收益率等基本信息

2. **查看核心指标**
   - 页面顶部显示关键指标卡片
   - 包括：收益率、最大回撤、胜率、交易次数等

3. **观看回测播放**
   - 点击"播放"按钮
   - 系统会逐K线播放整个回测过程
   - 实时显示：
     - K线图和价格走势
     - 买入/卖出信号
     - 持仓情况
     - 账户价值变化
     - 盈亏情况

4. **交互功能**
   - ⏯️ 播放/暂停
   - ⏩ 快进（调整播放速度）
   - 📊 切换图表视图
   - 🔍 缩放和拖动

### 1.4 播放器界面说明

```
┌─────────────────────────────────────────────────────────┐
│  Grid V3 - ETHUSDT 4h                         [选择器]   │
├─────────────────────────────────────────────────────────┤
│  📈 收益率: +0.32%   💰 最终价值: $10,032   📊 交易: 40  │
├─────────────────────────────────────────────────────────┤
│                                                          │
│              [K线图 + 交易信号]                           │
│                                                          │
├─────────────────────────────────────────────────────────┤
│  🏷️ 持仓列表         💼 账户价值曲线                     │
├─────────────────────────────────────────────────────────┤
│  ⏮️ ⏯️ ⏭️   进度条: ▬▬▬▬▬▬▬▬▬▬○────────── 60%          │
└─────────────────────────────────────────────────────────┘
```

---

## 方式2：命令行查询（快速查看）

### 2.1 查看最新回测结果

```bash
python manage.py shell -c "
from backtest.models import BacktestResult

result = BacktestResult.objects.latest('created_at')

print(f'策略: {result.name}')
print(f'收益率: {float(result.total_return)*100:.2f}%')
print(f'最大回撤: {float(result.max_drawdown)*100:.2f}%')
print(f'夏普比率: {float(result.sharpe_ratio):.2f}' if result.sharpe_ratio else 'N/A')
print(f'交易次数: {result.total_trades}')
print(f'胜率: {float(result.win_rate):.2f}%')
"
```

### 2.2 列出所有回测结果

```bash
python manage.py shell -c "
from backtest.models import BacktestResult

results = BacktestResult.objects.all().order_by('-created_at')

for r in results:
    print(f'{r.id}. {r.name} - 收益率: {float(r.total_return)*100:.2f}%')
"
```

### 2.3 查看特定ID的回测详情

```bash
python manage.py shell -c "
from backtest.models import BacktestResult
import json

result = BacktestResult.objects.get(id=2)  # 修改ID

print('='*80)
print(f'回测ID: {result.id}')
print(f'策略: {result.name}')
print('='*80)

# 核心指标
print('\n【核心指标】')
print(f'  总收益率: {float(result.total_return)*100:.2f}%')
print(f'  年化收益率: {float(result.annual_return)*100:.2f}%' if result.annual_return else '  年化收益率: N/A')
print(f'  最大回撤: {float(result.max_drawdown)*100:.2f}%')
print(f'  夏普比率: {float(result.sharpe_ratio):.2f}' if result.sharpe_ratio else '  夏普比率: N/A')
print(f'  索提诺比率: {float(result.sortino_ratio):.2f}' if result.sortino_ratio else '  索提诺比率: N/A')
print(f'  卡玛比率: {float(result.calmar_ratio):.2f}' if result.calmar_ratio else '  卡玛比率: N/A')

# 交易统计
print('\n【交易统计】')
print(f'  总交易次数: {result.total_trades}')
print(f'  盈利交易: {result.profitable_trades}')
print(f'  亏损交易: {result.losing_trades}')
print(f'  胜率: {float(result.win_rate):.2f}%')
print(f'  盈亏比: {float(result.profit_factor):.2f}' if result.profit_factor else '  盈亏比: N/A')

# 查看前5笔交易
if result.trades_detail:
    print('\n【前5笔交易】')
    trades = result.trades_detail[:5]
    for i, trade in enumerate(trades, 1):
        print(f'  {i}. 盈亏: {trade.get(\"PnL\", \"N/A\")}')
"
```

### 2.4 比较多个回测结果

```bash
python manage.py shell -c "
from backtest.models import BacktestResult

results = BacktestResult.objects.all().order_by('-total_return')[:5]

print('回测结果排名 (按收益率)')
print('-'*80)
for i, r in enumerate(results, 1):
    print(f'{i}. {r.name:40} {float(r.total_return)*100:>6.2f}%')
"
```

---

## 方式3：生成专业分析报告

### 3.1 生成综合报告（推荐）

```bash
# 生成最新10个回测的综合报告
python manage.py generate_report --latest 10
```

**生成的文件**：
- `backtest_reports/backtest_report_YYYYMMDD_HHMMSS.csv` - 汇总表
- `backtest_reports/backtest_report_YYYYMMDD_HHMMSS.md` - Markdown报告
- `backtest_reports/backtest_report_YYYYMMDD_HHMMSS_equity.png` - 权益曲线图
- `backtest_reports/backtest_report_YYYYMMDD_HHMMSS_returns.png` - 收益分布图
- `backtest_reports/backtest_report_YYYYMMDD_HHMMSS_drawdown_best.png` - 最佳策略回撤图

### 3.2 生成特定回测的报告

```bash
# 根据ID生成报告（多个ID用逗号分隔）
python manage.py generate_report --ids 1,2,3
```

### 3.3 筛选条件生成报告

```bash
# 只看ETHUSDT的回测
python manage.py generate_report --symbol ETHUSDT --latest 5

# 只看4h周期的回测
python manage.py generate_report --interval 4h --latest 5

# 组合条件
python manage.py generate_report --symbol ETHUSDT --interval 4h --latest 10
```

### 3.4 报告内容示例

生成的Markdown报告包含：

```markdown
# 回测分析报告

## 回测结果汇总

| ID | 策略 | 交易对 | 收益率 | 夏普比率 | 最大回撤 | 胜率 | 交易次数 |
|----|------|--------|--------|---------|---------|------|---------|
| 2  | Grid V3 | ETHUSDT 4h | 0.32% | N/A | 0.00% | 60.00% | 40 |

## 策略分析

### 最佳策略: Grid V3 - ETHUSDT 4h
- 收益率: 0.32%
- 风险控制: 优秀（最大回撤0.00%）
- 交易效率: 良好（胜率60%）

## 图表

[权益曲线图]
[收益分布图]
[回撤分析图]
```

---

## 快速参考命令

### 日常使用命令

```bash
# 1. 查看最新回测结果摘要
python manage.py shell -c "from backtest.models import BacktestResult; r=BacktestResult.objects.latest('created_at'); print(f'{r.name}: {float(r.total_return)*100:.2f}%')"

# 2. 列出所有回测（简洁版）
python manage.py shell -c "from backtest.models import BacktestResult; [print(f'{r.id}. {r.name} - {float(r.total_return)*100:.2f}%') for r in BacktestResult.objects.all().order_by('-created_at')]"

# 3. 生成最新回测的报告
python manage.py generate_report --latest 1

# 4. 启动Web播放器
python manage.py runserver 8001
# 然后访问: http://127.0.0.1:8001/backtest/player/
```

---

## 当前系统状态

### 现有回测记录

运行以下命令查看：
```bash
python manage.py shell -c "from backtest.models import BacktestResult; print(f'共有 {BacktestResult.objects.count()} 条回测记录')"
```

你当前有 **2条** Grid V3回测记录：

| ID | 策略 | 收益率 | 交易次数 | 胜率 |
|----|------|--------|---------|------|
| 2  | Grid V3 - ETHUSDT 4h | +0.32% | 40 | 60% |
| 1  | Grid V3 - ETHUSDT 4h | +0.32% | 40 | 60% |

### 注意事项

⚠️ **增强指标缺失**：
这两条回测记录是在实施增强指标之前创建的，所以没有：
- 年化收益率
- 索提诺比率
- 卡玛比率
- 盈亏比
- 等其他新增指标

**解决方案**：重新运行回测以获得完整指标

```bash
python manage.py run_backtest \
  --symbol ETHUSDT \
  --interval 4h \
  --strategy grid_v3 \
  --start-date 2025-01-01 \
  --end-date 2025-11-30 \
  --initial-cash 10000 \
  --executor simple
```

---

## 高级用法

### 导出回测数据到CSV

```bash
python manage.py shell -c "
from backtest.models import BacktestResult
import csv

with open('backtest_export.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['ID', '策略', '交易对', '收益率', '夏普比率', '最大回撤', '交易次数', '胜率'])

    for r in BacktestResult.objects.all():
        writer.writerow([
            r.id,
            r.name,
            f'{r.symbol} {r.interval}',
            f'{float(r.total_return)*100:.2f}%',
            f'{float(r.sharpe_ratio):.2f}' if r.sharpe_ratio else 'N/A',
            f'{float(r.max_drawdown)*100:.2f}%',
            r.total_trades,
            f'{float(r.win_rate):.2f}%'
        ])

print('导出完成: backtest_export.csv')
"
```

### Python脚本中使用

```python
from backtest.models import BacktestResult

# 获取最佳策略（按夏普比率）
best_strategy = BacktestResult.objects.filter(
    sharpe_ratio__isnull=False
).order_by('-sharpe_ratio').first()

# 获取收益最高的策略
best_return = BacktestResult.objects.order_by('-total_return').first()

# 获取特定时间范围的回测
from datetime import datetime
recent_backtests = BacktestResult.objects.filter(
    created_at__gte=datetime(2025, 12, 1)
)
```

---

## 推荐工作流

### 日常回测分析流程

1. **运行回测**
   ```bash
   python manage.py run_backtest [参数]
   ```

2. **快速查看结果**（命令行）
   ```bash
   python manage.py shell -c "from backtest.models import BacktestResult; r=BacktestResult.objects.latest('created_at'); print(f'收益: {float(r.total_return)*100:.2f}%, 夏普: {float(r.sharpe_ratio):.2f}' if r.sharpe_ratio else f'收益: {float(r.total_return)*100:.2f}%')"
   ```

3. **可视化分析**（Web播放器）
   - 启动服务
   - 在播放器中逐步观察交易过程
   - 理解策略行为

4. **生成专业报告**（存档/分享）
   ```bash
   python manage.py generate_report --latest 5
   ```

5. **对比分析**
   - 比较不同参数的策略
   - 找出最优配置

---

## 故障排查

### Q: Web播放器无法访问？
A: 确保Django服务已启动
```bash
python manage.py runserver 8001
```

### Q: 看不到增强指标？
A: 旧的回测记录没有增强指标，需要重新运行回测

### Q: 报告生成失败？
A: 检查是否有回测数据
```bash
python manage.py shell -c "from backtest.models import BacktestResult; print(BacktestResult.objects.count())"
```

### Q: 如何删除旧的回测记录？
A: 使用Django shell
```bash
python manage.py shell -c "from backtest.models import BacktestResult; BacktestResult.objects.filter(id__in=[1,2]).delete()"
```

---

**Happy Backtesting! 🚀**
