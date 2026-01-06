"""
StrategyAdapter功能验证测试

测试目标：
- adapt_for_backtest() 完整流程
- 策略接口类型验证（TypeError）
- K线数据验证（ValueError）
- 初始资金验证（ValueError）
- 返回数据结构完整性
"""

from decimal import Decimal
from strategy_adapter.core import StrategyAdapter, UnifiedOrderManager
from strategy_adapter.interfaces import IStrategy
from strategy_adapter.models import Order, OrderStatus
from typing import Dict, List
import pandas as pd


class MockSimpleStrategy(IStrategy):
    """简单模拟策略（用于测试）"""

    def get_strategy_name(self) -> str:
        return "MockSimpleStrategy"

    def get_strategy_version(self) -> str:
        return "1.0"

    def generate_buy_signals(self, klines, indicators) -> List[Dict]:
        # 在第1根K线买入
        if len(klines) > 0:
            return [{
                'timestamp': int(klines.index[0].timestamp() * 1000),
                'price': klines.iloc[0]['close'],
                'reason': '测试买入',
                'confidence': 0.8
            }]
        return []

    def generate_sell_signals(self, klines, indicators, open_orders) -> List[Dict]:
        # 在第3根K线卖出
        if len(open_orders) > 0 and len(klines) >= 3:
            order = open_orders[0]
            return [{
                'timestamp': int(klines.index[2].timestamp() * 1000),
                'price': klines.iloc[2]['close'],
                'order_id': order.id,
                'reason': '测试卖出'
            }]
        return []

    def calculate_position_size(self, signal, available_capital, current_price) -> Decimal:
        return Decimal("100")  # 固定100 USDT

    def should_stop_loss(self, order, current_price, current_timestamp) -> bool:
        return False

    def should_take_profit(self, order, current_price, current_timestamp) -> bool:
        return False


class InvalidStrategy:
    """无效策略（未实现IStrategy接口）"""
    pass


def create_test_klines():
    """创建测试K线数据"""
    dates = pd.date_range('2026-01-06', periods=5, freq='4H', tz='UTC')
    klines = pd.DataFrame({
        'open': [2300.0, 2310.0, 2320.0, 2315.0, 2325.0],
        'high': [2310.0, 2320.0, 2330.0, 2325.0, 2335.0],
        'low': [2295.0, 2305.0, 2315.0, 2310.0, 2320.0],
        'close': [2305.0, 2315.0, 2325.0, 2320.0, 2330.0],
        'volume': [1000, 1100, 1200, 1150, 1250]
    }, index=dates)
    return klines


def test_adapter_invalid_strategy():
    """测试无效策略实例（TypeError）"""
    print("\n=== 测试1: 无效策略实例 (TypeError) ===")

    invalid_strategy = InvalidStrategy()

    try:
        adapter = StrategyAdapter(invalid_strategy)
        assert False, "应该抛出TypeError"
    except TypeError as e:
        print(f"✅ 正确抛出TypeError: {e}")


def test_adapter_empty_klines():
    """测试空K线数据（ValueError）"""
    print("\n=== 测试2: 空K线数据 (ValueError) ===")

    strategy = MockSimpleStrategy()
    adapter = StrategyAdapter(strategy)

    empty_klines = pd.DataFrame()

    try:
        adapter.adapt_for_backtest(empty_klines, {})
        assert False, "应该抛出ValueError"
    except ValueError as e:
        print(f"✅ 正确抛出ValueError: {e}")


def test_adapter_invalid_initial_cash():
    """测试无效初始资金（ValueError）"""
    print("\n=== 测试3: 无效初始资金 (ValueError) ===")

    strategy = MockSimpleStrategy()
    adapter = StrategyAdapter(strategy)
    klines = create_test_klines()

    try:
        adapter.adapt_for_backtest(klines, {}, initial_cash=Decimal("0"))
        assert False, "应该抛出ValueError"
    except ValueError as e:
        print(f"✅ 正确抛出ValueError: {e}")


def test_adapter_complete_flow():
    """测试完整适配流程"""
    print("\n=== 测试4: 完整适配流程 ===")

    strategy = MockSimpleStrategy()
    adapter = StrategyAdapter(strategy)
    klines = create_test_klines()
    indicators = {}

    result = adapter.adapt_for_backtest(klines, indicators, Decimal("10000"))

    # 验证返回数据结构
    assert 'entries' in result
    assert 'exits' in result
    assert 'orders' in result
    assert 'statistics' in result

    # 验证entries和exits是pd.Series
    assert isinstance(result['entries'], pd.Series)
    assert isinstance(result['exits'], pd.Series)

    # 验证entries和exits的index与klines一致
    assert len(result['entries']) == len(klines)
    assert len(result['exits']) == len(klines)
    assert result['entries'].index.equals(klines.index)
    assert result['exits'].index.equals(klines.index)

    # 验证信号数量
    assert result['entries'].sum() == 1  # 1个买入信号
    assert result['exits'].sum() == 1    # 1个卖出信号

    # 验证订单
    assert len(result['orders']) == 1
    order = result['orders'][0]
    assert order.status == OrderStatus.CLOSED  # 已平仓
    assert order.profit_loss is not None       # 有盈亏数据

    # 验证统计
    stats = result['statistics']
    assert stats['total_orders'] == 1
    assert stats['closed_orders'] == 1
    assert stats['win_rate'] >= 0  # 胜率在0-100之间

    print(f"✅ 完整流程测试通过")
    print(f"  - 买入信号: {result['entries'].sum()}个")
    print(f"  - 卖出信号: {result['exits'].sum()}个")
    print(f"  - 订单数量: {len(result['orders'])}个")
    print(f"  - 胜率: {stats['win_rate']:.2f}%")
    print(f"  - 总盈亏: {stats['total_profit']:.4f} USDT")


def test_adapter_with_custom_order_manager():
    """测试自定义订单管理器"""
    print("\n=== 测试5: 自定义订单管理器 ===")

    strategy = MockSimpleStrategy()
    custom_manager = UnifiedOrderManager()
    adapter = StrategyAdapter(strategy, order_manager=custom_manager)

    klines = create_test_klines()
    result = adapter.adapt_for_backtest(klines, {}, Decimal("10000"))

    # 验证使用了自定义订单管理器
    assert adapter.order_manager is custom_manager
    assert len(custom_manager._orders) > 0  # 订单已存储在自定义管理器中

    print(f"✅ 自定义订单管理器测试通过")
    print(f"  - 管理器中订单数: {len(custom_manager._orders)}个")


def test_adapter_return_structure():
    """测试返回数据结构完整性"""
    print("\n=== 测试6: 返回数据结构完整性 ===")

    strategy = MockSimpleStrategy()
    adapter = StrategyAdapter(strategy)
    klines = create_test_klines()

    result = adapter.adapt_for_backtest(klines, {}, Decimal("10000"))

    # 验证statistics字段完整性
    required_stats_fields = [
        'total_orders', 'open_orders', 'closed_orders',
        'win_orders', 'lose_orders', 'win_rate',
        'total_profit', 'avg_profit_rate', 'max_profit', 'max_loss'
    ]

    for field in required_stats_fields:
        assert field in result['statistics'], f"缺少统计字段: {field}"

    print(f"✅ 返回数据结构完整")
    print(f"  - entries: pd.Series, 长度={len(result['entries'])}")
    print(f"  - exits: pd.Series, 长度={len(result['exits'])}")
    print(f"  - orders: List[Order], 数量={len(result['orders'])}")
    print(f"  - statistics: Dict, 字段数={len(result['statistics'])}")


if __name__ == "__main__":
    print("开始测试 StrategyAdapter...")

    try:
        test_adapter_invalid_strategy()
        test_adapter_empty_klines()
        test_adapter_invalid_initial_cash()
        test_adapter_complete_flow()
        test_adapter_with_custom_order_manager()
        test_adapter_return_structure()

        print("\n" + "="*60)
        print("✅ 所有测试通过！StrategyAdapter 功能正常")
        print("="*60)
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        raise
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        raise
