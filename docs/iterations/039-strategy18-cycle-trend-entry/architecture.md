# 架构设计 - 策略18：周期趋势入场策略

## 文档信息
- **迭代编号**: 039
- **创建日期**: 2026-01-13

---

## 1. 整体架构

### 1.1 组件图

```
┌─────────────────────────────────────────────────────────────────┐
│                    Strategy18CycleTrendEntry                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  指标计算模块    │  │  周期状态判断    │  │  订单管理模块    │  │
│  │                 │  │                 │  │                 │  │
│  │ - EMA7/25/99    │  │ - 42周期占比    │  │ - 双挂单管理    │  │
│  │ - cycle_phases  │  │ - EMA25斜率    │  │ - 持仓管理      │  │
│  │ - β值计算       │  │ - 状态标记      │  │ - 止盈止损      │  │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘  │
│           │                    │                    │           │
│           └────────────────────┼────────────────────┘           │
│                                ▼                                │
│                    ┌─────────────────────┐                      │
│                    │    run_backtest()   │                      │
│                    │    主回测循环        │                      │
│                    └─────────────────────┘                      │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────┐
                    │   回测结果输出       │
                    │   orders/statistics │
                    └─────────────────────┘
```

### 1.2 数据流

```
K线数据 (DataFrame)
        │
        ▼
┌───────────────────┐
│   指标计算        │
│ EMA7/25/99        │
│ cycle_phases      │
│ β值               │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐     ┌───────────────────┐
│  周期占比计算     │────►│  EMA25斜率计算    │
│  (最近42根)       │     │  (最近6根)        │
└─────────┬─────────┘     └─────────┬─────────┘
          │                         │
          └────────────┬────────────┘
                       ▼
              ┌───────────────────┐
              │  周期状态判断     │
              │  bull/bear/cons.  │
              └─────────┬─────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   [上涨周期]      [下跌周期]      [震荡周期]
        │               │               │
        ▼               │               │
   双挂单买入           │               │
   (EMA7+EMA25)         │               │
        │               │               │
        └───────────────┴───────────────┘
                        │
                        ▼
              ┌───────────────────┐
              │    持仓检查       │
              │  止损→止盈→周期  │
              └───────────────────┘
```

---

## 2. 核心类设计

### 2.1 Strategy18CycleTrendEntry

```python
class Strategy18CycleTrendEntry(IStrategy):
    """
    策略18：周期趋势入场策略

    基于42周期占比和EMA25斜率双重确认的趋势跟踪策略。

    Attributes:
        position_size: 单笔仓位金额（USDT）
        max_positions: 最大持仓数量
        cycle_window: 周期占比统计窗口（默认42）
        bull_threshold: 上涨周期占比阈值（默认40%）
        bear_threshold: 下跌周期占比阈值（默认40%）
        slope_window: EMA25斜率比较窗口（默认6）
        take_profit_pct: 止盈比例（默认10%）
        stop_loss_pct: 止损比例（默认3%）
    """

    STRATEGY_ID = 'strategy_18'
    STRATEGY_NAME = '周期趋势入场'
    STRATEGY_VERSION = '1.0'

    def __init__(self, ...): ...

    # 核心方法
    def run_backtest(self, klines_df, initial_capital) -> Dict: ...

    # 指标计算
    def _calculate_indicators(self, klines_df) -> Dict[str, pd.Series]: ...

    # 周期状态判断
    def _calculate_cycle_distribution(self, cycle_phases, window=42) -> Dict[str, float]: ...
    def _calculate_ema_slopes(self, ema25_series) -> np.ndarray: ...
    def _is_slope_highest(self, slopes, window=6) -> bool: ...
    def _is_slope_lowest(self, slopes, window=6) -> bool: ...
    def _determine_cycle_state(self, distribution, is_highest, is_lowest) -> str: ...

    # 订单管理
    def _create_pending_orders(self, ema7, ema25, timestamp, kline_index) -> List[PendingOrder]: ...
    def _check_order_fill(self, order, low) -> bool: ...
    def _check_stop_loss(self, holding, low) -> Optional[Dict]: ...
    def _check_take_profit(self, holding, high) -> Optional[Dict]: ...
    def _check_cycle_exit(self, holding, cycle_state, ema7, ema25, prev_ema7, prev_ema25) -> bool: ...

    # 结果生成
    def _generate_result(self, initial_capital, kline_count) -> Dict: ...
```

### 2.2 状态管理

```python
# 挂单管理（每根K线最多2笔）
_pending_orders: List[PendingOrder] = []

# 持仓管理
_holdings: Dict[str, Dict] = {
    'order_id': {
        'buy_price': Decimal,
        'quantity': Decimal,
        'amount': Decimal,
        'buy_timestamp': int,
        'kline_index': int,
        'metadata': {
            'cross_triggered': bool,  # 是否已触发EMA下穿
            'pending_exit': bool,     # 是否等待下根K线卖出
        }
    }
}

# 已完成订单
_completed_orders: List[Dict] = []

# 可用资金
_available_capital: Decimal
```

---

## 3. 关键算法

### 3.1 周期状态判断

```python
def _determine_cycle_state(self, distribution, is_slope_highest, is_slope_lowest) -> str:
    """
    判断当前周期状态

    Returns:
        'bull': 上涨周期
        'bear': 下跌周期
        'consolidation': 震荡周期
    """
    bull_strong_pct = distribution.get('bull_strong', 0)
    bear_strong_pct = distribution.get('bear_strong', 0)

    if bull_strong_pct > self.bull_threshold and is_slope_highest:
        return 'bull'
    elif bear_strong_pct > self.bear_threshold and is_slope_lowest:
        return 'bear'
    else:
        return 'consolidation'
```

### 3.2 双挂单机制

```python
def _create_pending_orders(self, ema7, ema25, timestamp, kline_index) -> List[PendingOrder]:
    """
    创建双挂单（EMA7 + EMA25）
    """
    orders = []

    # 挂单1: EMA7价格
    if self._available_capital >= self.position_size:
        order1 = PendingOrder(
            order_id=f"pending_{timestamp}_{kline_index}_ema7",
            price=ema7,
            amount=self.position_size,
            quantity=self.position_size / ema7,
            status=PendingOrderStatus.PENDING,
            side=PendingOrderSide.BUY,
            frozen_capital=self.position_size,
            kline_index=kline_index,
            created_at=timestamp,
            metadata={'entry_type': 'ema7'}
        )
        orders.append(order1)
        self._available_capital -= self.position_size

    # 挂单2: EMA25价格
    if self._available_capital >= self.position_size:
        order2 = PendingOrder(
            order_id=f"pending_{timestamp}_{kline_index}_ema25",
            price=ema25,
            amount=self.position_size,
            quantity=self.position_size / ema25,
            status=PendingOrderStatus.PENDING,
            side=PendingOrderSide.BUY,
            frozen_capital=self.position_size,
            kline_index=kline_index,
            created_at=timestamp,
            metadata={'entry_type': 'ema25'}
        )
        orders.append(order2)
        self._available_capital -= self.position_size

    return orders
```

### 3.3 卖出优先级处理

```python
# 在每根K线处理持仓时的检查顺序
for order_id, holding in self._holdings.items():
    # 1. 检查止损（最高优先级）
    stop_loss_result = self._check_stop_loss(holding, low)
    if stop_loss_result:
        holdings_to_close.append(stop_loss_result)
        continue

    # 2. 检查止盈
    take_profit_result = self._check_take_profit(holding, high)
    if take_profit_result:
        holdings_to_close.append(take_profit_result)
        continue

    # 3. 检查周期状态止盈
    if self._check_cycle_exit(holding, cycle_state, ema7, ema25, prev_ema7, prev_ema25):
        # 标记下根K线以open卖出
        holding['metadata']['pending_exit'] = True
```

---

## 4. 配置文件格式

```json
{
  "project_name": "策略18-周期趋势入场",
  "description": "基于42周期占比和EMA25斜率双重确认的趋势跟踪策略",
  "version": "1.0",
  "created_at": "2026-01-13",
  "iteration": "039",

  "backtest_config": {
    "symbol": "ETHUSDT",
    "interval": "4h",
    "market_type": "futures",
    "start_date": "2025-01-01",
    "end_date": "2025-12-31",
    "initial_cash": 10000,
    "commission_rate": 0.001
  },

  "capital_management": {
    "mode": "shared",
    "position_size_mode": "fixed",
    "position_size": 1000,
    "max_positions": 10
  },

  "strategies": [
    {
      "id": "strategy_18",
      "name": "周期趋势入场",
      "type": "strategy-18-cycle-trend",
      "enabled": true,
      "entry": {
        "cycle_window": 42,
        "bull_threshold": 40,
        "bear_threshold": 40,
        "slope_window": 6,
        "description": "上涨周期(bull_strong>40%且EMA25斜率最高)时双挂单(EMA7+EMA25)"
      },
      "exits": [
        {
          "type": "stop_loss",
          "params": { "percentage": 3 },
          "description": "3%止损"
        },
        {
          "type": "take_profit",
          "params": { "percentage": 10 },
          "description": "10%止盈"
        },
        {
          "type": "cycle_state",
          "params": {},
          "description": "非上涨周期+EMA7下穿EMA25→下根K线open卖出"
        }
      ]
    }
  ]
}
```

---

## 5. 文件结构

```
strategy_adapter/
├── strategies/
│   ├── __init__.py                    # 添加Strategy18导出
│   └── strategy18_cycle_trend_entry.py  # 🆕 策略18实现
├── configs/
│   └── strategy18_cycle_trend.json    # 🆕 策略18配置
└── tests/
    └── test_strategy18.py             # 🆕 策略18测试（可选）
```

---

## 6. 回测主循环伪代码

```python
def run_backtest(self, klines_df, initial_capital):
    # 初始化
    self._available_capital = initial_capital
    self._pending_orders = []
    self._holdings = {}
    self._completed_orders = []

    # 计算指标
    indicators = self._calculate_indicators(klines_df)

    # 逐K线处理
    for i in range(42, len(klines_df)):  # 从第42根开始（需要42根历史）
        kline = klines_df.iloc[i]
        timestamp = int(klines_df.index[i].timestamp() * 1000)

        # 获取当前指标
        ema7 = indicators['ema7'].iloc[i]
        ema25 = indicators['ema25'].iloc[i]
        cycle_phases = indicators['cycle_phases'][:i+1]

        # Step 1: 处理待卖出订单（上根K线标记的）
        self._process_pending_exits(kline['open'], timestamp)

        # Step 2: 检查挂单成交
        self._process_pending_orders(kline['low'], timestamp, i)

        # Step 3: 检查持仓止盈止损
        self._process_holdings(kline, indicators, i, timestamp)

        # Step 4: 判断周期状态
        distribution = self._calculate_cycle_distribution(cycle_phases)
        slopes = self._calculate_ema_slopes(indicators['ema25'].iloc[:i+1])
        is_highest = self._is_slope_highest(slopes)
        is_lowest = self._is_slope_lowest(slopes)
        cycle_state = self._determine_cycle_state(distribution, is_highest, is_lowest)

        # Step 5: 创建新挂单（仅上涨周期）
        if cycle_state == 'bull':
            self._cancel_pending_orders()  # 取消旧挂单
            new_orders = self._create_pending_orders(ema7, ema25, timestamp, i)
            self._pending_orders.extend(new_orders)
        else:
            self._cancel_pending_orders()  # 非上涨周期取消所有挂单

    return self._generate_result(initial_capital, len(klines_df))
```

---

## 7. 架构决策记录

| 决策 | 选项 | 选择 | 理由 |
|-----|------|-----|------|
| 策略实现方式 | Mixin/独立类 | 独立类 | 逻辑独立，便于维护 |
| 周期占比计算 | 复用Service/内联 | 内联 | 避免依赖，保持独立 |
| 挂单管理 | 复用LimitOrderManager/内置 | 内置 | 双挂单逻辑简单，无需复杂管理器 |
| 周期状态止盈 | 立即卖出/下根K线卖出 | 下根K线open | 符合用户需求 |
