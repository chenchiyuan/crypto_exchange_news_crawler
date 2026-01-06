"""
测试文件：StrategyAdapter返回值扩展测试

Purpose:
    验证 StrategyAdapter.adapt_for_backtest() 方法返回值包含 'orders' 字段

关联任务: TASK-014-009
关联需求: architecture.md#6.2 StrategyAdapter复用适配
关联架构: architecture.md#6.2 StrategyAdapter - 接口扩展复用

测试策略:
    - 单元测试
    - 验证返回值包含 'orders' 字段
    - 回归测试：现有返回字段不受影响
"""

import unittest
import pandas as pd
from decimal import Decimal
from typing import Dict, List
from strategy_adapter.core.strategy_adapter import StrategyAdapter
from strategy_adapter.interfaces.strategy import IStrategy


class MockStrategy(IStrategy):
    """Mock策略用于测试"""

    def get_strategy_name(self) -> str:
        return "MockStrategy"

    def get_strategy_version(self) -> str:
        return "1.0.0"

    def generate_buy_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series]
    ) -> List[Dict]:
        """生成空的买入信号（用于测试）"""
        return []

    def generate_sell_signals(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series],
        open_orders: List
    ) -> List[Dict]:
        """生成空的卖出信号（用于测试）"""
        return []

    def calculate_position_size(
        self,
        signal: Dict,
        available_capital: Decimal,
        current_price: Decimal
    ) -> Decimal:
        """返回固定仓位大小（用于测试）"""
        return Decimal("100.00")

    def should_stop_loss(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series],
        order: Dict
    ) -> bool:
        """返回False（不触发止损，用于测试）"""
        return False

    def should_take_profit(
        self,
        klines: pd.DataFrame,
        indicators: Dict[str, pd.Series],
        order: Dict
    ) -> bool:
        """返回False（不触发止盈，用于测试）"""
        return False


class TestStrategyAdapterExtension(unittest.TestCase):
    """StrategyAdapter返回值扩展测试套件"""

    def test_adapt_for_backtest_returns_orders_field(self):
        """
        测试用例1：验证返回值包含 'orders' 字段

        验收标准: 返回字典包含 'orders' 键，值为 List[Order]
        """
        # Arrange
        strategy = MockStrategy()
        adapter = StrategyAdapter(strategy)

        # 构建最小化K线数据（3根K线）
        klines = pd.DataFrame({
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

        # 构建最小化指标
        indicators = {
            'sma5': pd.Series([100.0, 101.0, 102.0], index=klines.index),
        }

        initial_cash = Decimal("10000.00")
        symbol = "BTCUSDT"

        # Act
        result = adapter.adapt_for_backtest(klines, indicators, initial_cash, symbol)

        # Assert: 验证 'orders' 字段存在
        self.assertIn('orders', result)
        self.assertIsInstance(result['orders'], list)

    def test_adapt_for_backtest_existing_fields_not_affected(self):
        """
        测试用例2：回归测试 - 现有返回字段不受影响

        验收标准: 返回字典仍包含 'entries', 'exits', 'statistics' 字段
        """
        # Arrange
        strategy = MockStrategy()
        adapter = StrategyAdapter(strategy)

        # 构建最小化K线数据
        klines = pd.DataFrame({
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

        indicators = {
            'sma5': pd.Series([100.0, 101.0, 102.0], index=klines.index),
        }

        initial_cash = Decimal("10000.00")
        symbol = "BTCUSDT"

        # Act
        result = adapter.adapt_for_backtest(klines, indicators, initial_cash, symbol)

        # Assert: 验证现有字段仍然存在
        expected_keys = {'entries', 'exits', 'orders', 'statistics'}
        self.assertEqual(set(result.keys()), expected_keys)

        # 验证字段类型
        self.assertIsInstance(result['entries'], pd.Series)
        self.assertIsInstance(result['exits'], pd.Series)
        self.assertIsInstance(result['orders'], list)
        self.assertIsInstance(result['statistics'], dict)


if __name__ == '__main__':
    unittest.main()
