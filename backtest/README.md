# 网格交易回测系统

基于Django + vectorbt的专业回测框架，支持历史数据持久化、网格策略回测、参数优化和Web可视化。

## 功能特性

### 核心功能

- **数据管理**
  - 币安历史K线数据获取（支持多批次，突破1000条限制）
  - SQLite/PostgreSQL数据持久化
  - 数据验证和质量检查
  - 自动增量更新

- **回测引擎**
  - vectorbt专业回测框架
  - 支持多种策略（网格、买入持有）
  - 考虑手续费和滑点
  - 完整的性能指标（收益率、夏普比率、最大回撤、胜率）

- **网格策略**
  - 动态网格层级生成
  - 价格穿越触发交易
  - 可配置止损
  - 参数优化支持

- **分析与可视化**
  - 权益曲线图
  - 回撤曲线图
  - 收益分布直方图
  - 参数优化热力图
  - Markdown报告生成

- **Web可视化**
  - 交互式Web界面
  - 实时回测执行
  - 动态图表展示
  - 回放控制（播放/暂停/速度调节）
  - RESTful API

## 快速开始

### 1. 安装依赖

```bash
pip install vectorbt==0.26.2 pandas==2.1.4 numpy==1.26.2 matplotlib==3.8.2 scikit-learn==1.3.2 pyyaml plotly==5.18.0
```

### 2. 数据库迁移

```bash
python manage.py migrate
```

### 3. 获取历史数据

```bash
# 获取ETHUSDT 4小时数据（180天）
python manage.py fetch_klines --symbol ETHUSDT --interval 4h --days 180 --validate
```

### 4. 运行回测

#### 命令行方式

```bash
# 运行网格策略回测
python manage.py run_backtest --symbol ETHUSDT --interval 4h --strategy grid

# 参数优化
python manage.py optimize_params --symbol ETHUSDT --interval 4h

# 生成可视化报告
python manage.py generate_report --symbol ETHUSDT --interval 4h
```

#### Web界面方式

```bash
# 启动Web服务器
./start_web_backtest.sh

# 或
python manage.py runserver 8001
```

然后在浏览器访问: `http://127.0.0.1:8001/backtest/`

## 项目结构

```
backtest/
├── __init__.py
├── models.py                    # 数据模型（KLine, BacktestResult）
├── views.py                     # Web视图和API
├── urls.py                      # URL路由
├── admin.py                     # Django Admin配置
├── templates/
│   └── backtest/
│       └── index.html          # Web可视化界面
├── management/
│   └── commands/
│       ├── fetch_klines.py     # 数据获取命令
│       ├── update_klines.py    # 数据更新命令
│       ├── run_backtest.py     # 回测执行命令
│       ├── compare_results.py  # 结果对比命令
│       ├── optimize_params.py  # 参数优化命令
│       ├── visualize_results.py # 可视化命令
│       └── generate_report.py  # 报告生成命令
└── services/
    ├── data_fetcher.py         # 数据获取服务
    ├── data_validator.py       # 数据验证服务
    ├── backtest_engine.py      # 回测引擎
    ├── grid_strategy_vbt.py    # 网格策略
    ├── buy_hold_strategy.py    # 买入持有策略
    ├── result_analyzer.py      # 结果分析
    └── parameter_optimizer.py  # 参数优化
```

## 使用示例

### 1. 数据获取

```bash
# 获取多个币种的数据
python manage.py fetch_klines --symbol BTCUSDT --interval 4h --days 180
python manage.py fetch_klines --symbol ETHUSDT --interval 4h --days 180
python manage.py fetch_klines --symbol SOLUSDT --interval 1h --days 90
```

### 2. 运行回测

```bash
# 基本回测
python manage.py run_backtest \
  --symbol ETHUSDT \
  --interval 4h \
  --strategy grid

# 指定初始资金
python manage.py run_backtest \
  --symbol ETHUSDT \
  --interval 4h \
  --strategy grid \
  --initial-cash 50000
```

### 3. 参数优化

```bash
# 自动优化网格参数
python manage.py optimize_params \
  --symbol ETHUSDT \
  --interval 4h \
  --days 180
```

### 4. 生成报告

```bash
# 生成综合分析报告
python manage.py generate_report \
  --symbol ETHUSDT \
  --interval 4h \
  --output backtest_reports/
```

### 5. Web API调用

```python
import requests

url = "http://127.0.0.1:8001/backtest/api/run/"
params = {
    "symbol": "ETHUSDT",
    "interval": "4h",
    "days": 180,
    "initial_cash": 10000,
    "strategy_type": "grid",
    "grid_step_pct": 2.0,
    "grid_levels": 10,
    "order_size_pct": 10.0,
    "stop_loss_pct": 15.0
}

response = requests.post(url, json=params)
data = response.json()

if data['success']:
    result = data['result']
    print(f"收益率: {result['total_return']:.2f}%")
    print(f"夏普比率: {result['sharpe_ratio']:.2f}")
```

## 配置说明

配置文件位于 `config/backtest.yaml`:

```yaml
# 默认回测参数
default:
  initial_cash: 10000          # 初始资金（USDT）
  commission: 0.001            # 手续费率（0.1%）
  slippage: 0.0005            # 滑点（0.05%）

# 网格策略参数范围
grid_strategy:
  grid_step_pct:
    min: 0.005                 # 0.5%
    max: 0.02                  # 2%
    default: 0.01              # 1%

  grid_levels:
    min: 5
    max: 20
    default: 10

  stop_loss_pct:
    min: 0.05                  # 5%
    max: 0.20                  # 20%
    default: 0.10              # 10%
```

## 性能指标

基于ETHUSDT 4h数据的测试结果：

**数据处理**:
- 3240条K线（540天）获取: < 30秒
- 数据库查询: < 100ms
- 数据验证: < 1秒

**回测性能**:
- 180天回测: < 5秒
- 参数优化（9组合）: < 30秒
- 报告生成: < 10秒

**Web性能**:
- API响应: < 5秒
- 图表渲染（1080点）: < 1秒
- 内存使用: < 50MB

## 回测结果示例

### 网格策略 vs 买入持有

**网格策略** (步长1.5%, 层数10):
- 总收益率: 23.97%
- 夏普比率: 2.44
- 最大回撤: 0.11%
- 胜率: 100%
- 交易次数: 4

**买入持有**:
- 总收益率: 19.75%
- 夏普比率: 0.93
- 最大回撤: 0.44%
- 胜率: N/A
- 交易次数: 1

**结论**: 网格策略在风险调整后的收益更优（更高的夏普比率，更低的回撤）

## 技术架构

**后端**:
- Django 4.2.8
- vectorbt 0.26.2 (回测引擎)
- pandas 2.1.4 (数据处理)
- matplotlib 3.8.2 (图表生成)

**前端**:
- Chart.js 4.4.0 (图表库)
- Vanilla JavaScript
- CSS Grid/Flexbox

**数据库**:
- SQLite (开发)
- PostgreSQL (生产)

## API文档

### POST /backtest/api/run/

运行回测并返回结果。

**请求参数**:
```json
{
  "symbol": "ETHUSDT",
  "interval": "4h",
  "days": 180,
  "initial_cash": 10000,
  "strategy_type": "grid",
  "grid_step_pct": 2.0,
  "grid_levels": 10,
  "order_size_pct": 10.0,
  "stop_loss_pct": 15.0
}
```

**响应格式**:
```json
{
  "success": true,
  "result": {
    "total_return": 23.97,
    "sharpe_ratio": 2.44,
    "max_drawdown": 0.11,
    "win_rate": 100.0,
    "total_trades": 4,
    ...
  },
  "data": {
    "prices": [...],
    "signals": [...],
    "equity": [...],
    "trades": [...]
  },
  "grid_info": {...}
}
```

## 常见问题

**Q: 如何获取更多历史数据？**

A: 使用`--days`参数指定天数，系统会自动分批获取：
```bash
python manage.py fetch_klines --symbol ETHUSDT --interval 4h --days 540
```

**Q: 如何自定义网格参数？**

A: 编辑`config/backtest.yaml`文件中的grid_strategy部分。

**Q: 如何导出回测结果？**

A: 使用generate_report命令生成Markdown报告：
```bash
python manage.py generate_report --symbol ETHUSDT --interval 4h
```

**Q: 如何添加新的交易策略？**

A:
1. 在`backtest/services/`创建新策略文件
2. 继承或参考`GridStrategyVBT`的实现
3. 实现`generate_signals()`和`run()`方法
4. 在命令中注册新策略

## 更多文档

- [完整使用指南](../WEB_BACKTEST_GUIDE.md)
- [实施计划](../specs/005-backtest-framework/IMPLEMENTATION_PLAN.md)
- [方案文档](../specs/005-backtest-framework/solution-proposal.md)

## 许可证

本项目仅用于学习和研究目的。

## 更新日志

**v1.0.0** (2025-11-28)
- 初始版本发布
- 支持网格策略回测
- Web可视化界面
- 参数优化功能
- 完整文档

---

**最后更新**: 2025-11-28
