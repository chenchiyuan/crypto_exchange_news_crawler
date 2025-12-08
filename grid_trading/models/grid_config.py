"""
网格配置模型 (GridConfig)
存储网格策略的所有配置参数
"""
from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError


class GridMode(models.TextChoices):
    """网格模式枚举"""
    SHORT = 'SHORT', '做空网格'
    NEUTRAL = 'NEUTRAL', '中性网格'
    LONG = 'LONG', '做多网格'


class GridConfig(models.Model):
    """网格配置模型"""
    
    # 基本信息
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='配置名称',
        help_text='唯一标识，如 btc_short_grid'
    )
    exchange = models.CharField(
        max_length=50,
        verbose_name='交易所',
        help_text='交易所代码: binance/okx/bybit'
    )
    symbol = models.CharField(
        max_length=20,
        verbose_name='交易对',
        help_text='交易对代码: BTCUSDT'
    )
    grid_mode = models.CharField(
        max_length=10,
        choices=GridMode.choices,
        verbose_name='网格模式',
        help_text='做空/中性/做多'
    )
    
    # 价格配置
    upper_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='价格上界',
        help_text='网格价格上界'
    )
    lower_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='价格下界',
        help_text='网格价格下界'
    )
    grid_levels = models.IntegerField(
        verbose_name='网格层数',
        help_text='网格总数量，至少5层'
    )
    
    # 交易配置
    trade_amount = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='单笔开仓数量',
        help_text='每次开仓的数量'
    )
    max_position_size = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='最大持仓限制',
        help_text='最大持仓数量'
    )
    
    # 风控配置
    stop_loss_buffer_pct = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        default=Decimal('0.0050'),
        verbose_name='止损缓冲区百分比',
        help_text='默认0.5%'
    )
    
    # 系统配置
    refresh_interval_ms = models.IntegerField(
        default=1000,
        verbose_name='轮询间隔(毫秒)',
        help_text='订单同步间隔，默认1000ms'
    )
    price_tick = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='价格精度',
        help_text='如0.01'
    )
    qty_step = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='数量精度',
        help_text='如0.001'
    )
    
    # 状态
    is_active = models.BooleanField(
        default=False,
        verbose_name='是否启用',
        help_text='启用后策略开始运行'
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
        verbose_name = '网格配置'
        verbose_name_plural = '网格配置'
        db_table = 'grid_config'
        indexes = [
            models.Index(fields=['name'], name='idx_config_name'),
            models.Index(fields=['exchange', 'symbol'], name='idx_config_exchange_symbol'),
            models.Index(fields=['is_active'], name='idx_config_active'),
        ]
    
    def clean(self):
        """验证规则"""
        errors = {}
        
        # 价格验证
        if self.lower_price and self.upper_price:
            if self.lower_price >= self.upper_price:
                errors['lower_price'] = '下界价格必须小于上界价格'
        
        if self.upper_price and self.upper_price <= 0:
            errors['upper_price'] = '价格上界必须大于0'
        
        if self.lower_price and self.lower_price <= 0:
            errors['lower_price'] = '价格下界必须大于0'
        
        # 网格层数验证
        if self.grid_levels and self.grid_levels < 5:
            errors['grid_levels'] = '网格数量至少为5'
        
        # 持仓验证
        if self.max_position_size and self.max_position_size <= 0:
            errors['max_position_size'] = '最大持仓限制必须大于0'
        
        # 交易数量验证
        if self.trade_amount is not None and self.trade_amount <= 0:
            errors['trade_amount'] = '单笔金额必须大于0'

        # 精度验证
        if self.price_tick is not None and self.price_tick <= 0:
            errors['price_tick'] = '价格精度必须大于0'

        if self.qty_step is not None and self.qty_step <= 0:
            errors['qty_step'] = '数量精度必须大于0'
        
        # 止损缓冲区验证
        if self.stop_loss_buffer_pct and (
            self.stop_loss_buffer_pct < 0 or self.stop_loss_buffer_pct > 1
        ):
            errors['stop_loss_buffer_pct'] = '止损缓冲区百分比必须在0-1之间'
        
        # 轮询间隔验证
        if self.refresh_interval_ms and self.refresh_interval_ms < 100:
            errors['refresh_interval_ms'] = '轮询间隔不能小于100毫秒'
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        """保存前验证"""
        self.clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name} ({self.exchange} {self.symbol} {self.grid_mode})"
    
    @property
    def grid_spacing(self):
        """计算网格间距"""
        if self.grid_levels <= 1:
            return Decimal('0')
        upper = Decimal(str(self.upper_price))
        lower = Decimal(str(self.lower_price))
        return (upper - lower) / Decimal(self.grid_levels - 1)

    @property
    def grid_spacing_pct(self):
        """计算网格间距百分比"""
        upper = Decimal(str(self.upper_price))
        lower = Decimal(str(self.lower_price))
        center_price = (upper + lower) / Decimal('2')
        if center_price == 0:
            return Decimal('0')
        return (self.grid_spacing / center_price) * Decimal('100')
