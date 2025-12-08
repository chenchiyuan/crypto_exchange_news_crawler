"""
交易所适配器单元测试
Exchange Adapter Unit Tests
"""
import pytest
import os
from decimal import Decimal

from grid_trading.services.exchange.grvt_adapter import GRVTExchangeAdapter, GRVTCredentials
from grid_trading.services.exchange.factory import create_adapter, get_supported_exchanges
from grid_trading.services.exchange.types import CreateOrderParams, OrderSide, OrderType


class TestGRVTCredentials:
    """GRVT凭据测试"""

    def test_credentials_from_params(self):
        """测试从参数创建凭据"""
        creds = GRVTCredentials(
            api_key="test_key",
            api_secret="test_secret",
            sub_account_id="test_sub_account",
            instrument="BTC-USD",
            symbol="BTCUSD"
        )

        assert creds.api_key == "test_key"
        assert creds.api_secret == "test_secret"
        assert creds.sub_account_id == "test_sub_account"
        assert creds.instrument == "BTC-USD"
        assert creds.symbol == "BTCUSD"

    def test_credentials_missing_required(self):
        """测试缺少必填参数"""
        with pytest.raises(ValueError, match="Missing GRVT_SUB_ACCOUNT_ID"):
            GRVTCredentials(api_key="test_key")

    def test_symbol_normalization(self):
        """测试symbol标准化"""
        creds = GRVTCredentials(
            api_key="test_key",
            sub_account_id="test_sub",
            instrument="BTC_USD"
        )
        assert creds.symbol == "BTCUSD"


class TestGRVTAdapter:
    """GRVT适配器测试"""

    @pytest.fixture
    def adapter(self):
        """创建测试用适配器"""
        creds = GRVTCredentials(
            api_key="test_key",
            api_secret="test_secret",
            sub_account_id="test_sub",
            instrument="BTC-USD"
        )
        return GRVTExchangeAdapter(creds)

    def test_adapter_id(self, adapter):
        """测试适配器ID"""
        assert adapter.id == "grvt"

    def test_supports_trailing_stops(self, adapter):
        """测试是否支持追踪止损"""
        assert adapter.supports_trailing_stops() is False

    def test_watch_account(self, adapter):
        """测试监听账户"""
        called = []

        def callback(snapshot):
            called.append(snapshot)

        adapter.watch_account(callback)
        assert adapter._account_callback is not None

    def test_watch_orders(self, adapter):
        """测试监听订单"""
        called = []

        def callback(orders):
            called.append(orders)

        adapter.watch_orders(callback)
        assert adapter._orders_callback is not None

    @pytest.mark.asyncio
    async def test_create_order(self, adapter):
        """测试创建订单"""
        params: CreateOrderParams = {
            "symbol": "BTCUSD",
            "side": "BUY",
            "type": "LIMIT",
            "quantity": 0.001,
            "price": 50000,
            "client_order_id": "test_order_1"
        }

        order = await adapter.create_order(params)

        assert order["symbol"] == "BTCUSD"
        assert order["side"] == "BUY"
        assert order["type"] == "LIMIT"
        assert order["status"] == "NEW"
        assert "order_id" in order

    @pytest.mark.asyncio
    async def test_cancel_order(self, adapter):
        """测试撤销订单"""
        # 不应该抛出异常
        await adapter.cancel_order("BTCUSD", "test_order_1")

    @pytest.mark.asyncio
    async def test_get_precision(self, adapter):
        """测试获取精度"""
        precision = await adapter.get_precision("BTCUSD")

        assert precision is not None
        assert "price_tick" in precision
        assert "qty_step" in precision
        assert isinstance(precision["price_tick"], Decimal)
        assert isinstance(precision["qty_step"], Decimal)


class TestExchangeFactory:
    """交易所工厂测试"""

    def test_create_grvt_adapter(self):
        """测试创建GRVT适配器"""
        credentials = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "sub_account_id": "test_sub",
            "instrument": "BTC-USD"
        }

        adapter = create_adapter("grvt", credentials)

        assert adapter.id == "grvt"
        assert isinstance(adapter, GRVTExchangeAdapter)

    def test_create_unsupported_exchange(self):
        """测试创建不支持的交易所"""
        with pytest.raises(ValueError, match="不支持的交易所类型"):
            create_adapter("binance")

    def test_get_supported_exchanges(self):
        """测试获取支持的交易所列表"""
        exchanges = get_supported_exchanges()

        assert isinstance(exchanges, list)
        assert "grvt" in exchanges
