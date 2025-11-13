# Feature Specification: Twitter 应用集成与 AI 分析

**Feature Branch**: `001-twitter-app-integration`
**Created**: 2025-11-13
**Status**: Draft
**Input**: User description: "在 crypto_exchange_news_crawler 项目中创建独立的 twitter 应用，实现以下功能：从 Twitter List 获取推文数据，存储到数据库，并使用 AI 进行内容分析。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 获取和存储 Twitter List 推文 (Priority: P1)

运维人员需要从指定的 Twitter List 中获取最近的推文数据，并将这些推文持久化存储到系统数据库中，以便后续分析使用。

**Why this priority**: 这是整个功能的基础，没有推文数据就无法进行后续的 AI 分析。这是最小可用产品（MVP）的核心部分，独立交付即可产生价值（数据收集）。

**Independent Test**: 可以通过执行命令获取指定 Twitter List 的推文，验证数据库中是否成功存储了推文记录（包括作者、内容、时间戳、互动数据）。不依赖 AI 分析功能即可完成测试。

**Acceptance Scenarios**:

1. **Given** 系统配置了有效的 Twitter API 凭证和 List ID，**When** 运维人员执行推文获取命令指定时间范围，**Then** 系统成功获取该时间范围内的所有推文并存储到数据库，显示获取成功的推文数量
2. **Given** Twitter List 中有 1000 条推文，**When** 运维人员执行获取命令，**Then** 系统自动分批获取（默认 500 条/批），无需手动干预
3. **Given** 数据库中已存在某些推文记录，**When** 再次获取相同 List 的推文，**Then** 系统自动去重，不会创建重复记录
4. **Given** Twitter API 返回限流错误，**When** 系统继续尝试获取推文，**Then** 系统自动实施重试机制（指数退避），并在日志中记录重试次数

---

### User Story 2 - AI 分析推文内容并生成报告 (Priority: P2)

运维人员需要对收集到的推文进行 AI 内容分析，生成结构化的分析报告（如多空情绪、市场观点、关键信号等），以支持加密货币投研决策。

**Why this priority**: 这是核心增值功能，将原始推文数据转化为可操作的洞察。虽然重要，但在 P1 完成后才能执行（依赖推文数据）。

**Independent Test**: 可以通过提供预设的推文数据集，执行 AI 分析命令，验证是否生成了符合预期格式的分析报告，包括成本统计和处理时间。

**Acceptance Scenarios**:

1. **Given** 数据库中已有 100 条推文，**When** 运维人员执行分析命令并选择 crypto_analysis 模板，**Then** 系统调用 AI 服务分析这些推文，生成包含多空统计、关键观点、交易信号的结构化报告
2. **Given** 推文数量超过 500 条，**When** 运维人员选择批次模式执行分析，**Then** 系统自动分批调用 AI 服务，最后合并生成完整报告
3. **Given** 运维人员提供自定义 prompt 模板，**When** 执行分析命令，**Then** 系统使用自定义 prompt 进行分析，而不使用预设模板
4. **Given** 分析任务正在执行，**When** 运维人员查询任务状态，**Then** 系统显示当前进度、已处理推文数、预估剩余时间
5. **Given** 单次分析的预估成本超过配置的上限（默认 $10），**When** 执行分析命令，**Then** 系统拒绝执行并提示成本超限，建议调整参数

---

### User Story 3 - 使用高级命令选项优化工作流 (Priority: P3)

运维人员需要使用试运行模式验证配置、使用异步模式后台执行长时间任务、以及灵活选择批次或一次性分析模式，以优化日常运维效率。

**Why this priority**: 这些是便利性功能，提升用户体验但不影响核心功能价值。可以在 P1 和 P2 稳定后再实现。

**Independent Test**: 可以分别测试每个命令选项：dry-run 模式不执行实际操作但显示预估信息；async 模式立即返回任务 ID；batch-mode 控制是否分批调用 AI。

**Acceptance Scenarios**:

1. **Given** 运维人员不确定配置是否正确，**When** 使用 --dry-run 选项执行分析命令，**Then** 系统验证所有参数和权限，显示预估的推文数量和成本，但不执行实际分析
2. **Given** 运维人员需要分析大量推文（预计耗时超过 10 分钟），**When** 使用 --async 选项执行命令，**Then** 系统立即返回任务 ID 并在后台执行，运维人员可以随时查询任务状态
3. **Given** 推文数量较少（少于 100 条），**When** 运维人员不使用 --batch-mode 选项，**Then** 系统一次性将所有推文发送给 AI 分析（默认行为），减少 API 调用次数
4. **Given** 运维人员想要取消正在执行的分析任务，**When** 使用 cancel 命令并提供任务 ID，**Then** 系统停止该任务并标记为已取消状态

---

### User Story 4 - 接收分析完成通知 (Priority: P4)

运维人员希望在分析任务完成（成功或失败）时自动接收通知，以便及时查看结果或处理错误，无需持续监控系统。

**Why this priority**: 这是锦上添花的功能，提升用户体验但不影响核心功能。系统可以在没有通知的情况下正常工作（用户手动查询状态）。

**Independent Test**: 可以通过完成一次分析任务，验证是否通过配置的通知渠道（复用 monitor 应用的告警推送服务）收到通知消息。

**Acceptance Scenarios**:

1. **Given** 分析任务成功完成，**When** 系统生成最终报告，**Then** 系统通过告警推送服务发送包含任务 ID、推文数量、成本、处理时间的通知消息
2. **Given** 分析任务失败（如 AI API 错误），**When** 系统捕获错误，**Then** 系统发送失败通知，包含错误信息和任务 ID
3. **Given** 单次分析成本超过告警阈值（默认 $5），**When** 分析完成，**Then** 系统除了发送完成通知外，额外发送成本告警通知

---

### Edge Cases

- **当 Twitter List 不存在或无访问权限时**：系统应返回明确的错误信息（如 "List not found" 或 "Access denied"），不应尝试重试或继续执行
- **当时间范围内没有任何推文时**：系统应正常完成执行，返回 0 条推文的结果，不应视为错误
- **当 AI 服务返回格式错误的响应时**：系统应记录原始响应用于调试，返回友好的错误信息，并标记任务为失败状态
- **当同一 List 的多个分析任务同时执行时**：系统应能正确处理并发执行，数据库操作应避免竞争条件（使用事务）
- **当推文包含特殊字符或超长内容时**：系统应正确处理并存储，不应截断或导致数据库错误（字段长度应足够）
- **当网络不稳定导致部分推文获取失败时**：系统应记录失败的批次，允许用户重试获取缺失数据，不应丢弃已成功获取的数据

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统必须提供命令行工具，接受 Twitter List ID、时间范围（start_time, end_time）作为输入参数
- **FR-002**: 系统必须通过 Twitter API 获取指定 List 在指定时间范围内的所有推文数据
- **FR-003**: 系统必须支持分批获取推文，默认批次大小为 500 条，可通过参数配置
- **FR-004**: 系统必须在遇到 API 限流时自动实施指数退避重试机制，最多重试 3 次
- **FR-005**: 系统必须将获取的推文数据持久化存储到数据库，包括字段：推文 ID、作者信息（user_id, screen_name）、内容、发布时间、互动数据（转发数、点赞数、回复数）
- **FR-006**: 系统必须在存储推文时执行去重检查，基于推文 ID 避免重复存储
- **FR-007**: 系统必须提供 AI 分析功能，调用 DeepSeek AI 服务分析推文内容
- **FR-008**: 系统必须支持两种 prompt 模板：预设模板（crypto_analysis）和用户自定义文本
- **FR-009**: 系统必须在执行 AI 分析前估算成本，如果超过配置的上限（默认 $10.00）则拒绝执行
- **FR-010**: 系统必须支持两种分析模式：批次模式（分批调用 AI）和一次性模式（单次调用 AI）
- **FR-011**: 系统必须将 AI 分析结果存储到数据库，包括字段：任务 ID、关联的 Twitter List、时间范围、分析内容（JSON 格式）、推文数量、成本、处理时间、状态
- **FR-012**: 系统必须提供任务状态查询功能，支持查询任务的当前状态（pending, running, completed, failed）
- **FR-013**: 系统必须提供试运行模式（--dry-run），验证参数和权限但不执行实际操作，显示预估的推文数量和成本
- **FR-014**: 系统必须支持异步执行模式（--async），立即返回任务 ID 并在后台执行
- **FR-015**: 系统必须在分析任务完成（成功或失败）时，通过告警推送服务发送通知，包含任务摘要信息
- **FR-016**: 系统必须在成本超过告警阈值（默认 $5.00）时发送额外的成本告警通知
- **FR-017**: 系统必须记录详细的操作日志，包括 API 调用、错误信息、性能指标
- **FR-018**: 系统必须提供任务取消功能，允许用户取消正在执行的分析任务
- **FR-019**: 系统必须将 Twitter 功能实现为独立的 Django 应用（twitter），与现有 monitor 应用分离

### Key Entities

- **TwitterList**: 表示一个 Twitter List，包含属性：list_id（唯一标识）、名称、描述、状态（active/inactive/archived）、创建时间、更新时间。用于管理系统监控的 Twitter List 配置。

- **Tweet**: 表示一条推文，包含属性：tweet_id（主键）、twitter_list（外键关联）、user_id、screen_name、内容、发布时间、互动指标（retweet_count, favorite_count, reply_count）、创建时间。用于存储从 Twitter 获取的原始推文数据。

- **TwitterAnalysisResult**: 表示一次分析任务的结果，包含属性：task_id（UUID，唯一标识）、twitter_list（外键关联）、时间范围（start_time, end_time）、prompt 模板、推文数量、分析结果（JSON 格式，包含 AI 生成的结构化内容）、状态（pending/running/completed/failed/cancelled）、成本金额、处理时间、错误信息（如果失败）、创建时间、更新时间。用于追踪分析任务的执行情况和存储分析输出。

- **关系说明**：
  - TwitterList 与 Tweet 是一对多关系（一个 List 包含多条推文）
  - TwitterList 与 TwitterAnalysisResult 是一对多关系（一个 List 可以被多次分析）
  - TwitterAnalysisResult 间接关联多条 Tweet（通过时间范围筛选）

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 运维人员可以在 30 秒内完成一次命令执行（从输入命令到看到执行结果或任务 ID），不包括后台处理时间
- **SC-002**: 系统能够在 5 秒内获取并存储 500 条推文（单批次），包括数据库写入时间
- **SC-003**: 系统能够在 2 分钟内完成对 100 条推文的 AI 分析（一次性模式），包括 API 调用和结果存储时间
- **SC-004**: 推文去重机制能够 100% 避免重复存储相同的推文（基于 tweet_id 唯一性约束）
- **SC-005**: API 限流重试机制能够在 90% 的限流场景下成功恢复并完成数据获取
- **SC-006**: 试运行模式能够在不执行实际操作的情况下，准确预估推文数量（误差 ±5%）和分析成本（误差 ±10%）
- **SC-007**: 成本控制机制能够 100% 阻止超过上限的分析任务执行，避免意外的高额 API 费用
- **SC-008**: 通知服务能够在分析任务完成后 10 秒内发送通知消息，送达成功率达到 95%
- **SC-009**: 系统能够正确处理并存储包含特殊字符（emoji、多语言）的推文内容，无数据丢失或损坏
- **SC-010**: 异步任务的状态查询响应时间少于 1 秒，即使在高并发场景下（10 个并发查询）

## Assumptions

- 运维人员已经拥有有效的 Twitter API 访问凭证（通过第三方代理服务 apidance.pro）
- DeepSeek AI 服务稳定可用，API 响应时间通常在 5-30 秒之间
- 系统运行环境已安装 Python 3.8+ 和 Django 4.2+
- 数据库性能足以支持每秒写入 100 条推文记录
- Twitter List 中的推文数量通常不超过 10,000 条（单次获取）
- 运维人员熟悉 Django management commands 的使用方式
- 推文内容长度不超过 5,000 字符（Twitter 官方限制）
- AI 分析的输出格式为结构化 JSON，包含预定义的字段（如多空统计、关键观点等）
- 成本计算基于 token 数量，DeepSeek API 的定价稳定且可预测
- 现有 monitor 应用的告警推送服务（AlertPushService）可以直接复用，无需修改

## Dependencies

- **Twitter API 代理服务** (apidance.pro): 提供 Twitter GraphQL API 访问能力，需要有效的 API Key
- **DeepSeek AI API**: 提供推文内容分析能力，需要有效的 API Key 和充足的配额
- **monitor 应用的告警推送服务**: 用于发送通知消息，需要确保该服务已正确配置
- **参考项目** (references/twitter_analyze/): 提供 TwitterSDK 和 DeepSeekSDK 的参考实现，需要完整移植
- **Django ORM**: 用于数据模型定义和数据库操作
- **Python 依赖包**: requests (HTTP 客户端), tenacity (重试机制), python-dateutil (时间解析)

## Out of Scope

以下功能明确不在本次需求范围内，但可能在未来版本中考虑：

- Twitter 用户关注关系管理（Follow/Followers）
- 推文的实时流式获取（Streaming API）
- 推文内容的情绪分析趋势图表可视化
- 支持除 DeepSeek 之外的其他 AI 服务（如 OpenAI）
- Web UI 界面（当前仅支持命令行工具）
- 推文数据的导出功能（CSV、Excel 等格式）
- 多租户支持（当前假设单一运维团队使用）
- Twitter List 的自动化管理（创建、编辑、删除 List）
- 推文回复、转发等互动功能的追踪
- 与其他社交媒体平台的集成（如微博、Discord）

## Notes

- 本功能设计为独立的 Django 应用（twitter），与现有的 monitor 应用在架构上分离，但可以复用部分基础服务（如通知服务）
- TwitterSDK 和 DeepSeekSDK 将从参考项目（references/twitter_analyze/）完整移植，确保成熟度和稳定性
- 数据模型设计参考了 twitter_analyze 项目，但根据 crypto_exchange_news_crawler 的实际需求进行了适配
- 成本控制是本功能的重要关注点，通过预估、上限检查、告警等多层机制确保不会产生意外的高额费用
- 命令行工具设计借鉴了 monitor 应用的现有命令（如 monitor, monitor_futures），保持一致的用户体验
- 由于 Twitter API 的限流限制，推文获取可能需要较长时间，因此提供了异步执行模式以提升用户体验
