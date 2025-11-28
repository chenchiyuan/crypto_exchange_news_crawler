"""
测试配置加载器
Test Configuration Loader
"""
import pytest
from grid_trading.services.config_loader import load_config, load_global_config, ConfigLoader


class TestConfigLoader:
    """配置加载器测试"""

    def test_load_btc_config(self):
        """测试加载BTC配置"""
        config = load_config('btc')

        assert config['symbol'] == 'BTCUSDT'
        assert config['atr_multiplier'] == 0.8
        assert config['grid_levels'] == 10
        assert config['order_size_usdt'] == 100
        assert config['stop_loss_pct'] == 0.10
        assert config['max_position_usdt'] == 1000

    def test_load_eth_config(self):
        """测试加载ETH配置"""
        config = load_config('eth')

        assert config['symbol'] == 'ETHUSDT'
        assert config['atr_multiplier'] == 0.8

    def test_load_btcusdt_config(self):
        """测试使用完整符号加载配置"""
        config = load_config('BTCUSDT')

        assert config['symbol'] == 'BTCUSDT'

    def test_load_global_config(self):
        """测试加载全局配置"""
        global_cfg = load_global_config()

        assert 'simulation' in global_cfg
        assert global_cfg['simulation']['slippage_pct'] == 0.0005
        assert global_cfg['simulation']['taker_fee_pct'] == 0.001

    def test_load_invalid_symbol(self):
        """测试加载不存在的交易对配置"""
        with pytest.raises(ValueError, match="找不到配置"):
            load_config('sol')  # 配置文件中不存在SOL

    def test_config_loader_singleton(self):
        """测试配置加载器单例模式"""
        from grid_trading.services.config_loader import get_config_loader

        loader1 = get_config_loader()
        loader2 = get_config_loader()

        assert loader1 is loader2  # 应该是同一个实例
