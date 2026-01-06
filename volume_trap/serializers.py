"""
Volume Trap API序列化器

用途：定义REST API的数据序列化和验证逻辑

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md (第五部分-7.1 监控池列表API)
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md (API服务层)
    - Task: TASK-002-040
"""

from rest_framework import serializers

from volume_trap.models import VolumeTrapIndicators, VolumeTrapMonitor, VolumeTrapStateTransition


class VolumeTrapIndicatorsSerializer(serializers.ModelSerializer):
    """指标快照序列化器。

    序列化VolumeTrapIndicators模型，返回指标快照数据。

    业务逻辑：
        - 序列化所有指标字段
        - 时间字段格式化为ISO 8601
        - Decimal字段转换为float

    Examples:
        >>> indicator = VolumeTrapIndicators.objects.first()
        >>> serializer = VolumeTrapIndicatorsSerializer(indicator)
        >>> serializer.data
        {
            'id': 1,
            'snapshot_time': '2024-12-24T12:00:00+08:00',
            'kline_close_price': 50000.0,
            'rvol_ratio': 10.5,
            'amplitude_ratio': 4.2,
            ...
        }

    Related:
        - PRD: 第五部分-7.1 监控池列表API
        - Architecture: API服务层 - Serializers
        - Task: TASK-002-040
    """

    class Meta:
        model = VolumeTrapIndicators
        fields = [
            "id",
            "snapshot_time",
            "kline_close_price",
            # Discovery阶段指标
            "rvol_ratio",
            "amplitude_ratio",
            "upper_shadow_ratio",
            # Confirmation阶段指标
            "volume_retention_ratio",
            "key_level_breach",
            "price_efficiency",
            # Validation阶段指标
            "ma7",
            "ma25",
            "ma25_slope",
            "obv_divergence",
            "atr",
            "atr_compression",
        ]


class VolumeTrapMonitorSerializer(serializers.ModelSerializer):
    """监控记录序列化器。

    序列化VolumeTrapMonitor模型，返回监控记录 + 最新指标快照。

    业务逻辑：
        - 序列化Monitor主要字段
        - 嵌套序列化最新的Indicators快照
        - 添加合约信息（symbol）
        - 时间字段格式化为ISO 8601
        - Decimal字段转换为float

    Examples:
        >>> monitor = VolumeTrapMonitor.objects.first()
        >>> serializer = VolumeTrapMonitorSerializer(monitor)
        >>> serializer.data
        {
            'id': 1,
            'symbol': 'BTCUSDT',
            'interval': '4h',
            'status': 'pending',
            'trigger_time': '2024-12-24T12:00:00+08:00',
            'trigger_price': 50000.0,
            'latest_indicators': {...},
            ...
        }

    Related:
        - PRD: 第五部分-7.1 监控池列表API
        - Architecture: API服务层 - Serializers
        - Task: TASK-002-040
    """

    # 添加symbol字段（根据market_type动态获取）
    symbol = serializers.SerializerMethodField()

    # 添加market_type字段
    market_type = serializers.CharField(read_only=True)

    # 添加当前价格字段（从latest_indicators中获取）
    current_price = serializers.SerializerMethodField()

    # 添加相对涨跌幅字段
    price_change_percent = serializers.SerializerMethodField()

    # 嵌套序列化最新的Indicators快照
    latest_indicators = serializers.SerializerMethodField()

    class Meta:
        model = VolumeTrapMonitor
        fields = [
            "id",
            "symbol",
            "market_type",
            "interval",
            "trigger_time",
            "trigger_price",
            "trigger_volume",
            "trigger_kline_high",
            "trigger_kline_low",
            "status",
            "phase_1_passed",
            "phase_2_passed",
            "phase_3_passed",
            "current_price",
            "price_change_percent",
            "latest_indicators",
            "created_at",
            "updated_at",
        ]

    def get_symbol(self, obj):
        """获取交易对符号。

        根据market_type动态从对应的合约表中获取symbol。

        Args:
            obj: VolumeTrapMonitor实例

        Returns:
            str: 交易对符号，如果未找到则返回None

        Side Effects:
            - 只读操作，无副作用
        """
        if obj.market_type == "futures" and obj.futures_contract:
            return obj.futures_contract.symbol
        elif obj.market_type == "spot" and obj.spot_contract:
            return obj.spot_contract.symbol
        return None

    def get_latest_indicators(self, obj):
        """获取最新的Indicators快照。

        Args:
            obj: VolumeTrapMonitor实例

        Returns:
            Dict: 最新指标快照的序列化数据，如果没有则返回None

        Side Effects:
            - 查询数据库获取最新的Indicators快照
        """
        latest = obj.indicators.order_by("-snapshot_time").first()
        if latest:
            return VolumeTrapIndicatorsSerializer(latest).data
        return None

    def get_current_price(self, obj):
        """获取当前价格。

        Args:
            obj: VolumeTrapMonitor实例

        Returns:
            float: 当前价格（最新K线收盘价），如果没有则返回None

        Side Effects:
            - 只读操作，无副作用
        """
        # 根据market_type获取symbol
        symbol = self.get_symbol(obj)
        if not symbol:
            return None

        # 优先从KLine表获取最新价格（而不是Indicators快照）
        from backtest.models import KLine

        # 获取最新K线
        latest_kline = KLine.objects.filter(
            symbol=symbol,
            interval=obj.interval
        ).order_by("-open_time").first()

        if latest_kline:
            return float(latest_kline.close_price)

        # 如果KLine表中没有数据，尝试从Indicators快照获取
        latest_indicator = obj.indicators.order_by("-snapshot_time").first()
        if latest_indicator and latest_indicator.kline_close_price:
            return float(latest_indicator.kline_close_price)

        return None

    def get_price_change_percent(self, obj):
        """获取相对涨跌幅。

        Args:
            obj: VolumeTrapMonitor实例

        Returns:
            float: 相对涨跌幅（百分比），格式为 +-X.X%，如果没有数据则返回None

        Side Effects:
            - 只读操作，无副作用
        """
        current_price = self.get_current_price(obj)
        if current_price is None or obj.trigger_price is None:
            return None

        # 计算涨跌幅：(当前价格 - 触发价格) / 触发价格 * 100
        change_percent = (current_price - float(obj.trigger_price)) / float(obj.trigger_price) * 100
        return round(change_percent, 2)


class VolumeTrapStateTransitionSerializer(serializers.ModelSerializer):
    """状态转换日志序列化器。

    序列化VolumeTrapStateTransition模型，返回状态转换历史记录。

    业务逻辑：
        - 序列化状态转换日志
        - 包含trigger_condition JSON字段
        - 时间字段格式化为ISO 8601

    Examples:
        >>> transition = VolumeTrapStateTransition.objects.first()
        >>> serializer = VolumeTrapStateTransitionSerializer(transition)
        >>> serializer.data
        {
            'id': 1,
            'from_status': 'pending',
            'to_status': 'suspected_abandonment',
            'trigger_condition': {...},
            'transition_time': '2024-12-24T16:00:00+08:00'
        }

    Related:
        - PRD: 第五部分-7.2 详情API
        - Architecture: API服务层 - Serializers
        - Task: TASK-002-050 (P1任务)
    """

    class Meta:
        model = VolumeTrapStateTransition
        fields = [
            "id",
            "from_status",
            "to_status",
            "trigger_condition",
            "transition_time",
        ]
