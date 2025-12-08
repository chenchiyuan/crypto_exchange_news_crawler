"""
交易所适配器集成测试
Exchange Adapter Integration Tests

测试适配器与网格引擎的集成
"""
import pytest
from decimal import Decimal

from grid_trading.models import GridConfig
from grid_trading.services.grid.engine import GridEngine
from grid_trading.services.exchange.grvt_adapter import GRVTExchangeAdapter, GRVTCredentials
from grid_trading.services.exchange.factory import create_adapter


@pytest.mark.django_db
class TestAdapterIntegration:
    """适配器集成测试"""

    @pytest.fixture
    def grid_config(self):
        """创建测试网格配置"""
        config = GridConfig.objects.create(
            name="TEST_ADAPTER_GRID",
            exchange="grvt",
            symbol="BTCUSD",
            grid_mode="SHORT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=10,
            trade_amount=Decimal("0.001"),
            max_position_size=Decimal("0.01"),
            price_tick=Decimal("0.01"),
            qty_step=Decimal("0.001"),
            is_active=False
        )
        return config

    @pytest.fixture
    def grvt_adapter(self):
        """创建GRVT适配器"""
        creds = GRVTCredentials(
            api_key="test_key",
            api_secret="test_secret",
            sub_account_id="test_sub",
            instrument="BTC-USD"
        )
        return GRVTExchangeAdapter(creds)

    def test_grid_engine_with_adapter(self, grid_config, grvt_adapter):
        """测试GridEngine接受适配器"""
        engine = GridEngine(grid_config, grvt_adapter)

        assert engine.config == grid_config
        assert engine.exchange_adapter == grvt_adapter
        assert engine.exchange_adapter.id == "grvt"

    def test_grid_engine_without_adapter(self, grid_config):
        """测试GridEngine不使用适配器（回测模式）"""
        engine = GridEngine(grid_config)

        assert engine.config == grid_config
        assert engine.exchange_adapter is None

    def test_grid_engine_with_factory_adapter(self, grid_config):
        """测试GridEngine使用工厂创建的适配器"""
        adapter = create_adapter("grvt", {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "sub_account_id": "test_sub",
            "instrument": "BTC-USD"
        })

        engine = GridEngine(grid_config, adapter)

        assert engine.exchange_adapter is not None
        assert engine.exchange_adapter.id == "grvt"

    def test_grid_levels_calculation_with_adapter(self, grid_config, grvt_adapter):
        """测试有适配器时的网格层级计算"""
        engine = GridEngine(grid_config, grvt_adapter)

        levels = engine.calculate_grid_levels()

        assert len(levels) == 10
        assert all('level_index' in level for level in levels)
        assert all('price' in level for level in levels)
        assert all('side' in level for level in levels)

    def test_grid_initialization_with_adapter(self, grid_config, grvt_adapter):
        """测试有适配器时的网格初始化"""
        engine = GridEngine(grid_config, grvt_adapter)

        created_levels = engine.initialize_grid()

        assert len(created_levels) == 10
        # 验证数据库中确实创建了层级
        from grid_trading.models import GridLevel
        db_levels = GridLevel.objects.filter(config=grid_config)
        assert db_levels.count() == 10

    @pytest.mark.asyncio
    async def test_adapter_precision_query(self, grvt_adapter):
        """测试从适配器查询精度信息"""
        precision = await grvt_adapter.get_precision("BTCUSD")

        assert precision is not None
        assert "price_tick" in precision
        assert "qty_step" in precision
        assert isinstance(precision["price_tick"], Decimal)

    @pytest.mark.asyncio
    async def test_adapter_create_order_from_engine(self, grid_config, grvt_adapter):
        """测试通过引擎的适配器创建订单"""
        engine = GridEngine(grid_config, grvt_adapter)

        # 模拟创建订单
        order = await engine.exchange_adapter.create_order({
            "symbol": "BTCUSD",
            "side": "SELL",
            "type": "LIMIT",
            "quantity": 0.001,
            "price": 45000,
            "client_order_id": "test_order_from_engine"
        })

        assert order is not None
        assert order["symbol"] == "BTCUSD"
        assert order["side"] == "SELL"
        assert "order_id" in order


@pytest.mark.django_db
class TestAdapterConfigurationMethods:
    """适配器配置方法测试"""

    def test_adapter_from_env_vars(self, monkeypatch):
        """测试从环境变量创建适配器"""
        monkeypatch.setenv("GRVT_API_KEY", "env_test_key")
        monkeypatch.setenv("GRVT_API_SECRET", "env_test_secret")
        monkeypatch.setenv("GRVT_SUB_ACCOUNT_ID", "env_test_sub")
        monkeypatch.setenv("GRVT_INSTRUMENT", "BTC-USD")

        adapter = create_adapter("grvt")

        assert adapter.id == "grvt"
        assert adapter.credentials.api_key == "env_test_key"
        assert adapter.credentials.sub_account_id == "env_test_sub"

    def test_adapter_explicit_credentials_override_env(self, monkeypatch):
        """测试显式凭据覆盖环境变量"""
        monkeypatch.setenv("GRVT_API_KEY", "env_key")
        monkeypatch.setenv("GRVT_SUB_ACCOUNT_ID", "env_sub")
        monkeypatch.setenv("GRVT_INSTRUMENT", "BTC-USD")

        adapter = create_adapter("grvt", {
            "api_key": "explicit_key",
            "api_secret": "explicit_secret",
            "sub_account_id": "explicit_sub",
            "instrument": "ETH-USD"
        })

        assert adapter.credentials.api_key == "explicit_key"
        assert adapter.credentials.sub_account_id == "explicit_sub"
        assert adapter.credentials.instrument == "ETH-USD"
