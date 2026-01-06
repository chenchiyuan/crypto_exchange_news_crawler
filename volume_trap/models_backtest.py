"""
Volume Trap 策略回测模型

用于存储单个异常事件的回测结果和整体统计数据。

Related:
    - PRD: docs/iterations/007-backtest-framework/IMPLEMENTATION_PLAN.md
    - Task: 回测框架实现
"""

from decimal import Decimal

from django.db import models


class BacktestResult(models.Model):
    """单个异常事件的回测结果。

    存储从发现异常事件后做空策略的完整表现数据，包括：
    - 入场信息（时间、价格）
    - 最低点信息（位置、价格、到达K线数）
    - 反弹信息（是否反弹、反弹幅度、最大回撤）
    - 最终结果（出场价格、收益率）

    Attributes:
        monitor (ForeignKey): 关联的异常事件监控记录
        symbol (str): 交易对符号（冗余存储，便于查询）
        interval (str): K线周期
        market_type (str): 市场类型

        # 入场信息
        entry_time (datetime): 入场时间（触发后下一根K线开盘）
        entry_price (Decimal): 入场价格

        # 最低点信息
        lowest_time (datetime): 到达最低点时间
        lowest_price (Decimal): 最低价格
        bars_to_lowest (int): 到达最低点的K线数
        max_profit_percent (Decimal): 最大盈利百分比（做空视角）

        # 反弹信息
        has_rebound (bool): 是否有显著反弹
        rebound_high_price (Decimal): 反弹后最高价
        rebound_percent (Decimal): 反弹幅度百分比
        max_drawdown_percent (Decimal): 最大回撤百分比（做空视角的不利波动）

        # 最终结果
        exit_time (datetime): 出场时间
        exit_price (Decimal): 出场价格
        final_profit_percent (Decimal): 最终收益率
        is_profitable (bool): 是否盈利

        # 配置参数
        holding_bars (int): 持仓K线数（回测参数）

    Examples:
        >>> result = BacktestResult.objects.get(monitor_id=1)
        >>> print(f"最大盈利: {result.max_profit_percent}%")
        >>> print(f"最终收益: {result.final_profit_percent}%")
    """

    # 关联监控记录
    monitor = models.OneToOneField(
        "VolumeTrapMonitor",
        on_delete=models.CASCADE,
        related_name="backtest_result",
        verbose_name="关联监控记录",
    )

    # 冗余字段（便于查询和统计）
    symbol = models.CharField("交易对", max_length=50, db_index=True)
    interval = models.CharField("K线周期", max_length=10, db_index=True)
    market_type = models.CharField("市场类型", max_length=20, db_index=True)

    # 入场信息
    entry_time = models.DateTimeField("入场时间", db_index=True)
    entry_price = models.DecimalField("入场价格", max_digits=20, decimal_places=8)

    # 最低点信息
    lowest_time = models.DateTimeField("最低点时间", null=True, blank=True)
    lowest_price = models.DecimalField(
        "最低价格", max_digits=20, decimal_places=8, null=True, blank=True
    )
    bars_to_lowest = models.IntegerField("到达最低点K线数", null=True, blank=True)
    max_profit_percent = models.DecimalField(
        "最大盈利百分比",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="做空视角：(entry_price - lowest_price) / entry_price * 100",
    )

    # 反弹信息
    has_rebound = models.BooleanField("是否有反弹", default=False)
    rebound_high_price = models.DecimalField(
        "反弹最高价", max_digits=20, decimal_places=8, null=True, blank=True
    )
    rebound_percent = models.DecimalField(
        "反弹幅度百分比",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="(rebound_high - lowest_price) / lowest_price * 100",
    )
    max_drawdown_percent = models.DecimalField(
        "最大回撤百分比",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="做空视角：持仓期间价格上涨导致的最大浮亏",
    )

    # 最终结果
    exit_time = models.DateTimeField("出场时间", null=True, blank=True)
    exit_price = models.DecimalField(
        "出场价格", max_digits=20, decimal_places=8, null=True, blank=True
    )
    final_profit_percent = models.DecimalField(
        "最终收益率",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="(entry_price - exit_price) / entry_price * 100",
    )
    is_profitable = models.BooleanField("是否盈利", null=True, blank=True)

    # 配置参数
    observation_bars = models.IntegerField(
        "观察K线数", default=0, help_text="观察的K线数，0表示观察全部历史数据"
    )

    # 回测状态
    STATUS_CHOICES = [
        ("pending", "待回测"),
        ("completed", "已完成"),
        ("insufficient_data", "数据不足"),
        ("error", "回测错误"),
    ]
    status = models.CharField(
        "回测状态", max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True
    )
    error_message = models.TextField("错误信息", null=True, blank=True)

    # 元数据
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "volume_trap_backtest_result"
        ordering = ["-entry_time"]
        indexes = [
            models.Index(fields=["status", "-entry_time"], name="idx_bt_status_entry"),
            models.Index(fields=["symbol", "interval"], name="idx_bt_symbol_interval"),
            models.Index(fields=["is_profitable"], name="idx_bt_profitable"),
        ]
        verbose_name = "回测结果"
        verbose_name_plural = "回测结果"

    def __str__(self):
        profit_str = f"{self.final_profit_percent:+.2f}%" if self.final_profit_percent else "N/A"
        return f"{self.symbol} ({self.interval}) - {profit_str} @ {self.entry_time.strftime('%Y-%m-%d')}"


class BacktestStatistics(models.Model):
    """整体回测统计结果。

    存储一批回测的聚合统计数据，用于评估整体策略表现。

    Attributes:
        name (str): 统计名称（如 "spot_4h_2025Q1"）
        description (str): 统计描述

        # 筛选条件
        market_type (str): 市场类型筛选
        interval (str): K线周期筛选
        status_filter (str): 状态筛选（如 suspected_abandonment）
        start_date (date): 开始日期
        end_date (date): 结束日期

        # 基础统计
        total_trades (int): 总交易数
        profitable_trades (int): 盈利交易数
        losing_trades (int): 亏损交易数
        win_rate (Decimal): 胜率

        # 收益统计
        avg_profit_percent (Decimal): 平均收益率
        max_profit_percent (Decimal): 最大单笔收益
        min_profit_percent (Decimal): 最小单笔收益（可能为负）
        total_profit_percent (Decimal): 总收益率

        # 回撤统计
        avg_max_drawdown (Decimal): 平均最大回撤
        worst_drawdown (Decimal): 最差回撤

        # 时间统计
        avg_bars_to_lowest (Decimal): 平均到达最低点K线数

        # 风险调整收益
        profit_factor (Decimal): 盈亏比 = 总盈利/总亏损
        sharpe_ratio (Decimal): 夏普比率（可选）

    Examples:
        >>> stats = BacktestStatistics.objects.latest('created_at')
        >>> print(f"胜率: {stats.win_rate}%")
        >>> print(f"盈亏比: {stats.profit_factor}")
    """

    # 基本信息
    name = models.CharField("统计名称", max_length=100, db_index=True)
    description = models.TextField("描述", null=True, blank=True)

    # 筛选条件
    market_type = models.CharField(
        "市场类型", max_length=20, null=True, blank=True, help_text="all表示全部"
    )
    interval = models.CharField(
        "K线周期", max_length=10, null=True, blank=True, help_text="all表示全部"
    )
    status_filter = models.CharField(
        "状态筛选",
        max_length=50,
        null=True,
        blank=True,
        help_text="逗号分隔的状态列表",
    )
    start_date = models.DateField("开始日期", null=True, blank=True)
    end_date = models.DateField("结束日期", null=True, blank=True)
    observation_bars = models.IntegerField("观察K线数", default=0)

    # 基础统计
    total_trades = models.IntegerField("总交易数", default=0)
    profitable_trades = models.IntegerField("盈利交易数", default=0)
    losing_trades = models.IntegerField("亏损交易数", default=0)
    win_rate = models.DecimalField(
        "胜率", max_digits=5, decimal_places=2, null=True, blank=True
    )

    # 收益统计
    avg_profit_percent = models.DecimalField(
        "平均收益率", max_digits=10, decimal_places=2, null=True, blank=True
    )
    max_profit_percent = models.DecimalField(
        "最大单笔收益", max_digits=10, decimal_places=2, null=True, blank=True
    )
    min_profit_percent = models.DecimalField(
        "最小单笔收益", max_digits=10, decimal_places=2, null=True, blank=True
    )
    total_profit_percent = models.DecimalField(
        "总收益率", max_digits=10, decimal_places=2, null=True, blank=True
    )

    # 回撤统计
    avg_max_drawdown = models.DecimalField(
        "平均最大回撤", max_digits=10, decimal_places=2, null=True, blank=True
    )
    worst_drawdown = models.DecimalField(
        "最差回撤", max_digits=10, decimal_places=2, null=True, blank=True
    )

    # 时间统计
    avg_bars_to_lowest = models.DecimalField(
        "平均到达最低点K线数", max_digits=10, decimal_places=2, null=True, blank=True
    )

    # 风险调整收益
    profit_factor = models.DecimalField(
        "盈亏比", max_digits=10, decimal_places=2, null=True, blank=True
    )

    # 元数据
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "volume_trap_backtest_statistics"
        ordering = ["-created_at"]
        verbose_name = "回测统计"
        verbose_name_plural = "回测统计"

    def __str__(self):
        return f"{self.name} - 胜率{self.win_rate}% ({self.total_trades}笔)"
