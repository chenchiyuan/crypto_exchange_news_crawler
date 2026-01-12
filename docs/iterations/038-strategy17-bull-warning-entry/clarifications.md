# 需求澄清记录 - 策略17

## 澄清事项

### Q1: 上涨预警的具体定义

**问题**: "第一根出现上涨预警"的具体条件是什么？

**澄清**:
- 上涨预警(`bull_warning`)由`BetaCycleCalculator`定义
- 触发条件：β > 600（显示值）且 β正在增加
- "第一根"指cycle_phase从`consolidation`首次变为`bull_warning`
- 如果从`bull_strong`回落到`bull_warning`，不算"第一根"

### Q2: 买入时机

**问题**: "第二根K线open处买入"的具体含义？

**澄清**:
- 当K线i的cycle_phase首次变为`bull_warning`时
- 在K线i+1的open价格买入
- 这避免了使用K线i的close价格导致的后验偏差

### Q3: 周期延续的处理

**问题**: 如果bull_warning持续多根K线，是否重复买入？

**澄清**:
- 否，仅在状态转变时买入一次
- bull_warning → bull_warning: 不买入
- bull_strong → bull_warning: 不买入（周期延续）
- consolidation → bull_warning: 买入（新周期开始）

### Q4: 止盈止损完全复用策略16

**问题**: 止盈止损逻辑是否有任何调整？

**澄清**:
- 完全复用，无任何调整
- EMA状态止盈：四种市场状态对应四种止盈逻辑
- 固定止损：5%

---

**澄清完成时间**: 2026-01-12
**状态**: ✅ 所有关键问题已澄清
