# 🛠️ Scrapy 环境修复说明

## 📋 问题描述

在服务器上执行监控命令时遇到以下错误：

```bash
FileNotFoundError: [Errno 2] No such file or directory: 'scrapy'
```

**错误位置**：`monitor/services/crawler.py:78`

## 🔍 原因分析

### 1. 问题根源
- 代码中直接调用了 `scrapy` 命令
- 服务器使用 `miniconda` 环境，PATH 可能不包含 scrapy
- 当前 Python 环境已安装 scrapy，但不在系统 PATH 中

### 2. 场景示例
**服务器环境**：
- Python 路径：`/home/ubuntu/miniconda3/envs/crypto_exchange_monitor/bin/python`
- Scrapy 路径：`/home/ubuntu/miniconda3/envs/crypto_exchange_monitor/bin/scrapy`
- 但 PATH 环境变量可能不包含上述 bin 目录

**直接调用 `scrapy`**：
```bash
# 查找顺序：
# 1. 当前目录
# 2. PATH 环境变量中的目录
# 3. 找不到 scrapy → 报错
```

## ✅ 解决方案

### 修改内容
**文件**：`monitor/services/crawler.py`

**修改前**：
```python
import subprocess

cmd = ['scrapy', 'crawl', spider_name, ...]
```

**修改后**：
```python
import subprocess
import sys

cmd = [sys.executable, '-m', 'scrapy', 'crawl', spider_name, ...]
```

### 优势
1. **不依赖 PATH 环境变量**：直接使用当前 Python 解释器
2. **环境无关**：兼容 venv、conda、virtualenv 等所有虚拟环境
3. **更可靠**：确保使用当前环境的 scrapy 模块

## 🚀 验证修复

### 1. 服务器部署后测试
```bash
# 测试获取公告
python manage.py monitor --hours 48

# 预期结果：无 FileNotFoundError
# 应该看到：获取到 X 条公告
```

### 2. 本地测试
```bash
# 在本地开发环境测试
python manage.py monitor --hours 24 --skip-notification

# 应该正常工作
```

## 📝 技术细节

### 调用方式对比

| 方式 | 命令 | 优点 | 缺点 |
|------|------|------|------|
| **旧方式** | `scrapy crawl spider` | 简单 | 依赖 PATH |
| **新方式** | `python -m scrapy crawl` | 环境无关 | 命令稍长 |

### Python 模块调用原理
```bash
python -m scrapy crawl
等价于
python /path/to/scrapy/__main__.py crawl
```

系统会自动在 `sys.path` 中查找 `scrapy` 模块，并执行其 `__main__.py` 文件。

## ⚠️ 注意事项

1. **确保 scrapy 已安装**：
   ```bash
   pip install scrapy
   ```

2. **验证当前环境**：
   ```bash
   python -c "import scrapy; print(scrapy.__file__)"
   ```

3. **如果仍有问题，检查权限**：
   ```bash
   chmod +x $(which python)
   ```

## 🔄 相关文件

- **修改文件**：`monitor/services/crawler.py`
- **涉及命令**：
  - `python manage.py monitor`
  - `python manage.py daily_summary`
  - `python manage.py identify_listings`

## ✅ 修复状态

- [x] 已修复 crawler.py 中的 scrapy 调用
- [x] 已测试本地环境正常工作
- [x] 已提交到 Git 仓库
- [ ] **待服务器验证**（需要部署后测试）

---

**部署建议**：将修改后的代码推送到服务器，并重新测试监控命令。