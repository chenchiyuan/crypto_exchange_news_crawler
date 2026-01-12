# 架构设计: 策略14-优化买入策略

## 文档信息
- **版本**: 1.0
- **创建日期**: 2026-01-11
- **迭代编号**: 030

## 1. 组件设计

### 1.1 OptimizedEntryStrategy

```python
class OptimizedEntryStrategy(IStrategy):
    """
    优化买入策略（策略14）

    价格分布：首档base_price，第2档低first_gap(4%)，后续每档低interval(1%)
    金额分布：1×, 3×, 9×, 27×, 剩余全部
    止盈止损：沿用策略12（2%止盈，6%止损）
    """

    def __init__(
        self,
        base_amount: Decimal = Decimal("100"),
        multiplier: float = 3.0,
        order_count: int = 5,
        first_gap: float = 0.04,
        interval: float = 0.01,
        first_order_discount: float = 0.003,
        take_profit_rate: float = 0.02,
        stop_loss_rate: float = 0.06
    ):
        ...
```

### 1.2 核心方法

| 方法 | 功能 |
|------|------|
| `_calculate_prices()` | 计算5档挂单价格 |
| `_calculate_amounts()` | 计算5档挂单金额（第5档动态） |
| `process_kline()` | 处理单根K线（复用策略12逻辑） |
| `run_optimized_backtest()` | 执行回测 |

## 2. 数据流

```
K线数据 → 指标计算 → 价格计算 → 金额计算 → 创建挂单
                                    ↓
                            检查成交 → 止盈/止损
```

## 3. 关键决策

| 决策 | 选项 | 决定 | 理由 |
|------|------|------|------|
| 价格计算 | 复用/内置 | 内置 | 逻辑简单，无需抽象 |
| 金额计算 | 固定/动态 | 动态 | 第5档需要实时计算 |
| 代码复用 | 继承/复制 | 复制修改 | 避免继承复杂性 |

## Q-Gate 4: ✅ 通过
