# Data Model: Market Cap & FDV Display Integration

**Feature**: 008-marketcap-fdv-display
**Date**: 2025-12-12
**Status**: Design Complete

## Overview

本文档定义了市值/FDV展示功能所需的3个核心数据模型,以及它们之间的关系和约束条件。所有模型遵循Django ORM规范,使用SQLite(开发)和PostgreSQL(生产)作为底层存储。

### 实体关系图 (ERD)

```
┌─────────────────────┐
│   TokenMapping      │
├─────────────────────┤
│ + id (PK)           │
│ + symbol (UQ)       │───┐
│ + base_token        │   │
│ + coingecko_id      │   │
│ + match_status      │   │
│ + alternatives JSON │   │
│ + created_at        │   │
│ + updated_at        │   │
└─────────────────────┘   │
                          │
                          │ 1:1 (optional)
                          │
                          ▼
                ┌─────────────────────┐
                │   MarketData        │
                ├─────────────────────┤
                │ + id (PK)           │
                │ + symbol (UQ, FK)   │
                │ + market_cap        │
                │ + fdv               │
                │ + data_source       │
                │ + fetched_at        │
                │ + created_at        │
                │ + updated_at        │
                └─────────────────────┘
                          │
                          │
                          │ 1:N
                          │
                          ▼
                ┌─────────────────────┐
                │   UpdateLog         │
                ├─────────────────────┤
                │ + id (PK)           │
                │ + batch_id          │
                │ + symbol (FK)       │
                │ + operation_type    │
                │ + status            │
                │ + error_message     │
                │ + executed_at       │
                └─────────────────────┘
```

### 关系说明
- **TokenMapping ← → MarketData**: 1对1关系(可选),一个映射关系对应一个市场数据记录
- **MarketData → UpdateLog**: 1对多关系,一个symbol可以有多条更新日志记录

---

## Entity 1: TokenMapping (代币映射表)

### 用途
存储币安交易对symbol与CoinGecko代币ID的映射关系,支持自动匹配和人工审核。

### Django模型定义

```python
# grid_trading/models/token_mapping.py
from django.db import models
from django.utils import timezone


class TokenMapping(models.Model):
    """币安symbol与CoinGecko ID的映射关系"""

    class MatchStatus(models.TextChoices):
        AUTO_MATCHED = "auto_matched", "自动匹配"
        MANUAL_CONFIRMED = "manual_confirmed", "人工确认"
        NEEDS_REVIEW = "needs_review", "需要审核"

    # 主键
    id = models.AutoField(primary_key=True)

    # 币安交易对symbol (如: BTCUSDT)
    symbol = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        verbose_name="币安交易对"
    )

    # 基础代币symbol (如: BTC)
    base_token = models.CharField(
        max_length=10,
        verbose_name="基础代币"
    )

    # CoinGecko代币ID (如: bitcoin)
    coingecko_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="CoinGecko ID"
    )

    # 匹配状态
    match_status = models.CharField(
        max_length=20,
        choices=MatchStatus.choices,
        default=MatchStatus.NEEDS_REVIEW,
        db_index=True,
        verbose_name="匹配状态"
    )

    # 候选CoinGecko ID列表 (JSON格式)
    # 例如: ["bitcoin", "wrapped-bitcoin", "bitcoin-cash"]
    alternatives = models.JSONField(
        null=True,
        blank=True,
        verbose_name="候选ID列表"
    )

    # 创建时间
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间"
    )

    # 最后更新时间
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新时间"
    )

    class Meta:
        db_table = "token_mapping"
        verbose_name = "代币映射"
        verbose_name_plural = "代币映射"
        ordering = ["symbol"]
        indexes = [
            models.Index(fields=["symbol"]),
            models.Index(fields=["match_status"]),
            models.Index(fields=["coingecko_id"]),
        ]

    def __str__(self):
        return f"{self.symbol} → {self.coingecko_id or '未映射'}"

    def is_ready_for_update(self):
        """判断是否可以用于数据更新"""
        return self.match_status in [
            self.MatchStatus.AUTO_MATCHED,
            self.MatchStatus.MANUAL_CONFIRMED
        ] and self.coingecko_id is not None
```

### 字段说明

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | AutoField | PK | 主键 |
| symbol | CharField(20) | UNIQUE, INDEX | 币安交易对symbol,如BTCUSDT |
| base_token | CharField(10) | NOT NULL | 基础代币,如BTC |
| coingecko_id | CharField(100) | NULL, INDEX | CoinGecko代币ID,如bitcoin |
| match_status | CharField(20) | CHOICES, INDEX | 匹配状态(auto_matched/manual_confirmed/needs_review) |
| alternatives | JSONField | NULL | 候选CoinGecko ID列表,用于needs_review状态 |
| created_at | DateTimeField | AUTO | 创建时间 |
| updated_at | DateTimeField | AUTO | 最后更新时间 |

### 数据示例

```json
[
  {
    "id": 1,
    "symbol": "BTCUSDT",
    "base_token": "BTC",
    "coingecko_id": "bitcoin",
    "match_status": "auto_matched",
    "alternatives": null,
    "created_at": "2025-12-12T10:00:00Z",
    "updated_at": "2025-12-12T10:00:00Z"
  },
  {
    "id": 2,
    "symbol": "MONUSDT",
    "base_token": "MON",
    "coingecko_id": "mon-protocol",
    "match_status": "auto_matched",
    "alternatives": ["mon-protocol", "monster-galaxy"],
    "created_at": "2025-12-12T10:00:00Z",
    "updated_at": "2025-12-12T10:00:00Z"
  },
  {
    "id": 3,
    "symbol": "XYZUSDT",
    "base_token": "XYZ",
    "coingecko_id": null,
    "match_status": "needs_review",
    "alternatives": ["xyz-coin", "xyz-token", "xyz-protocol"],
    "created_at": "2025-12-12T10:00:00Z",
    "updated_at": "2025-12-12T10:00:00Z"
  }
]
```

### 业务规则

#### 规则1: 唯一性约束
- **symbol**必须唯一(一个币安交易对只能有一条映射记录)
- 更新映射关系时使用`update_or_create(symbol=...)`

#### 规则2: 状态转换
```
[new record]
    ↓
needs_review  ──(自动匹配成功)──→  auto_matched
    ↓                                     ↓
 (人工选择)                          (人工修正)
    ↓                                     ↓
manual_confirmed ←────────────────────────┘
```

#### 规则3: alternatives字段规则
- 只在`needs_review`状态时填充
- 存储最多5个候选项(优先级从高到低排序)
- auto_matched或manual_confirmed状态时可为null

#### 规则4: 数据更新资格
- 只有`auto_matched`或`manual_confirmed`状态的记录才能用于市场数据更新
- `coingecko_id`不能为null

---

## Entity 2: MarketData (市场数据表)

### 用途
存储从CoinGecko获取的市值和FDV数据,每个symbol一条最新记录(覆盖更新)。

### Django模型定义

```python
# grid_trading/models/market_data.py
from django.db import models
from django.utils import timezone


class MarketData(models.Model):
    """市值和FDV市场数据"""

    # 主键
    id = models.AutoField(primary_key=True)

    # 币安交易对symbol (外键到TokenMapping)
    symbol = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        verbose_name="币安交易对"
    )

    # 市值 (美元)
    market_cap = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="市值(USD)"
    )

    # 全稀释估值 (美元)
    fully_diluted_valuation = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="FDV(USD)"
    )

    # 数据来源 (固定为"coingecko")
    data_source = models.CharField(
        max_length=50,
        default="coingecko",
        verbose_name="数据来源"
    )

    # 数据获取时间 (从API拿到数据的时间)
    fetched_at = models.DateTimeField(
        verbose_name="获取时间"
    )

    # 创建时间 (首次插入记录的时间)
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间"
    )

    # 最后更新时间 (最后一次更新记录的时间)
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新时间"
    )

    class Meta:
        db_table = "market_data"
        verbose_name = "市场数据"
        verbose_name_plural = "市场数据"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["symbol"]),
            models.Index(fields=["updated_at"]),
        ]

    def __str__(self):
        return f"{self.symbol}: MC=${self.market_cap}, FDV=${self.fully_diluted_valuation}"

    @property
    def market_cap_formatted(self):
        """格式化市值(K/M/B)"""
        if self.market_cap is None:
            return "-"
        return self._format_number(float(self.market_cap))

    @property
    def fdv_formatted(self):
        """格式化FDV(K/M/B)"""
        if self.fully_diluted_valuation is None:
            return "-"
        return self._format_number(float(self.fully_diluted_valuation))

    @staticmethod
    def _format_number(value):
        """数字格式化辅助函数"""
        if value >= 1_000_000_000:
            return f"${value / 1_000_000_000:.2f}B"
        elif value >= 1_000_000:
            return f"${value / 1_000_000:.2f}M"
        elif value >= 1_000:
            return f"${value / 1_000:.2f}K"
        else:
            return f"${value:.2f}"
```

### 字段说明

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | AutoField | PK | 主键 |
| symbol | CharField(20) | UNIQUE, INDEX | 币安交易对symbol |
| market_cap | DecimalField(20,2) | NULL | 市值(美元),精度到分 |
| fully_diluted_valuation | DecimalField(20,2) | NULL | FDV(美元),精度到分 |
| data_source | CharField(50) | DEFAULT="coingecko" | 数据来源标识 |
| fetched_at | DateTimeField | NOT NULL | API数据获取时间 |
| created_at | DateTimeField | AUTO | 首次创建时间 |
| updated_at | DateTimeField | AUTO | 最后更新时间 |

### 数据示例

```json
[
  {
    "id": 1,
    "symbol": "BTCUSDT",
    "market_cap": "1234567890123.45",
    "fully_diluted_valuation": "1300000000000.00",
    "data_source": "coingecko",
    "fetched_at": "2025-12-12T04:05:00Z",
    "created_at": "2025-12-10T04:00:00Z",
    "updated_at": "2025-12-12T04:10:00Z"
  },
  {
    "id": 2,
    "symbol": "ETHUSDT",
    "market_cap": "456789012345.67",
    "fully_diluted_valuation": "500000000000.00",
    "data_source": "coingecko",
    "fetched_at": "2025-12-12T04:05:00Z",
    "created_at": "2025-12-10T04:00:00Z",
    "updated_at": "2025-12-12T04:10:00Z"
  },
  {
    "id": 3,
    "symbol": "MONUSDT",
    "market_cap": "68000000.00",
    "fully_diluted_valuation": "350000000.00",
    "data_source": "coingecko",
    "fetched_at": "2025-12-12T04:05:00Z",
    "created_at": "2025-12-12T04:10:00Z",
    "updated_at": "2025-12-12T04:10:00Z"
  }
]
```

### 业务规则

#### 规则1: 覆盖更新策略
- 每个symbol只保留一条最新记录
- 使用`MarketData.objects.update_or_create(symbol=..., defaults={...})`
- 不维护历史快照(需求已确认)

#### 规则2: NULL值处理
- `market_cap`和`fully_diluted_valuation`允许NULL
- NULL表示CoinGecko中无此数据或获取失败
- 前端显示"-"

#### 规则3: 数据精度
- 使用DecimalField(20,2)存储,避免浮点数精度问题
- 市值/FDV最大值: 10^18 USD (足够覆盖所有加密货币)

#### 规则4: 数据时效性
- `fetched_at`: API返回数据的时间戳(CoinGecko的数据快照时间)
- `updated_at`: 数据库记录的更新时间
- 前端Tooltip显示`updated_at`,而非`fetched_at`

---

## Entity 3: UpdateLog (更新日志表)

### 用途
记录每次数据更新操作的详细日志,用于审计、错误追踪和性能监控。

### Django模型定义

```python
# grid_trading/models/update_log.py
import uuid
from django.db import models
from django.utils import timezone


class UpdateLog(models.Model):
    """数据更新日志"""

    class OperationType(models.TextChoices):
        MAPPING_UPDATE = "mapping_update", "映射更新"
        DATA_FETCH = "data_fetch", "数据获取"

    class Status(models.TextChoices):
        SUCCESS = "success", "成功"
        FAILURE = "failure", "失败"
        PARTIAL = "partial", "部分成功"

    # 主键
    id = models.AutoField(primary_key=True)

    # 批次ID (UUID,用于关联同一批次的多条日志)
    batch_id = models.UUIDField(
        default=uuid.uuid4,
        db_index=True,
        verbose_name="批次ID"
    )

    # 处理的symbol (可选,如果是批量操作则为NULL)
    symbol = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="币安交易对"
    )

    # 操作类型
    operation_type = models.CharField(
        max_length=20,
        choices=OperationType.choices,
        db_index=True,
        verbose_name="操作类型"
    )

    # 状态
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        db_index=True,
        verbose_name="状态"
    )

    # 错误信息 (如果失败)
    error_message = models.TextField(
        null=True,
        blank=True,
        verbose_name="错误信息"
    )

    # 执行时间
    executed_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name="执行时间"
    )

    # 元数据 (JSON格式,存储额外信息)
    # 例如: {"total": 500, "success": 480, "failed": 20, "duration_seconds": 180}
    metadata = models.JSONField(
        null=True,
        blank=True,
        verbose_name="元数据"
    )

    class Meta:
        db_table = "update_log"
        verbose_name = "更新日志"
        verbose_name_plural = "更新日志"
        ordering = ["-executed_at"]
        indexes = [
            models.Index(fields=["batch_id"]),
            models.Index(fields=["symbol"]),
            models.Index(fields=["operation_type", "status"]),
            models.Index(fields=["executed_at"]),
        ]

    def __str__(self):
        return f"{self.get_operation_type_display()} - {self.get_status_display()} ({self.executed_at})"

    @classmethod
    def log_batch_start(cls, operation_type):
        """记录批次开始"""
        batch_id = uuid.uuid4()
        cls.objects.create(
            batch_id=batch_id,
            operation_type=operation_type,
            status=cls.Status.SUCCESS,
            metadata={"status": "started"}
        )
        return batch_id

    @classmethod
    def log_batch_complete(cls, batch_id, total, success, failed, duration):
        """记录批次完成"""
        status = cls.Status.SUCCESS if failed == 0 else (
            cls.Status.PARTIAL if success > 0 else cls.Status.FAILURE
        )
        cls.objects.create(
            batch_id=batch_id,
            operation_type=cls.OperationType.DATA_FETCH,
            status=status,
            metadata={
                "status": "completed",
                "total": total,
                "success": success,
                "failed": failed,
                "duration_seconds": duration
            }
        )

    @classmethod
    def log_symbol_error(cls, batch_id, symbol, error):
        """记录单个symbol的错误"""
        cls.objects.create(
            batch_id=batch_id,
            symbol=symbol,
            operation_type=cls.OperationType.DATA_FETCH,
            status=cls.Status.FAILURE,
            error_message=str(error)
        )
```

### 字段说明

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | AutoField | PK | 主键 |
| batch_id | UUIDField | INDEX | 批次ID,用于关联同一批次的日志 |
| symbol | CharField(20) | NULL, INDEX | 处理的symbol,批量操作时为NULL |
| operation_type | CharField(20) | CHOICES, INDEX | 操作类型(mapping_update/data_fetch) |
| status | CharField(10) | CHOICES, INDEX | 状态(success/failure/partial) |
| error_message | TextField | NULL | 错误信息详情 |
| executed_at | DateTimeField | INDEX | 执行时间 |
| metadata | JSONField | NULL | 额外元数据(total, success, failed等) |

### 数据示例

```json
[
  {
    "id": 1,
    "batch_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "symbol": null,
    "operation_type": "data_fetch",
    "status": "partial",
    "error_message": null,
    "executed_at": "2025-12-12T04:05:00Z",
    "metadata": {
      "status": "completed",
      "total": 500,
      "success": 480,
      "failed": 20,
      "duration_seconds": 180
    }
  },
  {
    "id": 2,
    "batch_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "symbol": "XYZUSDT",
    "operation_type": "data_fetch",
    "status": "failure",
    "error_message": "CoinGecko API error: 404 Not Found",
    "executed_at": "2025-12-12T04:03:00Z",
    "metadata": null
  },
  {
    "id": 3,
    "batch_id": "b2c3d4e5-f678-90ab-cdef-123456789abc",
    "symbol": null,
    "operation_type": "mapping_update",
    "status": "success",
    "error_message": null,
    "executed_at": "2025-12-12T03:00:00Z",
    "metadata": {
      "new_mappings": 5,
      "updated_mappings": 2,
      "needs_review": 3
    }
  }
]
```

### 业务规则

#### 规则1: 批次管理
- 每次批量操作生成唯一的`batch_id`
- 批次开始和结束分别记录一条日志
- 批次中的每个失败的symbol单独记录一条日志

#### 规则2: 日志保留期
- 默认保留30天(根据spec规格)
- 定期清理超过30天的日志: `UpdateLog.objects.filter(executed_at__lt=thirty_days_ago).delete()`

#### 规则3: 告警触发
- 连续3次失败同一symbol → 发送告警
- 单次更新失败率>10% → 发送告警
- 查询SQL示例:
  ```sql
  SELECT symbol, COUNT(*) as failure_count
  FROM update_log
  WHERE status = 'failure'
    AND executed_at >= NOW() - INTERVAL '24 hours'
  GROUP BY symbol
  HAVING COUNT(*) >= 3;
  ```

#### 规则4: 性能监控
- `metadata`字段记录批次的执行时长
- 可用于性能趋势分析和瓶颈识别

---

## 数据迁移脚本

### 迁移文件: `00XX_add_market_cap_fdv.py`

```python
# grid_trading/migrations/00XX_add_market_cap_fdv.py
from django.db import migrations, models
import uuid
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('grid_trading', '00XX_previous_migration'),  # 替换为实际的前一个迁移
    ]

    operations = [
        # 创建TokenMapping表
        migrations.CreateModel(
            name='TokenMapping',
            fields=[
                ('id', models.AutoField(primary_key=True)),
                ('symbol', models.CharField(max_length=20, unique=True, db_index=True)),
                ('base_token', models.CharField(max_length=10)),
                ('coingecko_id', models.CharField(max_length=100, null=True, blank=True, db_index=True)),
                ('match_status', models.CharField(
                    max_length=20,
                    choices=[
                        ('auto_matched', '自动匹配'),
                        ('manual_confirmed', '人工确认'),
                        ('needs_review', '需要审核')
                    ],
                    default='needs_review',
                    db_index=True
                )),
                ('alternatives', models.JSONField(null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'token_mapping',
                'verbose_name': '代币映射',
                'verbose_name_plural': '代币映射',
                'ordering': ['symbol'],
            },
        ),

        # 创建MarketData表
        migrations.CreateModel(
            name='MarketData',
            fields=[
                ('id', models.AutoField(primary_key=True)),
                ('symbol', models.CharField(max_length=20, unique=True, db_index=True)),
                ('market_cap', models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)),
                ('fully_diluted_valuation', models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)),
                ('data_source', models.CharField(max_length=50, default='coingecko')),
                ('fetched_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'market_data',
                'verbose_name': '市场数据',
                'verbose_name_plural': '市场数据',
                'ordering': ['-updated_at'],
            },
        ),

        # 创建UpdateLog表
        migrations.CreateModel(
            name='UpdateLog',
            fields=[
                ('id', models.AutoField(primary_key=True)),
                ('batch_id', models.UUIDField(default=uuid.uuid4, db_index=True)),
                ('symbol', models.CharField(max_length=20, null=True, blank=True, db_index=True)),
                ('operation_type', models.CharField(
                    max_length=20,
                    choices=[
                        ('mapping_update', '映射更新'),
                        ('data_fetch', '数据获取')
                    ],
                    db_index=True
                )),
                ('status', models.CharField(
                    max_length=10,
                    choices=[
                        ('success', '成功'),
                        ('failure', '失败'),
                        ('partial', '部分成功')
                    ],
                    db_index=True
                )),
                ('error_message', models.TextField(null=True, blank=True)),
                ('executed_at', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('metadata', models.JSONField(null=True, blank=True)),
            ],
            options={
                'db_table': 'update_log',
                'verbose_name': '更新日志',
                'verbose_name_plural': '更新日志',
                'ordering': ['-executed_at'],
            },
        ),

        # 添加索引
        migrations.AddIndex(
            model_name='tokenmapping',
            index=models.Index(fields=['symbol'], name='token_mapping_symbol_idx'),
        ),
        migrations.AddIndex(
            model_name='tokenmapping',
            index=models.Index(fields=['match_status'], name='token_mapping_status_idx'),
        ),
        migrations.AddIndex(
            model_name='marketdata',
            index=models.Index(fields=['symbol'], name='market_data_symbol_idx'),
        ),
        migrations.AddIndex(
            model_name='marketdata',
            index=models.Index(fields=['updated_at'], name='market_data_updated_idx'),
        ),
        migrations.AddIndex(
            model_name='updatelog',
            index=models.Index(fields=['batch_id'], name='update_log_batch_idx'),
        ),
        migrations.AddIndex(
            model_name='updatelog',
            index=models.Index(fields=['operation_type', 'status'], name='update_log_op_status_idx'),
        ),
    ]
```

### 运行迁移

```bash
# 生成迁移文件
python manage.py makemigrations grid_trading --name add_market_cap_fdv

# 执行迁移
python manage.py migrate grid_trading

# 验证表创建
python manage.py dbshell
.tables  # (SQLite)
\dt      # (PostgreSQL)
```

---

## 数据库索引策略

### TokenMapping表索引
1. **symbol** (UNIQUE INDEX) - 主查询字段,用于JOIN
2. **match_status** (INDEX) - 用于过滤"可用于更新"的记录
3. **coingecko_id** (INDEX) - 用于反向查找

### MarketData表索引
1. **symbol** (UNIQUE INDEX) - 主查询字段,用于JOIN
2. **updated_at** (INDEX) - 用于查找最近更新的数据

### UpdateLog表索引
1. **batch_id** (INDEX) - 用于查找同一批次的所有日志
2. **(operation_type, status)** (COMPOSITE INDEX) - 用于统计分析
3. **executed_at** (INDEX) - 用于时间范围查询和清理旧日志
4. **symbol** (INDEX) - 用于查找特定symbol的失败记录

### 性能验证

```sql
-- 查询某个symbol的市值/FDV (最常见查询)
EXPLAIN ANALYZE
SELECT mc.market_cap, mc.fully_diluted_valuation
FROM market_data mc
WHERE mc.symbol = 'BTCUSDT';

-- 预期: Index Scan on market_data_symbol_idx

-- 查询所有可用于更新的映射 (数据更新时的查询)
EXPLAIN ANALYZE
SELECT tm.symbol, tm.coingecko_id
FROM token_mapping tm
WHERE tm.match_status IN ('auto_matched', 'manual_confirmed')
  AND tm.coingecko_id IS NOT NULL;

-- 预期: Index Scan on token_mapping_status_idx

-- 查询近24小时失败的更新 (告警查询)
EXPLAIN ANALYZE
SELECT ul.symbol, COUNT(*) as failure_count
FROM update_log ul
WHERE ul.status = 'failure'
  AND ul.executed_at >= NOW() - INTERVAL '24 hours'
GROUP BY ul.symbol
HAVING COUNT(*) >= 3;

-- 预期: Index Scan on update_log_op_status_idx
```

---

## 数据一致性与完整性

### 一致性保证

#### 1. TokenMapping ↔ MarketData一致性
- MarketData.symbol必须存在于TokenMapping中
- 使用应用层逻辑保证(Django ORM级别)
- 不使用外键约束(避免级联删除的复杂性)

#### 2. 数据更新原子性
- 每次批量更新使用数据库事务
- 失败时回滚,确保数据不会部分更新

```python
from django.db import transaction

@transaction.atomic
def update_market_data_batch(market_data_list):
    """原子性批量更新"""
    for data in market_data_list:
        MarketData.objects.update_or_create(
            symbol=data["symbol"],
            defaults={
                "market_cap": data["market_cap"],
                "fully_diluted_valuation": data["fdv"],
                "fetched_at": timezone.now()
            }
        )
```

### 数据清理策略

#### UpdateLog清理
```python
# grid_trading/management/commands/cleanup_update_logs.py
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from grid_trading.models import UpdateLog


class Command(BaseCommand):
    help = '清理30天前的更新日志'

    def handle(self, *args, **options):
        cutoff_date = timezone.now() - timedelta(days=30)
        deleted_count, _ = UpdateLog.objects.filter(
            executed_at__lt=cutoff_date
        ).delete()

        self.stdout.write(
            self.style.SUCCESS(f'成功删除 {deleted_count} 条历史日志')
        )
```

---

## 测试数据准备

### Fixture文件: `test_market_data.json`

```json
[
  {
    "model": "grid_trading.tokenmapping",
    "pk": 1,
    "fields": {
      "symbol": "BTCUSDT",
      "base_token": "BTC",
      "coingecko_id": "bitcoin",
      "match_status": "auto_matched",
      "alternatives": null,
      "created_at": "2025-12-12T00:00:00Z",
      "updated_at": "2025-12-12T00:00:00Z"
    }
  },
  {
    "model": "grid_trading.marketdata",
    "pk": 1,
    "fields": {
      "symbol": "BTCUSDT",
      "market_cap": "1234567890123.45",
      "fully_diluted_valuation": "1300000000000.00",
      "data_source": "coingecko",
      "fetched_at": "2025-12-12T04:00:00Z",
      "created_at": "2025-12-12T04:00:00Z",
      "updated_at": "2025-12-12T04:00:00Z"
    }
  }
]
```

### 加载测试数据

```bash
python manage.py loaddata test_market_data.json
```

---

**Data Model Designed by**: Claude Code
**Date**: 2025-12-12
**Status**: Ready for Implementation ✅
