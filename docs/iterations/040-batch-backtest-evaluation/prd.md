# PRD: 批量回测评估体系

## 文档信息
| 属性 | 值 |
|------|-----|
| 迭代编号 | 040 |
| 项目名称 | batch-backtest-evaluation |
| 创建日期 | 2026-01-13 |
| 版本 | 1.0 |
| 状态 | 需求定义中 |

## 1. 背景与目标

### 1.1 背景
当前策略回测系统（`run_strategy_backtest`）仅支持单交易对回测，缺乏以下能力：
- 批量回测多个交易对并汇总结果
- 资金利用效率相关指标（APR/APY）
- 结构化的回测结果存储和对比

用户需要一套**整体评估体系**，能够基于指定策略批量回测多个交易对，输出关键指标并以CSV格式存储，便于横向对比和筛选优质交易对。

### 1.2 目标
1. **扩展现有回测指标**：在`run_strategy_backtest`中新增APR/APY等资金效率指标
2. **支持批量回测**：提供批量回测多交易对的能力，支持指定交易对列表或回测全部
3. **结果CSV存储**：将回测结果以CSV格式存储，便于后续分析

### 1.3 非目标（MVP排除）
- 实时交易信号推送
- Web可视化Dashboard
- 回测结果的数据库持久化（仅CSV）
- 按前缀匹配交易对（如ETH*）

## 2. 核心概念定义

### 2.1 资金静态APR（Annual Percentage Rate）
简单年化收益率，假设收益率在回测期间均匀分布：

```
静态APR = (账户总值 - 初始资金) / 初始资金 / 回测天数 × 365 × 100%
```

**示例**：初始资金10000，回测357天，账户总值7875.36
```
静态APR = (7875.36 - 10000) / 10000 / 357 × 365 × 100% = -21.72%
```

### 2.2 资金综合年化APY（Annual Percentage Yield）
基于时间加权法计算的综合年化收益率，考虑每笔订单的持仓时间和资金占用：

```
APY = Σ(单笔收益率 × 单笔金额 × 365/持仓天数) / Σ(单笔金额)
```

**计算步骤**：
1. 对每笔已平仓订单：年化收益率 = 收益率 × (365 / 持仓天数)
2. 加权平均：APY = Σ(年化收益率_i × 金额_i) / Σ(金额_i)

**示例**：
| 订单 | 金额 | 收益率 | 持仓天数 | 年化收益率 |
|------|------|--------|----------|------------|
| A | 1000 | +5% | 10 | +182.5% |
| B | 1000 | -2% | 5 | -146% |
| C | 1000 | +3% | 15 | +73% |

```
APY = (182.5% × 1000 + (-146%) × 1000 + 73% × 1000) / 3000 = 36.5%
```

### 2.3 持仓天数计算
- **已平仓订单**：`(sell_timestamp - buy_timestamp) / (24 × 60 × 60 × 1000)`
- **持仓中订单**：`(回测结束时间 - buy_timestamp) / (24 × 60 × 60 × 1000)`
- **最小值**：1天（避免除零）

## 3. 功能需求

### 3.1 阶段一：扩展run_strategy_backtest指标

#### FP-040-001：新增静态APR指标
- **优先级**：P0
- **描述**：在回测结果中新增`static_apr`字段
- **计算公式**：`(total_equity - initial_capital) / initial_capital / backtest_days × 365 × 100`
- **显示位置**：【整体统计】区域
- **验收标准**：
  - [x] 命令行输出显示静态APR
  - [x] 精度：保留2位小数

#### FP-040-002：新增综合年化APY指标
- **优先级**：P0
- **描述**：在回测结果中新增`weighted_apy`字段
- **计算公式**：时间加权法（见2.2节）
- **特殊处理**：
  - 持仓中订单按回测结束时间计算持仓天数
  - 浮盈浮亏计入收益率计算
- **显示位置**：【整体统计】区域
- **验收标准**：
  - [x] 命令行输出显示综合APY
  - [x] 精度：保留2位小数

#### FP-040-003：扩展统计输出
- **优先级**：P0
- **描述**：整合所有指标的结构化输出
- **输出字段**（完整列表）：
  ```
  总订单数, 已平仓, 持仓中
  可用现金, 挂单冻结, 持仓成本, 持仓市值, 账户总值
  总交易量, 总手续费
  胜率, 净利润, 收益率, 静态APR, 综合APY
  ```
- **验收标准**：
  - [x] 所有字段在命令行正确显示
  - [x] 返回值Dict包含所有字段

### 3.2 阶段二：批量回测框架

#### FP-040-004：批量回测命令
- **优先级**：P0
- **描述**：新增`run_batch_backtest`管理命令
- **命令格式**：
  ```bash
  python manage.py run_batch_backtest \
    --config <config.json> \
    --symbols ETHUSDT,BTCUSDT,SOLUSDT \
    --output <output.csv> \
    --auto-fetch
  ```
- **参数说明**：
  | 参数 | 必填 | 默认值 | 说明 |
  |------|------|--------|------|
  | --config | 是 | - | 策略配置文件路径 |
  | --symbols | 否 | ALL | 交易对列表（逗号分隔）或ALL |
  | --output | 否 | `data/backtest_results_{timestamp}.csv` | CSV输出路径 |
  | --auto-fetch | 否 | False | 自动拉取缺失K线 |
- **验收标准**：
  - [x] 支持指定单个交易对
  - [x] 支持指定多个交易对（逗号分隔）
  - [x] 支持ALL回测所有合约交易对
  - [x] 进度显示：`[1/50] ETHUSDT ...`

#### FP-040-005：交易对列表获取
- **优先级**：P0
- **描述**：获取待回测交易对列表
- **数据源**：`FuturesContract`模型
- **ALL模式**：查询所有`status=trading`的合约
- **验收标准**：
  - [x] 正确获取交易对列表
  - [x] 跳过无K线数据的交易对

#### FP-040-006：CSV结果存储
- **优先级**：P0
- **描述**：将回测结果保存为CSV文件
- **CSV字段**（表头）：
  ```csv
  symbol,total_orders,closed_orders,open_positions,
  available_capital,frozen_capital,holding_cost,holding_value,total_equity,
  total_volume,total_commission,
  win_rate,net_profit,return_rate,static_apr,weighted_apy,
  backtest_days,start_date,end_date
  ```
- **编码**：UTF-8 with BOM（Excel兼容）
- **验收标准**：
  - [x] CSV文件正确生成
  - [x] Excel可正确打开并显示中文

#### FP-040-007：错误处理与跳过
- **优先级**：P0
- **描述**：单个交易对回测失败不影响整体
- **处理策略**：
  - 记录错误日志
  - 在CSV中标记该交易对为ERROR
  - 继续处理下一个交易对
- **验收标准**：
  - [x] 单个失败不中断整体
  - [x] 错误信息记录到日志

#### FP-040-008：进度显示
- **优先级**：P1
- **描述**：显示批量回测进度
- **格式**：`[当前/总数] 交易对 耗时 结果摘要`
- **示例**：
  ```
  [1/50] ETHUSDT ... 3.2s | 订单:180 胜率:56.98% APR:-21.72%
  [2/50] BTCUSDT ... 2.8s | 订单:145 胜率:62.07% APR:+15.34%
  ```
- **验收标准**：
  - [x] 实时显示进度
  - [x] 显示关键统计

## 4. 技术设计要点

### 4.1 现有代码修改
- `strategy_adapter/strategies/strategy16_limit_entry.py`
  - `_generate_result()`：新增APR/APY计算
- `strategy_adapter/management/commands/run_strategy_backtest.py`
  - 输出显示：新增APR/APY行

### 4.2 新增文件
- `strategy_adapter/management/commands/run_batch_backtest.py`
  - 批量回测命令主入口
- `strategy_adapter/services/batch_backtest_service.py`（可选）
  - 封装批量回测逻辑

### 4.3 依赖
- 复用现有`run_strategy_backtest`核心逻辑
- 复用`Strategy16LimitEntry`策略类
- 使用`FuturesContract`模型获取交易对

## 5. 测试场景

### 5.1 APR/APY计算测试
| 场景 | 输入 | 预期输出 |
|------|------|----------|
| 正收益 | 初始10000，总值12000，357天 | APR≈+20.45% |
| 负收益 | 初始10000，总值7875，357天 | APR≈-21.72% |
| 无订单 | 初始10000，总值10000，357天 | APR=0%, APY=0% |
| 单笔订单 | 1000USDT，+5%，10天 | APY≈+182.5% |

### 5.2 批量回测测试
| 场景 | 命令 | 预期结果 |
|------|------|----------|
| 单个交易对 | --symbols ETHUSDT | CSV含1行数据 |
| 多个交易对 | --symbols ETHUSDT,BTCUSDT | CSV含2行数据 |
| 全部交易对 | --symbols ALL | CSV含所有交易对 |
| 部分失败 | 含无数据交易对 | 失败项标记ERROR |

## 6. 里程碑

### MVP（Phase 1）
- [x] FP-040-001：静态APR指标
- [x] FP-040-002：综合APY指标
- [x] FP-040-003：扩展统计输出

### MVP（Phase 2）
- [x] FP-040-004：批量回测命令
- [x] FP-040-005：交易对列表获取
- [x] FP-040-006：CSV结果存储
- [x] FP-040-007：错误处理与跳过
- [ ] FP-040-008：进度显示（P1）

## 7. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 批量回测耗时长 | 用户体验差 | 显示进度、支持断点续传（P1） |
| 内存占用过高 | 程序崩溃 | 逐个处理交易对，不并行 |
| K线数据缺失 | 回测失败 | 支持--auto-fetch自动拉取 |

## 8. 附录

### 8.1 CSV示例
```csv
symbol,total_orders,closed_orders,open_positions,available_capital,frozen_capital,holding_cost,holding_value,total_equity,total_volume,total_commission,win_rate,net_profit,return_rate,static_apr,weighted_apy,backtest_days,start_date,end_date
ETHUSDT,180,172,8,956.59,0.00,8000.00,6918.76,7875.36,342956.59,342.96,56.98,-1043.41,-21.25,-21.72,45.32,357,2024-12-31,2025-12-24
BTCUSDT,145,140,5,2500.00,0.00,5000.00,5500.00,8000.00,250000.00,250.00,62.07,500.00,10.00,10.22,38.50,357,2024-12-31,2025-12-24
```

### 8.2 关联文档
- 策略16实现：`strategy_adapter/strategies/strategy16_limit_entry.py`
- 回测命令：`strategy_adapter/management/commands/run_strategy_backtest.py`
- 配置示例：`strategy_adapter/configs/strategy16_p5_ema_state_exit.json`
