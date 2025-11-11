# Tasks: Futures Contract Data Monitor

**Input**: Design documents from `/specs/002-futures-data-monitor/`
**Prerequisites**: plan.md, spec.md, research.md

**Tests**: 根据plan.md的要求,本项目采用TDD方法,每个Service方法都有对应的单元测试

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Django项目结构:
- **Django项目根**: `listing_monitor_project/`
- **Django App**: `monitor/`
- **测试**: `monitor/tests/` (单元测试), `tests/` (集成测试)
- **配置**: `config/`
- **脚本**: `scripts/`

---

## Phase 1: Setup (共享基础设施)

**Purpose**: 项目初始化和基础结构搭建

- [X] T001 创建 monitor/api_clients/ 目录结构
- [X] T002 创建 config/futures_config.py 配置文件(交易所API配置、重试策略、轮询间隔)
- [X] T003 [P] 在 requirements.txt 添加依赖: requests, tenacity (重试库), ratelimit (速率限制)

---

## Phase 2: Foundational (阻塞性前置条件)

**Purpose**: 核心基础设施,必须在任何用户故事之前完成

**⚠️ CRITICAL**: 所有用户故事工作必须等待此阶段完成

- [X] T004 创建 FuturesContract 模型在 monitor/models.py (字段: exchange, symbol, contract_type, status, current_price, first_seen, last_updated, unique_together=[exchange, symbol])
- [X] T005 生成数据库迁移文件 monitor/migrations/000X_add_futures_contract.py
- [X] T006 [P] 创建抽象基类 BaseFuturesClient 在 monitor/api_clients/base.py (定义 fetch_contracts() 和 _normalize_symbol() 抽象方法)
- [X] T007 [P] 创建 FuturesListingNotification 模型在 monitor/models.py (字段: futures_contract, channel, timestamp, status, error_message)
- [X] T008 运行数据库迁移 python manage.py migrate
- [X] T009 [P] 配置 Django Admin: 注册 FuturesContract 和 FuturesListingNotification 在 monitor/admin.py (list_display, list_filter, search_fields)

**Checkpoint**: 基础设施就绪 - 用户故事实现现在可以并行开始

---

## Phase 3: User Story 1 - View Real-time Futures Contract Data (Priority: P1) 🎯 MVP

**Goal**: 实现从3个交易所获取合约列表和当前价格,并在Django Admin中展示

**Independent Test**: 访问 Django admin futures 页面,验证至少一个交易所的合约数据显示(包含交易所、符号、当前价格)

### Tests for User Story 1 (TDD方法)

> **NOTE: 先编写这些测试,确保它们FAIL,然后再实现功能**

- [ ] T010 [P] [US1] 为 BinanceFuturesClient 创建单元测试在 monitor/tests/api_clients/test_binance.py (测试: fetch_contracts返回格式, 符号标准化, 错误处理)
- [ ] T011 [P] [US1] 为 HyperliquidFuturesClient 创建单元测试在 monitor/tests/api_clients/test_hyperliquid.py (测试: fetch_contracts返回格式, BTC→BTCUSDT转换, 错误处理)
- [ ] T012 [P] [US1] 为 BybitFuturesClient 创建单元测试在 monitor/tests/api_clients/test_bybit.py (测试: fetch_contracts返回格式, 符号标准化, 错误处理)
- [ ] T013 [P] [US1] 为 FuturesFetcherService 创建单元测试在 monitor/tests/test_futures_fetcher.py (测试: 多交易所数据获取, 重试机制, 错误处理, 数据库更新逻辑)

### Implementation for User Story 1

#### API客户端实现 (Priority 1: Binance)

- [ ] T014 [US1] 实现 BinanceFuturesClient 在 monitor/api_clients/binance.py (调用 exchangeInfo + ticker/bookTicker, 返回标准化数据结构)
- [ ] T015 [US1] 在 BinanceFuturesClient 中实现重试机制(使用 tenacity, 3次重试, 指数退避)
- [ ] T016 [US1] 在 BinanceFuturesClient 中实现速率限制(使用 ratelimit, 20请求/秒)
- [ ] T017 [US1] 运行 test_binance.py 确保所有测试通过

#### API客户端实现 (Priority 2: Hyperliquid)

- [ ] T018 [US1] 实现 HyperliquidFuturesClient 在 monitor/api_clients/hyperliquid.py (POST /info, 实现符号格式转换 BTC→BTCUSDT)
- [ ] T019 [US1] 在 HyperliquidFuturesClient 中实现重试机制(3次重试, 指数退避)
- [ ] T020 [US1] 在 HyperliquidFuturesClient 中实现速率限制(20请求/秒)
- [ ] T021 [US1] 运行 test_hyperliquid.py 确保所有测试通过

#### API客户端实现 (Priority 3: Bybit)

- [ ] T022 [US1] 实现 BybitFuturesClient 在 monitor/api_clients/bybit.py (调用 instruments-info + tickers, 提取 lastPrice)
- [ ] T023 [US1] 在 BybitFuturesClient 中实现重试机制(3次重试, 指数退避)
- [ ] T024 [US1] 在 BybitFuturesClient 中实现速率限制(20请求/秒)
- [ ] T025 [US1] 运行 test_bybit.py 确保所有测试通过

#### Service层实现

- [ ] T026 [US1] 实现 FuturesFetcherService 在 monitor/services/futures_fetcher.py (使用所有API客户端, 实现数据获取、去重、数据库更新逻辑)
- [ ] T027 [US1] 在 FuturesFetcherService 中实现复合唯一标识逻辑(exchange + symbol)
- [ ] T028 [US1] 在 FuturesFetcherService 中实现增量更新逻辑(新增 vs 更新现有记录)
- [ ] T029 [US1] 运行 test_futures_fetcher.py 确保所有测试通过

#### Management Command

- [X] T030 [US1] 实现 fetch_futures 命令在 monitor/management/commands/fetch_futures.py (手动触发数据获取, 支持 --exchange 参数过滤)
- [ ] T031 [US1] 测试命令: python manage.py fetch_futures --exchange binance

#### Django Admin增强

- [ ] T032 [US1] 在 FuturesContract Admin 中添加自定义过滤器(按交易所、状态、价格区间)
- [ ] T033 [US1] 在 FuturesContract Admin 中添加自定义排序(按价格、按更新时间)
- [ ] T034 [US1] 在 FuturesContract Admin 中添加搜索功能(按符号搜索)
- [ ] T035 [US1] 添加颜色标记(不同交易所用不同颜色显示)

**Checkpoint**: 此时 User Story 1 应该完全功能可用且可独立测试

---

## Phase 4: User Story 2 - Receive New Futures Listing Alerts (Priority: P2)

**Goal**: 检测新合约上线并通过慧诚告警推送发送通知

**Independent Test**: 手动触发新合约检测(或等待真实新合约),验证通过配置的通道发送通知

### Tests for User Story 2 (TDD方法)

- [ ] T036 [P] [US2] 为 FuturesNotifierService 创建单元测试在 monitor/tests/test_futures_notifier.py (测试: 新合约检测, 通知发送, 去重逻辑, 初始部署不发送)

### Implementation for User Story 2

- [ ] T037 [US2] 实现 FuturesNotifierService 在 monitor/services/futures_notifier.py (检测新合约: first_seen = last_updated, 排除初始部署)
- [ ] T038 [US2] 在 FuturesNotifierService 中集成慧诚告警推送服务(复用 monitor/services/notifier.py)
- [ ] T039 [US2] 实现通知内容模板(包含: 交易所、符号、当前价格、上线时间)
- [ ] T040 [US2] 实现去重逻辑(检查 FuturesListingNotification 表, 避免重复通知)
- [ ] T041 [US2] 在 FuturesNotifierService 中实现初始部署检测(系统首次运行标识)
- [ ] T042 [US2] 运行 test_futures_notifier.py 确保所有测试通过

#### Management Command集成

- [ ] T043 [US2] 创建 monitor_futures 命令在 monitor/management/commands/monitor_futures.py (集成 fetch + notify, 一键监控)
- [ ] T044 [US2] 在 monitor_futures 命令中添加 --skip-notification 参数(用于测试)
- [ ] T045 [US2] 测试命令: python manage.py monitor_futures --skip-notification

#### Django Admin增强

- [ ] T046 [US2] 在 FuturesListingNotification Admin 中显示通知历史(状态、时间戳、错误信息)
- [ ] T047 [US2] 添加批量操作: 标记为已读、重新发送通知

**Checkpoint**: 此时 User Stories 1 和 2 应该都能独立工作

---

## Phase 5: User Story 3 - Monitor Contract Status Changes (Priority: P3)

**Goal**: 监控合约状态变化(下线/过期),并在Admin中显示状态指示

**Independent Test**: 手动标记一个合约为 delisted,验证在Admin界面中显示相应的状态指示

### Tests for User Story 3 (TDD方法)

- [ ] T048 [P] [US3] 为合约状态检测创建单元测试(测试: 检测下线合约, 90天保留逻辑)

### Implementation for User Story 3

- [ ] T049 [US3] 在 FuturesFetcherService 中实现下线检测逻辑(当前API数据中不存在但数据库有 → 标记为 delisted)
- [ ] T050 [US3] 实现90天保留策略(创建定时任务清理90天前下线的合约)
- [ ] T051 [US3] 在 FuturesContract Admin 中添加状态指示器(active显示绿色, delisted显示红色)
- [ ] T052 [US3] 在 FuturesContract Admin 中添加状态过滤器(仅显示active / 仅显示delisted)
- [ ] T053 [US3] 测试状态变化检测逻辑

**Checkpoint**: 所有用户故事现在应该都能独立功能

---

## Phase 6: Automation & Monitoring

**Purpose**: 自动化和生产环境部署

- [ ] T054 创建 Shell 脚本 scripts/monitor_futures.sh (每5分钟运行一次 monitor_futures 命令)
- [ ] T055 [P] 添加日志记录到 FuturesFetcherService (记录每次获取的结果、错误、耗时)
- [ ] T056 [P] 添加日志记录到 FuturesNotifierService (记录每次通知的结果)
- [ ] T057 配置 cron job 或 systemd timer (每5分钟运行 monitor_futures.sh)

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 影响多个用户故事的改进

- [ ] T058 [P] 创建 quickstart.md 文档在 specs/002-futures-data-monitor/ (包含: 快速开始指南、测试场景、故障排除)
- [ ] T059 [P] 创建集成测试在 tests/test_futures_integration.py (端到端测试: 数据获取 → 存储 → Admin展示 → 通知)
- [ ] T060 代码清理和重构(移除重复代码, 统一错误处理)
- [ ] T061 [P] 性能优化: 确保3个交易所总计30秒内完成
- [ ] T062 [P] 添加监控指标(数据获取成功率、通知发送成功率、平均响应时间)
- [ ] T063 安全加固(验证所有输入、防止SQL注入)
- [ ] T064 运行 quickstart.md 验证

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖 - 可立即开始
- **Foundational (Phase 2)**: 依赖 Setup 完成 - 阻塞所有用户故事
- **User Stories (Phase 3-5)**: 所有依赖 Foundational 完成
  - User Story 1 (P1): 可在 Foundational 后立即开始 - 无其他故事依赖
  - User Story 2 (P2): 可在 Foundational 后立即开始 - 但实际需要US1的数据获取功能
  - User Story 3 (P3): 可在 Foundational 后立即开始 - 需要US1的数据获取功能
- **Automation (Phase 6)**: 依赖 US1 和 US2 完成
- **Polish (Phase 7)**: 依赖所有期望的用户故事完成

### User Story Dependencies

- **User Story 1 (P1)**: 可在 Foundational 后开始 - 无其他故事依赖
- **User Story 2 (P2)**: 实际依赖 US1 (需要数据获取功能), 但可独立测试
- **User Story 3 (P3)**: 实际依赖 US1 (需要数据获取功能), 但可独立测试

### Within Each User Story

- Tests (TDD方法) 必须先编写并FAIL, 然后再实现
- API客户端按优先级顺序实现: Binance → Hyperliquid → Bybit
- Models → Services → Commands → Admin
- 核心实现 → 集成 → 增强功能
- 故事完成后再移至下一个优先级

### Parallel Opportunities

- Setup 阶段所有标记 [P] 的任务可并行
- Foundational 阶段所有标记 [P] 的任务可并行(在Phase 2内)
- Foundational 完成后, 所有用户故事可并行开始(如果团队能力允许)
- 每个用户故事中所有测试标记 [P] 可并行
- 不同用户故事可由不同团队成员并行处理

---

## Parallel Example: User Story 1

```bash
# 并行启动 User Story 1 的所有测试:
Task T010: "为 BinanceFuturesClient 创建单元测试在 monitor/tests/api_clients/test_binance.py"
Task T011: "为 HyperliquidFuturesClient 创建单元测试在 monitor/tests/api_clients/test_hyperliquid.py"
Task T012: "为 BybitFuturesClient 创建单元测试在 monitor/tests/api_clients/test_bybit.py"
Task T013: "为 FuturesFetcherService 创建单元测试在 monitor/tests/test_futures_fetcher.py"
```

---

## Implementation Strategy

### MVP First (仅 User Story 1)

1. 完成 Phase 1: Setup
2. 完成 Phase 2: Foundational (关键 - 阻塞所有故事)
3. 完成 Phase 3: User Story 1
4. **停止并验证**: 独立测试 User Story 1
5. 如果准备好则部署/演示

### Incremental Delivery

1. 完成 Setup + Foundational → 基础就绪
2. 添加 User Story 1 → 独立测试 → 部署/演示 (MVP!)
3. 添加 User Story 2 → 独立测试 → 部署/演示
4. 添加 User Story 3 → 独立测试 → 部署/演示
5. 每个故事在不破坏之前故事的情况下添加价值

### Parallel Team Strategy

多开发者情况:

1. 团队一起完成 Setup + Foundational
2. Foundational 完成后:
   - 开发者 A: User Story 1 (Binance API客户端)
   - 开发者 B: User Story 1 (Hyperliquid API客户端)
   - 开发者 C: User Story 1 (Bybit API客户端)
3. 故事独立完成并集成

---

## Notes

- [P] 任务 = 不同文件, 无依赖
- [Story] 标签将任务映射到特定用户故事以便追溯
- 每个用户故事应该能独立完成和测试
- 实现前验证测试失败
- 每个任务或逻辑组后提交
- 在任何检查点停止以独立验证故事
- 避免: 模糊任务、相同文件冲突、破坏独立性的跨故事依赖
