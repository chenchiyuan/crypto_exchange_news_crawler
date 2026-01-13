# 任务计划 - 迭代043：动态复利仓位管理

## 任务总览

| 阶段 | 任务数 | 预估工时 | 状态 |
|------|--------|----------|------|
| Phase 1: 核心模块开发 | 3 | 1h | 待开发 |
| Phase 2: 策略集成 | 2 | 0.5h | 待开发 |
| Phase 3: 测试与验证 | 2 | 0.5h | 待开发 |
| **总计** | **7** | **2h** | - |

---

## Phase 1: 核心模块开发

### Task 1.1: 创建仓位管理器模块文件

**功能点**: F01 IPositionManager接口定义

**描述**: 创建 `strategy_adapter/core/position_manager.py` 文件，定义 `IPositionManager` 接口协议

**文件**: `strategy_adapter/core/position_manager.py`

**实现内容**:
```python
from typing import Protocol
from decimal import Decimal

class IPositionManager(Protocol):
    """仓位管理器接口协议"""

    def calculate_position_size(
        self,
        available_cash: Decimal,
        max_positions: int,
        current_positions: int
    ) -> Decimal:
        """计算单笔仓位金额"""
        ...
```

**验收标准**:
- [ ] 文件创建成功
- [ ] 接口定义符合Protocol规范
- [ ] 文档字符串完整

**预估工时**: 15min

**状态**: 待开发

---

### Task 1.2: 实现DynamicPositionManager

**功能点**: F02 DynamicPositionManager实现

**描述**: 在同一文件中实现动态复利仓位管理器

**文件**: `strategy_adapter/core/position_manager.py`

**实现内容**:
```python
class DynamicPositionManager:
    """动态复利仓位管理器"""

    def __init__(self, min_position: Decimal = Decimal("0")):
        self.min_position = min_position

    def calculate_position_size(
        self,
        available_cash: Decimal,
        max_positions: int,
        current_positions: int
    ) -> Decimal:
        # 核心公式: available_cash / (max_positions - current_positions)
        ...
```

**验收标准**:
- [ ] 正常场景计算正确
- [ ] 实现符合IPositionManager接口
- [ ] 日志记录完整

**依赖**: Task 1.1

**预估工时**: 20min

**状态**: 待开发

---

### Task 1.3: 实现边界条件处理

**功能点**: F03 边界条件处理

**描述**: 在 `calculate_position_size` 方法中实现边界条件处理

**边界场景**:

| 场景 | 条件 | 返回值 |
|------|------|--------|
| 无可用资金 | available_cash ≤ 0 | 0 |
| 持仓已满 | current_positions ≥ max_positions | 0 |
| 低于最小金额 | position_size < min_position | 0 |

**验收标准**:
- [ ] 可用现金≤0返回0
- [ ] 持仓已满返回0
- [ ] 低于最小金额返回0
- [ ] 每种边界情况有日志记录

**依赖**: Task 1.2

**预估工时**: 15min

**状态**: 待开发

---

## Phase 2: 策略集成

### Task 2.1: 修改Strategy19构造函数

**功能点**: F04 Strategy19仓位管理器集成, F05 移除固定position_size参数

**描述**: 修改 `Strategy19ConservativeEntry` 的构造函数，注入仓位管理器

**文件**: `strategy_adapter/strategies/strategy19_conservative_entry.py`

**修改点**:
1. 移除 `position_size` 参数
2. 添加 `position_manager: IPositionManager` 参数
3. 更新 `__init__` 方法

**新构造函数**:
```python
def __init__(
    self,
    position_manager: IPositionManager,
    discount: float = 0.001,
    max_positions: int = 10,
    consolidation_multiplier: int = 3
):
    self.position_manager = position_manager
    self.discount = Decimal(str(discount))
    self.max_positions = max_positions
    self.consolidation_multiplier = consolidation_multiplier
    # 初始化状态管理（从Strategy16复制必要代码）
```

**验收标准**:
- [ ] position_size参数已移除
- [ ] position_manager参数已添加
- [ ] 无残留的固定仓位代码

**依赖**: Task 1.3

**预估工时**: 15min

**状态**: 待开发

---

### Task 2.2: 重写_get_actual_position_size方法

**功能点**: F04 Strategy19仓位管理器集成

**描述**: 重写 `_get_actual_position_size` 方法，调用仓位管理器计算

**文件**: `strategy_adapter/strategies/strategy19_conservative_entry.py`

**实现逻辑**:
```python
def _get_actual_position_size(self, cycle_phase: Optional[str]) -> Decimal:
    # 1. 调用仓位管理器计算基础金额
    base_size = self.position_manager.calculate_position_size(
        available_cash=self._available_capital,
        max_positions=self.max_positions,
        current_positions=len(self._holdings)
    )

    # 2. 返回0则跳过
    if base_size == 0:
        return Decimal("0")

    # 3. 应用震荡期倍数
    if cycle_phase == 'consolidation':
        return base_size * self.consolidation_multiplier

    return base_size
```

**验收标准**:
- [ ] 仓位管理器正确调用
- [ ] 动态仓位计算正确
- [ ] 震荡期倍数正确应用
- [ ] 返回0时正确跳过挂单

**依赖**: Task 2.1

**预估工时**: 15min

**状态**: 待开发

---

## Phase 3: 测试与验证

### Task 3.1: 编写仓位管理器单元测试

**功能点**: F06 单元测试

**描述**: 创建 `strategy_adapter/tests/test_position_manager.py`，编写单元测试

**文件**: `strategy_adapter/tests/test_position_manager.py`

**测试用例**:

| 测试场景 | 输入 | 期望输出 |
|----------|------|----------|
| test_normal_calculation | cash=10000, max=10, curr=0 | 1000 |
| test_partial_positions | cash=9000, max=10, curr=1 | 1000 |
| test_zero_cash | cash=0, max=10, curr=0 | 0 |
| test_negative_cash | cash=-100, max=10, curr=0 | 0 |
| test_positions_full | cash=10000, max=10, curr=10 | 0 |
| test_compound_profit | cash=11000, max=10, curr=1 | 1222.22 |
| test_risk_control | cash=7000, max=10, curr=1 | 777.78 |
| test_min_position | cash=100, max=10, curr=0, min=50 | 10（若<50则返回0） |

**验收标准**:
- [ ] 所有测试用例通过
- [ ] 测试覆盖率≥90%
- [ ] 边界条件全覆盖

**依赖**: Task 1.3

**预估工时**: 20min

**状态**: 待开发

---

### Task 3.2: 集成验证

**描述**: 验证Strategy19与仓位管理器的集成效果

**验证内容**:
1. 使用DynamicPositionManager实例化Strategy19
2. 执行回测验证动态仓位计算
3. 验证复利效应和风控效应

**验证代码示例**:
```python
from strategy_adapter.core.position_manager import DynamicPositionManager
from strategy_adapter.strategies import Strategy19ConservativeEntry

# 创建仓位管理器
position_manager = DynamicPositionManager()

# 创建策略
strategy = Strategy19ConservativeEntry(
    position_manager=position_manager,
    max_positions=10,
    consolidation_multiplier=3
)

# 执行回测
result = strategy.run_backtest(klines_df, initial_capital=10000)
```

**验收标准**:
- [ ] Strategy19回测功能正常
- [ ] 动态仓位计算生效
- [ ] 复利/风控效应可验证

**依赖**: Task 2.2, Task 3.1

**预估工时**: 15min

**状态**: 待开发

---

## 任务依赖关系

```
Task 1.1 (接口定义)
    │
    v
Task 1.2 (实现类)
    │
    v
Task 1.3 (边界处理) ──────> Task 3.1 (单元测试)
    │                           │
    v                           │
Task 2.1 (构造函数修改)         │
    │                           │
    v                           │
Task 2.2 (方法重写) <───────────┘
    │
    v
Task 3.2 (集成验证)
```

---

## 风险与注意事项

### 风险点
1. **Strategy16继承问题**：Strategy19继承自Strategy16，需确保不破坏继承链
2. **资金计算精度**：使用Decimal确保精度，避免浮点误差

### 注意事项
1. 所有金额计算必须使用 `Decimal` 类型
2. 日志记录使用现有的 `logger` 实例
3. 保持与现有代码风格一致

---

## 文档信息

- **迭代编号**: 043
- **创建日期**: 2026-01-13
- **总任务数**: 7
- **预估总工时**: 2小时
- **关联文档**:
  - PRD: `docs/iterations/043-dynamic-position-manager/prd.md`
  - 架构: `docs/iterations/043-dynamic-position-manager/architecture.md`
