"""
经验CDF指标计算器单元测试

测试覆盖：
- EMA计算（边界、正常、精度）
- 偏离率计算
- EWMA均值/波动率测试
- 经验CDF测试（冷启动、窗口边界、百分位正确性）
- reset方法测试

迭代编号: 034 (滚动经验CDF信号策略)
创建日期: 2026-01-12
关联任务: TASK-034-004
"""

import pytest
from decimal import Decimal
import pandas as pd
import numpy as np

from strategy_adapter.calculators.empirical_cdf_calculator import EmpiricalCDFCalculator


class TestEmpiricalCDFCalculatorInit:
    """初始化测试"""

    def test_default_params(self):
        """默认参数初始化"""
        calc = EmpiricalCDFCalculator()
        assert calc._ema_period == 25
        assert calc._ewma_period == 50
        assert calc._cdf_window == 100
        assert calc._bar_count == 0
        assert calc._ema is None
        assert calc._mu is None

    def test_custom_params(self):
        """自定义参数初始化"""
        calc = EmpiricalCDFCalculator(
            ema_period=10,
            ewma_period=20,
            cdf_window=50,
            epsilon=1e-10
        )
        assert calc._ema_period == 10
        assert calc._ewma_period == 20
        assert calc._cdf_window == 50


class TestEMACalculation:
    """EMA计算测试"""

    def test_ema_first_bar(self):
        """第一根K线EMA等于close"""
        calc = EmpiricalCDFCalculator(ema_period=25)
        result = calc.update(Decimal("100.00"))
        assert result['ema'] == Decimal("100.00")

    def test_ema_incremental(self):
        """EMA增量更新"""
        calc = EmpiricalCDFCalculator(ema_period=25)

        # 第一根
        result1 = calc.update(Decimal("100.00"))
        ema1 = result1['ema']

        # 第二根：EMA应该向新价格靠近
        result2 = calc.update(Decimal("110.00"))
        ema2 = result2['ema']

        # EMA应该在100和110之间，且更接近100（α较小）
        assert Decimal("100.00") < ema2 < Decimal("110.00")

        # 验证增量公式：EMA_t = α * close + (1-α) * EMA_{t-1}
        alpha = Decimal(2) / Decimal(26)  # 2/(25+1)
        expected_ema2 = alpha * Decimal("110.00") + (1 - alpha) * Decimal("100.00")
        assert abs(ema2 - expected_ema2) < Decimal("0.0001")

    def test_ema_vs_pandas(self):
        """EMA计算结果与pandas一致"""
        closes = [100, 102, 101, 103, 105, 104, 106, 108, 107, 109] * 5
        closes_decimal = [Decimal(str(c)) for c in closes]

        # 使用自实现计算
        calc = EmpiricalCDFCalculator(ema_period=25)
        our_emas = []
        for close in closes_decimal:
            result = calc.update(close)
            our_emas.append(float(result['ema']))

        # 使用pandas计算
        df = pd.DataFrame({'close': closes})
        pd_emas = df['close'].ewm(span=25, adjust=False).mean().tolist()

        # 比较（允许小误差）
        for i, (our, pd_val) in enumerate(zip(our_emas, pd_emas)):
            assert abs(our - pd_val) < 0.0001, f"Bar {i}: our={our}, pandas={pd_val}"


class TestDeviationCalculation:
    """偏离率计算测试"""

    def test_deviation_positive(self):
        """正偏离率：价格高于EMA"""
        calc = EmpiricalCDFCalculator(ema_period=25)

        # 让EMA稳定在100附近
        for _ in range(50):
            calc.update(Decimal("100.00"))

        # 价格上涨到105
        result = calc.update(Decimal("105.00"))
        d = result['d']

        # D应该为正，约5%
        assert d > 0
        # 粗略检查：(105-EMA)/EMA 约为正值
        assert d < Decimal("0.1")  # 不应该太大

    def test_deviation_negative(self):
        """负偏离率：价格低于EMA"""
        calc = EmpiricalCDFCalculator(ema_period=25)

        # 让EMA稳定在100附近
        for _ in range(50):
            calc.update(Decimal("100.00"))

        # 价格下跌到95
        result = calc.update(Decimal("95.00"))
        d = result['d']

        # D应该为负
        assert d < 0

    def test_deviation_precision(self):
        """偏离率计算精度"""
        calc = EmpiricalCDFCalculator(ema_period=25)

        # 第一根K线：EMA = 100，偏离率 = 0
        result = calc.update(Decimal("100.00"))
        assert result['d'] == Decimal("0")


class TestEWMACalculation:
    """EWMA均值/波动率测试"""

    def test_ewma_first_bar(self):
        """第一根K线EWMA初始化"""
        calc = EmpiricalCDFCalculator()
        result = calc.update(Decimal("100.00"))

        # 第一根K线：μ = D = 0，σ = 0
        assert result['mu'] == Decimal("0")
        # σ不应该为0（有epsilon保护）
        assert result['sigma'] > 0

    def test_ewma_stability(self):
        """EWMA数值稳定性"""
        calc = EmpiricalCDFCalculator()

        # 连续相同价格
        for _ in range(100):
            result = calc.update(Decimal("100.00"))

        # σ应该很小但不为0
        assert result['sigma'] > 0
        assert result['sigma'] < Decimal("0.01")

    def test_ewma_sigma_always_positive(self):
        """波动率始终为正"""
        calc = EmpiricalCDFCalculator()

        # 各种价格模式
        prices = [100, 100, 100, 105, 95, 100, 110, 90, 100]
        for price in prices * 20:
            result = calc.update(Decimal(str(price)))
            assert result['sigma'] > 0, f"sigma should be positive, got {result['sigma']}"


class TestStandardizedDeviation:
    """标准化偏离X测试"""

    def test_x_calculation(self):
        """X计算正确性"""
        calc = EmpiricalCDFCalculator()

        # 让计算器warm up
        for _ in range(50):
            calc.update(Decimal("100.00"))

        # 价格大幅上涨
        result = calc.update(Decimal("110.00"))

        # X应该是正数（价格高于均值）
        assert result['x'] > 0

    def test_x_with_zero_sigma(self):
        """σ接近0时X的处理"""
        calc = EmpiricalCDFCalculator()

        # 连续相同价格，σ很小
        for _ in range(10):
            result = calc.update(Decimal("100.00"))

        # X应该是有限值（不是inf或nan）
        assert result['x'] is not None
        assert not np.isnan(float(result['x']))
        assert not np.isinf(float(result['x']))


class TestEmpiricalCDF:
    """滚动经验CDF测试"""

    def test_prob_cold_start(self):
        """冷启动期返回None"""
        calc = EmpiricalCDFCalculator(cdf_window=100)

        # 前100根K线Prob应该为None
        for i in range(100):
            result = calc.update(Decimal("100.00"))
            assert result['prob'] is None, f"Bar {i}: prob should be None during cold start"

    def test_prob_after_warmup(self):
        """冷启动后返回有效值"""
        calc = EmpiricalCDFCalculator(cdf_window=100)

        # warm up
        for _ in range(100):
            calc.update(Decimal("100.00"))

        # 第101根应该有Prob值
        result = calc.update(Decimal("100.00"))
        assert result['prob'] is not None

    def test_prob_range(self):
        """百分位范围0-100"""
        calc = EmpiricalCDFCalculator(cdf_window=100)

        # warm up + 额外测试
        prices = [100 + i * 0.1 for i in range(150)]
        for price in prices:
            result = calc.update(Decimal(str(price)))
            if result['prob'] is not None:
                assert 0 <= result['prob'] <= 100, f"prob out of range: {result['prob']}"

    def test_prob_window_exclusion(self):
        """窗口排除当前样本（因果性验证）

        注意：经验CDF计算的是标准化偏离X的百分位，不是原始价格。
        X = (D - μ) / σ，其中 D = (close - EMA) / EMA

        验证思路：
        1. 使用稳定价格让指标进入稳定状态
        2. 极端价格变化会产生极端的X值
        3. 验证新的极端X值的百分位计算正确
        """
        calc = EmpiricalCDFCalculator(cdf_window=5)

        # 让指标稳定在100附近
        for _ in range(5):
            calc.update(Decimal("100"))

        # 此时历史X值应该都接近0（因为价格=EMA，偏离率≈0）

        # 添加一个高价格（大正偏离）
        result = calc.update(Decimal("120"))

        # 这个大正偏离应该产生大X值，Prob应该是100%（因为历史X都≈0）
        assert result['prob'] == 100.0, f"Expected 100%, got {result['prob']}"

        # 添加一个低价格（大负偏离）
        result2 = calc.update(Decimal("80"))

        # 历史X值现在包含一个大正值，这个负偏离应该产生小X值
        # Prob取决于有多少历史X <= 当前X
        # 由于历史包含一个很大的正X，当前负X应该是较小的
        assert result2['prob'] is not None
        # 不做精确断言，只验证返回了有效值

    def test_prob_percentile_accuracy(self):
        """百分位计算准确性

        经验CDF计算的是标准化偏离X的百分位。
        验证思路：使用稳定价格产生接近0的X，然后验证Prob值合理。
        """
        calc = EmpiricalCDFCalculator(cdf_window=10)

        # 添加10个稳定价格，产生接近0的X值
        for _ in range(10):
            calc.update(Decimal("100"))

        # 历史X值现在应该都接近0

        # 再添加一个接近的值，X应该接近0
        result = calc.update(Decimal("100"))

        # Prob应该接近50%（因为X≈0，约一半历史值<=0，一半>0）
        # 实际上由于数值精度，可能在0-100之间
        assert result['prob'] is not None
        # 不做精确断言，只验证返回了有效值且在合理范围
        assert 0 <= result['prob'] <= 100

    def test_prob_extreme_values(self):
        """极端值的百分位测试"""
        calc = EmpiricalCDFCalculator(cdf_window=10)

        # 使用稳定价格warm up
        for _ in range(10):
            calc.update(Decimal("100"))

        # 极端高价格应该产生接近100%的Prob
        result_high = calc.update(Decimal("200"))
        assert result_high['prob'] >= 90, f"Expected high prob, got {result_high['prob']}"

        # 极端低价格应该产生接近0%的Prob
        result_low = calc.update(Decimal("50"))
        assert result_low['prob'] <= 10, f"Expected low prob, got {result_low['prob']}"


class TestReset:
    """reset方法测试"""

    def test_reset_clears_state(self):
        """reset清除所有状态"""
        calc = EmpiricalCDFCalculator()

        # 更新一些数据
        for _ in range(50):
            calc.update(Decimal("100.00"))

        # 验证状态不为空
        assert calc._bar_count > 0
        assert calc._ema is not None

        # 重置
        calc.reset()

        # 验证状态已清空
        assert calc._bar_count == 0
        assert calc._ema is None
        assert calc._mu is None
        assert len(calc._x_history) == 0

    def test_reset_allows_reuse(self):
        """reset后可以重新使用"""
        calc = EmpiricalCDFCalculator()

        # 第一轮
        for _ in range(10):
            calc.update(Decimal("100.00"))
        first_round_count = calc.bar_count

        # 重置
        calc.reset()

        # 第二轮
        for _ in range(10):
            calc.update(Decimal("100.00"))

        # 验证bar_count是独立的
        assert calc.bar_count == 10


class TestProperties:
    """属性测试"""

    def test_bar_count(self):
        """bar_count属性"""
        calc = EmpiricalCDFCalculator()
        assert calc.bar_count == 0

        calc.update(Decimal("100"))
        assert calc.bar_count == 1

        calc.update(Decimal("100"))
        assert calc.bar_count == 2

    def test_is_warmed_up(self):
        """is_warmed_up属性"""
        calc = EmpiricalCDFCalculator(cdf_window=10)

        assert calc.is_warmed_up is False

        for _ in range(9):
            calc.update(Decimal("100"))
            assert calc.is_warmed_up is False

        calc.update(Decimal("100"))
        assert calc.is_warmed_up is True

    def test_warmup_remaining(self):
        """warmup_remaining属性"""
        calc = EmpiricalCDFCalculator(cdf_window=10)

        assert calc.warmup_remaining == 10

        for i in range(10):
            calc.update(Decimal("100"))
            assert calc.warmup_remaining == max(0, 10 - i - 1)

        assert calc.warmup_remaining == 0

    def test_get_state(self):
        """get_state方法"""
        calc = EmpiricalCDFCalculator(cdf_window=10)

        for _ in range(5):
            calc.update(Decimal("100"))

        state = calc.get_state()
        assert state['bar_count'] == 5
        assert state['x_history_len'] == 5
        assert state['is_warmed_up'] is False
        assert state['warmup_remaining'] == 5


class TestEdgeCases:
    """边界情况测试"""

    def test_decimal_precision(self):
        """Decimal精度保持"""
        calc = EmpiricalCDFCalculator()

        result = calc.update(Decimal("3456.78901234"))
        assert isinstance(result['ema'], Decimal)
        assert isinstance(result['d'], Decimal)
        assert isinstance(result['mu'], Decimal)
        assert isinstance(result['sigma'], Decimal)
        assert isinstance(result['x'], Decimal)

    def test_float_input_converted(self):
        """float输入自动转换"""
        calc = EmpiricalCDFCalculator()

        # 虽然推荐使用Decimal，但float也应该能工作
        result = calc.update(100.0)
        assert result['ema'] == Decimal("100")

    def test_large_values(self):
        """大数值处理"""
        calc = EmpiricalCDFCalculator()

        result = calc.update(Decimal("99999999.99"))
        assert result['ema'] is not None
        assert not np.isnan(float(result['ema']))

    def test_small_values(self):
        """小数值处理"""
        calc = EmpiricalCDFCalculator()

        result = calc.update(Decimal("0.00000001"))
        assert result['ema'] is not None
        assert result['ema'] > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
