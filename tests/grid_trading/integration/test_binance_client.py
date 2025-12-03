"""
Binance Futures Client 集成测试

测试覆盖: T051
- test_fetch_all_market_data_success: 真实API调用成功
- test_api_rate_limit_retry: 429错误重试机制
- test_initial_filter_logic: 初筛条件验证
"""

import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import datetime, timedelta
from grid_trading.services.binance_futures_client import BinanceFuturesClient
from requests.exceptions import HTTPError


class TestBinanceFuturesClientIntegration:
    """Binance Futures Client 集成测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return BinanceFuturesClient()

    def test_fetch_exchange_info_success(self, client):
        """测试获取交易所信息 - 真实API调用"""
        result = client.fetch_exchange_info()

        # 验证返回数据结构
        assert isinstance(result, list)
        assert len(result) > 0

        # 验证第一个合约数据包含必要字段
        first_contract = result[0]
        assert "symbol" in first_contract
        assert "contractType" in first_contract
        assert "onboardDate" in first_contract
        assert first_contract["contractType"] == "PERPETUAL"
        assert first_contract["symbol"].endswith("USDT")

    def test_fetch_24h_ticker_success(self, client):
        """测试获取24小时行情 - 真实API调用"""
        result = client.fetch_24h_ticker()

        # 验证返回数据结构
        assert isinstance(result, dict)
        assert len(result) > 0

        # 验证数据包含必要字段
        first_symbol = next(iter(result.keys()))
        ticker_data = result[first_symbol]
        assert "volume" in ticker_data
        assert "lastPrice" in ticker_data
        assert float(ticker_data["volume"]) >= 0
        assert float(ticker_data["lastPrice"]) > 0

    def test_fetch_funding_rate_success(self, client):
        """测试获取资金费率 - 真实API调用"""
        result = client.fetch_funding_rate()

        # 验证返回数据结构
        assert isinstance(result, dict)
        assert len(result) > 0

        # 验证数据包含必要字段
        first_symbol = next(iter(result.keys()))
        funding_data = result[first_symbol]
        assert "lastFundingRate" in funding_data
        assert "nextFundingTime" in funding_data
        assert isinstance(funding_data["lastFundingRate"], str)

    def test_fetch_all_market_data_success(self, client):
        """测试获取所有市场数据 - 真实API调用 (T051)"""
        # 使用较低的阈值以确保能获取到数据
        min_volume = Decimal("10000000")  # 10M USDT
        min_days = 7  # 7天

        result = client.fetch_all_market_data(min_volume, min_days)

        # 验证返回数据
        assert isinstance(result, list)
        # 至少应该有一些符合条件的标的
        assert len(result) > 0

        # 验证每个标的都符合初筛条件
        for market_symbol in result:
            assert market_symbol.volume_24h >= min_volume
            days_since_listing = (datetime.now() - market_symbol.listing_date).days
            assert days_since_listing >= min_days

            # 验证数据完整性
            assert market_symbol.symbol.endswith("USDT")
            assert market_symbol.current_price > Decimal("0")
            assert market_symbol.volume_24h > Decimal("0")

    def test_initial_filter_logic(self, client):
        """测试初筛逻辑 - 使用严格条件验证过滤 (T051)"""
        # 使用严格条件
        min_volume = Decimal("100000000")  # 100M USDT (高流动性阈值)
        min_days = 90  # 90天 (长时间上市)

        result = client.fetch_all_market_data(min_volume, min_days)

        # 验证所有返回的标的都满足条件
        for market_symbol in result:
            # 流动性检查
            assert (
                market_symbol.volume_24h >= min_volume
            ), f"{market_symbol.symbol} volume {market_symbol.volume_24h} < {min_volume}"

            # 上市天数检查
            days_since_listing = (datetime.now() - market_symbol.listing_date).days
            assert (
                days_since_listing >= min_days
            ), f"{market_symbol.symbol} listed {days_since_listing} days < {min_days}"

    @patch("grid_trading.services.binance_futures_client.requests.get")
    def test_api_rate_limit_retry(self, mock_get, client):
        """测试429错误重试机制 - Mock API (T051)"""
        # 模拟前两次返回429错误，第三次成功
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.raise_for_status.side_effect = HTTPError(
            response=mock_response_429
        )

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "contractType": "PERPETUAL",
                    "onboardDate": int(
                        (datetime.now() - timedelta(days=100)).timestamp() * 1000
                    ),
                }
            ]
        }

        # 前两次429，第三次成功
        mock_get.side_effect = [
            mock_response_429,
            mock_response_429,
            mock_response_success,
        ]

        # 执行调用 - 应该在第三次成功
        result = client.fetch_exchange_info()

        # 验证重试了3次
        assert mock_get.call_count == 3

        # 验证返回了正确的数据
        assert len(result) == 1
        assert result[0]["symbol"] == "BTCUSDT"

    @patch("grid_trading.services.binance_futures_client.requests.get")
    def test_api_rate_limit_exhausted(self, mock_get, client):
        """测试429错误重试次数耗尽 - Mock API"""
        # 模拟始终返回429错误
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.raise_for_status.side_effect = HTTPError(
            response=mock_response_429
        )
        mock_get.return_value = mock_response_429

        # 应该在最大重试次数后抛出异常
        with pytest.raises(HTTPError):
            client.fetch_exchange_info()

        # 验证重试了最大次数 (3次)
        assert mock_get.call_count == 3

    def test_fetch_klines_insufficient_data(self, client):
        """测试K线数据不足的边界情况"""
        # 尝试获取一个可能数据不足的新上市标的
        # 这个测试可能会失败，因为Binance通常有足够的K线数据
        # 但它验证了我们的错误处理逻辑

        # 获取所有标的
        all_symbols = client.fetch_exchange_info()

        # 找到最近上市的标的
        recent_symbols = sorted(all_symbols, key=lambda x: x["onboardDate"], reverse=True)[
            :5
        ]

        if recent_symbols:
            symbols_list = [s["symbol"] for s in recent_symbols]

            # 尝试获取K线，使用非常大的limit
            result = client.fetch_klines(symbols_list, interval="4h", limit=1000)

            # 验证返回的数据结构
            assert isinstance(result, dict)

            # 验证每个标的的K线数据
            for symbol in symbols_list:
                if symbol in result:
                    klines = result[symbol]
                    # 如果返回了数据，应该是列表
                    assert isinstance(klines, list)
                # 如果数据不足，可能不在result中（被跳过）
