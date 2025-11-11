from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Exchange, Announcement, Listing, NotificationRecord, FuturesContract, FuturesListingNotification, FuturesMarketIndicators


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
        return format_html('<span style="color: {};">{}%</span>', color, int(confidence_pct))
    confidence_display.short_description = '置信度'

    def status_display(self, obj):
        """状态显示"""
        status_colors = {
            Listing.CONFIRMED: 'green',
            Listing.PENDING_REVIEW: 'orange',
            Listing.IGNORED: 'gray',
        }
        status_icons = {
            Listing.CONFIRMED: '✓',
            Listing.PENDING_REVIEW: '?',
            Listing.IGNORED: '✗',
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


class FuturesMarketIndicatorsInline(admin.StackedInline):
    """合约市场指标内联展示"""
    model = FuturesMarketIndicators
    can_delete = False
    extra = 0
    readonly_fields = ['last_updated']

    fieldsets = (
        ('市场指标', {
            'fields': ('open_interest', 'volume_24h')
        }),
        ('资金费率', {
            'fields': ('funding_rate', 'funding_rate_annual', 'next_funding_time', 'funding_interval_hours')
        }),
        ('费率限制', {
            'fields': ('funding_rate_cap', 'funding_rate_floor'),
            'classes': ('collapse',)
        }),
        ('元数据', {
            'fields': ('last_updated',),
            'classes': ('collapse',)
        }),
    )


@admin.register(FuturesContract)
class FuturesContractAdmin(admin.ModelAdmin):
    """合约管理"""
    list_display = [
        'exchange_name',
        'symbol',
        'current_price_display',
        'open_interest_display',
        'volume_24h_display',
        'funding_rate_display',
        'annual_rate_display',
        'status_display',
        'last_updated'
    ]
    list_filter = ['exchange', 'status', 'contract_type', 'first_seen']
    search_fields = ['symbol']
    readonly_fields = ['first_seen', 'last_updated']
    date_hierarchy = 'first_seen'
    inlines = [FuturesMarketIndicatorsInline]

    fieldsets = (
        ('基本信息', {
            'fields': ('exchange', 'symbol', 'contract_type', 'status')
        }),
        ('价格信息', {
            'fields': ('current_price',)
        }),
        ('时间信息', {
            'fields': ('first_seen', 'last_updated'),
            'classes': ('collapse',)
        }),
    )

    def exchange_name(self, obj):
        """交易所名称"""
        if obj.exchange:
            # 不同交易所用不同颜色
            colors = {
                'binance': '#F0B90B',  # 币安黄
                'hyperliquid': '#00D4AA',  # Hyperliquid青
                'bybit': '#F7A600',  # Bybit橙
            }
            color = colors.get(obj.exchange.code.lower(), 'black')
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span>',
                color, obj.exchange.name
            )
        return '-'
    exchange_name.short_description = '交易所'
    exchange_name.admin_order_field = 'exchange__name'

    def current_price_display(self, obj):
        """当前价格显示"""
        return format_html(
            '<span style="font-family: monospace; color: #2196F3;">${}</span>',
            obj.current_price
        )
    current_price_display.short_description = '当前价格'
    current_price_display.admin_order_field = 'current_price'

    def status_display(self, obj):
        """状态显示"""
        if obj.status == FuturesContract.ACTIVE:
            return format_html('<span style="color: green;">✓ 活跃</span>')
        return format_html('<span style="color: red;">✗ 已下线</span>')
    status_display.short_description = '状态'
    status_display.admin_order_field = 'status'

    def open_interest_display(self, obj):
        """持仓量显示"""
        try:
            indicators = obj.market_indicators
            if indicators and indicators.open_interest:
                # 格式化为千分位，保留2位小数
                value = f"{indicators.open_interest:,.2f}"
                return format_html('<span style="font-family: monospace;">{}</span>', value)
        except FuturesMarketIndicators.DoesNotExist:
            pass
        return '-'
    open_interest_display.short_description = '持仓量'

    def volume_24h_display(self, obj):
        """24小时交易量显示"""
        try:
            indicators = obj.market_indicators
            if indicators and indicators.volume_24h:
                # 格式化为千分位，保留2位小数
                value = f"{indicators.volume_24h:,.2f}"
                return format_html('<span style="font-family: monospace; color: #2196F3;">{}</span>', value)
        except FuturesMarketIndicators.DoesNotExist:
            pass
        return '-'
    volume_24h_display.short_description = '24H交易量'

    def funding_rate_display(self, obj):
        """资金费率显示"""
        try:
            indicators = obj.market_indicators
            if indicators and indicators.funding_rate is not None:
                rate_pct = float(indicators.funding_rate) * 100
                # 正费率绿色，负费率红色
                color = 'green' if indicators.funding_rate >= 0 else 'red'
                # 格式化为4位小数
                formatted_rate = f"{rate_pct:.4f}"
                return format_html(
                    '<span style="color: {}; font-weight: bold;">{}%</span>',
                    color, formatted_rate
                )
        except FuturesMarketIndicators.DoesNotExist:
            pass
        return '-'
    funding_rate_display.short_description = '资金费率'

    def annual_rate_display(self, obj):
        """年化费率显示"""
        try:
            indicators = obj.market_indicators
            if indicators and indicators.funding_rate_annual is not None:
                annual_pct = float(indicators.funding_rate_annual) * 100
                # 根据年化收益率设置颜色
                if abs(annual_pct) >= 50:
                    color = '#FF5722'  # 橙红色 - 高费率
                elif abs(annual_pct) >= 20:
                    color = '#FF9800'  # 橙色 - 中等费率
                else:
                    color = '#4CAF50'  # 绿色 - 低费率

                # 格式化为2位小数
                formatted_rate = f"{annual_pct:.2f}"
                return format_html(
                    '<span style="color: {}; font-weight: bold;">{}%</span>',
                    color, formatted_rate
                )
        except FuturesMarketIndicators.DoesNotExist:
            pass
        return '-'
    annual_rate_display.short_description = '年化费率'


@admin.register(FuturesListingNotification)
class FuturesListingNotificationAdmin(admin.ModelAdmin):
    """合约上线通知记录管理"""
    list_display = ['contract_info', 'channel', 'status_display', 'retry_count', 'sent_at', 'created_at']
    list_filter = ['channel', 'status', 'sent_at', 'created_at']
    search_fields = ['futures_contract__symbol', 'error_message']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('关联信息', {
            'fields': ('futures_contract',)
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

    def contract_info(self, obj):
        """合约信息"""
        if obj.futures_contract:
            url = reverse('admin:monitor_futurescontract_change', args=[obj.futures_contract.id])
            return format_html(
                '<a href="{}">{} - {}</a>',
                url,
                obj.futures_contract.exchange.name,
                obj.futures_contract.symbol
            )
        return '-'
    contract_info.short_description = '合约'

    def status_display(self, obj):
        """状态显示"""
        status_colors = {
            FuturesListingNotification.SUCCESS: 'green',
            FuturesListingNotification.FAILED: 'red',
            FuturesListingNotification.PENDING: 'orange',
        }
        color = status_colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {};">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = '状态'


@admin.register(FuturesMarketIndicators)
class FuturesMarketIndicatorsAdmin(admin.ModelAdmin):
    """合约市场指标管理"""
    list_display = ['contract_symbol', 'open_interest_display', 'volume_24h_display',
                    'funding_rate_display', 'annual_rate_display', 'next_funding_display', 'last_updated']
    list_filter = ['funding_interval_hours', 'last_updated']
    search_fields = ['futures_contract__symbol']
    readonly_fields = ['last_updated']
    date_hierarchy = 'last_updated'

    fieldsets = (
        ('关联信息', {
            'fields': ('futures_contract',)
        }),
        ('市场指标', {
            'fields': ('open_interest', 'volume_24h')
        }),
        ('资金费率', {
            'fields': ('funding_rate', 'funding_rate_annual', 'next_funding_time', 'funding_interval_hours')
        }),
        ('费率限制', {
            'fields': ('funding_rate_cap', 'funding_rate_floor'),
        }),
        ('元数据', {
            'fields': ('last_updated',),
            'classes': ('collapse',)
        }),
    )

    def contract_symbol(self, obj):
        """合约代码"""
        if obj.futures_contract:
            url = reverse('admin:monitor_futurescontract_change', args=[obj.futures_contract.id])
            exchange_colors = {
                'binance': '#F0B90B',
                'hyperliquid': '#00D4AA',
                'bybit': '#F7A600',
            }
            color = exchange_colors.get(obj.futures_contract.exchange.code.lower(), 'black')
            return format_html(
                '<a href="{}"><span style="color: {};">{}</span> - {}</a>',
                url,
                color,
                obj.futures_contract.exchange.name,
                obj.futures_contract.symbol
            )
        return '-'
    contract_symbol.short_description = '合约'
    contract_symbol.admin_order_field = 'futures_contract__symbol'

    def open_interest_display(self, obj):
        """持仓量显示"""
        if obj.open_interest:
            # 格式化为千分位
            value = f"{obj.open_interest:,.2f}"
            return format_html('<span style="font-family: monospace;">{}</span>', value)
        return '-'
    open_interest_display.short_description = '持仓量'
    open_interest_display.admin_order_field = 'open_interest'

    def volume_24h_display(self, obj):
        """24小时交易量显示"""
        if obj.volume_24h:
            # 格式化为千分位
            value = f"{obj.volume_24h:,.2f}"
            return format_html('<span style="font-family: monospace; color: #2196F3;">{}</span>', value)
        return '-'
    volume_24h_display.short_description = '24H交易量'
    volume_24h_display.admin_order_field = 'volume_24h'

    def funding_rate_display(self, obj):
        """资金费率显示"""
        if obj.funding_rate is not None:
            rate_pct = float(obj.funding_rate) * 100
            # 正费率绿色，负费率红色
            color = 'green' if obj.funding_rate >= 0 else 'red'
            # 格式化为4位小数
            formatted_rate = f"{rate_pct:.4f}"
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}%</span>',
                color, formatted_rate
            )
        return '-'
    funding_rate_display.short_description = '当前费率'
    funding_rate_display.admin_order_field = 'funding_rate'

    def annual_rate_display(self, obj):
        """年化费率显示"""
        if obj.funding_rate_annual is not None:
            annual_pct = float(obj.funding_rate_annual) * 100
            # 根据年化收益率设置颜色
            if abs(annual_pct) >= 50:
                color = '#FF5722'  # 橙红色 - 高费率
            elif abs(annual_pct) >= 20:
                color = '#FF9800'  # 橙色 - 中等费率
            else:
                color = '#4CAF50'  # 绿色 - 低费率

            # 格式化为2位小数
            formatted_rate = f"{annual_pct:.2f}"
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}%</span>',
                color, formatted_rate
            )
        return '-'
    annual_rate_display.short_description = '年化费率'
    annual_rate_display.admin_order_field = 'funding_rate_annual'

    def next_funding_display(self, obj):
        """下次结算时间显示"""
        if obj.next_funding_time:
            from django.utils import timezone
            now = timezone.now()
            delta = obj.next_funding_time - now

            if delta.total_seconds() < 0:
                return format_html('<span style="color: gray;">已结算</span>')

            hours = int(delta.total_seconds() // 3600)
            minutes = int((delta.total_seconds() % 3600) // 60)

            return format_html(
                '<span style="color: #2196F3;">{} ({}h{}m后)</span>',
                obj.next_funding_time.strftime('%Y-%m-%d %H:%M'),
                hours,
                minutes
            )
        return '-'
    next_funding_display.short_description = '下次结算'
    next_funding_display.admin_order_field = 'next_funding_time'
