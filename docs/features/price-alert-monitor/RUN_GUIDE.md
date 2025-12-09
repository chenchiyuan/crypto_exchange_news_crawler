# 价格监控系统运行指南

## 🎯 系统架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                      价格监控系统                             │
│                                                               │
│  ┌─────────────────┐      ┌──────────────────┐             │
│  │  数据更新任务    │ ───▶ │  K线数据缓存      │             │
│  │  (每5分钟)       │      │  (1m/15m/4h)     │             │
│  └─────────────────┘      └──────────────────┘             │
│                                    │                         │
│                                    ▼                         │
│  ┌─────────────────┐      ┌──────────────────┐             │
│  │  价格检测任务    │ ───▶ │  规则引擎        │             │
│  │  (每5分钟)       │      │  (5种规则)       │             │
│  └─────────────────┘      └──────────────────┘             │
│                                    │                         │
│                                    ▼                         │
│  ┌─────────────────┐      ┌──────────────────┐             │
│  │  自动同步任务    │      │  推送通知        │             │
│  │  (每天10:30)     │      │  (汇成接口)      │             │
│  └─────────────────┘      └──────────────────┘             │
│                                                               │
│  ┌─────────────────────────────────────────────────┐       │
│  │              Web Dashboard + REST API            │       │
│  └─────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 完整部署流程

### Step 1: 数据库初始化

```bash
# 1. 执行迁移
python manage.py migrate grid_trading

# 2. 初始化规则和配置
python manage.py shell <<'EOF'
from grid_trading.django_models import PriceAlertRule, SystemConfig

# 创建5条规则
rules = [
    {'rule_id': 1, 'name': '7天价格新高(4h)', 'description': '...', 'enabled': True, 'parameters': {}},
    {'rule_id': 2, 'name': '7天价格新低(4h)', 'description': '...', 'enabled': True, 'parameters': {}},
    {'rule_id': 3, 'name': '价格触及MA20', 'description': '...', 'enabled': True, 'parameters': {'ma_threshold': 0.5}},
    {'rule_id': 4, 'name': '价格触及MA99', 'description': '...', 'enabled': True, 'parameters': {'ma_threshold': 0.5}},
    {'rule_id': 5, 'name': '价格达到分布区间90%极值', 'description': '...', 'enabled': True, 'parameters': {'percentile': 90}},
]

for rule in rules:
    PriceAlertRule.objects.get_or_create(rule_id=rule['rule_id'], defaults=rule)

print("✓ 初始化完成")
EOF
```

### Step 2: 手动测试

#### 测试1: 数据更新

```bash
# 执行一次数据更新
python manage.py update_price_monitor_data --skip-lock

# 预期输出:
# [2025-12-08 10:30:00] 开始数据更新...
# 获取到 0 个启用的监控合约
# ⚠️ 没有启用的监控合约，退出执行
```

#### 测试2: 添加监控合约

```bash
# 使用REST API添加合约
curl -X POST http://localhost:8000/grid_trading/price-monitor/api/contracts/ \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["BTCUSDT", "ETHUSDT"],
    "source": "manual"
  }'

# 预期响应:
# {
#   "added": ["BTCUSDT", "ETHUSDT"],
#   "skipped": [],
#   "message": "成功添加2个合约，跳过0个已存在的合约"
# }
```

#### 测试3: 再次数据更新

```bash
# 执行数据更新
python manage.py update_price_monitor_data --skip-lock

# 预期输出:
# [2025-12-08 10:31:00] 开始数据更新...
# 获取到 2 个启用的监控合约
#
# [1/2] 更新 BTCUSDT...
#   ✓ 1m  :  150 条 (0.15s)
#   ✓ 15m :   96 条 (0.12s)
#   ✓ 4h  :   42 条 (0.10s)
#
# [2/2] 更新 ETHUSDT...
#   ✓ 1m  :  150 条 (0.14s)
#   ✓ 15m :   96 条 (0.11s)
#   ✓ 4h  :   42 条 (0.09s)
#
# ✓ 数据更新完成，耗时 1.2 秒
# 统计: 更新 2 个合约，获取 576 条K线
```

#### 测试4: 价格检测

```bash
# 执行价格检测
python manage.py check_price_alerts --skip-lock

# 预期输出:
# [2025-12-08 10:32:00] 开始价格触发检测...
# 获取到 2 个启用的监控合约
# 启用规则数量: 5
#
# [1/2] 检测 BTCUSDT...
#   当前价格: $43,250.50
#   K线数据: 42 根(4h)
#   ✓ 未触发任何规则
#
# [2/2] 检测 ETHUSDT...
#   当前价格: $2,280.75
#   K线数据: 42 根(4h)
#   🔔 触发 1 个规则:
#     - 规则3: 价格触及MA20 [✓ 已推送]
#
# ✓ 价格检测完成，耗时 2.5 秒
# 统计: 检测 2 个合约，触发 1 次规则，推送 1 条告警
```

#### 测试5: 查看触发日志

```bash
# 查询触发日志
curl "http://localhost:8000/grid_trading/price-monitor/api/logs/?limit=5"

# 预期响应:
# {
#   "count": 1,
#   "results": [
#     {
#       "id": 1,
#       "symbol": "ETHUSDT",
#       "rule_id": 3,
#       "rule_name": "价格触及MA20",
#       "current_price": "2280.75",
#       "current_price_display": "$2,280.75",
#       "pushed": true,
#       "pushed_at": "2025-12-08T10:32:15Z",
#       "skip_reason": "",
#       "extra_info": {
#         "ma20": 2285.20,
#         "threshold_pct": 0.5,
#         "distance_pct": 0.19
#       },
#       "triggered_at": "2025-12-08T10:32:15Z"
#     }
#   ]
# }
```

### Step 3: 配置定时任务(Cron)

创建 cron 脚本 `/etc/cron.d/price_monitor`:

```bash
# 价格监控系统定时任务

# 数据更新任务: 每5分钟执行
*/5 * * * * www-data cd /path/to/project && /path/to/venv/bin/python manage.py update_price_monitor_data >> /var/log/price_monitor/data_update.log 2>&1

# 价格检测任务: 每5分钟执行(错开2分钟)
2,7,12,17,22,27,32,37,42,47,52,57 * * * * www-data cd /path/to/project && /path/to/venv/bin/python manage.py check_price_alerts >> /var/log/price_monitor/check_alerts.log 2>&1

# 自动同步任务: 每天10:30执行
30 10 * * * www-data cd /path/to/project && /path/to/venv/bin/python manage.py sync_monitored_contracts >> /var/log/price_monitor/sync_contracts.log 2>&1
```

### Step 4: 启动Web服务

```bash
# 开发环境
python manage.py runserver 0.0.0.0:8000

# 生产环境(使用gunicorn)
gunicorn listing_monitor_project.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --timeout 60 \
  --access-logfile /var/log/price_monitor/gunicorn_access.log \
  --error-logfile /var/log/price_monitor/gunicorn_error.log
```

### Step 5: 访问Dashboard

打开浏览器访问: http://localhost:8000/grid_trading/price-monitor/

## 🔧 系统配置

### 必需配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `huicheng_push_token` | 汇成推送Token | `6020867bc6334c609d4f348c22f90f14` |
| `huicheng_push_channel` | 推送渠道名称 | `price_monitor` |

### 可选配置

| 配置项 | 说明 | 默认值 | 推荐值 |
|--------|------|--------|--------|
| `duplicate_suppress_minutes` | 防重复间隔(分钟) | 60 | 60-120 |
| `data_update_interval_minutes` | 数据更新间隔(分钟) | 5 | 5 |
| `sync_schedule_time` | 同步时间(HH:MM) | 10:30 | 任意 |
| `max_monitored_contracts` | 最大合约数 | 500 | 500-1000 |

修改配置:

```bash
# 方式1: Django Admin
# 访问 http://localhost:8000/admin/grid_trading/systemconfig/

# 方式2: REST API
curl -X PATCH http://localhost:8000/grid_trading/price-monitor/api/configs/duplicate_suppress_minutes/ \
  -H "Content-Type: application/json" \
  -d '{"value": "120"}'

# 方式3: Django Shell
python manage.py shell -c "
from grid_trading.django_models import SystemConfig
SystemConfig.objects.filter(key='duplicate_suppress_minutes').update(value='120')
"
```

## 📊 监控运维

### 1. 日常监控指标

#### 查看执行统计

```bash
# 数据更新成功率
python manage.py shell -c "
from grid_trading.django_models import DataUpdateLog
from datetime import timedelta
from django.utils import timezone

recent = DataUpdateLog.objects.filter(
    started_at__gte=timezone.now() - timedelta(days=1)
)
total = recent.count()
success = recent.filter(status='success').count()
failed = recent.filter(status='failed').count()

print(f'数据更新统计(24h):')
print(f'  总次数: {total}')
print(f'  成功: {success} ({success/total*100:.1f}%)')
print(f'  失败: {failed} ({failed/total*100:.1f}%)')
"
```

#### 查看推送统计

```bash
# 今日触发和推送统计
python manage.py shell -c "
from grid_trading.django_models import AlertTriggerLog
from django.utils import timezone

today_start = timezone.now().replace(hour=0, minute=0, second=0)
logs = AlertTriggerLog.objects.filter(triggered_at__gte=today_start)

total_triggers = logs.count()
total_pushes = logs.filter(pushed=True).count()
push_rate = (total_pushes / total_triggers * 100) if total_triggers > 0 else 0

print(f'触发统计(今日):')
print(f'  触发次数: {total_triggers}')
print(f'  推送次数: {total_pushes}')
print(f'  推送率: {push_rate:.1f}%')
"
```

### 2. 故障排查

#### 问题1: 数据更新失败

**症状**: DataUpdateLog显示status=failed

**排查步骤**:

```bash
# 1. 查看错误信息
python manage.py shell -c "
from grid_trading.django_models import DataUpdateLog
log = DataUpdateLog.objects.filter(status='failed').order_by('-started_at').first()
if log:
    print(f'错误时间: {log.started_at}')
    print(f'错误信息: {log.error_message}')
"

# 2. 检查网络连接
curl -I https://fapi.binance.com/fapi/v1/time

# 3. 检查API限流
# 查看最近请求频率是否过高

# 4. 手动重试
python manage.py update_price_monitor_data --skip-lock
```

**常见原因**:
- Binance API限流(超过1200请求/分钟)
- 网络超时
- 数据库连接失败
- K线数据格式异常

#### 问题2: 价格检测未执行

**症状**: 长时间无触发日志

**排查步骤**:

```bash
# 1. 检查是否有启用的合约
python manage.py shell -c "
from grid_trading.django_models import MonitoredContract
count = MonitoredContract.objects.filter(status='enabled').count()
print(f'启用的监控合约: {count}')
"

# 2. 检查是否有启用的规则
python manage.py shell -c "
from grid_trading.django_models import PriceAlertRule
count = PriceAlertRule.objects.filter(enabled=True).count()
print(f'启用的规则: {count}')
"

# 3. 检查脚本锁状态
python manage.py shell -c "
from grid_trading.services.script_lock import check_lock_status
status = check_lock_status('price_alert_check')
if status['is_locked']:
    print(f'⚠️ 脚本被锁定，剩余 {status[\"remaining_minutes\"]:.1f} 分钟')
else:
    print('✓ 脚本未锁定')
"

# 4. 手动执行检测
python manage.py check_price_alerts --skip-lock
```

#### 问题3: 推送失败

**症状**: AlertTriggerLog显示pushed=False, skip_reason='推送失败'

**排查步骤**:

```bash
# 1. 测试推送服务连接
python manage.py shell -c "
from grid_trading.services.alert_notifier import PriceAlertNotifier
notifier = PriceAlertNotifier()
if notifier.test_connection():
    print('✓ 推送服务连接正常')
else:
    print('✗ 推送服务连接失败')
"

# 2. 检查推送配置
python manage.py shell -c "
from grid_trading.django_models import SystemConfig
token = SystemConfig.get_value('huicheng_push_token')
channel = SystemConfig.get_value('huicheng_push_channel')
print(f'Token: {token[:20]}...')
print(f'Channel: {channel}')
"

# 3. 重试失败的推送
python manage.py check_price_alerts --retry-failed --skip-lock
```

### 3. 性能优化

#### 优化1: K线缓存预热

```bash
# 预热缓存(批量获取K线数据)
python manage.py shell -c "
from grid_trading.django_models import MonitoredContract
from grid_trading.services.kline_cache import KlineCache
from grid_trading.services.binance_futures_client import BinanceFuturesClient

client = BinanceFuturesClient()
cache = KlineCache(api_client=client)

contracts = MonitoredContract.objects.filter(status='enabled')
print(f'开始预热 {contracts.count()} 个合约的K线缓存...')

for idx, contract in enumerate(contracts, 1):
    try:
        cache.get_klines(contract.symbol, '4h', 42, use_cache=True)
        if idx % 10 == 0:
            print(f'进度: {idx}/{contracts.count()}')
    except Exception as e:
        print(f'✗ {contract.symbol}: {e}')

print('✓ 缓存预热完成')
"
```

#### 优化2: 数据库索引

检查索引是否存在:

```bash
python manage.py dbshell <<'SQL'
-- 检查AlertTriggerLog索引
SELECT name FROM sqlite_master
WHERE type='index'
  AND tbl_name='grid_trading_alerttriggerlog';

-- 预期结果应包含:
-- idx_alert_trigger_dedup (symbol, rule_id, pushed, pushed_at)
-- idx_alert_trigger_time (triggered_at)
SQL
```

#### 优化3: 日志清理

定期清理历史日志:

```bash
# 清理30天前的触发日志
python manage.py shell -c "
from grid_trading.django_models import AlertTriggerLog, DataUpdateLog
from datetime import timedelta
from django.utils import timezone

threshold = timezone.now() - timedelta(days=30)

# 清理触发日志
deleted_triggers = AlertTriggerLog.objects.filter(
    triggered_at__lt=threshold
).delete()[0]

# 清理数据更新日志
deleted_updates = DataUpdateLog.objects.filter(
    started_at__lt=threshold
).delete()[0]

print(f'✓ 清理 {deleted_triggers} 条触发日志')
print(f'✓ 清理 {deleted_updates} 条更新日志')
"

# 配置cron任务(每周日凌晨3点执行)
# 0 3 * * 0 www-data cd /path/to/project && /path/to/venv/bin/python manage.py shell -c "..."
```

## 🔍 常见问题

### Q1: 如何调整规则参数?

A: 规则3、4(MA触及)和规则5(价格分布)支持参数调整:

```bash
# 修改MA20触及阈值为1%(默认0.5%)
curl -X PATCH http://localhost:8000/grid_trading/price-monitor/api/rules/3/ \
  -H "Content-Type: application/json" \
  -d '{"parameters": {"ma_threshold": 1.0}}'

# 修改价格分布分位数为95%(默认90%)
curl -X PATCH http://localhost:8000/grid_trading/price-monitor/api/rules/5/ \
  -H "Content-Type: application/json" \
  -d '{"parameters": {"percentile": 95}}'
```

### Q2: 如何临时禁用某个规则?

A: 使用API或Django Admin:

```bash
# 禁用规则4(MA99)
curl -X POST http://localhost:8000/grid_trading/price-monitor/api/rules/bulk_disable/ \
  -H "Content-Type: application/json" \
  -d '{"rule_ids": [4]}'

# 重新启用
curl -X POST http://localhost:8000/grid_trading/price-monitor/api/rules/bulk_enable/ \
  -H "Content-Type: application/json" \
  -d '{"rule_ids": [4]}'
```

### Q3: 如何临时暂停某个合约的监控?

A: 将合约状态改为disabled:

```bash
curl -X POST http://localhost:8000/grid_trading/price-monitor/api/contracts/bulk_update/ \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["BTCUSDT"],
    "status": "disabled"
  }'
```

### Q4: 自动同步会影响手动添加的合约吗?

A: 不会。自动同步只影响`source=auto`的合约，不会修改或删除`source=manual`的合约。

### Q5: 如何修改防重复推送间隔?

A: 修改`duplicate_suppress_minutes`配置(默认60分钟):

```bash
curl -X PATCH http://localhost:8000/grid_trading/price-monitor/api/configs/duplicate_suppress_minutes/ \
  -H "Content-Type: application/json" \
  -d '{"value": "120"}'
```

## 📚 相关文档

- [快速启动指南](quickstart.md) - 基础使用说明
- [API接口文档](contracts/api.yaml) - REST API完整文档
- [数据模型文档](data-model.md) - 数据库表结构
- [系统架构文档](plan.md) - 技术架构设计
