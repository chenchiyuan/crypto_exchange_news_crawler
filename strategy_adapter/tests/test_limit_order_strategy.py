"""
测试文件：策略11（限价挂单策略）单元测试

Purpose:
    验证策略11各组件的正确性：
    - LimitOrderPriceCalculator: 挂单价格计算
    - LimitOrderManager: 限价挂单管理器
    - LimitOrderExit: 限价卖出计算
    - LimitOrderStrategy: 策略整体逻辑

关联任务: TASK-027-009
关联需求: FP-027-001~018 (function-points.md)
关联架构: architecture.md#5.4 LimitOrderStrategy

测试策略:
    - 单元测试每个组件
    - 覆盖边界情况和异常场景
    - 验证资金冻结和释放逻辑
"""

import unittest
from decimal import Decimal
from datetime import datetime

from strategy_adapter.models import PendingOrder, PendingOrderStatus, PendingOrderSide
from strategy_adapter.core.limit_order_price_calculator import LimitOrderPriceCalculator
from strategy_adapter.core.limit_order_manager import LimitOrderManager
from strategy_adapter.exits.limit_order_exit import LimitOrderExit
from strategy_adapter.strategies import LimitOrderStrategy


class TestLimitOrderPriceCalculator(unittest.TestCase):
    """LimitOrderPriceCalculator单元测试套件"""

    def setUp(self):
        """测试前准备"""
        self.calculator = LimitOrderPriceCalculator(
            order_count=10,
            order_interval=0.005  # 0.5%
        )

    def test_calculate_start_price_mid_less_than_p5(self):
        """
        测试用例1a：验证起始价格计算（mid < P5）

        验收标准:
        - mid < P5时，start_price = (P5 + mid) / 2 × (1 - first_order_discount)
        """
        # Arrange
        p5 = Decimal('100.0')
        mid = Decimal('80.0')  # mid < P5

        # Act
        start_price = self.calculator.get_first_buy_price(p5, mid)

        # Assert - (100+80)/2 × 0.99 = 90 × 0.99 = 89.1
        base_price = (p5 + mid) / 2
        expected = base_price * Decimal('0.99')
        self.assertEqual(start_price, expected)
        self.assertEqual(start_price, Decimal('89.1'))

    def test_calculate_start_price_mid_greater_than_p5(self):
        """
        测试用例1b：验证起始价格计算（mid >= P5）

        验收标准:
        - mid >= P5时，start_price = P5 × (1 - first_order_discount)
        """
        # Arrange
        p5 = Decimal('100.0')
        mid = Decimal('120.0')  # mid > P5

        # Act
        start_price = self.calculator.get_first_buy_price(p5, mid)

        # Assert - 默认first_order_discount=0.01
        expected = p5 * Decimal('0.99')  # 100 * 0.99 = 99
        self.assertEqual(start_price, expected)

    def test_calculate_buy_prices_count(self):
        """
        测试用例2：验证生成的挂单数量

        验收标准:
        - 返回order_count个价格
        """
        # Arrange - 使用mid < P5的情况
        p5 = Decimal('100.0')
        mid = Decimal('80.0')

        # Act
        prices = self.calculator.calculate_buy_prices(p5, mid)

        # Assert
        self.assertEqual(len(prices), 10)

    def test_calculate_buy_prices_decreasing(self):
        """
        测试用例3：验证价格递减

        验收标准:
        - 每个价格比前一个低order_interval
        """
        # Arrange - 使用mid < P5的情况
        p5 = Decimal('100.0')
        mid = Decimal('80.0')

        # Act
        prices = self.calculator.calculate_buy_prices(p5, mid)

        # Assert
        for i in range(1, len(prices)):
            # 验证递减关系
            self.assertLess(prices[i], prices[i - 1])

        # 验证间隔约为0.5%
        # 首笔 = (100+80)/2 × 0.99 = 89.1
        start_price = Decimal('89.1')
        expected_second = start_price * (1 - Decimal('0.005'))  # 89.1 × 0.995 = 88.6545
        self.assertAlmostEqual(
            float(prices[1]),
            float(expected_second),
            places=4
        )

    def test_calculate_buy_prices_with_zero_p5(self):
        """
        测试用例4：P5为0时的行为

        验收标准:
        - 当P5=0且mid>P5时，首笔价格 = 0 * 0.995 = 0
        """
        # Arrange
        p5 = Decimal('0')
        mid = Decimal('120.0')

        # Act
        prices = self.calculator.calculate_buy_prices(p5, mid)

        # Assert - mid > p5, 所以首笔 = p5 * 0.995 = 0
        self.assertEqual(len(prices), 10)
        self.assertEqual(prices[0], Decimal('0'))

    def test_calculate_buy_prices_with_zero_mid(self):
        """
        测试用例5：mid为0时的行为

        验收标准:
        - 当mid=0且mid<P5时，首笔价格 = (P5 + 0) / 2 × (1 - first_order_discount)
        """
        # Arrange
        p5 = Decimal('100.0')
        mid = Decimal('0')

        # Act
        prices = self.calculator.calculate_buy_prices(p5, mid)

        # Assert - mid < p5, 首笔 = (100 + 0) / 2 × 0.99 = 50 × 0.99 = 49.5
        self.assertEqual(len(prices), 10)
        self.assertEqual(prices[0], Decimal('49.5'))


class TestLimitOrderManager(unittest.TestCase):
    """LimitOrderManager单元测试套件"""

    def setUp(self):
        """测试前准备"""
        self.manager = LimitOrderManager(position_size=Decimal('100'))
        self.manager.initialize(Decimal('10000'))

    def test_initialize_sets_capital(self):
        """
        测试用例1：验证初始化设置资金

        验收标准:
        - available_capital = initial_capital
        - frozen_capital = 0
        """
        # Assert
        self.assertEqual(self.manager.available_capital, Decimal('10000'))
        self.assertEqual(self.manager.frozen_capital, Decimal('0'))

    def test_create_buy_order_freezes_capital(self):
        """
        测试用例2：创建买入挂单冻结资金

        验收标准:
        - 创建挂单后，frozen_capital增加position_size
        - available_capital减少position_size
        """
        # Act
        order = self.manager.create_buy_order(
            price=Decimal('100'),
            kline_index=0,
            timestamp=1000
        )

        # Assert
        self.assertIsNotNone(order)
        self.assertEqual(self.manager.frozen_capital, Decimal('100'))
        self.assertEqual(self.manager.available_capital, Decimal('9900'))

    def test_create_buy_order_insufficient_capital(self):
        """
        测试用例3：资金不足时无法创建挂单

        验收标准:
        - 可用资金不足时返回None
        - insufficient_capital_count增加
        """
        # Arrange
        manager = LimitOrderManager(position_size=Decimal('5000'))
        manager.initialize(Decimal('4000'))  # 资金不足

        # Act
        order = manager.create_buy_order(
            price=Decimal('100'),
            kline_index=0,
            timestamp=1000
        )

        # Assert
        self.assertIsNone(order)
        self.assertEqual(manager.insufficient_capital_count, 1)

    def test_cancel_all_buy_orders_unfreezes_capital(self):
        """
        测试用例4：取消所有买入挂单释放资金

        验收标准:
        - 取消挂单后，frozen_capital归零
        - available_capital恢复
        """
        # Arrange
        self.manager.create_buy_order(Decimal('100'), 0, 1000)
        self.manager.create_buy_order(Decimal('99'), 0, 1000)
        self.assertEqual(self.manager.frozen_capital, Decimal('200'))

        # Act
        self.manager.cancel_all_buy_orders()

        # Assert
        self.assertEqual(self.manager.frozen_capital, Decimal('0'))
        self.assertEqual(self.manager.available_capital, Decimal('10000'))

    def test_check_buy_order_fill(self):
        """
        测试用例5：检查买入挂单是否成交

        验收标准:
        - low <= price <= high 时返回True
        - 否则返回False
        """
        # Arrange
        order = self.manager.create_buy_order(Decimal('100'), 0, 1000)

        # Act & Assert
        # 成交：low=95, high=105, price=100
        self.assertTrue(self.manager.check_buy_order_fill(
            order, Decimal('95'), Decimal('105')
        ))

        # 不成交：low=101, high=110, price=100
        self.assertFalse(self.manager.check_buy_order_fill(
            order, Decimal('101'), Decimal('110')
        ))

        # 边界：low=100 (刚好等于price)
        self.assertTrue(self.manager.check_buy_order_fill(
            order, Decimal('100'), Decimal('110')
        ))

    def test_fill_buy_order_updates_status(self):
        """
        测试用例6：填充买入订单更新状态

        验收标准:
        - 状态变为filled
        - 从pending列表移除
        """
        # Arrange
        order = self.manager.create_buy_order(Decimal('100'), 0, 1000)
        order_id = order.order_id

        # Act
        filled = self.manager.fill_buy_order(order_id, 2000)

        # Assert
        self.assertIsNotNone(filled)
        self.assertEqual(filled.status, PendingOrderStatus.FILLED)
        self.assertEqual(len(self.manager.get_pending_buy_orders()), 0)

    def test_create_sell_order_after_buy_fill(self):
        """
        测试用例7：买入成交后创建卖出挂单

        验收标准:
        - 卖出挂单关联到买入订单
        - 卖出数量与买入一致
        """
        # Arrange
        buy_order = self.manager.create_buy_order(Decimal('100'), 0, 1000)
        self.manager.fill_buy_order(buy_order.order_id, 2000)

        # Act
        sell_order = self.manager.create_sell_order(
            parent_order_id=buy_order.order_id,
            sell_price=Decimal('105'),
            quantity=buy_order.quantity,
            kline_index=1,
            timestamp=3000
        )

        # Assert
        self.assertIsNotNone(sell_order)
        self.assertEqual(sell_order.parent_order_id, buy_order.order_id)
        self.assertEqual(sell_order.quantity, buy_order.quantity)

    def test_fill_sell_order_releases_capital(self):
        """
        测试用例8：卖出成交释放资金

        验收标准:
        - 卖出后冻结资金释放
        - 可用资金增加
        """
        # Arrange
        buy_order = self.manager.create_buy_order(Decimal('100'), 0, 1000)
        self.manager.fill_buy_order(buy_order.order_id, 2000)
        sell_order = self.manager.create_sell_order(
            parent_order_id=buy_order.order_id,
            sell_price=Decimal('105'),  # 5%盈利
            quantity=buy_order.quantity,
            kline_index=1,
            timestamp=3000
        )

        # Act
        result = self.manager.fill_sell_order(
            sell_order.order_id, 4000, buy_order.price
        )

        # Assert
        self.assertIsNotNone(result)
        self.assertIn('profit_loss', result)
        self.assertIn('profit_rate', result)
        # 验证盈利
        self.assertGreater(result['profit_loss'], 0)


class TestLimitOrderExit(unittest.TestCase):
    """LimitOrderExit单元测试套件"""

    def setUp(self):
        """测试前准备"""
        self.exit = LimitOrderExit(
            take_profit_rate=0.05,  # 5%
            ema_period=25
        )

    def test_calculate_sell_price_take_profit(self):
        """
        测试用例1：卖出价格为5%止盈价

        验收标准:
        - 当EMA高于止盈价时，使用止盈价
        """
        # Arrange
        buy_price = Decimal('100')
        ema = Decimal('120')  # EMA高于止盈价

        # Act
        sell_price = self.exit.calculate_sell_price(buy_price, ema)

        # Assert
        expected = buy_price * Decimal('1.05')
        self.assertEqual(sell_price, expected)
        self.assertEqual(sell_price, Decimal('105'))

    def test_calculate_sell_price_ema(self):
        """
        测试用例2：卖出价格为EMA

        验收标准:
        - 当EMA低于止盈价时，使用EMA
        """
        # Arrange
        buy_price = Decimal('100')
        ema = Decimal('102')  # EMA低于止盈价(105)

        # Act
        sell_price = self.exit.calculate_sell_price(buy_price, ema)

        # Assert
        self.assertEqual(sell_price, ema)
        self.assertEqual(sell_price, Decimal('102'))

    def test_calculate_sell_price_ema_equals_take_profit(self):
        """
        测试用例3：EMA等于止盈价

        验收标准:
        - 返回该价格
        """
        # Arrange
        buy_price = Decimal('100')
        ema = Decimal('105')  # EMA等于止盈价

        # Act
        sell_price = self.exit.calculate_sell_price(buy_price, ema)

        # Assert
        self.assertEqual(sell_price, Decimal('105'))

    def test_calculate_sell_price_loss_prevention_ema_floor(self):
        """
        测试用例4：防亏损逻辑 - 使用EMA保底价

        验收标准:
        - 当正常卖出价格 < 买入价时，启用防亏损逻辑
        - EMA保底价 = EMA × (1 + min_profit_rate)
        - 手续费保底价 = 买入价 × (1 + commission_rate)
        - 返回两者较低值
        """
        # Arrange
        exit_handler = LimitOrderExit(
            take_profit_rate=0.05,
            ema_period=25,
            commission_rate=0.001,  # 0.1%
            min_profit_rate=0.02    # 2%
        )
        buy_price = Decimal('100')
        ema = Decimal('95')  # EMA远低于买入价，触发防亏损

        # Act
        sell_price = exit_handler.calculate_sell_price(buy_price, ema)

        # Assert
        # EMA保底价 = 95 × 1.02 = 96.9
        # 手续费保底价 = 100 × 1.001 = 100.1
        # min(96.9, 100.1) = 96.9
        expected_ema_floor = ema * Decimal('1.02')
        self.assertEqual(sell_price, expected_ema_floor)
        self.assertEqual(sell_price, Decimal('96.9'))

    def test_calculate_sell_price_loss_prevention_commission_floor(self):
        """
        测试用例5：防亏损逻辑 - 使用手续费保底价

        验收标准:
        - 当EMA保底价 > 手续费保底价时，使用手续费保底价
        """
        # Arrange
        exit_handler = LimitOrderExit(
            take_profit_rate=0.05,
            ema_period=25,
            commission_rate=0.001,  # 0.1%
            min_profit_rate=0.02    # 2%
        )
        buy_price = Decimal('100')
        ema = Decimal('99')  # EMA略低于买入价

        # Act
        sell_price = exit_handler.calculate_sell_price(buy_price, ema)

        # Assert
        # EMA保底价 = 99 × 1.02 = 100.98
        # 手续费保底价 = 100 × 1.001 = 100.1
        # min(100.98, 100.1) = 100.1
        expected_commission_floor = buy_price * Decimal('1.001')
        self.assertEqual(sell_price, expected_commission_floor)
        self.assertEqual(sell_price, Decimal('100.1'))


class TestLimitOrderStrategy(unittest.TestCase):
    """LimitOrderStrategy单元测试套件"""

    def setUp(self):
        """测试前准备"""
        self.strategy = LimitOrderStrategy(
            position_size=Decimal('100'),
            order_count=5,
            order_interval=0.01,  # 1%
            take_profit_rate=0.05,
            ema_period=25
        )
        self.strategy.initialize(Decimal('10000'))

    def test_initialize_resets_state(self):
        """
        测试用例1：初始化重置状态

        验收标准:
        - 持仓清空
        - 完成订单清空
        """
        # Arrange
        self.strategy._holdings['test'] = {'buy_price': Decimal('100')}
        self.strategy._completed_orders.append({})

        # Act
        self.strategy.initialize(Decimal('10000'))

        # Assert
        self.assertEqual(len(self.strategy._holdings), 0)
        self.assertEqual(len(self.strategy._completed_orders), 0)

    def test_get_required_indicators(self):
        """
        测试用例2：验证所需指标

        验收标准:
        - 返回 ['ema25', 'p5', 'inertia_mid']
        """
        # Act
        indicators = self.strategy.get_required_indicators()

        # Assert
        self.assertIn('ema25', indicators)
        self.assertIn('p5', indicators)
        self.assertIn('inertia_mid', indicators)

    def test_process_kline_creates_orders(self):
        """
        测试用例3：process_kline创建挂单

        验收标准:
        - 返回orders_placed > 0
        """
        # Arrange
        kline = {
            'open': 110, 'high': 115, 'low': 105, 'close': 112
        }
        indicators = {
            'p5': 100,
            'inertia_mid': 120,
            'ema25': 110,
            'beta': 1  # future_ema = 110 + 1*6 = 116 > first_buy_price(99)
        }

        # Act
        result = self.strategy.process_kline(0, kline, indicators, 1000)

        # Assert
        self.assertGreater(result['orders_placed'], 0)
        self.assertEqual(result['orders_placed'], 5)  # order_count=5

    def test_process_kline_cancels_previous_orders(self):
        """
        测试用例4：process_kline取消上一根K线的未成交挂单

        验收标准:
        - orders_cancelled记录取消数量
        - 如果上一根K线的挂单都成交了，则orders_cancelled=0
        """
        # Arrange - 第一根K线：high远低于挂单价格，挂单不成交
        kline1 = {
            'open': 90, 'high': 95, 'low': 85, 'close': 92
        }
        indicators = {
            'p5': 100,
            'inertia_mid': 120,
            'ema25': 110,
            'beta': 1  # future_ema = 110 + 1*6 = 116 > first_buy_price(99)
        }

        # 第一根K线创建挂单 - 起始价格=(100+120)/2=110
        # 挂单价格都在105-110范围，K线high=95，所以都不成交
        result1 = self.strategy.process_kline(0, kline1, indicators, 1000)
        self.assertEqual(result1['orders_placed'], 5)
        self.assertEqual(len(result1['buy_fills']), 0)

        # Act - 第二根K线应该取消上一根的挂单
        kline2 = {
            'open': 90, 'high': 95, 'low': 85, 'close': 92
        }
        result2 = self.strategy.process_kline(1, kline2, indicators, 2000)

        # Assert
        self.assertEqual(result2['orders_cancelled'], 5)

    def test_process_kline_fills_buy_order(self):
        """
        测试用例5：挂单价格在K线范围内成交

        验收标准:
        - buy_fills包含成交订单

        注意：使用 mid < p5 场景，首笔价格 = (p5+mid)/2
        """
        # Arrange
        # 使用 mid < p5 场景
        # p5=120, mid=100 -> 首笔价格 = (120+100)/2 = 110
        kline1 = {
            'open': 110, 'high': 115, 'low': 105, 'close': 112
        }
        indicators = {
            'p5': 120,
            'inertia_mid': 100,
            'ema25': 110,
            'beta': 1  # future_ema = 110 + 1*6 = 116 > first_buy_price(110)
        }
        self.strategy.process_kline(0, kline1, indicators, 1000)

        # 第二根K线：low足够低触发成交
        # 起始价 = (120+100)/2 = 110
        # 第一个挂单价 = 110
        # 第二个挂单价 = 110 * 0.995 = 109.45
        kline2 = {
            'open': 112, 'high': 115, 'low': 105, 'close': 110
        }

        # Act
        result = self.strategy.process_kline(1, kline2, indicators, 2000)

        # Assert
        # 挂单价格范围大约是110到105.6，low=105应该触发多个成交
        self.assertGreater(len(result['buy_fills']), 0)

    def test_get_strategy_name(self):
        """
        测试用例6：验证策略名称

        验收标准:
        - 返回 '限价挂单策略'
        """
        # Act
        name = self.strategy.get_strategy_name()

        # Assert
        self.assertEqual(name, '限价挂单策略')

    def test_get_statistics(self):
        """
        测试用例7：获取统计信息

        验收标准:
        - 返回包含关键统计字段的字典
        """
        # Act
        stats = self.strategy.get_statistics()

        # Assert
        self.assertIn('holdings_count', stats)
        self.assertIn('completed_trades', stats)
        self.assertIn('total_profit_loss', stats)
        self.assertIn('win_rate', stats)


class TestPendingOrder(unittest.TestCase):
    """PendingOrder数据结构单元测试"""

    def test_create_pending_order(self):
        """
        测试用例1：创建挂单对象

        验收标准:
        - 所有字段正确设置
        """
        # Act
        order = PendingOrder(
            order_id='test_001',
            side=PendingOrderSide.BUY,
            price=Decimal('100'),
            quantity=Decimal('1.5'),
            amount=Decimal('150'),
            status=PendingOrderStatus.PENDING,
            frozen_capital=Decimal('150'),
            kline_index=5,
            created_at=1000
        )

        # Assert
        self.assertEqual(order.order_id, 'test_001')
        self.assertEqual(order.side, PendingOrderSide.BUY)
        self.assertEqual(order.price, Decimal('100'))
        self.assertEqual(order.quantity, Decimal('1.5'))
        self.assertEqual(order.status, PendingOrderStatus.PENDING)
        self.assertTrue(order.is_buy_order())
        self.assertTrue(order.is_pending())

    def test_pending_order_status_transitions(self):
        """
        测试用例2：挂单状态转换

        验收标准:
        - PENDING -> FILLED
        - PENDING -> CANCELLED
        """
        # Arrange
        order = PendingOrder(
            order_id='test_001',
            side=PendingOrderSide.BUY,
            price=Decimal('100'),
            quantity=Decimal('1'),
            amount=Decimal('100'),
            status=PendingOrderStatus.PENDING,
            frozen_capital=Decimal('100'),
            kline_index=0,
            created_at=1000
        )

        # Act & Assert - mark_filled
        order.mark_filled(2000)
        self.assertEqual(order.status, PendingOrderStatus.FILLED)
        self.assertEqual(order.filled_at, 2000)

        # Reset status for cancel test
        order.status = PendingOrderStatus.PENDING
        order.mark_cancelled()
        self.assertEqual(order.status, PendingOrderStatus.CANCELLED)

    def test_pending_order_to_dict(self):
        """
        测试用例3：转换为字典

        验收标准:
        - to_dict()返回包含所有字段的字典
        - Decimal类型转换为float
        """
        # Arrange
        order = PendingOrder(
            order_id='test_001',
            side=PendingOrderSide.SELL,
            price=Decimal('100'),
            quantity=Decimal('1'),
            amount=Decimal('100'),
            status=PendingOrderStatus.PENDING,
            frozen_capital=Decimal('0'),
            kline_index=0,
            created_at=1000,
            parent_order_id='parent_001'
        )

        # Act
        result = order.to_dict()

        # Assert
        self.assertEqual(result['order_id'], 'test_001')
        self.assertEqual(result['side'], 'sell')
        self.assertEqual(result['price'], 100.0)
        self.assertEqual(result['parent_order_id'], 'parent_001')
        self.assertTrue(order.is_sell_order())


if __name__ == '__main__':
    unittest.main()
