# Quickstart Guide: Market Cap & FDV Display Integration

**Feature**: 008-marketcap-fdv-display
**Date**: 2025-12-12
**Audience**: 开发者、运维人员

## Overview

本指南帮助你快速完成市值/FDV展示功能的初始化、配置和验证。预计耗时: **20-30分钟**。

**前置条件**:
- Python 3.12+ 已安装
- Django 4.2.8 项目已就绪
- CoinGecko API密钥(免费版即可)
- 币安API密钥(现有)

---

## Step 1: 环境配置

### 1.1 安装依赖

在项目根目录下,更新`requirements.txt`:

```bash
# 编辑 requirements.txt
echo "tenacity>=8.2.0  # API重试库" >> requirements.txt

# 安装依赖
pip install -r requirements.txt
```

**验证安装**:
```bash
python -c "import tenacity; print(f'tenacity {tenacity.__version__} installed')"
```

### 1.2 配置环境变量

创建或编辑 `.env` 文件:

```bash
# CoinGecko API配置
COINGECKO_API_KEY=your_api_key_here

# (可选) 如果项目中没有,添加币安API密钥
BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_api_secret
```

**获取CoinGecko API密钥**:
1. 访问 https://www.coingecko.com/en/api
2. 注册免费账户
3. 在Dashboard中获取API密钥

**验证环境变量**:
```bash
python manage.py shell -c "
from django.conf import settings
import os

api_key = os.environ.get('COINGECKO_API_KEY')
print(f'CoinGecko API Key: {api_key[:10]}...' if api_key else 'NOT SET')
"
```

### 1.3 配置Django Settings

编辑 `listing_monitor_project/settings.py`:

```python
import environ

# 初始化environ
env = environ.Env()
environ.Env.read_env()  # 读取.env文件

# CoinGecko配置
COINGECKO_API_KEY = env('COINGECKO_API_KEY', default='')

# (可选) 如果项目中没有,添加币安配置
BINANCE_API_KEY = env('BINANCE_API_KEY', default='')
BINANCE_API_SECRET = env('BINANCE_API_SECRET', default='')
```

---

## Step 2: 数据库迁移

### 2.1 生成迁移文件

```bash
python manage.py makemigrations grid_trading --name add_market_cap_fdv
```

**预期输出**:
```
Migrations for 'grid_trading':
  grid_trading/migrations/00XX_add_market_cap_fdv.py
    - Create model TokenMapping
    - Create model MarketData
    - Create model UpdateLog
    - Add index token_mapping_symbol_idx on field(s) symbol of model tokenmapping
    - Add index token_mapping_status_idx on field(s) match_status of model tokenmapping
    - Add index market_data_symbol_idx on field(s) symbol of model marketdata
    - Add index market_data_updated_idx on field(s) updated_at of model marketdata
    - Add index update_log_batch_idx on field(s) batch_id of model updatelog
    - Add index update_log_op_status_idx on field(s) operation_type, status of model updatelog
```

### 2.2 执行迁移

```bash
python manage.py migrate grid_trading
```

**预期输出**:
```
Operations to perform:
  Apply all migrations: grid_trading
Running migrations:
  Applying grid_trading.00XX_add_market_cap_fdv... OK
```

### 2.3 验证表创建

```bash
# SQLite
python manage.py dbshell
.tables  # 应该看到: token_mapping, market_data, update_log

# PostgreSQL
python manage.py dbshell
\dt  # 应该看到3个新表
```

---

## Step 3: 生成映射关系

### 3.1 运行映射脚本

```bash
python manage.py generate_token_mapping
```

**预期输出**:
```
[INFO] Fetching Binance USDT perpetual contracts...
[INFO] Found 531 USDT perpetual contracts
[INFO] Fetching CoinGecko coins list...
[INFO] Found 14523 coins in CoinGecko
[INFO] Matching symbols...
[INFO] Auto-matched BTCUSDT by volume: bitcoin
[INFO] Auto-matched ETHUSDT by volume: ethereum
[INFO] Auto-matched SOLUSDT by volume: solana
...
[WARNING] Multiple matches for MON: 2 candidates
[INFO] Auto-matched MONUSDT by rank: mon-protocol
...
[WARNING] Cannot auto-match XYZ, marking as needs_review
[INFO] Mapping generation completed
[INFO] Statistics:
  - Total: 531
  - Auto-matched: 485 (91.3%)
  - Needs review: 46 (8.7%)
```

### 3.2 查看映射结果

```bash
python manage.py shell -c "
from grid_trading.models import TokenMapping

# 统计信息
total = TokenMapping.objects.count()
auto_matched = TokenMapping.objects.filter(match_status='auto_matched').count()
needs_review = TokenMapping.objects.filter(match_status='needs_review').count()

print(f'Total mappings: {total}')
print(f'Auto-matched: {auto_matched} ({auto_matched/total*100:.1f}%)')
print(f'Needs review: {needs_review} ({needs_review/total*100:.1f}%)')

# 查看需要审核的前5个
print('\nNeeds review (top 5):')
for mapping in TokenMapping.objects.filter(match_status='needs_review')[:5]:
    print(f'  {mapping.symbol} ({mapping.base_token}): {mapping.alternatives}')
"
```

### 3.3 (可选) 人工审核映射

如果有`needs_review`状态的映射,使用Django Admin进行审核:

```bash
# 启动开发服务器
python manage.py runserver

# 访问 http://127.0.0.1:8000/admin/grid_trading/tokenmapping/
# 筛选 match_status = needs_review
# 从alternatives中选择正确的CoinGecko ID
# 修改coingecko_id字段
# 将match_status改为 manual_confirmed
# 保存
```

---

## Step 4: 首次数据更新

### 4.1 运行数据更新脚本

```bash
python manage.py update_market_data
```

**预期输出**:
```
[INFO] Loading mappings...
[INFO] Found 485 mappings ready for update
[INFO] Fetching market data from CoinGecko...
[INFO] Processing batch 1/2 (250 coins)...
[INFO] Processed batch 1, waiting 60s...
[INFO] Processing batch 2/2 (235 coins)...
[INFO] Updating database...
[INFO] Successfully updated: 480/485 (99.0%)
[INFO] Failed: 5 (XYZUSDT, ABCUSDT, ...)
[INFO] Market data update completed in 185.3 seconds
```

### 4.2 验证数据

```bash
python manage.py shell -c "
from grid_trading.models import MarketData

# 统计信息
total = MarketData.objects.count()
with_mc = MarketData.objects.filter(market_cap__isnull=False).count()
with_fdv = MarketData.objects.filter(fully_diluted_valuation__isnull=False).count()

print(f'Total market data records: {total}')
print(f'With market cap: {with_mc} ({with_mc/total*100:.1f}%)')
print(f'With FDV: {with_fdv} ({with_fdv/total*100:.1f}%)')

# 查看示例数据
print('\nSample data (top 5):')
for data in MarketData.objects.all()[:5]:
    print(f'  {data.symbol}: MC={data.market_cap_formatted}, FDV={data.fdv_formatted}')
"
```

### 4.3 检查更新日志

```bash
python manage.py shell -c "
from grid_trading.models import UpdateLog

# 查看最近的批次
latest = UpdateLog.objects.filter(operation_type='data_fetch').order_by('-executed_at').first()
print(f'Latest update: {latest.executed_at}')
print(f'Status: {latest.get_status_display()}')
print(f'Metadata: {latest.metadata}')

# 查看失败的symbol
failed = UpdateLog.objects.filter(
    operation_type='data_fetch',
    status='failure',
    symbol__isnull=False
).values_list('symbol', 'error_message')[:5]

print('\nFailed symbols (top 5):')
for symbol, error in failed:
    print(f'  {symbol}: {error[:50]}...')
"
```

---

## Step 5: 前端展示验证

### 5.1 启动开发服务器

```bash
python manage.py runserver
```

### 5.2 访问筛选页面

打开浏览器访问: http://127.0.0.1:8000/screening/daily/

**预期结果**:
- 列表页面增加了"市值"和"FDV"两列
- 数值以K/M/B格式显示(如: $1.23T, $456.78M)
- 有数据的合约显示具体数值
- 无数据的合约显示"-"
- 鼠标悬停显示数据更新时间

### 5.3 测试排序功能

点击"市值"或"FDV"列标题:
- 第一次点击: 降序排列(高到低)
- 第二次点击: 升序排列(低到高)
- 显示"-"的行排在最后

---

## Step 6: 配置定时任务

### 6.1 创建Cron脚本

创建 `scripts/cron_update_market_data.sh`:

```bash
#!/bin/bash
set -e

# 日志文件
LOG_FILE="/var/log/market_data_update.log"

# 激活虚拟环境
source /path/to/venv/bin/activate

# 进入项目目录
cd /path/to/crypto_exchange_news_crawler

# 记录开始时间
echo "=== Market Data Update Start: $(date) ===" >> "$LOG_FILE"

# 同步币安合约列表(检测新合约)
echo "Syncing Binance contracts..." >> "$LOG_FILE"
python manage.py sync_binance_contracts >> "$LOG_FILE" 2>&1

# 更新市值/FDV数据
echo "Updating market data..." >> "$LOG_FILE"
python manage.py update_market_data >> "$LOG_FILE" 2>&1

# 检查退出状态
if [ $? -eq 0 ]; then
    echo "=== Market Data Update Success: $(date) ===" >> "$LOG_FILE"
else
    echo "=== Market Data Update Failed: $(date) ===" >> "$LOG_FILE"
    # 可选: 发送告警通知
    # curl -X POST "YOUR_NOTIFICATION_URL" -d "Market data update failed"
fi
```

### 6.2 赋予执行权限

```bash
chmod +x scripts/cron_update_market_data.sh
```

### 6.3 配置Crontab

```bash
# 编辑crontab
crontab -e

# 添加以下行(每日凌晨4点执行)
0 4 * * * /path/to/crypto_exchange_news_crawler/scripts/cron_update_market_data.sh
```

**验证Crontab**:
```bash
crontab -l | grep market_data
```

### 6.4 测试Cron脚本

手动执行一次验证:

```bash
./scripts/cron_update_market_data.sh

# 查看日志
tail -f /var/log/market_data_update.log
```

---

## Step 7: 监控与告警

### 7.1 监控指标

创建监控查询脚本 `scripts/monitor_market_data.py`:

```python
#!/usr/bin/env python
import django
import os
import sys
from datetime import timedelta

# Django setup
sys.path.append('/path/to/crypto_exchange_news_crawler')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')
django.setup()

from django.utils import timezone
from grid_trading.models import TokenMapping, MarketData, UpdateLog

# 计算指标
total_mappings = TokenMapping.objects.count()
ready_mappings = TokenMapping.objects.filter(
    match_status__in=['auto_matched', 'manual_confirmed']
).count()

total_market_data = MarketData.objects.count()
coverage_rate = total_market_data / total_mappings * 100 if total_mappings > 0 else 0

# 最近24小时的更新成功率
yesterday = timezone.now() - timedelta(hours=24)
recent_updates = UpdateLog.objects.filter(
    operation_type='data_fetch',
    executed_at__gte=yesterday
)

total_updates = recent_updates.count()
successful_updates = recent_updates.filter(status='success').count()
success_rate = successful_updates / total_updates * 100 if total_updates > 0 else 0

# 输出结果
print("=== Market Data Monitoring ===")
print(f"Total mappings: {total_mappings}")
print(f"Ready for update: {ready_mappings} ({ready_mappings/total_mappings*100:.1f}%)")
print(f"Market data coverage: {total_market_data}/{total_mappings} ({coverage_rate:.1f}%)")
print(f"Recent update success rate: {successful_updates}/{total_updates} ({success_rate:.1f}%)")

# 告警检查
alerts = []

if coverage_rate < 90:
    alerts.append(f"ALERT: Coverage rate below 90% (current: {coverage_rate:.1f}%)")

if success_rate < 95 and total_updates > 0:
    alerts.append(f"ALERT: Update success rate below 95% (current: {success_rate:.1f}%)")

if alerts:
    print("\n=== ALERTS ===")
    for alert in alerts:
        print(alert)
else:
    print("\nAll metrics within thresholds ✅")
```

### 7.2 添加监控到Cron

```bash
# 编辑crontab
crontab -e

# 添加每小时检查(可选)
0 * * * * /path/to/venv/bin/python /path/to/scripts/monitor_market_data.py
```

---

## Troubleshooting

### 问题1: CoinGecko API限流

**症状**: 日志中出现大量429错误

**解决方案**:
1. 检查批次间延迟是否足够(默认60秒)
2. 减少每批的coin数量(从250降到100)
3. 考虑升级CoinGecko API计划

### 问题2: 映射准确率低(<85%)

**症状**: 大量`needs_review`状态的映射

**解决方案**:
1. 检查CoinGecko `/coins/markets`返回的交易量和排名数据
2. 手动审核并确认前20个高市值合约的映射
3. 调整消歧逻辑中的交易量阈值(当前是2倍)

### 问题3: 前端加载慢

**症状**: 页面加载时间超过2秒

**解决方案**:
1. 检查数据库索引是否正确创建:
   ```sql
   SELECT indexname FROM pg_indexes WHERE tablename = 'market_data';
   ```
2. 添加数据库查询日志,查找慢查询
3. 考虑使用`select_related`优化查询

### 问题4: 数据更新失败

**症状**: UpdateLog显示大量失败记录

**解决方案**:
1. 检查CoinGecko API密钥是否有效
2. 检查网络连接和防火墙设置
3. 查看失败symbol的具体错误信息:
   ```bash
   python manage.py shell -c "
   from grid_trading.models import UpdateLog
   failed = UpdateLog.objects.filter(status='failure').order_by('-executed_at')[:10]
   for log in failed:
       print(f'{log.symbol}: {log.error_message}')
   "
   ```

---

## Next Steps

完成快速开始后,你可以:

1. **优化性能**: 根据实际数据量调整批次大小和延迟时间
2. **扩展功能**: 添加更多CoinGecko数据(24h交易量、市值排名等)
3. **增强监控**: 集成到现有的监控系统(Prometheus、Grafana等)
4. **自动化运维**: 添加告警通知到Slack/Email/企业微信

---

## Useful Commands Reference

```bash
# 数据管理
python manage.py generate_token_mapping  # 生成映射关系
python manage.py update_market_data      # 更新市值/FDV数据
python manage.py sync_binance_contracts  # 同步币安合约列表

# 数据库操作
python manage.py makemigrations          # 生成迁移文件
python manage.py migrate                 # 执行迁移
python manage.py dbshell                 # 进入数据库Shell

# 开发调试
python manage.py shell                   # 进入Django Shell
python manage.py runserver               # 启动开发服务器
python manage.py test grid_trading       # 运行测试

# 监控维护
tail -f /var/log/market_data_update.log  # 查看更新日志
crontab -l                               # 查看定时任务
./scripts/monitor_market_data.py         # 检查监控指标
```

---

**Quickstart Guide Prepared by**: Claude Code
**Last Updated**: 2025-12-12
**Estimated Setup Time**: 20-30 minutes
