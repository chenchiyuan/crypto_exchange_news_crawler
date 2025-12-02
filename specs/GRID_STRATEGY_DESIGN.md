# 经典网格交易策略 - 完整设计文档

## 目录

- [1. 策略概述](#1-策略概述)
- [2. 核心概念](#2-核心概念)
- [3. 网格初始化](#3-网格初始化)
- [4. 交易流程](#4-交易流程)
- [5. 状态管理](#5-状态管理)
- [6. 完整示例](#6-完整示例)
- [7. 实现细节](#7-实现细节)
- [8. 待确认问题](#8-待确认问题)

---

## 1. 策略概述

### 1.1 什么是网格交易？

网格交易是一种在**价格区间内**通过**频繁的低买高卖**来获利的量化策略。

```mermaid
graph LR
    A[价格震荡] --> B[多次买入]
    B --> C[多次卖出]
    C --> D[赚取价差]
    D --> A

    style A fill:#e1f5ff
    style D fill:#d4edda
```

### 1.2 策略优势

| 优势 | 说明 |
|------|------|
| 🎯 **适合震荡市** | 在横盘或震荡行情中表现优秀 |
| 🔄 **自动化** | 无需预测方向，价格触发自动交易 |
| 💰 **频繁套利** | 通过多次小幅盈利积累收益 |
| 📊 **风险分散** | 分层建仓，降低单笔风险 |

### 1.3 策略风险

| 风险 | 说明 | 缓解措施 |
|------|------|---------|
| ⚠️ **单边行情** | 持续上涨或下跌时表现差 | 设置止损 |
| 💸 **资金占用** | 需要足够资金支撑多层网格 | 合理设置网格层数 |
| 📉 **套牢风险** | 下跌时可能全仓买入 | 控制单格投入比例 |

---

## 2. 核心概念

### 2.1 参数定义

```mermaid
graph TD
    A[网格策略参数] --> B[基准价格<br/>Base Price]
    A --> C[网格步长<br/>Grid Step]
    A --> D[网格层数<br/>Grid Levels]
    A --> E[每格投入<br/>Per Grid Amount]
    A --> F[止损价格<br/>Stop Loss]

    B --> B1[2500 USDT<br/>网格中心]
    C --> C1[2%<br/>相邻网格间距]
    D --> D1[10层<br/>上下各10个价格点]
    E --> E1[1000 USDT<br/>每层投入金额]
    F --> F1[15%<br/>基准价下跌15%]

    style A fill:#4a90e2,color:#fff
    style B fill:#e8f4f8
    style C fill:#e8f4f8
    style D fill:#e8f4f8
    style E fill:#e8f4f8
    style F fill:#e8f4f8
```

### 2.2 网格结构

```mermaid
graph TB
    subgraph "卖出区域 (上方)"
        S10[Sell-10: 3000 USDT]
        S9[Sell-9: 2950 USDT]
        S8[Sell-8: 2900 USDT]
        S7[Sell-7: 2850 USDT]
        S6[Sell-6: 2800 USDT]
        S5[Sell-5: 2750 USDT]
        S4[Sell-4: 2700 USDT]
        S3[Sell-3: 2650 USDT]
        S2[Sell-2: 2600 USDT]
        S1[Sell-1: 2550 USDT]
    end

    BASE[⭐ 基准价格: 2500 USDT]

    subgraph "买入区域 (下方)"
        B1[Buy-1: 2450 USDT]
        B2[Buy-2: 2400 USDT]
        B3[Buy-3: 2350 USDT]
        B4[Buy-4: 2300 USDT]
        B5[Buy-5: 2250 USDT]
        B6[Buy-6: 2200 USDT]
        B7[Buy-7: 2150 USDT]
        B8[Buy-8: 2100 USDT]
        B9[Buy-9: 2050 USDT]
        B10[Buy-10: 2000 USDT]
    end

    S1 -.配对.-> B1
    S2 -.配对.-> B2
    S3 -.配对.-> B3

    style BASE fill:#ffd700,color:#000
    style S1 fill:#90EE90
    style S2 fill:#90EE90
    style S3 fill:#90EE90
    style B1 fill:#FFB6C1
    style B2 fill:#FFB6C1
    style B3 fill:#FFB6C1
```

### 2.3 网格配对关系

```mermaid
graph LR
    subgraph "配对示例 (步长2%)"
        B1[Buy-1<br/>2450 USDT] -->|+2%| S1[Sell-1<br/>2550 USDT]
        B2[Buy-2<br/>2400 USDT] -->|+2%| S2[Sell-2<br/>2600 USDT]
        B3[Buy-3<br/>2350 USDT] -->|+2%| S3[Sell-3<br/>2650 USDT]
    end

    style B1 fill:#FFB6C1
    style B2 fill:#FFB6C1
    style B3 fill:#FFB6C1
    style S1 fill:#90EE90
    style S2 fill:#90EE90
    style S3 fill:#90EE90
```

**配对公式**：
```
卖出价格 = 买入价格 × (1 + 步长)

例如：
Sell-1 = Buy-1 × 1.02 = 2450 × 1.02 = 2499 ≈ 2550
```

---

## 3. 网格初始化

### 3.1 初始化流程

```mermaid
flowchart TD
    Start([开始]) --> Input[输入参数]
    Input --> Calc1[计算买入网格价格]
    Input --> Calc2[计算卖出网格价格]

    Calc1 --> B1[Buy-1 = Base × 0.98]
    Calc1 --> B2[Buy-2 = Base × 0.96]
    Calc1 --> B3[Buy-3 = Base × 0.94]
    Calc1 --> BN[...]

    Calc2 --> S1[Sell-1 = Base × 1.02]
    Calc2 --> S2[Sell-2 = Base × 1.04]
    Calc2 --> S3[Sell-3 = Base × 1.06]
    Calc2 --> SN[...]

    B1 --> Init[初始化网格状态]
    B2 --> Init
    B3 --> Init
    BN --> Init
    S1 --> Init
    S2 --> Init
    S3 --> Init
    SN --> Init

    Init --> Ready[网格就绪]
    Ready --> End([等待价格触发])

    style Start fill:#4a90e2,color:#fff
    style End fill:#4a90e2,color:#fff
    style Ready fill:#52c41a,color:#fff
```

### 3.2 网格价格计算表

**示例配置**：
- 基准价格：2500 USDT
- 网格步长：2%
- 网格层数：10

| 买入网格 | 计算公式 | 价格 | 卖出网格 | 计算公式 | 价格 | 价差 |
|---------|---------|------|---------|---------|------|------|
| Buy-1 | 2500×0.98 | 2450 | Sell-1 | 2500×1.02 | 2550 | +100 |
| Buy-2 | 2500×0.96 | 2400 | Sell-2 | 2500×1.04 | 2600 | +200 |
| Buy-3 | 2500×0.94 | 2350 | Sell-3 | 2500×1.06 | 2650 | +300 |
| Buy-4 | 2500×0.92 | 2300 | Sell-4 | 2500×1.08 | 2700 | +400 |
| Buy-5 | 2500×0.90 | 2250 | Sell-5 | 2500×1.10 | 2750 | +500 |
| Buy-6 | 2500×0.88 | 2200 | Sell-6 | 2500×1.12 | 2800 | +600 |
| Buy-7 | 2500×0.86 | 2150 | Sell-7 | 2500×1.14 | 2850 | +700 |
| Buy-8 | 2500×0.84 | 2100 | Sell-8 | 2500×1.16 | 2900 | +800 |
| Buy-9 | 2500×0.82 | 2050 | Sell-9 | 2500×1.18 | 2950 | +900 |
| Buy-10 | 2500×0.80 | 2000 | Sell-10 | 2500×1.20 | 3000 | +1000 |

### 3.3 初始状态

```
┌─────────────────────────────────────┐
│         初始账户状态                 │
├─────────────────────────────────────┤
│ 💰 现金余额：10,000 USDT            │
│ 📊 持仓数量：0 ETH                  │
│ 💵 总价值：  10,000 USDT            │
├─────────────────────────────────────┤
│ 🔲 买入网格：10个（全部激活）       │
│ 🔳 卖出网格：10个（全部未激活）     │
└─────────────────────────────────────┘
```

---

## 4. 交易流程

### 4.1 完整交易生命周期

```mermaid
stateDiagram-v2
    [*] --> Idle: 初始化
    Idle --> Monitoring: 开始监控

    Monitoring --> BuyTriggered: 价格下穿买入网格
    BuyTriggered --> ExecuteBuy: 执行买入
    ExecuteBuy --> UpdateState1: 更新状态
    UpdateState1 --> ActivateSell: 激活卖出网格
    ActivateSell --> Monitoring

    Monitoring --> SellTriggered: 价格上穿卖出网格
    SellTriggered --> CheckPosition: 检查是否有对应持仓
    CheckPosition --> ExecuteSell: 有持仓→执行卖出
    CheckPosition --> Monitoring: 无持仓→跳过
    ExecuteSell --> UpdateState2: 更新状态
    UpdateState2 --> ReactivateBuy: 重新激活买入网格
    ReactivateBuy --> Monitoring

    Monitoring --> StopLoss: 触发止损
    StopLoss --> [*]: 清空所有持仓

    style Idle fill:#e8f4f8
    style Monitoring fill:#fff4e6
    style ExecuteBuy fill:#FFB6C1
    style ExecuteSell fill:#90EE90
    style StopLoss fill:#ff4d4f,color:#fff
```

### 4.2 买入流程详解

```mermaid
flowchart TD
    Start([价格监控]) --> Check1{价格下穿<br/>买入网格?}
    Check1 -->|否| Start
    Check1 -->|是| Check2{该网格<br/>是否激活?}

    Check2 -->|否| Start
    Check2 -->|是| Check3{剩余资金<br/>是否充足?}

    Check3 -->|否| Log1[记录：资金不足] --> Start
    Check3 -->|是| CalcAmount[计算买入数量]

    CalcAmount --> Execute[执行买入订单]
    Execute --> CalcFee[扣除手续费]
    CalcFee --> UpdateGrid[更新网格状态]

    UpdateGrid --> Save1[保存持仓记录]
    UpdateGrid --> Save2[更新现金余额]
    UpdateGrid --> Save3[标记网格已成交]
    UpdateGrid --> Save4[激活对应卖出网格]

    Save1 --> End([继续监控])
    Save2 --> End
    Save3 --> End
    Save4 --> End

    style Start fill:#4a90e2,color:#fff
    style Execute fill:#FFB6C1
    style End fill:#4a90e2,color:#fff
```

**买入计算示例**：

```
输入：
  - 买入价格：2450 USDT
  - 投入金额：1000 USDT
  - 手续费率：0.1%

计算：
  1. 手续费 = 1000 × 0.1% = 1 USDT
  2. 实际投入 = 1000 + 1 = 1001 USDT
  3. 买入数量 = 1000 / 2450 = 0.4082 ETH

输出：
  - 买入数量：0.4082 ETH
  - 成本：1001 USDT
  - 持仓记录：{ level: 1, amount: 0.4082, cost: 1001 }
```

### 4.3 卖出流程详解

```mermaid
flowchart TD
    Start([价格监控]) --> Check1{价格上穿<br/>卖出网格?}
    Check1 -->|否| Start
    Check1 -->|是| Check2{该网格<br/>对应持仓存在?}

    Check2 -->|否| Start
    Check2 -->|是| GetPosition[获取对应持仓信息]

    GetPosition --> Execute[执行卖出订单]
    Execute --> CalcFee[扣除手续费]
    CalcFee --> CalcProfit[计算盈亏]

    CalcProfit --> UpdateGrid[更新网格状态]
    UpdateGrid --> Save1[清空持仓记录]
    UpdateGrid --> Save2[更新现金余额]
    UpdateGrid --> Save3[标记网格已平仓]
    UpdateGrid --> Save4[重新激活买入网格]

    Save1 --> End([继续监控])
    Save2 --> End
    Save3 --> End
    Save4 --> End

    style Start fill:#4a90e2,color:#fff
    style Execute fill:#90EE90
    style CalcProfit fill:#ffd700
    style End fill:#4a90e2,color:#fff
```

**卖出计算示例**：

```
输入：
  - 卖出价格：2550 USDT
  - 卖出数量：0.4082 ETH (来自Buy-1)
  - 买入成本：1001 USDT
  - 手续费率：0.1%

计算：
  1. 卖出所得 = 0.4082 × 2550 = 1041 USDT
  2. 手续费 = 1041 × 0.1% = 1.04 USDT
  3. 实际收入 = 1041 - 1.04 = 1039.96 USDT
  4. 净利润 = 1039.96 - 1001 = 38.96 USDT
  5. 收益率 = 38.96 / 1001 = 3.89%

输出：
  - 实际收入：1039.96 USDT
  - 净利润：38.96 USDT
  - 收益率：3.89%
```

### 4.4 价格穿越检测

```mermaid
graph TB
    subgraph "买入穿越检测 (向下)"
        A1[前一时刻价格<br/>2460 USDT] -->|向下移动| A2[当前时刻价格<br/>2440 USDT]
        A3[买入网格<br/>2450 USDT]
        A1 -.大于.-> A3
        A2 -.小于等于.-> A3
        A4[✅ 触发买入]
        A3 --> A4
    end

    subgraph "卖出穿越检测 (向上)"
        B1[前一时刻价格<br/>2540 USDT] -->|向上移动| B2[当前时刻价格<br/>2560 USDT]
        B3[卖出网格<br/>2550 USDT]
        B1 -.小于.-> B3
        B2 -.大于等于.-> B3
        B4[✅ 触发卖出]
        B3 --> B4
    end

    style A4 fill:#FFB6C1
    style B4 fill:#90EE90
```

**伪代码**：

```python
# 买入穿越检测
def check_buy_cross(prev_price, curr_price, buy_level_price):
    """检查是否向下穿过买入网格"""
    return prev_price > buy_level_price >= curr_price

# 卖出穿越检测
def check_sell_cross(prev_price, curr_price, sell_level_price):
    """检查是否向上穿过卖出网格"""
    return prev_price < sell_level_price <= curr_price
```

---

## 5. 状态管理

### 5.1 网格状态机

```mermaid
stateDiagram-v2
    [*] --> Available: 初始化

    Available --> Triggered: 价格穿越
    Triggered --> Filled: 订单成交

    state Filled {
        [*] --> BuyFilled: 买入成交
        [*] --> SellFilled: 卖出成交
    }

    BuyFilled --> WaitingSell: 激活卖出网格
    WaitingSell --> SellFilled: 卖出成交
    SellFilled --> Available: 重新激活

    Available --> Disabled: 止损触发
    Disabled --> [*]

    style Available fill:#e8f4f8
    style Filled fill:#ffd700
    style BuyFilled fill:#FFB6C1
    style SellFilled fill:#90EE90
    style Disabled fill:#ff4d4f,color:#fff
```

### 5.2 网格数据结构

```python
# 单个网格的状态
Grid = {
    "level": 1,                    # 网格层级
    "type": "buy",                 # 类型：buy/sell
    "price": 2450.0,               # 触发价格
    "status": "available",         # 状态：available/filled/waiting
    "paired_level": 1,             # 配对的网格层级
    "position": {                  # 持仓信息
        "amount": 0.4082,          # 持仓数量（ETH）
        "cost": 1001.0,            # 总成本（USDT）
        "buy_price": 2450.0,       # 买入价格
        "buy_time": "2025-01-15T10:00:00"  # 买入时间
    } or None                      # 无持仓时为None
}
```

### 5.3 账户状态

```python
Account = {
    "cash": 8999.0,                # 现金余额（USDT）
    "positions": [                 # 所有持仓列表
        {
            "grid_level": 1,
            "amount": 0.4082,
            "cost": 1001.0,
            "buy_price": 2450.0
        }
    ],
    "total_buy_orders": 1,         # 总买入次数
    "total_sell_orders": 0,        # 总卖出次数
    "realized_pnl": 0.0,           # 已实现盈亏
    "unrealized_pnl": -1.0,        # 未实现盈亏（含手续费）
    "total_fees": 2.0              # 总手续费
}
```

---

## 6. 完整示例

### 6.1 时序图

```mermaid
sequenceDiagram
    autonumber
    participant P as 价格
    participant S as 策略引擎
    participant G as 网格管理器
    participant A as 账户

    Note over P,A: T0: 初始化
    S->>G: 初始化网格（2500, 2%, 10层）
    G->>G: 生成买入网格 2450~2000
    G->>G: 生成卖出网格 2550~3000
    G-->>S: 网格就绪

    Note over P,A: T1: 价格跌至2450（Buy-1）
    P->>S: 当前价格2450
    S->>G: 检查网格穿越
    G->>G: 发现Buy-1触发
    G->>A: 买入0.4082 ETH @ 2450
    A-->>G: 成交确认
    G->>G: 激活Sell-1网格
    G-->>S: 买入完成

    Note over P,A: T2: 价格跌至2400（Buy-2）
    P->>S: 当前价格2400
    S->>G: 检查网格穿越
    G->>G: 发现Buy-2触发
    G->>A: 买入0.4167 ETH @ 2400
    A-->>G: 成交确认
    G->>G: 激活Sell-2网格
    G-->>S: 买入完成

    Note over P,A: T3: 价格涨至2550（Sell-1）
    P->>S: 当前价格2550
    S->>G: 检查网格穿越
    G->>G: 发现Sell-1触发
    G->>G: 查找Buy-1持仓
    G->>A: 卖出0.4082 ETH @ 2550
    A-->>G: 成交确认
    A->>A: 计算盈亏：+38.96 USDT
    G->>G: 清空Buy-1持仓
    G->>G: 重新激活Buy-1网格
    G-->>S: 卖出完成，盈利38.96
```

### 6.2 价格走势与交易点

```mermaid
graph TB
    subgraph "价格时间序列"
        T0[T0: 2500 USDT<br/>初始价格]
        T1[T1: 2450 USDT<br/>🔴 Buy-1]
        T2[T2: 2400 USDT<br/>🔴 Buy-2]
        T3[T3: 2350 USDT<br/>🔴 Buy-3]
        T4[T4: 2420 USDT<br/>价格震荡]
        T5[T5: 2550 USDT<br/>🟢 Sell-1]
        T6[T6: 2600 USDT<br/>🟢 Sell-2]
        T7[T7: 2450 USDT<br/>🔴 Buy-1再次触发]

        T0 -->|下跌| T1
        T1 -->|继续下跌| T2
        T2 -->|继续下跌| T3
        T3 -->|小幅反弹| T4
        T4 -->|大幅上涨| T5
        T5 -->|继续上涨| T6
        T6 -->|回落| T7
    end

    style T1 fill:#FFB6C1
    style T2 fill:#FFB6C1
    style T3 fill:#FFB6C1
    style T5 fill:#90EE90
    style T6 fill:#90EE90
    style T7 fill:#FFB6C1
```

### 6.3 账户余额变化表

| 时刻 | 事件 | 价格 | 现金 | 持仓(ETH) | 持仓市值 | 总价值 | 盈亏 |
|------|------|------|------|----------|---------|--------|------|
| T0 | 初始化 | 2500 | 10,000 | 0 | 0 | 10,000 | 0 |
| T1 | Buy-1买入 | 2450 | 8,999 | 0.4082 | 1,000 | 9,999 | -1 |
| T2 | Buy-2买入 | 2400 | 7,998 | 0.8249 | 1,980 | 9,978 | -22 |
| T3 | Buy-3买入 | 2350 | 6,997 | 1.2504 | 2,938 | 9,935 | -65 |
| T4 | 价格震荡 | 2420 | 6,997 | 1.2504 | 3,026 | 10,023 | +23 |
| T5 | Sell-1卖出 | 2550 | 8,037 | 0.8422 | 2,148 | 10,185 | +185 |
| T6 | Sell-2卖出 | 2600 | 9,119 | 0.4255 | 1,106 | 10,225 | +225 |
| T7 | Buy-1再买 | 2450 | 8,118 | 0.8337 | 2,043 | 10,161 | +161 |

**关键观察**：
- 手续费导致初始亏损（-1 USDT）
- 下跌时浮亏扩大（-65 USDT）
- 反弹卖出后转为盈利（+185 USDT）
- 网格可重复触发（T7再次买入）

---

## 7. 实现细节

### 7.1 核心算法流程

```mermaid
flowchart TD
    Start([开始回测]) --> Init[初始化网格]
    Init --> Loop{遍历所有K线}

    Loop -->|有下一根| GetPrice[获取当前价格]
    Loop -->|结束| Final[最后平仓]

    GetPrice --> CheckBuy[检查所有买入网格]
    CheckBuy --> BuyLoop{遍历买入网格}

    BuyLoop -->|有下一个| CheckBuyStatus{网格是否激活?}
    BuyLoop -->|结束| CheckSell[检查所有卖出网格]

    CheckBuyStatus -->|是| CheckBuyCross{价格下穿?}
    CheckBuyStatus -->|否| BuyLoop

    CheckBuyCross -->|是| ExecuteBuy[执行买入]
    CheckBuyCross -->|否| BuyLoop

    ExecuteBuy --> BuyLoop

    CheckSell --> SellLoop{遍历卖出网格}

    SellLoop -->|有下一个| CheckSellStatus{有对应持仓?}
    SellLoop -->|结束| CheckStop[检查止损]

    CheckSellStatus -->|是| CheckSellCross{价格上穿?}
    CheckSellStatus -->|否| SellLoop

    CheckSellCross -->|是| ExecuteSell[执行卖出]
    CheckSellCross -->|否| SellLoop

    ExecuteSell --> SellLoop

    CheckStop --> StopCheck{触发止损?}
    StopCheck -->|是| CloseAll[清空所有持仓]
    StopCheck -->|否| UpdateStats[更新统计]

    CloseAll --> UpdateStats
    UpdateStats --> Loop

    Final --> CalcResult[计算回测结果]
    CalcResult --> End([结束])

    style Start fill:#4a90e2,color:#fff
    style ExecuteBuy fill:#FFB6C1
    style ExecuteSell fill:#90EE90
    style CloseAll fill:#ff4d4f,color:#fff
    style End fill:#4a90e2,color:#fff
```

### 7.2 数据结构设计

```python
class GridStrategy:
    """网格策略核心类"""

    def __init__(self, config):
        # 配置参数
        self.base_price = config.base_price        # 基准价格
        self.grid_step = config.grid_step          # 网格步长
        self.grid_levels = config.grid_levels      # 网格层数
        self.per_grid_amount = config.amount       # 每格投入
        self.stop_loss_pct = config.stop_loss      # 止损百分比

        # 网格列表
        self.buy_grids = []      # 买入网格列表
        self.sell_grids = []     # 卖出网格列表

        # 账户状态
        self.cash = config.initial_cash            # 现金
        self.positions = {}                        # 持仓字典 {level: Position}

        # 统计信息
        self.total_buy_orders = 0
        self.total_sell_orders = 0
        self.realized_pnl = 0.0
        self.total_fees = 0.0

    def initialize_grids(self):
        """初始化网格"""
        for i in range(1, self.grid_levels + 1):
            # 买入网格
            buy_price = self.base_price * (1 - self.grid_step * i)
            sell_price = self.base_price * (1 + self.grid_step * i)

            self.buy_grids.append({
                'level': i,
                'price': buy_price,
                'status': 'available',
                'paired_sell_level': i
            })

            # 卖出网格
            self.sell_grids.append({
                'level': i,
                'price': sell_price,
                'status': 'inactive',  # 初始未激活
                'paired_buy_level': i
            })

    def on_price_update(self, prev_price, curr_price):
        """价格更新时调用"""
        # 1. 检查买入网格
        for grid in self.buy_grids:
            if self.check_buy_cross(prev_price, curr_price, grid):
                self.execute_buy(grid)

        # 2. 检查卖出网格
        for grid in self.sell_grids:
            if self.check_sell_cross(prev_price, curr_price, grid):
                self.execute_sell(grid)

        # 3. 检查止损
        if self.check_stop_loss(curr_price):
            self.close_all_positions(curr_price)
```

### 7.3 关键函数伪代码

#### 买入执行

```python
def execute_buy(self, grid, price):
    """
    执行买入操作

    Args:
        grid: 买入网格对象
        price: 当前价格
    """
    # 1. 检查资金
    if self.cash < self.per_grid_amount:
        log("资金不足，跳过买入")
        return

    # 2. 计算买入数量
    amount_in_usdt = self.per_grid_amount
    fee = amount_in_usdt * FEE_RATE
    total_cost = amount_in_usdt + fee
    amount_in_eth = amount_in_usdt / price

    # 3. 更新账户
    self.cash -= total_cost
    self.positions[grid.level] = {
        'amount': amount_in_eth,
        'cost': total_cost,
        'buy_price': price,
        'buy_time': current_time
    }

    # 4. 更新网格状态
    grid.status = 'filled'
    paired_sell_grid = self.sell_grids[grid.paired_sell_level - 1]
    paired_sell_grid.status = 'active'  # 激活卖出网格

    # 5. 统计
    self.total_buy_orders += 1
    self.total_fees += fee

    log(f"买入成交: Level {grid.level}, "
        f"价格 {price}, 数量 {amount_in_eth:.4f}")
```

#### 卖出执行

```python
def execute_sell(self, grid, price):
    """
    执行卖出操作

    Args:
        grid: 卖出网格对象
        price: 当前价格
    """
    # 1. 检查持仓
    buy_level = grid.paired_buy_level
    if buy_level not in self.positions:
        log("无对应持仓，跳过卖出")
        return

    position = self.positions[buy_level]

    # 2. 计算卖出收益
    amount_in_eth = position['amount']
    revenue = amount_in_eth * price
    fee = revenue * FEE_RATE
    net_revenue = revenue - fee

    # 3. 计算盈亏
    pnl = net_revenue - position['cost']
    pnl_pct = pnl / position['cost'] * 100

    # 4. 更新账户
    self.cash += net_revenue
    del self.positions[buy_level]

    # 5. 更新网格状态
    grid.status = 'inactive'  # 卖出网格重置
    paired_buy_grid = self.buy_grids[buy_level - 1]
    paired_buy_grid.status = 'available'  # 重新激活买入网格

    # 6. 统计
    self.total_sell_orders += 1
    self.realized_pnl += pnl
    self.total_fees += fee

    log(f"卖出成交: Level {grid.level}, "
        f"价格 {price}, 数量 {amount_in_eth:.4f}, "
        f"盈亏 {pnl:.2f} ({pnl_pct:.2f}%)")
```

---

## 8. 待确认问题

在实现之前，请明确以下设计选择：

### 问题1: 网格配对策略

```mermaid
graph LR
    subgraph "选项A: 严格配对"
        A1[Buy-1 @ 2450] -->|只能| A2[Sell-1 @ 2550]
        A3[Buy-2 @ 2400] -->|只能| A4[Sell-2 @ 2600]
    end

    subgraph "选项B: 灵活卖出"
        B1[Buy-1 @ 2450] -->|可以| B2[Sell-1 @ 2550]
        B1 -->|或| B3[Sell-2 @ 2600]
        B1 -->|或| B4[Sell-3 @ 2650]
    end

    style A2 fill:#90EE90
    style A4 fill:#90EE90
    style B2 fill:#90EE90
    style B3 fill:#90EE90
    style B4 fill:#90EE90
```

**你的选择**：`选项A` 或 `选项B`？

---

### 问题2: 卖出顺序

如果同时持有多个买入持仓（Buy-1, Buy-2, Buy-3），当Sell-2触发时：

```mermaid
graph TD
    A[Sell-2触发<br/>2600 USDT] --> B{卖出哪个持仓?}

    B --> C1[选项A: FIFO<br/>卖出最早的Buy-1]
    B --> C2[选项B: 配对<br/>只卖出Buy-2]
    B --> C3[选项C: LIFO<br/>卖出最晚的Buy-3]

    style A fill:#90EE90
```

**你的选择**：`选项A`, `选项B`, 或 `选项C`？

---

### 问题3: 资金分配策略

```mermaid
graph TB
    subgraph "选项A: 固定金额"
        A1[每格固定1000 USDT]
        A2[优点: 简单, 每格收益相等]
        A3[缺点: 需要预留足够资金]
    end

    subgraph "选项B: 固定比例"
        B1[每格 = 剩余资金 / 剩余网格数]
        B2[优点: 充分利用资金]
        B3[缺点: 每格金额不同]
    end

    subgraph "选项C: 按层级加权"
        C1[越低的网格投入越多]
        C2[优点: 低位重仓]
        C3[缺点: 复杂, 可能资金不足]
    end
```

**你的选择**：`选项A`, `选项B`, 或 `选项C`？

---

### 问题4: 基准价格确定

```mermaid
graph LR
    A[基准价格选择] --> B[选项A:<br/>第一根K线价格]
    A --> C[选项B:<br/>回测期平均价]
    A --> D[选项C:<br/>用户手动指定]
    A --> E[选项D:<br/>中位数价格]

    style A fill:#4a90e2,color:#fff
```

**你的选择**：`选项A`, `选项B`, `选项C`, 或 `选项D`？

---

### 问题5: 止损机制

```mermaid
graph TD
    A[止损类型] --> B[选项A: 全局止损]
    A --> C[选项B: 单笔止损]
    A --> D[选项C: 无止损]

    B --> B1[价格 < 基准 × 0.85<br/>清空所有持仓]
    C --> C1[单笔浮亏 > 15%<br/>止损该笔持仓]
    D --> D1[不设置止损<br/>允许完全套牢]

    style A fill:#4a90e2,color:#fff
    style B1 fill:#ff4d4f,color:#fff
```

**你的选择**：`选项A`, `选项B`, 或 `选项C`？

---

## 9. 预期结果

### 9.1 合理的交易频率

在**震荡市场**（ETH 2000-3000区间，180天）：

| 市场特征 | 预期买入次数 | 预期卖出次数 | 总交易 |
|---------|------------|------------|--------|
| 窄幅震荡 (±5%) | 10-20 | 10-20 | 20-40 |
| 中幅震荡 (±10%) | 20-40 | 20-40 | 40-80 |
| 宽幅震荡 (±20%) | 30-60 | 30-60 | 60-120 |

**如果只有4笔交易，说明策略实现有误！**

### 9.2 收益分布

```mermaid
graph TD
    A[网格收益来源] --> B[交易价差<br/>最主要]
    A --> C[持仓市值变化<br/>次要]

    B --> B1[每次完整网格:<br/>约2-4%收益]
    B --> B2[震荡越频繁<br/>累计收益越高]

    C --> C1[最终价格>基准:<br/>额外收益]
    C --> C2[最终价格<基准:<br/>浮亏]

    style A fill:#4a90e2,color:#fff
    style B fill:#52c41a,color:#fff
```

---

## 10. 总结

### ✅ 确认清单

请确认你理解并同意以下内容：

- [ ] 理解经典网格策略的核心原理
- [ ] 理解网格配对和重置机制
- [ ] 理解买入/卖出穿越检测逻辑
- [ ] 理解资金管理和持仓跟踪
- [ ] 明确8个待确认问题的答案

### 📋 实现前的准备

1. **明确设计选择**：回答8个待确认问题
2. **确定配置参数**：基准价格、步长、层数等
3. **商定测试标准**：期望的交易频率、收益率
4. **准备测试数据**：ETH 4h, 180天数据

### 🚀 下一步

**请回复你对8个待确认问题的答案，我将据此实现完整的网格策略！**

---

**文档版本**: v1.0
**创建时间**: 2025-11-28
**最后更新**: 2025-11-28
