# Implementation Plan: Market Cap & FDV Display Integration

**Branch**: `008-marketcap-fdv-display` | **Date**: 2025-12-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-marketcap-fdv-display/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

为做空网格筛选系统的 `/screening/daily/` 页面添加市值(Market Cap)和FDV(Fully Diluted Valuation)展示功能。核心技术路径:
1. 建立币安symbol与CoinGecko ID的映射关系(自动匹配+人工审核)
2. 定期从CoinGecko API获取市值/FDV数据并存储
3. 前端页面直接从数据库读取并展示(始终显示最新数据)

**技术方法**:
- 使用CoinGecko API的`/coins/list`和`/coins/markets`端点
- 优先级规则: 24h交易量 → 市值排名 → 标记needs_review
- 数据以美元(USD)为单位,使用K/M/B单位缩写格式化
- 每日定时任务自动更新数据

## Technical Context

**Language/Version**: Python 3.12 (项目已使用)
**Primary Dependencies**:
  - Django 4.2.8 (现有Web框架)
  - python-binance 1.0.19 (用于获取币安合约列表,已有)
  - requests (用于调用CoinGecko API)
  - pandas 2.0+ (数据处理,已有)

**Storage**: SQLite (开发) / PostgreSQL 14+ (生产) - 新增3个表: TokenMapping, MarketData, UpdateLog

**Testing**: pytest (项目已使用)

**Target Platform**: Linux server (生产环境), macOS (开发环境)

**Project Type**: Django Web应用 + 后台脚本

**Performance Goals**:
  - 映射脚本: 500+合约映射 < 5分钟
  - 数据更新脚本: 500+合约更新 < 15分钟
  - 页面加载增量: < 200ms
  - 排序响应: < 100ms

**Constraints**:
  - CoinGecko API限流: 50次/分钟(免费版)
  - 必须实现指数退避重试机制
  - 同名代币冲突必须按规则自动选择或标记review

**Scale/Scope**:
  - 约500+个USDT永续合约
  - 每日1次数据更新
  - 数据覆盖率目标: ≥90%
  - 自动映射准确率: ≥85%

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Design Gates (Phase 0前)

#### ✅ 核心原则合规性
- [x] **零假设原则**: 规格说明已通过澄清流程,所有模糊点已解决
- [x] **小步提交**: 将通过4个独立的user story进行增量交付
- [x] **简单至上**:
  - 单一职责: 每个模块(映射、数据获取、展示)独立
  - 避免过早抽象: 初期使用直接的脚本+Django管理命令
  - 拒绝奇技淫巧: 使用标准的Django ORM和REST API模式

#### ✅ 量化系统原则
本功能虽服务于量化系统,但属于**数据增强层**,不直接涉及交易策略,因此:
- ⚠️ **回测优先**: N/A (不涉及交易决策)
- ⚠️ **风险控制**: N/A (不涉及资金操作)
- ✅ **模块化与状态隔离**: 映射、更新、展示三模块独立
- ✅ **参数可追溯**: UpdateLog表记录所有更新操作
- ⚠️ **渐进式部署**: N/A (只读功能,无资金风险)

#### ✅ 数据质量原则
- [x] 所有数据包含时间戳(fetched_at, updated_at)
- [x] 验证数据完整性(symbol, coingecko_id必填)
- [x] 处理API失败和异常(重试机制+日志)
- [x] 记录更新失败和异常(UpdateLog表)

#### ✅ 技术栈一致性
- [x] 使用现有Django框架
- [x] 使用现有python-binance连接
- [x] 复用现有数据库配置
- [x] 遵循现有测试框架(pytest)

### Post-Design Gates (Phase 1后)
*待Phase 1设计完成后重新评估*

### Complexity Justification
*无违反宪法的复杂性引入,无需填写此表*

## Project Structure

### Documentation (this feature)

```text
specs/008-marketcap-fdv-display/
├── spec.md              # 功能规格说明(已完成)
├── plan.md              # 本文件 - 实施计划
├── research.md          # Phase 0 输出 - 技术研究
├── data-model.md        # Phase 1 输出 - 数据模型
├── quickstart.md        # Phase 1 输出 - 快速开始指南
├── contracts/           # Phase 1 输出 - API契约
│   └── coingecko_api.md # CoinGecko API调用说明
└── tasks.md             # Phase 2 输出 (由 /speckit.tasks 命令生成)
```

### Source Code (repository root)

**项目类型**: Django Web应用,选择**现有Django应用扩展**模式

```text
grid_trading/                          # 现有Django应用(做空网格筛选系统)
├── models/                            # [NEW] 新增数据模型
│   ├── token_mapping.py               # TokenMapping模型
│   ├── market_data.py                 # MarketData模型
│   └── update_log.py                  # UpdateLog模型
├── services/                          # [EXISTING] 服务层
│   ├── coingecko_client.py            # [NEW] CoinGecko API客户端
│   ├── mapping_service.py             # [NEW] 映射关系管理服务
│   └── market_data_service.py         # [NEW] 市值/FDV数据服务
├── management/commands/               # [EXISTING] Django管理命令
│   ├── generate_token_mapping.py      # [NEW] 生成映射关系命令
│   ├── update_market_data.py          # [NEW] 更新市值/FDV数据命令
│   └── sync_binance_contracts.py      # [NEW] 同步币安合约列表命令
├── admin.py                           # [MODIFY] 添加TokenMapping/MarketData后台管理
├── views.py                           # [MODIFY] 修改daily_screening_detail视图
├── templates/grid_trading/            # [EXISTING] Django模板
│   └── daily_screening.html           # [MODIFY] 添加市值/FDV列
└── migrations/                        # [NEW] 数据库迁移
    └── 00XX_add_market_cap_fdv.py     # 新增3个表的迁移文件

scripts/                               # [EXISTING] 独立脚本目录
├── cron_update_market_data.sh         # [NEW] 定时任务脚本(每日4am执行)
└── validate_mapping.py                # [NEW] 映射关系验证工具

tests/                                 # [EXISTING] 测试目录
├── test_coingecko_client.py           # [NEW] CoinGecko客户端测试
├── test_mapping_service.py            # [NEW] 映射服务测试
├── test_market_data_service.py        # [NEW] 市场数据服务测试
└── test_views_screening.py            # [MODIFY] 添加市值/FDV展示测试
```

**Structure Decision**:
- **选择理由**: 本功能是现有`grid_trading` Django应用的扩展,不需要新建独立应用
- **模块化原则**:
  - Models: 3个独立数据模型文件
  - Services: 3个独立服务文件(客户端、映射、数据)
  - Commands: 3个独立管理命令
- **复用现有**: 复用Django ORM、Admin、模板系统、定时任务框架

## Phase 0: Research & Technical Decisions

### 0.1 CoinGecko API调研

**研究目标**: 确认CoinGecko API端点选择、限流策略、错误处理

**关键决策点**:
1. API端点选择: `/coins/list` vs `/coins/markets` vs `/search`
2. 免费版vs付费版限制
3. 同名代币消歧策略
4. API失败重试机制

**输出**: `research.md` - CoinGecko API最佳实践

### 0.2 币安合约列表获取

**研究目标**: 确认如何从币安API获取所有USDT永续合约列表

**关键决策点**:
1. 使用现有的`python-binance`还是直接HTTP调用
2. 如何从交易对symbol提取基础代币(BTCUSDT → BTC)
3. 是否需要过滤某些特殊合约(如季度合约)

**输出**: `research.md` - 币安合约API使用说明

### 0.3 数据更新策略

**研究目标**: 确定数据更新频率、批量处理策略、定时任务实现

**关键决策点**:
1. 更新频率: 每日1次 vs 每12小时 vs 实时
2. 批量处理: 串行 vs 并行(多线程/多进程)
3. 定时任务: Django Celery vs Cron Job vs APScheduler
4. API限流应对: 延迟策略(每批50个symbol,批次间延迟1分钟)

**输出**: `research.md` - 数据更新最佳实践

### 0.4 前端展示方案

**研究目标**: 确认如何在现有Django模板中添加市值/FDV列

**关键决策点**:
1. 数字格式化: 前端JavaScript vs 后端Python
2. 排序实现: 前端DataTables vs 后端QuerySet
3. Tooltip实现: Bootstrap Tooltip vs 自定义CSS
4. 单位缩写算法: K/M/B转换逻辑

**输出**: `research.md` - 前端集成方案

## Phase 1: Data Model & API Contracts

### 1.1 数据模型设计

**输出**: `data-model.md`

**核心实体**:
1. **TokenMapping (代币映射表)**
2. **MarketData (市场数据表)**
3. **UpdateLog (更新日志表)**

详见下一节。

### 1.2 API契约定义

**输出**: `contracts/coingecko_api.md`

**关键接口**:
1. CoinGecko `/coins/list` - 获取所有代币ID列表
2. CoinGecko `/coins/markets` - 批量获取市值/FDV数据
3. 内部服务接口:
   - MappingService.generate_mappings()
   - MarketDataService.update_all()
   - CoingeckoClient.fetch_market_data()

### 1.3 快速开始指南

**输出**: `quickstart.md`

**内容**:
1. 初始化: 生成映射关系
2. 首次数据获取
3. 配置定时任务
4. 验证展示效果

### 1.4 Agent Context Update

运行 `.specify/scripts/bash/update-agent-context.sh claude` 更新项目上下文:
- 新增技术: CoinGecko API, requests库
- 新增模块: grid_trading.models.token_mapping, market_data, update_log
- 新增服务: coingecko_client, mapping_service, market_data_service

## Phase 2: Task Breakdown

*此阶段由 `/speckit.tasks` 命令执行,不在本计划范围内*

**预期输出**: `tasks.md` - 详细的任务列表和执行顺序

**预期任务阶段** (供参考):
1. Setup & Infrastructure (T001-T005)
2. Data Models (T006-T010)
3. CoinGecko Integration (T011-T020)
4. Mapping Service (T021-T030)
5. Market Data Service (T031-T040)
6. Frontend Display (T041-T050)
7. Testing & Validation (T051-T060)

## Implementation Notes

### 技术选择说明

#### 1. 为什么不使用Celery?
- **理由**: 项目当前使用Cron Job进行定时任务(如`update_market_data.sh`)
- **一致性原则**: 保持与现有架构一致,避免引入新的依赖
- **简单性原则**: Cron Job足够满足每日1次的更新需求

#### 2. 为什么使用requests而非python-binance的统一客户端?
- **理由**: CoinGecko不在python-binance支持范围
- **隔离原则**: CoinGecko API与币安API逻辑独立,分离客户端更清晰
- **依赖最小化**: requests是Python标准库,无需额外依赖

#### 3. 为什么数据存储在数据库而非缓存?
- **持久化需求**: 市值/FDV数据需要历史追溯(UpdateLog)
- **数据量小**: 500个合约 × 2个字段 = 1000条记录,数据库完全足够
- **查询便利**: 支持JOIN查询、排序、过滤

#### 4. 为什么前端始终显示最新数据?
- **用户需求**: 规格澄清阶段确认,用户希望看到当前最新的市值/FDV
- **实现简单**: 无需维护历史快照,查询逻辑简单
- **数据一致性**: 避免历史数据与筛选结果时间不一致的困惑

### 风险与缓解

#### 风险1: CoinGecko API限流导致数据更新失败
**影响**: 高 | **概率**: 中
**缓解措施**:
- 实现指数退避重试(1s → 2s → 4s)
- 分批处理(每批50个symbol,批次间延迟1分钟)
- 记录失败的symbol,在下次更新时优先重试
- 监控UpdateLog表,告警失败率超过5%

#### 风险2: 同名代币映射错误
**影响**: 中 | **概率**: 低-中
**缓解措施**:
- 优先级规则: 24h交易量 → 市值排名 → needs_review
- 生成映射后人工审核(needs_review状态)
- 提供Django Admin界面,方便手工修正
- 记录alternatives字段,保留所有候选项

#### 风险3: 币安新上线合约未及时建立映射
**影响**: 低 | **概率**: 中
**缓解措施**:
- 每日定时任务先同步币安合约列表
- 检测新合约并自动触发映射流程
- 告警needs_review状态的合约数量变化

#### 风险4: 页面加载性能影响
**影响**: 中 | **概率**: 低
**缓解措施**:
- 数据库JOIN优化(添加索引)
- 前端分页(已有机制)
- 数字格式化在后端预处理(避免前端重复计算)
- 监控页面加载时间,确保增量<200ms

### 依赖外部服务

#### CoinGecko API
- **状态监控**: https://status.coingecko.com/
- **备选方案**: 如长期不可用,考虑CoinMarketCap API
- **降级策略**: API不可用时,前端显示"-",不阻塞筛选功能

#### 币安API
- **现有依赖**: 项目已依赖币安API
- **风险**: 与现有功能共享,风险可控

### 运维注意事项

#### 初始化流程
1. 运行迁移: `python manage.py migrate`
2. 生成映射: `python manage.py generate_token_mapping`
3. 人工审核: 在Django Admin中确认needs_review的映射
4. 首次更新: `python manage.py update_market_data`
5. 配置Cron: 每日凌晨4点执行更新脚本

#### 监控指标
- 映射覆盖率: ≥90% (目标)
- 数据更新成功率: ≥95% (目标)
- API调用失败率: <5% (告警阈值)
- 页面加载增量: <200ms (性能阈值)

#### 告警触发条件
- UpdateLog中连续3次失败相同的symbol
- 单次更新失败率>10%
- needs_review状态的合约数量突增(>20个)
- 页面加载时间超过阈值

## Post-Design Constitution Check

*待Phase 1完成后填写*

### 设计复杂度评估
- [ ] 数据模型是否遵循单一职责原则
- [ ] 服务层是否过度抽象
- [ ] API契约是否清晰明确
- [ ] 是否存在可以简化的流程

### 测试覆盖计划
- [ ] 单元测试: CoinGecko客户端、服务层逻辑
- [ ] 集成测试: 映射生成流程、数据更新流程
- [ ] 端到端测试: 前端展示、排序功能
- [ ] 边界测试: API限流、同名冲突、数据缺失

## Next Steps

1. ✅ 完成Phase 0: 执行research任务,填充`research.md` - **已完成**
2. ✅ 完成Phase 1: 定义数据模型和API契约 - **已完成**
   - ✅ `data-model.md` - 3个数据模型完整定义
   - ✅ `contracts/coingecko_api.md` - API契约和服务接口
   - ✅ `quickstart.md` - 初始化配置指南
   - ✅ Agent上下文更新完成
3. ⏸️ 等待用户执行: `/speckit.tasks` 生成详细任务列表
4. ⏸️ 开始实施: 按tasks.md中的任务顺序执行

---

**Prepared by**: Claude Code
**Last Updated**: 2025-12-12
**Status**: Phase 0 & 1 Completed ✅ | Ready for Phase 2 (Task Generation)
