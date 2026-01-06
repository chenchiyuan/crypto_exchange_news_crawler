"""
Django 数据库模型定义

Purpose:
    定义回测结果的持久化数据模型，用于存储回测结果和订单详情。

关联任务: TASK-014-012, TASK-014-013
关联需求: FP-014-018, FP-014-019（prd.md）
关联架构: architecture.md#7 关键技术决策 - 决策点4

Models:
    - BacktestResult: 回测结果主表，存储回测配置、权益曲线和量化指标
    - BacktestOrder: 回测订单表，存储订单详情（外键关联BacktestResult）

Design Philosophy:
    - 使用 JSONField 存储复杂数据（equity_curve, metrics）
    - 使用 Decimal 字段确保金额精度
    - 支持级联删除（删除回测结果时自动删除关联订单）
"""

from django.db import models


class BacktestResult(models.Model):
    """
    回测结果数据模型

    Purpose:
        存储单次回测的完整结果，包括配置参数、权益曲线和量化指标。
        支持回测结果的持久化存储和历史查询。

    Fields:
        基本信息:
            - strategy_name: 策略名称（如 "DDPS-Z"）
            - symbol: 交易对（如 "BTCUSDT"）
            - interval: K线周期（如 "4h"）
            - market_type: 市场类型（futures/spot）
            - start_date: 回测开始日期
            - end_date: 回测结束日期

        回测参数:
            - initial_cash: 初始资金（USDT）
            - position_size: 单笔买入金额（USDT）
            - commission_rate: 手续费率
            - risk_free_rate: 无风险收益率（年化百分比）

        结果数据:
            - equity_curve: 权益曲线（JSON数组）
            - metrics: 量化指标（JSON对象，包含17个P0指标）

        元数据:
            - created_at: 创建时间（自动记录）

    Example:
        >>> result = BacktestResult.objects.create(
        ...     strategy_name="DDPS-Z",
        ...     symbol="BTCUSDT",
        ...     interval="4h",
        ...     market_type="futures",
        ...     start_date=datetime.date(2025, 1, 1),
        ...     end_date=datetime.date(2025, 12, 31),
        ...     initial_cash=Decimal("10000.00"),
        ...     position_size=Decimal("100.00"),
        ...     commission_rate=Decimal("0.001"),
        ...     risk_free_rate=Decimal("3.00"),
        ...     equity_curve=[...],
        ...     metrics={...}
        ... )

    Context:
        关联任务：TASK-014-012
        关联需求：FP-014-018
    """

    # === 基本信息 ===
    strategy_name = models.CharField(
        max_length=100,
        verbose_name="策略名称",
        help_text="回测使用的策略名称，如 DDPS-Z"
    )
    symbol = models.CharField(
        max_length=20,
        verbose_name="交易对",
        help_text="交易对符号，如 BTCUSDT"
    )
    interval = models.CharField(
        max_length=10,
        verbose_name="K线周期",
        help_text="K线周期，如 4h, 1d"
    )
    market_type = models.CharField(
        max_length=10,
        choices=[("futures", "合约"), ("spot", "现货")],
        default="futures",
        verbose_name="市场类型",
        help_text="市场类型：futures（合约）或 spot（现货）"
    )
    start_date = models.DateField(
        verbose_name="开始日期",
        help_text="回测开始日期"
    )
    end_date = models.DateField(
        verbose_name="结束日期",
        help_text="回测结束日期"
    )

    # === 回测参数 ===
    initial_cash = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        verbose_name="初始资金",
        help_text="回测初始资金（USDT）"
    )
    position_size = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        verbose_name="单笔金额",
        help_text="单笔买入金额（USDT）"
    )
    commission_rate = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        verbose_name="手续费率",
        help_text="交易手续费率，如 0.001 表示千一"
    )
    risk_free_rate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name="无风险收益率",
        help_text="年化无风险收益率（百分比），如 3.00 表示 3%"
    )

    # === 结果数据 ===
    equity_curve = models.JSONField(
        default=list,
        verbose_name="权益曲线",
        help_text="权益曲线数据（JSON数组），每个元素包含 timestamp, cash, position_value, equity, equity_rate"
    )
    metrics = models.JSONField(
        default=dict,
        verbose_name="量化指标",
        help_text="量化指标数据（JSON对象），包含17个P0指标"
    )

    # === 元数据 ===
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间",
        help_text="记录创建时间"
    )

    class Meta:
        app_label = "strategy_adapter"
        db_table = "strategy_adapter_backtest_result"
        verbose_name = "回测结果"
        verbose_name_plural = "回测结果"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["strategy_name"]),
            models.Index(fields=["symbol"]),
            models.Index(fields=["market_type"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.strategy_name} - {self.symbol} ({self.start_date} ~ {self.end_date})"


class BacktestOrder(models.Model):
    """
    回测订单数据模型

    Purpose:
        存储回测过程中的订单详情，通过外键关联到BacktestResult。
        支持查询单个回测的所有订单记录。

    Fields:
        关联关系:
            - backtest_result: 外键关联到 BacktestResult（级联删除）

        订单信息:
            - order_id: 订单ID（策略内部标识）
            - status: 订单状态（filled/closed）
            - buy_price: 买入价格
            - buy_timestamp: 买入时间戳（毫秒）
            - sell_price: 卖出价格（可空）
            - sell_timestamp: 卖出时间戳（可空）

        持仓信息:
            - quantity: 持仓数量
            - position_value: 持仓市值
            - commission: 手续费

        收益信息:
            - profit_loss: 盈亏金额
            - profit_loss_rate: 盈亏率
            - holding_periods: 持仓K线数

    Example:
        >>> order = BacktestOrder.objects.create(
        ...     backtest_result=result,
        ...     order_id="DDPS-Z-001",
        ...     status="closed",
        ...     buy_price=Decimal("50000.00"),
        ...     buy_timestamp=1640995200000,
        ...     sell_price=Decimal("52000.00"),
        ...     sell_timestamp=1641081600000,
        ...     quantity=Decimal("0.002"),
        ...     position_value=Decimal("100.00"),
        ...     commission=Decimal("0.20"),
        ...     profit_loss=Decimal("3.80"),
        ...     profit_loss_rate=Decimal("3.80"),
        ...     holding_periods=6
        ... )

    Context:
        关联任务：TASK-014-013
        关联需求：FP-014-019
    """

    # === 关联关系 ===
    backtest_result = models.ForeignKey(
        BacktestResult,
        on_delete=models.CASCADE,
        related_name="orders",
        verbose_name="回测结果",
        help_text="关联的回测结果"
    )

    # === 订单信息 ===
    order_id = models.CharField(
        max_length=100,
        verbose_name="订单ID",
        help_text="策略内部订单标识"
    )
    status = models.CharField(
        max_length=20,
        choices=[("filled", "持仓中"), ("closed", "已平仓")],
        verbose_name="订单状态",
        help_text="订单状态：filled（持仓中）或 closed（已平仓）"
    )
    buy_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name="买入价格",
        help_text="买入成交价格"
    )
    buy_timestamp = models.BigIntegerField(
        verbose_name="买入时间戳",
        help_text="买入时间戳（毫秒）"
    )
    sell_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name="卖出价格",
        help_text="卖出成交价格（持仓中为空）"
    )
    sell_timestamp = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name="卖出时间戳",
        help_text="卖出时间戳（毫秒，持仓中为空）"
    )

    # === 持仓信息 ===
    quantity = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name="持仓数量",
        help_text="持仓数量（币数）"
    )
    position_value = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        verbose_name="持仓市值",
        help_text="持仓市值（USDT）"
    )
    commission = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name="手续费",
        help_text="总手续费（开仓+平仓）"
    )

    # === 收益信息 ===
    profit_loss = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="盈亏金额",
        help_text="盈亏金额（USDT，持仓中为空）"
    )
    profit_loss_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="盈亏率",
        help_text="盈亏率（%，持仓中为空）"
    )
    holding_periods = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="持仓K线数",
        help_text="持仓K线数（持仓中为空）"
    )

    class Meta:
        app_label = "strategy_adapter"
        db_table = "strategy_adapter_backtest_order"
        verbose_name = "回测订单"
        verbose_name_plural = "回测订单"
        ordering = ["buy_timestamp"]
        indexes = [
            models.Index(fields=["order_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["buy_timestamp"]),
        ]

    def __str__(self) -> str:
        return f"{self.order_id} ({self.status})"
