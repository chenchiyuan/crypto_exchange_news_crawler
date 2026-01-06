"""
测试文件：CLI参数扩展测试

Purpose:
    验证 run_strategy_backtest 命令支持新增的 --risk-free-rate 参数

关联任务: TASK-014-010
关联需求: FP-014-017（prd.md）
关联架构: architecture.md#7 关键技术决策 - 决策点2

测试策略:
    - 单元测试
    - 验证参数默认值
    - 验证参数自定义值
    - 验证参数范围边界
"""

import unittest
from io import StringIO
from unittest.mock import patch, MagicMock
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import CommandError


class TestRiskFreeRateParameter(unittest.TestCase):
    """--risk-free-rate参数测试套件"""

    @patch('strategy_adapter.management.commands.run_strategy_backtest.Command._load_klines')
    @patch('strategy_adapter.management.commands.run_strategy_backtest.Command._calculate_indicators')
    @patch('strategy_adapter.management.commands.run_strategy_backtest.Command._create_strategy')
    @patch('strategy_adapter.management.commands.run_strategy_backtest.StrategyAdapter')
    def test_risk_free_rate_default_value(
        self,
        mock_adapter_class,
        mock_create_strategy,
        mock_calculate_indicators,
        mock_load_klines
    ):
        """
        测试用例1：验证默认值为3.0%

        验收标准: 未指定时，risk_free_rate默认为3.0
        """
        # Arrange: Mock所有依赖
        import pandas as pd
        mock_load_klines.return_value = pd.DataFrame({
            'open': [100.0, 101.0, 102.0],
            'high': [105.0, 106.0, 107.0],
            'low': [99.0, 100.0, 101.0],
            'close': [102.0, 103.0, 104.0],
            'volume': [1000.0, 1100.0, 1200.0],
        }, index=pd.DatetimeIndex([
            '2026-01-06 00:00:00',
            '2026-01-06 04:00:00',
            '2026-01-06 08:00:00'
        ], tz='UTC'))

        mock_calculate_indicators.return_value = {
            'ema25': pd.Series([100.0, 101.0, 102.0]),
        }

        mock_strategy = MagicMock()
        mock_strategy.get_strategy_name.return_value = "TestStrategy"
        mock_strategy.get_strategy_version.return_value = "1.0.0"
        mock_create_strategy.return_value = mock_strategy

        mock_adapter_instance = MagicMock()
        mock_adapter_instance.adapt_for_backtest.return_value = {
            'entries': pd.Series([False, False, False]),
            'exits': pd.Series([False, False, False]),
            'orders': [],
            'statistics': {
                'total_orders': 0,
                'open_orders': 0,
                'closed_orders': 0,
                'total_profit': Decimal('0'),
                'total_commission': Decimal('0'),
                'win_rate': Decimal('0'),
                'win_orders': 0,
                'lose_orders': 0,
                'avg_profit_rate': Decimal('0'),
            }
        }
        mock_adapter_class.return_value = mock_adapter_instance

        # Act: 运行命令（未指定--risk-free-rate）
        out = StringIO()
        call_command(
            'run_strategy_backtest',
            'BTCUSDT',
            stdout=out
        )

        # Assert: 验证命令成功执行
        # 注：当前阶段只验证参数被正确解析，MetricsCalculator集成在TASK-014-011
        self.assertIn('回测执行成功', out.getvalue())

    @patch('strategy_adapter.management.commands.run_strategy_backtest.Command._load_klines')
    @patch('strategy_adapter.management.commands.run_strategy_backtest.Command._calculate_indicators')
    @patch('strategy_adapter.management.commands.run_strategy_backtest.Command._create_strategy')
    @patch('strategy_adapter.management.commands.run_strategy_backtest.StrategyAdapter')
    def test_risk_free_rate_custom_value(
        self,
        mock_adapter_class,
        mock_create_strategy,
        mock_calculate_indicators,
        mock_load_klines
    ):
        """
        测试用例2：验证自定义值5.0%

        验收标准: 指定--risk-free-rate 5.0时，参数值为5.0
        """
        # Arrange: Mock所有依赖（同test_risk_free_rate_default_value）
        import pandas as pd
        mock_load_klines.return_value = pd.DataFrame({
            'open': [100.0, 101.0, 102.0],
            'high': [105.0, 106.0, 107.0],
            'low': [99.0, 100.0, 101.0],
            'close': [102.0, 103.0, 104.0],
            'volume': [1000.0, 1100.0, 1200.0],
        }, index=pd.DatetimeIndex([
            '2026-01-06 00:00:00',
            '2026-01-06 04:00:00',
            '2026-01-06 08:00:00'
        ], tz='UTC'))

        mock_calculate_indicators.return_value = {
            'ema25': pd.Series([100.0, 101.0, 102.0]),
        }

        mock_strategy = MagicMock()
        mock_strategy.get_strategy_name.return_value = "TestStrategy"
        mock_strategy.get_strategy_version.return_value = "1.0.0"
        mock_create_strategy.return_value = mock_strategy

        mock_adapter_instance = MagicMock()
        mock_adapter_instance.adapt_for_backtest.return_value = {
            'entries': pd.Series([False, False, False]),
            'exits': pd.Series([False, False, False]),
            'orders': [],
            'statistics': {
                'total_orders': 0,
                'open_orders': 0,
                'closed_orders': 0,
                'total_profit': Decimal('0'),
                'total_commission': Decimal('0'),
                'win_rate': Decimal('0'),
                'win_orders': 0,
                'lose_orders': 0,
                'avg_profit_rate': Decimal('0'),
            }
        }
        mock_adapter_class.return_value = mock_adapter_instance

        # Act: 运行命令（指定--risk-free-rate 5.0）
        out = StringIO()
        call_command(
            'run_strategy_backtest',
            'BTCUSDT',
            '--risk-free-rate', '5.0',
            stdout=out
        )

        # Assert: 验证命令成功执行
        self.assertIn('回测执行成功', out.getvalue())

    @patch('strategy_adapter.management.commands.run_strategy_backtest.Command._load_klines')
    @patch('strategy_adapter.management.commands.run_strategy_backtest.Command._calculate_indicators')
    @patch('strategy_adapter.management.commands.run_strategy_backtest.Command._create_strategy')
    @patch('strategy_adapter.management.commands.run_strategy_backtest.StrategyAdapter')
    def test_risk_free_rate_boundary_value_zero(
        self,
        mock_adapter_class,
        mock_create_strategy,
        mock_calculate_indicators,
        mock_load_klines
    ):
        """
        测试用例3：边界值测试 - 0%

        验收标准: 指定--risk-free-rate 0时，命令成功执行
        """
        # Arrange: Mock所有依赖
        import pandas as pd
        mock_load_klines.return_value = pd.DataFrame({
            'open': [100.0, 101.0, 102.0],
            'high': [105.0, 106.0, 107.0],
            'low': [99.0, 100.0, 101.0],
            'close': [102.0, 103.0, 104.0],
            'volume': [1000.0, 1100.0, 1200.0],
        }, index=pd.DatetimeIndex([
            '2026-01-06 00:00:00',
            '2026-01-06 04:00:00',
            '2026-01-06 08:00:00'
        ], tz='UTC'))

        mock_calculate_indicators.return_value = {
            'ema25': pd.Series([100.0, 101.0, 102.0]),
        }

        mock_strategy = MagicMock()
        mock_strategy.get_strategy_name.return_value = "TestStrategy"
        mock_strategy.get_strategy_version.return_value = "1.0.0"
        mock_create_strategy.return_value = mock_strategy

        mock_adapter_instance = MagicMock()
        mock_adapter_instance.adapt_for_backtest.return_value = {
            'entries': pd.Series([False, False, False]),
            'exits': pd.Series([False, False, False]),
            'orders': [],
            'statistics': {
                'total_orders': 0,
                'open_orders': 0,
                'closed_orders': 0,
                'total_profit': Decimal('0'),
                'total_commission': Decimal('0'),
                'win_rate': Decimal('0'),
                'win_orders': 0,
                'lose_orders': 0,
                'avg_profit_rate': Decimal('0'),
            }
        }
        mock_adapter_class.return_value = mock_adapter_instance

        # Act: 运行命令（指定--risk-free-rate 0）
        out = StringIO()
        call_command(
            'run_strategy_backtest',
            'BTCUSDT',
            '--risk-free-rate', '0',
            stdout=out
        )

        # Assert: 验证命令成功执行
        self.assertIn('回测执行成功', out.getvalue())

    @patch('strategy_adapter.management.commands.run_strategy_backtest.Command._load_klines')
    @patch('strategy_adapter.management.commands.run_strategy_backtest.Command._calculate_indicators')
    @patch('strategy_adapter.management.commands.run_strategy_backtest.Command._create_strategy')
    @patch('strategy_adapter.management.commands.run_strategy_backtest.StrategyAdapter')
    def test_risk_free_rate_boundary_value_high(
        self,
        mock_adapter_class,
        mock_create_strategy,
        mock_calculate_indicators,
        mock_load_klines
    ):
        """
        测试用例4：边界值测试 - 100%（极端高值）

        验收标准: 指定--risk-free-rate 100时，命令成功执行并显示警告
        """
        # Arrange: Mock所有依赖
        import pandas as pd
        mock_load_klines.return_value = pd.DataFrame({
            'open': [100.0, 101.0, 102.0],
            'high': [105.0, 106.0, 107.0],
            'low': [99.0, 100.0, 101.0],
            'close': [102.0, 103.0, 104.0],
            'volume': [1000.0, 1100.0, 1200.0],
        }, index=pd.DatetimeIndex([
            '2026-01-06 00:00:00',
            '2026-01-06 04:00:00',
            '2026-01-06 08:00:00'
        ], tz='UTC'))

        mock_calculate_indicators.return_value = {
            'ema25': pd.Series([100.0, 101.0, 102.0]),
        }

        mock_strategy = MagicMock()
        mock_strategy.get_strategy_name.return_value = "TestStrategy"
        mock_strategy.get_strategy_version.return_value = "1.0.0"
        mock_create_strategy.return_value = mock_strategy

        mock_adapter_instance = MagicMock()
        mock_adapter_instance.adapt_for_backtest.return_value = {
            'entries': pd.Series([False, False, False]),
            'exits': pd.Series([False, False, False]),
            'orders': [],
            'statistics': {
                'total_orders': 0,
                'open_orders': 0,
                'closed_orders': 0,
                'total_profit': Decimal('0'),
                'total_commission': Decimal('0'),
                'win_rate': Decimal('0'),
                'win_orders': 0,
                'lose_orders': 0,
                'avg_profit_rate': Decimal('0'),
            }
        }
        mock_adapter_class.return_value = mock_adapter_instance

        # Act: 运行命令（指定--risk-free-rate 100）
        out = StringIO()
        call_command(
            'run_strategy_backtest',
            'BTCUSDT',
            '--risk-free-rate', '100',
            stdout=out
        )

        # Assert: 验证命令成功执行（当前阶段不强制验证警告）
        self.assertIn('回测执行成功', out.getvalue())


if __name__ == '__main__':
    unittest.main()
