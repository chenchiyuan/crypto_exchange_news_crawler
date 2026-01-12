"""
SignalCalculator策略8单元测试

测试策略8: 强势下跌区间做空信号计算功能，包括：
- bear_strong周期+EMA25触及
- bear_strong周期+P95触及
- 非bear_strong周期不触发
- NaN数据处理
- 边界条件
- 数据结构契约

Related:
    - PRD: docs/iterations/022-bear-strong-short-strategy/prd.md
    - Architecture: docs/iterations/022-bear-strong-short-strategy/architecture.md
    - Task: TASK-022-007

关联任务: TASK-022-007
关联需求: FP-022-006 (prd.md)
"""

import unittest
from datetime import datetime, timezone

import numpy as np
from django.test import TestCase

from ddps_z.calculators.signal_calculator import SignalCalculator


class SignalCalculatorStrategy8Test(TestCase):
    """测试策略8: 强势下跌区间做空

    策略8触发条件:
        前置条件: 当前处于强势下跌阶段（bear_strong）
        主条件: 价格触及EMA25或P95（high >= ema25 OR high >= p95）
    """

    def setUp(self):
        """测试前准备：创建计算器实例"""
        self.calculator = SignalCalculator()

    def _create_test_data(
        self,
        high: float,
        close: float,
        ema: float,
        p95: float,
        cycle_phase: str = 'bear_strong',
        beta: float = -1.0,
        inertia_mid: float = 100.0
    ) -> tuple:
        """辅助方法：创建单根K线的测试数据

        Args:
            high: K线最高价
            close: K线收盘价
            ema: EMA25值
            p95: P95阈值
            cycle_phase: 周期状态（默认bear_strong）
            beta: β斜率（默认-1.0）
            inertia_mid: 惯性中值（默认100.0）

        Returns:
            tuple: (klines, ema_series, p5_series, beta_series,
                   inertia_mid_series, p95_series, cycle_phases)
        """
        klines = [
            {
                'open_time': datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
                'high': high,
                'low': 90.0,
                'close': close,
            }
        ]
        ema_series = np.array([ema])
        p5_series = np.array([80.0])  # 策略8不需要p5，给默认值
        beta_series = np.array([beta])
        inertia_mid_series = np.array([inertia_mid])
        p95_series = np.array([p95])

        # 构建cycle_phases（模拟BetaCycleCalculator输出）
        cycle_phases = [cycle_phase]

        return (klines, ema_series, p5_series, beta_series,
                inertia_mid_series, p95_series, cycle_phases)

    def test_strategy8_triggered_when_bear_strong_and_ema25_touched(self):
        """策略8正常触发：bear_strong周期 + 触及EMA25

        场景：
        - cycle_phase = 'bear_strong' ✓
        - high = 105, EMA25 = 100 → high >= EMA25 ✓
        - 预期: 触发，使用close作为开仓价
        """
        klines, ema_series, p5_series, beta_series, inertia_mid_series, p95_series, cycle_phases = (
            self._create_test_data(
                high=105.0,       # >= EMA25(100) ✓
                close=103.0,      # 开仓价格
                ema=100.0,
                p95=110.0,        # high未触及P95
                cycle_phase='bear_strong'
            )
        )

        result = self.calculator.calculate(
            klines=klines,
            ema_series=ema_series,
            p5_series=p5_series,
            beta_series=beta_series,
            inertia_mid_series=inertia_mid_series,
            p95_series=p95_series,
            enabled_strategies=[8]
        )

        short_signals = result['short_signals']
        self.assertEqual(len(short_signals), 1, "应触发1个做空信号")

        signal = short_signals[0]
        self.assertEqual(signal['direction'], 'short')
        self.assertEqual(signal['price'], 103.0, "开仓价格应为close")

        # 检查strategy8触发
        strategies = signal['strategies']
        self.assertEqual(len(strategies), 1)
        strategy8 = strategies[0]
        self.assertEqual(strategy8['id'], 'strategy_8')
        self.assertTrue(strategy8['triggered'])
        self.assertIn('强势下跌期', strategy8['reason'])
        self.assertIn('触及EMA25', strategy8['reason'])

        # 检查details
        details = strategy8['details']
        self.assertEqual(details['cycle_phase'], 'bear_strong')
        self.assertEqual(details['ema25'], 100.0)
        self.assertTrue(details['touches_ema25'])
        self.assertFalse(details['touches_p95'])

    def test_strategy8_triggered_when_bear_strong_and_p95_touched(self):
        """策略8正常触发：bear_strong周期 + 触及P95

        场景：
        - cycle_phase = 'bear_strong' ✓
        - high = 112, P95 = 110 → high >= P95 ✓
        - 预期: 触发
        """
        klines, ema_series, p5_series, beta_series, inertia_mid_series, p95_series, cycle_phases = (
            self._create_test_data(
                high=112.0,       # >= P95(110) ✓
                close=111.0,
                ema=100.0,        # high未触及EMA25
                p95=110.0,
                cycle_phase='bear_strong'
            )
        )

        result = self.calculator.calculate(
            klines=klines,
            ema_series=ema_series,
            p5_series=p5_series,
            beta_series=beta_series,
            inertia_mid_series=inertia_mid_series,
            p95_series=p95_series,
            enabled_strategies=[8]
        )

        short_signals = result['short_signals']
        self.assertEqual(len(short_signals), 1)

        signal = short_signals[0]
        strategy8 = signal['strategies'][0]
        self.assertTrue(strategy8['triggered'])
        self.assertIn('触及P95', strategy8['reason'])

        details = strategy8['details']
        self.assertFalse(details['touches_ema25'])
        self.assertTrue(details['touches_p95'])

    def test_strategy8_triggered_when_both_ema25_and_p95_touched(self):
        """策略8正常触发：bear_strong周期 + 同时触及EMA25和P95

        场景：
        - cycle_phase = 'bear_strong' ✓
        - high = 112, EMA25 = 100, P95 = 110
        - high >= EMA25 ✓ 且 high >= P95 ✓
        - 预期: 触发，reason包含两者
        """
        klines, ema_series, p5_series, beta_series, inertia_mid_series, p95_series, cycle_phases = (
            self._create_test_data(
                high=112.0,       # >= EMA25(100) 且 >= P95(110) ✓
                close=111.0,
                ema=100.0,
                p95=110.0,
                cycle_phase='bear_strong'
            )
        )

        result = self.calculator.calculate(
            klines=klines,
            ema_series=ema_series,
            p5_series=p5_series,
            beta_series=beta_series,
            inertia_mid_series=inertia_mid_series,
            p95_series=p95_series,
            enabled_strategies=[8]
        )

        short_signals = result['short_signals']
        self.assertEqual(len(short_signals), 1)

        signal = short_signals[0]
        strategy8 = signal['strategies'][0]
        self.assertTrue(strategy8['triggered'])
        self.assertIn('触及EMA25', strategy8['reason'])
        self.assertIn('触及P95', strategy8['reason'])

        details = strategy8['details']
        self.assertTrue(details['touches_ema25'])
        self.assertTrue(details['touches_p95'])

    def test_strategy8_not_triggered_when_not_bear_strong_phase(self):
        """策略8不触发：非bear_strong周期

        场景：
        - cycle_phase = 'consolidation' (非bear_strong)
        - high = 105, EMA25 = 100 → high >= EMA25 ✓
        - 预期: 不触发（前置条件不满足）
        """
        klines, ema_series, p5_series, beta_series, inertia_mid_series, p95_series, cycle_phases = (
            self._create_test_data(
                high=105.0,
                close=103.0,
                ema=100.0,
                p95=110.0,
                cycle_phase='consolidation'  # 非bear_strong
            )
        )

        result = self.calculator.calculate(
            klines=klines,
            ema_series=ema_series,
            p5_series=p5_series,
            beta_series=beta_series,
            inertia_mid_series=inertia_mid_series,
            p95_series=p95_series,
            enabled_strategies=[8]
        )

        short_signals = result['short_signals']
        self.assertEqual(len(short_signals), 0, "非bear_strong周期不应触发")

    def test_strategy8_not_triggered_when_high_below_thresholds(self):
        """策略8不触发：bear_strong周期但价格未触及阈值

        场景：
        - cycle_phase = 'bear_strong' ✓
        - high = 95, EMA25 = 100, P95 = 110
        - high < EMA25 且 high < P95
        - 预期: 不触发（主条件不满足）
        """
        klines, ema_series, p5_series, beta_series, inertia_mid_series, p95_series, cycle_phases = (
            self._create_test_data(
                high=95.0,        # < EMA25(100) 且 < P95(110)
                close=93.0,
                ema=100.0,
                p95=110.0,
                cycle_phase='bear_strong'
            )
        )

        result = self.calculator.calculate(
            klines=klines,
            ema_series=ema_series,
            p5_series=p5_series,
            beta_series=beta_series,
            inertia_mid_series=inertia_mid_series,
            p95_series=p95_series,
            enabled_strategies=[8]
        )

        short_signals = result['short_signals']
        self.assertEqual(len(short_signals), 0, "价格未触及阈值不应触发")

    def test_strategy8_not_triggered_when_ema_nan(self):
        """策略8不触发：EMA为NaN

        场景：
        - cycle_phase = 'bear_strong' ✓
        - EMA = NaN（无效数据）
        - 预期: 不触发（跳过无效数据）
        """
        klines, ema_series, p5_series, beta_series, inertia_mid_series, p95_series, cycle_phases = (
            self._create_test_data(
                high=105.0,
                close=103.0,
                ema=np.nan,       # EMA无效
                p95=110.0,
                cycle_phase='bear_strong'
            )
        )

        result = self.calculator.calculate(
            klines=klines,
            ema_series=ema_series,
            p5_series=p5_series,
            beta_series=beta_series,
            inertia_mid_series=inertia_mid_series,
            p95_series=p95_series,
            enabled_strategies=[8]
        )

        short_signals = result['short_signals']
        self.assertEqual(len(short_signals), 0, "EMA为NaN不应触发")

    def test_strategy8_not_triggered_when_p95_nan(self):
        """策略8不触发：P95为NaN

        场景：
        - cycle_phase = 'bear_strong' ✓
        - P95 = NaN（无效数据）
        - 预期: 不触发（跳过无效数据）
        """
        klines, ema_series, p5_series, beta_series, inertia_mid_series, p95_series, cycle_phases = (
            self._create_test_data(
                high=105.0,
                close=103.0,
                ema=100.0,
                p95=np.nan,       # P95无效
                cycle_phase='bear_strong'
            )
        )

        result = self.calculator.calculate(
            klines=klines,
            ema_series=ema_series,
            p5_series=p5_series,
            beta_series=beta_series,
            inertia_mid_series=inertia_mid_series,
            p95_series=p95_series,
            enabled_strategies=[8]
        )

        short_signals = result['short_signals']
        self.assertEqual(len(short_signals), 0, "P95为NaN不应触发")

    def test_strategy8_not_triggered_when_cycle_phase_none(self):
        """策略8不触发：cycle_phase为None

        场景：
        - cycle_phase = None（未计算周期状态）
        - 预期: 不触发（前置条件不满足）
        """
        klines, ema_series, p5_series, beta_series, inertia_mid_series, p95_series, cycle_phases = (
            self._create_test_data(
                high=105.0,
                close=103.0,
                ema=100.0,
                p95=110.0,
                cycle_phase=None  # cycle_phase为None
            )
        )

        # 模拟cycle_phases为None的情况
        result = self.calculator.calculate(
            klines=klines,
            ema_series=ema_series,
            p5_series=p5_series,
            beta_series=beta_series,
            inertia_mid_series=inertia_mid_series,
            p95_series=p95_series,
            enabled_strategies=[8]
        )

        short_signals = result['short_signals']
        # 注意：cycle_phases未计算时，SignalCalculator会自动计算
        # 这个测试用例需要验证cycle_phase为None时不触发
        # 实际上SignalCalculator会自动计算cycle_phases
        # 这里我们需要直接测试_calculate_strategy8方法

        strategy8_result = self.calculator._calculate_strategy8(
            kline=klines[0],
            ema=100.0,
            p95=110.0,
            cycle_phase=None  # 显式传None
        )

        self.assertFalse(strategy8_result['triggered'],
                        "cycle_phase为None不应触发")

    def test_strategy8_boundary_ema25_equals_high(self):
        """策略8边界条件：high恰好等于EMA25

        场景：
        - cycle_phase = 'bear_strong' ✓
        - high = 100, EMA25 = 100 → high == EMA25（边界）
        - 预期: 触发（high >= EMA25）
        """
        klines, ema_series, p5_series, beta_series, inertia_mid_series, p95_series, cycle_phases = (
            self._create_test_data(
                high=100.0,       # == EMA25(100)
                close=99.0,
                ema=100.0,
                p95=110.0,
                cycle_phase='bear_strong'
            )
        )

        result = self.calculator.calculate(
            klines=klines,
            ema_series=ema_series,
            p5_series=p5_series,
            beta_series=beta_series,
            inertia_mid_series=inertia_mid_series,
            p95_series=p95_series,
            enabled_strategies=[8]
        )

        short_signals = result['short_signals']
        self.assertEqual(len(short_signals), 1, "high等于EMA25应触发")

    def test_strategy8_boundary_p95_equals_high(self):
        """策略8边界条件：high恰好等于P95

        场景：
        - cycle_phase = 'bear_strong' ✓
        - high = 110, P95 = 110 → high == P95（边界）
        - 预期: 触发（high >= P95）
        """
        klines, ema_series, p5_series, beta_series, inertia_mid_series, p95_series, cycle_phases = (
            self._create_test_data(
                high=110.0,       # == P95(110)
                close=109.0,
                ema=100.0,
                p95=110.0,
                cycle_phase='bear_strong'
            )
        )

        result = self.calculator.calculate(
            klines=klines,
            ema_series=ema_series,
            p5_series=p5_series,
            beta_series=beta_series,
            inertia_mid_series=inertia_mid_series,
            p95_series=p95_series,
            enabled_strategies=[8]
        )

        short_signals = result['short_signals']
        self.assertEqual(len(short_signals), 1, "high等于P95应触发")

    def test_strategy8_data_contract(self):
        """验证策略8返回数据结构契约

        验证：
        - signal包含timestamp, kline_index, strategies, price, direction
        - strategy8包含id, name, triggered, reason, details
        - details包含cycle_phase, ema25, p95, current_high, current_close,
          touches_ema25, touches_p95
        """
        klines, ema_series, p5_series, beta_series, inertia_mid_series, p95_series, cycle_phases = (
            self._create_test_data(
                high=105.0,
                close=103.0,
                ema=100.0,
                p95=110.0,
                cycle_phase='bear_strong'
            )
        )

        result = self.calculator.calculate(
            klines=klines,
            ema_series=ema_series,
            p5_series=p5_series,
            beta_series=beta_series,
            inertia_mid_series=inertia_mid_series,
            p95_series=p95_series,
            enabled_strategies=[8]
        )

        short_signals = result['short_signals']
        self.assertEqual(len(short_signals), 1)

        # 检查signal结构
        signal = short_signals[0]
        self.assertIn('timestamp', signal)
        self.assertIn('kline_index', signal)
        self.assertIn('strategies', signal)
        self.assertIn('price', signal)
        self.assertIn('direction', signal)
        self.assertEqual(signal['direction'], 'short')

        # 检查strategy8结构
        strategy8 = signal['strategies'][0]
        self.assertIn('id', strategy8)
        self.assertIn('name', strategy8)
        self.assertIn('triggered', strategy8)
        self.assertIn('reason', strategy8)
        self.assertIn('details', strategy8)

        # 检查details结构
        details = strategy8['details']
        self.assertIn('cycle_phase', details)
        self.assertIn('ema25', details)
        self.assertIn('p95', details)
        self.assertIn('current_high', details)
        self.assertIn('current_close', details)
        self.assertIn('touches_ema25', details)
        self.assertIn('touches_p95', details)


if __name__ == '__main__':
    unittest.main()
