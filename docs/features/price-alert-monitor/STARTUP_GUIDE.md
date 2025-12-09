# 合约价格监控系统启动指南

**版本**: v1.0.0
**日期**: 2025-12-09
**适用环境**: 开发环境 + 生产环境

---

## 📋 目录

1. [前置准备](#前置准备)
2. [数据库初始化](#数据库初始化)
3. [系统配置](#系统配置)
4. [添加监控合约](#添加监控合约)
5. [启动监控服务](#启动监控服务)
6. [验证运行状态](#验证运行状态)
7. [常见问题](#常见问题)

---

## 🔧 前置准备

### 1. 确认环境

```bash
# 检查Python版本（需要3.12+）
python --version

# 检查Django版本（需要4.2.8+）
python -c "import django; print(django.VERSION)"

# 检查必要的包
python -c "import binance, pandas, numpy, requests; print('✓ 所有依赖已安装')"
```

### 2. 确认币安API配置

检查环境变量或配置文件中是否有币安API密钥：

```bash
# 方式1: 检查环境变量
echo $BINANCE_API_KEY
echo $BINANCE_API_SECRET

# 方式2: 检查配置文件（如果使用配置文件）
cat .env | grep BINANCE
```

**如果没有配置**，需要创建 `.env` 文件：

```bash
# 创建 .env 文件
cat > .env <<EOF
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
EOF
```

### 3. 确认筛选API可访问

```bash
# 测试筛选API是否正常
curl -s "http://localhost:8000/screening/daily/api/$(date -v-1d +%Y-%m-%d)/?min_vdr=6&min_amplitude=50&max_ma99_slope=-10&min_funding_rate=-10&min_volume=5000000" | python -m json.tool | head -20
```

如果返回JSON数据且包含 `results` 字段，说明API正常。

---

## 💾 数据库初始化

### 步骤1: 执行数据库迁移

```bash
# 查看待执行的迁移
python manage.py showmigrations grid_trading

# 执行迁移（创建价格监控相关的表）
python manage.py migrate grid_trading

# 确认迁移成功
python manage.py showmigrations grid_trading | grep "0022_create_price_monitor_models"
```

**预期输出**:
```
[X] 0022_create_price_monitor_models
```

### 步骤2: 初始化基础数据

运行Django Shell初始化5条价格触发规则和6条系统配置：

```bash
python manage.py shell <<'EOF'
from grid_trading.django_models import PriceAlertRule, SystemConfig

# 创建5条价格触发规则
rules_data = [
    {
        'rule_id': 1,
        'name': '7天价格新高(4h)',
        'description': '当前价格超过过去7天4h K线的最高价',
        'enabled': True,
        'parameters': {}
    },
    {
        'rule_id': 2,
        'name': '7天价格新低(4h)',
        'description': '当前价格低于过去7天4h K线的最低价',
        'enabled': True,
        'parameters': {}
    },
    {
        'rule_id': 3,
        'name': '价格触及MA20',
        'description': '当前价格在4h MA20的±0.5%范围内',
        'enabled': True,
        'parameters': {'ma_threshold': 0.5}
    },
    {
        'rule_id': 4,
        'name': '价格触及MA99',
        'description': '当前价格在4h MA99的±0.5%范围内',
        'enabled': True,
        'parameters': {'ma_threshold': 0.5}
    },
    {
        'rule_id': 5,
        'name': '价格达到分布区间90%极值',
        'description': '当前价格超过或低于过去7天4h K线价格分布的90%分位上限/下限',
        'enabled': True,
        'parameters': {'percentile': 90}
    },
]

for rule in rules_data:
    PriceAlertRule.objects.get_or_create(
        rule_id=rule['rule_id'],
        defaults=rule
    )

print("✓ 创建5条价格触发规则")

# 创建6条系统配置
configs_data = [
    {
        'key': 'duplicate_suppress_minutes',
        'value': '60',
        'description': '防重复推送间隔(分钟),默认60分钟'
    },
    {
        'key': 'data_update_interval_minutes',
        'value': '5',
        'description': '数据更新脚本执行间隔(分钟),默认5分钟'
    },
    {
        'key': 'sync_schedule_time',
        'value': '10:30',
        'description': '自动同步任务执行时间(HH:MM格式)'
    },
    {
        'key': 'huicheng_push_token',
        'value': '6020867bc6334c609d4f348c22f90f14',
        'description': '汇成推送接口Token'
    },
    {
        'key': 'huicheng_push_channel',
        'value': 'price_monitor',
        'description': '汇成推送渠道名称'
    },
    {
        'key': 'max_monitored_contracts',
        'value': '500',
        'description': '最大监控合约数量限制'
    },
]

for config in configs_data:
    SystemConfig.objects.get_or_create(
        key=config['key'],
        defaults=config
    )

print("✓ 创建6条系统配置")

# 验证数据
print(f"\n规则数量: {PriceAlertRule.objects.count()}")
print(f"配置数量: {SystemConfig.objects.count()}")

for rule in PriceAlertRule.objects.all():
    print(f"  [{rule.rule_id}] {rule.name} - 启用:{rule.enabled}")

EOF
```

**预期输出**:
```
✓ 创建5条价格触发规则
✓ 创建6条系统配置

规则数量: 5
配置数量: 6
  [1] 7天价格新高(4h) - 启用:True
  [2] 7天价格新低(4h) - 启用:True
  [3] 价格触及MA20 - 启用:True
  [4] 价格触及MA99 - 启用:True
  [5] 价格达到分布区间90%极值 - 启用:True
```

---

## ⚙️ 系统配置

### 步骤1: 检查系统配置

```bash
python manage.py shell <<'EOF'
from grid_trading.django_models import SystemConfig

print("当前系统配置:")
print("=" * 60)
for config in SystemConfig.objects.all():
    print(f"{config.key:35s} = {config.value}")
    print(f"  说明: {config.description}")
    print()
EOF
```

### 步骤2: 根据需要调整配置

**方式1: 通过Django Admin调整**

访问: `http://localhost:8000/admin/grid_trading/systemconfig/`

**方式2: 通过命令行调整**

```bash
# 示例1: 修改防重复推送间隔为120分钟
python manage.py shell <<'EOF'
from grid_trading.django_models import SystemConfig
config = SystemConfig.objects.get(key='duplicate_suppress_minutes')
config.value = '120'
config.save()
print(f"✓ 防重复推送间隔已改为 {config.value} 分钟")
EOF

# 示例2: 修改最大监控合约数为1000
python manage.py shell <<'EOF'
from grid_trading.django_models import SystemConfig
config = SystemConfig.objects.get(key='max_monitored_contracts')
config.value = '1000'
config.save()
print(f"✓ 最大监控合约数已改为 {config.value}")
EOF
```

### 步骤3: 配置汇成推送（可选）

如果需要修改推送配置：

```bash
python manage.py shell <<'EOF'
from grid_trading.django_models import SystemConfig

# 修改推送Token
config = SystemConfig.objects.get(key='huicheng_push_token')
config.value = 'your_token_here'
config.save()
print(f"✓ 推送Token已更新")

# 修改推送渠道
config = SystemConfig.objects.get(key='huicheng_push_channel')
config.value = 'your_channel_name'
config.save()
print(f"✓ 推送渠道已更新为: {config.value}")
EOF
```

---

## 📝 添加监控合约

您有3种方式添加监控合约：

### 方式1: 自动同步（推荐）

从筛选API自动同步符合条件的合约：

```bash
# 步骤1: 预览同步结果（不实际修改数据库）
python manage.py sync_monitored_contracts --dry-run

# 步骤2: 确认无误后，执行实际同步
python manage.py sync_monitored_contracts

# 步骤3: 查看同步后的合约列表
python manage.py shell <<'EOF'
from grid_trading.django_models import MonitoredContract

contracts = MonitoredContract.objects.filter(source='auto', status='enabled')
print(f"✓ 自动同步了 {contracts.count()} 个合约:\n")
for c in contracts[:10]:
    print(f"  - {c.symbol:15s} (同步日期: {c.last_screening_date})")
if contracts.count() > 10:
    print(f"  ... 还有 {contracts.count() - 10} 个")
EOF
```

**预期输出示例**:
```
[2025-12-09 10:30:00] 开始同步监控合约...
筛选API: http://localhost:8000/screening/daily/api/2025-12-08/?...
✓ 获取到 12 个筛选结果

同步摘要:
============================================================
筛选结果数量: 12
现有监控合约: 0 (auto源) + 0 (manual源)

✓ 保留: 0 个合约
+ 新增: 12 个合约
- 移除: 0 个合约

同步后总数: 12 (auto + manual)

✓ 同步完成，耗时 0.5 秒
```

### 方式2: Django Admin手动添加

**单个添加**:

1. 访问: `http://localhost:8000/admin/grid_trading/monitoredcontract/`
2. 点击右上角 **"新增监控合约"**
3. 填写信息：
   - 合约代码: `BTCUSDT`
   - 来源: `manual - 手动添加`
   - 监控状态: `enabled - 启用`
4. 点击 **"保存"**

**批量添加**:

1. 访问合约列表页
2. 点击右上角 **"批量添加合约"**
3. 在文本框中输入合约代码（支持多种格式）：
   ```
   BTCUSDT
   ETHUSDT
   BNBUSDT
   ADAUSDT
   ```
4. 点击 **"批量添加"**

**验证添加结果**:

```bash
python manage.py shell <<'EOF'
from grid_trading.django_models import MonitoredContract

manual_contracts = MonitoredContract.objects.filter(source='manual', status='enabled')
print(f"✓ 手动添加了 {manual_contracts.count()} 个合约:\n")
for c in manual_contracts:
    print(f"  - {c.symbol}")
EOF
```

### 方式3: 通过API添加

```bash
# 批量添加合约
curl -X POST http://localhost:8000/grid_trading/price-monitor/api/contracts/ \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
    "source": "manual"
  }'
```

**预期响应**:
```json
{
  "added": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
  "skipped": [],
  "message": "成功添加3个合约"
}
```

---

## 🚀 启动监控服务

价格监控系统需要运行3个定时任务：

### 1. 数据更新任务（每5分钟）

**功能**: 获取监控合约的4h K线数据（最近7天）

**首次运行**（立即更新数据）:

```bash
# 执行数据更新
python manage.py update_price_monitor_data

# 查看执行日志
python manage.py shell <<'EOF'
from grid_trading.django_models import DataUpdateLog

log = DataUpdateLog.objects.order_by('-started_at').first()
if log:
    print(f"执行时间: {log.started_at}")
    print(f"执行状态: {log.get_status_display()}")
    print(f"处理合约: {log.contracts_count} 个")
    print(f"获取K线: {log.klines_count} 条")
    print(f"执行耗时: {log.execution_seconds:.1f} 秒")
    if log.error_message:
        print(f"错误信息: {log.error_message}")
else:
    print("✗ 未找到执行日志")
EOF
```

**预期输出**:
```
执行时间: 2025-12-09 10:30:00
执行状态: 成功
处理合约: 12 个
获取K线: 504 条
执行耗时: 3.2 秒
```

### 2. 价格检测任务（每5分钟）

**功能**: 检测价格触发条件并推送通知

**首次运行**（立即检测）:

```bash
# 执行价格检测
python manage.py check_price_alerts

# 查看触发日志
python manage.py shell <<'EOF'
from grid_trading.django_models import AlertTriggerLog
from django.utils import timezone
from datetime import timedelta

# 查看最近10条触发日志
recent_logs = AlertTriggerLog.objects.order_by('-triggered_at')[:10]

print(f"最近触发记录（共 {AlertTriggerLog.objects.count()} 条）:\n")
for log in recent_logs:
    status = "✓ 已推送" if log.pushed else f"✗ 未推送 ({log.skip_reason})"
    print(f"{log.triggered_at.strftime('%H:%M:%S')} | {log.symbol:12s} | 规则{log.rule_id} | {status}")
EOF
```

**预期输出示例**:
```
最近触发记录（共 5 条）:

10:35:12 | BTCUSDT      | 规则1 | ✓ 已推送
10:35:12 | ETHUSDT      | 规则3 | ✗ 未推送 (防重复)
10:35:12 | BNBUSDT      | 规则5 | ✓ 已推送
```

### 3. 自动同步任务（每天10:30）

**功能**: 从筛选API同步符合条件的合约

**测试运行**:

```bash
# 使用预览模式测试
python manage.py sync_monitored_contracts --dry-run
```

---

## ⏰ 配置定时任务

### 方式1: 使用Crontab（推荐用于生产环境）

```bash
# 编辑crontab
crontab -e

# 添加以下内容（根据您的项目路径调整）
# 每5分钟更新K线数据
*/5 * * * * cd /path/to/crypto_exchange_news_crawler && /path/to/venv/bin/python manage.py update_price_monitor_data >> /tmp/update_price_monitor_data.log 2>&1

# 每5分钟检测价格触发
*/5 * * * * cd /path/to/crypto_exchange_news_crawler && /path/to/venv/bin/python manage.py check_price_alerts >> /tmp/check_price_alerts.log 2>&1

# 每天10:30同步监控合约
30 10 * * * cd /path/to/crypto_exchange_news_crawler && /path/to/venv/bin/python manage.py sync_monitored_contracts >> /tmp/sync_monitored_contracts.log 2>&1

# 保存并退出
```

**验证crontab配置**:

```bash
# 查看当前crontab
crontab -l

# 查看日志文件
tail -f /tmp/update_price_monitor_data.log
tail -f /tmp/check_price_alerts.log
tail -f /tmp/sync_monitored_contracts.log
```

### 方式2: 使用Supervisor（推荐用于开发环境）

创建 `supervisor_price_monitor.conf`:

```ini
[program:update_price_monitor_data]
command=/path/to/venv/bin/python manage.py update_price_monitor_data
directory=/path/to/crypto_exchange_news_crawler
autostart=true
autorestart=true
startsecs=10
stdout_logfile=/var/log/supervisor/update_price_monitor_data.log
stderr_logfile=/var/log/supervisor/update_price_monitor_data_error.log

[program:check_price_alerts]
command=/path/to/venv/bin/python manage.py check_price_alerts
directory=/path/to/crypto_exchange_news_crawler
autostart=true
autorestart=true
startsecs=10
stdout_logfile=/var/log/supervisor/check_price_alerts.log
stderr_logfile=/var/log/supervisor/check_price_alerts_error.log
```

**启动Supervisor**:

```bash
# 加载配置
sudo supervisorctl reread
sudo supervisorctl update

# 启动服务
sudo supervisorctl start update_price_monitor_data
sudo supervisorctl start check_price_alerts

# 查看状态
sudo supervisorctl status
```

### 方式3: 使用while循环（仅用于开发测试）

创建 `start_price_monitor.sh`:

```bash
#!/bin/bash

PROJECT_DIR="/path/to/crypto_exchange_news_crawler"
VENV_PYTHON="/path/to/venv/bin/python"

cd "$PROJECT_DIR"

echo "启动价格监控系统..."

# 后台运行数据更新任务
while true; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 执行数据更新..."
    $VENV_PYTHON manage.py update_price_monitor_data
    sleep 300  # 5分钟
done &

# 后台运行价格检测任务
while true; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 执行价格检测..."
    $VENV_PYTHON manage.py check_price_alerts
    sleep 300  # 5分钟
done &

echo "✓ 价格监控系统已启动"
echo "✓ 进程ID: $!"

# 等待所有后台任务
wait
```

**启动**:

```bash
chmod +x start_price_monitor.sh
./start_price_monitor.sh
```

---

## ✅ 验证运行状态

### 1. 检查监控合约

```bash
python manage.py shell <<'EOF'
from grid_trading.django_models import MonitoredContract

total = MonitoredContract.objects.exclude(status='expired').count()
enabled = MonitoredContract.objects.filter(status='enabled').count()
disabled = MonitoredContract.objects.filter(status='disabled').count()
auto = MonitoredContract.objects.filter(source='auto', status='enabled').count()
manual = MonitoredContract.objects.filter(source='manual', status='enabled').count()

print("监控合约统计:")
print("=" * 60)
print(f"总数: {total} 个")
print(f"  - 启用: {enabled} 个")
print(f"  - 暂停: {disabled} 个")
print(f"  - 自动: {auto} 个")
print(f"  - 手动: {manual} 个")
EOF
```

### 2. 检查K线数据

```bash
python manage.py shell <<'EOF'
from grid_trading.django_models import MonitoredContract, DataUpdateLog
from django.utils import timezone

# 检查最近更新的合约
recent_contracts = MonitoredContract.objects.filter(
    last_data_update_at__isnull=False
).order_by('-last_data_update_at')[:5]

print("最近更新的合约:")
print("=" * 60)
for c in recent_contracts:
    elapsed = (timezone.now() - c.last_data_update_at).total_seconds() / 60
    print(f"{c.symbol:15s} - {elapsed:.0f}分钟前")

# 检查未更新的合约
no_data_contracts = MonitoredContract.objects.filter(
    status='enabled',
    last_data_update_at__isnull=True
).count()

if no_data_contracts > 0:
    print(f"\n⚠️  有 {no_data_contracts} 个合约未获取到数据")
else:
    print(f"\n✓ 所有合约均已获取数据")

# 检查最后执行日志
last_log = DataUpdateLog.objects.order_by('-started_at').first()
if last_log:
    print(f"\n最后执行: {last_log.started_at}")
    print(f"执行状态: {last_log.get_status_display()}")
EOF
```

### 3. 检查价格触发规则

```bash
python manage.py shell <<'EOF'
from grid_trading.django_models import PriceAlertRule

print("价格触发规则状态:")
print("=" * 60)
for rule in PriceAlertRule.objects.all():
    status = "✓ 启用" if rule.enabled else "✗ 禁用"
    print(f"[{rule.rule_id}] {rule.name:30s} {status}")
EOF
```

### 4. 检查触发历史

```bash
python manage.py shell <<'EOF'
from grid_trading.django_models import AlertTriggerLog
from django.utils import timezone
from datetime import timedelta

# 今日统计
today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
today_triggers = AlertTriggerLog.objects.filter(triggered_at__gte=today_start)
today_pushes = today_triggers.filter(pushed=True)

print("今日触发统计:")
print("=" * 60)
print(f"触发次数: {today_triggers.count()}")
print(f"推送次数: {today_pushes.count()}")
if today_triggers.count() > 0:
    push_rate = today_pushes.count() / today_triggers.count() * 100
    print(f"推送率: {push_rate:.1f}%")

# 按规则统计
print("\n按规则统计:")
for rule_id in range(1, 6):
    count = today_triggers.filter(rule_id=rule_id).count()
    if count > 0:
        print(f"  规则{rule_id}: {count} 次")
EOF
```

### 5. 访问Dashboard（可选）

如果已实现Dashboard：

```bash
# 启动Django开发服务器
python manage.py runserver

# 在浏览器中访问
# http://localhost:8000/grid_trading/price-monitor/
```

### 6. 使用API查询状态

```bash
# 获取监控统计
curl -s http://localhost:8000/grid_trading/price-monitor/api/contracts/stats/ | python -m json.tool

# 获取触发日志摘要
curl -s "http://localhost:8000/grid_trading/price-monitor/api/logs/summary/?days=1" | python -m json.tool

# 查看最近触发日志
curl -s "http://localhost:8000/grid_trading/price-monitor/api/logs/?pushed=true" | python -m json.tool | head -50
```

---

## ❓ 常见问题

### Q1: 添加合约后多久开始监控？

**A**: 立即生效。

- 下次 **数据更新任务**（每5分钟）会获取该合约的K线数据
- 下次 **价格检测任务**（每5分钟）会开始检测规则

建议手动运行一次立即生效：

```bash
python manage.py update_price_monitor_data
python manage.py check_price_alerts
```

### Q2: 如何确认监控是否正常工作？

**A**: 按以下步骤检查：

```bash
# 1. 检查是否有监控合约
python manage.py shell -c "from grid_trading.django_models import MonitoredContract; print(f'监控合约: {MonitoredContract.objects.filter(status=\"enabled\").count()} 个')"

# 2. 检查K线数据是否更新
python manage.py shell -c "from grid_trading.django_models import MonitoredContract; c = MonitoredContract.objects.filter(status='enabled').first(); print(f'最后更新: {c.last_data_update_at if c else \"无\"}')"

# 3. 检查是否有触发日志
python manage.py shell -c "from grid_trading.django_models import AlertTriggerLog; print(f'触发日志: {AlertTriggerLog.objects.count()} 条')"

# 4. 检查crontab是否运行
ps aux | grep "manage.py"
```

### Q3: 没有触发任何推送，正常吗？

**A**: 可能是正常的，取决于市场情况。

检查原因：

```bash
python manage.py shell <<'EOF'
from grid_trading.django_models import AlertTriggerLog

# 查看所有触发（包括未推送的）
logs = AlertTriggerLog.objects.all().order_by('-triggered_at')[:10]

if logs.count() == 0:
    print("✗ 没有任何触发记录")
    print("可能原因:")
    print("  1. 合约数据未更新")
    print("  2. 价格检测任务未运行")
    print("  3. 所有规则都被禁用")
else:
    print(f"有 {logs.count()} 条触发记录:\n")
    for log in logs:
        if log.pushed:
            print(f"✓ {log.symbol:12s} 规则{log.rule_id} - 已推送")
        else:
            print(f"✗ {log.symbol:12s} 规则{log.rule_id} - {log.skip_reason}")
EOF
```

### Q4: 推送失败怎么办？

**A**: 检查汇成推送配置：

```bash
python manage.py shell <<'EOF'
from grid_trading.django_models import SystemConfig

token = SystemConfig.get_value('huicheng_push_token')
channel = SystemConfig.get_value('huicheng_push_channel')

print(f"推送Token: {token}")
print(f"推送渠道: {channel}")

# 测试推送
from grid_trading.services.alert_notifier import AlertNotifier
notifier = AlertNotifier()

success = notifier.push_alert(
    symbol="BTCUSDT",
    rule_name="测试规则",
    current_price=50000.0,
    extra_info="这是一条测试推送"
)

print(f"\n推送测试: {'✓ 成功' if success else '✗ 失败'}")
EOF
```

### Q5: 如何暂停监控某个合约？

**A**: 有3种方式：

**方式1: Django Admin**

访问 `http://localhost:8000/admin/grid_trading/monitoredcontract/`，找到合约，将状态改为 `disabled`。

**方式2: 命令行**

```bash
python manage.py shell <<'EOF'
from grid_trading.django_models import MonitoredContract

contract = MonitoredContract.objects.get(symbol='BTCUSDT')
contract.status = 'disabled'
contract.save()
print(f"✓ {contract.symbol} 已暂停监控")
EOF
```

**方式3: API**

```bash
curl -X PUT http://localhost:8000/grid_trading/price-monitor/api/contracts/BTCUSDT/ \
  -H "Content-Type: application/json" \
  -d '{"status": "disabled"}'
```

### Q6: 如何调整规则参数？

**A**: 例如调整MA20的触发阈值：

```bash
python manage.py shell <<'EOF'
from grid_trading.django_models import PriceAlertRule

rule = PriceAlertRule.objects.get(rule_id=3)
rule.parameters = {'ma_threshold': 1.0}  # 改为±1%
rule.save()
print(f"✓ 规则参数已更新: {rule.parameters}")
EOF
```

或通过Django Admin: `http://localhost:8000/admin/grid_trading/pricealertrule/3/change/`

### Q7: 数据更新失败怎么办？

**A**: 查看失败日志：

```bash
python manage.py shell <<'EOF'
from grid_trading.django_models import DataUpdateLog

failed_logs = DataUpdateLog.objects.filter(status='failed').order_by('-started_at')[:5]

print(f"失败日志（共 {failed_logs.count()} 条）:\n")
for log in failed_logs:
    print(f"时间: {log.started_at}")
    print(f"错误: {log.error_message}")
    print("-" * 60)
EOF
```

常见原因：
1. **币安API限流** - 降低监控合约数量或调整更新频率
2. **网络问题** - 检查网络连接
3. **API密钥错误** - 检查环境变量配置

### Q8: 如何查看实时日志？

**A**: 使用tail命令查看crontab日志：

```bash
# 数据更新日志
tail -f /tmp/update_price_monitor_data.log

# 价格检测日志
tail -f /tmp/check_price_alerts.log

# 自动同步日志
tail -f /tmp/sync_monitored_contracts.log
```

或查看Django日志（如果配置了日志文件）：

```bash
tail -f logs/grid_trading.log
```

---

## 📚 相关文档

- [Django Admin使用指南](ADMIN_GUIDE.md)
- [自动同步逻辑说明](AUTO_SYNC_LOGIC.md)
- [完整运行指南](RUN_GUIDE.md)
- [系统验证报告](VERIFICATION_REPORT.md)
- [API接口文档](contracts/api.yaml)

---

## 🎉 启动完成检查清单

启动完成后，确认以下项目：

- [ ] 数据库迁移已执行
- [ ] 5条价格规则已创建
- [ ] 6条系统配置已创建
- [ ] 至少有1个监控合约（手动或自动添加）
- [ ] 定时任务已配置（crontab或supervisor）
- [ ] 数据更新任务正常运行
- [ ] 价格检测任务正常运行
- [ ] K线数据已获取
- [ ] 能看到触发日志（如果有触发条件）

全部完成后，您的价格监控系统就正式运行了！ 🚀
