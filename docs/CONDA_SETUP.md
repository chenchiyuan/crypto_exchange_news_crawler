# Conda环境管理指南

本文档说明如何使用Conda管理项目Python环境和依赖。

## 📋 目录

- [为什么使用Conda](#为什么使用conda)
- [安装Miniconda/Anaconda](#安装minicondaanaconda)
- [创建项目环境](#创建项目环境)
- [激活和使用环境](#激活和使用环境)
- [管理依赖](#管理依赖)
- [配置定时任务](#配置定时任务)
- [常见问题](#常见问题)
- [从Virtualenv迁移](#从virtualenv迁移)

---

## 为什么使用Conda

### Conda vs Pip+Virtualenv

| 特性 | Conda | Pip+Virtualenv |
|------|-------|----------------|
| **包管理** | Python + 系统包 | 仅Python包 |
| **依赖解决** | 智能解析，避免冲突 | 需手动处理 |
| **环境隔离** | 完全隔离（包括系统库） | Python隔离 |
| **跨平台** | 统一管理 | 可能需要额外配置 |
| **性能** | 优化的二进制包 | 需编译部分包 |

### 项目优势

✅ **统一管理**: 一个environment.yml管理所有依赖
✅ **跨平台**: Mac/Linux/Windows统一配置
✅ **版本锁定**: 精确控制包版本
✅ **快速部署**: 一条命令创建完整环境
✅ **团队协作**: 确保团队环境一致

---

## 安装Miniconda/Anaconda

### 选择版本

- **Miniconda** (推荐): 轻量版，仅包含conda、Python和基础包
- **Anaconda**: 完整版，包含150+科学计算包

### 安装Miniconda

**Mac/Linux**:
```bash
# 下载安装脚本
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh  # Mac M1/M2
# 或
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh  # Linux

# 运行安装
bash Miniconda3-latest-*.sh

# 按提示操作：
# - 阅读许可协议（按空格快速翻页）
# - 输入 yes 接受
# - 确认安装路径（默认 ~/miniconda3）
# - 选择是否初始化conda（推荐选 yes）
```

**验证安装**:
```bash
# 重启终端或执行
source ~/.bashrc  # Linux
# 或
source ~/.zshrc   # Mac

# 验证
conda --version
# 应输出: conda 24.x.x
```

---

## 创建项目环境

### 从environment.yml创建（推荐）

```bash
# 1. 进入项目目录
cd /path/to/crypto_exchange_news_crawler

# 2. 创建环境
conda env create -f environment.yml

# 这会：
# - 创建名为 crypto_exchange_monitor 的环境
# - 安装 Python 3.12
# - 安装所有项目依赖
```

### 手动创建环境

```bash
# 创建指定Python版本的环境
conda create -n crypto_exchange_monitor python=3.12

# 激活环境
conda activate crypto_exchange_monitor

# 安装依赖
conda install django=4.2.8 scrapy requests pyyaml tenacity
pip install scrapy-playwright ratelimit
```

---

## 激活和使用环境

### 激活环境

```bash
# 激活项目环境
conda activate crypto_exchange_monitor

# 提示符会变为
(crypto_exchange_monitor) user@host:~$
```

### 退出环境

```bash
# 退出当前环境
conda deactivate
```

### 验证环境

```bash
# 查看当前环境
conda info --envs
# 或
conda env list

# 应该看到：
# crypto_exchange_monitor  *  /path/to/miniconda3/envs/crypto_exchange_monitor

# 查看已安装的包
conda list

# 检查Python版本
python --version
```

---

## 管理依赖

### 查看依赖

```bash
# 激活环境
conda activate crypto_exchange_monitor

# 查看所有包
conda list

# 搜索特定包
conda list django
```

### 安装新依赖

```bash
# Conda安装（优先）
conda install package_name

# Pip安装（conda没有的包）
pip install package_name

# 安装后更新environment.yml
conda env export > environment_updated.yml
# 手动整理后替换 environment.yml
```

### 更新依赖

```bash
# 更新单个包
conda update django

# 更新所有包
conda update --all

# 从environment.yml更新
conda env update -f environment.yml --prune
```

### 删除依赖

```bash
# 删除包
conda remove package_name

# 更新environment.yml
# （手动编辑 environment.yml 移除相应行）
```

---

## 配置定时任务

项目的定时更新脚本已经支持自动检测Conda环境！

### 使用Cron（Mac/Linux）

```bash
# 1. 确保环境已创建
conda env list | grep crypto_exchange_monitor

# 2. 运行配置脚本
./scripts/setup_cron.sh

# 脚本会自动：
# ✓ 检测Conda环境
# ✓ 使用 conda run 命令
# ✓ 配置正确的执行路径
```

### 使用Systemd（Linux）

```bash
# 运行配置脚本
sudo ./scripts/setup_systemd.sh

# 脚本会询问环境类型并自动配置
```

### 验证配置

```bash
# 查看cron任务
crontab -l

# 应该包含类似这样的命令：
# */10 * * * * cd /path/to/project && /path/to/conda run -n crypto_exchange_monitor python ...

# 等待10分钟后查看日志
tail -f logs/cron.log
```

---

## 常见问题

### Q1: conda命令找不到

**问题**: `bash: conda: command not found`

**解决**:
```bash
# 初始化conda
~/miniconda3/bin/conda init bash  # 或 zsh

# 重启终端
```

### Q2: 环境创建失败

**问题**: `ResolvePackageNotFound` 或 `PackagesNotFoundError`

**解决**:
```bash
# 1. 更新conda
conda update -n base conda

# 2. 清理缓存
conda clean --all

# 3. 重新创建环境
conda env create -f environment.yml --force
```

### Q3: 某个包conda没有

**问题**: 某些包只在PyPI有

**解决**:
```yaml
# 在 environment.yml 的 pip 部分添加
dependencies:
  - conda包...
  - pip:
    - pip专属包
```

### Q4: 如何在Jupyter中使用环境

```bash
# 激活环境
conda activate crypto_exchange_monitor

# 安装ipykernel
conda install ipykernel

# 注册kernel
python -m ipykernel install --user --name crypto_exchange_monitor --display-name "Python (Crypto Monitor)"

# 在Jupyter中选择这个kernel
```

### Q5: 环境太大怎么办

```bash
# 查看环境大小
du -sh ~/miniconda3/envs/crypto_exchange_monitor

# 清理不需要的包缓存
conda clean --all

# 移除不需要的包
conda remove --name crypto_exchange_monitor unused_package
```

### Q6: 如何导出精确的环境

```bash
# 导出完整环境（包含所有依赖）
conda env export > environment_full.yml

# 仅导出手动安装的包
conda env export --from-history > environment_minimal.yml
```

### Q7: Cron任务不执行

**检查路径**:
```bash
# 查看crontab
crontab -l

# 确保使用完整的conda路径
which conda
# 应该显示: /Users/yourusername/miniconda3/bin/conda

# 检查cron日志
tail -f logs/cron.log
```

### Q8: 多个项目如何管理

```bash
# 为每个项目创建独立环境
conda create -n project1 python=3.12
conda create -n project2 python=3.11

# 切换环境
conda activate project1
conda activate project2

# 查看所有环境
conda env list
```

---

## 从Virtualenv迁移

如果您之前使用virtualenv，可以这样迁移：

### 1. 导出现有依赖

```bash
# 激活旧的virtualenv
source venv/bin/activate

# 导出依赖
pip freeze > requirements_old.txt
```

### 2. 创建Conda环境

```bash
# 使用项目提供的environment.yml
conda env create -f environment.yml
```

### 3. 验证环境

```bash
# 激活Conda环境
conda activate crypto_exchange_monitor

# 测试运行
python manage.py update_futures_prices --dry-run
```

### 4. 更新定时任务

```bash
# 删除旧的cron任务
./scripts/remove_cron.sh

# 创建新的（会自动检测Conda环境）
./scripts/setup_cron.sh
```

### 5. 清理旧环境（可选）

```bash
# 备份后删除旧的venv
mv venv venv.backup
rm -rf venv.backup  # 确认无误后删除
```

---

## 环境文件说明

### environment.yml结构

```yaml
name: crypto_exchange_monitor   # 环境名称
channels:                        # 包源
  - defaults                     # Anaconda官方源
  - conda-forge                  # 社区维护源

dependencies:                    # 依赖列表
  - python=3.12                  # 固定Python版本
  - django=4.2.8                 # Conda包（精确版本）
  - scrapy>=2.11.0               # Conda包（最低版本）

  - pip                          # 包含pip工具
  - pip:                         # Pip专属包
    - scrapy-playwright>=0.0.25
    - ratelimit==2.2.1
```

### 版本约束符号

- `=` : 精确版本（`django=4.2.8`）
- `>=` : 最低版本（`scrapy>=2.11.0`）
- `<=` : 最高版本（`requests<=2.31.0`）
- `==` : Pip精确版本（`ratelimit==2.2.1`）
- 无符号 : 最新版本（`requests`）

---

## 最佳实践

### 1. 环境命名

- 使用项目名称作为环境名
- 避免使用通用名称（如`myenv`、`test`）
- 使用下划线而非连字符（`my_project` ✅ `my-project` ❌）

### 2. 依赖管理

- **优先使用Conda包**: 更稳定，依赖解析更好
- **必要时使用Pip**: 某些新包只在PyPI有
- **锁定重要版本**: Django、Scrapy等核心依赖
- **定期更新**: `conda update --all` 保持安全性

### 3. 版本控制

```bash
# 提交到Git
git add environment.yml
git commit -m "Update dependencies"

# 不要提交
# - 环境目录本身
# - __pycache__
# - conda-meta/
```

### 4. 团队协作

```bash
# 新成员加入
git clone project_repo
cd project_repo
conda env create -f environment.yml
conda activate crypto_exchange_monitor

# 依赖更新后
git pull
conda env update -f environment.yml --prune
```

### 5. 生产部署

```bash
# 在服务器上
conda env create -f environment.yml
conda activate crypto_exchange_monitor

# 配置定时任务
sudo ./scripts/setup_cron.sh
# 或
sudo ./scripts/setup_systemd.sh
```

---

## 高级技巧

### 1. 环境克隆

```bash
# 克隆现有环境
conda create --name crypto_test --clone crypto_exchange_monitor

# 用于测试新依赖而不影响原环境
```

### 2. 跨平台环境文件

```yaml
# environment.yml 可以包含平台特定配置
dependencies:
  - python=3.12
  - django=4.2.8
  - sel(linux): gcc_linux-64  # 仅Linux
  - sel(osx): clang_osx-64    # 仅Mac
```

### 3. 多环境配置

```bash
# 开发环境
conda env create -f environment.yml

# 测试环境（更严格）
conda env create -f environment.test.yml

# 生产环境（最小化）
conda env create -f environment.prod.yml
```

### 4. 自动激活

```bash
# 进入目录自动激活环境
# 在 ~/.bashrc 或 ~/.zshrc 添加：

function cd() {
    builtin cd "$@"
    if [ -f "environment.yml" ]; then
        ENV_NAME=$(grep "^name:" environment.yml | awk '{print $2}')
        if conda env list | grep -q "^$ENV_NAME "; then
            conda activate $ENV_NAME
        fi
    fi
}
```

---

## 相关命令速查

```bash
# 环境管理
conda env list                  # 列出所有环境
conda create -n NAME python=X   # 创建新环境
conda activate NAME             # 激活环境
conda deactivate                # 退出环境
conda env remove -n NAME        # 删除环境

# 包管理
conda install PACKAGE           # 安装包
conda update PACKAGE            # 更新包
conda remove PACKAGE            # 删除包
conda list                      # 列出已安装包
conda search PACKAGE            # 搜索包

# 环境导入导出
conda env export > env.yml      # 导出环境
conda env create -f env.yml     # 从文件创建
conda env update -f env.yml     # 更新环境

# 清理
conda clean --all               # 清理所有缓存
conda clean --packages          # 清理包缓存
conda clean --tarballs          # 清理压缩包

# 信息查看
conda info                      # Conda信息
conda info --envs               # 环境列表
conda --version                 # 版本信息
```

---

## 故障排查

### 日志位置

- Conda日志: `~/.conda/.logs/`
- Pip日志: `~/.pip/pip.log`

### 调试模式

```bash
# 详细输出
conda install --verbose PACKAGE

# 调试模式
conda install --debug PACKAGE
```

### 完全重置

```bash
# 删除环境
conda env remove -n crypto_exchange_monitor

# 清理缓存
conda clean --all

# 重新创建
conda env create -f environment.yml
```

---

## 技术支持

遇到问题时，请提供以下信息：

```bash
# 系统信息
uname -a

# Conda信息
conda info

# 环境信息
conda list

# 错误日志
tail -50 ~/.conda/.logs/conda.log
```

---

**相关文档**：
- [定期更新指南](SCHEDULED_UPDATES_GUIDE.md)
- [市场指标使用指南](MARKET_INDICATORS_GUIDE.md)
- [项目README](../README.md)
