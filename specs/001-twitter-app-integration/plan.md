# Implementation Plan: Twitter 应用集成与 AI 分析

**Branch**: `001-twitter-app-integration` | **Date**: 2025-11-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-twitter-app-integration/spec.md`

## Summary

创建独立的 Django 应用（twitter），实现从 Twitter List 获取推文数据并使用 AI 进行内容分析的功能。系统将提供命令行工具，支持分批获取推文、AI 分析（使用 DeepSeek）、成本控制、任务管理和通知推送。核心技术路径：完整移植 twitter_analyze 项目的 TwitterSDK 和 DeepSeekSDK，复用现有 monitor 应用的通知服务。

## Technical Context

**Language/Version**: Python 3.8+ (项目现有标准)
**Primary Dependencies**:
- Django 4.2+ (现有框架)
- requests 2.31+ (HTTP 客户端，用于 Twitter/DeepSeek API 调用)
- tenacity 8.2+ (重试机制，用于 API 限流处理)
- python-dateutil 2.8+ (时间解析)

**Storage**: SQLite (开发) / PostgreSQL 14+ (生产) - 项目现有配置
**Testing**: pytest (项目现有框架)
**Target Platform**: Linux server (运行环境与现有 monitor 应用相同)
**Project Type**: Django 应用（作为 crypto_exchange_news_crawler 项目的一部分）

**Performance Goals**:
- 推文获取：500 条/批次，5秒内完成（包括数据库写入）
- AI 分析：100 条推文，2分钟内完成（一次性模式）
- 任务状态查询：响应时间 <1秒（即使 10 并发查询）

**Constraints**:
- API 限流：Twitter API 和 DeepSeek AI 都有速率限制，必须实现重试机制
- 成本控制：单次分析成本上限 $10，告警阈值 $5
- 数据完整性：推文 ID 唯一性约束，100% 去重
- 字符集支持：正确处理 emoji 和多语言字符

**Scale/Scope**:
- 预期推文量：单次获取 10,000 条以内
- List 数量：初期支持 5-10 个活跃 List
- 并发任务：支持多个分析任务同时执行
- 数据保留：推文和分析结果长期保留

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### ✅ 核心理念检查

- ✅ **I. 使用中文沟通**: 所有文档、注释、提交信息均使用中文
- ✅ **II. 零假设原则**: 需求已在 spec.md 明确，已识别的技术未知项将在 Phase 0 研究解决
- ✅ **III. 小步提交**: 将按照 Phase 划分进行增量提交
- ✅ **IV. 借鉴现有代码**: 将完整移植 twitter_analyze 项目的成熟代码，并学习 monitor 应用的模式
- ✅ **V. 务实主义**: 选择完整移植而非重写，复用现有通知服务
- ✅ **VI. 简单至上**: 避免过度设计，采用 twitter_analyze 已验证的简单架构
- ✅ **VII. 测试驱动开发**: 将为所有新功能编写测试，移植的代码将保留原有测试

### ✅ 技术标准检查

- ✅ **SOLID 原则**:
  - 单一职责：TwitterListService（推文获取）、AIAnalysisService（AI分析）、TwitterAnalysisOrchestrator（流程编排）职责分离
  - 依赖倒置：服务层依赖 SDK 抽象，不直接耦合 API 实现
- ✅ **DRY 原则**: 复用 monitor 应用的通知服务，避免重复实现
- ✅ **奥卡姆剃刀**: 直接移植成熟代码而非重新设计，选择最简单的可行方案
- ✅ **演进式架构**: 独立的 twitter 应用，未来可扩展用户管理、情绪分析等功能

### ✅ 项目融入检查

- ✅ **学习代码库**: 已研究 monitor 应用的模型结构（Exchange, Announcement, NotificationRecord）
- ✅ **工具使用**: 使用项目现有的 Django、pytest、black/isort
- ✅ **模式遵循**: Django 应用结构与 monitor 应用保持一致

### ⚠️ 复杂度警示（需在下方表格说明）

无复杂度违规。此方案符合所有宪法原则。

## Project Structure

### Documentation (this feature)

```text
specs/001-twitter-app-integration/
├── plan.md              # 本文件 (实施计划)
├── research.md          # Phase 0: 技术研究和决策
├── data-model.md        # Phase 1: 数据模型设计
├── quickstart.md        # Phase 1: 快速开始指南
├── contracts/           # Phase 1: API 合约定义
│   └── management-commands.md  # Django management commands 规范
└── tasks.md             # Phase 2: 任务清单 (由 /speckit.tasks 生成)
```

### Source Code (repository root)

```text
# Django 多应用项目结构（crypto_exchange_news_crawler）

crypto_exchange_news_crawler/  # 项目根目录
├── monitor/                    # 现有应用：交易所监控
│   ├── models.py               # Exchange, Announcement, Listing, etc.
│   ├── services/
│   │   ├── notifier.py         # 告警推送服务（将被复用）
│   │   ├── identifier.py
│   │   └── ...
│   └── management/commands/
│
├── twitter/                    # ✨ 新增应用：Twitter 分析
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py               # TwitterList, Tweet, TwitterAnalysisResult
│   ├── admin.py                # Django Admin 配置
│   ├── services/
│   │   ├── __init__.py
│   │   ├── twitter_list_service.py      # 推文获取服务
│   │   ├── ai_analysis_service.py       # AI 分析服务
│   │   ├── orchestrator.py              # 流程编排
│   │   └── notifier.py                  # 通知服务（复用 monitor.services.notifier）
│   ├── sdk/
│   │   ├── __init__.py
│   │   ├── twitter_sdk.py               # 移植自 twitter_analyze
│   │   ├── deepseek_sdk.py              # 移植自 twitter_analyze
│   │   ├── rate_limiter.py              # 限流器
│   │   └── retry_manager.py             # 重试管理器
│   ├── management/
│   │   └── commands/
│   │       └── analyze_twitter_list.py  # 主命令
│   ├── migrations/
│   │   └── 0001_initial.py
│   └── tests/
│       ├── __init__.py
│       ├── test_models.py
│       ├── test_services.py
│       ├── test_sdk.py
│       └── test_commands.py
│
├── crypto_exchange_news/       # 项目配置
│   ├── settings.py             # 新增 'twitter' 到 INSTALLED_APPS
│   └── ...
│
├── references/                 # 参考项目（不会修改）
│   └── twitter_analyze/        # 代码移植的源头
│
├── docs/                       # 项目文档
│   └── twitter-integration-solution.md  # 方案文档（已完成）
│
└── manage.py
```

**Structure Decision**: 选择独立的 Django 应用结构（twitter），这是 Django 项目的标准组织方式。原因：
1. 与现有 monitor 应用保持一致的架构模式
2. 清晰的模块边界，易于测试和维护
3. 符合 Django 最佳实践（高内聚、低耦合）
4. 未来可以轻松扩展或拆分为独立服务

## Complexity Tracking

**无复杂度违规**。此实施方案完全符合宪法原则：
- 复用成熟代码（twitter_analyze 项目）而非重新发明轮子
- 复用现有服务（monitor 应用的通知服务）
- 采用项目标准技术栈（Django, pytest）
- 遵循现有架构模式（独立 Django 应用）

---

## Phase 0: Outline & Research

**目标**: 解决所有技术未知项，为 Phase 1 设计做好准备

### 研究任务清单

虽然 Technical Context 中没有标记 NEEDS CLARIFICATION（因为需求已明确），但以下技术细节需要通过研究来确认：

#### R1: Twitter API 集成模式
**问题**: twitter_analyze 使用的 TwitterSDK 如何与第三方代理（apidance.pro）集成？API 认证方式是什么？

**研究内容**:
- 阅读 references/twitter_analyze/utils/twitter_sdk.py
- 确认 API 端点、认证头、错误处理机制
- 确认分页游标机制和数据解析逻辑

**输出**: 完整的 TwitterSDK 移植清单，包括必要的配置项

#### R2: DeepSeek AI 集成模式
**问题**: DeepSeekSDK 的 API 接口、成本计算方式、错误处理机制是什么？

**研究内容**:
- 阅读 references/twitter_analyze 中的 DeepSeekSDK 实现
- 确认 token 计数方式和成本估算公式
- 确认 API 限流处理和重试策略

**输出**: DeepSeekSDK 移植清单，包括成本控制配置

#### R3: 数据模型字段设计
**问题**: Twitter List 和 Tweet 的字段应该包含哪些具体属性？如何映射 Twitter API 响应？

**研究内容**:
- 阅读 twitter_analyze 项目的数据模型定义
- 确认必填字段和可选字段
- 确认索引策略和查询优化方案

**输出**: 完整的数据模型字段列表（将在 Phase 1 的 data-model.md 中详细定义）

#### R4: 通知服务集成方式
**问题**: 如何复用 monitor 应用的 AlertPushService？需要什么接口和参数？

**研究内容**:
- 阅读 monitor/services/notifier.py 的实现
- 确认消息格式和推送接口
- 确认错误处理机制

**输出**: 通知服务复用指南，包括调用示例

#### R5: Django Management Command 最佳实践
**问题**: 如何实现支持异步执行、状态查询、任务取消的 Django 命令？

**研究内容**:
- 阅读 monitor 应用的现有命令（如 monitor.py, monitor_futures.py）
- 确认参数解析模式、日志记录方式
- 确认异步执行的实现方式（是否使用 Celery 或简单的后台线程）

**输出**: Django 命令实现模板和异步执行策略

### Phase 0 输出

完成后将生成 `research.md`，包含所有研究结果和技术决策。

---

## Phase 1: Design & Contracts

**前置条件**: Phase 0 研究完成

### 设计任务清单

#### D1: 数据模型设计 (`data-model.md`)
基于 Phase 0 的研究结果，详细定义：
- TwitterList 模型：字段、索引、约束
- Tweet 模型：字段、关系、去重策略
- TwitterAnalysisResult 模型：字段、状态机、存储格式

#### D2: API 合约设计 (`contracts/`)
虽然这是 Django 应用而非 REST API，但需要定义：
- Django Management Command 的参数规范
- 服务层接口（TwitterListService, AIAnalysisService）
- 异步任务接口（如果使用 Celery）

#### D3: 快速开始指南 (`quickstart.md`)
提供开发者快速上手文档：
- 环境配置（API Keys）
- 数据库迁移
- 命令行使用示例
- 常见问题排查

### Phase 1 输出

1. `data-model.md` - 数据模型详细设计
2. `contracts/management-commands.md` - 命令行接口规范
3. `quickstart.md` - 快速开始指南
4. 更新 CLAUDE.md（通过 update-agent-context.sh 脚本）

---

## Phase 2: Tasks Generation

**前置条件**: Phase 1 设计完成

此阶段由 `/speckit.tasks` 命令执行，将生成 `tasks.md`，包含：
- 按依赖关系排序的任务列表
- 每个任务的验收标准
- 测试要求
- 预估工作量

**注意**: Phase 2 不在本 `/speckit.plan` 命令的范围内。

---

## Next Steps

执行计划的下一步是运行 Phase 0 研究任务。所有研究结果将记录在 `research.md` 中。

当前状态：**Phase 0 - Ready to Start**
