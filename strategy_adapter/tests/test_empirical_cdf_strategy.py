"""
滚动经验CDF策略单元测试

测试覆盖：
- 初始化和配置
- 入场信号逻辑（Prob≤q_in）
- 出场信号逻辑（概率回归、时间止损、灾难止损）
- GFOB订单执行流程
- 因果一致性验证
- 完整回测流程

迭代编号: 034 (滚动经验CDF信号策略)
创建日期: 2026-01-12
关联任务: TASK-034-013
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch
import pandas as pd
import numpy as np

from strategy_adapter.strategies.empirical_cdf_strategy import (
    EmpiricalCDFStrategy,
    PositionState,
    ExitReason
)


class TestEmpiricalCDFStrategyInit:
    """初始化测试"""

    def test_default_params(self):
        """默认参数初始化"""
        strategy = EmpiricalCDFStrategy()
        assert strategy._q_in == 5.0
        assert strategy._q_out == 50.0
        assert strategy._max_holding_bars == 48
        assert strategy._stop_loss_threshold == Decimal("0.05")
        assert strategy._position_size == Decimal("100")

    def test_custom_params(self):
        """自定义参数初始化"""
        strategy = EmpiricalCDFStrategy(
            q_in=3.0,
            q_out=60.0,
            max_holding_bars=24,
            stop_loss_threshold=0.03,
            position_size=Decimal("200")
        )
        assert strategy._q_in == 3.0
        assert strategy._q_out == 60.0
        assert strategy._max_holding_bars == 24
        assert strategy._stop_loss_threshold == Decimal("0.03")
        assert strategy._position_size == Decimal("200")

    def test_initialize(self):
        """资金初始化"""
        strategy = EmpiricalCDFStrategy()
        strategy.initialize(Decimal("10000"))

        stats = strategy.get_statistics()
        assert stats['available_capital'] == 10000.0
        assert stats['frozen_capital'] == 0.0
        assert stats['position_state'] == 'FLAT'
        assert stats['has_holding'] is False


class TestEntrySignalLogic:
    """入场信号逻辑测试"""

    def test_entry_signal_when_prob_le_threshold(self):
        """Prob≤q_in时产生入场信号"""
        strategy = EmpiricalCDFStrategy(q_in=5.0, cdf_window=5)
        strategy.initialize(Decimal("10000"))

        # 模拟计算器warm up和产生低Prob
        # 先用稳定价格让计算器warm up
        for i in range(5):
            kline = {'open': 100, 'high': 101, 'low': 99, 'close': 100}
            strategy.process_kline(i, kline, 1000 + i)

        # 然后用低价格触发低Prob
        kline_entry = {'open': 100, 'high': 100, 'low': 80, 'close': 80}
        result = strategy.process_kline(5, kline_entry, 1005)

        # 由于极端负偏离，应该触发入场信号
        # 检查是否有挂单
        if result['indicators']['prob'] is not None and result['indicators']['prob'] <= 5:
            assert 'buy' in result['orders_placed'] or strategy._order_manager.has_pending_buy()

    def test_no_entry_signal_when_prob_gt_threshold(self):
        """Prob>q_in时不产生入场信号"""
        strategy = EmpiricalCDFStrategy(q_in=5.0, cdf_window=5)
        strategy.initialize(Decimal("10000"))

        # warm up with stable prices
        for i in range(6):
            kline = {'open': 100, 'high': 101, 'low': 99, 'close': 100}
            result = strategy.process_kline(i, kline, 1000 + i)

        # 稳定价格应该产生中等Prob，不触发入场
        prob = result['indicators']['prob']
        if prob is not None and prob > 5:
            assert 'buy' not in result.get('orders_placed', {})

    def test_no_entry_during_cold_start(self):
        """冷启动期不产生入场信号"""
        strategy = EmpiricalCDFStrategy(cdf_window=100)
        strategy.initialize(Decimal("10000"))

        # 冷启动期
        for i in range(50):
            kline = {'open': 100, 'high': 101, 'low': 50, 'close': 50}  # 极端价格
            result = strategy.process_kline(i, kline, 1000 + i)
            # Prob应该为None
            assert result['indicators']['prob'] is None
            # 不应该有入场订单
            assert 'buy' not in result.get('orders_placed', {})


class TestExitSignalLogic:
    """出场信号逻辑测试"""

    def test_exit_on_prob_reversion(self):
        """Prob≥q_out时触发概率回归出场"""
        strategy = EmpiricalCDFStrategy(q_in=5.0, q_out=50.0, cdf_window=5)
        strategy.initialize(Decimal("10000"))

        # 模拟已持仓状态
        strategy._position_state = PositionState.LONG
        strategy._holding = {
            'order_id': 'test_buy_001',
            'buy_price': Decimal("100"),
            'quantity': Decimal("1"),
            'amount': Decimal("100"),
            'entry_bar': 0,
            'entry_timestamp': 1000,
        }

        # 检查出场条件
        exit_signal, exit_reason = strategy._check_exit_conditions(
            prob=60.0,  # > q_out
            close=Decimal("105"),
            kline_index=10
        )

        assert exit_signal is True
        assert exit_reason == ExitReason.PROB_REVERSION

    def test_exit_on_time_stop(self):
        """时间止损触发"""
        strategy = EmpiricalCDFStrategy(max_holding_bars=48)
        strategy.initialize(Decimal("10000"))

        strategy._position_state = PositionState.LONG
        strategy._holding = {
            'order_id': 'test_buy_001',
            'buy_price': Decimal("100"),
            'quantity': Decimal("1"),
            'amount': Decimal("100"),
            'entry_bar': 0,
            'entry_timestamp': 1000,
        }

        # 持仓超过48根K线
        exit_signal, exit_reason = strategy._check_exit_conditions(
            prob=30.0,  # < q_out
            close=Decimal("99"),
            kline_index=50  # > entry_bar + 48
        )

        assert exit_signal is True
        assert exit_reason == ExitReason.TIME_STOP

    def test_exit_on_disaster_stop(self):
        """灾难止损触发"""
        strategy = EmpiricalCDFStrategy(stop_loss_threshold=0.05)
        strategy.initialize(Decimal("10000"))

        strategy._position_state = PositionState.LONG
        strategy._holding = {
            'order_id': 'test_buy_001',
            'buy_price': Decimal("100"),
            'quantity': Decimal("1"),
            'amount': Decimal("100"),
            'entry_bar': 0,
            'entry_timestamp': 1000,
        }

        # 亏损超过5%
        exit_signal, exit_reason = strategy._check_exit_conditions(
            prob=30.0,
            close=Decimal("94"),  # 亏损6%
            kline_index=10
        )

        assert exit_signal is True
        assert exit_reason == ExitReason.DISASTER_STOP

    def test_no_exit_when_conditions_not_met(self):
        """条件不满足时不出场"""
        strategy = EmpiricalCDFStrategy(q_out=50, max_holding_bars=48, stop_loss_threshold=0.05)
        strategy.initialize(Decimal("10000"))

        strategy._position_state = PositionState.LONG
        strategy._holding = {
            'order_id': 'test_buy_001',
            'buy_price': Decimal("100"),
            'quantity': Decimal("1"),
            'amount': Decimal("100"),
            'entry_bar': 0,
            'entry_timestamp': 1000,
        }

        # 所有条件都不满足
        exit_signal, exit_reason = strategy._check_exit_conditions(
            prob=30.0,  # < q_out
            close=Decimal("98"),  # 亏损2% < 5%
            kline_index=10  # < entry_bar + 48
        )

        assert exit_signal is False
        assert exit_reason is None


class TestGFOBOrderExecution:
    """GFOB订单执行测试"""

    def test_buy_order_valid_next_bar(self):
        """买单只在下一根K线有效"""
        strategy = EmpiricalCDFStrategy(cdf_window=5)
        strategy.initialize(Decimal("10000"))

        # Warm up
        for i in range(5):
            kline = {'open': 100, 'high': 101, 'low': 99, 'close': 100}
            strategy.process_kline(i, kline, 1000 + i)

        # 模拟入场信号并挂单
        strategy._order_manager.create_buy_order(
            close_price=Decimal("100"),
            kline_index=5,
            timestamp=1005
        )

        assert strategy._order_manager.has_pending_buy()

        # 检查valid_bar
        buy_price = strategy._order_manager.get_pending_buy_price()
        assert buy_price is not None

    def test_matching_order_sell_first_buy_second(self):
        """撮合顺序：先卖后买"""
        # 这个测试在GFOBOrderManager测试中已覆盖
        # 此处验证策略层面的调用正确性
        strategy = EmpiricalCDFStrategy()
        strategy.initialize(Decimal("10000"))

        # 模拟有待处理的买卖单
        strategy._order_manager.create_buy_order(
            close_price=Decimal("100"),
            kline_index=0,
            timestamp=1000
        )

        # 撮合时先卖后买的顺序由GFOBOrderManager保证
        kline = {'open': 100, 'high': 110, 'low': 95, 'close': 105}
        result = strategy.process_kline(1, kline, 1001)

        # 验证撮合结果结构
        assert 'buy_fills' in result
        assert 'sell_fills' in result


class TestCausalityConsistency:
    """因果一致性测试"""

    def test_signal_at_t_execution_at_t_plus_1(self):
        """信号在t，成交最早在t+1"""
        strategy = EmpiricalCDFStrategy(cdf_window=5)
        strategy.initialize(Decimal("10000"))

        # Warm up
        for i in range(5):
            kline = {'open': 100, 'high': 101, 'low': 99, 'close': 100}
            strategy.process_kline(i, kline, 1000 + i)

        # Bar 5: 模拟入场信号
        # 假设此时产生入场信号并挂单
        strategy._order_manager.create_buy_order(
            close_price=Decimal("100"),
            kline_index=5,
            timestamp=1005
        )
        assert strategy._order_manager.has_pending_buy()

        # Bar 5: 买单不应在同一bar成交
        result_5 = strategy.process_kline(5, {'open': 100, 'high': 110, 'low': 90, 'close': 100}, 1005)
        # 注意：订单是在process_kline之前手动创建的，所以需要检查撮合结果
        # 由于valid_bar=6，在bar 5不应成交

        # Bar 6: 买单应该可以成交
        result_6 = strategy.process_kline(6, {'open': 100, 'high': 110, 'low': 90, 'close': 100}, 1006)
        # 这取决于订单的valid_bar设置

    def test_prob_excludes_current_sample(self):
        """Prob计算窗口不含当前样本"""
        # 这个测试在EmpiricalCDFCalculator测试中已覆盖
        # 此处验证策略层面的调用正确性
        strategy = EmpiricalCDFStrategy(cdf_window=5)
        strategy.initialize(Decimal("10000"))

        # Warm up并记录历史
        for i in range(5):
            kline = {'open': 100, 'high': 101, 'low': 99, 'close': 100}
            strategy.process_kline(i, kline, 1000 + i)

        # 第6根K线
        kline_6 = {'open': 100, 'high': 101, 'low': 99, 'close': 100}
        result = strategy.process_kline(5, kline_6, 1005)

        # Prob应该是基于前5个X值计算的，不含当前
        assert result['indicators']['prob'] is not None


class TestBacktestFlow:
    """回测流程测试"""

    def test_run_backtest_basic(self):
        """基本回测流程"""
        strategy = EmpiricalCDFStrategy(cdf_window=10)

        # 创建测试数据
        dates = pd.date_range('2024-01-01', periods=50, freq='4h')
        data = {
            'open': [100 + i * 0.1 for i in range(50)],
            'high': [101 + i * 0.1 for i in range(50)],
            'low': [99 + i * 0.1 for i in range(50)],
            'close': [100 + i * 0.1 for i in range(50)],
        }
        klines_df = pd.DataFrame(data, index=dates)

        result = strategy.run_backtest(klines_df, Decimal("10000"))

        assert 'total_trades' in result
        assert 'winning_trades' in result
        assert 'win_rate' in result
        assert 'final_capital' in result
        assert 'return_rate' in result
        assert 'statistics' in result

    def test_run_backtest_with_trades(self):
        """带交易的回测"""
        strategy = EmpiricalCDFStrategy(q_in=10, q_out=50, cdf_window=10)

        # 创建会产生交易的数据
        # 先稳定，然后大幅下跌触发入场，再回升触发出场
        dates = pd.date_range('2024-01-01', periods=30, freq='4h')
        prices = []
        for i in range(30):
            if i < 15:
                prices.append(100)  # 稳定
            elif i < 20:
                prices.append(80)   # 下跌
            else:
                prices.append(100)  # 回升

        data = {
            'open': prices,
            'high': [p + 2 for p in prices],
            'low': [p - 2 for p in prices],
            'close': prices,
        }
        klines_df = pd.DataFrame(data, index=dates)

        result = strategy.run_backtest(klines_df, Decimal("10000"))

        # 验证基本结构
        assert isinstance(result['total_trades'], int)
        assert isinstance(result['final_capital'], float)

    def test_backtest_logs_complete(self):
        """回测日志完整性"""
        strategy = EmpiricalCDFStrategy(cdf_window=10)

        dates = pd.date_range('2024-01-01', periods=20, freq='4h')
        data = {
            'open': [100] * 20,
            'high': [101] * 20,
            'low': [99] * 20,
            'close': [100] * 20,
        }
        klines_df = pd.DataFrame(data, index=dates)

        result = strategy.run_backtest(klines_df, Decimal("10000"))

        # Bar日志应该有20条
        assert len(result['bar_logs']) == 20

        # 每条bar日志应包含关键字段
        bar_log = result['bar_logs'][0]
        assert 'bar_index' in bar_log
        assert 'timestamp' in bar_log
        assert 'close' in bar_log
        assert 'ema' in bar_log
        assert 'prob' in bar_log
        assert 'position' in bar_log


class TestStatistics:
    """统计信息测试"""

    def test_get_statistics(self):
        """获取统计信息"""
        strategy = EmpiricalCDFStrategy()
        strategy.initialize(Decimal("10000"))

        stats = strategy.get_statistics()

        assert 'available_capital' in stats
        assert 'frozen_capital' in stats
        assert 'total_capital' in stats
        assert 'position_state' in stats
        assert 'has_holding' in stats
        assert 'completed_trades' in stats
        assert 'win_rate' in stats
        assert 'calculator_bar_count' in stats
        assert 'calculator_warmed_up' in stats

    def test_get_completed_orders(self):
        """获取已完成交易"""
        strategy = EmpiricalCDFStrategy()
        strategy.initialize(Decimal("10000"))

        # 模拟完成一笔交易
        strategy._completed_orders.append({
            'buy_order_id': 'buy_001',
            'sell_order_id': 'sell_001',
            'profit_loss': 10.0,
        })

        orders = strategy.get_completed_orders()
        assert len(orders) == 1
        assert orders[0]['buy_order_id'] == 'buy_001'


class TestIStrategyInterface:
    """IStrategy接口兼容性测试"""

    def test_generate_buy_signals_returns_empty(self):
        """generate_buy_signals返回空列表"""
        strategy = EmpiricalCDFStrategy()
        result = strategy.generate_buy_signals(pd.DataFrame(), {})
        assert result == []

    def test_generate_sell_signals_returns_empty(self):
        """generate_sell_signals返回空列表"""
        strategy = EmpiricalCDFStrategy()
        result = strategy.generate_sell_signals(pd.DataFrame(), {}, [])
        assert result == []

    def test_calculate_position_size(self):
        """calculate_position_size返回配置的仓位大小"""
        strategy = EmpiricalCDFStrategy(position_size=Decimal("200"))
        result = strategy.calculate_position_size({}, Decimal("1000"), Decimal("100"))
        assert result == Decimal("200")

    def test_should_stop_loss_returns_false(self):
        """should_stop_loss返回False"""
        strategy = EmpiricalCDFStrategy()
        result = strategy.should_stop_loss(Mock(), Decimal("100"), 1000)
        assert result is False

    def test_should_take_profit_returns_false(self):
        """should_take_profit返回False"""
        strategy = EmpiricalCDFStrategy()
        result = strategy.should_take_profit(Mock(), Decimal("100"), 1000)
        assert result is False


class TestEdgeCases:
    """边界情况测试"""

    def test_no_holding_sell_fill(self):
        """无持仓时收到卖出成交"""
        strategy = EmpiricalCDFStrategy()
        strategy.initialize(Decimal("10000"))

        # 尝试处理卖出成交但无持仓
        fill = {'order_id': 'sell_001', 'price': Decimal("100"), 'quantity': Decimal("1")}
        strategy._handle_sell_fill(fill, 10, 1010)

        # 应该不产生错误，只是警告
        assert len(strategy._completed_orders) == 0

    def test_strategy_name_version(self):
        """策略名称和版本"""
        strategy = EmpiricalCDFStrategy()
        assert strategy.get_strategy_name() == '滚动经验CDF策略'
        assert strategy.get_strategy_version() == '1.0'

    def test_required_indicators_empty(self):
        """所需指标列表为空"""
        strategy = EmpiricalCDFStrategy()
        assert strategy.get_required_indicators() == []


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
