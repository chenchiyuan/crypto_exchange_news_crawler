from django.db import models
from .soft_delete import SoftDeleteModel


class Tag(SoftDeleteModel):
    """
    标签模型

    用于对 Twitter List 进行分类和标记。
    """
    name = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name='标签名称',
        help_text='标签名称，唯一'
    )
    description = models.TextField(
        blank=True,
        default='',
        verbose_name='标签描述',
        help_text='标签的详细描述'
    )
    color = models.CharField(
        max_length=7,
        blank=True,
        default='#007bff',
        verbose_name='标签颜色',
        help_text='标签显示颜色，十六进制格式 (如 #007bff)'
    )

    class Meta:
        db_table = 'twitter_tag'
        verbose_name = '标签'
        verbose_name_plural = '标签'
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_twitter_lists_count(self):
        """获取使用此标签的 Twitter List 数量"""
        return self.twitter_lists.filter(is_deleted=False).count()
