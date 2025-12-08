"""
订单同步管理器单元测试
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, MagicMock

from grid_trading.models import (
    GridConfig, GridLevel, GridLevelSide, GridLevelStatus,
    OrderIntent, OrderIntentType, OrderSide
)
from grid_trading.services.grid.order_sync import OrderSyncManager


@pytest.fixture
def grid_config(db, grid_config_data):
    """创建测试用网格配置"""
    return GridConfig.objects.create(**grid_config_data)


@pytest.fixture
def initialized_grid(grid_config):
    """创建初始化的网格层级"""
    from grid_trading.services.grid.engine import GridEngine
    engine = GridEngine(grid_config)
    levels = engine.initialize_grid()
    return grid_config, levels


@pytest.fixture
def mock_exchange():
    """模拟交易所适配器"""
    exchange = Mock()
    exchange.create_order = MagicMock(return_value={
        'orderId': '12345678',
        'status': 'NEW'
    })
    exchange.cancel_order = MagicMock(return_value={
        'orderId': '12345678',
        'status': 'CANCELED'
    })
    return exchange


@pytest.mark.django_db
class TestOrderSyncManager:
    """OrderSyncManager测试"""

    def test_initialization(self, grid_config):
        """测试初始化"""
        manager = OrderSyncManager(grid_config)
        assert manager.config == grid_config

    def test_generate_client_order_id_format(self, grid_config):
        """测试client_order_id生成格式"""
        manager = OrderSyncManager(grid_config)
        client_id = manager.generate_client_order_id(
            intent=OrderIntentType.ENTRY,
            side=OrderSide.SELL,
            level_index=5
        )

        # 验证格式: name_intent_side_level_timestamp_random
        parts = client_id.split('_')
        assert parts[0] == 'test'
        assert parts[1] == 'btc'
        assert parts[2] == 'short'
        assert parts[3] == OrderIntentType.ENTRY
        assert parts[4] == OrderSide.SELL
        assert parts[5] == '5'
        # 验证倒数第二部分是时间戳（13位数字）
        assert parts[6].isdigit()
        assert len(parts[6]) == 13  # 毫秒时间戳是13位
        # 验证最后一部分是4位随机hex
        assert len(parts[7]) == 4

    def test_generate_client_order_id_uniqueness(self, grid_config):
        """测试client_order_id唯一性"""
        manager = OrderSyncManager(grid_config)

        id1 = manager.generate_client_order_id(
            intent=OrderIntentType.ENTRY,
            side=OrderSide.SELL,
            level_index=5
        )
        id2 = manager.generate_client_order_id(
            intent=OrderIntentType.ENTRY,
            side=OrderSide.SELL,
            level_index=5
        )

        # 由于使用时间戳，相同参数在不同时间调用会生成不同ID
        assert id1 != id2

        # 不同层级应生成不同ID
        id3 = manager.generate_client_order_id(
            intent=OrderIntentType.ENTRY,
            side=OrderSide.SELL,
            level_index=6
        )
        assert id1 != id3
        assert id2 != id3

    def test_sync_orders_create_new_orders(self, initialized_grid, mock_exchange):
        """测试创建新订单"""
        grid_config, levels = initialized_grid
        manager = OrderSyncManager(grid_config)

        # 准备理想订单（2个开仓单）
        ideal_orders = [
            {
                'level': levels[10],  # 上方层级
                'level_index': levels[10].level_index,
                'intent': OrderIntentType.ENTRY,
                'side': OrderSide.SELL,
                'price': levels[10].price,
                'amount': Decimal('0.01')
            },
            {
                'level': levels[11],
                'level_index': levels[11].level_index,
                'intent': OrderIntentType.ENTRY,
                'side': OrderSide.SELL,
                'price': levels[11].price,
                'amount': Decimal('0.01')
            }
        ]

        # 执行同步
        created, cancelled = manager.sync_orders(ideal_orders, mock_exchange)

        assert len(created) == 2
        assert len(cancelled) == 0

        # 验证交易所API被调用
        assert mock_exchange.create_order.call_count == 2

        # 验证OrderIntent已创建
        intents = OrderIntent.objects.filter(config=grid_config)
        assert intents.count() == 2

        # 验证GridLevel状态已更新
        levels[10].refresh_from_db()
        assert levels[10].status == GridLevelStatus.ENTRY_WORKING
        assert levels[10].entry_order_id is not None

    def test_sync_orders_cancel_excess_orders(self, initialized_grid, mock_exchange):
        """测试撤销多余订单"""
        grid_config, levels = initialized_grid
        manager = OrderSyncManager(grid_config)

        # 先创建一个订单
        level = levels[10]
        level.transition_to_entry_working('12345', 'test_client_id')

        from grid_trading.models import OrderStatus
        OrderIntent.objects.create(
            config=grid_config,
            level_index=level.level_index,
            intent=OrderIntentType.ENTRY,
            side=OrderSide.SELL,
            price=level.price,
            amount=Decimal('0.01'),
            client_order_id='test_client_id',
            order_id='12345',
            status=OrderStatus.NEW
        )

        # 理想订单为空（需要撤销所有订单）
        ideal_orders = []

        # 执行同步
        created, cancelled = manager.sync_orders(ideal_orders, mock_exchange)

        assert len(created) == 0
        assert len(cancelled) == 1

        # 验证交易所API被调用
        mock_exchange.cancel_order.assert_called_once()

        # 验证OrderIntent状态已更新
        intent = OrderIntent.objects.get(client_order_id='test_client_id')
        assert intent.status == OrderStatus.CANCELED

        # 验证GridLevel状态已更新
        level.refresh_from_db()
        assert level.status == GridLevelStatus.IDLE
        assert level.entry_order_id is None

    def test_sync_orders_idempotent(self, initialized_grid, mock_exchange):
        """测试幂等性：相同订单不重复创建"""
        grid_config, levels = initialized_grid
        manager = OrderSyncManager(grid_config)

        ideal_orders = [
            {
                'level': levels[10],
                'level_index': levels[10].level_index,
                'intent': OrderIntentType.ENTRY,
                'side': OrderSide.SELL,
                'price': levels[10].price,
                'amount': Decimal('0.01')
            }
        ]

        # 第一次同步：应该创建订单
        created1, cancelled1 = manager.sync_orders(ideal_orders, mock_exchange)
        assert len(created1) == 1
        assert len(cancelled1) == 0

        # 第二次同步：相同订单应该不创建
        created2, cancelled2 = manager.sync_orders(ideal_orders, mock_exchange)
        assert len(created2) == 0
        assert len(cancelled2) == 0

        # 验证交易所API只调用了一次
        assert mock_exchange.create_order.call_count == 1

    def test_sync_orders_skip_blocked_level_create(self, initialized_grid, mock_exchange):
        """测试跳过冷却期层级的创建"""
        grid_config, levels = initialized_grid
        manager = OrderSyncManager(grid_config)

        # 设置层级为冷却状态
        level = levels[10]
        level.set_blocked(duration_ms=5000)

        ideal_orders = [
            {
                'level': level,
                'level_index': level.level_index,
                'intent': OrderIntentType.ENTRY,
                'side': OrderSide.SELL,
                'price': level.price,
                'amount': Decimal('0.01')
            }
        ]

        # 执行同步
        created, cancelled = manager.sync_orders(ideal_orders, mock_exchange)

        # 应该跳过创建
        assert len(created) == 0
        assert mock_exchange.create_order.call_count == 0

    def test_sync_orders_skip_blocked_level_cancel(self, initialized_grid, mock_exchange):
        """测试跳过冷却期层级的撤销"""
        grid_config, levels = initialized_grid
        manager = OrderSyncManager(grid_config)

        # 先创建一个订单
        level = levels[10]
        level.transition_to_entry_working('12345', 'test_client_id')

        from grid_trading.models import OrderStatus
        OrderIntent.objects.create(
            config=grid_config,
            level_index=level.level_index,
            intent=OrderIntentType.ENTRY,
            side=OrderSide.SELL,
            price=level.price,
            amount=Decimal('0.01'),
            client_order_id='test_client_id',
            order_id='12345',
            status=OrderStatus.NEW
        )

        # 设置层级为冷却状态
        level.set_blocked(duration_ms=5000)

        # 理想订单为空（需要撤销）
        ideal_orders = []

        # 执行同步
        created, cancelled = manager.sync_orders(ideal_orders, mock_exchange)

        # 应该跳过撤销
        assert len(cancelled) == 0
        assert mock_exchange.cancel_order.call_count == 0

    def test_create_order_failure_sets_cooldown(self, initialized_grid, mock_exchange):
        """测试创建订单失败后设置冷却期"""
        grid_config, levels = initialized_grid
        manager = OrderSyncManager(grid_config)

        # 模拟交易所API失败
        mock_exchange.create_order = MagicMock(side_effect=Exception("API Error"))

        level = levels[10]
        ideal_orders = [
            {
                'level': level,
                'level_index': level.level_index,
                'intent': OrderIntentType.ENTRY,
                'side': OrderSide.SELL,
                'price': level.price,
                'amount': Decimal('0.01')
            }
        ]

        # 执行同步
        created, cancelled = manager.sync_orders(ideal_orders, mock_exchange)

        # 创建应该失败
        assert len(created) == 0

        # 验证层级被设置为冷却状态
        level.refresh_from_db()
        assert level.is_blocked() is True

    def test_cancel_order_failure_sets_cooldown(self, initialized_grid, mock_exchange):
        """测试撤销订单失败后设置冷却期"""
        grid_config, levels = initialized_grid
        manager = OrderSyncManager(grid_config)

        # 先创建一个订单
        level = levels[10]
        level.transition_to_entry_working('12345', 'test_client_id')

        from grid_trading.models import OrderStatus
        OrderIntent.objects.create(
            config=grid_config,
            level_index=level.level_index,
            intent=OrderIntentType.ENTRY,
            side=OrderSide.SELL,
            price=level.price,
            amount=Decimal('0.01'),
            client_order_id='test_client_id',
            order_id='12345',
            status=OrderStatus.NEW
        )

        # 模拟交易所API失败
        mock_exchange.cancel_order = MagicMock(side_effect=Exception("API Error"))

        # 理想订单为空（需要撤销）
        ideal_orders = []

        # 执行同步
        created, cancelled = manager.sync_orders(ideal_orders, mock_exchange)

        # 撤销应该失败
        assert len(cancelled) == 0

        # 验证层级被设置为冷却状态
        level.refresh_from_db()
        assert level.is_blocked() is True

    def test_sync_orders_without_exchange_adapter(self, initialized_grid):
        """测试无交易所适配器时（测试模式）"""
        grid_config, levels = initialized_grid
        manager = OrderSyncManager(grid_config)

        ideal_orders = [
            {
                'level': levels[10],
                'level_index': levels[10].level_index,
                'intent': OrderIntentType.ENTRY,
                'side': OrderSide.SELL,
                'price': levels[10].price,
                'amount': Decimal('0.01')
            }
        ]

        # 不传入exchange_adapter（测试模式）
        created, cancelled = manager.sync_orders(ideal_orders, None)

        # 应该创建订单（使用模拟ID）
        assert len(created) == 1

        # 验证OrderIntent已创建
        intent = OrderIntent.objects.filter(config=grid_config).first()
        assert intent is not None
        assert intent.order_id.startswith('test_')

    def test_sync_orders_mixed_scenario(self, initialized_grid, mock_exchange):
        """测试混合场景：同时创建和撤销"""
        grid_config, levels = initialized_grid
        manager = OrderSyncManager(grid_config)

        # 先创建订单A
        levelA = levels[10]
        levelA.transition_to_entry_working('order_A', 'client_A')

        from grid_trading.models import OrderStatus
        OrderIntent.objects.create(
            config=grid_config,
            level_index=levelA.level_index,
            intent=OrderIntentType.ENTRY,
            side=OrderSide.SELL,
            price=levelA.price,
            amount=Decimal('0.01'),
            client_order_id='client_A',
            order_id='order_A',
            status=OrderStatus.NEW
        )

        # 理想订单：保留订单B，创建订单C
        levelB = levels[11]
        levelC = levels[12]

        ideal_orders = [
            {
                'level': levelB,
                'level_index': levelB.level_index,
                'intent': OrderIntentType.ENTRY,
                'side': OrderSide.SELL,
                'price': levelB.price,
                'amount': Decimal('0.01')
            },
            {
                'level': levelC,
                'level_index': levelC.level_index,
                'intent': OrderIntentType.ENTRY,
                'side': OrderSide.SELL,
                'price': levelC.price,
                'amount': Decimal('0.01')
            }
        ]

        # 执行同步
        created, cancelled = manager.sync_orders(ideal_orders, mock_exchange)

        # 应该撤销A，创建B和C
        assert len(created) == 2
        assert len(cancelled) == 1

        # 验证订单A已撤销
        levelA.refresh_from_db()
        assert levelA.status == GridLevelStatus.IDLE

        # 验证订单B和C已创建
        levelB.refresh_from_db()
        levelC.refresh_from_db()
        assert levelB.status == GridLevelStatus.ENTRY_WORKING
        assert levelC.status == GridLevelStatus.ENTRY_WORKING
