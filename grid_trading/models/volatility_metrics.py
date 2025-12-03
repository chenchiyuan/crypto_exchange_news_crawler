"""
VolatilityMetrics 数据模型

用途: 第一维度筛选 - 波动率特征
关联FR: FR-005, FR-006, FR-007, FR-008, FR-009, FR-010, FR-010.1, FR-010.2
"""

from dataclasses import dataclass
from typing import List


@dataclass
class VolatilityMetrics:
    """
    波动率指标数据类

    属性:
        symbol: 关联标的代码
        natr: 归一化ATR (%), ATR(14) / Close × 100
        ker: 考夫曼效率比, Direction / Volatility
        vdr: 波动率-位移比, CIV / Displacement
        amplitude_sum_15m: 最近100根15分钟K线振幅累计
        natr_percentile: NATR百分位排名 (0-1)
        inv_ker_percentile: (1-KER)百分位排名 (0-1)
    """

    symbol: str
    natr: float
    ker: float
    vdr: float
    amplitude_sum_15m: float
    natr_percentile: float
    inv_ker_percentile: float

    def passes_filter(self) -> bool:
        """
        波动率筛选 (FR-007, FR-008, FR-009)

        Returns:
            是否通过波动率筛选条件
        """
        # NATR范围检查 (FR-009): 剔除静默期和极端波动
        if not (1.0 <= self.natr <= 10.0):
            return False

        # KER效率检查 (FR-008): 低效率波动，均值回归特征
        if self.ker >= 0.3:
            return False

        # NATR分位数检查 (FR-007): 前20%分位
        if self.natr_percentile < 0.80:
            return False

        return True

    @property
    def warning_flags(self) -> List[str]:
        """
        生成警告标记和优势标记 (FR-032, FR-010.2)

        Returns:
            警告/优势标记列表
        """
        flags = []

        # 警告标记
        if self.natr > 10.0:
            flags.append("⚠️ 极端波动")
        if self.natr < 1.0:
            flags.append("⚠️ 静默期")

        # 优势标记 (FR-010.2)
        if self.vdr > 10.0:
            flags.append("✓ 高VDR - 完美震荡")

        return flags
