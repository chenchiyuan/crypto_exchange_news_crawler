"""
多策略回测项目配置数据类

Purpose:
    定义JSON配置文件的Python数据类结构，用于多策略组合回测。

关联任务: TASK-017-001, TASK-025-011
关联功能点: FP-017-001~005, FP-025-013

Classes:
    - ExitConfig: 卖出条件配置
    - StrategyConfig: 单个策略配置
    - CapitalManagementConfig: 资金管理配置
    - BacktestConfig: 回测配置
    - DataSourceConfig: 数据源配置
    - ProjectConfig: 项目总配置
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from decimal import Decimal


@dataclass
class ExitConfig:
    """
    卖出条件配置

    Attributes:
        type: 条件类型 (ema_reversion, stop_loss, take_profit)
        params: 条件参数字典
            - ema_reversion: {"ema_period": 25}
            - stop_loss: {"percentage": 5}
            - take_profit: {"percentage": 10}
    """
    type: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyConfig:
    """
    单个策略配置

    Attributes:
        id: 策略唯一标识符
        name: 策略显示名称
        type: 策略类型 (ddps-z)
        enabled: 是否启用该策略
        entry: 入场条件配置
            - ddps-z: {"strategy_id": 1}
        exits: 卖出条件列表
    """
    id: str
    name: str
    type: str
    enabled: bool = True
    entry: Dict[str, Any] = field(default_factory=dict)
    exits: List[ExitConfig] = field(default_factory=list)


@dataclass
class CapitalManagementConfig:
    """
    资金管理配置

    Attributes:
        mode: 资金模式 (shared - 共享资金池)
        position_size_mode: 仓位计算模式 (fixed - 固定金额)
        position_size: 单笔仓位金额
        max_positions: 最大同时持仓数
    """
    mode: str = "shared"
    position_size_mode: str = "fixed"
    position_size: Decimal = Decimal("100")
    max_positions: int = 10


@dataclass
class BacktestConfig:
    """
    回测配置

    Attributes:
        symbol: 交易对 (如 ETHUSDT)
        interval: K线周期 (如 4h)
        market_type: 市场类型 (futures/spot)
        start_date: 回测开始日期 (YYYY-MM-DD)
        end_date: 回测结束日期 (YYYY-MM-DD)
        initial_cash: 初始资金
        commission_rate: 手续费率
    """
    symbol: str
    interval: str
    market_type: str
    start_date: str
    end_date: str
    initial_cash: Decimal
    commission_rate: Decimal = Decimal("0.001")


@dataclass
class DataSourceConfig:
    """
    数据源配置

    用于指定回测数据来源，支持API和CSV两种类型。

    Attributes:
        type: 数据源类型
            - 'crypto_futures': 使用Binance合约API
            - 'crypto_spot': 使用Binance现货API
            - 'csv_local': 使用本地CSV文件
        csv_path: CSV文件路径（仅csv_local时需要）
        interval: K线周期（csv_local时指定CSV文件的周期）
        timestamp_unit: 时间戳单位
            - 'microseconds': 微秒（默认，币安1s数据使用）
            - 'milliseconds': 毫秒
            - 'seconds': 秒
    """
    type: str = 'crypto_futures'
    csv_path: Optional[str] = None
    interval: str = '4h'
    timestamp_unit: str = 'microseconds'


@dataclass
class ProjectConfig:
    """
    回测项目配置

    整合所有配置项的顶层数据类。

    Attributes:
        project_name: 项目名称
        description: 项目描述
        version: 配置版本
        backtest_config: 回测配置
        capital_management: 资金管理配置
        strategies: 策略列表
        data_source: 数据源配置（可选，默认使用backtest_config.market_type）
    """
    project_name: str
    description: str
    version: str
    backtest_config: BacktestConfig
    capital_management: CapitalManagementConfig
    strategies: List[StrategyConfig]
    data_source: Optional[DataSourceConfig] = None

    def get_enabled_strategies(self) -> List[StrategyConfig]:
        """获取所有启用的策略"""
        return [s for s in self.strategies if s.enabled]

    def get_strategy_by_id(self, strategy_id: str) -> Optional[StrategyConfig]:
        """根据ID获取策略配置"""
        for s in self.strategies:
            if s.id == strategy_id:
                return s
        return None

    def get_effective_market_type(self) -> str:
        """
        获取有效的市场类型

        如果配置了data_source则使用data_source.type，
        否则使用backtest_config.market_type。
        """
        if self.data_source:
            return self.data_source.type
        return self.backtest_config.market_type
