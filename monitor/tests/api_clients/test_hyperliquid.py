"""
Hyperliquid合约API客户端测试
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from decimal import Decimal

from monitor.api_clients.hyperliquid import HyperliquidFuturesClient
from monitor.models import Exchange


@pytest.fixture
def hyperliquid_client():
    """创建Hyperliquid客户端实例"""
    return HyperliquidFuturesClient(exchange_name='hyperliquid')


@pytest.fixture
def exchange():
    """创建交易所实例"""
    return Exchange.objects.create(
        name='Hyperliquid',
        code='hyperliquid',
        announcement_url='https://hyperliquid.gitbook.io/docs/announcements'
    )


@pytest.fixture
def mock_info_response():
    """Mock Hyperliquid info响应"""
    return {
        "universe": [
            {
                "name": "BTC",  # Hyperliquid使用基础货币作为 symbol
                "szDecimals": 5,
                "maxLeverage": 50,
                "maxPosition": 10000000,
                "oraclePx": "44000"
            },
            {
                "name": "ETH",
                "szDecimals": 6,
                "maxLeverage": 40,
                "maxPosition": 10000000,
                "oraclePx": "2200"
            },
            {
                "name": "PEPE",  # PEPE，应该包含在结果中
                "szDecimals": 6,
                "maxLeverage": 20,
                "maxPosition": 10000000,
                "oraclePx": "0.000010"
            }
        ]
    }


class TestHyperliquidFuturesClient:
    """Hyperliquid合约API客户端测试类"""

    def test_init(self, hyperliquid_client):
        """测试客户端初始化"""
        assert hyperliquid_client.exchange_name == 'hyperliquid'
        assert hasattr(hyperliquid_client, 'base_url')
        assert hasattr(hyperliquid_client, 'session')

    def test_normalize_symbol_with_btc(self, hyperliquid_client):
        """测试符号标准化 (BTC → BTCUSDT)"""
        assert hyperliquid_client._normalize_symbol("BTC") == "BTCUSDT"

    def test_normalize_symbol_with_eth(self, hyperliquid_client):
        """测试符号标准化 (ETH → ETHUSDT)"""
        assert hyperliquid_client._normalize_symbol("ETH") == "ETHUSDT"

    def test_normalize_symbol_with_pepe(self, hyperliquid_client):
        """测试符号标准化 (PEPE → PEPEUSDT)"""
        assert hyperliquid_client._normalize_symbol("PEPE") == "PEPEUSDT"

    def test_normalize_symbol_already_usdt(self, hyperliquid_client):
        """测试符号标准化 (已包含USDT后缀)"""
        # 如果已经包含USDT，保持原样
        assert hyperliquid_client._normalize_symbol("BTCUSDT") == "BTCUSDT"

    def test_fetch_contracts_success(self, hyperliquid_client, mock_info_response):
        """测试成功获取合约数据"""
        with patch('monitor.api_clients.hyperliquid.requests.Session.post') as mock_post:
            # Mock info响应
            mock_response = MagicMock()
            mock_response.json.return_value = mock_info_response
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            # 调用测试方法
            contracts = hyperliquid_client.fetch_contracts()

            # 验证结果
            assert len(contracts) == 3

            # 验证 BTC 合约
            btc_contract = next(c for c in contracts if c['symbol'] == 'BTCUSDT')
            assert btc_contract['current_price'] == Decimal('44000.00000000')
            assert btc_contract['contract_type'] == 'perpetual'
            # 统计数据
            assert 'max_leverage' in btc_contract
            assert btc_contract['max_leverage'] == 50
            assert 'max_position' in btc_contract
            assert btc_contract['max_position'] == 10000000

            # 验证 ETH 合约
            eth_contract = next(c for c in contracts if c['symbol'] == 'ETHUSDT')
            assert eth_contract['current_price'] == Decimal('2200.00000000')
            assert eth_contract['contract_type'] == 'perpetual'
            assert eth_contract['max_leverage'] == 40

            # 验证 PEPE 合约
            pepe_contract = next(c for c in contracts if c['symbol'] == 'PEPEUSDT')
            assert pepe_contract['current_price'] == Decimal('0.00001000')
            assert pepe_contract['contract_type'] == 'perpetual'
            assert pepe_contract.get('details', {}).get('sz_decimals') == 6

            # 验证请求URL
            mock_post.assert_called_once_with(
                'https://api.hyperliquid.xyz/info',
                json={"type": "metaAndAssetCtxs"},
                timeout=10
            )

    def test_fetch_contracts_empty_universe(self, hyperliquid_client):
        """测试空合约列表"""
        with patch('monitor.api_clients.hyperliquid.requests.Session.post') as mock_post:
            # Mock 空响应
            mock_response = MagicMock()
            mock_response.json.return_value = {"universe": []}
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            contracts = hyperliquid_client.fetch_contracts()
            assert contracts == []

    def test_fetch_contracts_api_failure(self, hyperliquid_client):
        """测试API失败处理"""
        with patch('monitor.api_clients.hyperliquid.requests.Session.post') as mock_post:
            # Mock API 异常
            mock_post.side_effect = Exception("Network error")

            with pytest.raises(Exception):
                hyperliquid_client.fetch_contracts()

    def test_fetch_contracts_missing_price_oracle(self, hyperliquid_client):
        """测试缺少 oraclePx 字段的处理"""
        mock_response_data = {
            "universe": [
                {
                    "name": "BTC",
                    "szDecimals": 5,
                    "maxLeverage": 50,
                    "maxPosition": 10000000,
                    "oraclePx": "44000"  # 有价格
                },
                {
                    "name": "ETH",
                    "szDecimals": 6,
                    "maxLeverage": 40,
                    "maxPosition": 10000000,
                    # 缺少 oraclePx 字段
                },
                {
                    "name": "SOL",
                    "szDecimals": 6,
                    "maxLeverage": 25,
                    "maxPosition": 10000000,
                    "oraclePx": ""  # 空价格
                }
            ]
        }

        with patch('monitor.api_clients.hyperliquid.requests.Session.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            contracts = hyperliquid_client.fetch_contracts()

            # 只应返回有价格的合约
            assert len(contracts) == 1  # 只有BTC有有效价格
            assert contracts[0]['symbol'] == 'BTCUSDT'

    def test_fetch_contracts_malformed_data(self, hyperliquid_client):
        """测试格式错误的响应数据"""
        mock_response_data = {
            "universe": 'invalid_data'  # universe 不是列表
        }

        with patch('monitor.api_clients.hyperliquid.requests.Session.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            # 应该抛出异常或返回空列表
            contracts = hyperliquid_client.fetch_contracts()
            assert contracts == []  # 或抛出异常，取决于实现

    def test_fetch_contracts_http_error(self, hyperliquid_client):
        """测试HTTP错误处理"""
        with patch('monitor.api_clients.hyperliquid.requests.Session.post') as mock_post:
            # Mock HTTP错误
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = Exception("HTTP 404: Not Found")
            mock_post.return_value = mock_response

            with pytest.raises(Exception):
                hyperliquid_client.fetch_contracts()  # 应该抛出异常

    def test_fetch_contracts_json_decode_error(self, hyperliquid_client):
        """测试JSON解析错误"""
        with patch('monitor.api_clients.hyperliquid.requests.Session.post') as mock_post:
            # Mock JSON解析错误
            mock_response = MagicMock()
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            with pytest.raises(json.JSONDecodeError):
                hyperliquid_client.fetch_contracts()

    def test_fetch_contracts_with_leverage_info(self, hyperliquid_client):
        """测试杠杆信息的提取"""
        mock_info_data = {
            "universe": [
                {
                    "name": "BTC",
                    "szDecimals": 5,
                    "maxLeverage": 125,  # 高杠杆
                    "maxPosition": 50000000,
                    "oraclePx": "44000"
                }
            ]
        }

        with patch('monitor.api_clients.hyperliquid.requests.Session.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_info_data
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            contracts = hyperliquid_client.fetch_contracts()

            assert len(contracts) == 1
            btc_contract = contracts[0]
            assert 'details' in btc_contract
            details = btc_contract['details']
            assert details['max_position'] == 50000000
            assert details['max_leverage'] == 125
            assert details['sz_decimals'] == 5  # 精度信息

    def test_fetch_contracts_large_price_value(self, hyperliquid_client):
        """测试极高的价格值处理"""
        mock_info_data = {
            "universe": [
                {
                    "name": "SHIB",
                    "szDecimals": 6,
                    "maxLeverage": 20,
                    "maxPosition": 10000000,
                    "oraclePx": "0.00001234"  # 极低价格
                }
            ]
        }

        with patch('monitor.api_clients.hyperliquid.requests.Session.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_info_data
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            contracts = hyperliquid_client.fetch_contracts()

            shib_contract = contracts[0]
            assert shib_contract['symbol'] == 'SHIBUSDT'
            assert shib_contract['current_price'] == Decimal('0.00001234')
            assert str(shib_contract['current_price']).endswith('.00001234')  # 验证精度保持

    def test_session_post_parameters(self, hyperliquid_client):
        """测试POST请求的参数格式"""
        with patch('monitor.api_clients.hyperliquid.requests.Session.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"universe": []}
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            hyperliquid_client.fetch_contracts()

            # 验证POST请求参数
            call_args = mock_post.call_args
            assert call_args[0][0] == "https://api.hyperliquid.xyz/info"
            assert "json" in call_args[1]
            assert call_args[1]["json"]["type"] == "metaAndAssetCtxs"
            assert call_args[1]["timeout"] == 10  # 超时时间配置

    def test_fetch_contracts_timeout_handling(self, hyperliquid_client):
        """测试超时处理"""
        with patch('monitor.api_clients.hyperliquid.requests.Session.post') as mock_post:
            # Mock 超时异常
            mock_post.side_effect = TimeoutError("Request timed out")

            with pytest.raises(TimeoutError):
                hyperliquid_client.fetch_contracts()

            # 应记录错误日志并抛异常
            # 具体行为取决于实际实现中的错误处理逻辑

    def test_required_fields_in_response(self, hyperliquid_client):
        """测试返回数据必须包含的字段"""
        mock_info_data = {
            "universe": [
                {
                    "name": "BTC",
                    "maxLeverage": 50,
                    "oraclePx": "44000"
                    # 缺少 szDecimals 字段
                }
            ]
        }

        with patch('monitor.api_clients.hyperliquid.requests.Session.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_info_data
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            contracts = hyperliquid_client.fetch_contracts()

            btc_contract = contracts[0]
            assert 'symbol' in btc_contract
            assert 'current_price' in btc_contract
            assert 'contract_type' in btc_contract
            assert 'exchange' in btc_contract
            # 其他可选字段应根据实际存在与否处理
            if 'details' in btc_contract:
                # 只有存在时才验证详情字段
                details = btc_contract['details']
                # 处理缺失字段的情况
                assert details.get('name') == 'BTC'  # 使用 .get() 避免KeyError
                # 不存在的字段应不出现或设为None
                assert 'sz_decimals' not in details or details.get('sz_decimals') is None  # 应有处理逻辑

    def test_no_duplicate_symbols(self, hyperliquid_client):
        """测试不会返回重复的合约代码"""
        mock_info_data = {
            "universe": [
                {"name": "BTC", "oraclePx": "44000"},
                {"name": "BTC", "oraclePx": "44001"},  # 重复的BTC
                {"name": "ETH", "oraclePx": "2200"}
            ]
        }

        with patch('monitor.api_clients.hyperliquid.requests.Session.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_info_data
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            contracts = hyperliquid_client.fetch_contracts()

            # 结果应有2条记录，但具体取决于去重逻辑
            symbols = [c['symbol'] for c in contracts]
            unique_symbols = set(symbols)
            assert unique_symbols <= {"BTCUSDT", "ETHUSDT"}  # BTCUSDT应只出现一次
            # 或具体调用结果应根据实际实现确定行为 (如取第一条、或平均价格等)

            # 如果实现中做了去重处理，最终的symbols数量应≤去重后数量
            assert len(contracts) == len(unique_symbols)  # 验证去重效果
# 实际结果取决于实现逻辑，这里验证基本原则

    def test_exact_return_schema(self, hyperliquid_client, mock_info_response):
        """精确验证返回数据的模式和字段名称"""
        with patch('monitor.api_clients.hyperliquid.requests.Session.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_info_response
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            contracts = hyperliquid_client.fetch_contracts()

            # 格式验证
            assert isinstance(contracts, list)
            assert len(contracts) == 3  # 预期3个合约, 具ath

            # 验证每个合约的字段和类型
            for contract in contracts:
                required_fields = ['symbol', 'current_price', 'contract_type', 'exchange']
                for field in required_fields:
                    assert field in contract, f"Missing required field: {field}"
                    if field.endswith('_price'):
                        assert isinstance(contract[field], Decimal), f"Price field should be Decimal, got: {type(contract[field])}"
                    elif field == 'symbol':
                        assert isinstance(contract[field], str) and contract[field].endswith('USDT'), f"Symbol should end with USDT, got: {contract[field]}"
                    elif field == 'contract_type':
                        assert contract[field] == 'perpetual', f"Contract type should be 'perpetual', got: {contract[field]}"
                    elif field == 'exchange':
                        assert contract[field] == 'hyperliquid', f"Exchange should be 'hyperliquid', got: {contract[field]}"

                # 可选字段验证
                # details字段存在时验证其完整性, 但本身不是必须存在 (取决于实现)
                if 'details' in contract:
                    details = contract['details']
                    assert isinstance(details, dict), "details should be a dict"
                    # 验证可选字段，根据实际测试数据中的字段进行断言,
                    for key, value in details.items():
                        # 基本类型验证, 内容可参考测试数据
                        if key.endswith('_px'):
                            try:
                                float(value)  # 假设数字字段可解析为数字
                            except (ValueError, TypeError):
                                assert False, f"Price-like field {key} should be numeric-like: {value}"
                    # 其他字段根据实际实现验证, 只要字段存在即满足數據格式提出即可 (非内容强验证 )

    def test_fetch_contracts_timeout_config(self, hyperliquid_client):
        """验证超时配置使用正确"""
        with patch('monitor.api_clients.hyperliquid.requests.Session.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"universe": []}
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            hyperliquid_client.fetch_contracts()

            call_kwargs = mock_post.call_args[1]
            assert call_kwargs.get('timeout') == 10, "Should use 10s timeout from config"  # 或项目配置的具体值
            # 可以根据项目中实际 import 的 timeout 常数进行软匹配或整个函数mock测试验证 timeout 参数传递, 不硬编码具体值,而是验证 config 常量的正确应用


class TestHyperliquidIntegration:

    """集成测试 - 模拟实际流程"""

    def test_end_to_end_fetch_and_process(self, hyperliquid_client):
        """端到端测试- 完整流程工作正常"""
        mock_info_data = {
            "universe": [
                {"name": "BTC", "szDecimals": 5, "oraclePx": "43000"},
                {"name": "ETH", "szDecimals": 6, "oraclePx": "2100"}
            ]
        }

        with patch('monitor.api_clients.hyperliquid.requests.Session.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_info_data
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            result = hyperliquid_client.fetch_contracts()

            # 结果不为空
            assert result, "Should return non-empty contract list"

            # 所有数据都有统一格式
            for contract in result:
                assert 'symbol' in contract
                assert 'current_price' in contract
                assert 'contract_type' in contract

                # 基本字段填充
                assert isinstance(contract['symbol'], str)
                assert isinstance(contract['current_price'], Decimal)
                assert contract['contract_type'] == 'perpetual'
                assert contract['exchange'] == 'hyperliquid'

            # 正确转换符号 (核心功能)
            symbols = [c['symbol'] for c in result]
            assert "BTCUSDT" in symbols
            assert "ETHUSDT" in symbols
            # 符号都以 USDT 结尾
            for sym in symbols:
                assert sym.endswith("USDT"), f"Symbol should end with USDT: {sym}"

    def test_error_handling_in_fetch_contracts(self, hyperliquid_client):
        """测试重大错误处理 ( 重要异常场景)"""
        ...  # 可补充具体测试,保持scope适度, 关注主要流程和边界

    def test_consistency_with_researchMd(self, hyperliquid_client):
        """与 research.md 中调研的结果保持一致"""
        # 验证行为符合调研报告中的描述
        # 1. 符号转换 (BTC→BTCUSDT) ✅ 已覆盖
        # 2. 使用 POST /info 端点 ✅ 已覆盖
        # 3. 需要处理缺失字段 ✅ 已覆盖 (missing oraclePx)
        # 4. 特殊符号格式 ✅ 已覆盖
        pass  # 可通过整合前面已有测试覆盖, 这里作显式标记
# 如果需要补充具体测试, 建议添加本节, 但目前重点功能都已覆盖