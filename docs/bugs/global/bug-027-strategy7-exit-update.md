# Bug-027: 策略7退出条件修改 + 命令行参数优先级

## 问题描述

### 需求1：策略7退出条件修改

**原逻辑**：
| 周期 | 止盈条件 | 止损条件 |
|------|---------|---------|
| 震荡期（consolidation） | P95止盈 | 5%止损 |
| 下跌期（bear_warning, bear_strong） | EMA25回归 | 5%止损 |
| 上涨期（bull_warning, bull_strong） | Mid止盈 `(P95+inertia_mid)/2` | 5%止损 |

**新逻辑**：
| 周期 | 止盈条件 | 止损条件 |
|------|---------|---------|
| 下跌期（bear_warning, bear_strong） | EMA25回归止盈 | **无止损** |
| 震荡期（consolidation） | `(P95 + EMA25) / 2` 止盈 | **无止损** |
| 上涨期（bull_warning, bull_strong） | P95止盈 | **无止损** |

### 需求2：命令行参数优先级

**问题**：`_handle_multi_strategy` 方法直接使用配置文件参数，命令行参数被忽略。

**期望**：命令行参数优先级 > 配置文件参数

## 修复方案

### 方案A：直接修改DynamicExitSelector（采用）

**修改点**：
1. 移除 `stop_loss_exit` 初始化和检查逻辑
2. 震荡期：新增 `_check_consolidation_exit` 方法计算 `(P95+EMA25)/2`
3. 上涨期：改用 `P95TakeProfitExit`
4. 下跌期：保持 `EmaReversionExit`

**优点**：改动集中，不影响其他策略

## 修改文件

1. `strategy_adapter/exits/dynamic_exit_selector.py`
   - 移除止损相关逻辑
   - 修改震荡期止盈条件：从P95改为(P95+EMA25)/2
   - 修改上涨期止盈条件：从Mid改为P95

2. `strategy_adapter/management/commands/run_strategy_backtest.py`
   - 在 `_handle_multi_strategy` 方法中添加命令行参数覆盖逻辑
   - 支持覆盖：symbol, interval, market_type, start_date, end_date, initial_cash, position_size, commission_rate

3. `strategy_adapter/configs/strategy7_adaptive_exit.json`
   - 更新描述和版本号
   - 移除止损参数

## 验证结果

### 策略7回测（HYPEUSDT）
```
【整体统计】
  总订单数: 124
  已平仓: 124
  持仓中: 0
  净利润: +2711.65 USDT
  胜率: 66.13%
  收益率: +27.12%
```

### 命令行参数覆盖验证
```bash
python manage.py run_strategy_backtest --config strategy_adapter/configs/strategy7_adaptive_exit.json BTCUSDT --start-date 2025-06-01 --end-date 2025-12-31
```

输出：
```
✓ 加载成功: 策略7-动态周期自适应
  命令行参数覆盖:
    - symbol: ETHUSDT -> BTCUSDT
    - start_date: 2025-01-01 -> 2025-06-01
    - end_date: 2026-01-07 -> 2025-12-31
  交易对: BTCUSDT
```

### 三种周期止盈验证
- 震荡期：`触发震荡期止盈: cycle_phase=consolidation, threshold=... (P95=..., EMA25=...)`
- 下跌期：`触发下跌期止盈: cycle_phase=bear_strong, exit_type=ema_reversion`
- 上涨期：`触发上涨期止盈: cycle_phase=bull_warning, exit_type=p95_take_profit`

## 修复状态

- [x] 需求对齐与澄清
- [x] 问题现象描述
- [x] 三层立体诊断分析
- [x] 修改DynamicExitSelector
- [x] 修改run_strategy_backtest
- [x] 验证交付

**修复完成时间**: 2026-01-08
