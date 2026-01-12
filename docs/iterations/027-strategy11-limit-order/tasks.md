# 任务计划: 策略11 - 限价挂单买卖机制

## 文档信息

| 属性 | 值 |
|------|-----|
| 迭代编号 | 027 |
| 迭代名称 | strategy11-limit-order |
| 版本 | 1.0 |
| 创建日期 | 2026-01-10 |
| 关联架构 | architecture.md |
| 总任务数 | 12 |

---

## 任务总览

| 阶段 | 任务数 | 说明 |
|------|--------|------|
| 阶段1: 数据结构 | 2 | PendingOrder模型、模块导出 |
| 阶段2: 核心组件 | 3 | 价格计算器、挂单管理器、限价卖出 |
| 阶段3: 策略实现 | 2 | LimitOrderStrategy、DDPSZAdapter扩展 |
| 阶段4: 配置集成 | 2 | ProjectLoader扩展、回测命令集成 |
| 阶段5: 测试验证 | 3 | 单元测试、集成测试、回测验证 |

---

## 阶段1: 数据结构 (基础层)

### TASK-027-001: 实现PendingOrder数据结构

**状态**: [ ] 未开始

**目标**: 定义限价挂单的数据结构

**文件**: `strategy_adapter/models/pending_order.py`

**功能点**: FP-027-001

**实现要点**:
```python
@dataclass
class PendingOrder:
    order_id: str           # 格式: "pending_{timestamp}_{index}"
    price: Decimal          # 挂单价格
    amount: Decimal         # 挂单金额(USDT)
    quantity: Decimal       # 挂单数量 = amount / price
    status: str             # pending, filled, cancelled
    side: str               # buy, sell
    frozen_capital: Decimal # 冻结资金
    kline_index: int        # 创建时的K线索引
    created_at: int         # 创建时间戳(毫秒)
    filled_at: Optional[int] = None
    parent_order_id: Optional[str] = None  # 卖出挂单关联的持仓ID
```

**验收标准**:
- [ ] PendingOrder可正常实例化
- [ ] 支持序列化为dict
- [ ] 字段类型正确

---

### TASK-027-002: 更新models模块导出

**状态**: [ ] 未开始

**目标**: 在models/__init__.py中导出PendingOrder

**文件**: `strategy_adapter/models/__init__.py`

**依赖**: TASK-027-001

**实现要点**:
- 添加 `from .pending_order import PendingOrder`
- 更新 `__all__` 列表

**验收标准**:
- [ ] `from strategy_adapter.models import PendingOrder` 可正常导入

---

## 阶段2: 核心组件 (业务层)

### TASK-027-003: 实现LimitOrderPriceCalculator

**状态**: [ ] 未开始

**目标**: 实现挂单价格计算器

**文件**: `strategy_adapter/core/limit_order_price_calculator.py`

**功能点**: FP-027-007, FP-027-008, FP-027-012

**实现要点**:
```python
class LimitOrderPriceCalculator:
    def __init__(self, order_count: int = 10, order_interval: float = 0.005):
        ...

    def calculate_buy_prices(self, p5: Decimal, mid: Decimal) -> List[Decimal]:
        """
        第1笔: (P5 + mid) / 2
        第N笔: 第1笔 × (1 - (N-1) × interval)
        """

    def calculate_sell_price(
        self, buy_price: Decimal, ema25: Decimal, take_profit_rate: float = 0.05
    ) -> Decimal:
        """返回 min(buy_price × 1.05, ema25)"""
```

**验收标准**:
- [ ] calculate_buy_prices返回正确数量的价格
- [ ] 价格按0.5%递减
- [ ] calculate_sell_price返回较低值

**单元测试**:
- 测试首笔价格 = (P5+mid)/2
- 测试第10笔价格 = 首笔 × (1-9×0.005)
- 测试卖出价格取较低值

---

### TASK-027-004: 实现LimitOrderManager

**状态**: [ ] 未开始

**目标**: 实现限价挂单管理器

**文件**: `strategy_adapter/core/limit_order_manager.py`

**功能点**: FP-027-002, FP-027-003, FP-027-004, FP-027-005, FP-027-006

**依赖**: TASK-027-001

**实现要点**:
```python
class LimitOrderManager:
    def __init__(self, position_size: Decimal = Decimal("100")):
        self._pending_orders: Dict[str, PendingOrder] = {}
        self._available_capital: Decimal = Decimal("0")
        self._frozen_capital: Decimal = Decimal("0")

    def initialize(self, initial_capital: Decimal) -> None
    def create_buy_order(self, price, kline_index, timestamp) -> Optional[PendingOrder]
    def cancel_all_buy_orders(self) -> Decimal  # 返回解冻金额
    def check_buy_order_fill(self, order, kline_low, kline_high) -> bool
    def create_sell_order(self, parent_order, sell_price, kline_index, timestamp) -> PendingOrder
    def update_sell_order_price(self, order_id, new_price) -> None
    def check_sell_order_fill(self, order, kline_low, kline_high) -> bool
    def get_pending_buy_orders(self) -> List[PendingOrder]
    def get_pending_sell_orders(self) -> List[PendingOrder]
```

**验收标准**:
- [ ] create_buy_order正确冻结资金
- [ ] 资金不足时返回None
- [ ] cancel_all_buy_orders正确解冻资金
- [ ] check_buy_order_fill判断 low <= price <= high
- [ ] available_capital和frozen_capital属性正确

**单元测试**:
- 测试资金冻结/解冻
- 测试资金不足场景
- 测试成交判断逻辑

---

### TASK-027-005: 实现LimitOrderExit

**状态**: [ ] 未开始

**目标**: 实现限价卖出条件

**文件**: `strategy_adapter/exits/limit_order_exit.py`

**功能点**: FP-027-013, FP-027-014, FP-027-015

**依赖**: TASK-027-003

**实现要点**:
```python
class LimitOrderExit(IExitCondition):
    def __init__(self, take_profit_rate: float = 0.05, ema_period: int = 25):
        self.take_profit_rate = take_profit_rate
        self.price_calculator = LimitOrderPriceCalculator()

    def check(self, order, kline, indicators, current_timestamp) -> Optional[ExitSignal]:
        """
        1. 计算卖出价格 = min(买入价×1.05, EMA25)
        2. 判断成交: low <= 卖出价 <= high
        3. 成交返回ExitSignal，否则None
        """

    def get_type(self) -> str:
        return "limit_order_exit"
```

**验收标准**:
- [ ] 实现IExitCondition接口
- [ ] 卖出价格计算正确
- [ ] 成交判断逻辑正确

---

## 阶段3: 策略实现 (集成层)

### TASK-027-006: 实现LimitOrderStrategy

**状态**: [ ] 未开始

**目标**: 实现策略11的核心逻辑

**文件**: `strategy_adapter/strategies/limit_order_strategy.py`

**功能点**: FP-027-009, FP-027-010, FP-027-011

**依赖**: TASK-027-003, TASK-027-004, TASK-027-005

**实现要点**:
```python
class LimitOrderStrategy(IStrategy):
    def __init__(
        self,
        order_count: int = 10,
        order_interval: float = 0.005,
        position_size: Decimal = Decimal("100"),
        take_profit_rate: float = 0.05
    ):
        self.order_manager = LimitOrderManager(position_size)
        self.price_calculator = LimitOrderPriceCalculator(order_count, order_interval)
        self.exit_condition = LimitOrderExit(take_profit_rate)

    def get_strategy_name(self) -> str:
        return "LimitOrder-Strategy11"

    def get_strategy_version(self) -> str:
        return "1.0"

    def generate_buy_signals(self, klines, indicators) -> List[Dict]:
        """
        每根K线处理:
        1. 检查上根K线挂单是否成交
        2. 取消未成交挂单
        3. 计算新挂单价格
        4. 创建新挂单
        返回成交的买入信号
        """

    def generate_sell_signals(self, klines, indicators, open_orders) -> List[Dict]:
        """
        检查持仓的卖出条件
        """

    def calculate_position_size(self, signal, available_capital, current_price) -> Decimal:
        return self.order_manager.position_size
```

**验收标准**:
- [ ] 实现IStrategy接口
- [ ] 每根K线正确处理挂单流程
- [ ] 资金不足时记录日志
- [ ] 成交的挂单正确转换为买入信号

---

### TASK-027-007: 扩展DDPSZAdapter支持策略11

**状态**: [ ] 未开始

**目标**: 在DDPSZAdapter中支持strategy_id=11

**文件**: `strategy_adapter/adapters/ddpsz_adapter.py`

**功能点**: FP-027-017

**依赖**: TASK-027-006

**实现要点**:
- 在 `__init__` 中识别 strategy_id=11
- 路由到 LimitOrderStrategy
- 或者：在工厂中根据strategy_id创建不同策略

**方案选择**:
推荐在适配层外部（如run_strategy_backtest命令中）根据strategy_id选择策略类，保持DDPSZAdapter不变。

**验收标准**:
- [ ] strategy_id=11可正确识别
- [ ] 路由到LimitOrderStrategy

---

## 阶段4: 配置集成 (接口层)

### TASK-027-008: 扩展ProjectLoader解析新参数

**状态**: [ ] 未开始

**目标**: 支持解析order_count、order_interval参数

**文件**: `strategy_adapter/core/project_loader.py`

**功能点**: FP-027-016

**实现要点**:
```python
def _parse_strategy(self, data: Dict) -> StrategyConfig:
    # 现有逻辑...

    # 新增: 解析entry中的order_count和order_interval
    entry = data.get('entry', {})
    order_count = entry.get('order_count', 10)
    order_interval = entry.get('order_interval', 0.005)
```

**验收标准**:
- [ ] order_count解析正确，默认10
- [ ] order_interval解析正确，默认0.005
- [ ] limit_order_exit类型被识别

---

### TASK-027-009: 集成到回测命令

**状态**: [ ] 未开始

**目标**: 在run_strategy_backtest中支持策略11

**文件**: `strategy_adapter/management/commands/run_strategy_backtest.py`

**功能点**: FP-027-018

**依赖**: TASK-027-006, TASK-027-007, TASK-027-008

**实现要点**:
- 根据strategy_id=11创建LimitOrderStrategy
- 传递order_count、order_interval参数
- 集成LimitOrderExit

**验收标准**:
- [ ] `--config strategy11_limit_order.json` 可正常执行
- [ ] 回测结果正确输出

---

## 阶段5: 测试验证 (质量保障)

### TASK-027-010: 编写单元测试

**状态**: [ ] 未开始

**目标**: 为核心组件编写单元测试

**文件**: `strategy_adapter/tests/test_limit_order_*.py`

**测试用例**:

| 测试文件 | 测试场景 |
|----------|----------|
| test_limit_order_price_calculator.py | 首笔价格计算、批量价格计算、卖出价格计算 |
| test_limit_order_manager.py | 资金冻结/解冻、成交判断、挂单取消 |
| test_limit_order_exit.py | 卖出条件判断、价格取较低值 |

**验收标准**:
- [ ] 测试覆盖率 > 80%
- [ ] 所有测试通过

---

### TASK-027-011: 编写集成测试

**状态**: [ ] 未开始

**目标**: 验证策略11的完整流程

**文件**: `strategy_adapter/tests/test_strategy11_integration.py`

**依赖**: TASK-027-010

**测试场景**:
- 单根K线挂10笔单
- 挂单成交转持仓
- 持仓卖出成交
- 资金不足处理
- CSV数据回测

**验收标准**:
- [ ] 集成测试全部通过
- [ ] 资金流正确

---

### TASK-027-012: 执行回测验证

**状态**: [ ] 未开始

**目标**: 使用真实CSV数据验证策略11

**依赖**: TASK-027-009, TASK-027-011

**执行步骤**:
```bash
python manage.py run_strategy_backtest --config strategy_adapter/configs/strategy11_limit_order.json
```

**验收标准**:
- [ ] 回测完成无报错
- [ ] 统计指标合理
- [ ] 性能满足目标（1个月<60秒）

---

## 任务依赖关系

```
TASK-027-001 (PendingOrder)
      ↓
TASK-027-002 (models导出)
      ↓
TASK-027-003 (PriceCalculator) ─────────┐
      ↓                                  │
TASK-027-004 (LimitOrderManager) ←───────┘
      ↓
TASK-027-005 (LimitOrderExit)
      ↓
TASK-027-006 (LimitOrderStrategy)
      ↓
TASK-027-007 (DDPSZAdapter扩展) ───→ TASK-027-008 (ProjectLoader)
                                            ↓
                                    TASK-027-009 (回测命令)
                                            ↓
                                    TASK-027-010 (单元测试)
                                            ↓
                                    TASK-027-011 (集成测试)
                                            ↓
                                    TASK-027-012 (回测验证)
```

---

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 性能不达标 | 中 | 使用numpy向量化操作 |
| 资金计算错误 | 高 | 单元测试全覆盖 |
| 与现有策略冲突 | 低 | 独立实现，不修改现有代码 |

---

## 验收清单

### 功能验收

| ID | 验收项 | 状态 |
|----|--------|------|
| AC-1 | 策略11配置文件可正常加载 | [ ] |
| AC-2 | 每根K线正确生成N笔挂单（默认10笔） | [ ] |
| AC-3 | 挂单价格计算正确 | [ ] |
| AC-4 | 资金不足时挂单失败并记录日志 | [ ] |
| AC-5 | 下根K线正确判断挂单是否成交 | [ ] |
| AC-6 | 卖出价格=min(买入价×1.05, EMA25) | [ ] |
| AC-7 | 卖出挂单每根K线动态更新 | [ ] |
| AC-8 | 回测结果可保存到数据库 | [ ] |
| AC-9 | Web界面可查看回测结果 | [ ] |

### 性能验收

| 指标 | 目标值 | 实际值 | 状态 |
|------|--------|--------|------|
| 单根K线处理时间 | < 10ms | - | [ ] |
| 1个月1m数据回测 | < 60秒 | - | [ ] |
| 内存占用 | < 2GB | - | [ ] |

---

## 附录

### A. 相关文档

- PRD: `prd.md`
- 功能点清单: `function-points.md`
- 架构设计: `architecture.md`
- 需求澄清: `clarifications.md`

### B. 变更历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|----------|------|
| 1.0 | 2026-01-10 | 初始版本 | AI助手 |
