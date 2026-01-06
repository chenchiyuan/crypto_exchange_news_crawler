# PRD: 买卖订单追踪系统 (Buy-Sell Order Tracking)

**迭代编号**: 012
**迭代名称**: 买卖订单追踪系统
**文档版本**: 1.0
**创建日期**: 2026-01-06
**状态**: 需求定义
**优先级**: P0

---

## ⚠️ 增量更新声明

**本迭代是增量更新，遵循以下原则：**

| 原则 | 说明 |
|------|------|
| **完全兼容** | 现有 DDPS-Z 所有功能保持不变（买入信号标记、EMA、概率带等） |
| **功能叠加** | 订单追踪是**新增**功能，基于现有买入信号生成虚拟订单 |
| **复用优先** | 充分复用迭代011的买入信号计算（BuySignalCalculator） |
| **UI 扩展** | 前端新增订单状态显示和盈亏统计面板 |

---

## 第一部分：需求原始输入

### 1.1 原始需求
> 每个买单都需要单独记录买入时间和金额。购买金额支持多策略，目前的策略是每次策略触发固定100U，需要以订单的形式记录购买金额，时间，数量。
>
> 每个订单都需要匹配卖出策略，可以支持设置多策略，任何策略触发即卖出。第一版最简的卖出策略：买入之后的k线检查low到high之间的价格包含4h ema25均线价格，则以ema25均线价格卖出，按照第一个满足条件的k线卖出。总结就是在下一次回归ema25均线价格时卖出，不带止损策略。
>
> 我需要记录买入情况，持仓情况，卖出情况。在/ddps-z/detail/ETHUSDT/ 中也有一个最简单的盈亏和胜率统计

### 1.2 核心目标
将迭代011的买入信号转化为完整的**虚拟订单生命周期管理**，实现：
1. 买入订单记录（触发时自动创建）
2. 持仓状态追踪（等待卖出）
3. 卖出订单匹配（策略触发时执行）
4. 盈亏统计分析（胜率、收益率）

### 1.3 目标用户
- 主要用户：产品开发者本人
- 使用目的：策略回测验证、盈亏分析

### 1.4 预期效果
用户在查看K线图时，能够：
1. 看到每个买入信号对应的虚拟订单
2. 了解每个订单的持仓状态（持仓中/已卖出）
3. 查看每个订单的盈亏情况
4. 在页面顶部看到汇总的胜率和总收益统计

---

## 第二部分：功能规格框架

### 2.1 订单数据模型

#### 2.1.1 虚拟订单结构
```python
class VirtualOrder:
    """虚拟订单（纯内存计算，不持久化）"""

    # 买入信息
    buy_timestamp: int          # 买入时间戳
    buy_price: Decimal          # 买入价格（K线close）
    buy_amount_usdt: Decimal    # 买入金额（固定100U）
    buy_quantity: Decimal       # 买入数量 = buy_amount_usdt / buy_price
    buy_strategy_id: str        # 触发的买入策略ID

    # 卖出信息
    sell_timestamp: int | None  # 卖出时间戳（None表示持仓中）
    sell_price: Decimal | None  # 卖出价格（EMA25）
    sell_strategy_id: str | None  # 触发的卖出策略ID

    # 计算字段
    status: str                 # 状态：holding（持仓）| sold（已卖出）
    profit_usdt: Decimal | None # 盈亏金额（USDT）
    profit_rate: Decimal | None # 盈亏比例（%）
    holding_periods: int | None # 持仓K线数
```

#### 2.1.2 买入金额策略
| 策略名称 | 说明 | MVP实现 |
|----------|------|---------|
| **固定金额** | 每次买入固定100 USDT | ✅ MVP默认 |
| 比例金额 | 按总资金比例买入 | ❌ P1推迟 |
| 动态金额 | 根据信号强度调整 | ❌ P1推迟 |

**MVP买入逻辑**：
```python
buy_amount_usdt = Decimal("100")  # 固定100U
buy_quantity = buy_amount_usdt / buy_price
```

---

### 2.2 卖出策略定义

#### 2.2.1 策略1：EMA25回归卖出（MVP默认）

**触发条件**：
```
买入后的任意K线满足：low <= EMA25 <= high
```

**卖出价格**：
```
sell_price = EMA25（当根K线的EMA25值）
```

**逻辑说明**：
- 买入后，从下一根K线开始检查
- 当K线的价格区间[low, high]包含EMA25时触发卖出
- 使用第一根满足条件的K线
- 不带止损策略（无最大持仓时间限制）

**计算示例**：
```python
# 买入时刻 t=100
buy_price = 50000  # close价格

# 检查 t=101, 102, 103...
# 假设 t=105 时：
#   low = 50800
#   high = 51200
#   EMA25 = 51000
# 满足 low(50800) <= EMA25(51000) <= high(51200)
# 触发卖出，sell_price = 51000
```

#### 2.2.2 未来可扩展策略（P1推迟）

| 策略 | 触发条件 | MVP状态 |
|------|----------|---------|
| EMA25回归 | K线包含EMA25 | ✅ MVP |
| 止盈止损 | 收益率达到±X% | ❌ P1 |
| 时间止损 | 持仓超过N根K线 | ❌ P1 |
| 趋势反转 | β由负转正 | ❌ P1 |

**策略组合机制**（预留）：
- 多策略并存
- 任一策略触发即卖出
- 记录触发的策略ID

---

### 2.3 持仓状态追踪

#### 2.3.1 订单生命周期
```
[买入信号触发] → [创建订单(holding)] → [检查卖出条件] → [卖出触发] → [订单完成(sold)]
                        ↓                      ↓
                   持续检查直到            记录盈亏
                   数据结束或卖出
```

#### 2.3.2 未平仓订单处理
**场景**：买入后到当前时间，未触发卖出条件

**处理方式**：
- 状态保持 `holding`
- 计算当前浮动盈亏（使用最新close价格）
- UI标记为"持仓中"

---

### 2.4 盈亏统计

#### 2.4.1 单笔订单盈亏
```python
# 已卖出订单
profit_usdt = (sell_price - buy_price) * buy_quantity
profit_rate = (sell_price - buy_price) / buy_price * 100

# 持仓中订单（浮动盈亏）
current_price = latest_close
floating_profit_usdt = (current_price - buy_price) * buy_quantity
floating_profit_rate = (current_price - buy_price) / buy_price * 100
```

#### 2.4.2 汇总统计
```python
class OrderStatistics:
    # 订单数量
    total_orders: int           # 总订单数
    sold_orders: int            # 已卖出订单数
    holding_orders: int         # 持仓中订单数

    # 胜率统计
    win_orders: int             # 盈利订单数（profit > 0）
    lose_orders: int            # 亏损订单数（profit <= 0）
    win_rate: Decimal           # 胜率 = win_orders / sold_orders * 100

    # 收益统计
    total_invested: Decimal     # 总投入（买入金额之和）
    total_profit: Decimal       # 总盈亏（已卖出订单）
    total_profit_rate: Decimal  # 总收益率

    # 浮动盈亏
    floating_profit: Decimal    # 持仓浮动盈亏

    # 平均指标
    avg_profit_rate: Decimal    # 平均单笔收益率
    avg_holding_periods: int    # 平均持仓K线数
```

---

### 2.5 操作日志

#### 2.5.1 功能概述
提供按时间展示所有买入/卖出事件的操作日志面板，帮助用户追踪完整的交易历史。

#### 2.5.2 数据结构
```python
@dataclass
class TradeEvent:
    """交易事件（操作日志）"""
    event_type: str           # "buy" | "sell"
    timestamp: int            # 事件时间戳
    price: Decimal            # 价格
    quantity: Decimal         # 数量
    order_id: str             # 关联订单ID
    amount_usdt: Decimal      # 金额（USDT）
    profit_usdt: Optional[Decimal]    # 盈亏（仅卖出事件）
    profit_rate: Optional[Decimal]    # 盈亏率（仅卖出事件）
```

#### 2.5.3 日志列表
- **排序方式**：按时间倒序（最新在最上方）
- **事件类型区分**：
  - 买入事件：绿色圆点 🟢
  - 卖出事件：红色圆点 🔴
- **显示信息**：
  - 买入：时间、价格、数量
  - 卖出：时间、价格、数量、盈亏金额、盈亏率

#### 2.5.4 UI布局
```
┌──────────────────────────────────────────────────────────────────────┐
│ 📋 操作日志                                           [全部|买入|卖出] │
├──────────────────────────────────────────────────────────────────────┤
│ 🔴 2026-01-06 12:00 | 卖出 | $2,350.00 | 0.0425 ETH | +$2.15 (+2.15%)│
│ 🟢 2026-01-05 08:00 | 买入 | $2,300.50 | 0.0435 ETH | 100 USDT       │
│ 🔴 2026-01-04 16:00 | 卖出 | $2,280.00 | 0.0438 ETH | -$0.88 (-0.88%)│
│ 🟢 2026-01-03 04:00 | 买入 | $2,292.00 | 0.0436 ETH | 100 USDT       │
│ ...                                                                   │
└──────────────────────────────────────────────────────────────────────┘
```

#### 2.5.5 筛选功能
- **全部**：显示所有买入和卖出事件
- **买入**：仅显示买入事件
- **卖出**：仅显示卖出事件

---

### 2.6 可视化设计

#### 2.6.1 统计面板（页面顶部）
**位置**：详情页顶部，紧接导航栏下方

**布局**：
```
┌─────────────────────────────────────────────────────────────────────────┐
│ 📊 策略表现统计                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│  总订单    已卖出    持仓中    胜率      总收益      浮动盈亏             │
│   25        22        3      68.2%    +$156.32     +$12.45              │
│                               ↑绿       ↑绿         ↑绿                 │
└─────────────────────────────────────────────────────────────────────────┘
```

**样式**：
- 使用Bootstrap Card
- 关键指标高亮（盈利绿色/亏损红色）
- 响应式布局（移动端堆叠显示）

#### 2.5.2 买入点标记扩展
**现有**：绿色向上箭头 ↑（迭代011）

**扩展**：
- 已卖出订单：绿色箭头保持
- 持仓中订单：箭头上方添加持仓标记（小圆点）

#### 2.5.3 卖出点标记
**新增**：在卖出K线上标记

**样式**：
- 图标：红色向下箭头 ↓
- 颜色：`#dc3545`（Bootstrap danger色）
- 位置：K线上方（aboveBar）

#### 2.5.4 订单连接线
**显示**：从买入点到卖出点的虚线连接

**样式**：
- 盈利订单：绿色虚线
- 亏损订单：红色虚线
- 持仓订单：灰色虚线延伸到当前

**MVP处理**：连接线为P1功能，MVP阶段不实现

#### 2.5.5 悬浮Card扩展
**扩展迭代011的买入信号Card**：

```
┌─────────────────────────────────────────┐
│ 📊 买入信号详情                          │
├─────────────────────────────────────────┤
│ 🕐 触发时间: 2026-01-06 16:00:00        │
│ 💰 买入价格: $49,876.54                 │
│ 📦 买入金额: 100 USDT                   │
│ 📊 买入数量: 0.002005                   │
├─────────────────────────────────────────┤
│ ✅ 触发策略: 策略1: EMA斜率未来预测      │
├─────────────────────────────────────────┤
│ 📈 订单状态: 已卖出                      │ ← 新增
│ 🕐 卖出时间: 2026-01-08 08:00:00        │ ← 新增
│ 💵 卖出价格: $51,234.00 (EMA25)         │ ← 新增
│ 📊 持仓周期: 10根K线                     │ ← 新增
│ 💹 盈亏: +$2.72 (+2.72%)               │ ← 新增
└─────────────────────────────────────────┘
```

---

### 2.6 技术实现

#### 2.6.1 系统架构
```
┌─────────────────────────────────────────────────────────────────┐
│                  ddps_z 模块（增量扩展）                          │
├─────────────────────────────────────────────────────────────────┤
│  calculators/                                                   │
│  ├─ buy_signal_calculator.py   (✅ 复用，不修改)                 │
│  └─ order_tracker.py           (🆕 新增：订单追踪计算器)          │
├─────────────────────────────────────────────────────────────────┤
│  services/                                                      │
│  └─ chart_data_service.py      (📝 扩展：添加orders字段)         │
├─────────────────────────────────────────────────────────────────┤
│  templates/                                                     │
│  └─ detail.html                (📝 扩展：统计面板 + 卖出标记)     │
└─────────────────────────────────────────────────────────────────┘

图例：✅ 复用（不修改） | 🆕 新增 | 📝 扩展（向后兼容）
```

#### 2.6.2 API 扩展

**GET /ddps-z/api/chart/** 响应扩展：
```json
{
  "chart": {
    // ✅ 现有字段保持不变
    "candles": [...],
    "ema": [...],
    "buy_signals": [...],

    // 🆕 新增 orders 字段
    "orders": [
      {
        "id": "order_001",
        "buy_timestamp": 1736078400000,
        "buy_price": 49876.54,
        "buy_amount_usdt": 100,
        "buy_quantity": 0.002005,
        "buy_strategy_id": "strategy_1",
        "sell_timestamp": 1736236800000,
        "sell_price": 51234.00,
        "sell_strategy_id": "ema25_reversion",
        "status": "sold",
        "profit_usdt": 2.72,
        "profit_rate": 2.72,
        "holding_periods": 10
      },
      {
        "id": "order_002",
        "buy_timestamp": 1736323200000,
        "buy_price": 48500.00,
        "buy_amount_usdt": 100,
        "buy_quantity": 0.002062,
        "buy_strategy_id": "strategy_2",
        "sell_timestamp": null,
        "sell_price": null,
        "sell_strategy_id": null,
        "status": "holding",
        "profit_usdt": null,
        "profit_rate": null,
        "holding_periods": null,
        "floating_profit_usdt": 1.23,
        "floating_profit_rate": 1.23
      }
    ],

    // 🆕 新增 order_statistics 字段
    "order_statistics": {
      "total_orders": 25,
      "sold_orders": 22,
      "holding_orders": 3,
      "win_orders": 15,
      "lose_orders": 7,
      "win_rate": 68.2,
      "total_invested": 2500,
      "total_profit": 156.32,
      "total_profit_rate": 6.25,
      "floating_profit": 12.45,
      "avg_profit_rate": 7.1,
      "avg_holding_periods": 8
    },

    // 🆕 新增 trade_events 字段（操作日志）
    "trade_events": [
      {
        "event_type": "sell",
        "timestamp": 1736164800000,
        "price": 2350.00,
        "quantity": 0.0425,
        "order_id": "order_001",
        "amount_usdt": 99.88,
        "profit_usdt": 2.15,
        "profit_rate": 2.15
      },
      {
        "event_type": "buy",
        "timestamp": 1736078400000,
        "price": 2300.50,
        "quantity": 0.0435,
        "order_id": "order_001",
        "amount_usdt": 100,
        "profit_usdt": null,
        "profit_rate": null
      }
    ]
  }
}
```

#### 2.6.3 前端扩展

**统计面板组件**：
```html
<div class="card mb-3" id="statistics-panel">
    <div class="card-body">
        <h6 class="card-title">📊 策略表现统计</h6>
        <div class="row text-center">
            <div class="col-2">
                <small class="text-muted">总订单</small>
                <div class="h5" id="stat-total-orders">-</div>
            </div>
            <div class="col-2">
                <small class="text-muted">已卖出</small>
                <div class="h5" id="stat-sold-orders">-</div>
            </div>
            <div class="col-2">
                <small class="text-muted">持仓中</small>
                <div class="h5" id="stat-holding-orders">-</div>
            </div>
            <div class="col-2">
                <small class="text-muted">胜率</small>
                <div class="h5" id="stat-win-rate">-</div>
            </div>
            <div class="col-2">
                <small class="text-muted">总收益</small>
                <div class="h5" id="stat-total-profit">-</div>
            </div>
            <div class="col-2">
                <small class="text-muted">浮动盈亏</small>
                <div class="h5" id="stat-floating-profit">-</div>
            </div>
        </div>
    </div>
</div>
```

**卖出点标记**：
```javascript
// 卖出点标记（与买入点一起设置）
const sellMarkers = orders
    .filter(o => o.status === 'sold')
    .map(order => ({
        time: order.sell_timestamp / 1000,
        position: 'aboveBar',
        color: '#dc3545',
        shape: 'arrowDown',
        text: 'S',  // Sell
        size: 1
    }));

// 合并买入和卖出标记
const allMarkers = [...buyMarkers, ...sellMarkers];
candleSeries.setMarkers(allMarkers);
```

---

## 第三部分：AI分析与建议

### 3.1 MVP功能点清单（已确认）

#### 📊 **核心功能（P0 - 必须实现）**

- **[P0] 订单数据结构设计**
  - VirtualOrder类定义
  - 支持买入/卖出/持仓状态
  - 包含盈亏计算字段

- **[P0] OrderTracker计算器**
  - 接收买入信号，创建虚拟订单
  - 固定买入金额：100 USDT
  - 计算买入数量：amount / price

- **[P0] EMA25回归卖出策略**
  - 检查条件：low <= EMA25 <= high
  - 卖出价格：EMA25值
  - 从买入后下一根K线开始检查

- **[P0] 订单状态追踪**
  - holding：持仓中（未触发卖出）
  - sold：已卖出

- **[P0] 单笔订单盈亏计算**
  - 盈亏金额：(sell_price - buy_price) * quantity
  - 盈亏比例：(sell_price - buy_price) / buy_price * 100
  - 持仓周期：卖出时间 - 买入时间（K线数）

- **[P0] 持仓订单浮动盈亏**
  - 使用最新close计算浮动盈亏
  - 标记状态为"持仓中"

- **[P0] 汇总统计计算**
  - 总订单数、已卖出、持仓中
  - 胜率计算（盈利订单 / 已卖出订单）
  - 总收益、浮动盈亏
  - 平均收益率、平均持仓周期

- **[P0] API扩展**
  - orders字段：订单列表
  - order_statistics字段：汇总统计

- **[P0] 统计面板UI**
  - Bootstrap Card布局
  - 六项关键指标展示
  - 盈亏颜色高亮

- **[P0] 卖出点标记**
  - 红色向下箭头
  - 位置：aboveBar
  - 与买入标记合并渲染

- **[P0] 悬浮Card扩展**
  - 显示订单状态
  - 显示卖出信息（如已卖出）
  - 显示盈亏详情

---

#### 🎨 **增强功能（P1 - 可推迟）**

- **[P1] 多卖出策略支持**
  - 止盈止损策略
  - 时间止损策略
  - 策略组合机制

- **[P1] 买入金额策略可配置**
  - 比例金额
  - 动态金额

- **[P1] 订单连接线可视化**
  - 买入点到卖出点连线
  - 盈亏颜色区分

- **[P1] 订单列表面板**
  - 详细订单表格
  - 支持排序/筛选

- **[P1] 数据持久化**
  - 订单存储到数据库
  - 支持历史查询

---

### 3.2 已解决的决策点

#### ✅ 决策点1：买入金额策略
**采用方案**：固定100 USDT
- 每次买入信号触发，固定投入100 USDT
- 理由：MVP阶段最简单，便于计算和验证

#### ✅ 决策点2：卖出策略选择
**采用方案**：EMA25回归卖出
- 触发条件：K线[low, high]包含EMA25
- 卖出价格：EMA25值
- 理由：与现有DDPS-Z系统紧密结合，逻辑简单清晰

#### ✅ 决策点3：未平仓订单处理
**采用方案**：显示浮动盈亏
- 使用最新close计算浮动盈亏
- UI标记为"持仓中"
- 理由：提供实时信息，不遗漏任何订单

#### ✅ 决策点4：订单数据存储
**采用方案**：纯内存计算，不持久化
- 每次加载页面重新计算所有订单
- 理由：与现有DDPS-Z架构一致，MVP阶段无需数据库

#### ✅ 决策点5：多买入策略订单区分
**采用方案**：记录buy_strategy_id
- 每个订单记录触发的买入策略ID
- 统计时可按策略分组
- 理由：支持未来按策略分析

---

### 3.3 验收标准

#### 功能验收
| 功能点 | 验收标准 |
|--------|----------|
| 订单创建 | 买入信号触发时自动创建订单，金额固定100U |
| EMA25卖出 | 正确检测K线包含EMA25并触发卖出 |
| 盈亏计算 | 盈亏金额和比例计算准确 |
| 统计面板 | 所有统计指标正确计算并显示 |
| 卖出标记 | 正确在卖出K线上显示红色箭头 |
| 悬浮Card | 显示完整订单信息 |

#### 性能指标
| 指标 | 目标值 |
|------|--------|
| 订单计算延迟 | < 100ms（500个订单） |
| 页面加载时间 | < 1s |
| 统计面板渲染 | < 10ms |

---

### 3.4 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 订单数量过多 | 计算和渲染性能下降 | 1. 限制时间范围；2. 分页加载 |
| EMA25卖出信号过于敏感 | 频繁交易导致统计失真 | 1. 观察实际数据；2. 预留策略扩展 |
| 浮动盈亏计算延迟 | 数据不实时 | 使用最后一根K线close |

---

### 3.5 排期建议

**总计工作量**: 约1.5天

| 阶段 | 任务 | 工作量 |
|------|------|--------|
| 后端开发 | OrderTracker计算器 + API扩展 | 0.5天 |
| 前端开发 | 统计面板 + 卖出标记 + Card扩展 | 0.5天 |
| 测试验证 | 订单计算验证 + 回归测试 | 0.5天 |

---

## 附录

### A. 公式速查

| 名称 | 公式 |
|------|------|
| 买入数量 | quantity = 100 / buy_price |
| 盈亏金额 | profit = (sell_price - buy_price) × quantity |
| 盈亏比例 | rate = (sell_price - buy_price) / buy_price × 100 |
| 胜率 | win_rate = win_orders / sold_orders × 100 |
| 总收益率 | total_rate = total_profit / total_invested × 100 |
| EMA25卖出条件 | low ≤ EMA25 ≤ high |

### B. 卖出策略详细逻辑

```python
def check_ema25_sell(order: VirtualOrder, klines: List[KLine], ema_values: List[float]) -> bool:
    """
    检查EMA25回归卖出条件

    Args:
        order: 待检查的订单
        klines: K线数据
        ema_values: EMA25序列

    Returns:
        是否触发卖出
    """
    buy_index = find_kline_index(klines, order.buy_timestamp)

    # 从买入后的下一根K线开始检查
    for i in range(buy_index + 1, len(klines)):
        kline = klines[i]
        ema25 = ema_values[i]

        # 检查K线是否包含EMA25
        if kline.low <= ema25 <= kline.high:
            order.sell_timestamp = kline.close_time
            order.sell_price = ema25
            order.sell_strategy_id = "ema25_reversion"
            order.status = "sold"
            order.holding_periods = i - buy_index
            return True

    return False  # 未触发卖出，保持holding状态
```

### C. 数据依赖

订单追踪计算依赖的现有数据：
- ✅ 买入信号列表（buy_signal_calculator.py）
- ✅ EMA25序列（ema_calculator.py）
- ✅ K线OHLC数据（chart_data_service.py）

### D. 技术栈

| 层级 | 技术 |
|------|------|
| 后端计算 | Python + Decimal精度计算 |
| API | Django REST Framework |
| 前端渲染 | LightweightCharts + Bootstrap |
| 数据格式 | JSON |

---

**文档状态**: ✅ MVP需求定稿完成
**Gate 1检查**: ✅ 已通过
**下一阶段**: 技术实现（P3-P4）
