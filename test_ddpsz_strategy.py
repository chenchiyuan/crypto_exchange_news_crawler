"""
DDPSZStrategy功能验证测试

测试目标：
- 实现IStrategy接口的8个方法
- generate_buy_signals() 调用BuySignalCalculator
- 信号格式转换正确性
- generate_sell_signals() EMA25回归逻辑
- indicators缺少必要字段时的异常处理
"""

from decimal import Decimal
from strategy_adapter.adapters import DDPSZStrategy
from strategy_adapter.models import Order, OrderStatus, OrderSide
from typing import Dict, List
import pandas as pd
import numpy as np


def test_strategy_interface():
    """测试IStrategy接口实现"""
    print("\n=== 测试1: IStrategy接口实现 ===")

    strategy = DDPSZStrategy()

    # 验证8个方法都存在
    assert hasattr(strategy, 'get_strategy_name')
    assert hasattr(strategy, 'get_strategy_version')
    assert hasattr(strategy, 'generate_buy_signals')
    assert hasattr(strategy, 'generate_sell_signals')
    assert hasattr(strategy, 'calculate_position_size')
    assert hasattr(strategy, 'should_stop_loss')
    assert hasattr(strategy, 'should_take_profit')
    assert hasattr(strategy, 'get_required_indicators')

    print(f"策略名称: {strategy.get_strategy_name()}")
    print(f"策略版本: {strategy.get_strategy_version()}")
    print(f"所需指标: {strategy.get_required_indicators()}")
    print(f"✅ IStrategy接口完整实现")


def test_missing_indicators():
    """测试缺少indicators时的异常"""
    print("\n=== 测试2: 缺少indicators (KeyError) ===")

    strategy = DDPSZStrategy()

    # 创建简单的K线数据
    dates = pd.date_range('2026-01-06', periods=5, freq='4h', tz='UTC')
    klines = pd.DataFrame({
        'open_time': dates,
        'open': [2300.0, 2310.0, 2320.0, 2315.0, 2325.0],
        'high': [2310.0, 2320.0, 2330.0, 2325.0, 2335.0],
        'low': [2295.0, 2305.0, 2315.0, 2310.0, 2320.0],
        'close': [2305.0, 2315.0, 2325.0, 2320.0, 2330.0],
        'volume': [1000, 1100, 1200, 1150, 1250]
    }, index=dates)

    # 缺少p5指标
    incomplete_indicators = {
        'ema25': pd.Series([2300.0] * 5, index=dates),
        'beta': pd.Series([5.0] * 5, index=dates)
    }

    try:
        strategy.generate_buy_signals(klines, incomplete_indicators)
        assert False, "应该抛出KeyError"
    except KeyError as e:
        print(f"✅ 正确抛出KeyError: {e}")


def test_empty_klines():
    """测试空K线数据"""
    print("\n=== 测试3: 空K线数据 (ValueError) ===")

    strategy = DDPSZStrategy()
    empty_klines = pd.DataFrame()

    try:
        strategy.generate_buy_signals(empty_klines, {})
        assert False, "应该抛出ValueError"
    except ValueError as e:
        print(f"✅ 正确抛出ValueError: {e}")


def test_generate_sell_signals_no_ema25():
    """测试卖出信号缺少ema25"""
    print("\n=== 测试4: 卖出信号缺少ema25 (KeyError) ===")

    strategy = DDPSZStrategy()
    dates = pd.date_range('2026-01-06', periods=5, freq='4h', tz='UTC')
    klines = pd.DataFrame({
        'low': [2295.0, 2305.0, 2315.0, 2310.0, 2320.0],
        'high': [2310.0, 2320.0, 2330.0, 2325.0, 2335.0]
    }, index=dates)

    try:
        strategy.generate_sell_signals(klines, {}, [])
        assert False, "应该抛出KeyError"
    except KeyError as e:
        print(f"✅ 正确抛出KeyError: {e}")


def test_generate_sell_signals_empty_orders():
    """测试卖出信号无持仓订单"""
    print("\n=== 测试5: 卖出信号无持仓订单 ===")

    strategy = DDPSZStrategy()
    dates = pd.date_range('2026-01-06', periods=5, freq='4h', tz='UTC')
    klines = pd.DataFrame({
        'low': [2295.0, 2305.0, 2315.0, 2310.0, 2320.0],
        'high': [2310.0, 2320.0, 2330.0, 2325.0, 2335.0]
    }, index=dates)
    indicators = {'ema25': pd.Series([2300.0] * 5, index=dates)}

    sell_signals = strategy.generate_sell_signals(klines, indicators, [])

    assert sell_signals == []
    print(f"✅ 无持仓订单时返回空列表")


def test_generate_sell_signals_ema25_reversion():
    """测试EMA25回归卖出逻辑"""
    print("\n=== 测试6: EMA25回归卖出逻辑 ===")

    strategy = DDPSZStrategy()

    # 创建K线数据：第1根不满足，第2根满足条件
    dates = pd.date_range('2026-01-06', periods=5, freq='4h', tz='UTC')
    klines = pd.DataFrame({
        'low': [2290.0, 2320.0, 2285.0, 2310.0, 2320.0],   # 第1根low=2320 > ema25
        'high': [2310.0, 2340.0, 2305.0, 2330.0, 2340.0]   # 第2根[2285, 2305]包含ema25=2300
    }, index=dates)

    # EMA25在第2根为2300（在[2285, 2305]范围内）
    indicators = {
        'ema25': pd.Series([2305.0, 2350.0, 2300.0, 2298.0, 2295.0], index=dates)
    }

    # 创建持仓订单（在第0根K线买入）
    order = Order(
        id='order_test',
        symbol='ETHUSDT',
        side=OrderSide.BUY,
        status=OrderStatus.FILLED,
        open_timestamp=int(dates[0].timestamp() * 1000),
        open_price=Decimal("2300.0"),
        quantity=Decimal("0.043"),
        position_value=Decimal("100"),
        strategy_name='DDPS-Z',
        strategy_id='test',
        entry_reason='test',
        open_commission=Decimal("0.1")
    )

    sell_signals = strategy.generate_sell_signals(klines, indicators, [order])

    assert len(sell_signals) == 1
    signal = sell_signals[0]

    assert signal['order_id'] == 'order_test'
    assert signal['reason'] == 'EMA25回归'
    # EMA25值应该是2300.0（第2根K线的ema25）
    assert signal['price'] == Decimal("2300.0")

    print(f"✅ EMA25回归卖出逻辑正确")
    print(f"  - 卖出信号数: {len(sell_signals)}")
    print(f"  - 卖出价格: {signal['price']} (EMA25值)")
    print(f"  - 卖出理由: {signal['reason']}")


def test_calculate_position_size():
    """测试仓位计算（固定100 USDT）"""
    print("\n=== 测试7: 仓位计算 ===")

    strategy = DDPSZStrategy()

    size = strategy.calculate_position_size(
        signal={},
        available_capital=Decimal("10000"),
        current_price=Decimal("2300")
    )

    assert size == Decimal("100")
    print(f"✅ 仓位计算正确: {size} USDT")


def test_stop_loss_take_profit():
    """测试止损止盈（MVP不启用）"""
    print("\n=== 测试8: 止损止盈 ===")

    strategy = DDPSZStrategy()

    order = Order(
        id='test',
        symbol='ETHUSDT',
        side=OrderSide.BUY,
        status=OrderStatus.FILLED,
        open_timestamp=123456,
        open_price=Decimal("2300"),
        quantity=Decimal("0.043"),
        position_value=Decimal("100"),
        strategy_name='DDPS-Z',
        strategy_id='test',
        entry_reason='test',
        open_commission=Decimal("0.1")
    )

    should_stop = strategy.should_stop_loss(order, Decimal("2200"), 123457)
    should_profit = strategy.should_take_profit(order, Decimal("2400"), 123457)

    assert should_stop == False
    assert should_profit == False
    print(f"✅ 止损止盈正确（MVP不启用）")


def test_required_indicators():
    """测试所需指标列表"""
    print("\n=== 测试9: 所需指标列表 ===")

    strategy = DDPSZStrategy()
    indicators = strategy.get_required_indicators()

    expected = ['ema25', 'p5', 'beta', 'inertia_mid']
    assert indicators == expected
    print(f"✅ 所需指标列表正确: {indicators}")


if __name__ == "__main__":
    print("开始测试 DDPSZStrategy...")

    try:
        test_strategy_interface()
        test_missing_indicators()
        test_empty_klines()
        test_generate_sell_signals_no_ema25()
        test_generate_sell_signals_empty_orders()
        test_generate_sell_signals_ema25_reversion()
        test_calculate_position_size()
        test_stop_loss_take_profit()
        test_required_indicators()

        print("\n" + "="*60)
        print("✅ 所有测试通过！DDPSZStrategy 功能正常")
        print("="*60)
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        raise
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        raise
