# 🔔 通知服务配置指南

## ✅ 默认配置状态

通知服务已**自动启用**，无需手动配置！

### 默认配置
- **Token**: `6020867bc6334c609d4f348c22f90f14`（系统默认）
- **渠道**: `twitter_analysis`
- **成本告警阈值**: `$5.00`

### 日志确认
运行分析命令时会看到：
```
[INFO] 使用默认通知 token，通知功能已启用（可配置 ALERT_PUSH_TOKEN 覆盖）
[INFO] [Task xxx] 发送完成通知
```

## 📱 接收通知

### 方案 1：使用默认 Token（推荐快速体验）

默认 token 已启用，通知会发送到慧诚告警推送平台。

**如何接收通知**：
1. 访问：https://huicheng.powerby.com.cn/api/simple/alert/
2. 注册账号并登录
3. 在控制台中添加接收渠道（微信/邮件/短信等）
4. 系统会向该渠道推送通知

### 方案 2：配置自己的 Token（推荐生产使用）

如果您有自己的账号和 token，可以配置自定义 token：

```bash
# 方法1：环境变量（推荐）
export ALERT_PUSH_TOKEN="your_actual_token_here"

# 方法2：.env 文件
echo 'ALERT_PUSH_TOKEN=your_actual_token_here' >> .env

# 方法3：Django settings
# 在 listing_monitor_project/settings.py 中添加：
ALERT_PUSH_TOKEN = "your_actual_token_here"
```

## 🎯 通知类型

系统会发送以下通知：

### 1. ✅ 分析完成通知
```
✅ Twitter 分析完成 - List 1939614372311302186

任务 ID: 7a166cb0-04d9-4db3-a781-d5da0381dd39
Twitter List: List 1939614372311302186
推文数量: 7 条

📊 分析结果：
市场情绪：
  • 多头: X 条 (X.X%)
  • 空头: X 条 (X.X%)
  • 中性: X 条 (X.X%)

关键话题：
  1. 话题1 (X 次) 📈
  2. 话题2 (X 次) 📉

💰 成本统计：
  • 实际成本: $0.0003
  • 处理时长: 18.70 秒

完成时间: 2025-11-14 08:37:17
```

### 2. ❌ 分析失败通知
```
❌ Twitter 分析失败 - List 1939614372311302186

任务 ID: xxx
Twitter List: List 1939614372311302186
推文数量: X 条

⚠️ 错误信息：
[错误详情]

失败时间: 2025-11-14 08:40:00
```

### 3. ⚠️ 成本告警通知
```
⚠️ Twitter 分析成本告警 - List 1939614372311302186

任务 ID: xxx
Twitter List: List 1939614372311302186
推文数量: X 条

💰 成本告警：
  • 实际成本: $6.00
  • 告警阈值: $5.00
  • 超出比例: 20.0%

⚠️ 提示: 建议检查分析参数，避免成本过高
```

## 🔧 高级配置

### 自定义渠道
```bash
export ALERT_PUSH_CHANNEL="my_custom_channel"
```

### 自定义成本告警阈值
```bash
export COST_ALERT_THRESHOLD=10.00
```

### 禁用通知
如果需要禁用通知，可以显式传递 None：
```python
from twitter.services.notifier import TwitterNotificationService

notifier = TwitterNotificationService(token=None)
```

## 📊 测试通知

运行分析命令测试通知：
```bash
python manage.py run_analysis 1939614372311302186 --hours 24
```

查看日志确认通知发送：
```bash
# 成功的日志
[INFO] 使用默认通知 token，通知功能已启用
[INFO] [Task xxx] 发送完成通知
[INFO] 推送成功: ✅ Twitter 分析完成...

# 失败的日志（如果未配置接收端）
[WARNING] 推送失败: 找不到数据
```

## 🚨 故障排除

### 推送失败：找不到数据
**原因**: 默认 token 需要在平台上配置接收端

**解决**: 访问 https://huicheng.powerby.com.cn/api/simple/alert/ 登录并配置接收渠道

### 推送失败：认证失败
**原因**: token 无效或已过期

**解决**: 获取新的 token 并配置
```bash
export ALERT_PUSH_TOKEN="new_valid_token"
```

### 完全收不到通知
**检查步骤**:
1. 确认日志中有 "通知功能已启用"
2. 确认日志中有 "发送完成通知"
3. 访问推送平台确认接收端配置正确
4. 检查垃圾邮件文件夹（如果使用邮件通知）

## 💡 最佳实践

1. **开发环境**: 使用默认 token，无需配置
2. **生产环境**: 配置自己的 token，确保稳定接收
3. **监控成本**: 设置合适的 COST_ALERT_THRESHOLD（建议 $1-5）
4. **定期检查**: 定期查看通知日志，确保服务正常

## 📞 技术支持

- **平台文档**: https://huicheng.powerby.com.cn/api/simple/alert/
- **API 文档**: 查看 `monitor/services/notifier.py` 中的 `AlertPushService` 类
- **日志位置**: Django 日志文件或控制台输出

---

**状态**: ✅ 通知服务已默认启用，立即可用！

**下一步**: 根据您的需求选择接收方案（默认 token 或自定义 token）
