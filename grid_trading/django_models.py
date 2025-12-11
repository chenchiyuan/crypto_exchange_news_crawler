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


class SymbolInfo(models.Model):
    """
    合约基本信息缓存模型
    Symbol Info Cache Model

    存储币安永续合约的基本信息和元数据
    用于筛选系统的初筛和基础数据查询
    """

    # ========== 基本信息 ==========
    symbol = models.CharField("交易对", max_length=20, unique=True, db_index=True)
    base_asset = models.CharField("基础货币", max_length=10)  # BTC
    quote_asset = models.CharField("计价货币", max_length=10)  # USDT
    contract_type = models.CharField(
        "合约类型", max_length=20, default="PERPETUAL"
    )  # PERPETUAL, DELIVERY

    # ========== 市场数据 (最新快照) ==========
    current_price = models.DecimalField(
        "当前价格", max_digits=20, decimal_places=8, null=True, blank=True
    )
    volume_24h = models.DecimalField(
        "24小时成交量(USDT)", max_digits=30, decimal_places=8, null=True, blank=True
    )
    open_interest = models.DecimalField(
        "持仓量(USDT)", max_digits=30, decimal_places=8, null=True, blank=True
    )
    funding_rate = models.DecimalField(
        "资金费率", max_digits=10, decimal_places=8, null=True, blank=True
    )
    next_funding_time = models.DateTimeField("下次资金费率时间", null=True, blank=True)

    # ========== 上市信息 ==========
    listing_date = models.DateTimeField("上市时间", null=True, blank=True)
    is_active = models.BooleanField("是否活跃", default=True, db_index=True)

    # ========== 市值排名 (可选) ==========
    market_cap_rank = models.IntegerField("市值排名", null=True, blank=True)

    # ========== 现货市场 ==========
    has_spot = models.BooleanField("是否有现货", default=False, help_text="该合约是否在币安现货市场有对应交易对")

    # ========== 元数据 ==========
    last_updated = models.DateTimeField("最后更新时间", auto_now=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "合约信息"
        verbose_name_plural = "合约信息缓存"
        db_table = "symbol_info"
        indexes = [
            models.Index(fields=["is_active", "volume_24h"]),  # 流动性筛选
            models.Index(fields=["is_active", "listing_date"]),  # 上市时间筛选
        ]
        ordering = ["-volume_24h"]

    def __str__(self):
        return f"{self.symbol} ({self.contract_type})"

    def passes_initial_filter(self, min_volume: Decimal, min_days: int) -> bool:
        """
        判断是否通过初筛条件

        Args:
            min_volume: 最小流动性阈值 (USDT)
            min_days: 最小上市天数

        Returns:
            True if 通过, False otherwise
        """
        from datetime import datetime

        # 流动性检查
        if self.volume_24h is None or self.volume_24h < min_volume:
            return False

        # 上市时间检查
        if self.listing_date is None:
            return False

        days_since_listing = (datetime.now() - self.listing_date.replace(tzinfo=None)).days
        if days_since_listing < min_days:
            return False

        # 活跃状态检查
        if not self.is_active:
            return False

        return True

    def to_market_symbol(self):
        """
        转换为 MarketSymbol dataclass

        Returns:
            MarketSymbol实例
        """
        from grid_trading.models.market_symbol import MarketSymbol

        return MarketSymbol(
            symbol=self.symbol,
            exchange="binance",
            contract_type=self.contract_type,
            listing_date=self.listing_date,
            current_price=self.current_price,
            volume_24h=self.volume_24h,
            open_interest=self.open_interest or Decimal("0"),
            funding_rate=self.funding_rate or Decimal("0"),
            funding_interval_hours=8,
            next_funding_time=self.next_funding_time or self.listing_date,
            market_cap_rank=self.market_cap_rank,
        )


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
            Dict包含OHLCV和扩展字段，时间字段为毫秒时间戳
        """
        return {
            "open_time": int(self.open_time.timestamp() * 1000),  # 转换为毫秒时间戳
            "open": float(self.open),
            "high": float(self.high),
            "low": float(self.low),
            "close": float(self.close),
            "volume": float(self.volume),
            "close_time": int(self.close_time.timestamp() * 1000),  # 转换为毫秒时间戳
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
            # 字典格式 (从BinanceFuturesClient获取)
            # open_time和close_time是int毫秒时间戳,需要转换为datetime
            return cls(
                symbol=symbol,
                interval=interval,
                open_time=datetime.fromtimestamp(kline_data["open_time"] / 1000),
                close_time=datetime.fromtimestamp(kline_data["close_time"] / 1000),
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
                number_of_trades=kline_data.get("trades") or kline_data.get("number_of_trades"),
            )


class ScreeningRecord(models.Model):
    """
    筛选记录主表

    存储每次筛选的元数据和配置
    """

    # 筛选时间
    created_at = models.DateTimeField('筛选时间', default=timezone.now, db_index=True)
    screening_date = models.DateField(
        '筛选日期',
        null=True,
        blank=True,
        db_index=True,
        help_text='标识该筛选对应的交易日期(如2024-12-05)，用于按天分析场景。null表示实时筛选'
    )

    # 筛选参数
    min_volume = models.DecimalField('最小流动性', max_digits=20, decimal_places=2)
    min_days = models.IntegerField('最小上市天数')

    # 权重配置
    vdr_weight = models.DecimalField('VDR权重', max_digits=5, decimal_places=4, default=Decimal('0.40'))
    ker_weight = models.DecimalField('KER权重', max_digits=5, decimal_places=4, default=Decimal('0.30'))
    ovr_weight = models.DecimalField('OVR权重', max_digits=5, decimal_places=4, default=Decimal('0.20'))
    cvd_weight = models.DecimalField('CVD权重', max_digits=5, decimal_places=4, default=Decimal('0.10'))

    # 过滤条件 (可选)
    filter_min_vdr = models.FloatField('VDR最小值过滤', null=True, blank=True, help_text='VDR>=此值才会被筛选出来')
    filter_min_ker = models.FloatField('KER最小值过滤', null=True, blank=True, help_text='KER>=此值才会被筛选出来')
    filter_min_amplitude = models.FloatField('15m振幅最小值过滤(%)', null=True, blank=True, help_text='15m振幅>=此值才会被筛选出来')
    filter_min_funding_rate = models.FloatField('年化资金费率最小值过滤(%)', null=True, blank=True, help_text='年化资金费率>=此值才会被筛选出来')
    filter_max_ma99_slope = models.FloatField('EMA99斜率最大值过滤', null=True, blank=True, help_text='EMA99斜率<=此值才会被筛选出来（负值表示下降趋势）')

    # 结果统计
    total_candidates = models.IntegerField('候选标的数')
    execution_time = models.FloatField('执行耗时(秒)')

    # 备注
    notes = models.TextField('备注', blank=True, default='')

    class Meta:
        verbose_name = '筛选记录'
        verbose_name_plural = '筛选记录列表'
        db_table = 'screening_record'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['-screening_date']),
        ]

    def __str__(self):
        if self.screening_date:
            return f"筛选记录 {self.screening_date} ({self.total_candidates}个标的)"
        return f"筛选记录 {self.created_at.strftime('%Y-%m-%d %H:%M')} ({self.total_candidates}个标的)"


class ScreeningResultModel(models.Model):
    """
    筛选结果明细表

    存储每个标的的详细评分数据
    """

    # 关联筛选记录
    record = models.ForeignKey(
        ScreeningRecord,
        on_delete=models.CASCADE,
        related_name='results',
        verbose_name='所属筛选记录'
    )

    # 排名
    rank = models.IntegerField('排名', db_index=True)

    # 标的信息
    symbol = models.CharField('标的代码', max_length=20, db_index=True)
    current_price = models.DecimalField('当前价格', max_digits=20, decimal_places=8)

    # 原始指标
    vdr = models.FloatField('VDR(波动率-位移比)')
    ker = models.FloatField('KER(考夫曼效率比)')
    ovr = models.FloatField('OVR(持仓/成交比)')
    cvd_divergence = models.BooleanField('CVD背离', default=False)
    amplitude_sum_15m = models.FloatField('15分钟振幅累计(%)', default=0.0, help_text='最近100根15分钟K线的振幅百分比累加')
    annual_funding_rate = models.FloatField('年化资金费率(%)', default=0.0, help_text='基于过去24小时平均资金费率年化，正值表示做空有利')

    # 市场数据
    open_interest = models.DecimalField('持仓量(USDT)', max_digits=30, decimal_places=2, null=True, blank=True, help_text='合约未平仓总量(美元价值)')
    volume_24h_calculated = models.DecimalField('24h交易量(USDT)', max_digits=30, decimal_places=2, null=True, blank=True, default=0, help_text='从1440根1m K线计算的24小时交易量')
    vol_oi_ratio = models.FloatField('Vol/OI比率', default=0.0, help_text='24h交易量/持仓量比率')
    fdv = models.DecimalField('完全稀释市值(USD)', max_digits=30, decimal_places=2, null=True, blank=True, help_text='Fully Diluted Valuation')
    oi_fdv_ratio = models.FloatField('OI/FDV比率(%)', null=True, blank=True, help_text='持仓量占完全稀释市值的百分比')
    has_spot = models.BooleanField('是否有现货', default=False, help_text='该合约是否在币安现货市场有对应交易对')

    # 趋势指标
    ma99_slope = models.FloatField('EMA99斜率', default=0.0, help_text='EMA(99)均线斜率(标准化), 正值=上升趋势, 负值=下降趋势')
    ma20_slope = models.FloatField('EMA20斜率', default=0.0, help_text='EMA(20)均线斜率(标准化), 正值=上升趋势, 负值=下降趋势')

    # 分项得分
    vdr_score = models.FloatField('VDR得分')
    ker_score = models.FloatField('KER得分')
    ovr_score = models.FloatField('OVR得分')
    cvd_score = models.FloatField('CVD得分')

    # 综合指数
    composite_index = models.FloatField('综合指数', db_index=True)

    # 网格参数推荐
    grid_upper_limit = models.DecimalField('网格上限', max_digits=20, decimal_places=8)
    grid_lower_limit = models.DecimalField('网格下限', max_digits=20, decimal_places=8)
    grid_count = models.IntegerField('推荐网格数')
    grid_step = models.DecimalField('网格步长', max_digits=20, decimal_places=8)

    # 止盈止损推荐
    take_profit_price = models.DecimalField('止盈价格', max_digits=20, decimal_places=8)
    stop_loss_price = models.DecimalField('止损价格', max_digits=20, decimal_places=8)
    take_profit_pct = models.FloatField('止盈百分比(%)')
    stop_loss_pct = models.FloatField('止损百分比(%)')

    # 挂单建议（新增）
    rsi_15m = models.FloatField('RSI(15m)', default=50.0, help_text='15分钟RSI指标')
    recommended_entry_price = models.DecimalField('推荐挂单价', max_digits=20, decimal_places=8, null=True, blank=True)
    entry_trigger_prob_24h = models.FloatField('触发概率(24h)', default=0.0, help_text='24小时内触发概率(0-1)')
    entry_trigger_prob_72h = models.FloatField('触发概率(72h)', default=0.0, help_text='72小时内触发概率(0-1)')
    entry_strategy_label = models.CharField('入场策略', max_length=20, default='立即入场', help_text='立即入场/保守反弹/理论反弹')
    entry_rebound_pct = models.FloatField('反弹幅度(%)', default=0.0, help_text='相对当前价的反弹百分比')
    entry_avg_trigger_time = models.FloatField('平均触发时间(h)', default=0.0, help_text='历史平均触发时间（小时）')
    entry_expected_return_24h = models.FloatField('期望收益(24h)', default=0.0, help_text='24小时期望收益')
    entry_candidates_json = models.JSONField('3档挂单候选', default=list, blank=True, help_text='存储3个挂单候选方案的详细信息')

    # 高点回落指标（新增）
    highest_price_300 = models.DecimalField('300根4h高点', max_digits=20, decimal_places=8, null=True, blank=True, help_text='300根4h K线内的最高价')
    drawdown_from_high_pct = models.FloatField('高点回落(%)', default=0.0, help_text='当前价格相对300根4h高点的回落比例，正值=已回落，负值=创新高')

    # 价格分位指标（新增）
    price_percentile_100 = models.FloatField('价格分位(100根4h)', default=50.0, help_text='基于100根4h K线的价格分位，0%=最低点，100%=最高点')

    # 24小时资金流分析（新增）
    money_flow_large_net = models.FloatField('大单净流入(USDT)', default=0.0, help_text='24小时大单净流入金额，正值=流入，负值=流出')
    money_flow_strength = models.FloatField('资金流强度', default=0.5, help_text='主动买入占比(0-1)，>0.55=买盘强，<0.45=卖盘强')
    money_flow_large_dominance = models.FloatField('大单主导度', default=0.0, help_text='大单对资金流的影响程度(0-1)，越高表示机构影响越大')


    class Meta:
        verbose_name = '筛选结果'
        verbose_name_plural = '筛选结果列表'
        db_table = 'screening_result_record'
        ordering = ['record', 'rank']
        indexes = [
            models.Index(fields=['record', 'rank']),
            models.Index(fields=['symbol']),
            models.Index(fields=['-composite_index']),
        ]

    def __str__(self):
        return f"{self.symbol} (排名#{self.rank}, 指数={self.composite_index:.4f})"

    def to_dict(self):
        """转换为字典用于API返回"""
        import math

        # 处理可能的Infinity/NaN值
        def safe_float(value, default=0.0, max_value=999.99):
            """安全转换浮点数，处理Infinity和NaN"""
            if value is None:
                return default
            if math.isinf(value):
                return max_value if value > 0 else -max_value
            if math.isnan(value):
                return default
            return value

        return {
            'rank': self.rank,
            'symbol': self.symbol,
            'price': float(self.current_price),
            'vdr': round(safe_float(self.vdr), 2),
            'ker': round(safe_float(self.ker), 3),
            'ovr': round(safe_float(self.ovr), 2),
            'cvd': '✓' if self.cvd_divergence else '✗',
            'amplitude_sum_15m': round(safe_float(self.amplitude_sum_15m), 2),
            'annual_funding_rate': round(safe_float(self.annual_funding_rate), 2),
            'open_interest': float(self.open_interest) if self.open_interest else 0.0,
            'volume_24h_calculated': float(self.volume_24h_calculated) if self.volume_24h_calculated else 0.0,
            'vol_oi_ratio': round(safe_float(self.vol_oi_ratio), 3),
            'fdv': float(self.fdv) if self.fdv else 0.0,
            'oi_fdv_ratio': round(safe_float(self.oi_fdv_ratio), 2) if self.oi_fdv_ratio else 0.0,
            'has_spot': self.has_spot,
            'ma99_slope': round(safe_float(self.ma99_slope), 2),
            'ma20_slope': round(safe_float(self.ma20_slope), 2),
            'vdr_score': round(safe_float(self.vdr_score) * 100, 1),
            'ker_score': round(safe_float(self.ker_score) * 100, 1),
            'ovr_score': round(safe_float(self.ovr_score) * 100, 1),
            'cvd_score': round(safe_float(self.cvd_score) * 100, 1),
            'composite_index': round(safe_float(self.composite_index), 4),
            'grid_upper': float(self.grid_upper_limit),
            'grid_lower': float(self.grid_lower_limit),
            'grid_count': self.grid_count,
            'grid_step': float(self.grid_step),
            'take_profit_price': float(self.take_profit_price),
            'stop_loss_price': float(self.stop_loss_price),
            'take_profit_pct': round(safe_float(self.take_profit_pct), 2),
            'stop_loss_pct': round(safe_float(self.stop_loss_pct), 2),
            # 挂单建议
            'rsi_15m': round(safe_float(self.rsi_15m), 1),
            'recommended_entry_price': float(self.recommended_entry_price) if self.recommended_entry_price else float(self.current_price),
            'entry_trigger_prob_24h': round(safe_float(self.entry_trigger_prob_24h), 3),
            'entry_trigger_prob_72h': round(safe_float(self.entry_trigger_prob_72h), 3),
            'entry_strategy_label': self.entry_strategy_label,
            'entry_rebound_pct': round(safe_float(self.entry_rebound_pct), 2),
            'entry_avg_trigger_time': round(safe_float(self.entry_avg_trigger_time), 1),
            'entry_expected_return_24h': round(safe_float(self.entry_expected_return_24h), 3),
            'entry_candidates': self.entry_candidates_json if self.entry_candidates_json else [],
            # 高点回落指标
            'highest_price_300': float(self.highest_price_300) if self.highest_price_300 else 0.0,
            'drawdown_from_high_pct': round(safe_float(self.drawdown_from_high_pct), 2),
            # 价格分位指标
            'price_percentile_100': round(safe_float(self.price_percentile_100), 2),
            # 资金流指标
            'money_flow_large_net': round(safe_float(self.money_flow_large_net), 2),
            'money_flow_strength': round(safe_float(self.money_flow_strength), 3),
            'money_flow_large_dominance': round(safe_float(self.money_flow_large_dominance), 3),
        }


# ============================================================================
# 价格触发预警监控系统模型 (Price Alert Monitor System Models)
# Feature: 001-price-alert-monitor
# ============================================================================


class MonitoredContract(models.Model):
    """
    监控合约模型
    Monitored Contract Model

    存储所有被监控的合约标的，支持手动添加和自动同步两种来源
    """

    SOURCE_CHOICES = [
        ('manual', '手动添加'),
        ('auto', '自动筛选'),
    ]

    STATUS_CHOICES = [
        ('enabled', '启用'),
        ('disabled', '禁用'),
        ('expired', '已过期'),
    ]

    symbol = models.CharField(
        '合约代码',
        max_length=20,
        primary_key=True,
        help_text='如BTCUSDT'
    )

    source = models.CharField(
        '来源',
        max_length=10,
        choices=SOURCE_CHOICES,
        default='manual',
        db_index=True
    )

    status = models.CharField(
        '监控状态',
        max_length=10,
        choices=STATUS_CHOICES,
        default='enabled',
        db_index=True
    )

    created_at = models.DateTimeField(
        '添加时间',
        auto_now_add=True
    )

    last_screening_date = models.DateField(
        '最后筛选出现日期',
        null=True,
        blank=True,
        help_text='仅自动添加的合约有此字段'
    )

    last_data_update_at = models.DateTimeField(
        '最后数据更新时间',
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'monitored_contract'
        verbose_name = '监控合约'
        verbose_name_plural = '监控合约'
        indexes = [
            models.Index(fields=['source', 'status']),  # 查询启用的自动合约
            models.Index(fields=['-last_screening_date']),  # 查询最近筛选日期
        ]

    def __str__(self):
        return f"{self.symbol} ({self.get_source_display()})"


class PriceAlertRule(models.Model):
    """
    价格触发规则模型
    Price Alert Rule Model

    存储5种预设的价格触发规则配置，支持启用/禁用和参数调整
    """

    RULE_CHOICES = [
        (1, '7天价格新高(4h)'),
        (2, '7天价格新低(4h)'),
        (3, '价格触及MA20'),
        (4, '价格触及MA99'),
        (5, '价格达到分布区间90%极值'),
    ]

    rule_id = models.IntegerField(
        '规则ID',
        primary_key=True,
        choices=RULE_CHOICES,
        help_text='1-5对应5种预设规则'
    )

    name = models.CharField(
        '规则名称',
        max_length=50
    )

    description = models.TextField(
        '规则描述',
        help_text='规则的技术说明和判定逻辑'
    )

    enabled = models.BooleanField(
        '启用状态',
        default=True,
        db_index=True
    )

    parameters = models.JSONField(
        '规则参数',
        default=dict,
        help_text='JSON格式的参数配置,如{"ma_threshold": 0.5, "percentile": 90}'
    )

    updated_at = models.DateTimeField(
        '更新时间',
        auto_now=True
    )

    class Meta:
        db_table = 'price_alert_rule'
        verbose_name = '价格触发规则'
        verbose_name_plural = '价格触发规则'

    def __str__(self):
        return f"规则{self.rule_id}: {self.name}"


class AlertTriggerLog(models.Model):
    """
    触发日志模型
    Alert Trigger Log Model

    记录每次规则触发的详细日志，实现防重复推送和历史审计
    """

    symbol = models.CharField(
        '合约代码',
        max_length=20,
        db_index=True
    )

    rule_id = models.IntegerField(
        '规则ID',
        db_index=True,
        help_text='关联PriceAlertRule.rule_id'
    )

    triggered_at = models.DateTimeField(
        '触发时间',
        auto_now_add=True,
        db_index=True
    )

    current_price = models.DecimalField(
        '当前价格',
        max_digits=20,
        decimal_places=8
    )

    pushed = models.BooleanField(
        '是否已推送',
        default=False,
        db_index=True
    )

    pushed_at = models.DateTimeField(
        '推送时间',
        null=True,
        blank=True
    )

    skip_reason = models.CharField(
        '跳过原因',
        max_length=100,
        blank=True,
        help_text='如"防重复"、"推送失败"等'
    )

    extra_info = models.JSONField(
        '额外信息',
        default=dict,
        help_text='存储MA值、7天最高/最低等上下文信息'
    )

    class Meta:
        db_table = 'alert_trigger_log'
        verbose_name = '触发日志'
        verbose_name_plural = '触发日志'
        indexes = [
            # 核心索引: 查询某合约某规则的最近推送时间(防重复查询)
            models.Index(fields=['symbol', 'rule_id', '-pushed_at']),
            # 查询最近的触发记录
            models.Index(fields=['-triggered_at']),
            # 查询失败的推送(用于补偿重试)
            models.Index(fields=['pushed', 'skip_reason', '-triggered_at']),
        ]

    def __str__(self):
        return f"{self.symbol} 规则{self.rule_id} - {self.triggered_at}"


class DataUpdateLog(models.Model):
    """
    数据更新日志模型
    Data Update Log Model

    记录每次数据更新脚本的执行情况，便于监控和故障排查
    """

    STATUS_CHOICES = [
        ('running', '执行中'),
        ('success', '成功'),
        ('failed', '失败'),
        ('timeout', '超时'),
    ]

    started_at = models.DateTimeField(
        '执行开始时间',
        auto_now_add=True,
        db_index=True
    )

    ended_at = models.DateTimeField(
        '执行结束时间',
        null=True,
        blank=True
    )

    contracts_count = models.IntegerField(
        '更新合约数量',
        default=0
    )

    klines_count = models.IntegerField(
        '获取K线总数',
        default=0,
        help_text='所有合约×所有周期的K线总数'
    )

    status = models.CharField(
        '执行状态',
        max_length=10,
        choices=STATUS_CHOICES,
        default='running',
        db_index=True
    )

    error_message = models.TextField(
        '错误信息',
        blank=True
    )

    execution_seconds = models.IntegerField(
        '执行耗时(秒)',
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'data_update_log'
        verbose_name = '数据更新日志'
        verbose_name_plural = '数据更新日志'
        ordering = ['-started_at']

    def __str__(self):
        return f"数据更新 {self.started_at} - {self.status}"

    def complete(self, status='success', error_message=''):
        """标记执行完成"""
        from django.utils import timezone
        self.ended_at = timezone.now()
        self.status = status
        self.error_message = error_message
        if self.ended_at and self.started_at:
            self.execution_seconds = int((self.ended_at - self.started_at).total_seconds())
        self.save()


class SystemConfig(models.Model):
    """
    系统配置模型
    System Config Model

    存储系统级配置参数，支持动态修改无需重启服务
    """

    key = models.CharField(
        '配置键',
        max_length=50,
        primary_key=True
    )

    value = models.TextField(
        '配置值',
        help_text='支持字符串、数字、JSON等格式'
    )

    description = models.CharField(
        '配置说明',
        max_length=200,
        blank=True
    )

    updated_at = models.DateTimeField(
        '更新时间',
        auto_now=True
    )

    class Meta:
        db_table = 'system_config'
        verbose_name = '系统配置'
        verbose_name_plural = '系统配置'

    def __str__(self):
        return f"{self.key} = {self.value}"

    @classmethod
    def get_value(cls, key, default=None):
        """获取配置值"""
        try:
            config = cls.objects.get(key=key)
            return config.value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set_value(cls, key, value, description=''):
        """设置配置值"""
        config, created = cls.objects.update_or_create(
            key=key,
            defaults={'value': str(value), 'description': description}
        )
        return config


class ScriptLock(models.Model):
    """
    脚本锁模型
    Script Lock Model

    实现脚本互斥机制，避免定时任务并发执行
    """

    lock_name = models.CharField(
        '锁名称',
        max_length=50,
        unique=True,
        primary_key=True
    )

    acquired_at = models.DateTimeField(
        '获取时间',
        auto_now=True
    )

    expires_at = models.DateTimeField(
        '过期时间'
    )

    class Meta:
        db_table = 'script_lock'
        verbose_name = '脚本锁'
        verbose_name_plural = '脚本锁'

    def __str__(self):
        return f"Lock: {self.lock_name}"
