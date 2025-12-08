"""
做空网格策略单元测试
"""
import pytest
from decimal import Decimal

from grid_trading.models import (
    GridConfig, GridLevel, GridLevelSide, GridLevelStatus,
    OrderIntentType, OrderSide
)
from grid_trading.services.grid.engine import GridEngine
from grid_trading.services.grid.short_grid import ShortGridStrategy


@pytest.fixture
def short_config(db, grid_config_data):
    """创建做空网格配置"""
    return GridConfig.objects.create(**grid_config_data)


@pytest.fixture
def initialized_grid(short_config):
    """创建已初始化的网格"""
    engine = GridEngine(short_config)
    engine.initialize_grid()
    return short_config


@pytest.mark.django_db
class TestShortGridStrategy:
    """做空网格策略测试"""
    
    def test_initialization(self, short_config):
        """测试策略初始化"""
        strategy = ShortGridStrategy(short_config)
        
        assert strategy.config == short_config
        assert strategy.grid_levels == []
    
    def test_initialization_wrong_mode(self, db, grid_config_data):
        """测试错误的网格模式初始化"""
        grid_config_data['grid_mode'] = 'LONG'
        grid_config_data['name'] = 'test_long'
        long_config = GridConfig.objects.create(**grid_config_data)
        
        with pytest.raises(ValueError, match="配置的网格模式不是SHORT"):
            ShortGridStrategy(long_config)
    
    def test_load_grid_levels(self, initialized_grid):
        """测试加载网格层级"""
        strategy = ShortGridStrategy(initialized_grid)
        strategy.load_grid_levels()
        
        assert len(strategy.grid_levels) == 20
        # 验证按level_index排序
        indices = [level.level_index for level in strategy.grid_levels]
        assert indices == sorted(indices)
    
    def test_calculate_ideal_orders_all_idle(self, initialized_grid):
        """测试全部idle状态时的理想订单"""
        strategy = ShortGridStrategy(initialized_grid)
        orders = strategy.calculate_ideal_orders()
        
        # 只有上方的卖单（ENTRY）会被挂出
        # 下方的买单需要等开仓后才挂
        entry_orders = [o for o in orders if o['intent'] == OrderIntentType.ENTRY]
        exit_orders = [o for o in orders if o['intent'] == OrderIntentType.EXIT]
        
        assert len(entry_orders) > 0  # 至少有一些开仓单
        assert len(exit_orders) == 0  # idle状态不挂平仓单
        
        # 所有开仓单都是SELL
        for order in entry_orders:
            assert order['side'] == OrderSide.SELL
            assert order['amount'] == Decimal('0.01')
    
    def test_calculate_ideal_orders_with_position_open(self, initialized_grid):
        """测试有持仓时的理想订单"""
        strategy = ShortGridStrategy(initialized_grid)
        
        # 模拟一个层级已开仓
        level = GridLevel.objects.filter(
            config=initialized_grid,
            side=GridLevelSide.SELL
        ).first()
        GridLevel.objects.filter(pk=level.pk).update(
            status=GridLevelStatus.POSITION_OPEN,
            entry_order_id='12345'
        )
        
        orders = strategy.calculate_ideal_orders()
        
        # 应该有平仓单
        exit_orders = [o for o in orders if o['intent'] == OrderIntentType.EXIT]
        assert len(exit_orders) >= 1
        
        # 平仓单应该是BUY
        for order in exit_orders:
            if order['level'].pk == level.pk:
                assert order['side'] == OrderSide.BUY
                # 平仓价格应该低于开仓价格
                assert order['price'] < Decimal(str(level.price))
    
    def test_check_position_limit_within_limit(self, short_config):
        """测试持仓在限制范围内"""
        strategy = ShortGridStrategy(short_config)
        
        # 当前持仓0.05，上限0.20
        current_position = Decimal('-0.05')
        assert strategy.check_position_limit(current_position) is True
    
    def test_check_position_limit_at_limit(self, short_config):
        """测试持仓达到上限"""
        strategy = ShortGridStrategy(short_config)
        
        # 当前持仓0.20，上限0.20
        current_position = Decimal('-0.20')
        assert strategy.check_position_limit(current_position) is True
    
    def test_check_position_limit_exceeds(self, short_config):
        """测试持仓超限"""
        strategy = ShortGridStrategy(short_config)
        
        # 当前持仓0.25，上限0.20
        current_position = Decimal('-0.25')
        assert strategy.check_position_limit(current_position) is False
    
    def test_filter_orders_by_position_limit_all_allowed(self, initialized_grid):
        """测试持仓未满时所有订单都允许"""
        strategy = ShortGridStrategy(initialized_grid)
        
        # 创建一些理想订单
        ideal_orders = [
            {
                'level_index': 1,
                'intent': OrderIntentType.ENTRY,
                'side': OrderSide.SELL,
                'price': Decimal('63000'),
                'amount': Decimal('0.01')
            },
            {
                'level_index': 2,
                'intent': OrderIntentType.ENTRY,
                'side': OrderSide.SELL,
                'price': Decimal('63500'),
                'amount': Decimal('0.01')
            }
        ]
        
        # 当前持仓0.05，还可以开仓
        current_position = Decimal('-0.05')
        allowed, filtered = strategy.filter_orders_by_position_limit(
            ideal_orders, current_position
        )
        
        assert len(allowed) == 2
        assert len(filtered) == 0
    
    def test_filter_orders_by_position_limit_some_filtered(self, initialized_grid):
        """测试持仓接近上限时过滤部分订单"""
        strategy = ShortGridStrategy(initialized_grid)
        
        # 创建多个开仓订单
        ideal_orders = [
            {
                'level_index': i,
                'intent': OrderIntentType.ENTRY,
                'side': OrderSide.SELL,
                'price': Decimal('63000') + Decimal(i * 100),
                'amount': Decimal('0.01')
            }
            for i in range(5)
        ]
        
        # 当前持仓0.18，上限0.20，只能再开2个0.01的仓位
        current_position = Decimal('-0.18')
        allowed, filtered = strategy.filter_orders_by_position_limit(
            ideal_orders, current_position
        )
        
        assert len(allowed) == 2
        assert len(filtered) == 3
    
    def test_filter_orders_exit_always_allowed(self, initialized_grid):
        """测试平仓单总是允许"""
        strategy = ShortGridStrategy(initialized_grid)
        
        # 创建平仓订单
        ideal_orders = [
            {
                'level_index': 1,
                'intent': OrderIntentType.EXIT,
                'side': OrderSide.BUY,
                'price': Decimal('62000'),
                'amount': Decimal('0.01')
            }
        ]
        
        # 即使持仓已满，平仓单也应该允许
        current_position = Decimal('-0.20')
        allowed, filtered = strategy.filter_orders_by_position_limit(
            ideal_orders, current_position
        )
        
        assert len(allowed) == 1
        assert len(filtered) == 0
    
    def test_on_order_filled_entry(self, initialized_grid):
        """测试开仓单成交"""
        strategy = ShortGridStrategy(initialized_grid)
        
        # 创建一个entry_working状态的层级
        level = GridLevel.objects.filter(config=initialized_grid).first()
        level.status = GridLevelStatus.ENTRY_WORKING
        level.entry_order_id = '12345'
        level.entry_client_id = 'test_client_id'
        level.save()
        
        # 模拟开仓成交
        updated_level = strategy.on_order_filled(level, OrderIntentType.ENTRY)
        
        updated_level.refresh_from_db()
        assert updated_level.status == GridLevelStatus.POSITION_OPEN
    
    def test_on_order_filled_exit(self, initialized_grid):
        """测试平仓单成交"""
        strategy = ShortGridStrategy(initialized_grid)
        
        # 创建一个exit_working状态的层级
        level = GridLevel.objects.filter(config=initialized_grid).first()
        level.status = GridLevelStatus.EXIT_WORKING
        level.entry_order_id = '12345'
        level.exit_order_id = '67890'
        level.save()
        
        # 模拟平仓成交
        updated_level = strategy.on_order_filled(level, OrderIntentType.EXIT)
        
        updated_level.refresh_from_db()
        assert updated_level.status == GridLevelStatus.IDLE
        # 订单ID应该被清空
        assert updated_level.entry_order_id is None
        assert updated_level.exit_order_id is None
    
    def test_get_current_position_all_idle(self, initialized_grid):
        """测试全部idle时持仓为0"""
        strategy = ShortGridStrategy(initialized_grid)
        
        position = strategy.get_current_position()
        assert position == Decimal('0')
    
    def test_get_current_position_with_positions(self, initialized_grid):
        """测试有持仓时的计算"""
        strategy = ShortGridStrategy(initialized_grid)
        
        # 模拟3个层级已开仓
        levels = list(GridLevel.objects.filter(config=initialized_grid)[:3])
        for level in levels:
            GridLevel.objects.filter(pk=level.pk).update(
                status=GridLevelStatus.POSITION_OPEN
            )
        
        position = strategy.get_current_position()
        # 3个层级 × 0.01 = -0.03（负数表示空头）
        assert position == Decimal('-0.03')
    
    def test_get_current_position_includes_exit_working(self, initialized_grid):
        """测试持仓计算包含exit_working状态"""
        strategy = ShortGridStrategy(initialized_grid)
        
        # 2个position_open + 1个exit_working
        levels = list(GridLevel.objects.filter(config=initialized_grid)[:3])
        GridLevel.objects.filter(pk=levels[0].pk).update(
            status=GridLevelStatus.POSITION_OPEN
        )
        GridLevel.objects.filter(pk=levels[1].pk).update(
            status=GridLevelStatus.POSITION_OPEN
        )
        GridLevel.objects.filter(pk=levels[2].pk).update(
            status=GridLevelStatus.EXIT_WORKING
        )
        
        position = strategy.get_current_position()
        # 3个层级都算持仓
        assert position == Decimal('-0.03')
