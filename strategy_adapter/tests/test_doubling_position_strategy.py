"""
策略12: 倍增仓位限价挂单策略 单元测试

迭代编号: 028 (策略12-倍增仓位限价挂单)
创建日期: 2026-01-11
关联任务: TASK-028-007
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock

from strategy_adapter.strategies import DoublingPositionStrategy
from strategy_adapter.core.limit_order_manager import LimitOrderManager
from strategy_adapter.exits.take_profit import TakeProfitExit


class TestDoublingAmounts:
    """测试倍增金额计算"""

    def test_default_doubling_amounts(self):
        """默认配置(base=100, multiplier=2, count=5)应返回[100,200,400,800,1600]"""
        strategy = DoublingPositionStrategy(
            base_amount=Decimal("100"),
            multiplier=2.0,
            order_count=5
        )
        amounts = strategy.calculate_doubling_amounts()

        assert len(amounts) == 5
        assert amounts[0] == Decimal("100")
        assert amounts[1] == Decimal("200")
        assert amounts[2] == Decimal("400")
        assert amounts[3] == Decimal("800")
        assert amounts[4] == Decimal("1600")

    def test_total_required_capital(self):
        """总资金需求应为3100 USDT"""
        strategy = DoublingPositionStrategy(
            base_amount=Decimal("100"),
            multiplier=2.0,
            order_count=5
        )
        total = strategy.get_total_required_capital()

        assert total == Decimal("3100")

    def test_custom_multiplier(self):
        """自定义倍增系数1.5应正确计算"""
        strategy = DoublingPositionStrategy(
            base_amount=Decimal("100"),
            multiplier=1.5,
            order_count=4
        )
        amounts = strategy.calculate_doubling_amounts()

        assert len(amounts) == 4
        assert amounts[0] == Decimal("100")
        assert amounts[1] == Decimal("150")
        assert amounts[2] == Decimal("225")
        assert amounts[3] == Decimal("337.5")

    def test_custom_base_amount(self):
        """自定义首单金额200应正确计算"""
        strategy = DoublingPositionStrategy(
            base_amount=Decimal("200"),
            multiplier=2.0,
            order_count=3
        )
        amounts = strategy.calculate_doubling_amounts()

        assert amounts == [Decimal("200"), Decimal("400"), Decimal("800")]


class TestLimitOrderManagerExtension:
    """测试LimitOrderManager自定义金额扩展"""

    def test_create_buy_order_default_amount(self):
        """不传amount参数时使用默认position_size"""
        manager = LimitOrderManager(position_size=Decimal("100"))
        manager.initialize(Decimal("1000"))

        order = manager.create_buy_order(
            price=Decimal("3000"),
            kline_index=0,
            timestamp=1736500800000
        )

        assert order is not None
        assert order.amount == Decimal("100")
        assert manager.frozen_capital == Decimal("100")
        assert manager.available_capital == Decimal("900")

    def test_create_buy_order_custom_amount(self):
        """传入自定义amount应覆盖默认值"""
        manager = LimitOrderManager(position_size=Decimal("100"))
        manager.initialize(Decimal("1000"))

        order = manager.create_buy_order(
            price=Decimal("3000"),
            kline_index=0,
            timestamp=1736500800000,
            amount=Decimal("200")
        )

        assert order is not None
        assert order.amount == Decimal("200")
        assert manager.frozen_capital == Decimal("200")
        assert manager.available_capital == Decimal("800")

    def test_create_doubling_orders(self):
        """连续创建倍增金额挂单"""
        manager = LimitOrderManager(position_size=Decimal("100"))
        manager.initialize(Decimal("5000"))

        amounts = [Decimal("100"), Decimal("200"), Decimal("400")]
        prices = [Decimal("3000"), Decimal("2970"), Decimal("2940")]

        orders = []
        for price, amount in zip(prices, amounts):
            order = manager.create_buy_order(
                price=price,
                kline_index=0,
                timestamp=1736500800000,
                amount=amount
            )
            orders.append(order)

        assert all(o is not None for o in orders)
        assert orders[0].amount == Decimal("100")
        assert orders[1].amount == Decimal("200")
        assert orders[2].amount == Decimal("400")
        assert manager.frozen_capital == Decimal("700")
        assert manager.available_capital == Decimal("4300")

    def test_insufficient_capital_for_large_amount(self):
        """资金不足时返回None"""
        manager = LimitOrderManager(position_size=Decimal("100"))
        manager.initialize(Decimal("500"))

        order = manager.create_buy_order(
            price=Decimal("3000"),
            kline_index=0,
            timestamp=1736500800000,
            amount=Decimal("600")
        )

        assert order is None
        assert manager.insufficient_capital_count == 1


class TestTakeProfitExit:
    """测试固定比例止盈"""

    def test_take_profit_triggered(self):
        """止盈价在K线范围内应触发"""
        exit_cond = TakeProfitExit(percentage=2.0)  # 2%

        mock_order = Mock()
        mock_order.open_price = Decimal("3000")

        kline = {'low': 3050, 'high': 3100}  # 止盈价3060在范围内
        indicators = {}
        timestamp = 1736500800000

        signal = exit_cond.check(mock_order, kline, indicators, timestamp)

        assert signal is not None
        assert signal.price == Decimal("3060")
        assert "止盈" in signal.reason

    def test_take_profit_not_triggered(self):
        """止盈价不在K线范围内不应触发"""
        exit_cond = TakeProfitExit(percentage=2.0)  # 2%

        mock_order = Mock()
        mock_order.open_price = Decimal("3000")

        kline = {'low': 3010, 'high': 3050}  # 止盈价3060不在范围内
        indicators = {}
        timestamp = 1736500800000

        signal = exit_cond.check(mock_order, kline, indicators, timestamp)

        assert signal is None


class TestDoublingPositionStrategy:
    """测试策略12核心功能"""

    def test_initialization(self):
        """策略初始化应正确设置参数"""
        strategy = DoublingPositionStrategy(
            base_amount=Decimal("100"),
            multiplier=2.0,
            order_count=5,
            order_interval=0.01,
            first_order_discount=0.01,
            take_profit_rate=0.02
        )

        assert strategy.base_amount == Decimal("100")
        assert strategy.multiplier == Decimal("2")
        assert strategy.order_count == 5
        assert strategy.order_interval == 0.01
        assert strategy.first_order_discount == 0.01
        assert strategy.take_profit_rate == 0.02
        assert strategy.STRATEGY_ID == 'strategy_12'
        assert strategy.STRATEGY_NAME == '倍增仓位限价挂单'

    def test_get_strategy_name(self):
        """get_strategy_name应返回正确名称"""
        strategy = DoublingPositionStrategy()
        assert strategy.get_strategy_name() == '倍增仓位限价挂单'

    def test_get_required_indicators(self):
        """get_required_indicators应返回['p5', 'inertia_mid']"""
        strategy = DoublingPositionStrategy()
        indicators = strategy.get_required_indicators()

        assert 'p5' in indicators
        assert 'inertia_mid' in indicators

    def test_process_kline_creates_orders(self):
        """process_kline应创建倍增金额的买入挂单"""
        strategy = DoublingPositionStrategy(
            base_amount=Decimal("100"),
            multiplier=2.0,
            order_count=3
        )
        strategy.initialize(Decimal("1000"))

        kline = {
            'open': 3000,
            'high': 3050,
            'low': 2950,
            'close': 3020,
            'open_time': 1736500800000
        }
        indicators = {
            'p5': 2900,
            'inertia_mid': 2950
        }

        result = strategy.process_kline(
            kline_index=0,
            kline=kline,
            indicators=indicators,
            timestamp=1736500800000
        )

        assert result['orders_placed'] == 3
        assert result['insufficient_capital_count'] == 0

        # 验证挂单金额
        pending_orders = strategy.order_manager.get_pending_buy_orders()
        amounts = sorted([o.amount for o in pending_orders])
        assert amounts == [Decimal("100"), Decimal("200"), Decimal("400")]

    def test_process_kline_insufficient_capital(self):
        """资金不足时应记录失败次数"""
        strategy = DoublingPositionStrategy(
            base_amount=Decimal("100"),
            multiplier=2.0,
            order_count=5  # 需要3100，但只有1000
        )
        strategy.initialize(Decimal("1000"))

        kline = {
            'open': 3000,
            'high': 3050,
            'low': 2950,
            'close': 3020,
            'open_time': 1736500800000
        }
        indicators = {
            'p5': 2900,
            'inertia_mid': 2950
        }

        result = strategy.process_kline(
            kline_index=0,
            kline=kline,
            indicators=indicators,
            timestamp=1736500800000
        )

        # 100+200+400=700 可以创建，800+1600=2400 资金不足
        assert result['orders_placed'] == 3
        assert result['insufficient_capital_count'] == 2

    def test_process_kline_take_profit(self):
        """持仓达到2%止盈应触发卖出"""
        strategy = DoublingPositionStrategy(
            base_amount=Decimal("100"),
            multiplier=2.0,
            order_count=1,
            take_profit_rate=0.02
        )
        strategy.initialize(Decimal("1000"))

        # 第一根K线：创建挂单
        kline1 = {
            'open': 3000,
            'high': 3050,
            'low': 2950,
            'close': 3020,
            'open_time': 1736500800000
        }
        indicators = {
            'p5': 2900,
            'inertia_mid': 2950
        }

        strategy.process_kline(0, kline1, indicators, 1736500800000)

        # 模拟挂单成交：手动添加一个持仓
        strategy._holdings['test_order'] = {
            'buy_price': Decimal("2900"),
            'quantity': Decimal("0.0345"),  # 100/2900
            'amount': Decimal("100"),
            'buy_timestamp': 1736500800000,
            'kline_index': 0
        }
        # 冻结相应资金
        strategy.order_manager._frozen_capital = Decimal("100")
        strategy.order_manager._available_capital = Decimal("900")

        # 第二根K线：价格上涨触发止盈 (2900 * 1.02 = 2958)
        kline2 = {
            'open': 2950,
            'high': 3000,  # high >= 2958，止盈触发
            'low': 2940,
            'close': 2980,
            'open_time': 1736504400000
        }

        result = strategy.process_kline(1, kline2, indicators, 1736504400000)

        assert len(result['sell_fills']) == 1
        assert result['sell_fills'][0]['profit_rate'] == pytest.approx(2.0, rel=0.01)

    def test_get_statistics(self):
        """get_statistics应返回正确的统计信息"""
        strategy = DoublingPositionStrategy(
            base_amount=Decimal("100"),
            multiplier=2.0,
            order_count=3
        )
        strategy.initialize(Decimal("1000"))

        stats = strategy.get_statistics()

        assert 'available_capital' in stats
        assert 'frozen_capital' in stats
        assert 'holdings_count' in stats
        assert 'completed_trades' in stats
        assert 'win_rate' in stats


class TestStrategyFactoryIntegration:
    """测试StrategyFactory策略12集成"""

    def test_create_strategy_12(self):
        """StrategyFactory应正确创建策略12"""
        from strategy_adapter.core.strategy_factory import StrategyFactory
        from strategy_adapter.models.project_config import StrategyConfig, ExitConfig

        config = StrategyConfig(
            id='strategy_12',
            name='倍增仓位限价挂单',
            type='ddps-z',
            enabled=True,
            entry={
                'strategy_id': 12,
                'base_amount': 100,
                'multiplier': 2.0,
                'order_count': 5,
                'order_interval': 0.01,
                'first_order_discount': 0.01,
                'take_profit_rate': 0.02
            },
            exits=[]
        )

        strategy = StrategyFactory.create(config)

        assert isinstance(strategy, DoublingPositionStrategy)
        assert strategy.base_amount == Decimal("100")
        assert strategy.multiplier == Decimal("2.0")
        assert strategy.order_count == 5
        assert strategy.take_profit_rate == 0.02
