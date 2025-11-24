"""VP-Squeeze数据模型"""
from django.db import models


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
