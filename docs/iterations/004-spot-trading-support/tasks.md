# 开发任务计划

**迭代编号**: 004
**分支**: 004-spot-trading-support
**创建日期**: 2025-12-25
**生命周期阶段**: P5 - 开发规划
**文档化标准**: docs/comment-templates.md

---

## 任务统计

| 优先级 | 任务数 | 预估总工时 |
|-------|-------|-----------|
| P0 | 5个 | 16小时 |
| P1 | 2个 | 6小时 |
| P2 | 1个 | 2小时 |
| **总计** | **8个** | **24小时** |

---

## 开发任务清单

### P0 核心功能 (Must Have)

#### TASK-004-001: 现货交易对列表管理模型
- **关联需求**: [P0-3] 现货交易对列表管理
- **关联架构**: SpotContract模型（architecture.md 3.2.2）
- **任务描述**: 创建SpotContract模型，管理现货交易对列表，镜像FuturesContract模型
- **验收标准**:
  - [ ] SpotContract模型创建完成，包含symbol、exchange、status、current_price字段
  - [ ] 模型与Exchange模型建立ForeignKey关联
  - [ ] 实现unique_together约束：(exchange, symbol)
  - [ ] 模型包含__str__方法，返回标准格式字符串
  - [ ] 数据库迁移脚本生成并测试通过
  - [ ] **异常路径验证**: 当symbol为空或exchange不存在时抛出ValidationError
  - [ ] **文档化标准合规** 📝
    - [ ] 类docstring符合PEP 257，包含Attributes、Examples
    - [ ] 所有字段都有verbose_name和help_text
    - [ ] 通过Django makemigrations验证
- **边界检查**:
  - 输入边界: symbol长度≤50，status必须为'active'或'delisted'
  - 资源状态: Exchange记录必须存在
- **预估工时**: 2小时
- **依赖关系**: 无（独立任务）
- **测试策略**: 单元测试（模型字段验证）+ 集成测试（迁移验证）
- **异常测试**: 
  - 创建重复(exchange, symbol)记录时抛出IntegrityError
  - symbol为空字符串时抛出ValidationError
- **文档要求**: ⭐
  - 类docstring描述现货交易对管理职责
  - 字段docstring描述各字段含义和约束
- **状态**: 待开始

#### TASK-004-002: 现货数据存储扩展
- **关联需求**: [P0-2] 现货数据存储扩展
- **关联架构**: KLine模型扩展（architecture.md 3.2.2）
- **任务描述**: 扩展KLine模型，新增market_type字段，区分现货和合约数据
- **验收标准**:
  - [ ] KLine模型新增market_type字段（CharField，choices=['spot', 'futures']）
  - [ ] 更新unique_together为：(symbol, interval, market_type, open_time)
  - [ ] 现有数据自动标记为market_type='futures'
  - [ ] 为现有KLine记录执行数据迁移
  - [ ] 查询逻辑添加market_type过滤
  - [ ] **异常路径验证**: 当market_type不在允许值内时抛出ValidationError
  - [ ] **文档化标准合规** 📝
    - [ ] 字段docstring描述market_type的用途
    - [ ] 数据库迁移注释清晰说明变更
- **边界检查**:
  - 输入边界: market_type只能为'spot'或'futures'
  - 资源状态: 现有数据不能丢失
- **预估工时**: 3小时
- **依赖关系**: TASK-004-001完成
- **测试策略**: 单元测试（字段验证）+ 集成测试（数据迁移）
- **异常测试**:
  - 插入market_type='invalid'时抛出ValidationError
  - 重复(symbol, interval, market_type, open_time)时抛出IntegrityError
- **文档要求**: ⭐
  - 字段docstring说明市场类型区分的重要性
- **状态**: 待开始

#### TASK-004-003: 现货API客户端开发
- **关联需求**: [P0-1] 现货K线数据获取能力
- **关联架构**: BinanceSpotClient（architecture.md 3.2.2）
- **任务描述**: 创建BinanceSpotClient，镜像BinanceFuturesClient实现，调用Binance Spot API
- **验收标准**:
  - [ ] 创建BinanceSpotClient类，继承BaseFuturesClient
  - [ ] 实现fetch_contracts()方法，获取现货交易对列表
  - [ ] 实现_normalize_symbol()方法，标准化现货符号格式
  - [ ] 支持从/api/v3/exchangeInfo端点获取现货交易对
  - [ ] 支持从/api/v3/ticker/price端点获取价格
  - [ ] 复用BaseFuturesClient的重试和限流逻辑
  - [ ] **异常路径验证**: API调用失败时抛出明确异常
  - [ ] **文档化标准合规** 📝
    - [ ] 类docstring描述现货API客户端职责
    - [ ] 方法docstring包含Args、Returns、Raises
- **边界检查**:
  - 输入边界: symbol必须为USDT本位现货（如BTC/USDT）
  - 资源状态: API响应状态码必须为200
- **预估工时**: 3小时
- **依赖关系**: TASK-004-001完成
- **测试策略**: 单元测试（符号标准化）+ 集成测试（API调用）
- **异常测试**:
  - API返回非200状态码时抛出APIError
  - symbol格式无效时抛出ValueError
- **文档要求**: ⭐
  - 类docstring说明与BinanceFuturesClient的差异
  - 方法docstring说明API端点和返回格式
- **状态**: 待开始

#### TASK-004-004: 现货交易对同步命令
- **关联需求**: [P0-1] 现货K线数据获取能力
- **关联架构**: fetch_spot_contracts命令（architecture.md 3.2.2）
- **任务描述**: 创建fetch_spot_contracts命令，镜像fetch_futures命令
- **验收标准**:
  - [ ] 创建fetch_spot_contracts管理命令
  - [ ] 支持--exchange参数（默认binance）
  - [ ] 支持--all参数获取所有交易所
  - [ ] 支持--verbose参数显示详细输出
  - [ ] 支持--test参数（不保存到数据库）
  - [ ] 调用BinanceSpotClient获取现货交易对
  - [ ] 保存/更新现货交易对到SpotContract表
  - [ ] 返回同步统计信息（新增、更新、下线数量）
  - [ ] **异常路径验证**: 当exchange不存在或无效时抛出CommandError
  - [ ] **文档化标准合规** 📝
    - [ ] 类docstring描述现货交易对同步功能
    - [ ] add_arguments()和handle()方法有完整docstring
- **边界检查**:
  - 输入边界: exchange必须为支持的交易所代码
  - 资源状态: Exchange记录必须存在
- **预估工时**: 2小时
- **依赖关系**: TASK-004-001, TASK-004-003完成
- **测试策略**: 单元测试（参数解析）+ 集成测试（命令执行）
- **异常测试**:
  - 无效exchange代码时抛出CommandError
  - API调用失败时显示错误信息并返回非0退出码
- **文档要求**: ⭐
  - 类docstring说明命令用途和示例
  - 方法docstring说明参数和返回值
- **状态**: 待开始

#### TASK-004-005: 现货异常检测扩展
- **关联需求**: [P0-4] 现货异常检测扩展
- **关联架构**: 状态机适配（architecture.md 3.2.2）
- **任务描述**: 扩展VolumeTrapStateMachine和VolumeTrapMonitor支持现货交易对
- **验收标准**:
  - [x] VolumeTrapMonitor模型新增spot_contract外键和market_type字段
  - [x] 实现futures_contract和spot_contract的条件外键（互斥）
  - [x] VolumeTrapStateMachine适配支持SpotContract
  - [x] InvalidationDetector适配支持SpotContract
  - [x] update_klines命令新增--market-type参数
  - [x] scan_volume_traps命令新增--market-type参数
  - [x] check_invalidations命令新增--market-type参数
  - [x] 8个检测器100%复用，无需修改
  - [x] **异常路径验证**: 当market_type与外键不匹配时抛出ValidationError
  - [x] **文档化标准合规** 📝
    - [x] 字段docstring说明spot_contract的用途
    - [x] 方法docstring说明market_type参数的处理
- **边界检查**:
  - 输入边界: market_type只能为'spot'或'futures'
  - 资源状态: SpotContract/FuturesContract记录必须存在
- **预估工时**: 4小时
- **依赖关系**: TASK-004-001, TASK-004-002完成
- **测试策略**: 单元测试（字段验证）+ 集成测试（状态机流程）
- **异常测试**:
  - [x] 同时设置futures_contract和spot_contract时抛出ValidationError
  - [x] 无效market_type时抛出ValidationError
- **文档要求**: ⭐
  - [x] 字段docstring说明多市场类型支持
- **状态**: ✅完成（所有功能已完成并通过测试）
- **完成报告**: `docs/iterations/004-spot-trading-support/TASK-004-005-implementation-report.md`

#### TASK-004-006: API筛选功能扩展
- **关联需求**: [P0-5] 结果区分显示
- **关联架构**: MonitorListAPI扩展（architecture.md 3.2.2）
- **任务描述**: 扩展MonitorListAPI，支持按market_type筛选现货/合约监控结果
- **验收标准**:
  - [x] MonitorListAPI新增market_type查询参数
  - [x] 支持market_type='spot'筛选现货监控记录
  - [x] 支持market_type='futures'筛选合约监控记录
  - [x] 支持market_type='all'（默认）返回所有
  - [x] API文档更新，包含market_type参数说明
  - [x] **异常路径验证**: 当market_type无效时返回400错误
  - [x] **文档化标准合规** 📝
    - [x] API视图docstring说明market_type筛选功能
- **边界检查**:
  - 输入边界: market_type必须为'spot'、'futures'或'all'
  - 资源状态: 查询参数必须有效
- **预估工时**: 2小时
- **依赖关系**: TASK-004-005完成
- **测试策略**: 单元测试（参数验证）+ 集成测试（API响应）
- **异常测试**:
  - 无效market_type值时返回400 Bad Request
  - 空结果时返回空列表
- **文档要求**: ⭐
  - 视图docstring说明market_type参数的使用方法
- **状态**: ✅完成（所有功能已完成并通过测试）

### P1 重要功能 (Should Have)

#### TASK-004-101: 现货K线批量更新优化
- **关联需求**: [P0-1] 现货K线数据获取能力
- **任务描述**: 优化DataFetcher支持现货K线批量更新
- **验收标准**:
  - [ ] DataFetcher适配支持market_type参数
  - [ ] update_klines --market-type spot支持批量更新所有现货交易对
  - [ ] 复用现有的增量更新和历史数据获取逻辑
  - [ ] 性能优化：并发处理现货交易对
- **预估工时**: 4小时
- **依赖关系**: TASK-004-002, TASK-004-005完成
- **测试策略**: 性能测试 + 集成测试
- **文档要求**: 📝
- **状态**: 待开始

#### TASK-004-102: SpotFetcherService服务开发
- **关联需求**: [P0-3] 现货交易对列表管理
- **任务描述**: 创建SpotFetcherService，镜像FuturesFetcherService
- **验收标准**:
  - [ ] 创建SpotFetcherService类
  - [ ] 支持多交易所现货交易对获取（初期仅binance）
  - [ ] 实现update_exchanges_manually()方法
  - [ ] 复用现有的重试机制和错误处理
  - [ ] 支持批量同步现货交易对列表
- **预估工时**: 2小时
- **依赖关系**: TASK-004-003完成
- **测试策略**: 单元测试 + 集成测试
- **文档要求**: 📝
- **状态**: 待开始

### P2 增强功能 (Could Have)

#### TASK-004-201: API文档完善
- **关联需求**: [P0-5] 结果区分显示
- **任务描述**: 更新API文档，包含现货支持的所有接口
- **验收标准**:
  - [ ] 更新MonitorListAPI文档
  - [ ] 添加market_type参数说明和示例
  - [ ] 创建现货交易对管理API文档
  - [ ] 更新命令行文档
- **预估工时**: 2小时
- **依赖关系**: TASK-004-006完成
- **测试策略**: 文档审查
- **文档要求**: 📝
- **状态**: 待开始

---

## 技术任务

### 环境搭建
- [x] 开发环境配置
- [x] 代码规范配置（PEP8）
- [x] **文档风格定义** 📝
  - [x] 已确定项目文档化标准（PEP 257 Python Docstrings）
  - [x] 注释模板已创建（docs/comment-templates.md）
  - [ ] 自动化文档生成工具已配置（TODO）
  - [ ] CI/CD包含文档化验证步骤（TODO）

### 基础设施
- [ ] 数据库迁移脚本（3个迁移）
- [ ] API文档生成
- [ ] 监控和日志系统

---

## 开发里程碑

| 里程碑 | 包含任务 | 预计完成时间 | 验收标准 |
|-------|---------|------------|---------|
| M1: 数据层完成 | TASK-001, TASK-002 | 第1天 | 数据库迁移成功，模型测试通过 |
| M2: API客户端完成 | TASK-003, TASK-004 | 第2天 | 现货交易对同步成功 |
| M3: 状态机适配完成 | TASK-005 | 第3天 | 现货异常检测流程正常 |
| M4: API扩展完成 | TASK-006 | 第3天 | API筛选功能正常 |
| M5: 优化与文档 | TASK-101, TASK-102, TASK-201 | 第4天 | 性能达标，文档完整 |

---

## 风险评估

### 高风险任务
- **任务**: TASK-004-002（KLine模型扩展）
- **风险**: 数据库迁移可能影响现有数据
- **缓解措施**: 
  - 充分测试迁移脚本
  - 先在测试环境验证
  - 提供回滚方案

### 技术依赖
- **依赖**: Binance Spot API
- **风险**: API变更或不可用
- **应对**: 实现降级策略，使用缓存数据

### 中风险任务
- **任务**: TASK-004-005（状态机适配）
- **风险**: 外键互斥逻辑复杂
- **缓解措施**: 
  - 实现clean()方法验证
  - 添加单元测试覆盖

---

## 可追溯性矩阵

| 功能点编号 | 任务ID | 架构组件 | 测试用例ID |
|-----------|-------|---------|-----------|
| P0-1 | TASK-003, TASK-004 | BinanceSpotClient, fetch_spot_contracts | TC-001, TC-002 |
| P0-2 | TASK-002 | KLine模型扩展 | TC-003, TC-004 |
| P0-3 | TASK-001, TASK-102 | SpotContract模型, SpotFetcherService | TC-005, TC-006 |
| P0-4 | TASK-005 | VolumeTrapStateMachine适配 | TC-007, TC-008 |
| P0-5 | TASK-006, TASK-201 | MonitorListAPI扩展 | TC-009, TC-010 |

---

## Gate 5 检查清单

### 现有代码分析
- [x] **现有代码分析已完成** ⭐
  - [x] 代码库扫描已完成
  - [x] 复用能力评估已完成
  - [x] 规范识别已完成
  - [x] 现有代码分析报告已输出

### 开发规划
- [x] 所有P0功能都有对应的开发任务
- [x] 任务分解粒度合适（1-2天可完成）
- [x] 依赖关系清晰合理
- [x] 验收标准可验证
- [x] **异常路径覆盖完整** ⚡
  - [x] 每个P0任务都包含异常路径验证
  - [x] 边界检查已明确定义
  - [x] 失败用例已规划
- [x] 工作量估算合理
- [x] 技术方案可行

### 文档化标准
- [x] **文档风格定义完成** 📝
  - [x] 已确定项目文档化标准（PEP 257）
  - [x] 注释模板已创建（docs/comment-templates.md）
  - [x] 公共接口注释要求已明确

**Gate 5 检查结果**: ✅ **通过** - 可以进入P6开发实现阶段

---

**变更历史**:
- v1.0.0 (2025-12-25): 初始版本，完成P5开发规划
