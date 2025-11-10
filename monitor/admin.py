from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Exchange, Announcement, Listing, NotificationRecord


@admin.register(Exchange)
class ExchangeAdmin(admin.ModelAdmin):
    """交易所管理"""
    list_display = ['name', 'code', 'enabled_status', 'announcement_count', 'announcement_url_link', 'created_at']
    list_filter = ['enabled', 'created_at']
    search_fields = ['name', 'code']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'code', 'announcement_url', 'enabled')
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def enabled_status(self, obj):
        """启用状态"""
        if obj.enabled:
            return format_html('<span style="color: green;">✓ 已启用</span>')
        return format_html('<span style="color: red;">✗ 已禁用</span>')
    enabled_status.short_description = '状态'

    def announcement_count(self, obj):
        """公告数量"""
        count = obj.announcements.count()
        if count > 0:
            url = reverse('admin:monitor_announcement_changelist') + f'?exchange__id__exact={obj.id}'
            return format_html('<a href="{}">{} 条</a>', url, count)
        return '0 条'
    announcement_count.short_description = '公告数量'

    def announcement_url_link(self, obj):
        """公告链接"""
        if obj.announcement_url:
            return format_html('<a href="{}" target="_blank">查看 ↗</a>', obj.announcement_url)
        return '-'
    announcement_url_link.short_description = '公告页面'


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    """公告管理"""
    list_display = ['title_short', 'exchange', 'category', 'announced_at', 'processed_status', 'listing_count', 'view_link']
    list_filter = ['exchange', 'category', 'processed', 'announced_at']
    search_fields = ['title', 'description', 'news_id']
    readonly_fields = ['news_id', 'created_at']
    date_hierarchy = 'announced_at'

    fieldsets = (
        ('基本信息', {
            'fields': ('news_id', 'title', 'exchange', 'category')
        }),
        ('内容信息', {
            'fields': ('description', 'url')
        }),
        ('时间与状态', {
            'fields': ('announced_at', 'processed', 'created_at')
        }),
    )

    actions = ['mark_as_processed', 'mark_as_unprocessed']

    def title_short(self, obj):
        """标题缩略"""
        if len(obj.title) > 60:
            return obj.title[:60] + '...'
        return obj.title
    title_short.short_description = '标题'

    def processed_status(self, obj):
        """处理状态"""
        if obj.processed:
            return format_html('<span style="color: green;">✓ 已处理</span>')
        return format_html('<span style="color: orange;">⏳ 待处理</span>')
    processed_status.short_description = '处理状态'

    def listing_count(self, obj):
        """识别的新币数量"""
        count = obj.listings.count()
        if count > 0:
            url = reverse('admin:monitor_listing_changelist') + f'?announcement__id__exact={obj.id}'
            return format_html('<a href="{}">{} 个</a>', url, count)
        return '0 个'
    listing_count.short_description = '识别新币'

    def view_link(self, obj):
        """查看链接"""
        return format_html('<a href="{}" target="_blank">查看 ↗</a>', obj.url)
    view_link.short_description = '原文链接'

    def mark_as_processed(self, request, queryset):
        """标记为已处理"""
        updated = queryset.update(processed=True)
        self.message_user(request, f'成功标记 {updated} 条公告为已处理')
    mark_as_processed.short_description = '标记为已处理'

    def mark_as_unprocessed(self, request, queryset):
        """标记为未处理"""
        updated = queryset.update(processed=False)
        self.message_user(request, f'成功标记 {updated} 条公告为未处理')
    mark_as_unprocessed.short_description = '标记为未处理'


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    """新币上线管理"""
    list_display = ['coin_symbol', 'coin_name', 'listing_type_display', 'exchange_name', 'confidence_display', 'status_display', 'identified_at', 'notification_count']
    list_filter = ['listing_type', 'status', 'announcement__exchange', 'identified_at']
    search_fields = ['coin_symbol', 'coin_name']
    readonly_fields = ['identified_at', 'created_at']
    date_hierarchy = 'identified_at'

    fieldsets = (
        ('币种信息', {
            'fields': ('coin_symbol', 'coin_name', 'listing_type')
        }),
        ('关联信息', {
            'fields': ('announcement',)
        }),
        ('识别信息', {
            'fields': ('confidence', 'status', 'identified_at')
        }),
        ('时间信息', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    actions = ['confirm_listing', 'mark_as_pending']

    def listing_type_display(self, obj):
        """上线类型"""
        return obj.get_listing_type_display()
    listing_type_display.short_description = '类型'

    def exchange_name(self, obj):
        """交易所"""
        return obj.announcement.exchange.name if obj.announcement else '-'
    exchange_name.short_description = '交易所'

    def confidence_display(self, obj):
        """置信度显示"""
        confidence_pct = obj.confidence * 100
        if confidence_pct >= 90:
            color = 'green'
        elif confidence_pct >= 70:
            color = 'orange'
        else:
            color = 'red'
        return format_html('<span style="color: {};">{:.0f}%</span>', color, confidence_pct)
    confidence_display.short_description = '置信度'

    def status_display(self, obj):
        """状态显示"""
        status_colors = {
            Listing.CONFIRMED: 'green',
            Listing.PENDING_REVIEW: 'orange',
            Listing.REJECTED: 'red',
        }
        status_icons = {
            Listing.CONFIRMED: '✓',
            Listing.PENDING_REVIEW: '?',
            Listing.REJECTED: '✗',
        }
        color = status_colors.get(obj.status, 'gray')
        icon = status_icons.get(obj.status, '-')
        return format_html(
            '<span style="color: {};">{} {}</span>',
            color, icon, obj.get_status_display()
        )
    status_display.short_description = '状态'

    def notification_count(self, obj):
        """通知次数"""
        count = obj.notification_records.count()
        if count > 0:
            url = reverse('admin:monitor_notificationrecord_changelist') + f'?listing__id__exact={obj.id}'
            return format_html('<a href="{}">{} 次</a>', url, count)
        return '0 次'
    notification_count.short_description = '通知次数'

    def confirm_listing(self, request, queryset):
        """确认新币上线"""
        updated = queryset.update(status=Listing.CONFIRMED)
        self.message_user(request, f'成功确认 {updated} 个新币上线')
    confirm_listing.short_description = '确认上线'

    def mark_as_pending(self, request, queryset):
        """标记为待审核"""
        updated = queryset.update(status=Listing.PENDING_REVIEW)
        self.message_user(request, f'成功标记 {updated} 个为待审核')
    mark_as_pending.short_description = '标记为待审核'


@admin.register(NotificationRecord)
class NotificationRecordAdmin(admin.ModelAdmin):
    """通知记录管理"""
    list_display = ['listing_info', 'channel', 'status_display', 'retry_count', 'sent_at', 'created_at']
    list_filter = ['channel', 'status', 'sent_at', 'created_at']
    search_fields = ['listing__coin_symbol', 'error_message']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('关联信息', {
            'fields': ('listing',)
        }),
        ('通知信息', {
            'fields': ('channel', 'status', 'retry_count')
        }),
        ('结果信息', {
            'fields': ('sent_at', 'error_message')
        }),
        ('时间信息', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def listing_info(self, obj):
        """新币信息"""
        if obj.listing:
            url = reverse('admin:monitor_listing_change', args=[obj.listing.id])
            return format_html(
                '<a href="{}">{} ({})</a>',
                url,
                obj.listing.coin_symbol,
                obj.listing.get_listing_type_display()
            )
        return '-'
    listing_info.short_description = '新币'

    def status_display(self, obj):
        """状态显示"""
        status_colors = {
            NotificationRecord.SUCCESS: 'green',
            NotificationRecord.FAILED: 'red',
            NotificationRecord.PENDING: 'orange',
        }
        color = status_colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {};">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = '状态'
