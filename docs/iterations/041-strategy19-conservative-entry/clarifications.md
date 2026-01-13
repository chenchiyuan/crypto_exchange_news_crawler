# 需求澄清记录: 策略19-保守入场策略

## 文档信息

| 字段 | 值 |
|------|-----|
| 迭代编号 | 041 |
| 创建日期 | 2026-01-13 |

## 澄清记录

### Q1: 下跌期禁止挂单的范围

**问题**: bear_warning禁止挂单是否也包括bear_strong周期？（策略16的下跌期包含bear_warning和bear_strong两个阶段）

**选项**:
- A. 仅bear_warning
- B. bear_warning + bear_strong（完整下跌期）

**用户回答**: A. 仅bear_warning

**决策**: 只在cycle_phase == 'bear_warning'时禁止挂单，bear_strong允许挂单

**影响**: 代码中只需判断单一条件 `if cycle_phase == 'bear_warning': skip`

---

### Q2: 震荡期倍增是否影响max_positions

**问题**: 震荡期3x挂单金额是否影响max_positions（最大持仓数）？例如，如果base=1000，震荡期挂3000，max_positions仍为10？

**选项**:
- A. 保持不变（推荐）- max_positions不变，仅单笔金额变大
- B. 按比例调整 - max_positions也需要重新考虑

**用户回答**: A. 保持不变（推荐）

**决策**: max_positions保持策略16默认值（10），震荡期仅增大单笔挂单金额

**影响**: 震荡期可能更快消耗可用资金，但持仓数上限不变

---

## 澄清总结

| 编号 | 问题摘要 | 决策结果 |
|------|----------|----------|
| Q1 | 下跌期范围 | 仅bear_warning禁止挂单 |
| Q2 | max_positions | 保持不变，默认10 |

## 质量检查

- [x] 关键模糊点已识别并澄清（≤3个）
- [x] 澄清记录完整
- [x] 无遗留[TBD]
