"""
MicrostructureMetrics 数据模型

用途: 第三维度筛选 - 资金/持仓特征 (微观结构)
关联FR: FR-016, FR-017, FR-018, FR-019, FR-020, FR-021, FR-021.1, FR-025
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import List


@dataclass
class MicrostructureMetrics:
    """
    微观结构指标数据类

    属性:
        symbol: 关联标的代码
        ovr: 持仓量/成交量比率, OI / 24h_Volume
        funding_rate: 资金费率 (%)
        annual_funding_rate: 年化资金费率 (%)
        cvd: 累积成交量增量
        cvd_roc: CVD变化率 (%), 5周期变化率
        has_cvd_divergence: CVD背离检测 (熊市背离)
    """

    symbol: str
    ovr: float
    funding_rate: Decimal
    annual_funding_rate: float
    cvd: float
    cvd_roc: float
    has_cvd_divergence: bool

    def passes_filter(self) -> bool:
        """
        微观结构筛选 (FR-018, FR-019)

        Returns:
            是否通过微观结构筛选条件
        """
        # 正资金费率检查 (FR-018): > 0.01%
        if self.funding_rate <= Decimal("0.0001"):  # 0.01%
            return False

        # OVR检查 (FR-019): 剔除高OVR (> 2.0)
        if self.ovr > 2.0:
            return False

        return True

    def calculate_micro_score(self, vdr: float = 0.0) -> float:
        """
        计算微观结构评分 I_Micro (FR-025)

        Args:
            vdr: 波动率-位移比 (用于VDR加分判断)

        Returns:
            微观结构得分 (0-1)
        """
        score = 0.5  # 基础分

        # CVD背离加分
        if self.has_cvd_divergence:
            score += 0.3

        # 温和正费率加分 (0.01% - 0.1%)
        funding_pct = float(self.funding_rate) * 100
        if 0.01 <= funding_pct <= 0.1:
            score += 0.2
        elif funding_pct > 0.1:
            # 高费率扣分 (逼空风险)
            score -= 0.2

        # 高OVR扣分
        if self.ovr > 1.5:
            score -= 0.2

        # VDR加分 (FR-025)
        if vdr > 5.0:
            score += 0.2

        # CVD_ROC异常扣分 (FR-025, FR-021.1)
        if self.cvd_roc > 50.0:
            score -= 0.3

        return max(0.0, min(1.0, score))

    @property
    def warning_flags(self) -> List[str]:
        """
        生成警告标记 (FR-032)

        Returns:
            警告标记列表
        """
        flags = []

        if self.ovr > 2.0:
            flags.append("⚠️ 高杠杆拥挤")

        if float(self.funding_rate) * 100 > 0.1:
            flags.append("⚠️ 逼空风险")

        if self.cvd_roc > 50.0:
            flags.append("⚠️ CVD异常买盘")

        return flags
