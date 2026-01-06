"""
fetch_spot_contracts管理命令测试

测试现货交易对同步命令的功能，包括：
1. 命令行参数解析
2. 交易所验证
3. 数据获取和保存
4. 错误处理
5. 测试模式
6. 详细输出
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from io import StringIO
from decimal import Decimal

from django.core.management import call_command, CommandError
from django.test import override_settings

from monitor.services.spot_fetcher import SpotFetcherService
from monitor.models import Exchange, SpotContract


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
        }
    ]


class TestFetchSpotContractsCommand:
    """fetch_spot_contracts管理命令测试类"""

    def test_command_exists(self):
        """测试命令是否存在"""
        from monitor.management.commands.fetch_spot_contracts import Command
        assert Command is not None

    def test_command_help(self):
        """测试命令帮助信息"""
        from monitor.management.commands.fetch_spot_contracts import Command
        assert '手动获取现货交易对数据从指定交易所' in Command.help

    @pytest.mark.django_db
    @patch('monitor.management.commands.fetch_spot_contracts.SpotFetcherService')
    def test_command_exchange_binance_success(self, mock_service_class, mock_contracts, capsys):
        """测试成功获取binance现货数据"""
        # 模拟服务
        mock_service = MagicMock()
        mock_service.get_supported_exchanges.return_value = ['binance']
        mock_service.update_exchanges_manually.return_value = {
            'binance': {
                'status': 'success',
                'new': 2,
                'updated': 0,
                'delisted': 0,
                'saved': 2
            }
        }
        mock_service_class.return_value = mock_service

        # 模拟交易所创建
        Exchange.objects.create(
            name='Binance',
            code='binance',
            announcement_url='https://www.binance.com/en/support/announcement'
        )

        # 执行命令
        call_command('fetch_spot_contracts', '--exchange', 'binance', verbosity=2)

        # 验证服务调用
        mock_service.update_exchanges_manually.assert_called_once_with(['binance'])

        # 验证输出
        captured = capsys.readouterr()
        assert '开始获取现货交易对数据' in captured.out
        assert '成功:' in captured.out
        assert '新增 2, 更新 0, 下线 0' in captured.out

    @pytest.mark.django_db
    @patch('monitor.management.commands.fetch_spot_contracts.SpotFetcherService')
    def test_command_all_exchanges(self, mock_service_class, capsys):
        """测试获取所有交易所数据"""
        # 模拟服务
        mock_service = MagicMock()
        mock_service.get_supported_exchanges.return_value = ['binance']
        mock_service.update_exchanges_manually.return_value = {
            'binance': {
                'status': 'success',
                'new': 1,
                'updated': 0,
                'delisted': 0,
                'saved': 1
            }
        }
        mock_service_class.return_value = mock_service

        # 模拟交易所创建
        Exchange.objects.create(
            name='Binance',
            code='binance',
            announcement_url='https://www.binance.com/en/support/announcement'
        )

        # 执行命令
        call_command('fetch_spot_contracts', '--all', verbosity=2)

        # 验证服务调用
        mock_service.update_exchanges_manually.assert_called_once_with(['binance'])

        # 验证输出
        captured = capsys.readouterr()
        assert '开始获取现货交易对数据' in captured.out

    @pytest.mark.django_db
    @patch('monitor.management.commands.fetch_spot_contracts.SpotFetcherService')
    def test_command_test_mode(self, mock_service_class, mock_contracts, capsys):
        """测试测试模式（不保存到数据库）"""
        # 模拟服务
        mock_service = MagicMock()
        mock_service.get_supported_exchanges.return_value = ['binance']
        mock_service.clients = {'binance': MagicMock()}
        mock_service.clients['binance'].fetch_contracts.return_value = mock_contracts
        mock_service_class.return_value = mock_service

        # 执行命令
        call_command('fetch_spot_contracts', '--exchange', 'binance', '--test', '--verbose', verbosity=2)

        # 验证测试模式调用
        mock_service.clients['binance'].fetch_contracts.assert_called_once()
        mock_service.update_exchanges_manually.assert_not_called()

        # 验证输出
        captured = capsys.readouterr()
        assert '测试模式' in captured.out
        assert '成功获取 2 个现货交易对' in captured.out
        assert 'BTC/USDT' in captured.out
        assert 'ETH/USDT' in captured.out

    @pytest.mark.django_db
    @patch('monitor.management.commands.fetch_spot_contracts.SpotFetcherService')
    def test_command_verbose_output(self, mock_service_class, mock_contracts, capsys):
        """测试详细输出模式"""
        # 模拟服务
        mock_service = MagicMock()
        mock_service.get_supported_exchanges.return_value = ['binance']
        mock_service.update_exchanges_manually.return_value = {
            'binance': {
                'status': 'success',
                'new': 2,
                'updated': 0,
                'delisted': 0,
                'saved': 2
            }
        }
        mock_service_class.return_value = mock_service

        # 模拟交易所创建
        exchange = Exchange.objects.create(
            name='Binance',
            code='binance',
            announcement_url='https://www.binance.com/en/support/announcement'
        )

        # 执行命令
        call_command('fetch_spot_contracts', '--exchange', 'binance', '--verbose', verbosity=2)

        # 验证输出
        captured = capsys.readouterr()
        assert '交易所已存在' in captured.out
        assert '✓ 交易所已存在: Binance (binance)' in captured.out

    @pytest.mark.django_db
    @patch('monitor.management.commands.fetch_spot_contracts.SpotFetcherService')
    def test_command_api_error(self, mock_service_class, capsys):
        """测试API错误处理"""
        # 模拟服务
        mock_service = MagicMock()
        mock_service.get_supported_exchanges.return_value = ['binance']
        mock_service.update_exchanges_manually.return_value = {
            'binance': {
                'status': 'error',
                'error': 'API不可用'
            }
        }
        mock_service_class.return_value = mock_service

        # 模拟交易所创建
        Exchange.objects.create(
            name='Binance',
            code='binance',
            announcement_url='https://www.binance.com/en/support/announcement'
        )

        # 执行命令（应该返回非0退出码）
        with pytest.raises(SystemExit) as exc_info:
            call_command('fetch_spot_contracts', '--exchange', 'binance', verbosity=2)

        # 验证退出码
        assert exc_info.value.code == 1

        # 验证错误输出
        captured = capsys.readouterr()
        assert '✗ 失败' in captured.out
        assert 'API不可用' in captured.out

    @pytest.mark.django_db
    @patch('monitor.management.commands.fetch_spot_contracts.SpotFetcherService')
    def test_command_invalid_exchange(self, mock_service_class, capsys):
        """测试无效交易所代码"""
        # 模拟服务
        mock_service = MagicMock()
        mock_service.get_supported_exchanges.return_value = ['binance']
        mock_service_class.return_value = mock_service

        # 执行命令（应该抛出CommandError）
        with pytest.raises(CommandError) as exc_info:
            call_command('fetch_spot_contracts', '--exchange', 'invalid_exchange')

        # 验证错误信息（argparse会在参数验证阶段抛出错误）
        assert 'invalid choice' in str(exc_info.value)
        assert 'invalid_exchange' in str(exc_info.value)

    @pytest.mark.django_db
    def test_command_no_exchange_specified(self, capsys):
        """测试未指定交易所"""
        # 执行命令
        call_command('fetch_spot_contracts', verbosity=2)

        # 验证输出提示
        captured = capsys.readouterr()
        assert '未指定交易所' in captured.out
        assert '--exchange binance' in captured.out
        assert '--all' in captured.out

    @pytest.mark.django_db
    @patch('monitor.management.commands.fetch_spot_contracts.SpotFetcherService')
    def test_command_auto_create_exchange(self, mock_service_class, mock_contracts, capsys):
        """测试自动创建交易所记录"""
        # 确保binance交易所不存在
        Exchange.objects.filter(code='binance').delete()

        # 模拟服务
        mock_service = MagicMock()
        mock_service.get_supported_exchanges.return_value = ['binance']
        mock_service.update_exchanges_manually.return_value = {
            'binance': {
                'status': 'success',
                'new': 2,
                'updated': 0,
                'delisted': 0,
                'saved': 2
            }
        }
        mock_service_class.return_value = mock_service

        # 执行命令
        call_command('fetch_spot_contracts', '--exchange', 'binance', verbosity=2)

        # 验证交易所被自动创建
        assert Exchange.objects.filter(code='binance').exists()
        exchange = Exchange.objects.get(code='binance')
        assert exchange.name == 'Binance'
        assert exchange.enabled is True

        # 验证输出
        captured = capsys.readouterr()
        assert '已自动创建交易所' in captured.out
        assert 'Binance (binance)' in captured.out

    @pytest.mark.django_db
    @patch('monitor.management.commands.fetch_spot_contracts.SpotFetcherService')
    def test_command_execution_summary(self, mock_service_class, capsys):
        """测试执行摘要输出"""
        # 模拟服务
        mock_service = MagicMock()
        mock_service.get_supported_exchanges.return_value = ['binance']
        mock_service.update_exchanges_manually.return_value = {
            'binance': {
                'status': 'success',
                'new': 5,
                'updated': 3,
                'delisted': 1,
                'saved': 8
            }
        }
        mock_service_class.return_value = mock_service

        # 模拟交易所创建
        Exchange.objects.create(
            name='Binance',
            code='binance',
            announcement_url='https://www.binance.com/en/support/announcement'
        )

        # 执行命令
        call_command('fetch_spot_contracts', '--exchange', 'binance', verbosity=2)

        # 验证执行摘要
        captured = capsys.readouterr()
        assert '📊 执行摘要' in captured.out
        assert '处理交易所: binance' in captured.out
        assert '保存现货交易对: 8' in captured.out
        assert '执行时间' in captured.out
        assert '✅ 执行完成' in captured.out

    @pytest.mark.django_db
    @patch('monitor.management.commands.fetch_spot_contracts.SpotFetcherService')
    def test_command_test_mode_execution_summary(self, mock_service_class, mock_contracts, capsys):
        """测试模式下执行摘要（不显示保存数量）"""
        # 模拟服务
        mock_service = MagicMock()
        mock_service.get_supported_exchanges.return_value = ['binance']
        mock_service.clients = {'binance': MagicMock()}
        mock_service.clients['binance'].fetch_contracts.return_value = mock_contracts
        mock_service_class.return_value = mock_service

        # 执行命令
        call_command('fetch_spot_contracts', '--exchange', 'binance', '--test', verbosity=2)

        # 验证执行摘要（测试模式不显示保存数量）
        captured = capsys.readouterr()
        assert '📊 执行摘要' in captured.out
        assert '保存现货交易对' not in captured.out  # 测试模式不显示
        assert '✅ 执行完成' in captured.out
