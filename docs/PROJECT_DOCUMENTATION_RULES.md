# 项目文档管理规则

## 📋 文档存放规范

### 核心原则

**所有Markdown文档必须存放在 `docs/` 目录下**

---

## 📁 目录结构

```
crypto_exchange_news_crawler/
├── docs/                          # 📚 所有文档集中存放
│   ├── README.md                  # 项目总览
│   ├── archive/                   # 📦 已废弃/历史文档归档
│   ├── twitter/                   # 🐦 Twitter相关子文档
│   │
│   ├── SCREENING_*.md             # 筛选系统相关
│   ├── GRID_*.md                  # 网格交易相关
│   ├── VP_*.md                    # 成交量价格分析相关
│   ├── TWITTER_*.md               # Twitter监控相关
│   ├── *_GUIDE.md                 # 各类使用指南
│   └── PROJECT_*.md               # 项目元信息
│
├── grid_trading/                  # 应用代码
├── specs/                         # 功能规格（保留，不移动）
└── [其他应用目录]/
```

---

## 📝 文档命名规范

### 命名格式

```
[模块]_[类型]_[简短描述].md
```

### 常用前缀

| 前缀 | 用途 | 示例 |
|------|------|------|
| `SCREENING_` | 筛选系统 | `SCREENING_QUICKSTART.md` |
| `GRID_` | 网格交易 | `GRID_PARAMETERS_EXPLAINED.md` |
| `VP_` | 成交量价格分析 | `VP_SQUEEZE_GUIDE.md` |
| `TWITTER_` | Twitter监控 | `TWITTER_FILTER_GUIDE.md` |
| `PROJECT_` | 项目元信息 | `PROJECT_OVERVIEW.md` |
| `*_GUIDE` | 使用指南 | `USAGE_GUIDE.md` |
| `*_API` | API文档 | `WEB_BACKTEST_API_GUIDE.md` |

### 特殊文档

| 文档名 | 用途 |
|--------|------|
| `README.md` | 项目总入口，位于 `docs/` 根目录 |
| `CHANGELOG.md` | 版本变更记录（如需要） |
| `CONTRIBUTING.md` | 贡献指南（开源项目） |

---

## ✅ 文档检查清单

在创建/修改文档时，请确保：

### 1. 位置检查
- [ ] 文档已存放在 `docs/` 目录
- [ ] 如果是子模块文档，已放在对应子目录（如 `docs/twitter/`）
- [ ] 不在代码目录（如 `grid_trading/`）中创建.md文件（README.md除外）

### 2. 命名检查
- [ ] 文件名使用全大写或驼峰命名
- [ ] 文件名具有描述性，能反映文档内容
- [ ] 如属于特定模块，已添加前缀

### 3. 内容检查
- [ ] 包含清晰的标题和概述
- [ ] 包含更新日期
- [ ] 代码示例完整可运行
- [ ] 链接指向正确（相对路径）

### 4. 索引更新
- [ ] 已在 `docs/README.md` 中添加链接（如果是重要文档）
- [ ] 已添加到相关文档的"相关文档"章节

---

## 🔍 检查现有文档

### 手动检查命令

```bash
# 查找所有不在docs目录的.md文件（排除node_modules和venv）
find . -name "*.md" -type f \
  | grep -v "/venv/" \
  | grep -v "/node_modules/" \
  | grep -v "/docs/" \
  | grep -v "/specs/"  # specs保留，不移动
```

### 自动检查脚本

```bash
#!/bin/bash
# 文件: scripts/check_docs.sh

echo "📚 检查文档位置规范..."
echo ""

# 查找不在docs目录的.md文件
misplaced_docs=$(find . -name "*.md" -type f \
  | grep -v "/venv/" \
  | grep -v "/node_modules/" \
  | grep -v "/docs/" \
  | grep -v "/specs/" \
  | grep -v "README.md$")  # 允许各模块有README

if [ -z "$misplaced_docs" ]; then
  echo "✅ 所有文档位置符合规范"
else
  echo "⚠️ 发现以下文档不在docs目录:"
  echo "$misplaced_docs"
  echo ""
  echo "建议: 将这些文档移动到 docs/ 目录"
fi
```

---

## 🗂️ 文档归档规则

### 何时归档

文档满足以下条件之一时，应移入 `docs/archive/`:

1. **已废弃**: 功能已删除或重构
2. **过时**: 内容已不再适用
3. **重复**: 已被新文档替代
4. **实验性**: 未采纳的方案记录

### 归档方法

```bash
# 移动到归档目录
mv docs/OLD_DOCUMENT.md docs/archive/

# 在原位置创建重定向（可选）
echo "此文档已归档，请查看 [归档版本](./archive/OLD_DOCUMENT.md)" > docs/OLD_DOCUMENT.md
```

### 归档后处理

- [ ] 从 `docs/README.md` 移除索引
- [ ] 在归档文件顶部添加归档原因
- [ ] 如有替代文档，添加跳转链接

---

## 📚 文档模板

### 标准文档模板

```markdown
# [文档标题]

## 📋 概述

简短描述文档内容（2-3句话）

**创建日期**: YYYY-MM-DD
**最后更新**: YYYY-MM-DD
**相关模块**: [模块名称]

---

## 🎯 [章节1标题]

内容...

---

## 📝 更新日志

| 日期 | 版本 | 变更内容 |
|------|------|----------|
| YYYY-MM-DD | v1.0 | 初始版本 |

---

## 📚 相关文档

- [相关文档1](./RELATED_DOC1.md)
- [相关文档2](./RELATED_DOC2.md)

---

**文档维护**: [维护者名称]
**最后更新**: YYYY-MM-DD
```

---

## 🔗 文档互联

### 原则

1. **双向链接**: 相关文档应相互引用
2. **分层索引**:
   - `docs/README.md` → 主要文档
   - 主要文档 → 详细文档
3. **相对路径**: 使用相对路径，方便迁移

### 示例

```markdown
## 相关文档

### 上游文档（概述性）
- [项目总览](./PROJECT_OVERVIEW.md)
- [使用指南](./USAGE_GUIDE.md)

### 平级文档（相关主题）
- [网格参数详解](./GRID_PARAMETERS_EXPLAINED.md)
- [回测系统指南](./BACKTEST_SYSTEM_GUIDE.md)

### 下游文档（详细实现）
- [API接口文档](./WEB_BACKTEST_API_GUIDE.md)
- [数据模型设计](./specs/002-futures-data-monitor/data-model.md)
```

---

## ⚠️ 特殊情况处理

### specs/ 目录

**保留原有结构**，不移动到docs/:
```
specs/                     # 功能规格目录
├── 001-listing-monitor/   # 特定功能的完整规格
│   ├── spec.md
│   ├── plan.md
│   └── tasks.md
└── GRID_V4_IMPLEMENTATION_PLAN.md
```

**原因**:
- specs/ 是功能开发的完整生命周期记录
- 包含规格、计划、任务、检查清单等
- 与 `docs/` 的"用户文档"定位不同

### 各模块的 README.md

**允许**在各应用目录保留 `README.md`:
```
grid_trading/
├── README.md          # ✅ 允许：模块说明
├── models.py
└── ...

twitter/
├── README.md          # ✅ 允许：模块说明
├── models.py
└── ...
```

**但**其他.md文档应移动到 `docs/`:
```
❌ grid_trading/GUIDE.md  → ✅ docs/GRID_TRADING_GUIDE.md
❌ twitter/SETUP.md       → ✅ docs/TWITTER_SETUP.md
```

---

## 📊 当前文档统计

### 最近检查

**检查日期**: 2024-12-04

**docs/ 目录**:
- 总文档数: 43个
- 归档文档: 1个子目录
- 子目录: twitter/ (14个文档)

**待处理**:
- ✅ 所有主要文档已在 docs/
- ✅ specs/ 保持独立
- ✅ 新增文档符合规范

---

## 🔄 维护流程

### 新增文档

1. 在 `docs/` 创建文档
2. 遵循命名规范
3. 使用文档模板
4. 更新 `docs/README.md` 索引
5. 添加到相关文档的链接

### 更新文档

1. 修改文档内容
2. 更新"最后更新"日期
3. 在"更新日志"添加记录
4. 检查所有链接是否有效

### 归档文档

1. 移动到 `docs/archive/`
2. 添加归档原因说明
3. 从索引中移除
4. 如有替代，添加跳转

---

## 📝 更新日志

| 日期 | 版本 | 变更内容 |
|------|------|----------|
| 2024-12-04 | v1.0 | 初始版本：建立文档管理规范 |

---

**文档维护**: Claude Code
**最后更新**: 2024-12-04
