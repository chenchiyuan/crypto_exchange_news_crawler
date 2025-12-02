"""
回测框架数据模型
Backtest Framework Models
"""
from django.db import models
from decimal import Decimal


class KLine(models.Model):
    """K线历史数据"""

    # 基本信息
    symbol = models.CharField(
        '交易对', max_length=20, db_index=True,
        help_text='如: BTCUSDT, ETHUSDT'
    )
    interval = models.CharField(
        '时间周期', max_length=10, db_index=True,
        help_text='如: 1h, 4h, 1d'
    )

    # 时间
    open_time = models.DateTimeField('开盘时间', db_index=True)
    close_time = models.DateTimeField('收盘时间')

    # OHLCV数据
    open_price = models.DecimalField('开盘价', max_digits=20, decimal_places=8)
    high_price = models.DecimalField('最高价', max_digits=20, decimal_places=8)
    low_price = models.DecimalField('最低价', max_digits=20, decimal_places=8)
    close_price = models.DecimalField('收盘价', max_digits=20, decimal_places=8)
    volume = models.DecimalField('成交量', max_digits=30, decimal_places=8)

    # 其他数据
    quote_volume = models.DecimalField(
        '成交额', max_digits=30, decimal_places=8,
        help_text='Quote asset volume'
    )
    trade_count = models.IntegerField('成交笔数', default=0)
    taker_buy_volume = models.DecimalField(
        '主动买入量', max_digits=30, decimal_places=8, default=0
    )
    taker_buy_quote_volume = models.DecimalField(
        '主动买入额', max_digits=30, decimal_places=8, default=0
    )

    # 元数据
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = 'K线数据'
        verbose_name_plural = 'K线数据列表'
        db_table = 'backtest_kline'
        unique_together = [['symbol', 'interval', 'open_time']]  # 防止重复
        indexes = [
            models.Index(fields=['symbol', 'interval', 'open_time']),
            models.Index(fields=['symbol', 'interval', '-open_time']),  # 倒序查询
            models.Index(fields=['open_time']),
        ]
        ordering = ['symbol', 'interval', 'open_time']

    def __str__(self):
        return f"{self.symbol} {self.interval} {self.open_time.strftime('%Y-%m-%d %H:%M')}"


class BacktestResult(models.Model):
    """回测结果记录"""

    # 基本信息
    name = models.CharField('回测名称', max_length=100)
    symbol = models.CharField('交易对', max_length=20, db_index=True)
    interval = models.CharField('时间周期', max_length=10)

    # 时间范围
    start_date = models.DateTimeField('开始日期')
    end_date = models.DateTimeField('结束日期')

    # 策略参数（JSON格式）
    strategy_params = models.JSONField(
        '策略参数',
        help_text='包含: grid_step_pct, grid_levels, order_size, stop_loss等'
    )

    # 回测结果指标
    initial_cash = models.DecimalField('初始资金', max_digits=20, decimal_places=2, default=10000)
    final_value = models.DecimalField('最终价值', max_digits=20, decimal_places=2)
    total_return = models.DecimalField('总收益率', max_digits=10, decimal_places=4)

    sharpe_ratio = models.DecimalField(
        '夏普比率', max_digits=10, decimal_places=4, null=True, blank=True
    )
    max_drawdown = models.DecimalField('最大回撤', max_digits=10, decimal_places=4)
    win_rate = models.DecimalField('胜率', max_digits=5, decimal_places=2)

    # 增强指标 - 年化指标
    annual_return = models.DecimalField(
        '年化收益率', max_digits=10, decimal_places=4, null=True, blank=True,
        help_text='年化收益率 (APR)'
    )
    annual_volatility = models.DecimalField(
        '年化波动率', max_digits=10, decimal_places=4, null=True, blank=True,
        help_text='年化波动率'
    )

    # 增强指标 - 风险调整收益
    sortino_ratio = models.DecimalField(
        '索提诺比率', max_digits=10, decimal_places=4, null=True, blank=True,
        help_text='索提诺比率（只考虑下行风险）'
    )
    calmar_ratio = models.DecimalField(
        '卡玛比率', max_digits=10, decimal_places=4, null=True, blank=True,
        help_text='卡玛比率（年化收益率/最大回撤）'
    )

    # 增强指标 - 回撤分析
    max_drawdown_duration = models.IntegerField(
        '最大回撤持续期', null=True, blank=True,
        help_text='最大回撤持续期（天）'
    )

    # 增强指标 - 交易质量
    profit_factor = models.DecimalField(
        '盈亏比', max_digits=10, decimal_places=4, null=True, blank=True,
        help_text='盈亏比（总盈利/总亏损）'
    )
    avg_win = models.DecimalField(
        '平均盈利', max_digits=20, decimal_places=2, null=True, blank=True,
        help_text='平均盈利'
    )
    avg_loss = models.DecimalField(
        '平均亏损', max_digits=20, decimal_places=2, null=True, blank=True,
        help_text='平均亏损'
    )

    total_trades = models.IntegerField('总交易次数', default=0)
    profitable_trades = models.IntegerField('盈利交易次数', default=0)
    losing_trades = models.IntegerField('亏损交易次数', default=0)

    # 详细数据（JSON格式）
    equity_curve = models.JSONField(
        '权益曲线', null=True, blank=True,
        help_text='时间序列的账户价值'
    )
    trades_detail = models.JSONField(
        '交易明细', null=True, blank=True,
        help_text='每笔交易的详细信息'
    )
    daily_returns = models.JSONField(
        '每日收益', null=True, blank=True
    )

    # 元数据
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    notes = models.TextField('备注', blank=True)

    class Meta:
        verbose_name = '回测结果'
        verbose_name_plural = '回测结果列表'
        db_table = 'backtest_result'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['symbol', 'interval', '-created_at']),
            models.Index(fields=['-total_return']),  # 按收益率排序
        ]

    def __str__(self):
        return f"{self.name} - {self.symbol} ({self.total_return:.2%})"


class GridPosition(models.Model):
    """网格持仓记录 V2 - 支持R1/R2分级止盈"""

    # 关联回测
    backtest_result = models.ForeignKey(
        'BacktestResult',
        on_delete=models.CASCADE,
        related_name='grid_positions',
        verbose_name='所属回测'
    )

    # 买入信息
    buy_level = models.CharField(
        '买入层级',
        max_length=20,
        help_text='support_1 或 support_2'
    )
    buy_price = models.DecimalField(
        '买入价格',
        max_digits=20,
        decimal_places=8
    )
    buy_time = models.DateTimeField('买入时间')
    buy_amount = models.DecimalField(
        '买入数量',
        max_digits=20,
        decimal_places=8,
        help_text='币的数量'
    )
    buy_cost = models.DecimalField(
        '买入成本',
        max_digits=20,
        decimal_places=2,
        help_text='USDT，含手续费'
    )
    buy_zone_weight = models.DecimalField(
        '买入权重',
        max_digits=5,
        decimal_places=4,
        help_text='0.05-1.0'
    )

    # 止损价格（买入时计算，固定不变）
    stop_loss_price = models.DecimalField(
        '止损价格',
        max_digits=20,
        decimal_places=8,
        default=0,
        help_text='买入时的S2下界 × (1 - 止损%)，固定值'
    )

    # R1卖出目标（压力位1）
    sell_target_r1_price = models.DecimalField(
        'R1目标价',
        max_digits=20,
        decimal_places=8
    )
    sell_target_r1_pct = models.DecimalField(
        'R1分配比例',
        max_digits=5,
        decimal_places=2,
        help_text='百分比，如50.00表示50%'
    )
    sell_target_r1_sold = models.DecimalField(
        'R1已卖数量',
        max_digits=20,
        decimal_places=8,
        default=0
    )
    sell_target_r1_zone_low = models.DecimalField(
        'R1区间下界',
        max_digits=20,
        decimal_places=8
    )
    sell_target_r1_zone_high = models.DecimalField(
        'R1区间上界',
        max_digits=20,
        decimal_places=8
    )

    # R2卖出目标（压力位2）
    sell_target_r2_price = models.DecimalField(
        'R2目标价',
        max_digits=20,
        decimal_places=8
    )
    sell_target_r2_pct = models.DecimalField(
        'R2分配比例',
        max_digits=5,
        decimal_places=2,
        help_text='百分比，如50.00表示50%'
    )
    sell_target_r2_sold = models.DecimalField(
        'R2已卖数量',
        max_digits=20,
        decimal_places=8,
        default=0
    )
    sell_target_r2_zone_low = models.DecimalField(
        'R2区间下界',
        max_digits=20,
        decimal_places=8
    )
    sell_target_r2_zone_high = models.DecimalField(
        'R2区间上界',
        max_digits=20,
        decimal_places=8
    )

    # 交易状态
    total_sold_amount = models.DecimalField(
        '总已卖数量',
        max_digits=20,
        decimal_places=8,
        default=0
    )
    total_revenue = models.DecimalField(
        '总卖出收入',
        max_digits=20,
        decimal_places=2,
        default=0,
        help_text='扣除手续费后'
    )
    pnl = models.DecimalField(
        '净利润',
        max_digits=20,
        decimal_places=2,
        default=0
    )
    status = models.CharField(
        '状态',
        max_length=20,
        choices=[
            ('open', '持仓中'),
            ('partial', '部分平仓'),
            ('closed', '已平仓'),
        ],
        default='open'
    )

    # 元数据
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '网格持仓V2'
        verbose_name_plural = '网格持仓列表V2'
        db_table = 'grid_position_v2'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['backtest_result', 'status']),
            models.Index(fields=['buy_level', 'status']),
        ]

    def __str__(self):
        return f"{self.buy_level} @ {self.buy_price} ({self.status})"

    @property
    def is_open(self):
        """是否持仓中"""
        return self.status == 'open'

    @property
    def is_closed(self):
        """是否已平仓"""
        return self.status == 'closed'


class BacktestSnapshot(models.Model):
    """回测K线快照 - 记录每根K线的完整状态"""

    # 关联回测
    backtest_result = models.ForeignKey(
        'BacktestResult',
        on_delete=models.CASCADE,
        related_name='snapshots',
        verbose_name='所属回测'
    )

    # K线信息
    timestamp = models.DateTimeField('K线时间', db_index=True)
    kline_index = models.IntegerField('K线索引')

    # 价格和资金
    current_price = models.DecimalField(
        '当前价格',
        max_digits=20,
        decimal_places=2
    )
    cash_balance = models.DecimalField(
        '现金余额',
        max_digits=20,
        decimal_places=2
    )
    total_value = models.DecimalField(
        '总价值',
        max_digits=20,
        decimal_places=2,
        help_text='现金 + 持仓市值'
    )

    # 网格层级（JSON格式）
    grid_levels = models.JSONField(
        '网格层级',
        null=True,
        blank=True,
        help_text='''
        {
            "support_2": {"price": 3100.0, "zone_low": 3098.0, "zone_high": 3102.0},
            "support_1": {"price": 3270.0, "zone_low": 3268.0, "zone_high": 3272.0},
            "resistance_1": {"price": 3740.0, "zone_low": 3738.0, "zone_high": 3742.0},
            "resistance_2": {"price": 3910.0, "zone_low": 3908.0, "zone_high": 3912.0}
        }
        '''
    )

    # 持仓快照（JSON格式）
    positions = models.JSONField(
        '持仓列表',
        default=list,
        help_text='''
        [
            {
                "id": 1,
                "buy_level": "support_1",
                "buy_price": 3271.33,
                "buy_amount": 0.0644,
                "stop_loss_price": 3008.18,
                "r1_target": 3593.56,
                "r1_sold_pct": 0.0,
                "r2_target": 3758.76,
                "r2_sold_pct": 0.0,
                "status": "open"
            }
        ]
        '''
    )

    # 关键事件（JSON格式）
    events = models.JSONField(
        '事件列表',
        default=list,
        help_text='''
        [
            {
                "type": "buy",
                "position_id": 1,
                "price": 3271.33,
                "amount": 0.0644,
                "cost": 210.80
            },
            {
                "type": "sell",
                "position_id": 13,
                "target": "resistance_1",
                "price": 2448.45,
                "amount": 0.0027,
                "revenue": 6.65
            },
            {
                "type": "stop_loss",
                "position_ids": [9, 10, 11],
                "price": 2527.12,
                "total_revenue": 455.29
            }
        ]
        '''
    )

    # 元数据
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '回测快照'
        verbose_name_plural = '回测快照列表'
        db_table = 'backtest_snapshot'
        unique_together = [['backtest_result', 'kline_index']]
        ordering = ['backtest_result', 'kline_index']
        indexes = [
            models.Index(fields=['backtest_result', 'kline_index']),
            models.Index(fields=['backtest_result', 'timestamp']),
        ]

    def __str__(self):
        return (
            f"Snapshot {self.kline_index} @ {self.timestamp.strftime('%Y-%m-%d %H:%M')} "
            f"价格={self.current_price}"
        )


class PendingOrder(models.Model):
    """挂单记录 - Grid V3"""

    # 关联回测
    backtest_result = models.ForeignKey(
        'BacktestResult',
        on_delete=models.CASCADE,
        related_name='pending_orders',
        verbose_name='回测结果'
    )

    # 挂单类型
    order_type = models.CharField(
        '挂单类型',
        max_length=10,
        choices=[
            ('buy', '买入'),
            ('sell', '卖出')
        ],
        db_index=True
    )

    # 网格层级
    grid_level = models.CharField(
        '网格层级',
        max_length=20,
        db_index=True,
        help_text='support_1, support_2, resistance_1, resistance_2'
    )

    # 价格信息
    target_price = models.DecimalField(
        '挂单价格',
        max_digits=20,
        decimal_places=8,
        help_text='买入/卖出的目标价格'
    )

    zone_low = models.DecimalField(
        '区间下界',
        max_digits=20,
        decimal_places=8,
        help_text='网格区间的下界'
    )

    zone_high = models.DecimalField(
        '区间上界',
        max_digits=20,
        decimal_places=8,
        help_text='网格区间的上界'
    )

    # 资金锁定（买单）
    locked_amount_usdt = models.DecimalField(
        '锁定金额USDT',
        max_digits=20,
        decimal_places=2,
        default=0,
        help_text='锁定的USDT金额（买单）'
    )

    # 持仓锁定（卖单）
    locked_amount_crypto = models.DecimalField(
        '锁定币数量',
        max_digits=20,
        decimal_places=8,
        default=0,
        help_text='锁定的币数量（卖单）'
    )

    locked_position = models.ForeignKey(
        'GridPosition',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sell_orders',
        verbose_name='锁定仓位',
        help_text='卖单锁定的仓位'
    )

    # 时间信息
    created_time = models.DateTimeField('创建时间', db_index=True)
    expire_time = models.DateTimeField('过期时间', db_index=True)
    filled_time = models.DateTimeField('成交时间', null=True, blank=True)

    # 状态
    status = models.CharField(
        '挂单状态',
        max_length=20,
        choices=[
            ('pending', '挂单中'),
            ('filled', '已成交'),
            ('expired', '已过期'),
            ('cancelled', '已取消')
        ],
        default='pending',
        db_index=True
    )

    fund_status = models.CharField(
        '资金状态',
        max_length=20,
        choices=[
            ('locked', '资金已锁定'),
            ('released', '资金已释放')
        ],
        default='locked',
        db_index=True
    )

    # 成交信息
    filled_price = models.DecimalField(
        '成交价',
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        help_text='实际成交价格'
    )

    filled_amount = models.DecimalField(
        '成交金额',
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='实际成交金额'
    )

    created_position = models.ForeignKey(
        'GridPosition',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_by_order',
        verbose_name='创建的仓位',
        help_text='买单成交后创建的仓位'
    )

    # 元数据
    created_at = models.DateTimeField('记录创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '挂单记录'
        verbose_name_plural = '挂单记录列表'
        db_table = 'backtest_pending_order'
        ordering = ['backtest_result', 'created_time']
        indexes = [
            models.Index(fields=['backtest_result', 'status', 'fund_status']),
            models.Index(fields=['backtest_result', 'order_type', 'status']),
            models.Index(fields=['backtest_result', 'grid_level', 'status']),
            models.Index(fields=['expire_time']),
        ]

    def __str__(self):
        return (
            f"{self.get_order_type_display()} 挂单 - {self.grid_level} @ {self.target_price} "
            f"[{self.get_status_display()}]"
        )
