"""
价格监控系统视图
Price Monitor Views

提供REST API接口用于合约管理、规则配置、日志查询等
Feature: 001-price-alert-monitor
Task: T051-T055, T058-T064
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Q, Count
from datetime import timedelta

from grid_trading.django_models import (
    MonitoredContract,
    PriceAlertRule,
    AlertTriggerLog,
    DataUpdateLog,
    SystemConfig
)
from grid_trading.serializers_price_monitor import (
    MonitoredContractSerializer,
    MonitoredContractListSerializer,
    MonitoredContractCreateSerializer,
    MonitoredContractBulkUpdateSerializer,
    PriceAlertRuleSerializer,
    AlertTriggerLogSerializer,
    AlertTriggerLogListSerializer,
    DataUpdateLogSerializer,
    SystemConfigSerializer,
    MonitoringStatsSerializer
)


class MonitoredContractViewSet(viewsets.ModelViewSet):
    """
    监控合约管理API

    list: 获取监控合约列表
    retrieve: 获取单个合约详情
    create: 批量添加监控合约
    update: 更新合约状态
    destroy: 移除合约(标记为expired)
    """
    queryset = MonitoredContract.objects.all()
    serializer_class = MonitoredContractSerializer
    permission_classes = [AllowAny]
    lookup_field = 'symbol'

    def get_queryset(self):
        """
        自定义查询集，支持筛选

        支持的查询参数:
        - source: 来源(manual/auto)
        - status: 状态(enabled/disabled/expired)
        - search: 搜索合约代码(支持模糊匹配)
        """
        queryset = MonitoredContract.objects.all()

        # 按来源筛选
        source = self.request.query_params.get('source')
        if source:
            queryset = queryset.filter(source=source)

        # 按状态筛选
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        else:
            # 默认不显示已过期的合约
            queryset = queryset.exclude(status='expired')

        # 搜索
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(symbol__icontains=search)

        return queryset.order_by('-created_at')

    def get_serializer_class(self):
        """根据action返回不同的序列化器"""
        if self.action == 'list':
            return MonitoredContractListSerializer
        elif self.action == 'create':
            return MonitoredContractCreateSerializer
        elif self.action == 'bulk_update':
            return MonitoredContractBulkUpdateSerializer
        return MonitoredContractSerializer

    def create(self, request, *args, **kwargs):
        """
        批量添加监控合约

        请求体:
        {
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "source": "manual"
        }

        响应:
        {
            "added": ["BTCUSDT", "ETHUSDT"],
            "skipped": [],
            "message": "成功添加2个合约"
        }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        symbols = serializer.validated_data['symbols']
        source = serializer.validated_data['source']

        # 检查已存在的合约
        existing = set(
            MonitoredContract.objects.filter(
                symbol__in=symbols
            ).values_list('symbol', flat=True)
        )

        added = []
        skipped = []

        for symbol in symbols:
            if symbol in existing:
                skipped.append(symbol)
                continue

            MonitoredContract.objects.create(
                symbol=symbol,
                source=source,
                status='enabled'
            )
            added.append(symbol)

        return Response({
            'added': added,
            'skipped': skipped,
            'message': f'成功添加{len(added)}个合约，跳过{len(skipped)}个已存在的合约'
        }, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        """
        移除合约(标记为expired)
        """
        instance = self.get_object()
        instance.status = 'expired'
        instance.save()

        return Response({
            'message': f'成功移除合约 {instance.symbol}'
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """
        批量更新合约状态

        请求体:
        {
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "status": "enabled"
        }

        响应:
        {
            "updated": 2,
            "message": "成功更新2个合约"
        }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        symbols = serializer.validated_data['symbols']
        target_status = serializer.validated_data['status']

        updated = MonitoredContract.objects.filter(
            symbol__in=symbols
        ).update(status=target_status)

        return Response({
            'updated': updated,
            'message': f'成功更新{updated}个合约'
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        获取监控统计信息

        响应:
        {
            "total_contracts": 100,
            "enabled_contracts": 80,
            "disabled_contracts": 15,
            "auto_contracts": 70,
            "manual_contracts": 30,
            "total_rules": 5,
            "enabled_rules": 5,
            "triggers_today": 120,
            "pushes_today": 45,
            "last_data_update": "2025-12-08T10:30:00Z",
            "last_check": "2025-12-08T10:35:00Z"
        }
        """
        # 合约统计
        contracts = MonitoredContract.objects.exclude(status='expired')
        total_contracts = contracts.count()
        enabled_contracts = contracts.filter(status='enabled').count()
        disabled_contracts = contracts.filter(status='disabled').count()
        auto_contracts = contracts.filter(source='auto').count()
        manual_contracts = contracts.filter(source='manual').count()

        # 规则统计
        total_rules = PriceAlertRule.objects.count()
        enabled_rules = PriceAlertRule.objects.filter(enabled=True).count()

        # 触发统计(今日)
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        triggers_today = AlertTriggerLog.objects.filter(
            triggered_at__gte=today_start
        ).count()
        pushes_today = AlertTriggerLog.objects.filter(
            triggered_at__gte=today_start,
            pushed=True
        ).count()

        # 最后执行时间
        last_update_log = DataUpdateLog.objects.filter(
            status='success'
        ).order_by('-completed_at').first()

        last_data_update = last_update_log.completed_at if last_update_log else None

        last_check_contract = MonitoredContract.objects.filter(
            last_check_at__isnull=False
        ).order_by('-last_check_at').first()

        last_check = last_check_contract.last_check_at if last_check_contract else None

        data = {
            'total_contracts': total_contracts,
            'enabled_contracts': enabled_contracts,
            'disabled_contracts': disabled_contracts,
            'auto_contracts': auto_contracts,
            'manual_contracts': manual_contracts,
            'total_rules': total_rules,
            'enabled_rules': enabled_rules,
            'triggers_today': triggers_today,
            'pushes_today': pushes_today,
            'last_data_update': last_data_update,
            'last_check': last_check,
        }

        serializer = MonitoringStatsSerializer(data)
        return Response(serializer.data)


class PriceAlertRuleViewSet(viewsets.ModelViewSet):
    """
    价格触发规则管理API

    list: 获取规则列表
    retrieve: 获取单个规则详情
    update: 更新规则配置
    partial_update: 部分更新规则
    """
    queryset = PriceAlertRule.objects.all()
    serializer_class = PriceAlertRuleSerializer
    permission_classes = [AllowAny]
    lookup_field = 'rule_id'

    # 禁用创建和删除操作(规则是预设的，不能动态创建/删除)
    http_method_names = ['get', 'put', 'patch']

    @action(detail=False, methods=['post'])
    def bulk_enable(self, request):
        """
        批量启用规则

        请求体:
        {
            "rule_ids": [1, 2, 3]
        }
        """
        rule_ids = request.data.get('rule_ids', [])

        if not rule_ids:
            return Response({
                'error': 'rule_ids不能为空'
            }, status=status.HTTP_400_BAD_REQUEST)

        updated = PriceAlertRule.objects.filter(
            rule_id__in=rule_ids
        ).update(enabled=True)

        return Response({
            'updated': updated,
            'message': f'成功启用{updated}条规则'
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def bulk_disable(self, request):
        """
        批量禁用规则

        请求体:
        {
            "rule_ids": [1, 2, 3]
        }
        """
        rule_ids = request.data.get('rule_ids', [])

        if not rule_ids:
            return Response({
                'error': 'rule_ids不能为空'
            }, status=status.HTTP_400_BAD_REQUEST)

        updated = PriceAlertRule.objects.filter(
            rule_id__in=rule_ids
        ).update(enabled=False)

        return Response({
            'updated': updated,
            'message': f'成功禁用{updated}条规则'
        }, status=status.HTTP_200_OK)


class AlertTriggerLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    触发日志查询API

    list: 获取触发日志列表
    retrieve: 获取单个日志详情
    """
    queryset = AlertTriggerLog.objects.all()
    serializer_class = AlertTriggerLogSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        """
        自定义查询集，支持筛选

        支持的查询参数:
        - symbol: 合约代码
        - rule_id: 规则ID
        - pushed: 是否已推送(true/false)
        - date_from: 开始日期(YYYY-MM-DD)
        - date_to: 结束日期(YYYY-MM-DD)
        """
        queryset = AlertTriggerLog.objects.all()

        # 按合约筛选
        symbol = self.request.query_params.get('symbol')
        if symbol:
            queryset = queryset.filter(symbol__icontains=symbol)

        # 按规则筛选
        rule_id = self.request.query_params.get('rule_id')
        if rule_id:
            queryset = queryset.filter(rule_id=rule_id)

        # 按推送状态筛选
        pushed = self.request.query_params.get('pushed')
        if pushed is not None:
            is_pushed = pushed.lower() in ['true', '1', 'yes']
            queryset = queryset.filter(pushed=is_pushed)

        # 按日期范围筛选
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(triggered_at__date__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(triggered_at__date__lte=date_to)

        return queryset.order_by('-triggered_at')

    def get_serializer_class(self):
        """根据action返回不同的序列化器"""
        if self.action == 'list':
            return AlertTriggerLogListSerializer
        return AlertTriggerLogSerializer

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        获取触发日志统计摘要

        支持的查询参数:
        - days: 统计最近N天(默认7天)

        响应:
        {
            "total_triggers": 1200,
            "total_pushes": 450,
            "push_rate": 37.5,
            "triggers_by_rule": {
                "1": 300,
                "2": 250,
                ...
            },
            "triggers_by_day": [
                {"date": "2025-12-08", "count": 180},
                ...
            ]
        }
        """
        days = int(request.query_params.get('days', 7))
        date_from = timezone.now() - timedelta(days=days)

        queryset = AlertTriggerLog.objects.filter(triggered_at__gte=date_from)

        total_triggers = queryset.count()
        total_pushes = queryset.filter(pushed=True).count()
        push_rate = (total_pushes / total_triggers * 100) if total_triggers > 0 else 0

        # 按规则统计
        triggers_by_rule = dict(
            queryset.values('rule_id').annotate(
                count=Count('id')
            ).values_list('rule_id', 'count')
        )

        # 按日期统计
        triggers_by_day = []
        for i in range(days):
            date = (timezone.now() - timedelta(days=i)).date()
            count = queryset.filter(triggered_at__date=date).count()
            triggers_by_day.append({
                'date': date.strftime('%Y-%m-%d'),
                'count': count
            })

        triggers_by_day.reverse()

        return Response({
            'total_triggers': total_triggers,
            'total_pushes': total_pushes,
            'push_rate': round(push_rate, 2),
            'triggers_by_rule': triggers_by_rule,
            'triggers_by_day': triggers_by_day,
        })


class DataUpdateLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    数据更新日志查询API

    list: 获取更新日志列表
    retrieve: 获取单个日志详情
    """
    queryset = DataUpdateLog.objects.all()
    serializer_class = DataUpdateLogSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        """
        自定义查询集，支持筛选

        支持的查询参数:
        - status: 状态(success/failed/running)
        - date_from: 开始日期
        - date_to: 结束日期
        """
        queryset = DataUpdateLog.objects.all()

        # 按状态筛选
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # 按日期范围筛选
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(started_at__date__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(started_at__date__lte=date_to)

        return queryset.order_by('-started_at')


class SystemConfigViewSet(viewsets.ModelViewSet):
    """
    系统配置管理API

    list: 获取配置列表
    retrieve: 获取单个配置
    update: 更新配置值
    partial_update: 部分更新配置
    """
    queryset = SystemConfig.objects.all()
    serializer_class = SystemConfigSerializer
    permission_classes = [AllowAny]
    lookup_field = 'key'

    # 禁用删除操作
    http_method_names = ['get', 'put', 'patch', 'post']

    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """
        批量更新配置

        请求体:
        {
            "configs": [
                {"key": "duplicate_suppress_minutes", "value": "120"},
                {"key": "max_monitored_contracts", "value": "1000"}
            ]
        }
        """
        configs = request.data.get('configs', [])

        if not configs:
            return Response({
                'error': 'configs不能为空'
            }, status=status.HTTP_400_BAD_REQUEST)

        updated = 0
        for config in configs:
            key = config.get('key')
            value = config.get('value')

            if not key or not value:
                continue

            try:
                obj = SystemConfig.objects.get(key=key)
                obj.value = value
                obj.save()
                updated += 1
            except SystemConfig.DoesNotExist:
                pass

        return Response({
            'updated': updated,
            'message': f'成功更新{updated}个配置'
        }, status=status.HTTP_200_OK)


# ==================== Dashboard Views ====================

def price_monitor_dashboard(request):
    """
    价格监控系统Dashboard主页

    展示监控概览、实时统计、触发日志等
    Feature: 001-price-alert-monitor
    Task: T058-T064
    """
    return render(request, 'grid_trading/price_monitor_dashboard.html')
