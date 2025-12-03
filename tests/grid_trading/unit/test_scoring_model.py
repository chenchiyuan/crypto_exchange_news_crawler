"""
scoring_model 单元测试

测试覆盖: T049
"""

import pytest
from decimal import Decimal
from grid_trading.services.scoring_model import ScoringModel
from grid_trading.models import VolatilityMetrics, TrendMetrics, MicrostructureMetrics


class TestScoringModel:
    """评分模型测试"""

    def test_weights_validation(self):
        """测试权重验证"""
        # 有效权重
        model = ScoringModel(0.2, 0.2, 0.3, 0.3)
        assert model.w1 == 0.2

        # 无效权重 (总和≠1.0)
        with pytest.raises(ValueError, match="权重总和必须=1.0"):
            ScoringModel(0.3, 0.3, 0.3, 0.3)

    def test_trend_veto_mechanism(self):
        """测试趋势否决机制 (SC-007)"""
        model = ScoringModel(0.2, 0.2, 0.3, 0.3)

        # 构造强上升趋势标的
        volatility = VolatilityMetrics(
            symbol="TEST",
            natr=3.0,
            ker=0.2,
            vdr=5.0,
            natr_percentile=0.85,
            inv_ker_percentile=0.80,
        )

        trend = TrendMetrics(
            symbol="TEST",
            norm_slope=60.0,  # 强趋势
            r_squared=0.85,  # 高拟合度
            hurst_exponent=0.45,
            z_score=1.5,
            is_strong_uptrend=True,
        )

        microstructure = MicrostructureMetrics(
            symbol="TEST",
            ovr=1.0,
            funding_rate=Decimal("0.0001"),
            annual_funding_rate=10.95,
            cvd=1000.0,
            cvd_roc=20.0,
            has_cvd_divergence=True,
        )

        gss = model.calculate_gss_score(volatility, trend, microstructure)

        # GSS应为0 (被否决)
        assert gss == 0.0

    def test_market_cap_boost(self):
        """测试市值排名加权"""
        model = ScoringModel(0.25, 0.25, 0.25, 0.25)

        base_gss = 0.8

        # 排名20-100应用1.2倍系数
        boosted_gss = model.apply_market_cap_boost(base_gss, market_cap_rank=50)
        assert boosted_gss == base_gss * 1.2

        # 排名<20或>100不应用加权
        unboosted_gss = model.apply_market_cap_boost(base_gss, market_cap_rank=10)
        assert unboosted_gss == base_gss

        # 无市值数据不应用加权
        no_boost_gss = model.apply_market_cap_boost(base_gss, market_cap_rank=None)
        assert no_boost_gss == base_gss

    def test_grid_parameters_calculation(self):
        """测试网格参数计算"""
        model = ScoringModel(0.25, 0.25, 0.25, 0.25)

        current_price = Decimal("100.0")
        atr_daily = 5.0
        atr_hourly = 1.0

        upper, lower, grid_count = model.calculate_grid_parameters(
            current_price, atr_daily, atr_hourly
        )

        # 验证公式
        assert upper == current_price + Decimal(str(2 * atr_daily))  # 110
        assert lower == current_price - Decimal(str(3 * atr_daily))  # 85
        assert grid_count > 0  # 格数应为正数
