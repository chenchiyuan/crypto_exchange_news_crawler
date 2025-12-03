# Implementation Plan: 做空网格标的量化筛选系统

**Branch**: `001-short-grid-screening` | **Date**: 2025-12-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-short-grid-screening/spec.md`

**Note**: This plan follows the `/speckit.plan` workflow and incorporates findings from [research.md](./research.md).

## Summary

实现一个Django Management Command (`python manage.py screen_short_grid`),通过三维筛选框架(波动率、趋势、资金/持仓)对币安永续合约市场进行量化筛选,计算GSS(Grid Short Score)评分,最终在终端输出Top 5适合做空网格的标的及其详细指标。

**技术方法**:
- 复用项目现有的 `monitor/api_clients/binance.py` 并行请求模式
- 引入 scipy 实现Hurst指数R/S分析
- 使用 NumPy向量化计算三维指标(NATR/KER/趋势/CVD)
- ThreadPoolExecutor并行优化(数据获取20并发,指标计算4并发)
- 目标性能: 60秒内完成500+标的扫描

## Technical Context

**Language/Version**: Python 3.12 (项目标准)
**Primary Dependencies**:
- Django 4.2.8 (Management Command框架)
- NumPy >= 1.24.0 (数值计算,scipy依赖)
- Pandas >= 2.0.0 (DataFrame操作,scipy依赖)
- **scipy >= 1.11.0** (新增: Hurst指数R/S分析,线性回归)
- requests 2.31.0 (币安API调用,已有)
- tenacity 8.2.3 (API重试机制,已有)
- ratelimit 2.2.1 (API限流保护,已有)

**Storage**: N/A (MVP不持久化,仅内存处理和终端输出)
**Testing**: pytest (项目标准,单元测试覆盖指标计算和评分模型)
**Target Platform**: macOS/Linux (开发和生产环境)
**Project Type**: single (Django Management Command,命令行工具)
**Performance Goals**:
- 全市场扫描(500+标的): <60秒 (SC-001)
- 单标的三维指标计算: <100ms
- NATR计算精度: 与TA-Lib误差<0.1% (SC-002)
- 币安API成功率: ≥99% (SC-004)

**Constraints**:
- 无数据库持久化(Out of Scope)
- 仅支持币安交易所(不含Bybit/OKX)
- 仅命令行输出(无Web界面/推送通知)
- 内存占用: <512MB (峰值预估60MB)
- API限流遵守: 币安1200权重/分钟

**Scale/Scope**:
- 扫描标的数: 500+ 永续合约
- K线数据量: 500标的 × 300根K线 × 8字段 ≈ 9.6MB
- 计算指标: 8个核心指标(NATR/KER/H/NormSlope/R²/OVR/Funding/CVD)
- 输出规模: Top 5标的(可配置3-10)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### ✅ 核心原则验证 (Core Principles)

| 原则 | 状态 | 说明 |
|------|------|------|
| **I. 使用中文沟通** | ✅ PASS | 所有文档、代码注释、提交信息均使用中文 |
| **II. 零假设原则** | ✅ PASS | spec.md已明确所有需求,无模糊假设 |
| **III. 小步提交** | ✅ PASS | 计划分阶段提交(数据获取→指标计算→评分→输出) |
| **IV. 借鉴现有代码** | ✅ PASS | 复用`monitor/api_clients/binance.py`和ThreadPoolExecutor模式 |
| **V. 务实主义** | ✅ PASS | 仅引入必需的scipy依赖,手动实现ATR避免TA-Lib |
| **VI. 简单至上** | ✅ PASS | MVP范围明确,不含持久化/通知/Web界面 |
| **VII. 测试驱动开发** | ✅ PASS | pytest单元测试覆盖指标计算和评分模型 |

### ✅ 量化系统原则验证 (Quantitative System Principles)

| 原则 | 状态 | 说明 |
|------|------|------|
| **VIII.6 做空网格筛选原则** | ✅ PASS | |
| └─ 三维筛选框架 | ✅ PASS | 实现波动率/趋势/资金持仓三个维度 |
| └─ 数据质量与标准化 | ✅ PASS | 币安Futures API官方数据,对数收益率/Z-Score标准化 |
| └─ 筛选Pipeline | ✅ PASS | 全市场初筛→指标计算→评分→输出四步骤 |
| └─ 风险控制 | ✅ PASS | 效率悖论识别,CVD防空警报,资金费率陷阱检测 |
| └─ 可追溯性 | ⚠️ PARTIAL | MVP不持久化筛选记录(Out of Scope),仅日志记录 |

### ⚠️ 潜在违反项 (Potential Violations)

| 违反项 | 影响 | 缓解措施 |
|--------|------|----------|
| **可追溯性不完整** | 无法验证筛选稳定性(重叠度>60%) | 可接受:MVP专注算法验证,后续迭代可添加持久化 |
| **无回测验证** | 筛选标的未与Grid V4回测集成 | 可接受:Out of Scope明确声明,MVP验证算法有效性 |

### ✅ 技术标准验证 (Technical Standards)

| 标准 | 状态 | 说明 |
|------|------|------|
| **架构原则(SOLID/DRY)** | ✅ PASS | 单一职责:独立的筛选服务模块 |
| **代码质量** | ✅ PASS | pytest测试,遵循项目格式化规范 |
| **错误处理** | ✅ PASS | API限流重试,数据缺失降级,快速失败 |
| **筛选系统约束** | ✅ PASS | |
| └─ 数据源约束 | ✅ PASS | 币安Futures API四个端点 |
| └─ 标准化约束 | ✅ PASS | 对数收益率,百分位排名,NATR归一化 |
| └─ 阈值约束 | ✅ PASS | 流动性>5000万,上市>30天,NATR 1-10% |
| └─ 评分模型约束 | ✅ PASS | 权重总和=1.0,可配置,单维度10-50% |
| └─ 输出约束 | ✅ PASS | Top N(3-10),自动计算网格参数 |
| └─ 性能约束 | ✅ PASS | 60秒全市场,100ms单标的,512MB内存 |

### ✅ 决策框架验证 (Decision Framework)

按优先级排序:

1. **可测试性** ✅: 指标计算纯函数,pytest覆盖
2. **可读性** ✅: NumPy向量化代码,清晰的分步Pipeline
3. **一致性** ✅: 复用项目的ThreadPoolExecutor模式
4. **简单性** ✅: 手动实现ATR/KER,避免TA-Lib复杂性
5. **可逆性** ✅: 无数据库迁移,仅命令行工具

### 🚦 Gate状态: PASS ✅

**结论**: 所有核心原则和技术标准满足要求。仅"可追溯性"为部分满足(MVP范围限制),但在Out of Scope中明确声明,后续迭代可补充。

**批准进入Phase 1设计阶段**。

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
grid_trading/                          # 新建Django app:做空网格筛选
├── __init__.py
├── management/
│   ├── __init__.py
│   └── commands/
│       ├── __init__.py
│       └── screen_short_grid.py      # FR-034: Django Management Command
│
├── services/                          # 业务逻辑层
│   ├── __init__.py
│   ├── binance_futures_client.py     # 币安Futures API客户端(复用monitor模式)
│   ├── indicator_calculator.py       # 技术指标计算(NATR/KER/Hurst/CVD)
│   ├── screening_engine.py           # 筛选引擎(Pipeline主流程)
│   └── scoring_model.py              # 评分模型(GSS公式)
│
├── models/                            # 数据模型(内存模型,无数据库)
│   ├── __init__.py
│   ├── market_symbol.py              # 市场标的概念模型
│   ├── volatility_metrics.py        # 波动率指标
│   ├── trend_metrics.py              # 趋势指标
│   ├── microstructure_metrics.py    # 微观结构指标
│   └── screening_result.py           # 筛选结果
│
└── utils/                             # 工具函数
    ├── __init__.py
    ├── validators.py                  # 参数验证(权重/阈值)
    └── formatters.py                  # 终端输出格式化

tests/grid_trading/                    # 测试目录
├── __init__.py
├── unit/
│   ├── test_indicator_calculator.py  # 单元测试:指标计算
│   ├── test_scoring_model.py         # 单元测试:评分模型
│   └── test_validators.py            # 单元测试:参数验证
├── integration/
│   ├── test_binance_client.py        # 集成测试:API调用
│   └── test_screening_engine.py      # 集成测试:筛选Pipeline
└── e2e/
    └── test_screen_command.py        # 端到端测试:命令执行
```

**Structure Decision**: 单一项目结构(Option 1)

**理由**:
1. **复用现有模式**: 项目已有`monitor/`, `backtest/`, `vp_squeeze/`等Django app,新建`grid_trading/`保持一致
2. **独立模块**: 筛选系统是独立功能,不依赖其他app的数据库模型
3. **清晰分层**:
   - `services/`: 业务逻辑(API客户端, 指标计算, 评分)
   - `models/`: 概念模型(仅数据类,无ORM)
   - `management/commands/`: Django命令入口
4. **可扩展性**: 后续迭代如需添加持久化,可在`grid_trading/models/`添加Django ORM模型

**关键文件说明**:
- `screen_short_grid.py`: 命令入口,参数解析,调用筛选引擎
- `screening_engine.py`: 核心Pipeline(初筛→指标计算→评分→排序)
- `indicator_calculator.py`: NumPy向量化实现NATR/KER/Hurst/CVD
- `scoring_model.py`: GSS评分公式,权重配置,趋势否决机制

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

### ⚠️ 部分违反项说明

| 违反项 | 为何需要 | 更简单替代方案被拒绝的原因 |
|--------|----------|--------------------------|
| **可追溯性不完整** (MVP不持久化筛选结果) | MVP专注验证筛选算法有效性,终端输出满足核心需求 | 完整持久化需引入数据库模型和API,超出MVP范围(明确列入Out of Scope) |
| **无回测验证** (不与Grid V4集成) | MVP仅输出筛选结果,回测验证是独立的后续迭代 | 回测集成需完整的数据流和状态管理,增加MVP复杂度(明确列入Out of Scope) |

**结论**: 上述违反项均在spec.md的Out of Scope中明确声明,符合MVP最小化原则。后续迭代可按需补充。


---

## Phase 1 Complete ✅

**Deliverables**:
- ✅ [research.md](./research.md) - 技术研究(Hurst指数/币安API/并行计算)
- ✅ [data-model.md](./data-model.md) - 数据模型(5个Entity定义)
- ✅ [quickstart.md](./quickstart.md) - 用户快速开始指南
- ✅ [contracts/command-interface.md](./contracts/command-interface.md) - 命令接口契约

**Constitution Re-check**: PASS ✅
- 所有Phase 0识别的风险已缓解
- 数据模型符合SOLID原则
- 接口契约明确且可测试

**Ready for Phase 2**: 运行 `/speckit.tasks` 生成实施任务清单


