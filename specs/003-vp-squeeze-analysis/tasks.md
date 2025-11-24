# Tasks: VP-Squeeze算法支撑压力位计算服务

**Input**: Design documents from `/specs/003-vp-squeeze-analysis/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: 按宪法要求包含测试任务，遵循TDD原则（先写测试，后实现）

**Organization**: 任务按用户故事分组，每个故事可独立实现和测试

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行执行（不同文件，无依赖）
- **[Story]**: 任务所属用户故事 (US1, US2, US3)
- 描述中包含精确文件路径

## Path Conventions

本项目为Django单体应用，路径结构：
- **App**: `vp_squeeze/` (新建Django app)
- **Tests**: `tests/vp_squeeze/`

---

## Phase 1: Setup (共享基础设施)

**Purpose**: 项目初始化和基本结构创建

- [x] T001 创建Django app结构 `vp_squeeze/__init__.py`, `vp_squeeze/apps.py`
- [x] T002 [P] 创建服务层目录结构 `vp_squeeze/services/__init__.py`
- [x] T003 [P] 创建指标计算模块目录 `vp_squeeze/services/indicators/__init__.py`
- [x] T004 [P] 创建management command目录 `vp_squeeze/management/__init__.py`, `vp_squeeze/management/commands/__init__.py`
- [x] T005 [P] 创建测试目录结构 `tests/vp_squeeze/__init__.py`
- [x] T006 注册app到 `listing_monitor_project/settings.py` 的 INSTALLED_APPS

---

## Phase 2: Foundational (阻塞性前置任务)

**Purpose**: 所有用户故事依赖的核心基础设施

**⚠️ CRITICAL**: 此阶段完成前，任何用户故事都不能开始

- [x] T007 创建异常类定义 `vp_squeeze/exceptions.py` (VPSqueezeError, BinanceAPIError, InsufficientDataError, InvalidSymbolError, InvalidIntervalError)
- [x] T008 创建常量和配置 `vp_squeeze/constants.py` (SYMBOL_MAP, VALID_INTERVALS, SYMBOL_GROUPS, MIN_KLINES, BB/KC参数)
- [x] T009 [P] 创建数据传输对象 `vp_squeeze/dto.py` (KLineData, SqueezeStatus, VolumeProfileResult, VPSqueezeAnalysisResult)
- [x] T010 [P] 实现基础计算函数 `vp_squeeze/services/indicators/utils.py` (sma, ema, std, atr, format_price)
- [x] T011 创建VPSqueezeResult模型 `vp_squeeze/models.py` (含Meta、索引、约束)
- [x] T012 创建数据库迁移 `python manage.py makemigrations vp_squeeze`
- [x] T013 执行数据库迁移 `python manage.py migrate`
- [x] T014 创建Admin配置 `vp_squeeze/admin.py` (VPSqueezeResultAdmin)

**Checkpoint**: 基础设施就绪 - 可以开始用户故事实现

---

## Phase 3: User Story 1 - 量化交易脚本执行 (Priority: P1) 🎯 MVP

**Goal**: 量化交易团队通过Django management command执行技术分析，获取支撑位和压力位

**Independent Test**: 执行 `python manage.py vp_analysis --symbol eth --interval 4h --limit 100`，验证输出包含VAL、VAH、VPOC、HVN、LVN和Squeeze状态

### Tests for User Story 1 ⚠️

> **NOTE**: 先写测试，确保测试失败，再实现功能

- [ ] T015 [P] [US1] 基础计算函数单元测试 `tests/vp_squeeze/test_utils.py` (test_sma, test_ema, test_std, test_atr)
- [ ] T016 [P] [US1] Bollinger Bands单元测试 `tests/vp_squeeze/test_bollinger_bands.py`
- [ ] T017 [P] [US1] Keltner Channels单元测试 `tests/vp_squeeze/test_keltner_channels.py`
- [ ] T018 [P] [US1] Volume Profile单元测试 `tests/vp_squeeze/test_volume_profile.py`
- [ ] T019 [P] [US1] Squeeze检测单元测试 `tests/vp_squeeze/test_squeeze_detector.py`
- [ ] T020 [P] [US1] 币安K线服务Mock测试 `tests/vp_squeeze/test_binance_service.py`
- [ ] T021 [US1] VP-Squeeze分析器集成测试 `tests/vp_squeeze/test_analyzer.py`

### Implementation for User Story 1

- [x] T022 [P] [US1] 实现Bollinger Bands计算 `vp_squeeze/services/indicators/bollinger_bands.py` (Period=20, Multiplier=2.0)
- [x] T023 [P] [US1] 实现Keltner Channels计算 `vp_squeeze/services/indicators/keltner_channels.py` (EMA=20, ATR=10, Multiplier=1.5)
- [x] T024 [P] [US1] 实现Volume Profile计算 `vp_squeeze/services/indicators/volume_profile.py` (0.1%分辨率, 70%价值区域, HVN/LVN百分位)
- [x] T025 [US1] 实现Squeeze检测逻辑 `vp_squeeze/services/indicators/squeeze_detector.py` (连续3根K线判定)
- [x] T026 [US1] 实现币安K线数据获取服务 `vp_squeeze/services/binance_kline_service.py` (现货API, symbol映射, interval校验)
- [x] T027 [US1] 实现VP-Squeeze核心分析器 `vp_squeeze/services/vp_squeeze_analyzer.py` (整合所有指标, 生成VPSqueezeAnalysisResult)
- [x] T028 [US1] 实现输出格式化器 `vp_squeeze/services/output_formatter.py` (文本格式, JSON格式, 动态价格精度)
- [x] T029 [US1] 实现vp_analysis命令 `vp_squeeze/management/commands/vp_analysis.py` (--symbol, --interval, --limit, --json, -v参数)
- [x] T030 [US1] 添加错误处理和用户友好提示 (数据不足、无效symbol、API错误)

**Checkpoint**: User Story 1完成 - 可通过命令行执行单币种VP-Squeeze分析

---

## Phase 4: User Story 2 - 交易分析师手动查询 (Priority: P2)

**Goal**: 交易分析师通过Django Admin后台查询历史分析结果

**Independent Test**: 登录Django Admin，查看VPSqueezeResult列表，筛选特定币种和周期

### Tests for User Story 2 ⚠️

- [ ] T031 [P] [US2] Admin列表展示测试 `tests/vp_squeeze/test_admin.py` (list_display, list_filter, search_fields)
- [ ] T032 [P] [US2] 数据持久化测试 `tests/vp_squeeze/test_persistence.py` (save, query, unique constraint)

### Implementation for User Story 2

- [x] T033 [US2] 扩展vp_analysis命令添加--save参数 `vp_squeeze/management/commands/vp_analysis.py`
- [x] T034 [US2] 实现分析结果持久化逻辑 `vp_squeeze/services/vp_squeeze_analyzer.py` (to_model方法调用)
- [x] T035 [US2] 完善Admin配置 `vp_squeeze/admin.py` (fieldsets, readonly_fields, date_hierarchy)
- [ ] T036 [US2] 添加模型属性方法 `vp_squeeze/models.py` (price_range_pct, value_area_range)

**Checkpoint**: User Story 2完成 - 分析结果可保存并通过Admin查询

---

## Phase 5: User Story 3 - 批量分析与定时任务 (Priority: P3)

**Goal**: 系统支持批量分析多个币种，便于定时任务集成

**Independent Test**: 执行 `python manage.py vp_analysis --group top10 --interval 4h --save`，验证10个币种结果

### Tests for User Story 3 ⚠️

- [ ] T037 [P] [US3] 批量分析测试 `tests/vp_squeeze/test_batch_analysis.py` (多symbol, group参数)
- [ ] T038 [P] [US3] 并发执行测试 `tests/vp_squeeze/test_concurrency.py` (10币种无性能下降)

### Implementation for User Story 3

- [x] T039 [US3] 扩展命令支持多symbol `vp_squeeze/management/commands/vp_analysis.py` (--symbol eth,btc,sol)
- [x] T040 [US3] 实现预设组合 `vp_squeeze/constants.py` 添加 SYMBOL_GROUPS['top10']
- [x] T041 [US3] 扩展命令支持--group参数 `vp_squeeze/management/commands/vp_analysis.py`
- [x] T042 [US3] 实现批量分析输出格式 `vp_squeeze/services/output_formatter.py` (多币种结果汇总)
- [x] T043 [US3] 添加批量执行进度显示 `vp_squeeze/management/commands/vp_analysis.py` (处理进度、成功/失败统计)

**Checkpoint**: User Story 3完成 - 支持批量分析，可集成到定时任务

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 影响多个用户故事的改进

- [ ] T044 [P] 运行所有测试确保通过 `python -m pytest tests/vp_squeeze/ -v`
- [x] T045 [P] 代码格式化检查 `ruff check vp_squeeze/`
- [ ] T046 验证quickstart.md中的所有命令示例
- [ ] T047 添加日志配置到 `listing_monitor_project/settings.py` (vp_squeeze logger)
- [x] T048 性能验证：单币种分析<5秒，批量10币种无性能下降

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖 - 可立即开始
- **Foundational (Phase 2)**: 依赖Setup完成 - 阻塞所有用户故事
- **User Stories (Phase 3-5)**: 依赖Foundational完成
  - 可按优先级顺序执行 (P1 → P2 → P3)
  - 或并行执行（如有多人开发）
- **Polish (Phase 6)**: 依赖所需用户故事完成

### User Story Dependencies

- **User Story 1 (P1)**: Foundational完成后可开始 - 无其他故事依赖
- **User Story 2 (P2)**: 依赖US1完成（需要有分析结果可保存）
- **User Story 3 (P3)**: 依赖US1完成（扩展单币种为批量）

### Within Each User Story

- 测试先于实现
- 基础计算函数 → 指标模块 → 服务层 → 命令层
- 每个任务完成后提交

### Parallel Opportunities

**Phase 1 并行组**:
```
T002 + T003 + T004 + T005 (不同目录，无依赖)
```

**Phase 2 并行组**:
```
T009 + T010 (DTO和工具函数，无依赖)
```

**Phase 3 (US1) 测试并行组**:
```
T015 + T016 + T017 + T018 + T019 + T020 (不同测试文件)
```

**Phase 3 (US1) 实现并行组**:
```
T022 + T023 + T024 (三个指标模块，无依赖)
```

---

## Parallel Example: User Story 1

```bash
# 同时启动所有US1测试任务:
Task: "T015 [P] [US1] 基础计算函数单元测试 tests/vp_squeeze/test_utils.py"
Task: "T016 [P] [US1] Bollinger Bands单元测试 tests/vp_squeeze/test_bollinger_bands.py"
Task: "T017 [P] [US1] Keltner Channels单元测试 tests/vp_squeeze/test_keltner_channels.py"
Task: "T018 [P] [US1] Volume Profile单元测试 tests/vp_squeeze/test_volume_profile.py"

# 同时启动所有US1指标实现任务:
Task: "T022 [P] [US1] 实现Bollinger Bands计算 vp_squeeze/services/indicators/bollinger_bands.py"
Task: "T023 [P] [US1] 实现Keltner Channels计算 vp_squeeze/services/indicators/keltner_channels.py"
Task: "T024 [P] [US1] 实现Volume Profile计算 vp_squeeze/services/indicators/volume_profile.py"
```

---

## Implementation Strategy

### MVP First (仅User Story 1)

1. 完成 Phase 1: Setup
2. 完成 Phase 2: Foundational (关键 - 阻塞所有故事)
3. 完成 Phase 3: User Story 1
4. **停止并验证**: 独立测试US1
5. 可部署/演示

### Incremental Delivery

1. Setup + Foundational → 基础就绪
2. 添加 User Story 1 → 独立测试 → MVP发布
3. 添加 User Story 2 → 独立测试 → 增量发布
4. 添加 User Story 3 → 独立测试 → 完整发布
5. 每个故事独立增加价值

---

## Notes

- [P] 任务 = 不同文件，无依赖，可并行
- [Story] 标签关联任务到用户故事
- 每个用户故事应可独立完成和测试
- 实现前确保测试失败
- 每个任务或逻辑组完成后提交
- 可在任何检查点停止验证
- 避免：模糊任务、同文件冲突、破坏独立性的跨故事依赖
