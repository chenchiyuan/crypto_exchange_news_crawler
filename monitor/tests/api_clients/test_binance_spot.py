"""
Binance现货API客户端测试

测试BinanceSpotClient的功能，包括：
1. 现货交易对数据获取
2. 现货符号标准化
3. 价格数据获取
4. 异常路径处理
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

from monitor.api_clients.binance_spot import (
    BinanceSpotClient,
    validate_binance_spot_response_format,
    get_binance_test_spot_contract
)
from monitor.models import Exchange


@pytest.fixture
def spot_client():
    """创建Binance现货客户端实例"""
    return BinanceSpotClient(exchange_name='binance')


@pytest.fixture
def exchange():
    """创建交易所实例"""
    return Exchange.objects.create(
        name='Binance',
        code='binance',
        announcement_url='https://www.binance.com/en/support/announcement'
    )


@pytest.fixture
def mock_spot_exchange_info_response():
    """Mock Binance现货exchangeInfo响应"""
    return {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "status": "TRADING",
                "baseAsset": "BTC",
                "quoteAsset": "USDT",
                "isSpotTradingAllowed": True,
                "filters": []
            },
            {
                "symbol": "ETHUSDT",
                "status": "TRADING",
                "baseAsset": "ETH",
                "quoteAsset": "USDT",
                "isSpotTradingAllowed": True,
                "filters": []
            },
            {
                "symbol": "BNBUSDT",
                "status": "TRADING",
                "baseAsset": "BNB",
                "quoteAsset": "USDT",
                "isSpotTradingAllowed": True,
                "filters": []
            },
            {
                "symbol": "ADAUSDT",
                "status": "BREAK",  # 非交易状态，应该被过滤
                "baseAsset": "ADA",
                "quoteAsset": "USDT",
                "isSpotTradingAllowed": True,
                "filters": []
            },
            {
                "symbol": "BTCBUSD",  # 非USDT本位，应该被过滤
                "status": "TRADING",
                "baseAsset": "BTC",
                "quoteAsset": "BUSD",
                "isSpotTradingAllowed": True,
                "filters": []
            }
        ]
    }


@pytest.fixture
def mock_spot_ticker_response():
    """Mock Binance现货ticker响应"""
    return [
        {"symbol": "BTCUSDT", "price": "50000.00"},
        {"symbol": "ETHUSDT", "price": "3000.00"},
        {"symbol": "BNBUSDT", "price": "300.00"}
    ]


class TestBinanceSpotClient:
    """Binance现货API客户端测试类"""

    def test_init(self, spot_client):
        """测试客户端初始化"""
        assert spot_client.exchange_name == 'binance'
        assert hasattr(spot_client, 'base_url')
        assert hasattr(spot_client, 'session')
        assert spot_client.base_url == 'https://api.binance.com'

    def test_spot_config_property(self, spot_client):
        """测试现货API端点配置"""
        config = spot_client._spot_config
        assert 'exchange_info' in config
        assert 'ticker' in config
        assert config['exchange_info'] == '/api/v3/exchangeInfo'
        assert config['ticker'] == '/api/v3/ticker/price'

    def test_normalize_symbol_usdt_pairs(self, spot_client):
        """测试现货符号标准化 - USDT交易对"""
        assert spot_client._normalize_symbol("BTCUSDT") == "BTC/USDT"
        assert spot_client._normalize_symbol("ETHUSDT") == "ETH/USDT"
        assert spot_client._normalize_symbol("BNBUSDT") == "BNB/USDT"
        assert spot_client._normalize_symbol("ADAUSDT") == "ADA/USDT"

    def test_normalize_symbol_other_quote_assets(self, spot_client):
        """测试现货符号标准化 - 其他计价货币"""
        assert spot_client._normalize_symbol("BTCBUSD") == "BTC/BUSD"
        assert spot_client._normalize_symbol("ETHBTC") == "ETH/BTC"
        assert spot_client._normalize_symbol("ADAETH") == "ADA/ETH"
        assert spot_client._normalize_symbol("BNBBNB") == "BNB/BNB"

    def test_normalize_symbol_invalid_format(self, spot_client):
        """测试现货符号标准化 - 无效格式"""
        with pytest.raises(ValueError, match="无法识别的现货符号格式"):
            spot_client._normalize_symbol("INVALID")

        with pytest.raises(ValueError, match="无法识别的现货符号格式"):
            spot_client._normalize_symbol("BTC")

        with pytest.raises(ValueError, match="符号不能为空"):
            spot_client._normalize_symbol("")

    def test_fetch_contracts_success(
        self,
        spot_client,
        mock_spot_exchange_info_response,
        mock_spot_ticker_response
    ):
        """测试成功获取现货交易对数据"""
        with patch('monitor.api_clients.binance_spot.requests.Session.get') as mock_get:
            # Mock exchangeInfo 响应
            mock_exchange_info = MagicMock()
            mock_exchange_info.json.return_value = mock_spot_exchange_info_response
            mock_exchange_info.raise_for_status.return_value = None

            # Mock ticker 响应
            mock_ticker = MagicMock()
            mock_ticker.json.return_value = mock_spot_ticker_response
            mock_ticker.raise_for_status.return_value = None

            # 设置两次API调用的响应
            mock_get.side_effect = [mock_exchange_info, mock_ticker]

            # 调用fetch_contracts
            contracts = spot_client.fetch_contracts()

            # 验证结果
            assert len(contracts) == 3  # 只有3个活跃的USDT交易对
            assert validate_binance_spot_response_format(contracts)

            # 验证第一个交易对
            btc_contract = next(c for c in contracts if c['symbol'] == 'BTC/USDT')
            assert btc_contract['current_price'] == Decimal('50000.00')
            assert btc_contract['contract_type'] == 'spot'
            assert btc_contract['exchange'] == 'binance'
            assert btc_contract['details']['base_symbol'] == 'BTC'
            assert btc_contract['details']['quote_symbol'] == 'USDT'

            # 验证eth交易对
            eth_contract = next(c for c in contracts if c['symbol'] == 'ETH/USDT')
            assert eth_contract['current_price'] == Decimal('3000.00')

            # 验证bnb交易对
            bnb_contract = next(c for c in contracts if c['symbol'] == 'BNB/USDT')
            assert bnb_contract['current_price'] == Decimal('300.00')

    def test_fetch_contracts_no_symbols(self, spot_client):
        """测试获取合约 - 响应中无symbols字段"""
        with patch('monitor.api_clients.binance_spot.requests.Session.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {}  # 没有symbols字段
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            contracts = spot_client.fetch_contracts()
            assert contracts == []

    def test_fetch_contracts_no_trading_pairs(self, spot_client):
        """测试获取合约 - 没有活跃交易对"""
        with patch('monitor.api_clients.binance_spot.requests.Session.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "symbols": [
                    {
                        "symbol": "INACTIVEUSDT",
                        "status": "BREAK",
                        "baseAsset": "INACTIVE",
                        "quoteAsset": "USDT",
                        "isSpotTradingAllowed": True
                    }
                ]
            }
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            contracts = spot_client.fetch_contracts()
            assert contracts == []

    def test_fetch_contracts_no_prices(self, spot_client, mock_spot_exchange_info_response):
        """测试获取合约 - 无法获取价格数据"""
        with patch('monitor.api_clients.binance_spot.requests.Session.get') as mock_get:
            # Mock exchangeInfo 响应
            mock_exchange_info = MagicMock()
            mock_exchange_info.json.return_value = mock_spot_exchange_info_response
            mock_exchange_info.raise_for_status.return_value = None

            # Mock ticker 响应 - 空列表
            mock_ticker = MagicMock()
            mock_ticker.json.return_value = []
            mock_ticker.raise_for_status.return_value = None

            # 设置第一次调用返回exchangeInfo，第二次返回空ticker
            mock_get.side_effect = [mock_exchange_info, mock_ticker]

            contracts = spot_client.fetch_contracts()
            assert contracts == []

    def test_fetch_current_prices_success(self, spot_client, mock_spot_ticker_response):
        """测试成功获取价格数据"""
        with patch('monitor.api_clients.binance_spot.requests.Session.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_spot_ticker_response
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
            prices = spot_client._fetch_current_prices(symbols)

            assert len(prices) == 3
            assert prices["BTCUSDT"] == Decimal('50000.00')
            assert prices["ETHUSDT"] == Decimal('3000.00')
            assert prices["BNBUSDT"] == Decimal('300.00')

    def test_fetch_current_prices_filter(self, spot_client):
        """测试价格获取 - 过滤不需要的符号"""
        with patch('monitor.api_clients.binance_spot.requests.Session.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = [
                {"symbol": "BTCUSDT", "price": "50000.00"},
                {"symbol": "ETHUSDT", "price": "3000.00"},
                {"symbol": "UNWANTED", "price": "100.00"}  # 不在symbols列表中
            ]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            symbols = ["BTCUSDT", "ETHUSDT"]
            prices = spot_client._fetch_current_prices(symbols)

            # 只应该返回请求的符号
            assert len(prices) == 2
            assert "UNWANTED" not in prices

    def test_fetch_current_prices_invalid_price(self, spot_client):
        """测试价格获取 - 无效价格处理"""
        with patch('monitor.api_clients.binance_spot.requests.Session.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = [
                {"symbol": "BTCUSDT", "price": "invalid"},
                {"symbol": "ETHUSDT", "price": "3000.00"}
            ]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            symbols = ["BTCUSDT", "ETHUSDT"]
            prices = spot_client._fetch_current_prices(symbols)

            # 无效价格应该被跳过
            assert len(prices) == 1
            assert "ETHUSDT" in prices
            assert "BTCUSDT" not in prices

    def test_build_standardized_contracts(self, spot_client):
        """测试构建标准化交易对数据"""
        raw_symbols = [
            {
                "symbol": "BTCUSDT",
                "baseAsset": "BTC",
                "quoteAsset": "USDT"
            },
            {
                "symbol": "ETHUSDT",
                "baseAsset": "ETH",
                "quoteAsset": "USDT"
            }
        ]

        prices = {
            "BTCUSDT": Decimal('50000.00'),
            "ETHUSDT": Decimal('3000.00')
        }

        contracts = spot_client._build_standardized_contracts(raw_symbols, prices)

        assert len(contracts) == 2

        # 验证第一个
        btc_contract = contracts[0]
        assert btc_contract['symbol'] == 'BTC/USDT'
        assert btc_contract['current_price'] == Decimal('50000.00')
        assert btc_contract['contract_type'] == 'spot'
        assert btc_contract['exchange'] == 'binance'
        assert btc_contract['details']['base_symbol'] == 'BTC'
        assert btc_contract['details']['quote_symbol'] == 'USDT'
        assert btc_contract['details']['raw_symbol'] == 'BTCUSDT'

        # 验证第二个
        eth_contract = contracts[1]
        assert eth_contract['symbol'] == 'ETH/USDT'
        assert eth_contract['current_price'] == Decimal('3000.00')

    def test_build_standardized_contracts_missing_price(self, spot_client):
        """测试构建标准化交易对 - 缺少价格数据"""
        raw_symbols = [
            {
                "symbol": "BTCUSDT",
                "baseAsset": "BTC",
                "quoteAsset": "USDT"
            }
        ]

        prices = {}  # 没有价格数据

        contracts = spot_client._build_standardized_contracts(raw_symbols, prices)

        # 没有价格的交易对应该被跳过
        assert len(contracts) == 0

    def test_fetch_contracts_with_indicators(self, spot_client):
        """测试获取交易对及指标（现货版）"""
        with patch('monitor.api_clients.binance_spot.requests.Session.get') as mock_get:
            mock_exchange_info = MagicMock()
            mock_exchange_info.json.return_value = {
                "symbols": [
                    {
                        "symbol": "BTCUSDT",
                        "status": "TRADING",
                        "baseAsset": "BTC",
                        "quoteAsset": "USDT",
                        "isSpotTradingAllowed": True
                    }
                ]
            }
            mock_exchange_info.raise_for_status.return_value = None

            mock_ticker = MagicMock()
            mock_ticker.json.return_value = [
                {"symbol": "BTCUSDT", "price": "50000.00"}
            ]
            mock_ticker.raise_for_status.return_value = None

            mock_get.side_effect = [mock_exchange_info, mock_ticker]

            contracts = spot_client.fetch_contracts_with_indicators()

            # 现货交易对没有特殊指标，应该返回与fetch_contracts相同的数据
            assert len(contracts) == 1
            assert contracts[0]['symbol'] == 'BTC/USDT'
            assert contracts[0]['contract_type'] == 'spot'

    def test_api_error_handling(self, spot_client):
        """测试API错误处理"""
        with patch('monitor.api_clients.binance_spot.requests.Session.get') as mock_get:
            # 模拟API调用失败
            mock_get.side_effect = Exception("API不可用")

            with pytest.raises(Exception, match="API不可用"):
                spot_client.fetch_contracts()

    def test_validate_binance_spot_response_format_valid(self):
        """测试响应格式验证 - 有效数据"""
        contracts = [
            {
                'symbol': 'BTC/USDT',
                'current_price': Decimal('50000.00'),
                'contract_type': 'spot',
                'exchange': 'binance'
            },
            {
                'symbol': 'ETH/USDT',
                'current_price': Decimal('3000.00'),
                'contract_type': 'spot',
                'exchange': 'binance'
            }
        ]

        assert validate_binance_spot_response_format(contracts) is True

    def test_validate_binance_spot_response_format_invalid_type(self):
        """测试响应格式验证 - 无效类型"""
        assert validate_binance_spot_response_format("not a list") is False

    def test_validate_binance_spot_response_format_missing_fields(self):
        """测试响应格式验证 - 缺少字段"""
        contracts = [
            {
                'symbol': 'BTC/USDT',
                'current_price': Decimal('50000.00')
                # 缺少contract_type和exchange
            }
        ]

        assert validate_binance_spot_response_format(contracts) is False

    def test_validate_binance_spot_response_format_invalid_price_type(self):
        """测试响应格式验证 - 价格类型错误"""
        contracts = [
            {
                'symbol': 'BTC/USDT',
                'current_price': '50000.00',  # 应该是Decimal，不是字符串
                'contract_type': 'spot',
                'exchange': 'binance'
            }
        ]

        assert validate_binance_spot_response_format(contracts) is False

    def test_validate_binance_spot_response_format_invalid_contract_type(self):
        """测试响应格式验证 - 交易对类型错误"""
        contracts = [
            {
                'symbol': 'BTC/USDT',
                'current_price': Decimal('50000.00'),
                'contract_type': 'futures',  # 应该是'spot'
                'exchange': 'binance'
            }
        ]

        assert validate_binance_spot_response_format(contracts) is False

    def test_validate_binance_spot_response_format_invalid_symbol_format(self):
        """测试响应格式验证 - 符号格式错误"""
        contracts = [
            {
                'symbol': 'BTCUSDT',  # 应该是BTC/USDT格式
                'current_price': Decimal('50000.00'),
                'contract_type': 'spot',
                'exchange': 'binance'
            }
        ]

        assert validate_binance_spot_response_format(contracts) is False

    def test_get_binance_test_spot_contract(self):
        """测试获取测试用现货交易对数据"""
        contract = get_binance_test_spot_contract()

        assert contract['symbol'] == 'BTC/USDT'
        assert contract['current_price'] == Decimal('50000.00')
        assert contract['contract_type'] == 'spot'
        assert contract['exchange'] == 'binance'
        assert 'details' in contract
        assert contract['details']['base_symbol'] == 'BTC'
        assert contract['details']['quote_symbol'] == 'USDT'
