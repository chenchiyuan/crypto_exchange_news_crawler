"""
Django Admin管理界面配置
Admin Configuration for Grid Trading System
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import GridConfig, GridLevel, OrderIntent, TradeLog, GridStatistics


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
