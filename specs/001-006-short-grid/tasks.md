# Implementation Tasks: 止盈止损智能监控规则 (Rule 6 & 7)

**Feature**: 001-006-short-grid
**Created**: 2025-12-11
**Based on**: plan.md, spec.md, research.md

---

## Task Summary

| Phase | Description | Task Count | Parallelizable |
|-------|-------------|------------|----------------|
| Phase 1 | Setup & Configuration | 2 | 0 |
| Phase 2 | Foundational (Technical Indicators) | 3 | 2 |
| Phase 3 | User Story 1 - 急刹车模式检测 (P1) | 5 | 2 |
| Phase 4 | User Story 2 - 金针探底模式检测 (P1) | 4 | 1 |
| Phase 5 | User Story 3 - 攻城锤模式检测 (P1) | 4 | 1 |
| Phase 6 | User Story 4 - 阳包阴模式检测 (P1) | 4 | 1 |
| Phase 7 | User Story 5 - 多周期集成与批量推送 (P1) | 6 | 2 |
| Phase 8 | User Story 6 - Django Admin配置 (P3) | 3 | 1 |
| Phase 9 | Polish & Cross-Cutting | 3 | 1 |
| **Total** | | **34** | **11** |

---

## Implementation Strategy

### MVP Scope (Minimum Viable Product)
推荐首次交付范围：**仅User Story 1（急刹车模式）+ User Story 5（多周期集成基础）**
- 验证VPA检测逻辑可行性
- 验证与现有规则引擎的集成
- 快速获得用户反馈
- 后续迭代快速扩展其他3种VPA模式

### Incremental Delivery Plan
1. **Iteration 1**: US1 + US5基础（仅15m周期，急刹车+RSI超卖）
2. **Iteration 2**: US2（金针探底+布林带）
3. **Iteration 3**: US3 + US4（规则7的两种模式）
4. **Iteration 4**: US5完整版（双周期独立触发）
5. **Iteration 5**: US6（参数可配置）+ 打磨

### Parallel Execution Opportunities
- **Phase 2**: T002和T003可并行（布林带 || RSI辅助方法）
- **Phase 3**: T005和T006可并行（急刹车检测 || RSI超卖检测）
- **Phase 4**: T010可与Phase 3并行开发
- **Phase 5**: T014和T015可并行（攻城锤 || RSI加速检测）
- **Phase 6**: T019可与Phase 5并行开发
- **Phase 7**: T022和T024可并行（推送格式 || 15m/1h独立检测）
- **Phase 8**: T028可并行（Django Admin配置独立于核心逻辑）

---

## Phase 1: Setup & Configuration

**Goal**: 初始化规则6和7的基础配置

**Tasks**:
- [X] T001 在 `grid_trading/management/commands/init_price_alert_rules.py` 中新增规则6和7的初始化逻辑（见spec.md FR-025/FR-026的parameters JSON schema）
- [X] T002 运行Django migration（如需要）或手动在Django Admin创建PriceAlertRule记录（rule_id=6和7，enabled=True）

**Acceptance**: Django Admin中可见规则6和7的配置记录，parameters字段包含完整JSON配置

---

## Phase 2: Foundational - Technical Indicators

**Goal**: 实现规则6/7共用的技术指标计算方法

**Dependencies**: 无（独立于用户故事）

**Tasks**:
- [X] T003 [P] 在 `grid_trading/services/rule_engine.py` 中新增私有方法 `_calculate_bollinger_bands(klines, period=20, std_dev=2.0)` 实现布林带计算（见research.md任务1的NumPy实现）
- [X] T004 [P] 在 `grid_trading/services/rule_engine.py` 中新增私有方法 `_calculate_ma(klines, period)` 实现简单移动平均（用于成交量MA50和价格MA20）
- [X] T005 在 `grid_trading/services/rule_engine.py` 中新增私有方法 `_calculate_rsi_slope(klines_list, period=14, lookback=3)` 计算RSI加速（见spec.md FR-017：(RSI_t - RSI_t-3) / 3）

**Acceptance**:
- 布林带计算与TradingView标准实现一致（可通过历史K线数据对照验证）
- RSI斜率计算逻辑正确（正斜率=加速上升，负斜率=减速）

---

## Phase 3: User Story 1 - 规则6止盈监控：急刹车模式识别 (P1)

**Story Goal**: 检测"急刹车"模式（前序暴跌+成交量维持+实体压缩）且RSI超卖时触发止盈提醒

**Independent Test**:
```python
# 模拟K线数据
klines_15m = [
    {'open': 98000, 'close': 96000, 'volume': 2000},  # 前序大阴线（跌幅2.04%）
    {'open': 95800, 'close': 95900, 'volume': 1700}   # 当前实体压缩（实体100 < 前实体2000×0.25）
]
# 验证触发条件
assert 急刹车检测(klines_15m) == True
assert RSI(14) < 20  # RSI超卖
# 预期触发规则6
```

**Tasks**:
- [X] T006 [P] [US1] 在 `grid_trading/services/rule_engine.py` 中实现 `_detect_stopping_volume(klines, params)` 检测急刹车模式（见spec.md FR-008：前序暴跌>2% AND 成交量维持≥80% AND 实体压缩<25%）
- [X] T007 [P] [US1] 在 `grid_trading/services/rule_engine.py` 中实现 `_check_rsi_oversold(klines, params)` 检测RSI超卖（见spec.md FR-010：RSI<20 OR 底背离）
- [X] T008 [US1] 在 `grid_trading/services/rule_engine.py` 中实现 `_check_rule_6_take_profit(symbol, klines_15m, klines_1h, current_price)` 主方法，组合急刹车+RSI超卖检测（见spec.md FR-012：VPA AND 技术指标）
- [X] T009 [US1] 在 `grid_trading/services/rule_engine.py` 的 `check_all_rules_batch` 方法中集成规则6检测逻辑（参考现有规则1-5的调用模式）
- [X] T010 [US1] 验证规则6在MonitoredContract表的合约上正常工作（使用真实历史K线数据测试，确认触发记录到AlertTriggerLog.extra_info包含vpa_signal='急刹车', tech_signal='RSI超卖'）

**Acceptance**:
- 急刹车模式检测准确（前序暴跌、成交量维持、实体压缩三条件同时满足）
- RSI超卖检测支持单纯超卖和底背离两种情况
- 规则6触发记录的extra_info符合spec.md FR-020的JSON schema
- 不满足条件时返回None，不触发

**File Modifications**:
- `grid_trading/services/rule_engine.py` (PriceRuleEngine类扩展)

---

## Phase 4: User Story 2 - 规则6止盈监控：金针探底模式识别 (P1)

**Story Goal**: 检测"金针探底"模式（放量暴跌+长下影线+收盘强势）且布林带回升时触发止盈提醒

**Independent Test**:
```python
klines_15m = [
    {'open': 96000, 'high': 96200, 'low': 94500, 'close': 95800, 'volume': 3000, ...}
    # 验证：vol=3000 > MA50×2.5, 下影线1300 > 实体200×2.0, close位于76%位置 > 60%, close > BB_lower
]
assert 金针探底检测(klines_15m) == True
assert 布林带回升检测(klines_15m) == True
```

**Tasks**:
- [ ] T011 [P] [US2] 在 `grid_trading/services/rule_engine.py` 中实现 `_detect_golden_needle(klines, params)` 检测金针探底模式（见spec.md FR-009：放量>MA50×2.5 AND 下影线>实体×2.0 AND 收盘位置>60%）
- [ ] T012 [US2] 在 `grid_trading/services/rule_engine.py` 中实现 `_check_bb_reversion(klines, params)` 检测布林带触底回升（见spec.md FR-011：Low<BB_Lower AND Close>BB_Lower）
- [ ] T013 [US2] 扩展 `_check_rule_6_take_profit` 方法，支持金针探底模式分支（急刹车 OR 金针探底）
- [ ] T014 [US2] 验证金针探底+布林带回升触发规则6（使用历史数据测试，确认extra_info中vpa_signal='金针探底', tech_signal='布林带回升'）

**Acceptance**:
- 金针探底检测准确（放量、长下影线、收盘强势三条件）
- 布林带回升逻辑正确（击穿后收回）
- 规则6支持两种VPA信号（急刹车 OR 金针探底）

**File Modifications**:
- `grid_trading/services/rule_engine.py`

---

## Phase 5: User Story 3 - 规则7止损监控：攻城锤模式识别 (P1)

**Story Goal**: 检测"攻城锤"模式（大阳线+放量+光头阳）且RSI超买加速时触发止损预警

**Independent Test**:
```python
klines_15m = [
    {'open': 96000, 'close': 98080, 'high': 98100, 'low': 96000, 'volume': 2500, ...}
    # 涨幅2.08%>2%, vol=2500 > MA50×1.5, 上影线20 < 实体2080×0.1
]
assert 攻城锤检测(klines_15m) == True
assert RSI超买加速检测([55,58,62,66]) == True  # 斜率3.67>2.0
```

**Tasks**:
- [ ] T015 [P] [US3] 在 `grid_trading/services/rule_engine.py` 中实现 `_detect_battering_ram(klines, params)` 检测攻城锤模式（见spec.md FR-015：涨幅>2% AND 放量≥MA50×1.5 AND 上影线<实体×0.1）
- [ ] T016 [P] [US3] 在 `grid_trading/services/rule_engine.py` 中实现 `_check_rsi_acceleration(klines, params)` 检测RSI超买加速（见spec.md FR-017：RSI>60 AND 斜率>2.0）
- [ ] T017 [US3] 在 `grid_trading/services/rule_engine.py` 中实现 `_check_rule_7_stop_loss(symbol, klines_15m, klines_1h, current_price)` 主方法，组合攻城锤+RSI超买加速检测
- [ ] T018 [US3] 在 `check_all_rules_batch` 中集成规则7检测逻辑（与规则6类似）

**Acceptance**:
- 攻城锤检测准确（涨幅、放量、光头阳）
- RSI超买加速计算正确（RSI>60且斜率>2.0）
- 规则7触发记录的extra_info符合spec.md FR-021的JSON schema

**File Modifications**:
- `grid_trading/services/rule_engine.py`

---

## Phase 6: User Story 4 - 规则7止损监控：阳包阴模式识别 (P1)

**Story Goal**: 检测"阳包阴"反转模式（当前阳线完全吞没前阴线）且布林带突破时触发止损预警

**Independent Test**:
```python
klines_15m = [
    {'open': 98000, 'close': 97500},  # 前阴线
    {'open': 97300, 'close': 98200}   # 当前阳线完全吞没（open<97500 AND close>98000）
]
assert 阳包阴检测(klines_15m) == True
assert 布林带突破检测(klines_15m) == True  # close > BB_upper AND BandWidth_t > BandWidth_t-1
```

**Tasks**:
- [ ] T019 [P] [US4] 在 `grid_trading/services/rule_engine.py` 中实现 `_detect_bullish_engulfing(klines, params)` 检测阳包阴模式（见spec.md FR-016：open<close_t-1 AND close>open_t-1 AND vol_t>vol_t-1 AND close>MA20）
- [ ] T020 [US4] 在 `grid_trading/services/rule_engine.py` 中实现 `_check_bb_breakout(klines, params)` 检测布林带突破扩张（见spec.md FR-018：Close>BB_Upper AND BandWidth扩张）
- [ ] T021 [US4] 扩展 `_check_rule_7_stop_loss` 方法，支持阳包阴模式分支（攻城锤 OR 阳包阴）
- [ ] T022 [US4] 验证阳包阴+布林带突破触发规则7（确认extra_info中vpa_signal='阳包阴', tech_signal='布林带突破扩张'）

**Acceptance**:
- 阳包阴检测严格（完全吞没+增量+位置确认）
- 布林带突破扩张逻辑正确（收盘价突破上轨且带宽扩张）
- 规则7支持两种VPA信号（攻城锤 OR 阳包阴）

**File Modifications**:
- `grid_trading/services/rule_engine.py`

---

## Phase 7: User Story 5 - 多周期独立触发与批量推送 (P1)

**Story Goal**: 同时检测15m和1h两个周期，任意周期触发即推送，支持与其他规则合并批量推送

**Independent Test**:
```python
# BTCUSDT的15m K线触发规则6（急刹车），1h K线未触发
assert 规则6触发结果.timeframe == '15m'
assert 推送消息包含 "[15m]" 标记

# ETHUSDT的15m和1h都触发规则7
assert 规则7触发结果.timeframe == '15m+1h'
assert 推送消息包含 "[15m+1h双周期确认]" 标记
```

**Tasks**:
- [X] T023 [P] [US5] 在 `grid_trading/management/commands/check_price_alerts.py` 中修改 `_check_all_contracts` 方法，对每个MonitoredContract合约额外获取15m和1h K线数据（使用KlineCache.get_klines，limit=100和30）
- [X] T024 [P] [US5] 修改 `check_all_rules_batch` 调用，传递klines_15m和klines_1h参数给规则6/7检测（保持向后兼容，其他规则忽略这些参数）
- [X] T025 [US5] 在 `_check_rule_6_take_profit` 和 `_check_rule_7_stop_loss` 中实现双周期独立检测逻辑（15m和1h分别检测，任意触发返回结果，timeframe字段标记触发周期）（注：已在Phase 3中完成）
- [X] T026 [US5] 在 `grid_trading/services/alert_notifier.py` 的 `RULE_NAMES` 字典中新增规则6和7的名称映射（6: "止盈信号监控", 7: "止损信号监控"）
- [X] T027 [US5] 在 `alert_notifier.py` 的 `_format_triggers` 方法中新增规则6和7的case处理（见research.md任务4的消息模板设计）
- [X] T028 [US5] 验证批量推送兼容性（同时触发规则1/2/6/7时，能正确合并推送；60分钟防重复机制正常工作）

**Acceptance**:
- 15m和1h K线数据正确获取（通过KlineCache）
- 双周期独立触发逻辑正确（任意周期满足即触发）
- 推送消息格式符合spec.md FR-022/FR-023（包含[15m]、[1h]或[15m+1h]标记）
- 规则6/7与规则1-5的批量推送100%兼容（见research.md任务4的分类方案）

**File Modifications**:
- `grid_trading/management/commands/check_price_alerts.py`
- `grid_trading/services/rule_engine.py`
- `grid_trading/services/alert_notifier.py`

---

## Phase 8: User Story 6 - Django Admin配置与参数调优 (P3)

**Story Goal**: 管理员可通过Django Admin动态配置规则6和7的参数，无需重启服务

**Independent Test**:
```python
# 在Django Admin修改规则6的VOL_MULTI_SPIKE从2.5改为3.0
# 下次检测时金针探底需要3倍放量才触发
assert PriceAlertRule.objects.get(rule_id=6).parameters['vol_multi_spike'] == 3.0
# 验证修改立即生效（无需重启check_price_alerts脚本）
```

**Tasks**:
- [ ] T029 [P] [US6] 在 `grid_trading/admin.py` 中注册PriceAlertRule模型（如尚未注册），确保rule_id=6和7的记录在Django Admin中可见
- [ ] T030 [US6] 在规则6/7的检测方法中，从PriceAlertRule.parameters字段读取参数配置（而非硬编码），支持动态调整vol_multi_spike、crash_threshold等参数（见spec.md FR-025/FR-026的完整参数列表）
- [ ] T031 [US6] 创建 `specs/001-006-short-grid/quickstart.md` 文档，记录Django Admin配置步骤、参数说明、调优建议（基于research.md任务3的参数调优结果）

**Acceptance**:
- Django Admin中可见规则6和7的配置页面
- 修改parameters字段后保存，下次检测立即生效（无需重启）
- quickstart.md文档完整清晰（包含参数调优建议）

**File Modifications**:
- `grid_trading/admin.py`
- `grid_trading/services/rule_engine.py`
- `specs/001-006-short-grid/quickstart.md` (新建)

---

## Phase 9: Polish & Cross-Cutting Concerns

**Goal**: 代码优化、日志完善、文档更新

**Tasks**:
- [ ] T032 [P] 在规则6/7的所有VPA检测方法中添加详细日志（使用logger.debug记录检测过程，logger.info记录触发结果），方便调试和审计
- [ ] T033 处理边界情况：K线数据不足50根时跳过检测并记录警告（与现有规则一致），RSI计算窗口不足14根时跳过RSI相关检测（见spec.md Edge Cases）
- [ ] T034 更新 `CLAUDE.md` 项目文档，添加规则6和7的技术栈信息（Python 3.12, NumPy实现的RSI/BB，VPA模式检测）

**Acceptance**:
- 所有VPA检测方法有充分日志输出（至少包含触发/未触发原因）
- 边界情况处理健壮（数据不足不会抛异常）
- CLAUDE.md文档已更新

**File Modifications**:
- `grid_trading/services/rule_engine.py`
- `CLAUDE.md`

---

## Dependencies & Execution Order

### Critical Path (Must be sequential)
```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational)
    ↓
Phase 3 (US1: 急刹车) ← MVP第一步
    ↓
Phase 7 (US5: 多周期集成) ← MVP第二步（仅基础集成，支持US1）
    ↓
Phase 4 (US2: 金针探底)
    ↓
Phase 5 (US3: 攻城锤)
    ↓
Phase 6 (US4: 阳包阴)
    ↓
Phase 8 (US6: Django Admin)
    ↓
Phase 9 (Polish)
```

### Parallel Opportunities
- **Phase 3 + Phase 4**: 规则6的两种VPA模式可并行开发（不同的检测方法）
- **Phase 5 + Phase 6**: 规则7的两种VPA模式可并行开发
- **Phase 8**: Django Admin配置可在Phase 7完成后独立开发
- **Within Phases**: 标记[P]的任务可并行（如T003 || T004, T006 || T007）

### User Story Dependencies
- **US1 → US5**: 多周期集成依赖至少一种VPA模式完成（US1）
- **US2-US4 → US5**: 其他VPA模式独立于US5，可在US5基础版完成后并行开发
- **US6**: 独立于所有其他User Story（仅读取parameters字段）

---

## Validation & Testing

### Independent Test Criteria (Per User Story)

**US1 (急刹车)**:
```bash
# 使用历史K线数据（BTCUSDT 2024-12-01某时刻）
python manage.py shell -c "
from grid_trading.services.rule_engine import PriceRuleEngine
engine = PriceRuleEngine()
# 准备测试K线数据（前序暴跌2%，当前实体压缩至20%，RSI=18）
result = engine._check_rule_6_take_profit('BTCUSDT', klines_15m, klines_1h, price)
assert result['vpa_signal'] == '急刹车'
assert result['tech_signal'] == 'RSI超卖'
"
```

**US2 (金针探底)**:
```bash
# 验证放量>MA50×2.5, 下影线>实体×2.0, 收盘>60%位置, close>BB_lower
```

**US3 (攻城锤)**:
```bash
# 验证涨幅>2%, 放量≥MA50×1.5, 上影线<实体×0.1, RSI>60且斜率>2.0
```

**US4 (阳包阴)**:
```bash
# 验证完全吞没（open<close_t-1 AND close>open_t-1）, vol增量, close>MA20, close>BB_upper
```

**US5 (多周期)**:
```bash
# 验证15m和1h独立触发，timeframe字段正确标记，批量推送兼容
python manage.py check_price_alerts  # 实际运行脚本，检查推送消息格式
```

**US6 (Django Admin)**:
```bash
# 在Django Admin修改parameters，验证下次检测使用新参数
```

### Integration Test
```bash
# 完整端到端测试
python manage.py check_price_alerts  # 运行价格监控脚本
# 预期：
# 1. 检测MonitoredContract中的所有合约
# 2. 规则6/7正常触发（如满足条件）
# 3. 触发记录到AlertTriggerLog，extra_info包含完整信息
# 4. 批量推送到企业微信，消息格式正确
# 5. 60分钟防重复机制生效
```

---

## Format Validation

✅ **All tasks follow checklist format**:
- [x] Every task starts with `- [ ]`
- [x] Every task has sequential Task ID (T001-T034)
- [x] Parallelizable tasks marked with [P]
- [x] User story tasks marked with [US1]-[US6]
- [x] All tasks include specific file paths
- [x] Clear action verbs (实现/新增/修改/验证)

✅ **Independent test criteria provided for each user story**

✅ **Dependencies clearly documented**

✅ **Parallel opportunities identified** (11 parallelizable tasks)

✅ **MVP scope defined** (US1 + US5 basic integration)

---

**Generated**: 2025-12-11
**Total Tasks**: 34
**Parallelizable**: 11
**Estimated MVP Effort**: 10 tasks (Phase 1-3 + Phase 7 basic)
**Full Feature Effort**: 34 tasks

**Next Steps**:
1. Review tasks.md with user
2. Begin with Phase 1 (Setup)
3. Complete Phase 2 (Foundational indicators)
4. Implement MVP (Phase 3 + Phase 7 basic)
5. Iterate remaining user stories
