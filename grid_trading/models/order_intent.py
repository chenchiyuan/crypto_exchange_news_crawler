"""
订单意图模型 (OrderIntent)
追踪订单的业务意图，用于状态同步和幂等性保证
"""
import hashlib
from decimal import Decimal
from django.db import models


class OrderIntentType(models.TextChoices):
    """订单意图类型枚举"""
    ENTRY = 'ENTRY', '开仓'
    EXIT = 'EXIT', '平仓'


class OrderSide(models.TextChoices):
    """订单方向枚举"""
    BUY = 'BUY', '买入'
    SELL = 'SELL', '卖出'


class OrderStatus(models.TextChoices):
    """订单状态枚举"""
    NEW = 'NEW', '新建'
    PARTIALLY_FILLED = 'PARTIALLY_FILLED', '部分成交'
    FILLED = 'FILLED', '完全成交'
    CANCELED = 'CANCELED', '已撤销'
    REJECTED = 'REJECTED', '已拒绝'
    EXPIRED = 'EXPIRED', '已过期'


class OrderIntent(models.Model):
    """订单意图模型"""
    
    # 关联
    config = models.ForeignKey(
        'GridConfig',
        on_delete=models.CASCADE,
        related_name='order_intents',
        verbose_name='网格配置'
    )
    
    # 订单标识
    order_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='交易所订单ID',
        help_text='创建订单后由交易所返回'
    )
    client_order_id = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='客户端订单ID',
        help_text='业务唯一标识，用于幂等性保证'
    )
    
    # 层级信息
    level_index = models.IntegerField(
        verbose_name='网格层级',
        help_text='对应的网格层级索引'
    )
    
    # 订单意图
    intent = models.CharField(
        max_length=10,
        choices=OrderIntentType.choices,
        verbose_name='意图',
        help_text='开仓或平仓'
    )
    side = models.CharField(
        max_length=10,
        choices=OrderSide.choices,
        verbose_name='方向',
        help_text='买入或卖出'
    )
    
    # 订单参数
    price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='订单价格'
    )
    amount = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='订单数量'
    )
    
    # 订单状态
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.NEW,
        verbose_name='订单状态'
    )
    
    # 时间戳
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='完结时间',
        help_text='订单成交或撤销的时间'
    )
    
    class Meta:
        verbose_name = '订单意图'
        verbose_name_plural = '订单意图'
        db_table = 'order_intent'
        indexes = [
            models.Index(fields=['config', 'level_index'], name='idx_intent_config_level'),
            models.Index(fields=['order_id'], name='idx_intent_order_id'),
            models.Index(fields=['client_order_id'], name='idx_intent_client_id'),
            models.Index(fields=['status'], name='idx_intent_status'),
        ]
    
    def __str__(self):
        return f"{self.config.name} {self.intent} {self.side} @ {self.price} (Level {self.level_index})"
    
    @staticmethod
    def generate_client_order_id(config_name: str, intent: str, side: str, level: int, price: Decimal) -> str:
        """
        生成客户端订单ID
        格式: {config}_{intent}_{side}_{level}_{price_hash}
        例如: btc_short_ENTRY_SELL_5_a3f2
        """
        price_hash = hashlib.md5(str(price).encode()).hexdigest()[:4]
        return f"{config_name}_{intent}_{side}_{level}_{price_hash}"
    
    def is_active(self):
        """订单是否处于活跃状态"""
        return self.status in [OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED]
    
    def is_finished(self):
        """订单是否已完结"""
        return self.status in [OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED, OrderStatus.EXPIRED]
    
    def mark_filled(self):
        """标记订单为完全成交"""
        from django.utils import timezone
        self.status = OrderStatus.FILLED
        self.resolved_at = timezone.now()
        self.save()
    
    def mark_canceled(self):
        """标记订单为已撤销"""
        from django.utils import timezone
        self.status = OrderStatus.CANCELED
        self.resolved_at = timezone.now()
        self.save()
    
    def get_quadruple(self):
        """获取订单四元组标识"""
        return (self.intent, self.side, str(self.price), self.level_index)
