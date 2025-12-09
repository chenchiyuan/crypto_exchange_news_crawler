"""
价格监控系统序列化器
Price Monitor Serializers

为REST API提供数据序列化和反序列化
Feature: 001-price-alert-monitor
Task: T047-T050
"""
from rest_framework import serializers
from grid_trading.django_models import (
    MonitoredContract,
    PriceAlertRule,
    AlertTriggerLog,
    DataUpdateLog,
    SystemConfig
)


class MonitoredContractSerializer(serializers.ModelSerializer):
    """监控合约序列化器"""

    class Meta:
        model = MonitoredContract
        fields = [
            'symbol',
            'source',
            'status',
            'last_screening_date',
            'last_data_update_at',
            'created_at'
        ]
        read_only_fields = ['created_at', 'last_screening_date', 'last_data_update_at']

    def validate_symbol(self, value):
        """验证合约代码格式"""
        if not value or len(value) < 3:
            raise serializers.ValidationError("合约代码长度至少3个字符")

        # 币安合约代码通常以USDT结尾
        if not value.endswith('USDT'):
            raise serializers.ValidationError("合约代码必须以USDT结尾")

        return value.upper()


class MonitoredContractListSerializer(serializers.ModelSerializer):
    """监控合约列表序列化器(简化版)"""

    status_display = serializers.CharField(source='get_status_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)

    class Meta:
        model = MonitoredContract
        fields = [
            'symbol',
            'source',
            'source_display',
            'status',
            'status_display',
            'last_screening_date',
            'created_at'
        ]


class MonitoredContractCreateSerializer(serializers.Serializer):
    """批量创建监控合约序列化器"""

    symbols = serializers.ListField(
        child=serializers.CharField(max_length=20),
        min_length=1,
        max_length=100,
        help_text="合约代码列表，最多100个"
    )

    source = serializers.ChoiceField(
        choices=['manual', 'auto'],
        default='manual',
        help_text="来源：manual=手动添加, auto=自动同步"
    )

    def validate_symbols(self, value):
        """验证合约代码列表"""
        validated = []
        for symbol in value:
            symbol = symbol.strip().upper()
            if not symbol.endswith('USDT'):
                raise serializers.ValidationError(
                    f"合约代码 {symbol} 必须以USDT结尾"
                )
            validated.append(symbol)

        # 去重
        validated = list(set(validated))

        return validated


class MonitoredContractBulkUpdateSerializer(serializers.Serializer):
    """批量更新监控合约状态序列化器"""

    symbols = serializers.ListField(
        child=serializers.CharField(max_length=20),
        min_length=1,
        help_text="合约代码列表"
    )

    status = serializers.ChoiceField(
        choices=['enabled', 'disabled', 'expired'],
        help_text="目标状态"
    )


class PriceAlertRuleSerializer(serializers.ModelSerializer):
    """价格触发规则序列化器"""

    class Meta:
        model = PriceAlertRule
        fields = [
            'rule_id',
            'name',
            'description',
            'enabled',
            'parameters',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_parameters(self, value):
        """验证规则参数JSON格式"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("参数必须是JSON对象")

        # 验证特定规则的参数
        rule_id = self.instance.rule_id if self.instance else None

        if rule_id in [3, 4]:  # MA规则
            if 'ma_threshold' in value:
                threshold = value['ma_threshold']
                if not isinstance(threshold, (int, float)) or threshold <= 0 or threshold > 10:
                    raise serializers.ValidationError(
                        "ma_threshold必须在(0, 10]范围内"
                    )

        if rule_id == 5:  # 价格分布规则
            if 'percentile' in value:
                percentile = value['percentile']
                if not isinstance(percentile, int) or percentile < 50 or percentile > 99:
                    raise serializers.ValidationError(
                        "percentile必须在[50, 99]范围内"
                    )

        return value


class AlertTriggerLogSerializer(serializers.ModelSerializer):
    """触发日志序列化器"""

    rule_name = serializers.SerializerMethodField()
    current_price_display = serializers.SerializerMethodField()

    class Meta:
        model = AlertTriggerLog
        fields = [
            'id',
            'symbol',
            'rule_id',
            'rule_name',
            'current_price',
            'current_price_display',
            'pushed',
            'pushed_at',
            'skip_reason',
            'extra_info',
            'triggered_at'
        ]

    def get_rule_name(self, obj):
        """获取规则名称"""
        rule_names = {
            1: "7天价格新高",
            2: "7天价格新低",
            3: "价格触及MA20",
            4: "价格触及MA99",
            5: "价格达到分布区间极值"
        }
        return rule_names.get(obj.rule_id, f"规则{obj.rule_id}")

    def get_current_price_display(self, obj):
        """格式化价格显示"""
        return f"${float(obj.current_price):,.2f}"


class AlertTriggerLogListSerializer(serializers.ModelSerializer):
    """触发日志列表序列化器(简化版)"""

    rule_name = serializers.SerializerMethodField()

    class Meta:
        model = AlertTriggerLog
        fields = [
            'id',
            'symbol',
            'rule_id',
            'rule_name',
            'current_price',
            'pushed',
            'triggered_at'
        ]

    def get_rule_name(self, obj):
        """获取规则名称"""
        rule_names = {
            1: "7天新高",
            2: "7天新低",
            3: "触及MA20",
            4: "触及MA99",
            5: "分布极值"
        }
        return rule_names.get(obj.rule_id, f"R{obj.rule_id}")


class DataUpdateLogSerializer(serializers.ModelSerializer):
    """数据更新日志序列化器"""

    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = DataUpdateLog
        fields = [
            'id',
            'started_at',
            'completed_at',
            'execution_seconds',
            'status',
            'status_display',
            'contracts_count',
            'klines_count',
            'error_message'
        ]


class SystemConfigSerializer(serializers.ModelSerializer):
    """系统配置序列化器"""

    class Meta:
        model = SystemConfig
        fields = [
            'key',
            'value',
            'description',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_key(self, value):
        """验证配置键"""
        # 只能更新现有配置，不能创建新配置(通过API)
        if not self.instance:
            allowed_keys = [
                'duplicate_suppress_minutes',
                'data_update_interval_minutes',
                'sync_schedule_time',
                'huicheng_push_token',
                'huicheng_push_channel',
                'max_monitored_contracts',
                'screening_api_base_url',
                'screening_min_vdr',
                'screening_min_amplitude',
                'screening_max_ma99_slope',
                'screening_min_funding_rate',
                'screening_min_volume',
            ]

            if value not in allowed_keys:
                raise serializers.ValidationError(
                    f"不允许创建配置键: {value}"
                )

        return value

    def validate_value(self, value):
        """验证配置值"""
        # 基本验证：不能为空
        if not value or not value.strip():
            raise serializers.ValidationError("配置值不能为空")

        return value


class MonitoringStatsSerializer(serializers.Serializer):
    """监控统计序列化器"""

    total_contracts = serializers.IntegerField(help_text="总合约数")
    enabled_contracts = serializers.IntegerField(help_text="启用的合约数")
    disabled_contracts = serializers.IntegerField(help_text="暂停的合约数")
    auto_contracts = serializers.IntegerField(help_text="自动同步的合约数")
    manual_contracts = serializers.IntegerField(help_text="手动添加的合约数")

    total_rules = serializers.IntegerField(help_text="总规则数")
    enabled_rules = serializers.IntegerField(help_text="启用的规则数")

    triggers_today = serializers.IntegerField(help_text="今日触发次数")
    pushes_today = serializers.IntegerField(help_text="今日推送次数")

    last_data_update = serializers.DateTimeField(
        allow_null=True,
        help_text="最后数据更新时间"
    )
    last_check = serializers.DateTimeField(
        allow_null=True,
        help_text="最后检测时间"
    )
