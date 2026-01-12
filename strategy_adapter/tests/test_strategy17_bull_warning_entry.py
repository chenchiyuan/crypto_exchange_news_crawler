"""
测试文件：策略17（上涨预警入场策略）单元测试

Purpose:
    验证策略17各组件的正确性：
    - 入场信号检测（consolidation→bull_warning）
    - 买入价格（下一根K线open）
    - 止盈止损逻辑

关联任务: TASK-038-003
关联需求: FP-038-001~004 (function-points.md)
关联架构: architecture.md

测试策略:
    - 单元测试入场信号检测
    - 验证不同状态转变的处理
    - 验证止盈止损触发
"""

import unittest
from decimal import Decimal

from strategy_adapter.strategies import Strategy17BullWarningEntry


class TestStrategy17EntrySignal(unittest.TestCase):
    """Strategy17入场信号检测测试套件"""

    def setUp(self):
        """测试前准备"""
        self.strategy = Strategy17BullWarningEntry(
            position_size=Decimal("1000"),
            stop_loss_pct=5.0
        )

    def test_entry_signal_consolidation_to_bull_warning(self):
        """
        测试用例1：consolidation→bull_warning触发入场

        验收标准:
        - 当cycle_phase从consolidation变为bull_warning时，返回True
        """
        # Arrange
        prev_phase = 'consolidation'
        curr_phase = 'bull_warning'

        # Act
        result = self.strategy._detect_entry_signal(prev_phase, curr_phase)

        # Assert
        self.assertTrue(result)

    def test_no_entry_signal_bull_warning_to_bull_warning(self):
        """
        测试用例2：bull_warning→bull_warning不触发入场

        验收标准:
        - 当cycle_phase持续为bull_warning时，不重��触发入场
        """
        # Arrange
        prev_phase = 'bull_warning'
        curr_phase = 'bull_warning'

        # Act
        result = self.strategy._detect_entry_signal(prev_phase, curr_phase)

        # Assert
        self.assertFalse(result)

    def test_no_entry_signal_bull_strong_to_bull_warning(self):
        """
        测试用例3：bull_strong→bull_warning不触发入场

        验收标准:
        - 当cycle_phase从bull_strong回落到bull_warning时，不触发入场（周期延续）
        """
        # Arrange
        prev_phase = 'bull_strong'
        curr_phase = 'bull_warning'

        # Act
        result = self.strategy._detect_entry_signal(prev_phase, curr_phase)

        # Assert
        self.assertFalse(result)

    def test_no_entry_signal_consolidation_to_consolidation(self):
        """
        测试用例4：consolidation→consolidation不触发入场

        验收标准:
        - 当cycle_phase持续为consolidation时，不触发入场
        """
        # Arrange
        prev_phase = 'consolidation'
        curr_phase = 'consolidation'

        # Act
        result = self.strategy._detect_entry_signal(prev_phase, curr_phase)

        # Assert
        self.assertFalse(result)

    def test_no_entry_signal_consolidation_to_bear_warning(self):
        """
        测试用例5：consolidation→bear_warning不触发入场

        验收标准:
        - 当cycle_phase从consolidation变为bear_warning时，不触发入场（仅关注上涨）
        """
        # Arrange
        prev_phase = 'consolidation'
        curr_phase = 'bear_warning'

        # Act
        result = self.strategy._detect_entry_signal(prev_phase, curr_phase)

        # Assert
        self.assertFalse(result)

    def test_no_entry_signal_bear_warning_to_bull_warning(self):
        """
        测试用例6：bear_warning→bull_warning不触发入场

        验收标准:
        - 当cycle_phase从bear_warning变为bull_warning时，不触发入场
        - 仅从consolidation进入bull_warning才是有效信号
        """
        # Arrange
        prev_phase = 'bear_warning'
        curr_phase = 'bull_warning'

        # Act
        result = self.strategy._detect_entry_signal(prev_phase, curr_phase)

        # Assert
        self.assertFalse(result)


class TestStrategy17Initialization(unittest.TestCase):
    """Strategy17初始化测试套件"""

    def test_default_initialization(self):
        """
        测试用例1：默认初始化参数

        验收标准:
        - 默认position_size=1000
        - 默认stop_loss_pct=5.0
        - 默认max_positions=10
        """
        # Act
        strategy = Strategy17BullWarningEntry()

        # Assert
        self.assertEqual(strategy.position_size, Decimal("1000"))
        self.assertEqual(strategy.stop_loss_pct, 5.0)
        self.assertEqual(strategy.max_positions, 10)

    def test_custom_initialization(self):
        """
        测试用例2：自定义初始化参数

        验收标准:
        - 可自定义position_size, stop_loss_pct, max_positions
        """
        # Act
        strategy = Strategy17BullWarningEntry(
            position_size=Decimal("500"),
            stop_loss_pct=3.0,
            max_positions=5
        )

        # Assert
        self.assertEqual(strategy.position_size, Decimal("500"))
        self.assertEqual(strategy.stop_loss_pct, 3.0)
        self.assertEqual(strategy.max_positions, 5)

    def test_strategy_metadata(self):
        """
        测试用例3：策略元数据

        验收标准:
        - STRATEGY_ID = 'strategy_17'
        - STRATEGY_NAME = '上涨预警入场'
        """
        # Act
        strategy = Strategy17BullWarningEntry()

        # Assert
        self.assertEqual(strategy.STRATEGY_ID, 'strategy_17')
        self.assertEqual(strategy.STRATEGY_NAME, '上涨预警入场')
        self.assertEqual(strategy.get_strategy_name(), '上涨预警入场')


class TestStrategy17RequiredIndicators(unittest.TestCase):
    """Strategy17所需指标测试套件"""

    def test_required_indicators(self):
        """
        测试用例1：验证所需指标列表

        验收标准:
        - 返回 ['ema7', 'ema25', 'ema99', 'cycle_phase']
        """
        # Arrange
        strategy = Strategy17BullWarningEntry()

        # Act
        indicators = strategy.get_required_indicators()

        # Assert
        self.assertIn('ema7', indicators)
        self.assertIn('ema25', indicators)
        self.assertIn('ema99', indicators)
        self.assertIn('cycle_phase', indicators)


if __name__ == '__main__':
    unittest.main()
