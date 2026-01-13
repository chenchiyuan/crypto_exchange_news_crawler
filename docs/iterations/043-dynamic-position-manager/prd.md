# 迭代043：动态复利仓位管理

## 1. 概述

### 1.1 背景
当前策略16/19使用固定金额仓位管理（如每笔1000 USDT），存在以下问题：
- 盈利后资金闲置，无法发挥复利效应
- 亏损后继续使用固定金额，可能加速亏损

### 1.2 目标
实现动态复利仓位管理策略：
- **复利效应**：盈利后单笔金额自动增大
- **风控效应**：亏损后单笔金额自动减小
- **可插拔性**：独立模块设计，支持配置给任意策略

### 1.3 核心公式
```
单笔仓位金额 = 当前可用现金 / (max_positions - 正在持仓数量)
```

## 2. 需求详情

### 2.1 核心功能

#### 2.1.1 动态仓位计算
- **输入**：当前可用现金、最大持仓数、当前持仓数
- **输出**：单笔挂单金额
- **公式**：`available_cash / (max_positions - current_positions)`

#### 2.1.2 边界处理
| 场景 | 处理方式 |
|------|----------|
| 可用现金 ≤ 0 | 跳过挂单，返回0 |
| 持仓数 = max_positions | 跳过挂单（持仓已满） |
| 计算结果 < min_position（可选） | 跳过挂单 |

#### 2.1.3 接口设计
```python
class IPositionManager(Protocol):
    """仓位管理器接口"""

    def calculate_position_size(
        self,
        available_cash: Decimal,
        max_positions: int,
        current_positions: int
    ) -> Decimal:
        """计算单笔仓位金额"""
        ...
```

### 2.2 实现类

#### 2.2.1 DynamicPositionManager
```python
class DynamicPositionManager(IPositionManager):
    """动态复利仓位管理器"""

    def __init__(self, min_position: Decimal = Decimal("0")):
        """
        Args:
            min_position: 最小仓位金额（可选），低于此值跳过挂单
        """
        self.min_position = min_position

    def calculate_position_size(
        self,
        available_cash: Decimal,
        max_positions: int,
        current_positions: int
    ) -> Decimal:
        """
        计算单笔仓位金额

        Returns:
            Decimal: 仓位金额，0表示跳过挂单
        """
        # 边界检查
        if available_cash <= 0:
            return Decimal("0")

        available_slots = max_positions - current_positions
        if available_slots <= 0:
            return Decimal("0")

        # 计算仓位
        position_size = available_cash / available_slots

        # 最小金额检查（可选）
        if self.min_position > 0 and position_size < self.min_position:
            return Decimal("0")

        return position_size
```

### 2.3 策略集成

#### 2.3.1 依赖注入方式
```python
class Strategy19ConservativeEntry:
    def __init__(
        self,
        position_manager: IPositionManager,  # 注入仓位管理器
        discount: float = 0.001,
        max_positions: int = 10,
        consolidation_multiplier: int = 3
    ):
        self.position_manager = position_manager
        ...

    def _get_actual_position_size(self, cycle_phase: str) -> Decimal:
        """获取实际挂单金额"""
        # 使用仓位管理器计算基础金额
        base_size = self.position_manager.calculate_position_size(
            available_cash=self._available_capital,
            max_positions=self.max_positions,
            current_positions=len(self._holdings)
        )

        if base_size == 0:
            return Decimal("0")

        # 应用震荡期倍数
        if cycle_phase == 'consolidation':
            return base_size * self.consolidation_multiplier

        return base_size
```

### 2.4 向后兼容

移除固定仓位模式，仅保留动态复利模式：
- 删除 `position_size` 构造参数
- 使用 `position_manager` 替代

## 3. 示例场景

### 3.1 复利效应示例
```
初始状态：
- 初始资金：10000 USDT
- max_positions：10
- 当前持仓：0

第1笔挂单：
- 可用现金：10000
- 单笔金额：10000 / (10 - 0) = 1000 USDT

盈利后：
- 可用现金：11000（盈利1000）
- 当前持仓：1
- 单笔金额：11000 / (10 - 1) = 1222 USDT（自动增大）
```

### 3.2 风控效应示例
```
亏损后：
- 可用现金：9000（亏损1000）
- 当前持仓：1
- 单笔金额：9000 / (10 - 1) = 1000 USDT（自动减小）

继续亏损：
- 可用现金：7000（再亏损2000）
- 当前持仓：1
- 单笔金额：7000 / (10 - 1) = 778 USDT（进一步减小）
```

## 4. 验收标准

### 4.1 功能验收
- [ ] 动态仓位计算公式正确：`available_cash / (max_positions - current_positions)`
- [ ] 可用现金≤0时返回0，跳过挂单
- [ ] 持仓已满时返回0，跳过挂单
- [ ] 策略19能通过依赖注入使用仓位管理器

### 4.2 复利效应验证
- [ ] 盈利后单笔金额增大
- [ ] 亏损后单笔金额减小

### 4.3 兼容性验收
- [ ] 策略19回测功能正常
- [ ] 现有测试通过

## 5. 技术决策记录

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 边界处理 | 跳过挂单 | 简单直接，避免复杂异常处理 |
| 集成方式 | 独立模块注入 | 可插拔性好，支持多策略复用 |
| 兼容性 | 仅动态模式 | 简化代码，专注复利效应 |

## 6. 文档信息

- **迭代编号**：043
- **创建日期**：2026-01-13
- **关联策略**：Strategy19ConservativeEntry
- **依赖迭代**：041（策略19-保守入场策略）
