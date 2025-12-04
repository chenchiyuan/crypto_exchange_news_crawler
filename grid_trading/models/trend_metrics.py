"""
TrendMetrics 数据模型

用途: 第二维度筛选 - 趋势特征(负面滤网)
关联FR: FR-011, FR-012, FR-013, FR-014, FR-015, FR-015.1, FR-015.2, FR-024
"""

from dataclasses import dataclass
from typing import List


@dataclass
class TrendMetrics:
    """
    趋势指标数据类

    属性:
        symbol: 关联标的代码
        norm_slope: 标准化斜率, (slope / Close_t) × 10000
        r_squared: 线性拟合优度 (判定系数)
        hurst_exponent: 赫斯特指数, H < 0.5 表示均值回归
        z_score: 价格Z-Score, (Close - MA_20) / StdDev_20
        is_strong_uptrend: 强上升趋势标记
        ma99_slope: MA(99)斜率 (标准化)
        ma20_slope: MA(20)斜率 (标准化)
    """

    symbol: str
    norm_slope: float
    r_squared: float
    hurst_exponent: float
    z_score: float
    is_strong_uptrend: bool
    ma99_slope: float = 0.0  # EMA(99)斜率 (标准化)
    ma20_slope: float = 0.0  # EMA(20)斜率 (标准化)

    def passes_filter(self) -> bool:
        """
        趋势筛选 (FR-013)

        Returns:
            是否通过趋势筛选条件 (H < 0.5, 反持久性)
        """
        if self.hurst_exponent >= 0.5:
            return False
        return True

    def calculate_trend_score(
        self, norm_slope_threshold: float = 50.0, ker: float = 0.0
    ) -> float:
        """
        计算趋势评分 I_Trend (FR-024)

        Args:
            norm_slope_threshold: 强趋势阈值 (默认50.0)
            ker: 考夫曼效率比 (用于Z-Score加分判断)

        Returns:
            趋势得分 (0-1)
        """
        # 否决机制 (FR-014): 强上升趋势 GSS归零
        if self.norm_slope > norm_slope_threshold and self.r_squared > 0.8:
            return 0.0

        # 水平震荡优选 (FR-015)
        if abs(self.norm_slope) < 5.0:
            base_score = 1.0
        else:
            # 斜率惩罚
            base_score = max(0.0, 1.0 - abs(self.norm_slope) / 100.0)

        # Hurst加分 (FR-024): H < 0.5 时加分
        if self.hurst_exponent < 0.5:
            hurst_bonus = (0.5 - self.hurst_exponent) * 0.5
        else:
            hurst_bonus = 0.0

        # Z-Score假突破加分 (FR-024, FR-015.2)
        z_score_bonus = 0.0
        if self.z_score > 2.0 and ker < 0.3:
            z_score_bonus = 0.2  # 假突破优势位置

        return min(1.0, base_score + hurst_bonus + z_score_bonus)

    @property
    def warning_flags(self) -> List[str]:
        """
        生成优势标记 (FR-032)

        Returns:
            优势标记列表
        """
        flags = []
        if self.z_score > 2.0:
            flags.append("✓ 假突破优势")
        return flags
