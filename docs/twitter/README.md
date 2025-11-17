# 🐦 Twitter分析系统文档

本目录包含Twitter分析系统的完整文档。

## 📋 文档列表

### 核心功能文档

1. **PROMPT_FILE_SYSTEM.md** - 提示词文件管理系统
   - 提示词从数据库迁移到文件系统的完整说明
   - List ID到提示词文件的映射配置
   - 默认配置和使用方法

2. **RUN_ANALYSIS_GUIDE.md** - 分析运行指南
   - 如何运行Twitter分析任务
   - 命令行参数说明
   - 常见问题和解决方案

3. **PROMPT_TEMPLATE_GUIDE.md** - 提示词模板指南
   - 提示词模板的创建和修改
   - 不同分析类型的模板说明
   - 模板最佳实践

### 专业投研分析

4. **PRO_TEMPLATE_SUMMARY.md** - 专业投研模板总结
   - 专业投研分析提示词说明
   - 分析结构和输出格式
   - 使用案例

### 推送通知

5. **PUSH_FORMAT_FIX_SUMMARY.md** - 推送格式修复总结
   - 推送通知格式问题的修复过程
   - 智能格式识别逻辑
   - 兼容性处理方案

### 调试文档

6. **AI_ANALYSIS_DEBUG_REPORT.md** - AI分析调试报告
   - 完整记录推送给AI的内容
   - AI分析结果详细分析
   - 问题诊断和原因分析

7. **DEBUG_COMPLETE_SUMMARY.md** - 调试完整总结
   - 调试过程完整记录
   - 修复方案和验证结果
   - 优化建议

## 🎯 快速导航

### 新功能开发
- 查看 `PROMPT_FILE_SYSTEM.md` 了解提示词管理
- 查看 `PRO_TEMPLATE_SUMMARY.md` 了解专业投研模板

### 运行分析
- 查看 `RUN_ANALYSIS_GUIDE.md` 了解如何运行分析
- 查看 `PUSH_FORMAT_FIX_SUMMARY.md` 了解推送配置

### 问题调试
- 查看 `AI_ANALYSIS_DEBUG_REPORT.md` 了解问题诊断
- 查看 `DEBUG_COMPLETE_SUMMARY.md` 了解修复过程

## 📊 系统架构

```
Twitter分析系统
├── 提示词加载 (PromptLoader)
│   ├── 文件系统存储
│   ├── JSON映射配置
│   └── 动态加载
├── 分析编排器 (Orchestrator)
│   ├── 任务创建
│   ├── 数据获取
│   ├── 成本估算
│   └── AI分析
├── AI分析服务 (AIAnalysisService)
│   ├── DeepSeek SDK
│   ├── 批次处理
│   └── 结果解析
└── 通知服务 (NotificationService)
    ├── 慧诚推送
    ├── 动态格式化
    └── 兼容性处理
```

## 🔧 核心文件

- `twitter/services/prompt_loader.py` - 提示词加载服务
- `twitter/services/orchestrator.py` - 分析编排器
- `twitter/services/ai_analysis_service.py` - AI分析服务
- `twitter/services/notifier.py` - 通知服务
- `twitter/prompts/` - 提示词文件目录
- `twitter/prompts/prompt_mappings.json` - List映射配置

## 📝 使用示例

### 运行分析
```bash
# 专业投研分析
python manage.py run_analysis 1939614372311302186 --hours 24

# 市场情绪分析
python manage.py run_analysis 1988517245048455250 --hours 24
```

### 测试提示词加载
```bash
python manage.py test_prompt_loader
```

### 干跑测试
```bash
python manage.py run_analysis <list_id> --hours 24 --dry-run
```

## 🚀 最新更新

- **2025-11-14**: 修复推送格式化字段名映射问题
- **2025-11-14**: 实现智能格式识别逻辑，支持中英文键名
- **2025-11-14**: 完成提示词文件管理系统

## 📚 相关文档

- 主文档：`/Users/chenchiyuan/projects/crypto_exchange_news_crawler/README.md`
- 使用指南：`/Users/chenchiyuan/projects/crypto_exchange_news_crawler/USAGE_GUIDE.md`
- 快速开始：`/Users/chenchiyuan/projects/crypto_exchange_news_crawler/QUICKSTART.md`

---
最后更新：2025-11-14
