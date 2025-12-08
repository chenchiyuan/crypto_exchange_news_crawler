"""
GridLevel状态机单元测试
"""
import pytest
import time
from decimal import Decimal

from grid_trading.models import GridConfig, GridLevel, GridLevelStatus, GridLevelSide


@pytest.fixture
def grid_config(db, grid_config_data):
    """创建测试用网格配置"""
    return GridConfig.objects.create(**grid_config_data)


@pytest.fixture
def grid_level(grid_config):
    """创建测试用网格层级"""
    return GridLevel.objects.create(
        config=grid_config,
        level_index=5,
        price=Decimal('63500.00'),
        side=GridLevelSide.SELL,
        status=GridLevelStatus.IDLE
    )


@pytest.mark.django_db
class TestGridLevelStateMachine:
    """GridLevel状态机测试"""
    
    def test_initial_state_is_idle(self, grid_level):
        """测试初始状态为idle"""
        assert grid_level.status == GridLevelStatus.IDLE
        assert grid_level.entry_order_id is None
        assert grid_level.exit_order_id is None
    
    def test_transition_idle_to_entry_working(self, grid_level):
        """测试状态转换: idle → entry_working"""
        grid_level.transition_to_entry_working(
            entry_order_id='12345',
            entry_client_id='test_ENTRY_SELL_5_a3f2'
        )
        
        grid_level.refresh_from_db()
        assert grid_level.status == GridLevelStatus.ENTRY_WORKING
        assert grid_level.entry_order_id == '12345'
        assert grid_level.entry_client_id == 'test_ENTRY_SELL_5_a3f2'
    
    def test_transition_entry_working_to_position_open(self, grid_level):
        """测试状态转换: entry_working → position_open"""
        grid_level.transition_to_entry_working('12345', 'test_client_id')
        grid_level.transition_to_position_open()
        
        grid_level.refresh_from_db()
        assert grid_level.status == GridLevelStatus.POSITION_OPEN
        assert grid_level.entry_order_id == '12345'  # 订单ID保留
    
    def test_transition_position_open_to_exit_working(self, grid_level):
        """测试状态转换: position_open → exit_working"""
        grid_level.transition_to_entry_working('12345', 'entry_client')
        grid_level.transition_to_position_open()
        grid_level.transition_to_exit_working(
            exit_order_id='67890',
            exit_client_id='test_EXIT_BUY_5_b4e1'
        )
        
        grid_level.refresh_from_db()
        assert grid_level.status == GridLevelStatus.EXIT_WORKING
        assert grid_level.exit_order_id == '67890'
        assert grid_level.exit_client_id == 'test_EXIT_BUY_5_b4e1'
    
    def test_transition_exit_working_to_idle(self, grid_level):
        """测试状态转换: exit_working → idle (平仓完成)"""
        grid_level.transition_to_entry_working('12345', 'entry_client')
        grid_level.transition_to_position_open()
        grid_level.transition_to_exit_working('67890', 'exit_client')
        grid_level.transition_to_idle()
        
        grid_level.refresh_from_db()
        assert grid_level.status == GridLevelStatus.IDLE
        # 所有订单ID应被清空
        assert grid_level.entry_order_id is None
        assert grid_level.exit_order_id is None
        assert grid_level.entry_client_id is None
        assert grid_level.exit_client_id is None
    
    def test_transition_entry_working_to_idle_cancel(self, grid_level):
        """测试状态转换: entry_working → idle (撤销开仓单)"""
        grid_level.transition_to_entry_working('12345', 'entry_client')
        grid_level.transition_to_idle()
        
        grid_level.refresh_from_db()
        assert grid_level.status == GridLevelStatus.IDLE
        assert grid_level.entry_order_id is None
    
    def test_invalid_transition_raises_error(self, grid_level):
        """测试无效状态转换抛出错误"""
        # idle状态不能直接转到exit_working
        with pytest.raises(ValueError) as exc_info:
            grid_level.transition_to_exit_working('67890', 'exit_client')
        
        assert 'Cannot transition from idle to exit_working' in str(exc_info.value)
    
    def test_can_place_entry_order_when_idle(self, grid_level):
        """测试空闲状态可以挂开仓单"""
        assert grid_level.can_place_entry_order() is True
    
    def test_cannot_place_entry_order_when_not_idle(self, grid_level):
        """测试非空闲状态不能挂开仓单"""
        grid_level.transition_to_entry_working('12345', 'entry_client')
        assert grid_level.can_place_entry_order() is False
    
    def test_can_place_exit_order_when_position_open(self, grid_level):
        """测试持仓状态可以挂平仓单"""
        grid_level.transition_to_entry_working('12345', 'entry_client')
        grid_level.transition_to_position_open()
        
        assert grid_level.can_place_exit_order() is True
    
    def test_cannot_place_exit_order_when_not_position_open(self, grid_level):
        """测试非持仓状态不能挂平仓单"""
        assert grid_level.can_place_exit_order() is False
    
    def test_is_blocked_when_blocked_until_set(self, grid_level):
        """测试冷却期判断"""
        # 设置冷却期为5秒后
        future_time_ms = int(time.time() * 1000) + 5000
        grid_level.blocked_until = future_time_ms
        grid_level.save()
        
        assert grid_level.is_blocked() is True
    
    def test_is_not_blocked_when_expired(self, grid_level):
        """测试冷却期过期后不再冷却"""
        # 设置冷却期为过去的时间
        past_time_ms = int(time.time() * 1000) - 1000
        grid_level.blocked_until = past_time_ms
        grid_level.save()
        
        assert grid_level.is_blocked() is False
    
    def test_is_not_blocked_when_null(self, grid_level):
        """测试未设置冷却期时不冷却"""
        assert grid_level.blocked_until is None
        assert grid_level.is_blocked() is False
    
    def test_set_blocked(self, grid_level):
        """测试设置冷却期"""
        before_time_ms = int(time.time() * 1000)
        grid_level.set_blocked(duration_ms=5000)
        
        grid_level.refresh_from_db()
        assert grid_level.blocked_until is not None
        assert grid_level.blocked_until >= before_time_ms + 5000
        assert grid_level.is_blocked() is True
    
    def test_cannot_place_order_when_blocked(self, grid_level):
        """测试冷却期内不能挂单"""
        grid_level.set_blocked(duration_ms=5000)
        
        assert grid_level.can_place_entry_order() is False
    
    def test_cancel_entry_order(self, grid_level):
        """测试撤销开仓单"""
        grid_level.transition_to_entry_working('12345', 'entry_client')
        grid_level.cancel_entry_order()
        
        grid_level.refresh_from_db()
        assert grid_level.status == GridLevelStatus.IDLE
        assert grid_level.entry_order_id is None
    
    def test_cancel_exit_order(self, grid_level):
        """测试撤销平仓单"""
        grid_level.transition_to_entry_working('12345', 'entry_client')
        grid_level.transition_to_position_open()
        grid_level.transition_to_exit_working('67890', 'exit_client')
        grid_level.cancel_exit_order()
        
        grid_level.refresh_from_db()
        assert grid_level.status == GridLevelStatus.POSITION_OPEN
        assert grid_level.exit_order_id is None
        assert grid_level.entry_order_id == '12345'  # 开仓订单ID保留
    
    def test_unique_together_constraint(self, grid_config):
        """测试config和level_index的唯一性约束"""
        GridLevel.objects.create(
            config=grid_config,
            level_index=10,
            price=Decimal('64000.00'),
            side=GridLevelSide.SELL
        )
        
        # 尝试创建相同config和level_index的层级应失败
        with pytest.raises(Exception):  # IntegrityError
            GridLevel.objects.create(
                config=grid_config,
                level_index=10,
                price=Decimal('64500.00'),
                side=GridLevelSide.SELL
            )
    
    def test_str_representation(self, grid_level):
        """测试字符串表示"""
        expected = "test_btc_short Level 5 @ 63500.00 (idle)"
        assert str(grid_level) == expected
