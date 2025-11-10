# 加密货币新币上线监控系统 - Phase 1

## 🚀 快速开始

### 1. 初始化（首次运行）

```bash
# 初始化交易所数据
python manage.py init_exchanges
```

### 2. 一键监控（推荐）

```bash
# 方式1: Shell脚本
./scripts/monitor.sh 24              # 监控最近24小时

# 方式2: Python命令
python manage.py monitor --hours 24  # 完整流程：获取→识别→通知
```

> 💡 **默认监控的交易所**：Binance、Bybit、Bitget、Hyperliquid
>
> 如需指定交易所：`python manage.py monitor --hours 24 --exchanges "binance,bybit"`

### 3. 分步执行

```bash
# 步骤1: 获取公告
./scripts/fetch_announcements.sh 24
# 或
python manage.py fetch_all_announcements --hours 24

# 步骤2: 识别新币
python manage.py identify_listings --show-details

# 步骤3: 测试通知（需要webhook URL）
python manage.py test_webhook --url YOUR_WEBHOOK_URL --test-only
```

---

## 📋 所有可用命令

| 命令 | 功能 | 示例 |
|------|------|------|
| `monitor` | **一键监控**（获取→识别→通知） | `python manage.py monitor --hours 24` |
| `fetch_all_announcements` | 批量获取所有交易所 | `python manage.py fetch_all_announcements --hours 24` |
| `fetch_announcements` | 获取单个交易所 | `python manage.py fetch_announcements --exchange binance --hours 24` |
| `identify_listings` | 识别新币上线 | `python manage.py identify_listings --show-details` |
| `test_webhook` | 测试Webhook通知 | `python manage.py test_webhook --url URL` |
| `init_exchanges` | 初始化交易所 | `python manage.py init_exchanges` |

---

## ⚙️ 配置

### 支持的交易所

- ✅ Binance (币安)
- ✅ Bybit
- ✅ Bitget
- ✅ Hyperliquid

### 通知配置

系统支持两种通知方式：

#### 1. 慧诚告警推送（默认）

**无需配置，开箱即用**

系统默认使用慧诚告警推送服务，当识别到新币上线时自动推送。

```bash
# 直接运行，自动使用告警推送
python manage.py monitor --hours 24
```

**测试推送服务**：
```bash
# 测试推送连接
python manage.py test_push

# 测试推送指定新币
python manage.py test_listing_push --listing-id <ID>
```

#### 2. 自定义Webhook（可选）

如果需要使用自定义Webhook，可通过以下方式配置：

**方式1: 环境变量**
```bash
export WEBHOOK_URL="https://your-webhook-url.com"
python manage.py monitor --hours 24
```

**方式2: 命令参数**
```bash
python manage.py monitor --hours 24 --webhook-url "https://your-webhook-url.com"
```

**跳过通知**：
```bash
python manage.py monitor --hours 24 --skip-notification
```

### 定时任务设置

```bash
# 编辑crontab
crontab -e

# 每小时运行一次（推荐）
0 * * * * cd /path/to/project && ./scripts/monitor.sh 2 >> logs/monitor.log 2>&1

# 每15分钟运行一次（高频）
*/15 * * * * cd /path/to/project && ./scripts/monitor.sh 0.5 >> logs/monitor.log 2>&1
```

### Django Admin 管理后台

系统提供了完整的 Django Admin 管理界面，方便手动管理数据。

**启动步骤**：

```bash
# 1. 创建超级用户（首次使用）
python manage.py createsuperuser

# 2. 启动开发服务器
python manage.py runserver

# 3. 访问 http://127.0.0.1:8000/admin/
```

**管理功能**：
- 📊 **交易所管理**：启用/禁用交易所，查看公告统计
- 📰 **公告管理**：查看、搜索、过滤公告，标记处理状态
- 🪙 **新币管理**：确认上线、审核新币、查看置信度
- 📨 **通知记录**：查看推送历史、重试记录

详细使用指南：[docs/DJANGO_ADMIN_GUIDE.md](docs/DJANGO_ADMIN_GUIDE.md)

---

## 📊 查看数据

### SQL查询

```bash
# 查看公告统计
sqlite3 db.sqlite3 "SELECT e.name, COUNT(a.id) FROM announcements a JOIN exchanges e ON a.exchange_id = e.id GROUP BY e.name;"

# 查看识别出的新币
sqlite3 db.sqlite3 "SELECT coin_symbol, listing_type, confidence, status FROM listings ORDER BY identified_at DESC LIMIT 10;"

# 查看最新公告
sqlite3 db.sqlite3 "SELECT title, datetime(announced_at, 'localtime') FROM announcements ORDER BY announced_at DESC LIMIT 5;"
```

### Management Command

```bash
# 查看识别结果（带详情）
python manage.py identify_listings --show-details
```

---

## 🎯 典型使用场景

### 场景1: 每日检查

```bash
# 早上运行一次，获取过去24小时的新币上线
./scripts/monitor.sh 24
```

### 场景2: 实时监控

```bash
# 每15分钟运行，只获取最近30分钟的公告
# Crontab: */15 * * * * ./scripts/monitor.sh 0.5
```

### 场景3: 手动测试

```bash
# 只获取，不识别
python manage.py fetch_all_announcements --hours 1

# 只识别已获取的公告
python manage.py identify_listings

# 完整流程但跳过通知
python manage.py monitor --hours 24 --skip-notification
```

---

## 📚 文档

- [完整Phase 1报告](docs/PHASE1_REPORT.md) - 详细的开发和测试报告
- [批量获取指南](docs/batch_fetch_guide.md) - 批量获取使用文档
- [快速参考](QUICKSTART.md) - 常用命令速查

---

## 🔧 故障排查

### 问题1: 未获取到公告

**原因**: 时间范围太小或该时间段没有新公告

**解决**:
```bash
# 增大时间范围
python manage.py fetch_all_announcements --hours 48

# 增加页数
python manage.py fetch_all_announcements --hours 24 --max-pages 5
```

### 问题2: Bitget获取失败

**原因**: Bitget使用Playwright爬虫，可能超时或JSON解析错误

**解决**:
```bash
# 暂时跳过Bitget，只获取Binance和Bybit
python manage.py fetch_all_announcements --exchanges "binance,bybit"
```

### 问题3: 脚本无执行权限

```bash
chmod +x scripts/*.sh
```

---

## ✅ 功能特性

- ✅ **智能增量获取**: 按时间范围过滤，避免重复数据
- ✅ **自动去重**: 数据库唯一约束 + 应用层去重
- ✅ **置信度评分**: 自动判断是否需要人工审核
- ✅ **时区感知**: 正确处理所有时间字段
- ✅ **一键监控**: 完整流程自动化
- ✅ **批量处理**: 支持多交易所同时获取
- ✅ **错误容忍**: 单个交易所失败不影响其他

---

## 📈 数据统计

当前已验证功能：
- ✅ 获取公告：17条（Binance 5 + Bybit 12）
- ✅ 识别新币：4个
  - STABLEUSDT (合约) x2
  - DCA (合约)
  - CC (现货)
- ✅ 置信度分布：
  - 已确认（≥0.8）: 2个
  - 待审核（<0.8）: 2个

---

## 🚀 下一步（Phase 2）

Phase 1已完成，等待验收。验收通过后将开发：

- ⏳ Celery自动化任务
- ⏳ Redis消息队列
- ⏳ REST API接口
- ⏳ Django Admin管理界面

---

*最后更新: 2025-11-07*
*版本: Phase 1 Final*
