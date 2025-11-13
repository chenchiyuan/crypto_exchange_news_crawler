from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
import json

from twitter.models import Tag, TwitterList, Tweet, TwitterAnalysisResult


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """Tag 模型管理"""

    list_display = ('name', 'description', 'color_badge', 'is_deleted', 'created_at')
    list_filter = ('is_deleted', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')
    ordering = ('-created_at',)

    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'description', 'color')
        }),
        ('状态信息', {
            'fields': ('is_deleted', 'deleted_at')
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def color_badge(self, obj):
        """显示颜色徽章"""
        if obj.color:
            return format_html(
                '<span style="background-color: {}; padding: 3px 10px; '
                'border-radius: 3px; color: white;">{}</span>',
                obj.color,
                obj.name
            )
        return obj.name
    color_badge.short_description = '颜色徽章'


@admin.register(TwitterList)
class TwitterListAdmin(admin.ModelAdmin):
    """TwitterList 模型管理"""

    list_display = ('list_id', 'name', 'status', 'tweet_count', 'tags_display', 'created_at')
    list_filter = ('status', 'is_deleted', 'created_at')
    search_fields = ('list_id', 'name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at', 'tweet_count')
    filter_horizontal = ('tags',)
    ordering = ('-created_at',)

    fieldsets = (
        ('基本信息', {
            'fields': ('list_id', 'name', 'description')
        }),
        ('状态管理', {
            'fields': ('status', 'is_deleted', 'deleted_at')
        }),
        ('分类标签', {
            'fields': ('tags',)
        }),
        ('统计信息', {
            'fields': ('tweet_count',)
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def tweet_count(self, obj):
        """推文数量"""
        return obj.tweets.count()
    tweet_count.short_description = '推文数量'

    def tags_display(self, obj):
        """显示标签列表"""
        tags = obj.tags.all()
        if tags:
            return ', '.join([tag.name for tag in tags])
        return '-'
    tags_display.short_description = '标签'


@admin.register(Tweet)
class TweetAdmin(admin.ModelAdmin):
    """Tweet 模型管理"""

    list_display = ('tweet_id', 'screen_name_link', 'content_preview',
                   'engagement_score', 'tweet_created_at', 'is_deleted')
    list_filter = ('twitter_list', 'is_deleted', 'tweet_created_at')
    search_fields = ('tweet_id', 'screen_name', 'user_name', 'content')
    readonly_fields = ('tweet_id', 'twitter_list', 'user_id', 'screen_name',
                      'user_name', 'content', 'tweet_created_at',
                      'retweet_count', 'favorite_count', 'reply_count',
                      'engagement_rate_display', 'created_at', 'updated_at', 'deleted_at')
    date_hierarchy = 'tweet_created_at'
    ordering = ('-tweet_created_at',)

    fieldsets = (
        ('推文信息', {
            'fields': ('tweet_id', 'twitter_list', 'content')
        }),
        ('用户信息', {
            'fields': ('user_id', 'screen_name', 'user_name')
        }),
        ('互动数据', {
            'fields': ('retweet_count', 'favorite_count', 'reply_count', 'engagement_rate_display')
        }),
        ('时间信息', {
            'fields': ('tweet_created_at', 'created_at', 'updated_at')
        }),
        ('软删除', {
            'fields': ('is_deleted', 'deleted_at'),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        """禁止在 Admin 中添加推文"""
        return False

    def has_delete_permission(self, request, obj=None):
        """禁止在 Admin 中删除推文"""
        return False

    def screen_name_link(self, obj):
        """显示用户名链接"""
        return format_html(
            '<a href="https://twitter.com/{}" target="_blank">@{}</a>',
            obj.screen_name,
            obj.screen_name
        )
    screen_name_link.short_description = '用户'

    def content_preview(self, obj):
        """内容预览（前 50 字符）"""
        if len(obj.content) > 50:
            return obj.content[:50] + '...'
        return obj.content
    content_preview.short_description = '内容预览'

    def engagement_score(self, obj):
        """互动分数（彩色显示）"""
        score = obj.get_engagement_rate()
        if score >= 1000:
            color = '#e74c3c'  # 红色 - 超高互动
        elif score >= 100:
            color = '#f39c12'  # 橙色 - 高互动
        elif score >= 10:
            color = '#27ae60'  # 绿色 - 中等互动
        else:
            color = '#95a5a6'  # 灰色 - 低互动

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            score
        )
    engagement_score.short_description = '互动分数'

    def engagement_rate_display(self, obj):
        """显示互动率详情"""
        return f"总互动: {obj.get_engagement_rate()} (👍{obj.favorite_count} 🔄{obj.retweet_count} 💬{obj.reply_count})"
    engagement_rate_display.short_description = '互动详情'


@admin.register(TwitterAnalysisResult)
class TwitterAnalysisResultAdmin(admin.ModelAdmin):
    """TwitterAnalysisResult 模型管理"""

    list_display = ('task_id_short', 'twitter_list', 'status_badge',
                   'tweet_count', 'cost_display', 'processing_time_display',
                   'created_at')
    list_filter = ('status', 'twitter_list', 'is_deleted', 'created_at')
    search_fields = ('task_id', 'twitter_list__name', 'error_message')
    readonly_fields = ('task_id', 'twitter_list', 'start_time', 'end_time',
                      'prompt_template', 'tweet_count', 'analysis_result_display',
                      'status', 'error_message', 'cost_amount', 'processing_time',
                      'created_at', 'updated_at', 'deleted_at')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    fieldsets = (
        ('任务信息', {
            'fields': ('task_id', 'twitter_list', 'status', 'tweet_count')
        }),
        ('时间范围', {
            'fields': ('start_time', 'end_time')
        }),
        ('Prompt 模板', {
            'fields': ('prompt_template',),
            'classes': ('collapse',)
        }),
        ('分析结果', {
            'fields': ('analysis_result_display',)
        }),
        ('成本和性能', {
            'fields': ('cost_amount', 'processing_time')
        }),
        ('错误信息', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at')
        }),
        ('软删除', {
            'fields': ('is_deleted', 'deleted_at'),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        """禁止在 Admin 中添加分析结果"""
        return False

    def has_delete_permission(self, request, obj=None):
        """禁止在 Admin 中删除分析结果"""
        return False

    def task_id_short(self, obj):
        """显示短任务 ID"""
        return str(obj.task_id)[:8] + '...'
    task_id_short.short_description = '任务 ID'

    def status_badge(self, obj):
        """状态徽章（彩色显示）"""
        status_colors = {
            'pending': '#95a5a6',    # 灰色
            'running': '#3498db',    # 蓝色
            'completed': '#27ae60',  # 绿色
            'failed': '#e74c3c',     # 红色
            'cancelled': '#f39c12',  # 橙色
        }
        color = status_colors.get(obj.status, '#95a5a6')

        return format_html(
            '<span style="background-color: {}; padding: 3px 8px; '
            'border-radius: 3px; color: white; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = '状态'

    def cost_display(self, obj):
        """成本显示（彩色显示）"""
        cost = obj.cost_amount
        if cost > 5:
            color = '#e74c3c'  # 红色 - 高成本
        elif cost > 1:
            color = '#f39c12'  # 橙色 - 中等成本
        else:
            color = '#27ae60'  # 绿色 - 低成本

        return format_html(
            '<span style="color: {}; font-weight: bold;">${:.4f}</span>',
            color,
            cost
        )
    cost_display.short_description = '成本'

    def processing_time_display(self, obj):
        """处理时长显示"""
        return f"{obj.processing_time:.2f}s"
    processing_time_display.short_description = '处理时长'

    def analysis_result_display(self, obj):
        """格式化显示分析结果"""
        if not obj.analysis_result:
            return '-'

        result = obj.analysis_result

        # 提取情绪数据
        sentiment = result.get('sentiment', {})
        sentiment_html = f"""
        <h3>📊 市场情绪</h3>
        <ul>
            <li>多头: {sentiment.get('bullish', 0)} 条 ({sentiment.get('bullish_percentage', 0):.1f}%)</li>
            <li>空头: {sentiment.get('bearish', 0)} 条 ({sentiment.get('bearish_percentage', 0):.1f}%)</li>
            <li>中性: {sentiment.get('neutral', 0)} 条 ({sentiment.get('neutral_percentage', 0):.1f}%)</li>
        </ul>
        """

        # 提取关键话题
        topics = result.get('key_topics', [])
        if topics:
            topics_html = "<h3>🔥 关键话题</h3><ol>"
            for topic in topics[:5]:
                sentiment_icon = {
                    'bullish': '📈',
                    'bearish': '📉',
                    'neutral': '➖'
                }.get(topic.get('sentiment', 'neutral'), '➖')
                topics_html += f"<li>{topic['topic']} ({topic['count']} 次) {sentiment_icon}</li>"
            topics_html += "</ol>"
        else:
            topics_html = ""

        # 市场总结
        summary = result.get('market_summary', '')
        summary_html = f"<h3>📝 市场总结</h3><p>{summary}</p>" if summary else ""

        # 完整 JSON（折叠）
        json_str = json.dumps(result, ensure_ascii=False, indent=2)
        json_html = f"""
        <details style="margin-top: 20px;">
            <summary style="cursor: pointer; font-weight: bold;">📄 查看完整 JSON</summary>
            <pre style="background: #f5f5f5; padding: 10px; border-radius: 5px; overflow-x: auto;">{json_str}</pre>
        </details>
        """

        return mark_safe(sentiment_html + topics_html + summary_html + json_html)

    analysis_result_display.short_description = '分析结果'
