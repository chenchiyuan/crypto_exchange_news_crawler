"""
测试文件：策略20（多交易对共享资金池策略）单元测试

Purpose:
    验证策略20各组件的正确性：
    - GlobalCapitalManager: 全局资金池管理器
    - GlobalPositionTracker: 全局持仓跟踪器
    - SymbolState: 交易对状态管理
    - entry_exit_logic: 买卖逻辑工具函数
    - Strategy20MultiSymbol: 策略整体逻辑

关联任务: TASK-045-012
关联需求: 迭代045功能点清单
关联架构: architecture.md

测试策略:
    - 单元测试每个组件
    - 覆盖边界情况和异常场景
    - 验证资金冻结和释放逻辑
    - 验证全局持仓限制
"""

import unittest
from decimal import Decimal
from datetime import datetime

import pandas as pd
import numpy as np

from strategy_adapter.core.global_capital_manager import GlobalCapitalManager
from strategy_adapter.core.global_position_tracker import GlobalPositionTracker
from strategy_adapter.models.symbol_state import SymbolState
from strategy_adapter.models import PendingOrder, PendingOrderStatus, PendingOrderSide
from strategy_adapter.utils.entry_exit_logic import (
    calculate_base_price,
    calculate_order_price,
    calculate_sell_price,
    should_skip_entry,
    is_buy_order_filled,
    is_sell_order_filled,
    calculate_profit,
)


class TestGlobalCapitalManager(unittest.TestCase):
    """GlobalCapitalManager单元测试套件"""

    def setUp(self):
        """测试前准备"""
        self.manager = GlobalCapitalManager(initial_capital=Decimal('10000'))

    def test_initial_state(self):
        """测试初始状态"""
        self.assertEqual(self.manager.initial_capital, Decimal('10000'))
        self.assertEqual(self.manager.available_cash, Decimal('10000'))
        self.assertEqual(self.manager.frozen_cash, Decimal('0'))
        self.assertEqual(self.manager.get_equity(), Decimal('10000'))

    def test_freeze_success(self):
        """测试成功冻结资金"""
        result = self.manager.freeze(
            amount=Decimal('1000'),
            symbol='ETHUSDT',
            order_id='order_001',
            timestamp=1000
        )
        self.assertTrue(result)
        self.assertEqual(self.manager.available_cash, Decimal('9000'))
        self.assertEqual(self.manager.frozen_cash, Decimal('1000'))

    def test_freeze_insufficient_funds(self):
        """测试资金不足时冻结失败"""
        result = self.manager.freeze(
            amount=Decimal('15000'),  # 超过可用资金
            symbol='ETHUSDT',
            order_id='order_001',
            timestamp=1000
        )
        self.assertFalse(result)
        self.assertEqual(self.manager.available_cash, Decimal('10000'))
        self.assertEqual(self.manager.frozen_cash, Decimal('0'))

    def test_unfreeze(self):
        """测试解冻资金"""
        # 先冻结
        self.manager.freeze(
            amount=Decimal('1000'),
            symbol='ETHUSDT',
            order_id='order_001',
            timestamp=1000
        )

        # 再解冻
        self.manager.unfreeze(
            amount=Decimal('1000'),
            symbol='ETHUSDT',
            order_id='order_001',
            timestamp=2000
        )
        # unfreeze 没有返回值，只验证状态
        self.assertEqual(self.manager.available_cash, Decimal('10000'))
        self.assertEqual(self.manager.frozen_cash, Decimal('0'))

    def test_settle(self):
        """测试结算（冻结资金转为持仓）"""
        # 先冻结
        self.manager.freeze(
            amount=Decimal('1000'),
            symbol='ETHUSDT',
            order_id='order_001',
            timestamp=1000
        )

        # 结算
        self.manager.settle(
            frozen_amount=Decimal('1000'),
            symbol='ETHUSDT',
            order_id='order_001',
            timestamp=2000
        )
        # settle 没有返回值，只验证状态
        self.assertEqual(self.manager.available_cash, Decimal('9000'))
        self.assertEqual(self.manager.frozen_cash, Decimal('0'))

    def test_add_profit(self):
        """测试添加利润"""
        self.manager.add_profit(
            profit=Decimal('500'),
            symbol='ETHUSDT',
            order_id='order_001',
            timestamp=1000
        )
        self.assertEqual(self.manager.available_cash, Decimal('10500'))
        self.assertEqual(self.manager.get_equity(), Decimal('10500'))

    def test_add_loss(self):
        """测试添加亏损"""
        self.manager.add_profit(
            profit=Decimal('-200'),
            symbol='ETHUSDT',
            order_id='order_001',
            timestamp=1000
        )
        self.assertEqual(self.manager.available_cash, Decimal('9800'))
        self.assertEqual(self.manager.get_equity(), Decimal('9800'))


class TestGlobalPositionTracker(unittest.TestCase):
    """GlobalPositionTracker单元测试套件"""

    def setUp(self):
        """测试前准备"""
        self.tracker = GlobalPositionTracker(max_positions=10)

    def test_initial_state(self):
        """测试初始状态"""
        self.assertEqual(self.tracker.max_positions, 10)
        self.assertEqual(self.tracker.total_holdings, 0)
        self.assertTrue(self.tracker.can_open_position())

    def test_add_holding(self):
        """测试添加持仓"""
        self.tracker.add_holding('ETHUSDT')
        self.assertEqual(self.tracker.total_holdings, 1)
        self.assertEqual(self.tracker.get_holdings_count('ETHUSDT'), 1)

        self.tracker.add_holding('ETHUSDT')
        self.assertEqual(self.tracker.total_holdings, 2)
        self.assertEqual(self.tracker.get_holdings_count('ETHUSDT'), 2)

    def test_remove_holding(self):
        """测试移除持仓"""
        self.tracker.add_holding('ETHUSDT')
        self.tracker.add_holding('ETHUSDT')

        # remove_holding 没有返回值
        self.tracker.remove_holding('ETHUSDT')
        self.assertEqual(self.tracker.total_holdings, 1)

    def test_remove_holding_empty(self):
        """测试移除不存在的持仓"""
        # remove_holding 对于不存在的 symbol 不做任何事
        self.tracker.remove_holding('ETHUSDT')
        self.assertEqual(self.tracker.total_holdings, 0)

    def test_can_open_position(self):
        """测试持仓限制"""
        # 添加满持仓
        for i in range(10):
            self.tracker.add_holding('ETHUSDT')

        self.assertFalse(self.tracker.can_open_position())

        # 移除一个后可以开仓
        self.tracker.remove_holding('ETHUSDT')
        self.assertTrue(self.tracker.can_open_position())

    def test_calculate_position_size(self):
        """测试仓位大小计算"""
        available_cash = Decimal('10000')

        # 初始时：10000 / 10 = 1000
        size = self.tracker.calculate_position_size(available_cash)
        self.assertEqual(size, Decimal('1000'))

        # 添加5个持仓后：10000 / 5 = 2000
        for _ in range(5):
            self.tracker.add_holding('ETHUSDT')
        size = self.tracker.calculate_position_size(available_cash)
        self.assertEqual(size, Decimal('2000'))

    def test_calculate_position_size_full(self):
        """测试满仓时的仓位计算"""
        available_cash = Decimal('10000')

        # 满仓时返回0
        for _ in range(10):
            self.tracker.add_holding('ETHUSDT')
        size = self.tracker.calculate_position_size(available_cash)
        self.assertEqual(size, Decimal('0'))


class TestSymbolState(unittest.TestCase):
    """SymbolState单元测试套件"""

    def test_initial_state(self):
        """测试初始状态"""
        state = SymbolState(symbol='ETHUSDT')
        self.assertEqual(state.symbol, 'ETHUSDT')
        self.assertIsNone(state.pending_buy_order)
        self.assertEqual(len(state.pending_sell_orders), 0)
        self.assertEqual(len(state.holdings), 0)
        self.assertEqual(state.total_orders, 0)
        self.assertEqual(state.winning_orders, 0)
        self.assertEqual(state.total_profit_loss, Decimal('0'))

    def test_has_pending_buy_order(self):
        """测试是否有挂单检测"""
        state = SymbolState(symbol='ETHUSDT')
        self.assertEqual(state.get_pending_buy_count(), 0)

        state.pending_buy_order = PendingOrder(
            order_id='order_001',
            price=Decimal('3000'),
            amount=Decimal('300'),
            quantity=Decimal('0.1'),
            status=PendingOrderStatus.PENDING,
            side=PendingOrderSide.BUY,
            frozen_capital=Decimal('300'),
            kline_index=100,
            created_at=1704067200000
        )
        self.assertEqual(state.get_pending_buy_count(), 1)

    def test_holdings_count(self):
        """测试持仓数量统计"""
        state = SymbolState(symbol='ETHUSDT')
        self.assertEqual(state.get_holding_count(), 0)

        state.holdings['h1'] = {'quantity': Decimal('0.1')}
        state.holdings['h2'] = {'quantity': Decimal('0.2')}
        self.assertEqual(state.get_holding_count(), 2)


class TestEntryExitLogic(unittest.TestCase):
    """买卖逻辑工具函数测试套件"""

    def test_calculate_base_price_p5_less_than_close(self):
        """测试P5低于收盘价时的基准价格"""
        p5 = Decimal('100')
        close = Decimal('105')
        inertia_mid = Decimal('102')

        base = calculate_base_price(p5, close, inertia_mid)
        # base_price = min(P5, close, (P5+mid)/2)
        # min(100, 105, (100+102)/2) = min(100, 105, 101) = 100
        self.assertEqual(base, Decimal('100'))

    def test_calculate_base_price_p5_greater_than_close(self):
        """测试P5高于收盘价时的基准价格"""
        p5 = Decimal('105')
        close = Decimal('100')
        inertia_mid = Decimal('102')

        base = calculate_base_price(p5, close, inertia_mid)
        # base_price = min(P5, close, (P5+mid)/2)
        # min(105, 100, (105+102)/2) = min(105, 100, 103.5) = 100
        self.assertEqual(base, Decimal('100'))

    def test_calculate_base_price_mid_p5_lowest(self):
        """测试(P5+mid)/2最低时的基准价格"""
        p5 = Decimal('100')
        close = Decimal('105')
        inertia_mid = Decimal('90')

        base = calculate_base_price(p5, close, inertia_mid)
        # base_price = min(P5, close, (P5+mid)/2)
        # min(100, 105, (100+90)/2) = min(100, 105, 95) = 95
        self.assertEqual(base, Decimal('95'))

    def test_calculate_order_price(self):
        """测试订单价格计算"""
        base_price = Decimal('100')
        discount = Decimal('0.001')  # 千一折扣

        order_price = calculate_order_price(base_price, discount)
        expected = Decimal('100') * (1 - Decimal('0.001'))
        self.assertEqual(order_price, expected)

    def test_calculate_sell_price_bull_strong(self):
        """测试bull_strong阶段的卖出价格"""
        price, reason = calculate_sell_price(
            cycle_phase='bull_strong',
            ema25=Decimal('100'),
            p95=Decimal('110')
        )
        # bull_strong: P95
        self.assertEqual(price, Decimal('110'))
        self.assertIn('P95', reason)

    def test_calculate_sell_price_bull_warning(self):
        """测试bull_warning阶段的卖出价格"""
        price, reason = calculate_sell_price(
            cycle_phase='bull_warning',
            ema25=Decimal('100'),
            p95=Decimal('110')
        )
        # bull_warning: P95 (在实现中与其他牛市阶段一样)
        self.assertEqual(price, Decimal('110'))
        self.assertIn('P95', reason)

    def test_calculate_sell_price_bear_warning(self):
        """测试bear_warning阶段的卖出价格"""
        price, reason = calculate_sell_price(
            cycle_phase='bear_warning',
            ema25=Decimal('100'),
            p95=Decimal('110')
        )
        # bear_warning: EMA25
        self.assertEqual(price, Decimal('100'))
        self.assertIn('EMA25', reason)

    def test_calculate_sell_price_consolidation(self):
        """测试consolidation阶段的卖出价格"""
        price, reason = calculate_sell_price(
            cycle_phase='consolidation',
            ema25=Decimal('100'),
            p95=Decimal('110')
        )
        # consolidation: (P95 + EMA25) / 2
        expected = (Decimal('110') + Decimal('100')) / 2
        self.assertEqual(price, expected)

    def test_should_skip_entry_bear_warning(self):
        """测试bear_warning阶段是否跳过入场"""
        self.assertTrue(should_skip_entry('bear_warning'))

    def test_should_skip_entry_other_phases(self):
        """测试其他阶段不跳过入场"""
        self.assertFalse(should_skip_entry('bull_confirmed'))
        self.assertFalse(should_skip_entry('bull_warning'))
        self.assertFalse(should_skip_entry('bear_confirmed'))
        self.assertFalse(should_skip_entry('neutral'))

    def test_is_buy_order_filled(self):
        """测试买单成交判断"""
        # 最低价触及订单价格
        self.assertTrue(is_buy_order_filled(
            low=Decimal('99'),
            order_price=Decimal('100')
        ))

        # 最低价未触及订单价格
        self.assertFalse(is_buy_order_filled(
            low=Decimal('101'),
            order_price=Decimal('100')
        ))

    def test_is_sell_order_filled(self):
        """测试卖单成交判断"""
        # 最高价触及订单价格
        self.assertTrue(is_sell_order_filled(
            high=Decimal('101'),
            order_price=Decimal('100')
        ))

        # 最高价未触及订单价格
        self.assertFalse(is_sell_order_filled(
            high=Decimal('99'),
            order_price=Decimal('100')
        ))

    def test_calculate_profit(self):
        """测试利润计算"""
        profit, profit_pct = calculate_profit(
            sell_price=Decimal('110'),
            buy_price=Decimal('100'),
            quantity=Decimal('1')
        )
        self.assertEqual(profit, Decimal('10'))
        self.assertEqual(profit_pct, Decimal('10'))  # 10%


class TestStrategy20MultiSymbol(unittest.TestCase):
    """Strategy20MultiSymbol集成测试套件"""

    def setUp(self):
        """测试前准备：创建模拟K线数据"""
        from strategy_adapter.strategies import Strategy20MultiSymbol
        self.strategy_class = Strategy20MultiSymbol

    def test_strategy_initialization(self):
        """测试策略初始化"""
        strategy = self.strategy_class(
            symbols=['ETHUSDT', 'BTCUSDT'],
            discount=Decimal('0.001'),
            max_positions=10,
            interval_hours=4.0
        )
        self.assertEqual(strategy.symbols, ['ETHUSDT', 'BTCUSDT'])
        self.assertEqual(strategy.discount, Decimal('0.001'))
        self.assertEqual(strategy.max_positions, 10)

    def test_strategy_id(self):
        """测试策略ID"""
        self.assertEqual(self.strategy_class.STRATEGY_ID, 'strategy_20')

    def test_default_symbols(self):
        """测试默认交易对"""
        self.assertIn('ETHUSDT', self.strategy_class.DEFAULT_SYMBOLS)
        self.assertIn('BTCUSDT', self.strategy_class.DEFAULT_SYMBOLS)


if __name__ == '__main__':
    unittest.main()
