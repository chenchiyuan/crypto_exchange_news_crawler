# Implementation Plan: 止盈止损智能监控规则 (Rule 6 & 7)

**Branch**: `001-006-short-grid` | **Date**: 2025-12-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-006-short-grid/spec.md`

## Summary

本功能在现有的价格触发预警监控系统（001-price-alert-monitor）基础上，新增规则6（止盈信号监控）和规则7（止损信号监控）。通过量价形态识别（VPA）和技术指标确认，检测市场的动能衰竭（止盈时机）和动能爆发（止损时机），为网格交易员提供及时的平仓建议。

**核心技术方法**:
- 复用现有check_price_alerts.py脚本的5分钟定时检测机制
- 扩展PriceRuleEngine，新增规则6和规则7的检测逻辑
- 新增15m和1h两个K线周期的数据获取（现有规则仅使用4h）
- 实现4个VPA模式检测：急刹车、金针探底、攻城锤、阳包阴
- 实现4个技术指标确认：RSI超卖/超买、布林带回升/突破
- 通过现有的批量推送机制发送告警，支持多规则合并推送

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**:
- Django 4.2.8 (现有框架)
- python-binance 1.0.19 (币安SDK，现有依赖)
- pandas 2.0+, numpy 1.24+ (K线数据处理，现有依赖)
- TA-Lib或pandas-ta (技术指标计算，需确认项目已有哪个库)

**Storage**: SQLite (开发) / PostgreSQL 14+ (生产)，复用现有数据库表
- MonitoredContract (复用)
- AlertTriggerLog (复用)
- PriceAlertRule (新增rule_id=6和7的记录)
- SystemConfig (复用)
- KlineData (复用，新增15m和1h周期数据)

**Testing**: pytest (现有框架)
**Target Platform**: Linux server (定时任务cron)
**Project Type**: Single Django project (后端服务)
**Performance Goals**:
- 单个合约检测耗时 ≤ 2秒
- 推送延迟 ≤ 30秒
- 防重复机制有效性 ≥ 95%

**Constraints**:
- 必须与现有5条规则100%兼容，不影响现有功能
- 必须支持15m和1h双周期独立触发
- 必须通过Django Admin动态配置参数，无需重启服务
- 必须复用现有的批量推送和防重复机制

**Scale/Scope**:
- 检测范围：MonitoredContract表中的所有合约（估计20-50个）
- 触发频率：每5分钟检测一次
- 规则数量：从5条扩展到7条
- 代码修改：5个文件（rule_engine.py, check_price_alerts.py, django_models.py, init_price_alert_rules.py, alert_notifier.py）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### ✅ 核心原则检查

| 原则 | 合规性 | 说明 |
|------|--------|------|
| I. 使用中文沟通 | ✅ PASS | 所有文档、注释、提交信息使用中文 |
| II. 零假设原则 | ✅ PASS | 已通过澄清流程明确所有关键决策点 |
| III. 小步提交 | ✅ PASS | 计划分阶段实施，每阶段独立可测试 |
| IV. 借鉴现有代码 | ✅ PASS | 复用现有的PriceRuleEngine和alert框架 |
| V. 务实主义 | ✅ PASS | 选择最简单的扩展方案，避免重构现有架构 |
| VI. 简单至上 | ✅ PASS | VPA检测逻辑简单明确，单一职责 |
| VII. 测试驱动开发 | ⚠️ ADVISORY | 建议为VPA模式检测编写单元测试 |

### ✅ 量化交易系统原则检查

| 原则 | 合规性 | 说明 |
|------|--------|------|
| VIII.1 回测优先 | ⚠️ ADVISORY | 建议用历史数据验证规则6和7的准确率（SC-002/003要求≥65%） |
| VIII.2 风险控制第一 | ✅ PASS | 规则6和7提供止盈止损建议，符合风险管理目标 |
| VIII.3 模块化与状态隔离 | ✅ PASS | 作为独立规则模块，不影响现有Trigger逻辑 |
| VIII.4 参数可追溯 | ✅ PASS | 所有触发记录到AlertTriggerLog，parameters字段可配置 |
| VIII.5 渐进式部署 | ✅ PASS | 初期可设置rule.enabled=False进行Paper Testing |

### ⚠️ 需要额外关注的约束

| 约束 | 状态 | 应对措施 |
|------|------|----------|
| 技术指标库选择 | NEEDS RESEARCH | 需确认项目已使用TA-Lib还是pandas-ta |
| K线数据完整性 | NEEDS VERIFICATION | 需验证KlineData表是否已有足够的15m/1h历史数据 |
| RSI/布林带计算准确性 | NEEDS TESTING | 需要单元测试验证计算逻辑与标准实现一致 |

### ✅ 无宪法违规

本功能不涉及以下禁止行为：
- ❌ 跳过回测直接实盘部署（规则6和7仅提供建议，不自动交易）
- ❌ 使用绝对价格/成交量比较（VPA模式使用百分比和比率）
- ❌ 绕过三维筛选框架（本功能属于Trigger模块，不涉及筛选）

## Project Structure

### Documentation (this feature)

```text
specs/001-006-short-grid/
├── spec.md              # 功能规格（已完成）
├── plan.md              # 本文件（实施计划）
├── research.md          # Phase 0: 技术调研（待生成）
├── data-model.md        # Phase 1: 数据模型（待生成）
├── quickstart.md        # Phase 1: 快速开始（待生成）
├── contracts/           # Phase 1: API契约（待生成）
└── tasks.md             # Phase 2: 任务分解（/speckit.tasks命令生成）
```

### Source Code (repository root)

```text
grid_trading/
├── services/
│   ├── rule_engine.py                    # [MODIFY] 新增规则6和7的检测逻辑
│   ├── alert_notifier.py                 # [MODIFY] 新增规则6和7的消息模板
│   ├── kline_cache.py                    # [USE] 复用现有K线缓存服务
│   └── binance_futures_client.py         # [USE] 复用现有币安API客户端
├── management/commands/
│   ├── check_price_alerts.py             # [MODIFY] 新增15m/1h K线获取
│   └── init_price_alert_rules.py         # [MODIFY] 初始化规则6和7配置
├── django_models.py                       # [MODIFY] 新增规则6和7的PriceAlertRule记录
└── models/                                # [USE] 复用现有模型

tests/
├── unit/
│   ├── test_rule_6_vpa_patterns.py       # [NEW] 规则6 VPA模式单元测试
│   ├── test_rule_7_vpa_patterns.py       # [NEW] 规则7 VPA模式单元测试
│   └── test_technical_indicators.py      # [NEW] 技术指标计算单元测试
└── integration/
    └── test_check_price_alerts.py        # [MODIFY] 扩展集成测试覆盖规则6和7
```

**Structure Decision**:
采用现有的Django单体项目结构（Option 1: Single project）。本功能是对现有价格监控系统的扩展，不需要新建独立模块或服务。所有代码变更集中在`grid_trading`包内，符合项目的模块化架构。

## Complexity Tracking

> **无需填写 - 本功能不违反宪法原则**

本功能完全遵循现有架构和约定，不引入新的复杂性：
- ✅ 复用现有的规则引擎和推送机制
- ✅ 遵循现有的5条规则的实现模式
- ✅ 不引入新的外部依赖（TA-Lib/pandas-ta项目已有）
- ✅ 保持与现有代码的一致性

---

## Phase 0: Research

**Status**: ✅ Completed (2025-12-11)

**Output**: `research.md`

**Research Tasks**:
1. 技术指标库选择
   - ✅ 调研项目现有使用的是TA-Lib还是pandas-ta → **纯NumPy/SciPy实现**
   - ✅ 确认RSI(14)和BB(20,2)的计算接口 → **RSI已有，BB需新增**
   - ✅ 验证计算结果与标准实现的一致性 → **通过indicator_calculator.py验证**

2. K线数据可用性
   - ✅ 检查KlineData表是否已有15m和1h周期的数据 → **15m: 878,288条, 1h: 112,435条**
   - ✅ 评估历史数据的完整性（是否有足够的50根K线用于MA计算） → **充分满足**
   - ✅ 确认KlineCache服务对15m/1h的支持情况 → **已支持，含历史模式**

3. VPA模式检测最佳实践
   - ✅ 研究急刹车、金针探底模式的参数调优 → **参数已优化并文档化**
   - ✅ 研究攻城锤、阳包阴模式的误报率控制 → **三重条件过滤策略明确**
   - ✅ 参考开源量化库的K线形态识别实现 → **已分析并设计代码结构**

4. 批量推送消息格式
   - ✅ 研究现有的PriceAlertNotifier.send_batch_alert实现 → **已分析完整逻辑**
   - ✅ 确认多规则合并推送的格式设计 → **采用合并分类方案（选项B）**
   - ✅ 确认企业微信推送的字符数限制 → **已确认2000字符限制**

**Completion Criteria**:
- [x] 技术指标库已确认并验证可用
- [x] K线数据可用性已确认，或制定补充数据方案
- [x] VPA模式检测参数已优化并文档化
- [x] 批量推送格式已设计并与现有格式兼容

**详细研究报告**: 见 `research.md`

---

## Phase 1: Design & Contracts

**Status**: ⏳ Pending Phase 0 Completion

**Output**: `data-model.md`, `contracts/`, `quickstart.md`, agent context updated

**Tasks**:
1. 数据模型设计
   - PriceAlertRule (rule_id=6和7) 的parameters字段JSON schema
   - AlertTriggerLog.extra_info字段的JSON schema（规则6和7）
   - KlineData表的15m/1h数据需求分析

2. API契约设计
   - PriceRuleEngine._check_rule_6_take_profit() 接口定义
   - PriceRuleEngine._check_rule_7_stop_loss() 接口定义
   - VPA模式检测子方法的输入输出契约

3. 快速开始文档
   - 如何在Django Admin中配置规则6和7
   - 如何查看触发日志和推送历史
   - 如何调整parameters参数进行优化

**Completion Criteria**:
- [ ] data-model.md已生成并包含完整的数据字典
- [ ] contracts/目录已创建并包含所有接口定义
- [ ] quickstart.md已生成并包含操作指南
- [ ] agent context已更新（CLAUDE.md或类似文件）

---

## Next Steps

1. **Phase 0执行**: 生成research.md，解决所有NEEDS CLARIFICATION
2. **Phase 1执行**: 生成data-model.md和contracts/
3. **Phase 2启动**: 运行`/speckit.tasks`生成详细的任务分解
4. **实施开始**: 按照tasks.md的阶段逐步实现

**当前状态**: ⏸️ 等待Phase 0研究完成
