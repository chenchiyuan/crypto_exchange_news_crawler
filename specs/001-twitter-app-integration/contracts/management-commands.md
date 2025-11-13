# Management Command 接口规范

**Feature**: Twitter 应用集成与 AI 分析
**Version**: 1.0
**Last Updated**: 2025-11-13
**Status**: Design Phase

---

## 目录

- [概述](#概述)
- [命令清单](#命令清单)
- [命令详细规范](#命令详细规范)
  - [analyze_twitter_list](#analyze_twitter_list)
  - [collect_twitter_list](#collect_twitter_list)
  - [query_analysis_task](#query_analysis_task)
  - [cancel_analysis_task](#cancel_analysis_task)
- [通用规范](#通用规范)
- [错误码规范](#错误码规范)
- [输出格式规范](#输出格式规范)

---

## 概述

本文档定义了 Twitter 应用的所有 Django Management Command 的参数规范、行为约定和输出格式。

**设计原则**：
1. **一致性**：所有命令遵循相同的参数命名和输出格式
2. **可测试性**：所有命令支持 `--dry-run` 模式验证参数
3. **用户友好**：提供清晰的帮助文档和错误提示
4. **可追溯性**：所有操作记录详细日志

---

## 命令清单

| 命令名称 | 功能 | 优先级 | 用途 |
|---------|------|--------|------|
| `analyze_twitter_list` | 分析 Twitter List 推文 | P0 | 核心功能：获取推文并执行 AI 分析 |
| `collect_twitter_list` | 仅收集推文数据 | P1 | 数据收集：不执行分析，只存储推文 |
| `query_analysis_task` | 查询分析任务状态 | P2 | 任务管理：查询任务执行状态和结果 |
| `cancel_analysis_task` | 取消正在执行的任务 | P3 | 任务管理：取消运行中的分析任务 |

---

## 命令详细规范

### analyze_twitter_list

**功能**：获取指定 Twitter List 在指定时间范围内的推文，并使用 DeepSeek AI 进行内容分析。

#### 命令格式

```bash
python manage.py analyze_twitter_list <list_id> [options]
```

#### 位置参数

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| `list_id` | String | 是 | Twitter List ID，例如：`1234567890` |

#### 可选参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--hours` | Float | `24.0` | 时间范围（小时数），例如：`--hours 48` 表示最近 48 小时 |
| `--start-time` | DateTime | `None` | 开始时间（ISO 格式），例如：`2025-11-13T00:00:00` |
| `--end-time` | DateTime | `None` | 结束时间（ISO 格式），例如：`2025-11-13T23:59:59` |
| `--prompt` | String | `'crypto_analysis'` | 提示词模板名称或自定义文本文件路径 |
| `--batch-mode` | Boolean | `False` | 是否分批调用 AI（推荐用于大量推文） |
| `--batch-size` | Integer | `100` | 批次大小（仅在 `--batch-mode` 启用时有效） |
| `--max-cost` | Decimal | `10.00` | 最大允许成本（美元），超过则拒绝执行 |
| `--dry-run` | Boolean | `False` | 试运行模式，只验证和估算，不执行实际操作 |
| `--async` | Boolean | `False` | 异步执行模式，立即返回任务 ID |
| `--verbosity` | Integer | `1` | 日志详细程度（0=静默，1=正常，2=详细，3=调试） |

#### 时间参数规则

1. **使用 `--hours`（相对时间）**：
   ```bash
   # 分析最近 24 小时的推文
   python manage.py analyze_twitter_list 1234567890 --hours 24
   ```

2. **使用 `--start-time` 和 `--end-time`（绝对时间）**：
   ```bash
   # 分析指定时间范围的推文
   python manage.py analyze_twitter_list 1234567890 \
     --start-time "2025-11-13T00:00:00" \
     --end-time "2025-11-13T23:59:59"
   ```

3. **优先级**：如果同时提供 `--hours` 和 `--start-time/--end-time`，优先使用后者

#### 提示词模板

1. **使用预设模板**：
   ```bash
   python manage.py analyze_twitter_list 1234567890 --prompt crypto_analysis
   ```

2. **使用自定义文本文件**：
   ```bash
   python manage.py analyze_twitter_list 1234567890 --prompt /path/to/custom_prompt.txt
   ```

3. **预设模板清单**：
   - `crypto_analysis`: 加密货币市场分析（多空情绪、交易信号）
   - `sentiment_only`: 仅情绪分析
   - `topic_extraction`: 主题提取和趋势识别

#### 使用示例

**基础用法（同步执行）**：
```bash
# 分析最近 24 小时的推文
python manage.py analyze_twitter_list 1234567890

# 分析最近 48 小时的推文，使用自定义提示词
python manage.py analyze_twitter_list 1234567890 \
  --hours 48 \
  --prompt /tmp/my_prompt.txt
```

**异步执行（后台运行）**：
```bash
# 异步执行，立即返回任务 ID
python manage.py analyze_twitter_list 1234567890 \
  --hours 168 \
  --async

# 输出示例：
# ✅ 任务已创建: a1b2c3d4-e5f6-7890-abcd-ef1234567890
# 查看状态: python manage.py query_analysis_task a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**试运行模式**：
```bash
# 验证参数并估算成本，不执行实际分析
python manage.py analyze_twitter_list 1234567890 \
  --hours 72 \
  --dry-run

# 输出示例：
# [DRY RUN] 预览模式
# ✅ 验证通过
# 📊 预估信息:
#   - 推文数量: 约 1,250 条
#   - 预估成本: $3.45
#   - 预估时间: 约 5 分钟
#   - 批次数: 13 批（每批 100 条）
```

**批次模式（大量推文）**：
```bash
# 分批调用 AI，每批 50 条推文
python manage.py analyze_twitter_list 1234567890 \
  --hours 168 \
  --batch-mode \
  --batch-size 50
```

#### 输出格式

**同步执行（成功）**：
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

**异步执行（成功）**：
```
🚀 创建异步分析任务...
✅ 任务已创建: a1b2c3d4-e5f6-7890-abcd-ef1234567890

查看状态:
python manage.py query_analysis_task a1b2c3d4-e5f6-7890-abcd-ef1234567890

等待完成后查看结果:
python manage.py query_analysis_task a1b2c3d4-e5f6-7890-abcd-ef1234567890 --result
```

#### 错误处理

| 错误场景 | 错误码 | 错误信息 |
|---------|--------|---------|
| List ID 不存在 | `LIST_NOT_FOUND` | `❌ Twitter List 不存在: {list_id}` |
| API 认证失败 | `AUTH_FAILED` | `❌ Twitter API 认证失败，请检查 TWITTER_API_KEY` |
| 成本超限 | `COST_EXCEEDED` | `❌ 预估成本 ${cost:.2f} 超过上限 ${max_cost:.2f}` |
| 时间范围无效 | `INVALID_TIME_RANGE` | `❌ 开始时间必须早于结束时间` |
| 推文数量为 0 | `NO_TWEETS` | `⚠️ 警告: 时间范围内没有找到推文` |

---

### collect_twitter_list

**功能**：仅收集 Twitter List 的推文数据到数据库，不执行 AI 分析。

#### 命令格式

```bash
python manage.py collect_twitter_list <list_id> [options]
```

#### 位置参数

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| `list_id` | String | 是 | Twitter List ID |

#### 可选参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--hours` | Float | `24.0` | 时间范围（小时数） |
| `--start-time` | DateTime | `None` | 开始时间（ISO 格式） |
| `--end-time` | DateTime | `None` | 结束时间（ISO 格式） |
| `--batch-size` | Integer | `500` | 每批获取的推文数量 |
| `--dry-run` | Boolean | `False` | 试运行模式 |
| `--verbosity` | Integer | `1` | 日志详细程度 |

#### 使用示例

```bash
# 收集最近 24 小时的推文
python manage.py collect_twitter_list 1234567890

# 收集指定时间范围的推文
python manage.py collect_twitter_list 1234567890 \
  --start-time "2025-11-01T00:00:00" \
  --end-time "2025-11-13T23:59:59"

# 试运行（只验证和估算）
python manage.py collect_twitter_list 1234567890 \
  --hours 168 \
  --dry-run
```

#### 输出格式

```
🚀 开始收集 Twitter List 推文: CryptoKOLs (ID: 1234567890)
📅 时间范围: 2025-11-12 10:00:00 → 2025-11-13 10:00:00

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

---

### query_analysis_task

**功能**：查询分析任务的状态和结果。

#### 命令格式

```bash
python manage.py query_analysis_task <task_id> [options]
```

#### 位置参数

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| `task_id` | UUID | 是 | 任务 ID，例如：`a1b2c3d4-e5f6-7890-abcd-ef1234567890` |

#### 可选参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--result` | Boolean | `False` | 显示完整的分析结果（JSON 格式） |
| `--format` | String | `'text'` | 输出格式：`text`, `json`, `summary` |
| `--verbosity` | Integer | `1` | 日志详细程度 |

#### 使用示例

```bash
# 查询任务状态
python manage.py query_analysis_task a1b2c3d4-e5f6-7890-abcd-ef1234567890

# 查询并显示完整结果
python manage.py query_analysis_task a1b2c3d4-e5f6-7890-abcd-ef1234567890 --result

# 以 JSON 格式输出
python manage.py query_analysis_task a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  --format json
```

#### 输出格式

**基础状态查询（`--format text`）**：
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 任务详情
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  任务 ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
  Twitter List: CryptoKOLs (ID: 1234567890)
  时间范围: 2025-11-12 10:00:00 → 2025-11-13 10:00:00
  状态: ✅ 已完成
  创建时间: 2025-11-13 10:15:30
  完成时间: 2025-11-13 10:18:05

📊 执行统计
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  推文数量: 850
  处理时间: 2m 35s
  分析成本: $2.34

💡 分析结果摘要
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  多空情绪:
    看多: 62%
    看空: 23%
    中性: 15%

  主要话题:
    1. BTC 价格突破 (120 次提及)
    2. ETH 合并进展 (85 次提及)
    3. DeFi 协议安全 (54 次提及)

  查看完整结果: --result 参数
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**JSON 格式输出（`--format json`）**：
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "twitter_list": {
    "list_id": "1234567890",
    "name": "CryptoKOLs"
  },
  "time_range": {
    "start": "2025-11-12T10:00:00Z",
    "end": "2025-11-13T10:00:00Z"
  },
  "status": "completed",
  "created_at": "2025-11-13T10:15:30Z",
  "completed_at": "2025-11-13T10:18:05Z",
  "statistics": {
    "tweet_count": 850,
    "processing_time": "2m 35s",
    "cost_amount": "2.34"
  },
  "analysis_result": {
    "summary": "...",
    "sentiment": { ... },
    "key_topics": [ ... ]
  }
}
```

**运行中任务的输出**：
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 任务详情
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  任务 ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
  Twitter List: CryptoKOLs (ID: 1234567890)
  状态: ⏳ 执行中
  创建时间: 2025-11-13 10:15:30
  已处理推文: 450 / 850 (53%)
  预估剩余时间: 约 1 分钟

💡 提示: 使用相同命令稍后重新查询
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### cancel_analysis_task

**功能**：取消正在执行的分析任务。

#### 命令格式

```bash
python manage.py cancel_analysis_task <task_id> [options]
```

#### 位置参数

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| `task_id` | UUID | 是 | 任务 ID |

#### 可选参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--force` | Boolean | `False` | 强制取消（即使任务已完成） |
| `--verbosity` | Integer | `1` | 日志详细程度 |

#### 使用示例

```bash
# 取消运行中的任务
python manage.py cancel_analysis_task a1b2c3d4-e5f6-7890-abcd-ef1234567890

# 强制取消（即使任务已完成）
python manage.py cancel_analysis_task a1b2c3d4-e5f6-7890-abcd-ef1234567890 --force
```

#### 输出格式

**成功取消**：
```
⏳ 正在取消任务: a1b2c3d4-e5f6-7890-abcd-ef1234567890
✅ 任务已取消

任务信息:
  Twitter List: CryptoKOLs (ID: 1234567890)
  已处理推文: 450 / 850
  已产生成本: $1.20
```

**无法取消（任务已完成）**：
```
❌ 无法取消任务: 任务已完成
使用 --force 参数强制标记为已取消
```

---

## 通用规范

### 时间格式

所有命令接受以下时间格式：

1. **ISO 8601 格式**（推荐）：
   - `2025-11-13T10:00:00`
   - `2025-11-13T10:00:00+08:00`
   - `2025-11-13T10:00:00Z`

2. **相对时间**（使用 `--hours` 参数）：
   - `--hours 24` (最近 24 小时)
   - `--hours 168` (最近 7 天)
   - `--hours 0.5` (最近 30 分钟)

### 成本格式

所有成本金额使用美元（USD），保留 4 位小数：
- `$0.0000` - `$9999.9999`

### 进度显示

所有长时间运行的操作使用以下格式显示进度：
```
⏳ [1/3] 正在执行步骤...
✅ 成功 (耗时: 30s)

⏳ [2/3] 正在执行下一步...
```

### Verbosity 等级

| 等级 | 说明 | 输出内容 |
|------|------|---------|
| `0` | 静默模式 | 只输出错误 |
| `1` | 正常模式（默认） | 输出主要步骤和结果 |
| `2` | 详细模式 | 输出所有步骤和中间信息 |
| `3` | 调试模式 | 输出 API 调用细节和调试信息 |

---

## 错误码规范

### 错误码格式

所有错误码采用 `UPPER_SNAKE_CASE` 格式，例如：`LIST_NOT_FOUND`

### 错误码清单

| 错误码 | HTTP 等价 | 说明 | 示例信息 |
|--------|-----------|------|---------|
| `INVALID_ARGUMENT` | 400 | 参数验证失败 | `❌ 无效的 List ID: {value}` |
| `LIST_NOT_FOUND` | 404 | Twitter List 不存在 | `❌ Twitter List 不存在: {list_id}` |
| `LIST_ACCESS_DENIED` | 403 | 无权限访问 List | `❌ 无权限访问该 Twitter List` |
| `AUTH_FAILED` | 401 | API 认证失败 | `❌ Twitter API 认证失败` |
| `RATE_LIMIT_EXCEEDED` | 429 | API 限流 | `❌ API 限流，请 {seconds} 秒后重试` |
| `COST_EXCEEDED` | 400 | 成本超限 | `❌ 预估成本 ${cost} 超过上限 ${max}` |
| `INVALID_TIME_RANGE` | 400 | 时间范围无效 | `❌ 开始时间必须早于结束时间` |
| `NO_TWEETS` | 200 | 无推文（警告） | `⚠️ 时间范围内没有找到推文` |
| `TASK_NOT_FOUND` | 404 | 任务不存在 | `❌ 任务不存在: {task_id}` |
| `TASK_ALREADY_COMPLETED` | 400 | 任务已完成 | `❌ 任务已完成，无法取消` |
| `AI_SERVICE_ERROR` | 500 | AI 服务错误 | `❌ AI 服务错误: {error_message}` |
| `DATABASE_ERROR` | 500 | 数据库错误 | `❌ 数据库错误: {error_message}` |
| `UNKNOWN_ERROR` | 500 | 未知错误 | `❌ 未知错误: {error_message}` |

### 错误输出格式

```
❌ 错误: {ERROR_CODE}
{错误详细信息}

建议:
- {解决建议 1}
- {解决建议 2}

如需帮助:
python manage.py {command_name} --help
```

---

## 输出格式规范

### 颜色和图标

| 类型 | 图标 | 颜色 | 用途 |
|------|------|------|------|
| 成功 | ✅ | 绿色 | 操作成功 |
| 错误 | ❌ | 红色 | 操作失败 |
| 警告 | ⚠️ | 黄色 | 警告信息 |
| 信息 | ℹ️ | 蓝色 | 提示信息 |
| 进行中 | ⏳ | 默认 | 正在执行 |
| 完成 | 🎉 | 绿色 | 全部完成 |

### 表格格式

使用 Unicode 字符绘制表格：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 标题
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  字段 1: 值 1
  字段 2: 值 2
  字段 3: 值 3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### JSON 输出格式

当使用 `--format json` 时，输出标准 JSON 格式：

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "timestamp": "2025-11-13T10:00:00Z"
}
```

错误时：

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "LIST_NOT_FOUND",
    "message": "Twitter List 不存在: 1234567890",
    "suggestions": [
      "检查 List ID 是否正确",
      "确认该 List 是公开的"
    ]
  },
  "timestamp": "2025-11-13T10:00:00Z"
}
```

---

## 日志记录

### 日志级别映射

| Verbosity | Python Logging | 说明 |
|-----------|----------------|------|
| `0` | `ERROR` | 只记录错误 |
| `1` | `INFO` | 记录主要操作 |
| `2` | `DEBUG` | 记录详细步骤 |
| `3` | `DEBUG` + API 详情 | 记录所有细节 |

### 日志格式

```python
# 标准日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 示例输出
2025-11-13 10:15:30 - twitter.commands.analyze - INFO - 开始分析 List: 1234567890
2025-11-13 10:15:35 - twitter.sdk - DEBUG - API 请求: /graphql/ListLatestTweetsTimeline
2025-11-13 10:15:40 - twitter.sdk - DEBUG - API 响应: 200 OK (500 tweets)
2025-11-13 10:18:05 - twitter.commands.analyze - INFO - 分析完成，耗时: 2m 35s
```

---

## 总结

本规范定义了 Twitter 应用所有命令行工具的接口标准，确保：

1. **一致性**：所有命令遵循统一的参数和输出格式
2. **可用性**：清晰的帮助文档和友好的错误提示
3. **可维护性**：标准化的错误码和日志格式
4. **可测试性**：支持 dry-run 模式和 JSON 输出

**下一步**：基于本规范实现 Django Management Commands。
