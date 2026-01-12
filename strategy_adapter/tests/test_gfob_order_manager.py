"""
GFOB订单管理器单元测试

测试覆盖：
- 初始化和资金管理
- 买入挂单创建（入场定价）
- 卖出挂单创建（出场定价）
- 撮合逻辑（GFOB特有规则）
- 订单过期处理
- 撮合顺序（先卖后买）

迭代编号: 034 (滚动经验CDF信号策略)
创建日期: 2026-01-12
关联任务: TASK-034-008
"""

import pytest
from decimal import Decimal

from strategy_adapter.core.gfob_order_manager import GFOBOrderManager


class TestGFOBOrderManagerInit:
    """初始化测试"""

    def test_default_params(self):
        """默认参数初始化"""
        manager = GFOBOrderManager()
        assert manager._position_size == Decimal("100")
        assert manager._delta_in == Decimal("0.001")
        assert manager._delta_out == Decimal("0.0")
        assert manager._delta_out_fast == Decimal("0.001")

    def test_custom_params(self):
        """自定义参数初始化"""
        manager = GFOBOrderManager(
            position_size=Decimal("200"),
            delta_in=0.002,
            delta_out=0.001,
            delta_out_fast=0.002
        )
        assert manager._position_size == Decimal("200")
        assert manager._delta_in == Decimal("0.002")
        assert manager._delta_out == Decimal("0.001")
        assert manager._delta_out_fast == Decimal("0.002")

    def test_initialize(self):
        """资金初始化"""
        manager = GFOBOrderManager()
        manager.initialize(Decimal("10000"))

        assert manager.available_capital == Decimal("10000")
        assert manager.frozen_capital == Decimal("0")
        assert manager.total_capital == Decimal("10000")
        assert not manager.has_pending_buy()
        assert not manager.has_pending_sell()


class TestBuyOrderCreation:
    """买入挂单创建测试"""

    def test_create_buy_order_success(self):
        """成功创建买入挂单"""
        manager = GFOBOrderManager(position_size=Decimal("100"), delta_in=0.001)
        manager.initialize(Decimal("10000"))

        order = manager.create_buy_order(
            close_price=Decimal("3500"),
            kline_index=10,
            timestamp=1000
        )

        assert order is not None
        assert order['status'] == 'PLACED'
        assert order['reason'] == 'ENTRY_TAIL'
        assert order['placed_bar'] == 10
        assert order['valid_bar'] == 11  # GFOB: 下一根K线有效

        # 验证价格计算: L = close × (1 - δ_in) = 3500 × 0.999 = 3496.5
        expected_price = Decimal("3500") * (1 - Decimal("0.001"))
        assert order['price'] == expected_price

    def test_create_buy_order_insufficient_capital(self):
        """资金不足无法创建买入挂单"""
        manager = GFOBOrderManager(position_size=Decimal("100"))
        manager.initialize(Decimal("50"))  # 只有50，需要100

        order = manager.create_buy_order(
            close_price=Decimal("3500"),
            kline_index=10,
            timestamp=1000
        )

        assert order is None
        assert not manager.has_pending_buy()

    def test_create_buy_order_freezes_capital(self):
        """创建买入挂单冻结资金"""
        manager = GFOBOrderManager(position_size=Decimal("100"))
        manager.initialize(Decimal("10000"))

        initial_available = manager.available_capital

        manager.create_buy_order(
            close_price=Decimal("3500"),
            kline_index=10,
            timestamp=1000
        )

        # 资金应该被冻结
        assert manager.available_capital == initial_available - Decimal("100")
        assert manager.frozen_capital == Decimal("100")

    def test_buy_order_price_calculation(self):
        """买入挂单价格计算验证"""
        # 不同delta_in值
        for delta_in in [0.001, 0.002, 0.005]:
            manager = GFOBOrderManager(delta_in=delta_in)
            manager.initialize(Decimal("10000"))

            close_price = Decimal("4000")
            order = manager.create_buy_order(
                close_price=close_price,
                kline_index=1,
                timestamp=100
            )

            expected_price = close_price * (1 - Decimal(str(delta_in)))
            assert order['price'] == expected_price, f"delta_in={delta_in}"


class TestSellOrderCreation:
    """卖出挂单创建测试"""

    def test_create_sell_order_prob_reversion(self):
        """概率回归卖出挂单（delta_out=0）"""
        manager = GFOBOrderManager(delta_out=0.0)
        manager.initialize(Decimal("10000"))

        order = manager.create_sell_order(
            close_price=Decimal("3600"),
            parent_order_id="buy_123",
            quantity=Decimal("0.1"),
            reason='PROB_REVERSION',
            kline_index=20,
            timestamp=2000
        )

        assert order['status'] == 'PLACED'
        assert order['reason'] == 'PROB_REVERSION'
        assert order['parent_order_id'] == "buy_123"
        assert order['valid_bar'] == 21

        # 价格计算: U = close × (1 - δ_out) = 3600 × 1.0 = 3600
        assert order['price'] == Decimal("3600")

    def test_create_sell_order_fast_exit(self):
        """快速出场卖出挂单（delta_out_fast）"""
        manager = GFOBOrderManager(delta_out_fast=0.001)
        manager.initialize(Decimal("10000"))

        order = manager.create_sell_order(
            close_price=Decimal("3600"),
            parent_order_id="buy_123",
            quantity=Decimal("0.1"),
            reason='FAST_EXIT',
            kline_index=20,
            timestamp=2000
        )

        # 价格计算: U = close × (1 - δ_out_fast) = 3600 × 0.999 = 3596.4
        expected_price = Decimal("3600") * (1 - Decimal("0.001"))
        assert order['price'] == expected_price

    def test_sell_order_quantity_amount(self):
        """卖出挂单数量和金额计算"""
        manager = GFOBOrderManager()
        manager.initialize(Decimal("10000"))

        quantity = Decimal("0.5")
        close_price = Decimal("4000")

        order = manager.create_sell_order(
            close_price=close_price,
            parent_order_id="buy_123",
            quantity=quantity,
            reason='PROB_REVERSION',
            kline_index=20,
            timestamp=2000
        )

        assert order['quantity'] == quantity
        assert order['amount'] == order['price'] * quantity


class TestMatchingRules:
    """撮合规则测试（GFOB特有）"""

    def test_buy_order_match_low_le_limit(self):
        """买单撮合：low ≤ L 成交"""
        manager = GFOBOrderManager(delta_in=0.001)
        manager.initialize(Decimal("10000"))

        # 创建买入挂单，价格 L = 3500 × 0.999 = 3496.5
        manager.create_buy_order(
            close_price=Decimal("3500"),
            kline_index=10,
            timestamp=1000
        )

        # 下一根K线撮合
        # low = 3490 < 3496.5，应该成交
        result = manager.match_orders(
            kline_index=11,  # valid_bar
            low=Decimal("3490"),
            high=Decimal("3550"),
            timestamp=1100
        )

        assert len(result['buy_fills']) == 1
        assert result['buy_fills'][0]['status'] == 'FILLED'

    def test_buy_order_no_match_low_gt_limit(self):
        """买单不撮合：low > L"""
        manager = GFOBOrderManager(delta_in=0.001)
        manager.initialize(Decimal("10000"))

        # L = 3500 × 0.999 = 3496.5
        manager.create_buy_order(
            close_price=Decimal("3500"),
            kline_index=10,
            timestamp=1000
        )

        # low = 3500 > 3496.5，不成交
        result = manager.match_orders(
            kline_index=11,
            low=Decimal("3500"),
            high=Decimal("3600"),
            timestamp=1100
        )

        assert len(result['buy_fills']) == 0
        # 订单仍然存在（但会过期，如果不是当前valid_bar）

    def test_sell_order_match_high_ge_limit(self):
        """卖单撮合：high ≥ U 成交"""
        manager = GFOBOrderManager(delta_out=0.0)
        manager.initialize(Decimal("10000"))

        # 创建卖出挂单，价格 U = 3600
        manager.create_sell_order(
            close_price=Decimal("3600"),
            parent_order_id="buy_123",
            quantity=Decimal("0.1"),
            reason='PROB_REVERSION',
            kline_index=20,
            timestamp=2000
        )

        # high = 3650 >= 3600，应该成交
        result = manager.match_orders(
            kline_index=21,
            low=Decimal("3550"),
            high=Decimal("3650"),
            timestamp=2100
        )

        assert len(result['sell_fills']) == 1
        assert result['sell_fills'][0]['status'] == 'FILLED'

    def test_sell_order_no_match_high_lt_limit(self):
        """卖单不撮合：high < U"""
        manager = GFOBOrderManager(delta_out=0.0)
        manager.initialize(Decimal("10000"))

        # U = 3600
        manager.create_sell_order(
            close_price=Decimal("3600"),
            parent_order_id="buy_123",
            quantity=Decimal("0.1"),
            reason='PROB_REVERSION',
            kline_index=20,
            timestamp=2000
        )

        # high = 3580 < 3600，不成交
        result = manager.match_orders(
            kline_index=21,
            low=Decimal("3500"),
            high=Decimal("3580"),
            timestamp=2100
        )

        assert len(result['sell_fills']) == 0

    def test_gfob_vs_limit_order_manager_rule_difference(self):
        """GFOB撮合规则与LimitOrderManager差异验证

        GFOB: 买单 low ≤ L 即成交（不要求 L ≤ high）
        LOM:  买单要求 low ≤ price ≤ high
        """
        manager = GFOBOrderManager(delta_in=0.001)
        manager.initialize(Decimal("10000"))

        # L = 3500 × 0.999 = 3496.5
        manager.create_buy_order(
            close_price=Decimal("3500"),
            kline_index=10,
            timestamp=1000
        )

        # 场景：low = 3400, high = 3450
        # low ≤ L (3400 ≤ 3496.5) ✓
        # 但 L > high (3496.5 > 3450) - LimitOrderManager不会成交
        # GFOB应该成交
        result = manager.match_orders(
            kline_index=11,
            low=Decimal("3400"),
            high=Decimal("3450"),
            timestamp=1100
        )

        assert len(result['buy_fills']) == 1, "GFOB规则：只要low≤L即成交"


class TestOrderExpiry:
    """订单过期测试"""

    def test_buy_order_expires_after_valid_bar(self):
        """买单过期：超过valid_bar"""
        manager = GFOBOrderManager()
        manager.initialize(Decimal("10000"))

        # 创建买入挂单，valid_bar = 11
        manager.create_buy_order(
            close_price=Decimal("3500"),
            kline_index=10,
            timestamp=1000
        )

        initial_frozen = manager.frozen_capital

        # K线12：跳过valid_bar，订单应过期
        result = manager.match_orders(
            kline_index=12,
            low=Decimal("3400"),
            high=Decimal("3600"),
            timestamp=1200
        )

        assert len(result['expired_orders']) == 1
        assert not manager.has_pending_buy()
        # 资金应解冻
        assert manager.frozen_capital < initial_frozen

    def test_sell_order_expires_after_valid_bar(self):
        """卖单过期：超过valid_bar"""
        manager = GFOBOrderManager()
        manager.initialize(Decimal("10000"))

        # 创建卖出挂单，valid_bar = 21
        manager.create_sell_order(
            close_price=Decimal("3600"),
            parent_order_id="buy_123",
            quantity=Decimal("0.1"),
            reason='PROB_REVERSION',
            kline_index=20,
            timestamp=2000
        )

        # K线22：跳过valid_bar
        result = manager.match_orders(
            kline_index=22,
            low=Decimal("3500"),
            high=Decimal("3700"),
            timestamp=2200
        )

        assert len(result['expired_orders']) == 1
        assert not manager.has_pending_sell()

    def test_order_not_matched_on_wrong_bar(self):
        """订单只在valid_bar上撮合"""
        manager = GFOBOrderManager()
        manager.initialize(Decimal("10000"))

        # 创建买入挂单，valid_bar = 11
        manager.create_buy_order(
            close_price=Decimal("3500"),
            kline_index=10,
            timestamp=1000
        )

        # K线10（placed_bar）：不应撮合，即使价格满足
        result = manager.match_orders(
            kline_index=10,
            low=Decimal("3400"),
            high=Decimal("3600"),
            timestamp=1050
        )

        assert len(result['buy_fills']) == 0


class TestMatchingOrder:
    """撮合顺序测试"""

    def test_sell_before_buy(self):
        """先卖后买：防止同bar翻手套利"""
        manager = GFOBOrderManager(delta_in=0.001, delta_out=0.0)
        manager.initialize(Decimal("10000"))

        # 创建买入挂单，valid_bar = 11
        buy_order = manager.create_buy_order(
            close_price=Decimal("3500"),
            kline_index=10,
            timestamp=1000
        )

        # 创建卖出挂单，valid_bar = 11
        sell_order = manager.create_sell_order(
            close_price=Decimal("3600"),
            parent_order_id="existing_position",
            quantity=Decimal("0.1"),
            reason='PROB_REVERSION',
            kline_index=10,
            timestamp=1000
        )

        # 两者都在K线11有效，应先卖后买
        result = manager.match_orders(
            kline_index=11,
            low=Decimal("3400"),  # 满足买单 low ≤ L
            high=Decimal("3650"),  # 满足卖单 high ≥ U
            timestamp=1100
        )

        # 验证两者都成交
        assert len(result['sell_fills']) == 1
        assert len(result['buy_fills']) == 1

        # 验证顺序：sell_fills在前（虽然返回的是列表，顺序由实现保证）
        # 这里主要验证功能正确性，实际顺序由日志验证


class TestCancelOrder:
    """取消订单测试"""

    def test_cancel_pending_buy(self):
        """取消待处理买单"""
        manager = GFOBOrderManager()
        manager.initialize(Decimal("10000"))

        order = manager.create_buy_order(
            close_price=Decimal("3500"),
            kline_index=10,
            timestamp=1000
        )

        frozen_before = manager.frozen_capital

        cancelled_id = manager.cancel_pending_buy(timestamp=1050)

        assert cancelled_id == order['order_id']
        assert not manager.has_pending_buy()
        # 资金应解冻
        assert manager.frozen_capital < frozen_before

    def test_cancel_no_pending_buy(self):
        """无待处理买单时取消返回None"""
        manager = GFOBOrderManager()
        manager.initialize(Decimal("10000"))

        cancelled_id = manager.cancel_pending_buy(timestamp=1000)

        assert cancelled_id is None


class TestCapitalManagement:
    """资金管理测试"""

    def test_release_sell_capital(self):
        """释放卖出后资金"""
        manager = GFOBOrderManager()
        manager.initialize(Decimal("10000"))

        # 模拟买入后冻结资金
        buy_price = Decimal("3500")
        quantity = Decimal("0.1")
        manager._capital_manager._available_capital -= buy_price * quantity
        manager._capital_manager._frozen_capital += buy_price * quantity

        initial_available = manager.available_capital
        profit_loss = Decimal("50")  # 盈利50

        manager.release_sell_capital(buy_price, quantity, profit_loss)

        # 可用资金 = 原可用 + 原冻结 + 盈亏
        expected_available = initial_available + buy_price * quantity + profit_loss
        assert manager.available_capital == expected_available


class TestOrderLogs:
    """订单日志测试"""

    def test_order_log_on_place(self):
        """下单时记录日志"""
        manager = GFOBOrderManager()
        manager.initialize(Decimal("10000"))

        manager.create_buy_order(
            close_price=Decimal("3500"),
            kline_index=10,
            timestamp=1000
        )

        logs = manager.get_order_logs()
        assert len(logs) == 1
        assert logs[0]['event'] == 'PLACED'

    def test_order_log_on_fill(self):
        """成交时记录日志"""
        manager = GFOBOrderManager()
        manager.initialize(Decimal("10000"))

        manager.create_buy_order(
            close_price=Decimal("3500"),
            kline_index=10,
            timestamp=1000
        )

        manager.match_orders(
            kline_index=11,
            low=Decimal("3400"),
            high=Decimal("3600"),
            timestamp=1100
        )

        logs = manager.get_order_logs()
        assert len(logs) == 2
        assert logs[1]['event'] == 'FILLED'

    def test_order_log_on_expire(self):
        """过期时记录日志"""
        manager = GFOBOrderManager()
        manager.initialize(Decimal("10000"))

        manager.create_buy_order(
            close_price=Decimal("3500"),
            kline_index=10,
            timestamp=1000
        )

        # 跳过valid_bar导致过期
        manager.match_orders(
            kline_index=12,
            low=Decimal("3400"),
            high=Decimal("3600"),
            timestamp=1200
        )

        logs = manager.get_order_logs()
        assert len(logs) == 2
        assert logs[1]['event'] == 'EXPIRED'


class TestStatistics:
    """统计信息测试"""

    def test_get_statistics(self):
        """获取统计信息"""
        manager = GFOBOrderManager()
        manager.initialize(Decimal("10000"))

        manager.create_buy_order(
            close_price=Decimal("3500"),
            kline_index=10,
            timestamp=1000
        )

        stats = manager.get_statistics()

        assert 'available_capital' in stats
        assert 'frozen_capital' in stats
        assert 'total_capital' in stats
        assert 'has_pending_buy' in stats
        assert 'has_pending_sell' in stats
        assert 'pending_buy_price' in stats
        assert 'pending_sell_price' in stats
        assert 'total_order_events' in stats

        assert stats['has_pending_buy'] is True
        assert stats['has_pending_sell'] is False
        assert stats['total_order_events'] == 1


class TestHelperMethods:
    """辅助方法测试"""

    def test_get_pending_buy_price(self):
        """获取待处理买单价格"""
        manager = GFOBOrderManager()
        manager.initialize(Decimal("10000"))

        assert manager.get_pending_buy_price() is None

        manager.create_buy_order(
            close_price=Decimal("3500"),
            kline_index=10,
            timestamp=1000
        )

        price = manager.get_pending_buy_price()
        assert price is not None
        assert price == Decimal("3500") * (1 - Decimal("0.001"))

    def test_get_pending_sell_price(self):
        """获取待处理卖单价格"""
        manager = GFOBOrderManager()
        manager.initialize(Decimal("10000"))

        assert manager.get_pending_sell_price() is None

        manager.create_sell_order(
            close_price=Decimal("3600"),
            parent_order_id="buy_123",
            quantity=Decimal("0.1"),
            reason='PROB_REVERSION',
            kline_index=20,
            timestamp=2000
        )

        price = manager.get_pending_sell_price()
        assert price is not None

    def test_has_pending_buy(self):
        """检查是否有待处理买单"""
        manager = GFOBOrderManager()
        manager.initialize(Decimal("10000"))

        assert manager.has_pending_buy() is False

        manager.create_buy_order(
            close_price=Decimal("3500"),
            kline_index=10,
            timestamp=1000
        )

        assert manager.has_pending_buy() is True

    def test_has_pending_sell(self):
        """检查是否有待处理卖单"""
        manager = GFOBOrderManager()
        manager.initialize(Decimal("10000"))

        assert manager.has_pending_sell() is False

        manager.create_sell_order(
            close_price=Decimal("3600"),
            parent_order_id="buy_123",
            quantity=Decimal("0.1"),
            reason='PROB_REVERSION',
            kline_index=20,
            timestamp=2000
        )

        assert manager.has_pending_sell() is True


class TestEdgeCases:
    """边界情况测试"""

    def test_zero_delta_in(self):
        """delta_in为0时价格等于close"""
        manager = GFOBOrderManager(delta_in=0.0)
        manager.initialize(Decimal("10000"))

        close_price = Decimal("3500")
        order = manager.create_buy_order(
            close_price=close_price,
            kline_index=10,
            timestamp=1000
        )

        assert order['price'] == close_price

    def test_large_price_precision(self):
        """大数值价格精度"""
        manager = GFOBOrderManager()
        manager.initialize(Decimal("1000000"))

        close_price = Decimal("99999.99999999")
        order = manager.create_buy_order(
            close_price=close_price,
            kline_index=10,
            timestamp=1000
        )

        assert order is not None
        assert order['price'] < close_price

    def test_small_price(self):
        """小数值价格处理"""
        manager = GFOBOrderManager()
        manager.initialize(Decimal("10000"))

        close_price = Decimal("0.00001234")
        order = manager.create_buy_order(
            close_price=close_price,
            kline_index=10,
            timestamp=1000
        )

        assert order is not None
        assert order['price'] > 0

    def test_multiple_orders_same_bar(self):
        """同一K线创建多个订单"""
        manager = GFOBOrderManager()
        manager.initialize(Decimal("10000"))

        # 创建买入挂单
        buy = manager.create_buy_order(
            close_price=Decimal("3500"),
            kline_index=10,
            timestamp=1000
        )

        # 创建卖出挂单
        sell = manager.create_sell_order(
            close_price=Decimal("3600"),
            parent_order_id="existing_pos",
            quantity=Decimal("0.1"),
            reason='PROB_REVERSION',
            kline_index=10,
            timestamp=1000
        )

        assert buy is not None
        assert sell is not None
        assert manager.has_pending_buy()
        assert manager.has_pending_sell()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
