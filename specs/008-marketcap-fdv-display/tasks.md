# Tasks: Market Cap & FDV Display Integration

**Input**: Design documents from `/specs/008-marketcap-fdv-display/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: Tests are NOT explicitly requested in the feature specification. Test tasks are omitted per specification guidance.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

Based on plan.md, this is a Django Web application extending the existing `grid_trading` app:
- Models: `grid_trading/models/`
- Services: `grid_trading/services/`
- Management Commands: `grid_trading/management/commands/`
- Templates: `grid_trading/templates/grid_trading/`
- Static files: `grid_trading/static/grid_trading/`
- Migrations: `grid_trading/migrations/`
- Scripts: `scripts/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and dependency configuration

- [x] T001 Install tenacity dependency (add to requirements.txt)
- [x] T002 Configure CoinGecko API key in .env file and listing_monitor_project/settings.py
- [x] T003 [P] Create grid_trading/models/ directory for new data models
- [x] T004 [P] Create grid_trading/services/ directory structure for API clients and services

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core database schema and base services that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 Create TokenMapping model in grid_trading/models/token_mapping.py (symbol, base_token, coingecko_id, match_status, alternatives, timestamps)
- [ ] T006 [P] Create MarketData model in grid_trading/models/market_data.py (symbol, market_cap, fully_diluted_valuation, data_source, fetched_at, timestamps)
- [ ] T007 [P] Create UpdateLog model in grid_trading/models/update_log.py (batch_id, symbol, operation_type, status, error_message, executed_at, metadata)
- [ ] T008 Generate and run Django migration for 3 new models (run makemigrations and migrate commands)
- [ ] T009 Verify database tables and indexes created correctly (token_mapping, market_data, update_log with 10 indexes)
- [ ] T010 [P] Implement CoingeckoClient base class in grid_trading/services/coingecko_client.py (API封装+限流处理+重试机制)
- [ ] T011 [P] Implement CoingeckoClient._request method with tenacity retry and 429 handling
- [ ] T012 [P] Implement CoingeckoClient.fetch_coins_list method for /coins/list endpoint
- [ ] T013 [P] Implement CoingeckoClient.fetch_market_data method for /coins/markets endpoint (batch 250, 60s delay)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 2 - 建立币安symbol与CoinGecko ID的映射关系 (Priority: P1) 🎯

**Goal**: 建立自动化映射机制,系统管理员可以生成币安symbol到CoinGecko ID的映射表,并支持人工审核确认

**Independent Test**:
1. 运行 `python manage.py generate_token_mapping` 成功获取币安合约列表
2. 映射表在数据库中创建,包含symbol、coingecko_id、match_status字段
3. 自动匹配准确率≥85%,needs_review≤15%
4. 在Django Admin中可以查看和编辑needs_review状态的映射

**Why US2 before US1**: 映射关系是整个数据流的起点,必须先建立才能获取市值/FDV数据

### Implementation for User Story 2

- [ ] T014 [P] [US2] Implement MappingService class in grid_trading/services/mapping_service.py (初始化,依赖CoingeckoClient和Binance Client)
- [ ] T015 [P] [US2] Implement MappingService.get_binance_usdt_perpetuals method (获取币安USDT永续合约列表,使用futures_exchange_info)
- [ ] T016 [US2] Implement MappingService.match_coingecko_id method (symbol匹配逻辑,调用fetch_coins_list)
- [ ] T017 [US2] Implement MappingService._resolve_conflict method (同名消歧:交易量→市值排名→needs_review优先级链)
- [ ] T018 [US2] Implement MappingService.generate_mappings method (完整映射生成流程,@transaction.atomic,记录UpdateLog)
- [ ] T019 [US2] Create generate_token_mapping Django management command in grid_trading/management/commands/generate_token_mapping.py
- [ ] T020 [US2] Register TokenMapping model in grid_trading/admin.py (添加list_display, list_filter, search_fields支持审核)
- [ ] T021 [US2] Add TokenMapping model methods: is_ready_for_update, __str__ in token_mapping.py
- [ ] T022 [US2] Add validation and error handling for mapping generation (API失败,网络错误,数据格式异常)
- [ ] T023 [US2] Add logging for mapping generation operations (batch开始/结束,匹配状态,需要审核数量)

**Checkpoint**: 运行generate_token_mapping命令后,数据库中有完整的TokenMapping记录,可在Django Admin中查看和审核

---

## Phase 4: User Story 3 - 定期更新市值和FDV数据 (Priority: P2)

**Goal**: 实现自动化脚本定期从CoinGecko获取市值/FDV数据并存储到数据库,确保数据时效性

**Independent Test**:
1. 运行 `python manage.py update_market_data` 成功获取市值/FDV数据
2. 数据库中MarketData表有≥95%的合约数据(对应auto_matched/manual_confirmed状态的映射)
3. UpdateLog记录显示成功/失败数量和详细错误信息
4. 部分失败时(如API限流),脚本继续处理其他symbol并记录失败项

**Dependencies**: 依赖US2完成(需要TokenMapping数据)

### Implementation for User Story 3

- [ ] T024 [P] [US3] Implement MarketDataService class in grid_trading/services/market_data_service.py (初始化,依赖CoingeckoClient)
- [ ] T025 [US3] Implement MarketDataService.update_all method (批量更新市值/FDV,@transaction.atomic,记录UpdateLog)
- [ ] T026 [P] [US3] Implement MarketDataService.update_single method (单个symbol更新,用于失败重试)
- [ ] T027 [US3] Create update_market_data Django management command in grid_trading/management/commands/update_market_data.py
- [ ] T028 [US3] Add MarketData model properties: market_cap_formatted, fdv_formatted in market_data.py (K/M/B格式化)
- [ ] T029 [US3] Add MarketData model method: _format_number static method in market_data.py (数字格式化逻辑)
- [ ] T030 [US3] Add UpdateLog model class methods: log_batch_start, log_batch_complete, log_symbol_error in update_log.py
- [ ] T031 [US3] Add validation for market data updates (NULL值处理,DecimalField精度,fetched_at时间戳)
- [ ] T032 [US3] Add error handling for API failures (429限流重试,503服务不可用,部分成功处理)
- [ ] T033 [US3] Add logging for data update operations (批次统计,失败symbol列表,执行时长)

**Checkpoint**: 运行update_market_data命令后,数据库中有最新的MarketData记录,UpdateLog显示详细的执行结果

---

## Phase 5: User Story 1 - 查看合约市值和FDV数据 (Priority: P1) 🎯 MVP

**Goal**: 在/screening/daily/页面展示市值和FDV数据,用户可以看到格式化的数值,支持排序,无数据时显示"-"

**Independent Test**:
1. 访问 http://127.0.0.1:8000/screening/daily/ 页面,看到"市值"和"FDV"两列
2. 有数据的合约显示K/M/B格式的数值(如 $1.23B, $456.78M)
3. 无数据的合约显示"-"占位符
4. 点击列标题可以按市值/FDV升序/降序排序
5. 鼠标悬停显示数据更新时间(Tooltip)
6. 页面加载增量<200ms,排序响应<100ms

**Dependencies**: 依赖US2和US3完成(需要TokenMapping和MarketData数据)

### Implementation for User Story 1

- [ ] T034 [P] [US1] Create Django template filter format_market_cap in grid_trading/templatetags/market_filters.py (K/M/B格式化逻辑)
- [ ] T035 [US1] Modify get_daily_screening_detail view in grid_trading/views.py (添加LEFT JOIN MarketData的annotate查询)
- [ ] T036 [US1] Update daily_screening.html template in grid_trading/templates/grid_trading/daily_screening.html (添加市值和FDV两列)
- [ ] T037 [US1] Add market_cap and fdv columns to table header with sortable attributes in daily_screening.html
- [ ] T038 [US1] Add market_cap and fdv data cells using format_market_cap filter in daily_screening.html
- [ ] T039 [US1] Add Tooltip to show updated_at timestamp on hover in daily_screening.html (使用Bootstrap Tooltip或data-title属性)
- [ ] T040 [US1] Update frontend sorting logic in grid_trading/static/grid_trading/js/daily_screening.js (处理"-"值,排在最后)
- [ ] T041 [US1] Add CSS styles for market cap and FDV columns in grid_trading/static/grid_trading/css/daily_screening.css (对齐,颜色,悬停效果)
- [ ] T042 [US1] Test page load performance (使用Django Debug Toolbar或Chrome DevTools,确保增量<200ms)
- [ ] T043 [US1] Test sorting performance (点击列标题,确保响应<100ms)
- [ ] T044 [US1] Add database query optimization if needed (检查EXPLAIN结果,添加select_related或prefetch_related)

**Checkpoint**: 访问/screening/daily/页面可以看到完整的市值和FDV列,所有功能正常,性能达标

---

## Phase 6: User Story 4 - 手动更新映射关系 (Priority: P3)

**Goal**: 系统管理员可以手动更新特定symbol的映射关系,处理新合约上线或修正错误映射

**Independent Test**:
1. 运行 `python manage.py update_token_mapping --symbols BTCUSDT,ETHUSDT` 只更新指定的symbol
2. 如果新ID与现有不同,提示管理员确认是否覆盖
3. 更新成功后,数据库中的映射关系已修改,UpdateLog记录变更
4. 如果symbol在CoinGecko中找不到,保留现有映射并记录警告

**Dependencies**: 依赖US2完成(扩展映射功能)

### Implementation for User Story 4

- [ ] T045 [P] [US4] Add MappingService.update_mapping_for_symbols method in mapping_service.py (指定symbol列表更新)
- [ ] T046 [P] [US4] Add MappingService.confirm_overwrite_prompt method in mapping_service.py (交互式确认覆盖)
- [ ] T047 [US4] Create update_token_mapping Django management command in grid_trading/management/commands/update_token_mapping.py
- [ ] T048 [US4] Add --symbols argument parser in update_token_mapping.py (支持逗号分隔的symbol列表)
- [ ] T049 [US4] Add --force flag to skip confirmation prompt in update_token_mapping.py (自动化场景使用)
- [ ] T050 [US4] Add validation for symbol existence in update_token_mapping.py (检查symbol是否在币安合约列表中)
- [ ] T051 [US4] Add logging for manual update operations (记录哪些symbol被更新,是否覆盖,最终结果)
- [ ] T052 [US4] Add UpdateLog entry for manual mapping updates (operation_type="mapping_update",包含变更详情)

**Checkpoint**: 运行update_token_mapping命令可以成功更新指定symbol的映射,所有变更被记录

---

## Phase 7: Scheduled Tasks & Monitoring

**Goal**: 配置定时任务自动更新数据,添加监控脚本检查系统健康状态

**Dependencies**: 依赖US2和US3完成(需要mapping和data update命令)

### Implementation

- [ ] T053 [P] Create sync_binance_contracts Django management command in grid_trading/management/commands/sync_binance_contracts.py (检测新合约并触发映射)
- [ ] T054 [P] Create cron_update_market_data.sh script in scripts/cron_update_market_data.sh (调用sync_binance_contracts和update_market_data)
- [ ] T055 Set executable permission for cron script (chmod +x scripts/cron_update_market_data.sh)
- [ ] T056 [P] Create monitor_market_data.py monitoring script in scripts/monitor_market_data.py (检查覆盖率,成功率,告警)
- [ ] T057 Configure crontab for daily 4am execution (添加cron entry: 0 4 * * *)
- [ ] T058 [P] Add notification support in cron script (成功/失败通知,集成现有推送机制)
- [ ] T059 Test cron script execution manually (运行./scripts/cron_update_market_data.sh,检查日志输出)
- [ ] T060 Verify monitoring script alerts (手动触发低覆盖率/低成功率场景,验证告警)

**Checkpoint**: 定时任务配置完成,每日自动更新数据,监控脚本能够检测异常并告警

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 改进和优化,影响多个用户故事

- [ ] T061 [P] Add comprehensive logging across all services (统一日志格式,包含batch_id追踪)
- [ ] T062 [P] Optimize database queries for MarketData JOIN (添加必要的索引,使用annotate代替多次查询)
- [ ] T063 [P] Add cleanup job for old UpdateLog records in grid_trading/management/commands/cleanup_update_logs.py (删除30天前的日志)
- [ ] T064 Add error boundary handling for frontend display (API查询失败时的降级展示)
- [ ] T065 Update Django Admin list views with better filters and search (TokenMapping按match_status筛选,MarketData按更新时间排序)
- [ ] T066 [P] Add performance monitoring for API calls (记录每次CoinGecko调用的耗时和状态)
- [ ] T067 Run quickstart.md validation (按照quickstart.md步骤完整验证一遍,确保文档准确)
- [ ] T068 Document troubleshooting steps based on implementation experience (更新quickstart.md的Troubleshooting章节)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 2 (Phase 3)**: Depends on Foundational - 映射关系是数据流起点
- **User Story 3 (Phase 4)**: Depends on US2 - 需要TokenMapping数据才能更新市值/FDV
- **User Story 1 (Phase 5)**: Depends on US2 and US3 - 需要完整的数据才能展示
- **User Story 4 (Phase 6)**: Depends on US2 - 扩展映射功能
- **Scheduled Tasks (Phase 7)**: Depends on US2 and US3 - 定时执行mapping和data update
- **Polish (Phase 8)**: Depends on all core user stories being complete

### User Story Dependencies

```
Foundational (Phase 2) - MUST complete first
    ↓
US2: 建立映射关系 (Phase 3) - P1 - 数据流起点
    ↓
    ├─→ US3: 定期更新数据 (Phase 4) - P2 - 获取市值/FDV
    │       ↓
    └─→ US1: 前端展示 (Phase 5) - P1 - MVP最终交付

US4: 手动更新映射 (Phase 6) - P3 - 扩展US2功能,可独立开发

Scheduled Tasks (Phase 7) - 依赖US2+US3

Polish (Phase 8) - 依赖所有核心功能完成
```

### Critical Path for MVP (User Story 1)

1. Phase 1: Setup (T001-T004)
2. Phase 2: Foundational (T005-T013) ⚠️ 阻塞所有功能
3. Phase 3: US2 映射关系 (T014-T023) ⚠️ 必须先建立映射
4. Phase 4: US3 数据更新 (T024-T033) ⚠️ 必须先获取数据
5. Phase 5: US1 前端展示 (T034-T044) ✅ MVP交付

**MVP最小范围**: Phase 1 + Phase 2 + Phase 3 + Phase 4 + Phase 5 (共44个任务)

### Within Each User Story

- **US2 (映射关系)**:
  - CoingeckoClient基础 → MappingService逻辑 → Django命令 → Admin注册
  - 并行机会: T014(MappingService类), T015(获取币安合约) 可在T013完成后并行开发

- **US3 (数据更新)**:
  - MarketDataService基础 → 更新逻辑 → Django命令 → UpdateLog支持
  - 并行机会: T024(MarketDataService类), T026(单个更新) 可并行开发

- **US1 (前端展示)**:
  - Template filter → View修改 → 模板更新 → 前端JS/CSS → 性能测试
  - 并行机会: T034(Template filter), T040(JS逻辑), T041(CSS样式) 可并行开发

- **US4 (手动更新)**:
  - MappingService扩展 → Django命令 → 验证和日志
  - 并行机会: T045(update方法), T046(确认提示) 可并行开发

### Parallel Opportunities

#### Setup Phase (can all run in parallel after prerequisites)
- T001 (requirements.txt) || T002 (settings.py) || T003 (models/ dir) || T004 (services/ dir)

#### Foundational Phase (marked [P] can run in parallel)
- After T005-T008 (models + migrations) complete:
  - T010 || T011 || T012 || T013 (CoingeckoClient全部方法可并行)

#### User Story 2 (US2)
- After T013 complete:
  - T014 || T015 (MappingService类和获取合约方法)

#### User Story 3 (US3)
- After T023 complete:
  - T024 || T026 (MarketDataService类和单个更新方法)

#### User Story 1 (US1)
- After T033 complete:
  - T034 || T040 || T041 (Template filter, JS, CSS可并行)

#### User Story 4 (US4)
- After T044 complete:
  - T045 || T046 (update方法和确认提示)

#### Scheduled Tasks Phase
- After T052 complete:
  - T053 || T054 || T056 (sync命令, cron脚本, 监控脚本)

#### Polish Phase (most can run in parallel)
- After T060 complete:
  - T061 || T062 || T063 || T064 || T065 || T066 (所有优化任务)

---

## Parallel Example: Foundational Phase

```bash
# After models and migrations are complete (T005-T009):

# Launch all CoingeckoClient methods in parallel:
Task: "T010 - Implement CoingeckoClient base class"
Task: "T011 - Implement _request method with retry"
Task: "T012 - Implement fetch_coins_list method"
Task: "T013 - Implement fetch_market_data method"

# Wait for all 4 tasks to complete before proceeding to US2
```

## Parallel Example: User Story 1 (Frontend)

```bash
# After US3 data is available (T033 complete):

# Launch frontend components in parallel:
Task: "T034 - Create template filter for formatting"
Task: "T040 - Update frontend sorting logic JS"
Task: "T041 - Add CSS styles for new columns"

# Then integrate into view and template (T035-T039)
```

---

## Implementation Strategy

### MVP First (Minimum Viable Product)

**Goal**: Deliver US1 "查看市值和FDV数据" as the primary user value

1. ✅ Complete Phase 1: Setup (T001-T004)
2. ✅ Complete Phase 2: Foundational (T005-T013) - **CRITICAL PATH**
3. ✅ Complete Phase 3: US2 映射关系 (T014-T023) - **CRITICAL PATH**
4. ✅ Complete Phase 4: US3 数据更新 (T024-T033) - **CRITICAL PATH**
5. ✅ Complete Phase 5: US1 前端展示 (T034-T044) - **MVP DELIVERY**
6. **STOP and VALIDATE**: Test US1 independently
   - 访问 /screening/daily/ 页面
   - 验证市值/FDV列显示
   - 测试排序功能
   - 检查性能指标
7. Deploy/demo if ready

**MVP Task Count**: 44 tasks (T001-T044)

### Incremental Delivery

**每个阶段都是可交付增量**:

1. **Milestone 1: Foundation** (Phase 1 + Phase 2)
   - Deliverable: 数据库schema就绪,API客户端可用
   - Test: 直接调用CoingeckoClient验证API连接

2. **Milestone 2: Mapping System** (Phase 3 = US2)
   - Deliverable: 映射关系建立,可在Admin中审核
   - Test: 运行generate_token_mapping,检查数据库和Admin

3. **Milestone 3: Data Pipeline** (Phase 4 = US3)
   - Deliverable: 市值/FDV数据定期更新,日志完整
   - Test: 运行update_market_data,检查MarketData和UpdateLog

4. **Milestone 4: MVP Launch** (Phase 5 = US1) 🎯
   - Deliverable: 用户可见的市值/FDV展示,完整功能
   - Test: 前端页面验证,性能测试

5. **Milestone 5: Maintenance Tools** (Phase 6 = US4)
   - Deliverable: 手动更新工具,应对特殊情况
   - Test: 更新指定symbol,验证覆盖和日志

6. **Milestone 6: Automation** (Phase 7)
   - Deliverable: 定时任务和监控,无需人工干预
   - Test: Cron执行验证,监控告警测试

7. **Milestone 7: Production Ready** (Phase 8)
   - Deliverable: 性能优化,文档完善,生产就绪
   - Test: Quickstart验证,性能基准测试

### Parallel Team Strategy

With multiple developers:

1. **Week 1**: Team completes Setup + Foundational together (T001-T013)
   - All developers pair on critical path tasks
   - Focus: Database schema, API client foundation

2. **Week 2**: Split after Foundational complete
   - **Developer A**: US2 映射关系 (T014-T023)
   - **Developer B**: 准备US3服务层逻辑 (预读contracts/文档)
   - **Developer C**: 准备US1前端组件设计 (UI原型)

3. **Week 3**: US2 complete, proceed to US3 and US1
   - **Developer A**: US3 数据更新 (T024-T033)
   - **Developer B**: 协助US3测试和调优
   - **Developer C**: US1前端准备(等待US3数据)

4. **Week 4**: US3 complete, full team on US1
   - **All developers**: US1 前端展示 (T034-T044)
   - Parallel: Template filter || JS logic || CSS styling
   - Integration testing and performance tuning

5. **Week 5**: MVP delivered, proceed to enhancements
   - **Developer A**: US4 手动更新 (T045-T052)
   - **Developer B**: Scheduled tasks (T053-T060)
   - **Developer C**: Polish and optimization (T061-T068)

---

## Task Summary

### Total Task Count: 68 tasks

**By Phase**:
- Phase 1 (Setup): 4 tasks
- Phase 2 (Foundational): 9 tasks ⚠️ BLOCKING
- Phase 3 (US2 - P1): 10 tasks ⚠️ CRITICAL PATH
- Phase 4 (US3 - P2): 10 tasks ⚠️ CRITICAL PATH
- Phase 5 (US1 - P1): 11 tasks ⚠️ MVP TARGET
- Phase 6 (US4 - P3): 8 tasks
- Phase 7 (Scheduled): 8 tasks
- Phase 8 (Polish): 8 tasks

**MVP Scope**: 44 tasks (Phase 1-5)

**By User Story**:
- US1 (前端展示): 11 tasks - MVP交付
- US2 (映射关系): 10 tasks - 数据流起点
- US3 (数据更新): 10 tasks - 数据获取
- US4 (手动更新): 8 tasks - 维护工具

**Parallel Opportunities**: 20+ tasks marked [P]

### Independent Test Criteria

**US1 (前端展示)**:
- ✅ /screening/daily/ 页面显示市值和FDV列
- ✅ 数值格式化正确(K/M/B)
- ✅ 无数据时显示"-"
- ✅ 排序功能正常
- ✅ 性能达标(<200ms)

**US2 (映射关系)**:
- ✅ generate_token_mapping命令成功运行
- ✅ TokenMapping表有完整数据
- ✅ 自动匹配准确率≥85%
- ✅ Django Admin可审核needs_review

**US3 (数据更新)**:
- ✅ update_market_data命令成功运行
- ✅ MarketData表有≥95%覆盖率
- ✅ UpdateLog记录详细日志
- ✅ 部分失败时脚本继续执行

**US4 (手动更新)**:
- ✅ update_token_mapping命令支持--symbols参数
- ✅ 覆盖前提示确认
- ✅ 更新记录到UpdateLog
- ✅ 找不到symbol时保留现有映射

### Format Validation

✅ All tasks follow checklist format:
- ✅ All tasks start with `- [ ]`
- ✅ All tasks have sequential IDs (T001-T068)
- ✅ [P] marker present for parallelizable tasks (20+ tasks)
- ✅ [Story] label present for user story tasks (US1, US2, US3, US4)
- ✅ File paths included in descriptions
- ✅ Clear action verbs (Create, Implement, Add, Configure, etc.)

---

## Notes

- [P] tasks = different files, no dependencies, can run in parallel
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group of tasks
- Stop at any checkpoint to validate story independently
- MVP = Phase 1 + Phase 2 + Phase 3 + Phase 4 + Phase 5 (44 tasks)
- US2 必须在US3之前完成(映射是数据流起点)
- US3 必须在US1之前完成(需要数据才能展示)
- US4 可独立开发,不阻塞MVP
- Performance targets: 页面加载增量<200ms, 排序响应<100ms, 数据覆盖率≥90%, 更新成功率≥95%
