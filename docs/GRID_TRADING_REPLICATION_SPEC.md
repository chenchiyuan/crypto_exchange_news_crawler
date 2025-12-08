# 核心功能复刻技术规格书
## ritmex-bot 网格交易系统逆向工程分析

**项目源**: ritmex-bot (TypeScript/Bun)
**目标平台**: Django/Python
**分析日期**: 2025-12-05
**复刻需求**: 自动网格交易、交易所对接、统计功能、安全容错机制

---

## Step 1: 全局透视 (System Audit)

### 1.1 业务目标
**一句话总结**: 基于 Bun 的多交易所永续合约量化终端，支持趋势跟随、做市、Guardian 防守和**基础网格策略**，通过 WebSocket + REST 实现实时行情订阅、自动恢复与风险控制。

### 1.2 核心架构

**架构模式**: 分层模块化架构 (Layered Modular Architecture)

```
┌─────────────────────────────────────────────────┐
│          CLI / UI Layer (Ink React)             │  ← 用户交互
├─────────────────────────────────────────────────┤
│       Strategy Layer (Engine Pattern)           │  ← 策略引擎
│  - TrendEngine                                   │
│  - MakerEngine                                   │
│  - GridEngine  ★核心                             │
│  - GuardianEngine                                │
│  - BasisArbEngine                                │
├─────────────────────────────────────────────────┤
│    Exchange Abstraction (Adapter Pattern)        │  ← 交易所适配
│  - ExchangeAdapter Interface                     │
│  - Order Router (策略模式)                       │
│  - AsterAdapter / GRVT / Lighter / Backpack...   │
├─────────────────────────────────────────────────┤
│         Core Utilities & Config                  │  ← 基础设施
│  - Math Utils (price/qty rounding)               │
│  - Trade Log (ring buffer)                       │
│  - Error Handling                                │
└─────────────────────────────────────────────────┘
```

**设计模式识别**:
- **Adapter Pattern**: 交易所适配器统一接口
- **Observer Pattern**: WebSocket 事件订阅 (watchAccount, watchOrders, watchDepth, watchTicker)
- **Strategy Pattern**: 订单路由根据交易所类型动态分发
- **Template Method**: 策略引擎通用生命周期 (bootstrap → tick → stop)
- **Ring Buffer**: TradeLog 实现固定容量日志队列

### 1.3 关键入口

**主入口**: `/index.ts` → `/src/index.tsx`

**启动流程**:
```typescript
// src/index.tsx:1-34
1. setupGlobalErrorHandlers()        // 全局异常捕获
2. parseCliArgs()                    // 解析命令行参数
3. if (options.exchange) → 覆盖环境变量
4. if (options.strategy) → startStrategy()  // 静默启动
   else → render(<App />)            // Ink CLI 交互式启动
```

**配置加载**:
- **文件**: `src/config.ts:1-185`
- **机制**:
  - 从 `.env` 读取环境变量
  - 每个策略有独立配置结构 (TradingConfig, GridConfig, MakerConfig...)
  - 使用 `parseNumber()` / `parseBoolean()` 进行类型安全解析
  - 交易所特定符号通过 `SYMBOL_PRIORITY_BY_EXCHANGE` 优先级链解析

---

## Step 2: 核心映射 (Target Mapping)

### 2.1 功能需求映射

| 需求 | 源文件路径 | 核心类/函数 | 依赖模块 |
|------|-----------|------------|---------|
| **自动网格功能** | `src/strategy/grid-engine.ts` | `GridEngine` 类 | ExchangeAdapter, GridConfig, order-router |
| **交易所对接** | `src/exchanges/adapter.ts`<br>`src/exchanges/order-router.ts`<br>`src/exchanges/aster-adapter.ts` | `ExchangeAdapter` 接口<br>`routeLimitOrder()` 函数<br>`AsterAdapter` 实现 | ccxt (可选), WebSocket 库 |
| **网格统计** | `src/logging/trade-log.ts`<br>`src/strategy/grid-engine.ts:728-758` | `createTradeLog()`<br>`getSnapshot()` 方法 | Ring Buffer 实现 |
| **安全/容错** | `src/strategy/common/subscriptions.ts`<br>`src/strategy/grid-engine.ts:324-358` | `safeSubscribe()`<br>`shouldStop()` + `stopAndFlatten()` | Error handling, 止损逻辑 |

### 2.2 关键文件定位 (Top 5)

#### ⭐ 1. `src/strategy/grid-engine.ts` (760 行)
**职责**: 网格策略核心引擎
- **核心类**: `GridEngine`
- **关键方法**:
  - `buildGrid(referencePrice)`: 初始化等比网格价位 (292-317)
  - `buildDesiredOrders()`: 计算理想挂单列表 (381-425)
  - `syncOpenOrders()`: 订单同步与补单逻辑 (435-486)
  - `shouldStop()`: 止损条件判断 (324-337)
  - `stopAndFlatten()`: 紧急平仓 (339-358)

#### 2. `src/exchanges/adapter.ts` (52 行)
**职责**: 交易所适配器接口定义
- **核心接口**: `ExchangeAdapter`
- **必须实现方法**:
  ```typescript
  watchAccount(cb: AccountListener)      // 账户快照订阅
  watchOrders(cb: OrderListener)         // 订单状态订阅
  watchDepth(symbol, cb)                 // 盘口深度订阅
  watchTicker(symbol, cb)                // 行情推送订阅
  createOrder(params)                    // 下单
  cancelOrder/cancelOrders/cancelAllOrders  // 撤单
  ```

#### 3. `src/exchanges/order-router.ts` (119 行)
**职责**: 订单路由器 - 根据交易所类型分发订单创建逻辑
- **核心函数**:
  - `routeLimitOrder(intent)`: 限价单路由 (95-97)
  - `routeMarketOrder(intent)`: 市价单路由 (99-101)
  - `routeStopOrder(intent)`: 止损单路由 (103-105)
- **策略模式实现**: `handlerMap` 映射表 (27-63)

#### 4. `src/config.ts` (185 行)
**职责**: 配置管理 - 从环境变量加载策略参数
- **网格配置结构**:
  ```typescript
  GridConfig {
    symbol: string              // 交易对
    tradeAmount: number         // 单笔数量
    refreshIntervalMs: number   // 轮询间隔
    priceTick: number          // 价格精度
    qtyStep: number            // 数量精度
    levelsPerSide: number      // 单侧网格数
    spacingPct: number         // 网格间距百分比
    stopLossBufferPct: number  // 止损缓冲区
    maxPositionSize: number    // 最大持仓
  }
  ```

#### 5. `src/logging/trade-log.ts` (推测路径)
**职责**: 交易日志环形缓冲区
- **核心功能**:
  - Ring Buffer 实现固定容量 FIFO 队列
  - 支持日志类型: `info`, `warn`, `error`, `order`, `fill`
  - 通过 `push(type, detail)` 和 `all()` 访问

### 2.3 依赖分析

**强依赖模块**:
1. **WebSocket 库**: 用于实时数据推送
   - 源码使用 Bun 内置 WebSocket 或第三方库
   - Python 可用 `websockets` 或 `python-binance` 内置

2. **数学工具**: 价格/数量精度处理
   - `roundDownToTick()`: 价格向下取整到 tick
   - `roundQtyDownToStep()`: 数量向下取整到 step
   - `formatPriceToString()`: 格式化为固定小数位
   - **Python 替代**: `Decimal` 类型 + 自定义舍入函数

3. **事件发射器**: 策略状态通知
   - 源码: `StrategyEventEmitter` (EventEmitter pattern)
   - **Python 替代**: Django Signals 或 `asyncio.Event`

**可选依赖**:
- **CCXT 库**: 部分交易所使用 CCXT 适配器 (未强制)
- **Ink UI**: CLI 交互界面 (可用 `rich` 或 Django Admin 替代)

---

## Step 3: 逻辑解剖 (Logic Anatomy)

### 3.1 网格交易完整执行链路 (Happy Path)

#### Input: 用户配置 + 市场数据流

```python
# 配置输入
{
  "symbol": "BTCUSDT",
  "tradeAmount": 0.001,          # 单笔开仓数量
  "levelsPerSide": 15,           # 单侧网格数 (总共 30 条)
  "spacingPct": 0.00025,         # 网格间距 0.025%
  "maxPositionSize": 0.01,       # 最大净持仓 0.01 BTC
  "stopLossBufferPct": 0.003,    # 止损缓冲 0.3%
  "priceTick": 0.1,              # 价格精度
  "qtyStep": 0.001               # 数量精度
}

# WebSocket 数据流
- Account Snapshot: { positions: [...], assets: [...] }
- Orders Feed: [ {orderId, status, price, qty, ...}, ... ]
- Depth: { bids: [[price, qty], ...], asks: [...] }
- Ticker: { lastPrice, markPrice, ... }
```

#### Process: 核心执行流程

##### **Phase 1: 初始化 (bootstrap)**
```typescript
// src/strategy/grid-engine.ts:144-215
constructor(config, exchange) {
  this.tradeLog = createTradeLog(maxLogEntries)
  this.priceDecimals = decimalsOf(config.priceTick)

  // 订阅 4 个 WebSocket 数据流
  safeSubscribe(exchange.watchAccount, (snapshot) => {
    this.accountSnapshot = snapshot
    this.position = getPosition(snapshot, symbol)  // 提取持仓
    this.feedStatus.account = true
  })

  safeSubscribe(exchange.watchOrders, (orders) => {
    this.syncOrdersFromFeed(orders)  // 同步订单状态
    this.feedStatus.orders = true
  })

  safeSubscribe(exchange.watchDepth, (depth) => {
    this.depthSnapshot = depth
  })

  safeSubscribe(exchange.watchTicker, (ticker) => {
    this.lastPrice = getMidOrLast(depth, ticker)  // 获取参考价
  })
}
```

**关键点**:
- 使用 `safeSubscribe()` 包装所有订阅,确保异常不会导致策略崩溃
- 通过 `feedStatus` 追踪数据流就绪状态

##### **Phase 2: 网格构建 (buildGrid)**
```typescript
// src/strategy/grid-engine.ts:292-317
buildGrid(referencePrice: number) {
  // 1. 计算网格间距 (取最大值)
  const spacingRaw = max(priceTick, referencePrice * spacingPct)
  const spacing = roundToTick(spacingRaw)

  // 2. 确定中心价和上下边界
  const center = roundToTick(referencePrice)
  const lower = center - spacing * levelsPerSide   // 例: 150 - 0.5*15 = 142.5
  const upper = center + spacing * levelsPerSide   // 例: 150 + 0.5*15 = 157.5

  // 3. 生成网格价位数组
  for (let i = -levelsPerSide; i <= levelsPerSide; i++) {
    if (i === 0) continue  // 跳过中心点避免自成交

    const price = clampPrice(center + spacing * i)
    const side = i < 0 ? "BUY" : "SELL"  // 负索引=买单, 正索引=卖单

    levels.push({
      index: i,           // 例: -15, -14, ..., -1, 1, ..., 15
      price,              // 例: 142.5, 143.0, ..., 157.5
      side,
      status: "idle"      // 状态机: idle → entry-working → position-open → exit-working
    })
  }

  this.gridReady = true
  this.tradeLog.push("info", `网格已初始化: 中心=${center}, 间距=${spacing}`)
}
```

**数学原理**:
- **等比网格**: 每个价位相对中心点的间距相同 (算术级数)
- **价位索引**: 使用有符号整数标识网格层级,便于计算开平仓对应关系

##### **Phase 3: 计算理想挂单 (buildDesiredOrders)**
```typescript
// src/strategy/grid-engine.ts:381-425
buildDesiredOrders() {
  const desired = []
  const absPos = abs(position.positionAmt)  // 当前净持仓绝对值

  for (const level of levels) {
    // 跳过冷却期的网格层
    if (level.blockedUntil && now() < level.blockedUntil) continue

    // 场景 A: 该层已有持仓 → 挂平仓单
    if (level.status === "position-open" || level.status === "exit-working") {
      const exitPrice = computeExitPrice(level)  // 开仓价 + spacing
      desired.push({
        level: level.index,
        side: level.side === "BUY" ? "SELL" : "BUY",  // 反向平仓
        price: formatPrice(exitPrice),
        amount: tradeAmount,
        intent: "EXIT"
      })
    }
    // 场景 B: 该层空闲 → 挂开仓单
    else {
      desired.push({
        level: level.index,
        side: level.side,
        price: formatPrice(level.price),
        amount: tradeAmount,
        intent: "ENTRY"
      })
    }
  }

  // 风控: 过滤会超过最大持仓的开仓单
  if (maxPositionSize > 0) {
    return desired.filter(order => {
      if (order.intent !== "ENTRY") return true

      // 计算开仓后的净持仓
      if (position >= 0 && order.side === "BUY") {
        return absPos + order.amount <= maxPositionSize
      }
      if (position <= 0 && order.side === "SELL") {
        return absPos + order.amount <= maxPositionSize
      }
      return true
    })
  }

  return desired
}
```

**核心算法**:
1. **状态机驱动**: 每个网格层有 4 种状态
   - `idle`: 无仓位无挂单
   - `entry-working`: 开仓单挂单中
   - `position-open`: 已持仓等待平仓
   - `exit-working`: 平仓单挂单中

2. **持仓限制**: 通过 `maxPositionSize` 限制净持仓上限
   - 多头持仓时拒绝新的买单
   - 空头持仓时拒绝新的卖单

##### **Phase 4: 订单同步 (syncOpenOrders)**
```typescript
// src/strategy/grid-engine.ts:435-486
async syncOpenOrders() {
  // 1. 构建理想订单映射表
  const desiredKeys = new Map()
  for (const order of desiredOrders) {
    const key = `${order.intent}:${order.side}:${order.price}:${order.level}`
    desiredKeys.set(key, order)
  }

  // 2. 检查现有订单,撤销不在理想列表中的
  const activeKeys = new Set()
  for (const order of openOrders) {
    if (order.status === "FILLED" || "CANCELED") continue

    const key = orderKey(order)
    if (desiredKeys.has(key)) {
      activeKeys.add(key)  // 标记为已存在
    } else {
      await cancelOrder(order)  // 撤销多余订单
      tradeLog.push("order", `撤销多余挂单 #${order.orderId}`)
    }
  }

  // 3. 补挂缺失的订单
  for (const order of desiredOrders) {
    const key = orderKey(order)
    if (activeKeys.has(key)) continue  // 已存在则跳过

    await placeGridOrder(order)
  }
}
```

**幂等性保证**:
- 使用 `intent:side:price:level` 四元组作为订单唯一标识
- 每次轮询都重新计算理想状态并同步,避免状态不一致

##### **Phase 5: 订单成交处理 (handleOrderResolution)**
```typescript
// src/strategy/grid-engine.ts:568-605
handleOrderResolution(orderId, status, order) {
  const meta = orderIntentById.get(orderId)  // 获取订单元信息
  const level = levels.find(lv => lv.index === meta.level)

  if (meta.intent === "ENTRY") {
    level.entryOrderId = undefined

    if (status === "FILLED") {
      level.status = "position-open"  // 状态转换: entry-working → position-open
      tradeLog.push("fill", `网格开仓成交 ${meta.side} @ ${meta.price} (#${meta.level})`)
    } else {
      level.status = "idle"  // 订单取消或拒绝 → 回到空闲
    }
  }
  else {  // EXIT
    level.exitOrderId = undefined

    if (status === "FILLED") {
      level.status = "idle"  // 平仓完成 → 回到空闲,可再次开仓
      tradeLog.push("fill", `网格平仓成交 ${meta.side} @ ${meta.price} (#${meta.level})`)
    } else {
      level.status = "position-open"  // 平仓单取消 → 仓位仍存在
    }
  }

  // 清理订单追踪映射
  orderIntentById.delete(orderId)
  pendingCancels.delete(orderId)
}
```

**状态转换图**:
```
       开仓单提交           开仓成交           平仓单提交           平仓成交
idle ──────────→ entry-working ──────→ position-open ──────────→ exit-working ──────→ idle
  ↑                  │                                                 │                  │
  │                  │ 订单取消/拒绝                                    │ 平仓单取消       │
  └──────────────────┘                                                 └──────────────────┘
```

##### **Phase 6: 止损保护 (shouldStop + stopAndFlatten)**
```typescript
// src/strategy/grid-engine.ts:324-358
shouldStop(price) {
  const lowerGuard = lowerPrice * (1 - stopLossBufferPct)  // 下界外推 0.3%
  const upperGuard = upperPrice * (1 + stopLossBufferPct)  // 上界外推 0.3%

  if (price <= lowerGuard) {
    stopReason = `价格跌破网格下界 ${(100*(1 - price/lowerPrice)).toFixed(2)}%`
    return true
  }
  if (price >= upperGuard) {
    stopReason = `价格突破网格上界 ${(100*(price/upperPrice - 1)).toFixed(2)}%`
    return true
  }
  return false
}

async stopAndFlatten(price) {
  running = false
  tradeLog.push("warn", `${stopReason}, 开始撤单并平仓`)

  // 1. 撤销所有挂单
  await exchange.cancelAllOrders({ symbol })

  // 2. 市价平仓所有持仓
  await closePosition()

  // 3. 清空状态
  orderIntentById.clear()
  for (const level of levels) {
    level.status = "idle"
    level.entryOrderId = undefined
    level.exitOrderId = undefined
  }
}
```

**安全机制**:
- **缓冲区外推**: 在网格边界外额外预留 `stopLossBufferPct` 作为缓冲
- **市价平仓**: 使用 `reduceOnly=true` 和 `closePosition=true` 确保只平不开
- **状态重置**: 清空所有网格层状态,避免重启后继承旧仓位

#### Output: 持续运行的网格状态

```python
# GridEngineSnapshot (每次 tick 发射)
{
  "ready": True,
  "symbol": "BTCUSDT",
  "centerPrice": 150.0,
  "lowerPrice": 142.5,
  "upperPrice": 157.5,
  "lastPrice": 149.8,
  "gridLines": [
    {"level": -15, "price": 142.5, "side": "BUY", "active": True, "hasOrder": True},
    {"level": -14, "price": 143.0, "side": "BUY", "active": True, "hasOrder": True},
    # ... 其余 28 个网格
  ],
  "desiredOrders": [
    {"level": -15, "side": "BUY", "price": "142.5", "amount": 0.001, "intent": "ENTRY"},
    # ...
  ],
  "openOrders": [
    {"orderId": "12345", "symbol": "BTCUSDT", "side": "BUY", "price": "142.5", "status": "NEW", ...}
  ],
  "position": {
    "positionAmt": 0.003,      # 当前净持仓
    "entryPrice": 148.5,       # 平均开仓价
    "unrealizedProfit": 3.9,   # 未实现盈亏
    "markPrice": 149.8         # 标记价格
  },
  "running": True,
  "stopReason": None,
  "tradeLog": [
    {"timestamp": 1701234567890, "type": "info", "detail": "网格已初始化"},
    {"timestamp": 1701234568000, "type": "fill", "detail": "网格开仓成交 BUY @ 148.5 (#-5)"},
    # ... 最近 200 条日志
  ],
  "feedStatus": {
    "account": True,
    "orders": True,
    "depth": True,
    "ticker": True
  },
  "lastUpdated": 1701234570000
}
```

### 3.2 Magic: 巧妙设计点

#### 🎯 1. ClientOrderId 编码网格信息
```typescript
// src/strategy/grid-engine.ts:674-682
buildClientOrderId(order) {
  const intentFlag = order.intent === "ENTRY" ? "1" : "2"
  const sideFlag = order.side === "BUY" ? "1" : "2"
  const signFlag = order.level < 0 ? "0" : "1"
  const levelCode = abs(order.level).toString().padStart(3, "0")
  const ts = Date.now().toString().slice(-8)

  // 结果: "11004212345678" (纯数字满足交易所要求)
  //       ││││└─────────── 时间戳后8位
  //       │││└──────────── 网格层级 (000-999)
  //       ││└───────────── 层级符号 (0=负, 1=正)
  //       │└────────────── 订单方向 (1=BUY, 2=SELL)
  //       └─────────────── 订单意图 (1=ENTRY, 2=EXIT)
  return `${intentFlag}${sideFlag}${signFlag}${levelCode}${ts}`
}
```

**好处**:
- 订单丢失时可通过 ClientOrderId 反向解析意图和层级
- 满足部分交易所要求纯数字 ClientOrderId 的限制

#### 🎯 2. 订单映射双向索引
```typescript
// src/strategy/grid-engine.ts:88-89
private readonly orderIntentById = new Map<orderId, metadata>()
private readonly orderIntentByClientId = new Map<clientOrderId, metadata>()
```

**场景**:
- WebSocket 推送可能只包含 `orderId` 或 `clientOrderId` 中的一个
- 通过双向索引确保无论哪种情况都能找到订单元信息

#### 🎯 3. 幂等性订单同步算法
```typescript
// src/strategy/grid-engine.ts:441-485
// 伪代码
desired = computeDesiredOrders()
active = filterActiveOrders(openOrders)

// Diff 算法
toCancel = active - desired  // 多余的订单
toCreate = desired - active  // 缺失的订单

for order in toCancel: cancel(order)
for order in toCreate: create(order)
```

**优势**:
- 无论程序重启多少次,最终都会收敛到理想状态
- 避免重复下单或遗漏订单

#### 🎯 4. 状态机驱动网格层管理
```typescript
// 每个 GridLevelState 内嵌状态机
type Status = "idle" | "entry-working" | "position-open" | "exit-working"
```

**替代笨重方案**:
- ❌ 使用多个 boolean 标志位 (`hasPosition`, `hasEntryOrder`, `hasExitOrder`)
- ✅ 单一状态枚举,状态转换清晰

---

## Step 4: 复刻规格书 (Replication Spec)

### 4.1 Configuration (环境变量设计)

#### 必需配置项

```ini
# ========== 交易所配置 ==========
EXCHANGE=binance                    # 交易所标识 (binance/okx/bybit...)
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret

# ========== 网格策略参数 ==========
GRID_SYMBOL=BTCUSDT                 # 交易对
GRID_TRADE_AMOUNT=0.001             # 单笔开仓数量 (BTC)
GRID_LEVELS_PER_SIDE=15             # 单侧网格数 (总共30条)
GRID_SPACING_PCT=0.00025            # 网格间距 0.025%
GRID_MAX_POSITION_SIZE=0.01         # 最大净持仓 (BTC)
GRID_STOP_LOSS_BUFFER_PCT=0.003     # 止损缓冲区 0.3%
GRID_REFRESH_INTERVAL_MS=1000       # 轮询间隔 (毫秒)

# ========== 精度配置 ==========
GRID_PRICE_TICK=0.1                 # 价格最小变动单位
GRID_QTY_STEP=0.001                 # 数量最小变动单位

# ========== 日志与监控 ==========
GRID_MAX_LOG_ENTRIES=200            # 环形日志容量
GRID_ENABLE_STATS=true              # 启用统计功能
GRID_STATS_INTERVAL_MS=60000        # 统计计算间隔

# ========== 安全设置 ==========
GRID_MAX_OPEN_ORDERS=40             # 最大挂单数限制
GRID_RECONNECT_DELAY_MS=5000        # WebSocket 断线重连延迟
GRID_ORDER_RETRY_LIMIT=3            # 订单失败重试次数
```

#### 可选高级配置

```ini
# 网格模式 (geometric/arithmetic/fibonacci)
GRID_MODE=geometric

# 双向/单边交易
GRID_DIRECTION=both                 # both/long/short

# 自动重启 (价格回归时重新初始化网格)
GRID_AUTO_RESTART=true
GRID_RESTART_TRIGGER_PCT=0.02

# 滑点保护
GRID_MAX_CLOSE_SLIPPAGE_PCT=0.05    # 平仓单最大滑点 5%

# 订单 Post-Only 模式
GRID_POST_ONLY=true                 # 确保限价单总是maker
GRID_TIME_IN_FORCE=GTX              # Good-Till-Crossing
```

### 4.2 Schema Design (数据库表设计)

#### 表 1: `grid_trading_config`
```sql
CREATE TABLE grid_trading_config (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    trade_amount DECIMAL(20, 8) NOT NULL,
    levels_per_side INT NOT NULL CHECK (levels_per_side >= 5),
    spacing_pct DECIMAL(10, 6) NOT NULL,
    max_position_size DECIMAL(20, 8) NOT NULL,
    stop_loss_buffer_pct DECIMAL(10, 6) NOT NULL,
    price_tick DECIMAL(20, 8) NOT NULL,
    qty_step DECIMAL(20, 8) NOT NULL,
    refresh_interval_ms INT DEFAULT 1000,
    max_log_entries INT DEFAULT 200,

    -- 可选字段
    grid_mode VARCHAR(20) DEFAULT 'geometric',
    direction VARCHAR(10) DEFAULT 'both' CHECK (direction IN ('both', 'long', 'short')),
    auto_restart BOOLEAN DEFAULT true,
    restart_trigger_pct DECIMAL(10, 6) DEFAULT 0.02,

    -- 审计字段
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

CREATE INDEX idx_grid_config_symbol ON grid_trading_config(symbol);
CREATE INDEX idx_grid_config_active ON grid_trading_config(is_active);
```

#### 表 2: `grid_level_state`
```sql
CREATE TABLE grid_level_state (
    id SERIAL PRIMARY KEY,
    config_id INT REFERENCES grid_trading_config(id) ON DELETE CASCADE,
    level_index INT NOT NULL,              -- 网格层级 (-15 ~ 15)
    price DECIMAL(20, 8) NOT NULL,         -- 网格价位
    side VARCHAR(4) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    status VARCHAR(20) NOT NULL DEFAULT 'idle'
        CHECK (status IN ('idle', 'entry_working', 'position_open', 'exit_working')),

    entry_order_id VARCHAR(100),           -- 开仓订单ID
    exit_order_id VARCHAR(100),            -- 平仓订单ID
    entry_client_id VARCHAR(100),
    exit_client_id VARCHAR(100),

    blocked_until BIGINT,                  -- 冷却时间戳 (毫秒)

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(config_id, level_index)
);

CREATE INDEX idx_grid_level_config ON grid_level_state(config_id);
CREATE INDEX idx_grid_level_status ON grid_level_state(status);
```

#### 表 3: `grid_order_intent`
```sql
CREATE TABLE grid_order_intent (
    id SERIAL PRIMARY KEY,
    config_id INT REFERENCES grid_trading_config(id) ON DELETE CASCADE,
    order_id VARCHAR(100) UNIQUE NOT NULL,
    client_order_id VARCHAR(100) UNIQUE,

    level_index INT NOT NULL,
    intent VARCHAR(10) NOT NULL CHECK (intent IN ('ENTRY', 'EXIT')),
    side VARCHAR(4) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    price DECIMAL(20, 8) NOT NULL,
    amount DECIMAL(20, 8) NOT NULL,

    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

CREATE INDEX idx_order_intent_config ON grid_order_intent(config_id);
CREATE INDEX idx_order_intent_order_id ON grid_order_intent(order_id);
CREATE INDEX idx_order_intent_client_id ON grid_order_intent(client_order_id);
```

#### 表 4: `grid_trade_log`
```sql
CREATE TABLE grid_trade_log (
    id BIGSERIAL PRIMARY KEY,
    config_id INT REFERENCES grid_trading_config(id) ON DELETE CASCADE,
    log_type VARCHAR(20) NOT NULL CHECK (log_type IN ('info', 'warn', 'error', 'order', 'fill')),
    detail TEXT NOT NULL,
    timestamp BIGINT NOT NULL,             -- Unix 毫秒时间戳

    -- 可选: 关联订单ID
    order_id VARCHAR(100),
    level_index INT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_trade_log_config ON grid_trade_log(config_id);
CREATE INDEX idx_trade_log_timestamp ON grid_trade_log(timestamp DESC);
CREATE INDEX idx_trade_log_type ON grid_trade_log(log_type);

-- Ring Buffer 实现: 定期清理旧日志
-- CREATE TRIGGER delete_old_logs ...
```

#### 表 5: `grid_statistics` (统计表)
```sql
CREATE TABLE grid_statistics (
    id SERIAL PRIMARY KEY,
    config_id INT REFERENCES grid_trading_config(id) ON DELETE CASCADE,

    -- 时间范围
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,

    -- 交易统计
    total_trades INT DEFAULT 0,
    filled_entry_orders INT DEFAULT 0,
    filled_exit_orders INT DEFAULT 0,
    canceled_orders INT DEFAULT 0,

    -- 盈亏统计
    realized_pnl DECIMAL(20, 8) DEFAULT 0,     -- 已实现盈亏
    unrealized_pnl DECIMAL(20, 8) DEFAULT 0,   -- 未实现盈亏
    total_pnl DECIMAL(20, 8) DEFAULT 0,

    -- 持仓统计
    max_position_size DECIMAL(20, 8) DEFAULT 0,
    avg_position_size DECIMAL(20, 8) DEFAULT 0,
    current_position_size DECIMAL(20, 8) DEFAULT 0,

    -- 风控统计
    stop_loss_triggered_count INT DEFAULT 0,
    max_drawdown DECIMAL(10, 4) DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_grid_stats_config ON grid_statistics(config_id);
CREATE INDEX idx_grid_stats_period ON grid_statistics(period_start, period_end);
```

#### 表 6: `exchange_adapter_status` (连接状态)
```sql
CREATE TABLE exchange_adapter_status (
    id SERIAL PRIMARY KEY,
    exchange VARCHAR(20) UNIQUE NOT NULL,

    -- WebSocket 状态
    account_feed_connected BOOLEAN DEFAULT false,
    orders_feed_connected BOOLEAN DEFAULT false,
    depth_feed_connected BOOLEAN DEFAULT false,
    ticker_feed_connected BOOLEAN DEFAULT false,

    -- 最后活跃时间
    last_account_update TIMESTAMP,
    last_order_update TIMESTAMP,
    last_depth_update TIMESTAMP,
    last_ticker_update TIMESTAMP,

    -- 错误统计
    reconnect_count INT DEFAULT 0,
    last_error TEXT,
    last_error_time TIMESTAMP,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4.3 Interface Definition (核心接口签名)

#### Interface 1: ExchangeAdapter (交易所适配器)

```python
from abc import ABC, abstractmethod
from typing import Callable, List, Dict, Any
from dataclasses import dataclass
from decimal import Decimal

@dataclass
class AccountSnapshot:
    can_trade: bool
    total_wallet_balance: Decimal
    total_unrealized_profit: Decimal
    positions: List[Dict[str, Any]]
    assets: List[Dict[str, Any]]
    update_time: int

@dataclass
class Order:
    order_id: str
    client_order_id: str
    symbol: str
    side: str  # "BUY" | "SELL"
    type: str  # "LIMIT" | "MARKET" | "STOP"
    status: str  # "NEW" | "PARTIALLY_FILLED" | "FILLED" | "CANCELED" | "REJECTED"
    price: Decimal
    orig_qty: Decimal
    executed_qty: Decimal
    time: int
    update_time: int
    reduce_only: bool
    close_position: bool

@dataclass
class Depth:
    symbol: str
    bids: List[tuple[Decimal, Decimal]]  # [(price, qty), ...]
    asks: List[tuple[Decimal, Decimal]]
    timestamp: int

@dataclass
class Ticker:
    symbol: str
    last_price: Decimal
    mark_price: Decimal
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    volume: Decimal
    quote_volume: Decimal

class ExchangeAdapter(ABC):
    """交易所适配器基类"""

    @property
    @abstractmethod
    def id(self) -> str:
        """交易所唯一标识"""
        pass

    @abstractmethod
    async def watch_account(self, callback: Callable[[AccountSnapshot], None]) -> None:
        """
        订阅账户快照推送

        Args:
            callback: 回调函数,接收 AccountSnapshot
        """
        pass

    @abstractmethod
    async def watch_orders(self, callback: Callable[[List[Order]], None]) -> None:
        """
        订阅订单状态推送

        Args:
            callback: 回调函数,接收订单列表
        """
        pass

    @abstractmethod
    async def watch_depth(self, symbol: str, callback: Callable[[Depth], None]) -> None:
        """
        订阅盘口深度推送

        Args:
            symbol: 交易对
            callback: 回调函数,接收 Depth
        """
        pass

    @abstractmethod
    async def watch_ticker(self, symbol: str, callback: Callable[[Ticker], None]) -> None:
        """
        订阅行情推送

        Args:
            symbol: 交易对
            callback: 回调函数,接收 Ticker
        """
        pass

    @abstractmethod
    async def create_order(self,
                          symbol: str,
                          side: str,
                          order_type: str,
                          quantity: Decimal,
                          price: Decimal = None,
                          time_in_force: str = "GTC",
                          client_order_id: str = None,
                          reduce_only: bool = False,
                          close_position: bool = False) -> Order:
        """
        创建订单

        Args:
            symbol: 交易对
            side: "BUY" | "SELL"
            order_type: "LIMIT" | "MARKET"
            quantity: 数量
            price: 价格 (限价单必填)
            time_in_force: "GTC" | "GTX" | "IOC" | "FOK"
            client_order_id: 客户端订单ID
            reduce_only: 仅平仓
            close_position: 全部平仓

        Returns:
            Order 对象
        """
        pass

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> None:
        """撤销单个订单"""
        pass

    @abstractmethod
    async def cancel_all_orders(self, symbol: str) -> None:
        """撤销指定交易对的所有订单"""
        pass

    @abstractmethod
    async def get_precision(self, symbol: str) -> Dict[str, Any]:
        """
        获取交易对精度信息

        Returns:
            {
                "price_tick": Decimal,
                "qty_step": Decimal,
                "price_decimals": int,
                "qty_decimals": int
            }
        """
        pass
```

#### Interface 2: GridEngine (网格引擎)

```python
from dataclasses import dataclass
from typing import List, Optional, Callable
from enum import Enum

class GridLevelStatus(Enum):
    IDLE = "idle"
    ENTRY_WORKING = "entry_working"
    POSITION_OPEN = "position_open"
    EXIT_WORKING = "exit_working"

@dataclass
class GridConfig:
    symbol: str
    trade_amount: Decimal
    levels_per_side: int
    spacing_pct: Decimal
    max_position_size: Decimal
    stop_loss_buffer_pct: Decimal
    price_tick: Decimal
    qty_step: Decimal
    refresh_interval_ms: int = 1000
    max_log_entries: int = 200

@dataclass
class GridLevelState:
    index: int
    price: Decimal
    side: str
    status: GridLevelStatus
    entry_order_id: Optional[str] = None
    exit_order_id: Optional[str] = None
    blocked_until: Optional[int] = None

@dataclass
class GridEngineSnapshot:
    ready: bool
    symbol: str
    center_price: Optional[Decimal]
    lower_price: Optional[Decimal]
    upper_price: Optional[Decimal]
    last_price: Optional[Decimal]
    grid_lines: List[Dict]
    desired_orders: List[Dict]
    open_orders: List[Order]
    position: Dict
    running: bool
    stop_reason: Optional[str]
    trade_log: List[Dict]
    feed_status: Dict[str, bool]
    last_updated: Optional[int]

class GridEngine:
    """网格交易引擎"""

    def __init__(self,
                 config: GridConfig,
                 exchange: ExchangeAdapter,
                 logger: Optional[Any] = None):
        """
        初始化网格引擎

        Args:
            config: 网格配置
            exchange: 交易所适配器
            logger: 日志记录器
        """
        self.config = config
        self.exchange = exchange
        self.logger = logger

        self._grid_ready = False
        self._running = False
        self._levels: List[GridLevelState] = []
        # ... 其他私有属性

    async def start(self) -> None:
        """
        启动网格引擎
        - 订阅 WebSocket 数据流
        - 启动定时器轮询
        """
        pass

    async def stop(self) -> None:
        """
        停止网格引擎
        - 停止定时器
        - 关闭 WebSocket 连接
        - 不撤单不平仓 (保留现场)
        """
        pass

    async def emergency_stop(self) -> None:
        """
        紧急停止
        - 撤销所有挂单
        - 市价平仓所有持仓
        - 清空状态
        """
        pass

    def on(self, event: str, listener: Callable) -> None:
        """
        注册事件监听器

        Args:
            event: "update" | "error" | "stop"
            listener: 回调函数
        """
        pass

    def get_snapshot(self) -> GridEngineSnapshot:
        """获取当前网格状态快照"""
        pass

    # ========== 私有方法 ==========

    async def _bootstrap(self) -> None:
        """初始化: 订阅数据流"""
        pass

    def _build_grid(self, reference_price: Decimal) -> None:
        """构建网格价位数组"""
        pass

    def _build_desired_orders(self) -> List[Dict]:
        """计算理想挂单列表"""
        pass

    async def _sync_open_orders(self) -> None:
        """订单同步: 撤销多余订单,补挂缺失订单"""
        pass

    def _should_stop(self, price: Decimal) -> bool:
        """判断是否触发止损"""
        pass

    async def _stop_and_flatten(self) -> None:
        """止损平仓流程"""
        pass

    def _handle_order_resolution(self, order_id: str, status: str) -> None:
        """处理订单成交/取消事件"""
        pass

    async def _tick(self) -> None:
        """主循环: 每个轮询周期执行一次"""
        pass
```

#### Interface 3: OrderRouter (订单路由)

```python
from typing import Protocol

class OrderIntent(Protocol):
    """订单意图基类"""
    adapter: ExchangeAdapter
    symbol: str
    side: str
    quantity: Decimal

class LimitOrderIntent(OrderIntent):
    price: Decimal
    time_in_force: str = "GTC"
    client_order_id: Optional[str] = None

class MarketOrderIntent(OrderIntent):
    reduce_only: bool = False
    close_position: bool = False

async def route_limit_order(intent: LimitOrderIntent) -> Order:
    """
    路由限价单到对应交易所

    Args:
        intent: 限价单意图

    Returns:
        Order 对象
    """
    exchange_id = intent.adapter.id
    handler = get_limit_order_handler(exchange_id)
    return await handler(intent)

async def route_market_order(intent: MarketOrderIntent) -> Order:
    """路由市价单"""
    pass
```

#### Interface 4: TradeLog (交易日志)

```python
from collections import deque
from typing import Literal

LogType = Literal["info", "warn", "error", "order", "fill"]

@dataclass
class LogEntry:
    timestamp: int
    log_type: LogType
    detail: str
    order_id: Optional[str] = None
    level_index: Optional[int] = None

class TradeLog:
    """环形缓冲区日志"""

    def __init__(self, max_entries: int = 200):
        self._buffer: deque[LogEntry] = deque(maxlen=max_entries)

    def push(self, log_type: LogType, detail: str, **kwargs) -> None:
        """
        添加日志条目

        Args:
            log_type: 日志类型
            detail: 详细信息
            **kwargs: 可选字段 (order_id, level_index...)
        """
        entry = LogEntry(
            timestamp=int(time.time() * 1000),
            log_type=log_type,
            detail=detail,
            **kwargs
        )
        self._buffer.append(entry)

    def all(self) -> List[LogEntry]:
        """获取所有日志 (最近 max_entries 条)"""
        return list(self._buffer)

    def filter(self, log_type: Optional[LogType] = None) -> List[LogEntry]:
        """筛选特定类型的日志"""
        if log_type is None:
            return self.all()
        return [entry for entry in self._buffer if entry.log_type == log_type]
```

### 4.4 Implementation Roadmap (实施路线图)

#### Phase 1: 搭建基础 (Setup & Config) - 2-3 天

**目标**: 建立项目骨架和配置管理

**任务清单**:
1. ✅ 创建 Django App `grid_trading`
2. ✅ 数据库表设计与迁移
   ```bash
   python manage.py makemigrations grid_trading
   python manage.py migrate
   ```
3. ✅ 配置管理
   - 从 `.env` 读取配置
   - 创建 `GridConfig` dataclass
   - 实现 `load_config(name)` 函数
4. ✅ 日志系统
   - 实现 `TradeLog` 环形缓冲区
   - 集成 Django logging
5. ✅ 数学工具函数
   ```python
   def round_down_to_tick(price: Decimal, tick: Decimal) -> Decimal
   def round_qty_down_to_step(qty: Decimal, step: Decimal) -> Decimal
   def format_price(price: Decimal, decimals: int) -> str
   def decimals_of(tick: Decimal) -> int
   ```

**验收标准**:
- 配置可以从数据库和 `.env` 加载
- TradeLog 可以正确限制容量
- 数学函数通过单元测试

---

#### Phase 2: 实现核心算法 (Core Logic) - 5-7 天

**⚠️ 核心难点提示**:

##### 难点 1: 网格价位计算精度
**问题**: Decimal 计算可能产生无限小数,需要严格舍入
```python
# ❌ 错误示例
spacing = Decimal(str(reference_price * spacing_pct))  # 可能有精度误差

# ✅ 正确示例
spacing_raw = reference_price * spacing_pct
spacing = round_down_to_tick(max(price_tick, spacing_raw), price_tick)
```

**解决方案**:
- 所有价格计算后都调用 `round_down_to_tick()`
- 使用 `Decimal.quantize()` 控制小数位数

##### 难点 2: 订单状态同步时序问题
**问题**: WebSocket 推送和 REST API 查询可能不一致
```python
# 场景: 订单在 WebSocket 中显示 FILLED, 但账户快照仓位未更新

# 解决: 使用最后更新时间戳判断数据新鲜度
if order.update_time > account.update_time:
    # 订单数据更新,暂时信任订单状态
    # 等待账户快照推送
    pass
```

**解决方案**:
- 每个数据流记录最后更新时间
- 使用 `last_updated` 字段判断数据一致性
- 订单成交后等待 1 秒再计算 desired_orders

##### 难点 3: 幂等性订单同步算法
**问题**: 网络延迟导致订单重复创建或遗漏撤销

**核心代码**:
```python
async def sync_open_orders(self):
    # 1. 构建理想订单映射
    desired_keys = {
        self._order_key(order): order
        for order in self._build_desired_orders()
    }

    # 2. 标记已存在的订单
    active_keys = set()
    for order in self.open_orders:
        if order.status not in FINAL_STATUSES:
            key = self._order_key_from_order(order)
            if key in desired_keys:
                active_keys.add(key)
            else:
                # 多余订单 → 撤销
                await self._cancel_order(order)

    # 3. 补挂缺失订单
    for key, order in desired_keys.items():
        if key not in active_keys:
            await self._place_grid_order(order)

def _order_key(self, order_dict) -> str:
    """生成订单唯一键"""
    return f"{order_dict['intent']}:{order_dict['side']}:{order_dict['price']}:{order_dict['level']}"
```

**测试用例**:
```python
# 测试 1: 初始化时补齐所有订单
assert len(engine.open_orders) == 0
await engine.sync_open_orders()
assert len(engine.open_orders) == 30  # 30 条网格

# 测试 2: 幂等性 - 重复调用不产生额外订单
await engine.sync_open_orders()
assert len(engine.open_orders) == 30  # 仍然 30 条

# 测试 3: 订单成交后自动补单
engine._handle_order_resolution(order_id="123", status="FILLED")
await engine.sync_open_orders()
assert len(engine.open_orders) == 30  # 自动补回
```

##### 难点 4: WebSocket 断线重连
**问题**: 网络不稳定导致数据流中断

**解决方案**:
```python
async def safe_subscribe(self,
                         subscribe_func: Callable,
                         callback: Callable,
                         max_retries: int = 3):
    """安全订阅包装器"""
    retry_count = 0

    while retry_count < max_retries:
        try:
            await subscribe_func(callback)
            self.logger.info(f"订阅成功: {subscribe_func.__name__}")

            # 监听断线事件
            while True:
                await asyncio.sleep(1)
                if not self._is_feed_alive():
                    raise ConnectionError("数据流中断")

        except Exception as e:
            retry_count += 1
            self.logger.error(f"订阅失败 ({retry_count}/{max_retries}): {e}")

            if retry_count < max_retries:
                await asyncio.sleep(5 * retry_count)  # 指数退避
            else:
                raise
```

**任务清单**:
1. ✅ 实现 `GridLevelState` 模型
2. ✅ 实现 `GridEngine._build_grid()`
   - 等比网格计算
   - 价格精度舍入
   - 边界检查
3. ✅ 实现 `GridEngine._build_desired_orders()`
   - 状态机逻辑
   - 持仓限制过滤
   - 开平仓配对
4. ✅ 实现 `GridEngine._sync_open_orders()`
   - Diff 算法
   - 订单唯一键生成
   - 幂等性保证
5. ✅ 实现 `GridEngine._handle_order_resolution()`
   - 状态转换
   - 日志记录
6. ✅ 实现止损逻辑
   - `_should_stop()`
   - `_stop_and_flatten()`

**验收标准**:
- 单元测试覆盖率 >= 80%
- 网格价位计算误差 < 1e-8
- 订单同步幂等性测试通过

---

#### Phase 3: 交易所对接 (Exchange Integration) - 3-5 天

**任务清单**:
1. ✅ 定义 `ExchangeAdapter` 抽象基类
2. ✅ 实现 Binance 适配器
   ```python
   class BinanceAdapter(ExchangeAdapter):
       async def watch_account(self, callback):
           # 使用 Binance WebSocket UserData Stream
           pass

       async def create_order(self, **kwargs):
           # POST /fapi/v1/order
           pass
   ```
3. ✅ 实现 OKX 适配器 (如需支持)
4. ✅ 订单路由器
   ```python
   async def route_limit_order(intent: LimitOrderIntent) -> Order:
       handlers = {
           "binance": binance_create_limit_order,
           "okx": okx_create_limit_order
       }
       handler = handlers[intent.adapter.id]
       return await handler(intent)
   ```
5. ✅ WebSocket 管理
   - 自动重连
   - 心跳检测
   - 错误日志

**关键代码示例 (Binance)**:
```python
import asyncio
from binance.client import AsyncClient
from binance.streams import BinanceSocketManager

class BinanceAdapter(ExchangeAdapter):
    def __init__(self, api_key: str, api_secret: str):
        self.client = AsyncClient(api_key, api_secret)
        self.bsm = BinanceSocketManager(self.client)

    async def watch_account(self, callback):
        """订阅账户快照"""
        # 1. 开启 UserData Stream
        listen_key = await self.client.futures_stream_get_listen_key()

        # 2. 订阅 WebSocket
        async with self.bsm.futures_user_socket(listen_key=listen_key) as stream:
            while True:
                msg = await stream.recv()
                if msg['e'] == 'ACCOUNT_UPDATE':
                    snapshot = self._parse_account_snapshot(msg)
                    callback(snapshot)

    async def create_order(self, **params):
        """创建订单"""
        response = await self.client.futures_create_order(**params)
        return self._parse_order(response)
```

**验收标准**:
- Binance 适配器可以成功连接 testnet
- 订单创建和撤销功能正常
- WebSocket 断线后 30 秒内自动重连

---

#### Phase 4: 组装与接口 (Wiring & API) - 2-3 天

**任务清单**:
1. ✅ Django Management Command
   ```bash
   python manage.py start_grid --config my_btc_grid
   python manage.py stop_grid --config my_btc_grid
   python manage.py grid_status --config my_btc_grid
   ```
2. ✅ Django Admin 界面
   - 网格配置 CRUD
   - 实时状态监控
   - 日志查看
3. ✅ RESTful API (可选)
   ```python
   # /api/grid/<config_id>/start/
   # /api/grid/<config_id>/stop/
   # /api/grid/<config_id>/snapshot/
   # /api/grid/<config_id>/logs/
   ```
4. ✅ WebSocket 推送 (可选)
   - 实时网格状态
   - 订单成交通知
5. ✅ 统计功能
   ```python
   class GridStatistics:
       def calculate_realized_pnl(self) -> Decimal
       def calculate_unrealized_pnl(self) -> Decimal
       def calculate_win_rate(self) -> float
       def get_position_distribution(self) -> Dict[int, Decimal]
   ```

**Django Management Command 示例**:
```python
# management/commands/start_grid.py
from django.core.management.base import BaseCommand
from grid_trading.models import GridTradingConfig
from grid_trading.engine import GridEngine
from grid_trading.exchanges import create_adapter

class Command(BaseCommand):
    help = "启动网格交易策略"

    def add_arguments(self, parser):
        parser.add_argument("--config", type=str, required=True)

    def handle(self, *args, **options):
        config_name = options["config"]

        # 1. 加载配置
        config = GridTradingConfig.objects.get(name=config_name)

        # 2. 创建交易所适配器
        adapter = create_adapter(config.exchange)

        # 3. 初始化引擎
        engine = GridEngine(config, adapter)

        # 4. 注册事件监听
        engine.on("update", self.on_update)
        engine.on("error", self.on_error)

        # 5. 启动
        asyncio.run(engine.start())

        self.stdout.write(f"网格策略已启动: {config_name}")

    def on_update(self, snapshot):
        # 更新数据库状态
        pass

    def on_error(self, error):
        self.stderr.write(f"错误: {error}")
```

**验收标准**:
- Management Command 可以正常启动/停止网格
- Django Admin 可以查看实时状态
- 统计数据计算准确

---

### 4.5 安全与容错机制 (Safety & Fault Tolerance)

#### 1. 止损保护
```python
def _should_stop(self, price: Decimal) -> bool:
    """判断是否触发止损"""
    if not self.lower_price or not self.upper_price:
        return False

    lower_guard = self.lower_price * (1 - self.config.stop_loss_buffer_pct)
    upper_guard = self.upper_price * (1 + self.config.stop_loss_buffer_pct)

    if price <= lower_guard:
        self.stop_reason = f"价格跌破网格下界 {(100 * (1 - price / self.lower_price)):.2f}%"
        return True

    if price >= upper_guard:
        self.stop_reason = f"价格突破网格上界 {(100 * (price / self.upper_price - 1)):.2f}%"
        return True

    return False
```

#### 2. 最大持仓限制
```python
def _filter_orders_by_position_limit(self, orders: List[Dict]) -> List[Dict]:
    """过滤超过持仓上限的开仓单"""
    if self.config.max_position_size <= 0:
        return orders

    abs_pos = abs(self.position.position_amt)

    return [
        order for order in orders
        if order["intent"] != "ENTRY" or (
            # 多头持仓时拒绝新买单
            not (self.position.position_amt >= 0 and order["side"] == "BUY"
                 and abs_pos + order["amount"] > self.config.max_position_size)
            and
            # 空头持仓时拒绝新卖单
            not (self.position.position_amt <= 0 and order["side"] == "SELL"
                 and abs_pos + order["amount"] > self.config.max_position_size)
        )
    ]
```

#### 3. 订单失败重试
```python
async def _place_grid_order_with_retry(self, order_dict: Dict, max_retries: int = 3):
    """带重试的订单创建"""
    for attempt in range(max_retries):
        try:
            return await self._place_grid_order(order_dict)
        except Exception as e:
            if "max open orders" in str(e).lower():
                # 达到挂单上限 → 不重试,冷却 30 秒
                self._max_open_order_hit_until = time.time() + 30
                raise

            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # 指数退避
            else:
                self.trade_log.push("error", f"订单创建失败 (已重试 {max_retries} 次): {e}")
                raise
```

#### 4. 数据流健康检查
```python
def _is_feed_alive(self) -> bool:
    """检查数据流是否存活"""
    now = time.time()
    timeout = 60  # 60 秒无数据视为断线

    checks = [
        ("account", self._last_account_update),
        ("orders", self._last_order_update),
        ("ticker", self._last_ticker_update)
    ]

    for feed_name, last_update in checks:
        if last_update is None:
            self.logger.warning(f"{feed_name} feed 从未收到数据")
            return False

        if now - last_update > timeout:
            self.logger.error(f"{feed_name} feed 超时 ({now - last_update:.0f}s)")
            return False

    return True
```

#### 5. 异常捕获与日志
```python
async def _tick(self):
    """主循环 - 带全局异常保护"""
    try:
        # 主逻辑
        await self._sync_open_orders()
        self._emit_update()

    except Exception as e:
        self.trade_log.push("error", f"轮询异常: {e}")
        self.logger.exception("Tick 循环崩溃", exc_info=e)

        # 决策: 是否需要紧急停止?
        if isinstance(e, CriticalError):
            await self.emergency_stop()
```

---

## 附录 A: 关键代码片段索引

| 功能 | 源文件:行号 | 说明 |
|------|-----------|------|
| 网格构建算法 | `grid-engine.ts:292-317` | 等比网格价位计算 |
| 订单同步算法 | `grid-engine.ts:435-486` | Diff + 幂等补单 |
| 状态转换处理 | `grid-engine.ts:568-605` | 订单成交/取消后的状态机 |
| ClientOrderId 编码 | `grid-engine.ts:674-682` | 编码网格层级到订单ID |
| 止损逻辑 | `grid-engine.ts:324-358` | 价格突破检测+市价平仓 |
| 安全订阅包装 | `subscriptions.ts:11-45` | WebSocket 异常保护 |
| 交易所适配器接口 | `adapter.ts:38-51` | 统一抽象层 |
| 订单路由器 | `order-router.ts:95-117` | 策略模式实现 |
| 配置加载 | `config.ts:64-178` | 环境变量解析 |

---

## 附录 B: 测试用例建议

### 单元测试 (Unit Tests)

```python
# tests/test_grid_engine.py

def test_build_grid_geometric():
    """测试几何网格构建"""
    config = GridConfig(
        symbol="BTCUSDT",
        trade_amount=Decimal("0.001"),
        levels_per_side=15,
        spacing_pct=Decimal("0.00025"),
        price_tick=Decimal("0.1"),
        # ...
    )
    engine = GridEngine(config, MockAdapter())
    engine._build_grid(Decimal("150.0"))

    assert engine.center_price == Decimal("150.0")
    assert engine.lower_price == Decimal("142.5")
    assert engine.upper_price == Decimal("157.5")
    assert len(engine._levels) == 30  # 排除中心点

def test_order_sync_idempotence():
    """测试订单同步幂等性"""
    engine = GridEngine(config, adapter)

    # 第一次同步 - 补齐所有订单
    await engine._sync_open_orders()
    initial_count = len(adapter.created_orders)

    # 第二次同步 - 不应创建新订单
    await engine._sync_open_orders()
    assert len(adapter.created_orders) == initial_count

def test_position_limit_enforcement():
    """测试持仓上限强制执行"""
    config.max_position_size = Decimal("0.002")  # 最多 2 手
    engine = GridEngine(config, adapter)

    # 模拟已持有 2 手多仓
    engine.position = Position(position_amt=Decimal("0.002"))

    desired = engine._build_desired_orders()
    buy_orders = [o for o in desired if o["side"] == "BUY" and o["intent"] == "ENTRY"]

    # 应该没有新的买单 (会超过上限)
    assert len(buy_orders) == 0

def test_stop_loss_trigger():
    """测试止损触发"""
    engine = GridEngine(config, adapter)
    engine._build_grid(Decimal("150.0"))

    # 价格跌破下界 0.3%
    lower_guard = engine.lower_price * Decimal("0.997")
    assert engine._should_stop(lower_guard - Decimal("0.1")) is True
    assert "跌破" in engine.stop_reason
```

### 集成测试 (Integration Tests)

```python
# tests/test_binance_integration.py

@pytest.mark.integration
@pytest.mark.asyncio
async def test_binance_testnet_connection():
    """测试 Binance Testnet 连接"""
    adapter = BinanceAdapter(
        api_key=os.getenv("BINANCE_TESTNET_API_KEY"),
        api_secret=os.getenv("BINANCE_TESTNET_API_SECRET"),
        testnet=True
    )

    # 测试 REST API
    precision = await adapter.get_precision("BTCUSDT")
    assert "price_tick" in precision

    # 测试 WebSocket
    received_account = asyncio.Event()

    async def on_account(snapshot):
        assert snapshot.can_trade is not None
        received_account.set()

    await adapter.watch_account(on_account)
    await asyncio.wait_for(received_account.wait(), timeout=10)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_grid_lifecycle():
    """测试完整网格生命周期"""
    engine = GridEngine(config, adapter)

    # 1. 启动
    await engine.start()
    await asyncio.sleep(5)  # 等待数据流就绪

    snapshot = engine.get_snapshot()
    assert snapshot.ready is True
    assert len(snapshot.grid_lines) == 30

    # 2. 模拟订单成交
    # (手动在交易所制造成交,或 Mock WebSocket 推送)

    # 3. 停止
    await engine.stop()
    assert engine._running is False
```

---

## 附录 C: 性能优化建议

### 1. 数据库查询优化
```python
# ❌ N+1 查询问题
for level in grid_levels:
    order = Order.objects.get(level_id=level.id)

# ✅ 使用 select_related
grid_levels = GridLevelState.objects.select_related('order').filter(config_id=1)
```

### 2. WebSocket 消息批处理
```python
# 批量处理订单更新,避免每条消息都触发 sync
self._pending_order_updates = []

async def on_order_update(self, order):
    self._pending_order_updates.append(order)

    if len(self._pending_order_updates) >= 10:
        await self._batch_process_orders()

async def _batch_process_orders(self):
    updates = self._pending_order_updates
    self._pending_order_updates = []

    for order in updates:
        self._handle_order_resolution(order.order_id, order.status)
```

### 3. 内存缓存热点数据
```python
from django.core.cache import cache

def get_grid_config(config_id: int) -> GridConfig:
    cache_key = f"grid_config:{config_id}"
    config = cache.get(cache_key)

    if config is None:
        config = GridTradingConfig.objects.get(id=config_id)
        cache.set(cache_key, config, timeout=300)  # 5分钟

    return config
```

---

## 附录 D: 部署检查清单

- [ ] 环境变量已正确配置 (`.env` 文件)
- [ ] 数据库迁移已执行 (`python manage.py migrate`)
- [ ] 交易所 API 密钥已设置且有效
- [ ] 交易所账户有足够余额 (建议至少 100 USDT)
- [ ] 杠杆倍数已在交易所后台设置 (建议 50x)
- [ ] 持仓模式已设置为单向持仓
- [ ] 服务器时间已同步 (NTP)
- [ ] 防火墙允许 WebSocket 连接 (端口 443)
- [ ] 日志目录有写权限
- [ ] Supervisor / PM2 进程守护已配置
- [ ] 监控告警已配置 (策略停止/异常)
- [ ] 备份策略已制定 (数据库 + 配置文件)

---

## 结论

本技术规格书基于对 ritmex-bot 项目的深度逆向工程,提供了完整的网格交易系统复刻方案。核心要点:

1. **架构选择**: 采用分层模块化 + Adapter 模式,确保交易所可扩展
2. **算法实现**: 重点关注幂等性订单同步和精度处理
3. **安全机制**: 多层次风控 (止损/持仓限制/异常保护)
4. **开发路线**: 分 4 个阶段渐进式实施,每阶段有明确验收标准

**预计开发周期**: 12-18 天 (1 名高级 Python 开发者)

**技术债务风险**:
- WebSocket 管理复杂度高,需要充分测试断线场景
- Decimal 精度处理容易出错,建议使用辅助函数统一处理
- 数据流时序一致性是隐蔽 bug 来源,需要时间戳校验

**后续扩展方向**:
- 支持多网格并行运行
- 添加动态网格调整 (根据波动率)
- 集成回测引擎
- 支持现货网格
