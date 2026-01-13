# PRD: 回测结果协议抽象

## 文档信息

| 字段 | 值 |
|------|-----|
| 迭代编号 | 042 |
| 创建日期 | 2026-01-13 |
| 状态 | 草稿 |

## 1. 问题陈述

### 1.1 当前问题

**统计字段硬编码**
- Strategy16的`_generate_result()`方法定义了所有统计字段
- 子策略继承时无法优雅地添加策略特有字段
- run_batch_backtest的CSV_HEADERS需要手动与策略返回字段保持同步

**策略与输出层紧耦合**
- CSV_HEADERS直接硬编码19个字段
- 字段映射逻辑(`field_mappings`)在命令层处理
- 新策略添加字段时需要修改多处代码

**扩展性差**
- Strategy19的`strategy19_stats`字段无法自动输出到CSV
- 不同策略可能需要不同的统计维度

### 1.2 用户需求

> "我需要使用run_batch_backtest回测19策略的所有交易对，需要先让框架本身支持需要的统计项。目前似乎是写死在16策略里面，我建议在run_strategy_backtest和run_batch_backtest支持统计参数，抽象成协议，让策略本身返回，系统性的解决问题"

## 2. 目标

### 2.1 核心目标

1. **定义BacktestResult协议** - 标准化回测结果数据结构
2. **策略返回标准化结果** - 策略实现协议方法返回结果
3. **支持扩展字段** - 策略可添加自定义统计字段
4. **命令层自动适配** - run_batch_backtest/run_strategy_backtest自动处理协议

### 2.2 非目标

- 不修改现有策略的回测逻辑
- 不改变现有CSV输出格式的核心字段
- 不引入复杂的插件系统

## 3. 解决方案

### 3.1 BacktestResult数据类

定义标准化的回测结果数据类，包含：
- **核心字段**: 所有策略必须返回的基础统计
- **扩展字段**: 策略特有的统计（字典形式）

```python
@dataclass
class BacktestResult:
    # === 核心统计 (必须) ===
    total_orders: int           # 总订单数
    winning_orders: int         # 盈利订单数
    losing_orders: int          # 亏损订单数
    open_positions: int         # 持仓中订单数
    win_rate: float             # 胜率 (%)
    net_profit: float           # 净利润
    return_rate: float          # 收益率 (%)

    # === 资金统计 ===
    initial_capital: float      # 初始资金
    total_equity: float         # 账户总值
    available_capital: float    # 可用现金
    frozen_capital: float       # 挂单冻结
    holding_cost: float         # 持仓成本
    holding_value: float        # 持仓市值

    # === 交易统计 ===
    total_volume: float         # 总交易量
    total_commission: float     # 总手续费

    # === 年化指标 ===
    static_apr: float           # 静态APR (%)
    weighted_apy: float         # 综合APY (%)
    backtest_days: int          # 回测天数
    start_date: str             # 开始日期
    end_date: str               # 结束日期

    # === 扩展字段 ===
    extra_stats: Dict[str, Any] # 策略特有统计
    orders: List[Dict]          # 订单详情列表
```

### 3.2 IStrategy接口扩展

在IStrategy中添加可选方法：

```python
class IStrategy(ABC):
    # ... 现有方法 ...

    def get_extra_csv_headers(self) -> List[str]:
        """
        返回策略特有的CSV表头（可选）

        Returns:
            List[str]: 额外的CSV列名，对应extra_stats中的键
        """
        return []
```

### 3.3 命令层适配

run_batch_backtest修改：
1. 基础CSV_HEADERS保持不变
2. 动态合并策略的extra_csv_headers
3. 从BacktestResult提取数据填充行

## 4. 功能点清单

| ID | 功能点 | 优先级 | 描述 |
|----|--------|--------|------|
| FP-042-001 | BacktestResult数据类 | P0 | 定义标准化回测结果结构 |
| FP-042-002 | Strategy16返回BacktestResult | P0 | 修改_generate_result返回标准类型 |
| FP-042-003 | run_batch_backtest适配 | P0 | 支持BacktestResult和extra_stats |
| FP-042-004 | get_extra_csv_headers方法 | P1 | IStrategy可选方法 |
| FP-042-005 | Strategy19实现扩展字段 | P1 | 输出bear_warning跳过次数等 |

## 5. 验收标准

1. **基础兼容**: 现有策略回测结果格式不变
2. **协议实现**: Strategy16/19返回BacktestResult
3. **CSV输出**: run_batch_backtest正确输出所有字段
4. **扩展支持**: Strategy19的extra_stats出现在CSV中
5. **向后兼容**: 旧格式Dict返回仍可工作

## 6. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 破坏现有策略 | 高 | 保持Dict返回的兼容性 |
| CSV格式变化 | 中 | 基础字段位置不变 |
| 性能影响 | 低 | dataclass转换开销可忽略 |
