"""
GSS评分模型

用途: 计算Grid Short Score并排序标的
关联FR: FR-022至FR-030
"""

import logging
import numpy as np
from typing import List, Tuple, Optional
from decimal import Decimal

from grid_trading.models import (
    MarketSymbol,
    VolatilityMetrics,
    TrendMetrics,
    MicrostructureMetrics,
    ScreeningResult,
)

logger = logging.getLogger("grid_trading")


class ScoringModel:
    """
    GSS评分模型

    公式: GSS = w₁·Rank(NATR) + w₂·Rank(1-KER) + w₃·I_Trend + w₄·I_Micro
    """

    def __init__(self, w1: float, w2: float, w3: float, w4: float):
        """
        初始化评分模型 (FR-026, FR-027, T037)

        Args:
            w1: NATR百分位排名权重
            w2: (1-KER)百分位排名权重
            w3: 趋势评分权重
            w4: 微观结构评分权重

        Raises:
            ValueError: 权重总和≠1.0
        """
        if not np.isclose(w1 + w2 + w3 + w4, 1.0, atol=1e-6):
            raise ValueError(f"权重总和必须=1.0,当前为{w1+w2+w3+w4:.4f}")

        self.w1 = w1
        self.w2 = w2
        self.w3 = w3
        self.w4 = w4

    def calculate_gss_score(
        self,
        volatility: VolatilityMetrics,
        trend: TrendMetrics,
        microstructure: MicrostructureMetrics,
    ) -> float:
        """
        计算GSS评分 (FR-022至FR-025, T038)

        Args:
            volatility: 波动率指标
            trend: 趋势指标
            microstructure: 微观结构指标

        Returns:
            GSS得分 (0-1)
        """
        # 趋势评分 (FR-024)
        trend_score = trend.calculate_trend_score(
            norm_slope_threshold=50.0,
            ker=volatility.ker,
        )

        # 趋势否决机制 (FR-014, SC-007)
        if trend_score == 0.0:
            return 0.0

        # 微观结构评分 (FR-025)
        micro_score = microstructure.calculate_micro_score(vdr=volatility.vdr)

        # GSS公式 (FR-022)
        gss = (
            self.w1 * volatility.natr_percentile
            + self.w2 * volatility.inv_ker_percentile
            + self.w3 * trend_score
            + self.w4 * micro_score
        )

        return float(gss)

    def apply_market_cap_boost(
        self, gss: float, market_cap_rank: Optional[int]
    ) -> float:
        """
        应用市值排名加权 (FR-027.1, T039)

        效率悖论原则: 市值排名20-100的中等市值资产应用1.2倍系数

        Args:
            gss: 原始GSS得分
            market_cap_rank: 市值排名 (可选)

        Returns:
            加权后的GSS得分
        """
        if market_cap_rank is None:
            return gss

        # 市值排名20-100应用1.2倍加权
        if 20 <= market_cap_rank <= 100:
            return gss * 1.2

        return gss

    def calculate_grid_parameters(
        self, current_price: Decimal, atr_daily: float, atr_hourly: float
    ) -> Tuple[Decimal, Decimal, int]:
        """
        计算推荐网格参数 (FR-030, T040)

        公式:
            Upper Limit = Current Price + 2 × ATR_daily
            Lower Limit = Current Price - 3 × ATR_daily
            Grid Count = (Upper - Lower) / (0.5 × ATR_hourly)

        Args:
            current_price: 当前价格
            atr_daily: 日线ATR
            atr_hourly: 小时线ATR

        Returns:
            (upper_limit, lower_limit, grid_count)
        """
        from grid_trading.models import calculate_grid_parameters

        return calculate_grid_parameters(current_price, atr_daily, atr_hourly)

    def score_and_rank(
        self,
        data: List[
            Tuple[
                MarketSymbol,
                VolatilityMetrics,
                TrendMetrics,
                MicrostructureMetrics,
                float,
                float,
            ]
        ],
        top_n: int,
    ) -> List[ScreeningResult]:
        """
        评分并排序 (FR-028, FR-029, T041)

        Args:
            data: List[(MarketSymbol, VolatilityMetrics, TrendMetrics, MicrostructureMetrics, atr_daily, atr_hourly)]
            top_n: Top N数量

        Returns:
            List[ScreeningResult] (按GSS降序排序，取Top N)
        """
        logger.info("=" * 70)
        logger.info("🎯 步骤3: 加权评分与排序")
        logger.info("-" * 70)

        results = []

        for (
            market_symbol,
            volatility,
            trend,
            microstructure,
            atr_daily,
            atr_hourly,
        ) in data:
            # 计算GSS评分
            gss = self.calculate_gss_score(volatility, trend, microstructure)

            # 应用市值加权 (如果有数据)
            gss = self.apply_market_cap_boost(gss, market_symbol.market_cap_rank)

            # 跳过GSS=0的标的 (强上升趋势被否决)
            if gss == 0.0:
                continue

            # 创建筛选结果
            result = ScreeningResult.from_metrics(
                rank=0,  # 稍后排序后赋值
                symbol=market_symbol.symbol,
                current_price=market_symbol.current_price,
                volatility=volatility,
                trend=trend,
                microstructure=microstructure,
                gss_score=gss,
                atr_daily=atr_daily,
                atr_hourly=atr_hourly,
            )

            results.append(result)

        # 按GSS降序排序
        results.sort(key=lambda r: r.gss_score, reverse=True)

        # 赋值排名
        for rank, result in enumerate(results[:top_n], start=1):
            result.rank = rank

        logger.info(f"  ✓ GSS评分完成，排序Top {min(top_n, len(results))}")

        return results[:top_n]
