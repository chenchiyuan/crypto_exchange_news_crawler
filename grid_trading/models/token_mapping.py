"""币安symbol与CoinGecko ID的映射关系模型"""
from django.db import models
from django.utils import timezone


class TokenMapping(models.Model):
    """币安symbol与CoinGecko ID的映射关系"""

    class MatchStatus(models.TextChoices):
        AUTO_MATCHED = "auto_matched", "自动匹配"
        MANUAL_CONFIRMED = "manual_confirmed", "人工确认"
        NEEDS_REVIEW = "needs_review", "需要审核"

    # 主键
    id = models.AutoField(primary_key=True)

    # 币安交易对symbol (如: BTCUSDT)
    symbol = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        verbose_name="币安交易对"
    )

    # 基础代币symbol (如: BTC)
    base_token = models.CharField(
        max_length=10,
        verbose_name="基础代币"
    )

    # CoinGecko代币ID (如: bitcoin)
    coingecko_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="CoinGecko ID"
    )

    # 匹配状态
    match_status = models.CharField(
        max_length=20,
        choices=MatchStatus.choices,
        default=MatchStatus.NEEDS_REVIEW,
        db_index=True,
        verbose_name="匹配状态"
    )

    # 候选CoinGecko ID列表 (JSON格式)
    # 例如: ["bitcoin", "wrapped-bitcoin", "bitcoin-cash"]
    alternatives = models.JSONField(
        null=True,
        blank=True,
        verbose_name="候选ID列表"
    )

    # 创建时间
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间"
    )

    # 最后更新时间
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新时间"
    )

    class Meta:
        db_table = "token_mapping"
        verbose_name = "代币映射"
        verbose_name_plural = "代币映射"
        ordering = ["symbol"]
        indexes = [
            models.Index(fields=["symbol"], name="token_mapping_symbol_idx"),
            models.Index(fields=["match_status"], name="token_mapping_status_idx"),
            models.Index(fields=["coingecko_id"], name="token_mapping_cg_id_idx"),
        ]

    def __str__(self):
        return f"{self.symbol} → {self.coingecko_id or '未映射'}"

    def is_ready_for_update(self):
        """判断是否可以用于数据更新"""
        return self.match_status in [
            self.MatchStatus.AUTO_MATCHED,
            self.MatchStatus.MANUAL_CONFIRMED
        ] and self.coingecko_id is not None
