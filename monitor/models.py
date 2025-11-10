"""
数据模型定义
包含4个核心模型: Exchange, Announcement, Listing, NotificationRecord
"""
from django.db import models
from django.utils import timezone


class Exchange(models.Model):
    """交易所模型"""

    # 基本信息
    name = models.CharField(max_length=100, unique=True, verbose_name='交易所名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='交易所代码')
    announcement_url = models.URLField(max_length=500, blank=True, verbose_name='公告URL')

    # 状态
    enabled = models.BooleanField(default=True, verbose_name='是否启用')

    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'exchanges'
        verbose_name = '交易所'
        verbose_name_plural = '交易所'
        ordering = ['id']

    def __str__(self):
        return f"{self.name} ({self.code})"


class Announcement(models.Model):
    """公告模型"""

    # 公告信息
    news_id = models.CharField(max_length=200, unique=True, verbose_name='公告ID',
                               help_text='交易所提供的唯一ID')
    title = models.CharField(max_length=1000, verbose_name='公告标题')
    description = models.TextField(blank=True, verbose_name='公告描述')
    url = models.URLField(max_length=1000, unique=True, verbose_name='公告URL')
    announced_at = models.DateTimeField(verbose_name='发布时间')

    # 分类
    category = models.CharField(max_length=100, blank=True, verbose_name='分类')

    # 外键
    exchange = models.ForeignKey(
        Exchange,
        on_delete=models.CASCADE,
        related_name='announcements',
        verbose_name='交易所'
    )

    # 处理状态
    processed = models.BooleanField(default=False, verbose_name='是否已处理')

    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'announcements'
        ordering = ['-announced_at']
        indexes = [
            models.Index(fields=['exchange', 'announced_at'], name='idx_exchange_announced'),
            models.Index(fields=['processed'], name='idx_processed'),
            models.Index(fields=['created_at'], name='idx_created'),
        ]
        verbose_name = '公告'
        verbose_name_plural = '公告'

    def __str__(self):
        return f"{self.exchange.name} - {self.title[:30]}..."


class Listing(models.Model):
    """新币上线模型"""

    # 上线类型选择
    SPOT = 'spot'
    FUTURES = 'futures'
    BOTH = 'both'
    LISTING_TYPE_CHOICES = [
        (SPOT, '现货'),
        (FUTURES, '合约'),
        (BOTH, '现货+合约'),
    ]

    # 状态选择
    PENDING_REVIEW = 'pending_review'
    CONFIRMED = 'confirmed'
    IGNORED = 'ignored'
    STATUS_CHOICES = [
        (PENDING_REVIEW, '待审核'),
        (CONFIRMED, '已确认'),
        (IGNORED, '已忽略'),
    ]

    # 币种信息
    coin_symbol = models.CharField(max_length=50, verbose_name='币种代码',
                                   help_text='如BTC, ETH')
    coin_name = models.CharField(max_length=200, blank=True, verbose_name='币种全称',
                                help_text='如Bitcoin')
    listing_type = models.CharField(max_length=50, choices=LISTING_TYPE_CHOICES,
                                   verbose_name='上线类型')

    # 外键
    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.CASCADE,
        related_name='listings',
        verbose_name='关联公告'
    )

    # 识别信息
    confidence = models.FloatField(verbose_name='识别置信度',
                                  help_text='0.0-1.0之间的浮点数')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES,
                             default=PENDING_REVIEW, verbose_name='状态')

    # 时间戳
    identified_at = models.DateTimeField(verbose_name='识别时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='入库时间')

    class Meta:
        db_table = 'listings'
        ordering = ['-identified_at']
        indexes = [
            models.Index(fields=['status'], name='idx_listing_status'),
            models.Index(fields=['coin_symbol'], name='idx_coin_symbol'),
            models.Index(fields=['identified_at'], name='idx_identified'),
            models.Index(fields=['announcement'], name='idx_listing_announcement'),
        ]
        verbose_name = '新币上线'
        verbose_name_plural = '新币上线'

    def __str__(self):
        exchange_name = self.announcement.exchange.name if self.announcement else 'Unknown'
        return f"{exchange_name} - {self.coin_symbol} ({self.get_listing_type_display()})"

    def get_exchange(self):
        """获取关联的交易所"""
        return self.announcement.exchange if self.announcement else None


class NotificationRecord(models.Model):
    """通知记录模型"""

    # 通知渠道选择
    WEBHOOK = 'webhook'
    TELEGRAM = 'telegram'
    EMAIL = 'email'
    CHANNEL_CHOICES = [
        (WEBHOOK, 'Webhook'),
        (TELEGRAM, 'Telegram'),
        (EMAIL, 'Email'),
    ]

    # 发送状态选择
    PENDING = 'pending'
    SUCCESS = 'success'
    FAILED = 'failed'
    STATUS_CHOICES = [
        (PENDING, '待发送'),
        (SUCCESS, '发送成功'),
        (FAILED, '发送失败'),
    ]

    # 外键
    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name='notification_records',
        verbose_name='关联新币上线'
    )

    # 通知信息
    channel = models.CharField(max_length=50, choices=CHANNEL_CHOICES,
                              verbose_name='通知渠道')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES,
                             verbose_name='发送状态')
    retry_count = models.IntegerField(default=0, verbose_name='重试次数')
    error_message = models.TextField(blank=True, verbose_name='错误信息')

    # 时间戳
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name='成功发送时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'notification_records'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['listing'], name='idx_notif_listing'),
            models.Index(fields=['status'], name='idx_notif_status'),
            models.Index(fields=['created_at'], name='idx_notif_created'),
        ]
        verbose_name = '通知记录'
        verbose_name_plural = '通知记录'

    def __str__(self):
        return f"{self.listing.coin_symbol} - {self.get_channel_display()} ({self.get_status_display()})"
