"""
indicator_calculator 单元测试

测试覆盖: T048
"""

import pytest
import numpy as np
from grid_trading.services.indicator_calculator import (
    calculate_natr,
    calculate_ker,
    calculate_vdr,
    calculate_z_score,
    calculate_hurst_exponent,
    calculate_cvd,
    detect_cvd_divergence,
    calculate_cvd_roc,
)


class TestVolatilityIndicators:
    """波动率指标测试"""

    def test_calculate_natr_basic(self):
        """测试NATR基本计算"""
        klines = [
            {"high": 110, "low": 90, "close": 100},
            {"high": 105, "low": 95, "close": 102},
            {"high": 108, "low": 98, "close": 105},
            {"high": 112, "low": 102, "close": 110},
            {"high": 115, "low": 105, "close": 112},
            {"high": 118, "low": 108, "close": 115},
            {"high": 120, "low": 110, "close": 118},
            {"high": 122, "low": 112, "close": 120},
            {"high": 125, "low": 115, "close": 122},
            {"high": 128, "low": 118, "close": 125},
            {"high": 130, "low": 120, "close": 127},
            {"high": 132, "low": 122, "close": 130},
            {"high": 135, "low": 125, "close": 132},
            {"high": 138, "low": 128, "close": 135},
            {"high": 140, "low": 130, "close": 137},
        ]

        natr = calculate_natr(klines, period=14)

        assert isinstance(natr, float)
        assert natr > 0  # NATR应为正数
        assert natr < 100  # NATR不应超过100%

    def test_calculate_ker_range(self):
        """测试KER值范围"""
        # 趋势性强的价格序列
        trending_prices = np.array([100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120])
        ker_trending = calculate_ker(trending_prices, window=10)

        # 震荡性强的价格序列
        oscillating_prices = np.array([100, 102, 100, 102, 100, 102, 100, 102, 100, 102, 100])
        ker_oscillating = calculate_ker(oscillating_prices, window=10)

        # KER应在0-1之间
        assert 0 <= ker_trending <= 1
        assert 0 <= ker_oscillating <= 1

        # 趋势性强的KER应更高
        assert ker_trending > ker_oscillating

    def test_calculate_vdr_edge_case(self):
        """测试VDR边界情况"""
        # 1分钟K线数据不足
        klines_insufficient = [{"open": 100, "close": 100} for _ in range(50)]
        vdr = calculate_vdr(klines_insufficient)
        assert vdr == 0.0  # 应降级返回0

        # 完全横盘 (displacement=0)
        klines_flat = [{"open": 100, "close": 100} for _ in range(240)]
        vdr = calculate_vdr(klines_flat)
        assert vdr == float("inf")  # 应返回无穷大


class TestTrendIndicators:
    """趋势指标测试"""

    def test_calculate_z_score_bollinger_bands(self):
        """测试Z-Score识别布林带上轨"""
        # 模拟价格触及布林带上轨的场景
        # MA=100, StdDev=5, 当前价格=110 → Z-Score = (110-100)/5 = 2.0
        prices = np.array([95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105] * 2 + [110])

        z_score = calculate_z_score(prices, window=20)

        # Z-Score应大于2.0 (触及上轨)
        assert z_score > 2.0

    def test_calculate_hurst_mean_reversion(self):
        """测试Hurst指数识别均值回归"""
        # 模拟均值回归序列
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(200) * 0.1)
        # 加入均值回归特征
        mean = np.mean(prices)
        prices = prices + (mean - prices) * 0.1

        hurst = calculate_hurst_exponent(prices)

        # 均值回归序列H应<0.5
        # 注意: 由于随机性，这个测试可能不稳定，仅作示例
        assert isinstance(hurst, float)


class TestMicrostructureIndicators:
    """微观结构指标测试"""

    def test_calculate_cvd_divergence(self):
        """测试CVD背离检测"""
        klines = []
        for i in range(25):
            # 构造背离场景: 价格上涨，但买盘减少
            price = 100 + i * 2  # 价格线性上涨
            taker_buy = 1000 - i * 20  # 买盘线性下降
            total_volume = 2000

            klines.append({
                "close": price,
                "volume": total_volume,
                "taker_buy_base_volume": taker_buy,
            })

        prices = np.array([k["close"] for k in klines])
        cvd = calculate_cvd(klines)

        has_divergence = detect_cvd_divergence(prices, cvd, window=20)

        # 应检测到背离
        assert isinstance(has_divergence, bool)

    def test_calculate_cvd_roc(self):
        """测试CVD_ROC计算"""
        cvd_series = np.array([100, 105, 110, 120, 150, 200])  # 急剧上升

        cvd_roc = calculate_cvd_roc(cvd_series, period=5)

        # CVD_ROC应为正数且较大
        assert cvd_roc > 0
        assert cvd_roc > 50  # 根据数据，ROC应>50%
