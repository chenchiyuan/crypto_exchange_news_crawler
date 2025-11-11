# Implementation Plan: Futures Contract Data Monitor

**Branch**: `002-futures-data-monitor` | **Date**: 2025-11-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-futures-data-monitor/spec.md`

## Summary

**MVP阶段简化范围**: 实现一个合约数据监控系统,从3家交易所(Binance优先级1, Hyperliquid优先级2, Bybit优先级3)获取USDT本位永续合约列表和当前价格。系统每5分钟轮询一次,检测新合约上线并通过慧诚告警推送服务发送通知。数据存储在Django数据库中,通过Admin界面提供查看和管理功能。

**延后至Phase 2**: Open Interest、24H Volume、Funding Rate等高级指标; Bitget交易所集成; 历史价格数据存储

**技术方案**:
- 扩展现有的 Django 项目(listing_monitor_project)
- 使用官方交易所REST API获取合约列表和当前价格(无需认证的公开端点)
- 采用单表模型存储当前快照(仅包含基础字段: symbol, price, status, timestamps)
- 实现3次重试机制处理API失败,使用指数退避策略
- 复用001-listing-monitor的通知服务架构

## Technical Context

**Language/Version**: Python 3.8+ (已确定,项目使用Python 3.12.9)
**Primary Dependencies**: Django 4.2.8, requests/httpx (HTTP客户端), 已有的慧诚告警推送服务
**Storage**: SQLite (开发) / PostgreSQL (生产) - 扩展现有的 db.sqlite3
**Testing**: pytest (项目已采用)
**Target Platform**: Linux server (与现有系统一致)
**Project Type**: Django web application (单体应用)
**Performance Goals**: 3个交易所总计30秒内完成数据获取,每5分钟执行一次
**Constraints**: API rate limit尊重(每个交易所1200-6000 req/min), 90天delisted合约保留期
**Scale/Scope**: 预计每个交易所100-200个永续合约,MVP阶段总计300-600条记录

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### 核心原则符合性

| 原则 | 状态 | 说明 |
|------|------|------|
| **使用中文沟通** | ✅ 通过 | 所有文档、代码注释使用中文 |
| **零假设原则** | ✅ 通过 | 已通过clarify阶段澄清5个关键问题 |
| **小步提交** | ✅ 通过 | 计划分3个优先级实施,每个PR独立可测试 |
| **借鉴现有代码** | ✅ 通过 | 复用001特性的架构模式(Exchange模型、Service层、Django Admin) |
| **务实主义** | ✅ 通过 | 选择简单的单表模型,放弃复杂的时序数据库 |
| **简单至上** | ✅ 通过 | 直接API轮询,避免WebSocket复杂性;单表存储,避免join查询 |
| **测试驱动开发** | ✅ 通过 | 每个Service方法都有对应的单元测试 |

### 技术标准符合性

| 标准 | 状态 | 说明 |
|------|------|------|
| **SOLID原则** | ✅ 通过 | Service层单一职责;API客户端可替换 |
| **DRY原则** | ✅ 通过 | 复用Exchange模型;共享错误处理逻辑 |
| **奥卡姆剃刀** | ✅ 通过 | 最简单的轮询+单表方案 |
| **演进式架构** | ✅ 通过 | 可后续扩展时序数据,不影响现有功能 |
| **组合优于继承** | ✅ 通过 | Service使用依赖注入 |
| **接口优于单例** | ✅ 通过 | API客户端基于接口设计 |
| **显式优于隐式** | ✅ 通过 | 明确的重试策略,显式的时间戳字段 |

### 项目特定约束

| 约束 | 状态 | 说明 |
|------|------|------|
| **尊重服务器** | ✅ 通过 | 5分钟轮询间隔,远低于rate limit;3次重试使用指数退避 |
| **数据质量** | ✅ 通过 | 所有记录包含first_seen和last_updated时间戳;必填字段验证 |
| **可扩展性** | ✅ 通过 | 每个交易所独立的API客户端;标准化的数据结构 |

### 违规需要说明的复杂性

无违规项。本方案完全符合宪法原则,采用最简单的架构设计。

## Project Structure

### Documentation (this feature)

```text
specs/002-futures-data-monitor/
├── spec.md              # 功能规范 (已完成)
├── plan.md              # 本文件 - 实施计划
├── research.md          # Phase 0 输出 - 技术调研
├── data-model.md        # Phase 1 输出 - 数据模型
├── quickstart.md        # Phase 1 输出 - 快速开始
├── contracts/           # Phase 1 输出 - API契约
│   ├── binance-api.md   # Priority 1
│   ├── hyperliquid-api.md  # Priority 2
│   └── bybit-api.md     # Priority 3
└── tasks.md             # Phase 2 输出 - 任务分解 (由/speckit.tasks生成)
```

### Source Code (repository root)

```text
listing_monitor_project/     # Django项目根目录 (已存在)
├── settings.py              # Django配置 (扩展INSTALLED_APPS)
├── urls.py                  # URL路由 (无需修改)
└── wsgi.py

monitor/                     # Django App (已存在,扩展)
├── models.py                # 新增: FuturesContract模型 (MVP: 仅基础字段)
├── admin.py                 # 新增: FuturesContract Admin配置
├── services/
│   ├── futures_fetcher.py   # 新增: 合约数据获取服务
│   └── futures_notifier.py  # 新增: 新合约通知服务 (复用notifier基础)
├── api_clients/             # 新增: 交易所API客户端目录
│   ├── __init__.py
│   ├── base.py              # 抽象基类
│   ├── binance.py           # Priority 1
│   ├── hyperliquid.py       # Priority 2
│   └── bybit.py             # Priority 3
├── management/commands/
│   ├── fetch_futures.py     # 新增: 手动获取合约数据命令
│   └── monitor_futures.py   # 新增: 一键监控命令 (获取+检测+通知)
├── migrations/
│   └── 000X_add_futures_contract.py  # 新增: 数据库迁移
└── tests/
    ├── test_futures_fetcher.py
    ├── test_futures_notifier.py
    └── api_clients/
        ├── test_binance.py
        ├── test_hyperliquid.py
        └── test_bybit.py

scripts/                     # Shell脚本 (已存在)
└── monitor_futures.sh       # 新增: 定时任务脚本

config/                      # 配置文件 (已存在)
└── futures_config.py        # 新增: 合约监控配置

tests/                       # 集成测试 (已存在)
└── test_futures_integration.py  # 新增: 端到端测试
```

**Structure Decision**:
采用 Django 单体应用架构,扩展现有的 `monitor` app。这种结构符合项目现状:
- 复用已有的 Exchange 模型(无需重复定义交易所)
- 复用已有的通知服务基础设施
- 保持项目结构一致性,降低维护成本
- 所有合约相关代码集中在 monitor app 下,职责清晰

新增的 `api_clients` 目录采用抽象基类模式,每个交易所独立实现,符合开闭原则。

## Complexity Tracking

无需填写。本方案无宪法违规项,所有复杂性决策都有充分理由且符合最简原则。
