# PRD: 策略19-保守入场策略

## 文档信息

| 字段 | 值 |
|------|-----|
| 迭代编号 | 041 |
| 版本 | 1.0 |
| 创建日期 | 2026-01-13 |
| 状态 | 已确认 |

## 1. 产品概述

### 1.1 核心价值（一句话）

在策略16基础上增加周期敏感的入场控制，bear_warning时禁止入场，震荡期加大仓位，实现更稳健的交易策略。

### 1.2 目标用户

量化交易策略研究人员，需要测试不同周期入场策略的回测效果。

## 2. 功能需求

### 2.1 核心功能 (P0)

#### F1: bear_warning周期禁止挂单
- **描述**: 当cycle_phase为bear_warning时，不创建买入挂单
- **验收标准**:
  - bear_warning周期内不产生任何新的买入挂单
  - bear_strong、consolidation、bull_warning、bull_strong正常挂单
- **优先级**: P0

#### F2: 震荡期挂单金额倍增
- **描述**: 当cycle_phase为consolidation时，挂单金额为base_position_size × consolidation_multiplier
- **验收标准**:
  - consolidation周期挂单金额=base × multiplier
  - 其他周期挂单金额=base
  - multiplier可通过参数配置，默认3
- **优先级**: P0

#### F3: 策略参数配置
- **描述**: 新增参数consolidation_multiplier控制震荡期挂单倍数
- **验收标准**:
  - 参数名: consolidation_multiplier
  - 默认值: 3
  - 类型: int，取值范围[1, 10]
- **优先级**: P0

#### F4: 策略注册
- **描述**: 策略19注册到策略工厂，支持回测命令调用
- **验收标准**:
  - STRATEGY_ID = 'strategy_19'
  - 支持run_strategy_backtest --strategy=strategy_19调用
- **优先级**: P0

### 2.2 延迟功能 (P1)

- bear_strong周期也禁止挂单（当前仅bear_warning）
- 上涨期（bull_warning/bull_strong）也支持独立的倍数配置
- 实盘运行器支持

## 3. 范围边界

### 3.1 In-Scope

- 策略19核心逻辑实现
- 回测框架集成
- 参数配置支持
- 策略工厂注册

### 3.2 Out-of-Scope

- 实盘运行器（复用策略16的Strategy16Runner模式，推迟实现）
- 前端Dashboard展示
- 与其他策略的组合
- 批量回测支持（使用现有run_batch_backtest命令）

## 4. 技术约束

- 继承自Strategy16LimitEntry
- 复用现有cycle_phase计算逻辑
- 保持与现有回测CLI兼容

## 5. 验收标准

| 验收项 | 标准 |
|--------|------|
| bear_warning不挂单 | 回测结果中bear_warning周期无买入订单 |
| 震荡期金额正确 | consolidation订单金额=base×multiplier |
| 参数可配置 | CLI支持--consolidation-multiplier参数 |
| 回测正常 | run_strategy_backtest可正常执行 |
