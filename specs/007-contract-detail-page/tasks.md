# Implementation Tasks: 合约分析详情页

**Feature**: 007-contract-detail-page
**Branch**: `007-contract-detail-page`
**Plan**: [plan.md](./plan.md)
**Spec**: [spec.md](./spec.md)

---

## Overview

本功能为做空网格筛选系统添加合约详情页，用户可点击列表中的合约查看完整的分析数据、K线图和技术指标。功能分为4个用户故事（User Stories），优先级从P1到P3，每个故事独立可测试。

### User Stories Summary

- **US1 (P1)**: 查看合约分析详情 - 基础信息和指标展示
- **US2 (P1)**: 查看关键指标K线图 - 4h K线+EMA均线+价格标注
- **US3 (P2)**: 查看多周期K线数据 - 支持15m/1h/4h/1d切换
- **US4 (P3)**: 查看VPA和规则触发信号 - K线图上标记交易信号

### MVP Scope (最小可行产品)

**推荐**: 实施US1+US2（两个P1故事），提供基础的详情页查看和K线图展示功能。US3和US4可作为后续迭代。

---

## Task Statistics

- **Total Tasks**: 45
- **Setup Phase**: 3 tasks
- **Foundational Phase**: 4 tasks
- **US1 Phase**: 10 tasks (含路由、视图、模板、指标展示)
- **US2 Phase**: 13 tasks (含K线图、EMA均线、分批渲染)
- **US3 Phase**: 6 tasks (多周期切换)
- **US4 Phase**: 6 tasks (VPA和规则信号标记)
- **Polish Phase**: 3 tasks (性能优化、文档)

**Parallelization Opportunities**: 约35%的任务可并行执行（标记为[P]）

---

## Dependencies & Execution Order

### Story Dependencies Graph

```
Setup Phase (T001-T003)
    ↓
Foundational Phase (T004-T007)
    ↓
    ├─→ US1 (T008-T017) [P1] ← MVP必须
    │       ↓
    └─→ US2 (T018-T030) [P1] ← MVP必须
            ↓
        US3 (T031-T036) [P2] ← 可选增强
            ↓
        US4 (T037-T042) [P3] ← 可选增强
            ↓
        Polish Phase (T043-T045)
```

### Parallel Execution Strategy

**Setup + Foundational阶段** (串行执行):
- 必须完成T001-T007才能开始用户故事

**US1阶段** (可并行执行3个任务流):
1. 视图+路由 (T008, T009, T010, T011)
2. 数据服务 (T012)
3. 前端模板+样式 (T013, T014, T015, T016, T017)

**US2阶段** (可并行执行2个任务流):
1. 后端API (T018, T019, T020, T021)
2. 前端图表 (T022, T023, T024, T025, T026, T027, T028, T029, T030)

**US3阶段** (串行，依赖US2):
- T031-T036按顺序执行

**US4阶段** (可并行执行2个任务流):
1. 后端信号检测 (T037, T038)
2. 前端信号渲染 (T039, T040, T041, T042)

---

## Phase 1: Setup (项目初始化)

**目标**: 创建必要的目录结构，安装图表库依赖

### Tasks

- [X] T001 创建Django模板目录结构 grid_trading/templates/grid_trading/
- [X] T002 创建静态文件目录结构 grid_trading/static/grid_trading/{js,css}/
- [X] T003 选择并引入K线图表库（推荐Lightweight Charts 4.x，备选ECharts 5.5+），在base模板中添加CDN链接或下载到static/

**验收标准**:
- [ ] 目录结构符合Django约定
- [ ] 图表库可在浏览器控制台中访问（如window.LightweightCharts存在）

---

## Phase 2: Foundational (基础设施)

**目标**: 实现共享的数据服务和URL路由基础，为所有用户故事提供支撑

### Tasks

- [X] T004 [P] 扩展ScreeningResultModel的to_dict()方法，处理None值并生成错误信息 grid_trading/django_models.py
- [X] T005 [P] 创建DetailPageService服务类，聚合详情页所需的所有数据 grid_trading/services/detail_page_service.py
- [X] T006 扩展grid_trading/urls.py，添加详情页路由占位符（/screening/daily/<date>/、/screening/daily/<date>/<symbol>/）
- [X] T007 创建404错误页面模板 grid_trading/templates/404.html

**验收标准**:
- [ ] to_dict()方法正确处理None值，返回包含error字段的JSON
- [ ] DetailPageService.prepare_detail_data()能聚合ScreeningResultModel的所有指标
- [ ] 路由配置正确，访问不存在的URL返回404页面

**Parallel Execution**: T004和T005可并行开发（不同文件）

---

## Phase 3: User Story 1 - 查看合约分析详情 (P1)

**Story Goal**: 用户能够点击筛选列表中的合约，进入详情页，查看该合约的完整分析指标（20+指标，4个维度）

**Independent Test**: 在任意日期的筛选结果页点击合约的"详情"按钮，成功跳转到详情页，页面展示基本信息、波动率指标、趋势指标、市场数据、资金流指标

### Tasks

#### 后端：路由与视图

- [ ] T008 [US1] 实现screening_daily_index视图函数，展示所有筛选日期列表 grid_trading/views.py
- [ ] T009 [US1] 实现screening_daily_detail视图函数，展示指定日期的筛选结果列表 grid_trading/views.py
- [ ] T010 [US1] 实现contract_detail视图函数，查询ScreeningResultModel并调用DetailPageService grid_trading/views.py
- [ ] T011 [US1] 在contract_detail视图中处理404场景（日期不存在、合约不存在） grid_trading/views.py

#### 后端：数据服务

- [ ] T012 [P] [US1] 在DetailPageService中实现prepare_detail_data()方法，聚合基本信息、指标、网格参数、挂单建议 grid_trading/services/detail_page_service.py

#### 前端：模板与样式

- [ ] T013 [P] [US1] 创建screening_daily.html模板，展示日期列表和筛选结果表格 grid_trading/templates/grid_trading/screening_daily.html
- [ ] T014 [P] [US1] 在screening_daily.html的合约行添加"详情"按钮，链接到详情页URL grid_trading/templates/grid_trading/screening_daily.html
- [ ] T015 [P] [US1] 创建screening_detail.html模板，布局包括：基本信息区、指标明细区、K线图占位区、网格参数区、挂单建议区 grid_trading/templates/grid_trading/screening_detail.html
- [ ] T016 [P] [US1] 在screening_detail.html中展示基本信息（symbol、price、rank、GSS、screening_date） grid_trading/templates/grid_trading/screening_detail.html
- [ ] T017 [P] [US1] 在screening_detail.html中展示4个维度的指标，支持"计算失败"显示+Tooltip(FR-028) grid_trading/templates/grid_trading/screening_detail.html

**Parallel Execution**:
- T008-T011串行（同一文件）
- T012独立并行
- T013-T017并行（不同模板区域）

**Acceptance Criteria**:
- [ ] 访问/grid_trading/screening/daily/显示所有日期列表
- [ ] 访问/grid_trading/screening/daily/2024-12-05/显示该日期的筛选结果，每行有"详情"按钮
- [ ] 点击"详情"按钮跳转到/grid_trading/screening/daily/2024-12-05/ZENUSDT/
- [ ] 详情页顶部显示symbol、当前价格、排名、综合指数
- [ ] 详情页展示20+指标，按波动率、趋势、市场、资金流4个维度分组
- [ ] 计算失败的指标显示"计算失败ⓘ"，鼠标悬停显示Tooltip说明原因
- [ ] 访问不存在的日期或合约返回友好404页面，包含"返回列表"按钮和最近5个日期链接

---

## Phase 4: User Story 2 - 查看关键指标K线图 (P1)

**Story Goal**: 在详情页展示4h K线图（300根），叠加EMA99/EMA20均线，标注当前价格、网格上下限、止盈止损位，支持鼠标悬停查看K线详情

**Independent Test**: 进入任意合约详情页，页面加载后看到K线图，图表显示300根4h K线、EMA99蓝色线、EMA20橙色线、当前价格虚线

### Tasks

#### 后端：K线数据API

- [ ] T018 [US2] 创建api_klines视图函数，接收date、symbol、interval、limit参数 grid_trading/views.py
- [ ] T019 [US2] 在api_klines中调用KlineCache.get_klines()获取K线数据 grid_trading/views.py
- [ ] T020 [US2] 在api_klines中调用IndicatorCalculator.calculate_ema_slope()计算EMA99和EMA20 grid_trading/views.py
- [ ] T021 [US2] 在api_klines中处理K线数据不足的场景，返回warnings字段 grid_trading/views.py

#### 前端：K线图渲染（分批渲染策略）

- [ ] T022 [P] [US2] 创建screening_detail.js，实现图表初始化和分批渲染流程 grid_trading/static/grid_trading/js/screening_detail.js
- [ ] T023 [P] [US2] 实现renderStage1()：渲染K线蜡烛图（绿涨红跌），使用Lightweight Charts或ECharts grid_trading/static/grid_trading/js/screening_detail.js
- [ ] T024 [P] [US2] 实现renderStage1()：从API-4获取K线数据，设置candlestickSeries grid_trading/static/grid_trading/js/screening_detail.js
- [ ] T025 [P] [US2] 实现renderStage1()：如果data.warnings存在，显示黄色警告横幅（FR-019） grid_trading/static/grid_trading/js/screening_detail.js
- [ ] T026 [P] [US2] 实现renderStage2()：叠加EMA99均线（蓝色#2196F3） grid_trading/static/grid_trading/js/screening_detail.js
- [ ] T027 [P] [US2] 实现renderStage2()：叠加EMA20均线（橙色#FF9800） grid_trading/static/grid_trading/js/screening_detail.js
- [ ] T028 [P] [US2] 实现renderStage2()：标注当前价格水平虚线（蓝色#2962FF） grid_trading/static/grid_trading/js/screening_detail.js
- [ ] T029 [P] [US2] 在screening_detail.html中添加图表容器div#chart，引入screening_detail.js grid_trading/templates/grid_trading/screening_detail.html
- [ ] T030 [P] [US2] 创建screening_detail.css，定义图表容器样式、警告横幅样式 grid_trading/static/grid_trading/css/screening_detail.css

**Parallel Execution**:
- T018-T021串行（同一文件，API逻辑有依赖）
- T022-T028并行（JavaScript同一文件但不同函数）
- T029-T030并行（不同文件）

**Acceptance Criteria**:
- [ ] 访问/api/screening/2024-12-05/ZENUSDT/klines/?interval=4h&limit=300返回JSON，包含klines、ema99、ema20字段
- [ ] 详情页K线图在<500ms内显示蜡烛图骨架（阶段1）
- [ ] 详情页K线图在<1.5s累计时间内叠加EMA99和EMA20均线（阶段2）
- [ ] K线图使用国际标准配色：绿色上涨、红色下跌
- [ ] K线图标注当前价格水平虚线
- [ ] 鼠标悬停在K线上显示Tooltip（时间、开高低收、成交量）
- [ ] 如果K线数据不足300根，图表顶部显示黄色警告横幅"数据不足，仅显示XX根K线(需要300根)"

**Performance Target**: 符合FR-025的分批渲染时间要求

---

## Phase 5: User Story 3 - 查看多周期K线数据 (P2)

**Story Goal**: 在K线图上方添加周期切换器（15m、1h、4h、1d），用户点击后图表切换到对应周期的K线，EMA均线重新计算

**Independent Test**: 在详情页K线图上方点击"15m"按钮，图表更新为15分钟K线（100根），EMA均线相应调整

### Tasks

- [ ] T031 [US3] 在screening_detail.html的K线图上方添加周期切换器按钮组（15m、1h、4h、1d） grid_trading/templates/grid_trading/screening_detail.html
- [ ] T032 [US3] 在screening_detail.js中实现switchInterval()函数，接收interval参数 grid_trading/static/grid_trading/js/screening_detail.js
- [ ] T033 [US3] 在switchInterval()中重新调用api_klines API，传递新的interval和对应的limit grid_trading/static/grid_trading/js/screening_detail.js
- [ ] T034 [US3] 在switchInterval()中清空当前图表的所有Series grid_trading/static/grid_trading/js/screening_detail.js
- [ ] T035 [US3] 在switchInterval()中重新执行renderStage1+renderStage2渲染新周期的K线和均线 grid_trading/static/grid_trading/js/screening_detail.js
- [ ] T036 [US3] 在周期切换器中高亮当前选中的周期按钮 grid_trading/static/grid_trading/css/screening_detail.css

**Acceptance Criteria**:
- [ ] K线图上方显示4个周期按钮（15m、1h、4h、1d），默认选中4h
- [ ] 点击"15m"按钮，图表切换为15分钟K线，显示100根
- [ ] 点击"1h"按钮，图表切换为1小时K线，显示50根
- [ ] 点击"1d"按钮，图表切换为日线K线，显示30根
- [ ] 切换周期后，EMA99和EMA20均线基于新周期K线重新计算并显示
- [ ] 周期切换响应时间<1秒（符合SC-006）

---

## Phase 6: User Story 4 - 查看VPA和规则触发信号 (P3)

**Story Goal**: 在K线图上标记VPA模式（急刹车、金针探底、攻城锤、阳包阴）和规则6/7触发点，鼠标悬停显示详细信息

**Independent Test**: 选择一个历史上触发过规则6的合约和日期，进入详情页，K线图上看到绿色向上箭头标记，鼠标悬停显示"规则6触发: 急刹车+RSI超卖"

### Tasks

#### 后端：信号检测

- [ ] T037 [P] [US4] 在api_klines视图中调用VPA检测服务，识别K线中的VPA模式 grid_trading/views.py
- [ ] T038 [P] [US4] 在api_klines视图中调用RuleEngine.check_all_rules_batch()，检测规则6/7触发点 grid_trading/views.py

#### 前端：信号标记渲染

- [ ] T039 [P] [US4] 在screening_detail.js中实现renderStage3()：遍历data.vpa_signals，使用Marker标记VPA模式 grid_trading/static/grid_trading/js/screening_detail.js
- [ ] T040 [P] [US4] 在renderStage3()中为VPA模式设置图标（bullish=圆圈belowBar，bearish=圆圈aboveBar） grid_trading/static/grid_trading/js/screening_detail.js
- [ ] T041 [P] [US4] 在renderStage3()中遍历data.rule_signals，标记规则6（绿色向上箭头）和规则7（红色向下箭头） grid_trading/static/grid_trading/js/screening_detail.js
- [ ] T042 [P] [US4] 在Marker的tooltip中显示规则详细信息（VPA模式、技术信号、RSI值、触发时间） grid_trading/static/grid_trading/js/screening_detail.js

**Parallel Execution**:
- T037-T038并行（不同逻辑模块）
- T039-T042并行（JavaScript不同函数）

**Acceptance Criteria**:
- [ ] api_klines返回的JSON包含vpa_signals和rule_signals字段
- [ ] K线图上显示VPA模式标记（急刹车、金针探底、攻城锤、阳包阴），位置正确
- [ ] K线图上显示规则6触发点（绿色向上箭头），规则7触发点（红色向下箭头）
- [ ] 鼠标悬停在信号标记上显示详细信息（如"规则6触发: 急刹车+RSI超卖，RSI=18.5"）
- [ ] 信号标记在<2s累计时间内完成渲染（阶段3）

---

## Phase 7: Polish & Cross-Cutting Concerns (收尾与优化)

**目标**: 性能优化、错误处理、文档完善

### Tasks

- [ ] T043 [P] 添加详情页加载指示器（Loading Spinner），在K线图渲染期间显示 grid_trading/static/grid_trading/js/screening_detail.js
- [ ] T044 [P] 添加图表渲染错误处理，捕获API失败和图表库错误，显示友好错误信息 grid_trading/static/grid_trading/js/screening_detail.js
- [ ] T045 [P] 更新项目README.md，添加详情页功能说明和开发指南 README.md

**Parallel Execution**: 所有3个任务可并行执行

**Acceptance Criteria**:
- [ ] 详情页初始加载时显示Loading Spinner，图表渲染完成后自动隐藏
- [ ] 如果API调用失败（网络错误、404），页面显示错误提示"K线图加载失败，请刷新页面重试"
- [ ] README.md包含详情页的功能说明、URL示例、开发指南

---

## Implementation Strategy

### MVP First (最小可行产品优先)

**Phase 1 MVP** (必须完成):
- Setup + Foundational (T001-T007)
- User Story 1 (T008-T017) - 基础详情页
- User Story 2 (T018-T030) - K线图展示

**Total MVP Tasks**: 30 tasks (约67%的工作量)

**MVP Deliverable**: 用户可以点击筛选列表中的合约，查看详情页，页面展示20+指标和4h K线图（含EMA均线），满足核心需求。

### Incremental Delivery (增量交付)

**Phase 2 Enhancement**:
- User Story 3 (T031-T036) - 多周期切换
- 提供更灵活的分析工具，用户可以从不同时间维度验证信号

**Phase 3 Enhancement**:
- User Story 4 (T037-T042) - VPA和规则信号标记
- 可视化交易信号，帮助用户识别关键入场/出场点

**Phase 4 Polish**:
- Polish Phase (T043-T045)
- 性能优化和文档完善

### Parallel Execution Examples

**Setup阶段** (串行):
```
T001 → T002 → T003
```

**Foundational阶段** (部分并行):
```
开发者A: T004 (扩展to_dict)
开发者B: T005 (创建DetailPageService)
  ↓
T006 → T007 (串行，路由和404模板)
```

**US1阶段** (3个并行流):
```
流1 (视图):   T008 → T009 → T010 → T011
流2 (服务):   T012
流3 (前端):   T013 → T014 ← (串行)
              ↓
            T015 → T016 → T017 (并行，不同模板区域)
```

**US2阶段** (2个并行流):
```
流1 (后端API):  T018 → T019 → T020 → T021
流2 (前端图表):  T022 → T023 → T024 → T025
                 ↓
               T026 → T027 → T028 (并行，不同渲染阶段)
                 ↓
               T029 → T030 (模板和样式)
```

---

## Testing Strategy (可选)

本功能规格未明确要求TDD，但建议在关键模块添加测试：

### 推荐测试点

1. **DetailPageService单元测试**:
   - 测试prepare_detail_data()正确聚合数据
   - 测试None值处理和错误信息生成

2. **API Endpoint集成测试**:
   - 测试api_klines返回正确的JSON结构
   - 测试K线数据不足时返回warnings字段
   - 测试404场景返回正确的HTTP状态码

3. **前端渲染测试** (可选，使用Selenium):
   - 测试K线图在<500ms内首次可见
   - 测试周期切换功能正确更新图表
   - 测试VPA信号标记正确显示

### 测试命令

```bash
# Django单元测试
python manage.py test grid_trading.tests.test_detail_page

# 前端E2E测试（可选）
pytest tests/e2e/test_detail_page_chart.py --headed
```

---

## Notes

- **图表库选择**: plan.md推荐Lightweight Charts（轻量级、专为金融图表优化），如果功能不足可升级为ECharts
- **性能目标**: 严格遵守FR-025的分批渲染时间要求（阶段1<500ms，阶段2<1.5s，阶段3<2s）
- **数据追溯**: K线数据来自screening_date时刻的历史快照，非实时最新价格
- **错误透明度**: 所有计算失败的指标必须显示原因（FR-028），不能隐藏或用默认值替代
- **渐进增强**: US3和US4是可选增强功能，MVP只需完成US1+US2
- **移动端**: 本版本不考虑移动端适配，专注桌面网页版

---

## Next Steps

1. **开始实施**: 从Setup阶段（T001-T003）开始，按顺序执行任务
2. **检查点**: 完成Foundational阶段后，验证所有基础服务和路由正常工作
3. **MVP验收**: 完成US1+US2后，进行完整的用户验收测试
4. **迭代增强**: 根据用户反馈决定是否实施US3和US4

---

**Generated**: 2025-12-12
**Total Tasks**: 45
**Estimated MVP Effort**: 30 tasks (US1+US2)
**Parallel Opportunities**: ~35% tasks can run in parallel
