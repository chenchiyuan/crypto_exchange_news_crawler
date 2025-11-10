# 告警推送服务集成文档

## 概述

本系统集成了慧诚告警推送服务，用于在识别到新币上线时自动发送告警通知。

## 推送服务配置

### 默认配置

系统已内置推送服务配置，**无需额外设置**即可使用：

- **API URL**: `https://huicheng.powerby.com.cn/api/simple/alert/`
- **Token**: `6020867bc6334c609d4f348c22f90f14`
- **Channel**: `coin`

### 使用方式

#### 1. 自动推送（监控命令）

运行监控命令时，系统会自动使用告警推送服务：

```bash
# 默认使用告警推送
python manage.py monitor --hours 24

# 或使用脚本
./scripts/monitor.sh 24
```

#### 2. 手动推送（测试命令）

**测试推送连接**：
```bash
python manage.py test_push
```

输出示例：
```
======================================================================
🧪 测试告警推送服务
======================================================================

推送服务配置:
  API URL: https://huicheng.powerby.com.cn/api/simple/alert/
  Channel: coin
  Token: 6020867bc6...

正在发送测试消息...

✅ 推送服务测试成功！
```

**推送指定新币**：
```bash
# 查看可推送的新币列表
python manage.py test_listing_push

# 推送指定ID的新币
python manage.py test_listing_push --listing-id 43
```

## 推送消息格式

### 标题格式

```
🚀 {交易所名称} 新币上线 - {币种符号} ({上线类型})
```

示例：
- `🚀 Hyperliquid 新币上线 - MET (现货)`
- `🚀 Bybit 新币上线 - STABLEUSDT (合约)`

### 内容格式

```
币种: {coin_symbol}
名称: {coin_name}
类型: {listing_type}
交易所: {exchange_name} ({exchange_code})
置信度: {confidence}

公告标题: {announcement_title}
发布时间: {announced_at}

公告链接: {announcement_url}
```

示例：
```
币种: MET
类型: 现货
交易所: Hyperliquid (hyperliquid)
置信度: 95%

公告标题: New listing: MET-USD hyperps
发布时间: 2025-10-10 11:00

公告链接: https://app.hyperliquid.xyz/announcements?uuid=f5yl4qrhuxq
```

## API 接口说明

### 请求格式

```http
POST https://huicheng.powerby.com.cn/api/simple/alert/
Content-Type: application/json

{
  "token": "6020867bc6334c609d4f348c22f90f14",
  "title": "告警标题",
  "content": "告警内容\n支持多行文本",
  "channel": "coin"
}
```

### 响应格式

成功时：
```json
{
  "errcode": 0,
  "msg": "success"
}
```

失败时：
```json
{
  "errcode": 非0值,
  "msg": "错误描述"
}
```

## 服务类使用

如需在代码中直接使用推送服务：

```python
from monitor.services.notifier import AlertPushService
from monitor.models import Listing

# 创建推送服务实例
push_service = AlertPushService()

# 测试连接
if push_service.test_push():
    print("推送服务正常")

# 推送单个新币
listing = Listing.objects.get(id=43)
success = push_service.send_notification(listing, create_record=True)

# 批量推送
listings = Listing.objects.filter(status=Listing.CONFIRMED)
stats = push_service.send_batch_notifications(listings)
print(f"成功: {stats['success']}, 失败: {stats['failed']}")
```

## 与Webhook的区别

| 特性 | 告警推送（默认） | Webhook（可选） |
|------|----------------|----------------|
| 配置 | 无需配置 | 需要提供URL |
| 使用 | 开箱即用 | 需额外开发接收端 |
| 消息格式 | 固定格式，易读 | JSON格式，灵活 |
| 适用场景 | 一般使用 | 需要自定义处理 |

## 切换到Webhook模式

如果需要使用自定义Webhook而不是默认的告警推送：

```bash
# 方式1: 环境变量
export WEBHOOK_URL="https://your-webhook-url.com"
python manage.py monitor --hours 24

# 方式2: 命令参数
python manage.py monitor --hours 24 --webhook-url "https://your-webhook-url.com"
```

## 故障排查

### 推送失败

1. **检查网络连接**
```bash
curl -X POST https://huicheng.powerby.com.cn/api/simple/alert/ \
  -H "Content-Type: application/json" \
  -d '{"token":"6020867bc6334c609d4f348c22f90f14","title":"测试","content":"测试","channel":"coin"}'
```

2. **查看日志**
```bash
# Django日志会记录详细错误信息
tail -f logs/django.log
```

3. **验证Token**
- 确认Token未过期
- 确认Channel配置正确

### 常见错误

| errcode | 说明 | 解决方案 |
|---------|------|---------|
| 401 | Token无效 | 检查Token配置 |
| 403 | 权限不足 | 联系管理员 |
| 500 | 服务器错误 | 稍后重试或联系技术支持 |

## 通知记录

所有推送记录都会保存在 `notification_records` 表中：

```bash
# 查看推送记录
sqlite3 db.sqlite3 "SELECT * FROM notification_records ORDER BY created_at DESC LIMIT 10;"

# 查看推送统计
sqlite3 db.sqlite3 "SELECT status, COUNT(*) FROM notification_records GROUP BY status;"
```

## 最佳实践

1. **生产环境**：使用cron定时运行监控脚本
2. **测试环境**：使用 `--skip-notification` 跳过推送
3. **调试时**：使用 `test_listing_push` 单独测试推送
4. **监控健康**：定期使用 `test_push` 检查服务状态
