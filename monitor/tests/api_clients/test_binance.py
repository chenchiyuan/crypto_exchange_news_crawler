"""
Binance合约API客户端测试
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from decimal import Decimal

from monitor.api_clients.binance import BinanceFuturesClient
from monitor.models import Exchange


@pytest.fixture
def binance_client():
    """创建Binance客户端实例"""
    return BinanceFuturesClient(exchange_name='binance')


@pytest.fixture
def exchange():
    """创建交易所实例"""
    return Exchange.objects.create(
        name='Binance',
        code='binance',
        announcement_url='https://www.binance.com/en/support/announcement'
    )


@pytest.fixture
def mock_exchange_info_response():
    """Mock Binance exchangeInfo响应"""
    return {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "contractType": "PERPETUAL",
                "status": "TRADING",
                "baseAsset": "BTC",
                "quoteAsset": "USDT",
                "filters": [
                    {"minPrice": "0.01", "maxPrice": "10000000", "tickSize": "0.01"}
                ]
            },
            {
                "symbol": "ETHUSDT",
                "contractType": "PERPETUAL",
                "status": "TRADING",
                "baseAsset": "ETH",
                "quoteAsset": "USDT",
                "filters": []
            },
            {
                "symbol": "BNBUSDT",  # 无效合约类型，应该被过滤
                "contractType": "QUARTERLY",
                "status": "TRADING",
            }
        ]
    }


@pytest.fixture
def mock_ticker_response():
    """Mock Binance ticker响应"""
    return [
        {
            "symbol": "BTCUSDT",
            "bidPrice": "44000.00",
            "askPrice": "44001.00"
        },
        {
            "symbol": "ETHUSDT",
            "bidPrice": "2200.00",
            "askPrice": "2201.00"
        }
    ]


class TestBinanceFuturesClient:
    """Binance合约API客户端测试类"""

    def test_init(self, binance_client):
        """测试客户端初始化"""
        assert binance_client.exchange_name == 'binance'
        assert hasattr(binance_client, 'base_url')
        assert hasattr(binance_client, 'session')

    def test_normalize_symbol_no_change(self, binance_client):
        """测试符号标准化 (无需改变)"""
        assert binance_client._normalize_symbol("BTCUSDT") == "BTCUSDT"
        assert binance_client._normalize_symbol("ETHUSDT") == "ETHUSDT"

    def test_fetch_contracts_success(self, binance_client, mock_exchange_info_response, mock_ticker_response):
        """测试成功获取合约数据"""
        with patch('monitor.api_clients.binance.requests.Session.get') as mock_get:
            # Mock exchangeInfo 响应
            mock_exchange_info = MagicMock()
            mock_exchange_info.json.return_value = mock_exchange_info_response
            mock_exchange_info.raise_for_status.return_value = None

            # Mock ticker 响应
            mock_ticker = MagicMock()
            mock_ticker.json.return_value = mock_ticker_response
            mock_ticker.raise_for_status.return_value = None

            # 两次GET调用分别返回不同结果
            mock_get.side_effect = [mock_exchange_info, mock_ticker]

            # 调用测试方法
            contracts = binance_client.fetch_contracts()

            # 验证结果
            assert len(contracts) == 2  # 仅永续合约

            # 验证 BTC 合约
            btc_contract = next(c for c in contracts if c['symbol'] == 'BTCUSDT')
            assert btc_contract['current_price'] == Decimal('44000.50')  # 平均价格
            assert btc_contract['contract_type'] == 'perpetual'

            # 验证 ETH 合约
            eth_contract = next(c for c in contracts if c['symbol'] == 'ETHUSDT')
            assert eth_contract['current_price'] == Decimal('2200.50')  # 平均价格
            assert eth_contract['contract_type'] == 'perpetual'

    def test_fetch_contracts_empty_response(self, binance_client):
        """测试空响应处理"""
        with patch('monitor.api_clients.binance.requests.Session.get') as mock_get:
            # Mock 空响应
            mock_response = MagicMock()
            mock_response.json.side_effect = [
                {"symbols": []},  # 空合约列表
                []  # 空价格列表
            ]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            contracts = binance_client.fetch_contracts()
            assert contracts == []

    def test_fetch_contracts_api_failure(self, binance_client):
        """测试API失败处理"""
        with patch('monitor.api_clients.binance.requests.Session.get') as mock_get:
            # Mock API 异常
            mock_get.side_effect = Exception("Network error")

            with pytest.raises(Exception):
                binance_client.fetch_contracts()

    def test_fetch_contracts_partial_price_data(self, binance_client, mock_exchange_info_response):
        """测试合约有但无价格数据的处理"""
        with patch('monitor.api_clients.binance.requests.Session.get') as mock_get:
            # Mock exchangeInfo 返回所有合约
            mock_exchange_info = MagicMock()
            mock_exchange_info.json.return_value = mock_exchange_info_response
            mock_exchange_info.raise_for_status.return_value = None

            # Mock ticker 只返回部分价格
            mock_ticker = MagicMock()
            mock_ticker.json.return_value = [
                {"symbol": "BTCUSDT", "bidPrice": "44000.00", "askPrice": "44001.00"}
                # ETHUSDT 的价格缺失
            ]
            mock_ticker.raise_for_status.return_value = None

            mock_get.side_effect = [mock_exchange_info, mock_ticker]

            contracts = binance_client.fetch_contracts()

            # 只应返回有价格的合约
            assert len(contracts) == 1
            assert contracts[0]['symbol'] == 'BTCUSDT'

    def test_fetch_contracts_filter_non_perpetual(self, binance_client):
        """测试只获取永续合约的过滤"""
        mock_exchange_info = {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "contractType": "PERPETUAL",
                    "status": "TRADING",
                },
                {
                    "symbol": "ETHUSDTPERP",
                    "contractType": "PERPETUAL",
                    "status": "TRADING",
                },
                {
                    "symbol": "BTCUSDT_240628",  # 季度合约，应该被过滤
                    "contractType": "QUARTERLY",
                    "status": "TRADING",
                },
                {
                    "symbol": "ETHUSDT_240628",  # 季度合约，应该被过滤
                    "contractType": "CURRENT_QUARTER",
                    "status": "TRADING",
                }
            ]
        }

        mock_ticker = [
            {"symbol": "BTCUSDT", "bidPrice": "44000.00", "askPrice": "44001.00"},
            {"symbol": "ETHUSDTPERP", "bidPrice": "2200.00", "askPrice": "2201.00"},
            {"symbol": "BTCUSDT_240628", "bidPrice": "43500.00", "askPrice": "43501.00"},
            {"symbol": "ETHUSDT_240628", "bidPrice": "2180.00", "askPrice": "2181.00"}
        ]

        with patch('monitor.api_clients.binance.requests.Session.get') as mock_get:
            # Mock 两次调用的响应
            mock_exchange_info_response = MagicMock()
            mock_exchange_info_response.json.return_value = mock_exchange_info
            mock_exchange_info_response.raise_for_status.return_value = None

            mock_ticker_response = MagicMock()
            mock_ticker_response.json.return_value = mock_ticker
            mock_ticker_response.raise_for_status.return_value = None

            mock_get.side_effect = [mock_exchange_info_response, mock_ticker_response]

            contracts = binance_client.fetch_contracts()

            # 只应返回永续合约
            assert len(contracts) == 2
            symbols = [c['symbol'] for c in contracts]
            assert 'BTCUSDT' in symbols
            assert 'ETHUSDTPERP' in symbols
            assert 'BTCUSDT_240628' not in symbols  # 季度合约被过滤
            assert 'ETHUSDT_240628' not in symbols  # 季度合约被过滤