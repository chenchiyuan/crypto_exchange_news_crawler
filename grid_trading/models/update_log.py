"""更新日志模型 - 记录API调用和数据更新的批次日志"""
import uuid
from django.db import models
from django.utils import timezone


class UpdateLog(models.Model):
    """更新日志 - 审计和调试"""

    class OperationType(models.TextChoices):
        MAPPING_GENERATION = "mapping_generation", "映射关系生成"
        MAPPING_UPDATE = "mapping_update", "映射关系更新"
        MARKET_DATA_UPDATE = "market_data_update", "市值/FDV数据更新"
        CONTRACT_SYNC = "contract_sync", "合约同步"

    class Status(models.TextChoices):
        SUCCESS = "success", "成功"
        PARTIAL_SUCCESS = "partial_success", "部分成功"
        FAILED = "failed", "失败"

    # 主键
    id = models.AutoField(primary_key=True)

    # 批次ID (用于关联同一批次的多条日志)
    batch_id = models.UUIDField(
        default=uuid.uuid4,
        db_index=True,
        verbose_name="批次ID"
    )

    # 币安交易对symbol (可选，批量操作时为NULL)
    symbol = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="币安交易对"
    )

    # 操作类型
    operation_type = models.CharField(
        max_length=50,
        choices=OperationType.choices,
        db_index=True,
        verbose_name="操作类型"
    )

    # 操作状态
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        db_index=True,
        verbose_name="状态"
    )

    # 错误信息 (成功时为NULL)
    error_message = models.TextField(
        null=True,
        blank=True,
        verbose_name="错误信息"
    )

    # 执行时间
    executed_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name="执行时间"
    )

    # 额外元数据 (JSON格式)
    # 例如: {"total": 100, "success": 95, "failed": 5, "duration_seconds": 123.45}
    metadata = models.JSONField(
        null=True,
        blank=True,
        verbose_name="元数据"
    )

    class Meta:
        db_table = "update_log"
        verbose_name = "更新日志"
        verbose_name_plural = "更新日志"
        ordering = ["-executed_at"]
        indexes = [
            models.Index(fields=["batch_id"], name="update_log_batch_idx"),
            models.Index(fields=["symbol"], name="update_log_symbol_idx"),
            models.Index(fields=["operation_type"], name="update_log_operation_idx"),
            models.Index(fields=["status"], name="update_log_status_idx"),
            models.Index(fields=["executed_at"], name="update_log_executed_idx"),
        ]

    def __str__(self):
        symbol_str = f" ({self.symbol})" if self.symbol else ""
        return f"[{self.batch_id}] {self.operation_type}{symbol_str}: {self.status}"

    @classmethod
    def log_batch_start(cls, operation_type, batch_id=None, metadata=None):
        """记录批次开始"""
        if batch_id is None:
            batch_id = uuid.uuid4()

        log = cls.objects.create(
            batch_id=batch_id,
            operation_type=operation_type,
            status=cls.Status.SUCCESS,  # 临时状态，后续更新
            metadata=metadata or {},
            executed_at=timezone.now()
        )
        return batch_id, log

    @classmethod
    def log_batch_complete(cls, batch_id, operation_type, status, metadata=None):
        """记录批次完成"""
        return cls.objects.create(
            batch_id=batch_id,
            operation_type=operation_type,
            status=status,
            metadata=metadata or {},
            executed_at=timezone.now()
        )

    @classmethod
    def log_symbol_error(cls, batch_id, symbol, operation_type, error_message, metadata=None):
        """记录单个symbol的错误"""
        return cls.objects.create(
            batch_id=batch_id,
            symbol=symbol,
            operation_type=operation_type,
            status=cls.Status.FAILED,
            error_message=error_message,
            metadata=metadata or {},
            executed_at=timezone.now()
        )
