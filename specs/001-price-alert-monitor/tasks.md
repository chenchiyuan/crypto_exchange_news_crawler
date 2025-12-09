# Tasks: 价格触发预警监控系统

**Feature**: 001-price-alert-monitor
**Generated**: 2025-12-08
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.yaml

**架构说明**: 本系统采用**定时批量处理**架构,通过两个独立的Django管理命令协同工作:
1. **数据更新脚本**(每5分钟): 批量获取监控合约的1m/15m/4h K线数据
2. **合约监控脚本**(数据更新后): 检测5种价格触发规则并推送通知

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行执行(不同文件,无依赖)
- **[Story]**: 任务所属用户故事(US1, US2, US3, US4, US5)
- 所有任务包含精确的文件路径

---

## Phase 1: Setup (共享基础设施)

**目的**: 项目初始化和数据库迁移准备

- [ ] T001 在grid_trading/django_models.py中添加7个新模型定义(MonitoredContract, PriceAlertRule, AlertTriggerLog, DataUpdateLog, SystemConfig, ScriptLock, 复用KlineData)
- [ ] T002 创建数据库迁移文件: grid_trading/migrations/0XXX_create_price_monitor_models.py
- [ ] T003 创建索引迁移文件: grid_trading/migrations/0XXX_add_price_monitor_indexes.py
- [ ] T004 创建初始数据迁移文件: grid_trading/migrations/0XXX_initialize_price_monitor_data.py (插入5条规则和6条系统配置)

**检查点**: 数据库结构准备完成,可开始功能实现

---

## Phase 2: Foundational (阻塞性前置任务)

**目的**: 核心基础设施,所有用户故事都依赖这些组件

**⚠️ 关键**: 在此阶段完成前,任何用户故事都无法开始实现

- [ ] T005 [P] 实现脚本锁机制: grid_trading/services/script_lock.py (acquire_lock, release_lock函数)
- [ ] T006 [P] 封装价格预警通知服务: grid_trading/services/alert_notifier.py (PriceAlertNotifier类,封装AlertPushService)
- [ ] T007 [P] 实现规则判定工具函数: grid_trading/services/rule_utils.py (calculate_ma, calculate_price_distribution, validate_kline_continuity)
- [ ] T008 执行数据库迁移: python manage.py migrate grid_trading
- [ ] T009 验证初始数据: 确认5条规则和6条配置已创建

**检查点**: 基础设施就绪,用户故事实现可以并行开始

---

## Phase 3: User Story 4 - 定时数据更新与批量规则检测 (Priority: P1) 🎯 MVP核心

**目标**: 实现系统的核心工作流程:数据更新脚本每5分钟获取K线数据,监控脚本检测规则并推送通知

**独立测试**: 手动执行`python manage.py update_price_monitor_data`更新数据,然后执行`python manage.py check_price_alerts`检测规则,验证整个流程耗时<5分钟

### 实现任务

- [ ] T010 [P] [US4] 创建数据更新管理命令: grid_trading/management/commands/update_price_monitor_data.py
- [ ] T011 [P] [US4] 创建合约监控管理命令: grid_trading/management/commands/check_price_alerts.py
- [ ] T012 [US4] 实现数据更新逻辑: 在update_price_monitor_data.py中实现handle()方法,调用KlineCache更新所有监控合约的1m/15m/4h K线
- [ ] T013 [US4] 添加数据完整性检测: 调用rule_utils.validate_kline_continuity()检测K线连续性,记录警告日志
- [ ] T014 [US4] 添加执行日志记录: 在数据更新脚本中创建DataUpdateLog记录,记录开始/结束时间、合约数量、K线数量
- [ ] T015 [US4] 实现规则检测逻辑: 在check_price_alerts.py中实现handle()方法,遍历监控合约并调用规则引擎
- [ ] T016 [US4] 添加脚本锁保护: 在两个脚本的handle()开头使用acquire_lock(),结束时释放锁,避免并发执行
- [ ] T017 [US4] 添加脚本执行超时处理: 锁超时设置为10分钟,记录超时告警日志

**检查点**: 两个核心脚本可独立运行,数据更新→规则检测→推送通知的完整流程可验证

---

## Phase 4: User Story 5 - 价格触发规则的精确判定逻辑 (Priority: P2)

**目标**: 实现5种价格触发规则的判定算法,基于K线数据计算MA均线和价格分布区间

**独立测试**: 准备测试K线数据,调用规则引擎检测每条规则,验证判定逻辑准确率100%

### 实现任务

- [ ] T018 [P] [US5] 实现规则引擎核心类: grid_trading/services/rule_engine.py (PriceRuleEngine类)
- [ ] T019 [P] [US5] 实现规则1判定: check_rule_1_7d_high() - 7天价格新高(4h)
- [ ] T020 [P] [US5] 实现规则2判定: check_rule_2_7d_low() - 7天价格新低(4h)
- [ ] T021 [P] [US5] 实现规则3判定: check_rule_3_ma20_touch() - 价格触及MA20(±0.5%阈值)
- [ ] T022 [P] [US5] 实现规则4判定: check_rule_4_ma99_touch() - 价格触及MA99(±0.5%阈值)
- [ ] T023 [P] [US5] 实现规则5判定: check_rule_5_price_distribution() - 价格达到分布区间90%极值
- [ ] T024 [US5] 实现边界情况处理: 在规则1和2中添加降级逻辑,数据不足7天时使用已有数据并标记degraded=True
- [ ] T025 [US5] 集成规则引擎到监控脚本: 在check_price_alerts.py中实例化PriceRuleEngine,遍历启用的规则并调用相应判定方法

**检查点**: 5种规则判定逻辑全部实现,可通过单元测试验证准确性

---

## Phase 5: User Story 1 - 手动配置合约监控与接收推送 (Priority: P1) 🎯 MVP用户交互

**目标**: 管理员可以在后台手动添加监控合约,系统检测到触发规则时立即推送通知,防重复机制确保1小时内同规则仅推送一次

**独立测试**: 在Django Admin中手动添加BTCUSDT合约,执行监控脚本,当价格触发规则时收到推送消息,再次触发同规则时因防重复机制不推送

### 实现任务

- [ ] T026 [P] [US1] 注册模型到Django Admin: 在grid_trading/admin.py中注册MonitoredContract、PriceAlertRule、AlertTriggerLog、DataUpdateLog、SystemConfig
- [ ] T027 [P] [US1] 配置MonitoredContract的Admin界面: 添加list_display、list_filter、search_fields,支持手动添加/编辑/删除
- [ ] T028 [US1] 实现防重复推送检查: 在rule_engine.py中实现should_push_alert()方法,查询AlertTriggerLog判断是否在防重复间隔内
- [ ] T029 [US1] 实现触发事件处理: 在rule_engine.py中实现process_trigger()方法,检查防重复→推送通知→记录AlertTriggerLog
- [ ] T030 [US1] 集成触发处理到监控脚本: 在check_price_alerts.py中,规则触发时调用process_trigger()
- [ ] T031 [US1] 实现推送消息格式化: 在alert_notifier.py的send_price_alert()中格式化消息,包含合约代码、规则名称、当前价格、触发时间、额外信息(MA值、7天高低等)
- [ ] T032 [US1] 添加推送失败重试: 在check_price_alerts.py开头添加retry_failed_pushes()逻辑,补偿推送最近1小时失败的触发

**检查点**: 管理员可手动管理监控合约,触发规则时收到推送,防重复机制生效

---

## Phase 6: User Story 3 - 灵活配置规则与防重复间隔 (Priority: P1)

**目标**: 管理员可以在后台启用/禁用每条规则,修改防重复推送间隔,动态调整MA触及阈值和价格分布分位数

**独立测试**: 在Django Admin中禁用规则1,执行监控脚本验证该规则不再触发;修改防重复间隔为30分钟,验证推送间隔变化

### 实现任务

- [ ] T033 [P] [US3] 配置PriceAlertRule的Admin界面: 添加list_display(显示启用状态)、list_editable(快速启用/禁用)、fieldsets(分组显示参数)
- [ ] T034 [P] [US3] 配置SystemConfig的Admin界面: 添加list_display、search_fields,支持快速修改配置值
- [ ] T035 [US3] 实现规则启用状态检查: 在check_price_alerts.py中查询PriceAlertRule.objects.filter(enabled=True)仅检测启用的规则
- [ ] T036 [US3] 实现动态防重复间隔: 在should_push_alert()中调用SystemConfig.get_value('duplicate_suppress_minutes')获取当前配置
- [ ] T037 [US3] 实现动态规则参数: 在规则3和4中从PriceAlertRule.parameters读取ma_threshold,在规则5中读取percentile
- [ ] T038 [US3] 添加配置验证: 在SystemConfig模型中添加clean()方法,验证duplicate_suppress_minutes≥5分钟

**检查点**: 管理员可动态调整规则配置和防重复间隔,无需重启服务

---

## Phase 7: User Story 2 - 基于筛选结果自动监控合约 (Priority: P2)

**目标**: 系统每日定时从`/screening/daily/` API同步最近7天的筛选结果,自动添加新合约到监控列表,标记7天未出现的合约为过期

**独立测试**: 手动执行`python manage.py sync_screening_contracts`命令,验证能从筛选API获取合约并更新监控列表,输出新增/更新/过期的合约数量

### 实现任务

- [ ] T039 [P] [US2] 创建同步管理命令: grid_trading/management/commands/sync_screening_contracts.py
- [ ] T040 [P] [US2] 实现筛选合约同步服务: grid_trading/services/contract_sync_service.py (ContractSyncService类)
- [ ] T041 [US2] 实现API日期列表获取: 在ContractSyncService中实现get_screening_dates()方法,调用`/screening/daily/api/dates/`获取最近7天日期
- [ ] T042 [US2] 实现逐日筛选结果获取: 实现get_screening_results(date)方法,调用`/screening/daily/api/{date}/`获取单日结果
- [ ] T043 [US2] 实现合约自动添加逻辑: 实现add_or_update_contract()方法,如果合约不存在则创建(source='auto'),如果存在则更新last_screening_date
- [ ] T044 [US2] 实现过期合约标记: 实现mark_expired_contracts()方法,查询7天未出现的auto来源合约,标记status='expired'
- [ ] T045 [US2] 集成同步逻辑到命令: 在sync_screening_contracts.py的handle()中调用ContractSyncService的完整同步流程
- [ ] T046 [US2] 添加同步任务定时配置: 在README或部署文档中说明crontab配置(每日10:30执行)

**检查点**: 自动同步功能完整,可手动触发验证,准备配置定时任务

---

## Phase 8: REST API实现 (Priority: P2)

**目标**: 提供REST API接口供前端或外部系统调用,支持监控合约管理、规则配置、触发日志查询、系统配置修改

**独立测试**: 使用curl或Postman测试所有API端点,验证CRUD操作和查询功能

### 实现任务

- [ ] T047 [P] 创建监控合约视图集: grid_trading/views/monitored_contract_viewset.py (继承ModelViewSet)
- [ ] T048 [P] 创建触发规则视图集: grid_trading/views/price_alert_rule_viewset.py
- [ ] T049 [P] 创建触发日志视图集: grid_trading/views/alert_trigger_log_viewset.py
- [ ] T050 [P] 创建系统配置视图集: grid_trading/views/system_config_viewset.py
- [ ] T051 [P] 创建数据更新日志视图集: grid_trading/views/data_update_log_viewset.py
- [ ] T052 实现监控合约序列化器: grid_trading/serializers/monitored_contract_serializer.py (包含基础序列化器和详情序列化器)
- [ ] T053 [P] 实现其他模型序列化器: serializers/price_alert_rule_serializer.py, alert_trigger_log_serializer.py, system_config_serializer.py
- [ ] T054 实现批量同步API端点: 在monitored_contract_viewset.py中添加@action方法batch_sync(),调用ContractSyncService
- [ ] T055 实现触发日志统计API: 在alert_trigger_log_viewset.py中添加@action方法statistics(),返回各规则的触发次数和推送成功率
- [ ] T056 配置URL路由: 在grid_trading/urls.py中注册所有ViewSet到DRF Router,配置前缀/api/v1/price-monitor/
- [ ] T057 添加API权限控制: 配置DRF权限类,确保仅登录用户可访问(IsAuthenticated)

**检查点**: 所有REST API端点可通过HTTP客户端访问,符合contracts/api.yaml规范

---

## Phase 9: 监控仪表盘 (Priority: P3)

**目标**: 提供Web仪表盘展示监控状态,包括当前监控合约数量、今日触发次数、最近推送记录、最后数据更新时间

**独立测试**: 访问仪表盘页面,验证所有统计数据正确显示,页面加载时间<2秒

### 实现任务

- [ ] T058 [P] 创建仪表盘视图: grid_trading/views/price_monitor_dashboard.py (DashboardView类)
- [ ] T059 [P] 创建仪表盘模板: grid_trading/templates/grid_trading/price_monitor_dashboard.html
- [ ] T060 实现仪表盘统计数据聚合: 在DashboardView中查询监控合约数量、今日触发次数、最近10条推送记录、最后更新时间
- [ ] T061 实现前端图表展示: 在模板中使用Chart.js或ECharts展示触发趋势图(最近7天每日触发次数)
- [ ] T062 添加实时刷新功能: 使用AJAX每30秒刷新统计数据,无需刷新整个页面
- [ ] T063 配置仪表盘URL路由: 在grid_trading/urls.py中添加路由path('price-monitor/dashboard/', DashboardView.as_view())
- [ ] T064 添加导航菜单入口: 在Django Admin侧边栏或顶部菜单添加"价格监控仪表盘"链接

**检查点**: 仪表盘可访问,实时展示监控状态和统计数据

---

## Phase 10: Polish & Cross-Cutting Concerns (优化与完善)

**目的**: 跨用户故事的改进,代码质量和性能优化

- [ ] T065 [P] 添加日志配置: 在settings.py中配置grid_trading模块的日志级别和输出格式
- [ ] T066 [P] 性能优化-查询优化: 在监控脚本中使用prefetch_related优化K线数据查询,减少N+1问题
- [ ] T067 [P] 性能优化-批量处理: 当监控合约数量>200时,自动分片处理,每批100个合约
- [ ] T068 [P] 添加错误告警: 当数据更新或监控脚本连续失败3次时,发送告警通知给管理员
- [ ] T069 数据清理脚本: 创建management command clean_old_logs.py,清理6个月前的AlertTriggerLog和3个月前的DataUpdateLog
- [ ] T070 [P] 代码规范检查: 运行ruff check grid_trading/ 修复所有linting错误
- [ ] T071 [P] 类型注解补充: 为所有服务类和函数添加完整的类型注解(Type Hints)
- [ ] T072 验证quickstart.md: 按照quickstart.md文档步骤在干净环境中验证所有功能
- [ ] T073 更新README: 在项目README中添加"价格触发预警监控系统"章节,说明功能、架构、使用方法
- [ ] T074 生成API文档: 使用drf-spectacular或Swagger生成在线API文档,部署到/api/docs/

**检查点**: 代码质量达标,性能满足目标,文档完整

---

## Dependencies & Execution Order (依赖关系与执行顺序)

### Phase依赖关系

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational) ← 阻塞所有用户故事
    ↓
┌───────────┬────────────┬────────────┬────────────┬────────────┐
│  Phase 3  │  Phase 4   │  Phase 5   │  Phase 6   │  Phase 7   │
│   (US4)   │   (US5)    │   (US1)    │   (US3)    │   (US2)    │
│ P1-核心   │  P2-算法   │ P1-交互    │ P1-配置    │ P2-自动化  │
└─────┬─────┴──────┬─────┴──────┬─────┴──────┬─────┴──────┬─────┘
      └────────────┴────────────┴────────────┴────────────┘
                              ↓
                         Phase 8 (API)
                              ↓
                         Phase 9 (Dashboard)
                              ↓
                         Phase 10 (Polish)
```

### 用户故事依赖关系

- **US4 (定时数据更新)**: 核心工作流程,最优先实现 → **必须首先完成**
- **US5 (规则判定逻辑)**: US4依赖的算法实现 → **紧随US4**
- **US1 (手动监控推送)**: 用户交互功能,依赖US4和US5 → **第三优先**
- **US3 (规则配置)**: 增强US1的灵活性,可与US1并行 → **可与US1并行**
- **US2 (自动同步)**: 独立于核心流程,可最后实现 → **独立,可并行**

### Phase内任务依赖

**Phase 2 (Foundational)**:
- T005, T006, T007 可并行(不同文件)
- T008依赖T001-T004(需要先生成migration文件)
- T009依赖T008(需要先执行迁移)

**Phase 3 (US4)**:
- T010和T011可并行(两个独立脚本)
- T012依赖T010(在脚本中实现逻辑)
- T015依赖T011(在脚本中实现逻辑)
- T013-T017依赖T012和T015(在现有脚本基础上增强)

**Phase 4 (US5)**:
- T018-T023可并行(不同规则判定方法,在同一文件不同函数中)
- T024-T025依赖T018-T023(需要规则引擎类存在)

**Phase 5 (US1)**:
- T026和T027可并行(Admin配置)
- T028-T032依赖Phase 4完成(需要规则引擎)

### 并行执行机会

**Phase 2 (Foundational)** - 3个任务可并行:
```bash
# 同时启动3个任务
Task T005: 实现脚本锁机制 (grid_trading/services/script_lock.py)
Task T006: 封装通知服务 (grid_trading/services/alert_notifier.py)
Task T007: 实现规则工具函数 (grid_trading/services/rule_utils.py)
```

**Phase 4 (US5)** - 6个任务可并行:
```bash
# 同时实现所有规则判定方法
Task T019: 规则1判定 (rule_engine.py - check_rule_1_7d_high)
Task T020: 规则2判定 (rule_engine.py - check_rule_2_7d_low)
Task T021: 规则3判定 (rule_engine.py - check_rule_3_ma20_touch)
Task T022: 规则4判定 (rule_engine.py - check_rule_4_ma99_touch)
Task T023: 规则5判定 (rule_engine.py - check_rule_5_price_distribution)
Task T024: 边界情况处理 (rule_engine.py - 降级逻辑)
```

**Phase 8 (API)** - 多个ViewSet可并行:
```bash
# 同时实现5个ViewSet
Task T047: 监控合约ViewSet
Task T048: 触发规则ViewSet
Task T049: 触发日志ViewSet
Task T050: 系统配置ViewSet
Task T051: 数据更新日志ViewSet
```

**团队并行策略** (3人团队):
```
完成Phase 1 + Phase 2(基础设施)
    ↓
Developer A: Phase 3 (US4) + Phase 4 (US5) → 核心流程
Developer B: Phase 5 (US1) + Phase 6 (US3) → 用户交互
Developer C: Phase 7 (US2) → 自动化功能
    ↓
合并代码,继续Phase 8-10
```

---

## Implementation Strategy (实施策略)

### 策略1: MVP First (最小可行产品优先)

**目标**: 最快验证核心价值

1. ✅ **Phase 1: Setup** - 数据库结构准备
2. ✅ **Phase 2: Foundational** - 基础服务实现
3. 🎯 **Phase 3: US4** - 核心工作流程(数据更新+规则检测)
4. 🎯 **Phase 4: US5** - 规则判定算法
5. 🎯 **Phase 5: US1** - 手动监控和推送

**停止点**: 完成Phase 5后,系统已可用
- 管理员可手动添加监控合约
- 定时脚本自动更新数据和检测规则
- 触发规则时推送通知
- **验证**: 运行监控脚本,确认推送功能正常

**MVP范围**: Phase 1-5 (约35个任务)

---

### 策略2: Incremental Delivery (增量交付)

**迭代1** (核心功能): Phase 1-5
- 交付物: 可工作的价格监控和推送系统
- 验证: 手动添加合约,验证推送功能
- 时间估算: 5-7个工作日

**迭代2** (配置增强): Phase 6
- 交付物: 动态规则配置和防重复间隔调整
- 验证: 在Admin中修改配置,验证生效
- 时间估算: 1-2个工作日

**迭代3** (自动化): Phase 7
- 交付物: 自动同步筛选结果,自动管理监控列表
- 验证: 运行同步脚本,验证合约自动添加和过期
- 时间估算: 2-3个工作日

**迭代4** (API): Phase 8
- 交付物: REST API接口,支持外部调用
- 验证: API文档和集成测试
- 时间估算: 2-3个工作日

**迭代5** (可视化): Phase 9
- 交付物: 监控仪表盘
- 验证: 仪表盘展示完整,数据准确
- 时间估算: 2-3个工作日

**迭代6** (优化): Phase 10
- 交付物: 性能优化,文档完善
- 验证: 性能目标达成,文档齐全
- 时间估算: 1-2个工作日

**总时间估算**: 13-20个工作日 (约3-4周)

---

### 策略3: Parallel Team (并行团队)

**前提**: 3人团队,Phase 2完成后并行开发

**分工方案**:

**Developer A** (后端核心):
- Phase 3: US4 - 数据更新和监控脚本
- Phase 4: US5 - 规则判定算法
- 预计: 5天

**Developer B** (用户交互):
- Phase 5: US1 - Django Admin和推送功能
- Phase 6: US3 - 规则配置管理
- 预计: 4天

**Developer C** (自动化与API):
- Phase 7: US2 - 自动同步筛选合约
- Phase 8: REST API实现
- 预计: 5天

**合并后共同完成**:
- Phase 9: Dashboard (2天)
- Phase 10: Polish (1天)

**总时间估算**: 约2周 (并行开发)

---

## Testing Strategy (测试策略)

**注意**: 本项目不强制要求编写测试,但建议为核心逻辑添加单元测试

### 推荐测试覆盖

**高优先级** (建议测试):
1. 规则判定算法(rule_engine.py) - 确保判定逻辑100%准确
2. 防重复推送逻辑(should_push_alert) - 确保防重复机制生效
3. K线数据连续性检测(validate_kline_continuity) - 确保数据质量

**中优先级** (可选测试):
4. 数据更新脚本集成测试 - 验证完整数据更新流程
5. 合约监控脚本集成测试 - 验证规则检测和推送流程

**低优先级** (可手动测试):
6. Admin界面功能测试 - 手动验证即可
7. API端点测试 - 使用Postman/curl手动测试

### 测试文件结构(如需编写)

```
tests/
├── unit/
│   ├── test_rule_engine.py          # 规则判定算法单元测试
│   ├── test_rule_utils.py           # 工具函数单元测试
│   └── test_alert_notifier.py       # 推送服务单元测试
├── integration/
│   ├── test_data_update_command.py  # 数据更新脚本集成测试
│   └── test_check_alerts_command.py # 监控脚本集成测试
└── fixtures/
    └── kline_test_data.json         # 测试K线数据夹具
```

---

## Performance Goals (性能目标)

根据plan.md的性能目标:

| 指标 | 目标 | 验证方法 |
|------|------|----------|
| 数据更新脚本(100合约) | <3分钟 | DataUpdateLog.execution_seconds |
| 合约监控脚本(100合约) | <2分钟 | 监控脚本执行日志 |
| 完整流程(更新+检测+推送) | <5分钟 | 两个脚本总耗时 |
| 防重复查询性能 | <10ms | 数据库查询EXPLAIN分析 |
| 仪表盘加载时间 | <2秒 | 浏览器Network面板 |

**优化建议** (Phase 10):
- 使用prefetch_related优化K线查询
- 添加数据库索引加速防重复查询
- 当合约数量>200时启用分片处理

---

## Risk Mitigation (风险缓解)

### 风险1: 币安API不稳定

**缓解措施**:
- T013: 实现请求重试机制(最多3次,指数退避)
- T014: 记录API失败详细日志
- T068: 连续失败3次发送告警

### 风险2: 推送服务限流

**缓解措施**:
- T031: 控制推送频率(≥100ms间隔)
- T032: 实现失败推送补偿重试
- T068: 推送失败告警通知

### 风险3: 数据库性能瓶颈

**缓解措施**:
- T003: 添加关键字段索引
- T066: 查询优化(prefetch_related)
- T069: 定期清理历史日志

### 风险4: 脚本执行超时

**缓解措施**:
- T016: 脚本锁机制,10分钟超时自动释放
- T067: 大数据量时自动分片处理
- T068: 超时告警通知

---

## Notes (注意事项)

- **[P]标记**: 表示任务可并行执行,不同文件,无依赖关系
- **[Story]标记**: 任务所属用户故事,便于追溯和独立测试
- **提交策略**: 建议每完成1-2个任务提交一次,提交信息格式`feat(US4): 实现数据更新脚本`
- **检查点验证**: 每个Phase完成后,运行相关功能验证无问题再继续
- **文档同步**: 如有实现细节与设计文档不符,及时更新相关文档

**关键路径** (Critical Path):
```
T001-T004 → T008 → T009 → T005-T007 → T010-T017 → T018-T025 → T026-T032
```
关键路径任务必须按顺序完成,非关键路径任务可灵活安排

---

**任务总数**: 74个任务
**MVP范围**: Phase 1-5 (35个任务)
**并行机会**: 约20个任务可并行执行
**预估时间**: 3-4周(单人) / 2周(3人团队并行)

**生成日期**: 2025-12-08
**下一步**: 执行Phase 1: Setup,创建数据库模型和迁移文件
