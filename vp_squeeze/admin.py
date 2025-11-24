"""VP-Squeeze Admin配置"""
from django.contrib import admin
from .models import VPSqueezeResult


@admin.register(VPSqueezeResult)
class VPSqueezeResultAdmin(admin.ModelAdmin):
    list_display = [
        'symbol', 'interval', 'squeeze_active', 'reliability',
        'val', 'vah', 'vpoc', 'analyzed_at'
    ]
    list_filter = ['symbol', 'interval', 'squeeze_active', 'reliability']
    search_fields = ['symbol']
    date_hierarchy = 'analyzed_at'
    readonly_fields = ['created_at', 'raw_result']

    fieldsets = (
        ('基本信息', {
            'fields': ('symbol', 'interval', 'analyzed_at', 'klines_count')
        }),
        ('Squeeze状态', {
            'fields': ('squeeze_active', 'squeeze_consecutive_bars', 'reliability')
        }),
        ('关键价位', {
            'fields': ('val', 'vah', 'vpoc')
        }),
        ('节点数据', {
            'fields': ('hvn_data', 'lvn_data'),
            'classes': ('collapse',)
        }),
        ('技术指标', {
            'fields': ('bb_upper', 'bb_lower', 'kc_upper', 'kc_lower'),
            'classes': ('collapse',)
        }),
        ('统计信息', {
            'fields': ('price_min', 'price_max', 'total_volume'),
            'classes': ('collapse',)
        }),
        ('系统信息', {
            'fields': ('created_at', 'raw_result'),
            'classes': ('collapse',)
        }),
    )
