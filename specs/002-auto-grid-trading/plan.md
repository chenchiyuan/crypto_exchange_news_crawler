# Implementation Plan: 自动化网格交易系统

**Branch**: `002-auto-grid-trading` | **Date**: 2025-12-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-auto-grid-trading/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

实现一个自动化的永续合约网格交易系统,支持做空、中性、做多三种网格模式。系统能够自动对接多个交易所(优先Binance Futures),实时监控市场行情,在预设价格区间内自动挂单开仓和平仓,实现震荡市场套利。系统内置完善的风控机制(止损保护、持仓限制)、错误处理(WebSocket重连、订单失败重试)和交易统计功能(盈亏分析、成交率统计)。

技术方法:采用模块化架构,分为Scanner(扫描)、Trigger(触发)、Executor(执行)三个独立模块。使用WebSocket实时数据流订阅市场行情,通过订单同步机制(四元组标识)确保网格订单与交易所一致,通过环形缓冲区记录交易日志。

## Technical Context

**Language/Version**: Python 3.8+
**Primary Dependencies**: Django 4.2.8, python-binance (币安SDK), websockets, pandas, numpy
**Storage**: PostgreSQL (生产环境) / SQLite (开发环境)
**Testing**: pytest
**Target Platform**: Linux server (支持24/7运行的服务器环境)
**Project Type**: Web application (Django后台 + 异步策略执行器)
**Performance Goals**:
- WebSocket数据推送到订单同步延迟 < 2秒
- 止损触发到完成平仓时间 < 10秒
- 单服务器支持并发运行20个网格策略
- 全市场扫描(500+标的)完成时间 < 60秒

**Constraints**:
- 订单同步幂等性: 多次执行不产生重复订单
- 系统可用性: 24小时连续运行无崩溃 >= 99.9%
- 统计数据计算误差 < 0.01%
- 交易所API限流: Binance 1200请求/分钟

**Scale/Scope**:
- 支持3种网格模式(做空/中性/做多)
- 13个功能需求模块
- 5个核心实体(GridConfig, GridLevel, OrderIntent, TradeLog, GridStatistics)
- 预计代码量: 3000-5000行核心代码

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### 核心原则合规性

✅ **使用中文沟通**: 所有文档、代码注释、提交信息均使用中文
✅ **零假设原则**: 规格文档已完成3个关键问题澄清,无模糊需求
✅ **小步提交**: 计划分阶段实施,每个阶段独立可测试
✅ **借鉴现有代码**: 将研究参考项目ritmex-bot和项目现有模式
✅ **务实主义**: 优先实现做空网格(MVP),渐进式扩展中性/做多模式
✅ **简单至上**: 采用等间距网格(非斐波那契等复杂变种),避免过早抽象
✅ **测试驱动**: 计划包含单元测试和集成测试覆盖率要求(>=80%)

### 量化交易系统原则合规性

✅ **回测优先**: 虽然MVP阶段不包含回测引擎,但策略逻辑将支持后续回测集成
✅ **风险控制第一**: 实现止损保护(FR-8)、持仓限制(FR-9)、异常恢复(FR-12)
✅ **模块化与状态隔离**: 采用Scanner/Trigger/Executor三层架构
✅ **参数可追溯**: 所有配置参数持久化到数据库,交易日志完整记录(FR-10)
✅ **渐进式部署**: 计划先实现做空网格,验证后再扩展中性/做多模式

### 技术标准合规性

✅ **SOLID原则**: 交易所适配器使用抽象基类(FR-5),支持多交易所扩展
✅ **DRY原则**: 订单同步逻辑抽象为通用机制,复用于三种网格模式
✅ **错误处理**: 完整的错误处理机制(FR-12),覆盖WebSocket断线、API限流等场景
✅ **提交标准**: 每次提交必须通过测试,符合black/isort格式化规范

### 约束条件合规性

✅ **模块运行频率**: Scanner(4小时)、Trigger(15分钟)、Executor(实时/1秒轮询)
✅ **数据依赖**: Scanner使用至少300根K线(约50天的4H数据)
✅ **风险参数范围**: 止损缓冲区配置化,持仓限制强制执行
✅ **状态持久化**: 所有策略状态持久化到数据库,支持系统重启恢复
✅ **日志与监控**: 完整的交易日志记录(FR-10),环形缓冲区(200条默认)

### 潜在复杂性 (无需额外论证)

本功能符合所有宪法原则,不存在需要论证的复杂性违规。

## Project Structure

### Documentation (this feature)

```text
specs/002-auto-grid-trading/
├── plan.md              # 本文件 (/speckit.plan 输出)
├── research.md          # Phase 0 输出 (技术选型研究)
├── data-model.md        # Phase 1 输出 (数据模型设计)
├── quickstart.md        # Phase 1 输出 (快速开始指南)
├── contracts/           # Phase 1 输出 (API契约定义)
│   ├── grid-config.yaml # 网格配置管理API
│   ├── grid-control.yaml # 网格生命周期控制API
│   └── grid-stats.yaml  # 网格统计查询API
├── spec.md              # 功能规格文档 (已完成)
└── checklists/
    └── requirements.md  # 规格质量检查清单 (已完成)
```

### Source Code (repository root)

```text
grid_trading/                        # Django app (新增)
├── __init__.py
├── models/                          # Django models
│   ├── __init__.py
│   ├── grid_config.py               # GridConfig模型
│   ├── grid_level.py                # GridLevel模型
│   ├── order_intent.py              # OrderIntent模型
│   ├── trade_log.py                 # TradeLog模型
│   └── grid_statistics.py           # GridStatistics模型
├── services/                        # 业务逻辑层
│   ├── __init__.py
│   ├── exchange/                    # 交易所适配器
│   │   ├── __init__.py
│   │   ├── base.py                  # ExchangeAdapter抽象基类
│   │   └── binance_futures.py       # Binance Futures实现
│   ├── grid/                        # 网格策略核心
│   │   ├── __init__.py
│   │   ├── engine.py                # 网格引擎主逻辑
│   │   ├── short_grid.py            # 做空网格策略
│   │   ├── neutral_grid.py          # 中性网格策略
│   │   ├── long_grid.py             # 做多网格策略
│   │   └── order_sync.py            # 订单同步机制
│   ├── risk/                        # 风控模块
│   │   ├── __init__.py
│   │   ├── stop_loss.py             # 止损保护
│   │   └── position_limit.py        # 持仓限制
│   └── stats/                       # 统计分析
│       ├── __init__.py
│       └── calculator.py            # 统计指标计算
├── management/                      # Django management commands
│   └── commands/
│       ├── start_grid.py            # 启动网格策略
│       ├── stop_grid.py             # 停止网格策略
│       ├── pause_grid.py            # 暂停网格策略
│       ├── resume_grid.py           # 恢复网格策略
│       └── grid_status.py           # 查询网格状态
├── admin.py                         # Django admin配置
├── apps.py
├── migrations/                      # 数据库迁移文件
└── tests/                           # 测试文件
    ├── __init__.py
    ├── unit/                        # 单元测试
    │   ├── test_grid_engine.py
    │   ├── test_order_sync.py
    │   └── test_exchange_adapter.py
    └── integration/                 # 集成测试
        ├── test_grid_lifecycle.py
        └── test_binance_integration.py

crypto_exchange_news_crawler/       # Django项目配置 (已存在)
├── settings.py                      # 需更新: INSTALLED_APPS添加grid_trading
└── urls.py                          # 需更新: 路由配置(如需要)
```

**Structure Decision**: 采用Django Web应用架构,新增`grid_trading` app。选择理由:
1. **复用现有基础设施**: 项目已使用Django框架,复用ORM、Admin、命令行工具
2. **模块化隔离**: 网格交易作为独立app,与现有爬虫功能解耦
3. **三层架构**: models(数据层) → services(业务逻辑层) → management(控制层)
4. **测试友好**: 单元测试和集成测试分离,便于TDD开发

## Complexity Tracking

> **本项目无需额外论证的复杂性**

本功能设计完全符合宪法原则,不存在需要论证的架构复杂性或约束违规。
