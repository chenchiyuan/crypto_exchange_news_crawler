# 快速开始指南 (Quickstart)

**Feature**: Twitter 应用集成与 AI 分析
**Version**: 1.0
**Last Updated**: 2025-11-13
**Target Audience**: 开发者和运维人员

---

## 目录

- [前置要求](#前置要求)
- [安装步骤](#安装步骤)
- [环境配置](#环境配置)
- [数据库设置](#数据库设置)
- [基础使用](#基础使用)
- [高级用法](#高级用法)
- [常见问题](#常见问题)
- [故障排查](#故障排查)

---

## 前置要求

### 系统要求

| 组件 | 最低版本 | 推荐版本 | 说明 |
|------|---------|---------|------|
| Python | 3.8+ | 3.11+ | 必需 |
| Django | 4.2+ | 5.0+ | 必需 |
| PostgreSQL | 14+ | 15+ | 生产环境推荐 |
| SQLite | 3.35+ | 最新 | 开发环境可用 |

### API 密钥

在开始之前，你需要准备以下 API 密钥：

1. **Twitter API Key**（通过 apidance.pro 获取）
   - 注册地址：https://apidance.pro
   - 费用：约 $10-20/月
   - 用途：获取 Twitter List 推文数据

2. **DeepSeek API Key**（通过 DeepSeek 官网获取）
   - 注册地址：https://platform.deepseek.com
   - 费用：按使用量计费（约 $0.14/1M input tokens）
   - 用途：AI 内容分析

3. **告警推送 Token**（可选，用于接收通知）
   - 复用项目现有的告警推送服务
   - 配置位置：`.env` 文件中的 `ALERT_PUSH_TOKEN`

---

## 安装步骤

### Step 1: 克隆项目并进入目录

```bash
cd /path/to/crypto_exchange_news_crawler
```

### Step 2: 激活虚拟环境

```bash
# 如果已有虚拟环境
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate  # Windows

# 如果没有虚拟环境
python3 -m venv venv
source venv/bin/activate
```

### Step 3: 安装依赖

```bash
# 安装项目基础依赖（如果尚未安装）
pip install -r requirements.txt

# 验证关键依赖
pip list | grep -E 'Django|requests|tenacity|python-dateutil'
```

**预期输出**：
```
Django               4.2.7
requests             2.31.0
tenacity             8.2.3
python-dateutil      2.8.2
```

### Step 4: 验证安装

```bash
# 检查 Django 版本
python manage.py --version

# 检查 Twitter 应用是否已注册
python manage.py show_apps | grep twitter
```

---

## 环境配置

### Step 1: 创建环境变量文件

```bash
# 在项目根目录创建 .env 文件（如果不存在）
touch .env
```

### Step 2: 配置 API 密钥

编辑 `.env` 文件，添加以下配置：

```bash
# ============================================================
# Twitter API 配置
# ============================================================
TWITTER_API_KEY=your_twitter_api_key_here
TWITTER_BASE_URL=https://api.twitter.com  # 可选，默认值

# ============================================================
# DeepSeek AI 配置
# ============================================================
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com  # 可选，默认值
DEEPSEEK_MODEL=deepseek-chat  # 可选，默认值

# ============================================================
# 告警推送配置（可选）
# ============================================================
ALERT_PUSH_TOKEN=your_alert_push_token_here
ALERT_PUSH_CHANNEL=twitter_analysis  # 推送渠道
```

### Step 3: 验证配置

```bash
# 测试 Twitter API 连接（需要先创建测试命令，这里假设已有）
python manage.py test_twitter_api

# 测试 DeepSeek API 连接
python manage.py test_deepseek_api
```

**预期输出**：
```
✅ Twitter API 连接成功
✅ DeepSeek API 连接成功
```

---

## 数据库设置

### 开发环境（SQLite）

```bash
# Step 1: 创建数据库迁移文件
python manage.py makemigrations twitter

# Step 2: 执行迁移
python manage.py migrate twitter

# Step 3: 验证表是否创建
python manage.py dbshell
sqlite> .tables
# 应该看到 twitter_lists, twitter_tweets, twitter_analysis_results 等表
sqlite> .exit
```

### 生产环境（PostgreSQL）

#### Step 1: 创建数据库

```bash
# 连接到 PostgreSQL
psql -U postgres

# 创建数据库
CREATE DATABASE crypto_exchange_news;

# 创建用户（如果不存在）
CREATE USER crypto_user WITH PASSWORD 'your_password';

# 授权
GRANT ALL PRIVILEGES ON DATABASE crypto_exchange_news TO crypto_user;

# 退出
\q
```

#### Step 2: 配置数据库连接

编辑 `crypto_exchange_news/settings.py` 或 `.env` 文件：

```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'crypto_exchange_news',
        'USER': 'crypto_user',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

或在 `.env` 文件中：

```bash
DATABASE_URL=postgresql://crypto_user:your_password@localhost:5432/crypto_exchange_news
```

#### Step 3: 执行迁移

```bash
python manage.py migrate twitter
```

#### Step 4: 验证

```bash
# 连接到数据库
psql -U crypto_user -d crypto_exchange_news

# 查看表
\dt twitter_*

# 预期输出
# twitter_lists
# twitter_tweets
# twitter_analysis_results
# twitter_tags
# twitter_lists_tags

\q
```

---

## 基础使用

### 场景 1: 收集推文数据（不分析）

```bash
# 收集某个 Twitter List 最近 24 小时的推文
python manage.py collect_twitter_list 1234567890

# 收集最近 7 天的推文
python manage.py collect_twitter_list 1234567890 --hours 168
```

**预期输出**：
```
🚀 开始收集 Twitter List 推文: CryptoKOLs (ID: 1234567890)
📅 时间范围: 2025-11-06 10:00:00 → 2025-11-13 10:00:00

⏳ 批次 1/3: 获取推文 [0-500]...
✅ 成功: 500 条

⏳ 批次 2/3: 获取推文 [500-1000]...
✅ 成功: 500 条

⏳ 批次 3/3: 获取推文 [1000-1250]...
✅ 成功: 250 条

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 收集摘要
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  总推文数: 1,250
  新增推文: 1,120
  已存在推文: 130
  执行时间: 45s
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 场景 2: 分析推文（同步执行）

```bash
# 分析最近 24 小时的推文（使用默认 crypto_analysis 模板）
python manage.py analyze_twitter_list 1234567890

# 分析最近 48 小时的推文
python manage.py analyze_twitter_list 1234567890 --hours 48
```

**预期输出**：
```
🚀 开始分析 Twitter List: CryptoKOLs (ID: 1234567890)
📅 时间范围: 2025-11-12 10:00:00 → 2025-11-13 10:00:00

⏳ [1/3] 获取推文数据...
✅ 获取成功: 850 条推文

⏳ [2/3] 调用 AI 分析服务...
✅ 分析完成 (耗时: 2m 35s)

⏳ [3/3] 保存分析结果...
✅ 保存成功

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 执行摘要
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  任务 ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
  推文数量: 850
  分析成本: $2.34
  处理时间: 2m 35s
  状态: 已完成

  多空情绪:
    看多: 62%
    看空: 23%
    中性: 15%

  查看完整结果:
  python manage.py query_analysis_task a1b2c3d4-e5f6-7890-abcd-ef1234567890
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 场景 3: 查询分析结果

```bash
# 查询任务状态
python manage.py query_analysis_task a1b2c3d4-e5f6-7890-abcd-ef1234567890

# 查看完整分析结果
python manage.py query_analysis_task a1b2c3d4-e5f6-7890-abcd-ef1234567890 --result

# 以 JSON 格式导出
python manage.py query_analysis_task a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  --format json > analysis_result.json
```

---

## 高级用法

### 技巧 1: 试运行模式（验证配置）

在执行实际分析前，先验证参数和估算成本：

```bash
python manage.py analyze_twitter_list 1234567890 \
  --hours 168 \
  --dry-run
```

**预期输出**：
```
[DRY RUN] 预览模式
✅ 验证通过
📊 预估信息:
  - 推文数量: 约 1,250 条
  - 预估成本: $3.45
  - 预估时间: 约 5 分钟
  - 批次数: 13 批（每批 100 条）
```

### 技巧 2: 异步执行（后台运行）

对于大量推文的分析，使用异步模式避免长时间等待：

```bash
# 异步执行，立即返回任务 ID
python manage.py analyze_twitter_list 1234567890 \
  --hours 168 \
  --async

# 输出示例：
# ✅ 任务已创建: a1b2c3d4-e5f6-7890-abcd-ef1234567890
# 查看状态: python manage.py query_analysis_task a1b2c3d4-e5f6-7890-abcd-ef1234567890

# 稍后查询任务状态
python manage.py query_analysis_task a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### 技巧 3: 批次模式（大量推文）

当推文数量超过 500 条时，使用批次模式分批调用 AI：

```bash
python manage.py analyze_twitter_list 1234567890 \
  --hours 168 \
  --batch-mode \
  --batch-size 50
```

**优势**：
- 降低单次 API 调用的 token 数量
- 避免超时错误
- 更细粒度的进度追踪

### 技巧 4: 自定义提示词

使用自己的提示词模板进行分析：

```bash
# Step 1: 创建自定义提示词文件
cat > /tmp/my_prompt.txt << 'EOF'
请分析以下推文内容，重点关注：
1. 市场情绪（看多/看空/中性）
2. 提到的加密货币及其价格预测
3. 交易信号和策略建议
4. 风险警告

推文内容：
{{tweets}}
EOF

# Step 2: 使用自定义提示词
python manage.py analyze_twitter_list 1234567890 \
  --prompt /tmp/my_prompt.txt
```

### 技巧 5: 指定时间范围

分析特定日期的推文：

```bash
# 分析 2025 年 11 月 13 日的推文
python manage.py analyze_twitter_list 1234567890 \
  --start-time "2025-11-13T00:00:00" \
  --end-time "2025-11-13T23:59:59"

# 分析特定时间段（精确到分钟）
python manage.py analyze_twitter_list 1234567890 \
  --start-time "2025-11-13T09:00:00" \
  --end-time "2025-11-13T17:00:00"
```

### 技巧 6: 成本控制

设置成本上限，避免意外高额费用：

```bash
# 设置成本上限为 $5
python manage.py analyze_twitter_list 1234567890 \
  --hours 168 \
  --max-cost 5.00

# 如果超过上限，将拒绝执行：
# ❌ 预估成本 $8.50 超过上限 $5.00
```

### 技巧 7: 取消运行中的任务

如果发现任务执行时间过长或配置错误：

```bash
# 取消任务
python manage.py cancel_analysis_task a1b2c3d4-e5f6-7890-abcd-ef1234567890

# 输出示例：
# ⏳ 正在取消任务...
# ✅ 任务已取消
#
# 任务信息:
#   已处理推文: 450 / 850
#   已产生成本: $1.20
```

---

## 常见问题

### Q1: 如何获取 Twitter List ID?

**答**：在浏览器中打开 Twitter List 页面，URL 格式如下：
```
https://twitter.com/i/lists/1234567890
                          ^^^^^^^^^^
                          这是 List ID
```

或者使用 Twitter Web 界面：
1. 打开 Twitter List 页面
2. 右键点击"查看页面源代码"
3. 搜索 `list_id`

### Q2: 推文数量为 0 怎么办?

**可能原因**：
1. 时间范围内确实没有推文
2. Twitter List 是私有的（需要权限）
3. API Key 没有访问权限

**解决方法**：
```bash
# 1. 扩大时间范围
python manage.py collect_twitter_list 1234567890 --hours 168

# 2. 使用 --dry-run 验证 API 连接
python manage.py analyze_twitter_list 1234567890 --dry-run

# 3. 检查 List 是否公开
# 在浏览器中访问: https://twitter.com/i/lists/1234567890
```

### Q3: 分析成本比预期高很多?

**可能原因**：
1. 推文内容过长（包含大量链接、图片描述）
2. 使用了复杂的自定义提示词

**解决方法**：
```bash
# 1. 先使用 --dry-run 估算成本
python manage.py analyze_twitter_list 1234567890 --hours 168 --dry-run

# 2. 减少批次大小
python manage.py analyze_twitter_list 1234567890 \
  --batch-mode \
  --batch-size 50

# 3. 使用更简洁的提示词模板
python manage.py analyze_twitter_list 1234567890 --prompt sentiment_only
```

### Q4: 如何定期自动执行分析?

**答**：使用系统的定时任务（cron）：

```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每天 10:00 执行）
0 10 * * * cd /path/to/crypto_exchange_news_crawler && \
  source venv/bin/activate && \
  python manage.py analyze_twitter_list 1234567890 --hours 24 --async
```

### Q5: 如何查看历史分析结果?

**答**：使用 Django shell 或数据库查询：

```bash
# 使用 Django shell
python manage.py shell

>>> from twitter.models import TwitterAnalysisResult
>>> results = TwitterAnalysisResult.objects.filter(status='completed').order_by('-created_at')[:10]
>>> for r in results:
...     print(f"{r.task_id} - {r.twitter_list.name} - {r.created_at}")
```

或者直接查询数据库：

```sql
-- SQLite
sqlite3 db.sqlite3
SELECT task_id, created_at, tweet_count, cost_amount, status
FROM twitter_analysis_results
ORDER BY created_at DESC
LIMIT 10;

-- PostgreSQL
psql -U crypto_user -d crypto_exchange_news
SELECT task_id, created_at, tweet_count, cost_amount, status
FROM twitter_analysis_results
ORDER BY created_at DESC
LIMIT 10;
```

---

## 故障排查

### 问题 1: `Twitter API 认证失败`

**错误信息**：
```
❌ 错误: AUTH_FAILED
Twitter API 认证失败，请检查 TWITTER_API_KEY
```

**排查步骤**：

1. 检查 `.env` 文件中的 API Key 是否正确：
   ```bash
   grep TWITTER_API_KEY .env
   ```

2. 验证 API Key 是否有效：
   ```bash
   curl -H "apikey: your_api_key_here" https://api.twitter.com/1.1/application/rate_limit_status.json
   ```

3. 检查 API Key 是否过期（联系 apidance.pro）

### 问题 2: `DeepSeek API 限流`

**错误信息**：
```
❌ 错误: RATE_LIMIT_EXCEEDED
API 限流，请 60 秒后重试
```

**排查步骤**：

1. 检查 API 配额使用情况：
   - 登录 DeepSeek 控制台
   - 查看 API 调用统计

2. 使用批次模式降低调用频率：
   ```bash
   python manage.py analyze_twitter_list 1234567890 \
     --batch-mode \
     --batch-size 50
   ```

3. 等待限流恢复后重试

### 问题 3: `数据库锁定错误` (SQLite)

**错误信息**：
```
❌ 错误: DATABASE_ERROR
database is locked
```

**排查步骤**：

1. 检查是否有其他进程在使用数据库：
   ```bash
   lsof db.sqlite3
   ```

2. 关闭所有 Django shell 和 dbshell 会话

3. 如果是生产环境，迁移到 PostgreSQL：
   ```bash
   # 导出数据
   python manage.py dumpdata > data.json

   # 配置 PostgreSQL
   # （见上文"数据库设置 - 生产环境"）

   # 导入数据
   python manage.py loaddata data.json
   ```

### 问题 4: `任务一直处于 running 状态`

**排查步骤**：

1. 检查任务详情：
   ```bash
   python manage.py query_analysis_task <task_id> -v 2
   ```

2. 查看日志文件：
   ```bash
   tail -f logs/twitter.log
   ```

3. 如果任务确实卡住，手动标记为失败：
   ```bash
   python manage.py shell
   >>> from twitter.models import TwitterAnalysisResult
   >>> task = TwitterAnalysisResult.objects.get(task_id='<task_id>')
   >>> task.mark_as_failed('任务超时')
   ```

### 问题 5: `内存不足` (大量推文)

**错误信息**：
```
MemoryError: Unable to allocate array
```

**排查步骤**：

1. 使用批次模式：
   ```bash
   python manage.py analyze_twitter_list 1234567890 \
     --batch-mode \
     --batch-size 50
   ```

2. 减少时间范围：
   ```bash
   python manage.py analyze_twitter_list 1234567890 --hours 24
   ```

3. 监控内存使用：
   ```bash
   # 使用 htop 或 top 监控
   htop

   # 使用 memory_profiler
   pip install memory_profiler
   python -m memory_profiler manage.py analyze_twitter_list 1234567890
   ```

---

## 下一步

完成快速开始后，你可以：

1. **阅读详细文档**：
   - [数据模型设计](./data-model.md)
   - [命令行接口规范](./contracts/management-commands.md)

2. **查看源代码**：
   - `twitter/models.py` - 数据模型
   - `twitter/management/commands/` - 命令实现
   - `twitter/utils/` - 工具模块

3. **运行测试**：
   ```bash
   python manage.py test twitter
   ```

4. **贡献代码**：
   - 提交 Issue
   - 创建 Pull Request

---

## 获取帮助

如果遇到本文档未覆盖的问题：

1. **查看命令帮助**：
   ```bash
   python manage.py analyze_twitter_list --help
   ```

2. **查看日志**：
   ```bash
   tail -f logs/twitter.log
   ```

3. **联系支持**：
   - 项目 Issue: [GitHub Issues](https://github.com/your-repo/issues)
   - 邮件: support@example.com

---

**祝你使用愉快！** 🚀
