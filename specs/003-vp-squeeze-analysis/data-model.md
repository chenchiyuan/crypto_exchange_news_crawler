# Data Model: VP-Squeeze算法支撑压力位计算服务

**Created**: 2025-11-24
**Status**: Complete

## Entity Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      VPSqueezeResult                        │
│  ─────────────────────────────────────────────────────────  │
│  存储VP-Squeeze分析结果的持久化模型                            │
└─────────────────────────────────────────────────────────────┘
```

本功能为单一模型设计，无复杂关联关系。

---

## 1. VPSqueezeResult

### Description
存储VP-Squeeze算法的完整分析结果，支持历史查询和Admin展示。

### Fields

| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| id | BigAutoField | PK, auto | 主键 |
| symbol | CharField(20) | NOT NULL, indexed | 交易对，如ETHUSDT |
| interval | CharField(10) | NOT NULL | 时间周期，如4h |
| analyzed_at | DateTimeField | NOT NULL, indexed | 分析时间 |
| klines_count | PositiveIntegerField | NOT NULL | 使用的K线数量 |
| squeeze_active | BooleanField | NOT NULL | Squeeze是否有效 |
| squeeze_consecutive_bars | PositiveIntegerField | NOT NULL | 连续满足条件的K线数 |
| reliability | CharField(10) | NOT NULL | 可靠度: high/low |
| val | DecimalField(20,8) | NOT NULL | 支撑位 (Value Area Low) |
| vah | DecimalField(20,8) | NOT NULL | 压力位 (Value Area High) |
| vpoc | DecimalField(20,8) | NOT NULL | 成交量重心 (Volume POC) |
| hvn_data | JSONField | NOT NULL | 高量节点列表 |
| lvn_data | JSONField | NOT NULL | 低量节点列表 |
| price_min | DecimalField(20,8) | NOT NULL | 分析期间最低价 |
| price_max | DecimalField(20,8) | NOT NULL | 分析期间最高价 |
| total_volume | DecimalField(30,8) | NOT NULL | 总成交量 |
| bb_upper | DecimalField(20,8) | NULL | 最新BB上轨 |
| bb_lower | DecimalField(20,8) | NULL | 最新BB下轨 |
| kc_upper | DecimalField(20,8) | NULL | 最新KC上轨 |
| kc_lower | DecimalField(20,8) | NULL | 最新KC下轨 |
| raw_result | JSONField | NULL | 完整原始计算结果 |
| created_at | DateTimeField | auto_now_add | 记录创建时间 |

### Indexes

```python
class Meta:
    db_table = 'vp_squeeze_results'
    verbose_name = 'VP-Squeeze分析结果'
    verbose_name_plural = 'VP-Squeeze分析结果'
    ordering = ['-analyzed_at']
    indexes = [
        models.Index(fields=['symbol', 'interval', '-analyzed_at']),
        models.Index(fields=['squeeze_active', '-analyzed_at']),
    ]
    constraints = [
        models.UniqueConstraint(
            fields=['symbol', 'interval', 'analyzed_at'],
            name='unique_analysis_per_time'
        )
    ]
```

### Django Model Definition

```python
from django.db import models
from decimal import Decimal


class VPSqueezeResult(models.Model):
    """VP-Squeeze分析结果模型"""

    RELIABILITY_CHOICES = [
        ('high', '高'),
        ('low', '低'),
    ]

    # 基本信息
    symbol = models.CharField(
        max_length=20,
        verbose_name='交易对',
        db_index=True
    )
    interval = models.CharField(
        max_length=10,
        verbose_name='时间周期'
    )
    analyzed_at = models.DateTimeField(
        verbose_name='分析时间',
        db_index=True
    )
    klines_count = models.PositiveIntegerField(
        verbose_name='K线数量'
    )

    # Squeeze状态
    squeeze_active = models.BooleanField(
        verbose_name='Squeeze有效',
        help_text='是否处于有效的盘整状态'
    )
    squeeze_consecutive_bars = models.PositiveIntegerField(
        verbose_name='连续K线数',
        help_text='连续满足Squeeze条件的K线数量'
    )
    reliability = models.CharField(
        max_length=10,
        choices=RELIABILITY_CHOICES,
        verbose_name='可靠度'
    )

    # 核心价位
    val = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='支撑位(VAL)'
    )
    vah = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='压力位(VAH)'
    )
    vpoc = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='成交量重心(VPOC)'
    )

    # 节点数据
    hvn_data = models.JSONField(
        verbose_name='高量节点(HVN)',
        default=list,
        help_text='高成交量价格区间列表'
    )
    lvn_data = models.JSONField(
        verbose_name='低量节点(LVN)',
        default=list,
        help_text='低成交量价格区间列表'
    )

    # 统计信息
    price_min = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='最低价'
    )
    price_max = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='最高价'
    )
    total_volume = models.DecimalField(
        max_digits=30,
        decimal_places=8,
        verbose_name='总成交量'
    )

    # 技术指标快照
    bb_upper = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name='BB上轨'
    )
    bb_lower = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name='BB下轨'
    )
    kc_upper = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name='KC上轨'
    )
    kc_lower = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name='KC下轨'
    )

    # 原始数据
    raw_result = models.JSONField(
        null=True,
        blank=True,
        verbose_name='原始结果',
        help_text='完整的计算结果JSON'
    )

    # 时间戳
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )

    class Meta:
        db_table = 'vp_squeeze_results'
        verbose_name = 'VP-Squeeze分析结果'
        verbose_name_plural = 'VP-Squeeze分析结果'
        ordering = ['-analyzed_at']
        indexes = [
            models.Index(fields=['symbol', 'interval', '-analyzed_at']),
            models.Index(fields=['squeeze_active', '-analyzed_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['symbol', 'interval', 'analyzed_at'],
                name='unique_analysis_per_time'
            )
        ]

    def __str__(self):
        status = '✓' if self.squeeze_active else '✗'
        return f"{self.symbol} ({self.interval}) {status} @ {self.analyzed_at:%Y-%m-%d %H:%M}"

    @property
    def price_range_pct(self) -> float:
        """价格波动百分比"""
        if self.price_min and self.price_min > 0:
            return float((self.price_max - self.price_min) / self.price_min * 100)
        return 0.0

    @property
    def value_area_range(self) -> float:
        """价值区域范围（VAH - VAL）"""
        return float(self.vah - self.val)
```

---

## 2. Data Transfer Objects (DTO)

### 2.1 KLineData

用于内部传递K线数据的数据类。

```python
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class KLineData:
    """K线数据"""
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: datetime
    quote_volume: float
    trade_count: int
    taker_buy_volume: float
    taker_buy_quote_volume: float

    @classmethod
    def from_binance_response(cls, data: list) -> 'KLineData':
        """从币安API响应创建"""
        return cls(
            open_time=datetime.fromtimestamp(data[0] / 1000),
            open=float(data[1]),
            high=float(data[2]),
            low=float(data[3]),
            close=float(data[4]),
            volume=float(data[5]),
            close_time=datetime.fromtimestamp(data[6] / 1000),
            quote_volume=float(data[7]),
            trade_count=int(data[8]),
            taker_buy_volume=float(data[9]),
            taker_buy_quote_volume=float(data[10]),
        )
```

### 2.2 SqueezeStatus

```python
@dataclass
class SqueezeStatus:
    """Squeeze状态"""
    active: bool
    consecutive_bars: int
    reliability: str  # 'high' or 'low'
    signals: list[bool]  # 每根K线的Squeeze信号
```

### 2.3 VolumeProfileResult

```python
@dataclass
class VolumeProfileResult:
    """Volume Profile计算结果"""
    vpoc: float
    vah: float
    val: float
    hvn: list[dict]  # [{'low': float, 'high': float, 'volume': float}]
    lvn: list[dict]  # [{'low': float, 'high': float, 'volume': float}]
    profile: dict[float, float]  # 价格桶 -> 成交量
```

### 2.4 VPSqueezeAnalysisResult

```python
@dataclass
class VPSqueezeAnalysisResult:
    """VP-Squeeze完整分析结果"""
    symbol: str
    interval: str
    timestamp: datetime
    klines_count: int

    # Squeeze状态
    squeeze: SqueezeStatus

    # Volume Profile
    volume_profile: VolumeProfileResult

    # 价格范围
    price_min: float
    price_max: float
    total_volume: float

    # 技术指标快照
    bb_upper: float
    bb_lower: float
    kc_upper: float
    kc_lower: float

    def to_dict(self) -> dict:
        """转换为字典（用于JSON输出）"""
        return {
            'symbol': self.symbol,
            'interval': self.interval,
            'timestamp': self.timestamp.isoformat(),
            'squeeze': {
                'active': self.squeeze.active,
                'consecutive_bars': self.squeeze.consecutive_bars,
                'reliability': self.squeeze.reliability,
            },
            'levels': {
                'val': self.volume_profile.val,
                'vah': self.volume_profile.vah,
                'vpoc': self.volume_profile.vpoc,
            },
            'hvn': self.volume_profile.hvn,
            'lvn': self.volume_profile.lvn,
            'metadata': {
                'klines_count': self.klines_count,
                'price_range': {
                    'min': self.price_min,
                    'max': self.price_max,
                },
                'total_volume': self.total_volume,
            },
        }

    def to_model(self) -> 'VPSqueezeResult':
        """转换为Django模型实例"""
        from vp_squeeze.models import VPSqueezeResult
        return VPSqueezeResult(
            symbol=self.symbol,
            interval=self.interval,
            analyzed_at=self.timestamp,
            klines_count=self.klines_count,
            squeeze_active=self.squeeze.active,
            squeeze_consecutive_bars=self.squeeze.consecutive_bars,
            reliability=self.squeeze.reliability,
            val=Decimal(str(self.volume_profile.val)),
            vah=Decimal(str(self.volume_profile.vah)),
            vpoc=Decimal(str(self.volume_profile.vpoc)),
            hvn_data=self.volume_profile.hvn,
            lvn_data=self.volume_profile.lvn,
            price_min=Decimal(str(self.price_min)),
            price_max=Decimal(str(self.price_max)),
            total_volume=Decimal(str(self.total_volume)),
            bb_upper=Decimal(str(self.bb_upper)) if self.bb_upper else None,
            bb_lower=Decimal(str(self.bb_lower)) if self.bb_lower else None,
            kc_upper=Decimal(str(self.kc_upper)) if self.kc_upper else None,
            kc_lower=Decimal(str(self.kc_lower)) if self.kc_lower else None,
            raw_result=self.to_dict(),
        )
```

---

## 3. Validation Rules

### 3.1 Symbol验证

```python
VALID_SYMBOLS = {
    'btc', 'eth', 'bnb', 'sol', 'xrp',
    'doge', 'ada', 'avax', 'dot', 'matic'
}

def validate_symbol(symbol: str) -> bool:
    """验证symbol是否在支持列表中"""
    return symbol.lower() in VALID_SYMBOLS or symbol.upper().endswith('USDT')
```

### 3.2 Interval验证

```python
VALID_INTERVALS = {
    '1m', '3m', '5m', '15m', '30m',
    '1h', '2h', '4h', '6h', '8h', '12h',
    '1d', '3d', '1w', '1M'
}

def validate_interval(interval: str) -> bool:
    """验证时间周期是否有效"""
    return interval in VALID_INTERVALS
```

### 3.3 K线数量验证

```python
MIN_KLINES = 30  # 最少需要30根K线（BB周期20 + 缓冲）
MAX_KLINES = 1500  # 币安API最大限制

def validate_klines_count(count: int) -> bool:
    """验证K线数量是否在有效范围内"""
    return MIN_KLINES <= count <= MAX_KLINES
```

---

## 4. State Transitions

本功能无复杂状态转换，分析结果为一次性计算产出。

```
[API请求] → [获取K线] → [计算指标] → [生成结果] → [可选：持久化]
```

---

## 5. Admin Configuration

```python
from django.contrib import admin
from .models import VPSqueezeResult


@admin.register(VPSqueezeResult)
class VPSqueezeResultAdmin(admin.ModelAdmin):
    list_display = [
        'symbol', 'interval', 'squeeze_active', 'reliability',
        'val', 'vah', 'vpoc', 'analyzed_at'
    ]
    list_filter = ['symbol', 'interval', 'squeeze_active', 'reliability']
    search_fields = ['symbol']
    date_hierarchy = 'analyzed_at'
    readonly_fields = ['created_at', 'raw_result']

    fieldsets = (
        ('基本信息', {
            'fields': ('symbol', 'interval', 'analyzed_at', 'klines_count')
        }),
        ('Squeeze状态', {
            'fields': ('squeeze_active', 'squeeze_consecutive_bars', 'reliability')
        }),
        ('关键价位', {
            'fields': ('val', 'vah', 'vpoc')
        }),
        ('节点数据', {
            'fields': ('hvn_data', 'lvn_data'),
            'classes': ('collapse',)
        }),
        ('技术指标', {
            'fields': ('bb_upper', 'bb_lower', 'kc_upper', 'kc_lower'),
            'classes': ('collapse',)
        }),
        ('统计信息', {
            'fields': ('price_min', 'price_max', 'total_volume'),
            'classes': ('collapse',)
        }),
        ('系统信息', {
            'fields': ('created_at', 'raw_result'),
            'classes': ('collapse',)
        }),
    )
```
