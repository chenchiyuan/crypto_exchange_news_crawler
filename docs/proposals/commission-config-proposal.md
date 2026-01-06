# 手续费可配置化方案

**提议日期**: 2026-01-06
**提议人**: PowerBy Engineer
**状态**: 待用户确认

---

## 一、现状分析 (Current State)

### 1.1 手续费计算现状

**已实现的手续费逻辑** ✅:
- **开仓手续费**: `open_commission = position_size × 0.001`（在create_order时计算）
- **平仓手续费**: `close_commission = close_value × 0.001`（在update_order时计算）
- **盈亏扣费**: `profit_loss -= (open_commission + close_commission)`（在Order.calculate_pnl()中扣除）

**代码位置**:
```python
# strategy_adapter/core/unified_order_manager.py:135
commission_rate = Decimal("0.001")  # 硬编码
open_commission = position_size * commission_rate

# strategy_adapter/core/unified_order_manager.py:222
commission_rate = Decimal("0.001")  # 硬编码
close_value = order.close_price * order.quantity
order.close_commission = close_value * commission_rate

# strategy_adapter/models/order.py:163-164
# 扣除手续费
self.profit_loss -= (self.open_commission + self.close_commission)
```

### 1.2 问题识别

**核心问题**:
- ❌ 手续费率硬编码为0.001（千一），不可配置
- ❌ 无法适应不同交易所的手续费政策
- ❌ 无法测试不同手续费场景对策略的影响

**影响范围**:
- UnifiedOrderManager.create_order()
- UnifiedOrderManager.update_order()

---

## 二、技术分析 (Your Analysis)

### 2.1 核心矛盾

**手续费配置的层级选择**:
- **Strategy层配置**: 每个策略可以有不同的手续费率（符合策略独立性）
- **OrderManager层配置**: 统一管理手续费（符合单一职责）
- **全局配置**: 使用Django settings（符合配置外部化）

**关键考虑**:
1. 手续费率是交易环境属性，不是策略属性
2. 回测和实盘可能使用不同的手续费率
3. 应该保持向后兼容（默认值0.001）

### 2.2 设计原则

遵循以下原则：
1. **配置外部化**: 手续费率应该可以从外部传入
2. **向后兼容**: 默认值保持0.001，现有代码无需修改
3. **单一职责**: UnifiedOrderManager负责应用手续费率
4. **测试友好**: 可以轻松测试不同手续费场景

---

## 三、方案选项 (Solution Options)

### 方案A：在UnifiedOrderManager初始化时配置（推荐）

**方案描述**:
在UnifiedOrderManager的`__init__`方法中接受`commission_rate`参数，并在整个生命周期中使用。

**实现方式**:
```diff
# strategy_adapter/core/unified_order_manager.py

class UnifiedOrderManager:
-   def __init__(self):
+   def __init__(self, commission_rate: Decimal = Decimal("0.001")):
        """
        初始化订单管理器
+
+       Args:
+           commission_rate (Decimal): 手续费率，默认0.001（千一）
        """
        self._orders: Dict[str, Order] = {}
+       self.commission_rate = commission_rate

    def create_order(self, ...):
        # ...
-       commission_rate = Decimal("0.001")
-       open_commission = position_size * commission_rate
+       open_commission = position_size * self.commission_rate
        # ...

    def update_order(self, order_id: str, close_signal: Dict):
        # ...
-       commission_rate = Decimal("0.001")
        close_value = order.close_price * order.quantity
-       order.close_commission = close_value * commission_rate
+       order.close_commission = close_value * self.commission_rate
        # ...
```

**调用示例**:
```python
# 使用默认手续费（千一）
order_manager = UnifiedOrderManager()

# 自定义手续费率（如万五）
order_manager = UnifiedOrderManager(commission_rate=Decimal("0.0005"))

# 在StrategyAdapter中使用
adapter = StrategyAdapter(
    strategy=DDPSZStrategy(),
    order_manager=UnifiedOrderManager(commission_rate=Decimal("0.001"))
)
```

**命令行支持**:
```diff
# strategy_adapter/management/commands/run_strategy_backtest.py

parser.add_argument(
    '--position-size',
    type=float,
    default=100.0,
    help='单笔买入金额（默认: 100 USDT）'
)
+parser.add_argument(
+   '--commission-rate',
+   type=float,
+   default=0.001,
+   help='手续费率（默认: 0.001，即千一）'
+)

# 在handle方法中
+commission_rate = Decimal(str(options['commission_rate']))
+order_manager = UnifiedOrderManager(commission_rate=commission_rate)
-adapter = StrategyAdapter(strategy)
+adapter = StrategyAdapter(strategy, order_manager=order_manager)
```

**优点**:
- ✅ 简单直接，修改最少（仅修改UnifiedOrderManager）
- ✅ 向后兼容（默认值0.001）
- ✅ 易于测试（可以注入不同的commission_rate）
- ✅ 符合依赖注入原则
- ✅ 配置灵活（支持命令行参数）

**缺点**:
- ⚠️ 需要在创建UnifiedOrderManager时传入参数

---

### 方案B：使用Django Settings全局配置

**方案描述**:
在Django settings中定义全局手续费率，UnifiedOrderManager从settings读取。

**实现方式**:
```diff
# listing_monitor_project/settings.py
+# 策略回测配置
+STRATEGY_COMMISSION_RATE = Decimal("0.001")  # 默认千一手续费

# strategy_adapter/core/unified_order_manager.py
+from django.conf import settings

class UnifiedOrderManager:
    def __init__(self):
        self._orders: Dict[str, Order] = {}
+       self.commission_rate = getattr(
+           settings,
+           'STRATEGY_COMMISSION_RATE',
+           Decimal("0.001")
+       )
```

**优点**:
- ✅ 全局统一配置
- ✅ 符合Django最佳实践

**缺点**:
- ❌ 不够灵活（无法针对单次回测调整）
- ❌ 测试时需要修改settings
- ❌ 引入了对Django框架的依赖

---

### 方案C：在IStrategy接口中定义

**方案描述**:
在IStrategy接口中添加`get_commission_rate()`方法，由策略定义手续费率。

**实现方式**:
```python
class IStrategy(ABC):
    # 现有方法...

    @abstractmethod
    def get_commission_rate(self) -> Decimal:
        """返回手续费率"""
        pass

class DDPSZStrategy(IStrategy):
    def get_commission_rate(self) -> Decimal:
        return Decimal("0.001")
```

**优点**:
- ✅ 策略级别配置
- ✅ 可以针对不同策略使用不同手续费

**缺点**:
- ❌ 手续费是环境属性，不是策略属性（违反单一职责）
- ❌ 需要修改IStrategy接口（破坏性变更）
- ❌ 所有策略都要实现此方法

---

## 四、推荐方案

### ✅ 推荐：方案A（UnifiedOrderManager初始化时配置）

**推荐理由**:
1. **简单性**: 修改范围最小，仅涉及UnifiedOrderManager
2. **灵活性**: 可以针对每次回测设置不同手续费
3. **测试友好**: 单元测试可以轻松注入不同手续费率
4. **向后兼容**: 默认值保持0.001，现有代码无需修改
5. **符合设计原则**:
   - 依赖注入（Dependency Injection）
   - 单一职责（Single Responsibility）
   - 开闭原则（Open-Closed Principle）

**实施成本**: 低（约1小时）
**技术风险**: 低（仅修改内部实现）
**业务风险**: 无（向后兼容）

---

## 五、实施计划

### 5.1 任务分解

- [ ] **任务1**: 修改UnifiedOrderManager.__init__() - 0.2小时
  - 添加commission_rate参数（默认值0.001）
  - 保存为实例属性

- [ ] **任务2**: 修改create_order()方法 - 0.1小时
  - 使用self.commission_rate替代硬编码

- [ ] **任务3**: 修改update_order()方法 - 0.1小时
  - 使用self.commission_rate替代硬编码

- [ ] **任务4**: 添加命令行参数支持 - 0.3小时
  - run_strategy_backtest.py添加--commission-rate参数
  - 传递给UnifiedOrderManager

- [ ] **任务5**: 更新文档和注释 - 0.2小时
  - 更新UnifiedOrderManager文档字符串
  - 添加使用示例

- [ ] **任务6**: 测试验证 - 0.1小时
  - 测试默认手续费（向后兼容）
  - 测试自定义手续费（如万五）

### 5.2 验收标准

- [ ] commission_rate可以在UnifiedOrderManager初始化时配置
- [ ] 默认值为0.001（向后兼容）
- [ ] 命令行支持--commission-rate参数
- [ ] 测试不同手续费率场景（0.001, 0.0005, 0.0015）
- [ ] 盈亏计算正确反映手续费影响

### 5.3 回归测试检查

- [ ] 运行现有回测命令，结果与修改前一致（使用默认手续费）
- [ ] 测试position_size=100和1000场景
- [ ] 验证盈亏率计算正确

---

## 六、风险评估

### 6.1 技术风险

**风险1**: 默认值传递错误
- **影响**: 中
- **概率**: 低
- **缓解**: 充分的单元测试

**风险2**: Decimal类型转换错误
- **影响**: 低
- **概率**: 低
- **缓解**: 使用Decimal(str(...))确保精度

### 6.2 业务风险

**风险**: 无显著业务风险
- **原因**: 向后兼容，默认行为不变

---

## 七、决策点

### 需要您确认的问题

1. **手续费率配置层级**：
   - 您是否同意在UnifiedOrderManager层级配置手续费率？
   - 建议：✅ 同意（符合单一职责）

2. **命令行参数**：
   - 是否需要在run_strategy_backtest命令中添加--commission-rate参数？
   - 建议：✅ 需要（方便回测不同手续费场景）

3. **默认值**：
   - 默认手续费率保持0.001（千一）是否合适？
   - 建议：✅ 合适（符合主流交易所费率）

### 请您决策

请选择：
- [ ] 采用推荐方案A，立即实施
- [ ] 修改方案：[说明修改要求]
- [ ] 暂缓实施：[说明原因]
- [ ] 其他：[说明具体要求]

---

**提议版本**: v1.0
**关联迭代**: 013 (策略适配层)
**关联文档**:
- architecture.md#4.3 核心组件模块
- prd.md#功能点清单
