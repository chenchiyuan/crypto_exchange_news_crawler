"""市值和FDV市场数据模型"""
from django.db import models
from django.utils import timezone


class MarketData(models.Model):
    """市值和FDV市场数据"""

    # 主键
    id = models.AutoField(primary_key=True)

    # 币安交易对symbol (外键到TokenMapping)
    symbol = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        verbose_name="币安交易对"
    )

    # 市值 (美元)
    market_cap = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="市值(USD)"
    )

    # 全稀释估值 (美元)
    fully_diluted_valuation = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="FDV(USD)"
    )

    # 数据来源 (固定为"coingecko")
    data_source = models.CharField(
        max_length=50,
        default="coingecko",
        verbose_name="数据来源"
    )

    # 数据获取时间 (从API拿到数据的时间)
    fetched_at = models.DateTimeField(
        verbose_name="获取时间"
    )

    # 创建时间 (首次插入记录的时间)
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间"
    )

    # 最后更新时间 (最后一次更新记录的时间)
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新时间"
    )

    class Meta:
        db_table = "market_data"
        verbose_name = "市场数据"
        verbose_name_plural = "市场数据"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["symbol"], name="market_data_symbol_idx"),
            models.Index(fields=["updated_at"], name="market_data_updated_idx"),
        ]

    def __str__(self):
        return f"{self.symbol}: MC=${self.market_cap}, FDV=${self.fully_diluted_valuation}"

    @property
    def market_cap_formatted(self):
        """格式化市值(K/M/B)"""
        if self.market_cap is None:
            return "-"
        return self._format_number(float(self.market_cap))

    @property
    def fdv_formatted(self):
        """格式化FDV(K/M/B)"""
        if self.fully_diluted_valuation is None:
            return "-"
        return self._format_number(float(self.fully_diluted_valuation))

    @staticmethod
    def _format_number(value):
        """数字格式化辅助函数"""
        if value >= 1_000_000_000:
            return f"${value / 1_000_000_000:.2f}B"
        elif value >= 1_000_000:
            return f"${value / 1_000_000:.2f}M"
        elif value >= 1_000:
            return f"${value / 1_000:.2f}K"
        else:
            return f"${value:.2f}"
