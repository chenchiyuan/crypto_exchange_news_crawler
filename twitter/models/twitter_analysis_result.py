import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone
from .soft_delete import SoftDeleteModel
from .twitter_list import TwitterList


class TwitterAnalysisResult(SoftDeleteModel):
    """
    Twitter 分析结果模型

    存储 AI 分析任务的元数据和结果，支持异步任务状态跟踪。
    """

    # 任务状态选项
    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING, '待处理'),
        (STATUS_RUNNING, '运行中'),
        (STATUS_COMPLETED, '已完成'),
        (STATUS_FAILED, '失败'),
        (STATUS_CANCELLED, '已取消'),
    ]

    task_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='任务 ID',
        help_text='任务的唯一标识符（UUID）'
    )
    twitter_list = models.ForeignKey(
        TwitterList,
        on_delete=models.CASCADE,
        related_name='analysis_results',
        db_index=True,
        verbose_name='Twitter List',
        help_text='分析的 Twitter List'
    )
    start_time = models.DateTimeField(
        verbose_name='分析起始时间',
        help_text='分析的推文时间范围起点'
    )
    end_time = models.DateTimeField(
        verbose_name='分析结束时间',
        help_text='分析的推文时间范围终点'
    )
    prompt_template = models.TextField(
        verbose_name='Prompt 模板',
        help_text='使用的 AI 分析 prompt 内容'
    )
    tweet_count = models.IntegerField(
        default=0,
        verbose_name='推文数量',
        help_text='本次分析的推文总数'
    )
    analysis_result = models.JSONField(
        null=True,
        blank=True,
        verbose_name='分析结果',
        help_text='AI 生成的结构化分析结果（JSON 格式）'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
        verbose_name='任务状态',
        help_text='任务当前的执行状态'
    )
    error_message = models.TextField(
        blank=True,
        default='',
        verbose_name='错误信息',
        help_text='任务失败时的错误详情'
    )
    cost_amount = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name='实际成本（美元）',
        help_text='本次分析的实际 API 调用成本'
    )
    processing_time = models.FloatField(
        default=0.0,
        verbose_name='处理时长（秒）',
        help_text='任务实际执行时长'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间',
        help_text='任务创建时间'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间',
        help_text='任务最后更新时间'
    )

    class Meta:
        db_table = 'twitter_analysis_results'
        ordering = ['-created_at']
        verbose_name = 'Twitter 分析结果'
        verbose_name_plural = 'Twitter 分析结果'
        indexes = [
            models.Index(fields=['twitter_list', 'created_at'], name='tw_analysis_list_time_idx'),
            models.Index(fields=['status', 'created_at'], name='tw_analysis_status_time_idx'),
            models.Index(fields=['created_at'], name='tw_analysis_created_idx'),
        ]

    def __str__(self):
        return f"Analysis {self.task_id} - {self.get_status_display()}"

    def mark_as_running(self):
        """标记任务为运行中"""
        self.status = self.STATUS_RUNNING
        self.updated_at = timezone.now()
        self.save(update_fields=['status', 'updated_at'])

    def mark_as_completed(self, analysis_result, cost_amount, processing_time):
        """
        标记任务为已完成

        Args:
            analysis_result: 分析结果字典
            cost_amount: 实际成本（Decimal）
            processing_time: 处理时长（秒）
        """
        self.status = self.STATUS_COMPLETED
        self.analysis_result = analysis_result
        self.cost_amount = cost_amount
        self.processing_time = processing_time
        self.updated_at = timezone.now()
        self.save(update_fields=['status', 'analysis_result', 'cost_amount',
                                'processing_time', 'updated_at'])

    def mark_as_failed(self, error_message, processing_time=0.0):
        """
        标记任务为失败

        Args:
            error_message: 错误信息
            processing_time: 处理时长（秒）
        """
        self.status = self.STATUS_FAILED
        self.error_message = error_message
        self.processing_time = processing_time
        self.updated_at = timezone.now()
        self.save(update_fields=['status', 'error_message', 'processing_time', 'updated_at'])

    def mark_as_cancelled(self):
        """标记任务为已取消"""
        self.status = self.STATUS_CANCELLED
        self.updated_at = timezone.now()
        self.save(update_fields=['status', 'updated_at'])

    def is_terminal_state(self):
        """
        判断任务是否处于终态

        Returns:
            bool: 是否为终态（completed/failed/cancelled）
        """
        return self.status in [
            self.STATUS_COMPLETED,
            self.STATUS_FAILED,
            self.STATUS_CANCELLED
        ]

    def can_be_cancelled(self):
        """
        判断任务是否可以被取消

        Returns:
            bool: 是否可以取消（pending 或 running 状态）
        """
        return self.status in [self.STATUS_PENDING, self.STATUS_RUNNING]

    @classmethod
    def get_pending_tasks(cls):
        """获取所有待处理的任务"""
        return cls.objects.filter(status=cls.STATUS_PENDING).order_by('created_at')

    @classmethod
    def get_running_tasks(cls):
        """获取所有运行中的任务"""
        return cls.objects.filter(status=cls.STATUS_RUNNING).order_by('created_at')

    @classmethod
    def get_completed_tasks(cls, twitter_list=None, days=7):
        """
        获取已完成的任务

        Args:
            twitter_list: 可选，筛选指定 List
            days: 最近 N 天的任务

        Returns:
            QuerySet: 已完成的任务列表
        """
        queryset = cls.objects.filter(
            status=cls.STATUS_COMPLETED,
            created_at__gte=timezone.now() - timezone.timedelta(days=days)
        )
        if twitter_list:
            queryset = queryset.filter(twitter_list=twitter_list)
        return queryset.order_by('-created_at')
