"""
巨量诱多/弃盘检测系统 - 数据模型定义

包含3个核心模型：VolumeTrapMonitor, VolumeTrapIndicators, VolumeTrapStateTransition
以及回测模型：BacktestResult, BacktestStatistics

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md (持久化层)
    - Task: TASK-002-001
"""

from django.db import models


class VolumeTrapMonitor(models.Model):
    """巨量诱多/弃盘监控池记录模型。

    用于存储通过三阶段状态机筛选的交易对监控记录，跟踪从"异常放量发现"
    到"确定弃盘"的完整生命周期。

    三阶段状态机流转：
        pending → suspected_abandonment → confirmed_abandonment
        任意状态 → invalidated (失效条件：价格收复P_trigger)

    Attributes:
        futures_contract (ForeignKey): 关联的USDT永续合约（market_type='futures'时使用）
        spot_contract (ForeignKey): 关联的现货交易对（market_type='spot'时使用）
        market_type (str): 市场类型（'spot'现货或'futures'合约）
        interval (str): K线周期（1h/4h/1d）
        trigger_time (datetime): 触发阶段1的时间戳
        trigger_price (Decimal): 触发时的价格（P_trigger）
        trigger_volume (Decimal): 触发时的成交量（V_trigger）
        trigger_kline_high (Decimal): 触发K线最高价
        trigger_kline_low (Decimal): 触发K线最低价
        status (str): 状态机当前状态（pending/suspected_abandonment/confirmed_abandonment/invalidated）
        phase_1_passed (bool): 阶段1通过标记（默认True）
        phase_2_passed (bool): 阶段2通过标记（默认False）
        phase_3_passed (bool): 阶段3通过标记（默认False）
        created_at (datetime): 记录创建时间
        updated_at (datetime): 记录最后更新时间

    Related:
        - PRD: docs/iterations/002-volume-trap-detection/prd.md (第二部分-2.2节)
        - Architecture: docs/iterations/002-volume-trap-detection/architecture.md (持久化层)
        - Task: TASK-002-001

    Constraints:
        - 唯一性约束：(spot_contract/futures_contract, interval, trigger_time, market_type) 组合唯一
        - interval 必须为 ['1h', '4h', '1d'] 之一
        - market_type 必须为 ['spot', 'futures'] 之一
        - 外键约束：futures_contract/spot_contract 必须引用对应的 monitor 模型
        - 互斥约束：futures_contract 和 spot_contract 不能同时设置

    Indexes:
        - (status, -trigger_time): 按状态查询最近触发记录
        - (futures_contract, status): 按合约查询特定状态记录
        - (interval, status): 按周期和状态筛选

    Examples:
        >>> from monitor.models import FuturesContract
        >>> from decimal import Decimal
        >>> from django.utils import timezone
        >>>
        >>> contract = FuturesContract.objects.get(symbol='ETHUSDT')
        >>> monitor = VolumeTrapMonitor.objects.create(
        ...     futures_contract=contract,
        ...     interval='4h',
        ...     trigger_time=timezone.now(),
        ...     trigger_price=Decimal('98234.56'),
        ...     trigger_volume=Decimal('1234567.89'),
        ...     trigger_kline_high=Decimal('99000.00'),
        ...     trigger_kline_low=Decimal('97000.00'),
        ... )
        >>> monitor.status
        'pending'
        >>> monitor.phase_1_passed
        True
    """

    # 关联交易对（条件外键：现货和合约互斥）
    futures_contract = models.ForeignKey(
        "monitor.FuturesContract",
        on_delete=models.CASCADE,
        related_name="volume_trap_monitors",
        verbose_name="关联合约",
        null=True,
        blank=True,
    )
    spot_contract = models.ForeignKey(
        "monitor.SpotContract",
        on_delete=models.CASCADE,
        related_name="volume_trap_monitors",
        verbose_name="关联现货交易对",
        null=True,
        blank=True,
    )

    # 市场类型
    market_type = models.CharField(
        max_length=20,
        choices=[("spot", "现货"), ("futures", "合约")],
        default="futures",
        db_index=True,
        help_text="市场类型：现货或合约",
    )

    # 监控周期配置
    interval = models.CharField(
        max_length=10,
        choices=[("1h", "1小时"), ("4h", "4小时"), ("1d", "1天")],
        default="4h",
        help_text="K线周期",
    )

    # 触发信息
    trigger_time = models.DateTimeField("触发时间", db_index=True)
    trigger_price = models.DecimalField("触发价格", max_digits=20, decimal_places=8)
    trigger_volume = models.DecimalField("触发成交量", max_digits=30, decimal_places=8)
    trigger_kline_high = models.DecimalField("触发K线最高价", max_digits=20, decimal_places=8)
    trigger_kline_low = models.DecimalField("触发K线最低价", max_digits=20, decimal_places=8)

    # 状态机
    status = models.CharField(
        max_length=30,
        choices=[
            ("pending", "待观察"),
            ("suspected_abandonment", "疑似弃盘"),
            ("confirmed_abandonment", "确定弃盘"),
            ("invalidated", "失效"),
        ],
        default="pending",
        db_index=True,
    )

    # 阶段标记
    phase_1_passed = models.BooleanField("阶段1通过", default=True)
    phase_2_passed = models.BooleanField("阶段2通过", default=False)
    phase_3_passed = models.BooleanField("阶段3通过", default=False)

    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "volume_trap_monitor"
        unique_together = [
            ["spot_contract", "interval", "trigger_time"],
            ["futures_contract", "interval", "trigger_time"],
        ]
        indexes = [
            models.Index(fields=["status", "-trigger_time"], name="idx_vt_status_time"),
            models.Index(fields=["spot_contract", "status"], name="idx_vt_spot_status"),
            models.Index(fields=["futures_contract", "status"], name="idx_vt_contract_status"),
            models.Index(fields=["interval", "status"], name="idx_vt_interval_status"),
            models.Index(fields=["market_type", "status"], name="idx_vt_market_type_status"),
        ]
        verbose_name = "量价异常监控"
        verbose_name_plural = "量价异常监控"
        ordering = ["-trigger_time"]

    def clean(self):
        """验证市场类型和外键的互斥约束"""
        from django.core.exceptions import ValidationError

        # 检查futures_contract和spot_contract不能同时设置
        if self.futures_contract and self.spot_contract:
            raise ValidationError(
                {
                    "futures_contract": "不能同时设置合约和现货交易对",
                    "spot_contract": "不能同时设置合约和现货交易对",
                }
            )

        # 检查必须至少设置一个
        if not self.futures_contract and not self.spot_contract:
            raise ValidationError("必须设置合约或现货交易对")

        # 检查market_type与外键的一致性
        if self.futures_contract and self.market_type != "futures":
            raise ValidationError({"market_type": '设置合约时，market_type必须为"futures"'})

        if self.spot_contract and self.market_type != "spot":
            raise ValidationError({"market_type": '设置现货交易对时，market_type必须为"spot"'})

    def __str__(self):
        contract = self.futures_contract if self.futures_contract else self.spot_contract
        symbol = contract.symbol if contract else "Unknown"
        return (
            f"{symbol} ({self.interval}) - "
            f"{self.get_status_display()} @ {self.trigger_time.strftime('%Y-%m-%d %H:%M')}"
        )


class VolumeTrapIndicators(models.Model):
    """量化指标快照模型 - 选择性存储（状态变更时）。

    用于存储关键节点的量化指标快照，仅在以下情况记录：
    1. 监控记录首次创建（阶段1触发）
    2. 状态发生变更（pending→suspected→confirmed→invalidated）

    指标分三个阶段：
        - 阶段1：RVOL倍数、振幅倍数、上影线比例
        - 阶段2：成交量留存率、关键位跌破、价差效率
        - 阶段3：MA(7/25)、MA25斜率、OBV、OBV背离、ATR、ATR压缩

    Attributes:
        monitor (ForeignKey): 关联的监控记录
        snapshot_time (datetime): 快照时间戳
        kline_close_price (Decimal): K线收盘价

        # 阶段1指标
        rvol_ratio (Decimal): RVOL倍数（当前成交量 / MA(V,20)）
        amplitude_ratio (Decimal): 振幅倍数（当前振幅 / 过去30根均值）
        upper_shadow_ratio (Decimal): 上影线比例（(最高-收盘)/(最高-最低) * 100）

        # 阶段2指标
        volume_retention_ratio (Decimal): 成交量留存率（avg(V_post) / V_trigger * 100）
        key_level_breach (bool): 关键位跌破标记
        price_efficiency (Decimal): 价差效率（|ΔPrice| / Volume）

        # 阶段3指标
        ma7 (Decimal): 7期移动平均线
        ma25 (Decimal): 25期移动平均线
        ma25_slope (Decimal): MA(25)斜率
        obv (Decimal): 能量潮指标
        obv_divergence (bool): OBV底背离标记
        atr (Decimal): 平均真实波幅
        atr_compression (bool): ATR压缩标记

        created_at (datetime): 快照创建时间

    Related:
        - PRD: docs/iterations/002-volume-trap-detection/prd.md
        - Architecture: docs/iterations/002-volume-trap-detection/architecture.md (决策点三：指标快照存储策略)
        - Task: TASK-002-001

    Constraints:
        - 外键约束：monitor 必须引用 VolumeTrapMonitor
        - 可为空字段：所有指标字段（根据阶段不同，部分指标可能未计算）

    Indexes:
        - (monitor, -snapshot_time): 按监控记录查询时间倒序快照

    Storage Strategy:
        选择性快照（状态变更时存储），而非全周期记录，降低80-90%存储成本。

    Examples:
        >>> indicator = VolumeTrapIndicators.objects.create(
        ...     monitor=monitor,
        ...     snapshot_time=timezone.now(),
        ...     kline_close_price=Decimal('98000.00'),
        ...     rvol_ratio=Decimal('12.50'),
        ...     amplitude_ratio=Decimal('3.20'),
        ...     upper_shadow_ratio=Decimal('55.00'),
        ... )
        >>> indicator.rvol_ratio
        Decimal('12.50')
    """

    # 关联监控记录
    monitor = models.ForeignKey(
        "VolumeTrapMonitor",
        on_delete=models.CASCADE,
        related_name="indicators",
        verbose_name="关联监控记录",
    )

    # 快照时间
    snapshot_time = models.DateTimeField("快照时间", db_index=True)
    kline_close_price = models.DecimalField("K线收盘价", max_digits=20, decimal_places=8)

    # 阶段1指标
    rvol_ratio = models.DecimalField(
        "RVOL倍数",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="当前成交量 / MA(V,20)",
    )
    amplitude_ratio = models.DecimalField(
        "振幅倍数",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="当前振幅 / 过去30根均值",
    )
    upper_shadow_ratio = models.DecimalField(
        "上影线比例",
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="(最高-收盘)/(最高-最低) * 100",
    )

    # 阶段2指标
    volume_retention_ratio = models.DecimalField(
        "成交量留存率",
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="avg(V_post) / V_trigger * 100",
    )
    key_level_breach = models.BooleanField("关键位跌破", default=False, null=True, blank=True)
    price_efficiency = models.DecimalField(
        "价差效率",
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="|ΔPrice| / Volume",
    )

    # 阶段3指标
    ma7 = models.DecimalField("MA(7)", max_digits=20, decimal_places=8, null=True, blank=True)
    ma25 = models.DecimalField("MA(25)", max_digits=20, decimal_places=8, null=True, blank=True)
    ma25_slope = models.DecimalField(
        "MA(25)斜率", max_digits=10, decimal_places=6, null=True, blank=True
    )
    obv = models.DecimalField("OBV", max_digits=30, decimal_places=2, null=True, blank=True)
    obv_divergence = models.BooleanField("OBV底背离", default=False, null=True, blank=True)
    atr = models.DecimalField("ATR", max_digits=20, decimal_places=8, null=True, blank=True)
    atr_compression = models.BooleanField("ATR压缩", default=False, null=True, blank=True)

    # 元数据
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "volume_trap_indicators"
        ordering = ["monitor", "-snapshot_time"]
        indexes = [
            models.Index(fields=["monitor", "-snapshot_time"], name="idx_vt_ind_monitor_time"),
        ]
        verbose_name = "量价异常指标快照"
        verbose_name_plural = "量价异常指标快照"

    def __str__(self):
        return (
            f"{self.monitor.futures_contract.symbol} - "
            f"Snapshot @ {self.snapshot_time.strftime('%Y-%m-%d %H:%M')}"
        )


class VolumeTrapStateTransition(models.Model):
    """状态转换日志模型。

    用于记录监控记录的状态流转历史，便于追踪和调试状态机行为。

    状态流转路径：
        - pending → suspected_abandonment: 阶段2条件满足
        - suspected_abandonment → confirmed_abandonment: 阶段3条件满足
        - 任意状态 → invalidated: 价格收复P_trigger

    Attributes:
        monitor (ForeignKey): 关联的监控记录
        from_status (str): 原状态
        to_status (str): 新状态
        trigger_condition (dict): 触发条件JSON（记录具体指标值）
        transition_time (datetime): 转换时间
        created_at (datetime): 日志创建时间

    Related:
        - PRD: docs/iterations/002-volume-trap-detection/prd.md
        - Architecture: docs/iterations/002-volume-trap-detection/architecture.md (持久化层)
        - Task: TASK-002-001

    Constraints:
        - 外键约束：monitor 必须引用 VolumeTrapMonitor
        - trigger_condition 使用JSONField存储复杂对象

    Indexes:
        - (monitor, transition_time): 按监控记录查询时间序列转换历史

    JSON Structure (trigger_condition):
        {
            "rvol_ratio": 12.5,
            "amplitude_ratio": 3.2,
            "upper_shadow_ratio": 55.0,
            "phase": 1,
            "timestamp": "2024-12-24T16:00:00Z"
        }

    Examples:
        >>> transition = VolumeTrapStateTransition.objects.create(
        ...     monitor=monitor,
        ...     from_status='pending',
        ...     to_status='suspected_abandonment',
        ...     trigger_condition={
        ...         'volume_retention_ratio': 12.5,
        ...         'key_level_breach': True,
        ...         'price_efficiency': 0.00012,
        ...         'phase': 2
        ...     },
        ...     transition_time=timezone.now()
        ... )
        >>> transition.get_trigger_phase()
        2
    """

    # 关联监控记录
    monitor = models.ForeignKey(
        "VolumeTrapMonitor",
        on_delete=models.CASCADE,
        related_name="state_transitions",
        verbose_name="关联监控记录",
    )

    # 状态转换
    from_status = models.CharField("原状态", max_length=30)
    to_status = models.CharField("新状态", max_length=30)

    # 触发条件（JSON格式）
    trigger_condition = models.JSONField("触发条件", help_text="记录触发状态变更的具体指标值")

    # 时间
    transition_time = models.DateTimeField("转换时间")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "volume_trap_state_transition"
        ordering = ["monitor", "transition_time"]
        indexes = [
            models.Index(fields=["monitor", "transition_time"], name="idx_vt_trans_monitor_time"),
        ]
        verbose_name = "状态转换日志"
        verbose_name_plural = "状态转换日志"

    def __str__(self):
        return (
            f"{self.monitor.futures_contract.symbol} - "
            f"{self.from_status} → {self.to_status} @ {self.transition_time.strftime('%Y-%m-%d %H:%M')}"
        )

    def get_trigger_phase(self):
        """获取触发条件所属的阶段。

        Returns:
            int: 阶段编号（1/2/3），如果未记录则返回None

        Examples:
            >>> transition.trigger_condition = {'phase': 2}
            >>> transition.get_trigger_phase()
            2
        """
        return self.trigger_condition.get("phase", None)


# 导入回测模型
from volume_trap.models_backtest import BacktestResult, BacktestStatistics

__all__ = [
    "VolumeTrapMonitor",
    "VolumeTrapIndicators",
    "VolumeTrapStateTransition",
    "BacktestResult",
    "BacktestStatistics",
]
