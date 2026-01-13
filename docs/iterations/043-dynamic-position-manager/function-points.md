# 功能点清单 - 迭代043：动态复利仓位管理

## 功能点总览

| 序号 | 功能点 | 模块 | 优先级 | 状态 |
|------|--------|------|--------|------|
| F01 | IPositionManager接口定义 | 核心模块 | P0 | 待开发 |
| F02 | DynamicPositionManager实现 | 核心模块 | P0 | 待开发 |
| F03 | 边界条件处理 | 核心模块 | P0 | 待开发 |
| F04 | Strategy19仓位管理器集成 | 策略模块 | P0 | 待开发 |
| F05 | 移除固定position_size参数 | 策略模块 | P0 | 待开发 |
| F06 | 单元测试 | 测试模块 | P0 | 待开发 |

---

## 功能点详情

### F01: IPositionManager接口定义

**描述**：定义仓位管理器的抽象接口

**所属模块**：`strategy_adapter/core/position_manager.py`

**输入**：
- `available_cash: Decimal` - 当前可用现金
- `max_positions: int` - 最大持仓数量
- `current_positions: int` - 当前持仓数量

**输出**：
- `Decimal` - 单笔仓位金额，0表示跳过

**接口签名**：
```python
class IPositionManager(Protocol):
    def calculate_position_size(
        self,
        available_cash: Decimal,
        max_positions: int,
        current_positions: int
    ) -> Decimal: ...
```

**验收标准**：
- [ ] 接口符合Protocol规范
- [ ] 文档字符串完整

---

### F02: DynamicPositionManager实现

**描述**：实现动态复利仓位计算逻辑

**所属模块**：`strategy_adapter/core/position_manager.py`

**核心公式**：
```
position_size = available_cash / (max_positions - current_positions)
```

**构造参数**：
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| min_position | Decimal | 0 | 最小仓位金额（可选） |

**验收标准**：
- [ ] 正常场景计算正确
- [ ] 实现IPositionManager接口
- [ ] 日志记录完整

---

### F03: 边界条件处理

**描述**：处理各种边界场景

**所属模块**：`strategy_adapter/core/position_manager.py`

**边界场景**：

| 场景 | 条件 | 返回值 | 行为 |
|------|------|--------|------|
| 无可用资金 | available_cash ≤ 0 | 0 | 跳过挂单 |
| 持仓已满 | current_positions ≥ max_positions | 0 | 跳过挂单 |
| 低于最小金额 | position_size < min_position | 0 | 跳过挂单 |

**验收标准**：
- [ ] 可用现金≤0返回0
- [ ] 持仓已满返回0
- [ ] 低于最小金额返回0

---

### F04: Strategy19仓位管理器集成

**描述**：将仓位管理器注入Strategy19

**所属模块**：`strategy_adapter/strategies/strategy19_conservative_entry.py`

**修改点**：
1. 构造函数增加`position_manager`参数
2. `_get_actual_position_size`方法调用仓位管理器
3. 保留`consolidation_multiplier`逻辑（在基础金额上倍增）

**新构造函数**：
```python
def __init__(
    self,
    position_manager: IPositionManager,
    discount: float = 0.001,
    max_positions: int = 10,
    consolidation_multiplier: int = 3
): ...
```

**验收标准**：
- [ ] 仓位管理器正确注入
- [ ] 动态仓位计算正确
- [ ] 震荡期倍数正确应用

---

### F05: 移除固定position_size参数

**描述**：清理旧的固定仓位逻辑

**所属模块**：`strategy_adapter/strategies/strategy19_conservative_entry.py`

**删除项**：
- `position_size`构造参数
- `self.position_size`属性

**验收标准**：
- [ ] position_size参数已移除
- [ ] 无残留的固定仓位代码

---

### F06: 单元测试

**描述**：编写仓位管理器单元测试

**所属模块**：`strategy_adapter/tests/test_position_manager.py`

**测试用例**：

| 测试场景 | 输入 | 期望输出 |
|----------|------|----------|
| 正常计算 | cash=10000, max=10, curr=0 | 1000 |
| 部分持仓 | cash=9000, max=10, curr=1 | 1000 |
| 资金不足 | cash=0, max=10, curr=0 | 0 |
| 持仓已满 | cash=10000, max=10, curr=10 | 0 |
| 复利效应 | cash=11000, max=10, curr=1 | 1222.22 |
| 风控效应 | cash=7000, max=10, curr=1 | 777.78 |

**验收标准**：
- [ ] 所有测试用例通过
- [ ] 测试覆盖率≥90%

---

## 依赖关系

```
F01 (接口) ─────┬───> F02 (实现)
                │
                └───> F03 (边界处理)
                        │
                        v
                      F04 (策略集成) ───> F05 (移除旧代码)
                        │
                        v
                      F06 (测试)
```

## 统计信息

- **P0功能点**：6个
- **P1功能点**：0个
- **总计**：6个功能点
