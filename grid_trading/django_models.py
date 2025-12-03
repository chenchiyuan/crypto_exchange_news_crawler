"""
网格交易系统数据模型
Grid Trading System Models
"""
from django.db import models
from django.utils import timezone
from decimal import Decimal


class GridZone(models.Model):
    """
    支撑/压力区间模型
    Support/Resistance Zone Model

    存储Scanner模块识别的S/R价格区间
    """
    ZONE_TYPE_CHOICES = [
        ('support', '支撑区'),
        ('resistance', '压力区'),
    ]

    symbol = models.CharField('交易对', max_length=20, db_index=True)  # BTCUSDT
    zone_type = models.CharField('区间类型', max_length=20, choices=ZONE_TYPE_CHOICES, db_index=True)
    price_low = models.DecimalField('区间下界', max_digits=20, decimal_places=8)
    price_high = models.DecimalField('区间上界', max_digits=20, decimal_places=8)
    confidence = models.IntegerField('置信度', default=0, help_text='0-100, 越高越可靠')

    # 时间管理
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    expires_at = models.DateTimeField('过期时间', help_text='Scanner每次更新会刷新')
    is_active = models.BooleanField('是否激活', default=True, db_index=True)

    class Meta:
        verbose_name = '网格区间'
        verbose_name_plural = '网格区间列表'
        db_table = 'grid_zone'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['symbol', 'is_active', 'zone_type']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"{self.symbol} {self.get_zone_type_display()} [{self.price_low}-{self.price_high}]"

    def is_price_in_zone(self, price):
        """检查价格是否在区间内"""
        return self.price_low <= price <= self.price_high

    def is_expired(self):
        """检查区间是否已过期"""
        return timezone.now() > self.expires_at


class StrategyConfig(models.Model):
    """
    策略参数配置模型（可追溯）
    Strategy Configuration Model (Traceable)

    记录所有策略参数，确保每次运行都可追溯
    """
    symbol = models.CharField('交易对', max_length=20, db_index=True)
    config_name = models.CharField('配置名称', max_length=50, help_text='如: btc_default_v1')

    # 网格配置
    atr_multiplier = models.DecimalField(
        'ATR倍数', max_digits=5, decimal_places=2, default=Decimal('0.80'),
        help_text='网格步长 = ATR * 此倍数'
    )
    grid_levels = models.IntegerField('网格层数', default=10, help_text='上下各N层')
    order_size_usdt = models.DecimalField(
        '每格金额(USDT)', max_digits=10, decimal_places=2, default=Decimal('100.00')
    )

    # 风险配置
    stop_loss_pct = models.DecimalField(
        '止损百分比', max_digits=5, decimal_places=4, default=Decimal('0.10'),
        help_text='默认10%'
    )
    max_position_usdt = models.DecimalField(
        '最大仓位(USDT)', max_digits=10, decimal_places=2, default=Decimal('1000.00')
    )

    # 状态
    is_active = models.BooleanField('是否激活', default=True, db_index=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '策略配置'
        verbose_name_plural = '策略配置列表'
        db_table = 'strategy_config'
        ordering = ['-created_at']
        unique_together = [['symbol', 'config_name']]

    def __str__(self):
        return f"{self.symbol} - {self.config_name}"


class GridStrategy(models.Model):
    """
    网格策略实例模型
    Grid Strategy Instance Model

    每次启动网格交易时创建一个实例
    """
    STRATEGY_TYPE_CHOICES = [
        ('long', '做多网格'),
        ('short', '做空网格'),
    ]

    STATUS_CHOICES = [
        ('idle', '空闲'),
        ('active', '运行中'),
        ('stopped', '已停止'),
        ('error', '异常'),
    ]

    symbol = models.CharField('交易对', max_length=20, db_index=True)
    strategy_type = models.CharField('策略类型', max_length=10, choices=STRATEGY_TYPE_CHOICES)

    # 网格参数（快照）
    grid_step_pct = models.DecimalField(
        '网格步长(%)', max_digits=5, decimal_places=4,
        help_text='如0.0080表示0.8%'
    )
    grid_levels = models.IntegerField('网格层数', default=10)
    order_size = models.DecimalField(
        '每格数量', max_digits=20, decimal_places=8,
        help_text='币种数量,如0.01 BTC'
    )

    # 止损参数
    stop_loss_pct = models.DecimalField(
        '止损百分比', max_digits=5, decimal_places=4, default=Decimal('0.10')
    )

    # 运行状态
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='idle', db_index=True)
    entry_price = models.DecimalField(
        '入场价格', max_digits=20, decimal_places=8, null=True, blank=True
    )
    current_pnl = models.DecimalField(
        '当前盈亏(USDT)', max_digits=20, decimal_places=8, default=Decimal('0.00')
    )

    # 关联配置（可选，用于追溯）
    config = models.ForeignKey(
        StrategyConfig, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='使用的配置'
    )

    # 时间戳
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    started_at = models.DateTimeField('启动时间', null=True, blank=True)
    stopped_at = models.DateTimeField('停止时间', null=True, blank=True)

    class Meta:
        verbose_name = '网格策略'
        verbose_name_plural = '网格策略列表'
        db_table = 'grid_strategy'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['symbol', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.symbol} {self.get_strategy_type_display()} - {self.get_status_display()}"

    def calculate_total_position_value(self):
        """计算总仓位价值（USDT）"""
        # 统计所有已成交的买单
        filled_buy_orders = self.gridorder_set.filter(
            order_type='buy',
            status='filled'
        )
        total_cost = sum(
            order.price * order.quantity for order in filled_buy_orders
        )
        return float(total_cost)


class GridOrder(models.Model):
    """
    网格订单模型
    Grid Order Model

    记录所有网格订单（包括pending、filled、cancelled）
    """
    ORDER_TYPE_CHOICES = [
        ('buy', '买单'),
        ('sell', '卖单'),
    ]

    STATUS_CHOICES = [
        ('pending', '待成交'),
        ('filled', '已成交'),
        ('cancelled', '已撤销'),
    ]

    strategy = models.ForeignKey(
        GridStrategy, on_delete=models.CASCADE, verbose_name='所属策略'
    )
    order_type = models.CharField('订单类型', max_length=10, choices=ORDER_TYPE_CHOICES, db_index=True)
    price = models.DecimalField('价格', max_digits=20, decimal_places=8)
    quantity = models.DecimalField('数量', max_digits=20, decimal_places=8)

    # 订单状态
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    filled_at = models.DateTimeField('成交时间', null=True, blank=True)

    # 模拟撮合字段
    simulated_price = models.DecimalField(
        '实际成交价', max_digits=20, decimal_places=8, null=True, blank=True,
        help_text='模拟滑点后的价格'
    )
    simulated_fee = models.DecimalField(
        '手续费(USDT)', max_digits=20, decimal_places=8, default=Decimal('0.00')
    )

    # 时间戳
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '网格订单'
        verbose_name_plural = '网格订单列表'
        db_table = 'grid_order'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['strategy', 'status']),
            models.Index(fields=['order_type', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.get_order_type_display()} {self.quantity}@{self.price} - {self.get_status_display()}"

    def calculate_pnl(self, current_price):
        """
        计算订单盈亏（仅对已成交的订单）

        Args:
            current_price: 当前市场价格

        Returns:
            float: 盈亏金额(USDT)
        """
        if self.status != 'filled':
            return 0.0

        if self.order_type == 'buy':
            # 买单: (当前价 - 买入价) * 数量 - 手续费
            pnl = (float(current_price) - float(self.price)) * float(self.quantity)
        else:  # sell
            # 卖单: (卖出价 - 买入价) * 数量 - 手续费
            # 注意: 卖单的盈亏需要配对对应的买单才能计算准确
            # 这里简化处理，仅计算卖出后的现金流
            pnl = (float(self.price) - float(current_price)) * float(self.quantity)

        return pnl - float(self.simulated_fee)
