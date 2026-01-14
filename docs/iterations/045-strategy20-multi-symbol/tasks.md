# 策略20 开发任务计划

## 迭代信息

| 项目 | 值 |
|------|-----|
| 迭代编号 | 045 |
| 迭代名称 | 策略20-多交易对共享资金池 |
| 创建日期 | 2026-01-14 |
| 基础策略 | 策略16 (v4.0) |

---

## 阶段概览

| 阶段 | 名称 | 任务数 | 状态 |
|------|------|--------|------|
| P5-1 | 核心组件开发 | 4 | 待开始 |
| P5-2 | 逻辑提取与复用 | 2 | 待开始 |
| P5-3 | 主策略类实现 | 3 | 待开始 |
| P5-4 | 集成与注册 | 2 | 待开始 |
| P5-5 | 测试与验证 | 2 | 待开始 |

---

## 阶段 P5-1: 核心组件开发

**目标**: 创建全局资金管理和持仓跟踪的基础组件

### TASK-045-001: 创建 GlobalCapitalManager

**文件**: `strategy_adapter/core/global_capital_manager.py`

**实现要点**:
```python
class GlobalCapitalManager:
    """全局资金池管理器"""

    def __init__(self, initial_capital: Decimal):
        self._total_capital = initial_capital
        self._available_cash = initial_capital
        self._frozen_cash = Decimal("0")

    @property
    def available_cash(self) -> Decimal: ...

    def freeze(self, amount: Decimal) -> bool: ...
    def unfreeze(self, amount: Decimal): ...
    def settle(self, frozen_amount: Decimal, actual_amount: Decimal): ...
    def add_profit(self, profit: Decimal): ...
```

**验收标准**:
- [ ] freeze/unfreeze/settle 方法正确处理资金变动
- [ ] available_cash 属性实时反映可用资金

**状态**: 待开始

---

### TASK-045-002: 创建 GlobalPositionTracker

**文件**: `strategy_adapter/core/global_position_tracker.py`

**实现要点**:
```python
class GlobalPositionTracker:
    """全局持仓跟踪器"""

    def __init__(self, max_positions: int = 10):
        self._max_positions = max_positions
        self._holdings: Dict[str, int] = {}  # symbol -> count

    @property
    def total_holdings(self) -> int: ...

    def can_open_position(self) -> bool: ...
    def add_holding(self, symbol: str): ...
    def remove_holding(self, symbol: str): ...
    def calculate_position_size(self, available_cash: Decimal) -> Decimal: ...
```

**验收标准**:
- [ ] total_holdings 正确统计所有交易对持仓
- [ ] can_open_position 在达到上限时返回 False
- [ ] calculate_position_size 使用公式 `available_cash / (max - total)`

**状态**: 待开始

---

### TASK-045-003: 创建 SymbolState 数据类

**文件**: `strategy_adapter/models.py` (追加)

**实现要点**:
```python
@dataclass
class SymbolState:
    """单交易对状态"""
    symbol: str
    pending_buy_order: Optional[PendingOrder] = None
    pending_sell_orders: Dict[str, Dict] = field(default_factory=dict)
    holdings: Dict[str, Dict] = field(default_factory=dict)
    completed_orders: List[Dict] = field(default_factory=list)
    indicators_cache: Dict = field(default_factory=dict)

    # 统计字段
    total_orders: int = 0
    winning_orders: int = 0
    total_profit_loss: Decimal = field(default_factory=lambda: Decimal("0"))
```

**验收标准**:
- [ ] SymbolState 可正确存储单交易对的所有状态
- [ ] 支持默认值初始化

**状态**: 待开始

---

### TASK-045-004: 更新 models __init__.py

**文件**: `strategy_adapter/models/__init__.py`

**实现要点**:
- 导出 SymbolState
- 确保向后兼容

**状态**: 待开始

---

## 阶段 P5-2: 逻辑提取与复用

**目标**: 将策略16的买卖逻辑提取为可复用的工具函数

### TASK-045-005: 创建 entry_exit_logic.py

**文件**: `strategy_adapter/utils/entry_exit_logic.py`

**实现要点**:
```python
def calculate_base_price(
    p5: Decimal, close: Decimal, inertia_mid: Decimal
) -> Decimal:
    """计算基准价格: min(p5, close, (p5+mid)/2)"""

def calculate_order_price(
    base_price: Decimal, discount: Decimal
) -> Decimal:
    """计算挂单价格: base_price × (1 - discount)"""

def calculate_sell_price(
    cycle_phase: str, ema25: Decimal, p95: Decimal
) -> Tuple[Decimal, str]:
    """根据周期计算卖出挂单价和原因"""

def should_skip_entry(cycle_phase: Optional[str]) -> bool:
    """判断是否跳过入场 (bear_warning)"""
```

**验收标准**:
- [ ] 函数逻辑与策略16完全一致
- [ ] 单元测试覆盖所有边界情况

**状态**: 待开始

---

### TASK-045-006: 创建 indicator_calculator.py

**文件**: `strategy_adapter/utils/indicator_calculator.py`

**实现要点**:
```python
def calculate_indicators(klines_df: pd.DataFrame) -> Dict[str, pd.Series]:
    """
    计算策略所需的技术指标

    Returns:
        Dict with keys: ema7, ema25, ema99, p5, p95, inertia_mid, cycle_phase
    """
```

**说明**: 从 Strategy16LimitEntry._calculate_indicators 提取

**验收标准**:
- [ ] 输出与策略16的指标计算结果完全一致

**状态**: 待开始

---

## 阶段 P5-3: 主策略类实现

**目标**: 实现 Strategy20MultiSymbol 主类

### TASK-045-007: 创建策略主类框架

**文件**: `strategy_adapter/strategies/strategy20_multi_symbol.py`

**实现要点**:
```python
class Strategy20MultiSymbol(IStrategy):
    """策略20：多交易对共享资金池"""

    STRATEGY_ID = 'strategy_20'
    STRATEGY_NAME = '多交易对共享资金池'
    STRATEGY_VERSION = '1.0'

    DEFAULT_SYMBOLS = ['ETHUSDT', 'BTCUSDT', 'HYPEUSDT', 'BNBUSDT']

    def __init__(
        self,
        symbols: List[str] = None,
        discount: float = 0.001,
        max_positions: int = 10
    ):
        self.symbols = symbols or self.DEFAULT_SYMBOLS
        self.discount = Decimal(str(discount))
        self.max_positions = max_positions

        self._capital_manager: GlobalCapitalManager = None
        self._position_tracker: GlobalPositionTracker = None
        self._symbol_states: Dict[str, SymbolState] = {}

    def run_backtest(
        self,
        klines_dict: Dict[str, pd.DataFrame],
        initial_capital: Decimal = Decimal("10000")
    ) -> Dict:
        """执行多交易对回测"""
        ...
```

**验收标准**:
- [ ] 类结构符合架构设计
- [ ] IStrategy 接口方法实现

**状态**: 待开始

---

### TASK-045-008: 实现回测核心循环

**文件**: `strategy_adapter/strategies/strategy20_multi_symbol.py`

**实现要点**:

1. **初始化阶段**:
   - 创建 GlobalCapitalManager
   - 创建 GlobalPositionTracker
   - 为每个交易对创建 SymbolState
   - 计算每个交易对的指标

2. **处理循环**:
   ```python
   def _process_timestamp(self, ts: int, klines_dict: Dict):
       for symbol in self.symbols:
           state = self._symbol_states[symbol]

           # 1. 检查卖出挂单成交
           self._check_sell_orders(state, kline)

           # 2. 检查买入挂单成交
           self._check_buy_orders(state, kline)

           # 3. 创建新的卖出挂单
           self._create_sell_orders(state, indicators)

           # 4. 创建新的买入挂单（检查全局约束）
           self._create_buy_order(state, indicators)
   ```

3. **全局约束检查**:
   - 买入前检查 `position_tracker.can_open_position()`
   - 使用 `position_tracker.calculate_position_size()` 计算金额
   - 调用 `capital_manager.freeze()` 冻结资金

**验收标准**:
- [ ] 逐时间戳处理所有交易对
- [ ] 资金冻结/解冻正确
- [ ] 持仓数不超过 max_positions

**状态**: 待开始

---

### TASK-045-009: 实现统计输出

**文件**: `strategy_adapter/strategies/strategy20_multi_symbol.py`

**实现要点**:
```python
def _generate_result(self) -> Dict:
    """生成回测结果"""
    return {
        "global": {
            "initial_capital": ...,
            "final_capital": ...,
            "total_return": ...,
            "total_return_rate": ...,
            "total_orders": ...,
            "winning_orders": ...,
            "win_rate": ...,
            "max_drawdown": ...,
            "apr": ...,
            "apy": ...,
            "trading_days": ...
        },
        "by_symbol": {
            "ETHUSDT": {...},
            "BTCUSDT": {...},
            ...
        },
        "orders": [...],
        "equity_curve": [...]
    }
```

**验收标准**:
- [ ] global 统计正确合并所有交易对
- [ ] by_symbol 每个交易对独立统计
- [ ] equity_curve 正确记录资金曲线
- [ ] max_drawdown 计算正确

**状态**: 待开始

---

## 阶段 P5-4: 集成与注册

**目标**: 将策略20集成到现有系统

### TASK-045-010: 注册到策略工厂

**文件**: `strategy_adapter/core/strategy_factory.py`

**实现要点**:

1. 在 `_auto_register_strategies()` 中添加:
```python
# 注册策略20: 多交易对共享资金池 (迭代045)
try:
    from strategy_adapter.strategies import Strategy20MultiSymbol
    StrategyFactory.register("strategy-20-multi-symbol", Strategy20MultiSymbol)
except ImportError as e:
    logger.warning(f"无法注册策略20: {e}")
```

2. 在 `create()` 方法中添加分支:
```python
elif strategy_type == "strategy-20-multi-symbol":
    from strategy_adapter.strategies import Strategy20MultiSymbol

    symbols = config.entry.get("symbols", Strategy20MultiSymbol.DEFAULT_SYMBOLS)
    discount = float(config.entry.get("discount", 0.001))
    max_positions = int(config.entry.get("max_positions", 10))

    strategy = Strategy20MultiSymbol(
        symbols=symbols,
        discount=discount,
        max_positions=max_positions
    )
    return strategy
```

**验收标准**:
- [ ] `StrategyFactory.get_available_types()` 包含 "strategy-20-multi-symbol"
- [ ] `StrategyFactory.create()` 可正确创建策略20实例

**状态**: 待开始

---

### TASK-045-011: 更新 CLI 命令

**文件**: `strategy_adapter/management/commands/run_strategy_backtest.py`

**实现要点**:

1. 添加 `--symbols` 参数:
```python
parser.add_argument(
    '--symbols',
    type=str,
    help='交易对列表（逗号分隔），如: ETHUSDT,BTCUSDT'
)
```

2. 处理多交易对数据加载:
```python
if strategy_type == "strategy-20-multi-symbol":
    symbols = options.get('symbols', '').split(',') or strategy.DEFAULT_SYMBOLS
    klines_dict = {}
    for symbol in symbols:
        klines_dict[symbol] = self._load_klines(symbol, ...)
    result = strategy.run_backtest(klines_dict, initial_capital)
```

**验收标准**:
- [ ] `--strategy strategy-20-multi-symbol` 命令执行正常
- [ ] `--symbols` 参数正确解析
- [ ] 多交易对数据正确加载

**状态**: 待开始

---

## 阶段 P5-5: 测试与验证

**目标**: 确保功能正确性和性能达标

### TASK-045-012: 单元测试

**文件**: `strategy_adapter/tests/test_strategy20_multi_symbol.py`

**测试用例**:
1. `test_global_capital_manager_freeze_unfreeze`
2. `test_global_position_tracker_limits`
3. `test_symbol_state_initialization`
4. `test_multi_symbol_backtest_basic`
5. `test_position_limit_enforcement`
6. `test_dynamic_position_size_calculation`
7. `test_result_structure`

**验收标准**:
- [ ] 所有核心逻辑有单元测试覆盖
- [ ] 测试通过率 100%

**状态**: 待开始

---

### TASK-045-013: 集成测试

**测试场景**:

1. **基本回测**:
```bash
python manage.py run_strategy_backtest \
    --strategy strategy-20-multi-symbol \
    --symbols ETHUSDT,BTCUSDT,HYPEUSDT,BNBUSDT \
    --initial-cash 10000 \
    --start-date 2025-01-01 \
    --end-date 2025-12-31
```

2. **验证项目**:
- [ ] 4交易对同时回测执行成功
- [ ] 全局持仓数不超过10
- [ ] 输出包含 global 和 by_symbol 统计
- [ ] APR/APY 计算正确
- [ ] 执行时间 < 60秒
- [ ] 内存占用 < 2GB

**状态**: 待开始

---

## 任务依赖关系

```
TASK-045-001 (GlobalCapitalManager)
    ↓
TASK-045-002 (GlobalPositionTracker)
    ↓
TASK-045-003 (SymbolState)
    ↓
TASK-045-005 (entry_exit_logic)
TASK-045-006 (indicator_calculator)
    ↓
TASK-045-007 (策略主类框架)
    ↓
TASK-045-008 (回测核心循环)
    ↓
TASK-045-009 (统计输出)
    ↓
TASK-045-010 (策略工厂注册)
TASK-045-011 (CLI命令)
    ↓
TASK-045-012 (单元测试)
TASK-045-013 (集成测试)
```

---

## 风险与注意事项

1. **内存管理**: 4个交易对的K线数据可能占用较大内存，需注意数据加载方式
2. **时间戳对齐**: 确保所有交易对使用相同的时间周期，K线时间戳一致
3. **向后兼容**: 不影响现有策略16/19的功能
4. **指标计算效率**: 考虑缓存指标计算结果，避免重复计算

---

## 验收检查清单

### 功能验收
- [ ] 4个交易对同时回测，资金池正确共享
- [ ] 全局持仓数不超过 max_positions (10)
- [ ] 每个交易对独立输出统计
- [ ] 合并汇总统计正确（总收益/APR/APY/最大回撤）
- [ ] run_strategy_backtest 命令正常执行

### 性能验收
- [ ] 4交易对1年4h数据回测 < 60秒
- [ ] 内存占用 < 2GB

### 兼容性验收
- [ ] 不影响现有策略16/19功能
- [ ] 与现有回测框架兼容
