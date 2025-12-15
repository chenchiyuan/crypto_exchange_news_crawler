# 市值/FDV数据初始化和定期更新指南

**Feature**: 008-marketcap-fdv-display  
**更新日期**: 2025-12-15

---

## 📋 快速开始

### 1. 首次初始化（生产环境）

```bash
# 初始化Token映射和市值数据
python manage.py init_market_data

# 增量导入（默认）- 不会删除现有数据
python manage.py init_market_data

# 完全重置（慎用）- 清空后重新导入
python manage.py init_market_data --reset

# 测试模式 - 不实际写入数据
python manage.py init_market_data --dry-run

# 只导入映射，不更新市值
python manage.py init_market_data --skip-update
```

**执行流程**:
1. ✅ 检查环境（API Key、数据文件）
2. ✅ 导入Token映射（355个）
3. ✅ 更新市值/FDV数据
4. ✅ 验证数据完整性

**耗时**: 约2-3分钟

---

### 2. 定期更新（配置到Crontab）

```bash
# 手动执行更新
python manage.py update_market_data_scheduled

# 静默模式（适合cron）
python manage.py update_market_data_scheduled --quiet

# 测试模式
python manage.py update_market_data_scheduled --dry-run

# 自定义日志清理天数（默认30天）
python manage.py update_market_data_scheduled --cleanup-days 60
```

---

## 🕐 配置Crontab定时任务

### 方式1: 直接编辑crontab

```bash
# 编辑crontab
crontab -e

# 添加以下任务（根据需要选择一个频率）
```

### 推荐配置选项

#### 选项A: 每天凌晨4点更新（推荐）

```cron
# 每天4:00 AM更新市值数据
0 4 * * * cd /path/to/project && /path/to/venv/bin/python manage.py update_market_data_scheduled --quiet >> logs/market_data.log 2>&1
```

#### 选项B: 每12小时更新一次

```cron
# 每天0:00和12:00更新
0 */12 * * * cd /path/to/project && /path/to/venv/bin/python manage.py update_market_data_scheduled --quiet >> logs/market_data.log 2>&1
```

#### 选项C: 每6小时更新一次

```cron
# 每6小时更新（0:00, 6:00, 12:00, 18:00）
0 */6 * * * cd /path/to/project && /path/to/venv/bin/python manage.py update_market_data_scheduled --quiet >> logs/market_data.log 2>&1
```

### 完整示例（含环境变量）

```cron
# 设置环境变量
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
DJANGO_SETTINGS_MODULE=listing_monitor_project.settings

# 每天凌晨4点更新市值数据
0 4 * * * cd /home/user/crypto_exchange_news_crawler && source venv/bin/activate && python manage.py update_market_data_scheduled --quiet >> logs/market_data_$(date +\%Y\%m\%d).log 2>&1
```

### 方式2: 使用systemd timer（推荐用于生产服务器）

创建service文件：

```bash
# /etc/systemd/system/market-data-update.service
[Unit]
Description=Update Crypto Market Data (Market Cap & FDV)
After=network.target postgresql.service

[Service]
Type=oneshot
User=www-data
WorkingDirectory=/path/to/project
Environment="DJANGO_SETTINGS_MODULE=listing_monitor_project.settings"
ExecStart=/path/to/venv/bin/python manage.py update_market_data_scheduled --quiet
StandardOutput=append:/var/log/market_data_update.log
StandardError=append:/var/log/market_data_update.log
```

创建timer文件：

```bash
# /etc/systemd/system/market-data-update.timer
[Unit]
Description=Run Market Data Update Daily at 4 AM
Requires=market-data-update.service

[Timer]
OnCalendar=daily
OnCalendar=04:00
Persistent=true

[Install]
WantedBy=timers.target
```

启用timer：

```bash
sudo systemctl daemon-reload
sudo systemctl enable market-data-update.timer
sudo systemctl start market-data-update.timer

# 查看状态
sudo systemctl status market-data-update.timer

# 查看下次执行时间
sudo systemctl list-timers market-data-update.timer
```

---

## 📊 数据文件说明

### data/token_mappings_initial.csv

**位置**: `data/token_mappings_initial.csv`  
**内容**: 355个币安合约的初始Token映射关系  
**格式**:
```csv
binance_symbol,base_asset,coingecko_id,coingecko_symbol,coingecko_name,match_status
BTCUSDT,BTC,bitcoin,,,auto_matched
ETHUSDT,ETH,ethereum,,,auto_matched
```

**重要**: 此文件已包含在项目中，无需手动创建

---

## 🔧 环境配置

### 必需配置

确保`.env`或`settings.py`中配置了CoinGecko API Key：

```bash
# .env
COINGECKO_API_KEY=CG-S9WAcfdu3ENrRmeAwP53iGj7
```

或在`settings.py`中：

```python
# settings.py
COINGECKO_API_KEY = os.getenv('COINGECKO_API_KEY', 'your-api-key-here')
```

---

## 📝 日志查看

### 命令输出日志

```bash
# 查看最新更新日志
tail -f logs/market_data.log

# 查看最近100行
tail -100 logs/market_data.log

# 搜索错误
grep "ERROR" logs/market_data.log

# 查看更新统计
grep "更新报告" logs/market_data.log -A 10
```

### Django日志

```bash
# 查看Django应用日志
tail -f logs/general.log

# 查看UpdateLog数据库记录
python manage.py shell
>>> from grid_trading.models import UpdateLog
>>> UpdateLog.objects.filter(operation_type='market_data_update').order_by('-executed_at')[:10]
```

---

## 🔍 验证和监控

### 检查数据覆盖率

```bash
python manage.py shell -c "
from grid_trading.models import TokenMapping, MarketData

mapping_count = TokenMapping.objects.count()
market_data_count = MarketData.objects.count()
coverage = (market_data_count / mapping_count * 100) if mapping_count > 0 else 0

print(f'Token映射数: {mapping_count}')
print(f'市值数据数: {market_data_count}')
print(f'覆盖率: {coverage:.1f}%')
"
```

### 检查最近更新

```bash
python manage.py shell -c "
from grid_trading.models import MarketData
from datetime import timedelta
from django.utils import timezone

recent = MarketData.objects.filter(
    fetched_at__gte=timezone.now() - timedelta(hours=24)
)

print(f'24小时内更新: {recent.count()} 个代币')
print(f'最新更新时间: {recent.order_by(\"-fetched_at\").first().fetched_at if recent.exists() else \"无\"}')
"
```

### 检查失败记录

```bash
python manage.py shell -c "
from grid_trading.models import UpdateLog

latest = UpdateLog.objects.filter(
    operation_type='market_data_update'
).order_by('-executed_at').first()

if latest:
    failed = UpdateLog.objects.filter(
        batch_id=latest.batch_id,
        status='failed'
    )
    print(f'批次ID: {latest.batch_id}')
    print(f'失败数量: {failed.count()}')
    for log in failed[:5]:
        print(f'  - {log.symbol}: {log.error_message}')
"
```

---

## 🚨 故障排查

### 问题1: 命令找不到

**错误**: `Unknown command: 'init_market_data'`

**解决**:
```bash
# 确认命令文件存在
ls grid_trading/management/commands/init_market_data.py

# 重启Django shell
python manage.py shell
```

### 问题2: API Key未配置

**错误**: `CoinGecko API Key未配置`

**解决**:
```bash
# 检查环境变量
echo $COINGECKO_API_KEY

# 或在.env文件中添加
echo "COINGECKO_API_KEY=your-key-here" >> .env
```

### 问题3: 数据文件不存在

**错误**: `Token映射文件不存在: data/token_mappings_initial.csv`

**解决**:
```bash
# 检查文件
ls data/token_mappings_initial.csv

# 如果不存在，从git拉取
git pull origin 008-marketcap-fdv-display

# 或手动导出
python manage.py shell -c "
from grid_trading.models import TokenMapping
import csv

mappings = TokenMapping.objects.all()
with open('data/token_mappings_initial.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['binance_symbol', 'base_asset', 'coingecko_id', 'coingecko_symbol', 'coingecko_name', 'match_status'])
    for m in mappings:
        writer.writerow([m.symbol, m.base_token, m.coingecko_id or '', '', '', m.match_status])
"
```

### 问题4: Cron任务未执行

**检查步骤**:
```bash
# 1. 确认cron任务已添加
crontab -l

# 2. 检查cron服务状态
sudo systemctl status cron  # Ubuntu/Debian
sudo systemctl status crond  # CentOS/RHEL

# 3. 查看cron日志
grep CRON /var/log/syslog  # Ubuntu/Debian
grep CRON /var/log/cron     # CentOS/RHEL

# 4. 测试命令路径
which python
cd /path/to/project && python manage.py update_market_data_scheduled --dry-run
```

### 问题5: 覆盖率低于90%

**检查原因**:
```bash
# 查看未更新的symbol
python manage.py shell -c "
from grid_trading.models import TokenMapping, MarketData

all_symbols = set(TokenMapping.objects.values_list('symbol', flat=True))
updated_symbols = set(MarketData.objects.values_list('symbol', flat=True))
missing = all_symbols - updated_symbols

print(f'缺失市值数据的代币: {len(missing)}')
for symbol in list(missing)[:10]:
    mapping = TokenMapping.objects.get(symbol=symbol)
    print(f'  {symbol}: coingecko_id={mapping.coingecko_id}')
"

# 手动重试更新
python manage.py update_market_data_scheduled
```

---

## 📞 支持信息

- **命令文档**: 运行 `python manage.py <command> --help`
- **Feature规格**: [specs/008-marketcap-fdv-display/](specs/008-marketcap-fdv-display/)
- **快速开始**: [specs/008-marketcap-fdv-display/quickstart.md](specs/008-marketcap-fdv-display/quickstart.md)
- **Git分支**: `008-marketcap-fdv-display`

---

**最后更新**: 2025-12-15  
**维护者**: 项目团队
