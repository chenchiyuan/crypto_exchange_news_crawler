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


class KlineData(models.Model):
    """
    K线数据缓存模型
    Kline Data Cache Model

    存储从币安API获取的K线数据，支持增量更新
    用于筛选系统和回测系统的数据复用
    """

    # ========== 标识字段 ==========
    symbol = models.CharField("交易对", max_length=20, db_index=True)  # BTCUSDT
    interval = models.CharField(
        "时间周期",
        max_length=10,
        db_index=True,
        help_text="1m, 5m, 15m, 1h, 4h, 1d等",
    )
    open_time = models.DateTimeField("开盘时间", db_index=True)
    close_time = models.DateTimeField("收盘时间")

    # ========== OHLCV数据 ==========
    open = models.DecimalField("开盘价", max_digits=20, decimal_places=8)
    high = models.DecimalField("最高价", max_digits=20, decimal_places=8)
    low = models.DecimalField("最低价", max_digits=20, decimal_places=8)
    close = models.DecimalField("收盘价", max_digits=20, decimal_places=8)
    volume = models.DecimalField("成交量(base)", max_digits=30, decimal_places=8)

    # ========== 扩展数据 (用于CVD等指标计算) ==========
    quote_volume = models.DecimalField(
        "成交额(quote)", max_digits=30, decimal_places=8, null=True, blank=True
    )
    taker_buy_base_volume = models.DecimalField(
        "主动买入成交量(base)",
        max_digits=30,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="用于CVD计算",
    )
    taker_buy_quote_volume = models.DecimalField(
        "主动买入成交额(quote)",
        max_digits=30,
        decimal_places=8,
        null=True,
        blank=True,
    )
    number_of_trades = models.IntegerField("成交笔数", null=True, blank=True)

    # ========== 元数据 ==========
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "K线数据"
        verbose_name_plural = "K线数据缓存"
        db_table = "kline_data"
        # 唯一约束: 同一标的、同一周期、同一时间只有一条记录
        unique_together = [["symbol", "interval", "open_time"]]
        # 索引优化
        indexes = [
            # 主查询索引: 按标的+周期+时间查询
            models.Index(fields=["symbol", "interval", "open_time"]),
            # 倒序索引: 获取最新K线
            models.Index(fields=["symbol", "interval", "-open_time"]),
            # 时间范围查询索引
            models.Index(fields=["symbol", "interval", "open_time", "close_time"]),
        ]
        ordering = ["symbol", "interval", "open_time"]

    def __str__(self):
        return f"{self.symbol} {self.interval} @ {self.open_time.strftime('%Y-%m-%d %H:%M')}"

    def to_dict(self):
        """
        转换为字典格式 (与币安API返回格式兼容)

        Returns:
            Dict包含OHLCV和扩展字段
        """
        return {
            "open_time": self.open_time,
            "open": float(self.open),
            "high": float(self.high),
            "low": float(self.low),
            "close": float(self.close),
            "volume": float(self.volume),
            "close_time": self.close_time,
            "quote_volume": float(self.quote_volume) if self.quote_volume else None,
            "taker_buy_base_volume": (
                float(self.taker_buy_base_volume)
                if self.taker_buy_base_volume
                else None
            ),
            "taker_buy_quote_volume": (
                float(self.taker_buy_quote_volume)
                if self.taker_buy_quote_volume
                else None
            ),
            "number_of_trades": self.number_of_trades,
        }

    @classmethod
    def from_binance_kline(cls, symbol, interval, kline_data):
        """
        从币安API返回的K线数据创建模型实例

        Args:
            symbol: 交易对
            interval: 时间周期
            kline_data: 币安API返回的K线数据 (列表或字典格式)

        Returns:
            KlineData实例
        """
        from datetime import datetime

        # 处理两种格式: 列表格式 [时间戳, open, high, ...] 或字典格式
        if isinstance(kline_data, list):
            # 币安API原始格式 (列表)
            return cls(
                symbol=symbol,
                interval=interval,
                open_time=datetime.fromtimestamp(kline_data[0] / 1000),
                close_time=datetime.fromtimestamp(kline_data[6] / 1000),
                open=Decimal(str(kline_data[1])),
                high=Decimal(str(kline_data[2])),
                low=Decimal(str(kline_data[3])),
                close=Decimal(str(kline_data[4])),
                volume=Decimal(str(kline_data[5])),
                quote_volume=Decimal(str(kline_data[7])),
                number_of_trades=kline_data[8],
                taker_buy_base_volume=Decimal(str(kline_data[9])),
                taker_buy_quote_volume=Decimal(str(kline_data[10])),
            )
        else:
            # 字典格式
            return cls(
                symbol=symbol,
                interval=interval,
                open_time=kline_data["open_time"],
                close_time=kline_data["close_time"],
                open=Decimal(str(kline_data["open"])),
                high=Decimal(str(kline_data["high"])),
                low=Decimal(str(kline_data["low"])),
                close=Decimal(str(kline_data["close"])),
                volume=Decimal(str(kline_data["volume"])),
                quote_volume=(
                    Decimal(str(kline_data["quote_volume"]))
                    if kline_data.get("quote_volume")
                    else None
                ),
                taker_buy_base_volume=(
                    Decimal(str(kline_data["taker_buy_base_volume"]))
                    if kline_data.get("taker_buy_base_volume")
                    else None
                ),
                taker_buy_quote_volume=(
                    Decimal(str(kline_data["taker_buy_quote_volume"]))
                    if kline_data.get("taker_buy_quote_volume")
                    else None
                ),
                number_of_trades=kline_data.get("number_of_trades"),
            )
