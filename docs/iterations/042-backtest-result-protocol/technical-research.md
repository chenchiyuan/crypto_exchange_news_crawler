# 技术调研: 回测结果协议抽象

## 文档信息

| 字段 | 值 |
|------|-----|
| 迭代编号 | 042 |
| 创建日期 | 2026-01-13 |

## 1. 现状分析

### 1.1 Strategy16._generate_result返回结构

```python
{
    # 订单列表
    'orders': List[Dict],

    # 核心统计
    'total_trades': int,
    'winning_trades': int,
    'losing_trades': int,
    'total_profit_loss': float,
    'net_profit': float,
    'win_rate': float,
    'return_rate': float,
    'remaining_holdings': int,

    # 资金统计
    'available_capital': float,
    'frozen_capital': float,
    'holding_cost': float,
    'holding_value': float,
    'holding_unrealized_pnl': float,
    'total_equity': float,
    'last_close_price': float,

    # 交易统计
    'total_volume': float,
    'total_commission': float,

    # 年化指标
    'static_apr': float,
    'weighted_apy': float,
    'backtest_days': int,
    'start_date': str,
    'end_date': str,

    # 嵌套统计(冗余)
    'statistics': Dict
}
```

### 1.2 run_batch_backtest CSV_HEADERS

```python
CSV_HEADERS = [
    'symbol',           # 交易对
    'total_orders',     # 总订单数
    'closed_orders',    # 已平仓
    'open_positions',   # 持仓中
    'available_capital',
    'frozen_capital',
    'holding_cost',
    'holding_value',
    'total_equity',
    'total_volume',
    'total_commission',
    'win_rate',
    'net_profit',
    'return_rate',
    'static_apr',
    'weighted_apy',
    'backtest_days',
    'start_date',
    'end_date',
]
```

### 1.3 字段映射问题

run_batch_backtest的_format_row有字段映射:
```python
field_mappings = {
    'total_orders': ['total_orders', 'total_trades'],
    'closed_orders': ['closed_orders', 'total_trades'],
    'open_positions': ['open_positions', 'remaining_holdings'],
    'net_profit': ['net_profit', 'total_profit_loss'],
}
```

说明：策略返回的字段名与CSV期望的字段名不一致，需要兼容映射。

## 2. 设计方案

### 2.1 方案A: 纯协议模式（推荐）

**思路**: 定义BacktestResult dataclass作为协议，策略返回此类型。

**优点**:
- 类型安全，IDE提示友好
- 字段定义清晰明确
- to_dict()保持向后兼容

**缺点**:
- 需要修改现有_generate_result方法

**实现**:
```python
@dataclass
class BacktestResult:
    total_orders: int
    winning_orders: int
    # ... 其他字段

    extra_stats: Dict[str, Any] = field(default_factory=dict)
    orders: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """转换为字典格式（兼容现有代码）"""
        result = asdict(self)
        # 展开extra_stats到顶层
        result.update(result.pop('extra_stats', {}))
        return result
```

### 2.2 方案B: 适配器模式

**思路**: 不修改策略代码，在命令层添加结果适配器。

**优点**:
- 不修改现有策略代码
- 风险最低

**缺点**:
- 命令层代码复杂
- 无法在策略层定义扩展字段

### 2.3 选择方案A

理由:
1. 策略是结果的来源，应该由策略定义返回结构
2. dataclass提供类型检查和文档
3. to_dict()保证向后兼容
4. 扩展字段通过extra_stats灵活处理

## 3. 技术细节

### 3.1 BacktestResult位置

文件: `strategy_adapter/models/backtest_result.py`

与db_models.py中的BacktestResult区分:
- db_models.BacktestResult: Django ORM模型，用于数据库存储
- models.BacktestResult: dataclass，用于内存数据传递

命名: 使用相同名称但不同导入路径，由上下文区分。

### 3.2 字段标准化

统一使用以下命名:
- total_orders (不是 total_trades)
- open_positions (不是 remaining_holdings)

策略返回BacktestResult后，命令层不需要field_mappings。

### 3.3 扩展字段处理

策略实现get_extra_csv_headers():
```python
class Strategy19(Strategy16):
    def get_extra_csv_headers(self) -> List[str]:
        return ['skipped_bear_warning', 'consolidation_multiplier']
```

run_batch_backtest动态合并:
```python
# 获取策略实例
strategy = StrategyFactory.create(...)

# 获取扩展表头
extra_headers = []
if hasattr(strategy, 'get_extra_csv_headers'):
    extra_headers = strategy.get_extra_csv_headers()

# 合并表头
headers = CSV_HEADERS + extra_headers
```

## 4. 兼容性策略

### 4.1 向后兼容

1. BacktestResult.to_dict()返回与原格式兼容的字典
2. 命令层检测返回类型，dict直接使用，BacktestResult调用to_dict()
3. 保留statistics嵌套字段（部分代码可能依赖）

### 4.2 渐进式迁移

1. 先添加BacktestResult类
2. Strategy16使用BacktestResult构建并to_dict()
3. 验证所有测试通过
4. 逐步移除冗余字段映射

## 5. 结论

采用方案A（纯协议模式），实现步骤:
1. 创建BacktestResult dataclass
2. 修改Strategy16._generate_result使用BacktestResult
3. 添加IStrategy.get_extra_csv_headers()可选方法
4. 修改run_batch_backtest支持扩展表头
5. Strategy19实现扩展字段输出
