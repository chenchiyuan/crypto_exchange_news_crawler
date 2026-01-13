# 验收清单 - 迭代043：动态复利仓位管理

## 1. 功能验收

### 1.1 核心功能

| 检查项 | 验收标准 | 状态 |
|--------|----------|------|
| 动态仓位公式 | `available_cash / (max_positions - current_positions)` 计算正确 | ⬜ |
| 复利效应 | 盈利后可用现金增加 → 单笔金额自动增大 | ⬜ |
| 风控效应 | 亏损后可用现金减少 → 单笔金额自动减小 | ⬜ |

### 1.2 边界处理

| 检查项 | 验收标准 | 状态 |
|--------|----------|------|
| 无可用资金 | available_cash ≤ 0 时返回 0，跳过挂单 | ⬜ |
| 持仓已满 | current_positions ≥ max_positions 时返回 0 | ⬜ |
| 最小金额检查 | position_size < min_position 时返回 0（可选功能） | ⬜ |

### 1.3 策略集成

| 检查项 | 验收标准 | 状态 |
|--------|----------|------|
| 依赖注入 | Strategy19 通过构造函数接受 IPositionManager | ⬜ |
| 参数移除 | position_size 参数已从 Strategy19 中移除 | ⬜ |
| 震荡期倍增 | consolidation 周期正确应用 multiplier | ⬜ |

---

## 2. 接口验收

### 2.1 IPositionManager 接口

| 检查项 | 验收标准 | 状态 |
|--------|----------|------|
| Protocol定义 | 使用 `typing.Protocol` 定义接口 | ⬜ |
| 方法签名 | `calculate_position_size(available_cash, max_positions, current_positions) -> Decimal` | ⬜ |
| 文档字符串 | 完整的 docstring 说明参数和返回值 | ⬜ |

### 2.2 DynamicPositionManager 实现

| 检查项 | 验收标准 | 状态 |
|--------|----------|------|
| 接口实现 | 实现 IPositionManager 接口 | ⬜ |
| 构造参数 | 支持可选的 min_position 参数 | ⬜ |
| 类型安全 | 所有金额使用 Decimal 类型 | ⬜ |

---

## 3. 测试验收

### 3.1 单元测试

| 测试场景 | 输入 | 期望输出 | 状态 |
|----------|------|----------|------|
| 正常计算 | cash=10000, max=10, curr=0 | 1000 | ⬜ |
| 部分持仓 | cash=9000, max=10, curr=1 | 1000 | ⬜ |
| 资金为零 | cash=0, max=10, curr=0 | 0 | ⬜ |
| 资金为负 | cash=-100, max=10, curr=0 | 0 | ⬜ |
| 持仓已满 | cash=10000, max=10, curr=10 | 0 | ⬜ |
| 复利效应 | cash=11000, max=10, curr=1 | 1222.22 | ⬜ |
| 风控效应 | cash=7000, max=10, curr=1 | 777.78 | ⬜ |

### 3.2 集成测试

| 检查项 | 验收标准 | 状态 |
|--------|----------|------|
| 策略实例化 | Strategy19 可正常使用 DynamicPositionManager 实例化 | ⬜ |
| 回测执行 | run_backtest 方法正常执行无异常 | ⬜ |
| 结果正确 | 回测结果中仓位金额动态变化 | ⬜ |

---

## 4. 代码质量验收

### 4.1 代码规范

| 检查项 | 验收标准 | 状态 |
|--------|----------|------|
| 类型注解 | 所有公开方法有完整类型注解 | ⬜ |
| 文档字符串 | 所有类和公开方法有 docstring | ⬜ |
| 代码风格 | 符合项目现有代码风格 | ⬜ |
| 日志记录 | 关键操作有日志记录 | ⬜ |

### 4.2 兼容性

| 检查项 | 验收标准 | 状态 |
|--------|----------|------|
| Strategy16 不变 | Strategy16LimitEntry 代码未修改 | ⬜ |
| 现有测试通过 | 项目现有测试全部通过 | ⬜ |
| 导入正常 | 模块可正常导入无循环依赖 | ⬜ |

---

## 5. 文件清单

### 5.1 新增文件

| 文件路径 | 用途 | 状态 |
|----------|------|------|
| `strategy_adapter/core/position_manager.py` | 仓位管理器模块 | ⬜ |
| `strategy_adapter/tests/test_position_manager.py` | 单元测试 | ⬜ |

### 5.2 修改文件

| 文件路径 | 修改内容 | 状态 |
|----------|----------|------|
| `strategy_adapter/strategies/strategy19_conservative_entry.py` | 注入仓位管理器 | ⬜ |

---

## 6. 验收示例代码

```python
from decimal import Decimal
from strategy_adapter.core.position_manager import DynamicPositionManager
from strategy_adapter.strategies import Strategy19ConservativeEntry

# 1. 测试仓位管理器
pm = DynamicPositionManager()

# 正常计算
assert pm.calculate_position_size(Decimal("10000"), 10, 0) == Decimal("1000")

# 边界: 无资金
assert pm.calculate_position_size(Decimal("0"), 10, 0) == Decimal("0")

# 边界: 持仓已满
assert pm.calculate_position_size(Decimal("10000"), 10, 10) == Decimal("0")

# 复利效应
result = pm.calculate_position_size(Decimal("11000"), 10, 1)
assert result == Decimal("11000") / Decimal("9")  # ≈1222.22

# 2. 测试策略集成
strategy = Strategy19ConservativeEntry(
    position_manager=pm,
    max_positions=10,
    consolidation_multiplier=3
)

# 验证策略可正常实例化
assert strategy.position_manager is pm
assert strategy.max_positions == 10

print("✅ 所有验收测试通过")
```

---

## 7. 验收签核

| 阶段 | 验收人 | 日期 | 状态 |
|------|--------|------|------|
| 功能验收 | - | - | ⬜ |
| 测试验收 | - | - | ⬜ |
| 代码审查 | - | - | ⬜ |
| 最终签核 | - | - | ⬜ |

---

## 文档信息

- **迭代编号**: 043
- **创建日期**: 2026-01-13
- **关联任务**: `docs/iterations/043-dynamic-position-manager/tasks.md`
