from django.db import models
from django.utils import timezone


class PromptTemplate(models.Model):
    """
    Prompt 模板模型

    用于存储不同 Twitter List 的分析提示词模板。
    """

    # 分析类型选项
    ANALYSIS_TYPE_GENERAL = 'general'
    ANALYSIS_TYPE_OPPORTUNITY = 'opportunity'
    ANALYSIS_TYPE_SENTIMENT = 'sentiment'
    ANALYSIS_TYPE_NEWS = 'news'
    ANALYSIS_TYPE_TRADING = 'trading'
    ANALYSIS_TYPE_CUSTOM = 'custom'

    ANALYSIS_TYPE_CHOICES = [
        (ANALYSIS_TYPE_GENERAL, '通用分析'),
        (ANALYSIS_TYPE_OPPORTUNITY, '项目机会分析'),
        (ANALYSIS_TYPE_SENTIMENT, '市场情绪分析'),
        (ANALYSIS_TYPE_NEWS, '新闻事件分析'),
        (ANALYSIS_TYPE_TRADING, '交易信号分析'),
        (ANALYSIS_TYPE_CUSTOM, '自定义分析'),
    ]

    # 状态选项
    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, '活跃'),
        (STATUS_INACTIVE, '不活跃'),
    ]

    name = models.CharField(
        max_length=100,
        verbose_name='模板名称',
        help_text='Prompt 模板的名称'
    )
    description = models.TextField(
        blank=True,
        default='',
        verbose_name='模板描述',
        help_text='模板的详细描述和用途说明'
    )
    analysis_type = models.CharField(
        max_length=20,
        choices=ANALYSIS_TYPE_CHOICES,
        default=ANALYSIS_TYPE_GENERAL,
        verbose_name='分析类型',
        help_text='模板的分析类型分类'
    )

    # Twitter List 关联
    twitter_lists = models.ManyToManyField(
        'TwitterList',
        blank=True,
        related_name='prompt_templates',
        verbose_name='关联的 Twitter Lists',
        help_text='应用此模板的 Twitter List（可选，留空表示通用模板）'
    )

    # Prompt 模板内容
    template_content = models.TextField(
        verbose_name='Prompt 模板内容',
        help_text='包含 {tweet_content} 占位符的完整 prompt 模板'
    )

    # 配置参数
    max_tweets_per_batch = models.IntegerField(
        default=100,
        verbose_name='每批最大推文数',
        help_text='使用此模板时的批次大小限制'
    )
    max_cost_per_analysis = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=10.0000,
        verbose_name='每次分析最大成本（美元）',
        help_text='使用此模板时的成本上限'
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name='是否默认模板',
        help_text='当没有匹配到特定模板时使用（每种类型只能有一个默认模板）'
    )

    # 状态和时间
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        verbose_name='状态',
        help_text='模板的启用状态'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )

    class Meta:
        db_table = 'twitter_prompt_templates'
        ordering = ['-is_default', '-created_at']
        verbose_name = 'Prompt 模板'
        verbose_name_plural = 'Prompt 模板'
        indexes = [
            models.Index(fields=['analysis_type', 'status'], name='prompt_type_status_idx'),
            models.Index(fields=['is_default'], name='prompt_default_idx'),
            models.Index(fields=['created_at'], name='prompt_created_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['analysis_type', 'is_default'],
                condition=models.Q(is_default=True),
                name='unique_default_per_type'
            ),
        ]

    def __str__(self):
        list_count = self.twitter_lists.count()
        list_info = f' ({list_count} 个 List)' if list_count > 0 else ' (通用)'
        return f'{self.name} - {self.get_analysis_type_display()}{list_info}'

    def get_twitter_list_ids(self):
        """获取关联的 Twitter List ID 列表"""
        return list(self.twitter_lists.values_list('list_id', flat=True))

    def format_template(self, tweet_content: str) -> str:
        """
        格式化模板，替换推文内容

        Args:
            tweet_content: 推文内容

        Returns:
            str: 格式化后的完整 prompt
        """
        return self.template_content.format(tweet_content=tweet_content)

    def is_applicable_to_list(self, list_id: str) -> bool:
        """
        检查模板是否适用于指定的 List

        Args:
            list_id: Twitter List ID

        Returns:
            bool: 是否适用
        """
        # 如果没有指定特定 List，则为通用模板
        if self.twitter_lists.count() == 0:
            return True

        # 检查是否在关联的 List 中
        return self.twitter_lists.filter(list_id=list_id).exists()

    @classmethod
    def get_template_for_list(cls, list_id: str, analysis_type: str = None) -> 'PromptTemplate':
        """
        为指定的 List 获取合适的模板

        Args:
            list_id: Twitter List ID
            analysis_type: 分析类型（可选）

        Returns:
            PromptTemplate: 匹配的模板，如果找不到则返回默认通用模板

        Raises:
            PromptTemplate.DoesNotExist: 如果找不到任何可用模板
        """
        # 首先尝试查找匹配此 List 的模板
        qs = cls.objects.filter(
            status=cls.STATUS_ACTIVE
        )

        if analysis_type:
            qs = qs.filter(analysis_type=analysis_type)

        # 按优先级排序：
        # 1. 明确指定此 List 的模板
        # 2. 通用模板（未指定特定 List）
        template = (
            qs.filter(twitter_lists__list_id=list_id).first() or
            qs.filter(twitter_lists__isnull=True).first()
        )

        if not template:
            # 如果仍找不到，尝试获取默认的通用模板
            template = cls.objects.filter(
                status=cls.STATUS_ACTIVE,
                analysis_type=cls.ANALYSIS_TYPE_GENERAL,
                is_default=True
            ).first()

        if not template:
            raise cls.DoesNotExist(
                f"No suitable prompt template found for list {list_id}"
            )

        return template

    @classmethod
    def get_default_templates(cls):
        """获取所有默认模板"""
        return cls.objects.filter(
            status=cls.STATUS_ACTIVE,
            is_default=True
        ).order_by('analysis_type')

    def activate(self):
        """激活模板"""
        self.status = self.STATUS_ACTIVE
        self.save()

    def deactivate(self):
        """停用模板"""
        self.status = self.STATUS_INACTIVE
        self.save()

    def make_default(self):
        """
        设置为默认模板

        注意：每种分析类型只能有一个默认模板
        """
        # 取消同类型其他模板的默认状态
        cls = self.__class__
        cls.objects.filter(
            analysis_type=self.analysis_type,
            is_default=True
        ).exclude(pk=self.pk).update(is_default=False)

        # 设置当前模板为默认
        self.is_default = True
        self.save()
