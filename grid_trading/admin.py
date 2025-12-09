"""
Django Admin管理界面配置
Admin Configuration for Grid Trading System
"""
from django.contrib import admin
from django.utils.html import format_html
from django.shortcuts import render, redirect
from django.urls import path
from django.contrib import messages
from django.utils import timezone

from .models import GridConfig, GridLevel, OrderIntent, TradeLog, GridStatistics
from .django_models import (
    MonitoredContract, PriceAlertRule, AlertTriggerLog,
    DataUpdateLog, SystemConfig, ScriptLock
)


@admin.register(GridConfig)
class GridConfigAdmin(admin.ModelAdmin):
    """网格配置管理"""
    list_display = [
        'name', 'exchange', 'symbol', 'grid_mode_badge', 'price_range',
        'grid_levels', 'is_active_badge', 'created_at'
    ]
    list_filter = ['exchange', 'grid_mode', 'is_active', 'created_at']
    search_fields = ['name', 'symbol']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at', 'grid_spacing', 'grid_spacing_pct']

    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'exchange', 'symbol', 'grid_mode', 'is_active')
        }),
        ('网格参数', {
            'fields': (
                'upper_price', 'lower_price', 'grid_levels',
                'grid_spacing', 'grid_spacing_pct'
            )
        }),
        ('交易配置', {
            'fields': ('trade_amount', 'max_position_size')
        }),
        ('风控配置', {
            'fields': ('stop_loss_buffer_pct',)
        }),
        ('系统配置', {
            'fields': ('refresh_interval_ms', 'price_tick', 'qty_step')
        }),
        ('时间戳', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def grid_mode_badge(self, obj):
        """网格模式徽章"""
        colors = {
            'SHORT': '#dc3545',
            'NEUTRAL': '#17a2b8',
            'LONG': '#28a745',
        }
        color = colors.get(obj.grid_mode, '#6c757d')
        return format_html(
            '<span style="background:{}; color:white; padding:3px 8px; border-radius:3px;">{}</span>',
            color,
            obj.get_grid_mode_display()
        )
    grid_mode_badge.short_description = '网格模式'

    def price_range(self, obj):
        """价格区间"""
        return f"{obj.lower_price} ~ {obj.upper_price}"
    price_range.short_description = '价格区间'

    def is_active_badge(self, obj):
        """激活状态徽章"""
        if obj.is_active:
            return format_html('<span style="color:#28a745;">● 运行中</span>')
        else:
            return format_html('<span style="color:#6c757d;">● 已停止</span>')
    is_active_badge.short_description = '状态'


@admin.register(GridLevel)
class GridLevelAdmin(admin.ModelAdmin):
    """网格层级管理"""
    list_display = [
        'id', 'config', 'level_index', 'price', 'side_badge',
        'status_badge', 'is_blocked', 'updated_at'
    ]
    list_filter = ['config', 'status', 'side']
    search_fields = ['config__name']
    ordering = ['config', 'level_index']
    readonly_fields = ['created_at', 'updated_at']

    def side_badge(self, obj):
        """方向徽章"""
        color = '#28a745' if obj.side == 'BUY' else '#dc3545'
        return format_html(
            '<span style="background:{}; color:white; padding:3px 8px; border-radius:3px;">{}</span>',
            color,
            obj.get_side_display()
        )
    side_badge.short_description = '方向'

    def status_badge(self, obj):
        """状态徽章"""
        colors = {
            'idle': '#6c757d',
            'entry_working': '#ffc107',
            'position_open': '#007bff',
            'exit_working': '#17a2b8',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{}; color:white; padding:3px 8px; border-radius:3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = '状态'


@admin.register(OrderIntent)
class OrderIntentAdmin(admin.ModelAdmin):
    """订单意图管理"""
    list_display = [
        'id', 'config', 'client_order_id', 'level_index',
        'intent_badge', 'side_badge', 'price', 'amount',
        'status_badge', 'created_at'
    ]
    list_filter = ['config', 'intent', 'side', 'status']
    search_fields = ['client_order_id', 'order_id']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'resolved_at']

    def intent_badge(self, obj):
        """意图徽章"""
        color = '#007bff' if obj.intent == 'ENTRY' else '#17a2b8'
        return format_html(
            '<span style="background:{}; color:white; padding:3px 8px; border-radius:3px;">{}</span>',
            color,
            obj.get_intent_display()
        )
    intent_badge.short_description = '意图'

    def side_badge(self, obj):
        """方向徽章"""
        color = '#28a745' if obj.side == 'BUY' else '#dc3545'
        return format_html(
            '<span style="background:{}; color:white; padding:3px 8px; border-radius:3px;">{}</span>',
            color,
            obj.get_side_display()
        )
    side_badge.short_description = '方向'

    def status_badge(self, obj):
        """状态徽章"""
        colors = {
            'NEW': '#ffc107',
            'PARTIALLY_FILLED': '#17a2b8',
            'FILLED': '#28a745',
            'CANCELED': '#6c757d',
            'REJECTED': '#dc3545',
            'EXPIRED': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{}; color:white; padding:3px 8px; border-radius:3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = '状态'


@admin.register(TradeLog)
class TradeLogAdmin(admin.ModelAdmin):
    """交易日志管理"""
    list_display = [
        'id', 'config', 'log_type_badge', 'detail_short',
        'level_index', 'order_id', 'created_at'
    ]
    list_filter = ['config', 'log_type', 'created_at']
    search_fields = ['detail', 'order_id']
    ordering = ['-timestamp']
    readonly_fields = ['created_at']

    def log_type_badge(self, obj):
        """日志类型徽章"""
        colors = {
            'INIT': '#007bff',
            'ORDER_CREATE': '#17a2b8',
            'ORDER_FILL': '#28a745',
            'ORDER_CANCEL': '#ffc107',
            'STOP_LOSS': '#dc3545',
            'ERROR': '#dc3545',
            'WARNING': '#ffc107',
            'INFO': '#6c757d',
        }
        color = colors.get(obj.log_type, '#6c757d')
        return format_html(
            '<span style="background:{}; color:white; padding:3px 8px; border-radius:3px;">{}</span>',
            color,
            obj.get_log_type_display()
        )
    log_type_badge.short_description = '类型'

    def detail_short(self, obj):
        """简短详情"""
        return obj.detail[:50] + '...' if len(obj.detail) > 50 else obj.detail
    detail_short.short_description = '详情'


@admin.register(GridStatistics)
class GridStatisticsAdmin(admin.ModelAdmin):
    """网格统计管理"""
    list_display = [
        'id', 'config', 'period', 'total_trades',
        'pnl_badge', 'fill_rate_badge', 'created_at'
    ]
    list_filter = ['config', 'created_at']
    search_fields = ['config__name']
    ordering = ['-period_end']
    readonly_fields = ['created_at', 'fill_rate', 'roi_pct']

    fieldsets = (
        ('基本信息', {
            'fields': ('config', 'period_start', 'period_end')
        }),
        ('交易统计', {
            'fields': (
                'total_trades', 'filled_entry_orders', 'filled_exit_orders',
                'canceled_orders', 'fill_rate'
            )
        }),
        ('盈亏统计', {
            'fields': (
                'realized_pnl', 'unrealized_pnl', 'total_pnl', 'roi_pct'
            )
        }),
        ('持仓统计', {
            'fields': (
                'max_position_size', 'avg_position_size', 'current_position_size'
            )
        }),
        ('风险统计', {
            'fields': ('stop_loss_triggered_count', 'max_drawdown')
        }),
        ('扩展统计', {
            'fields': (
                'skipped_orders_count', 'avg_fill_time_seconds',
                'grid_utilization_pct'
            ),
            'classes': ('collapse',)
        }),
        ('时间戳', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def period(self, obj):
        """统计周期"""
        return f"{obj.period_start.strftime('%m-%d %H:%M')} ~ {obj.period_end.strftime('%m-%d %H:%M')}"
    period.short_description = '统计周期'

    def pnl_badge(self, obj):
        """盈亏徽章"""
        pnl = float(obj.total_pnl)
        if pnl > 0:
            color = '#28a745'
            symbol = '+'
        elif pnl < 0:
            color = '#dc3545'
            symbol = ''
        else:
            color = '#6c757d'
            symbol = ''
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}{:.4f}</span>',
            color,
            symbol,
            pnl
        )
    pnl_badge.short_description = '总盈亏'

    def fill_rate_badge(self, obj):
        """成交率徽章"""
        rate = obj.fill_rate
        if rate >= 80:
            color = '#28a745'
        elif rate >= 60:
            color = '#ffc107'
        else:
            color = '#dc3545'
        return format_html(
            '<span style="color:{}; font-weight:bold;">{:.1f}%</span>',
            color,
            rate
        )
    fill_rate_badge.short_description = '成交率'


# ==================== 价格监控系统 Admin ====================

@admin.register(MonitoredContract)
class MonitoredContractAdmin(admin.ModelAdmin):
    """监控合约管理"""
    list_display = [
        'symbol', 'source_badge', 'status_badge',
        'last_screening_date', 'last_data_update_at', 'created_at'
    ]
    list_filter = ['source', 'status', 'created_at']
    search_fields = ['symbol']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'last_screening_date', 'last_data_update_at']

    # 自定义模板以添加批量添加按钮
    change_list_template = 'admin/grid_trading/monitoredcontract_changelist.html'

    fieldsets = (
        ('基本信息', {
            'fields': ('symbol', 'source', 'status')
        }),
        ('监控状态', {
            'fields': ('last_screening_date', 'last_data_update_at', 'created_at')
        }),
    )

    # 批量操作
    actions = ['enable_monitoring', 'disable_monitoring', 'remove_monitoring']

    # 允许在列表页直接编辑状态
    list_editable = []  # status字段是主键，不能直接编辑

    # 自定义表单
    def get_form(self, request, obj=None, **kwargs):
        """自定义表单，添加提示"""
        form = super().get_form(request, obj, **kwargs)

        # 添加symbol字段的帮助文本
        if 'symbol' in form.base_fields:
            form.base_fields['symbol'].help_text = (
                '输入合约代码，如: BTCUSDT, ETHUSDT (必须以USDT结尾)'
            )
            form.base_fields['symbol'].widget.attrs.update({
                'placeholder': 'BTCUSDT',
                'style': 'width: 200px; text-transform: uppercase;'
            })

        # source字段默认为manual
        if 'source' in form.base_fields and obj is None:
            form.base_fields['source'].initial = 'manual'
            form.base_fields['source'].help_text = (
                'manual=手动添加, auto=自动同步(自动同步的合约请勿手动修改)'
            )

        # status字段默认为enabled
        if 'status' in form.base_fields and obj is None:
            form.base_fields['status'].initial = 'enabled'

        return form

    def save_model(self, request, obj, form, change):
        """保存模型时的验证"""
        from django.contrib import messages

        # 转换为大写
        obj.symbol = obj.symbol.upper().strip()

        # 验证合约代码格式
        if not obj.symbol.endswith('USDT'):
            messages.error(request, f'合约代码 {obj.symbol} 必须以USDT结尾')
            return

        # 验证合约代码长度
        if len(obj.symbol) < 5:
            messages.error(request, f'合约代码 {obj.symbol} 长度不正确')
            return

        try:
            super().save_model(request, obj, form, change)

            if change:
                messages.success(request, f'✓ 成功更新合约 {obj.symbol}')
            else:
                messages.success(request, f'✓ 成功添加合约 {obj.symbol} 到监控列表')

        except Exception as e:
            messages.error(request, f'✗ 保存失败: {str(e)}')

    def get_urls(self):
        """添加自定义URL"""
        urls = super().get_urls()
        custom_urls = [
            path(
                'batch-add/',
                self.admin_site.admin_view(self.batch_add_view),
                name='monitored-contract-batch-add'
            ),
        ]
        return custom_urls + urls

    def batch_add_view(self, request):
        """批量添加合约的视图"""
        if request.method == 'POST':
            symbols_text = request.POST.get('symbols', '')

            if not symbols_text:
                messages.error(request, '请输入合约代码')
                return render(request, 'admin/grid_trading/batch_add_contracts.html')

            # 解析输入的合约代码(支持逗号、空格、换行分隔)
            import re
            symbols = re.split(r'[,\s\n]+', symbols_text.strip())
            symbols = [s.strip().upper() for s in symbols if s.strip()]

            # 验证和添加
            added = []
            skipped = []
            errors = []

            for symbol in symbols:
                # 验证格式
                if not symbol.endswith('USDT'):
                    errors.append(f'{symbol}: 必须以USDT结尾')
                    continue

                if len(symbol) < 5:
                    errors.append(f'{symbol}: 长度不正确')
                    continue

                # 检查是否已存在
                if MonitoredContract.objects.filter(symbol=symbol).exists():
                    skipped.append(symbol)
                    continue

                # 创建合约
                try:
                    MonitoredContract.objects.create(
                        symbol=symbol,
                        source='manual',
                        status='enabled'
                    )
                    added.append(symbol)
                except Exception as e:
                    errors.append(f'{symbol}: {str(e)}')

            # 显示结果
            if added:
                messages.success(
                    request,
                    f'✓ 成功添加 {len(added)} 个合约: {", ".join(added[:10])}'
                    + (f' 等...' if len(added) > 10 else '')
                )

            if skipped:
                messages.warning(
                    request,
                    f'⚠ 跳过 {len(skipped)} 个已存在的合约: {", ".join(skipped[:10])}'
                    + (f' 等...' if len(skipped) > 10 else '')
                )

            if errors:
                messages.error(
                    request,
                    f'✗ {len(errors)} 个合约添加失败:\n' + '\n'.join(errors[:10])
                    + ('\n...' if len(errors) > 10 else '')
                )

            # 重定向回列表页
            return redirect('..')

        # GET请求：显示表单
        return render(request, 'admin/grid_trading/batch_add_contracts.html', {
            'title': '批量添加监控合约',
            'site_title': admin.site.site_title,
            'site_header': admin.site.site_header,
        })

    def source_badge(self, obj):
        """来源徽章"""
        colors = {
            'manual': '#007bff',
            'auto': '#28a745',
        }
        labels = {
            'manual': '手动添加',
            'auto': '自动同步',
        }
        color = colors.get(obj.source, '#6c757d')
        label = labels.get(obj.source, obj.source)
        return format_html(
            '<span style="background:{}; color:white; padding:3px 8px; border-radius:3px;">{}</span>',
            color,
            label
        )
    source_badge.short_description = '来源'

    def status_badge(self, obj):
        """状态徽章"""
        colors = {
            'enabled': '#28a745',
            'disabled': '#ffc107',
            'expired': '#6c757d',
        }
        labels = {
            'enabled': '● 启用',
            'disabled': '● 暂停',
            'expired': '● 已过期',
        }
        color = colors.get(obj.status, '#6c757d')
        label = labels.get(obj.status, obj.status)
        return format_html('<span style="color:{}; font-weight:bold;">{}</span>', color, label)
    status_badge.short_description = '监控状态'

    def enable_monitoring(self, request, queryset):
        """批量启用监控"""
        updated = queryset.update(status='enabled')
        self.message_user(request, f'成功启用 {updated} 个合约的监控')
    enable_monitoring.short_description = '启用监控'

    def disable_monitoring(self, request, queryset):
        """批量暂停监控"""
        updated = queryset.update(status='disabled')
        self.message_user(request, f'成功暂停 {updated} 个合约的监控')
    disable_monitoring.short_description = '暂停监控'

    def remove_monitoring(self, request, queryset):
        """批量移除监控"""
        updated = queryset.update(status='expired')
        self.message_user(request, f'成功移除 {updated} 个合约的监控')
    remove_monitoring.short_description = '移除监控'


@admin.register(PriceAlertRule)
class PriceAlertRuleAdmin(admin.ModelAdmin):
    """价格触发规则管理"""
    list_display = [
        'rule_id', 'name', 'enabled_badge', 'description_short', 'updated_at'
    ]
    list_filter = ['enabled']
    search_fields = ['name', 'description']
    ordering = ['rule_id']
    readonly_fields = ['updated_at']

    fieldsets = (
        ('基本信息', {
            'fields': ('rule_id', 'name', 'enabled', 'description')
        }),
        ('规则参数', {
            'fields': ('parameters',),
            'description': 'JSON格式配置，例如: {"ma_threshold": 0.5, "percentile": 90}'
        }),
        ('时间戳', {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        }),
    )

    actions = ['enable_rules', 'disable_rules']

    def enabled_badge(self, obj):
        """启用状态徽章"""
        if obj.enabled:
            return format_html('<span style="color:#28a745; font-weight:bold;">✓ 启用</span>')
        else:
            return format_html('<span style="color:#dc3545; font-weight:bold;">✗ 禁用</span>')
    enabled_badge.short_description = '状态'

    def description_short(self, obj):
        """简短描述"""
        return obj.description[:60] + '...' if len(obj.description) > 60 else obj.description
    description_short.short_description = '描述'

    def enable_rules(self, request, queryset):
        """批量启用规则"""
        updated = queryset.update(enabled=True)
        self.message_user(request, f'成功启用 {updated} 条规则')
    enable_rules.short_description = '启用规则'

    def disable_rules(self, request, queryset):
        """批量禁用规则"""
        updated = queryset.update(enabled=False)
        self.message_user(request, f'成功禁用 {updated} 条规则')
    disable_rules.short_description = '禁用规则'


@admin.register(AlertTriggerLog)
class AlertTriggerLogAdmin(admin.ModelAdmin):
    """触发日志管理"""
    list_display = [
        'id', 'symbol', 'rule_name_display', 'current_price_display',
        'pushed_badge', 'triggered_at', 'pushed_at'
    ]
    list_filter = ['rule_id', 'pushed', 'triggered_at']
    search_fields = ['symbol']
    ordering = ['-triggered_at']
    readonly_fields = ['triggered_at', 'pushed_at', 'extra_info']

    fieldsets = (
        ('触发信息', {
            'fields': ('symbol', 'rule_id', 'current_price', 'triggered_at')
        }),
        ('推送状态', {
            'fields': ('pushed', 'pushed_at', 'skip_reason')
        }),
        ('额外信息', {
            'fields': ('extra_info',),
            'classes': ('collapse',)
        }),
    )

    def rule_name_display(self, obj):
        """规则名称"""
        rule_names = {
            1: "7天价格新高",
            2: "7天价格新低",
            3: "价格触及MA20",
            4: "价格触及MA99",
            5: "价格达到分布区间极值"
        }
        return rule_names.get(obj.rule_id, f"规则{obj.rule_id}")
    rule_name_display.short_description = '触发规则'

    def current_price_display(self, obj):
        """当前价格显示"""
        return f"${float(obj.current_price):,.2f}"
    current_price_display.short_description = '触发价格'

    def pushed_badge(self, obj):
        """推送状态徽章"""
        if obj.pushed:
            return format_html('<span style="color:#28a745; font-weight:bold;">✓ 已推送</span>')
        else:
            reason = obj.skip_reason[:20] + '...' if len(obj.skip_reason) > 20 else obj.skip_reason
            return format_html(
                '<span style="color:#ffc107; font-weight:bold;">⊘ {}</span>',
                reason if reason else '跳过'
            )
    pushed_badge.short_description = '推送状态'


@admin.register(DataUpdateLog)
class DataUpdateLogAdmin(admin.ModelAdmin):
    """数据更新日志管理"""
    list_display = [
        'id', 'started_at', 'status_badge', 'execution_seconds',
        'contracts_count', 'klines_count', 'error_short'
    ]
    list_filter = ['status', 'started_at']
    ordering = ['-started_at']
    readonly_fields = ['started_at', 'ended_at', 'execution_seconds']

    fieldsets = (
        ('执行信息', {
            'fields': ('started_at', 'ended_at', 'execution_seconds', 'status')
        }),
        ('统计信息', {
            'fields': ('contracts_count', 'klines_count')
        }),
        ('错误信息', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
    )

    def status_badge(self, obj):
        """状态徽章"""
        colors = {
            'success': '#28a745',
            'failed': '#dc3545',
            'running': '#ffc107',
        }
        labels = {
            'success': '✓ 成功',
            'failed': '✗ 失败',
            'running': '⟳ 运行中',
        }
        color = colors.get(obj.status, '#6c757d')
        label = labels.get(obj.status, obj.status)
        return format_html('<span style="color:{}; font-weight:bold;">{}</span>', color, label)
    status_badge.short_description = '状态'

    def error_short(self, obj):
        """简短错误信息"""
        if obj.error_message:
            return obj.error_message[:50] + '...' if len(obj.error_message) > 50 else obj.error_message
        return '-'
    error_short.short_description = '错误信息'


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    """系统配置管理"""
    list_display = ['key', 'value_short', 'description_short', 'updated_at']
    search_fields = ['key', 'description']
    ordering = ['key']
    readonly_fields = ['updated_at']

    fieldsets = (
        ('配置信息', {
            'fields': ('key', 'value', 'description')
        }),
        ('时间戳', {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        }),
    )

    def value_short(self, obj):
        """简短配置值"""
        return obj.value[:50] + '...' if len(obj.value) > 50 else obj.value
    value_short.short_description = '配置值'

    def description_short(self, obj):
        """简短描述"""
        return obj.description[:60] + '...' if len(obj.description) > 60 else obj.description
    description_short.short_description = '描述'


@admin.register(ScriptLock)
class ScriptLockAdmin(admin.ModelAdmin):
    """脚本锁管理"""
    list_display = ['lock_name', 'acquired_at', 'expires_at', 'is_locked_badge']
    ordering = ['-acquired_at']
    readonly_fields = ['acquired_at']

    fieldsets = (
        ('锁信息', {
            'fields': ('lock_name', 'acquired_at', 'expires_at')
        }),
    )

    actions = ['release_locks']

    def is_locked_badge(self, obj):
        """锁状态徽章"""
        from django.utils import timezone
        if obj.expires_at > timezone.now():
            return format_html('<span style="color:#dc3545; font-weight:bold;">● 已锁定</span>')
        else:
            return format_html('<span style="color:#6c757d; font-weight:bold;">● 已过期</span>')
    is_locked_badge.short_description = '锁状态'

    def release_locks(self, request, queryset):
        """批量释放锁"""
        deleted, _ = queryset.delete()
        self.message_user(request, f'成功释放 {deleted} 个锁')
    release_locks.short_description = '释放锁'
