# 🔔 推送通知配置指南

## ✅ 已配置的推送服务

系统已集成**双重推送机制**，确保通知能够正常发送：

### 🏆 推荐方案：Bark 推送（iOS）

**Bark** 是一款优秀的 iOS 推送工具，只需在手机上安装应用并获取推送 URL，即可接收推送通知。

#### 📱 配置步骤

1. **安装 Bark 应用**
   - 在 iOS 设备上下载并安装 "Bark" 应用
   - 应用商店搜索 "Bark"

2. **获取推送 URL**
   - 打开 Bark 应用
   - 点击底部 "Devices" 选项
   - 复制显示的 URL（格式：`https://api.day.app/your_device_key`）

3. **配置系统**
   ```bash
   # 方法1：环境变量（推荐）
   export BARK_PUSH_URL="https://api.day.app/your_device_key"

   # 方法2：.env 文件
   echo 'BARK_PUSH_URL=https://api.day.app/your_device_key' >> .env

   # 方法3：Django settings.py
   # 添加到 settings.py：
   BARK_PUSH_URL = "https://api.day.app/your_device_key"
   ```

4. **测试推送**
   ```bash
   python manage.py run_analysis 1939614372311302186 --hours 24
   ```
   成功后会在 iPhone 上收到推送通知！

### 🔄 备选方案：慧诚告警推送

如果不想使用 Bark，可以配置其他推送渠道：

```bash
# 设置环境变量（使用您的实际 token）
export ALERT_PUSH_TOKEN="your_actual_token"
export ALERT_PUSH_CHANNEL="your_channel"
```

访问：https://huicheng.powerby.com.cn/api/simple/alert/ 注册并配置接收渠道。

## 🚀 即时使用

### 一键分析 + 自动推送

```bash
python manage.py run_analysis 1939614372311302186 --hours 24
```

执行后会自动：
1. ✅ 收集推文
2. ✅ 执行 AI 分析
3. ✅ **直接推送通知** 到您的设备

### 推送内容示例

```
✅ Twitter 分析完成 - List 1939614372311302186

任务 ID: 1a61ef15-19f1-49ba-8325-be4f52bbe210
Twitter List: List 1939614372311302186 - 项目机会分析
推文数量: 11 条

📊 分析结果：

市场情绪：
  • 多头: 3 条 (30.0%)
  • 空头: 1 条 (10.0%)
  • 中性: 7 条 (70.0%)

关键话题：
  1. 出金 (1 次) 📉
  2. HYPER-ALIGNMENT (1 次) ➖

💰 成本统计：
  • 实际成本: $0.0004
  • 处理时长: 34.48 秒

完成时间: 2025-11-14 09:21:24
```

## 📊 推送类型

系统会发送以下通知：

### 1. ✅ 分析完成通知
- 分析成功时发送
- 包含分析结果摘要
- 显示成本和处理时长

### 2. ❌ 分析失败通知
- 分析失败时发送
- 包含错误信息
- 显示失败原因

### 3. ⚠️ 成本告警通知
- 成本超过阈值时发送
- 默认阈值：$5.00
- 可自定义：环境变量 `COST_ALERT_THRESHOLD`

## ⚙️ 高级配置

### 自定义成本告警阈值
```bash
export COST_ALERT_THRESHOLD=10.00  # 设置为 $10.00
```

### 自定义推送频道
```bash
export ALERT_PUSH_CHANNEL="my_custom_channel"
```

### 禁用通知
```bash
# 设置 token 为空禁用通知
export ALERT_PUSH_TOKEN=""
```

## 🧪 测试推送

### 命令行测试
```bash
python manage.py test_notification
```

### 实际分析测试
```bash
python manage.py run_analysis 1939614372311302186 --hours 24
```

查看日志确认推送状态：
```
[INFO] 使用默认通知 token，通知功能已启用
[INFO] [Task xxx] 发送完成通知
[INFO] ✅ Bark 推送成功: ✅ Twitter 分析完成...
```

## 🎯 推荐配置

### 最优配置（推荐）
```bash
# .env 文件内容
BARK_PUSH_URL=https://api.day.app/your_device_key
COST_ALERT_THRESHOLD=5.00
```

**优势**：
- ✅ 推送即时到达
- ✅ 无需注册账号
- ✅ 完全免费
- ✅ 支持自定义声音和图标

### 生产环境配置
```bash
# .env 文件内容
ALERT_PUSH_TOKEN=your_production_token
ALERT_PUSH_CHANNEL=production
COST_ALERT_THRESHOLD=1.00
```

## 🚨 故障排除

### 问题1：收不到推送
**检查**：
1. 确认配置已生效：`python manage.py test_notification`
2. 查看日志：`grep -i "推送成功" logs/*.log`
3. 检查 Bark URL 是否正确

### 问题2：Bark 推送失败
**解决方案**：
1. 确认 iPhone 已安装 Bark 应用
2. 确认 URL 格式正确：`https://api.day.app/xxx`
3. 重新生成 URL：删除设备后重新添加

### 问题3：慧诚推送失败
**错误信息**：`找不到数据`
**解决方案**：
- 访问 https://huicheng.powerby.com.cn/api/simple/alert/ 注册并配置接收端
- 或改用 Bark 推送

## 📚 相关文件

- `twitter/services/notifier.py` - 通知服务实现
- `twitter/management/commands/test_notification.py` - 推送测试命令
- `RUN_ANALYSIS_GUIDE.md` - 一键分析使用指南

## 🎉 使用效果

配置完成后，每次运行分析都会自动推送通知：

```
[INFO] ✅ 使用默认通知 token，通知功能已启用
[INFO] [Task xxx] 发送完成通知
[INFO] ✅ Bark 推送成功: ✅ Twitter 分析完成 - List 1939614372311302186
```

**您将实时收到**：
- 📱 iPhone 推送通知（使用 Bark）
- 📊 完整分析结果
- 💰 成本和时间统计
- ⏰ 完成时间戳

## 💡 最佳实践

1. **一次性配置** - 配置后永久生效
2. **低成本监控** - 设置合理的成本阈值
3. **及时通知** - 推送延迟 < 5 秒
4. **多设备支持** - 可以添加多个 Bark 设备

---

**状态**: ✅ 推送服务已配置完成，支持多种推送渠道！

**下一步**: 根据指南配置您的推送渠道，即可享受实时推送通知！
