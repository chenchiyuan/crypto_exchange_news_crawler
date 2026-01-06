# 策略回测命令使用指南

## 命令概述

`run_strategy_backtest` 是一个Django management command，用于执行策略回测（当前支持DDPS-Z策略）。

## 基本用法

```bash
python manage.py run_strategy_backtest <交易对> [选项]
```

## 参数说明

### 必填参数

- `symbol`: 交易对名称（如BTCUSDT、ETHUSDT）

### 可选参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--start-date` | 日期 | 最早数据 | 回测开始日期，格式：YYYY-MM-DD |
| `--end-date` | 日期 | 最新数据 | 回测结束日期，格式：YYYY-MM-DD |
| `--interval` | 字符串 | 4h | K线周期（1h, 4h, 1d等） |
| `--market-type` | 枚举 | futures | 市场类型（futures或spot） |
| `--initial-cash` | 数字 | 10000.0 | 初始资金（USDT） |
| `--strategy` | 枚举 | ddps-z | 策略类型（当前仅支持ddps-z） |
| `--verbose` | 标志 | - | 显示详细信息 |

## 使用示例

### 1. 最简单用法（回测全部历史数据）

```bash
python manage.py run_strategy_backtest ETHUSDT
```

这将回测ETHUSDT的全部历史4小时K线数据，使用DDPS-Z策略，初始资金10000 USDT。

### 2. 指定日期范围

```bash
python manage.py run_strategy_backtest BTCUSDT \
  --start-date 2025-01-01 \
  --end-date 2025-12-31
```

回测2025年全年的BTCUSDT数据。

### 3. 指定周期和市场类型

```bash
# 回测现货市场
python manage.py run_strategy_backtest ETHUSDT \
  --interval 1h \
  --market-type spot

# 回测合约市场（默认）
python manage.py run_strategy_backtest BTCUSDT \
  --interval 4h \
  --market-type futures
```

### 4. 自定义初始资金

```bash
python manage.py run_strategy_backtest ETHUSDT \
  --initial-cash 50000
```

使用50000 USDT作为初始资金进行回测。

### 5. 完整示例（所有参数）

```bash
python manage.py run_strategy_backtest BTCUSDT \
  --start-date 2025-06-01 \
  --end-date 2025-12-31 \
  --interval 4h \
  --market-type futures \
  --initial-cash 20000 \
  --strategy ddps-z \
  --verbose
```

## 输出结果说明

命令执行后会输出以下信息：

### 1. 配置信息
```
=== 策略回测系统 ===

策略: DDPS-Z
交易对: ETHUSDT
周期: 4h
市场: futures
初始资金: 10000.00 USDT
```

### 2. 执行步骤
```
[1/5] 加载K线数据...
✓ 加载成功: 180根K线

[2/5] 计算技术指标...
✓ 计算完成: 4个指标

[3/5] 初始化策略...
✓ 策略创建: DDPS-Z v1.0

[4/5] 执行回测...
✓ 回测完成

[5/5] 回测结果
```

### 3. 回测结果

#### 基本信息
```
【基本信息】
  数据周期: 180根K线
  时间范围: 2025-11-07 ~ 2026-01-06
  初始资金: 10000.00 USDT
```

#### 订单统计
```
【订单统计】
  总订单数: 39
  持仓中: 0
  已平仓: 39
```

#### 盈亏统计
```
【盈亏统计】
  总盈亏: -59.64 USDT
  平均盈亏: -1.53 USDT
```

#### 胜率统计
```
【胜率统计】
  胜率: 41.03%
  盈利订单: 16
  亏损订单: 23
```

#### 收益率
```
【收益率】
  平均收益率: -1.53%
  总收益率: -1.53%
```

#### 极值订单
```
【极值订单】
  最佳订单: +23.45 USDT (23.45%)
  最差订单: -12.34 USDT (-12.34%)
```

#### 持仓时长
```
【持仓时长】
  平均持仓: 8.5根K线
```

## 前置条件

### 1. 确保数据已更新

在执行回测前，需要先更新K线数据：

```bash
# 更新合约数据
python manage.py update_klines --symbol ETHUSDT --interval 4h --market-type futures

# 更新现货数据
python manage.py update_klines --symbol ETHUSDT --interval 4h --market-type spot
```

### 2. 策略适配层已安装

确保`strategy_adapter`模块在`settings.py`的`INSTALLED_APPS`中：

```python
INSTALLED_APPS = [
    # ...
    'strategy_adapter',  # 策略适配层 (迭代013)
]
```

## 技术说明

### 执行流程

1. **数据加载**: 从`backtest.KLine`表加载指定条件的K线数据
2. **指标计算**: 计算DDPS-Z策略所需的技术指标
   - EMA25: 25周期指数移动平均线
   - P5: 动态支撑位
   - β: EMA斜率（变化率）
   - inertia_mid: 惯性中位线
3. **策略初始化**: 创建`DDPSZStrategy`实例
4. **回测执行**: 使用`StrategyAdapter`执行回测
5. **结果展示**: 输出详细的统计信息

### 策略说明

当前实现的DDPS-Z策略包括：
- **买入条件**: 基于BuySignalCalculator（策略1、策略2、策略3）
- **卖出条件**: EMA25回归（K线[low, high]包含EMA25）
- **仓位管理**: 固定100 USDT/订单
- **止盈止损**: MVP阶段不启用

## 常见问题

### Q: 提示"没有找到K线数据"？
**A**: 需要先运行`update_klines`命令更新数据：
```bash
python manage.py update_klines --symbol ETHUSDT --interval 4h
```

### Q: 如何回测特定时间段？
**A**: 使用`--start-date`和`--end-date`参数：
```bash
python manage.py run_strategy_backtest ETHUSDT \
  --start-date 2025-01-01 \
  --end-date 2025-06-30
```

### Q: 支持其他策略吗？
**A**: 当前版本仅支持DDPS-Z策略。未来可以通过实现`IStrategy`接口添加新策略。

### Q: 如何查看详细日志？
**A**: 添加`--verbose`参数：
```bash
python manage.py run_strategy_backtest ETHUSDT --verbose
```

## 相关文档

- [策略适配层PRD](./prd.md)
- [架构设计文档](./architecture.md)
- [开发任务计划](./tasks.md)
- [测试规范](./test-specs.md)

## 版本信息

- **创建日期**: 2026-01-06
- **迭代编号**: 013
- **当前版本**: 1.0
- **支持策略**: DDPS-Z v1.0

---

**注意**: 回测结果仅供参考，不构成投资建议。实盘交易存在风险，请谨慎决策。
