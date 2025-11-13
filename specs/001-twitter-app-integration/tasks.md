---
description: "Twitter 应用集成与 AI 分析 - 任务清单"
---

# Tasks: Twitter 应用集成与 AI 分析

**Input**: 设计文档来自 `/specs/001-twitter-app-integration/`
**Prerequisites**: spec.md (4个用户故事), plan.md (技术栈和架构), research.md (5个研究主题), data-model.md (5个模型), contracts/management-commands.md (4个命令)

**Tests**: 根据规范，每个用户故事都包含测试任务

**Organization**: 任务按用户故事分组，每个用户故事可独立实现和测试

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行执行（不同文件，无依赖）
- **[Story]**: 任务所属的用户故事（US1, US2, US3, US4）
- 所有描述都包含具体的文件路径

## 项目路径约定

- 项目根目录: `/Users/chenchiyuan/projects/crypto_exchange_news_crawler/`
- Django 应用: `twitter/` (新创建)
- 现有应用: `monitor/` (复用通知服务)
- 参考代码: `references/twitter_analyze/`

---

## Phase 1: Setup (共享基础设施)

**目的**: 项目初始化和基础结构搭建
**预估工作量**: 2-3 小时

- [x] T001 创建 Django 应用目录结构 `twitter/`，包含标准子目录：`models/`, `services/`, `sdk/`, `management/commands/`, `tests/`
- [x] T002 [P] 在 `listing_monitor_project/settings.py` 中添加 `'twitter'` 到 `INSTALLED_APPS` 列表
- [x] T003 [P] 配置环境变量到 `.env.example` 文件：`TWITTER_API_KEY`, `DEEPSEEK_API_KEY`, `ALERT_PUSH_TOKEN`, `ALERT_PUSH_CHANNEL`
- [x] T004 [P] 更新 `requirements.txt` 添加依赖：`requests>=2.31.0`, `python-dateutil>=2.8.2`

**Checkpoint**: 基础项目结构就绪 ✅

---

## Phase 2: Foundational (阻塞性前置条件)

**目的**: 必须在所有用户故事之前完成的核心基础设施
**预估工作量**: 8-12 小时

**⚠️ 关键**: 在此阶段完成前，任何用户故事都无法开始

### SDK 和工具层移植

- [ ] T005 [P] 移植 `references/twitter_analyze/utils/rate_limiter.py` 到 `twitter/sdk/rate_limiter.py`，支持令牌桶和滑动窗口策略
- [ ] T006 [P] 移植 `references/twitter_analyze/utils/retry_manager.py` 到 `twitter/sdk/retry_manager.py`，实现指数退避重试
- [ ] T007 [P] 移植 `references/twitter_analyze/utils/twitter_sdk.py` 到 `twitter/sdk/twitter_sdk.py`，包含所有 GraphQL API 封装
- [ ] T008 [P] 移植 `references/twitter_analyze/utils/deepseek_sdk.py` 到 `twitter/sdk/deepseek_sdk.py`，包含成本估算和 token 计数
- [ ] T009 编写 SDK 集成测试 `twitter/tests/test_sdk.py`，验证 Twitter 和 DeepSeek API 连通性

### 基础数据模型

- [ ] T010 [P] 创建软删除基类 `twitter/models/soft_delete.py`，包含 `SoftDeleteModel` 和 `SoftDeleteManager`
- [ ] T011 [P] 创建 Tag 模型在 `twitter/models/tag.py`，包含字段：`name` (unique), `created_at`, `deleted_at`
- [ ] T012 创建数据库迁移文件 `twitter/migrations/0001_initial.py`，运行 `python manage.py makemigrations twitter`
- [ ] T013 执行数据库迁移 `python manage.py migrate twitter`，验证表创建成功

**Checkpoint**: 基础架构就绪 - 用户故事实现可以并行开始

---

## Phase 3: User Story 1 - 获取和存储 Twitter List 推文 (Priority: P1) 🎯 MVP

**目标**: 从指定 Twitter List 获取推文并存储到数据库
**独立测试**: 执行 `collect_twitter_list` 命令，验证数据库中是否成功存储推文记录
**预估工作量**: 12-16 小时

### 数据模型 (US1)

- [ ] T014 [P] [US1] 创建 TwitterList 模型在 `twitter/models/twitter_list.py`，字段：`list_id` (unique), `name`, `description`, `status`, `tags` (M2M), `created_at`, `updated_at`, `deleted_at`
- [ ] T015 [P] [US1] 创建 Tweet 模型在 `twitter/models/tweet.py`，字段：`tweet_id` (PK), `twitter_list` (FK), `user_id`, `screen_name`, `user_name`, `content`, `tweet_created_at`, `retweet_count`, `favorite_count`, `reply_count`, `created_at`, `deleted_at`
- [ ] T016 [US1] 在 `twitter/models/__init__.py` 中导出所有模型，确保 Django 自动发现
- [ ] T017 [US1] 创建数据库迁移文件 `twitter/migrations/0002_twitterlist_tweet.py`，运行 `python manage.py makemigrations twitter`
- [ ] T018 [US1] 执行数据库迁移，验证表和索引创建成功

### 推文获取服务 (US1)

- [ ] T019 [US1] 实现 `TwitterListService` 在 `twitter/services/twitter_list_service.py`，包含方法：`get_tweets_in_range()`, `save_tweets_to_db()`
- [ ] T020 [US1] 在 `TwitterListService` 中实现去重逻辑，使用 `bulk_create(ignore_conflicts=True)`
- [ ] T021 [US1] 在 `TwitterListService` 中实现分批获取逻辑，默认批次大小 500 条
- [ ] T022 [US1] 在 `TwitterListService` 中集成限流器和重试管理器，处理 Twitter API 限流

### Management Command (US1)

- [ ] T023 [US1] 创建 `collect_twitter_list` 命令在 `twitter/management/commands/collect_twitter_list.py`，实现参数解析（`list_id`, `--hours`, `--start-time`, `--end-time`, `--batch-size`, `--dry-run`）
- [ ] T024 [US1] 在 `collect_twitter_list` 命令中实现时间参数解析，支持 ISO 格式和相对时间
- [ ] T025 [US1] 在 `collect_twitter_list` 命令中实现 dry-run 模式，显示预估推文数量
- [ ] T026 [US1] 在 `collect_twitter_list` 命令中实现进度显示和执行摘要输出

### 测试 (US1)

- [ ] T027 [P] [US1] 编写 Tweet 模型单元测试在 `twitter/tests/test_models.py`，验证去重约束和字段验证
- [ ] T028 [P] [US1] 编写 TwitterListService 单元测试在 `twitter/tests/test_services.py`，验证推文获取和去重逻辑
- [ ] T029 [US1] 编写 `collect_twitter_list` 命令集成测试在 `twitter/tests/test_commands.py`，验证完整的数据收集流程

**Checkpoint**: User Story 1 完全可用，可独立测试和部署

**验收标准**:
- ✅ 成功获取指定时间范围内的推文
- ✅ 推文 100% 去重（基于 tweet_id）
- ✅ 支持分批获取（500 条/批次）
- ✅ API 限流自动重试机制生效

---

## Phase 4: User Story 2 - AI 分析推文内容并生成报告 (Priority: P2)

**目标**: 对收集的推文执行 AI 内容分析，生成结构化报告
**独立测试**: 执行 `analyze_twitter_list` 命令，验证生成的 analysis_result JSON 格式
**预估工作量**: 16-20 小时

### 数据模型 (US2)

- [ ] T030 [US2] 创建 TwitterAnalysisResult 模型在 `twitter/models/twitter_analysis_result.py`，字段：`task_id` (UUID, PK), `twitter_list` (FK), `start_time`, `end_time`, `prompt_template`, `tweet_count`, `analysis_result` (JSONField), `status`, `error_message`, `cost_amount`, `processing_time`, `created_at`, `updated_at`, `deleted_at`
- [ ] T031 [US2] 创建数据库迁移文件 `twitter/migrations/0003_twitteranalysisresult.py`
- [ ] T032 [US2] 执行数据库迁移，验证 JSONField 和索引创建成功

### AI 分析服务 (US2)

- [ ] T033 [US2] 实现 `AIAnalysisService` 在 `twitter/services/ai_analysis_service.py`，包含方法：`estimate_cost()`, `analyze_tweets()`
- [ ] T034 [US2] 在 `AIAnalysisService` 中实现成本估算逻辑，调用 `DeepSeekSDK.count_tokens()` 和 `estimate_cost()`
- [ ] T035 [US2] 在 `AIAnalysisService` 中实现批次分析模式，支持分批调用 AI API（每批 100 条推文）
- [ ] T036 [US2] 在 `AIAnalysisService` 中实现一次性分析模式，适用于少量推文（<100 条）
- [ ] T037 [US2] 创建预设 prompt 模板文件在 `twitter/templates/prompts/crypto_analysis.txt`

### 流程编排 (US2)

- [ ] T038 [US2] 实现 `TwitterAnalysisOrchestrator` 在 `twitter/services/orchestrator.py`，编排完整的分析流程：获取推文 → 估算成本 → 执行分析 → 保存结果
- [ ] T039 [US2] 在 Orchestrator 中实现成本上限检查（默认 $10），超限拒绝执行
- [ ] T040 [US2] 在 Orchestrator 中实现任务状态管理，支持状态转换：pending → running → completed/failed

### Management Command (US2)

- [ ] T041 [US2] 创建 `analyze_twitter_list` 命令在 `twitter/management/commands/analyze_twitter_list.py`，实现参数解析（`list_id`, `--hours`, `--prompt`, `--batch-mode`, `--batch-size`, `--max-cost`, `--dry-run`）
- [ ] T042 [US2] 在 `analyze_twitter_list` 命令中实现 prompt 模板加载，支持预设模板和自定义文件路径
- [ ] T043 [US2] 在 `analyze_twitter_list` 命令中实现 dry-run 模式，显示预估推文数量和成本
- [ ] T044 [US2] 在 `analyze_twitter_list` 命令中实现执行摘要输出，包含多空情绪统计

### 测试 (US2)

- [ ] T045 [P] [US2] 编写 TwitterAnalysisResult 模型单元测试在 `twitter/tests/test_models.py`，验证状态转换和 JSON 字段
- [ ] T046 [P] [US2] 编写 AIAnalysisService 单元测试在 `twitter/tests/test_services.py`，验证成本估算和批次分析逻辑
- [ ] T047 [P] [US2] 编写 Orchestrator 单元测试在 `twitter/tests/test_services.py`，验证流程编排和错误处理
- [ ] T048 [US2] 编写 `analyze_twitter_list` 命令集成测试在 `twitter/tests/test_commands.py`，验证完整的分析流程

**Checkpoint**: User Story 1 和 2 都可独立工作

**验收标准**:
- ✅ 成功调用 DeepSeek AI 分析推文
- ✅ 成本预估误差 ±10%
- ✅ 生成结构化 JSON 分析结果
- ✅ 成本超限拒绝执行（100% 阻止）
- ✅ 批次模式和一次性模式都可用

---

## Phase 5: User Story 3 - 使用高级命令选项优化工作流 (Priority: P3)

**目标**: 提供 dry-run、异步执行、任务查询、任务取消功能
**独立测试**: 分别测试 `--dry-run`, `--async`, `query_analysis_task`, `cancel_analysis_task`
**预估工作量**: 10-14 小时

### 异步执行支持 (US3)

- [ ] T049 [US3] 在 `analyze_twitter_list` 命令中实现 `--async` 参数，创建任务记录并立即返回 task_id
- [ ] T050 [US3] 在 `TwitterAnalysisOrchestrator` 中实现任务状态更新逻辑，支持实时更新 `tweet_count` 和 `processing_time`
- [ ] T051 [US3] 创建后台任务处理脚本 `twitter/management/commands/process_pending_tasks.py`，定期检查并执行 pending 任务

### 任务查询和取消 (US3)

- [ ] T052 [US3] 创建 `query_analysis_task` 命令在 `twitter/management/commands/query_analysis_task.py`，实现参数：`task_id`, `--result`, `--format` (text/json)
- [ ] T053 [US3] 在 `query_analysis_task` 命令中实现任务状态展示，包含进度百分比和预估剩余时间
- [ ] T054 [US3] 在 `query_analysis_task` 命令中实现 JSON 格式输出（`--format json`）
- [ ] T055 [US3] 创建 `cancel_analysis_task` 命令在 `twitter/management/commands/cancel_analysis_task.py`，实现参数：`task_id`, `--force`
- [ ] T056 [US3] 在 `cancel_analysis_task` 命令中实现任务取消逻辑，更新状态为 `cancelled`

### Dry-run 模式增强 (US3)

- [ ] T057 [US3] 在 `collect_twitter_list` 命令的 dry-run 模式中添加推文数量预估（误差 ±5%）
- [ ] T058 [US3] 在 `analyze_twitter_list` 命令的 dry-run 模式中添加成本和时间预估

### 测试 (US3)

- [ ] T059 [P] [US3] 编写异步执行集成测试在 `twitter/tests/test_commands.py`，验证任务创建和状态查询
- [ ] T060 [P] [US3] 编写任务取消集成测试在 `twitter/tests/test_commands.py`，验证取消逻辑和状态转换
- [ ] T061 [P] [US3] 编写 dry-run 模式测试在 `twitter/tests/test_commands.py`，验证预估准确性

**Checkpoint**: 所有用户故事都可独立运行

**验收标准**:
- ✅ `--dry-run` 准确预估推文数量（±5%）和成本（±10%）
- ✅ `--async` 立即返回 task_id，后台执行
- ✅ 任务状态查询响应时间 <1 秒
- ✅ 成功取消 running 状态的任务

---

## Phase 6: User Story 4 - 接收分析完成通知 (Priority: P4)

**目标**: 任务完成时自动发送通知，包含成功/失败通知和成本告警
**独立测试**: 完成一次分析任务，验证收到通知消息
**预估工作量**: 6-8 小时

### 通知服务集成 (US4)

- [ ] T062 [US4] 创建 `TwitterNotificationService` 在 `twitter/services/notifier.py`，复用 `monitor.services.notifier.AlertPushService`
- [ ] T063 [US4] 在 `TwitterNotificationService` 中实现 `send_completion_notification()` 方法，格式化任务摘要信息
- [ ] T064 [US4] 在 `TwitterNotificationService` 中实现 `send_cost_alert()` 方法，当成本超过阈值（默认 $5）时发送告警
- [ ] T065 [US4] 在 `TwitterNotificationService` 中实现 `send_failure_notification()` 方法，包含错误信息和任务 ID

### 通知触发集成 (US4)

- [ ] T066 [US4] 在 `TwitterAnalysisOrchestrator.mark_as_completed()` 中集成通知发送
- [ ] T067 [US4] 在 `TwitterAnalysisOrchestrator.mark_as_failed()` 中集成失败通知发送
- [ ] T068 [US4] 在成本超过 $5 时触发成本告警通知

### 测试 (US4)

- [ ] T069 [P] [US4] 编写通知服务单元测试在 `twitter/tests/test_services.py`，验证消息格式化逻辑
- [ ] T070 [P] [US4] 编写通知集成测试在 `twitter/tests/test_commands.py`，验证完成通知和失败通知发送

**Checkpoint**: 所有 4 个用户故事都完全可用

**验收标准**:
- ✅ 分析成功完成时发送通知（包含任务 ID、推文数、成本、时间）
- ✅ 分析失败时发送错误通知（包含错误信息）
- ✅ 成本超过 $5 时发送额外告警
- ✅ 通知送达成功率 ≥95%

---

## Phase 7: Polish & Cross-Cutting Concerns

**目的**: 改进所有用户故事的质量和可维护性
**预估工作量**: 8-10 小时

### Django Admin 配置

- [ ] T071 [P] 在 `twitter/admin.py` 中注册 TwitterList 模型，配置列表展示和筛选器
- [ ] T072 [P] 在 `twitter/admin.py` 中注册 Tweet 模型，配置只读字段和搜索
- [ ] T073 [P] 在 `twitter/admin.py` 中注册 TwitterAnalysisResult 模型，配置状态筛选和 JSON 展示

### 日志和错误处理优化

- [ ] T074 在所有 SDK 中添加详细日志（使用 Python logging），记录 API 调用、重试、成本
- [ ] T075 在所有 Service 中添加异常处理和日志记录，确保错误可追溯
- [ ] T076 在所有 Management Command 中统一错误输出格式（参考 contracts/management-commands.md）

### 文档和工具

- [ ] T077 [P] 创建初始化数据脚本 `twitter/management/commands/init_twitter_data.py`，创建默认标签（Crypto, DeFi, NFT）
- [ ] T078 [P] 更新 `specs/001-twitter-app-integration/quickstart.md`，添加实际使用示例和故障排查
- [ ] T079 验证 quickstart.md 中的所有命令可正常执行，修复任何错误

### 性能优化

- [ ] T080 在 Tweet 模型查询中使用 `select_related('twitter_list')` 减少 N+1 查询
- [ ] T081 在 TwitterList 查询中使用 `prefetch_related('tags')` 优化多对多查询
- [ ] T082 为 TwitterAnalysisResult 的 `analysis_result` 字段添加 GIN 索引（仅 PostgreSQL）

### 代码质量

- [ ] T083 运行 `ruff check .` 和 `black .`，修复所有 linting 和格式化问题
- [ ] T084 运行完整的测试套件 `pytest twitter/tests/`，确保所有测试通过
- [ ] T085 代码审查：检查所有文件的注释、类型提示、异常处理

---

## 依赖关系和执行顺序

### Phase 依赖关系

- **Setup (Phase 1)**: 无依赖 - 可立即开始
- **Foundational (Phase 2)**: 依赖 Setup 完成 - **阻塞所有用户故事**
- **User Stories (Phase 3-6)**: 所有依赖 Foundational 完成
  - 用户故事可并行执行（如果有多人协作）
  - 或按优先级顺序执行（P1 → P2 → P3 → P4）
- **Polish (Phase 7)**: 依赖所有目标用户故事完成

### 用户故事依赖关系

- **User Story 1 (P1)**: 在 Foundational 后可开始 - 无其他故事依赖
- **User Story 2 (P2)**: 在 Foundational 后可开始 - 依赖 US1 的 Tweet 模型（T015），但可独立测试
- **User Story 3 (P3)**: 在 Foundational 后可开始 - 依赖 US2 的 TwitterAnalysisResult 模型（T030），但可独立测试
- **User Story 4 (P4)**: 在 Foundational 后可开始 - 依赖 US2 的 Orchestrator（T038），但可独立测试

### 每个用户故事内部

- 数据模型 → 服务层 → Management Command → 测试
- 标记 [P] 的任务可并行执行（不同文件）
- 测试应在实现后立即编写并验证通过

### 并行执行机会

- Phase 1 中所有 [P] 任务可并行
- Phase 2 中所有 [P] 任务可并行
- Phase 2 完成后，US1、US2、US3、US4 可并行开发（如果团队有多人）
- 每个用户故事内的 [P] 任务可并行

---

## 并行示例: User Story 2

```bash
# 同时创建数据模型（不同文件）
Task T030: "创建 TwitterAnalysisResult 模型"

# 同时编写测试（不同文件）
Task T045: "TwitterAnalysisResult 模型单元测试"
Task T046: "AIAnalysisService 单元测试"
Task T047: "Orchestrator 单元测试"
```

---

## 实施策略

### MVP 优先（仅 User Story 1）

1. 完成 Phase 1: Setup (2-3h)
2. 完成 Phase 2: Foundational (8-12h) - **关键阻塞点**
3. 完成 Phase 3: User Story 1 (12-16h)
4. **停止并验证**: 独立测试 User Story 1
5. 如果就绪可部署/演示

**总工作量（MVP）**: 约 22-31 小时

### 增量交付

1. 完成 Setup + Foundational → 基础就绪
2. 添加 User Story 1 → 独立测试 → 部署/演示（MVP 完成！）
3. 添加 User Story 2 → 独立测试 → 部署/演示（AI 分析可用）
4. 添加 User Story 3 → 独立测试 → 部署/演示（高级选项可用）
5. 添加 User Story 4 → 独立测试 → 部署/演示（通知功能可用）
6. 每个故事都增加价值，不破坏已有功能

**总工作量（全部功能）**: 约 64-83 小时

### 并行团队策略

如果有多名开发者：

1. 团队共同完成 Setup + Foundational (10-15h)
2. Foundational 完成后分工：
   - 开发者 A: User Story 1 (12-16h)
   - 开发者 B: User Story 2 (16-20h，等待 A 完成 T015 Tweet 模型）
   - 开发者 C: User Story 3 (10-14h，等待 B 完成 T030 AnalysisResult 模型）
   - 开发者 D: User Story 4 (6-8h，等待 B 完成 T038 Orchestrator）
3. 故事完成后独立集成和测试

**总工作量（并行）**: 约 26-35 小时（wall-clock time）

---

## 工作量估算总结

| Phase | 任务数 | 预估工作量 | 关键交付物 |
|-------|-------|-----------|-----------|
| Phase 1: Setup | 4 | 2-3h | Django 应用结构、环境配置 |
| Phase 2: Foundational | 9 | 8-12h | SDK、基础模型、数据库迁移 |
| Phase 3: US1 (P1) | 16 | 12-16h | 推文获取和存储（MVP） |
| Phase 4: US2 (P2) | 19 | 16-20h | AI 分析功能 |
| Phase 5: US3 (P3) | 13 | 10-14h | 高级命令选项 |
| Phase 6: US4 (P4) | 9 | 6-8h | 通知服务 |
| Phase 7: Polish | 15 | 8-10h | Admin、文档、优化 |
| **总计** | **85** | **64-83h** | **完整功能交付** |

---

## MVP 范围建议

**最小可用产品（MVP）应包含**:
- ✅ Phase 1: Setup
- ✅ Phase 2: Foundational
- ✅ Phase 3: User Story 1（推文获取和存储）

**MVP 可选增强**:
- User Story 2（AI 分析）- 核心价值增值功能
- User Story 3 中的 `--dry-run` 模式 - 提升用户体验

**Post-MVP 功能**:
- User Story 3（异步执行、任务管理）
- User Story 4（通知服务）
- Phase 7（Polish）

---

## 注意事项

- [P] 标记的任务 = 不同文件，无依赖，可并行
- [Story] 标签将任务映射到特定用户故事，便于追溯
- 每个用户故事应可独立完成和测试
- 在实现前确保测试失败（TDD 原则）
- 每个任务或逻辑组完成后提交代码
- 在任何 Checkpoint 处停下来独立验证用户故事
- 避免：模糊的任务、同文件冲突、破坏独立性的跨故事依赖

---

## 快速启动命令参考

### MVP 测试命令

```bash
# 1. 收集推文（User Story 1）
python manage.py collect_twitter_list 1234567890 --hours 24

# 2. 试运行验证
python manage.py collect_twitter_list 1234567890 --hours 24 --dry-run

# 3. 查看收集的推文
python manage.py shell
>>> from twitter.models import Tweet
>>> Tweet.objects.count()
```

### 完整功能测试命令

```bash
# 1. 分析推文（User Story 2）
python manage.py analyze_twitter_list 1234567890 --hours 24 --prompt crypto_analysis

# 2. 异步执行（User Story 3）
python manage.py analyze_twitter_list 1234567890 --hours 168 --async

# 3. 查询任务状态（User Story 3）
python manage.py query_analysis_task <task-id>

# 4. 查看完整结果（User Story 3）
python manage.py query_analysis_task <task-id> --result --format json

# 5. 取消任务（User Story 3）
python manage.py cancel_analysis_task <task-id>
```

---

**生成时间**: 2025-11-13
**下一步**: 执行 `/speckit.implement` 开始实施 Phase 1
