# 策略20：多交易对共享资金池策略

## 1. 概述

### 1.1 背景
现有策略（策略16/19等）均为单交易对设计，每个策略实例独立管理一个交易对的买卖。实际交易场景中，用户希望使用同一资金池同时管理多个交易对，实现跨交易对的资金动态分配。

### 1.2 目标
基于策略16实现策略20，支持单一资金池同时管理多个交易对（ETH, BTC, HYPE, BNB），在资金有限的约束下实现多交易对的并行交易。

### 1.3 核心价值
- **资金利用率提升**：共享资金池，哪个交易对有机会就分配资金
- **风险分散**：同时持有多个交易对，降低单一交易对风险
- **统一管理**：一次回测输出所有交易对的综合表现

## 2. 核心设计

### 2.1 资金管理模型

```
┌─────────────────────────────────────────────────────────────┐
│                    共享资金池 (10000 USDT)                    │
├─────────────────────────────────────────────────────────────┤
│  available_cash = total_cash - frozen_cash - holdings_value │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│   │  ETH    │  │  BTC    │  │  HYPE   │  │  BNB    │       │
│   │ 挂单/持仓│  │ 挂单/持仓│  │ 挂单/持仓│  │ 挂单/持仓│       │
│   └─────────┘  └─────────┘  └─────────┘  └─────────┘       │
│                                                             │
│   全局约束: 合计持仓数 ≤ max_positions (10)                  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心约束
| 约束项 | 说明 |
|--------|------|
| 资金池 | 全局共享，所有交易对竞争同一资金池 |
| max_positions | 全局限制，4个交易对合计最多10个持仓 |
| 仓位计算 | `单笔金额 = available_cash / (max_positions - total_holdings)` |
| 挂单处理 | 每个交易对独立计算挂单，但共享资金约束 |

### 2.3 处理流程

```
每根K线处理流程（按时间戳对齐）：
┌──────────────────────────────────────────────────────────┐
│ 1. 获取当前时间戳的所有交易对K线数据                        │
├──────────────────────────────────────────────────────────┤
│ 2. 按交易对顺序依次处理：                                  │
│    For symbol in [ETH, BTC, HYPE, BNB]:                  │
│      a. 检查卖出挂单是否成交 → 回收资金                    │
│      b. 检查买入挂单是否成交 → 记录持仓                    │
│      c. 更新卖出挂单（基于当前周期）                       │
│      d. 计算买入挂单（检查全局持仓限制和资金）              │
├──────────────────────────────────────────────────────────┤
│ 3. 更新全局资金状态                                        │
└──────────────────────────────────────────────────────────┘
```

## 3. 功能需求

### 3.1 P0 核心功能（MVP）

#### F-001: 多交易对数据加载
- 支持加载多个交易对的K线数据
- 按时间戳对齐处理
- 默认交易对：ETHUSDT, BTCUSDT, HYPEUSDT, BNBUSDT

#### F-002: 全局资金池管理
- 维护全局 `available_cash`
- 支持资金冻结（挂单）和解冻（取消/成交）
- 跟踪总持仓价值

#### F-003: 全局持仓限制
- 跟踪所有交易对的持仓总数
- 持仓数达到 `max_positions` 时，所有交易对停止新建挂单
- 单笔仓位 = `available_cash / (max_positions - total_holdings)`

#### F-004: 独立交易对买卖逻辑
- 复用策略16的买入条件计算
- 复用策略16的卖出挂单计算
- 每个交易对独立计算指标（P5, EMA25, cycle_phase等）

#### F-005: 分交易对统计输出
- 每个交易对输出独立统计：
  - 订单数、胜率、盈亏
  - 持仓数、平均持仓时长
- 输出格式与策略16一致

#### F-006: 合并汇总统计
- 全局统计：
  - 总订单数、总胜率、总盈亏
  - 总收益率、APR、APY
  - 最大回撤（基于全局资金曲线）

#### F-007: run_strategy_backtest集成
- 支持通过 `run_strategy_backtest` 命令执行回测
- 参数：`--strategy strategy-20-multi-symbol`
- 支持 `--symbols ETHUSDT,BTCUSDT,HYPEUSDT,BNBUSDT`

### 3.2 P1 延期功能

#### F-P1-001: 动态交易对配置
- 支持运行时指定任意交易对组合
- 支持从配置文件加载交易对列表

#### F-P1-002: 优先级机制
- 当多个交易对同时触发信号时，按优先级分配资金
- 优先级可配置（默认按交易量排序）

#### F-P1-003: 单交易对持仓限制
- 除全局限制外，可配置单交易对最大持仓数

## 4. 技术设计

### 4.1 类结构

```python
class Strategy20MultiSymbol(IStrategy):
    """多交易对共享资金池策略"""

    def __init__(
        self,
        symbols: List[str],           # 交易对列表
        position_manager: IPositionManager,
        discount: float = 0.001,
        max_positions: int = 10       # 全局限制
    ):
        self.symbols = symbols
        self._symbol_states: Dict[str, SymbolState] = {}  # 每个交易对的状态
        self._global_holdings: Dict[str, Dict] = {}       # 全局持仓
        self._available_capital: Decimal = Decimal("0")

    def run_backtest(
        self,
        klines_dict: Dict[str, pd.DataFrame],  # symbol -> K线数据
        initial_capital: Decimal = Decimal("10000")
    ) -> Dict:
        """执行多交易对回测"""
        pass
```

### 4.2 数据结构

```python
@dataclass
class SymbolState:
    """单交易对状态"""
    symbol: str
    pending_buy_order: Optional[PendingOrder]
    pending_sell_orders: Dict[str, Dict]  # order_id -> sell_order
    holdings: Dict[str, Dict]              # order_id -> holding
    completed_orders: List[Dict]
    indicators_cache: Dict                 # 缓存的指标值
```

### 4.3 回测结果结构

```python
{
    "global": {
        "initial_capital": 10000,
        "final_capital": 11234.56,
        "total_return": 12.35,
        "total_orders": 45,
        "win_rate": 0.62,
        "max_drawdown": 0.08,
        "apr": 0.15,
        "apy": 0.16
    },
    "by_symbol": {
        "ETHUSDT": {
            "orders": 15,
            "win_rate": 0.67,
            "profit_loss": 456.78,
            "holdings": 2
        },
        "BTCUSDT": {...},
        "HYPEUSDT": {...},
        "BNBUSDT": {...}
    },
    "orders": [...]  # 所有订单列表
}
```

## 5. 验收标准

### 5.1 功能验收
- [ ] 4个交易对同时回测，资金池正确共享
- [ ] 全局持仓数不超过 max_positions
- [ ] 每个交易对独立输出统计
- [ ] 合并汇总统计正确
- [ ] run_strategy_backtest 命令正常执行

### 5.2 性能验收
- [ ] 4交易对1年4h数据回测 < 60秒
- [ ] 内存占用 < 2GB

### 5.3 兼容性验收
- [ ] 不影响现有策略16/19功能
- [ ] 与现有回测框架兼容

## 6. 迭代信息

| 项目 | 值 |
|------|-----|
| 迭代编号 | 045 |
| 迭代名称 | 策略20-多交易对共享资金池 |
| 优先级 | P0 |
| 创建日期 | 2026-01-14 |
| 基础策略 | 策略16 (v4.0) |
| 默认交易对 | ETHUSDT, BTCUSDT, HYPEUSDT, BNBUSDT |
