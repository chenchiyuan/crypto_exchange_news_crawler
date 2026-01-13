"""
仓位管理器单元测试

测试 DynamicPositionManager 的各种场景：
- 正常仓位计算
- 边界条件处理
- 复利效应验证
- 风控效应验证

迭代编号: 043 (动态复利仓位管理)
创建日期: 2026-01-13
"""

import pytest
from decimal import Decimal

from strategy_adapter.core.position_manager import (
    IPositionManager,
    DynamicPositionManager,
)


class TestDynamicPositionManager:
    """DynamicPositionManager 单元测试"""

    def setup_method(self):
        """每个测试方法前初始化"""
        self.pm = DynamicPositionManager()

    # === 正常计算测试 ===

    def test_normal_calculation_no_positions(self):
        """测试正常计算：无持仓"""
        result = self.pm.calculate_position_size(
            available_cash=Decimal("10000"),
            max_positions=10,
            current_positions=0
        )
        assert result == Decimal("1000")

    def test_normal_calculation_partial_positions(self):
        """测试正常计算：部分持仓"""
        result = self.pm.calculate_position_size(
            available_cash=Decimal("9000"),
            max_positions=10,
            current_positions=1
        )
        assert result == Decimal("1000")

    def test_normal_calculation_many_positions(self):
        """测试正常计算：多个持仓"""
        result = self.pm.calculate_position_size(
            available_cash=Decimal("5000"),
            max_positions=10,
            current_positions=5
        )
        assert result == Decimal("1000")

    # === 边界条件测试 ===

    def test_zero_cash(self):
        """测试边界：可用资金为0"""
        result = self.pm.calculate_position_size(
            available_cash=Decimal("0"),
            max_positions=10,
            current_positions=0
        )
        assert result == Decimal("0")

    def test_negative_cash(self):
        """测试边界：可用资金为负"""
        result = self.pm.calculate_position_size(
            available_cash=Decimal("-100"),
            max_positions=10,
            current_positions=0
        )
        assert result == Decimal("0")

    def test_positions_full(self):
        """测试边界：持仓已满"""
        result = self.pm.calculate_position_size(
            available_cash=Decimal("10000"),
            max_positions=10,
            current_positions=10
        )
        assert result == Decimal("0")

    def test_positions_exceed_max(self):
        """测试边界：持仓超过最大值（异常情况）"""
        result = self.pm.calculate_position_size(
            available_cash=Decimal("10000"),
            max_positions=10,
            current_positions=11
        )
        assert result == Decimal("0")

    def test_single_slot_remaining(self):
        """测试边界：仅剩1个仓位槽"""
        result = self.pm.calculate_position_size(
            available_cash=Decimal("5000"),
            max_positions=10,
            current_positions=9
        )
        assert result == Decimal("5000")

    # === 最小金额限制测试 ===

    def test_min_position_not_triggered(self):
        """测试最小金额：计算结果高于最小值"""
        pm = DynamicPositionManager(min_position=Decimal("50"))
        result = pm.calculate_position_size(
            available_cash=Decimal("1000"),
            max_positions=10,
            current_positions=0
        )
        assert result == Decimal("100")

    def test_min_position_triggered(self):
        """测试最小金额：计算结果低于最小值"""
        pm = DynamicPositionManager(min_position=Decimal("200"))
        result = pm.calculate_position_size(
            available_cash=Decimal("1000"),
            max_positions=10,
            current_positions=0
        )
        # 1000 / 10 = 100 < 200，应返回0
        assert result == Decimal("0")

    def test_min_position_equal(self):
        """测试最小金额：计算结果等于最小值"""
        pm = DynamicPositionManager(min_position=Decimal("100"))
        result = pm.calculate_position_size(
            available_cash=Decimal("1000"),
            max_positions=10,
            current_positions=0
        )
        # 1000 / 10 = 100 == 100，应返回100
        assert result == Decimal("100")

    def test_min_position_zero_default(self):
        """测试最小金额：默认值为0（不限制）"""
        pm = DynamicPositionManager()
        assert pm.min_position == Decimal("0")

    # === 复利效应测试 ===

    def test_compound_profit_effect(self):
        """测试复利效应：盈利后单笔金额增大"""
        # 初始：10000现金，0持仓 -> 1000/笔
        initial_result = self.pm.calculate_position_size(
            available_cash=Decimal("10000"),
            max_positions=10,
            current_positions=0
        )
        assert initial_result == Decimal("1000")

        # 盈利后：11000现金，1持仓 -> 11000/9 = 1222.22
        profit_result = self.pm.calculate_position_size(
            available_cash=Decimal("11000"),
            max_positions=10,
            current_positions=1
        )
        expected = Decimal("11000") / Decimal("9")
        assert profit_result == expected
        assert profit_result > initial_result

    def test_compound_large_profit(self):
        """测试复利效应：大额盈利"""
        # 盈利后：20000现金，2持仓 -> 20000/8 = 2500
        result = self.pm.calculate_position_size(
            available_cash=Decimal("20000"),
            max_positions=10,
            current_positions=2
        )
        assert result == Decimal("2500")

    # === 风控效应测试 ===

    def test_risk_control_effect(self):
        """测试风控效应：亏损后单笔金额减小"""
        # 初始：10000现金，0持仓 -> 1000/笔
        initial_result = self.pm.calculate_position_size(
            available_cash=Decimal("10000"),
            max_positions=10,
            current_positions=0
        )
        assert initial_result == Decimal("1000")

        # 亏损后：7000现金，1持仓 -> 7000/9 = 777.78
        loss_result = self.pm.calculate_position_size(
            available_cash=Decimal("7000"),
            max_positions=10,
            current_positions=1
        )
        expected = Decimal("7000") / Decimal("9")
        assert loss_result == expected
        assert loss_result < initial_result

    def test_risk_control_severe_loss(self):
        """测试风控效应：严重亏损"""
        # 严重亏损后：3000现金，1持仓 -> 3000/9 = 333.33
        result = self.pm.calculate_position_size(
            available_cash=Decimal("3000"),
            max_positions=10,
            current_positions=1
        )
        expected = Decimal("3000") / Decimal("9")
        assert result == expected

    # === 精度测试 ===

    def test_decimal_precision(self):
        """测试Decimal精度"""
        result = self.pm.calculate_position_size(
            available_cash=Decimal("10000.123456"),
            max_positions=3,
            current_positions=0
        )
        expected = Decimal("10000.123456") / Decimal("3")
        assert result == expected

    def test_small_amounts(self):
        """测试小额资金计算"""
        result = self.pm.calculate_position_size(
            available_cash=Decimal("100"),
            max_positions=10,
            current_positions=0
        )
        assert result == Decimal("10")

    # === 接口兼容性测试 ===

    def test_implements_protocol(self):
        """测试是否实现IPositionManager接口"""
        pm = DynamicPositionManager()
        # Protocol检查通过方法存在性验证
        assert hasattr(pm, 'calculate_position_size')
        assert callable(pm.calculate_position_size)


class TestDynamicPositionManagerIntegration:
    """DynamicPositionManager 集成场景测试"""

    def test_full_cycle_simulation(self):
        """测试完整交易周期模拟"""
        pm = DynamicPositionManager()

        # 初始状态
        cash = Decimal("10000")
        positions = 0
        max_pos = 5

        # 第1笔：10000 / 5 = 2000
        size1 = pm.calculate_position_size(cash, max_pos, positions)
        assert size1 == Decimal("2000")

        # 买入后
        cash -= size1
        positions += 1

        # 第2笔：8000 / 4 = 2000
        size2 = pm.calculate_position_size(cash, max_pos, positions)
        assert size2 == Decimal("2000")

        # 买入后
        cash -= size2
        positions += 1

        # 模拟盈利：第1笔盈利500
        cash += Decimal("2500")  # 本金2000 + 盈利500
        positions -= 1

        # 第3笔：8500 / 4 = 2125（复利效应）
        size3 = pm.calculate_position_size(cash, max_pos, positions)
        assert size3 == Decimal("2125")
        assert size3 > size1  # 验证复利效应

    def test_loss_recovery_simulation(self):
        """测试亏损恢复模拟"""
        pm = DynamicPositionManager()

        # 初始状态
        cash = Decimal("10000")
        max_pos = 10

        # 模拟连续亏损
        positions = 0
        for i in range(3):
            size = pm.calculate_position_size(cash, max_pos, positions)
            cash -= size
            positions += 1

        # 模拟亏损平仓（每笔亏10%）
        for i in range(3):
            cash += Decimal("900")  # 本金1000 - 亏损100
            positions -= 1

        # 验证风控效应：下次仓位应该减小
        # 剩余现金 = 10000 - 3000 + 2700 = 9700
        # 下一笔 = 9700 / 10 = 970
        next_size = pm.calculate_position_size(cash, max_pos, positions)
        assert next_size == Decimal("970")
        assert next_size < Decimal("1000")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
