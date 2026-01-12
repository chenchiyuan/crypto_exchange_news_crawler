"""
测试文件：P5TouchTakeProfitExit单元测试

Purpose:
    验证P5TouchTakeProfitExit类的止盈逻辑正确性

关联任务: TASK-022-002
关联需求: FP-022-004 - P5触及止盈Exit
关联架构: architecture.md 2.1节 - P5TouchTakeProfitExit组件

测试策略:
    - 单元测试
    - 覆盖P5触及、未触及、NaN等边界情况
    - 验证成交价格为close（而非low）
    - 验证优先级和exit_type
"""

import unittest
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any

from strategy_adapter.exits.p5_touch_take_profit import P5TouchTakeProfitExit


class MockOrder:
    """Mock订单对象用于测试"""

    def __init__(self, direction='short', open_price=Decimal('120.0')):
        self.direction = direction
        self.open_price = open_price
        self.order_id = 'test_order_001'


class TestP5TouchTakeProfitExit(unittest.TestCase):
    """P5TouchTakeProfitExit单元测试套件"""

    def setUp(self):
        """测试前准备：初始化Exit条件和Mock订单"""
        self.exit_condition = P5TouchTakeProfitExit()
        self.order = MockOrder(direction='short', open_price=Decimal('120.0'))
        self.timestamp = int(datetime(2025, 1, 6, 12, 0, 0).timestamp())

    def test_p5_touched_triggers_exit(self):
        """
        测试用例1：K线low触及P5时触发止盈

        验收标准:
        - 当 kline['low'] <= p5 时，返回ExitSignal
        - 平仓价格为 kline['close']（而非low）
        """
        # Arrange
        kline = {
            'low': Decimal('100.0'),    # low触及P5
            'close': Decimal('105.0')   # 成交价应为close
        }
        indicators = {
            'p5': 110.0  # P5 = 110，low=100 < 110，触发
        }

        # Act
        signal = self.exit_condition.check(
            self.order, kline, indicators, self.timestamp
        )

        # Assert
        self.assertIsNotNone(signal, "P5触及时应返回ExitSignal")
        self.assertEqual(signal.price, Decimal('105.0'), "成交价格应为close")
        self.assertIn('P5触及止盈', signal.reason)
        self.assertIn('110.00', signal.reason)  # 验证原因包含P5值
        self.assertEqual(signal.exit_type, 'p5_touch_take_profit')

    def test_p5_exactly_equals_low_triggers_exit(self):
        """
        测试用例2：K线low等于P5时触发止盈（边界情况）

        验收标准:
        - 当 kline['low'] == p5 时，返回ExitSignal
        """
        # Arrange
        kline = {
            'low': Decimal('110.0'),    # low = P5
            'close': Decimal('115.0')
        }
        indicators = {
            'p5': 110.0
        }

        # Act
        signal = self.exit_condition.check(
            self.order, kline, indicators, self.timestamp
        )

        # Assert
        self.assertIsNotNone(signal, "P5等于low时应触发止盈")
        self.assertEqual(signal.price, Decimal('115.0'))

    def test_p5_not_touched_no_exit(self):
        """
        测试用例3：K线low未触及P5时不触发

        验收标准:
        - 当 kline['low'] > p5 时，返回None
        """
        # Arrange
        kline = {
            'low': Decimal('120.0'),    # low=120 > P5=110，未触及
            'close': Decimal('125.0')
        }
        indicators = {
            'p5': 110.0
        }

        # Act
        signal = self.exit_condition.check(
            self.order, kline, indicators, self.timestamp
        )

        # Assert
        self.assertIsNone(signal, "P5未触及时不应返回ExitSignal")

    def test_p5_nan_no_exit(self):
        """
        测试用例4：P5为NaN时不触发

        验收标准:
        - 当 p5 为 NaN 时，返回None
        - 避免NaN导致的异常
        """
        # Arrange
        kline = {
            'low': Decimal('100.0'),
            'close': Decimal('105.0')
        }
        indicators = {
            'p5': float('nan')  # P5为NaN
        }

        # Act
        signal = self.exit_condition.check(
            self.order, kline, indicators, self.timestamp
        )

        # Assert
        self.assertIsNone(signal, "P5为NaN时不应触发止盈")

    def test_p5_missing_in_indicators_no_exit(self):
        """
        测试用例5：indicators缺少p5时不触发

        验收标准:
        - 当 indicators 不包含 'p5' 键时，返回None
        """
        # Arrange
        kline = {
            'low': Decimal('100.0'),
            'close': Decimal('105.0')
        }
        indicators = {}  # 缺少p5

        # Act
        signal = self.exit_condition.check(
            self.order, kline, indicators, self.timestamp
        )

        # Assert
        self.assertIsNone(signal, "indicators缺少p5时不应触发止盈")

    def test_exit_price_uses_close_not_low(self):
        """
        测试用例6：验证平仓价格使用close而非low

        验收标准:
        - 成交价格 = kline['close']（而非kline['low']）
        - 符合实际交易逻辑，避免理想化假设
        """
        # Arrange
        kline = {
            'low': Decimal('95.0'),     # low更低
            'close': Decimal('108.0')   # close更高
        }
        indicators = {
            'p5': 100.0
        }

        # Act
        signal = self.exit_condition.check(
            self.order, kline, indicators, self.timestamp
        )

        # Assert
        self.assertIsNotNone(signal)
        self.assertEqual(
            signal.price,
            Decimal('108.0'),
            "应使用close价格而非low价格"
        )
        self.assertNotEqual(
            signal.price,
            Decimal('95.0'),
            "不应使用low价格"
        )

    def test_get_priority_returns_9(self):
        """
        测试用例7：验证优先级为9

        验收标准:
        - get_priority() 返回 9
        - 与P95TakeProfitExit保持一致
        """
        # Act
        priority = self.exit_condition.get_priority()

        # Assert
        self.assertEqual(priority, 9, "优先级应为9")

    def test_get_type_returns_correct_string(self):
        """
        测试用例8：验证exit_type为"p5_touch_take_profit"

        验收标准:
        - get_type() 返回 "p5_touch_take_profit"
        """
        # Act
        exit_type = self.exit_condition.get_type()

        # Assert
        self.assertEqual(
            exit_type,
            'p5_touch_take_profit',
            "exit_type应为'p5_touch_take_profit'"
        )

    def test_kline_missing_low_field_raises_error(self):
        """
        测试用例9：kline缺少'low'字段时抛出异常

        验收标准:
        - 当 kline 缺少 'low' 字段时，抛出KeyError
        """
        # Arrange
        kline = {
            'close': Decimal('105.0')
            # 缺少'low'字段
        }
        indicators = {
            'p5': 110.0
        }

        # Act & Assert
        with self.assertRaises(KeyError):
            self.exit_condition.check(
                self.order, kline, indicators, self.timestamp
            )

    def test_kline_missing_close_field_raises_error(self):
        """
        测试用例10：kline缺少'close'字段时抛出异常

        验收标准:
        - 当 kline 缺少 'close' 字段时，抛出KeyError
        """
        # Arrange
        kline = {
            'low': Decimal('100.0')
            # 缺少'close'字段
        }
        indicators = {
            'p5': 110.0
        }

        # Act & Assert
        with self.assertRaises(KeyError):
            self.exit_condition.check(
                self.order, kline, indicators, self.timestamp
            )

    def test_signal_contains_timestamp(self):
        """
        测试用例11：验证ExitSignal包含正确的timestamp

        验收标准:
        - signal.timestamp == current_timestamp
        """
        # Arrange
        kline = {
            'low': Decimal('100.0'),
            'close': Decimal('105.0')
        }
        indicators = {
            'p5': 110.0
        }
        expected_timestamp = int(datetime(2025, 1, 7, 16, 0, 0).timestamp())

        # Act
        signal = self.exit_condition.check(
            self.order, kline, indicators, expected_timestamp
        )

        # Assert
        self.assertIsNotNone(signal)
        self.assertEqual(signal.timestamp, expected_timestamp)


if __name__ == '__main__':
    unittest.main()
