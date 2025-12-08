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
    current_price: Decimal, atr_daily: float, atr_hourly: float, max_grids: int = 100
) -> tuple:
    """
    计算推荐网格参数 (FR-030) - 优化版（混合策略）

    基础公式:
        Upper Limit = Current Price + 2 × ATR_daily
        Lower Limit = Current Price - 3 × ATR_daily
        Grid Step = 0.5 × ATR_hourly
        Grid Count = (Upper - Lower) / Grid Step + 1

    优化策略（确保网格数 ≤ max_grids）:
        1. 如果理论网格数 ≤ max_grids: 使用原算法（无调整）
        2. 如果 max_grids < 理论网格数 ≤ 150: 仅调整步长（保持风险边界）
        3. 如果理论网格数 > 150: 同时收窄区间+调整步长（双重保护）

    Args:
        current_price: 当前价格
        atr_daily: 日线ATR (基于24小时K线, period=14)
        atr_hourly: 小时线ATR (基于1小时K线, period=14)
        max_grids: 最大网格数量（默认100）

    Returns:
        (upper_limit, lower_limit, grid_count)
    """
    # 计算理论值
    theoretical_upper = current_price + Decimal(str(2 * atr_daily))
    theoretical_lower = current_price - Decimal(str(3 * atr_daily))

    # 确保下限至少为价格的1%（避免负值或过低）
    min_lower = current_price * Decimal('0.01')
    theoretical_lower = max(theoretical_lower, min_lower)

    # 如果ATR为0导致上下限相同,使用默认区间(±10%)
    if theoretical_upper == theoretical_lower:
        theoretical_upper = current_price * Decimal('1.10')  # +10%
        theoretical_lower = current_price * Decimal('0.90')  # -10%
        theoretical_lower = max(theoretical_lower, min_lower)

    theoretical_step = 0.5 * atr_hourly

    # 防止除零错误：如果ATR过小导致步长为0，使用价格区间的1%作为最小步长
    if theoretical_step <= 0:
        theoretical_step = float(theoretical_upper - theoretical_lower) * 0.01
        # 如果区间也是0（理论上不会发生了），则使用当前价格的0.1%作为步长
        if theoretical_step <= 0:
            theoretical_step = float(current_price) * 0.001

    theoretical_count = int((float(theoretical_upper - theoretical_lower) / theoretical_step)) + 1

    # 场景1: 无需调整（≤ max_grids）
    if theoretical_count <= max_grids:
        return theoretical_upper, theoretical_lower, theoretical_count

    # 场景2: 轻微超限（max_grids < count ≤ 150），仅调整步长
    elif theoretical_count <= 150:
        adjusted_step = float(theoretical_upper - theoretical_lower) / max_grids
        return theoretical_upper, theoretical_lower, max_grids

    # 场景3: 严重超限（> 150），同时收窄区间和调整步长
    else:
        # 第一步：收窄区间到150层的理论值
        target_range = theoretical_step * 150

        # 按原比例2:3分配上下限
        price_float = float(current_price)
        upper = Decimal(str(price_float + (2/5) * target_range))
        lower = Decimal(str(price_float - (3/5) * target_range))
        lower = max(lower, min_lower)

        # 第二步：调整步长到max_grids层
        adjusted_step = float(upper - lower) / max_grids

        return upper, lower, max_grids


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
