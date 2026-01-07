"""
项目配置加载器

Purpose:
    加载和解析JSON格式的多策略回测项目配置文件。

关联任务: TASK-017-002
关联功能点: FP-017-006

Classes:
    - ProjectLoader: JSON配置加载器
"""

import json
import logging
from pathlib import Path
from decimal import Decimal
from typing import List, Dict, Any

from strategy_adapter.models.project_config import (
    ProjectConfig,
    BacktestConfig,
    CapitalManagementConfig,
    StrategyConfig,
    ExitConfig,
)

logger = logging.getLogger(__name__)


class ProjectLoaderError(Exception):
    """配置加载错误"""
    pass


class ProjectLoader:
    """
    项目配置加载器

    负责从JSON文件加载并解析多策略回测项目配置。

    Usage:
        loader = ProjectLoader()
        config = loader.load("path/to/project.json")
    """

    def load(self, path: str) -> ProjectConfig:
        """
        加载项目配置文件

        Args:
            path: JSON配置文件路径

        Returns:
            ProjectConfig: 解析后的项目配置对象

        Raises:
            ProjectLoaderError: 文件不存在或解析失败
        """
        file_path = Path(path)

        if not file_path.exists():
            raise ProjectLoaderError(f"配置文件不存在: {path}")

        if not file_path.suffix.lower() == '.json':
            raise ProjectLoaderError(f"配置文件必须是JSON格式: {path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ProjectLoaderError(f"JSON解析失败: {e}")

        return self._parse_config(data)

    def _parse_config(self, data: Dict[str, Any]) -> ProjectConfig:
        """
        解析配置数据

        Args:
            data: JSON解析后的字典

        Returns:
            ProjectConfig: 项目配置对象
        """
        # 验证必填字段
        required_fields = ['project_name', 'backtest_config', 'strategies']
        for field in required_fields:
            if field not in data:
                raise ProjectLoaderError(f"缺少必填字段: {field}")

        # 解析各部分配置
        backtest_config = self._parse_backtest_config(data['backtest_config'])
        capital_management = self._parse_capital_management(
            data.get('capital_management', {})
        )
        strategies = self._parse_strategies(data['strategies'])

        return ProjectConfig(
            project_name=data['project_name'],
            description=data.get('description', ''),
            version=data.get('version', '1.0'),
            backtest_config=backtest_config,
            capital_management=capital_management,
            strategies=strategies,
        )

    def _parse_backtest_config(self, data: Dict[str, Any]) -> BacktestConfig:
        """
        解析回测配置

        Args:
            data: 回测配置字典

        Returns:
            BacktestConfig: 回测配置对象
        """
        required_fields = ['symbol', 'interval', 'market_type', 'initial_cash']
        for field in required_fields:
            if field not in data:
                raise ProjectLoaderError(f"backtest_config缺少必填字段: {field}")

        return BacktestConfig(
            symbol=data['symbol'],
            interval=data['interval'],
            market_type=data['market_type'],
            start_date=data.get('start_date', ''),
            end_date=data.get('end_date', ''),
            initial_cash=Decimal(str(data['initial_cash'])),
            commission_rate=Decimal(str(data.get('commission_rate', '0.001'))),
        )

    def _parse_capital_management(
        self, data: Dict[str, Any]
    ) -> CapitalManagementConfig:
        """
        解析资金管理配置

        Args:
            data: 资金管理配置字典

        Returns:
            CapitalManagementConfig: 资金管理配置对象
        """
        return CapitalManagementConfig(
            mode=data.get('mode', 'shared'),
            position_size_mode=data.get('position_size_mode', 'fixed'),
            position_size=Decimal(str(data.get('position_size', '100'))),
            max_positions=int(data.get('max_positions', 10)),
        )

    def _parse_strategies(self, data: List[Dict[str, Any]]) -> List[StrategyConfig]:
        """
        解析策略列表

        Args:
            data: 策略配置列表

        Returns:
            List[StrategyConfig]: 策略配置对象列表
        """
        if not data:
            raise ProjectLoaderError("strategies不能为空")

        strategies = []
        for i, item in enumerate(data):
            try:
                strategy = self._parse_strategy(item)
                strategies.append(strategy)
            except ProjectLoaderError as e:
                raise ProjectLoaderError(f"策略[{i}]配置错误: {e}")

        return strategies

    def _parse_strategy(self, data: Dict[str, Any]) -> StrategyConfig:
        """
        解析单个策略配置

        Args:
            data: 策略配置字典

        Returns:
            StrategyConfig: 策略配置对象
        """
        required_fields = ['id', 'name', 'type']
        for field in required_fields:
            if field not in data:
                raise ProjectLoaderError(f"缺少必填字段: {field}")

        exits = self._parse_exits(data.get('exits', []))

        return StrategyConfig(
            id=data['id'],
            name=data['name'],
            type=data['type'],
            enabled=data.get('enabled', True),
            entry=data.get('entry', {}),
            exits=exits,
        )

    def _parse_exits(self, data: List[Dict[str, Any]]) -> List[ExitConfig]:
        """
        解析卖出条件列表

        Args:
            data: 卖出条件配置列表

        Returns:
            List[ExitConfig]: 卖出条件配置对象列表
        """
        exits = []
        valid_types = {'ema_reversion', 'stop_loss', 'take_profit'}

        for item in data:
            if 'type' not in item:
                raise ProjectLoaderError("卖出条件缺少type字段")

            exit_type = item['type']
            if exit_type not in valid_types:
                logger.warning(f"未知的卖出条件类型: {exit_type}，将被忽略")
                continue

            exits.append(ExitConfig(
                type=exit_type,
                params=item.get('params', {}),
            ))

        return exits
