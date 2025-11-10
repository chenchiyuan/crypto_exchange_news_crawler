# API端点契约文档

**项目**: 加密货币交易所新币上线监控系统
**创建日期**: 2025-11-06
**状态**: 设计完成
**架构模式**: Django + Celery混合架构

## 目录

1. [API概览](#1-api概览)
2. [认证与授权](#2-认证与授权)
3. [监控管理API](#3-监控管理api)
4. [新币上线API](#4-新币上线api)
5. [审核管理API](#5-审核管理api)
6. [交易所管理API](#6-交易所管理api)
7. [配置管理API](#7-配置管理api)
8. [统计信息API](#8-统计信息api)
9. [数据模型定义](#9-数据模型定义)
10. [错误响应规范](#10-错误响应规范)
11. [API使用示例](#11-api使用示例)

---

## 1. API概览

### 基础信息

- **Base URL**: `http://localhost:8000/api`
- **协议**: HTTP/1.1
- **数据格式**: JSON
- **字符编码**: UTF-8
- **API文档**: `http://localhost:8000/api/docs/` (drf-yasg Swagger UI)
- **Django Admin**: `http://localhost:8000/admin/` (管理后台)
- **OpenAPI规范**: `http://localhost:8000/api/swagger.json`

### 端点列表

| 分类 | 方法 | 路径 | 描述 | 优先级 |
|------|------|------|------|--------|
| **监控管理** | POST | `/monitor/trigger` | 手动触发监控任务 | P0 |
| | GET | `/monitor/status` | 查询监控状态 | P0 |
| | PUT | `/monitor/schedule` | 更新监控调度 | P1 |
| **新币上线** | GET | `/listings` | 查询新币上线列表 | P0 |
| | GET | `/listings/{id}` | 查询新币详情 | P1 |
| | GET | `/listings/stats` | 新币统计信息 | P2 |
| **审核管理** | GET | `/review/pending` | 待审核列表 | P1 |
| | PUT | `/review/{id}` | 审核新币上线 | P1 |
| | POST | `/review/batch` | 批量审核 | P2 |
| **交易所** | GET | `/exchanges` | 查询交易所列表 | P1 |
| | PUT | `/exchanges/{id}` | 更新交易所配置 | P1 |
| **配置** | GET | `/config` | 查询配置 | P1 |
| | PUT | `/config` | 更新配置 | P1 |
| **统计** | GET | `/stats/overview` | 总体统计 | P2 |
| | GET | `/stats/exchanges` | 交易所统计 | P2 |
| **Django Admin** | GET | `/admin/` | 管理后台入口 | P0 |
| | GET | `/admin/monitor/listing/` | 新币上线管理 | P0 |
| | GET | `/admin/monitor/announcement/` | 公告管理 | P1 |

---

## 2. 认证与授权

### 方案A: API Key认证(推荐)

**请求头**:
```
X-API-Key: your_api_key_here
```

**示例**:
```bash
curl -H "X-API-Key: sk_12345abcde" http://localhost:8000/api/monitor/status
```

### 方案B: Bearer Token(可选)

**请求头**:
```
Authorization: Bearer your_token_here
```

**注**: 初期可暂不实现认证,后续根据需求添加。

---

## 3. 监控管理API

### 3.1 `POST /api/monitor/trigger`

**功能**: 手动触发监控任务

**请求**:
```http
POST /api/monitor/trigger HTTP/1.1
Content-Type: application/json

{
  "exchanges": ["binance", "bybit"],  // 可选,指定交易所
  "force": false                       // 可选,是否强制执行(忽略暂停状态)
}
```

**响应**(成功):
```json
{
  "status": "success",
  "message": "监控任务已触发",
  "task_id": "task_20251106_100000",
  "timestamp": "2025-11-06T10:00:00Z"
}
```

**响应**(已有任务运行):
```json
{
  "status": "skipped",
  "message": "监控任务正在运行中",
  "running_task_id": "task_20251106_095500"
}
```

---

### 3.2 `GET /api/monitor/status`

**功能**: 查询监控状态

**请求**:
```http
GET /api/monitor/status HTTP/1.1
```

**响应**:
```json
{
  "running": true,
  "uptime_seconds": 3600,
  "last_run": {
    "task_id": "task_20251106_095500",
    "started_at": "2025-11-06T09:55:00Z",
    "completed_at": "2025-11-06T09:55:15Z",
    "duration_seconds": 15,
    "status": "completed",
    "results": {
      "total_announcements": 150,
      "new_listings": 2,
      "notifications_sent": 2
    }
  },
  "next_run": "2025-11-06T10:00:00Z",
  "schedule": {
    "interval_seconds": 300,
    "enabled": true
  },
  "exchanges": [
    {
      "code": "binance",
      "name": "Binance",
      "enabled": true,
      "status": "normal",
      "last_success": "2025-11-06T09:55:05Z",
      "failure_count": 0
    }
  ]
}
```

---

## 4. 新币上线API

### 4.1 `GET /api/listings`

**功能**: 查询新币上线列表

**请求**:
```http
GET /api/listings?status=confirmed&exchange=binance&limit=20&offset=0 HTTP/1.1
```

**查询参数**:

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `status` | string | 否 | - | 过滤状态(pending_review/confirmed/ignored) |
| `exchange` | string | 否 | - | 过滤交易所代码 |
| `listing_type` | string | 否 | - | 过滤上线类型(spot/futures/both) |
| `coin_symbol` | string | 否 | - | 过滤币种代码 |
| `limit` | integer | 否 | 20 | 每页数量(1-100) |
| `offset` | integer | 否 | 0 | 偏移量 |

**响应**:
```json
{
  "total": 150,
  "limit": 20,
  "offset": 0,
  "items": [
    {
      "id": 1,
      "coin_symbol": "PEPE",
      "coin_name": "Pepe Coin",
      "listing_type": "spot",
      "exchange": {
        "code": "binance",
        "name": "Binance"
      },
      "announcement": {
        "title": "Binance Will List Pepe (PEPE)",
        "url": "https://www.binance.com/en/support/announcement/12345",
        "announced_at": "2025-11-06T09:00:00Z"
      },
      "confidence": 0.95,
      "status": "confirmed",
      "identified_at": "2025-11-06T09:05:00Z",
      "created_at": "2025-11-06T09:05:05Z"
    }
  ]
}
```

---

## 5. 审核管理API

### 5.1 `GET /api/review/pending`

**功能**: 查询待审核列表

**请求**:
```http
GET /api/review/pending?limit=20 HTTP/1.1
```

**响应**:
```json
{
  "total": 5,
  "items": [
    {
      "id": 10,
      "coin_symbol": "TRUMP",
      "listing_type": "futures",
      "exchange": {
        "code": "bybit",
        "name": "Bybit"
      },
      "announcement": {
        "title": "New Futures Listing",
        "url": "https://www.bybit.com/announcement/123"
      },
      "confidence": 0.65,
      "identified_at": "2025-11-06T09:05:00Z"
    }
  ]
}
```

---

### 5.2 `PUT /api/review/{id}`

**功能**: 审核新币上线

**请求**:
```http
PUT /api/review/1 HTTP/1.1
Content-Type: application/json

{
  "action": "confirm",  // confirm / ignore
  "send_notification": true
}
```

**响应**:
```json
{
  "status": "success",
  "message": "新币上线已确认",
  "listing": {
    "id": 1,
    "coin_symbol": "PEPE",
    "status": "confirmed",
    "notification_sent": true
  }
}
```

---

## 6. 交易所管理API

### 6.1 `GET /api/exchanges`

**功能**: 查询交易所列表

**响应**:
```json
{
  "items": [
    {
      "id": 1,
      "code": "binance",
      "name": "Binance",
      "enabled": true,
      "created_at": "2025-11-06T08:00:00Z"
    }
  ]
}
```

---

## 7. 配置管理API

### 7.1 `GET /api/config`

**功能**: 查询配置

**响应**:
```json
{
  "monitor": {
    "interval": 300,
    "run_immediately": true
  },
  "telegram": {
    "enabled": true
  }
}
```

---

## 8. 统计信息API

### 8.1 `GET /api/stats/overview`

**功能**: 总体统计

**响应**:
```json
{
  "period": {
    "days": 7
  },
  "listings": {
    "total": 15,
    "confirmed": 12
  },
  "notifications": {
    "sent": 12,
    "success_rate": 1.0
  }
}
```

---

## 9. 数据模型定义

### ListingResponse

```typescript
{
  id: integer,
  coin_symbol: string,
  coin_name?: string,
  listing_type: "spot" | "futures" | "both",
  exchange: {
    code: string,
    name: string
  },
  confidence: float,
  status: "pending_review" | "confirmed" | "ignored",
  identified_at: string
}
```

---

## 10. 错误响应规范

### 标准错误格式

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "错误描述"
  }
}
```

### HTTP状态码

| 状态码 | 说明 |
|--------|------|
| 200 OK | 成功 |
| 400 Bad Request | 参数错误 |
| 404 Not Found | 资源不存在 |
| 500 Internal Server Error | 服务器错误 |

---

## 11. API使用示例

### Python客户端示例 (使用requests)

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

# 审核
payload = {"action": "confirm", "send_notification": True}
response = requests.put(f"{base_url}/review/1", json=payload)
review = response.json()
print(review)
```

### Django管理后台使用

```
1. 访问 http://localhost:8000/admin/
2. 使用超级用户登录
3. 管理模型:
   - 交易所 (Exchanges)
   - 公告 (Announcements)
   - 新币上线 (Listings)
   - 通知记录 (Notification Records)
```

---

## 总结

本API端点契约定义了:
1. **RESTful API设计**: 符合REST规范,使用Django REST Framework实现
2. **清晰的数据模型**: 请求和响应结构明确
3. **完整的错误处理**: 统一的错误格式
4. **易于使用**: 提供客户端示例
5. **Admin管理界面**: Django Admin提供强大的数据管理功能

下一步将基于此契约实现Django REST Framework服务。
