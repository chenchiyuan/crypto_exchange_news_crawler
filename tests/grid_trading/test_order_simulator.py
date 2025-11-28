"""
测试订单模拟撮合引擎
Test Order Simulator
"""
import pytest
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone

from grid_trading.models import GridStrategy, GridOrder
from grid_trading.services.order_simulator import OrderSimulator


@pytest.mark.django_db
class TestOrderSimulator:
    """订单模拟器测试"""

    @pytest.fixture
    def strategy(self):
        """创建测试策略"""
        return GridStrategy.objects.create(
            symbol='BTCUSDT',
            strategy_type='long',
            grid_step_pct=Decimal('0.01'),
            grid_levels=5,
            order_size=Decimal('0.002'),
            stop_loss_pct=Decimal('0.10'),
            status='active',
            entry_price=Decimal('50000.00')
        )

    def test_fill_buy_order_when_price_drops(self, strategy):
        """测试价格下跌时买单成交"""
        simulator = OrderSimulator()

        # 创建买单: 49000
        buy_order = GridOrder.objects.create(
            strategy=strategy,
            order_type='buy',
            price=Decimal('49000.00'),
            quantity=Decimal('0.002'),
            status='pending'
        )

        # 当前价格: 48900 (低于挂单价)
        current_price = 48900.0
        filled_orders = simulator.check_and_fill_orders([buy_order], current_price)

        # 验证成交
        assert len(filled_orders) == 1
        buy_order.refresh_from_db()
        assert buy_order.status == 'filled'
        assert buy_order.filled_at is not None

        # 验证滑点: 买单价格应该略高于挂单价
        assert float(buy_order.simulated_price) > float(buy_order.price)

        # 验证手续费
        assert buy_order.simulated_fee > 0

    def test_fill_sell_order_when_price_rises(self, strategy):
        """测试价格上涨时卖单成交"""
        simulator = OrderSimulator()

        # 创建卖单: 51000
        sell_order = GridOrder.objects.create(
            strategy=strategy,
            order_type='sell',
            price=Decimal('51000.00'),
            quantity=Decimal('0.002'),
            status='pending'
        )

        # 当前价格: 51100 (高于挂单价)
        current_price = 51100.0
        filled_orders = simulator.check_and_fill_orders([sell_order], current_price)

        # 验证成交
        assert len(filled_orders) == 1
        sell_order.refresh_from_db()
        assert sell_order.status == 'filled'

        # 验证滑点: 卖单价格应该略低于挂单价
        assert float(sell_order.simulated_price) < float(sell_order.price)

    def test_no_fill_when_price_not_reached(self, strategy):
        """测试价格未达到时订单不成交"""
        simulator = OrderSimulator()

        # 创建买单: 49000
        buy_order = GridOrder.objects.create(
            strategy=strategy,
            order_type='buy',
            price=Decimal('49000.00'),
            quantity=Decimal('0.002'),
            status='pending'
        )

        # 当前价格: 50000 (高于买单价，不成交)
        current_price = 50000.0
        filled_orders = simulator.check_and_fill_orders([buy_order], current_price)

        # 验证未成交
        assert len(filled_orders) == 0
        buy_order.refresh_from_db()
        assert buy_order.status == 'pending'

    def test_slippage_calculation(self, strategy):
        """测试滑点计算"""
        simulator = OrderSimulator()

        # 买单
        buy_order = GridOrder.objects.create(
            strategy=strategy,
            order_type='buy',
            price=Decimal('50000.00'),
            quantity=Decimal('0.002'),
            status='pending'
        )

        simulator.check_and_fill_orders([buy_order], 49000.0)
        buy_order.refresh_from_db()

        # 滑点 = 0.05% (默认配置)
        expected_slippage_pct = simulator.slippage_pct
        actual_price = float(buy_order.simulated_price)
        order_price = float(buy_order.price)

        # 买单向上滑点
        assert actual_price == pytest.approx(
            order_price * (1 + expected_slippage_pct),
            rel=1e-6
        )

    def test_fee_calculation(self, strategy):
        """测试手续费计算"""
        simulator = OrderSimulator()

        buy_order = GridOrder.objects.create(
            strategy=strategy,
            order_type='buy',
            price=Decimal('50000.00'),
            quantity=Decimal('0.002'),
            status='pending'
        )

        simulator.check_and_fill_orders([buy_order], 49000.0)
        buy_order.refresh_from_db()

        # 手续费 = 成交金额 * 费率
        cost = float(buy_order.simulated_price) * float(buy_order.quantity)
        expected_fee = cost * simulator.taker_fee_pct

        assert float(buy_order.simulated_fee) == pytest.approx(expected_fee, rel=1e-6)

    def test_cancel_order(self, strategy):
        """测试撤销订单"""
        simulator = OrderSimulator()

        order = GridOrder.objects.create(
            strategy=strategy,
            order_type='buy',
            price=Decimal('49000.00'),
            quantity=Decimal('0.002'),
            status='pending'
        )

        simulator.cancel_order(order)

        order.refresh_from_db()
        assert order.status == 'cancelled'

    def test_cancel_all_orders(self, strategy):
        """测试批量撤销订单"""
        simulator = OrderSimulator()

        # 创建3个pending订单
        for i in range(3):
            GridOrder.objects.create(
                strategy=strategy,
                order_type='buy',
                price=Decimal(str(49000 + i * 100)),
                quantity=Decimal('0.002'),
                status='pending'
            )

        # 创建1个filled订单
        GridOrder.objects.create(
            strategy=strategy,
            order_type='buy',
            price=Decimal('48000.00'),
            quantity=Decimal('0.002'),
            status='filled'
        )

        # 撤销
        cancelled_count = simulator.cancel_all_orders(strategy.id)

        # 验证
        assert cancelled_count == 3

        pending_orders = strategy.gridorder_set.filter(status='pending')
        assert pending_orders.count() == 0

        cancelled_orders = strategy.gridorder_set.filter(status='cancelled')
        assert cancelled_orders.count() == 3

    def test_check_and_fill_multiple_orders(self, strategy):
        """测试批量撮合订单"""
        simulator = OrderSimulator()

        # 创建5个买单
        orders = []
        for i in range(5):
            order = GridOrder.objects.create(
                strategy=strategy,
                order_type='buy',
                price=Decimal(str(49000 - i * 500)),
                quantity=Decimal('0.002'),
                status='pending'
            )
            orders.append(order)

        # 当前价格: 47500，应该成交4个订单（包括等于47500的订单）
        current_price = 47500.0
        filled_orders = simulator.check_and_fill_orders(orders, current_price)

        # 验证
        assert len(filled_orders) == 4

        # 验证成交的是价格高的订单
        for order in filled_orders:
            assert float(order.price) >= current_price
