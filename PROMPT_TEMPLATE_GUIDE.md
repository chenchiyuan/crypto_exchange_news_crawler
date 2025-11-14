# 多 List 智能提示词模板 - 使用指南

## 🎯 功能概述

现在可以为不同的 Twitter List 配置不同的分析提示词模板，实现精准化分析！

### 核心特性
- ✅ **智能匹配**: 根据 List ID 自动选择对应模板
- ✅ **多类型支持**: 通用/项目机会/情绪/新闻/交易/自定义
- ✅ **灵活配置**: 每个模板可独立设置批次大小和成本上限
- ✅ **可视化管理**: 完整的 Django Admin 管理界面
- ✅ **预置模板**: 包含项目机会分析等常用模板

---

## 🚀 快速开始

### 1. 初始化模板数据

```bash
# 创建预置模板（推荐首次使用）
python manage.py init_prompt_templates
```

这会创建以下模板：
- ✅ 通用加密货币分析（默认）
- ✅ 项目机会分析（适用于 1939614372311302186）
- ✅ 市场情绪分析（默认）

### 2. 查看模板

访问 Admin 界面：
```
http://localhost:8000/admin/twitter/prompttemplate/
```

登录凭据：
- 用户名: `admin`
- 密码: `admin123`

### 3. 使用模板

```bash
# 自动选择模板（推荐）
python manage.py analyze_twitter_list 1939614372311302186 --hours 24

# 查看自动选择的模板
# 输出: ✓ 自动选择模板: 项目机会分析 (项目机会分析)
```

---

## 📋 模板管理

### 通过 Admin 管理（推荐）

1. **访问模板列表**
   ```
   http://localhost:8000/admin/twitter/prompttemplate/
   ```

2. **查看模板详情**
   - 名称和描述
   - 分析类型
   - 关联的 Twitter List
   - 配置参数（批次、成本）
   - 是否为默认模板

3. **创建新模板**
   ```
   点击 "添加 Prompt 模板"
   ```

4. **关联 List 到模板**
   ```
   在模板详情页面的 "Twitter List 关联" 中选择
   ```

### 通过代码管理

```python
from twitter.models import PromptTemplate, TwitterList

# 1. 获取或创建模板
template, created = PromptTemplate.objects.get_or_create(
    name='我的自定义模板',
    analysis_type=PromptTemplate.ANALYSIS_TYPE_CUSTOM,
    defaults={
        'template_content': '你的提示词模板...{tweet_content}',
        'is_default': False,
        'status': PromptTemplate.STATUS_ACTIVE,
    }
)

# 2. 关联 List
list_obj = TwitterList.objects.get(list_id='1234567890')
template.twitter_lists.add(list_obj)

# 3. 设置为默认模板（可选）
template.make_default()

# 4. 查看模板的 List
list_ids = template.get_twitter_list_ids()
print(list_ids)  # ['1234567890']

# 5. 查看 List 的模板
templates = list_obj.prompt_templates.all()
for t in templates:
    print(f'{t.name} - {t.get_analysis_type_display()}')
```

---

## 🎨 模板类型说明

### 1. 通用分析 (general)
- **用途**: 适用于一般性的加密货币推文分析
- **特点**: 市场情绪、关键话题、重要推文
- **默认**: 是
- **批次**: 100 条/批
- **成本**: $10.00

### 2. 项目机会分析 (opportunity) ⭐
- **用途**: 深度挖掘投资机会和交易信号
- **特点**: 多空一致性、观点提炼、操作解析、交易计划
- **默认**: 是
- **批次**: 50 条/批（更精细）
- **成本**: $15.00（更高上限）
- **关联**: 1939614372311302186

### 3. 市场情绪分析 (sentiment)
- **用途**: 专注于市场情绪和投资者心理分析
- **特点**: 恐惧贪婪指数、情绪指标、交易启示
- **默认**: 是
- **批次**: 200 条/批
- **成本**: $8.00

### 4. 新闻事件分析 (news)
- **用途**: 分析重大新闻事件对市场的影响
- **特点**: 事件分类、影响评估、相关性分析

### 5. 交易信号分析 (trading)
- **用途**: 提取交易信号和操作建议
- **特点**: 入场点、止损止盈、仓位管理

### 6. 自定义分析 (custom)
- **用途**: 用户自定义的分析类型
- **特点**: 完全自定义的内容和参数

---

## 🔧 配置说明

### 模板字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| name | 模板名称 | "项目机会分析" |
| description | 描述信息 | "深度挖掘投资机会..." |
| analysis_type | 分析类型 | "opportunity" |
| twitter_lists | 关联 List | List.objects.filter(list_id='1939...') |
| template_content | 模板内容 | 包含 {tweet_content} 占位符 |
| max_tweets_per_batch | 每批最大推文数 | 100 |
| max_cost_per_analysis | 每次分析最大成本 | 10.0000 |
| is_default | 是否为默认模板 | True/False |
| status | 状态 | active/inactive |

### Prompt 模板格式要求

```python
template_content = '''
你是角色定位...

请分析以下推文内容...

请按照以下格式输出：
{内容要求}

请开始分析以下推文：
{tweet_content}
'''
```

**注意**: 必须使用 `{tweet_content}` 作为推文内容的占位符。

---

## 💡 使用场景示例

### 场景 1: 项目调研 List
```python
# 创建项目机会分析模板
template = PromptTemplate.objects.create(
    name='项目调研分析',
    analysis_type=PromptTemplate.ANALYSIS_TYPE_OPPORTUNITY,
    template_content=project_opportunity_prompt,
    twitter_lists=list(project_lists),
    max_tweets_per_batch=50,
    max_cost_per_analysis=20.0000
)
```

### 场景 2: 情绪监控 List
```python
# 创建市场情绪分析模板
template = PromptTemplate.objects.create(
    name='情绪监控',
    analysis_type=PromptTemplate.ANALYSIS_TYPE_SENTIMENT,
    template_content=sentiment_prompt,
    twitter_lists=list(sentiment_lists),
    max_tweets_per_batch=300,
    max_cost_per_analysis=5.0000
)
```

### 场景 3: 通用监控 List
```python
# 使用通用分析模板（无需关联特定 List）
template = PromptTemplate.objects.create(
    name='通用监控',
    analysis_type=PromptTemplate.ANALYSIS_TYPE_GENERAL,
    template_content=general_prompt,
    # 不关联特定 List，默认为所有 List 使用
    max_tweets_per_batch=100,
    max_cost_per_analysis=10.0000
)
```

---

## 🔍 自动选择机制

### 选择优先级

1. **特定模板优先**: 如果 List 有关联的特定模板，使用该模板
2. **通用模板回退**: 如果没有特定模板，使用通用模板
3. **文件模板覆盖**: 如果指定了 `--prompt` 参数，强制使用文件模板

### 决策流程

```python
def get_template_for_list(list_id):
    # 1. 查找指定此 List 的模板
    specific = PromptTemplate.objects.filter(
        twitter_lists__list_id=list_id,
        status=PromptTemplate.STATUS_ACTIVE
    ).first()

    if specific:
        return specific

    # 2. 查找通用模板
    general = PromptTemplate.objects.filter(
        twitter_lists__isnull=True,
        status=PromptTemplate.STATUS_ACTIVE
    ).first()

    if general:
        return general

    # 3. 回退到默认通用模板
    default = PromptTemplate.objects.filter(
        analysis_type=PromptTemplate.ANALYSIS_TYPE_GENERAL,
        is_default=True,
        status=PromptTemplate.STATUS_ACTIVE
    ).first()

    return default
```

---

## 📊 实际测试结果

### 测试 1: 指定 List (1939614372311302186)
```bash
python manage.py analyze_twitter_list 1939614372311302186 --hours 24

# 输出:
# ✓ 自动选择模板: 项目机会分析 (项目机会分析)
```

### 测试 2: 通用 List (1988517245048455250)
```bash
python manage.py analyze_twitter_list 1988517245048455250 --hours 24

# 输出:
# ✓ 自动选择模板: 市场情绪分析 (市场情绪分析)
```

### 测试 3: 成本和批次控制
```bash
# List 1939614372311302186 (项目机会分析)
批次大小: 50 条/批
成本上限: $15.00

# List 1988517245048455250 (市场情绪分析)
批次大小: 200 条/批
成本上限: $8.00
```

---

## 🎯 最佳实践

### 1. 模板设计原则
- **专注性**: 每种模板专注一种分析类型
- **参数化**: 根据类型调整批次和成本
- **可复用**: 通用模板应适用于大多数场景

### 2. List 管理
- **分类管理**: 按用途分类 List（项目/情绪/新闻等）
- **精准匹配**: 重要 List 绑定特定模板
- **定期更新**: 根据使用效果调整模板

### 3. 成本控制
- **分级设置**: 不同类型设置不同成本上限
- **监控使用**: 定期检查实际成本消耗
- **优化提示词**: 简洁有效的提示词降低成本

### 4. 维护建议
- **备份配置**: 定期导出模板配置
- **版本控制**: 为重要模板添加版本号
- **测试验证**: 新模板上线前先测试效果

---

## 🔧 故障排查

### 问题 1: 模板未自动选择

```bash
# 检查模板是否存在
python manage.py shell -c "
from twitter.models import PromptTemplate
templates = PromptTemplate.objects.all()
for t in templates:
    print(f'{t.name}: {t.get_status_display()}, 默认: {t.is_default}')
"

# 检查 List 关联
python manage.py shell -c "
from twitter.models import TwitterList, PromptTemplate
list_obj = TwitterList.objects.get(list_id='你的list_id')
templates = list_obj.prompt_templates.all()
print(f'关联模板: {templates.count()}')
"
```

### 问题 2: 模板内容错误

```python
# 检查模板内容
template = PromptTemplate.objects.get(name='你的模板')
print(template.template_content[:100])  # 查看前100字符

# 验证是否包含 {tweet_content}
if '{tweet_content}' not in template.template_content:
    print('错误: 模板中缺少 {tweet_content} 占位符')
```

### 问题 3: 成本过高

```python
# 检查模板配置
template = PromptTemplate.objects.get(name='你的模板')
print(f'批次大小: {template.max_tweets_per_batch}')
print(f'成本上限: ${template.max_cost_per_analysis}')

# 调整参数
template.max_tweets_per_batch = 50  # 减小批次
template.max_cost_per_analysis = 5.0000  # 降低上限
template.save()
```

---

## 📚 更多资源

- **完整使用指南**: `USAGE_GUIDE.md`
- **项目总结**: `PROJECT_SUMMARY.md`
- **Admin 界面**: http://localhost:8000/admin/twitter/prompttemplate/

---

## ✨ 快速参考

### 常用命令

```bash
# 初始化模板
python manage.py init_prompt_templates

# 自动使用模板分析
python manage.py analyze_twitter_list <list_id> --hours 24

# 强制使用文件模板
python manage.py analyze_twitter_list <list_id> \
  --prompt /path/to/custom.txt
```

### 常用操作

```python
# 查看所有模板
PromptTemplate.objects.all()

# 查看 List 的模板
TwitterList.objects.get(list_id='xxx').prompt_templates.all()

# 设置默认模板
template.make_default()

# 关联 List
template.twitter_lists.add(list_obj)
```

---

**功能状态**: ✅ 已完成并通过测试，可立即投入使用！

**祝您使用愉快！** 🎉
