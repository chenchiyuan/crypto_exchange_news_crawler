# 技术调研报告

**迭代编号**: 005
**迭代名称**: Discovery历史扫描优化
**版本**: v1.0.0
**创建日期**: 2025-12-25

---

## 1. 技术背景

### 1.1 现有架构分析
当前巨量诱多/弃盘检测系统采用三阶段状态机架构：
- **Discovery阶段**: 发现异常放量事件
- **Confirmation阶段**: 确认弃盘特征
- **Validation阶段**: 验证趋势反转

核心组件：
- VolumeTrapStateMachine: 状态机控制器
- 8个检测器: RVOLCalculator、AmplitudeDetector等
- KLine模型: 存储K线数据
- VolumeTrapMonitor: 监控记录模型

### 1.2 现有数据模型
```python
# KLine模型
class KLine(models.Model):
    symbol = CharField()          # 交易对符号
    interval = CharField()        # K线周期
    market_type = CharField()     # 市场类型 (spot/futures)
    open_time = DateTimeField()   # 开盘时间
    open_price = DecimalField()   # 开盘价
    high_price = DecimalField()   # 最高价
    low_price = DecimalField()    # 最低价
    close_price = DecimalField()  # 收盘价
    volume = DecimalField()       # 成交量

# VolumeTrapMonitor模型
class VolumeTrapMonitor(models.Model):
    spot_contract = ForeignKey(SpotContract, null=True, blank=True)
    futures_contract = ForeignKey(FuturesContract, null=True, blank=True)
    market_type = CharField()     # spot/futures
    interval = CharField()        # 1h/4h/1d
    status = CharField()          # pending/suspected_abandonment/confirmed_abandonment/invalidated
    trigger_time = DateTimeField() # 触发时间
    trigger_price = DecimalField() # 触发价格
```

---

## 2. 技术可行性分析

### 2.1 Discovery阶段技术可行性

#### 2.1.1 现有实现分析
```python
# 当前实现：只检查最新K线
def _check_discovery_condition(self, symbol: str, interval: str) -> tuple:
    # 获取最新K线
    latest_kline = KLine.objects.filter(
        symbol=symbol,
        interval=interval,
        market_type=self.market_type
    ).order_by('-open_time').first()

    # 检查RVOL和振幅
    rvol_triggered = self.rvol_calculator.calculate(symbol, interval)['triggered']
    amplitude_triggered = self.amplitude_detector.calculate(symbol, interval)['triggered']

    return (rvol_triggered and amplitude_triggered, {...})
```

#### 2.1.2 改造方案
**方案A: 修改_check_discovery_condition方法**
- 优点：最小修改范围
- 缺点：方法职责变得复杂

**方案B: 新增_check_discovery_condition_history方法**
- 优点：职责清晰，易于维护
- 缺点：代码重复

**方案C: 增加可选参数控制扫描范围**
- 优点：向后兼容，灵活
- 缺点：方法签名变复杂

**推荐方案**: 方案C
- 修改_check_discovery_condition，增加start_date和end_date参数
- 默认行为：start_date=None, end_date=None（扫描最新）
- 历史扫描：指定start_date和end_date

#### 2.1.3 技术实现细节
```python
def _check_discovery_condition(
    self,
    symbol: str,
    interval: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> tuple:
    # 构建查询条件
    query_params = {
        'symbol': symbol,
        'interval': interval,
        'market_type': self.market_type
    }

    if start_date:
        query_params['open_time__gte'] = start_date
    if end_date:
        query_params['open_time__lte'] = end_date

    # 获取K线数据
    klines = KLine.objects.filter(**query_params).order_by('open_time')

    # 遍历所有K线，检查是否符合条件
    for kline in klines:
        # 调用检测器检查当前K线
        rvol_result = self.rvol_calculator.calculate_from_kline(kline)
        amplitude_result = self.amplitude_detector.calculate_from_kline(kline)

        if rvol_result['triggered'] and amplitude_result['triggered']:
            return True, {...}  # 发现异常

    return False, {}
```

### 2.2 批量扫描技术方案

#### 2.2.1 批量查询优化
```python
# 批量获取交易对
def _get_contracts_for_scanning(
    self,
    interval: str,
    market_type: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List[Union[SpotContract, FuturesContract]]:
    if market_type == 'spot':
        contracts = SpotContract.objects.filter(status='active')
    else:
        contracts = FuturesContract.objects.filter(status='active')

    # 优化：只查询活跃的、有数据的交易对
    contracts = contracts.filter(
        klines__interval=interval,
        klines__market_type=market_type
    ).distinct()

    return list(contracts)
```

#### 2.2.2 分批处理策略
```python
# 分批处理
BATCH_SIZE = 1000  # 每批处理1000个交易对

for i in range(0, len(contracts), BATCH_SIZE):
    batch = contracts[i:i + BATCH_SIZE]
    process_batch(batch)

    # 显示进度
    progress = (i + len(batch)) / len(contracts) * 100
    logger.info(f"扫描进度: {progress:.1f}% ({i + len(batch)}/{len(contracts)})")
```

### 2.3 性能优化方案

#### 2.3.1 数据库查询优化
- **索引利用**: 现有索引 `(symbol, interval, market_type, open_time)`
- **批量查询**: 使用 `bulk_create` 批量创建监控记录
- **查询优化**: 避免N+1查询，使用 `select_related` 预取外键

#### 2.3.2 内存优化
- **流式处理**: 分批加载数据，避免一次性加载全部历史数据
- **及时清理**: 处理完一批后及时清理内存
- **懒加载**: 只在需要时加载关联数据

#### 2.3.3 并发优化
- **单线程**: 避免数据库锁竞争
- **异步处理**: 考虑使用异步I/O提升性能
- **连接池**: 利用Django连接池

---

## 3. 技术风险评估

### 3.1 风险识别

| 风险项 | 风险等级 | 影响 | 缓解措施 |
|--------|---------|------|---------|
| 大数据量扫描性能问题 | 高 | 系统响应慢，资源占用高 | 分批处理、进度提示、资源监控 |
| 数据库锁竞争 | 中 | 数据写入冲突 | 单线程处理、批量写入 |
| 内存溢出 | 中 | 系统崩溃 | 流式处理、及时清理 |
| 现有功能破坏 | 低 | 回归测试成本高 | 保持向后兼容、增加测试 |

### 3.2 风险缓解策略

#### 3.2.1 性能风险缓解
```python
# 资源监控
import psutil
import gc

def monitor_resources():
    memory = psutil.virtual_memory()
    cpu = psutil.cpu_percent()

    if memory.percent > 80:
        logger.warning(f"内存使用率过高: {memory.percent}%")
        gc.collect()  # 强制垃圾回收

    if cpu > 90:
        logger.warning(f"CPU使用率过高: {cpu}%")
```

#### 3.2.2 数据一致性风险缓解
```python
# 使用数据库事务确保原子性
from django.db import transaction

@transaction.atomic
def create_monitor_record(contract, kline, indicators):
    monitor = VolumeTrapMonitor.objects.create(
        spot_contract=contract if isinstance(contract, SpotContract) else None,
        futures_contract=contract if isinstance(contract, FuturesContract) else None,
        market_type=contract.exchange.market_type,
        interval=kline.interval,
        status='pending',
        trigger_time=kline.open_time,
        trigger_price=kline.close_price,
        trigger_volume=kline.volume,
        # ... 其他字段
    )

    # 创建指标快照
    VolumeTrapIndicators.objects.create(
        monitor=monitor,
        snapshot_time=timezone.now(),
        # ... 指标数据
    )

    return monitor
```

---

## 4. 技术选型

### 4.1 核心框架
- **Django ORM**: 数据查询和操作 ✅
- **Python 3.12**: 开发语言 ✅
- **PostgreSQL**: 数据库 ✅

### 4.2 关键技术决策

#### 4.2.1 日期处理
- **库**: `datetime` (Python标准库)
- **格式**: ISO 8601 (YYYY-MM-DD)
- **时区**: UTC

#### 4.2.2 进度显示
- **库**: `tqdm` (进度条) 或内置logging
- **方案**: 实时显示进度和剩余时间

#### 4.2.3 并发处理
- **方案**: 单线程分批处理
- **原因**: 避免数据库锁竞争，简化实现

---

## 5. 技术调研结论

### 5.1 可行性评估
✅ **技术可行**: 基于现有架构，技术实现难度中等

**关键优势**:
- 现有架构清晰，易于扩展
- 数据模型支持多市场类型
- 8个检测器逻辑独立，易于复用

**关键挑战**:
- 大数据量场景的性能优化
- 资源使用的控制
- 数据库查询优化

### 5.2 技术决策
- **方案**: 修改现有方法，增加可选参数控制扫描范围
- **优势**: 向后兼容，灵活，代码改动小
- **风险**: 中等，可通过分批处理缓解

### 5.3 推荐实施路径
1. **第一步**: 修改_check_discovery_condition方法，增加日期范围参数
2. **第二步**: 实现批量扫描逻辑，分批处理
3. **第三步**: 优化性能，添加进度提示和资源监控
4. **第四步**: 完善错误处理和日志记录

---

## 6. Q-Gate 3检查

### 6.1 检查清单
- [x] 架构兼容性已评估
- [x] 技术选型已确认
- [x] 技术风险已识别

### 6.2 评估结果
✅ **通过**: 技术可行，风险可控，预计工作量2-3天

---

**技术调研版本**: v1.0.0
**调研完成时间**: 2025-12-25
**状态**: ✅ 通过
