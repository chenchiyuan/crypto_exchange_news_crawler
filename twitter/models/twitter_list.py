from django.db import models
from .soft_delete import SoftDeleteModel
from .tag import Tag


class TwitterList(SoftDeleteModel):
    """
    Twitter List 模型

    存储 Twitter List 的配置信息，作为推文获取和分析的入口。
    """

    STATUS_CHOICES = [
        ('active', '活跃'),      # 正常使用中
        ('inactive', '不活跃'),  # 暂时停用
        ('archived', '已归档'),  # 归档保留
    ]

    list_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name='Twitter List ID',
        help_text='Twitter List 的唯一标识符'
    )
    name = models.CharField(
        max_length=255,
        verbose_name='List 名称',
        help_text='Twitter List 的显示名称'
    )
    description = models.TextField(
        blank=True,
        default='',
        verbose_name='List 描述',
        help_text='Twitter List 的详细描述'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        db_index=True,
        verbose_name='状态',
        help_text='List 的当前状态'
    )
    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name='twitter_lists',
        verbose_name='标签',
        help_text='关联的分类标签'
    )

    class Meta:
        db_table = 'twitter_lists'
        ordering = ['-updated_at']
        verbose_name = 'Twitter List'
        verbose_name_plural = 'Twitter Lists'
        indexes = [
            models.Index(fields=['list_id'], name='twitter_list_id_idx'),
            models.Index(fields=['status'], name='twitter_list_status_idx'),
            models.Index(fields=['created_at'], name='twitter_list_created_idx'),
        ]

    def __str__(self):
        return f"{self.name} ({self.list_id})"

    @classmethod
    def get_active_lists(cls):
        """获取所有活跃的 Lists"""
        return cls.objects.filter(status='active')

    @classmethod
    def create_or_update_list(cls, list_id: str, name: str, description: str = ''):
        """创建或更新 Twitter List"""
        twitter_list, created = cls.objects.update_or_create(
            list_id=list_id,
            defaults={'name': name, 'description': description, 'status': 'active'}
        )
        return twitter_list, created

    def get_tweet_count(self):
        """获取此 List 的推文数量"""
        return self.tweets.filter(is_deleted=False).count()

    def get_latest_tweets(self, limit=10):
        """获取最新的推文"""
        return self.tweets.filter(is_deleted=False).order_by('-tweet_created_at')[:limit]
