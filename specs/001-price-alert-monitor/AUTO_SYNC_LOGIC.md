# 自动同步逻辑分析

## 📋 概述

价格监控系统支持两种合约来源：
1. **手动配置 (manual)**: 通过Django Admin或API手动添加
2. **自动配置 (auto)**: 每天从筛选API自动同步

## 🔄 自动同步流程

### 执行时机
- **定时任务**: 每天10:30执行一次
- **手动触发**: `python manage.py sync_monitored_contracts`

### 工作流程

```
┌─────────────────────────────────────────────────────────┐
│                 自动同步流程图                            │
│                                                           │
│  1. 获取脚本锁 (防止并发)                                │
│          ↓                                                │
│  2. 调用筛选API                                           │
│     http://localhost:8000/screening/daily/api/{date}/    │
│     参数: min_vdr=6, min_amplitude=50, etc.              │
│          ↓                                                │
│  3. 解析API返回的合约列表                                │
│     例如: [BTCUSDT, ETHUSDT, BNBUSDT]                    │
│          ↓                                                │
│  4. 对比现有监控列表                                      │
│     - 查询 source=auto 的合约                            │
│     - 查询 source=manual 的合约                          │
│          ↓                                                │
│  5. 计算差异                                              │
│     - to_add: 新增的合约                                 │
│     - to_keep: 保留的合约                                │
│     - to_remove: 移除的合约                              │
│          ↓                                                │
│  6. 应用变更                                              │
│     - 新增: 创建 source=auto, status=enabled            │
│     - 保留: 更新 last_screening_date                    │
│     - 移除: 更新 status=expired                         │
│          ↓                                                │
│  7. 释放脚本锁                                            │
└─────────────────────────────────────────────────────────┘
```

## 🎯 核心逻辑

### 1. 筛选API配置

**默认筛选参数**:
```python
{
    'min_vdr': 6,                  # VDR >= 6
    'min_amplitude': 50,           # 15m振幅 >= 50%
    'max_ma99_slope': -10,         # EMA99斜率 <= -10
    'min_funding_rate': -10,       # 年化资费 >= -10%
    'min_volume': 5000000,         # 24h交易量 >= 5M USDT
}
```

**参数可配置**:
在 `SystemConfig` 表中添加配置项：
- `screening_api_base_url`: API基础URL
- `screening_min_vdr`: VDR阈值
- `screening_min_amplitude`: 振幅阈值
- 等等...

### 2. 差异计算逻辑

```python
# 查询现有合约
existing_auto = set(
    MonitoredContract.objects.filter(
        source='auto',
        status__in=['enabled', 'disabled']  # 不包括expired
    ).values_list('symbol', flat=True)
)

existing_manual = set(
    MonitoredContract.objects.filter(
        source='manual',
        status__in=['enabled', 'disabled']
    ).values_list('symbol', flat=True)
)

screening_set = set(screening_symbols)

# 计算差异
to_add = screening_set - existing_auto - existing_manual  # 新增
to_keep = screening_set & existing_auto  # 保留
to_remove = existing_auto - screening_set  # 移除
```

**关键点**:
- ✅ **不会添加已存在的manual合约**: `to_add` 排除了 `existing_manual`
- ✅ **不会影响manual合约**: `to_remove` 只包含 `existing_auto`
- ✅ **忽略expired状态**: 已过期的合约不参与计算

### 3. 数据库操作

#### 新增合约
```python
MonitoredContract.objects.bulk_create([
    MonitoredContract(
        symbol=symbol,
        source='auto',
        status='enabled',
        last_screening_date=today  # 记录筛选日期
    )
    for symbol in to_add
], ignore_conflicts=True)
```

#### 保留合约
```python
MonitoredContract.objects.filter(
    symbol__in=to_keep,
    source='auto'
).update(last_screening_date=today)  # 更新筛选日期
```

#### 移除合约
```python
MonitoredContract.objects.filter(
    symbol__in=to_remove,
    source='auto'
).update(status='expired')  # 标记为已过期
```

## 🛡️ 安全机制

### 1. 脚本锁
- **锁名称**: `sync_monitored_contracts`
- **超时时间**: 5分钟
- **作用**: 防止定时任务并发执行

### 2. 数量限制检查
```python
max_contracts = SystemConfig.get_value('max_monitored_contracts', 500)

if total_after > max_contracts:
    # 拒绝同步，避免超出限制
    sys.exit(1)
```

### 3. 数据隔离
- **auto源**: 只能由自动同步修改
- **manual源**: 不受自动同步影响

### 4. 软删除
- 使用 `status='expired'` 而非硬删除
- 保留历史记录和触发日志

## 📊 同步示例

### 场景1: 首次同步

**初始状态**:
```
数据库: 空
```

**筛选API返回**:
```
[BTCUSDT, ETHUSDT, BNBUSDT]
```

**执行结果**:
```
✓ 保留: 0 个合约
+ 新增: 3 个合约
- 移除: 0 个合约

同步后总数: 3 (auto + manual)
```

**数据库状态**:
```
| symbol    | source | status  | last_screening_date |
|-----------|--------|---------|---------------------|
| BTCUSDT   | auto   | enabled | 2025-12-08          |
| ETHUSDT   | auto   | enabled | 2025-12-08          |
| BNBUSDT   | auto   | enabled | 2025-12-08          |
```

### 场景2: 增量同步

**初始状态**:
```
| symbol    | source | status  | last_screening_date |
|-----------|--------|---------|---------------------|
| BTCUSDT   | auto   | enabled | 2025-12-07          |
| ETHUSDT   | auto   | enabled | 2025-12-07          |
| ADAUSDT   | manual | enabled | NULL                |
```

**筛选API返回**:
```
[BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT]
```

**执行结果**:
```
✓ 保留: 2 个合约 (BTCUSDT, ETHUSDT)
+ 新增: 2 个合约 (BNBUSDT, SOLUSDT)
- 移除: 0 个合约

同步后总数: 5 (4 auto + 1 manual)
```

**数据库状态**:
```
| symbol    | source | status  | last_screening_date |
|-----------|--------|---------|---------------------|
| BTCUSDT   | auto   | enabled | 2025-12-08 ← 更新   |
| ETHUSDT   | auto   | enabled | 2025-12-08 ← 更新   |
| BNBUSDT   | auto   | enabled | 2025-12-08 ← 新增   |
| SOLUSDT   | auto   | enabled | 2025-12-08 ← 新增   |
| ADAUSDT   | manual | enabled | NULL       ← 不变   |
```

### 场景3: 合约移除

**初始状态**:
```
| symbol    | source | status  | last_screening_date |
|-----------|--------|---------|---------------------|
| BTCUSDT   | auto   | enabled | 2025-12-07          |
| ETHUSDT   | auto   | enabled | 2025-12-07          |
| BNBUSDT   | auto   | enabled | 2025-12-07          |
```

**筛选API返回**:
```
[BTCUSDT, ETHUSDT]
```

**执行结果**:
```
✓ 保留: 2 个合约 (BTCUSDT, ETHUSDT)
+ 新增: 0 个合约
- 移除: 1 个合约 (BNBUSDT)

同步后总数: 2 (auto + manual)
```

**数据库状态**:
```
| symbol    | source | status  | last_screening_date |
|-----------|--------|---------|---------------------|
| BTCUSDT   | auto   | enabled | 2025-12-08          |
| ETHUSDT   | auto   | enabled | 2025-12-08          |
| BNBUSDT   | auto   | expired | 2025-12-07 ← 过期   |
```

### 场景4: 手动合约保护

**初始状态**:
```
| symbol    | source | status  | last_screening_date |
|-----------|--------|---------|---------------------|
| BTCUSDT   | auto   | enabled | 2025-12-07          |
| ETHUSDT   | manual | enabled | NULL                |
```

**筛选API返回**:
```
[BTCUSDT, ETHUSDT, BNBUSDT]
```

**计算逻辑**:
```python
screening_set = {BTCUSDT, ETHUSDT, BNBUSDT}
existing_auto = {BTCUSDT}
existing_manual = {ETHUSDT}

to_add = screening_set - existing_auto - existing_manual
       = {BTCUSDT, ETHUSDT, BNBUSDT} - {BTCUSDT} - {ETHUSDT}
       = {BNBUSDT}  # ✓ 不包含ETHUSDT
```

**执行结果**:
```
✓ 保留: 1 个合约 (BTCUSDT)
+ 新增: 1 个合约 (BNBUSDT)
- 移除: 0 个合约

同步后总数: 3 (2 auto + 1 manual)
```

**数据库状态**:
```
| symbol    | source | status  | last_screening_date |
|-----------|--------|---------|---------------------|
| BTCUSDT   | auto   | enabled | 2025-12-08          |
| ETHUSDT   | manual | enabled | NULL       ← 保持   |
| BNBUSDT   | auto   | enabled | 2025-12-08 ← 新增   |
```

## ⚙️ 配置选项

### 1. 修改同步时间

修改 `SystemConfig` 表:
```sql
UPDATE system_config
SET value = '08:00'
WHERE key = 'sync_schedule_time';
```

然后更新 crontab:
```bash
# 改为每天08:00执行
0 8 * * * python manage.py sync_monitored_contracts
```

### 2. 修改筛选参数

在 `SystemConfig` 表中添加：
```sql
INSERT INTO system_config (key, value, description)
VALUES ('screening_min_vdr', '8', 'VDR阈值提高到8');
```

### 3. 修改最大合约数

```sql
UPDATE system_config
SET value = '1000'
WHERE key = 'max_monitored_contracts';
```

## 🔍 监控和调试

### 查看同步历史

通过 `last_screening_date` 字段追踪：
```sql
-- 查看最近同步的合约
SELECT symbol, source, last_screening_date
FROM monitored_contract
WHERE source = 'auto'
ORDER BY last_screening_date DESC;

-- 查看多久没同步的合约
SELECT symbol, last_screening_date,
       DATE('now') - last_screening_date as days_ago
FROM monitored_contract
WHERE source = 'auto'
  AND status = 'enabled'
  AND last_screening_date < DATE('now');
```

### 预览模式

在实际同步前预览变更：
```bash
python manage.py sync_monitored_contracts --dry-run
```

输出：
```
同步摘要:
============================================================
筛选结果数量: 25
现有监控合约: 20 (auto源) + 5 (manual源)

✓ 保留: 18 个合约
+ 新增: 7 个合约
- 移除: 2 个合约

同步后总数: 30 (auto + manual)

⚠️ 预览模式：未实际修改数据库
```

### 手动指定API URL

```bash
python manage.py sync_monitored_contracts \
  --api-url "http://localhost:8000/screening/daily/api/2025-12-07/?min_vdr=8"
```

## ⚠️ 注意事项

### 1. 不要手动修改auto源合约的source字段
- ❌ 错误: 将 `source='auto'` 改为 `'manual'`
- 后果: 该合约将不再受自动同步管理

### 2. 手动添加的合约不会被自动移除
- ✅ 手动添加的合约始终保留
- ✅ 即使不在筛选结果中也不会被标记为expired

### 3. 已过期的合约不会自动恢复
- 如果某个合约之前被移除（`status='expired'`）
- 即使再次出现在筛选结果中，也不会自动恢复
- 需要手动将其状态改为 `'enabled'` 或删除后重新同步

### 4. 数量限制检查
- 同步前会检查总数是否超过 `max_monitored_contracts`
- 如果超过，同步会失败并报错
- 需要调整筛选参数或提高限制

## 🔗 相关文档

- [Django Admin使用指南](ADMIN_GUIDE.md)
- [完整运行指南](RUN_GUIDE.md)
- [系统架构文档](plan.md)
