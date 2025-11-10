# Implementation Plan: 加密货币交易所新币上线监控系统

**Branch**: `001-listing-monitor` | **Date**: 2025-11-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-listing-monitor/spec.md`

## Summary

构建一个自动化监控系统,定期获取Binance、Bybit、Bitget三个交易所的公告,识别新币上线信息(现货/合约),将数据存储到数据库,并通过Webhook实时推送通知。系统需要处理错误、避免重复通知、监控解析成功率,并提供Django Admin管理界面供人工审核模糊公告。

**核心技术方案**:
- 使用Django框架构建Web应用
- 复用现有crypto_exchange_news_crawler的Scrapy爬虫获取公告
- 使用Celery + Django Celery Beat实现定期监控调度
- 新增识别器模块(关键词匹配)识别新币上线
- 使用Django ORM + PostgreSQL/SQLite存储数据
- 使用requests库发送Webhook通知到用户提供的Web接口
- 提供Django Admin后台管理界面

## Technical Context

**Language/Version**: Python 3.8+
**Primary Dependencies**:
- Django 4.2+ (Web框架和ORM)
- Scrapy 2.11.0+ (已有,用于爬取公告)
- Celery 5.3+ (异步任务队列)
- Django Celery Beat 2.5+ (定时任务调度)
- Redis 7.0+ (Celery消息代理和结果后端)
- requests 2.31+ (Webhook HTTP推送)
- django-cors-headers 4.3+ (CORS支持)

**Storage**: PostgreSQL 14+ (生产推荐) 或 SQLite (开发测试)
**Testing**: pytest, pytest-django
**Target Platform**: Linux server (支持Docker部署)
**Project Type**: Web application (Django项目)
**Performance Goals**:
- 监控周期5分钟内完成所有交易所爬取
- 单个交易所响应时间<30秒
- 通知延迟<30秒

**Constraints**:
- 必须遵守交易所robots.txt和请求频率限制
- 内存使用<500MB
- 支持7x24小时稳定运行

**Scale/Scope**:
- 初期支持3个交易所,可扩展到10+
- 预计每天识别0-20个新币上线事件
- 历史数据保留30天

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### 核心理念合规性

| 原则 | 状态 | 说明 |
|------|------|------|
| I. 使用中文沟通 | ✅ 通过 | 所有文档、注释使用中文 |
| II. 零假设原则 | ✅ 通过 | 已通过澄清阶段明确所有模糊需求 |
| III. 小步提交 | ✅ 通过 | 计划按用户故事分阶段实施 |
| IV. 借鉴现有代码 | ✅ 通过 | 复用crypto_exchange_news_crawler模块 |
| V. 务实主义 | ✅ 通过 | 选择成熟库而非自建复杂框架 |
| VI. 简单至上 | ✅ 通过 | 使用关键词匹配而非ML,SQLite而非复杂分布式系统 |
| VII. 测试驱动开发 | ✅ 通过 | 计划为每个模块编写测试 |

### 爬虫特定原则合规性

| 原则 | 状态 | 说明 |
|------|------|------|
| 尊重服务器 | ✅ 通过 | 5分钟监控周期,复用现有Scrapy配置(DOWNLOAD_DELAY) |
| 数据质量 | ✅ 通过 | 所有数据包含时间戳,验证必填字段 |
| 可扩展性 | ✅ 通过 | 设计支持新增交易所,预留Hyperliquid接口 |

**结论**: 所有宪法原则已满足,无需复杂度豁免。

## Project Structure

### Documentation (this feature)

```text
specs/001-listing-monitor/
├── plan.md              # 本文件
├── spec.md              # 功能规格说明
├── research.md          # Phase 0 研究文档
├── data-model.md        # Phase 1 数据模型
├── quickstart.md        # Phase 1 快速开始指南
├── contracts/           # Phase 1 API契约
│   └── api-endpoints.md # API端点规范
└── checklists/
    └── requirements.md  # 需求质量检查清单
```

### Source Code (repository root)

```text
crypto_exchange_news_crawler/  # 项目根目录
│
├── crypto_exchange_news/      # 现有Scrapy爬虫模块
│   ├── spiders/               # 现有:各交易所爬虫
│   ├── settings.py            # 现有:Scrapy配置
│   └── cli.py                 # 现有:CLI入口
│
├── listing_monitor_project/   # 【新增】Django项目根目录
│   ├── __init__.py
│   ├── settings.py            # Django配置
│   ├── urls.py                # 路由配置
│   ├── wsgi.py                # WSGI入口
│   ├── asgi.py                # ASGI入口
│   └── celery.py              # Celery配置
│
├── monitor/                   # 【新增】Django应用:监控核心模块
│   ├── __init__.py
│   ├── apps.py                # 应用配置
│   ├── models.py              # Django模型(Exchange, Announcement, Listing, NotificationRecord)
│   ├── admin.py               # Django Admin配置
│   ├── views.py               # API视图
│   ├── urls.py                # 应用路由
│   ├── tasks.py               # Celery任务
│   ├── services/              # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── crawler.py         # 调用Scrapy爬虫
│   │   ├── identifier.py      # 新币识别器
│   │   └── notifier.py        # Webhook通知器
│   ├── management/            # Django管理命令
│   │   └── commands/
│   │       ├── start_monitor.py
│   │       └── init_exchanges.py
│   └── migrations/            # 数据库迁移
│       └── __init__.py
│
├── api/                       # 【新增】Django应用:对外API
│   ├── __init__.py
│   ├── apps.py
│   ├── views.py               # REST API视图
│   ├── serializers.py         # DRF序列化器
│   └── urls.py
│
├── tests/                     # 【新增】测试目录
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_tasks.py
│   ├── test_identifier.py
│   ├── test_notifier.py
│   └── fixtures/
│       └── sample_announcements.json
│
├── config/                    # 【新增】配置文件目录
│   ├── keywords.yaml          # 识别关键词配置
│   └── celery.conf            # Celery配置
│
├── manage.py                  # 【新增】Django管理脚本
├── requirements.txt           # 更新:Django相关依赖
├── requirements-dev.txt       # 【新增】开发依赖
├── Dockerfile                 # 【新增】Docker构建文件
├── docker-compose.yml         # 【新增】Docker Compose配置
└── README.md                  # 更新:项目说明
```

**Structure Decision**:
采用Django Web应用结构,在现有Scrapy项目基础上新增独立的Django项目。理由:
1. Django项目与Scrapy爬虫模块共存,职责清晰分离
2. Django Admin提供强大的Web管理界面
3. Celery + Django Celery Beat是Django生态的标准定时任务方案
4. 复用现有爬虫,通过services/crawler.py调用
5. 提供REST API供外部系统集成
6. 完整的Web应用,支持横向扩展

## Complexity Tracking

无需填写 - 所有设计决策都符合宪法原则,无复杂度豁免。
