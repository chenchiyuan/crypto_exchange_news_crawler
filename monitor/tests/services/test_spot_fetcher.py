"""
SpotFetcherService服务测试

测试现货数据获取服务的功能，包括：
1. 多交易所数据获取
2. 数据库保存和更新
3. 错误处理
4. 统计信息生成
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

from monitor.services.spot_fetcher import SpotFetcherService
from monitor.models import Exchange, SpotContract
from monitor.api_clients.binance_spot import get_binance_test_spot_contract


@pytest.fixture
def spot_fetcher():
    """创建现货数据获取服务实例"""
    return SpotFetcherService()


@pytest.fixture
def exchange():
    """创建交易所实例"""
    return Exchange.objects.create(
        name='Binance',
        code='binance',
        announcement_url='https://www.binance.com/en/support/announcement'
    )


@pytest.fixture
def mock_contracts():
    """模拟现货交易对数据"""
    return [
        {
            'symbol': 'BTC/USDT',
            'current_price': Decimal('50000.00'),
            'contract_type': 'spot',
            'exchange': 'binance',
            'details': {
                'base_symbol': 'BTC',
                'quote_symbol': 'USDT',
                'raw_symbol': 'BTCUSDT'
            }
        },
        {
            'symbol': 'ETH/USDT',
            'current_price': Decimal('3000.00'),
            'contract_type': 'spot',
            'exchange': 'binance',
            'details': {
                'base_symbol': 'ETH',
                'quote_symbol': 'USDT',
                'raw_symbol': 'ETHUSDT'
            }
        },
        {
            'symbol': 'BNB/USDT',
            'current_price': Decimal('300.00'),
            'contract_type': 'spot',
            'exchange': 'binance',
            'details': {
                'base_symbol': 'BNB',
                'quote_symbol': 'USDT',
                'raw_symbol': 'BNBUSDT'
            }
        }
    ]


class TestSpotFetcherService:
    """现货数据获取服务测试类"""

    def test_init(self, spot_fetcher):
        """测试服务初始化"""
        assert 'binance' in spot_fetcher.clients
        assert isinstance(spot_fetcher.clients['binance'].__class__.__name__, str)

    def test_get_supported_exchanges(self, spot_fetcher):
        """测试获取支持的交易所列表"""
        exchanges = spot_fetcher.get_supported_exchanges()
        assert 'binance' in exchanges
        assert isinstance(exchanges, list)

    def test_fetch_from_all_exchanges_success(self, spot_fetcher, mock_contracts):
        """测试成功从所有交易所获取数据"""
        with patch.object(spot_fetcher.clients['binance'], 'fetch_contracts', return_value=mock_contracts):
            result = spot_fetcher.fetch_from_all_exchanges()

            assert 'binance' in result
            assert len(result['binance']) == 3
            assert result['binance'][0]['symbol'] == 'BTC/USDT'

    @pytest.mark.django_db
    def test_fetch_from_all_exchanges_empty(self, spot_fetcher):
        """测试获取空数据"""
        with patch.object(spot_fetcher.clients['binance'], 'fetch_contracts', return_value=[]):
            result = spot_fetcher.fetch_from_all_exchanges()

            assert result['binance'] == []

    @pytest.mark.django_db
    def test_fetch_from_all_exchanges_error(self, spot_fetcher):
        """测试获取数据时出错"""
        with patch.object(spot_fetcher.clients['binance'], 'fetch_contracts', side_effect=Exception("API错误")):
            result = spot_fetcher.fetch_from_all_exchanges()

            assert result['binance'] == []

    @pytest.mark.django_db
    def test_save_contracts_to_database_new_contracts(self, spot_fetcher, exchange, mock_contracts):
        """测试保存新合约到数据库"""
        stats = spot_fetcher.save_contracts_to_database(exchange, mock_contracts)

        assert stats['new'] == 3
        assert stats['updated'] == 0
        assert stats['delisted'] == 0
        assert stats['saved'] == 3

        # 验证数据库中的记录
        assert SpotContract.objects.filter(exchange=exchange).count() == 3
        btc_contract = SpotContract.objects.get(exchange=exchange, symbol='BTC/USDT')
        assert btc_contract.current_price == Decimal('50000.00')
        assert btc_contract.status == SpotContract.ACTIVE

    @pytest.mark.django_db
    def test_save_contracts_to_database_update_existing(self, spot_fetcher, exchange, mock_contracts):
        """测试更新现有合约"""
        # 先创建一些现有记录
        SpotContract.objects.create(
            exchange=exchange,
            symbol='BTC/USDT',
            status=SpotContract.ACTIVE,
            current_price=Decimal('45000.00')  # 旧价格
        )
        SpotContract.objects.create(
            exchange=exchange,
            symbol='ETH/USDT',
            status=SpotContract.ACTIVE,
            current_price=Decimal('2800.00')  # 旧价格
        )

        # 更新数据
        stats = spot_fetcher.save_contracts_to_database(exchange, mock_contracts)

        assert stats['new'] == 1  # BNB/USDT是新加的
        assert stats['updated'] == 2  # BTC和ETH被更新
        assert stats['delisted'] == 0
        assert stats['saved'] == 3

        # 验证更新
        btc_contract = SpotContract.objects.get(exchange=exchange, symbol='BTC/USDT')
        assert btc_contract.current_price == Decimal('50000.00')  # 价格已更新

    @pytest.mark.django_db
    def test_save_contracts_to_database_delisted(self, spot_fetcher, exchange, mock_contracts):
        """测试标记下线的合约"""
        # 创建现有记录，包括一个不在API返回中的
        SpotContract.objects.create(
            exchange=exchange,
            symbol='BTC/USDT',
            status=SpotContract.ACTIVE,
            current_price=Decimal('45000.00')
        )
        SpotContract.objects.create(
            exchange=exchange,
            symbol='ADA/USDT',  # 这个不在mock_contracts中，应该被标记为下线
            status=SpotContract.ACTIVE,
            current_price=Decimal('0.50')
        )

        # 更新数据（不包含ADA/USDT）
        stats = spot_fetcher.save_contracts_to_database(exchange, mock_contracts[:2])  # 只包含BTC和ETH

        assert stats['new'] == 1  # ETH是新加的（如果不存在）
        assert stats['updated'] == 1  # BTC被更新
        assert stats['delisted'] == 1  # ADA被标记为下线
        assert stats['saved'] == 2

        # 验证ADA被标记为下线
        ada_contract = SpotContract.objects.get(exchange=exchange, symbol='ADA/USDT')
        assert ada_contract.status == SpotContract.DELISTED

    @pytest.mark.django_db
    def test_save_contracts_to_database_error(self, spot_fetcher, exchange):
        """测试保存时出错"""
        invalid_contracts = [
            {
                'symbol': 'BTC/USDT',
                'current_price': Decimal('50000.00'),
            }
        ]

        # 模拟SpotContract.objects.create抛出异常（使用重试装饰器会捕获并重试，所以需要检查RetryError）
        with patch.object(SpotContract.objects, 'create', side_effect=Exception("数据库错误")):
            with pytest.raises(Exception):
                spot_fetcher.save_contracts_to_database(exchange, invalid_contracts)

    @pytest.mark.django_db
    def test_update_exchanges_manually_success(self, spot_fetcher, exchange, mock_contracts):
        """测试手动更新交易所成功"""
        with patch.object(spot_fetcher.clients['binance'], 'fetch_contracts', return_value=mock_contracts):
            result = spot_fetcher.update_exchanges_manually(['binance'])

            assert result['binance']['status'] == 'success'
            assert result['binance']['new'] == 3
            assert result['binance']['saved'] == 3

    @pytest.mark.django_db
    def test_update_exchanges_manually_invalid_exchange(self, spot_fetcher):
        """测试手动更新无效交易所"""
        result = spot_fetcher.update_exchanges_manually(['invalid_exchange'])

        assert result['invalid_exchange']['status'] == 'error'
        assert '不支持的交易所' in result['invalid_exchange']['error']

    @pytest.mark.django_db
    def test_update_exchanges_manually_api_error(self, spot_fetcher):
        """测试API调用错误"""
        with patch.object(spot_fetcher.clients['binance'], 'fetch_contracts', side_effect=Exception("API不可用")):
            result = spot_fetcher.update_exchanges_manually(['binance'])

            assert result['binance']['status'] == 'error'
            assert 'API不可用' in result['binance']['error']

    @pytest.mark.django_db
    def test_update_exchanges_manually_empty_data(self, spot_fetcher):
        """测试获取空数据"""
        with patch.object(spot_fetcher.clients['binance'], 'fetch_contracts', return_value=[]):
            result = spot_fetcher.update_exchanges_manually(['binance'])

            assert result['binance']['status'] == 'error'
            assert '未获取到现货交易对数据' in result['binance']['error']

    @pytest.mark.django_db
    def test_auto_create_exchange(self, spot_fetcher, mock_contracts):
        """测试自动创建交易所记录"""
        # 确保binance交易所不存在
        Exchange.objects.filter(code='binance').delete()

        with patch.object(spot_fetcher.clients['binance'], 'fetch_contracts', return_value=mock_contracts):
            result = spot_fetcher.update_exchanges_manually(['binance'])

            # 验证交易所被自动创建
            assert Exchange.objects.filter(code='binance').exists()
            exchange = Exchange.objects.get(code='binance')
            assert exchange.name == 'Binance'
            assert exchange.enabled is True

            # 验证结果成功
            assert result['binance']['status'] == 'success'

    @pytest.mark.django_db
    def test_existing_exchange_not_recreated(self, spot_fetcher, exchange, mock_contracts):
        """测试现有交易所不会被重复创建"""
        original_name = exchange.name
        original_enabled = exchange.enabled

        with patch.object(spot_fetcher.clients['binance'], 'fetch_contracts', return_value=mock_contracts):
            result = spot_fetcher.update_exchanges_manually(['binance'])

            # 验证交易所信息未改变
            exchange.refresh_from_db()
            assert exchange.name == original_name
            assert exchange.enabled == original_enabled

            # 验证结果成功
            assert result['binance']['status'] == 'success'

    @pytest.mark.django_db
    def test_multiple_exchanges(self, spot_fetcher, mock_contracts):
        """测试多个交易所（虽然目前只有binance）"""
        # 创建第二个交易所
        okx_exchange = Exchange.objects.create(
            name='OKX',
            code='okx',
            announcement_url='https://www.okx.com/support'
        )

        # 模拟两个交易所的数据
        binance_data = mock_contracts
        okx_data = [
            {
                'symbol': 'BTC/USDT',
                'current_price': Decimal('50100.00'),
                'contract_type': 'spot',
                'exchange': 'okx',
                'details': {
                    'base_symbol': 'BTC',
                    'quote_symbol': 'USDT',
                    'raw_symbol': 'BTCUSDT'
                }
            }
        ]

        with patch.object(spot_fetcher.clients['binance'], 'fetch_contracts', return_value=binance_data):
            # 注意：这里okx客户端不存在，但测试逻辑
            result = spot_fetcher.update_exchanges_manually(['binance'])

            assert result['binance']['status'] == 'success'
