"""
GridConfig模型单元测试
"""
import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError

from grid_trading.models import GridConfig, GridMode


@pytest.mark.django_db
class TestGridConfig:
    """GridConfig模型测试"""
    
    def test_create_valid_config(self, grid_config_data):
        """测试创建有效的网格配置"""
        config = GridConfig.objects.create(**grid_config_data)

        assert config.name == 'test_btc_short'
        assert config.exchange == 'binance'
        assert config.symbol == 'BTCUSDT'
        assert config.grid_mode == 'short'
        assert float(config.upper_price) == 65000.00
        assert float(config.lower_price) == 60000.00
        assert config.grid_levels == 20
        assert float(config.trade_amount) == 0.01
        assert float(config.max_position_size) == 0.20
        assert float(config.stop_loss_buffer_pct) == 0.005
        assert config.refresh_interval_ms == 1000
        assert float(config.price_tick) == 0.01
        assert float(config.qty_step) == 0.001
        assert config.is_active is False
    
    def test_unique_name_constraint(self, grid_config_data):
        """测试配置名称唯一性约束"""
        GridConfig.objects.create(**grid_config_data)
        
        # 尝试创建同名配置应失败
        with pytest.raises(Exception):  # IntegrityError
            GridConfig.objects.create(**grid_config_data)
    
    def test_validation_lower_price_must_less_than_upper_price(self, grid_config_data):
        """测试价格验证: 下界必须小于上界"""
        grid_config_data['lower_price'] = Decimal('70000.00')
        grid_config_data['upper_price'] = Decimal('60000.00')
        
        config = GridConfig(**grid_config_data)
        with pytest.raises(ValidationError) as exc_info:
            config.clean()
        
        assert '下界价格必须小于上界价格' in str(exc_info.value)
    
    def test_validation_upper_price_must_positive(self, grid_config_data):
        """测试价格验证: 上界必须大于0"""
        grid_config_data['upper_price'] = Decimal('-100.00')
        
        config = GridConfig(**grid_config_data)
        with pytest.raises(ValidationError) as exc_info:
            config.clean()
        
        assert '价格上界必须大于0' in str(exc_info.value)
    
    def test_validation_lower_price_must_positive(self, grid_config_data):
        """测试价格验证: 下界必须大于0"""
        grid_config_data['lower_price'] = Decimal('-100.00')
        
        config = GridConfig(**grid_config_data)
        with pytest.raises(ValidationError) as exc_info:
            config.clean()
        
        assert '价格下界必须大于0' in str(exc_info.value)
    
    def test_validation_grid_levels_minimum(self, grid_config_data):
        """测试网格层数验证: 至少5层"""
        grid_config_data['grid_levels'] = 3
        
        config = GridConfig(**grid_config_data)
        with pytest.raises(ValidationError) as exc_info:
            config.clean()
        
        assert '网格数量至少为5' in str(exc_info.value)
    
    def test_validation_max_position_size_positive(self, grid_config_data):
        """测试持仓验证: 最大持仓必须大于0"""
        grid_config_data['max_position_size'] = Decimal('-0.1')
        
        config = GridConfig(**grid_config_data)
        with pytest.raises(ValidationError) as exc_info:
            config.clean()
        
        assert '最大持仓限制必须大于0' in str(exc_info.value)
    
    def test_validation_trade_amount_positive(self, grid_config_data):
        """测试交易数量验证: 单笔金额必须大于0"""
        grid_config_data['trade_amount'] = Decimal('0')
        
        config = GridConfig(**grid_config_data)
        with pytest.raises(ValidationError) as exc_info:
            config.clean()
        
        assert '单笔金额必须大于0' in str(exc_info.value)
    
    def test_validation_price_tick_positive(self, grid_config_data):
        """测试精度验证: 价格精度必须大于0"""
        grid_config_data['price_tick'] = Decimal('0')
        
        config = GridConfig(**grid_config_data)
        with pytest.raises(ValidationError) as exc_info:
            config.clean()
        
        assert '价格精度必须大于0' in str(exc_info.value)
    
    def test_validation_qty_step_positive(self, grid_config_data):
        """测试精度验证: 数量精度必须大于0"""
        grid_config_data['qty_step'] = Decimal('0')
        
        config = GridConfig(**grid_config_data)
        with pytest.raises(ValidationError) as exc_info:
            config.clean()
        
        assert '数量精度必须大于0' in str(exc_info.value)
    
    def test_validation_stop_loss_buffer_range(self, grid_config_data):
        """测试止损缓冲区验证: 必须在0-1之间"""
        grid_config_data['stop_loss_buffer_pct'] = Decimal('1.5')
        
        config = GridConfig(**grid_config_data)
        with pytest.raises(ValidationError) as exc_info:
            config.clean()
        
        assert '止损缓冲区百分比必须在0-1之间' in str(exc_info.value)
    
    def test_validation_refresh_interval_minimum(self, grid_config_data):
        """测试轮询间隔验证: 不能小于100毫秒"""
        grid_config_data['refresh_interval_ms'] = 50
        
        config = GridConfig(**grid_config_data)
        with pytest.raises(ValidationError) as exc_info:
            config.clean()
        
        assert '轮询间隔不能小于100毫秒' in str(exc_info.value)
    
    def test_grid_spacing_property(self, grid_config_data):
        """测试网格间距计算"""
        config = GridConfig.objects.create(**grid_config_data)
        
        expected_spacing = (Decimal('65000.00') - Decimal('60000.00')) / Decimal(19)
        assert config.grid_spacing == expected_spacing
    
    def test_grid_spacing_pct_property(self, grid_config_data):
        """测试网格间距百分比计算"""
        config = GridConfig.objects.create(**grid_config_data)
        
        center_price = (Decimal('65000.00') + Decimal('60000.00')) / Decimal('2')
        expected_spacing = (Decimal('65000.00') - Decimal('60000.00')) / Decimal(19)
        expected_pct = (expected_spacing / center_price) * Decimal('100')
        
        assert abs(config.grid_spacing_pct - expected_pct) < Decimal('0.01')
    
    def test_str_representation(self, grid_config_data):
        """测试字符串表示"""
        config = GridConfig.objects.create(**grid_config_data)
        
        assert str(config) == "test_btc_short (binance BTCUSDT short)"
    
    def test_save_triggers_clean(self, grid_config_data):
        """测试保存时自动触发验证"""
        grid_config_data['lower_price'] = Decimal('70000.00')
        
        config = GridConfig(**grid_config_data)
        with pytest.raises(ValidationError):
            config.save()
