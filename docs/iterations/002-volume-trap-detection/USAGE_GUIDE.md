# 巨量诱多/弃盘检测系统 - 使用指南

**迭代编号**: 002
**创建日期**: 2024-12-24
**版本**: v1.0.0

---

## 📋 目录

1. [系统概述](#系统概述)
2. [快速开始](#快速开始)
3. [核心功能使用](#核心功能使用)
4. [API接口使用](#api接口使用)
5. [定时任务配置](#定时任务配置)
6. [常见使用场景](#常见使用场景)
7. [故障排查](#故障排查)

---

## 系统概述

### 功能说明

巨量诱多/弃盘检测系统通过**三阶段状态机**自动识别加密货币市场中的"拉高出货"行为：

- **阶段1 - Discovery（发现）**: 检测异常放量 + 脉冲式振幅
- **阶段2 - Confirmation（确认）**: 验证成交量萎缩 + 关键位跌破 + 买盘深度消失
- **阶段3 - Validation（验证）**: 确认趋势反转（MA死叉 + OBV下滑 + ATR压缩）

### 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                       REST API 层                            │
│  GET /api/volume-trap/monitors/  (查询监控池列表)           │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Management Commands                       │
│  • scan_volume_traps      (三阶段扫描)                      │
│  • check_invalidations    (失效检测)                        │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────────────────────────────────────┐
│                     状态机管理层                             │
│  • VolumeTrapStateMachine  (三阶段状态机)                   │
│  • InvalidationDetector    (失效检测器)                     │
│  • ConditionEvaluator      (条件评估器)                     │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────────────────────────────────────┐
│                       检测器层 (8个)                         │
│  Discovery:   RVOLCalculator, AmplitudeDetector             │
│  Confirmation: VolumeRetention, KeyLevelBreach, PEAnalyzer  │
│  Validation:  MACross, OBVDivergence, ATRCompression        │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────────────────────────────────────┐
│                       数据层                                 │
│  • VolumeTrapMonitor       (监控记录)                       │
│  • VolumeTrapIndicators    (指标快照)                       │
│  • VolumeTrapStateTransition (状态转换日志)                │
│  • KLine                   (K线数据)                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 快速开始

### 1. 环境检查

确保系统已正确安装：

```bash
# 检查Django配置
python manage.py check

# 检查数据库迁移
python manage.py showmigrations volume_trap
```

### 2. 准备K线数据

系统依赖K线数据，您可以使用现有的`update_klines`命令：

```bash
# 更新单个交易对的K线数据（测试）
python manage.py update_klines --symbol BTCUSDT --interval 4h --limit 100

# 批量更新所有活跃合约的K线数据
# （该功能需要编写批量脚本，或使用定时任务）
```

### 3. 执行首次扫描

```bash
# 执行4h周期的三阶段扫描
python manage.py scan_volume_traps --interval 4h
```

**预期输出**：
```
=== 开始巨量诱多/弃盘检测扫描 (interval=4h) ===
初始化状态机...
✓ 状态机初始化完成

执行三阶段扫描 (interval=4h)...

=== 扫描完成 ===
  阶段1 - Discovery（发现）: 3个
  阶段2 - Confirmation（确认）: 1个
  阶段3 - Validation（验证）: 0个
  耗时: 2.45秒
```

### 4. 查询检测结果

```bash
# 使用Django shell测试API
python manage.py shell
```

```python
from django.test import Client

client = Client()

# 获取所有监控记录
response = client.get('/api/volume-trap/monitors/')
print(response.json())

# 筛选pending状态的记录
response = client.get('/api/volume-trap/monitors/?status=pending&interval=4h')
print(response.json())
```

---

## 核心功能使用

### 功能1：三阶段扫描

**命令**: `scan_volume_traps`

**用途**: 执行Discovery、Confirmation、Validation三阶段检测

**使用方法**:

```bash
# 扫描4h周期（默认）
python manage.py scan_volume_traps

# 扫描1h周期
python manage.py scan_volume_traps --interval 1h

# 扫描1d周期
python manage.py scan_volume_traps --interval 1d
```

**业务逻辑**:

1. **Discovery阶段**:
   - 扫描所有active的USDT永续合约
   - 检测RVOL >= 8倍 AND 振幅 >= 3倍 AND 上影线 >= 50%
   - 触发时创建Monitor记录（status=pending）

2. **Confirmation阶段**:
   - 扫描所有pending状态的记录
   - 检测成交量留存 < 15% AND 关键位跌破 AND PE > 历史均值×2
   - 触发时更新为suspected_abandonment

3. **Validation阶段**:
   - 扫描所有suspected状态的记录
   - 检测MA死叉 AND OBV单边下滑 AND ATR压缩
   - 触发时更新为confirmed_abandonment

**输出说明**:

- `discovery`: 新增监控数量（阶段1触发数）
- `confirmation`: 状态转换数量（阶段2触发数）
- `validation`: 状态转换数量（阶段3触发数）
- `errors`: 错误列表（如数据不足、计算异常等）

---

### 功能2：失效检测

**命令**: `check_invalidations`

**用途**: 检测价格收复情况，标记失效的监控记录

**使用方法**:

```bash
# 检测4h周期的失效记录（默认）
python manage.py check_invalidations

# 检测1h周期
python manage.py check_invalidations --interval 1h
```

**业务逻辑**:

- 扫描所有非invalidated状态的记录
- 获取最新收盘价
- 如果 `current_close > P_trigger`，则判定为价格收复
- 更新状态为invalidated，并记录StateTransition日志

**使用场景**:

- 价格收复说明"弃盘"判断失败，市场重新获得支撑
- 失效记录可被定期清理，避免误导用户决策

---

### 功能3：监控池查询

**接口**: `GET /api/volume-trap/monitors/`

**用途**: 查询监控池列表，支持筛选和分页

**使用方法**:

#### 方法1: 浏览器访问

```
http://localhost:8000/api/volume-trap/monitors/
```

#### 方法2: curl命令

```bash
# 获取所有监控记录
curl http://localhost:8000/api/volume-trap/monitors/

# 筛选pending状态的4h周期记录
curl "http://localhost:8000/api/volume-trap/monitors/?status=pending&interval=4h"

# 获取第2页，每页50条
curl "http://localhost:8000/api/volume-trap/monitors/?page=2&page_size=50"
```

#### 方法3: Python代码

```python
import requests

# 获取所有监控记录
response = requests.get('http://localhost:8000/api/volume-trap/monitors/')
data = response.json()

print(f"总记录数: {data['count']}")
for monitor in data['results']:
    print(f"{monitor['symbol']} - {monitor['status']} - {monitor['trigger_time']}")
```

**查询参数**:

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| status | string | 状态筛选 | pending, suspected_abandonment, confirmed_abandonment, invalidated |
| interval | string | 周期筛选 | 1h, 4h, 1d |
| page | int | 页码（从1开始） | 1, 2, 3 |
| page_size | int | 每页数量（1-100） | 20, 50, 100 |

**响应格式**:

```json
{
  "count": 100,
  "next": "http://localhost:8000/api/volume-trap/monitors/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "symbol": "BTCUSDT",
      "interval": "4h",
      "trigger_time": "2024-12-24T12:00:00+08:00",
      "trigger_price": "50000.00",
      "trigger_volume": "10000.00",
      "trigger_kline_high": "51000.00",
      "trigger_kline_low": "49000.00",
      "status": "pending",
      "phase_1_passed": true,
      "phase_2_passed": false,
      "phase_3_passed": false,
      "latest_indicators": {
        "id": 1,
        "snapshot_time": "2024-12-24T12:00:00+08:00",
        "kline_close_price": "50500.00",
        "rvol_ratio": "10.5",
        "amplitude_ratio": "4.2",
        "upper_shadow_ratio": "0.65"
      },
      "created_at": "2024-12-24T12:05:00+08:00",
      "updated_at": "2024-12-24T12:05:00+08:00"
    }
  ]
}
```

---

## API接口使用

### 接口1: 监控池列表

**Endpoint**: `GET /api/volume-trap/monitors/`

**功能**: 查询监控池记录列表

**使用示例**:

```python
import requests

# 示例1: 获取所有pending状态的监控记录
response = requests.get(
    'http://localhost:8000/api/volume-trap/monitors/',
    params={'status': 'pending'}
)

for monitor in response.json()['results']:
    print(f"""
    交易对: {monitor['symbol']}
    触发时间: {monitor['trigger_time']}
    触发价格: {monitor['trigger_price']}
    当前状态: {monitor['status']}
    RVOL倍数: {monitor['latest_indicators']['rvol_ratio']}
    """)

# 示例2: 筛选confirmed_abandonment状态（已确认弃盘）
response = requests.get(
    'http://localhost:8000/api/volume-trap/monitors/',
    params={
        'status': 'confirmed_abandonment',
        'interval': '4h',
        'page_size': 50
    }
)

confirmed_list = response.json()['results']
print(f"已确认弃盘的合约数量: {len(confirmed_list)}")

# 示例3: 分页遍历所有记录
page = 1
while True:
    response = requests.get(
        'http://localhost:8000/api/volume-trap/monitors/',
        params={'page': page, 'page_size': 100}
    )
    data = response.json()

    # 处理当前页数据
    for monitor in data['results']:
        process_monitor(monitor)

    # 检查是否还有下一页
    if not data['next']:
        break
    page += 1
```

---

## 定时任务配置

### 使用Crontab自动化监控

**推荐配置**（每个周期独立执行）：

```bash
# 编辑crontab
crontab -e
```

#### 1h周期任务

```cron
# 每小时05分：更新K线数据
5 * * * * cd /path/to/project && python manage.py update_klines --symbol BTCUSDT --interval 1h --limit 50 >> /var/log/volume_trap/update_1h.log 2>&1

# 每小时10分：执行三阶段扫描
10 * * * * cd /path/to/project && python manage.py scan_volume_traps --interval 1h >> /var/log/volume_trap/scan_1h.log 2>&1

# 每小时15分：检测失效
15 * * * * cd /path/to/project && python manage.py check_invalidations --interval 1h >> /var/log/volume_trap/invalidation_1h.log 2>&1
```

#### 4h周期任务

```cron
# 每4小时05分：执行K线数据更新
5 */4 * * * cd /path/to/project && python manage.py update_klines --symbol ETHUSDT --interval 4h --limit 50 >> /var/log/volume_trap/update_4h.log 2>&1

# 每4小时10分：执行三阶段扫描
10 */4 * * * cd /path/to/project && python manage.py scan_volume_traps --interval 4h >> /var/log/volume_trap/scan_4h.log 2>&1

# 每4小时15分：检测失效
15 */4 * * * cd /path/to/project && python manage.py check_invalidations --interval 4h >> /var/log/volume_trap/invalidation_4h.log 2>&1
```

#### 1d周期任务

```cron
# 每日00:05：更新K线数据
5 0 * * * cd /path/to/project && python manage.py update_klines --symbol BTCUSDT --interval 1d --limit 30 >> /var/log/volume_trap/update_1d.log 2>&1

# 每日00:10：执行三阶段扫描
10 0 * * * cd /path/to/project && python manage.py scan_volume_traps --interval 1d >> /var/log/volume_trap/scan_1d.log 2>&1

# 每日00:15：检测失效
15 0 * * * cd /path/to/project && python manage.py check_invalidations --interval 1d >> /var/log/volume_trap/invalidation_1d.log 2>&1
```

### 执行时序说明

```
T+0分（周期结束）
  ↓
T+5分：更新K线数据（确保数据最新）
  ↓
T+10分：执行三阶段扫描（Discovery/Confirmation/Validation）
  ↓
T+15分：检测失效（价格收复检测）
```

**为什么这样设计**：
1. **05分更新数据**：确保扫描前有最新的K线数据
2. **10分执行扫描**：给数据更新留出5分钟缓冲
3. **15分失效检测**：在扫描完成后检测价格收复

---

## 常见使用场景

### 场景1：手动测试单个交易对

```bash
# Step 1: 更新K线数据
python manage.py update_klines --symbol BTCUSDT --interval 4h --limit 100

# Step 2: 执行扫描
python manage.py scan_volume_traps --interval 4h

# Step 3: 查询结果
python manage.py shell
```

```python
from volume_trap.models import VolumeTrapMonitor

# 查看BTCUSDT的监控记录
monitors = VolumeTrapMonitor.objects.filter(
    futures_contract__symbol='BTCUSDT',
    interval='4h'
).order_by('-trigger_time')

for m in monitors[:5]:
    print(f"{m.symbol} - {m.status} - {m.trigger_time}")
```

---

### 场景2：批量监控多个交易对

```python
# 创建批量扫描脚本: scripts/batch_scan.py

from volume_trap.services.volume_trap_fsm import VolumeTrapStateMachine

# 初始化状态机
fsm = VolumeTrapStateMachine()

# 扫描所有周期
for interval in ['1h', '4h', '1d']:
    print(f"扫描 {interval} 周期...")
    result = fsm.scan(interval=interval)
    print(f"  发现: {result['discovery']}")
    print(f"  确认: {result['confirmation']}")
    print(f"  验证: {result['validation']}")
```

执行脚本：
```bash
python manage.py shell < scripts/batch_scan.py
```

---

### 场景3：实时监控告警

```python
# 创建告警脚本: scripts/alert_confirmed.py

import requests
from volume_trap.models import VolumeTrapMonitor
from datetime import timedelta
from django.utils import timezone

# 查询最近1小时内确认弃盘的合约
recent_time = timezone.now() - timedelta(hours=1)
confirmed = VolumeTrapMonitor.objects.filter(
    status='confirmed_abandonment',
    updated_at__gte=recent_time
)

if confirmed.exists():
    # 发送告警（示例：钉钉/Slack/邮件）
    for monitor in confirmed:
        message = f"""
        ⚠️ 检测到弃盘信号！
        交易对: {monitor.futures_contract.symbol}
        周期: {monitor.interval}
        触发价格: {monitor.trigger_price}
        触发时间: {monitor.trigger_time}
        """
        print(message)
        # send_alert(message)  # 实现您的告警逻辑
```

在Crontab中配置每小时执行：
```cron
0 * * * * cd /path/to/project && python manage.py shell < scripts/alert_confirmed.py
```

---

### 场景4：数据分析与导出

```python
from volume_trap.models import VolumeTrapMonitor, VolumeTrapIndicators
import pandas as pd

# 导出所有confirmed_abandonment记录
monitors = VolumeTrapMonitor.objects.filter(
    status='confirmed_abandonment'
).select_related('futures_contract')

data = []
for m in monitors:
    # 获取最新指标
    latest = m.indicators.order_by('-snapshot_time').first()

    data.append({
        'symbol': m.futures_contract.symbol,
        'interval': m.interval,
        'trigger_time': m.trigger_time,
        'trigger_price': float(m.trigger_price),
        'rvol_ratio': float(latest.rvol_ratio) if latest else None,
        'amplitude_ratio': float(latest.amplitude_ratio) if latest else None,
        'status': m.status,
    })

# 转为DataFrame并导出
df = pd.DataFrame(data)
df.to_csv('confirmed_abandonment_export.csv', index=False)
print(f"导出完成: {len(df)} 条记录")
```

---

## 故障排查

### 问题1: 扫描时报错 "数据不足"

**错误信息**:
```
DataInsufficientError: K线数据不足 (required=21, actual=10)
```

**原因**: K线数据不足，无法计算RVOL、MA等指标

**解决方案**:
```bash
# 更新更多K线数据
python manage.py update_klines --symbol BTCUSDT --interval 4h --limit 200
```

---

### 问题2: API返回400错误

**错误信息**:
```json
{
  "error": "Invalid status parameter",
  "detail": "status must be one of: ['pending', 'suspected_abandonment', 'confirmed_abandonment', 'invalidated']",
  "received": "confirmed"
}
```

**原因**: status参数值错误

**解决方案**:
```bash
# 使用正确的status值
curl "http://localhost:8000/api/volume-trap/monitors/?status=confirmed_abandonment"
```

---

### 问题3: 扫描结果为0

**现象**: 执行扫描后，discovery/confirmation/validation都是0

**可能原因**:
1. K线数据不足
2. 市场未出现符合条件的信号
3. 配置阈值过于严格

**排查步骤**:

```python
from volume_trap.detectors.rvol_calculator import RVOLCalculator
from backtest.models import KLine

# 检查K线数据
klines = KLine.objects.filter(symbol='BTCUSDT', interval='4h')
print(f"K线数量: {klines.count()}")

# 手动测试RVOL计算
calc = RVOLCalculator()
result = calc.calculate('BTCUSDT', '4h')
print(f"RVOL结果: {result}")
```

---

### 问题4: 定时任务未执行

**排查步骤**:

```bash
# 1. 检查crontab是否正确配置
crontab -l

# 2. 检查日志文件
tail -f /var/log/volume_trap/scan_4h.log

# 3. 手动执行命令测试
python manage.py scan_volume_traps --interval 4h

# 4. 检查cron服务状态
sudo service cron status
```

---

## 总结

### 核心命令速查

| 命令 | 用途 | 频率 |
|------|------|------|
| `scan_volume_traps` | 三阶段扫描 | 每周期一次 |
| `check_invalidations` | 失效检测 | 每周期一次 |
| `update_klines` | K线数据更新 | 每周期一次 |

### API接口速查

| 接口 | 方法 | 用途 |
|------|------|------|
| `/api/volume-trap/monitors/` | GET | 查询监控池列表 |

### 状态流转图

```
                  Discovery触发
    [无监控] ──────────────────→ [pending]
                                    │
                                    │ Confirmation触发
                                    ↓
                          [suspected_abandonment]
                                    │
                                    │ Validation触发
                                    ↓
                          [confirmed_abandonment]

                  价格收复
    [任意状态] ──────────────────→ [invalidated]
```

---

**文档版本**: v1.0.0
**最后更新**: 2024-12-24
**相关文档**:
- PRD: `docs/iterations/002-volume-trap-detection/prd.md`
- 架构: `docs/iterations/002-volume-trap-detection/architecture.md`
- 任务: `docs/iterations/002-volume-trap-detection/tasks.md`
