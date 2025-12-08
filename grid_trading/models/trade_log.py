"""
交易日志模型 (TradeLog)
记录网格交易的关键事件

参考 ritmex-bot 的事件系统设计：
- info: 一般信息（网格初始化、状态变化等）
- warn: 警告信息（达到持仓上限、冷却期等）
- error: 错误信息（订单失败、API错误等）
- order: 订单操作（挂单、撤单）
- fill: 成交通知
"""
from django.db import models


class LogType(models.TextChoices):
    """日志类型枚举 - 对齐 ritmex-bot 的事件类型"""
    INFO = 'info', '信息'
    WARN = 'warn', '警告'
    ERROR = 'error', '错误'
    ORDER = 'order', '订单'
    FILL = 'fill', '成交'


class TradeLog(models.Model):
    """交易日志模型"""
    
    # 关联
    config = models.ForeignKey(
        'GridConfig',
        on_delete=models.CASCADE,
        related_name='trade_logs',
        verbose_name='网格配置'
    )
    
    # 日志信息
    log_type = models.CharField(
        max_length=20,
        choices=LogType.choices,
        verbose_name='日志类型'
    )
    detail = models.TextField(
        verbose_name='详细描述',
        help_text='日志的详细内容'
    )
    
    # 时间戳
    timestamp = models.BigIntegerField(
        verbose_name='Unix毫秒时间戳',
        help_text='事件发生的时间戳'
    )
    
    # 关联信息
    order_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='关联订单ID',
        help_text='如果是订单相关事件，记录订单ID'
    )
    level_index = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='网格层级',
        help_text='如果是层级相关事件，记录层级索引'
    )
    
    # Django时间戳
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    
    class Meta:
        verbose_name = '交易日志'
        verbose_name_plural = '交易日志'
        db_table = 'trade_log'
        indexes = [
            models.Index(fields=['config', '-timestamp'], name='idx_log_config_time'),
            models.Index(fields=['config', 'log_type'], name='idx_log_config_type'),
            models.Index(fields=['order_id'], name='idx_log_order_id'),
        ]
        ordering = ['-timestamp']  # 默认按时间倒序
    
    def __str__(self):
        return f"[{self.log_type}] {self.config.name} - {self.detail[:50]}"
    
    @classmethod
    def log(cls, config, log_type, detail, order_id=None, level_index=None):
        """便捷的日志记录方法"""
        import time
        timestamp = int(time.time() * 1000)
        return cls.objects.create(
            config=config,
            log_type=log_type,
            detail=detail,
            timestamp=timestamp,
            order_id=order_id,
            level_index=level_index
        )

    @classmethod
    def log_info(cls, config, detail, order_id=None, level_index=None):
        """记录信息事件"""
        return cls.log(config, LogType.INFO, detail, order_id, level_index)

    @classmethod
    def log_warn(cls, config, detail, order_id=None, level_index=None):
        """记录警告事件"""
        return cls.log(config, LogType.WARN, detail, order_id, level_index)

    @classmethod
    def log_error(cls, config, detail, order_id=None, level_index=None):
        """记录错误事件"""
        return cls.log(config, LogType.ERROR, detail, order_id, level_index)

    @classmethod
    def log_order(cls, config, detail, order_id=None, level_index=None):
        """记录订单操作事件（挂单、撤单）"""
        return cls.log(config, LogType.ORDER, detail, order_id, level_index)

    @classmethod
    def log_fill(cls, config, detail, order_id, level_index=None):
        """记录成交事件"""
        return cls.log(config, LogType.FILL, detail, order_id, level_index)

    @classmethod
    def get_recent_logs(cls, config, limit=200):
        """获取最近的日志"""
        return cls.objects.filter(config=config).order_by('-timestamp')[:limit]

    @classmethod
    def cleanup_old_logs(cls, config, keep_count=1000):
        """
        清理旧日志，保留最近的N条

        Args:
            config: 网格配置
            keep_count: 保留的日志数量

        Returns:
            删除的日志数量
        """
        total = cls.objects.filter(config=config).count()
        if total <= keep_count:
            return 0

        # 获取第N条记录的时间戳
        threshold_log = cls.objects.filter(config=config).order_by('-timestamp')[keep_count:keep_count+1].first()
        if not threshold_log:
            return 0

        # 删除比第N条更旧的记录
        deleted_count, _ = cls.objects.filter(
            config=config,
            timestamp__lt=threshold_log.timestamp
        ).delete()

        return deleted_count
