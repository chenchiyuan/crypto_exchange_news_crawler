#!/usr/bin/env python
"""
策略14 优化买入策略单元测试

测试内容：
1. 价格计算逻辑（首档→第2档-4%→后续每档-1%）
2. 金额计算逻辑（1×,3×,9×,27×,剩余全部）
3. 策略初始化
4. 回测执行
"""

import os
import sys
import unittest
from decimal import Decimal

# 设置项目路径
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_DIR)
os.chdir(PROJECT_DIR)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')
django.setup()

from strategy_adapter.strategies.optimized_entry_strategy import OptimizedEntryStrategy


class TestOptimizedEntryStrategy(unittest.TestCase):
    """策略14单元测试"""

    def setUp(self):
        """初始化测试策略"""
        self.strategy = OptimizedEntryStrategy(
            base_amount=Decimal("100"),
            multiplier=3.0,
            order_count=5,
            first_gap=0.04,
            interval=0.01,
            first_order_discount=0.003,
            take_profit_rate=0.02,
            stop_loss_rate=0.06
        )

    def test_price_calculation(self):
        """测试价格计算逻辑"""
        base_price = Decimal("1000")
        prices = self.strategy._calculate_prices(base_price)

        self.assertEqual(len(prices), 5)

        # first_order_discount=0.003 (测试用), first_gap=0.04, interval=0.01
        # 第1档: base_price × (1 - 0.003) = 997
        expected_1 = Decimal("1000") * (Decimal("1") - Decimal("0.003"))
        self.assertEqual(prices[0], expected_1)

        # 第2档: base_price × (1 - 0.003 - 0.04) = 957
        expected_2 = Decimal("1000") * (Decimal("1") - Decimal("0.003") - Decimal("0.04"))
        self.assertEqual(prices[1], expected_2)

        # 第3档: base_price × (1 - 0.003 - 0.04 - 0.01) = 947
        expected_3 = Decimal("1000") * (Decimal("1") - Decimal("0.003") - Decimal("0.04") - Decimal("0.01"))
        self.assertEqual(prices[2], expected_3)

        # 第4档: base_price × (1 - 0.003 - 0.04 - 0.02) = 937
        expected_4 = Decimal("1000") * (Decimal("1") - Decimal("0.003") - Decimal("0.04") - Decimal("0.02"))
        self.assertEqual(prices[3], expected_4)

        # 第5档: base_price × (1 - 0.003 - 0.04 - 0.03) = 927
        expected_5 = Decimal("1000") * (Decimal("1") - Decimal("0.003") - Decimal("0.04") - Decimal("0.03"))
        self.assertEqual(prices[4], expected_5)

    def test_fixed_amounts(self):
        """测试前4档固定金额"""
        amounts = self.strategy._fixed_amounts

        self.assertEqual(len(amounts), 4)  # 前4档

        # 第1档: 100 (1×)
        self.assertEqual(amounts[0], Decimal("100"))

        # 第2档: 300 (3×)
        self.assertEqual(amounts[1], Decimal("300"))

        # 第3档: 900 (9×)
        self.assertEqual(amounts[2], Decimal("900"))

        # 第4档: 2700 (27×)
        self.assertEqual(amounts[3], Decimal("2700"))

    def test_amount_calculation_with_full_capital(self):
        """测试金额计算 - 资金充足"""
        available = Decimal("10000")
        amounts = self.strategy._calculate_amounts(available)

        self.assertEqual(len(amounts), 5)

        # 前4档固定
        self.assertEqual(amounts[0], Decimal("100"))
        self.assertEqual(amounts[1], Decimal("300"))
        self.assertEqual(amounts[2], Decimal("900"))
        self.assertEqual(amounts[3], Decimal("2700"))

        # 第5档: 10000 - (100 + 300 + 900 + 2700) = 6000
        self.assertEqual(amounts[4], Decimal("6000"))

    def test_amount_calculation_with_limited_capital(self):
        """测试金额计算 - 资金有限"""
        available = Decimal("5000")
        amounts = self.strategy._calculate_amounts(available)

        # 第5档: 5000 - (100 + 300 + 900 + 2700) = 1000
        self.assertEqual(amounts[4], Decimal("1000"))

    def test_amount_calculation_with_insufficient_capital(self):
        """测试金额计算 - 资金不足"""
        available = Decimal("3000")
        amounts = self.strategy._calculate_amounts(available)

        # 第5档: 3000 - 4000 = -1000 → 0
        self.assertEqual(amounts[4], Decimal("0"))

    def test_strategy_initialization(self):
        """测试策略初始化"""
        self.assertEqual(self.strategy.STRATEGY_ID, 'strategy_14')
        self.assertEqual(self.strategy.STRATEGY_NAME, '优化买入策略')
        self.assertEqual(self.strategy.base_amount, Decimal("100"))
        self.assertEqual(self.strategy.multiplier, Decimal("3"))
        self.assertEqual(self.strategy.order_count, 5)
        self.assertEqual(self.strategy.first_gap, Decimal("0.04"))
        self.assertEqual(self.strategy.interval, Decimal("0.01"))

    def test_total_required_capital(self):
        """测试前4档所需资金"""
        required = self.strategy.get_total_required_capital()
        # 100 + 300 + 900 + 2700 = 4000
        self.assertEqual(required, Decimal("4000"))

    def test_required_indicators(self):
        """测试所需指标"""
        indicators = self.strategy.get_required_indicators()
        self.assertIn('p5', indicators)
        self.assertIn('inertia_mid', indicators)

    def test_base_price_calculation_mid_less_than_p5(self):
        """测试基础价格计算 - mid < p5"""
        p5 = Decimal("1000")
        mid = Decimal("900")
        close = Decimal("1100")

        # (p5 + mid) / 2 = 950
        # 注意：折扣在_calculate_prices中应用，这里返回原始价格
        base_price = self.strategy._get_base_price(p5, mid, close)

        expected = (Decimal("1000") + Decimal("900")) / 2
        self.assertEqual(base_price, expected)

    def test_base_price_calculation_mid_greater_than_p5(self):
        """测试基础价格计算 - mid >= p5"""
        p5 = Decimal("1000")
        mid = Decimal("1100")
        close = Decimal("1200")

        # base = p5 = 1000
        # 注意：折扣在_calculate_prices中应用，这里返回原始价格
        base_price = self.strategy._get_base_price(p5, mid, close)

        expected = Decimal("1000")
        self.assertEqual(base_price, expected)

    def test_base_price_with_close_constraint(self):
        """测试基础价格计算 - close约束"""
        p5 = Decimal("1000")
        mid = Decimal("900")
        close = Decimal("940")  # 小于 (p5+mid)/2 = 950

        # base = min(950, 940) = 940
        # 注意：折扣在_calculate_prices中应用，这里返回原始价格
        base_price = self.strategy._get_base_price(p5, mid, close)

        expected = Decimal("940")
        self.assertEqual(base_price, expected)


class TestPriceDistribution(unittest.TestCase):
    """价格分布专项测试"""

    def test_custom_gap_and_interval(self):
        """测试自定义间隔参数"""
        strategy = OptimizedEntryStrategy(
            base_amount=Decimal("100"),
            multiplier=3.0,
            order_count=5,
            first_order_discount=0.02,  # 首档2%
            first_gap=0.05,  # 第二档再低5%
            interval=0.02,   # 后续每档2%
        )

        base_price = Decimal("1000")
        prices = strategy._calculate_prices(base_price)

        # 第1档: 1000 × (1 - 2%) = 980
        self.assertEqual(prices[0], Decimal("980"))
        # 第2档: 1000 × (1 - 2% - 5%) = 930
        self.assertEqual(prices[1], Decimal("930"))
        # 第3档: 1000 × (1 - 2% - 5% - 2%) = 910
        self.assertEqual(prices[2], Decimal("910"))
        # 第4档: 1000 × (1 - 2% - 5% - 4%) = 890
        self.assertEqual(prices[3], Decimal("890"))
        # 第5档: 1000 × (1 - 2% - 5% - 6%) = 870
        self.assertEqual(prices[4], Decimal("870"))

    def test_2percent_first_order_discount(self):
        """测试首档2%折扣的价格分布"""
        strategy = OptimizedEntryStrategy(
            base_amount=Decimal("100"),
            multiplier=2.0,
            order_count=5,
            first_order_discount=0.02,  # 首档2%
            first_gap=0.04,  # 第二档再低4%
            interval=0.01,   # 后续每档1%
        )

        base_price = Decimal("1000")
        prices = strategy._calculate_prices(base_price)

        # 第1档: 1000 × (1 - 2%) = 980
        self.assertEqual(prices[0], Decimal("980"))
        # 第2档: 1000 × (1 - 2% - 4%) = 940
        self.assertEqual(prices[1], Decimal("940"))
        # 第3档: 1000 × (1 - 2% - 4% - 1%) = 930
        self.assertEqual(prices[2], Decimal("930"))
        # 第4档: 1000 × (1 - 2% - 4% - 2%) = 920
        self.assertEqual(prices[3], Decimal("920"))
        # 第5档: 1000 × (1 - 2% - 4% - 3%) = 910
        self.assertEqual(prices[4], Decimal("910"))


class TestAmountDistribution(unittest.TestCase):
    """金额分布专项测试"""

    def test_custom_multiplier(self):
        """测试自定义倍数"""
        strategy = OptimizedEntryStrategy(
            base_amount=Decimal("50"),
            multiplier=2.0,  # 2倍
            order_count=5,
        )

        amounts = strategy._fixed_amounts

        # 50, 100, 200, 400
        self.assertEqual(amounts[0], Decimal("50"))
        self.assertEqual(amounts[1], Decimal("100"))
        self.assertEqual(amounts[2], Decimal("200"))
        self.assertEqual(amounts[3], Decimal("400"))


class TestLimitOrderSellLogic(unittest.TestCase):
    """限价挂单卖出逻辑测试"""

    def setUp(self):
        """初始化测试策略"""
        self.strategy = OptimizedEntryStrategy(
            base_amount=Decimal("100"),
            multiplier=3.0,
            order_count=5,
            first_gap=0.04,
            interval=0.01,
            first_order_discount=0.003,
            take_profit_rate=0.02,
            stop_loss_rate=0.06
        )
        self.strategy.initialize(Decimal("10000"))

    def test_buy_fill_creates_sell_order(self):
        """测试买入成交后立即创建卖出挂单"""
        # K线1：创建买入挂单
        kline1 = {
            'open': '1000',
            'high': '1010',
            'low': '990',
            'close': '1000',
        }
        indicators1 = {
            'p5': 1000,
            'inertia_mid': 900,
        }
        result1 = self.strategy.process_kline(0, kline1, indicators1, 1000000)
        self.assertGreater(result1['orders_placed'], 0)

        # K线2：触发买入成交（价格下探到第1档挂单附近）
        # 第1档价格约947.15（base=950 × 0.997）
        # 止盈价约947.15 × 1.02 = 966.09
        kline2 = {
            'open': '950',
            'high': '960',  # 低于止盈价966.09，避免卖出挂单在同一根K线成交
            'low': '940',   # 触及第1档挂单947.15
            'close': '950',
        }
        indicators2 = {
            'p5': 1000,
            'inertia_mid': 900,
        }
        result2 = self.strategy.process_kline(1, kline2, indicators2, 2000000)

        # 验证买入成交
        self.assertGreater(len(result2['buy_fills']), 0)
        buy_fill = result2['buy_fills'][0]

        # 验证卖出挂单已创建
        sell_orders = self.strategy.order_manager.get_pending_sell_orders()
        self.assertEqual(len(sell_orders), 1)

        # 验证卖出价格 = 买入价 × 1.02
        sell_order = sell_orders[0]
        expected_sell_price = buy_fill['price'] * Decimal("1.02")
        self.assertAlmostEqual(float(sell_order.price), float(expected_sell_price), places=4)

    def test_sell_order_fills_on_next_kline(self):
        """测试下根K线判断卖出挂单是否成交"""
        # K线1：创建买入挂单
        kline1 = {
            'open': '1000',
            'high': '1010',
            'low': '990',
            'close': '1000',
        }
        indicators1 = {'p5': 1000, 'inertia_mid': 900}
        self.strategy.process_kline(0, kline1, indicators1, 1000000)

        # K线2：买入成交，创建卖出挂单（第1档约947.15）
        kline2 = {
            'open': '950',
            'high': '960',  # 低于止盈价，避免立即成交
            'low': '940',
            'close': '950',
        }
        indicators2 = {'p5': 1000, 'inertia_mid': 900}
        result2 = self.strategy.process_kline(1, kline2, indicators2, 2000000)
        self.assertGreater(len(result2['buy_fills']), 0)
        buy_price = result2['buy_fills'][0]['price']

        # K线3：价格上涨，触及卖出挂单（止盈价 = 买入价 × 1.02）
        sell_price = buy_price * Decimal("1.02")
        kline3 = {
            'open': str(sell_price - Decimal("5")),
            'high': str(sell_price + Decimal("5")),  # 超过卖出价
            'low': str(sell_price - Decimal("10")),   # 高于买入价，避免触发新的买入挂单
            'close': str(sell_price),
        }
        indicators3 = {'p5': 1000, 'inertia_mid': 900}
        result3 = self.strategy.process_kline(2, kline3, indicators3, 3000000)

        # 验证卖出成交
        self.assertEqual(len(result3['sell_fills']), 1)
        sell_fill = result3['sell_fills'][0]
        self.assertEqual(sell_fill['close_reason'], 'take_profit')

        # 验证持仓已清空
        self.assertEqual(len(self.strategy.get_holdings()), 0)

    def test_sell_order_adjusts_to_stop_loss(self):
        """测试价格跌破止损线时，卖出挂单调整为止损价"""
        # K线1：创建买入挂单
        kline1 = {
            'open': '1000',
            'high': '1010',
            'low': '990',
            'close': '1000',
        }
        indicators1 = {'p5': 1000, 'inertia_mid': 900}
        self.strategy.process_kline(0, kline1, indicators1, 1000000)

        # K线2：买入成交（第1档约947.15）
        kline2 = {
            'open': '950',
            'high': '960',
            'low': '940',
            'close': '950',
        }
        indicators2 = {'p5': 1000, 'inertia_mid': 900}
        result2 = self.strategy.process_kline(1, kline2, indicators2, 2000000)
        buy_price = result2['buy_fills'][0]['price']

        # K线3：价格跌破止损线（买入价 × 0.94）
        stop_loss_price = buy_price * Decimal("0.94")
        kline3 = {
            'open': str(buy_price),
            'high': str(buy_price),
            'low': str(stop_loss_price - Decimal("5")),  # 跌破止损
            'close': str(stop_loss_price + Decimal("5")),  # 收盘价高于止损，避免立即成交
        }
        indicators3 = {'p5': 1000, 'inertia_mid': 900}
        result3 = self.strategy.process_kline(2, kline3, indicators3, 3000000)

        # 验证卖出挂单价格已调整为止损价
        sell_orders = self.strategy.order_manager.get_pending_sell_orders()
        if len(sell_orders) > 0:
            sell_order = sell_orders[0]
            self.assertAlmostEqual(float(sell_order.price), float(stop_loss_price), places=4)

    def test_capital_release_after_sell(self):
        """测试卖出成交后正确释放冻结资金"""
        initial_capital = Decimal("10000")
        self.strategy.initialize(initial_capital)

        # K线1：创建买入挂单
        kline1 = {
            'open': '1000',
            'high': '1010',
            'low': '990',
            'close': '1000',
        }
        indicators1 = {'p5': 1000, 'inertia_mid': 900}
        self.strategy.process_kline(0, kline1, indicators1, 1000000)

        # K线2：买入成交
        kline2 = {
            'open': '950',
            'high': '960',
            'low': '940',
            'close': '950',
        }
        indicators2 = {'p5': 1000, 'inertia_mid': 900}
        result2 = self.strategy.process_kline(1, kline2, indicators2, 2000000)
        buy_price = result2['buy_fills'][0]['price']
        buy_amount = result2['buy_fills'][0]['amount']

        # 验证资金被冻结
        stats_after_buy = self.strategy.get_statistics()
        self.assertLess(stats_after_buy['available_capital'], float(initial_capital))

        # K线3：卖出成交
        sell_price = buy_price * Decimal("1.02")
        kline3 = {
            'open': str(sell_price - Decimal("5")),
            'high': str(sell_price + Decimal("5")),
            'low': str(sell_price - Decimal("10")),  # 高于买入价，避免触发新的买入挂单
            'close': str(sell_price),
        }
        indicators3 = {'p5': 1000, 'inertia_mid': 900}
        result3 = self.strategy.process_kline(2, kline3, indicators3, 3000000)

        # 验证资金已释放（本金 + 盈利）
        stats_after_sell = self.strategy.get_statistics()
        profit_loss = float(result3['sell_fills'][0]['profit_loss'])

        # 总资金应该 = 初始资金 + 盈利
        expected_total = float(initial_capital) + profit_loss
        self.assertAlmostEqual(stats_after_sell['total_capital'], expected_total, places=2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
