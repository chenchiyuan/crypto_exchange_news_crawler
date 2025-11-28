"""
测试网格订单生成器
Test Order Generator
"""
import pytest
from decimal import Decimal

from grid_trading.services.order_generator import GridOrderGenerator


class TestOrderGenerator:
    """订单生成器测试"""

    def test_generate_long_grid_orders(self):
        """测试生成做多网格订单"""
        generator = GridOrderGenerator()

        orders = generator.generate_grid_orders(
            entry_price=50000.0,
            grid_step=500.0,
            grid_levels=5,
            order_size_usdt=100.0,
            strategy_type='long'
        )

        # 验证订单总数: 上下各5层 = 10个订单
        assert len(orders) == 10

        # 验证买单（下方5层）
        buy_orders = [o for o in orders if o.order_type == 'buy']
        assert len(buy_orders) == 5

        # 验证买单价格递减
        buy_prices = [float(o.price) for o in buy_orders]
        expected_buy_prices = [
            49500.0,  # -500
            49000.0,  # -1000
            48500.0,  # -1500
            48000.0,  # -2000
            47500.0,  # -2500
        ]
        assert buy_prices == expected_buy_prices

        # 验证卖单（上方5层）
        sell_orders = [o for o in orders if o.order_type == 'sell']
        assert len(sell_orders) == 5

        # 验证卖单价格递增
        sell_prices = [float(o.price) for o in sell_orders]
        expected_sell_prices = [
            50500.0,  # +500
            51000.0,  # +1000
            51500.0,  # +1500
            52000.0,  # +2000
            52500.0,  # +2500
        ]
        assert sell_prices == expected_sell_prices

    def test_generate_short_grid_orders(self):
        """测试生成做空网格订单"""
        generator = GridOrderGenerator()

        orders = generator.generate_grid_orders(
            entry_price=50000.0,
            grid_step=500.0,
            grid_levels=3,
            order_size_usdt=100.0,
            strategy_type='short'
        )

        # 做空: 上方卖单，下方买单
        assert len(orders) == 6  # 上下各3层

        sell_orders = [o for o in orders if o.order_type == 'sell']
        buy_orders = [o for o in orders if o.order_type == 'buy']

        assert len(sell_orders) == 3
        assert len(buy_orders) == 3

    def test_order_quantity_calculation(self):
        """测试订单数量计算"""
        generator = GridOrderGenerator()

        orders = generator.generate_grid_orders(
            entry_price=50000.0,
            grid_step=500.0,
            grid_levels=1,
            order_size_usdt=100.0,
            strategy_type='long'
        )

        # 买单: 49500价格，100 USDT
        buy_order = [o for o in orders if o.order_type == 'buy'][0]
        expected_quantity = 100.0 / 49500.0
        assert float(buy_order.quantity) == pytest.approx(expected_quantity, rel=1e-6)

        # 卖单: 50500价格，100 USDT
        sell_order = [o for o in orders if o.order_type == 'sell'][0]
        expected_quantity = 100.0 / 50500.0
        assert float(sell_order.quantity) == pytest.approx(expected_quantity, rel=1e-6)

    def test_calculate_grid_step_percentage(self):
        """测试计算网格步长百分比"""
        generator = GridOrderGenerator()

        step_pct = generator.calculate_grid_step_percentage(
            entry_price=50000.0,
            grid_step=500.0
        )

        # 500 / 50000 = 0.01 = 1%
        assert step_pct == pytest.approx(0.01, rel=1e-6)

    def test_estimate_max_position_value(self):
        """测试估算最大仓位"""
        generator = GridOrderGenerator()

        max_position = generator.estimate_max_position_value(
            grid_levels=10,
            order_size_usdt=100.0,
            strategy_type='long'
        )

        # 10层 * 100 USDT = 1000 USDT
        assert max_position == 1000.0

    def test_invalid_strategy_type(self):
        """测试无效策略类型"""
        generator = GridOrderGenerator()

        with pytest.raises(ValueError, match="不支持的策略类型"):
            generator.generate_grid_orders(
                entry_price=50000.0,
                grid_step=500.0,
                grid_levels=5,
                order_size_usdt=100.0,
                strategy_type='invalid'
            )

    def test_order_level_assignment(self):
        """测试订单层级分配"""
        generator = GridOrderGenerator()

        orders = generator.generate_grid_orders(
            entry_price=50000.0,
            grid_step=500.0,
            grid_levels=3,
            order_size_usdt=100.0,
            strategy_type='long'
        )

        # 验证层级
        buy_orders = sorted(
            [o for o in orders if o.order_type == 'buy'],
            key=lambda o: o.level
        )
        assert [o.level for o in buy_orders] == [-3, -2, -1]

        sell_orders = sorted(
            [o for o in orders if o.order_type == 'sell'],
            key=lambda o: o.level
        )
        assert [o.level for o in sell_orders] == [1, 2, 3]
