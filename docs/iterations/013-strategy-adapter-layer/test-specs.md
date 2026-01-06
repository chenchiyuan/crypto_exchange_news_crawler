# 测试规格文档：策略适配层

**迭代编号**: 013
**迭代名称**: 策略适配层 (Strategy Adapter Layer)
**文档版本**: 1.0
**创建日期**: 2026-01-06
**测试策略**: TDD + 文档驱动

---

## 测试规格设计原则

1. **测试驱动开发（TDD）**：先写测试，后写实现
2. **Fail-Fast验证**：每个功能必须包含异常路径测试
3. **文档化测试**：测试即规格，测试名称清晰描述场景
4. **高覆盖率**：单元测试覆盖率 ≥ 80%
5. **可追溯性**：每个测试用例关联到tasks.md任务和prd.md需求

---

## 测试规格矩阵

### 阶段1：模块基础设施测试

| 测试点 ID | 关联需求 (prd.md) | 关联架构 (architecture.md) | 任务ID (tasks.md) | 测试策略 | 可量化成功标准 |
|----------|------------------|---------------------------|------------------|---------|--------------|
| TC-001 | 2.1 系统架构 | 4.1 模块结构 | TASK-013-001 | 手动验证 | 所有子模块可正常导入 |
| TC-002 | 2.2.2 订单数据结构 | 4.2 数据模型模块 | TASK-013-002 | 单元测试 | OrderStatus枚举包含4个状态 |
| TC-003 | 2.2.2 订单数据结构 | 4.2 数据模型模块 | TASK-013-003 | 单元测试 | Order.calculate_pnl()正确计算盈亏 |
| TC-004 | 2.2.1 IStrategy接口 | 4.1 接口定义模块 | TASK-013-004 | 单元测试 | 未实现抽象方法时抛出TypeError |

---

### 阶段2：核心组件测试

| 测试点 ID | 关联需求 (prd.md) | 关联架构 (architecture.md) | 任务ID (tasks.md) | 测试策略 | 可量化成功标准 |
|----------|------------------|---------------------------|------------------|---------|--------------|
| TC-005 | 2.3.1 UnifiedOrderManager | 4.3 核心组件模块 | TASK-013-005 | 单元测试 | create_order()返回Order对象且id唯一 |
| TC-006 | 2.3.1 UnifiedOrderManager | 4.3 核心组件模块 | TASK-013-005 | 单元测试 | calculate_statistics()胜率计算准确 |
| TC-007 | 2.3.3 SignalConverter | 4.3 核心组件模块 | TASK-013-006 | 单元测试 | to_vectorbt_signals()精确匹配成功 |
| TC-008 | 2.3.3 SignalConverter | 4.3 核心组件模块 | TASK-013-006 | 单元测试 | 时间戳不存在时抛出ValueError |
| TC-009 | 2.3.2 StrategyAdapter | 4.3 核心组件模块 | TASK-013-007 | 单元测试 | adapt_for_backtest()返回完整数据结构 |

---

### 阶段3：DDPS-Z适配测试

| 测试点 ID | 关联需求 (prd.md) | 关联架构 (architecture.md) | 任务ID (tasks.md) | 测试策略 | 可量化成功标准 |
|----------|------------------|---------------------------|------------------|---------|--------------|
| TC-010 | 2.4 DDPS-Z适配 | 4.4 应用适配模块 | TASK-013-008 | 单元测试 | generate_buy_signals()格式转换正确 |
| TC-011 | 2.4 DDPS-Z适配 | 4.4 应用适配模块 | TASK-013-008 | 单元测试 | generate_sell_signals()实现EMA25逻辑 |
| TC-012 | 2.4 DDPS-Z适配 | 回测层组件 | TASK-013-009 | 集成测试 | 回测结果与OrderTracker差异<5% |

---

### 阶段4：端到端测试

| 测试点 ID | 关联需求 (prd.md) | 关联架构 (architecture.md) | 任务ID (tasks.md) | 测试策略 | 可量化成功标准 |
|----------|------------------|---------------------------|------------------|---------|--------------|
| TC-013 | 完整回测流程 | 端到端集成 | TASK-013-013 | E2E测试 | DDPS-Z策略→适配器→回测引擎流程通过 |
| TC-014 | 完整回测流程 | 端到端集成 | TASK-013-013 | E2E测试 | BacktestResult包含夏普比率等指标 |

---

## 详细测试用例设计

### TC-002: OrderStatus枚举测试

**测试文件**: `strategy_adapter/tests/test_enums.py`

```python
def test_order_status_enum_values():
    """测试OrderStatus枚举包含正确的4个状态

    验收标准：
    - OrderStatus.PENDING.value == "pending"
    - OrderStatus.FILLED.value == "filled"
    - OrderStatus.CLOSED.value == "closed"
    - OrderStatus.CANCELLED.value == "cancelled"
    """
    assert OrderStatus.PENDING.value == "pending"
    assert OrderStatus.FILLED.value == "filled"
    assert OrderStatus.CLOSED.value == "closed"
    assert OrderStatus.CANCELLED.value == "cancelled"

def test_order_status_invalid_access_raises_attribute_error():
    """异常路径：无效枚举值访问时抛出AttributeError

    Fail-Fast验证：确保访问不存在的枚举值时立即失败
    """
    with pytest.raises(AttributeError):
        _ = OrderStatus.INVALID_STATUS
```

---

### TC-003: Order数据类盈亏计算测试

**测试文件**: `strategy_adapter/tests/test_order.py`

```python
def test_order_calculate_pnl_buy_side_profit():
    """测试做多订单盈利计算

    场景：
    - 买入价格：2300 USDT
    - 卖出价格：2350 USDT
    - 数量：0.04348 (100 USDT / 2300)
    - 预期盈利：约2.174 USDT（扣除手续费前）
    """
    order = Order(
        id="test_order_1",
        symbol="ETHUSDT",
        side=OrderSide.BUY,
        status=OrderStatus.CLOSED,
        open_timestamp=1736164800000,
        open_price=Decimal("2300"),
        quantity=Decimal("0.04348"),
        position_value=Decimal("100"),
        close_timestamp=1736230800000,
        close_price=Decimal("2350"),
        open_commission=Decimal("0.1"),
        close_commission=Decimal("0.102")
    )

    order.calculate_pnl()

    assert order.profit_loss is not None
    assert order.profit_loss > 0  # 盈利
    assert abs(order.profit_loss - Decimal("1.972")) < Decimal("0.01")  # 允许小误差

def test_order_calculate_pnl_when_close_price_is_none():
    """异常路径：close_price为None时calculate_pnl()不报错

    Fail-Fast验证：确保未平仓订单调用calculate_pnl()不会崩溃
    """
    order = Order(
        id="test_order_2",
        symbol="ETHUSDT",
        side=OrderSide.BUY,
        status=OrderStatus.FILLED,  # 持仓中
        open_timestamp=1736164800000,
        open_price=Decimal("2300"),
        quantity=Decimal("0.04348"),
        position_value=Decimal("100"),
        close_price=None  # 未平仓
    )

    # 应该不抛出异常
    order.calculate_pnl()
    assert order.profit_loss is None  # 盈亏应为None

def test_order_calculate_pnl_division_by_zero_handling():
    """异常路径：position_value为0时的除零处理

    Fail-Fast验证：确保除零情况被正确处理
    """
    order = Order(
        id="test_order_3",
        symbol="ETHUSDT",
        side=OrderSide.BUY,
        status=OrderStatus.CLOSED,
        open_timestamp=1736164800000,
        open_price=Decimal("2300"),
        quantity=Decimal("0"),
        position_value=Decimal("0"),  # 异常情况
        close_timestamp=1736230800000,
        close_price=Decimal("2350")
    )

    order.calculate_pnl()
    # 应该优雅处理，不崩溃
    assert order.profit_loss_rate is None or order.profit_loss_rate == 0
```

---

### TC-005: UnifiedOrderManager订单创建测试

**测试文件**: `strategy_adapter/tests/test_unified_order_manager.py`

```python
def test_create_order_success():
    """测试订单创建成功

    验收标准：
    - 返回Order对象
    - order.id格式为"order_{timestamp}"
    - order.status == OrderStatus.FILLED
    - order.position_value == 100 (固定100 USDT)
    """
    manager = UnifiedOrderManager()
    signal = {
        'timestamp': 1736164800000,
        'price': 2300.50,
        'reason': 'EMA斜率未来预测',
        'confidence': 0.85
    }

    # Mock strategy
    strategy = Mock(spec=IStrategy)
    strategy.calculate_position_size.return_value = Decimal("100")
    strategy.get_strategy_name.return_value = "DDPS-Z"

    order = manager.create_order(
        signal=signal,
        strategy=strategy,
        current_price=Decimal("2300.50"),
        available_capital=Decimal("10000")
    )

    assert isinstance(order, Order)
    assert order.id == "order_1736164800000"
    assert order.status == OrderStatus.FILLED
    assert order.position_value == Decimal("100")

def test_create_order_invalid_signal_raises_key_error():
    """异常路径：signal缺少必要字段时触发KeyError

    Fail-Fast验证：确保无效signal立即失败
    """
    manager = UnifiedOrderManager()
    invalid_signal = {
        'timestamp': 1736164800000
        # 缺少 'price' 字段
    }

    strategy = Mock(spec=IStrategy)

    with pytest.raises(KeyError) as exc_info:
        manager.create_order(
            signal=invalid_signal,
            strategy=strategy,
            current_price=Decimal("2300"),
            available_capital=Decimal("10000")
        )

    assert 'price' in str(exc_info.value)  # 错误信息包含缺失字段名
```

---

### TC-007: SignalConverter精确匹配测试

**测试文件**: `strategy_adapter/tests/test_signal_converter.py`

```python
def test_to_vectorbt_signals_exact_match_success():
    """测试精确匹配成功场景

    验收标准：
    - 返回(entries, exits)元组
    - entries为pd.Series，index与klines一致
    - 信号时间戳精确匹配K线index
    """
    # 准备测试数据
    klines = pd.DataFrame({
        'open': [2300, 2310, 2320],
        'close': [2310, 2320, 2330]
    }, index=pd.DatetimeIndex([
        '2026-01-06 00:00:00',
        '2026-01-06 04:00:00',
        '2026-01-06 08:00:00'
    ], tz='UTC'))

    buy_signals = [{
        'timestamp': int(pd.Timestamp('2026-01-06 04:00:00', tz='UTC').timestamp() * 1000),
        'price': 2310
    }]

    entries, exits = SignalConverter.to_vectorbt_signals(
        buy_signals=buy_signals,
        sell_signals=[],
        klines=klines
    )

    assert isinstance(entries, pd.Series)
    assert len(entries) == len(klines)
    assert entries.sum() == 1  # 只有1个买入信号
    assert entries.iloc[1] == True  # 第二根K线

def test_to_vectorbt_signals_exact_match_failure_raises_value_error():
    """异常路径：信号时间戳不存在时抛出ValueError

    Fail-Fast验证：确保时间戳不匹配时立即失败，提供清晰错误信息
    """
    klines = pd.DataFrame({
        'open': [2300],
        'close': [2310]
    }, index=pd.DatetimeIndex(['2026-01-06 00:00:00'], tz='UTC'))

    buy_signals = [{
        'timestamp': 9999999999999,  # 不存在的时间戳
        'price': 2310
    }]

    with pytest.raises(ValueError) as exc_info:
        SignalConverter.to_vectorbt_signals(
            buy_signals=buy_signals,
            sell_signals=[],
            klines=klines
        )

    error_message = str(exc_info.value)
    assert "在K线数据中不存在" in error_message
    assert "请检查" in error_message  # 包含修复建议

def test_to_vectorbt_signals_invalid_index_raises_type_error():
    """异常路径：klines.index不是DatetimeIndex时抛出TypeError

    Fail-Fast验证：确保数据类型错误时立即失败
    """
    klines = pd.DataFrame({
        'open': [2300],
        'close': [2310]
    }, index=[0])  # 使用整数index而非DatetimeIndex

    buy_signals = [{
        'timestamp': 1736164800000,
        'price': 2310
    }]

    with pytest.raises(TypeError):
        SignalConverter.to_vectorbt_signals(
            buy_signals=buy_signals,
            sell_signals=[],
            klines=klines
        )
```

---

### TC-010: DDPSZStrategy信号格式转换测试

**测试文件**: `strategy_adapter/tests/test_ddpsz_strategy.py`

```python
def test_generate_buy_signals_format_conversion():
    """测试买入信号格式转换

    验收标准：
    - BuySignalCalculator返回格式 → IStrategy要求格式
    - 包含timestamp、price、reason、confidence、strategy_id
    """
    strategy = DDPSZStrategy()

    # Mock BuySignalCalculator返回
    with patch('strategy_adapter.adapters.ddpsz_adapter.BuySignalCalculator') as MockCalc:
        mock_calculator = MockCalc.return_value
        mock_calculator.calculate.return_value = [{
            'timestamp': 1736164800000,
            'buy_price': 2300.50,
            'strategies': [{
                'id': 'strategy_1',
                'name': 'EMA斜率未来预测',
                'triggered': True
            }]
        }]

        klines = create_test_klines()
        indicators = {'ema25': create_test_ema25()}

        signals = strategy.generate_buy_signals(klines, indicators)

        assert len(signals) == 1
        signal = signals[0]
        assert signal['timestamp'] == 1736164800000
        assert signal['price'] == Decimal("2300.50")
        assert signal['reason'] == 'EMA斜率未来预测'
        assert 'confidence' in signal
        assert signal['strategy_id'] == 'strategy_1'

def test_generate_sell_signals_ema25_reversion_logic():
    """测试EMA25回归卖出逻辑

    验收标准：
    - 条件：kline['low'] <= ema25 <= kline['high']
    - 正确生成卖出信号
    """
    strategy = DDPSZStrategy()

    # 准备测试数据：第3根K线包含EMA25
    klines = pd.DataFrame({
        'low': [2300, 2310, 2295],
        'high': [2310, 2320, 2305],
        'close': [2305, 2315, 2300]
    }, index=pd.DatetimeIndex([
        '2026-01-06 00:00:00',
        '2026-01-06 04:00:00',
        '2026-01-06 08:00:00'
    ], tz='UTC'))

    ema25 = pd.Series([2305, 2310, 2300], index=klines.index)
    indicators = {'ema25': ema25}

    # 模拟一个持仓订单（在第1根K线买入）
    open_orders = [Order(
        id="order_test",
        symbol="ETHUSDT",
        side=OrderSide.BUY,
        status=OrderStatus.FILLED,
        open_timestamp=int(klines.index[0].timestamp() * 1000),
        open_price=Decimal("2305"),
        quantity=Decimal("0.04348"),
        position_value=Decimal("100")
    )]

    sell_signals = strategy.generate_sell_signals(klines, indicators, open_orders)

    assert len(sell_signals) == 1
    signal = sell_signals[0]
    assert signal['order_id'] == "order_test"
    assert signal['reason'] == 'EMA25回归'
    assert signal['price'] == Decimal("2300")  # EMA25值

def test_generate_sell_signals_missing_indicators_raises_key_error():
    """异常路径：indicators缺少ema25时触发KeyError

    Fail-Fast验证：确保缺少必要指标时立即失败
    """
    strategy = DDPSZStrategy()

    klines = create_test_klines()
    indicators = {}  # 缺少ema25
    open_orders = []

    with pytest.raises(KeyError) as exc_info:
        strategy.generate_sell_signals(klines, indicators, open_orders)

    assert 'ema25' in str(exc_info.value)
```

---

### TC-012: DDPS-Z回测结果一致性测试

**测试文件**: `strategy_adapter/tests/test_integration.py`

```python
def test_ddpsz_backtest_result_accuracy_vs_ordertracker():
    """集成测试：DDPS-Z适配层回测结果与OrderTracker对比

    验收标准：
    - 订单数量差异 < 5%
    - 总盈亏差异 < 5%
    - 胜率差异 < 5%

    测试场景：使用ETHUSDT 4h数据（180天）
    """
    # 1. 准备测试数据
    klines = load_test_klines("ETHUSDT", "4h", days=180)
    ema25 = calculate_ema(klines['close'], 25)
    indicators = {'ema25': ema25}

    # 2. 运行OrderTracker（基准）
    tracker = OrderTracker()
    tracker_result = tracker.track(klines, indicators)

    # 3. 运行适配层回测
    strategy = DDPSZStrategy()
    adapter = StrategyAdapter(strategy)
    adapter_result = adapter.adapt_for_backtest(klines, indicators)

    # 4. 对比订单数量
    tracker_order_count = tracker_result.total_orders
    adapter_order_count = len(adapter_result['orders'])

    order_count_diff = abs(adapter_order_count - tracker_order_count) / tracker_order_count
    assert order_count_diff < 0.05, f"订单数量差异 {order_count_diff:.2%} 超过5%"

    # 5. 对比总盈亏
    tracker_total_profit = tracker_result.total_profit
    adapter_total_profit = adapter_result['statistics']['total_profit']

    profit_diff = abs(adapter_total_profit - tracker_total_profit) / abs(tracker_total_profit)
    assert profit_diff < 0.05, f"总盈亏差异 {profit_diff:.2%} 超过5%"

    # 6. 对比胜率
    tracker_win_rate = tracker_result.win_rate
    adapter_win_rate = adapter_result['statistics']['win_rate']

    win_rate_diff = abs(adapter_win_rate - tracker_win_rate) / tracker_win_rate
    assert win_rate_diff < 0.05, f"胜率差异 {win_rate_diff:.2%} 超过5%"
```

---

## 测试覆盖率目标

| 模块 | 目标覆盖率 | 关键指标 |
|------|-----------|---------|
| strategy_adapter/models/ | ≥ 90% | 数据类逻辑全覆盖 |
| strategy_adapter/core/ | ≥ 85% | 核心组件高覆盖 |
| strategy_adapter/adapters/ | ≥ 80% | 适配器逻辑覆盖 |
| **整体覆盖率** | **≥ 80%** | **P0验收标准** |

---

## Fail-Fast测试清单

每个P0任务都必须包含以下异常路径测试：

- ✅ TC-002: 无效枚举值访问 → AttributeError
- ✅ TC-003: close_price为None → 不崩溃
- ✅ TC-003: position_value为0 → 除零处理
- ✅ TC-004: 未实现抽象方法 → TypeError
- ✅ TC-005: signal缺少字段 → KeyError
- ✅ TC-007: 时间戳不存在 → ValueError
- ✅ TC-007: index类型错误 → TypeError
- ✅ TC-010: indicators缺少ema25 → KeyError

---

## 文档化测试标准

每个测试用例必须包含：

1. **Docstring**（Google Style）：
   - 测试目的
   - 测试场景
   - 验收标准

2. **Fail-Fast说明**（异常测试）：
   - 触发条件
   - 预期异常类型
   - 错误信息验证

3. **可追溯性标记**：
   - 关联任务ID (TASK-013-xxx)
   - 关联需求点 (prd.md)

---

**文档状态**: ✅ 测试规格设计完成
**关联文档**: tasks.md, prd.md, architecture.md
**下一步**: 开始执行文档驱动TDD实现流程
