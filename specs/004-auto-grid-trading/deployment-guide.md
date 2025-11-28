# 网格交易系统部署指南

**版本**: 1.0
**日期**: 2025-11-28
**Branch**: `004-auto-grid-trading`

---

## 目录

1. [系统概览](#系统概览)
2. [环境准备](#环境准备)
3. [数据库初始化](#数据库初始化)
4. [配置文件](#配置文件)
5. [systemd服务部署](#systemd服务部署)
6. [日志管理](#日志管理)
7. [监控和告警](#监控和告警)
8. [常见问题排查](#常见问题排查)
9. [维护操作](#维护操作)

---

## 系统概览

### 架构组件

```text
┌─────────────────────────────────────────────────────────────┐
│                    Grid Trading System                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐      ┌──────────────┐                     │
│  │   Scanner    │      │   GridBot    │                     │
│  │  (每4小时)    │      │  (每分钟)     │                     │
│  └──────┬───────┘      └──────┬───────┘                     │
│         │                     │                             │
│         └─────────┬───────────┘                             │
│                   │                                         │
│         ┌─────────▼─────────┐                               │
│         │   Database        │                               │
│         │   (GridZone,      │                               │
│         │    GridStrategy,  │                               │
│         │    GridOrder)     │                               │
│         └───────────────────┘                               │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            Django Admin 管理后台                      │   │
│  │  - 查看策略状态                                        │   │
│  │  - 查看订单记录                                        │   │
│  │  - 风险指标监控                                        │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 核心功能

- **Scanner**: 识别VP-Squeeze支撑/压力区间
- **GridBot**: 监控价格，自动启动网格交易
- **Risk Manager**: 仓位限制、止损控制
- **Order Simulator**: Paper Trading模拟撮合

### 技术栈

- Python 3.8+
- Django 4.2.8
- PostgreSQL 14+ (生产) / SQLite (开发)
- systemd (服务管理)
- logrotate (日志轮转)

---

## 环境准备

### 1. 系统要求

- **操作系统**: Ubuntu 20.04+ / Debian 11+ / CentOS 8+
- **Python**: 3.8 或以上
- **内存**: 最低 2GB RAM
- **磁盘**: 最低 10GB 可用空间

### 2. 安装依赖

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装Python 3.8+
sudo apt install python3.8 python3.8-venv python3-pip -y

# 安装PostgreSQL (生产环境推荐)
sudo apt install postgresql postgresql-contrib -y

# 安装其他工具
sudo apt install git curl wget -y
```

### 3. 创建项目用户

```bash
# 创建专用用户（可选，推荐）
sudo useradd -m -s /bin/bash gridbot
sudo usermod -aG sudo gridbot

# 切换到项目用户
sudo su - gridbot
```

### 4. 克隆项目

```bash
# 克隆仓库
cd ~
git clone https://github.com/your-org/crypto_exchange_news_crawler.git
cd crypto_exchange_news_crawler

# 切换到开发分支
git checkout 004-auto-grid-trading
```

### 5. 创建虚拟环境

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 升级pip
pip install --upgrade pip

# 安装依赖
pip install -r requirements.txt
```

---

## 数据库初始化

### 方案A: PostgreSQL (生产环境推荐)

```bash
# 1. 创建数据库
sudo -u postgres psql

postgres=# CREATE DATABASE crypto_grid_trading;
postgres=# CREATE USER gridbot_user WITH PASSWORD 'your_secure_password';
postgres=# GRANT ALL PRIVILEGES ON DATABASE crypto_grid_trading TO gridbot_user;
postgres=# \q

# 2. 配置Django settings.py
vim listing_monitor_project/settings.py

# 修改DATABASES配置:
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'crypto_grid_trading',
        'USER': 'gridbot_user',
        'PASSWORD': 'your_secure_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# 3. 运行迁移
python manage.py makemigrations grid_trading
python manage.py migrate
```

### 方案B: SQLite (开发/测试环境)

```bash
# SQLite无需额外配置，直接运行迁移
python manage.py makemigrations grid_trading
python manage.py migrate

# 数据库文件位置: db.sqlite3
```

### 创建管理员账号

```bash
# 创建superuser
python manage.py createsuperuser

# 按提示输入用户名、邮箱、密码
```

---

## 配置文件

### 1. 网格交易配置

配置文件位置: `config/grid_trading.yaml`

```yaml
# BTC默认配置
btc_default:
  symbol: BTCUSDT

  # 网格参数
  atr_multiplier: 0.8      # ATR倍数：网格步长 = ATR * 0.8
  grid_levels: 10          # 网格层数：上下各10层
  order_size_usdt: 100     # 每格金额：100 USDT

  # 风险参数
  stop_loss_pct: 0.10      # 止损百分比：10%
  max_position_usdt: 1000  # 最大仓位：1000 USDT

  # Scanner参数
  scanner_interval_hours: 4  # Scanner运行间隔：每4小时

  # GridBot参数
  check_interval_seconds: 60  # GridBot检查间隔：每60秒
```

### 2. 参数说明

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| `atr_multiplier` | ATR倍数，控制网格密度 | 0.5-1.0 (越小网格越密集) |
| `grid_levels` | 网格层数 | 5-15 (层数越多仓位越大) |
| `order_size_usdt` | 每格金额 | 50-200 USDT |
| `stop_loss_pct` | 止损百分比 | 0.08-0.15 (8%-15%) |
| `max_position_usdt` | 最大仓位 | 500-2000 USDT |

### 3. 修改配置

```bash
# 编辑配置文件
vim config/grid_trading.yaml

# 验证配置加载
python manage.py shell
>>> from grid_trading.services.config_loader import load_config
>>> config = load_config('btc')
>>> print(config)
```

---

## systemd服务部署

### 1. 修改服务文件

所有服务文件位于 `scripts/systemd/`

```bash
# 需要替换以下占位符:
# - YOUR_USERNAME: 你的用户名
# - /path/to/crypto_exchange_news_crawler: 项目绝对路径

# 批量替换（示例）
cd scripts/systemd/
sed -i 's|YOUR_USERNAME|gridbot|g' *.service
sed -i 's|/path/to/crypto_exchange_news_crawler|/home/gridbot/crypto_exchange_news_crawler|g' *.service *.timer
```

### 2. 安装服务文件

```bash
# 复制服务文件到systemd目录
sudo cp scripts/systemd/gridbot@.service /etc/systemd/system/
sudo cp scripts/systemd/scanner@.service /etc/systemd/system/
sudo cp scripts/systemd/scanner@.timer /etc/systemd/system/
sudo cp scripts/systemd/strategy-monitor@.service /etc/systemd/system/

# 重新加载systemd配置
sudo systemctl daemon-reload
```

### 3. 启动Scanner (定时任务)

```bash
# 启用并启动Scanner定时器（BTC）
sudo systemctl enable scanner@btc.timer
sudo systemctl start scanner@btc.timer

# 查看定时器状态
sudo systemctl status scanner@btc.timer

# 查看下次运行时间
systemctl list-timers scanner@*

# 手动触发一次Scanner (测试)
sudo systemctl start scanner@btc.service

# 查看Scanner日志
journalctl -u scanner@btc.service -f
# 或查看日志文件
tail -f logs/scanner_btc.log
```

### 4. 启动GridBot (守护进程)

```bash
# 启用并启动GridBot（BTC）
sudo systemctl enable gridbot@btc.service
sudo systemctl start gridbot@btc.service

# 查看GridBot状态
sudo systemctl status gridbot@btc.service

# 查看实时日志
journalctl -u gridbot@btc.service -f
# 或查看日志文件
tail -f logs/gridbot_btc.log
```

### 5. 管理多个币种

```bash
# ETH示例
sudo systemctl enable scanner@eth.timer
sudo systemctl start scanner@eth.timer

sudo systemctl enable gridbot@eth.service
sudo systemctl start gridbot@eth.service

# 查看所有网格交易服务
systemctl list-units 'gridbot@*'
systemctl list-units 'scanner@*'
```

### 6. 常用命令

```bash
# 启动服务
sudo systemctl start gridbot@btc.service

# 停止服务
sudo systemctl stop gridbot@btc.service

# 重启服务
sudo systemctl restart gridbot@btc.service

# 查看状态
sudo systemctl status gridbot@btc.service

# 查看日志
journalctl -u gridbot@btc.service -n 100  # 最近100行
journalctl -u gridbot@btc.service -f      # 实时跟踪
journalctl -u gridbot@btc.service --since "1 hour ago"

# 禁用服务
sudo systemctl disable gridbot@btc.service
```

---

## 日志管理

### 1. 日志文件位置

```text
logs/
├── grid_trading.log        # 通用日志
├── gridbot_btc.log        # GridBot BTC日志
├── gridbot_eth.log        # GridBot ETH日志
├── scanner_btc.log        # Scanner BTC日志
├── scanner_eth.log        # Scanner ETH日志
└── systemd.log            # systemd统一日志
```

### 2. 配置logrotate

```bash
# 复制logrotate配置
sudo cp scripts/logrotate/grid_trading /etc/logrotate.d/

# 修改路径和用户名
sudo vim /etc/logrotate.d/grid_trading

# 测试配置
sudo logrotate -d /etc/logrotate.d/grid_trading

# 强制执行一次轮转（测试）
sudo logrotate -f /etc/logrotate.d/grid_trading
```

### 3. 查看日志

```bash
# 查看GridBot日志
tail -f logs/gridbot_btc.log

# 查看Scanner日志
tail -f logs/scanner_btc.log

# 查看最近的错误
grep -i error logs/gridbot_btc.log | tail -20

# 查看策略创建记录
grep "策略创建成功" logs/gridbot_btc.log

# 查看止损触发记录
grep "止损触发" logs/gridbot_btc.log
```

---

## 监控和告警

### 1. 使用Django Admin

```bash
# 启动Django Admin（开发环境）
python manage.py runserver 0.0.0.0:8000

# 生产环境使用gunicorn
pip install gunicorn
gunicorn --bind 0.0.0.0:8000 listing_monitor_project.wsgi:application
```

访问 `http://your-server:8000/admin`

#### Admin功能

- **GridZone**: 查看支撑/压力区间
- **GridStrategy**: 查看策略状态、盈亏
- **GridOrder**: 查看订单记录
- **StrategyConfig**: 管理配置参数

### 2. 使用策略监控命令

```bash
# 查看所有策略状态
python manage.py strategy_monitor

# 查看BTC策略
python manage.py strategy_monitor --symbol BTCUSDT

# 只显示活跃策略
python manage.py strategy_monitor --active-only

# 输出示例:
# ==================================================================================
# 策略监控仪表板
# 时间: 2025-11-28 20:30:00
# ==================================================================================
#
# 📊 GridZone 区间状态
# ----------------------------------------------------------------------------------
#   🔻 BTCUSDT 支撑区: $49000.00 - $49500.00 (置信度:85分, 过期:23:30)
#   🔺 BTCUSDT 压力区: $51000.00 - $51500.00 (置信度:80分, 过期:23:30)
#
# 🤖 策略状态
# ----------------------------------------------------------------------------------
#   🟢 📈 Strategy #12 - BTCUSDT [运行中]
#      入场价: $49200.00  |  当前盈亏: +$25.50  |  盈亏率: +2.55%
#      仓位价值: $1000.00  |  订单: 5/20 pending  |  成交率: 75.0%
#      运行时间: 12.5小时  |  止损线: 10%
```

### 3. 健康检查脚本

```bash
# 创建健康检查脚本
cat > scripts/healthcheck.sh << 'EOF'
#!/bin/bash

echo "=== Grid Trading System Health Check ==="
echo ""

# 检查GridBot服务
echo "GridBot 服务状态:"
systemctl is-active gridbot@btc.service

# 检查Scanner定时器
echo "Scanner 定时器状态:"
systemctl is-active scanner@btc.timer

# 检查数据库连接
echo "数据库连接:"
python manage.py shell -c "from django.db import connection; connection.ensure_connection(); print('OK')"

# 检查最近的策略
echo "活跃策略数:"
python manage.py shell -c "from grid_trading.models import GridStrategy; print(GridStrategy.objects.filter(status='active').count())"

echo ""
echo "=== 检查完成 ==="
EOF

chmod +x scripts/healthcheck.sh

# 运行检查
./scripts/healthcheck.sh
```

### 4. 告警配置 (可选)

```bash
# 创建告警脚本（示例：发送邮件）
cat > scripts/alert.sh << 'EOF'
#!/bin/bash

# 检查止损触发
STOP_LOSS_COUNT=$(grep -c "止损触发" logs/gridbot_btc.log)

if [ $STOP_LOSS_COUNT -gt 0 ]; then
    echo "警告: 检测到止损触发 $STOP_LOSS_COUNT 次" | mail -s "GridBot Alert" admin@example.com
fi
EOF

# 添加到cron (每小时检查一次)
crontab -e
# 添加:
# 0 * * * * /home/gridbot/crypto_exchange_news_crawler/scripts/alert.sh
```

---

## 常见问题排查

### 1. GridBot无法启动

**症状**: `systemctl start gridbot@btc.service` 失败

**排查步骤**:

```bash
# 查看详细错误
journalctl -u gridbot@btc.service -n 50

# 常见原因:
# 1. 虚拟环境路径错误
#    解决: 检查 /etc/systemd/system/gridbot@.service 中的路径

# 2. 数据库连接失败
#    解决: python manage.py shell -c "from django.db import connection; connection.ensure_connection()"

# 3. 配置文件缺失
#    解决: ls -la config/grid_trading.yaml

# 4. 权限问题
#    解决: sudo chown -R gridbot:gridbot /home/gridbot/crypto_exchange_news_crawler
```

### 2. Scanner识别不到区间

**症状**: `GridZone.objects.filter(is_active=True).count() == 0`

**排查步骤**:

```bash
# 手动运行Scanner
python manage.py scanner --symbol btc

# 检查VP-Squeeze数据
python manage.py shell
>>> from vp_squeeze.services.four_peaks_analyzer import FourPeaksAnalyzer
>>> analyzer = FourPeaksAnalyzer()
>>> result = analyzer.analyze('BTCUSDT', '4h')
>>> print(result)

# 常见原因:
# 1. 币安API限流
#    解决: 稍后重试

# 2. 数据不足
#    解决: 确保币安有足够的K线数据

# 3. 置信度阈值过高
#    解决: 暂时降低阈值进行测试
```

### 3. 订单不成交

**症状**: 所有订单状态都是 `pending`

**排查步骤**:

```bash
# 检查GridBot是否运行
systemctl status gridbot@btc.service

# 查看GridBot日志
tail -f logs/gridbot_btc.log

# 检查价格更新
python manage.py shell
>>> from grid_trading.services.price_service import get_current_price
>>> price = get_current_price('btc')
>>> print(price)

# 常见原因:
# 1. GridBot未运行
#    解决: sudo systemctl start gridbot@btc.service

# 2. 价格未触及订单价格
#    解决: 等待或调整grid_step

# 3. API请求失败
#    解决: 检查网络连接和币安API状态
```

### 4. 止损未触发

**症状**: 价格已跌破止损线，但策略仍在运行

**排查步骤**:

```bash
# 查看策略详情
python manage.py shell
>>> from grid_trading.models import GridStrategy
>>> strategy = GridStrategy.objects.get(id=YOUR_STRATEGY_ID)
>>> print(f"Entry: {strategy.entry_price}, StopLoss: {strategy.stop_loss_pct}")

# 计算止损价格
>>> stop_loss_price = float(strategy.entry_price) * (1 - float(strategy.stop_loss_pct))
>>> print(f"止损价格: {stop_loss_price}")

# 获取当前价格
>>> from grid_trading.services.price_service import get_current_price
>>> current_price = get_current_price('btc')
>>> print(f"当前价格: {current_price}")

# 常见原因:
# 1. GridBot检查间隔过长
#    解决: 修改config/grid_trading.yaml中的check_interval_seconds

# 2. 止损逻辑未执行
#    解决: 检查logs/gridbot_btc.log是否有"检查止损"日志
```

### 5. 内存/CPU占用过高

**症状**: 服务器资源耗尽

**排查步骤**:

```bash
# 查看进程资源占用
ps aux | grep python

# 查看systemd资源限制
systemctl show gridbot@btc.service | grep -i memory
systemctl show gridbot@btc.service | grep -i cpu

# 调整资源限制
sudo vim /etc/systemd/system/gridbot@.service
# 修改:
# MemoryMax=512M  # 降低内存限制
# CPUQuota=50%    # 降低CPU配额

# 重新加载并重启
sudo systemctl daemon-reload
sudo systemctl restart gridbot@btc.service
```

---

## 维护操作

### 1. 更新代码

```bash
# 停止服务
sudo systemctl stop gridbot@btc.service
sudo systemctl stop scanner@btc.timer

# 拉取最新代码
git pull origin 004-auto-grid-trading

# 激活虚拟环境
source venv/bin/activate

# 更新依赖
pip install -r requirements.txt --upgrade

# 运行迁移
python manage.py migrate

# 重启服务
sudo systemctl start scanner@btc.timer
sudo systemctl start gridbot@btc.service

# 验证
sudo systemctl status gridbot@btc.service
```

### 2. 备份数据库

```bash
# PostgreSQL备份
sudo -u postgres pg_dump crypto_grid_trading > backup_$(date +%Y%m%d).sql

# SQLite备份
cp db.sqlite3 db.sqlite3.backup_$(date +%Y%m%d)

# 自动备份脚本
cat > scripts/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/home/gridbot/backups"
mkdir -p $BACKUP_DIR
sudo -u postgres pg_dump crypto_grid_trading | gzip > $BACKUP_DIR/db_$(date +%Y%m%d_%H%M%S).sql.gz
# 保留最近30天的备份
find $BACKUP_DIR -name "db_*.sql.gz" -mtime +30 -delete
EOF

chmod +x scripts/backup.sh

# 添加到cron (每天凌晨2点备份)
crontab -e
# 添加:
# 0 2 * * * /home/gridbot/crypto_exchange_news_crawler/scripts/backup.sh
```

### 3. 清理旧数据

```bash
# 清理过期的GridZone (30天前)
python manage.py shell
>>> from grid_trading.models import GridZone
>>> from django.utils import timezone
>>> from datetime import timedelta
>>> cutoff = timezone.now() - timedelta(days=30)
>>> GridZone.objects.filter(created_at__lt=cutoff).delete()

# 清理已停止的策略的订单 (保留最近7天)
>>> from grid_trading.models import GridStrategy, GridOrder
>>> cutoff = timezone.now() - timedelta(days=7)
>>> old_strategies = GridStrategy.objects.filter(status='stopped', stopped_at__lt=cutoff)
>>> GridOrder.objects.filter(strategy__in=old_strategies).delete()
```

### 4. 性能优化

```bash
# PostgreSQL性能优化
sudo -u postgres psql crypto_grid_trading

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_gridzone_symbol_active ON grid_trading_gridzone(symbol, is_active);
CREATE INDEX IF NOT EXISTS idx_gridstrategy_symbol_status ON grid_trading_gridstrategy(symbol, status);
CREATE INDEX IF NOT EXISTS idx_gridorder_strategy_status ON grid_trading_gridorder(strategy_id, status);

-- 分析表
ANALYZE grid_trading_gridzone;
ANALYZE grid_trading_gridstrategy;
ANALYZE grid_trading_gridorder;

-- 清理
VACUUM ANALYZE;
```

### 5. 监控磁盘空间

```bash
# 检查磁盘空间
df -h

# 检查日志大小
du -sh logs/

# 手动清理旧日志
find logs/ -name "*.log" -mtime +30 -delete

# 清理压缩日志
find logs/ -name "*.gz" -mtime +90 -delete
```

---

## 附录

### A. 完整服务管理清单

```bash
# 启动所有服务 (BTC + ETH)
sudo systemctl start scanner@btc.timer
sudo systemctl start scanner@eth.timer
sudo systemctl start gridbot@btc.service
sudo systemctl start gridbot@eth.service

# 停止所有服务
sudo systemctl stop gridbot@btc.service gridbot@eth.service
sudo systemctl stop scanner@btc.timer scanner@eth.timer

# 查看所有服务状态
systemctl status 'gridbot@*'
systemctl status 'scanner@*'
```

### B. 目录结构

```text
crypto_exchange_news_crawler/
├── config/
│   └── grid_trading.yaml          # 策略配置
├── grid_trading/                   # Django应用
│   ├── models.py                   # 数据模型
│   ├── admin.py                    # Admin界面
│   ├── management/commands/        # 管理命令
│   │   ├── scanner.py
│   │   ├── gridbot.py
│   │   └── strategy_monitor.py
│   ├── services/                   # 核心服务
│   │   ├── atr_calculator.py
│   │   ├── order_generator.py
│   │   ├── order_simulator.py
│   │   ├── price_service.py
│   │   ├── risk_manager.py
│   │   └── config_loader.py
│   └── tests/                      # 单元测试
├── logs/                           # 日志文件
├── scripts/
│   ├── systemd/                    # systemd服务文件
│   │   ├── gridbot@.service
│   │   ├── scanner@.service
│   │   └── scanner@.timer
│   ├── logrotate/                  # logrotate配置
│   │   └── grid_trading
│   ├── healthcheck.sh              # 健康检查
│   └── backup.sh                   # 备份脚本
├── specs/004-auto-grid-trading/    # 文档
│   ├── deployment-guide.md         # 本文档
│   ├── IMPLEMENTATION_PLAN.md
│   └── solution-proposal-v2.md
└── venv/                           # Python虚拟环境
```

### C. 端口和URL

- Django Admin: `http://your-server:8000/admin`
- PostgreSQL: `localhost:5432`
- 币安API: `https://api.binance.com`

### D. 联系和支持

- 项目仓库: [GitHub](https://github.com/your-org/crypto_exchange_news_crawler)
- Issue跟踪: [GitHub Issues](https://github.com/your-org/crypto_exchange_news_crawler/issues)
- 文档: `specs/004-auto-grid-trading/`

---

**最后更新**: 2025-11-28
**维护者**: Grid Trading Team
