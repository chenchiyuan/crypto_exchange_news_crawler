# PRD - 策略17：上涨预警入场策略

## 1. 概述

### 1.1 核心价值（一句话定义）

**在DDPS-Z检测到市场进入上涨预警阶段的第一时间入场，捕捉上涨周期的起点。**

### 1.2 背景

策略16采用P5限价挂单入场，适合震荡市场的低位接盘。但在趋势启动时，价格可能不会回调到P5支撑位就直接上涨，导致错过入场时机。

策略17基于DDPS-Z的β宏观周期状态机，在检测到上涨预警信号时立即入场，旨在捕捉趋势启动的第一波行情。

### 1.3 目标用户

量化回测研究人员，用于验证"上涨预警入场"策略的有效性。

## 2. 功能需求

### 2.1 核心功能

#### FP-038-001: 上涨预警入场信号

**触发条件**：
- 当前K线的`cycle_phase`首次变为`bull_warning`
- 即：前一根K线的`cycle_phase`不是`bull_warning`或`bull_strong`，当前K线是`bull_warning`

**执行方式**：
- 在下一根K线的`open`价格买入
- 买入金额：固定1000 USDT（可配置）

**技术实现**：
- 使用`BetaCycleCalculator`计算每根K线的`cycle_phase`
- 检测状态从`consolidation`转变为`bull_warning`的时刻

#### FP-038-002: EMA状态止盈

**复用策略16的EMA状态止盈逻辑**：
- 强势上涨(bull_strong)：EMA7下穿EMA25时触发
- 强势下跌(bear_strong)：high突破EMA25时触发
- 震荡下跌(consolidation_down)：high突破EMA99时触发
- 震荡上涨(consolidation_up)：挂单止盈2%

#### FP-038-003: 固定比例止损

**止损条件**：
- 当K线low触及买入价的95%时止损
- 止损比例：5%（可配置）

### 2.2 范围边界

#### In-Scope（做）

- [x] 上涨预警入场信号检测
- [x] 下一根K线open价格买入
- [x] EMA状态止盈
- [x] 5%固定止损
- [x] 回测结果统计

#### Out-of-Scope（不做）

- [ ] 实盘交易接口
- [ ] 前端展示页面
- [ ] 下跌预警做空策略（后续迭代）
- [ ] 多仓位管理优化

## 3. 验收标准

### AC-038-001: 入场信号准确性
- [ ] 当cycle_phase从consolidation变为bull_warning时，下一根K线以open价格买入
- [ ] 仅在首次进入bull_warning时触发，bull_warning持续期间不重复买入
- [ ] 从bull_strong变为bull_warning不触发买入（周期延续）

### AC-038-002: 止盈正确性
- [ ] 复用EmaStateExit，四种状态下的止盈逻辑与策略16一致

### AC-038-003: 止损正确性
- [ ] 当low <= buy_price × 0.95时触发止损

### AC-038-004: 回测统计完整性
- [ ] 返回总交易数、胜率、总收益率、平均持仓周期等指标

## 4. 技术约束

### 4.1 依赖组件

| 组件 | 用途 |
|------|------|
| BetaCycleCalculator | 计算cycle_phase序列 |
| EmaStateExit | 止盈条件判断 |
| EMACalculator | 计算EMA7/25/99 |
| EWMACalculator | 计算偏离率标准差 |
| InertiaCalculator | 计算β值 |

### 4.2 接口实现

实现`IStrategy`接口的`run_backtest()`方法，与策略16保持一致的回测流程。

## 5. 非功能需求

### 5.1 性能
- 回测1000根K线 < 5秒

### 5.2 可维护性
- 代码结构与策略16保持一致
- 完整的docstring和类型注解

---

**版本**: 1.0
**创建时间**: 2026-01-12
**迭代编号**: 038
