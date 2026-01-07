"""
多策略回测项目配置数据类

Purpose:
    定义JSON配置文件的Python数据类结构，用于多策略组合回测。

关联任务: TASK-017-001
关联功能点: FP-017-001~005

Classes:
    - ExitConfig: 卖出条件配置
    - StrategyConfig: 单个策略配置
    - CapitalManagementConfig: 资金管理配置
    - BacktestConfig: 回测配置
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
    """
    project_name: str
    description: str
    version: str
    backtest_config: BacktestConfig
    capital_management: CapitalManagementConfig
    strategies: List[StrategyConfig]

    def get_enabled_strategies(self) -> List[StrategyConfig]:
        """获取所有启用的策略"""
        return [s for s in self.strategies if s.enabled]

    def get_strategy_by_id(self, strategy_id: str) -> Optional[StrategyConfig]:
        """根据ID获取策略配置"""
        for s in self.strategies:
            if s.id == strategy_id:
                return s
        return None
