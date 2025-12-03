"""
ScreeningResult 数据模型

用途: 最终输出的筛选结果，整合三维指标和GSS评分
关联FR: FR-022, FR-028, FR-029, FR-030, FR-031, FR-032, FR-033
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .volatility_metrics import VolatilityMetrics
    from .trend_metrics import TrendMetrics
    from .microstructure_metrics import MicrostructureMetrics


def calculate_grid_parameters(
    current_price: Decimal, atr_daily: float, atr_hourly: float
) -> tuple:
    """
    计算推荐网格参数 (FR-030)

    公式:
        Upper Limit = Current Price + 2 × ATR_daily
        Lower Limit = Current Price - 3 × ATR_daily
        Grid Count = (Upper - Lower) / (0.5 × ATR_hourly)

    Args:
        current_price: 当前价格
        atr_daily: 日线ATR (基于24小时K线, period=14)
        atr_hourly: 小时线ATR (基于1小时K线, period=14)

    Returns:
        (upper_limit, lower_limit, grid_count)
    """
    upper = current_price + Decimal(str(2 * atr_daily))
    lower = current_price - Decimal(str(3 * atr_daily))
    grid_step = 0.5 * atr_hourly
    grid_count = int((float(upper - lower) / grid_step)) + 1

    return upper, lower, grid_count


@dataclass
class ScreeningResult:
    """
    筛选结果数据类

    属性:
        rank: 排名
        symbol: 标的代码
        current_price: 当前价格
        volatility: 波动率指标对象
        trend: 趋势指标对象
        microstructure: 微观结构指标对象
        gss_score: GSS评分 (0-1)
        grid_upper_limit: 推荐网格上限
        grid_lower_limit: 推荐网格下限
        grid_count: 推荐格数
    """

    rank: int
    symbol: str
    current_price: Decimal
    volatility: "VolatilityMetrics"
    trend: "TrendMetrics"
    microstructure: "MicrostructureMetrics"
    gss_score: float
    grid_upper_limit: Decimal
    grid_lower_limit: Decimal
    grid_count: int

    @classmethod
    def from_metrics(
        cls,
        rank: int,
        symbol: str,
        current_price: Decimal,
        volatility: "VolatilityMetrics",
        trend: "TrendMetrics",
        microstructure: "MicrostructureMetrics",
        gss_score: float,
        atr_daily: float,
        atr_hourly: float,
    ) -> "ScreeningResult":
        """
        从三维指标构建筛选结果 (FR-028, FR-030)

        Args:
            rank: 排名
            symbol: 标的代码
            current_price: 当前价格
            volatility: 波动率指标
            trend: 趋势指标
            microstructure: 微观结构指标
            gss_score: GSS评分
            atr_daily: 日线ATR
            atr_hourly: 小时线ATR

        Returns:
            ScreeningResult 对象
        """
        upper, lower, grid_count = calculate_grid_parameters(
            current_price, atr_daily, atr_hourly
        )

        return cls(
            rank=rank,
            symbol=symbol,
            current_price=current_price,
            volatility=volatility,
            trend=trend,
            microstructure=microstructure,
            gss_score=gss_score,
            grid_upper_limit=upper,
            grid_lower_limit=lower,
            grid_count=grid_count,
        )

    def to_terminal_row(self) -> dict:
        """
        转换为终端输出行 (FR-031, FR-032)

        Returns:
            格式化的字典，用于终端表格输出
        """
        # 合并警告和优势标记
        warnings = (
            self.volatility.warning_flags
            + self.trend.warning_flags
            + self.microstructure.warning_flags
        )

        return {
            "rank": self.rank,
            "symbol": self.symbol,
            "price": f"${self.current_price:,.2f}",
            "natr": f"{self.volatility.natr:.2f}%",
            "ker": f"{self.volatility.ker:.3f}",
            "vdr": f"{self.volatility.vdr:.1f}",
            "hurst": f"{self.trend.hurst_exponent:.3f}",
            "z_score": f"{self.trend.z_score:.1f}",
            "slope": f"{self.trend.norm_slope:.1f}",
            "r2": f"{self.trend.r_squared:.3f}",
            "ovr": f"{self.microstructure.ovr:.2f}",
            "funding": f"{float(self.microstructure.funding_rate) * 100:.4f}%",
            "cvd": "✓" if self.microstructure.has_cvd_divergence else "✗",
            "cvd_roc": f"{self.microstructure.cvd_roc:.1f}%",
            "gss": f"{self.gss_score:.4f}",
            "grid_upper": f"${self.grid_upper_limit:,.2f}",
            "grid_lower": f"${self.grid_lower_limit:,.2f}",
            "warnings": " ".join(warnings) if warnings else "-",
        }
