"""
BetaCycleCalculator单元测试

测试β宏观周期计算器的状态机逻辑，包括：
- 完整上涨周期: idle → bull_warning → bull_strong → idle
- 完整下跌周期: idle → bear_warning → bear_strong → idle
- 未确认周期: idle → warning → idle
- 边界值测试
- 空数据处理
- 单K线处理

Related:
    - PRD: docs/iterations/018-beta-cycle-indicator/prd.md
    - Architecture: docs/iterations/018-beta-cycle-indicator/architecture.md
"""

from django.test import TestCase

from ddps_z.calculators.beta_cycle_calculator import (
    BetaCycleCalculator,
    PHASE_LABELS,
    PHASE_COLORS,
)


class BetaCycleCalculatorBasicTest(TestCase):
    """基础功能测试"""

    def setUp(self):
        """测试前准备：创建计算器实例"""
        # 使用默认阈值
        self.calculator = BetaCycleCalculator()

    def test_empty_data(self):
        """测试空数据处理"""
        cycle_phases, current_cycle = self.calculator.calculate(
            beta_list=[],
            timestamps=[],
            prices=[],
        )

        self.assertEqual(cycle_phases, [])
        self.assertEqual(current_cycle['phase'], 'consolidation')
        self.assertEqual(current_cycle['duration_bars'], 0)

    def test_single_kline_consolidation(self):
        """测试单根K线（震荡期）"""
        # β = 5 (显示值500)，低于600阈值
        cycle_phases, current_cycle = self.calculator.calculate(
            beta_list=[5.0],  # 原始值，显示值为500
            timestamps=[1704067200000],  # 2024-01-01 00:00
            prices=[100.0],
        )

        self.assertEqual(len(cycle_phases), 1)
        self.assertEqual(cycle_phases[0], 'consolidation')
        self.assertEqual(current_cycle['phase'], 'consolidation')


class BetaCycleCalculatorBullCycleTest(TestCase):
    """上涨周期测试"""

    def setUp(self):
        """测试前准备"""
        self.calculator = BetaCycleCalculator()

    def test_complete_bull_cycle(self):
        """测试完整上涨周期: consolidation → bull_warning → bull_strong → consolidation

        场景：
        - K线1: β = 5 (500) → 震荡
        - K线2: β = 7 (700), 增加 → 上涨预警
        - K线3: β = 11 (1100), 增加 → 强势上涨
        - K线4: β = 8 (800) → 保持强势上涨
        - K线5: β = -0.1 (-10), 跌破0 → 震荡
        """
        beta_list = [5.0, 7.0, 11.0, 8.0, -0.1]  # 原始值
        timestamps = [
            1704067200000,  # 2024-01-01 00:00
            1704081600000,  # 2024-01-01 04:00
            1704096000000,  # 2024-01-01 08:00
            1704110400000,  # 2024-01-01 12:00
            1704124800000,  # 2024-01-01 16:00
        ]
        prices = [100.0, 102.0, 105.0, 104.0, 101.0]

        cycle_phases, current_cycle = self.calculator.calculate(
            beta_list=beta_list,
            timestamps=timestamps,
            prices=prices,
        )

        self.assertEqual(len(cycle_phases), 5)
        self.assertEqual(cycle_phases[0], 'consolidation')  # β=500 < 600
        self.assertEqual(cycle_phases[1], 'bull_warning')   # β=700 > 600, 增加
        self.assertEqual(cycle_phases[2], 'bull_strong')    # β=1100 > 1000
        self.assertEqual(cycle_phases[3], 'bull_strong')    # 保持强势上涨
        self.assertEqual(cycle_phases[4], 'consolidation')  # β=-10 <= 0

        # 最后是震荡期
        self.assertEqual(current_cycle['phase'], 'consolidation')

    def test_unconfirmed_bull_warning(self):
        """测试未确认的上涨预警: consolidation → bull_warning → consolidation

        场景：β突破600但未达1000就跌回0
        - K线1: β = 5 (500) → 震荡
        - K线2: β = 7 (700), 增加 → 上涨预警
        - K线3: β = 8 (800), 继续增加 → 保持上涨预警
        - K线4: β = -0.1 (-10), 跌破0 → 震荡（未确认）
        """
        beta_list = [5.0, 7.0, 8.0, -0.1]
        timestamps = [
            1704067200000,
            1704081600000,
            1704096000000,
            1704110400000,
        ]
        prices = [100.0, 102.0, 103.0, 99.0]

        cycle_phases, current_cycle = self.calculator.calculate(
            beta_list=beta_list,
            timestamps=timestamps,
            prices=prices,
        )

        self.assertEqual(cycle_phases[0], 'consolidation')
        self.assertEqual(cycle_phases[1], 'bull_warning')
        self.assertEqual(cycle_phases[2], 'bull_warning')
        self.assertEqual(cycle_phases[3], 'consolidation')

        self.assertEqual(current_cycle['phase'], 'consolidation')

    def test_bull_warning_requires_increasing_beta(self):
        """测试上涨预警需要β递增

        场景：β > 600 但不是递增，不应触发预警
        - K线1: β = 7 (700) → 震荡（首根K线无法判断递增）
        - K线2: β = 6.5 (650), 减少 → 保持震荡
        """
        beta_list = [7.0, 6.5]
        timestamps = [1704067200000, 1704081600000]
        prices = [100.0, 99.0]

        cycle_phases, current_cycle = self.calculator.calculate(
            beta_list=beta_list,
            timestamps=timestamps,
            prices=prices,
        )

        # 第一根K线无法判断递增，保持震荡
        # 第二根K线β减少，保持震荡
        self.assertEqual(cycle_phases[0], 'consolidation')
        self.assertEqual(cycle_phases[1], 'consolidation')


class BetaCycleCalculatorBearCycleTest(TestCase):
    """下跌周期测试"""

    def setUp(self):
        """测试前准备"""
        self.calculator = BetaCycleCalculator()

    def test_complete_bear_cycle(self):
        """测试完整下跌周期: consolidation → bear_warning → bear_strong → consolidation

        场景：
        - K线1: β = -5 (-500) → 震荡
        - K线2: β = -7 (-700), 减少 → 下跌预警
        - K线3: β = -11 (-1100), 减少 → 强势下跌
        - K线4: β = -8 (-800) → 保持强势下跌
        - K线5: β = 0.1 (10), 回升到0以上 → 震荡
        """
        beta_list = [-5.0, -7.0, -11.0, -8.0, 0.1]
        timestamps = [
            1704067200000,
            1704081600000,
            1704096000000,
            1704110400000,
            1704124800000,
        ]
        prices = [100.0, 98.0, 95.0, 96.0, 99.0]

        cycle_phases, current_cycle = self.calculator.calculate(
            beta_list=beta_list,
            timestamps=timestamps,
            prices=prices,
        )

        self.assertEqual(len(cycle_phases), 5)
        self.assertEqual(cycle_phases[0], 'consolidation')  # β=-500 > -600
        self.assertEqual(cycle_phases[1], 'bear_warning')   # β=-700 < -600, 减少
        self.assertEqual(cycle_phases[2], 'bear_strong')    # β=-1100 < -1000
        self.assertEqual(cycle_phases[3], 'bear_strong')    # 保持强势下跌
        self.assertEqual(cycle_phases[4], 'consolidation')  # β=10 >= 0

        self.assertEqual(current_cycle['phase'], 'consolidation')

    def test_unconfirmed_bear_warning(self):
        """测试未确认的下跌预警"""
        beta_list = [-5.0, -7.0, -8.0, 0.1]
        timestamps = [
            1704067200000,
            1704081600000,
            1704096000000,
            1704110400000,
        ]
        prices = [100.0, 98.0, 97.0, 101.0]

        cycle_phases, current_cycle = self.calculator.calculate(
            beta_list=beta_list,
            timestamps=timestamps,
            prices=prices,
        )

        self.assertEqual(cycle_phases[0], 'consolidation')
        self.assertEqual(cycle_phases[1], 'bear_warning')
        self.assertEqual(cycle_phases[2], 'bear_warning')
        self.assertEqual(cycle_phases[3], 'consolidation')


class BetaCycleCalculatorBoundaryTest(TestCase):
    """边界值测试"""

    def setUp(self):
        """测试前准备"""
        self.calculator = BetaCycleCalculator()

    def test_exact_threshold_values(self):
        """测试恰好等于阈值的情况

        - β = 6.0 (600) 恰好等于bull_warning阈值
        - 条件是 > 600，所以不应触发
        """
        beta_list = [5.0, 6.0]  # 600恰好等于阈值
        timestamps = [1704067200000, 1704081600000]
        prices = [100.0, 101.0]

        cycle_phases, current_cycle = self.calculator.calculate(
            beta_list=beta_list,
            timestamps=timestamps,
            prices=prices,
        )

        # β = 600 不触发（需要 > 600）
        self.assertEqual(cycle_phases[0], 'consolidation')
        self.assertEqual(cycle_phases[1], 'consolidation')

    def test_null_beta_values(self):
        """测试包含None的β值"""
        beta_list = [5.0, None, 7.0, 11.0]
        timestamps = [
            1704067200000,
            1704081600000,
            1704096000000,
            1704110400000,
        ]
        prices = [100.0, 100.5, 102.0, 105.0]

        cycle_phases, current_cycle = self.calculator.calculate(
            beta_list=beta_list,
            timestamps=timestamps,
            prices=prices,
        )

        self.assertEqual(len(cycle_phases), 4)
        self.assertEqual(cycle_phases[0], 'consolidation')
        self.assertEqual(cycle_phases[1], 'consolidation')  # None视为震荡
        # K线3: β=700 > 600 且增加（从None后无法判断增加，保持震荡）
        # 实际上由于前一个是None，无法判断是否增加


class BetaCycleCalculatorCurrentCycleTest(TestCase):
    """当前周期统计测试"""

    def setUp(self):
        """测试前准备"""
        self.calculator = BetaCycleCalculator()

    def test_current_cycle_in_bull_strong(self):
        """测试处于强势上涨期时的当前周期统计"""
        beta_list = [5.0, 7.0, 11.0, 12.0]  # 保持在强势上涨
        timestamps = [
            1704067200000,  # 2024-01-01 00:00
            1704081600000,  # 2024-01-01 04:00
            1704096000000,  # 2024-01-01 08:00
            1704110400000,  # 2024-01-01 12:00
        ]
        prices = [100.0, 102.0, 105.0, 108.0]

        cycle_phases, current_cycle = self.calculator.calculate(
            beta_list=beta_list,
            timestamps=timestamps,
            prices=prices,
            interval_hours=4.0,
        )

        # 最后一根K线是强势上涨
        self.assertEqual(current_cycle['phase'], 'bull_strong')
        self.assertEqual(current_cycle['phase_label'], '强势上涨')
        self.assertEqual(current_cycle['phase_color'], 'success')

        # 从K线2（上涨预警）开始，持续3根K线
        self.assertEqual(current_cycle['duration_bars'], 3)
        self.assertEqual(current_cycle['duration_hours'], 12.0)

        # 起始价格是K线2的收盘价
        self.assertEqual(current_cycle['start_price'], 102.0)

        # 当前β值（显示值）
        self.assertEqual(current_cycle['current_beta'], 1200.0)

        # 周期内最大β值
        self.assertEqual(current_cycle['max_beta'], 1200.0)

    def test_current_cycle_consolidation(self):
        """测试震荡期的当前周期统计"""
        beta_list = [3.0, 4.0, 2.0]  # 始终低于阈值
        timestamps = [
            1704067200000,
            1704081600000,
            1704096000000,
        ]
        prices = [100.0, 101.0, 99.0]

        cycle_phases, current_cycle = self.calculator.calculate(
            beta_list=beta_list,
            timestamps=timestamps,
            prices=prices,
        )

        self.assertEqual(current_cycle['phase'], 'consolidation')
        self.assertEqual(current_cycle['phase_label'], '震荡')
        self.assertEqual(current_cycle['duration_bars'], 0)
        self.assertEqual(current_cycle['start_time'], None)
        self.assertEqual(current_cycle['start_price'], None)
        self.assertEqual(current_cycle['max_beta'], None)


class BetaCycleCalculatorCustomThresholdsTest(TestCase):
    """自定义阈值测试"""

    def test_custom_thresholds(self):
        """测试使用自定义阈值"""
        custom_thresholds = {
            'bull_warning': 300,    # 更低的阈值
            'bull_strong': 500,
            'bear_warning': -300,
            'bear_strong': -500,
            'cycle_end': 0,
        }
        calculator = BetaCycleCalculator(thresholds=custom_thresholds)

        # β = 4 (400) > 300 触发上涨预警
        beta_list = [2.0, 4.0]
        timestamps = [1704067200000, 1704081600000]
        prices = [100.0, 102.0]

        cycle_phases, current_cycle = calculator.calculate(
            beta_list=beta_list,
            timestamps=timestamps,
            prices=prices,
        )

        self.assertEqual(cycle_phases[0], 'consolidation')
        self.assertEqual(cycle_phases[1], 'bull_warning')  # 使用自定义阈值


class BetaCycleCalculatorPhaseLabelTest(TestCase):
    """周期标签映射测试"""

    def test_phase_labels(self):
        """测试周期标签映射"""
        self.assertEqual(PHASE_LABELS['consolidation'], '震荡')
        self.assertEqual(PHASE_LABELS['bull_warning'], '上涨预警')
        self.assertEqual(PHASE_LABELS['bull_strong'], '强势上涨')
        self.assertEqual(PHASE_LABELS['bear_warning'], '下跌预警')
        self.assertEqual(PHASE_LABELS['bear_strong'], '强势下跌')

    def test_phase_colors(self):
        """测试周期颜色映射"""
        self.assertEqual(PHASE_COLORS['consolidation'], 'secondary')
        self.assertEqual(PHASE_COLORS['bull_strong'], 'success')
        self.assertEqual(PHASE_COLORS['bear_strong'], 'danger')
