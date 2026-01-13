# 迭代初始化: 042-回测结果协议抽象

## 项目信息

| 字段 | 值 |
|------|-----|
| 迭代编号 | 042 |
| 创建日期 | 2026-01-13 |
| 状态 | 进行中 |
| 流程类型 | P0-P6快速流程 |

## 需求背景

当前问题：
1. 回测统计字段（如`total_orders`、`win_rate`、`static_apr`等）硬编码在Strategy16的`_generate_result()`方法中
2. 子策略（如Strategy19）直接继承这些统计，无法添加策略特有的统计字段
3. run_batch_backtest的CSV_HEADERS与策略返回的字段紧耦合
4. 新增策略时需要手动确保返回字段与CSV_HEADERS兼容

用户需求：
- 使用run_batch_backtest回测Strategy19的所有交易对
- 框架需要支持策略自定义的统计字段
- 抽象统计协议，让策略本身返回需要的统计项

## 预期成果

1. 定义BacktestResult数据类/协议
2. 策略通过实现协议方法返回标准化结果
3. run_strategy_backtest和run_batch_backtest使用协议
4. 支持策略扩展自定义统计字段

## 相关文件

- `strategy_adapter/interfaces/strategy.py` - IStrategy接口
- `strategy_adapter/strategies/strategy16_limit_entry.py` - 当前统计实现
- `strategy_adapter/management/commands/run_batch_backtest.py` - CSV输出
- `strategy_adapter/management/commands/run_strategy_backtest.py` - 单策略回测

## 下一步

进入P1阶段：编写PRD和功能点清单
