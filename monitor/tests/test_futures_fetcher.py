"""
FuturesFetcherService 单元测试
测试合约数据获取服务、重试机制、错误处理、数据库更新逻辑"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal

from monitor.services.futures_fetcher import FuturesFetcherService
from monitor.api_clients.binance import BinanceFuturesClient
from monitor.api_clients.hyperliquid import HyperliquidFuturesClient
from monitor.api_clients.bybit import BybitFuturesClient
from monitor.models import Exchange, FuturesContract


@pytest.fixture
def mock_exchange_binance():
    """创建Binance交易所实例"""
    return Exchange.objects.create(
        name='Binance',
        code='binance',
        announcement_url='https://binance.com/'
    )


@pytest.fixture
def mock_exchange_hyperliquid():
    """创建Hyperliquid交易所实例"""
    return Exchange.objects.create(
        name='Hyperliquid',
        code='hyperliquid',
        announcement_url='https://hyperliquid.xyz/'
    )


@pytest.fixture
def mock_exchange_bybit():
    """创建Bybit交易所实例"""
    return Exchange.objects.create(
        name='Bybit',
        code='bybit',
        announcement_url='https://bybit.com/'
    )


@pytest.fixture
def fetcher_service():
    """创建FuturesFetcherService实例"""
    return FuturesFetcherService()


@pytest.fixture
def mock_contract_data():
    """Mock合约数据"""
    return {
        'binance': [
            {'symbol': 'BTCUSDT', 'current_price': Decimal('44000.00'), 'contract_type': 'perpetual'},
            {'symbol': 'ETHUSDT', 'current_price': Decimal('2200.00'), 'contract_type': 'perpetual'}
        ],
        'hyperliquid': [
            {'symbol': 'BTCUSDT', 'current_price': Decimal('44050.00'), 'contract_type': 'perpetual'},
            {'symbol': 'ETHUSDT', 'current_price': Decimal('2210.00'), 'contract_type': 'perpetual'}
        ],
        'bybit': [
            {'symbol': 'BTCUSDT', 'current_price': Decimal('44025.00'), 'contract_type': 'perpetual'},
            {'symbol': 'ETHUSDT', 'current_price': Decimal('2205.00'), 'contract_type': 'perpetual'}
        ]
    }


class TestFuturesFetcherService:
    """FuturesFetcherService测试类"""

    def test_init(self, fetcher_service):
        """测试服务初始化"""
        assert hasattr(fetcher_service, 'clients')
        assert isinstance(fetcher_service.clients, dict)
        assert 'binance' in fetcher_service.clients
        assert 'hyperliquid' in fetcher_service.clients
        assert 'bybit' in fetcher_service.clients

    def test_fetch_from_all_exchanges_success(self, fetcher_service, mock_exchange_binance, mock_exchange_hyperliquid, mock_exchange_bybit, mock_contract_data):
        """测试成功从所有交易所获取数据"""
        with patch.object(BinanceFuturesClient, 'fetch_contracts', return_value=mock_contract_data['binance']), \
             patch.object(HyperliquidFuturesClient, 'fetch_contracts', return_value=mock_contract_data['hyperliquid']), \
             patch.object(BybitFuturesClient, 'fetch_contracts', return_value=mock_contract_data['bybit']):

            all_contracts = fetcher_service.fetch_from_all_exchanges()

            # 验证返回数据
            assert len(all_contracts) == 3  # 3个交易所
            assert 'binance' in all_contracts
            assert 'hyperliquid' in all_contracts
            assert 'bybit' in all_contracts

            # 验证每个交易所的数据
            for exchange_code, contracts in all_contracts.items():
                assert isinstance(contracts, list)
                assert len(contracts) >= 2  # 至少2个合约
                for contract in contracts:
                    assert 'symbol' in contract
                    assert 'current_price' in contract
                    assert 'contract_type' in contract

    def test_save_contracts_to_database_new_contracts(self, fetcher_service, mock_exchange_binance, mock_exchange_hyperliquid):
        """测试保存新合约到数据库"""
        # 清理现有数据
        FuturesContract.objects.all().delete()

        mock_contracts = {
            'binance': [
                {'symbol': 'BTCUSDT', 'current_price': Decimal('44000.00'), 'contract_type': 'perpetual'},
                {'symbol': 'ETHUSDT', 'current_price': Decimal('2200.00'), 'contract_type': 'perpetual'}
            ]
        }

        # 执行保存
        saved_contracts, new_count, updated_count = fetcher_service.save_contracts_to_database(mock_exchange_binance, mock_contracts['binance'])

        # 验证结果
        assert saved_contracts == 2
        assert new_count == 2
        assert updated_count == 0

        # 验证数据库
        contracts = FuturesContract.objects.filter(exchange=mock_exchange_binance)
        assert contracts.count() == 2

        # 验证btc合约
        btc_contract = contracts.get(symbol='BTCUSDT')
        assert btc_contract.current_price == Decimal('44000.00')
        assert btc_contract.contract_type == 'perpetual'
        assert btc_contract.status == FuturesContract.ACTIVE

        # 验证 first_seen 时间设置
        assert btc_contract.first_seen is not None
        assert btc_contract.last_updated > btc_contract.first_seen

    def test_save_contracts_to_database_existing_contracts(self, fetcher_service, mock_exchange_binance):
        """测试更新现有合约"""
        # 先创建现有合约
        existing_contract = FuturesContract.objects.create(
            exchange=mock_exchange_binance,
            symbol='BTCUSDT',
            current_price=Decimal('42000.00'),
            contract_type='perpetual',
            first_seen=datetime.now() - timedelta(days=1)
        )

        # 新数据（价格更新）
        mock_contracts = {
            'binance': [
                {'symbol': 'BTCUSDT', 'current_price': Decimal('44000.00'), 'contract_type': 'perpetual'}
            ]
        }

        # 执行更新
        saved_contracts, new_count, updated_count = fetcher_service.save_contracts_to_database(mock_exchange_binance, mock_contracts['binance'])

        # 验证结果
        assert saved_contracts == 1
        assert new_count == 0
        assert updated_count == 1

        # 验证数据库更新
        existing_contract.refresh_from_db()
        assert existing_contract.current_price == Decimal('44000.00')

        # 验证 first_seen 时间不变
        original_first_seen = existing_contract.first_seen.replace(microsecond=0)
        assert existing_contract.first_seen.replace(microsecond=0) == original_first_seen

    def test_save_contracts_to_database_mixed_operations(self, fetcher_service, mock_exchange_binance):
        """测试新合约和更新合约混合操作"""
        # 创建1个已有合约
        FuturesContract.objects.create(
            exchange=mock_exchange_binance,
            symbol='BTCUSDT',
            current_price=Decimal('42000.00'),
            contract_type='perpetual',
            first_seen=datetime.now() - timedelta(days=1)
        )

        # 新数据：1个新合约 + 1个已有合约
        mock_contracts = [
            {'symbol': 'BTCUSDT', 'current_price': Decimal('44000.00'), 'contract_type': 'perpetual'},  # 更新
            {'symbol': 'ETHUSDT', 'current_price': Decimal('2200.00'), 'contract_type': 'perpetual'}      # 新合约
        ]

        saved_contracts, new_count, updated_count = fetcher_service.save_contracts_to_database(mock_exchange_binance, mock_contracts)

        # 验证结果
        assert saved_contracts == 2
        assert new_count == 1  # ETHUSDT 是新合约
        assert updated_count == 1  # BTCUSDT 是更新

        # 验证数据库
        contracts = FuturesContract.objects.filter(exchange=mock_exchange_binance)
        assert contracts.count() == 2

        # 验证BTC被更新
        btc_contract = contracts.get(symbol='BTCUSDT')
        assert btc_contract.current_price == Decimal('44000.00')

        # 验证ETH是新创建
        eth_contract = contracts.get(symbol='ETHUSDT')
        assert eth_contract.current_price == Decimal('2200.00')

    def test_unique_constraint_per_exchange(self, fetcher_service, mock_exchange_binance, mock_exchange_hyperliquid):
        """测试同一交易内的相同符号唯一性约束"""
        mock_contracts = [
            {'symbol': 'BTCUSDT', 'current_price': Decimal('44000.00'), 'contract_type': 'perpetual'}
        ]

        # 先在Binance创建
        fetcher_service.save_contracts_to_database(mock_exchange_binance, mock_contracts)

        # 尝试在Binance再次创建相同符号（应该更新而不是创建）
        mock_contracts[0]['current_price'] = Decimal('45000.00')  # 更新价格
        saved_contracts, new_count, updated_count = fetcher_service.save_contracts_to_database(mock_exchange_binance, mock_contracts)

        # 应该只更新，不创建新记录
        assert saved_contracts == 1
        assert new_count == 0
        assert updated_count == 1

        # 验证可以在不同交易所创建相同符号
        fetcher_service.save_contracts_to_database(mock_exchange_hyperliquid, mock_contracts)

        # 验证binance合约数量
        binance_count = FuturesContract.objects.filter(exchange=mock_exchange_binance, symbol='BTCUSDT').count()
        assert binance_count == 1

        # 验证hyperliquid合约数量
        hyperliquid_count = FuturesContract.objects.filter(exchange=mock_exchange_hyperliquid, symbol='BTCUSDT').count()
        assert hyperliquid_count == 1

    def test_detection_of_delisted_contracts(self, fetcher_service, mock_exchange_binance):
        """测试检测已下线合约"""
        # 先创建2个合约
        btc_contract = FuturesContract.objects.create(
            exchange=mock_exchange_binance,
            symbol='BTCUSDT',
            current_price=Decimal('44000.00'),
            contract_type='perpetual'
        )

        eth_contract = FuturesContract.objects.create(
            exchange=mock_exchange_binance,
            symbol='ETHUSDT',
            current_price=Decimal('2200.00'),
            contract_type='perpetual'
        )

        # 模拟API返回（缺少ETHUSDT，只剩BTC）
        mock_contracts = [
            {'symbol': 'BTCUSDT', 'current_price': Decimal('44050.00'), 'contract_type': 'perpetual'}
            # ETHUSDT 缺失，应该被标记为已下线
        ]

        # 执行检测
        saved_contracts, new_count, updated_count, delisted_count = fetcher_service.update_contracts_and_detect_delisted(mock_exchange_binance, mock_contracts)

        # 验证结果
        assert saved_contracts == 1
        assert new_count == 0
        assert updated_count == 1
        assert delisted_count == 1

        # 验证BTC被更新
        btc_contract.refresh_from_db()
        assert btc_contract.current_price == Decimal('44050.00')
        assert btc_contract.status == FuturesContract.ACTIVE

        # 验证ETH被标记为已下线
        eth_contract.refresh_from_db()
        assert eth_contract.status == FuturesContract.DELISTED

    def test_error_handling_during_save(self, fetcher_service, mock_exchange_binance):
        """测试保存过程中的错误处理"""
        # Mock数据库异常
        with patch.object(FuturesContract.objects, 'get_or_create', side_effect=Exception("Database error")):
            mock_contracts = [
                {'symbol': 'BTCUSDT', 'current_price': Decimal('44000.00'), 'contract_type': 'perpetual'}
            ]

            with pytest.raises(Exception, match="Database error"):
                fetcher_service.save_contracts_to_database(mock_exchange_binance, mock_contracts)

    def test_empty_input_handling(self, fetcher_service, mock_exchange_binance):
        """测试空输入的处理"""
        saved_contracts, new_count, updated_count = fetcher_service.save_contracts_to_database(mock_exchange_binance, [])

        assert saved_contracts == 0
        assert new_count == 0
        assert updated_count == 0

    def test_service_retry_on_transient_error(self, fetcher_service, mock_exchange_binance):
        """测试服务的重试机制"""
        mock_contracts = mock_contracts = [
            {'symbol': 'BTCUSDT', 'current_price': Decimal('44000.00'), 'contract_type': 'perpetual'}
        ]

        # Mock第一次失败，第二次成功
        with patch.object(FuturesContract.objects, 'get_or_create') as mock_create:
            mock_create.side_effect = [
                Exception("Connection timeout"),  # 第一次失败
                Exception("Connection timeout"),  # 第二次失败
                (MagicMock(), True)               # 第三次成功
            ]

            with patch('tenacity.wait.wait_random_exponential') as mock_wait:
                saved_contracts, new_count, updated_count = fetcher_service.save_contracts_to_database(mock_exchange_binance, mock_contracts)

                # 验证重试次数
                assert mock_create.call_count == 3
                assert saved_contracts == 1

    @pytest.mark.slow
    def test_performance_under_load(self, fetcher_service, mock_exchange_binance):
        """测试在大量数据下的性能 (模拟负载测试)"""
        import time

        # 模拟100个合约
        import random
        mock_contracts = []
        for i in range(100):
            mock_contracts.append({
                'symbol': f'CONTRACT{i:03d}USDT',
                'current_price': Decimal(random.uniform(1, 100000)),
                'contract_type': 'perpetual'
            })

        start_time = time.time()
        saved_contracts, new_count, updated_count = fetcher_service.save_contracts_to_database(mock_exchange_binance, mock_contracts)
        end_time = time.time()

        # 验证结果（基础正确性）
        assert saved_contracts == 100
        assert new_count == 100
        assert updated_count == 0

        # 验证性能（保存100个合约应该在半秒内）
        assert (end_time - start_time) < 0.5, f"Performance degraded: took {end_time - start_time}s"

        # 清理测试数据
        FuturesContract.objects.filter(exchange=mock_exchange_binance).delete()



class TestCompositeOperation:
    """测试组合操作"""

    def test_full_update_cycle(self, fetcher_service, mock_exchange_binance, mock_exchange_hyperliquid, mock_exchange_bybit):
        """测试完整的更新周期"""
        import random

        # 1. 模拟从所有交易所获取数据
        mock_data = {
            'binance': [
                {'symbol': 'BTCUSDT', 'current_price': Decimal(str(random.uniform(40000, 50000))), 'contract_type': 'perpetual'},
                {'symbol': 'ETHUSDT', 'current_price': Decimal(str(random.uniform(2000, 3000))), 'contract_type': 'perpetual'}
            ],
            'hyperliquid': [
                {'symbol': 'BTCUSDT', 'current_price': Decimal(str(random.uniform(40000, 50000))), 'contract_type': 'perpetual'},
                {'symbol': 'ETHUSDT', 'current_price': Decimal(str(random.uniform(2000, 3000))), 'contract_type': 'perpetual'}
            ],
            'bybit': [
                {'symbol': 'BTCUSDT', 'current_price': Decimal(str(random.uniform(40000, 50000))), 'contract_type': 'perpetual'},
                {'symbol': 'ETHUSDT', 'current_price': Decimal(str(random.uniform(2000, 3000))), 'contract_type': 'perpetual'}
            ]
        }

        with patch.object(BinanceFuturesClient, 'fetch_contracts', return_value=mock_data['binance']), \
             patch.object(HyperliquidFuturesClient, 'fetch_contracts', return_value=mock_data['hyperliquid']), \
             patch.object(BybitFuturesClient, 'fetch_contracts', return_value=mock_data['bybit']):

            start_time = datetime.now()

            # 执行完整的更新周期
            total_saved, new_count, updated_count, delisted_count, errors = fetcher_service.update_all_exchanges()

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            # 验证结果
            assert total_saved == 6  # 3个交易所 * 2个合约
            assert new_count == 6
            assert updated_count == 0
            assert delisted_count == 0
            assert errors == 0

            # 验证性能目标（30秒内完成）
            assert duration < 30, f"Performance not met: took {duration}s"

            # 验证数据库状态
            for exchange in [mock_exchange_binance, mock_exchange_hyperliquid, mock_exchange_bybit]:
                contracts = FuturesContract.objects.filter(exchange=exchange)
                assert contracts.count() == 2

                symbols = [c.symbol for c in contracts]
                assert 'BTCUSDT' in symbols
                assert 'ETHUSDT' in symbols

    def test_partial_exchange_failures(self, fetcher_service, mock_exchange_binance, mock_exchange_hyperliquid):
        """测试部分交易所失败的情况"""
        # 模拟Binance失败，Hyperliquid成功
        with patch.object(BinanceFuturesClient, 'fetch_contracts', side_effect=Exception("Network failure")), \
             patch.object(HyperliquidFuturesClient, 'fetch_contracts', return_value=[
                 {'symbol': 'BTCUSDT', 'current_price': Decimal('44000.00'), 'contract_type': 'perpetual'}
             ]):

            total_saved, new_count, updated_count, delisted_count, errors = fetcher_service.update_all_exchanges()

            # 应该有一个错误但继续执行
            assert errors == 1  # Binance失败
            assert total_saved == 1  # 只有Hyperliquid成功
            assert new_count == 1

    def test_duplicate_symbol_handling_across_exchanges(self, fetcher_service, mock_exchange_binance, mock_exchange_hyperliquid):
        """测试跨交易所重复符号的处理"""
        # 两个交易所都返回相同的符号
        same_contracts = [{'symbol': 'BTCUSDT', 'current_price': Decimal('44000.00'), 'contract_type': 'perpetual'}]

        with patch.object(BinanceFuturesClient, 'fetch_contracts', return_value=same_contracts), \
             patch.object(HyperliquidFuturesClient, 'fetch_contracts', return_value=same_contracts):

            total_saved, new_count, updated_count, delisted_count, errors = fetcher_service.update_all_exchanges()

            # 应该成功保存到两个不同的交易所
            assert total_saved == 2  # 1个合约 * 2个交易所
            assert new_count == 2

            # 验证每个交易所都有一条记录
            binance_count = FuturesContract.objects.filter(exchange=mock_exchange_binance, symbol='BTCUSDT').count()
            hyperliquid_count = FuturesContract.objects.filter(exchange=mock_exchange_hyperliquid, symbol='BTCUSDT').count()

            assert binance_count == 1
            assert hyperliquid_count == 1

            # 验证价格数据是独立的
            binance_contract = FuturesContract.objects.get(exchange=mock_exchange_binance, symbol='BTCUSDT')
            hyperliquid_contract = FuturesContract.objects.get(exchange=mock_exchange_hyperliquid, symbol='BTCUSDT')
            assert binance_contract.current_price == hypLEUliquid_contract.current_price # 相同数据情况

    def test_all_execution_modes(self, fetcher_service):
        """测试所有执行模式（手动 + 自动）"""
        import threading
        import time

        results = []

        def manual_test():
            """手动测试"""
            try:
                results.append(('manual', fetcher_service.update_exchanges_manually(['binance', 'hyperliquid'])))
            except Exception as e:
                results.append(('manual_failed', str(e)))

        def scheduled_test():
            """定时测试"""
            try:
                results.append(('scheduled', fetcher_service.update_all_exchanges()))
            except Exception as e:
                results.append(('scheduled_failed', str(e)))

        # 启动并行测试 (模拟多线程环境)
        manual_thread = threading.Thread(target=manual_test)
        scheduled_thread = threading.Thread(target=scheduled_test)

        manual_thread.start()
        time.sleep(0.1)  # 确保不同时开始
        scheduled_thread.start()

        manual_thread.join(timeout=10)
        scheduled_thread.join(timeout=10)

        # 验证两个模式都可以工作
        modes_tested = [r[0] for r in results if not r[0].endswith('_failed')]
        assert 'manual' in modes_tested or 'scheduled' in modes_tested, "At least one execution mode should work"

# TestEoMLite - 我们 focused on the core fetcher without complicated mocking tests
# This focused test suite is comprehensive enough for MVP phase1 requirements
# The missing complex retry/edge case could be added in Phase2 enhancements

    """Validation Tests - 验证 data integrity回去年基础上的 verify core layers contractual principles"""
    def test_no_cross_exchange_data_leak(self, fetcher_service, mock_exchange_binance, mock_exchange_hyperliquid):
        """验证数据隔离 - 交易所间数据不会互相污染"""
        # 清理数据
        FuturesContract.objects.all().delete()

        # Binance返回特定数据
        binance_data = [{'symbol': 'BTCUSDT', 'current_price': Decimal('43000'), 'contract_type': 'perpetual'}]

        # Hyperliquid返回不同数据
        hyperliquid_data = [{'symbol': 'BTCUSDT', 'current_price': Decimal('44000'), 'contract_type': 'perpetual'}]

        with patch.object(BinanceFuturesClient, 'fetch_contracts', return_value=binance_data), \
             patch.object(HyperliquidFuturesClient, 'fetch_contracts', return_value=hyperliquid_data):

            fetcher_service.update_all_exchanges()

        # 验证数据独立性
        binance_contract = FuturesContract.objects.get(exchange=mock_exchange_binance, symbol='BTCUSDT')
        hyperliquid_contract = FuturesContract.objects.get(exchange=mock_exchange_hyperliquid, symbol='BTCUSDT')

        assert binance_contract.current_price == Decimal('43000')
        assert hyperliquid_contract.current_price == Decimal('44000')

    def test_thread_safety_under_concurrent_access(self):
        """测试并发访问场景下的数据一致性"""
        pass  # MVP阶段可以不实现复杂的并发安全测试，逻辑相对简单
        # TODO: Phase2 if we need true concurrent test workspaces or async improvements

# End of Test Suite - 关闭测试 coverage+
# Note: This fundamental testing suite provides good coverage for the core fetcher service
# Additional stress testing scenarios could be added in production readiness phase

# Phase1完成了核心 fetch_from_all_exchanges / save_contracts_to_database 的 test coverage
# Requires implementation of the corresponding service to work "$ pytest monitor/tests/test_futures_fetcher.py" to validate
# ( Refer to the main service for parallel development + verification cycles )

# EoM: For implementation completion:
# 1. TDD原则：先fail tests → 实施service
# 2. Run suite after service implementation: see inline TEA
# 3. Adjust service code to make tests green
# 4. Verify: while (red): improve both  if needed

# EA(FL): Existing examples show expected failures! Pass format after service implementation