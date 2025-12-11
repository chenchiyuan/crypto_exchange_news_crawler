# 筛选命令迁移指南

## 🎯 快速迁移

### 旧命令已废弃

从现在开始，请使用新的统一命令 `screen_contracts` 替代：
- ❌ ~~`screen_simple`~~ (已废弃)
- ❌ ~~`screen_by_date`~~ (已废弃)
- ✅ `screen_contracts` (推荐)

---

## 📋 迁移对照表

### 从 screen_simple 迁移

| 旧命令 | 新命令 | 说明 |
|--------|--------|------|
| `python manage.py screen_simple` | `python manage.py screen_contracts` | 实时筛选 |
| `python manage.py screen_simple --min-vdr 10` | `python manage.py screen_contracts --min-vdr 10` | 带过滤条件 |
| `python manage.py screen_simple --vdr-weight 0.5` | `python manage.py screen_contracts --vdr-weight 0.5` | 自定义权重 |
| `python manage.py screen_simple --output report.html` | `python manage.py screen_contracts --output report.html` | 自定义输出 |

⚠️ **注意**: `screen_contracts`的默认`min-volume`为5000000，如需与`screen_simple`的行为一致（不限制），请显式指定：
```bash
python manage.py screen_contracts --min-volume 0
```

### 从 screen_by_date 迁移

| 旧命令 | 新命令 | 说明 |
|--------|--------|------|
| `python manage.py screen_by_date --date 2024-12-10` | `python manage.py screen_contracts --date 2024-12-10` | 单日筛选 |
| `python manage.py screen_by_date --from-date 2024-12-01 --to-date 2024-12-10` | `python manage.py screen_contracts --from-date 2024-12-01 --to-date 2024-12-10` | 批量筛选 |
| `python manage.py screen_by_date --no-html` | `python manage.py screen_contracts --no-html` | 不生成HTML |

✅ **完全兼容**: 所有`screen_by_date`的参数都被`screen_contracts`完整支持。

---

## 🆕 新增功能

`screen_contracts` 除了整合旧命令的所有功能外，还新增了：

1. **实时筛选模式** (原`screen_by_date`不支持)
   ```bash
   python manage.py screen_contracts
   ```

2. **可自定义截止时间** (默认10点)
   ```bash
   python manage.py screen_contracts --date 2024-12-10 --cutoff-hour 12
   ```

3. **统一的参数体系**
   - 所有模式共享相同的参数
   - 更清晰的命令语义

---

## 📝 常见场景

### 场景1: 日常定时任务

**旧做法**:
```bash
# crontab 每天10:30执行
30 10 * * * cd /path/to/project && python manage.py screen_by_date
```

**新做法**:
```bash
# 使用新命令（功能完全一致）
30 10 * * * cd /path/to/project && python manage.py screen_contracts --date $(date +\%Y-\%m-\%d)
```

### 场景2: 回填历史数据

**旧做法**:
```bash
python manage.py screen_by_date --from-date 2024-12-01 --to-date 2024-12-10
```

**新做法**:
```bash
python manage.py screen_contracts --from-date 2024-12-01 --to-date 2024-12-10
```

### 场景3: 快速筛选测试

**旧做法**:
```bash
python manage.py screen_simple --min-vdr 999
```

**新做法**:
```bash
python manage.py screen_contracts --min-vdr 999 --no-html
```

---

## ⏰ 迁移时间表

| 时间节点 | 说明 |
|---------|------|
| **2025-12-10** | `screen_contracts`正式发布 |
| **2025-12-10 至今** | 旧命令标记废弃，但仍可用 |
| **3个月后** | 计划删除旧命令 |

**建议**: 尽快迁移到新命令，避免未来的兼容性问题。

---

## 🔍 检查旧命令使用

### 查找项目中的旧命令

```bash
# 搜索所有使用旧命令的地方
grep -r "screen_simple" .
grep -r "screen_by_date" .
```

### 查找crontab中的旧命令

```bash
# 查看当前用户的定时任务
crontab -l | grep -E "screen_simple|screen_by_date"
```

---

## ❓ 常见问题

### Q1: 旧命令还能用吗？

**A**: 能用，但会显示黄色废弃警告。建议尽快迁移。

### Q2: 数据库数据会受影响吗？

**A**: 不会。新命令保存的数据结构与旧命令完全一致，可以在同一数据库中混合查询。

### Q3: 我的脚本需要改动吗？

**A**: 只需要将命令名改为`screen_contracts`，参数保持不变即可。

### Q4: 新命令的性能如何？

**A**: 与旧命令完全一致，因为底层使用相同的筛选引擎。

### Q5: 如何验证迁移是否正确？

**A**: 运行以下命令验证：
```bash
# 验证help信息
python manage.py screen_contracts --help

# 运行快速测试
python manage.py screen_contracts --no-html --min-vdr 999 -v 0
```

---

## 📞 获取帮助

如有任何问题，请：

1. 查看完整文档: [SCREENING_UNIFICATION_COMPLETION.md](./SCREENING_UNIFICATION_COMPLETION.md)
2. 查看方案设计: [SCREENING_UNIFICATION_SOLUTION.md](./SCREENING_UNIFICATION_SOLUTION.md)
3. 运行帮助命令: `python manage.py screen_contracts --help`

---

**更新日期**: 2025-12-10
**维护者**: 加密货币网格交易系统开发团队
