# 策略14限价挂单卖出改造方案

## 文档信息
- **创建日期**: 2026-01-11
- **状态**: 待审批
- **迭代编号**: 030

---

## A. 现状分析 (Current State)

### A.1 当前卖出逻辑

策略14的`process_kline`方法当前流程：

```
Step 1: 检查买入挂单是否成交
  ├─ 遍历待成交的买入挂单
  ├─ 如果价格在K线[low, high]范围内
  └─ 成交并添加到持仓 (_holdings)

Step 2: 检查持仓止盈 (市价成交)
  ├─ 遍历所有持仓
  ├─ 如果 high >= 买入价×1.02
  └─ 直接按止盈价成交并平仓

Step 2.5: 检查持仓止损 (市价成交)
  ├─ 遍历所有持仓
  ├─ 如果 low <= 买入价×0.94
  └─ 直接按止损价成交并平仓

Step 3: 取消所有未成交的买入挂单

Step 4: 创建新的买入挂单
```

### A.2 核心问题

**问题**: 当前使用市价卖出，而非限价挂单卖出

- ❌ 在Step 2/2.5中，一旦价格触及止盈/止损，立即按该价格成交
- ❌ 没有创建卖出挂单
- ❌ 没有使用`LimitOrderManager`的卖出挂单功能

### A.3 与策略11/12的对比

| 特性 | 策略11/12 | 策略14（当前）| 策略14（期望）|
|------|-----------|--------------|---------------|
| 买入方式 | 限价挂单 | 限价挂单 | 限价挂单 |
| 卖出方式 | 限价挂单 | **市价成交** | **限价挂单** |
| 卖出价格计算 | min(买入价×1.05, EMA25) | 买入价×1.02或0.94 | 买入价×1.02或0.94 |
| 挂单时机 | 买入成交后立即挂单 | 无挂单 | 买入成交后立即挂单 |
| 价格调整 | 每根K线更新EMA25 | 无 | 每根K线检查是否需要止损 |

---

## B. 分析 (Your Analysis)

### B.1 关键挑战

1. **挂单时机**: 需要在买入成交的**同一根K线**立即创建卖出挂单
2. **价格调整**: 每根K线需检查是否从止盈价调整为止损价
3. **成交判断**: 下根K线起判断卖出挂单是否成交
4. **资金管理**: 卖出挂单成交后需正确释放冻结资金

### B.2 核心矛盾

- 策略14的止盈/止损是固定比例（2%/6%），不依赖指标
- 但仍需要限价挂单机制，确保成交逻辑的一致性
- 需要支持止盈→止损的价格调整（当价格跌破止损线时）

---

## C. 方案选项 (Solution Options)

### 方案一：独立实现卖出挂单逻辑（推荐）

**方案描述**:

在`OptimizedEntryStrategy`中直接使用`LimitOrderManager`的卖出挂单API：

```python
def process_kline(...):
    # Step 1: 检查买入挂单是否成交
    for order in pending_buy_orders:
        if check_buy_order_fill(order, low, high):
            filled_order = fill_buy_order(order)
            # 添加到持仓
            self._holdings[filled_order.order_id] = {...}

            # +++ 立即创建卖出挂单（2%止盈价） +++
            sell_price = filled_order.price * Decimal("1.02")
            self.order_manager.create_sell_order(
                parent_order_id=filled_order.order_id,
                sell_price=sell_price,
                quantity=filled_order.quantity,
                kline_index=kline_index,
                timestamp=timestamp
            )

    # Step 2: 检查卖出挂单是否需要调整为止损价
    for order_id, holding in self._holdings.items():
        sell_order = self.order_manager.get_sell_order_by_parent(order_id)
        if sell_order:
            stop_loss_price = holding['buy_price'] * Decimal("0.94")
            # 如果当前价跌破止损线，调整挂单价格
            if low <= stop_loss_price:
                self.order_manager.update_sell_order_price(
                    sell_order.order_id,
                    stop_loss_price
                )

    # Step 3: 检查卖出挂单是否成交
    pending_sell_orders = self.order_manager.get_pending_sell_orders()
    for sell_order in pending_sell_orders:
        if check_sell_order_fill(sell_order, low, high):
            result = fill_sell_order(
                sell_order.order_id,
                timestamp,
                holding['buy_price']
            )
            # 从持仓中移除
            del self._holdings[sell_order.parent_order_id]

    # Step 4: 取消未成交的买入挂单
    # Step 5: 创建新的买入挂单
```

**流程图**:

```mermaid
sequenceDiagram
    participant K线n
    participant 买入挂单
    participant 持仓
    participant 卖出挂单

    K线n->>买入挂单: 检查是否成交
    买入挂单->>持仓: 成交，添加持仓
    持仓->>卖出挂单: 立即创建卖出挂单(2%)

    Note over K线n+1: 下一根K线
    K线n+1->>卖出挂单: 检查是否需要调整为止损
    卖出挂单->>卖出挂单: 如跌破止损线，调整价格
    K线n+1->>卖出挂单: 检查是否成交
    卖出挂单->>持仓: 成交，移除持仓
```

**优点**:
- ✅ 直接使用现有的`LimitOrderManager` API
- ✅ 代码改动集中在`process_kline`方法
- ✅ 与策略11/12的卖出逻辑一致
- ✅ 支持止盈→止损的价格调整

**缺点**:
- ⚠️ 需要调整`process_kline`的执行顺序（先检查卖出，再取消买入挂单）
- ⚠️ 止损调整逻辑与策略11/12不同（固定比例 vs EMA25）

---

### 方案二：创建专用的FixedRateSellExit条件

**方案描述**:

创建一个新的Exit条件类`FixedRateSellExit`，封装固定比例止盈/止损逻辑：

```python
class FixedRateSellExit(IExitCondition):
    """固定比例止盈/止损的限价卖出条件"""

    def __init__(
        self,
        take_profit_rate: float = 0.02,
        stop_loss_rate: float = 0.06
    ):
        self.take_profit_rate = take_profit_rate
        self.stop_loss_rate = stop_loss_rate

    def calculate_sell_price(
        self,
        buy_price: Decimal,
        current_price: Decimal
    ) -> Decimal:
        """计算卖出价格：默认止盈，跌破止损线则止损"""
        stop_loss_price = buy_price * (1 - self.stop_loss_rate)
        take_profit_price = buy_price * (1 + self.take_profit_rate)

        if current_price <= stop_loss_price:
            return stop_loss_price
        else:
            return take_profit_price
```

在策略14中集成：

```python
def __init__(self, ...):
    self.sell_exit = FixedRateSellExit(
        take_profit_rate=0.02,
        stop_loss_rate=0.06
    )

def process_kline(...):
    # Step 1: 买入成交后，使用sell_exit计算价格并挂单
    sell_price = self.sell_exit.calculate_sell_price(
        buy_price,
        current_price=close
    )
    self.order_manager.create_sell_order(...)

    # Step 2: 每根K线调整卖出价格
    sell_price = self.sell_exit.calculate_sell_price(
        buy_price,
        current_price=close
    )
    self.order_manager.update_sell_order_price(...)
```

**优点**:
- ✅ 封装性更好，止盈/止损逻辑独立
- ✅ 可复用于其他固定比例策略
- ✅ 符合Exit条件的设计模式

**缺点**:
- ⚠️ 需要新建文件`fixed_rate_sell_exit.py`
- ⚠️ 增加代码复杂度（多一层抽象）
- ⚠️ 对于策略14来说，逻辑足够简单，抽象可能过度

---

## D. 推荐方案 (Your Recommendation)

**推荐方案一：独立实现卖出挂单逻辑**

**理由**:

1. **简单直接**: 策略14的止盈/止损逻辑非常简单（固定比例），不需要额外抽象
2. **易于维护**: 所有逻辑集中在`process_kline`中，便于理解和调试
3. **快速实现**: 直接使用现有的`LimitOrderManager` API，无需新建文件
4. **一致性**: 与策略11/12的卖出挂单机制保持一致

**实现步骤**:

1. 调整`process_kline`的执行顺序：
   - Step 1: 检查买入挂单成交 → **立即创建卖出挂单**
   - Step 2: 检查卖出挂单是否需要调整为止损价
   - Step 3: 检查卖出挂单是否成交
   - Step 4: 取消未成交的买入挂单
   - Step 5: 创建新的买入挂单

2. 移除当前的市价止盈/止损逻辑（Step 2和Step 2.5）

3. 新增卖出挂单成交后的资金管理（已在`LimitOrderManager.fill_sell_order`中实现）

---

## E. 验收标准

| AC编号 | 验收标准 | 验证方法 |
|--------|----------|----------|
| AC-001 | 买入成交后，立即创建卖出挂单（2%止盈价） | 回测日志验证 |
| AC-002 | 下根K线起，开始判断卖出挂单是否成交 | 单元测试 |
| AC-003 | 当价格跌破止损线，卖出挂单价格调整为止损价 | 回测验证 |
| AC-004 | 卖出挂单成交后，正确释放冻结资金 | 回测统计验证 |
| AC-005 | 取消买入挂单不影响卖出挂单 | 单元测试 |

---

## F. 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 卖出挂单成交后资金计算错误 | 高 | 详细测试资金流转逻辑 |
| 止盈→止损调整时机错误 | 中 | 使用K线low价格判断 |
| 持仓和卖出挂单状态不一致 | 中 | 成交后立即从_holdings删除 |
