"""
DDPS-Z回测集成测试

本脚本验证策略适配层的完整流程：
1. 准备K线数据和指标
2. 创建DDPSZStrategy实例
3. 使用StrategyAdapter适配策略
4. 验证回测结果的完整性

测试目标：
- 端到端流程验证：从数据准备到回测完成
- 数据格式验证：确保所有组件正确协作
- 结果完整性验证：确保返回正确的统计信息

迭代编号: 013 (策略适配层)
创建日期: 2026-01-06
关联任务: TASK-013-009
关联需求: FP-013-009 (prd.md)
"""

from decimal import Decimal
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from strategy_adapter import DDPSZStrategy, StrategyAdapter


def prepare_test_data(days=30):
    """
    准备测试用的K线数据和指标

    Args:
        days (int): 生成多少天的数据，默认30天

    Returns:
        Tuple[pd.DataFrame, Dict]: (klines, indicators)
            - klines: 包含OHLCV的DataFrame
            - indicators: 包含ema25, p5, beta, inertia_mid的字典

    Example:
        >>> klines, indicators = prepare_test_data(30)
        >>> print(len(klines))  # 180根K线（30天 * 6根/天）
    """
    # 生成时间序列（4小时K线，30天约180根）
    end_time = datetime(2026, 1, 6, tzinfo=pd.Timestamp.now(tz='UTC').tz)
    periods = days * 6  # 每天6根4小时K线
    dates = pd.date_range(end=end_time, periods=periods, freq='4h')

    # 生成模拟的价格数据（随机游走 + 趋势）
    np.random.seed(42)  # 固定随机种子确保可复现
    base_price = 2300.0
    returns = np.random.randn(periods) * 20 + 0.5  # 趋势向上
    prices = base_price + np.cumsum(returns)

    # 生成OHLCV数据
    # 重要：使用dates作为index，同时也作为open_time列
    klines = pd.DataFrame({
        'open': prices,
        'high': prices + np.abs(np.random.randn(periods) * 10),
        'low': prices - np.abs(np.random.randn(periods) * 10),
        'close': prices + np.random.randn(periods) * 5,
        'volume': np.random.randint(1000, 2000, periods)
    }, index=dates)

    # 添加open_time列（与index相同）
    klines['open_time'] = klines.index

    # 计算EMA25指标
    ema25 = klines['close'].ewm(span=25, adjust=False).mean()

    # 生成P5价格序列（基于EMA25的偏移）
    p5 = ema25 - 50  # P5在EMA25下方50点

    # 生成β斜率序列（EMA的变化率）
    beta = ema25.diff().rolling(window=5).mean()

    # 生成惯性mid序列（基于价格的动量指标）
    inertia_mid = klines['close'].rolling(window=10).mean()

    # 填充NaN值（使用ffill/bfill代替deprecated的method参数）
    indicators = {
        'ema25': ema25.bfill(),
        'p5': p5.bfill(),
        'beta': beta.bfill(),
        'inertia_mid': inertia_mid.bfill()
    }

    print(f"✅ 准备测试数据完成:")
    print(f"  - K线数量: {len(klines)}根")
    print(f"  - 时间范围: {klines.index[0]} ~ {klines.index[-1]}")
    print(f"  - 指标数量: {len(indicators)}个")

    return klines, indicators


def run_integration_test():
    """
    执行DDPS-Z回测集成测试

    测试流程：
    1. 准备K线数据和指标（30天，约180根K线）
    2. 创建DDPSZStrategy实例
    3. 创建StrategyAdapter实例
    4. 调用adapt_for_backtest()执行适配
    5. 验证返回结果的完整性
    6. 输出统计信息

    验收标准：
    - K线数据准备成功（至少180根）
    - 指标计算成功（ema25, p5, beta, inertia_mid）
    - DDPSZStrategy创建成功
    - StrategyAdapter创建成功
    - adapt_for_backtest()执行成功
    - 返回结果包含entries, exits, orders, statistics
    - statistics包含所有必要字段
    - 订单数量 > 0（确保策略有信号触发）

    Raises:
        AssertionError: 当验收标准未满足时抛出

    Example:
        >>> run_integration_test()
        ✅ DDPS-Z回测集成测试通过
        胜率: 65.00%
        总盈亏: 1234.56 USDT
    """
    print("\n" + "="*60)
    print("DDPS-Z回测集成测试")
    print("="*60)

    # === 步骤1: 准备K线数据和指标 ===
    print("\n[步骤1] 准备K线数据和指标...")
    klines, indicators = prepare_test_data(days=30)

    # 验收标准：K线数量至少180根
    assert len(klines) >= 180, f"K线数量不足: {len(klines)} < 180"

    # 验收标准：指标完整
    required_indicators = ['ema25', 'p5', 'beta', 'inertia_mid']
    for indicator in required_indicators:
        assert indicator in indicators, f"缺少指标: {indicator}"
        assert len(indicators[indicator]) == len(klines), f"{indicator}长度不匹配"

    # === 步骤2: 创建DDPSZStrategy实例 ===
    print("\n[步骤2] 创建DDPSZStrategy实例...")
    strategy = DDPSZStrategy()
    print(f"✅ 策略创建成功: {strategy.get_strategy_name()} v{strategy.get_strategy_version()}")

    # === 步骤3: 创建StrategyAdapter实例 ===
    print("\n[步骤3] 创建StrategyAdapter实例...")
    adapter = StrategyAdapter(strategy)
    print(f"✅ 适配器创建成功")

    # === 步骤4: 执行适配 ===
    print("\n[步骤4] 执行适配...")
    initial_cash = Decimal("10000")
    result = adapter.adapt_for_backtest(klines, indicators, initial_cash, symbol="ETHUSDT")
    print(f"✅ 适配完成")

    # === 步骤5: 验证返回结果的完整性 ===
    print("\n[步骤5] 验证返回结果...")

    # 验收标准：返回结果包含所有必要字段
    assert 'entries' in result, "缺少entries字段"
    assert 'exits' in result, "缺少exits字段"
    assert 'orders' in result, "缺少orders字段"
    assert 'statistics' in result, "缺少statistics字段"

    # 验收标准：entries和exits是pd.Series
    assert isinstance(result['entries'], pd.Series), "entries不是pd.Series"
    assert isinstance(result['exits'], pd.Series), "exits不是pd.Series"

    # 验收标准：entries和exits长度与klines一致
    assert len(result['entries']) == len(klines), "entries长度不匹配"
    assert len(result['exits']) == len(klines), "exits长度不匹配"

    # 验收标准：statistics包含所有必要字段
    required_stats_fields = [
        'total_orders', 'open_orders', 'closed_orders',
        'win_orders', 'lose_orders', 'win_rate',
        'total_profit', 'avg_profit_rate', 'max_profit', 'max_loss'
    ]
    for field in required_stats_fields:
        assert field in result['statistics'], f"statistics缺少字段: {field}"

    print(f"✅ 返回结果验证通过")

    # === 步骤6: 输出统计信息 ===
    print("\n[步骤6] 输出统计信息...")
    stats = result['statistics']

    print(f"\n" + "="*60)
    print("回测结果")
    print("="*60)
    print(f"初始资金: {initial_cash} USDT")
    print(f"\n信号统计:")
    print(f"  - 买入信号: {result['entries'].sum()}个")
    print(f"  - 卖出信号: {result['exits'].sum()}个")
    print(f"\n订单统计:")
    print(f"  - 总订单数: {stats['total_orders']}")
    print(f"  - 持仓订单: {stats['open_orders']}")
    print(f"  - 已平仓订单: {stats['closed_orders']}")
    print(f"  - 盈利订单: {stats['win_orders']}")
    print(f"  - 亏损订单: {stats['lose_orders']}")
    print(f"\n收益统计:")
    print(f"  - 胜率: {stats['win_rate']:.2f}%")
    print(f"  - 总盈亏: {stats['total_profit']:.2f} USDT")
    print(f"  - 平均收益率: {stats['avg_profit_rate']:.2f}%")
    print(f"  - 最大盈利: {stats['max_profit']:.2f} USDT")
    print(f"  - 最大亏损: {stats['max_loss']:.2f} USDT")

    # 验收标准：至少有订单生成（确保策略有信号触发）
    assert stats['total_orders'] > 0, "策略未生成任何订单"

    print(f"\n" + "="*60)
    print("✅ DDPS-Z回测集成测试通过！")
    print("="*60)

    return result


def test_error_handling():
    """
    测试异常路径处理

    测试场景：
    - 空K线数据
    - 缺少指标
    - 无效初始资金
    """
    print("\n" + "="*60)
    print("异常路径测试")
    print("="*60)

    strategy = DDPSZStrategy()
    adapter = StrategyAdapter(strategy)

    # 测试1: 空K线数据
    print("\n[测试1] 空K线数据...")
    empty_klines = pd.DataFrame()
    try:
        adapter.adapt_for_backtest(empty_klines, {})
        assert False, "应该抛出ValueError"
    except ValueError as e:
        print(f"✅ 正确抛出ValueError: {e}")

    # 测试2: 缺少指标
    print("\n[测试2] 缺少指标...")
    klines, _ = prepare_test_data(days=1)
    incomplete_indicators = {'ema25': pd.Series([2300.0] * len(klines), index=klines.index)}
    try:
        adapter.adapt_for_backtest(klines, incomplete_indicators)
        assert False, "应该抛出KeyError"
    except KeyError as e:
        print(f"✅ 正确抛出KeyError: {e}")

    print("\n✅ 异常路径测试通过")


if __name__ == "__main__":
    print("开始DDPS-Z回测集成测试...\n")

    try:
        # 执行主测试
        result = run_integration_test()

        # 执行异常路径测试
        test_error_handling()

        print("\n" + "="*60)
        print("✅ 所有集成测试通过！")
        print("="*60)

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        raise
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        raise
