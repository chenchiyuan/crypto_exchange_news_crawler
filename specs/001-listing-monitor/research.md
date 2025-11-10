# Phase 0: 技术研究文档

**项目**: 加密货币交易所新币上线监控系统
**创建日期**: 2025-11-06
**更新日期**: 2025-11-06
**状态**: 研究完成
**架构模式**: Django + Celery混合架构

## 目录

1. [架构模式选择](#1-架构模式选择)
2. [HTTP框架与API设计](#2-http框架与api设计)
3. [任务队列方案](#3-任务队列方案)
4. [ORM与数据库方案](#4-orm与数据库方案)
5. [Webhook通知方案](#5-webhook通知方案)
6. [关键词识别算法](#6-关键词识别算法)
7. [错误重试与退避策略](#7-错误重试与退避策略)
8. [配置管理方案](#8-配置管理方案)
9. [推荐技术栈总结](#9-推荐技术栈总结)

---

## 1. 架构模式选择

### 需求分析

系统需要支持两种访问方式:
- **HTTP API**: 允许外部系统主动查询和触发监控
- **定时任务**: 自动定期执行监控任务
- **异步处理**: 长时间运行的任务不阻塞HTTP请求

### 方案对比

#### 方案A: Django + Celery混合架构 (推荐)

**描述**: Django提供HTTP接口和管理后台,Celery + Django Celery Beat作为任务队列执行后台监控。

**架构图**:
```
┌─────────────┐
│   用户/外部  │
│    系统     │
└──────┬──────┘
       │ HTTP
       ▼
┌─────────────┐     触发     ┌──────────────┐
│   Django    │─────────────▶│    Celery    │
│  HTTP服务   │              │   任务队列    │
│  + Admin    │              │   + Beat     │
└──────┬──────┘              └──────┬───────┘
       │                            │
       │        ┌──────────┐        │
       └───────▶│  Redis   │◀───────┘
                │  消息代理 │
                └──────────┘
                      │
                      ▼
   ┌────────────────────────────────┐
   │         核心业务逻辑            │
   │  - 爬虫调度                     │
   │  - 新币识别                     │
   │  - 通知发送                     │
   └────────────────────────────────┘
```

**优点**:
- 灵活性强: 支持API、Admin和定时任务三种模式
- 可观测性好: Django Admin便于数据管理和审核
- 易于集成: 外部系统可通过REST API触发任务
- 响应迅速: Celery异步任务不阻塞HTTP请求
- 可扩展性强: Celery支持分布式部署和横向扩展
- 生态成熟: Django + Celery是Python Web开发标准组合

**缺点**:
- 需要额外中间件: 需要Redis作为消息代理
- 架构稍复杂: 需要同时管理Django、Celery Worker、Celery Beat

**代码示例**:
```python
# listing_monitor_project/celery.py
from celery import Celery
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')

app = Celery('listing_monitor')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# monitor/tasks.py
from celery import shared_task
from .services.crawler import CrawlerService
from .services.identifier import IdentifierService
from .services.notifier import WebhookNotifier

@shared_task
def monitor_job():
    """监控任务主逻辑"""
    # 1. 调用Scrapy爬虫
    crawler = CrawlerService()
    announcements = crawler.fetch_all_exchanges()

    # 2. 识别新币上线
    identifier = IdentifierService()
    listings = identifier.identify_listings(announcements)

    # 3. 存储和通知
    notifier = WebhookNotifier()
    for listing in listings:
        listing.save()
        notifier.send_notification(listing)

# monitor/views.py
from django.http import JsonResponse
from .tasks import monitor_job

def trigger_monitor(request):
    """手动触发监控"""
    task = monitor_job.delay()
    return JsonResponse({"status": "triggered", "task_id": str(task.id)})

def get_status(request):
    """查询监控状态"""
    return JsonResponse({"running": True})
```

**适用场景**: 本项目(需要API访问 + 自动监控 + 管理后台)

---

#### 方案B: 纯CLI模式

**描述**: 只提供命令行接口,通过APScheduler定时执行。

**优点**:
- 简单: 无需HTTP服务
- 资源占用少: 单进程运行

**缺点**:
- 无法远程访问: 只能本地操作
- 可观测性差: 需要查看日志和数据库
- 难以集成: 外部系统无法触发任务

**适用场景**: 简单场景,无需API访问

---

#### 方案C: 纯API模式(无定时任务)

**描述**: 只提供HTTP API,由外部系统(如cron)定时调用。

**优点**:
- 架构简单: 无状态HTTP服务
- 部署灵活: 易于水平扩展

**缺点**:
- 依赖外部调度: 需要额外的cron服务
- 任务管理复杂: 需要自行处理任务重叠

**适用场景**: 微服务架构,统一调度系统

---

### 推荐方案: Django + Celery混合架构

**理由**:
1. 满足"灵活性"要求 - 支持API、Admin和自动监控
2. 易于扩展 - Django Admin提供强大的管理界面
3. 可观测性强 - 通过REST API和Admin查询状态
4. 开发效率高 - Django REST Framework自动生成API文档
5. 生态成熟 - Django + Celery是Python Web开发标准组合
6. 可扩展性强 - Celery支持分布式部署

**实现要点**:
```python
# listing_monitor_project/settings.py
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_BEAT_SCHEDULE = {
    'monitor-every-5-minutes': {
        'task': 'monitor.tasks.monitor_job',
        'schedule': 300.0,  # 300秒
    },
}

# monitor/tasks.py
from celery import shared_task
from .services.crawler import CrawlerService
from .services.identifier import IdentifierService
from .services.notifier import WebhookNotifier

@shared_task
def monitor_job():
    """监控任务主逻辑"""
    crawler = CrawlerService()
    identifier = IdentifierService()
    notifier = WebhookNotifier()

    # 爬取、识别、通知
    announcements = crawler.fetch_all_exchanges()
    listings = identifier.identify_listings(announcements)
    for listing in listings:
        listing.save()
        notifier.send_notification(listing)

# monitor/views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .tasks import monitor_job

@api_view(['POST'])
def trigger_monitor(request):
    """手动触发监控"""
    task = monitor_job.delay()
    return Response({"status": "triggered", "task_id": str(task.id)})

@api_view(['GET'])
def get_status(request):
    """查询监控状态"""
    return Response({"running": True})
```

---

## 2. HTTP框架与API设计

### 需求分析

需要提供以下API端点:
- 触发监控任务
- 查询监控状态
- 查询新币上线列表
- 审核新币上线
- 配置管理

### 方案对比

#### 方案A: Django + Django REST Framework (推荐)

**描述**: Django作为Web框架,Django REST Framework提供RESTful API。

**优点**:
- 功能完整: 内置认证、权限、分页、过滤等
- ORM集成: 与Django ORM无缝集成
- Admin界面: 自带强大的管理后台,便于数据审核
- 序列化器: DRF的Serializers自动处理数据验证和转换
- 文档自动生成: 支持drf-yasg生成Swagger文档
- 社区成熟: 大量第三方插件和最佳实践
- 与Celery集成: Django + Celery是标准组合

**缺点**:
- 相对重量级: 框架较大,启动稍慢
- 学习曲线: 需要学习Django和DRF生态

**代码示例**:
```python
# monitor/serializers.py
from rest_framework import serializers
from .models import Listing, Announcement, Exchange

class ExchangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exchange
        fields = ['id', 'code', 'name', 'enabled']

class ListingSerializer(serializers.ModelSerializer):
    exchange = ExchangeSerializer(source='announcement.exchange', read_only=True)

    class Meta:
        model = Listing
        fields = ['id', 'coin_symbol', 'coin_name', 'listing_type',
                  'exchange', 'confidence', 'status', 'identified_at']

# api/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from monitor.models import Listing
from monitor.serializers import ListingSerializer
from monitor.tasks import monitor_job

class ListingViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Listing.objects.all()
    serializer_class = ListingSerializer
    filterset_fields = ['status', 'listing_type']

    @action(detail=False, methods=['post'])
    def trigger_monitor(self, request):
        """手动触发监控"""
        task = monitor_job.delay()
        return Response({"status": "triggered", "task_id": str(task.id)})

    @action(detail=True, methods=['put'])
    def review(self, request, pk=None):
        """审核新币上线"""
        listing = self.get_object()
        action = request.data.get('action')
        if action == 'confirm':
            listing.status = 'confirmed'
            listing.save()
        return Response({"status": "success"})

# api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ListingViewSet

router = DefaultRouter()
router.register(r'listings', ListingViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
```

**适用场景**: 本项目(需要完整的Web功能和管理后台)

---

#### 方案B: FastAPI

**描述**: 现代化的Python Web框架,基于类型提示和异步。

**优点**:
- 性能优秀: 基于Starlette和Pydantic,接近NodeJS/Go性能
- 自动文档: 自动生成OpenAPI(Swagger)文档
- 类型安全: 基于类型提示,自动验证和序列化
- 异步支持: 原生支持async/await

**缺点**:
- 无内置Admin: 需要自己实现管理界面
- 生态较新: 2018年发布,生态不如Django成熟
- 与Celery集成: 需要额外配置

**适用场景**: 对性能要求极高的API服务

---

#### 方案C: Flask

**描述**: 轻量级Web框架,Python Web开发标准。

**优点**:
- 成熟稳定: 2010年发布,生态丰富
- 学习成本低: 简单直接

**缺点**:
- 功能较少: 需要手动实现很多功能
- 无Admin界面

**适用场景**: 极简应用

---

### 推荐方案: Django + Django REST Framework

**理由**:
1. Django Admin提供强大的管理后台 - 满足人工审核需求
2. DRF功能完整 - 认证、权限、分页开箱即用
3. 与Django ORM无缝集成 - 减少代码量
4. 与Celery集成成熟 - Django + Celery是标准组合
5. 开发效率高 - ViewSets和Serializers大幅减少代码
6. 社区支持强 - 大量插件和最佳实践

---

## 3. 任务队列方案

### 需求分析

系统需要定期(默认每5分钟)执行以下任务:
- 调用Scrapy爬虫获取各交易所公告
- 识别新币上线信息
- 存储数据并发送通知

### 方案对比

#### 方案A: Celery + Django Celery Beat (推荐)

**描述**: Celery是Python最流行的分布式任务队列,Django Celery Beat提供定时任务支持。

**优点**:
- 支持分布式部署和水平扩展
- 丰富的任务管理功能(优先级、链式任务、回调)
- 内置任务重试、超时控制
- 支持多种消息代理(Redis、RabbitMQ)
- 与Django集成成熟(Django + Celery是标准组合)
- 任务监控工具(Flower)
- 适合生产环境

**缺点**:
- 需要额外中间件(Redis/RabbitMQ),部署稍复杂
- 学习曲线中等

**代码示例**:
```python
# listing_monitor_project/celery.py
from celery import Celery
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')

app = Celery('listing_monitor')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# listing_monitor_project/settings.py
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_BEAT_SCHEDULE = {
    'monitor-every-5-minutes': {
        'task': 'monitor.tasks.monitor_job',
        'schedule': 300.0,  # 300秒 = 5分钟
    },
}

# monitor/tasks.py
from celery import shared_task
from .services.crawler import CrawlerService
from .services.identifier import IdentifierService
from .services.notifier import WebhookNotifier

@shared_task
def monitor_job():
    """监控任务主逻辑"""
    crawler = CrawlerService()
    announcements = crawler.fetch_all_exchanges()

    identifier = IdentifierService()
    listings = identifier.identify_listings(announcements)

    notifier = WebhookNotifier()
    for listing in listings:
        listing.save()
        notifier.send_notification(listing)
```

**适用场景**: 本项目(需要可靠的定时任务和未来扩展性)

---

#### 方案B: APScheduler

**描述**: Python原生的任务调度库,轻量级、易用。

**优点**:
- 简单易用,5行代码即可启动定时任务
- 无需额外中间件(如Redis/RabbitMQ)
- 支持多种触发器(间隔、cron表达式、固定时间)

**缺点**:
- 单机运行,无法水平扩展
- 任务不支持分布式队列
- 与Django集成不如Celery自然

**适用场景**: 简单单机应用,无扩展需求

---

#### 方案C: Cron + 脚本

**描述**: 使用系统cron定时执行Python脚本。

**优点**:
- 系统原生,无需额外依赖
- 简单直接,易于理解
- 适合运维人员管理

**缺点**:
- 缺乏任务管理功能(监控、重试、日志)
- 跨平台兼容性差(Windows需要Task Scheduler)
- 无法动态修改调度计划
- 需要手动处理任务重叠问题

**代码示例**:
```bash
# crontab配置
*/5 * * * * cd /path/to/project && /usr/bin/python monitor.py >> /var/log/monitor.log 2>&1
```

**适用场景**: 非常简单的定时任务,无特殊需求

---

### 推荐方案: Celery + Django Celery Beat

**理由**:
1. 与Django集成成熟 - Django + Celery是Python Web开发标准组合
2. 可扩展性强 - 支持分布式部署和横向扩展
3. 功能完善 - 内置重试、超时、监控等企业级特性
4. 社区活跃 - 大量最佳实践和工具支持
5. 生产就绪 - 已被大量生产环境验证
6. 支持多种消息代理 - Redis、RabbitMQ等

**实现要点**:
```python
# listing_monitor_project/celery.py
from celery import Celery
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')

app = Celery('listing_monitor')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# listing_monitor_project/settings.py
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_BEAT_SCHEDULE = {
    'monitor-every-5-minutes': {
        'task': 'monitor.tasks.monitor_job',
        'schedule': 300.0,  # 300秒
    },
}
CELERY_TASK_SOFT_TIME_LIMIT = 240  # 4分钟超时
CELERY_TASK_TIME_LIMIT = 300  # 5分钟硬超时

# monitor/tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

@shared_task(bind=True, max_retries=3)
def monitor_job(self):
    """监控任务核心逻辑"""
    try:
        logger.info("开始监控任务")
        # 1. 爬取公告
        # 2. 识别新币
        # 3. 存储通知
        logger.info("监控任务完成")
    except Exception as e:
        logger.error(f"监控任务失败: {e}", exc_info=True)
        # 重试任务
        raise self.retry(exc=e, countdown=60)  # 60秒后重试
```

---

## 4. ORM与数据库方案

### 需求分析

需要存储四类实体:
- Exchange(交易所)
- Announcement(公告)
- Listing(新币上线)
- NotificationRecord(通知记录)

关键要求:
- 关系型数据存储(支持外键、事务)
- 支持复杂查询(去重、时间范围、统计)
- 开发效率高,代码可维护

### 方案对比

#### 方案A: SQLAlchemy ORM (推荐)

**描述**: Python最流行的ORM框架,支持多种数据库。

**优点**:
- 成熟稳定,社区活跃
- 支持多种数据库(SQLite/PostgreSQL/MySQL)
- 声明式模型,代码简洁
- 强大的查询API(支持join、聚合、子查询)
- 自动处理事务和连接池
- 数据库迁移工具(Alembic)

**缺点**:
- 学习曲线中等
- 复杂查询可能需要原生SQL

**代码示例**:
```python
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime

Base = declarative_base()

class Exchange(Base):
    __tablename__ = 'exchanges'

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    code = Column(String(20), unique=True, nullable=False)
    enabled = Column(Integer, default=1)

    # 关系
    announcements = relationship('Announcement', back_populates='exchange')

class Announcement(Base):
    __tablename__ = 'announcements'

    id = Column(Integer, primary_key=True)
    news_id = Column(String(100), unique=True, nullable=False)
    title = Column(String(500), nullable=False)
    url = Column(String(500), nullable=False)
    announced_at = Column(DateTime, nullable=False)
    exchange_id = Column(Integer, ForeignKey('exchanges.id'))

    # 关系
    exchange = relationship('Exchange', back_populates='announcements')

# 使用示例
engine = create_engine('sqlite:///listing_monitor.db')
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()

# 查询
exchange = session.query(Exchange).filter_by(code='binance').first()
recent_announcements = (
    session.query(Announcement)
    .filter(Announcement.exchange_id == exchange.id)
    .filter(Announcement.announced_at > datetime.now() - timedelta(days=1))
    .all()
)
```

**适用场景**: 本项目(需要关系型数据库和复杂查询)

---

#### 方案B: Peewee ORM

**描述**: 轻量级ORM,API更简洁。

**优点**:
- 代码更简洁,学习成本低
- 性能略优于SQLAlchemy
- 支持常见数据库

**缺点**:
- 功能相对较少
- 社区和文档不如SQLAlchemy
- 复杂查询支持较弱

**适用场景**: 非常简单的数据模型

---

#### 方案C: 原生SQL

**描述**: 直接使用数据库驱动(如sqlite3、psycopg2)。

**优点**:
- 性能最优
- 完全控制SQL语句

**缺点**:
- 开发效率低,代码冗长
- 易出错(SQL注入、类型转换)
- 维护成本高

**适用场景**: 性能极致要求或特殊场景

---

### 推荐方案: Django ORM + SQLite/PostgreSQL

**理由**:
1. 与Django框架集成 - 无缝使用Django模型
2. 成熟稳定 - Django ORM经过大量生产验证
3. 功能完善 - 支持复杂查询、聚合、事务
4. 迁移管理 - Django migrations自动管理数据库版本
5. 开发效率 - 模型定义简洁,查询API直观
6. Admin支持 - 与Django Admin无缝集成

**数据库选择**:
- **开发/小规模**: SQLite(无需额外安装,单文件存储)
- **生产/大规模**: PostgreSQL(支持并发,性能更好)

**最佳实践**:

```python
# monitor/models.py
from django.db import models

class Exchange(models.Model):
    """交易所模型"""
    name = models.CharField(max_length=100, unique=True, verbose_name='交易所名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='交易所代码')
    announcement_url = models.URLField(max_length=500, blank=True, verbose_name='公告URL')
    enabled = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'exchanges'
        verbose_name = '交易所'
        verbose_name_plural = '交易所'

    def __str__(self):
        return f"{self.name} ({self.code})"

class Announcement(models.Model):
    """公告模型"""
    news_id = models.CharField(max_length=200, unique=True, verbose_name='公告ID')
    title = models.CharField(max_length=1000, verbose_name='标题')
    description = models.TextField(blank=True, verbose_name='描述')
    url = models.URLField(max_length=1000, unique=True, verbose_name='URL')
    announced_at = models.DateTimeField(verbose_name='发布时间')
    category = models.CharField(max_length=100, blank=True, verbose_name='分类')
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE,
                                 related_name='announcements', verbose_name='交易所')
    processed = models.BooleanField(default=False, verbose_name='是否已处理')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'announcements'
        ordering = ['-announced_at']
        indexes = [
            models.Index(fields=['exchange', 'announced_at']),
            models.Index(fields=['processed']),
        ]

# 使用示例
# 查询
exchange = Exchange.objects.get(code='binance')
recent_announcements = Announcement.objects.filter(
    exchange=exchange,
    announced_at__gte=timezone.now() - timedelta(days=1)
)

# 数据库迁移
# python manage.py makemigrations
# python manage.py migrate
```

---

## 5. Webhook通知方案

### 需求分析

- 新币上线后30秒内发送通知
- 通知内容包含币种信息和公告链接
- 支持失败重试(3次,间隔1分钟)
- 用户提供Webhook URL接收通知

### 方案对比

#### 方案A: requests库 + Webhook推送 (推荐)

**描述**: 使用requests库向用户提供的Webhook URL发送HTTP POST请求。

**优点**:
- 简单直接,无需第三方服务
- 用户可自定义接收端点
- 支持灵活的数据格式(JSON)
- 易于集成到现有系统
- 支持失败重试和错误处理
- 无额外依赖成本

**缺点**:
- 需要用户自行维护接收端点
- 网络问题可能导致通知失败

**代码示例**:
```python
# monitor/services/notifier.py
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class WebhookNotifier:
    def __init__(self, webhook_url=None, max_retries=3, retry_delay=60):
        self.webhook_url = webhook_url or settings.WEBHOOK_URL
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def send_notification(self, listing):
        """发送Webhook通知"""
        payload = self._format_payload(listing)

        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10,
                    headers={'Content-Type': 'application/json'}
                )
                response.raise_for_status()
                logger.info(f"通知发送成功: {listing.coin_symbol}")
                return True

            except requests.exceptions.RequestException as e:
                logger.warning(f"通知发送失败(尝试{attempt+1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"通知发送最终失败: {listing.coin_symbol}")
                    return False

    def _format_payload(self, listing):
        """格式化Webhook负载"""
        return {
            "event": "new_listing",
            "data": {
                "coin_symbol": listing.coin_symbol,
                "coin_name": listing.coin_name or "",
                "listing_type": listing.listing_type,
                "exchange": {
                    "code": listing.announcement.exchange.code,
                    "name": listing.announcement.exchange.name
                },
                "announcement": {
                    "title": listing.announcement.title,
                    "url": listing.announcement.url,
                    "announced_at": listing.announcement.announced_at.isoformat()
                },
                "confidence": listing.confidence,
                "identified_at": listing.identified_at.isoformat()
            },
            "timestamp": timezone.now().isoformat()
        }

# 配置示例 (settings.py)
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://your-domain.com/api/webhook/listing')

# 使用示例
notifier = WebhookNotifier()
notifier.send_notification(listing)
```

**适用场景**: 本项目(用户明确要求使用Webhook推送)

---

#### 方案B: Telegram Bot (备选)

**描述**: 使用python-telegram-bot向Telegram发送通知。

**优点**:
- 官方Bot API,功能丰富
- 支持富文本消息

**缺点**:
- 需要用户有Telegram账号
- 需要创建和配置Bot
- 不符合用户明确要求的Webhook方案

**适用场景**: 个人使用,不需要集成到其他系统

---

### 推荐方案: requests库 + Webhook推送

**理由**:
1. 符合用户明确要求 - "推送使用webhook,我会提供web接口推送"
2. 集成灵活 - 用户可自由处理通知数据
3. 实现简单 - 无需第三方服务和账号
4. 易于测试 - 可使用webhook.site等工具调试
5. 扩展性强 - 可支持多个webhook端点

**实现要点**:

```python
# monitor/services/notifier.py
import requests
import logging
import time
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

class WebhookNotifier:
    def __init__(self, webhook_url=None, max_retries=3, retry_delay=60):
        self.webhook_url = webhook_url or settings.WEBHOOK_URL
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def send_notification(self, listing):
        """发送Webhook通知(带重试)"""
        for attempt in range(self.max_retries):
            try:
                payload = self._format_payload(listing)
                response = requests.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10,
                    headers={'Content-Type': 'application/json'}
                )
                response.raise_for_status()
                logger.info(f"通知发送成功: {listing.coin_symbol}")
                return True

            except requests.exceptions.RequestException as e:
                logger.warning(f"通知发送失败(尝试{attempt+1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"通知发送最终失败: {listing.coin_symbol}")
                    return False

    def _format_payload(self, listing):
        """格式化Webhook负载"""
        return {
            "event": "new_listing",
            "data": {
                "coin_symbol": listing.coin_symbol,
                "coin_name": listing.coin_name or "",
                "listing_type": listing.listing_type,
                "exchange": {
                    "code": listing.announcement.exchange.code,
                    "name": listing.announcement.exchange.name
                },
                "announcement": {
                    "title": listing.announcement.title,
                    "url": listing.announcement.url,
                    "announced_at": listing.announcement.announced_at.isoformat()
                },
                "confidence": listing.confidence
            },
            "timestamp": timezone.now().isoformat()
        }
```

---

## 6. 关键词识别算法

### 需求分析

从公告标题/内容中识别:
- 是否为新币上线公告
- 币种代码和名称
- 上线类型(现货/合约)

准确率要求: >90%
召回率要求: >85%

### 方案对比

#### 方案A: 关键词匹配 + 正则表达式 (推荐)

**描述**: 基于规则的识别,使用关键词列表和正则模式。

**优点**:
- 实现简单,易于理解和调试
- 无需训练数据
- 可解释性强(知道为什么匹配)
- 易于维护和更新规则

**缺点**:
- 准确率受限于规则完善程度
- 对新格式公告适应性差
- 需人工维护关键词库

**实现逻辑**:

```python
# listing_monitor/identifier.py
import re
from typing import Optional, Dict

class ListingIdentifier:
    # 新币上线关键词(中英文)
    LISTING_KEYWORDS = [
        # 英文
        'new listing', 'list', 'listing', 'will list', 'listed',
        'new coin', 'new token', 'adds', 'add',
        'launch', 'launches', 'launching',
        # 中文
        '上线', '上币', '新币', '开放交易',
    ]

    # 上线类型关键词
    SPOT_KEYWORDS = ['spot', 'spot trading', '现货']
    FUTURES_KEYWORDS = [
        'futures', 'perpetual', 'usdⓢ-m', 'usdt-margined',
        '合约', '永续', '永续合约'
    ]

    # 币种代码正则(1-10个大写字母/数字)
    COIN_PATTERN = re.compile(r'\b([A-Z][A-Z0-9]{0,9})\b')

    def identify(self, announcement: Dict) -> Optional[Dict]:
        """
        识别是否为新币上线公告

        返回格式:
        {
            'is_listing': bool,
            'coin_symbol': str,
            'coin_name': str,
            'listing_type': str,  # 'spot' / 'futures' / 'both'
            'confidence': float   # 0.0-1.0
        }
        """
        title = announcement.get('title', '').lower()
        content = announcement.get('desc', '').lower()
        text = f"{title} {content}"

        # 1. 检查是否包含新币上线关键词
        if not self._contains_listing_keywords(text):
            return None

        # 2. 提取币种代码
        coin_symbol = self._extract_coin_symbol(announcement['title'])
        if not coin_symbol:
            return None

        # 3. 判断上线类型
        listing_type = self._determine_listing_type(text)

        # 4. 计算置信度
        confidence = self._calculate_confidence(text, coin_symbol)

        return {
            'is_listing': True,
            'coin_symbol': coin_symbol,
            'coin_name': '',  # 可选:通过CoinGecko API查询
            'listing_type': listing_type,
            'confidence': confidence
        }

    def _contains_listing_keywords(self, text: str) -> bool:
        """检查是否包含新币上线关键词"""
        return any(keyword in text for keyword in self.LISTING_KEYWORDS)

    def _extract_coin_symbol(self, title: str) -> Optional[str]:
        """
        从标题提取币种代码
        示例:
        - "Binance Will List Pepe (PEPE)" -> "PEPE"
        - "OKX Lists TRUMP Token" -> "TRUMP"
        """
        # 优先提取括号内的代码
        match = re.search(r'\(([A-Z][A-Z0-9]{0,9})\)', title)
        if match:
            return match.group(1)

        # 否则提取第一个大写词
        match = self.COIN_PATTERN.search(title)
        if match:
            symbol = match.group(1)
            # 过滤常见干扰词
            if symbol not in ['USDT', 'USD', 'BTC', 'ETH', 'BNB', 'NEW', 'SPOT']:
                return symbol

        return None

    def _determine_listing_type(self, text: str) -> str:
        """判断上线类型"""
        has_spot = any(kw in text for kw in self.SPOT_KEYWORDS)
        has_futures = any(kw in text for kw in self.FUTURES_KEYWORDS)

        if has_spot and has_futures:
            return 'both'
        elif has_futures:
            return 'futures'
        else:
            return 'spot'  # 默认现货

    def _calculate_confidence(self, text: str, coin_symbol: str) -> float:
        """
        计算识别置信度

        规则:
        - 标题包含"listing" + 币种代码: 0.95
        - 标题包含"list" + 币种代码: 0.90
        - 仅内容包含: 0.70
        - 其他: 0.60
        """
        if 'listing' in text and coin_symbol.lower() in text:
            return 0.95
        elif 'list' in text and coin_symbol.lower() in text:
            return 0.90
        elif coin_symbol.lower() in text:
            return 0.70
        else:
            return 0.60
```

**适用场景**: 本项目(初期快速实现,准确率可接受)

---

#### 方案B: 机器学习分类器(NLP)

**描述**: 训练文本分类模型(如BERT、GPT)识别新币上线。

**优点**:
- 准确率可能更高
- 自动学习模式,无需人工规则
- 对新格式自适应

**缺点**:
- 需要大量标注数据
- 训练和部署复杂
- 推理成本高(时间、资源)
- 不可解释

**适用场景**: 大规模系统,准确率要求>95%

---

#### 方案C: 大语言模型API(如OpenAI GPT)

**描述**: 调用GPT API进行语义理解。

**优点**:
- 准确率极高
- 无需训练

**缺点**:
- 成本高(每次调用收费)
- 延迟高(网络请求)
- 依赖外部服务

**适用场景**: 对准确率要求极高且预算充足

---

### 推荐方案: 关键词匹配 + 正则表达式

**理由**:
1. 满足"简单至上"原则
2. 准确率可达90%+(根据Binance/Bybit公告格式特点)
3. 无需外部依赖,响应速度快
4. 易于调试和优化
5. 未来可升级到ML方案

**优化策略**:
- 维护关键词配置文件(YAML),便于更新
- 记录低置信度识别结果,供人工审核
- 定期分析误识别案例,改进规则

---

## 7. 错误重试与退避策略

### 需求分析

处理三类错误:
1. **网络错误**: 交易所API限流、超时
2. **通知错误**: Telegram发送失败
3. **数据库错误**: 连接失败、写入失败

### 指数退避策略

**描述**: 每次失败后等待时间翻倍,直到达到最大等待时间。

**公式**: `等待时间 = min(基础等待 * 2^尝试次数, 最大等待)`

**实现**:

```python
# listing_monitor/retry.py
import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def exponential_backoff(
    max_retries=3,
    base_delay=60,      # 基础等待60秒
    max_delay=1800,     # 最大等待30分钟
    exceptions=(Exception,)
):
    """
    指数退避装饰器

    示例:
    - 第1次失败: 等待60秒
    - 第2次失败: 等待120秒
    - 第3次失败: 等待240秒
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries - 1:
                        logger.error(f"{func.__name__}最终失败: {e}")
                        raise

                    wait_time = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(
                        f"{func.__name__}失败(尝试{attempt+1}/{max_retries}), "
                        f"等待{wait_time}秒后重试: {e}"
                    )
                    time.sleep(wait_time)

        return wrapper
    return decorator

# 使用示例
@exponential_backoff(max_retries=3, base_delay=60)
def fetch_exchange_announcements(exchange_name):
    """获取交易所公告(带重试)"""
    # 调用Scrapy爬虫
    pass
```

### 交易所监控暂停机制

**规则**: 连续失败3次后,暂停该交易所监控1小时,之后自动恢复。

**实现**:

```python
# listing_monitor/exchange_monitor.py
from datetime import datetime, timedelta

class ExchangeMonitor:
    def __init__(self):
        self.failure_counts = {}      # {exchange: count}
        self.pause_until = {}          # {exchange: datetime}

    def should_monitor(self, exchange):
        """检查是否应该监控该交易所"""
        if exchange in self.pause_until:
            if datetime.now() < self.pause_until[exchange]:
                return False
            else:
                # 恢复监控
                del self.pause_until[exchange]
                self.failure_counts[exchange] = 0

        return True

    def record_success(self, exchange):
        """记录成功"""
        self.failure_counts[exchange] = 0

    def record_failure(self, exchange):
        """记录失败"""
        self.failure_counts[exchange] = self.failure_counts.get(exchange, 0) + 1

        if self.failure_counts[exchange] >= 3:
            # 暂停1小时
            self.pause_until[exchange] = datetime.now() + timedelta(hours=1)
            logger.warning(f"{exchange}连续失败3次,暂停监控1小时")
```

---

## 8. 配置管理方案

### 需求分析

需要配置:
- 监控参数(间隔、交易所列表)
- 数据库连接
- Webhook URL
- 识别关键词
- 日志级别

### 方案对比

#### 方案A: Django settings.py + 环境变量 (推荐)

**描述**: 使用Django的settings.py存储配置,敏感信息通过环境变量覆盖。

**优点**:
- Django标准配置方式
- 支持环境变量覆盖
- 类型安全(Python代码)
- 可以使用django-environ简化环境变量管理
- 适配Docker/K8s部署

**缺点**:
- 配置分散在多个文件中

**配置示例**:

```python
# listing_monitor_project/settings.py
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Django基础配置
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# 数据库配置
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Celery配置
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_BEAT_SCHEDULE = {
    'monitor-every-5-minutes': {
        'task': 'monitor.tasks.monitor_job',
        'schedule': float(os.getenv('MONITOR_INTERVAL', '300')),
    },
}

# Webhook配置
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://your-domain.com/api/webhook/listing')
WEBHOOK_MAX_RETRIES = int(os.getenv('WEBHOOK_MAX_RETRIES', '3'))
WEBHOOK_RETRY_DELAY = int(os.getenv('WEBHOOK_RETRY_DELAY', '60'))

# 监控配置
ENABLED_EXCHANGES = os.getenv('ENABLED_EXCHANGES', 'binance,bybit,bitget').split(',')
CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD', '0.7'))

# 日志配置
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'listing_monitor.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'monitor': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
        },
    },
}
```

**环境变量文件** (.env):
```bash
SECRET_KEY=your-secret-key-here
DEBUG=False
WEBHOOK_URL=https://your-domain.com/api/webhook/listing
CELERY_BROKER_URL=redis://localhost:6379/0
MONITOR_INTERVAL=300
ENABLED_EXCHANGES=binance,bybit,bitget
```

**适用场景**: 本项目(Django标准配置)

---

#### 方案B: 纯环境变量

**优点**:
- 无需文件,12-Factor App最佳实践
- 天然支持容器化

**缺点**:
- 配置分散,难以管理
- 复杂配置(如列表、字典)难以表达

**适用场景**: 极简部署,配置项少

---

#### 方案C: Python配置文件

**优点**:
- 可执行Python代码(动态配置)

**缺点**:
- 安全风险(代码注入)
- 不适合非开发人员修改

**适用场景**: 高级用户,需要动态配置

---

### 推荐方案: Django settings.py + 环境变量

**理由**:
1. Django标准配置方式 - 符合Django最佳实践
2. 类型安全 - Python代码,IDE支持自动补全
3. 环境变量支持 - 敏感信息保护
4. 部署友好 - 适配Docker/K8s部署
5. 可扩展性强 - 可使用django-environ等工具增强

---

## 9. 推荐技术栈总结

| 组件 | 推荐方案 | 备选方案 | 理由 |
|------|---------|---------|------|
| **HTTP框架** | Django + DRF | FastAPI, Flask | 功能完整、Admin管理后台、与Celery集成成熟 |
| **任务队列** | Celery + Django Celery Beat | APScheduler, Cron | 分布式支持、功能强大、生产验证 |
| **消息代理** | Redis 7.0+ | RabbitMQ | 部署简单、性能优秀、支持Celery |
| **ORM/数据库** | Django ORM + SQLite/PostgreSQL | SQLAlchemy | 与Django集成、Admin支持、迁移管理 |
| **通知方案** | requests + Webhook | Telegram Bot | 符合用户要求、集成灵活、实现简单 |
| **识别算法** | 关键词匹配 + 正则 | ML分类器, GPT API | 简单快速、准确率可接受、易维护 |
| **错误重试** | 指数退避 + 暂停机制 | - | 标准实践,保护交易所API |
| **配置管理** | Django settings + 环境变量 | YAML | Django标准、类型安全、环境变量支持 |
| **API文档** | DRF Browsable API + drf-yasg | 手动编写 | 自动生成Swagger文档 |
| **WSGI服务器** | Gunicorn + Uvicorn Workers | uWSGI | 性能优秀、部署简单 |
| **日志** | Django logging + RotatingFileHandler | - | Django内置,成熟可靠 |
| **测试** | pytest + pytest-django | unittest | 社区标准,插件丰富 |
| **Admin界面** | Django Admin | 自建 | 开箱即用,便于数据审核 |

---

## 附录: 依赖清单

```txt
# requirements.txt (更新后的完整依赖)

# Django Web框架
Django==4.2.7
djangorestframework==3.14.0

# Celery任务队列
celery==5.3.4
django-celery-beat==2.5.0
redis==5.0.1

# 数据库
# SQLite (默认,无需额外安装)
# PostgreSQL (生产环境可选)
# psycopg2-binary==2.9.9

# HTTP请求
requests==2.31.0

# API文档
drf-yasg==1.21.7

# 环境变量管理
python-dotenv==1.0.0
django-environ==0.11.2

# 现有爬虫依赖(已有)
Scrapy==2.11.0

# CORS支持
django-cors-headers==4.3.1

# 开发/测试依赖
pytest==7.4.3
pytest-django==4.7.0
pytest-mock==3.12.0
pytest-cov==4.1.0
black==23.12.1
flake8==6.1.0
```

---

## 下一步

1. ✓ 根据本研究文档确定最终技术方案 - **已完成: Django + Celery混合架构**
2. 编写数据模型设计文档(data-model.md)
3. 定义API端点契约(contracts/api-endpoints.md)
4. 编写快速开始指南(quickstart.md)
5. 开始Phase 2实现
