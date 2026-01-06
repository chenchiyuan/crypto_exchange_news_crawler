# 功能点清单: 买卖订单追踪系统 (Buy-Sell Order Tracking)

**迭代编号**: 012
**文档版本**: 1.0
**创建日期**: 2026-01-06
**状态**: MVP功能已确认

---

## MVP功能点（P0 - 必须实现）

### 后端功能

| 编号 | 功能点 | 描述 | 验收标准 |
|------|--------|------|----------|
| BE-001 | VirtualOrder数据结构 | 定义虚拟订单数据类 | 包含所有必需字段：买入/卖出信息、状态、盈亏 |
| BE-002 | OrderTracker计算器 | 核心订单追踪逻辑类 | 能够接收买入信号并创建订单 |
| BE-003 | 固定买入金额逻辑 | 每次买入固定100 USDT | buy_quantity = 100 / buy_price |
| BE-004 | EMA25回归卖出检测 | 检查K线是否包含EMA25 | low <= EMA25 <= high 时触发 |
| BE-005 | 卖出价格计算 | 使用EMA25作为卖出价格 | sell_price = EMA25值 |
| BE-006 | 订单状态管理 | holding/sold状态切换 | 正确追踪订单生命周期 |
| BE-007 | 单笔盈亏计算 | 计算每笔订单盈亏 | profit = (sell - buy) × quantity |
| BE-008 | 浮动盈亏计算 | 持仓订单浮动盈亏 | 使用最新close计算 |
| BE-009 | 持仓周期计算 | 计算持仓K线数 | 卖出索引 - 买入索引 |
| BE-010 | 汇总统计计算 | OrderStatistics类 | 包含所有统计指标 |
| BE-011 | 胜率计算 | win_orders / sold_orders | 正确统计盈利/亏损订单 |
| BE-012 | API响应扩展 | 添加orders和statistics字段 | 向后兼容现有API |
| BE-013 | TradeEvent数据结构 | 定义交易事件数据类 | 包含event_type、timestamp、price、profit |
| BE-014 | 操作日志生成 | 从订单生成买卖事件列表 | 按时间倒序排列 |
| BE-015 | trade_events字段 | API返回交易事件列表 | 支持前端操作日志显示 |

### 前端功能

| 编号 | 功能点 | 描述 | 验收标准 |
|------|--------|------|----------|
| FE-001 | 统计面板组件 | 页面顶部统计卡片 | 显示6项关键指标 |
| FE-002 | 统计数据渲染 | 渲染API返回的统计数据 | 数值正确格式化 |
| FE-003 | 盈亏颜色高亮 | 盈利绿色/亏损红色 | 正确应用颜色 |
| FE-004 | 卖出点标记 | 红色向下箭头 | 位置正确，颜色#dc3545 |
| FE-005 | 标记合并渲染 | 买入+卖出标记一起设置 | 不覆盖现有买入标记 |
| FE-006 | 悬浮Card扩展 | 显示订单详细信息 | 包含状态、盈亏、持仓周期 |
| FE-007 | 持仓订单标识 | 区分持仓中和已卖出 | 持仓显示"持仓中"状态 |
| FE-008 | 响应式布局 | 统计面板移动端适配 | 小屏堆叠显示 |
| FE-009 | 操作日志面板 | 页面底部操作日志区域 | 显示买卖事件列表 |
| FE-010 | 日志事件渲染 | 按时间倒序渲染事件 | 区分买入(绿)/卖出(红) |
| FE-011 | 日志筛选按钮 | 全部/买入/卖出筛选 | 正确过滤事件类型 |
| FE-012 | 日志事件详情 | 显示价格、数量、盈亏 | 格式化数值显示 |

---

## 功能点详细说明

### BE-001: VirtualOrder数据结构

```python
@dataclass
class VirtualOrder:
    # 订单标识
    id: str

    # 买入信息
    buy_timestamp: int
    buy_price: Decimal
    buy_amount_usdt: Decimal  # 固定100
    buy_quantity: Decimal
    buy_strategy_id: str

    # 卖出信息
    sell_timestamp: Optional[int]
    sell_price: Optional[Decimal]
    sell_strategy_id: Optional[str]

    # 状态和盈亏
    status: str  # "holding" | "sold"
    profit_usdt: Optional[Decimal]
    profit_rate: Optional[Decimal]
    holding_periods: Optional[int]

    # 浮动盈亏（仅holding状态）
    floating_profit_usdt: Optional[Decimal]
    floating_profit_rate: Optional[Decimal]
```

### BE-004: EMA25回归卖出检测

```python
def check_sell_condition(kline: KLine, ema25: Decimal) -> bool:
    """
    检查EMA25回归卖出条件

    条件：K线的low-high区间包含EMA25值
    """
    return kline.low <= ema25 <= kline.high
```

### BE-010: 汇总统计计算

```python
@dataclass
class OrderStatistics:
    # 订单数量
    total_orders: int
    sold_orders: int
    holding_orders: int

    # 胜率
    win_orders: int
    lose_orders: int
    win_rate: Decimal

    # 收益
    total_invested: Decimal
    total_profit: Decimal
    total_profit_rate: Decimal
    floating_profit: Decimal

    # 平均指标
    avg_profit_rate: Decimal
    avg_holding_periods: int
```

### FE-001: 统计面板组件

```html
<div class="card mb-3" id="statistics-panel">
    <div class="card-body py-2">
        <div class="row text-center g-2">
            <div class="col-4 col-md-2">
                <small class="text-muted d-block">总订单</small>
                <span class="fw-bold" id="stat-total">-</span>
            </div>
            <div class="col-4 col-md-2">
                <small class="text-muted d-block">已卖出</small>
                <span class="fw-bold" id="stat-sold">-</span>
            </div>
            <div class="col-4 col-md-2">
                <small class="text-muted d-block">持仓中</small>
                <span class="fw-bold" id="stat-holding">-</span>
            </div>
            <div class="col-4 col-md-2">
                <small class="text-muted d-block">胜率</small>
                <span class="fw-bold" id="stat-winrate">-</span>
            </div>
            <div class="col-4 col-md-2">
                <small class="text-muted d-block">总收益</small>
                <span class="fw-bold" id="stat-profit">-</span>
            </div>
            <div class="col-4 col-md-2">
                <small class="text-muted d-block">浮动盈亏</small>
                <span class="fw-bold" id="stat-floating">-</span>
            </div>
        </div>
    </div>
</div>
```

### FE-004: 卖出点标记

```javascript
function renderSellMarkers(orders) {
    const sellMarkers = orders
        .filter(order => order.status === 'sold')
        .map(order => ({
            time: order.sell_timestamp / 1000,
            position: 'aboveBar',
            color: '#dc3545',
            shape: 'arrowDown',
            text: 'S',
            size: 1
        }));

    return sellMarkers;
}
```

### BE-013: TradeEvent数据结构

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
    profit_usdt: Optional[Decimal]    # 盈亏（仅卖出）
    profit_rate: Optional[Decimal]    # 盈亏率（仅卖出）
```

### FE-009: 操作日志面板

```html
<div class="card mb-3" id="trade-log-panel">
    <div class="card-header d-flex justify-content-between align-items-center">
        <span>📋 操作日志</span>
        <div class="btn-group btn-group-sm">
            <button class="btn btn-outline-secondary active" data-log-filter="all">全部</button>
            <button class="btn btn-outline-success" data-log-filter="buy">买入</button>
            <button class="btn btn-outline-danger" data-log-filter="sell">卖出</button>
        </div>
    </div>
    <div class="card-body p-0">
        <div class="list-group list-group-flush" id="trade-log-list">
            <!-- 动态渲染事件列表 -->
        </div>
    </div>
</div>
```

### FE-010: 日志事件渲染

```javascript
function renderTradeEvents(events, filter = 'all') {
    const filtered = events.filter(e =>
        filter === 'all' || e.event_type === filter
    );

    return filtered.map(e => {
        const isBuy = e.event_type === 'buy';
        const icon = isBuy ? '🟢' : '🔴';
        const typeText = isBuy ? '买入' : '卖出';
        const profitText = !isBuy && e.profit_usdt
            ? `${e.profit_usdt > 0 ? '+' : ''}$${e.profit_usdt.toFixed(2)} (${e.profit_rate.toFixed(2)}%)`
            : `${e.amount_usdt} USDT`;

        return `
            <div class="list-group-item">
                ${icon} ${formatTime(e.timestamp)} | ${typeText} |
                $${e.price.toFixed(2)} | ${e.quantity.toFixed(4)} | ${profitText}
            </div>
        `;
    }).join('');
}
```

---

## P1功能点（可推迟）

| 编号 | 功能点 | 描述 | 推迟原因 |
|------|--------|------|----------|
| P1-001 | 止盈止损策略 | 收益率达到±X%触发 | MVP先验证EMA25策略 |
| P1-002 | 时间止损策略 | 持仓超N根K线触发 | 复杂度增加 |
| P1-003 | 买入金额可配置 | 支持比例/动态金额 | MVP固定100U足够 |
| P1-004 | 订单连接线 | 买卖点之间的连线 | 视觉效果，非核心 |
| P1-005 | 订单列表面板 | 详细订单表格 | 统计面板已满足需求 |
| P1-006 | 数据持久化 | 订单存储到数据库 | MVP纯内存计算 |
| P1-007 | 按策略分组统计 | 策略1/策略2分别统计 | MVP统一统计 |

---

## 依赖关系

```
┌─────────────────────────────────────────────────────────────────┐
│                        迭代 012 依赖图                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────┐    ┌───────────────────┐                    │
│  │ 迭代 011      │    │ 现有 DDPS-Z       │                    │
│  │ BuySignal     │───▶│ EMACalculator     │                    │
│  │ Calculator    │    │ ChartDataService  │                    │
│  └───────┬───────┘    └─────────┬─────────┘                    │
│          │                      │                               │
│          ▼                      ▼                               │
│  ┌───────────────────────────────────────┐                     │
│  │          迭代 012                      │                     │
│  │         OrderTracker                  │                     │
│  │                                        │                     │
│  │  • 接收 buy_signals                   │                     │
│  │  • 使用 ema_values 检测卖出            │                     │
│  │  • 输出 orders + statistics           │                     │
│  └───────────────────────────────────────┘                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `ddps_z/calculators/order_tracker.py` | 新增 | 订单追踪计算器 |
| `ddps_z/calculators/__init__.py` | 修改 | 导出OrderTracker |
| `ddps_z/services/chart_data_service.py` | 修改 | 添加orders计算逻辑 |
| `ddps_z/templates/ddps_z/detail.html` | 修改 | 统计面板+卖出标记 |

---

**文档状态**: ✅ 功能点清单完成
**总P0功能点**: 27个（后端15 + 前端12）
**预计工作量**: 2天
