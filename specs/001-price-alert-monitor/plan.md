# Implementation Plan: 价格触发预警监控系统

**Branch**: `001-price-alert-monitor` | **Date**: 2025-12-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-price-alert-monitor/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

实现一个**价格触发预警监控系统**,采用**定时批量处理**架构模式。系统通过两个独立脚本协同工作:
1. **数据更新脚本**(每5分钟): 批量获取监控合约的1m/15m/4h K线数据和当前价格,存储到数据库
2. **合约监控脚本**(数据更新后触发): 遍历所有监控合约,检测5种价格触发规则(7天新高/新低、MA20/MA99触及、价格分布极值),通过汇成推送接口发送通知

系统支持手动添加合约和自动从筛选结果同步合约,实现防重复推送机制(同一合约同一规则1小时内仅推送一次),自动管理过期合约状态。

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: Django 4.2.8, python-binance 1.0.19, pandas 2.0+, numpy 1.24+
**Storage**: SQLite (开发) / PostgreSQL 14+ (生产), 复用现有KlineData表存储K线数据
**Testing**: pytest, pytest-django, pytest-cov, pytest-asyncio
**Target Platform**: Linux server, 支持crontab或Celery Beat定时任务调度
**Project Type**: Web (Django项目,已有grid_trading应用)
**Performance Goals**:
- 数据更新脚本: 3分钟内完成100个合约的K线更新(平均1.8秒/合约)
- 合约监控脚本: 2分钟内完成100个合约的规则检测(平均1.2秒/合约)
- 整体流程(更新+检测+推送): 5分钟内完成(满足下次定时任务前完成)

**Constraints**:
- 必须复用现有的KlineData模型存储K线数据(symbol, interval, open_time, OHLCV字段)
- 必须复用现有的AlertPushService(monitor/services/notifier.py)进行汇成推送
- 必须支持增量数据更新,避免重复获取已有K线数据
- 必须实现脚本锁机制,避免定时任务并发执行冲突
- API限流控制: 币安API 1200请求/分钟,需要实现请求队列管理

**Scale/Scope**:
- 初期支持100个监控合约,后续可扩展到500+
- K线数据存储: 每个合约×3个周期×7天数据≈2100条记录/合约
- 推送频率: 平均每小时5-10条触发通知(假设10%合约触发规则)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### 核心原则合规性

✅ **I. 使用中文沟通**: 所有文档、代码注释、提交信息使用中文
✅ **II. 零假设原则**: 已通过用户确认架构(定时批量处理)和推送渠道(汇成接口)
✅ **III. 小步提交**: 将按阶段提交,每次提交确保可编译和测试通过
✅ **IV. 借鉴现有代码**: 复用KlineData模型、AlertPushService、现有management commands结构
✅ **V. 务实主义**: 选择定时批量处理而非实时WebSocket,更简单且资源消耗低
✅ **VI. 简单至上**: 两个独立脚本,职责单一,逻辑清晰,易于测试
✅ **VII. 测试驱动开发**: 将为规则判定逻辑、防重复机制编写单元测试

### 量化系统原则合规性

✅ **VIII.2 风险控制第一**: 实现防重复推送机制,避免消息轰炸
✅ **VIII.3 模块化与状态隔离**: 数据更新和规则检测分离为独立脚本
✅ **VIII.4 参数可追溯**: DataUpdateLog记录每次执行情况,AlertTriggerLog记录触发详情
✅ **VIII.5 渐进式部署**: 可先在开发环境测试数据更新,再逐步启用规则检测和推送

### 项目特定约束合规性

✅ **模块运行频率**: 数据更新脚本每5分钟执行(中高频),符合约束要求
✅ **数据依赖**: 复用现有KlineData表,无额外数据依赖
✅ **风险参数范围**: 防重复间隔默认60分钟,强制最小5分钟(与更新频率一致)
✅ **状态持久化**: 所有状态(监控合约、触发日志、配置)持久化到数据库
✅ **日志与监控**: 记录每次数据更新和规则触发日志,便于审计和调试

### 合规性检查结果

**状态**: ✅ 通过所有核心原则和约束检查

**评估说明**:
- 本功能不涉及量化策略回测和参数优化,因此宪法VIII.1(回测优先)不适用
- 采用定时批量处理架构符合宪法V(务实主义)和VI(简单至上)原则
- 复用现有基础设施(KlineData、AlertPushService)符合宪法IV(借鉴现有代码)
- 无需引入新的复杂依赖或架构模式,满足奥卡姆剃刀原则

**无需特殊辩护的偏离**: 无

## Project Structure

### Documentation (this feature)

```text
specs/001-price-alert-monitor/
├── spec.md              # 功能规格文档
├── plan.md              # 本文件(技术规划)
├── research.md          # Phase 0 技术研究报告
├── data-model.md        # Phase 1 数据模型设计
├── quickstart.md        # Phase 1 快速开始指南
├── contracts/           # Phase 1 API契约定义
│   └── api.yaml         # REST API OpenAPI规范
├── checklists/          # 质量检查清单
│   └── requirements.md  # 需求验证清单(已完成)
└── tasks.md             # Phase 2 实现任务清单(待生成)
```

### Source Code (repository root)

```text
grid_trading/                          # 复用现有Django应用
├── models/
│   └── (新增模型在 django_models.py 中)
├── management/
│   └── commands/
│       ├── update_price_monitor_data.py    # 数据更新脚本(新增)
│       └── check_price_alerts.py           # 合约监控脚本(新增)
├── services/
│   ├── price_monitor_service.py      # 价格监控服务(新增)
│   ├── rule_engine.py                # 规则引擎(新增)
│   └── alert_notifier.py             # 预警通知服务(新增,封装AlertPushService)
├── views/
│   └── price_monitor_views.py        # Dashboard和API视图(新增)
├── templates/
│   └── grid_trading/
│       └── price_monitor_dashboard.html  # 监控仪表盘(新增)
├── urls.py                            # 添加price-monitor相关路由
└── admin.py                           # 注册新模型到Django Admin

tests/
├── unit/
│   ├── test_rule_engine.py           # 规则判定逻辑单元测试
│   ├── test_price_monitor_service.py # 服务层单元测试
│   └── test_alert_notifier.py        # 通知服务单元测试
├── integration/
│   ├── test_data_update_command.py   # 数据更新脚本集成测试
│   ├── test_alert_check_command.py   # 监控脚本集成测试
│   └── test_price_monitor_workflow.py # 完整工作流集成测试
└── fixtures/
    └── kline_test_data.json           # K线数据测试夹具
```

**Structure Decision**:

选择在现有`grid_trading`应用中扩展,而非创建新应用,原因:
1. **数据依赖**: 本功能大量复用grid_trading的KlineData模型和SymbolInfo模型
2. **代码复用**: 可以复用现有的币安API客户端和K线数据管理逻辑
3. **一致性**: 监控系统与筛选系统、网格交易系统属于同一业务域(量化交易)
4. **维护性**: 集中管理相关功能,避免应用碎片化

新增的模型将直接添加到`grid_trading/django_models.py`,新增的management commands遵循现有命名约定(如`screen_simple.py`, `screen_by_date.py`),确保项目结构一致性。

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

无需填写 - 本方案通过所有合规性检查,无违规需辩护。

## Phase 0: Research & Technical Decisions

**Status**: ⏳ Pending
**Output**: `research.md`

### Research Tasks

1. **K线数据增量更新策略**
   - 研究如何高效实现增量更新(查询最后一条K线时间,仅获取之后的数据)
   - 评估数据完整性验证方法(检测缺失的K线)
   - 研究币安API的K线查询最佳实践(批量查询 vs 单次查询)

2. **规则判定算法实现**
   - 研究MA均线计算方法(pandas rolling mean vs numpy conv滑动卷积)
   - 研究价格分布区间的计算方法(numpy percentile vs scipy.stats)
   - 研究7天新高/新低判定的边界情况处理(不足7天数据如何处理)

3. **脚本锁机制选型**
   - 评估文件锁 vs 数据库锁 vs Redis锁的优缺点
   - 研究Django中的分布式锁实现最佳实践
   - 评估定时任务超时处理策略

4. **防重复推送实现**
   - 研究基于数据库的防重复机制设计(查询最近推送时间)
   - 评估缓存防重复的可行性(Redis vs 内存缓存)
   - 研究推送失败的重试和补偿机制

5. **汇成推送接口集成**
   - 研究现有AlertPushService的使用方法和错误处理
   - 评估推送消息格式和内容设计(标题、正文、K线图链接)
   - 研究推送失败的日志记录和告警机制

### Technology Choices

- **K线数据获取**: 使用python-binance SDK的`futures_klines`方法
- **数据库查询优化**: 使用Django ORM的`select_related`和`prefetch_related`优化关联查询
- **异步处理**: 使用Python标准库`threading`或`multiprocessing`并行处理多合约
- **日志记录**: 使用Django标准logging配置,输出到文件和控制台

### Open Questions (需要在research.md中解答)

- Q1: 如果币安API返回的K线数据缺失某个时间点,如何检测和处理?
- Q2: 定时任务执行超过5分钟时,如何避免下次任务与当前任务冲突?
- Q3: 汇成推送接口的请求限流策略是什么?如何避免触发限流?
- Q4: 如果监控合约数量增长到500+,是否需要分片处理(分批更新和检测)?

## Phase 1: Design Artifacts

**Status**: ⏳ Pending
**Prerequisite**: Phase 0 research.md complete

### Deliverables

1. **data-model.md**: 完整数据库表结构设计,包括6个核心实体
2. **contracts/api.yaml**: REST API规范(OpenAPI 3.0),定义监控管理和查询接口
3. **quickstart.md**: 开发者快速上手指南,包含本地环境搭建和测试运行

### Key Design Decisions (待Phase 1确定)

- [ ] 脚本锁机制实现方案(文件锁 vs 数据库锁)
- [ ] 防重复推送存储方案(数据库 vs Redis缓存)
- [ ] 规则判定算法的性能优化策略(向量化计算 vs 逐个循环)
- [ ] Dashboard前端技术选择(纯Django模板 vs Vue.js组件)

## Phase 2: Implementation Tasks

**Status**: ⏳ Pending
**Command**: `/speckit.tasks` (在Phase 1完成后执行)

**Output**: `tasks.md` - 详细的实现任务清单,包括:
- 数据库迁移任务(创建新表和索引)
- 服务层实现任务(数据更新、规则引擎、通知服务)
- Management Commands实现任务(两个独立脚本)
- 单元测试和集成测试任务
- 文档和部署配置任务

## Next Steps

1. ✅ 规格文档已完成并验证(`spec.md`)
2. ✅ 技术规划已完成(`plan.md` - 本文件)
3. ⏳ 执行Phase 0研究,生成`research.md`
4. ⏳ 执行Phase 1设计,生成`data-model.md`、`contracts/`、`quickstart.md`
5. ⏳ 更新agent context文件
6. ⏳ 执行`/speckit.tasks`生成实现任务清单
7. ⏳ 开始Phase 2实现

**当前行动**: 开始Phase 0技术研究,解决上述Open Questions
