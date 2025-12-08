"""
网格引擎单元测试
"""
import pytest
from decimal import Decimal

from grid_trading.models import GridConfig, GridLevel, GridLevelSide, GridLevelStatus
from grid_trading.services.grid.engine import GridEngine


@pytest.fixture
def short_grid_config(db, grid_config_data):
    """创建做空网格配置"""
    return GridConfig.objects.create(**grid_config_data)


@pytest.fixture
def long_grid_config(db, grid_config_data):
    """创建做多网格配置"""
    grid_config_data['name'] = 'test_btc_long'
    grid_config_data['grid_mode'] = 'LONG'
    return GridConfig.objects.create(**grid_config_data)


@pytest.fixture
def neutral_grid_config(db, grid_config_data):
    """创建中性网格配置"""
    grid_config_data['name'] = 'test_btc_neutral'
    grid_config_data['grid_mode'] = 'NEUTRAL'
    return GridConfig.objects.create(**grid_config_data)


@pytest.mark.django_db
class TestGridEngine:
    """GridEngine测试"""
    
    def test_calculate_grid_levels_basic(self, short_grid_config):
        """测试基本网格计算"""
        engine = GridEngine(short_grid_config)
        grid_data = engine.calculate_grid_levels()
        
        # 验证网格数量
        assert len(grid_data) == 20
        
        # 验证价格范围
        prices = [Decimal(str(d['price'])) for d in grid_data]
        assert min(prices) == Decimal('60000.00')
        assert max(prices) == Decimal('65000.00')
        
        # 验证层级索引
        indices = [d['level_index'] for d in grid_data]
        assert min(indices) == -9  # (20-1)/2 向下取整
        assert max(indices) == 10
    
    def test_calculate_grid_levels_spacing(self, short_grid_config):
        """测试网格间距计算"""
        engine = GridEngine(short_grid_config)
        grid_data = engine.calculate_grid_levels()
        
        # 计算期望间距
        expected_spacing = (Decimal('65000') - Decimal('60000')) / Decimal(19)
        
        # 验证相邻价格差
        for i in range(len(grid_data) - 1):
            price1 = Decimal(str(grid_data[i]['price']))
            price2 = Decimal(str(grid_data[i + 1]['price']))
            spacing = price2 - price1
            assert abs(spacing - expected_spacing) < Decimal('0.01')
    
    def test_calculate_grid_levels_short_mode(self, short_grid_config):
        """测试做空模式的订单方向"""
        engine = GridEngine(short_grid_config)
        grid_data = engine.calculate_grid_levels()
        
        center_price = (Decimal('65000') + Decimal('60000')) / Decimal('2')
        
        for data in grid_data:
            price = Decimal(str(data['price']))
            if price >= center_price:
                # 上方应该是卖单（开仓）
                assert data['side'] == GridLevelSide.SELL
            else:
                # 下方应该是买单（平仓）
                assert data['side'] == GridLevelSide.BUY
    
    def test_calculate_grid_levels_long_mode(self, long_grid_config):
        """测试做多模式的订单方向"""
        engine = GridEngine(long_grid_config)
        grid_data = engine.calculate_grid_levels()
        
        center_price = (Decimal('65000') + Decimal('60000')) / Decimal('2')
        
        for data in grid_data:
            price = Decimal(str(data['price']))
            if price <= center_price:
                # 下方应该是买单（开仓）
                assert data['side'] == GridLevelSide.BUY
            else:
                # 上方应该是卖单（平仓）
                assert data['side'] == GridLevelSide.SELL
    
    def test_calculate_grid_levels_neutral_mode(self, neutral_grid_config):
        """测试中性模式的订单方向"""
        engine = GridEngine(neutral_grid_config)
        grid_data = engine.calculate_grid_levels()
        
        center_price = (Decimal('65000') + Decimal('60000')) / Decimal('2')
        
        for data in grid_data:
            price = Decimal(str(data['price']))
            if price >= center_price:
                # 上方是卖单
                assert data['side'] == GridLevelSide.SELL
            else:
                # 下方是买单
                assert data['side'] == GridLevelSide.BUY
    
    def test_initialize_grid(self, short_grid_config):
        """测试网格初始化"""
        engine = GridEngine(short_grid_config)
        levels = engine.initialize_grid()
        
        # 验证创建了正确数量的层级
        assert len(levels) == 20
        
        # 验证数据库中存在
        db_levels = GridLevel.objects.filter(config=short_grid_config)
        assert db_levels.count() == 20
        
        # 验证所有层级初始状态为idle
        for level in levels:
            assert level.status == GridLevelStatus.IDLE
            assert level.entry_order_id is None
            assert level.exit_order_id is None
    
    def test_initialize_grid_clears_existing(self, short_grid_config):
        """测试初始化时清空现有层级"""
        # 先创建一些层级
        GridLevel.objects.create(
            config=short_grid_config,
            level_index=0,
            price=Decimal('62500'),
            side=GridLevelSide.SELL,
            status=GridLevelStatus.POSITION_OPEN
        )
        
        # 初始化应该清空并重建
        engine = GridEngine(short_grid_config)
        levels = engine.initialize_grid()
        
        assert len(levels) == 20
        # 之前的position_open状态应该被清除
        assert not GridLevel.objects.filter(
            config=short_grid_config,
            status=GridLevelStatus.POSITION_OPEN
        ).exists()
    
    def test_recover_from_existing_positions(self, short_grid_config):
        """测试从现有持仓恢复"""
        # 先初始化
        engine = GridEngine(short_grid_config)
        engine.initialize_grid()
        
        # 模拟一些状态变化
        level = GridLevel.objects.filter(config=short_grid_config).first()
        level.status = GridLevelStatus.POSITION_OPEN
        level.entry_order_id = '12345'
        level.save()
        
        # 恢复
        new_engine = GridEngine(short_grid_config)
        recovered_levels, orphans = new_engine.recover_from_existing_positions()
        
        assert len(recovered_levels) == 20
        # 持仓状态应该被保留
        assert any(l.status == GridLevelStatus.POSITION_OPEN for l in recovered_levels)
    
    def test_recover_fixes_inconsistent_state(self, short_grid_config):
        """测试恢复时修复不一致状态"""
        # 创建一个状态不一致的层级
        level = GridLevel.objects.create(
            config=short_grid_config,
            level_index=0,
            price=Decimal('62500'),
            side=GridLevelSide.SELL,
            status=GridLevelStatus.ENTRY_WORKING,  # 状态说有订单
            entry_order_id=None  # 但订单ID为空
        )
        
        # 恢复应该修复状态
        engine = GridEngine(short_grid_config)
        recovered_levels, orphans = engine.recover_from_existing_positions()
        
        level.refresh_from_db()
        assert level.status == GridLevelStatus.IDLE  # 应该被重置为idle
    
    def test_get_grid_summary(self, short_grid_config):
        """测试获取网格摘要"""
        engine = GridEngine(short_grid_config)
        engine.initialize_grid()

        # 修改一些状态（直接更新数据库避免模型验证）
        levels = list(GridLevel.objects.filter(config=short_grid_config)[:3])
        GridLevel.objects.filter(pk=levels[0].pk).update(status=GridLevelStatus.ENTRY_WORKING)
        GridLevel.objects.filter(pk=levels[1].pk).update(status=GridLevelStatus.POSITION_OPEN)

        summary = engine.get_grid_summary()

        assert summary['config_name'] == 'test_btc_short'
        assert summary['total_levels'] == 20
        assert summary['idle'] == 18
        assert summary['entry_working'] == 1
        assert summary['position_open'] == 1
        assert summary['exit_working'] == 0
        assert summary['grid_spacing'] > 0
        assert summary['grid_spacing_pct'] > 0
    
    def test_calculate_with_invalid_levels(self, db, grid_config_data):
        """测试无效的网格层数"""
        grid_config_data['grid_levels'] = 1
        # 直接创建引擎，不保存到数据库（避免触发验证）
        config = GridConfig(**grid_config_data)

        engine = GridEngine(config)
        with pytest.raises(ValueError, match="网格层数必须大于1"):
            engine.calculate_grid_levels()
