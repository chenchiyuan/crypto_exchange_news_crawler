# 产品需求文档 (PRD) - 量化回测指标系统

**项目名称**: 加密货币交易监控系统
**迭代编号**: 014
**文档版本**: v1.0.0
**创建日期**: 2026-01-06
**生命周期阶段**: P1 - 需求定义+澄清

---

## 第一部分：需求原始输入

### 背景与动机

当前策略回测系统（迭代013-策略适配层）已实现基础订单管理和简单统计功能，但缺乏专业量化交易中常用的风险评估、收益分析和绩效度量指标。这导致策略研究人员无法全面评估策略质量，无法与行业标准进行对标。

### 核心问题

**用一句话定义核心价值**：提供符合量化交易行业标准的完整绩效评估指标体系，帮助策略研究人员科学评估策略质量和风险收益特征。

### 目标用户

1. **量化策略研究人员**：需要专业指标评估策略质量
2. **风险管理人员**：需要风险指标监控策略安全性
3. **投资决策人员**：需要收益指标支持策略选择

### 用户需求

用户提出了8大类30+指标的完整量化分析需求：

1. **概述信息**：策略名称、回测时间范围、交易标的、基准指数、策略逻辑
2. **收益分析**：年化收益率(APR)、绝对收益、收益曲线、月度/年度收益分布
3. **风险分析**：最大回撤(MDD)、卡玛比率、波动率、下行风险、尾部风险(VaR/CVaR)、最大连续亏损周期
4. **风险调整收益**：夏普率、索提诺比率、MAR比率、盈利因子
5. **稳定性分析**：稳定性(回归分析)、收益分布偏度和峰度
6. **交易效率**：交易频率、交易成本占比、胜率、盈亏比
7. **相对收益**：阿尔法(Alpha)、贝塔(Beta)、R平方、年化跟踪误差
8. **结论与建议**：综合评价、适用场景、改进建议

### 预期成果

1. **适配层支持**：StrategyAdapter能够从订单数据计算完整的量化指标
2. **报告增强**：run_strategy_backtest命令能够输出分层的专业报告（默认P0核心指标，--verbose显示全部）
3. **可扩展性**：指标计算模块独立，易于后续添加新指标

---

## 第二部分：功能规格框架

### 模块一：功能定义与拆解

#### 1.1 现有能力盘点

**已实现功能** ✅：
- 订单生命周期管理（UnifiedOrderManager）
- 基础统计指标（胜率、盈亏、手续费）
- 订单盈亏计算（profit_loss, profit_loss_rate）
- 手续费率可配置（commission_rate）
- 回测时间序列（K线数据加载）
- 命令行报告输出

**当前统计指标** ✅：
- 订单数量：total_orders, open_orders, closed_orders
- 盈亏：total_profit, avg_profit
- 手续费：total_commission, avg_commission
- 胜率：win_rate (盈利订单数 / 总订单数)
- 收益率：avg_profit_rate, total_return_rate
- 极值：max_profit, max_loss（对应的profit_loss_rate）

**缺失指标** ❌：
- 收益分析：APR、绝对收益、权益曲线、月度/年度分布
- 风险分析：MDD、卡玛比率、波动率、下行风险、VaR/CVaR、恢复时间
- 风险调整收益：夏普率、索提诺比率、MAR比率、盈利因子（计算公式）
- 稳定性：回归分析、偏度、峰度
- 交易效率：交易频率、成本占比（计算公式）、盈亏比（计算公式）
- 相对收益：Alpha、Beta、R平方、跟踪误差（需要基准数据）

#### 1.2 功能模块分类

##### 📊 模块1：核心收益指标（P0 - MVP必备）

- **[P0] 年化收益率（APR）**：基于回测期间的总收益，年化计算
  - 用户故事：作为策略研究人员，我需要看到策略的年化收益率，以便与基准收益率对比
  - 计算公式：`APR = (总收益 / 初始资金) × (365天 / 回测天数) × 100%`
  - 数据来源：total_profit, initial_cash, 回测时间范围

- **[P0] 绝对收益**：回测期间的总盈亏（USDT）
  - 用户故事：作为投资决策人员，我需要知道策略的绝对盈利金额
  - 计算公式：已有（total_profit）
  - 数据来源：UnifiedOrderManager.calculate_statistics()

- **[P0] 累计收益率**：回测期间的总收益率
  - 用户故事：作为策略研究人员，我需要看到策略的累计收益率
  - 计算公式：`累计收益率 = (总收益 / 初始资金) × 100%`
  - 数据来源：total_profit, initial_cash

##### 🛡️ 模块2：核心风险指标（P0 - MVP必备）

- **[P0] 最大回撤（MDD）**：权益曲线从最高点到最低点的最大跌幅
  - 用户故事：作为风险管理人员，我需要知道策略在最糟糕情况下的潜在亏损
  - 计算公式：`MDD = min((当前净值 - 历史最高净值) / 历史最高净值) × 100%`
  - 数据来源：权益曲线（需要新增）

- **[P0] 波动率（Volatility）**：收益率的标准差（年化）
  - 用户故事：作为风险管理人员，我需要衡量策略收益的波动幅度
  - 计算公式：`Volatility = std(daily_returns) × sqrt(252)`
  - 数据来源：权益曲线

- **[P0] 恢复时间**：从最大回撤开始到恢复到前高点所需的时间
  - 用户故事：作为策略研究人员，我需要知道策略在亏损后的恢复能力
  - 计算公式：计算MDD发生时间到净值恢复到前高点的时间间隔
  - 数据来源：权益曲线

##### ⚖️ 模块3：风险调整收益（P0 - MVP必备）

- **[P0] 夏普率（Sharpe Ratio）**：单位风险下的超额收益
  - 用户故事：作为策略研究人员，我需要衡量策略在承担单位风险下获得的收益
  - 计算公式：`Sharpe = (APR - 无风险收益率) / Volatility`
  - 数据来源：APR, Volatility, 无风险收益率（CLI配置）

- **[P0] 卡玛比率（Calmar Ratio）**：年化收益率与最大回撤的比值
  - 用户故事：作为风险管理人员，我需要衡量策略在承受最大回撤情况下的收益能力
  - 计算公式：`Calmar = APR / abs(MDD)`
  - 数据来源：APR, MDD

- **[P0] MAR比率（MAR Ratio）**：累计收益与最大回撤的比值
  - 用户故事：作为策略研究人员，我需要衡量策略的收益相对于最大回撤的比例
  - 计算公式：`MAR = 累计收益率 / abs(MDD)`
  - 数据来源：累计收益率, MDD

- **[P0] 盈利因子（Profit Factor）**：总盈利与总亏损的比值
  - 用户故事：作为策略研究人员，我需要知道策略的盈利能力是否显著大于亏损
  - 计算公式：`Profit Factor = sum(盈利订单盈利) / abs(sum(亏损订单亏损))`
  - 数据来源：closed_orders

##### 💹 模块4：交易效率指标（P0 - MVP必备）

- **[P0] 交易频率（Trade Frequency）**：单位时间内的平均交易次数
  - 用户故事：作为策略研究人员，我需要知道策略的交易频率
  - 计算公式：`交易频率 = 总交易次数 / 回测天数`（单位：次/天）
  - 数据来源：total_orders, 回测时间范围

- **[P0] 交易成本占比（Cost Percentage）**：交易成本占总收益的比例
  - 用户故事：作为成本控制人员，我需要知道交易成本对收益的侵蚀程度
  - 计算公式：`Cost % = total_commission / total_profit × 100%`
  - 数据来源：total_commission, total_profit

- **[P0] 胜率（Win Rate）**：盈利交易次数占比
  - 用户故事：已实现
  - 数据来源：win_orders / total_orders

- **[P0] 盈亏比（Payoff Ratio）**：平均盈利与平均亏损的比值
  - 用户故事：作为策略研究人员，我需要知道单笔盈利订单的盈利能力相对于亏损订单的倍数
  - 计算公式：`Payoff Ratio = avg(盈利订单盈利) / abs(avg(亏损订单亏损))`
  - 数据来源：closed_orders

##### 💾 模块5：数据持久化模块（P0 - MVP必备）

- **[P0] BacktestResult数据模型**：回测结果持久化存储
  - 用户故事：作为策略研究人员，我需要保存回测结果到数据库，以便后续查看和对比
  - 数据结构：
    - `id`: 主键
    - `strategy_name`: 策略名称
    - `symbol`: 交易对
    - `interval`: K线周期
    - `market_type`: 市场类型
    - `start_date`: 回测开始日期
    - `end_date`: 回测结束日期
    - `initial_cash`: 初始资金
    - `position_size`: 单笔买入金额
    - `commission_rate`: 手续费率
    - `risk_free_rate`: 无风险收益率
    - `equity_curve`: 权益曲线（JSON字段）
    - `metrics`: 量化指标（JSON字段，存储所有P0指标）
    - `created_at`: 创建时间
  - 数据来源：adapt_for_backtest()返回结果 + MetricsCalculator计算结果

- **[P0] BacktestOrder数据模型**：订单数据持久化存储
  - 用户故事：作为策略研究人员，我需要查看每笔订单的详细信息
  - 数据结构：
    - `id`: 主键
    - `backtest_result`: 外键关联BacktestResult
    - `order_id`: 订单ID
    - `status`: 订单状态（holding/sold）
    - `buy_price`: 买入价格
    - `buy_timestamp`: 买入时间
    - `sell_price`: 卖出价格（如已平仓）
    - `sell_timestamp`: 卖出时间（如已平仓）
    - `quantity`: 持仓数量
    - `position_value`: 持仓市值
    - `commission`: 手续费
    - `profit_loss`: 盈亏金额
    - `profit_loss_rate`: 盈亏率
    - `holding_periods`: 持仓周期
  - 数据来源：UnifiedOrderManager订单列表

- **[P0] 回测结果保存功能**：通过CLI参数触发保存
  - 用户故事：作为策略研究人员，我需要控制何时保存回测结果，避免数据库冗余
  - CLI参数：`--save-to-db` (bool, 默认False)
  - 实现逻辑：
    1. 在run_strategy_backtest命令中添加--save-to-db参数
    2. 回测完成后，如果--save-to-db=True，执行保存
    3. 创建BacktestResult记录
    4. 批量创建BacktestOrder记录
    5. 输出保存成功信息（包含记录ID和访问URL）
  - 示例：`python manage.py run_strategy_backtest ETHUSDT --save-to-db`

##### 🖼️ 模块6：后台展示模块（P0 - MVP必备）

- **[P0] 回测结果列表页**：展示所有已保存的回测结果
  - 用户故事：作为策略研究人员，我需要浏览所有历史回测记录
  - URL路径：`/backtest/results/`
  - 页面内容：
    - 表格展示：策略名称、交易对、周期、市场类型、时间范围、总收益、胜率、创建时间
    - 排序功能：按创建时间倒序排列
    - 分页功能：每页20条记录
    - 筛选功能：按策略名称、交易对、市场类型筛选
    - 操作按钮：查看详情、删除记录
  - 技术选型：Django模板 + Bootstrap CSS

- **[P0] 回测结果详情页**：展示单个回测的完整信息
  - 用户故事：作为策略研究人员，我需要查看单个回测的详细数据和可视化图表
  - URL路径：`/backtest/results/<id>/`
  - 页面内容：
    - **基本信息卡片**：策略名称、交易对、时间范围、初始资金等
    - **权益曲线图**：Chart.js折线图展示净值变化
    - **量化指标卡片**：
      - 收益分析：APR、绝对收益、累计收益率
      - 风险分析：MDD、波动率、恢复时间
      - 风险调整收益：夏普率、卡玛比率、MAR比率、盈利因子
      - 交易效率：交易频率、成本占比、胜率、盈亏比
    - **订单列表表格**：展示所有订单详情
      - 列：订单ID、买入时间、卖出时间、买入价、卖出价、盈亏、盈亏率、持仓周期
      - 排序功能：按盈亏倒序排列
      - 分页功能：每页50条
  - 技术选型：Django模板 + Chart.js + Bootstrap CSS

- **[P0] 权益曲线图可视化**：使用Chart.js绘制净值变化曲线（从P1提升到P0）
  - 用户故事：作为策略研究人员，我需要可视化地查看策略净值的变化趋势
  - 实现方式：
    - 使用Chart.js折线图
    - X轴：时间戳（格式化为日期时间）
    - Y轴：账户净值（USDT）
    - 数据来源：BacktestResult.equity_curve（JSON字段）
    - 交互功能：鼠标悬停显示时间点和净值
    - 响应式设计：适配不同屏幕尺寸
  - 原因：权益曲线是回测分析的核心可视化需求，从P1提升到P0

##### 📈 模块7：高级分析指标（P1 - 可推迟）

- **[P1] 索提诺比率（Sortino Ratio）**：考虑下行风险的夏普率改进版
  - 推迟理由：需要计算下行波动率，算法相对复杂，MVP阶段夏普率已足够
  - 计算公式：`Sortino = (APR - 无风险收益率) / Downside Volatility`

- **[P1] 稳定性（Stability）**：通过回归分析测量收益曲线的平滑程度
  - 推迟理由：需要进行线性回归分析，算法复杂度较高
  - 计算公式：对权益曲线进行线性回归，计算R²

- **[P1] 收益分布偏度和峰度**：收益分布的对称性和尖锐程度
  - 推迟理由：统计学分析，MVP阶段优先保证基础指标
  - 计算公式：`skewness = E[(X-μ)³] / σ³`, `kurtosis = E[(X-μ)⁴] / σ⁴`

- **[P1] VaR/CVaR（尾部风险）**：在险价值和条件在险价值
  - 推迟理由：算法复杂，需要分位数计算，MVP阶段MDD已能评估极端风险
  - 计算公式：`VaR_95% = percentile(returns, 5%)`, `CVaR = mean(returns < VaR)`

##### 📊 模块8：相对收益分析（P1 - 可推迟）

- **[P1] Alpha（阿尔法）**：策略剔除市场系统性风险后的超额收益
  - 推迟理由：需要基准数据（如BTC走势），MVP阶段优先绝对收益分析
  - 计算公式：`Alpha = 策略收益率 - (无风险收益率 + Beta × (基准收益率 - 无风险收益率))`

- **[P1] Beta（贝塔）**：策略收益对市场波动的敏感度
  - 推迟理由：需要基准数据
  - 计算公式：`Beta = Cov(策略收益, 基准收益) / Var(基准收益)`

- **[P1] R平方（R-squared）**：策略收益与基准收益的相关性
  - 推迟理由：需要基准数据
  - 计算公式：`R² = (Corr(策略收益, 基准收益))²`

- **[P1] 年化跟踪误差（Tracking Error）**：策略收益与基准收益差异的波动率
  - 推迟理由：需要基准数据
  - 计算公式：`TE = std(策略收益 - 基准收益) × sqrt(252)`

##### 📉 模块9：可视化与报告（P1 - 可推迟）

- **[P1] 月度/年度收益柱状图**：统计每月/每年的收益率分布
  - 推迟理由：MVP阶段优先提供核心指标
  - 实现方式：使用matplotlib绘制

#### 1.3 数据结构扩展

##### 权益曲线（Equity Curve）

**定义**：记录回测过程中每个时间点的账户净值（资金 + 持仓市值）

**数据结构**：
```python
@dataclass
class EquityPoint:
    timestamp: int          # 时间戳（毫秒）
    cash: Decimal           # 可用资金
    position_value: Decimal # 持仓市值
    equity: Decimal         # 账户净值（cash + position_value）
    equity_rate: Decimal    # 净值变化率（相对于初始资金）
```

**生成方式**：
- **方案A（推荐）**：事后从订单记录重建
  - 优点：实现简单，不修改回测主流程
  - 缺点：需要重新计算持仓市值
- **方案B**：回测过程中实时记录
  - 优点：数据准确
  - 缺点：需要修改StrategyAdapter主流程，增加复杂度

**MVP选择**：方案A（最小改动原则）

##### 无风险收益率配置

**CLI参数**：
```bash
--risk-free-rate FLOAT  # 无风险收益率（年化，百分比），默认3%
```

**示例**：
```bash
python manage.py run_strategy_backtest ETHUSDT \
    --start-date 2025-01-01 \
    --end-date 2026-01-01 \
    --risk-free-rate 3.0  # 3%年化无风险收益率
```

#### 1.4 模块设计

##### MetricsCalculator（新增模块）

**职责**：独立的量化指标计算模块

**设计原则**：
- 单一职责：只负责指标计算，不涉及订单管理
- 依赖注入：接受订单列表、权益曲线等数据作为输入
- 无状态设计：每次计算都是独立的，不保存中间状态

**类定义**：
```python
class MetricsCalculator:
    def __init__(self, risk_free_rate: Decimal = Decimal("0.03")):
        self.risk_free_rate = risk_free_rate

    # 收益指标
    def calculate_apr(self, total_profit, initial_cash, days) -> Decimal:
        """计算年化收益率"""

    def calculate_cumulative_return(self, total_profit, initial_cash) -> Decimal:
        """计算累计收益率"""

    # 风险指标
    def calculate_mdd(self, equity_curve: List[EquityPoint]) -> Dict:
        """计算最大回撤、恢复时间"""

    def calculate_volatility(self, equity_curve: List[EquityPoint]) -> Decimal:
        """计算年化波动率"""

    # 风险调整收益
    def calculate_sharpe_ratio(self, apr, volatility) -> Decimal:
        """计算夏普率"""

    def calculate_calmar_ratio(self, apr, mdd) -> Decimal:
        """计算卡玛比率"""

    def calculate_mar_ratio(self, cumulative_return, mdd) -> Decimal:
        """计算MAR比率"""

    def calculate_profit_factor(self, orders: List[Order]) -> Decimal:
        """计算盈利因子"""

    # 交易效率
    def calculate_trade_frequency(self, total_orders, days) -> Decimal:
        """计算交易频率"""

    def calculate_cost_percentage(self, total_commission, total_profit) -> Decimal:
        """计算交易成本占比"""

    def calculate_payoff_ratio(self, orders: List[Order]) -> Decimal:
        """计算盈亏比"""

    # 综合计算
    def calculate_all_metrics(self,
                              orders: List[Order],
                              equity_curve: List[EquityPoint],
                              initial_cash: Decimal,
                              days: int) -> Dict:
        """计算所有P0指标，返回完整字典"""
```

##### EquityCurveBuilder（新增工具类）

**职责**：从订单记录重建权益曲线

**类定义**：
```python
class EquityCurveBuilder:
    @staticmethod
    def build_from_orders(orders: List[Order],
                          klines: pd.DataFrame,
                          initial_cash: Decimal) -> List[EquityPoint]:
        """
        从订单记录重建权益曲线

        算法：
        1. 按时间顺序遍历K线
        2. 在每个K线时间点：
           - 计算当前持仓市值（持仓数量 × 当前价格）
           - 计算账户净值（可用资金 + 持仓市值）
        3. 返回完整的权益曲线
        """
```

### 模块二：交互流程与规则

#### 2.1 命令行交互流程

**现有交互**（保持不变）：
```bash
python manage.py run_strategy_backtest ETHUSDT \
    --start-date 2025-01-01 \
    --end-date 2026-01-01 \
    --interval 4h \
    --market-type futures \
    --initial-cash 10000 \
    --position-size 1000 \
    --commission-rate 0.001
```

**新增参数**（P0）：
```bash
--risk-free-rate FLOAT  # 无风险收益率（年化，百分比），默认3%
--verbose              # 显示详细指标（已有，复用）
```

**完整示例**：
```bash
python manage.py run_strategy_backtest ETHUSDT \
    --start-date 2025-01-01 \
    --end-date 2026-01-01 \
    --interval 4h \
    --market-type futures \
    --initial-cash 10000 \
    --position-size 1000 \
    --commission-rate 0.001 \
    --risk-free-rate 3.0 \
    --verbose
```

#### 2.2 报告输出流程

**分层输出原则**：
- **默认模式**（无--verbose）：输出P0核心指标（15个）
- **详细模式**（--verbose）：输出所有P0指标 + 部分P1指标（如果已实现）

**默认模式输出结构**：
```
=== 策略回测系统 ===

【基本信息】
  策略: DDPS-Z v1.0.0
  交易对: ETHUSDT
  周期: 4h
  市场: futures
  时间范围: 2025-01-01 ~ 2026-01-01 (365天)
  初始资金: 10000.00 USDT
  无风险收益率: 3.00%

【收益分析】
  绝对收益: +1234.56 USDT
  累计收益率: 12.35%
  年化收益率(APR): 12.35%

【风险分析】
  最大回撤(MDD): -8.45%
  波动率(年化): 15.23%
  恢复时间: 12天

【风险调整收益】
  夏普率: 0.61
  卡玛比率: 1.46
  MAR比率: 1.46
  盈利因子: 2.34

【交易效率】
  交易频率: 0.33次/天
  交易成本占比: 2.15%
  胜率: 65.00%
  盈亏比: 1.85

【订单统计】（保留现有）
  总订单数: 120
  持仓中: 5
  已平仓: 115
  盈利订单: 75
  亏损订单: 40

【极值订单】（保留现有）
  最佳订单: +123.45 USDT (12.35%)
  最差订单: -45.67 USDT (-4.57%)
```

**详细模式输出**（--verbose，在默认基础上增加）：
```
【收益分析（详细）】
  月度平均收益率: 1.02%
  月度收益标准差: 3.45%
  最佳月份: 2025-05 (+8.23%)
  最差月份: 2025-09 (-3.21%)

【风险分析（详细）】
  下行波动率: 10.12%
  索提诺比率: 0.92
  VaR(95%): -2.34%
  CVaR(95%): -3.56%

【稳定性分析】
  稳定性(R²): 0.85
  收益偏度: -0.12
  收益峰度: 2.34
```

#### 2.3 业务规则

**指标计算规则**：
1. **年化规则**：所有年化指标使用365天为基准
2. **波动率年化**：日波动率 × sqrt(252)，月波动率 × sqrt(12)
3. **除零保护**：所有除法运算必须检查分母不为0，返回None或0
4. **精度保留**：
   - 金额：保留2位小数
   - 百分比：保留2位小数
   - 比率：保留2位小数

**边界情况处理**：
1. **无已平仓订单**：MDD、波动率等指标无法计算，显示"N/A"
2. **回测时间 < 1天**：APR等年化指标无意义，显示警告
3. **总亏损 = 0**：盈利因子无法计算，显示"∞"
4. **MDD = 0**：卡玛比率、MAR比率无法计算，显示"N/A"

### 模块三：范围边界

#### In-Scope（本迭代实现）

✅ **P0 核心指标（15个）**：
- 收益：APR、绝对收益、累计收益率
- 风险：MDD、波动率、恢复时间
- 风险调整：夏普率、卡玛比率、MAR比率、盈利因子
- 交易效率：交易频率、成本占比、胜率、盈亏比

✅ **基础设施**：
- MetricsCalculator模块（独立）
- EquityCurveBuilder工具类
- CLI参数：--risk-free-rate
- 分层报告输出（默认/详细模式）

✅ **数据结构**：
- EquityPoint数据类
- 权益曲线重建算法

#### Out-of-Scope（后续迭代实现）

❌ **P1 高级指标**：
- 索提诺比率、下行波动率
- 稳定性（回归分析）
- 偏度、峰度
- VaR、CVaR

❌ **P1 相对收益分析**（需要基准数据）：
- Alpha、Beta
- R平方、跟踪误差

❌ **P1 可视化**：
- 权益曲线图
- 月度/年度收益柱状图
- 回撤分布图

❌ **超出范围**：
- 实时监控功能
- 多策略对比
- 参数优化建议
- 策略归因分析

---

## 第三部分：AI分析与建议

### 1. 建议的MVP功能点清单 (Proposed MVP Feature Point Checklist)

#### 📊 [收益指标模块]

- **[P0] FP-014-001: 年化收益率(APR)计算**
  - 描述：基于总收益和回测天数，计算策略的年化收益率
  - 计算公式：`APR = (total_profit / initial_cash) × (365 / days) × 100%`
  - 验收标准：
    - 回测天数365天，总收益10%，APR = 10%
    - 回测天数182.5天，总收益10%，APR = 20%
  - 实现位置：MetricsCalculator.calculate_apr()

- **[P0] FP-014-002: 绝对收益计算**
  - 描述：回测期间的总盈亏金额（USDT）
  - 计算公式：已实现（total_profit）
  - 验收标准：total_profit与订单盈亏总和一致
  - 实现位置：复用UnifiedOrderManager.calculate_statistics()

- **[P0] FP-014-003: 累计收益率计算**
  - 描述：回测期间的总收益率
  - 计算公式：`累计收益率 = (total_profit / initial_cash) × 100%`
  - 验收标准：初始资金10000，总收益1000，累计收益率 = 10%
  - 实现位置：MetricsCalculator.calculate_cumulative_return()

#### 🛡️ [风险指标模块]

- **[P0] FP-014-004: 权益曲线重建**
  - 描述：从订单记录和K线数据，重建完整的账户净值时间序列
  - 算法：按时间遍历K线，计算每个时间点的（可用资金 + 持仓市值）
  - 验收标准：
    - 权益曲线第一个点 = 初始资金
    - 权益曲线最后一个点 = 初始资金 + 总盈亏
    - 权益曲线长度 = K线数量
  - 实现位置：EquityCurveBuilder.build_from_orders()

- **[P0] FP-014-005: 最大回撤(MDD)计算**
  - 描述：权益曲线从最高点到最低点的最大跌幅
  - 计算公式：`MDD = min((equity - max_equity) / max_equity) × 100%`
  - 验证标准：
    - 持续盈利无回撤，MDD = 0%
    - 从10000跌到9000再涨回10000，MDD = -10%
  - 实现位置：MetricsCalculator.calculate_mdd()

- **[P0] FP-014-006: 恢复时间计算**
  - 描述：从MDD发生到净值恢复到前高点的时间间隔
  - 计算单位：天数（或K线根数）
  - 验收标准：
    - 如果未恢复，显示"未恢复"
    - 如果已恢复，显示天数
  - 实现位置：MetricsCalculator.calculate_mdd()（同时返回）

- **[P0] FP-014-007: 波动率计算**
  - 描述：收益率的标准差（年化）
  - 计算公式：`Volatility = std(daily_returns) × sqrt(252)`
  - 验收标准：收益率稳定，波动率低；收益率大起大落，波动率高
  - 实现位置：MetricsCalculator.calculate_volatility()

#### ⚖️ [风险调整收益模块]

- **[P0] FP-014-008: 夏普率计算**
  - 描述：单位风险下的超额收益
  - 计算公式：`Sharpe = (APR - risk_free_rate) / Volatility`
  - 验收标准：
    - APR = 12%, 无风险 = 3%, 波动率 = 15%, Sharpe = 0.6
    - 夏普率 > 1为优秀策略
  - 实现位置：MetricsCalculator.calculate_sharpe_ratio()

- **[P0] FP-014-009: 卡玛比率计算**
  - 描述：年化收益率与最大回撤的比值
  - 计算公式：`Calmar = APR / abs(MDD)`
  - 验收标准：
    - APR = 12%, MDD = -10%, Calmar = 1.2
    - 卡玛比率 > 1为优秀策略
  - 实现位置：MetricsCalculator.calculate_calmar_ratio()

- **[P0] FP-014-010: MAR比率计算**
  - 描述：累计收益与最大回撤的比值
  - 计算公式：`MAR = 累计收益率 / abs(MDD)`
  - 验收标准：MAR = 累计收益率 / abs(MDD)
  - 实现位置：MetricsCalculator.calculate_mar_ratio()

- **[P0] FP-014-011: 盈利因子计算**
  - 描述：总盈利与总亏损的比值
  - 计算公式：`Profit Factor = sum(盈利订单) / abs(sum(亏损订单))`
  - 验收标准：
    - 盈利因子 > 1说明策略盈利
    - 盈利因子 > 1.5为优秀策略
  - 实现位置：MetricsCalculator.calculate_profit_factor()

#### 💹 [交易效率模块]

- **[P0] FP-014-012: 交易频率计算**
  - 描述：单位时间内的平均交易次数
  - 计算公式：`交易频率 = total_orders / days`（单位：次/天）
  - 验收标准：365天120笔交易，频率 = 0.33次/天
  - 实现位置：MetricsCalculator.calculate_trade_frequency()

- **[P0] FP-014-013: 交易成本占比计算**
  - 描述：交易成本占总收益的比例
  - 计算公式：`Cost % = total_commission / total_profit × 100%`
  - 验收标准：总收益1000，手续费20，成本占比 = 2%
  - 实现位置：MetricsCalculator.calculate_cost_percentage()

- **[P0] FP-014-014: 胜率计算**
  - 描述：盈利交易次数占比
  - 计算公式：已实现（win_rate）
  - 验收标准：复用现有实现
  - 实现位置：UnifiedOrderManager.calculate_statistics()

- **[P0] FP-014-015: 盈亏比计算**
  - 描述：平均盈利与平均亏损的比值
  - 计算公式：`Payoff = avg(盈利订单) / abs(avg(亏损订单))`
  - 验收标准：
    - 盈亏比 > 1说明单笔盈利大于单笔亏损
    - 盈亏比 = 2说明单笔盈利是单笔亏损的2倍
  - 实现位置：MetricsCalculator.calculate_payoff_ratio()

#### 🖥️ [报告输出模块]

- **[P0] FP-014-016: 分层报告输出**
  - 描述：根据--verbose参数，输出不同层级的报告
  - 验收标准：
    - 默认模式：输出15个P0核心指标
    - 详细模式（--verbose）：输出所有可用指标
  - 实现位置：run_strategy_backtest.py._display_results()

- **[P0] FP-014-017: 无风险收益率配置**
  - 描述：支持CLI参数配置无风险收益率
  - CLI参数：`--risk-free-rate FLOAT`（默认3.0）
  - 验收标准：
    - 未指定时，使用默认值3%
    - 指定--risk-free-rate 5.0时，使用5%
  - 实现位置：run_strategy_backtest.py.add_arguments()

#### 💾 [数据持久化模块]

- **[P0] FP-014-018: BacktestResult数据模型**
  - 描述：创建回测结果数据模型，支持完整回测数据持久化
  - 数据结构：
    - 基本信息：strategy_name, symbol, interval, market_type, start_date, end_date
    - 回测参数：initial_cash, position_size, commission_rate, risk_free_rate
    - 结果数据：equity_curve(JSON), metrics(JSON)
    - 元数据：created_at
  - 验收标准：
    - 能够成功创建BacktestResult记录
    - equity_curve以JSON格式存储完整权益曲线
    - metrics以JSON格式存储所有17个P0指标
  - 实现位置：strategy_adapter/models.py

- **[P0] FP-014-019: BacktestOrder数据模型**
  - 描述：创建订单数据模型，支持订单明细持久化
  - 数据结构：
    - 外键：backtest_result
    - 订单信息：order_id, status, buy_price, buy_timestamp, sell_price, sell_timestamp
    - 持仓信息：quantity, position_value, commission
    - 收益信息：profit_loss, profit_loss_rate, holding_periods
  - 验收标准：
    - 能够成功创建BacktestOrder记录
    - 外键关联到BacktestResult正确
    - 所有订单字段正确存储
  - 实现位置：strategy_adapter/models.py

- **[P0] FP-014-020: 回测结果保存功能**
  - 描述：通过CLI参数--save-to-db触发保存回测结果到数据库
  - CLI参数：`--save-to-db` (action='store_true', 默认False)
  - 实现逻辑：
    1. 回测完成后检查--save-to-db参数
    2. 如果为True，创建BacktestResult记录
    3. 批量创建BacktestOrder记录
    4. 输出保存成功信息（包含ID和访问URL）
  - 验收标准：
    - 指定--save-to-db时成功保存
    - 未指定时不保存
    - 输出信息包含记录ID和访问URL
  - 实现位置：run_strategy_backtest.py.handle()

#### 🖼️ [后台展示模块]

- **[P0] FP-014-021: 回测结果列表页**
  - 描述：展示所有已保存的回测结果，支持筛选和排序
  - URL路径：`/backtest/results/`
  - 页面功能：
    - 表格展示：策略、交易对、周期、市场、时间范围、总收益、胜率、创建时间
    - 筛选：按策略名称、交易对、市场类型筛选
    - 排序：按创建时间倒序
    - 分页：每页20条
    - 操作：查看详情、删除记录
  - 验收标准：
    - 列表正确展示所有回测记录
    - 筛选功能正常工作
    - 分页功能正常工作
    - 点击查看详情跳转正确
  - 实现位置：strategy_adapter/views.py + templates/backtest/list.html

- **[P0] FP-014-022: 回测结果详情页**
  - 描述：展示单个回测的完整信息和可视化图表
  - URL路径：`/backtest/results/<id>/`
  - 页面功能：
    - 基本信息卡片：策略、交易对、时间范围、回测参数
    - 权益曲线图：Chart.js折线图展示净值变化
    - 量化指标卡片：4大模块17个P0指标
    - 订单列表：所有订单详情（分页50条）
  - 验收标准：
    - 基本信息正确显示
    - 权益曲线图正确绘制
    - 所有量化指标正确显示
    - 订单列表正确展示
  - 实现位置：strategy_adapter/views.py + templates/backtest/detail.html

- **[P0] FP-014-023: 权益曲线图可视化**（从P1提升到P0）
  - 描述：使用Chart.js绘制权益曲线，直观展示净值变化趋势
  - 图表类型：折线图（Line Chart）
  - 数据来源：BacktestResult.equity_curve（JSON字段）
  - 图表特性：
    - X轴：时间戳（格式化为日期时间）
    - Y轴：账户净值（USDT）
    - 交互：鼠标悬停显示时间点和净值
    - 响应式：适配不同屏幕尺寸
  - 验收标准：
    - 图表正确渲染
    - 数据点对应关系正确
    - 交互功能正常
    - 响应式布局正常
  - 实现位置：templates/backtest/detail.html + static/js/equity_chart.js
  - 提升理由：权益曲线是回测分析的核心可视化需求，从P1提升到P0

#### 🌐 [高级指标模块]（P1 - 可推迟）

- **[P1] FP-014-024: 索提诺比率计算**（原FP-014-018）
  - 推迟理由：需要计算下行波动率，算法复杂度较高，MVP阶段夏普率已足够

- **[P1] FP-014-025: 稳定性分析（回归）**（原FP-014-019）
  - 推迟理由：需要线性回归分析，算法复杂度较高

- **[P1] FP-014-026: 偏度和峰度计算**（原FP-014-020）
  - 推迟理由：统计学分析，MVP阶段优先保证基础指标

- **[P1] FP-014-027: VaR/CVaR计算**（原FP-014-021）
  - 推迟理由：算法复杂，需要分位数计算，MVP阶段MDD已能评估极端风险

#### 📈 [相对收益模块]（P1 - 需要基准数据）

- **[P1] FP-014-028: Alpha计算**（原FP-014-022）
  - 推迟理由：需要加载基准数据（如BTC走势），增加数据依赖

- **[P1] FP-014-029: Beta计算**（原FP-014-023）
  - 推迟理由：需要基准数据

- **[P1] FP-014-030: R平方计算**（原FP-014-024）
  - 推迟理由：需要基准数据

- **[P1] FP-014-031: 跟踪误差计算**（原FP-014-025）
  - 推迟理由：需要基准数据

### 2. 待决策清单 (Decision List)

#### 决策点 1：权益曲线跟踪方式

**问题描述**：如何生成权益曲线（净值时间序列）？

**逻辑阐述**：
- **为何重要**：权益曲线是计算MDD、波动率等核心风险指标的基础数据
- **影响范围**：影响MetricsCalculator的数据输入、StrategyAdapter的数据流、计算准确性

**建议方案**：

**方案A（推荐）**：事后从订单记录重建
- 描述：回测完成后，从订单列表和K线数据重建权益曲线
- 优点：
  - 实现简单，不修改回测主流程
  - 符合MVP最小改动原则
  - 无性能影响（回测过程）
- 缺点：
  - 需要额外的计算步骤
  - 需要重新遍历K线数据
- 实现复杂度：低
- MVP适配性：✅ 高（最小改动）

**方案B**：回测过程中实时记录
- 描述：在StrategyAdapter.adapt_for_backtest()中，每次订单变动时记录净值
- 优点：
  - 数据准确，不需要重新计算
  - 性能好（不需要重新遍历）
- 缺点：
  - 需要修改StrategyAdapter主流程
  - 增加回测过程复杂度
  - 引入状态管理（净值列表）
- 实现复杂度：高
- MVP适配性：❌ 低（侵入性强）

**⭐ 推荐方案**：方案A
**推荐理由**：
1. MVP优先原则：最小改动，不修改核心回测流程
2. 单一职责：权益曲线重建是独立的后处理步骤
3. 可测试性：EquityCurveBuilder可以独立测试
4. 技术债务：方案A不引入技术债务，后续可以无痛迁移到方案B

---

#### 决策点 2：无风险收益率配置方式

**问题描述**：如何配置无风险收益率（用于夏普率、索提诺比率计算）？

**逻辑阐述**：
- **为何重要**：无风险收益率是风险调整收益指标的关键参数，不同市场环境下有不同的合理值
- **影响范围**：影响夏普率、索提诺比率的计算准确性，影响用户体验

**建议方案**：

**方案A（推荐）**：CLI参数配置
- 描述：通过`--risk-free-rate`参数配置，默认值3%
- 优点：
  - 灵活性高，用户可以根据市场环境调整
  - 符合现有CLI设计模式（如--commission-rate）
  - 易于理解和使用
- 缺点：
  - 需要用户了解无风险收益率的含义
- 实现复杂度：低
- MVP适配性：✅ 高（符合现有模式）

**方案B**：固定硬编码值
- 描述：在MetricsCalculator中硬编码为3%
- 优点：
  - 实现简单
  - 无需用户配置
- 缺点：
  - 不灵活，无法适应不同市场环境
  - 违反配置外部化原则
- 实现复杂度：低
- MVP适配性：❌ 低（不符合设计原则）

**⭐ 推荐方案**：方案A
**推荐理由**：
1. 灵活性：用户可以根据市场环境调整（如加密货币市场可能使用0%或更高值）
2. 一致性：与现有的--commission-rate参数设计一致
3. 默认值合理：3%是传统金融市场的常见值，对大多数用户适用
4. 可扩展性：未来可以支持从配置文件读取

---

#### 决策点 3：报告输出详细程度

**问题描述**：如何控制报告输出的详细程度？

**逻辑阐述**：
- **为何重要**：用户有不同的信息需求，初学者需要精简报告，专业用户需要详细数据
- **影响范围**：影响用户体验、报告可读性、信息过载风险

**建议方案**：

**方案A（推荐）**：分层输出 + 复用--verbose
- 描述：
  - 默认模式：输出15个P0核心指标（适合大多数用户）
  - 详细模式（--verbose）：输出所有可用指标
- 优点：
  - 复用现有参数，无需新增CLI参数
  - 符合用户习惯（--verbose是通用约定）
  - 分层清晰，信息组织合理
- 缺点：
  - 需要设计两套输出格式
- 实现复杂度：中
- MVP适配性：✅ 高（复用现有机制）

**方案B**：输出所有指标
- 描述：一次性输出所有P0+P1指标
- 优点：
  - 实现简单
  - 信息完整
- 缺点：
  - 信息过载，不利于阅读
  - 违反分层设计原则
- 实现复杂度：低
- MVP适配性：❌ 低（用户体验差）

**方案C**：仅输出P0核心指标
- 描述：只输出15个P0核心指标，不支持详细模式
- 优点：
  - 实现简单
  - 报告精简
- 缺点：
  - 不支持专业用户的详细需求
  - 后续扩展需要修改设计
- 实现复杂度：低
- MVP适配性：⚠️ 中（功能受限）

**⭐ 推荐方案**：方案A
**推荐理由**：
1. 用户体验：满足不同用户群体的需求
2. 复用性：利用现有--verbose参数，无需新增CLI
3. 可扩展性：P1指标实现后，可以自然地加入详细模式
4. 行业惯例：--verbose是通用约定，用户理解成本低

---

#### 决策点 4：基准数据支持（Alpha/Beta等相对收益指标）

**问题描述**：MVP阶段是否支持相对收益分析（需要加载基准数据，如BTC走势）？

**逻辑阐述**：
- **为何重要**：相对收益指标（Alpha、Beta、R²、跟踪误差）是专业量化分析的重要组成部分
- **影响范围**：影响数据加载逻辑、指标计算模块、MVP范围

**建议方案**：

**方案A（推荐）**：MVP跳过，推迟到P1
- 描述：MVP阶段不实现相对收益分析，专注于绝对收益和风险指标
- 优点：
  - 避免引入基准数据依赖，降低复杂度
  - 符合MVP最小功能集原则
  - P0的15个指标已足够评估策略质量
- 缺点：
  - 专业用户可能需要相对收益指标
- 实现复杂度：N/A（不实现）
- MVP适配性：✅ 高（MVP原则）

**方案B**：MVP支持，加载基准数据
- 描述：在run_strategy_backtest中新增--benchmark参数，加载基准K线数据
- 优点：
  - 提供完整的专业指标
  - 满足专业用户需求
- 缺点：
  - 增加数据加载逻辑复杂度
  - 需要处理基准数据缺失、时间对齐等问题
  - 违反MVP原则（非核心功能）
- 实现复杂度：高
- MVP适配性：❌ 低（过度工程）

**⭐ 推荐方案**：方案A
**推荐理由**：
1. MVP优先原则：Alpha、Beta是"锦上添花"而非"雪中送炭"
2. 最小代价：避免引入基准数据依赖和时间对齐复杂度
3. 核心价值聚焦：P0的15个指标已足够评估策略的绝对收益和风险
4. 可逆性：后续迭代可以无痛添加相对收益分析
5. 用户优先级：根据需求描述，用户优先关注的是收益和风险指标，相对收益是次要需求

---

#### 决策点 5：指标计算模块设计（独立 vs 集成）

**问题描述**：MetricsCalculator应该作为独立模块，还是集成到UnifiedOrderManager中？

**逻辑阐述**：
- **为何重要**：影响代码架构、可测试性、可维护性、职责分离
- **影响范围**：影响StrategyAdapter调用方式、UnifiedOrderManager职责、代码组织

**建议方案**：

**方案A（推荐）**：独立的MetricsCalculator模块
- 描述：创建独立的MetricsCalculator类，接受订单列表、权益曲线等数据作为输入
- 优点：
  - 单一职责：MetricsCalculator只负责计算，UnifiedOrderManager只负责订单管理
  - 可测试性：可以独立测试MetricsCalculator
  - 可复用性：其他模块也可以复用MetricsCalculator
  - 符合SOLID原则
- 缺点：
  - 需要多一个类
  - 调用时需要传递数据
- 实现复杂度：中
- MVP适配性：✅ 高（符合设计原则）

**方案B**：扩展UnifiedOrderManager
- 描述：在UnifiedOrderManager中添加calculate_metrics()方法
- 优点：
  - 实现简单，不需要新类
  - 数据传递方便（直接访问self._orders）
- 缺点：
  - 违反单一职责原则（订单管理 + 指标计算）
  - 降低可测试性
  - 增加UnifiedOrderManager的复杂度
- 实现复杂度：低
- MVP适配性：❌ 低（违反设计原则）

**⭐ 推荐方案**：方案A
**推荐理由**：
1. 单一职责：MetricsCalculator专注指标计算，UnifiedOrderManager专注订单管理
2. 可测试性：MetricsCalculator可以独立测试，不依赖订单管理逻辑
3. 可维护性：指标计算逻辑独立，易于理解和修改
4. 可扩展性：后续添加新指标时，只需要修改MetricsCalculator
5. 符合架构原则：遵循迭代013的"单一职责"设计决策

---

### 3. MVP实施优先级总结

**P0 核心功能（本迭代必须完成）**：
1. ✅ 收益指标：APR、绝对收益、累计收益率
2. ✅ 风险指标：MDD、波动率、恢复时间
3. ✅ 风险调整收益：夏普率、卡玛比率、MAR比率、盈利因子
4. ✅ 交易效率：交易频率、成本占比、胜率、盈亏比
5. ✅ 基础设施：MetricsCalculator、EquityCurveBuilder
6. ✅ CLI增强：--risk-free-rate参数
7. ✅ 报告增强：分层输出（默认/--verbose）

**P1 可推迟功能（后续迭代）**：
1. ⏸️ 高级风险：索提诺比率、下行波动率、VaR/CVaR
2. ⏸️ 稳定性：回归分析、偏度、峰度
3. ⏸️ 相对收益：Alpha、Beta、R²、跟踪误差（需要基准数据）
4. ⏸️ 可视化：权益曲线图、月度/年度收益柱状图

### 4. 设计决策确认

**已确认的设计决策**（基于用户"都同意，请继续"）：
1. ✅ 权益曲线跟踪：事后从订单记录重建（方案A）
2. ✅ 无风险收益率：CLI参数配置（方案A）
3. ✅ 报告详细程度：分层输出 + 复用--verbose（方案A）
4. ✅ 基准数据支持：MVP跳过，推迟到P1（方案A）
5. ✅ 模块设计：独立的MetricsCalculator模块（方案A）

### 5. Gate 1 检查

- [x] MVP核心价值已用一句话定义：提供符合量化交易行业标准的完整绩效评估指标体系
- [x] 所有功能点已标记优先级（[P0] 15个核心指标，[P1] 高级指标）
- [x] 范围边界已明确（In-Scope: P0核心指标，Out-of-Scope: P1高级指标和可视化）
- [x] 待决策清单中每项都有2+可行方案（5个决策点，每个2-3个方案）
- [x] P0功能点数量 = 17个（符合≤20个标准）
- [x] 11大类覆盖度分析已完成（通过现有能力分析）
- [x] 高优先级模糊点已全部澄清（5个决策点已确认）
- [x] 所有决策已同步到PRD对应章节
- [x] 覆盖度状态：核心类别≥80%为"Clear"

**Gate 1 通过** ✅

---

## 附录：现有能力分析报告

### 现有功能清单

| 功能名称 | 模块 | 与新需求关联 | 复用可能性 | 备注 |
|---------|------|-------------|-----------|------|
| 订单生命周期管理 | UnifiedOrderManager | 高（订单数据是指标计算基础） | 高（直接复用） | 无需修改 |
| 基础统计计算 | UnifiedOrderManager.calculate_statistics() | 高（部分指标已实现） | 高（复用胜率、盈亏等） | 扩展新指标 |
| 手续费率配置 | UnifiedOrderManager.__init__() | 中（成本占比计算需要） | 高（直接复用） | 无需修改 |
| K线数据加载 | run_strategy_backtest._load_klines() | 高（权益曲线重建需要） | 高（直接复用） | 无需修改 |
| 命令行参数解析 | run_strategy_backtest.add_arguments() | 高（新增--risk-free-rate） | 高（扩展参数） | 新增1个参数 |
| 报告输出格式 | run_strategy_backtest._display_results() | 高（报告增强核心） | 中（重构输出逻辑） | 分层输出 |
| --verbose参数 | run_strategy_backtest | 高（复用控制详细程度） | 高（直接复用） | 无需修改 |

### 复用建议

**可直接复用**：
- UnifiedOrderManager订单管理能力
- UnifiedOrderManager.calculate_statistics()（胜率、盈亏）
- K线数据加载逻辑
- --verbose参数机制

**可扩展复用**：
- add_arguments()：新增--risk-free-rate参数
- _display_results()：重构为分层输出格式

**需全新开发**：
- MetricsCalculator模块（独立）
- EquityCurveBuilder工具类
- 权益曲线数据结构（EquityPoint）
- 15个P0核心指标计算算法

### 一致性建议

**风格参考**：
- 遵循迭代013的命名约定（如calculate_xxx()）
- 使用Decimal类型处理金额和百分比
- 使用dataclass定义数据结构

**交互模式**：
- 遵循现有CLI参数模式（--param-name格式）
- 遵循现有报告输出格式（【分类】+ 缩进结构）

**注意事项**：
- 避免修改UnifiedOrderManager的核心逻辑（单一职责）
- 避免修改StrategyAdapter的回测流程（稳定性）
- 确保新指标计算不影响现有统计指标的准确性

### 集成路径建议

**优先集成**：
1. 创建MetricsCalculator独立模块
2. 在run_strategy_backtest中调用MetricsCalculator
3. 扩展_display_results()输出新指标
4. 复用UnifiedOrderManager的订单数据

**扩展策略**：
1. 不修改UnifiedOrderManager内部实现
2. 通过依赖注入传递MetricsCalculator
3. 保持StrategyAdapter无状态设计
4. 使用EquityCurveBuilder作为独立工具类

---

**文档版本**: v1.0.0
**创建日期**: 2026-01-06
**P1阶段状态**: ✅ 已完成，等待P3架构设计
**下一步**: 使用 `powerby-architect` 进行P3-P4阶段（技术调研+架构设计）
