from django.db import models
from django.utils import timezone


class SoftDeleteManager(models.Manager):
    """软删除管理器 - 默认只返回未删除的记录"""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class SoftDeleteAllManager(models.Manager):
    """包含已删除记录的管理器"""

    def get_queryset(self):
        return super().get_queryset()


class SoftDeleteModel(models.Model):
    """
    软删除基类

    提供软删除功能，删除的记录不会从数据库中物理删除，而是标记为已删除。
    """
    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='是否删除',
        help_text='软删除标记，True 表示已删除'
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name='删除时间',
        help_text='记录被软删除的时间'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name='创建时间'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )

    objects = SoftDeleteManager()  # 默认管理器：只返回未删除的记录
    all_objects = SoftDeleteAllManager()  # 包含已删除记录的管理器

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def delete(self, using=None, keep_parents=False, hard=False):
        """
        软删除方法

        Args:
            using: 数据库别名
            keep_parents: 是否保留父记录
            hard: 是否硬删除（物理删除），默认False
        """
        if hard:
            # 硬删除：物理删除记录
            super().delete(using=using, keep_parents=keep_parents)
        else:
            # 软删除：只标记为已删除
            self.is_deleted = True
            self.deleted_at = timezone.now()
            self.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])

    def restore(self):
        """恢复已删除的记录"""
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])

    def is_active(self):
        """检查记录是否有效（未删除）"""
        return not self.is_deleted
