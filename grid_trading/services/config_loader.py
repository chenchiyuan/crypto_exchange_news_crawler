"""
配置加载器
Configuration Loader

从YAML文件加载网格交易策略参数
"""
import os
import yaml
from typing import Dict, Any
from pathlib import Path


class ConfigLoader:
    """配置加载器"""

    def __init__(self, config_file: str = None):
        """
        初始化配置加载器

        Args:
            config_file: 配置文件路径，默认为 config/grid_trading.yaml
        """
        if config_file is None:
            # 默认配置文件路径：项目根目录/config/grid_trading.yaml
            base_dir = Path(__file__).resolve().parent.parent.parent
            config_file = base_dir / 'config' / 'grid_trading.yaml'

        self.config_file = config_file
        self._config_data = None

    def load(self) -> Dict[str, Any]:
        """
        加载配置文件

        Returns:
            Dict: 完整的配置字典

        Raises:
            FileNotFoundError: 配置文件不存在
            yaml.YAMLError: YAML解析错误
        """
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"配置文件不存在: {self.config_file}")

        with open(self.config_file, 'r', encoding='utf-8') as f:
            self._config_data = yaml.safe_load(f)

        return self._config_data

    def get_symbol_config(self, symbol: str) -> Dict[str, Any]:
        """
        获取指定交易对的配置

        Args:
            symbol: 交易对名称，如 'btc' 或 'BTCUSDT'

        Returns:
            Dict: 该交易对的配置字典

        Raises:
            ValueError: 找不到该交易对的配置
        """
        if self._config_data is None:
            self.load()

        # 标准化symbol: btc -> btc_default, BTCUSDT -> btc_default
        symbol_lower = symbol.lower().replace('usdt', '')
        config_key = f"{symbol_lower}_default"

        if config_key not in self._config_data:
            available = [k for k in self._config_data.keys() if k != 'global']
            raise ValueError(
                f"找不到配置: {config_key}。可用配置: {', '.join(available)}"
            )

        return self._config_data[config_key]

    def get_global_config(self) -> Dict[str, Any]:
        """
        获取全局配置

        Returns:
            Dict: 全局配置字典
        """
        if self._config_data is None:
            self.load()

        return self._config_data.get('global', {})


# 全局单例实例
_config_loader = None


def get_config_loader() -> ConfigLoader:
    """
    获取配置加载器单例

    Returns:
        ConfigLoader: 配置加载器实例
    """
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader


def load_config(symbol: str) -> Dict[str, Any]:
    """
    便捷函数：加载指定交易对的配置

    Args:
        symbol: 交易对名称，如 'btc' 或 'BTCUSDT'

    Returns:
        Dict: 该交易对的配置字典

    Example:
        >>> config = load_config('btc')
        >>> print(config['atr_multiplier'])
        0.8
    """
    loader = get_config_loader()
    return loader.get_symbol_config(symbol)


def load_global_config() -> Dict[str, Any]:
    """
    便捷函数：加载全局配置

    Returns:
        Dict: 全局配置字典

    Example:
        >>> global_cfg = load_global_config()
        >>> print(global_cfg['simulation']['slippage_pct'])
        0.0005
    """
    loader = get_config_loader()
    return loader.get_global_config()
