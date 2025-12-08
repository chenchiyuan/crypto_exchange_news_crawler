"""
网格层级模型 (GridLevel)
记录单个网格价位的状态信息
"""
from django.db import models


class GridLevelStatus(models.TextChoices):
    """网格层级状态枚举"""
    IDLE = 'idle', '空闲'
    ENTRY_WORKING = 'entry_working', '开仓单已挂单'
    POSITION_OPEN = 'position_open', '持仓中'
    EXIT_WORKING = 'exit_working', '平仓单已挂单'


class GridLevelSide(models.TextChoices):
    """订单方向枚举"""
    BUY = 'BUY', '买入'
    SELL = 'SELL', '卖出'


class GridLevel(models.Model):
    """网格层级模型"""
    
    # 关联
    config = models.ForeignKey(
        'GridConfig',
        on_delete=models.CASCADE,
        related_name='levels',
        verbose_name='网格配置'
    )
    
    # 层级信息
    level_index = models.IntegerField(
        verbose_name='层级索引',
        help_text='层级索引，0为中心，负数为下方，正数为上方'
    )
    price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='网格价位',
        help_text='该层级的价格'
    )
    side = models.CharField(
        max_length=10,
        choices=GridLevelSide.choices,
        verbose_name='方向',
        help_text='买入或卖出'
    )
    
    # 状态机
    status = models.CharField(
        max_length=20,
        choices=GridLevelStatus.choices,
        default=GridLevelStatus.IDLE,
        verbose_name='状态',
        help_text='层级当前状态'
    )
    
    # 订单ID
    entry_order_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='开仓订单ID',
        help_text='交易所开仓订单ID'
    )
    exit_order_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='平仓订单ID',
        help_text='交易所平仓订单ID'
    )
    entry_client_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='开仓客户端ID',
        help_text='客户端开仓订单ID'
    )
    exit_client_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='平仓客户端ID',
        help_text='客户端平仓订单ID'
    )
    
    # 冷却期
    blocked_until = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name='冷却时间戳',
        help_text='Unix毫秒时间戳，为NULL表示不冷却'
    )
    
    # 时间戳
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )
    
    class Meta:
        verbose_name = '网格层级'
        verbose_name_plural = '网格层级'
        db_table = 'grid_level'
        unique_together = [['config', 'level_index']]
        indexes = [
            models.Index(fields=['config', 'level_index'], name='idx_level_config_index'),
            models.Index(fields=['config', 'status'], name='idx_level_config_status'),
        ]
    
    def __str__(self):
        return f"{self.config.name} Level {self.level_index} @ {self.price} ({self.status})"
    
    def is_blocked(self):
        """检查是否处于冷却期"""
        if self.blocked_until is None:
            return False
        import time
        current_time_ms = int(time.time() * 1000)
        return current_time_ms < self.blocked_until
    
    def can_place_entry_order(self):
        """是否可以挂开仓单"""
        return self.status == GridLevelStatus.IDLE and not self.is_blocked()
    
    def can_place_exit_order(self):
        """是否可以挂平仓单"""
        return self.status == GridLevelStatus.POSITION_OPEN and not self.is_blocked()
    
    def transition_to_entry_working(self, entry_order_id, entry_client_id):
        """状态转换: idle → entry_working"""
        if self.status != GridLevelStatus.IDLE:
            raise ValueError(f"Cannot transition from {self.status} to entry_working")
        self.status = GridLevelStatus.ENTRY_WORKING
        self.entry_order_id = entry_order_id
        self.entry_client_id = entry_client_id
        self.save()
    
    def transition_to_position_open(self):
        """状态转换: entry_working → position_open"""
        if self.status != GridLevelStatus.ENTRY_WORKING:
            raise ValueError(f"Cannot transition from {self.status} to position_open")
        self.status = GridLevelStatus.POSITION_OPEN
        self.save()
    
    def transition_to_exit_working(self, exit_order_id, exit_client_id):
        """状态转换: position_open → exit_working"""
        if self.status != GridLevelStatus.POSITION_OPEN:
            raise ValueError(f"Cannot transition from {self.status} to exit_working")
        self.status = GridLevelStatus.EXIT_WORKING
        self.exit_order_id = exit_order_id
        self.exit_client_id = exit_client_id
        self.save()
    
    def transition_to_idle(self):
        """状态转换: entry_working/exit_working → idle"""
        if self.status not in [GridLevelStatus.ENTRY_WORKING, GridLevelStatus.EXIT_WORKING]:
            raise ValueError(f"Cannot transition from {self.status} to idle")
        self.status = GridLevelStatus.IDLE
        # 清空订单ID
        if self.status == GridLevelStatus.ENTRY_WORKING:
            self.entry_order_id = None
            self.entry_client_id = None
        else:  # EXIT_WORKING
            self.exit_order_id = None
            self.exit_client_id = None
            # 完成平仓后，开仓ID也应清空
            self.entry_order_id = None
            self.entry_client_id = None
        self.save()
    
    def cancel_entry_order(self):
        """撤销开仓单"""
        if self.status != GridLevelStatus.ENTRY_WORKING:
            raise ValueError(f"Cannot cancel entry order in status {self.status}")
        self.transition_to_idle()
    
    def cancel_exit_order(self):
        """撤销平仓单"""
        if self.status != GridLevelStatus.EXIT_WORKING:
            raise ValueError(f"Cannot cancel exit order in status {self.status}")
        self.status = GridLevelStatus.POSITION_OPEN
        self.exit_order_id = None
        self.exit_client_id = None
        self.save()
    
    def set_blocked(self, duration_ms=5000):
        """设置冷却期"""
        import time
        current_time_ms = int(time.time() * 1000)
        self.blocked_until = current_time_ms + duration_ms
        self.save()
