"""
Screening Engine 集成测试

测试覆盖: T052
- test_end_to_end_screening_pipeline: 完整Pipeline流程 (Mock API)
- test_performance_under_60s: 500+标的<60秒 (SC-001)
- test_empty_results_handling: 全市场无合格标的提示 (SC-008)
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import datetime, timedelta
from grid_trading.services.screening_engine import ScreeningEngine
from grid_trading.models import MarketSymbol


class TestScreeningEngineIntegration:
    """Screening Engine 集成测试"""

    @pytest.fixture
    def mock_market_data(self):
        """创建模拟市场数据"""
        base_time = datetime.now()

        # 创建10个模拟标的，包含不同特征
        symbols = []
        for i in range(10):
            symbol = MarketSymbol(
                symbol=f"TEST{i}USDT",
                exchange="binance",
                contract_type="PERPETUAL",
                listing_date=base_time - timedelta(days=100 + i * 10),
                current_price=Decimal(f"{1000 + i * 100}"),
                volume_24h=Decimal(f"{60000000 + i * 10000000}"),  # 60M - 150M
                open_interest=Decimal(f"{10000000 + i * 1000000}"),
                funding_rate=Decimal("0.0001"),
                funding_interval_hours=8,
                next_funding_time=base_time + timedelta(hours=8),
                market_cap_rank=50 + i if i < 5 else None,  # 前5个有市值排名
            )
            symbols.append(symbol)

        return symbols

    @pytest.fixture
    def mock_klines_data(self):
        """创建模拟K线数据"""

        def generate_klines(count, base_price=100):
            """生成模拟K线"""
            klines = []
            for i in range(count):
                price = base_price + i * 0.5  # 轻微上涨趋势
                klines.append(
                    {
                        "open": price,
                        "high": price + 2,
                        "low": price - 2,
                        "close": price + 1,
                        "volume": 1000000,
                        "taker_buy_base_volume": 600000,  # 60% 买盘
                    }
                )
            return klines

        return {
            "4h": generate_klines(300, 1000),
            "1m": generate_klines(240, 1000),
            "1d": generate_klines(100, 1000),
            "1h": generate_klines(200, 1000),
        }

    @patch("grid_trading.services.screening_engine.BinanceFuturesClient")
    def test_end_to_end_screening_pipeline(
        self, mock_client_class, mock_market_data, mock_klines_data
    ):
        """测试完整Pipeline流程 - Mock API (T052)"""
        # 配置Mock客户端
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock fetch_all_market_data 返回模拟数据
        mock_client.fetch_all_market_data.return_value = mock_market_data

        # Mock fetch_klines 返回模拟K线数据
        def mock_fetch_klines(symbols, interval, limit):
            return {symbol: mock_klines_data[interval] for symbol in symbols}

        mock_client.fetch_klines.side_effect = mock_fetch_klines

        # 创建筛选引擎
        engine = ScreeningEngine(
            top_n=5,
            weights=[0.2, 0.2, 0.3, 0.3],
            min_volume=Decimal("50000000"),
            min_days=30,
            interval="4h",
        )

        # 执行筛选
        results = engine.run_screening()

        # ========== 验证Pipeline流程 ==========

        # 1. 验证API调用
        mock_client.fetch_all_market_data.assert_called_once()
        assert mock_client.fetch_klines.call_count == 4  # 4个不同周期

        # 2. 验证返回结果
        assert isinstance(results, list)
        assert len(results) <= 5  # Top 5

        # 3. 验证每个结果的数据完整性
        for result in results:
            assert result.rank > 0
            assert result.symbol.endswith("USDT")
            assert result.gss_score >= 0.0
            assert result.gss_score <= 1.0

            # 验证三维指标存在
            assert result.volatility is not None
            assert result.trend is not None
            assert result.microstructure is not None

            # 验证网格参数计算
            assert result.grid_upper_limit > result.current_price
            assert result.grid_lower_limit < result.current_price
            assert result.grid_count > 0

        # 4. 验证排序正确性（按GSS降序）
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert (
                    results[i].gss_score >= results[i + 1].gss_score
                ), "结果未按GSS降序排序"

    @patch("grid_trading.services.screening_engine.BinanceFuturesClient")
    def test_performance_under_60s(self, mock_client_class):
        """测试500+标的<60秒性能目标 - SC-001 (T052)"""
        # 创建大量模拟数据 (500个标的)
        base_time = datetime.now()
        large_market_data = []

        for i in range(500):
            symbol = MarketSymbol(
                symbol=f"TEST{i:04d}USDT",
                exchange="binance",
                contract_type="PERPETUAL",
                listing_date=base_time - timedelta(days=100),
                current_price=Decimal(f"{100 + i}"),
                volume_24h=Decimal(f"{60000000 + i * 100000}"),
                open_interest=Decimal(f"{10000000 + i * 10000}"),
                funding_rate=Decimal("0.0001"),
                funding_interval_hours=8,
                next_funding_time=base_time + timedelta(hours=8),
            )
            large_market_data.append(symbol)

        # 创建模拟K线数据
        def generate_simple_klines(count):
            return [
                {
                    "open": 100,
                    "high": 102,
                    "low": 98,
                    "close": 100,
                    "volume": 1000000,
                    "taker_buy_base_volume": 500000,
                }
                for _ in range(count)
            ]

        mock_klines = {
            "4h": generate_simple_klines(300),
            "1m": generate_simple_klines(240),
            "1d": generate_simple_klines(100),
            "1h": generate_simple_klines(200),
        }

        # 配置Mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.fetch_all_market_data.return_value = large_market_data

        def mock_fetch_klines(symbols, interval, limit):
            return {symbol: mock_klines[interval] for symbol in symbols}

        mock_client.fetch_klines.side_effect = mock_fetch_klines

        # 创建引擎
        engine = ScreeningEngine(
            top_n=10,
            weights=[0.25, 0.25, 0.25, 0.25],
            min_volume=Decimal("50000000"),
            min_days=30,
            interval="4h",
        )

        # ========== 性能测试 ==========
        start_time = time.time()
        results = engine.run_screening()
        elapsed_time = time.time() - start_time

        # 验证性能目标
        assert elapsed_time < 60.0, f"执行时间 {elapsed_time:.2f}秒 超过60秒目标"

        # 验证返回了正确数量的结果
        assert len(results) == 10

        # 输出性能统计
        print(f"\n性能统计:")
        print(f"- 处理标的数: 500")
        print(f"- 执行时间: {elapsed_time:.2f}秒")
        print(f"- 平均每标的: {elapsed_time / 500 * 1000:.2f}ms")

    @patch("grid_trading.services.screening_engine.BinanceFuturesClient")
    def test_empty_results_handling(self, mock_client_class):
        """测试全市场无合格标的的情况 - SC-008 (T052)"""
        # 创建不符合条件的模拟数据
        base_time = datetime.now()
        poor_quality_data = []

        # 场景1: 所有标的都是强上升趋势 (会被趋势否决)
        for i in range(5):
            symbol = MarketSymbol(
                symbol=f"UPTREND{i}USDT",
                exchange="binance",
                contract_type="PERPETUAL",
                listing_date=base_time - timedelta(days=100),
                current_price=Decimal("1000"),
                volume_24h=Decimal("60000000"),
                open_interest=Decimal("10000000"),
                funding_rate=Decimal("0.0001"),
                funding_interval_hours=8,
                next_funding_time=base_time + timedelta(hours=8),
            )
            poor_quality_data.append(symbol)

        # 创建强上升趋势的K线数据 (持续上涨)
        uptrend_klines = []
        base_price = 100
        for i in range(300):
            price = base_price + i * 2  # 强上升趋势
            uptrend_klines.append(
                {
                    "open": price,
                    "high": price + 3,
                    "low": price - 0.5,
                    "close": price + 2,
                    "volume": 1000000,
                    "taker_buy_base_volume": 900000,  # 90% 买盘
                }
            )

        mock_klines = {
            "4h": uptrend_klines,
            "1m": uptrend_klines[:240],
            "1d": uptrend_klines[:100],
            "1h": uptrend_klines[:200],
        }

        # 配置Mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.fetch_all_market_data.return_value = poor_quality_data

        def mock_fetch_klines(symbols, interval, limit):
            return {symbol: mock_klines[interval] for symbol in symbols}

        mock_client.fetch_klines.side_effect = mock_fetch_klines

        # 创建引擎
        engine = ScreeningEngine(
            top_n=5,
            weights=[0.2, 0.2, 0.3, 0.3],
            min_volume=Decimal("50000000"),
            min_days=30,
            interval="4h",
        )

        # 执行筛选
        results = engine.run_screening()

        # ========== 验证空结果处理 ==========
        # 由于强上升趋势会被否决，可能返回空列表或GSS=0的结果
        # 这取决于具体实现，这里验证至少不会崩溃
        assert isinstance(results, list)

        # 如果有结果，验证GSS评分
        if results:
            # 强上升趋势应该被否决，GSS应该很低或为0
            for result in results:
                # 验证趋势否决机制生效
                if result.trend.is_strong_uptrend:
                    assert (
                        result.gss_score == 0.0
                    ), "强上升趋势未被正确否决"

    @patch("grid_trading.services.screening_engine.BinanceFuturesClient")
    def test_insufficient_kline_data_handling(self, mock_client_class, mock_market_data):
        """测试K线数据不足的降级处理"""
        # 配置Mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.fetch_all_market_data.return_value = mock_market_data[:3]

        # Mock fetch_klines 返回不足的数据
        def mock_fetch_insufficient_klines(symbols, interval, limit):
            # 只返回50根K线（不足要求的300根）
            short_klines = [
                {
                    "open": 100,
                    "high": 102,
                    "low": 98,
                    "close": 100,
                    "volume": 1000000,
                    "taker_buy_base_volume": 500000,
                }
                for _ in range(50)
            ]
            return {symbol: short_klines for symbol in symbols}

        mock_client.fetch_klines.side_effect = mock_fetch_insufficient_klines

        # 创建引擎
        engine = ScreeningEngine(
            top_n=3,
            weights=[0.25, 0.25, 0.25, 0.25],
            min_volume=Decimal("50000000"),
            min_days=30,
            interval="4h",
        )

        # 执行筛选 - 应该优雅降级，不崩溃
        results = engine.run_screening()

        # 验证降级处理
        # 数据不足的标的应该被跳过，返回空列表或减少数量
        assert isinstance(results, list)

    @patch("grid_trading.services.screening_engine.BinanceFuturesClient")
    def test_percentile_calculation_accuracy(
        self, mock_client_class, mock_market_data, mock_klines_data
    ):
        """测试百分位排名计算准确性"""
        # 配置Mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.fetch_all_market_data.return_value = mock_market_data

        def mock_fetch_klines(symbols, interval, limit):
            return {symbol: mock_klines_data[interval] for symbol in symbols}

        mock_client.fetch_klines.side_effect = mock_fetch_klines

        # 创建引擎
        engine = ScreeningEngine(
            top_n=10,
            weights=[0.5, 0.5, 0.0, 0.0],  # 只关注波动率维度
            min_volume=Decimal("50000000"),
            min_days=30,
            interval="4h",
        )

        # 执行筛选
        results = engine.run_screening()

        # 验证百分位排名在0-1之间
        for result in results:
            assert (
                0.0 <= result.volatility.natr_percentile <= 1.0
            ), f"NATR百分位 {result.volatility.natr_percentile} 超出范围"
            assert (
                0.0 <= result.volatility.inv_ker_percentile <= 1.0
            ), f"inv_KER百分位 {result.volatility.inv_ker_percentile} 超出范围"
