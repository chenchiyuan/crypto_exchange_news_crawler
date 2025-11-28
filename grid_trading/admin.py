"""
Django Admin管理界面配置
Admin Configuration
"""
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum
from decimal import Decimal

from .models import GridZone, StrategyConfig, GridStrategy, GridOrder


@admin.register(GridZone)
class GridZoneAdmin(admin.ModelAdmin):
    """网格区间管理"""
    list_display = [
        'symbol', 'zone_type_badge', 'price_range', 'confidence_badge',
        'is_active_badge', 'expires_at', 'created_at'
    ]
    list_filter = ['symbol', 'zone_type', 'is_active', 'created_at']
    search_fields = ['symbol']
    ordering = ['-created_at']
    readonly_fields = ['created_at']

    def zone_type_badge(self, obj):
        """区间类型徽章"""
        color = '#28a745' if obj.zone_type == 'support' else '#dc3545'
        return format_html(
            '<span style="background:{}; color:white; padding:3px 8px; border-radius:3px;">{}</span>',
            color,
            obj.get_zone_type_display()
        )
    zone_type_badge.short_description = '类型'

    def price_range(self, obj):
        """价格区间"""
        return f"${obj.price_low:.2f} - ${obj.price_high:.2f}"
    price_range.short_description = '价格区间'

    def confidence_badge(self, obj):
        """置信度徽章"""
        if obj.confidence >= 80:
            color = '#28a745'
        elif obj.confidence >= 60:
            color = '#ffc107'
        else:
            color = '#dc3545'
        return format_html(
            '<span style="background:{}; color:white; padding:3px 8px; border-radius:3px;">{}</span>',
            color,
            f"{obj.confidence}分"
        )
    confidence_badge.short_description = '置信度'

    def is_active_badge(self, obj):
        """激活状态徽章"""
        if obj.is_active:
            return format_html(
                '<span style="color:#28a745;">●</span> 激活'
            )
        else:
            return format_html(
                '<span style="color:#6c757d;">●</span> 失效'
            )
    is_active_badge.short_description = '状态'


@admin.register(StrategyConfig)
class StrategyConfigAdmin(admin.ModelAdmin):
    """策略配置管理"""
    list_display = [
        'symbol', 'config_name', 'atr_multiplier', 'grid_levels',
        'order_size_usdt', 'stop_loss_pct', 'is_active', 'created_at'
    ]
    list_filter = ['symbol', 'is_active', 'created_at']
    search_fields = ['symbol', 'config_name']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(GridStrategy)
class GridStrategyAdmin(admin.ModelAdmin):
    """网格策略管理"""
    list_display = [
        'id', 'symbol', 'strategy_type_badge', 'status_badge',
        'entry_price', 'current_pnl_badge', 'position_info',
        'started_at', 'stopped_at'
    ]
    list_filter = ['symbol', 'strategy_type', 'status', 'started_at']
    search_fields = ['symbol']
    ordering = ['-created_at']
    readonly_fields = [
        'created_at', 'updated_at', 'started_at', 'stopped_at',
        'order_statistics', 'pnl_chart'
    ]

    fieldsets = (
        ('基本信息', {
            'fields': ('symbol', 'strategy_type', 'status', 'config')
        }),
        ('网格参数', {
            'fields': ('grid_step_pct', 'grid_levels', 'order_size', 'stop_loss_pct')
        }),
        ('运行状态', {
            'fields': ('entry_price', 'current_pnl', 'started_at', 'stopped_at')
        }),
        ('统计信息', {
            'fields': ('order_statistics', 'pnl_chart'),
            'classes': ('collapse',)
        }),
        ('时间戳', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def strategy_type_badge(self, obj):
        """策略类型徽章"""
        color = '#007bff' if obj.strategy_type == 'long' else '#fd7e14'
        return format_html(
            '<span style="background:{}; color:white; padding:3px 8px; border-radius:3px;">{}</span>',
            color,
            obj.get_strategy_type_display()
        )
    strategy_type_badge.short_description = '策略类型'

    def status_badge(self, obj):
        """状态徽章"""
        status_colors = {
            'idle': '#6c757d',
            'active': '#28a745',
            'stopped': '#dc3545',
            'error': '#ffc107',
        }
        color = status_colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{}; color:white; padding:3px 8px; border-radius:3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = '状态'

    def current_pnl_badge(self, obj):
        """当前盈亏徽章"""
        pnl = float(obj.current_pnl)
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
            '<span style="color:{}; font-weight:bold;">{}{:.2f} USDT</span>',
            color,
            symbol,
            pnl
        )
    current_pnl_badge.short_description = '当前盈亏'

    def position_info(self, obj):
        """仓位信息"""
        position_value = obj.calculate_total_position_value()
        return f"${position_value:.2f}"
    position_info.short_description = '仓位价值'

    def order_statistics(self, obj):
        """订单统计"""
        orders = obj.gridorder_set.aggregate(
            total=Count('id'),
            pending=Count('id', filter=admin.models.Q(status='pending')),
            filled=Count('id', filter=admin.models.Q(status='filled')),
            cancelled=Count('id', filter=admin.models.Q(status='cancelled')),
        )
        return format_html(
            '<div style="line-height:1.8;">'
            '<strong>总订单:</strong> {}<br>'
            '<strong>待成交:</strong> <span style="color:#ffc107;">{}</span><br>'
            '<strong>已成交:</strong> <span style="color:#28a745;">{}</span><br>'
            '<strong>已撤销:</strong> <span style="color:#6c757d;">{}</span><br>'
            '<strong>成交率:</strong> {:.1f}%'
            '</div>',
            orders['total'],
            orders['pending'],
            orders['filled'],
            orders['cancelled'],
            orders['filled'] / orders['total'] * 100 if orders['total'] > 0 else 0
        )
    order_statistics.short_description = '订单统计'

    def pnl_chart(self, obj):
        """盈亏图表（简化版）"""
        pnl = float(obj.current_pnl)
        if obj.entry_price and obj.entry_price > 0:
            position_value = obj.calculate_total_position_value()
            pnl_pct = pnl / position_value * 100 if position_value > 0 else 0
        else:
            pnl_pct = 0

        return format_html(
            '<div style="line-height:1.8;">'
            '<strong>盈亏金额:</strong> <span style="color:{}; font-weight:bold;">{}{:.2f} USDT</span><br>'
            '<strong>盈亏比例:</strong> <span style="color:{}; font-weight:bold;">{}{:.2f}%</span>'
            '</div>',
            '#28a745' if pnl > 0 else '#dc3545',
            '+' if pnl > 0 else '',
            pnl,
            '#28a745' if pnl_pct > 0 else '#dc3545',
            '+' if pnl_pct > 0 else '',
            pnl_pct
        )
    pnl_chart.short_description = '盈亏分析'


@admin.register(GridOrder)
class GridOrderAdmin(admin.ModelAdmin):
    """网格订单管理"""
    list_display = [
        'id', 'strategy_link', 'order_type_badge', 'price', 'quantity',
        'status_badge', 'simulated_price', 'simulated_fee', 'filled_at'
    ]
    list_filter = ['strategy__symbol', 'order_type', 'status', 'created_at']
    search_fields = ['strategy__symbol']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at', 'filled_at']

    def strategy_link(self, obj):
        """策略链接"""
        url = f'/admin/grid_trading/gridstrategy/{obj.strategy.id}/change/'
        return format_html(
            '<a href="{}">{} #{}</a>',
            url,
            obj.strategy.symbol,
            obj.strategy.id
        )
    strategy_link.short_description = '所属策略'

    def order_type_badge(self, obj):
        """订单类型徽章"""
        color = '#28a745' if obj.order_type == 'buy' else '#dc3545'
        return format_html(
            '<span style="background:{}; color:white; padding:3px 8px; border-radius:3px;">{}</span>',
            color,
            obj.get_order_type_display()
        )
    order_type_badge.short_description = '类型'

    def status_badge(self, obj):
        """状态徽章"""
        status_colors = {
            'pending': '#ffc107',
            'filled': '#28a745',
            'cancelled': '#6c757d',
        }
        color = status_colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{}; color:white; padding:3px 8px; border-radius:3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = '状态'
