# Quick Start Guide: 价格触发预警监控系统

**Date**: 2025-12-08
**Feature**: 001-price-alert-monitor
**Target Audience**: 新加入的开发者、测试人员

## 目录

1. [系统概述](#系统概述)
2. [前置要求](#前置要求)
3. [本地环境搭建](#本地环境搭建)
4. [核心功能快速体验](#核心功能快速体验)
5. [开发工作流](#开发工作流)
6. [常见问题](#常见问题)
7. [参考资料](#参考资料)

---

## 系统概述

价格触发预警监控系统是一个**定时批量处理架构**,通过两个独立的Django管理命令协同工作:

```
┌─────────────────────────────────────────────────────────┐
│  update_price_monitor_data (每5分钟执行)                │
│  - 更新启用合约的1m/15m/4h K线数据                       │
│  - 更新当前价格                                          │
│  - 记录执行日志                                          │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│  check_price_alerts (紧随数据更新后执行)                 │
│  - 读取最新K线和价格数据                                 │
│  - 检测5种价格触发规则                                   │
│  - 防重复检查(默认1小时)                                 │
│  - 推送触发通知(汇成接口)                                │
└─────────────────────────────────────────────────────────┘
```

**5种价格触发规则**:
1. 7天价格新高(4h)
2. 7天价格新低(4h)
3. 价格触及MA20
4. 价格触及MA99
5. 价格达到分布区间90%极值

---

## 前置要求

### 必需环境

- **Python**: 3.12+
- **Django**: 4.2.8
- **数据库**: SQLite (开发) / PostgreSQL (生产推荐)
- **系统**: macOS / Linux

### 必需的Python包

```bash
# 已在项目中安装的核心依赖
python-binance==1.0.19    # 币安API SDK
pandas==2.2.0             # 数据分析和MA计算
numpy==1.26.3             # 数学计算
requests==2.31.0          # HTTP客户端(推送通知)
```

### 可选工具

- **Swagger UI**: 查看API文档 (访问 `/api/docs/`)
- **Django Debug Toolbar**: 调试数据库查询性能
- **pytest**: 运行单元测试

---

## 本地环境搭建

### 1. 克隆代码并切换到功能分支

```bash
# 确保在项目根目录
cd /Users/chenchiyuan/projects/crypto_exchange_news_crawler

# 切换到功能分支
git checkout 001-price-alert-monitor

# 拉取最新代码
git pull origin 001-price-alert-monitor
```

### 2. 安装依赖

```bash
# 激活虚拟环境
source venv/bin/activate  # 或 workon your-venv

# 确认依赖已安装(通常项目已配置好)
pip install -r requirements.txt
```

### 3. 执行数据库迁移

```bash
cd src

# 查看待执行的migrations
python manage.py showmigrations grid_trading

# 执行迁移(创建新表和索引)
python manage.py migrate grid_trading

# 预期输出:
# Running migrations:
#   Applying grid_trading.0XXX_create_price_monitor_models... OK
#   Applying grid_trading.0XXX_add_price_monitor_indexes... OK
#   Applying grid_trading.0XXX_initialize_price_monitor_data... OK
```

### 4. 验证数据初始化

```bash
# 进入Django shell
python manage.py shell

# 执行验证脚本
from grid_trading.django_models import PriceAlertRule, SystemConfig

# 检查5条规则是否已创建
print(f"规则数量: {PriceAlertRule.objects.count()}")  # 应为5
for rule in PriceAlertRule.objects.all():
    print(f"  [{rule.rule_id}] {rule.name} - 启用:{rule.enabled}")

# 检查系统配置
print(f"\n配置数量: {SystemConfig.objects.count()}")  # 应为6
print(f"防重复间隔: {SystemConfig.get_value('duplicate_suppress_minutes')}分钟")
```

预期输出:
```
规则数量: 5
  [1] 7天价格新高(4h) - 启用:True
  [2] 7天价格新低(4h) - 启用:True
  [3] 价格触及MA20 - 启用:True
  [4] 价格触及MA99 - 启用:True
  [5] 价格达到分布区间90%极值 - 启用:True

配置数量: 6
防重复间隔: 60分钟
```

### 5. 启动开发服务器

```bash
# 在src目录下
python manage.py runserver 0.0.0.0:8000

# 访问管理后台
open http://localhost:8000/admin/

# 访问API文档(如已配置Swagger)
open http://localhost:8000/api/docs/
```

---

## 核心功能快速体验

### 场景1: 手动添加监控合约

**目标**: 添加BTCUSDT到监控列表

#### 方法A: 通过Django Admin

1. 访问 http://localhost:8000/admin/grid_trading/monitoredcontract/
2. 点击"Add Monitored Contract"
3. 填写:
   - Symbol: `BTCUSDT`
   - Source: `manual`
   - Status: `enabled`
4. 点击"Save"

#### 方法B: 通过API

```bash
curl -X POST http://localhost:8000/api/v1/monitored-contracts/ \
  -H "Content-Type: application/json" \
  -d '{"symbol": "ETHUSDT"}'
```

#### 方法C: 通过Django Shell

```bash
python manage.py shell

from grid_trading.django_models import MonitoredContract

contract = MonitoredContract.objects.create(
    symbol='BNBUSDT',
    source='manual',
    status='enabled'
)
print(f"✓ 添加成功: {contract}")
```

---

### 场景2: 执行数据更新脚本

**目标**: 手动触发一次数据更新,获取K线数据

```bash
# 在src目录下
python manage.py update_price_monitor_data

# 预期输出:
# [2025-12-08 10:30:00] 开始数据更新...
# [2025-12-08 10:30:00] 获取到3个启用的监控合约
# [2025-12-08 10:30:05] BTCUSDT: 更新1m K线 150条
# [2025-12-08 10:30:07] BTCUSDT: 更新15m K线 42条
# [2025-12-08 10:30:09] BTCUSDT: 更新4h K线 42条
# [2025-12-08 10:30:10] ETHUSDT: 更新1m K线 150条
# ...
# [2025-12-08 10:32:30] ✓ 数据更新完成,耗时150秒
# [2025-12-08 10:32:30] 统计: 更新3个合约,获取1134条K线
```

**验证数据**:

```bash
python manage.py shell

from grid_trading.django_models import KlineData, MonitoredContract

# 检查BTCUSDT的4h K线数据
klines_4h = KlineData.objects.filter(
    symbol='BTCUSDT',
    interval='4h'
).order_by('-open_time')[:10]

print(f"BTCUSDT 4h K线数量: {klines_4h.count()}")
for kline in klines_4h:
    print(f"  {kline.open_time} 收盘价:{kline.close_price}")
```

---

### 场景3: 执行规则检测脚本

**目标**: 检测价格触发规则并推送通知

```bash
# 在src目录下
python manage.py check_price_alerts

# 预期输出:
# [2025-12-08 10:35:00] 开始价格监控检测...
# [2025-12-08 10:35:00] 加载3个启用合约,5条启用规则
# [2025-12-08 10:35:01] BTCUSDT: 当前价格 $45,000.00
# [2025-12-08 10:35:01]   ✓ 规则1触发: 7天价格新高(7天最高=$44,800.00)
# [2025-12-08 10:35:02]   → 推送成功
# [2025-12-08 10:35:02]   ✗ 规则3检测: 未触及MA20 (MA20=$43,500.00, 阈值±0.5%)
# [2025-12-08 10:35:03] ETHUSDT: 当前价格 $2,300.00
# [2025-12-08 10:35:03]   ✗ 所有规则均未触发
# [2025-12-08 10:35:04] ✓ 检测完成,触发1次,推送1次
```

**验证触发日志**:

```bash
python manage.py shell

from grid_trading.django_models import AlertTriggerLog

# 查看最近的触发记录
recent_logs = AlertTriggerLog.objects.all()[:5]

for log in recent_logs:
    status = "✓已推送" if log.pushed else f"✗{log.skip_reason}"
    print(f"{log.symbol} 规则{log.rule_id} {log.triggered_at} {status}")
```

---

### 场景4: 自动同步筛选合约

**目标**: 从 `/screening/daily/` 接口同步最近7天的合约

#### 方法A: 通过API

```bash
curl -X POST http://localhost:8000/api/v1/monitored-contracts/batch-sync/

# 预期响应:
{
  "success": true,
  "added_count": 15,
  "updated_count": 30,
  "expired_count": 5,
  "total_active": 45
}
```

#### 方法B: 通过Django Shell

```bash
python manage.py shell

from grid_trading.services.contract_sync import ContractSyncService

service = ContractSyncService()
result = service.sync_from_screening_api(days=7)

print(f"新增: {result['added_count']}")
print(f"更新: {result['updated_count']}")
print(f"过期: {result['expired_count']}")
```

---

### 场景5: 修改系统配置

**目标**: 将防重复间隔从60分钟改为30分钟

#### 通过Django Admin

1. 访问 http://localhost:8000/admin/grid_trading/systemconfig/
2. 找到 `duplicate_suppress_minutes` 配置
3. 修改 Value 为 `30`
4. 点击"Save"

#### 通过API

```bash
curl -X PUT http://localhost:8000/api/v1/system-config/duplicate_suppress_minutes/ \
  -H "Content-Type: application/json" \
  -d '{
    "value": "30",
    "description": "修改为30分钟"
  }'
```

#### 通过Django Shell

```bash
python manage.py shell

from grid_trading.django_models import SystemConfig

SystemConfig.set_value('duplicate_suppress_minutes', 30, '修改为30分钟')
print(f"✓ 更新成功,当前值: {SystemConfig.get_value('duplicate_suppress_minutes')}")
```

---

## 开发工作流

### 添加新的价格触发规则

假设需要添加**规则6: 价格突破布林带上轨**

#### Step 1: 更新数据模型

```python
# 在 grid_trading/django_models.py 中
class PriceAlertRule(models.Model):
    RULE_CHOICES = [
        (1, '7天价格新高(4h)'),
        (2, '7天价格新低(4h)'),
        (3, '价格触及MA20'),
        (4, '价格触及MA99'),
        (5, '价格达到分布区间90%极值'),
        (6, '价格突破布林带上轨'),  # 新增
    ]
```

#### Step 2: 创建Migration添加初始数据

```bash
python manage.py makemigrations grid_trading --name add_bollinger_band_rule
python manage.py migrate
```

#### Step 3: 实现检测逻辑

```python
# 在 grid_trading/services/rule_detector.py 中

def check_rule_6_bollinger_breakout(self, symbol: str, current_price: Decimal) -> bool:
    """规则6: 价格突破布林带上轨"""
    klines_4h = self.kline_cache.get_klines(symbol, '4h', limit=20)

    if len(klines_4h) < 20:
        return False

    closes = [float(k['close']) for k in klines_4h]
    ma20 = np.mean(closes)
    std20 = np.std(closes)
    upper_band = ma20 + 2 * std20  # 布林带上轨 = MA20 + 2σ

    return float(current_price) > upper_band
```

#### Step 4: 注册到检测器

```python
# 在 check_price_alerts.py 的规则检测循环中

if rule.rule_id == 6 and detector.check_rule_6_bollinger_breakout(contract.symbol, current_price):
    trigger_alert(contract, rule, current_price)
```

#### Step 5: 编写测试

```python
# tests/unit/test_rule_detector.py

def test_rule_6_bollinger_breakout():
    """测试规则6: 布林带突破检测"""
    detector = RuleDetector()

    # Mock K线数据
    mock_klines = [
        {'close': '100.00'} for _ in range(19)
    ] + [{'close': '110.00'}]  # 最新价格突破

    with patch.object(detector.kline_cache, 'get_klines', return_value=mock_klines):
        result = detector.check_rule_6_bollinger_breakout('BTCUSDT', Decimal('115.00'))
        assert result is True
```

---

### 本地测试推送通知

**问题**: 不想在开发环境真实推送通知

**解决方案**: Mock汇成推送接口

```python
# 在 tests/conftest.py 中添加全局fixture

import pytest
from unittest.mock import patch

@pytest.fixture(autouse=True)
def mock_push_service():
    """自动Mock推送服务"""
    with patch('monitor.services.notifier.AlertPushService.send_message') as mock:
        mock.return_value = {'success': True, 'message_id': 'test123'}
        yield mock
```

现在运行任何测试都不会真实推送:

```bash
pytest tests/unit/test_alert_detector.py -v

# 输出:
# test_push_alert_on_rule_trigger PASSED
# 推送已Mock,未真实发送
```

---

### 性能优化技巧

#### 1. 批量查询优化

❌ **低效写法** (N+1查询问题):

```python
for contract in MonitoredContract.objects.filter(status='enabled'):
    klines = KlineData.objects.filter(symbol=contract.symbol, interval='4h')[:42]
    # 每个合约查询一次数据库
```

✅ **高效写法** (使用`prefetch_related`):

```python
from django.db.models import Prefetch

contracts = MonitoredContract.objects.filter(status='enabled').prefetch_related(
    Prefetch(
        'klinedata_set',
        queryset=KlineData.objects.filter(interval='4h').order_by('-open_time')[:42],
        to_attr='klines_4h'
    )
)

for contract in contracts:
    klines = contract.klines_4h  # 无额外查询
```

#### 2. 使用数据库索引

确保migration中包含复合索引:

```python
class Meta:
    indexes = [
        models.Index(fields=['symbol', 'rule_id', '-pushed_at']),  # 防重复查询
    ]
```

验证索引生效:

```bash
python manage.py dbshell

.indexes alert_trigger_log  # SQLite
# 或
\d+ alert_trigger_log       # PostgreSQL
```

---

## 常见问题

### Q1: 数据更新脚本执行超时

**症状**:
```
CommandError: 数据更新超时(>10分钟)
```

**原因**: 监控合约过多(>200个),或网络延迟高

**解决方案**:

1. 增加超时时间(修改SystemConfig)
2. 减少监控合约数量
3. 优化网络:使用代理或CDN

```python
# 临时增加超时
SystemConfig.set_value('data_update_timeout_minutes', 20)
```

---

### Q2: 触发规则但未推送

**症状**: AlertTriggerLog中有记录,但`pushed=False`,`skip_reason='防重复'`

**原因**: 该合约该规则在1小时内已推送过

**验证**:

```python
from datetime import timedelta
from django.utils import timezone

symbol = 'BTCUSDT'
rule_id = 1
threshold = timezone.now() - timedelta(hours=1)

last_push = AlertTriggerLog.objects.filter(
    symbol=symbol,
    rule_id=rule_id,
    pushed=True,
    pushed_at__gte=threshold
).first()

if last_push:
    print(f"上次推送时间: {last_push.pushed_at}")
    print(f"距离现在: {(timezone.now() - last_push.pushed_at).total_seconds() / 60:.1f}分钟")
```

**解决方案**: 等待1小时后自动恢复,或修改`duplicate_suppress_minutes`配置

---

### Q3: K线数据不连续

**症状**: 查询4h K线只有30条,但应该有42条(7天)

**原因**:
1. 合约上市时间<7天
2. 币安API限制或故障

**验证**:

```python
from grid_trading.services.kline_cache import KlineCache

cache = KlineCache(api_client=client)
klines = cache.get_klines('NEWUSDT', '4h', limit=42)

print(f"实际获取: {len(klines)}条")
if len(klines) < 42:
    print(f"⚠️ 数据不连续,可能影响规则检测")
```

**解决方案**:
- 启用降级检测模式(research.md第3.3节)
- 等待合约积累足够历史数据

---

### Q4: 如何重新推送失败的通知

**场景**: 汇成接口暂时故障,导致10条触发未推送

**查询失败记录**:

```python
from datetime import timedelta
from django.utils import timezone

failed_logs = AlertTriggerLog.objects.filter(
    pushed=False,
    skip_reason='推送失败',
    triggered_at__gte=timezone.now() - timedelta(hours=2)
)

print(f"失败数量: {failed_logs.count()}")
```

**补偿推送脚本**:

```python
from grid_trading.services.alert_notifier import PriceAlertNotifier

notifier = PriceAlertNotifier()

for log in failed_logs:
    try:
        notifier.push_alert(log.symbol, log.rule_id, log.current_price, log.extra_info)
        log.pushed = True
        log.pushed_at = timezone.now()
        log.skip_reason = ''
        log.save()
        print(f"✓ {log.symbol} 补偿推送成功")
    except Exception as e:
        print(f"✗ {log.symbol} 补偿推送失败: {e}")
```

---

## 参考资料

### 项目文档

- [功能规格说明](./spec.md) - 完整的用户故事和功能需求
- [技术研究报告](./research.md) - 技术决策和实现方案
- [数据模型设计](./data-model.md) - 完整的数据库模型定义
- [API契约规范](./contracts/api.yaml) - REST API接口文档

### 外部文档

- [币安Futures API文档](https://binance-docs.github.io/apidocs/futures/cn/)
- [Django管理命令](https://docs.djangoproject.com/en/4.2/howto/custom-management-commands/)
- [Pandas时间序列处理](https://pandas.pydata.org/docs/user_guide/timeseries.html)

### 相关代码文件

| 文件路径 | 说明 |
|---------|------|
| `grid_trading/django_models.py` | 数据模型定义 |
| `grid_trading/services/kline_cache.py` | K线数据缓存服务 |
| `grid_trading/services/rule_detector.py` | 规则检测器 |
| `grid_trading/services/alert_notifier.py` | 推送通知服务 |
| `grid_trading/management/commands/update_price_monitor_data.py` | 数据更新脚本 |
| `grid_trading/management/commands/check_price_alerts.py` | 规则检测脚本 |

---

## 获取帮助

遇到问题?

1. 查看Django错误日志: `tail -f logs/django.log`
2. 查看数据更新日志: 访问 `/admin/grid_trading/dataupdatelog/`
3. 联系团队成员: [Slack #crypto-monitor]

---

**Document Status**: ✅ Completed
**Last Updated**: 2025-12-08
**Maintained By**: Crypto Exchange Team
