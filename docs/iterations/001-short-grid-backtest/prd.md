# 产品需求文档 (PRD)

**迭代编号**：001
**迭代名称**：做空网格回测系统
**创建时间**：2025-12-19
**产品经理**：PowerBy AI Product Manager
**状态**：已确认 (P1阶段完成)

---

## 一、项目概述

### 1.1 项目背景

当前项目已实现基于成交量分析的动态网格交易系统（Grid V4），支持4小时、1小时、15分钟周期的回测。然而，现有回测引擎无法满足以下需求：

**痛点1：缺乏1分钟级别回测能力**
- 现有回测仅支持4h/1h/15m周期，无法模拟更精细的价格波动
- 1分钟K线是最接近tick数据的可获取数据源，是性能、可信度和可行性之间的最佳平衡点

**痛点2：选币策略缺乏验证工具**
- 现有筛选系统能输出代币评分，但无法快速验证某个代币在特定网格参数下的历史表现
- 需要手动指定网格范围（上下界、网格数）进行针对性回测

**痛点3：回测结果展示不直观**
- 需要独立的HTML报告页面，支持K线图、网格线叠加、交易标记
- 需要回放功能，逐分钟重现交易过程

### 1.2 目标用户

**主要用户**：项目开发者本人
- **使用场景**：在实盘运行网格策略前，通过历史数据回测验证策略参数的有效性
- **核心诉求**：快速测试不同交易对、不同网格范围、不同时间段的盈利潜力

### 1.3 核心价值主张

**一句话描述**：提供1分钟级别的做空网格回测能力，帮助用户通过历史数据验证选币策略和网格参数的有效性。

**核心价值**：
1. **精细回测**：1分钟K线级别，最接近真实tick数据的模拟
2. **灵活配置**：手动指定交易对、网格上下界、网格数量、回测时间段
3. **可视化报告**：独立HTML页面，ECharts图表，支持回放功能
4. **快速验证**：本地缓存1分钟K线数据，回测性能高效

### 1.4 MVP范围界定

**包含的功能**：
- 做空方向的经典网格策略（高抛低吸）
- 1分钟K线数据本地缓存
- 手动指定网格范围和参数
- Web回测报告生成和回放

**不包含的功能**（P1推迟）：
- 做多方向网格
- 多交易对批量回测
- 动态网格范围计算（复用现有成交量热力图）
- 高级风险指标（夏普比率、索提诺比率、最大回撤持续时间等）

### 1.5 成功标准

**定量指标**：
- 回测速度：10天1分钟K线（14400根）回测完成时间 < 30秒
- 数据准确性：网格触发判断误差率 = 0%（使用Decimal精度）
- 报告生成：HTML文件大小 < 50MB（10天回测）

**定性指标**：
- 用户（开发者本人）能够通过回测结果判断某个交易对是否适合网格策略
- 回测报告直观展示所有开仓/平仓事件和盈亏情况

---

## 二、网格实现机制量化定义

本章节定义做空网格回测的核心算法规格，所有参数和逻辑均已量化明确，无歧义。

### 2.1 网格范围与价格序列生成

#### 输入参数

| 参数名 | 类型 | 说明 | 约束 | 默认值示例 |
|--------|------|------|------|------------|
| `symbol` | string | 交易对 | 必填 | "ETHUSDT" |
| `price_upper` | float | 价格上界（做空起始价） | > price_lower | 2000.0 |
| `price_lower` | float | 价格下界（做空结束价） | < price_upper | 1800.0 |
| `grid_count` | int | 网格数量（不含边界） | 2 ≤ N ≤ 100 | 10 |

#### 计算逻辑

```python
# 计算网格间距（等间距）
grid_spacing = (price_upper - price_lower) / grid_count

# 生成网格价格序列（从上到下）
grid_prices = [price_upper - i * grid_spacing for i in range(grid_count + 1)]

# 示例：price_upper=2000, price_lower=1800, grid_count=10
# 结果：[2000.0, 1980.0, 1960.0, 1940.0, 1920.0, 1900.0,
#        1880.0, 1860.0, 1840.0, 1820.0, 1800.0]
# 共11个价格点，形成10个网格区间
```

#### 验收标准

- 网格价格序列严格递减
- 最高价格 = price_upper，最低价格 = price_lower
- 相邻网格间距均相等（误差 < 0.01 USDT）

### 2.2 做空网格交易逻辑（经典网格模式）

#### 核心原理

价格在网格区间内震荡时，**高点卖出（开空），低点买入（平仓）**，赚取差价。

#### 开仓规则

**触发条件**：
```python
# 价格上升触及某网格价格 grid_i
if candle.low <= grid_i <= candle.high:  # 1分钟K线区间包含网格价格
    if not has_open_position_at_grid(i):  # 该网格当前无持仓
        open_short_position(grid_i)
```

**开仓动作**：
- 在 `grid_i` 价格卖出开空
- 数量：`position_size_per_grid / grid_i` 个币
- 记录开仓时间、价格、数量

**约束条件**：
- 同一网格索引同时最多1个未平仓空单
- 开仓价格使用网格价格（而非K线收盘价，简化模型）

#### 平仓规则

**触发条件**：
```python
# 价格下降触及 grid_(i+1)（下一个更低的网格）
if candle.low <= grid_(i+1) <= candle.high:
    if has_open_position_at_grid(i):  # 上一层有持仓
        close_short_position(grid_i, close_price=grid_(i+1))
```

**平仓动作**：
- 在 `grid_(i+1)` 价格买入平仓
- 数量：等于开仓时的数量（全部平仓）
- 计算盈亏：`(grid_i - grid_(i+1)) * amount - 手续费`

#### 执行序列示例

```
时刻T1 (2024-01-01 10:15):
  - 1分钟K线: [Open=1955, High=1965, Low=1955, Close=1962]
  - 触发: Grid 3 (1960)
  - 动作: 卖出开空 0.5102个ETH @ 1960 USDT
  - 状态: 网格3持仓中

时刻T2 (2024-01-01 11:23):
  - 1分钟K线: [Open=1948, High=1948, Low=1938, Close=1942]
  - 触发: Grid 4 (1940)
  - 动作: 买入平仓 0.5102个ETH @ 1940 USDT
  - 盈亏: (1960-1940) * 0.5102 - 手续费 = 10.204 - 2.00 = 8.20 USDT
  - 状态: 网格3已平仓

时刻T3 (2024-01-01 14:05):
  - 1分钟K线: [Open=1975, High=1985, Low=1975, Close=1982]
  - 触发: Grid 2 (1980)
  - 动作: 卖出开空 0.5051个ETH @ 1980 USDT
  - 状态: 网格2持仓中
```

### 2.3 仓位分配（等额分配）

#### 计算逻辑

```python
total_capital = 10000.0  # USDT (初始资金)
position_size_per_grid = total_capital / grid_count

# 示例：10个网格，每个网格分配1000 USDT
```

#### 每个网格的币数量

```python
amount_at_grid_i = position_size_per_grid / grid_prices[i]

# 示例（10个网格，每个1000 USDT）：
# Grid 0 (2000 USDT): 1000 / 2000 = 0.5000 ETH
# Grid 1 (1980 USDT): 1000 / 1980 = 0.5051 ETH
# Grid 2 (1960 USDT): 1000 / 1960 = 0.5102 ETH
# Grid 3 (1940 USDT): 1000 / 1940 = 0.5155 ETH
# ...
```

#### 约束条件

- 任意时刻所有持仓市值总和 ≤ total_capital（避免超额使用资金）
- 每个网格最多持有1个未平仓空单

### 2.4 1分钟K线触发判断（区间包含法）

#### 判断逻辑

```python
def is_price_triggered(candle: KLine, target_price: float) -> bool:
    """
    判断1分钟K线是否触及目标价格

    Args:
        candle: 1分钟K线数据 {open, high, low, close, volume}
        target_price: 目标网格价格

    Returns:
        True: K线的[low, high]区间包含target_price
        False: 未触及
    """
    return candle.low <= target_price <= candle.high
```

#### 精度处理（避免浮点数误差）

```python
from decimal import Decimal

candle_low = Decimal(str(candle.low))
candle_high = Decimal(str(candle.high))
grid_price = Decimal(str(target_price))

is_triggered = candle_low <= grid_price <= candle_high
```

#### 边界情况处理

- **情况1**：`candle.low == grid_price` 或 `candle.high == grid_price` → 视为触发
- **情况2**：1分钟K线同时触及多个网格价格（极端波动）
  - 处理方式：按价格顺序依次处理（先处理高价格网格，再处理低价格网格）
  - 原因：符合实际交易执行顺序

#### 验收标准

- 触发判断准确率 = 100%（无浮点数误差）
- 极端波动情况下（单根K线跨越3+网格），所有触发网格均被正确识别

### 2.5 止损/止盈规则

#### 止损规则

**触发条件**：
```python
stop_loss_trigger_price = price_upper * (1 + stop_loss_pct)
# 默认: stop_loss_pct = 0.02 (2%)

if current_price > stop_loss_trigger_price:
    trigger_stop_loss()
```

**执行动作**：
1. 立即以当前K线收盘价平掉所有未平仓的空单
2. 记录止损事件：`{"type": "stop_loss", "trigger_price": ..., "loss": ...}`
3. 停止后续开仓（可选策略，MVP中止损后继续监控）

**示例**：
```
price_upper = 2000 USDT
stop_loss_pct = 0.02
止损触发价 = 2000 * 1.02 = 2040 USDT

时刻T (2024-01-05 15:30):
  - 当前价格: 2045 USDT
  - 触发: 止损
  - 持仓: Grid 2 (1980) 0.5051个ETH, Grid 1 (2000) 0.5000个ETH
  - 动作: 全部以2045 USDT平仓
  - 损失: Grid 2损失 (2045-1980)*0.5051 = 32.83 USDT
         Grid 1损失 (2045-2000)*0.5000 = 22.50 USDT
         总损失: 55.33 USDT + 手续费
```

#### 止盈规则

**止盈方式**：自然完成（无需额外平仓逻辑）

**说明**：
- 当价格下跌到 `price_lower` 时，所有网格空单已逐层平仓完毕
- 此时系统状态：无持仓，现金余额 = 初始资金 + 所有网格盈利 - 手续费总和
- **不需要**额外的止盈触发逻辑

#### 回测结束时强制平仓

**时刻**：回测时间段的最后一根1分钟K线

**执行动作**：
1. 以最后K线收盘价平掉所有剩余持仓
2. 计算最终盈亏
3. 标记为"超时平仓"事件：`{"type": "timeout_close", "remaining_positions": [...]}`

### 2.6 手续费计算

#### 手续费模型

```python
fee_rate = 0.001  # 0.1% (Binance Taker费率)

# 开仓手续费
fee_open = sell_amount * open_price * fee_rate

# 平仓手续费
fee_close = buy_amount * close_price * fee_rate

# 总手续费
total_fee = fee_open + fee_close

# 净盈亏
net_pnl = (open_price - close_price) * amount - total_fee
```

#### 计算示例

```
在Grid 3 (1960)开空 0.5102个ETH：
  - 开仓手续费 = 0.5102 * 1960 * 0.001 = 1.000 USDT

在Grid 4 (1940)平仓 0.5102个ETH：
  - 平仓手续费 = 0.5102 * 1940 * 0.001 = 0.990 USDT

毛利润 = (1960 - 1940) * 0.5102 = 10.204 USDT
总手续费 = 1.000 + 0.990 = 1.990 USDT
净盈亏 = 10.204 - 1.990 = 8.214 USDT
```

#### 验收标准

- 所有交易均扣除手续费
- 手续费计算精度：小数点后2位（USDT）
- 最终盈亏报告中包含手续费总和统计

### 2.7 持仓状态追踪

#### 数据结构定义

```python
GridPosition {
    id: int                      # 持仓ID（自增）
    grid_index: int              # 网格索引 (0~grid_count-1)
    grid_price: Decimal          # 网格价格
    direction: str               # 'short' (固定)
    open_price: Decimal          # 实际开仓价格（=grid_price）
    open_time: datetime          # 开仓时间（1分钟K线时间戳）
    amount: Decimal              # 开仓数量（ETH）
    status: str                  # 'open' | 'closed'
    close_price: Decimal | None  # 平仓价格（如已平仓）
    close_time: datetime | None  # 平仓时间
    pnl: Decimal | None          # 已实现盈亏（如已平仓）
    fee_paid: Decimal            # 已支付手续费总和
}
```

#### 状态机转换

```
open (持仓中)
  → [触发下一网格] → closed (已平仓)
  → [触发止损] → closed (止损平仓)
  → [回测结束] → closed (超时平仓)
```

#### 约束条件

- 同一`grid_index`同时最多1个`status='open'`的持仓
- 开仓时检查：`if GridPosition.filter(grid_index=i, status='open').exists(): skip`

#### 验收标准

- 所有持仓状态转换可追溯
- 回测结束时无遗漏的未平仓位（全部强制平仓）

---

## 三、功能需求详细描述

本章节按功能类别详细描述所有P0核心功能点（共21个）。

### 3.1 回测参数配置（5个功能点）

#### F1.1 交易对选择 [P0]

**功能描述**：用户可以输入单个交易对进行回测。

**输入**：
- 交易对代码（如"ETHUSDT"）
- 默认值："ETHUSDT"

**验证规则**：
- 必填字段
- 格式：大写字母 + "USDT"（如BTCUSDT, ETHUSDT, SOLUSDT）
- 交易对必须在Binance永续合约市场存在

**输出**：
- 验证通过：接受输入并继续
- 验证失败：提示"交易对不存在或格式错误"

#### F1.2 网格方向固定 [P0]

**功能描述**：MVP版本固定为"做空"方向，无需用户选择。

**实现方式**：
- 代码中硬编码 `direction = 'short'`
- UI界面可显示"网格方向：做空（固定）"提示

#### F1.3 网格范围设定 [P0]

**功能描述**：用户手动指定网格的价格上界、下界和网格数量。

**输入**：
- `price_upper`（价格上界，USDT）：必填，正数
- `price_lower`（价格下界，USDT）：必填，正数，< price_upper
- `grid_count`（网格数量）：必填，整数，2-100之间

**示例输入**：
```json
{
  "price_upper": 2000.0,
  "price_lower": 1800.0,
  "grid_count": 10
}
```

**验证规则**：
- price_upper > price_lower，否则提示"价格上界必须大于下界"
- grid_count ∈ [2, 100]，否则提示"网格数量必须在2-100之间"
- 网格间距 > 0.1 USDT，否则提示"网格过密，请减少网格数量"

**输出**：
- 自动生成网格价格序列并显示预览

#### F1.4 回测时间段选择 [P0]

**功能描述**：用户指定回测的开始日期和结束日期。

**输入**：
- `start_date`（开始日期）：必填，格式YYYY-MM-DD
- `end_date`（结束日期）：必填，格式YYYY-MM-DD，>= start_date

**示例输入**：
```json
{
  "start_date": "2024-01-01",
  "end_date": "2024-01-10"
}
```

**验证规则**：
- end_date >= start_date，否则提示"结束日期不能早于开始日期"
- 时间跨度 ≤ 90天，否则提示"回测时间跨度不能超过90天（性能限制）"
- 日期不能晚于当前日期

**输出**：
- 显示时间跨度天数和预计K线数量（天数 × 1440）

#### F1.5 止损比例设定 [P0]

**功能描述**：用户可以设定止损触发比例。

**输入**：
- `stop_loss_pct`（止损百分比）：必填，浮点数，0.01-0.10之间
- 默认值：0.02（2%）

**验证规则**：
- 范围限制：1%-10%
- 计算止损触发价：price_upper × (1 + stop_loss_pct)

**输出**：
- 显示止损触发价预览："止损触发价 = 2040 USDT"

---

### 3.2 K线数据管理（3个功能点）

#### F2.1 1分钟K线本地缓存 [P0]

**功能描述**：从Binance API获取1分钟K线数据并缓存到PostgreSQL数据库。

**数据来源**：
- API：Binance Futures /fapi/v1/klines
- 参数：symbol, interval=1m, startTime, endTime, limit=1000

**数据结构**：
```python
KLine {
    symbol: str              # ETHUSDT
    interval: str            # '1m'
    open_time: datetime      # K线开盘时间
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal
    close_time: datetime
}
```

**缓存策略**：
- 数据库表：`backtest_kline`
- 唯一索引：`(symbol, interval, open_time)`
- 增量更新：仅获取缺失时间段的数据

**性能要求**：
- 单次API请求获取1000根K线
- 10天数据（14400根）获取时间 < 20秒

#### F2.2 K线数据查询接口 [P0]

**功能描述**：提供按时间范围查询1分钟K线的接口，返回DataFrame格式。

**接口签名**：
```python
def load_klines(
    symbol: str,
    start_date: datetime,
    end_date: datetime
) -> pd.DataFrame
```

**查询逻辑**：
```python
queryset = KLine.objects.filter(
    symbol=symbol,
    interval='1m',
    open_time__gte=start_date,
    open_time__lte=end_date
).order_by('open_time')
```

**返回格式**：
```python
DataFrame {
    index: open_time (DatetimeIndex)
    columns: [Open, High, Low, Close, Volume]
}
```

**性能要求**：
- 10天数据（14400根）查询时间 < 1秒

#### F2.3 缓存数据验证 [P0]

**功能描述**：检查本地缓存是否完整覆盖回测时间段，缺失则自动补充。

**验证逻辑**：
```python
# 1. 查询缓存中的时间范围
cached_range = KLine.objects.filter(
    symbol=symbol,
    interval='1m'
).aggregate(Min('open_time'), Max('open_time'))

# 2. 检查是否覆盖 [start_date, end_date]
if cached_range['min'] > start_date or cached_range['max'] < end_date:
    # 3. 自动补充缺失数据
    fetch_missing_data(symbol, start_date, end_date)
```

**用户反馈**：
- 缓存完整：直接开始回测
- 缓存缺失：显示"正在获取缺失数据...（2024-01-05 ~ 2024-01-10）"

**验收标准**：
- 自动补全成功率 = 100%
- 补全后回测可无缝执行

---

### 3.3 做空策略执行模拟（9个功能点）

#### F3.1 网格价格序列生成 [P0]

**功能描述**：根据用户输入的上下界和网格数量，自动生成等间距的网格价格序列。

**实现逻辑**：参见2.1章节

**输出**：
```python
[2000.0, 1980.0, 1960.0, 1940.0, 1920.0, 1900.0, 1880.0, 1860.0, 1840.0, 1820.0, 1800.0]
```

#### F3.2 区间包含触发判断 [P0]

**功能描述**：实现1分钟K线区间包含网格价格的判断逻辑。

**实现逻辑**：参见2.4章节

**关键代码**：
```python
from decimal import Decimal

def is_triggered(candle, grid_price):
    low = Decimal(str(candle.low))
    high = Decimal(str(candle.high))
    price = Decimal(str(grid_price))
    return low <= price <= high
```

#### F3.3 卖出开空模拟 [P0]

**功能描述**：价格上升触及网格时，模拟卖出开空操作。

**执行条件**：
- K线触及某网格价格 grid_i
- 该网格当前无持仓

**执行动作**：
```python
amount = (total_capital / grid_count) / grid_i
fee = amount * grid_i * 0.001

position = GridPosition.objects.create(
    grid_index=i,
    grid_price=grid_i,
    direction='short',
    open_price=grid_i,
    open_time=candle.open_time,
    amount=amount,
    status='open',
    fee_paid=fee
)
```

**日志记录**：
```
[2024-01-01 10:15] 🔴 开空单: Grid 3 (1960 USDT), 数量=0.5102 ETH, 手续费=1.00 USDT
```

#### F3.4 买入平仓模拟 [P0]

**功能描述**：价格下降触及下一网格时，模拟买入平仓操作。

**执行条件**：
- K线触及 grid_(i+1)
- grid_i 有持仓

**执行动作**：
```python
close_fee = position.amount * grid_(i+1) * 0.001
total_fee = position.fee_paid + close_fee
pnl = (position.open_price - grid_(i+1)) * position.amount - total_fee

position.status = 'closed'
position.close_price = grid_(i+1)
position.close_time = candle.open_time
position.pnl = pnl
position.fee_paid = total_fee
position.save()
```

**日志记录**：
```
[2024-01-01 11:23] 🟢 平仓: Grid 3 (1940 USDT), 盈亏=+8.20 USDT
```

#### F3.5 持仓状态追踪 [P0]

**功能描述**：记录每个网格的开仓/平仓状态、持仓量、持仓成本。

**数据结构**：参见2.7章节

**查询接口**：
```python
# 获取所有持仓中的空单
open_positions = GridPosition.objects.filter(
    backtest_result_id=result_id,
    status='open',
    direction='short'
)

# 获取指定网格的持仓
grid_position = GridPosition.objects.filter(
    backtest_result_id=result_id,
    grid_index=i,
    status='open'
).first()
```

#### F3.6 重复开仓防护 [P0]

**功能描述**：防止在同一网格重复开仓。

**检查逻辑**：
```python
def has_open_position(grid_index):
    return GridPosition.objects.filter(
        backtest_result_id=result_id,
        grid_index=grid_index,
        status='open'
    ).exists()

# 开仓前检查
if not has_open_position(i):
    open_short_position(grid_i)
```

#### F3.7 等额仓位分配 [P0]

**功能描述**：总资金平均分配到所有网格。

**实现逻辑**：参见2.3章节

**计算示例**：
```python
total_capital = 10000.0
grid_count = 10
position_size_per_grid = 1000.0

# Grid 0: 1000 / 2000 = 0.5000 ETH
# Grid 1: 1000 / 1980 = 0.5051 ETH
```

#### F3.8 手续费计算（0.1%） [P0]

**功能描述**：开仓和平仓均扣除0.1%手续费。

**实现逻辑**：参见2.6章节

**计算公式**：
```python
fee_open = amount * open_price * 0.001
fee_close = amount * close_price * 0.001
total_fee = fee_open + fee_close
```

#### F3.9 Decimal精度处理 [P0]

**功能描述**：使用Decimal类型避免浮点数误差。

**实现规范**：
```python
from decimal import Decimal, ROUND_HALF_UP

# 所有价格、数量、金额字段使用Decimal
price = Decimal(str(raw_price))
amount = Decimal(str(raw_amount))

# 金额保留2位小数（USDT）
usdt_value = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

# 数量保留8位小数（ETH）
eth_amount = amount.quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP)
```

**验收标准**：
- 所有金额计算误差 < 0.01 USDT
- 触发判断无误判/漏判

---

### 3.4 回测结果计算（5个功能点）

#### F4.1 总盈亏计算 [P0]

**功能描述**：统计所有已平仓空单的盈亏总和。

**计算逻辑**：
```python
closed_positions = GridPosition.objects.filter(
    backtest_result_id=result_id,
    status='closed'
)

total_pnl = sum([pos.pnl for pos in closed_positions])
```

**输出格式**：
```json
{
  "total_pnl": 245.67,  // USDT
  "initial_capital": 10000.0,
  "final_capital": 10245.67,
  "return_rate": 0.0246  // 2.46%
}
```

#### F4.2 网格触发次数统计 [P0]

**功能描述**：记录开仓次数和平仓次数。

**统计逻辑**：
```python
all_positions = GridPosition.objects.filter(
    backtest_result_id=result_id
)

open_count = all_positions.count()
closed_count = all_positions.filter(status='closed').count()
```

**输出格式**：
```json
{
  "total_trades": 25,
  "closed_trades": 23,
  "open_trades": 2
}
```

#### F4.3 收益率计算 [P0]

**功能描述**：基于初始资金计算收益率百分比。

**计算公式**：
```python
return_rate = (final_capital - initial_capital) / initial_capital
return_pct = return_rate * 100
```

**输出示例**：
```
收益率: +2.46%
```

#### F4.4 手续费统计 [P0]

**功能描述**：累计所有交易的手续费支出。

**统计逻辑**：
```python
total_fee = sum([pos.fee_paid for pos in closed_positions])
```

**输出格式**：
```json
{
  "total_fee": 45.32,  // USDT
  "fee_ratio": 0.0045  // 占初始资金的0.45%
}
```

#### F4.5 止损触发记录 [P0]

**功能描述**：记录止损事件和止损损失。

**事件结构**：
```python
stop_loss_event = {
    "type": "stop_loss",
    "trigger_time": "2024-01-05 15:30",
    "trigger_price": 2045.0,
    "positions_closed": [
        {"grid_index": 1, "loss": -22.50},
        {"grid_index": 2, "loss": -32.83}
    ],
    "total_loss": -55.33
}
```

**存储位置**：
- BacktestSnapshot表的events字段（JSON）

---

### 3.5 Web报告生成（5个功能点）

#### F5.1 独立HTML页面生成 [P0]

**功能描述**：生成包含完整回测数据和可视化的单一HTML文件。

**文件结构**：
```html
<!DOCTYPE html>
<html>
<head>
    <title>回测报告 - ETHUSDT</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
    <style>/* 内联CSS */</style>
</head>
<body>
    <div id="summary"><!-- 盈亏汇总表格 --></div>
    <div id="chart" style="width:100%;height:600px;"></div>
    <div id="player"><!-- 回放控制器 --></div>
    <script>
        // 内联回测数据（JSON）
        const backtestData = { ... };
        // 内联ECharts可视化代码
    </script>
</body>
</html>
```

**文件命名**：
```
backtest_ETHUSDT_2024-01-01_2024-01-10_20250119_143052.html
```

#### F5.2 K线图表展示 [P0]

**功能描述**：使用ECharts绘制1分钟K线图表。

**图表配置**：
```javascript
option = {
    xAxis: { type: 'time' },
    yAxis: { type: 'value', scale: true },
    series: [{
        type: 'candlestick',
        data: klineData  // [[timestamp, open, close, low, high], ...]
    }],
    dataZoom: [
        { type: 'inside' },
        { type: 'slider', start: 0, end: 100 }
    ]
}
```

**数据格式**：
```javascript
klineData = [
    ['2024-01-01 00:00', 2200.5, 2205.3, 2198.2, 2203.8],
    ['2024-01-01 00:01', 2203.8, 2210.1, 2203.5, 2209.2],
    ...
]
```

#### F5.3 网格线叠加 [P0]

**功能描述**：在K线图上显示所有网格价格的水平线。

**实现方式**：
```javascript
option.series.push({
    type: 'line',
    name: '网格线',
    markLine: {
        symbol: 'none',
        label: { position: 'end', formatter: 'Grid {c}' },
        lineStyle: { type: 'dashed', color: '#999' },
        data: [
            { yAxis: 2000 },  // Grid 0
            { yAxis: 1980 },  // Grid 1
            { yAxis: 1960 },  // Grid 2
            ...
        ]
    }
})
```

#### F5.4 开仓/平仓标记 [P0]

**功能描述**：在K线图上标注每次开仓（红点）和平仓（绿点）的位置。

**实现方式**：
```javascript
option.series.push({
    type: 'scatter',
    name: '开仓',
    symbolSize: 8,
    itemStyle: { color: 'red' },
    data: [
        ['2024-01-01 10:15', 1960],  // [时间, 价格]
        ['2024-01-01 14:05', 1980],
        ...
    ]
})

option.series.push({
    type: 'scatter',
    name: '平仓',
    symbolSize: 8,
    itemStyle: { color: 'green' },
    data: [
        ['2024-01-01 11:23', 1940],
        ...
    ]
})
```

#### F5.5 盈亏汇总表格 [P0]

**功能描述**：展示总盈亏、收益率、触发次数、手续费等关键指标。

**表格内容**：
```html
<table>
  <tr><td>交易对</td><td>ETHUSDT</td></tr>
  <tr><td>回测时间</td><td>2024-01-01 ~ 2024-01-10</td></tr>
  <tr><td>初始资金</td><td>10,000.00 USDT</td></tr>
  <tr><td>最终资金</td><td>10,245.67 USDT</td></tr>
  <tr><td>总盈亏</td><td class="profit">+245.67 USDT</td></tr>
  <tr><td>收益率</td><td class="profit">+2.46%</td></tr>
  <tr><td>交易次数</td><td>25</td></tr>
  <tr><td>已平仓</td><td>23</td></tr>
  <tr><td>盈利交易</td><td>20 (86.96%)</td></tr>
  <tr><td>亏损交易</td><td>3 (13.04%)</td></tr>
  <tr><td>手续费总计</td><td>45.32 USDT</td></tr>
  <tr><td>止损触发</td><td>1次</td></tr>
</table>
```

---

### 3.6 回放功能（3个功能点）

#### F6.1 时间轴控制 [P0]

**功能描述**：提供播放/暂停按钮，按1分钟K线逐步推进回测过程。

**UI组件**：
```html
<div id="player-controls">
    <button id="play-btn">▶ 播放</button>
    <button id="pause-btn">⏸ 暂停</button>
    <button id="reset-btn">⏮ 重置</button>
    <span id="current-time">2024-01-01 00:00</span>
    <input type="range" id="timeline-slider" min="0" max="14400" value="0">
</div>
```

**播放逻辑**：
```javascript
let currentIndex = 0;
const playInterval = setInterval(() => {
    if (currentIndex >= klineData.length) {
        clearInterval(playInterval);
        return;
    }

    updateChart(currentIndex);
    highlightEvents(currentIndex);
    currentIndex++;
}, 100);  // 100ms per candle
```

#### F6.2 开平仓事件高亮 [P0]

**功能描述**：回放时高亮显示当前K线触发的开仓/平仓事件。

**实现方式**：
```javascript
function highlightEvents(index) {
    const currentCandle = klineData[index];
    const events = backtestData.snapshots[index].events;

    events.forEach(event => {
        if (event.type === 'open_position') {
            showNotification(`🔴 开空单: Grid ${event.grid_index}`);
        } else if (event.type === 'close_position') {
            showNotification(`🟢 平仓: Grid ${event.grid_index}, 盈亏=${event.pnl}`);
        }
    });
}
```

#### F6.3 持仓状态实时显示 [P0]

**功能描述**：回放时显示当前各网格的持仓状态。

**UI组件**：
```html
<div id="positions-panel">
    <h3>当前持仓</h3>
    <ul id="positions-list">
        <li>Grid 2 (1980 USDT): 0.5051 ETH, 未实现盈亏: +15.30 USDT</li>
        <li>Grid 5 (1900 USDT): 0.5263 ETH, 未实现盈亏: +31.58 USDT</li>
    </ul>
    <p>总持仓价值: 1980.00 USDT</p>
    <p>可用现金: 8020.00 USDT</p>
</div>
```

**更新逻辑**：
```javascript
function updatePositions(index) {
    const snapshot = backtestData.snapshots[index];
    const positionsList = document.getElementById('positions-list');

    positionsList.innerHTML = snapshot.positions.map(pos => `
        <li>Grid ${pos.grid_index} (${pos.grid_price} USDT):
            ${pos.remaining} ETH,
            未实现盈亏: ${calculateUnrealizedPnl(pos, snapshot.current_price)} USDT
        </li>
    `).join('');
}
```

---

## 四、非功能需求

### 4.1 性能需求

| 指标 | 要求 | 说明 |
|------|------|------|
| 回测速度 | 10天（14400根K线）< 30秒 | 包含数据加载、策略执行、结果计算全流程 |
| 数据获取速度 | 10天数据 < 20秒 | 从Binance API获取并缓存 |
| 数据库查询 | 10天数据 < 1秒 | 从本地PostgreSQL查询 |
| HTML生成 | < 5秒 | 生成包含全部数据的独立HTML文件 |
| HTML文件大小 | < 50MB | 10天回测的HTML文件大小上限 |
| 回放流畅度 | 100ms/K线 | 回放时每根K线切换延迟 |

### 4.2 数据准确性需求

| 指标 | 要求 | 说明 |
|------|------|------|
| 触发判断误差率 | 0% | 使用Decimal精度，无浮点数误差 |
| 金额计算精度 | ±0.01 USDT | 所有金额（盈亏、手续费）精度要求 |
| 数量计算精度 | 0.00000001 ETH | 持仓数量精度（8位小数） |
| 数据完整性 | 100% | 所有K线、持仓、事件数据无遗漏 |

### 4.3 可用性需求

| 指标 | 要求 |
|------|------|
| 参数验证 | 所有输入参数进行前端+后端双重验证，提供清晰错误提示 |
| 进度反馈 | 回测过程显示实时进度（X%），数据获取显示进度条 |
| 错误恢复 | API请求失败时自动重试3次，仍失败则提示用户 |
| 报告可用性 | HTML报告可在无网络环境下打开（CDN资源本地化可选） |

### 4.4 兼容性需求

| 组件 | 要求 |
|------|------|
| 数据库 | PostgreSQL 12+ |
| Python版本 | Python 3.8+ |
| Web浏览器 | Chrome 90+, Firefox 88+, Safari 14+ |
| ECharts版本 | ECharts 5.x |

### 4.5 可维护性需求

- **代码复用**：尽可能复用现有Grid V4策略的持仓管理、止损止盈等模块
- **模块化设计**：将网格生成、触发判断、仓位管理、报告生成等拆分为独立模块
- **日志记录**：关键操作（开仓、平仓、止损）记录详细日志，便于调试
- **测试覆盖**：核心逻辑（触发判断、盈亏计算）单元测试覆盖率 > 80%

---

## 五、验收标准

### 5.1 MVP验收清单

**必须通过所有以下测试，才能标记迭代001为"完成"**：

#### ✅ 基础功能验收

- [ ] **参数输入验证**：输入ETHUSDT、price_upper=2000、price_lower=1800、grid_count=10、start_date=2024-01-01、end_date=2024-01-10，系统接受并生成11个网格价格
- [ ] **数据缓存验证**：首次运行自动从Binance获取10天1分钟K线数据，第二次运行直接使用缓存
- [ ] **回测执行验证**：回测完成时间 < 30秒，无报错，生成回测结果记录

#### ✅ 网格逻辑验收

- [ ] **触发判断验证**：手动构造1分钟K线[Low=1955, High=1965]，验证Grid 3 (1960)被触发
- [ ] **开仓验证**：价格首次触及1960时，创建grid_index=2的空单持仓，数量=1000/1960≈0.5102 ETH
- [ ] **平仓验证**：价格触及1940时，平仓grid_index=2的空单，计算pnl=(1960-1940)*0.5102-手续费≈8.2 USDT
- [ ] **重复开仓防护验证**：价格在同一网格二次触发时，不创建新持仓

#### ✅ 盈亏计算验收

- [ ] **总盈亏准确性**：所有已平仓持仓pnl之和 = 回测结果total_pnl
- [ ] **手续费计算**：每笔交易扣除0.1%×2（开仓+平仓）手续费
- [ ] **收益率计算**：final_capital = initial_capital + total_pnl，return_rate计算正确

#### ✅ 止损验收

- [ ] **止损触发验证**：价格突破price_upper*(1+0.02)=2040时，所有持仓立即平仓
- [ ] **止损记录验证**：BacktestSnapshot.events包含type="stop_loss"事件

#### ✅ Web报告验收

- [ ] **HTML生成验证**：生成独立HTML文件，文件大小 < 50MB
- [ ] **K线图表验证**：打开HTML文件，显示完整1分钟K线图表，可缩放
- [ ] **网格线验证**：K线图上显示11条水平虚线（网格价格）
- [ ] **交易标记验证**：K线图上显示红点（开仓）和绿点（平仓）
- [ ] **盈亏表格验证**：汇总表格显示初始资金、最终资金、收益率、交易次数等所有指标

#### ✅ 回放功能验收

- [ ] **播放控制验证**：点击播放按钮，K线逐根推进，显示当前时间
- [ ] **事件高亮验证**：回放到开仓K线时，弹出"🔴 开空单"提示
- [ ] **持仓显示验证**：回放过程中，持仓面板实时显示当前各网格的持仓状态

### 5.2 边界情况测试

- [ ] **极端波动测试**：单根K线跨越3个网格，验证所有网格均被正确触发和处理
- [ ] **无交易测试**：回测期间价格始终在网格范围外，验证无开仓，最终盈亏=0
- [ ] **全止损测试**：回测期间触发止损，验证所有持仓被平仓，记录止损事件
- [ ] **长时间回测测试**：回测90天（129600根K线），验证性能和数据完整性

### 5.3 定性验收

**由用户（开发者本人）判断**：

- [ ] 回测结果是否能帮助判断某个交易对是否适合网格策略？
- [ ] 回测报告是否直观展示所有关键信息？
- [ ] 回放功能是否帮助理解策略执行过程？

### 5.4 交付物清单

**迭代001完成时，必须交付以下文件/功能**：

- [ ] **代码交付**：
  - 1分钟K线数据缓存模块
  - 做空网格回测引擎（新建或扩展现有引擎）
  - Web报告生成器（HTML + ECharts）
  - 回放功能前端代码

- [ ] **文档交付**：
  - 本PRD文档（prd.md）
  - 功能点清单（function-points.md）
  - 澄清记录（clarifications.md）
  - 代码注释和docstring

- [ ] **测试交付**：
  - 单元测试：触发判断、盈亏计算、手续费计算
  - 集成测试：完整回测流程端到端测试

- [ ] **示例交付**：
  - 至少1个完整的回测HTML报告示例（ETHUSDT, 10天）

---

## 六、附录

### 6.1 术语表

| 术语 | 定义 |
|------|------|
| 网格 (Grid) | 在价格区间内等间距分布的价格点 |
| 做空 (Short) | 高价卖出，低价买入，赚取差价 |
| 开仓 (Open Position) | 建立新的空单持仓 |
| 平仓 (Close Position) | 结束已有持仓，实现盈亏 |
| 触发 (Trigger) | 价格到达网格价格，满足交易条件 |
| 止损 (Stop Loss) | 价格突破止损线，强制平仓避免更大损失 |
| 手续费 (Fee) | 每笔交易（开仓+平仓）支付的交易成本 |
| 回放 (Playback) | 按时间顺序重现回测执行过程 |

### 6.2 参考资料

- **现有实现**：
  - Grid V4策略文档：`docs/GRID_STRATEGY_ALGORITHM.md`
  - Grid V4策略代码：`backtest/services/grid_strategy_v4.py`
  - Web播放器指南：`docs/WEB_BACKTEST_PLAYER_GUIDE.md`

- **外部资源**：
  - Binance API文档：https://binance-docs.github.io/apidocs/futures/en/
  - ECharts文档：https://echarts.apache.org/zh/index.html
  - Python Decimal模块：https://docs.python.org/3/library/decimal.html

### 6.3 变更记录

| 日期 | 版本 | 变更内容 | 变更人 |
|------|------|----------|--------|
| 2025-12-19 | v1.0 | 初始版本，P1阶段完成 | PowerBy AI Product Manager |

---

**文档结束**

