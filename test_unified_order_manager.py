"""
UnifiedOrderManager功能验证测试

测试目标：
- create_order() 正常流程
- create_order() 异常处理（KeyError, ValueError）
- update_order() 和盈亏计算
- get_open_orders() / get_closed_orders() 查询
- calculate_statistics() 统计计算
"""

from decimal import Decimal
from strategy_adapter.core import UnifiedOrderManager
from strategy_adapter.models import Order, OrderStatus, OrderSide
from strategy_adapter.interfaces import IStrategy
from typing import Dict, List
import pandas as pd


class MockStrategy(IStrategy):
    """模拟策略（用于测试）"""

    def get_strategy_name(self) -> str:
        return "MockStrategy"

    def get_strategy_version(self) -> str:
        return "1.0"

    def generate_buy_signals(self, klines, indicators) -> List[Dict]:
        return []

    def generate_sell_signals(self, klines, indicators, open_orders) -> List[Dict]:
        return []

    def calculate_position_size(self, signal, available_capital, current_price) -> Decimal:
        # 固定100 USDT
        return Decimal("100")

    def should_stop_loss(self, order, current_price, current_timestamp) -> bool:
        return False

    def should_take_profit(self, order, current_price, current_timestamp) -> bool:
        return False


def test_create_order_success():
    """测试创建订单成功"""
    print("\n=== 测试1: create_order() 成功流程 ===")

    manager = UnifiedOrderManager()
    strategy = MockStrategy()

    signal = {
        'timestamp': 1736164800000,
        'price': 2300.50,
        'reason': 'EMA斜率预测',
        'confidence': 0.85
    }

    order = manager.create_order(
        signal, strategy,
        Decimal("2300.50"), Decimal("10000"), "ETHUSDT"
    )

    assert order.id == "order_1736164800000"
    assert order.symbol == "ETHUSDT"
    assert order.side == OrderSide.BUY
    assert order.status == OrderStatus.FILLED
    assert order.open_price == Decimal("2300.50")
    assert order.position_value == Decimal("100")
    assert order.strategy_name == "MockStrategy"
    print(f"✅ 订单创建成功: {order.id}, 仓位: {order.position_value} USDT")


def test_create_order_missing_timestamp():
    """测试缺少timestamp字段"""
    print("\n=== 测试2: create_order() 缺少timestamp (KeyError) ===")

    manager = UnifiedOrderManager()
    strategy = MockStrategy()

    signal = {'price': 2300.50}  # 缺少timestamp

    try:
        manager.create_order(signal, strategy, Decimal("2300.50"), Decimal("10000"))
        assert False, "应该抛出KeyError"
    except KeyError as e:
        print(f"✅ 正确抛出KeyError: {e}")


def test_create_order_invalid_price():
    """测试无效价格"""
    print("\n=== 测试3: create_order() 无效价格 (ValueError) ===")

    manager = UnifiedOrderManager()
    strategy = MockStrategy()

    signal = {'timestamp': 1736164800000, 'price': 2300.50}

    try:
        manager.create_order(signal, strategy, Decimal("0"), Decimal("10000"))  # 价格=0
        assert False, "应该抛出ValueError"
    except ValueError as e:
        print(f"✅ 正确抛出ValueError: {e}")


def test_update_order_and_pnl():
    """测试更新订单和盈亏计算"""
    print("\n=== 测试4: update_order() 和盈亏计算 ===")

    manager = UnifiedOrderManager()
    strategy = MockStrategy()

    # 创建订单
    buy_signal = {'timestamp': 1736164800000, 'price': 2300.00}
    order = manager.create_order(
        buy_signal, strategy, Decimal("2300.00"), Decimal("10000")
    )
    print(f"开仓: 价格 {order.open_price}, 数量 {order.quantity:.8f}")

    # 平仓
    close_signal = {
        'timestamp': 1736230800000,
        'price': 2350.00,
        'reason': 'EMA25回归'
    }
    manager.update_order(order.id, close_signal)

    assert order.status == OrderStatus.CLOSED
    assert order.close_price == Decimal("2350.00")
    assert order.profit_loss is not None
    print(f"平仓: 价格 {order.close_price}, 盈亏 {order.profit_loss:.4f} USDT ({order.profit_loss_rate:.2f}%)")
    print(f"✅ 订单平仓成功，盈亏计算正确")


def test_query_orders():
    """测试查询持仓和已平仓订单"""
    print("\n=== 测试5: 查询持仓/已平仓订单 ===")

    manager = UnifiedOrderManager()
    strategy = MockStrategy()

    # 创建3个订单
    for i in range(3):
        signal = {'timestamp': 1736164800000 + i * 10000, 'price': 2300.00 + i * 10}
        manager.create_order(signal, strategy, Decimal(str(2300 + i * 10)), Decimal("10000"))

    # 平仓第1个订单
    orders = manager.get_open_orders()
    manager.update_order(orders[0].id, {'timestamp': 1736230800000, 'price': 2350.00})

    open_orders = manager.get_open_orders()
    closed_orders = manager.get_closed_orders()

    assert len(open_orders) == 2
    assert len(closed_orders) == 1
    print(f"✅ 持仓订单: {len(open_orders)} 个")
    print(f"✅ 已平仓订单: {len(closed_orders)} 个")


def test_calculate_statistics():
    """测试统计计算"""
    print("\n=== 测试6: calculate_statistics() 统计计算 ===")

    manager = UnifiedOrderManager()
    strategy = MockStrategy()

    # 创建5个订单
    for i in range(5):
        signal = {'timestamp': 1736164800000 + i * 10000, 'price': 2300.00}
        manager.create_order(signal, strategy, Decimal("2300.00"), Decimal("10000"))

    # 平仓：3个盈利，2个亏损
    close_prices = [2350.00, 2380.00, 2320.00, 2250.00, 2200.00]
    for i, close_price in enumerate(close_prices):
        orders = manager.get_open_orders()
        if orders:
            manager.update_order(orders[0].id, {
                'timestamp': 1736230800000 + i * 10000,
                'price': close_price
            })

    all_orders = list(manager._orders.values())
    stats = manager.calculate_statistics(all_orders)

    print(f"总订单数: {stats['total_orders']}")
    print(f"已平仓订单: {stats['closed_orders']}")
    print(f"盈利订单: {stats['win_orders']}")
    print(f"亏损订单: {stats['lose_orders']}")
    print(f"胜率: {stats['win_rate']:.2f}%")
    print(f"总盈亏: {stats['total_profit']:.4f} USDT")
    print(f"平均收益率: {stats['avg_profit_rate']:.4f}%")
    print(f"最大盈利: {stats['max_profit']:.4f} USDT")
    print(f"最大亏损: {stats['max_loss']:.4f} USDT")

    assert stats['total_orders'] == 5
    assert stats['closed_orders'] == 5
    assert stats['win_orders'] == 3
    assert stats['lose_orders'] == 2
    print(f"✅ 统计计算正确")


def test_calculate_statistics_empty():
    """测试空订单列表的统计"""
    print("\n=== 测试7: calculate_statistics() 空订单列表 ===")

    manager = UnifiedOrderManager()
    stats = manager.calculate_statistics([])

    assert stats['total_orders'] == 0
    assert stats['win_rate'] == 0.0
    assert stats['total_profit'] == Decimal("0")
    print(f"✅ 空订单列表统计正确")


if __name__ == "__main__":
    print("开始测试 UnifiedOrderManager...")

    try:
        test_create_order_success()
        test_create_order_missing_timestamp()
        test_create_order_invalid_price()
        test_update_order_and_pnl()
        test_query_orders()
        test_calculate_statistics()
        test_calculate_statistics_empty()

        print("\n" + "="*60)
        print("✅ 所有测试通过！UnifiedOrderManager 功能正常")
        print("="*60)
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        raise
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        raise
