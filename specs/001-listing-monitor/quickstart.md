# 快速开始指南

**项目**: 加密货币交易所新币上线监控系统
**创建日期**: 2025-11-06
**更新日期**: 2025-11-06
**架构模式**: Django + Celery混合架构

## 目录

1. [系统要求](#1-系统要求)
2. [安装步骤](#2-安装步骤)
3. [配置说明](#3-配置说明)
4. [启动服务](#4-启动服务)
5. [API使用](#5-api使用)
6. [验证运行](#6-验证运行)
7. [常见问题](#7-常见问题)
8. [下一步](#8-下一步)

---

## 1. 系统要求

### 硬件要求

- **CPU**: 1核心以上
- **内存**: 512MB以上(推荐1GB)
- **磁盘**: 1GB可用空间(用于日志和数据库)
- **网络**: 稳定的互联网连接

### 软件要求

- **操作系统**: Linux / macOS / Windows
- **Python**: 3.8或更高版本(推荐3.9+)
- **pip**: 最新版本
- **Redis**: 7.0+ (Celery消息代理)
- **可选**: PostgreSQL 14+(生产环境推荐)

### 外部依赖

- **Webhook接收端点**: 用户需提供Webhook URL接收新币上线通知

---

## 2. 安装步骤

### 2.1 克隆或下载项目

```bash
# 如果使用Git
git clone https://github.com/your-repo/crypto_exchange_news_crawler.git
cd crypto_exchange_news_crawler

# 或下载ZIP包后解压
unzip crypto_exchange_news_crawler.zip
cd crypto_exchange_news_crawler
```

### 2.2 创建虚拟环境(推荐)

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
# Linux/macOS:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

### 2.3 安装依赖

```bash
# 安装现有爬虫依赖
pip install -r requirements.txt

# 或安装包含监控系统的完整依赖(已合并到requirements.txt)
# requirements.txt已包含Django、Celery、Redis等依赖
```

**依赖清单**(requirements.txt中新增部分):
```txt
# Django Web框架
Django==4.2.7
djangorestframework==3.14.0

# Celery任务队列
celery==5.3.4
django-celery-beat==2.5.0
redis==5.0.1

# HTTP请求
requests==2.31.0

# API文档
drf-yasg==1.21.7

# 环境变量管理
python-dotenv==1.0.0
django-environ==0.11.2

# CORS支持
django-cors-headers==4.3.1

# 测试
pytest==7.4.3
pytest-django==4.7.0
pytest-mock==3.12.0
```

### 2.4 验证安装

```bash
# 验证Django安装
python -c "import django; print(django.__version__)"

# 验证Celery安装
python -c "import celery; print(celery.__version__)"

# 验证Redis连接(需要Redis服务运行)
python -c "import redis; r=redis.Redis(); r.ping()"
```

---

## 3. 配置说明

### 3.1 创建Django配置

```bash
# Django配置主要在listing_monitor_project/settings.py中
# 环境变量在.env文件中配置
cp .env.example .env

# 编辑环境变量
vim .env  # 或使用你喜欢的编辑器
```

### 3.2 配置Webhook URL

用户需要提供Webhook URL接收新币上线通知。

#### 步骤1: 准备Webhook接收端点

确保你有一个可接收POST请求的Web端点:
```
POST https://your-domain.com/api/webhook/listing
Content-Type: application/json

{
  "event": "new_listing",
  "data": {
    "coin_symbol": "BTC",
    "exchange": {"code": "binance", "name": "Binance"},
    ...
  }
}
```

#### 步骤2: 配置环境变量

```bash
# .env文件内容
SECRET_KEY=your-django-secret-key-here
DEBUG=True
WEBHOOK_URL=https://your-domain.com/api/webhook/listing
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
ENABLED_EXCHANGES=binance,bybit,bitget
```

#### 步骤3: 测试Webhook (可选)

使用webhook.site等在线工具测试:
```bash
# 临时测试URL
WEBHOOK_URL=https://webhook.site/your-unique-id
```

### 3.3 Django Settings配置详解

**最小配置示例** (listing_monitor_project/settings.py):
```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# 基础配置
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# 数据库(SQLite)
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
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
WEBHOOK_MAX_RETRIES = int(os.getenv('WEBHOOK_MAX_RETRIES', '3'))
WEBHOOK_RETRY_DELAY = int(os.getenv('WEBHOOK_RETRY_DELAY', '60'))

# 监控配置
ENABLED_EXCHANGES = os.getenv('ENABLED_EXCHANGES', 'binance,bybit,bitget').split(',')
CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD', '0.7'))
```

**完整配置示例** (listing_monitor_project/settings.py):
见项目源码中的settings.py文件。

### 3.4 Redis安装(必需)

**macOS**:
```bash
brew install redis
brew services start redis
```

**Ubuntu/Debian**:
```bash
sudo apt-get install redis-server
sudo systemctl start redis
sudo systemctl enable redis
```

**验证Redis运行**:
```bash
redis-cli ping
# 应返回: PONG
```

---

## 4. 启动服务

### 4.1 初始化数据库

```bash
# 创建数据库迁移
python manage.py makemigrations

# 应用迁移
python manage.py migrate

# 创建超级用户(用于Django Admin)
python manage.py createsuperuser

# 初始化交易所数据
python manage.py init_db

# 预期输出:
# 正在初始化数据库...
# 应用数据库迁移...
# 初始化交易所数据...
#   创建交易所: Binance
#   创建交易所: Bybit
#   创建交易所: Bitget
#   创易所已存在: Hyperliquid
# 数据库初始化完成!
```

### 4.2 启动Redis (必需)

```bash
# macOS
brew services start redis

# Linux
sudo systemctl start redis

# 或手动启动
redis-server
```

### 4.3 启动Django服务

#### 方式A: 开发模式(推荐用于测试)

```bash
# 启动Django开发服务器
python manage.py runserver 0.0.0.0:8000

# 预期输出:
# Performing system checks...
# System check identified no issues (0 silenced).
# November 06, 2025 - 10:00:00
# Django version 4.2.7, using settings 'listing_monitor_project.settings'
# Starting development server at http://0.0.0.0:8000/
# Quit the server with CONTROL-C.
```

#### 方式B: 生产模式(使用Gunicorn)

```bash
# 使用Gunicorn
gunicorn listing_monitor_project.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --access-logfile - \
  --error-logfile -
```

### 4.4 启动Celery Worker

**新终端窗口**:
```bash
# 启动Celery worker
celery -A listing_monitor_project worker -l info

# 预期输出:
# celery@hostname v5.3.4
# Connected to redis://localhost:6379/0
# [tasks]
#   . monitor.tasks.monitor_job
```

### 4.5 启动Celery Beat (定时任务调度器)

**新终端窗口**:
```bash
# 启动Celery beat
celery -A listing_monitor_project beat -l info

# 预期输出:
# celery beat v5.3.4 is starting.
# Scheduler: django_celery_beat.schedulers:DatabaseScheduler
# [2025-11-06 10:00:00] Celery beat is running
```

**启动总结**:
需要同时运行3个进程:
1. Django服务器 (`python manage.py runserver`)
2. Celery Worker (`celery -A listing_monitor_project worker`)
3. Celery Beat (`celery -A listing_monitor_project beat`)

**使用systemd管理** (Linux生产环境推荐,见下文)

---

## 5. API使用

### 5.1 访问API文档

服务启动后,访问以下URL:

- **Django Admin**: http://localhost:8000/admin/
- **API文档 (Swagger)**: http://localhost:8000/api/docs/
- **DRF Browsable API**: http://localhost:8000/api/
- **OpenAPI Schema**: http://localhost:8000/api/swagger.json

### 5.2 基本API调用

```bash
# 1. 查询监控状态
curl http://localhost:8000/api/monitor/status

# 2. 手动触发监控
curl -X POST http://localhost:8000/api/monitor/trigger \
  -H "Content-Type: application/json"

# 3. 查询新币上线列表
curl "http://localhost:8000/api/listings?limit=10&status=confirmed"

# 4. 查询待审核列表
curl http://localhost:8000/api/review/pending

# 5. 审核新币上线
curl -X PUT http://localhost:8000/api/review/1 \
  -H "Content-Type: application/json" \
  -d '{"action": "confirm", "send_notification": true}'
```

### 5.3 Python客户端示例

```python
import requests

base_url = "http://localhost:8000/api"

# 查询状态
response = requests.get(f"{base_url}/monitor/status")
status = response.json()
print(status)

# 触发监控
response = requests.post(f"{base_url}/monitor/trigger")
result = response.json()
print(result)

# 查询新币
params = {"status": "confirmed", "limit": 10}
response = requests.get(f"{base_url}/listings", params=params)
listings = response.json()
print(listings)
```

### 5.4 使用Django Admin管理数据

```bash
# 1. 创建超级用户(如果还没创建)
python manage.py createsuperuser

# 2. 访问Admin界面
# http://localhost:8000/admin/

# 3. 登录后可以:
#    - 查看和编辑交易所
#    - 查看和审核公告
#    - 管理新币上线记录
#    - 查看通知历史
```

---

## 6. 验证运行

### 6.1 检查HTTP服务

```bash
# 检查服务是否运行
curl http://localhost:8000/api/monitor/status

# 访问API文档
open http://localhost:8000/docs  # macOS
# 或在浏览器中访问 http://localhost:8000/docs
```

### 6.2 检查数据库
listing-monitor status

# 预期输出:
# 监控服务状态: 运行中
# PID: 12345
# 运行时长: 5分钟
# 配置文件: config/config.yaml
# 数据库: sqlite:///listing_monitor.db
#
# 监控交易所:
#   ✓ Binance   (最后监控: 2分钟前, 状态: 正常)
#   ✓ Bybit     (最后监控: 2分钟前, 状态: 正常)
#   ✓ Bitget    (最后监控: 2分钟前, 状态: 正常)
#
# 统计信息(今日):
#   - 识别新币上线: 2个
#   - 发送通知: 2个
#   - 待审核公告: 0个
```

### 6.2 检查数据库

```bash
# 使用Django shell
python manage.py shell

# 在shell中查询
>>> from monitor.models import Exchange, Announcement, Listing
>>> Exchange.objects.all()
>>> Announcement.objects.count()
>>> Listing.objects.filter(status='confirmed')

# 或使用SQLite命令行
sqlite3 db.sqlite3

# 查看交易所
SELECT * FROM exchanges;

# 查看公告数量
SELECT COUNT(*) FROM announcements;

# 查看新币上线
SELECT * FROM listings;

# 退出
.exit
```

### 6.3 检查日志

```bash
# 查看应用日志(如果使用uvicorn)
tail -f logs/app.log

# 查看监控任务日志
tail -f logs/listing_monitor.log
```

### 6.4 测试API端点

```bash
# 手动触发一次监控
curl -X POST http://localhost:8000/api/monitor/trigger

# 查询新币上线
curl http://localhost:8000/api/listings
```

---

## 7. 常见问题

### 7.1 安装问题

**Q: pip install失败,提示"Could not find a version..."**

A: 升级pip并指定镜像源:
```bash
pip install --upgrade pip
pip install -r requirements-monitor.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**Q: psycopg2-binary安装失败**

A: 如果使用SQLite,可以删除这个依赖:
```bash
# 编辑requirements-monitor.txt,删除或注释该行:
# psycopg2-binary==2.9.9
```

### 7.2 配置问题

**Q: 环境变量未生效,显示None**

A: 确保.env文件在项目根目录,并使用python-dotenv加载:
```python
# settings.py中添加
from dotenv import load_dotenv
load_dotenv()
```

或使用django-environ:
```python
import environ
env = environ.Env()
environ.Env.read_env()
```

**Q: Redis连接失败**

A: 检查Redis是否运行:
```bash
# 检查Redis状态
redis-cli ping

# 如果失败,启动Redis
brew services start redis  # macOS
sudo systemctl start redis  # Linux
```

**Q: Webhook通知失败**

A: 检查:
1. WEBHOOK_URL是否正确配置
2. 接收端点是否可访问
3. 查看Celery worker日志获取详细错误

### 7.3 运行问题

**Q: 服务启动失败,提示端口已被占用**

A: 检查8000端口是否被占用:
```bash
# 查看端口占用
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# 杀死占用进程或更换端口
uvicorn listing_monitor.app:app --host 0.0.0.0 --port 8001
```

**Q: Celery任务不执行**

A: 检查:
1. Celery worker和beat是否都在运行
2. Redis连接是否正常
3. 查看Celery日志确认任务是否被调度

```bash
# 检查Celery状态
celery -A listing_monitor_project inspect active
celery -A listing_monitor_project inspect scheduled
```

**Q: 监控运行但没有识别到新币**

A: 正常现象,可能原因:
1. 监控周期内没有新币上线公告
2. 置信度过低,进入待审核列表(使用Django Admin查看)
3. 识别规则需要调整(编辑关键词配置)

### 7.4 性能问题

**Q: 内存占用过高**

A: 可能原因:
1. 日志文件过大 → 配置日志轮转(logging.max_size)
2. 数据库数据过多 → 定期清理历史数据
3. 爬虫页数过多 → 减少 `scrapy.max_page`

**Q: 监控响应时间过长**

A: 优化建议:
1. 减少爬取页数(scrapy.max_page)
2. 增加监控间隔(monitor.interval)
3. 禁用部分交易所监控

---

## 8. 下一步

### 8.1 日常使用

- **访问Django Admin**: http://localhost:8000/admin/
- **查看API文档**: http://localhost:8000/api/docs/
- **查询新币**: `curl http://localhost:8000/api/listings`
- **审核新币**: 通过Django Admin或API端点 `PUT /api/review/{id}`
- **查看统计**: `curl http://localhost:8000/api/stats/overview`

### 8.2 高级功能

- **添加新交易所**: 实现新的Scrapy爬虫,在Django Admin中添加交易所记录
- **自定义通知**: 修改Webhook payload格式
- **扩展API**: 在Django REST Framework中添加新ViewSet

### 8.3 监控和维护

- **日志监控**: 查看Django和Celery日志
- **数据备份**: 定期备份数据库文件 `db.sqlite3`
- **性能监控**: 使用Celery Flower监控任务队列

```bash
# 安装Flower
pip install flower

# 启动Flower
celery -A listing_monitor_project flower

# 访问 http://localhost:5555
```

### 8.4 故障排查

遇到问题时:
1. 查看Django日志: `python manage.py runserver` 控制台输出
2. 查看Celery Worker日志: worker进程控制台输出
3. 查看Celery Beat日志: beat进程控制台输出
4. 检查数据库: `python manage.py dbshell` 或Django Admin
5. 测试API: 访问 http://localhost:8000/api/docs/
6. 查看监控状态: `curl http://localhost:8000/api/monitor/status`

---

## 总结

本快速开始指南涵盖:
1. **系统要求**: 硬件、软件依赖(包括Redis)
2. **安装步骤**: 从环境准备到依赖安装
3. **配置说明**: Django settings和Webhook URL配置
4. **启动服务**: Django、Celery Worker、Celery Beat三个进程
5. **API使用**: 接口调用和Django Admin使用
6. **验证运行**: 服务状态和数据库检查
7. **常见问题**: 安装、配置、运行问题排查

遵循本指南,你可以在30分钟内完成Django + Celery系统部署并通过REST API和Admin管理界面访问监控功能!
