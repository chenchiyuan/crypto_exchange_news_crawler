"""
简化评分模型 - 只基于4个核心指标

核心指标:
1. VDR - 波动率-位移比 (震荡性纯净度)
2. KER - 考夫曼效率比 (震荡vs趋势)
3. OVR - 持仓量/成交量比 (杠杆拥挤度)
4. CVD - CVD背离 (资金面信号)
"""

from typing import List, Tuple
from dataclasses import dataclass
from decimal import Decimal

from grid_trading.models import ScreeningResult, MarketSymbol
from grid_trading.models.volatility_metrics import VolatilityMetrics
from grid_trading.models.trend_metrics import TrendMetrics
from grid_trading.models.microstructure_metrics import MicrostructureMetrics


@dataclass
class SimpleScore:
    """简化评分结果"""

    symbol: str
    current_price: Decimal
    vdr: float
    ker: float
    ovr: float
    cvd_divergence: bool

    # 分项得分
    vdr_score: float
    ker_score: float
    ovr_score: float
    cvd_score: float

    # 综合指数
    composite_index: float

    # 推荐网格参数
    grid_upper_limit: Decimal
    grid_lower_limit: Decimal
    grid_count: int
    grid_step: Decimal

    # 止盈止损推荐
    take_profit_price: Decimal
    stop_loss_price: Decimal
    take_profit_pct: float
    stop_loss_pct: float

    def to_dict(self) -> dict:
        """转换为字典用于HTML渲染"""
        return {
            'symbol': self.symbol,
            'price': float(self.current_price),
            'vdr': round(self.vdr, 2),
            'ker': round(self.ker, 3),
            'ovr': round(self.ovr, 2),
            'cvd': '✓' if self.cvd_divergence else '✗',
            'vdr_score': round(self.vdr_score * 100, 1),
            'ker_score': round(self.ker_score * 100, 1),
            'ovr_score': round(self.ovr_score * 100, 1),
            'cvd_score': round(self.cvd_score * 100, 1),
            'composite_index': round(self.composite_index, 4),
            'grid_upper': float(self.grid_upper_limit),
            'grid_lower': float(self.grid_lower_limit),
            'grid_count': self.grid_count,
            'grid_step': float(self.grid_step),
            'take_profit_price': float(self.take_profit_price),
            'stop_loss_price': float(self.stop_loss_price),
            'take_profit_pct': round(self.take_profit_pct, 2),
            'stop_loss_pct': round(self.stop_loss_pct, 2),
        }


class SimpleScoring:
    """
    简化评分模型

    只基于4个核心指标计算综合指数:
    - VDR: 震荡性纯净度 (权重40%)
    - KER: 低效率波动 (权重30%)
    - OVR: 低杠杆拥挤 (权重20%)
    - CVD: 背离信号 (权重10%)
    """

    def __init__(
        self,
        vdr_weight: float = 0.40,
        ker_weight: float = 0.30,
        ovr_weight: float = 0.20,
        cvd_weight: float = 0.10,
    ):
        """
        初始化简化评分模型

        Args:
            vdr_weight: VDR权重 (默认40%)
            ker_weight: KER权重 (默认30%)
            ovr_weight: OVR权重 (默认20%)
            cvd_weight: CVD权重 (默认10%)
        """
        self.vdr_weight = vdr_weight
        self.ker_weight = ker_weight
        self.ovr_weight = ovr_weight
        self.cvd_weight = cvd_weight

        # 验证权重之和为1
        total = vdr_weight + ker_weight + ovr_weight + cvd_weight
        assert abs(total - 1.0) < 0.001, f"权重之和必须为1.0, 当前为{total}"

    def calculate_vdr_score(self, vdr: float) -> float:
        """
        计算VDR得分 (波动率-位移比)

        理想值: VDR越高越好 (震荡性越强)

        评分规则:
        - VDR >= 10: 满分 (1.0) - 完美震荡
        - 5 <= VDR < 10: 线性得分 (0.5-1.0)
        - VDR < 5: 低分 (0.0-0.5)

        Args:
            vdr: 波动率-位移比

        Returns:
            0.0-1.0得分
        """
        if vdr >= 10.0:
            return 1.0
        elif vdr >= 5.0:
            # 5-10之间线性映射到0.5-1.0
            return 0.5 + (vdr - 5.0) / 10.0
        else:
            # 0-5之间线性映射到0.0-0.5
            return vdr / 10.0

    def calculate_ker_score(self, ker: float) -> float:
        """
        计算KER得分 (考夫曼效率比)

        理想值: KER越低越好 (震荡性越强，趋势性越弱)

        评分规则:
        - KER <= 0.1: 满分 (1.0) - 极低效率，完美震荡
        - 0.1 < KER < 0.3: 线性得分 (0.5-1.0)
        - KER >= 0.3: 低分 (0.0-0.5) - 趋势性太强

        Args:
            ker: 考夫曼效率比

        Returns:
            0.0-1.0得分
        """
        if ker <= 0.1:
            return 1.0
        elif ker < 0.3:
            # 0.1-0.3之间反向映射到0.5-1.0
            return 1.0 - (ker - 0.1) * 2.5  # (0.3-0.1)^-1 = 5, 映射到0.5范围 = 2.5
        else:
            # KER >= 0.3，趋势性太强，低分
            # 0.3-1.0映射到0.5-0.0
            return max(0.0, 0.5 - (ker - 0.3) * 0.714)  # (1-0.3)^-1 * 0.5 ≈ 0.714

    def calculate_ovr_score(self, ovr: float) -> float:
        """
        计算OVR得分 (持仓量/成交量比)

        理想值: OVR适中最好 (0.5-1.5)

        评分规则:
        - 0.5 <= OVR <= 1.5: 满分 (1.0) - 杠杆健康
        - OVR < 0.5: 中等分 (0.5-1.0) - 流动性可能不足
        - 1.5 < OVR < 2.0: 中等分 (0.5-1.0) - 轻微拥挤
        - OVR >= 2.0: 低分 (0.0-0.5) - 高杠杆拥挤

        Args:
            ovr: 持仓量/成交量比

        Returns:
            0.0-1.0得分
        """
        if 0.5 <= ovr <= 1.5:
            return 1.0
        elif ovr < 0.5:
            # 0-0.5映射到0.5-1.0
            return 0.5 + ovr
        elif ovr < 2.0:
            # 1.5-2.0映射到1.0-0.5
            return 1.0 - (ovr - 1.5)
        else:
            # OVR >= 2.0，高杠杆拥挤
            # 2.0-5.0映射到0.5-0.0
            return max(0.0, 0.5 - (ovr - 2.0) / 6.0)

    def calculate_cvd_score(self, has_divergence: bool) -> float:
        """
        计算CVD得分 (CVD背离检测)

        理想值: 有熊市背离最好

        评分规则:
        - 有背离: 满分 (1.0)
        - 无背离: 基础分 (0.5)

        Args:
            has_divergence: 是否检测到CVD背离

        Returns:
            0.5或1.0得分
        """
        return 1.0 if has_divergence else 0.5

    def calculate_composite_index(
        self,
        vdr: float,
        ker: float,
        ovr: float,
        cvd_divergence: bool,
    ) -> Tuple[float, float, float, float, float]:
        """
        计算综合指数

        Args:
            vdr: 波动率-位移比
            ker: 考夫曼效率比
            ovr: 持仓量/成交量比
            cvd_divergence: 是否有CVD背离

        Returns:
            (vdr_score, ker_score, ovr_score, cvd_score, composite_index)
        """
        vdr_score = self.calculate_vdr_score(vdr)
        ker_score = self.calculate_ker_score(ker)
        ovr_score = self.calculate_ovr_score(ovr)
        cvd_score = self.calculate_cvd_score(cvd_divergence)

        composite = (
            self.vdr_weight * vdr_score
            + self.ker_weight * ker_score
            + self.ovr_weight * ovr_score
            + self.cvd_weight * cvd_score
        )

        return vdr_score, ker_score, ovr_score, cvd_score, composite

    def score_and_rank(
        self,
        indicators_data: List[Tuple[MarketSymbol, VolatilityMetrics, TrendMetrics, MicrostructureMetrics, float, float]]
    ) -> List[SimpleScore]:
        """
        对所有标的评分并排序

        Args:
            indicators_data: 包含三维指标的列表

        Returns:
            按综合指数降序排列的SimpleScore列表
        """
        results = []

        for market_symbol, vol, trend, micro, atr_daily, atr_hourly in indicators_data:
            # 计算分项得分和综合指数
            vdr_score, ker_score, ovr_score, cvd_score, composite = self.calculate_composite_index(
                vdr=vol.vdr,
                ker=vol.ker,
                ovr=micro.ovr,
                cvd_divergence=micro.has_cvd_divergence,
            )

            # 计算网格参数
            from grid_trading.models.screening_result import calculate_grid_parameters
            upper, lower, grid_count = calculate_grid_parameters(
                market_symbol.current_price, atr_daily, atr_hourly
            )

            # 计算网格步长
            grid_step = Decimal(str(0.5 * atr_hourly))

            # 计算止盈止损（做空网格）
            # 做空策略：止损=网格上限（价格突破上限），止盈=网格下限（价格触及下限）
            stop_loss_price = upper
            take_profit_price = lower

            stop_loss_pct = float((stop_loss_price - market_symbol.current_price) / market_symbol.current_price * 100)
            take_profit_pct = float((market_symbol.current_price - take_profit_price) / market_symbol.current_price * 100)

            results.append(
                SimpleScore(
                    symbol=market_symbol.symbol,
                    current_price=market_symbol.current_price,
                    vdr=vol.vdr,
                    ker=vol.ker,
                    ovr=micro.ovr,
                    cvd_divergence=micro.has_cvd_divergence,
                    vdr_score=vdr_score,
                    ker_score=ker_score,
                    ovr_score=ovr_score,
                    cvd_score=cvd_score,
                    composite_index=composite,
                    grid_upper_limit=upper,
                    grid_lower_limit=lower,
                    grid_count=grid_count,
                    grid_step=grid_step,
                    take_profit_price=take_profit_price,
                    stop_loss_price=stop_loss_price,
                    take_profit_pct=take_profit_pct,
                    stop_loss_pct=stop_loss_pct,
                )
            )

        # 按综合指数降序排序
        results.sort(key=lambda x: x.composite_index, reverse=True)

        return results
