"""
网格生命周期集成测试
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, MagicMock

from grid_trading.models import (
    GridConfig, GridLevel, GridLevelStatus,
    OrderIntent, OrderIntentType, OrderSide, OrderStatus
)
from grid_trading.services.grid.engine import GridEngine


@pytest.fixture
def grid_config(db, grid_config_data):
    """创建测试用网格配置"""
    return GridConfig.objects.create(**grid_config_data)


@pytest.fixture
def mock_exchange():
    """模拟交易所适配器"""
    exchange = Mock()

    # 使用计数器生成唯一订单ID
    order_counter = {'count': 0}

    def create_order_side_effect(**kwargs):
        order_counter['count'] += 1
        return {
            'orderId': f"order_{order_counter['count']}",
            'status': 'NEW'
        }

    exchange.create_order = MagicMock(side_effect=create_order_side_effect)
    exchange.cancel_order = MagicMock(return_value={
        'orderId': '12345678',
        'status': 'CANCELED'
    })
    return exchange


@pytest.mark.django_db
class TestGridLifecycle:
    """网格生命周期测试"""

    def test_start_engine(self, grid_config, mock_exchange):
        """测试启动引擎"""
        engine = GridEngine(grid_config, mock_exchange)
        engine.start()

        assert engine.running is True
        assert engine.strategy is not None
        assert engine.order_sync_manager is not None

        # 验证网格已初始化
        levels = GridLevel.objects.filter(config=grid_config)
        assert levels.count() == 20

    def test_stop_engine(self, grid_config, mock_exchange):
        """测试停止引擎"""
        engine = GridEngine(grid_config, mock_exchange)
        engine.start()
        engine.stop()

        assert engine.running is False

    def test_tick_creates_orders(self, grid_config, mock_exchange):
        """测试tick创建订单"""
        engine = GridEngine(grid_config, mock_exchange)
        engine.start()

        # 执行一次tick
        result = engine.tick()

        # 应该创建了一些订单（上方的卖单）
        assert result['created_orders_count'] > 0
        assert result['current_position'] == Decimal('0')

        # 验证OrderIntent已创建
        intents = OrderIntent.objects.filter(config=grid_config)
        assert intents.count() == result['created_orders_count']

    def test_tick_idempotent(self, grid_config, mock_exchange):
        """测试tick幂等性"""
        engine = GridEngine(grid_config, mock_exchange)
        engine.start()

        # 第一次tick - 创建开仓单
        result1 = engine.tick()
        created_count_1 = result1['created_orders_count']
        assert created_count_1 > 0

        # 第二次tick（相同状态）
        result2 = engine.tick()

        # 不应该重复创建或撤销订单（working状态的订单应该在理想订单中）
        assert result2['created_orders_count'] == 0
        assert result2['cancelled_orders_count'] == 0

        # 总订单数应该等于第一次创建的
        total_intents = OrderIntent.objects.filter(
            config=grid_config,
            status__in=[OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED]
        ).count()
        assert total_intents == created_count_1

    def test_on_order_filled_entry(self, grid_config, mock_exchange):
        """测试处理开仓单成交"""
        engine = GridEngine(grid_config, mock_exchange)
        engine.start()
        engine.tick()

        # 获取一个开仓订单（选择特定层级）
        entry_intent = OrderIntent.objects.filter(
            config=grid_config,
            intent=OrderIntentType.ENTRY,
            status=OrderStatus.NEW,
            level_index=1  # 指定层级
        ).first()

        assert entry_intent is not None

        # 模拟成交
        engine.on_order_filled(entry_intent.order_id, OrderIntentType.ENTRY)

        # 验证OrderIntent状态更新
        entry_intent.refresh_from_db()
        assert entry_intent.status == OrderStatus.FILLED

        # 验证GridLevel状态更新
        level = GridLevel.objects.get(
            config=grid_config,
            level_index=entry_intent.level_index
        )
        assert level.status == GridLevelStatus.POSITION_OPEN

    def test_on_order_filled_exit(self, grid_config, mock_exchange):
        """测试处理平仓单成交"""
        engine = GridEngine(grid_config, mock_exchange)
        engine.start()
        engine.tick()

        # 先模拟开仓成交（选择特定层级）
        entry_intent = OrderIntent.objects.filter(
            config=grid_config,
            intent=OrderIntentType.ENTRY,
            level_index=1  # 指定层级
        ).first()
        engine.on_order_filled(entry_intent.order_id, OrderIntentType.ENTRY)

        # 验证层级状态已更新
        level = GridLevel.objects.get(config=grid_config, level_index=1)
        assert level.status == GridLevelStatus.POSITION_OPEN
        print(f"Level 1 after fill: status={level.status}, side={level.side}")

        # 执行tick创建平仓单
        result = engine.tick()
        print(f"Tick result: created={result['created_orders_count']}, ideal={result['ideal_orders_count']}")

        # 查看所有OrderIntent
        all_intents = OrderIntent.objects.filter(config=grid_config, status=OrderStatus.NEW)
        print(f"All NEW intents after tick: {all_intents.count()}")
        for intent in all_intents:
            print(f"  - Level {intent.level_index}: {intent.intent} {intent.side}")

        # 获取平仓订单
        exit_intent = OrderIntent.objects.filter(
            config=grid_config,
            level_index=entry_intent.level_index,
            intent=OrderIntentType.EXIT,
            status=OrderStatus.NEW
        ).first()

        assert exit_intent is not None, "Exit intent should be created after entry is filled"

        # 模拟平仓成交
        engine.on_order_filled(exit_intent.order_id, OrderIntentType.EXIT)

        # 验证GridLevel回到idle状态
        level = GridLevel.objects.get(
            config=grid_config,
            level_index=entry_intent.level_index
        )
        assert level.status == GridLevelStatus.IDLE

    def test_full_cycle(self, grid_config, mock_exchange):
        """测试完整的开仓-平仓循环"""
        engine = GridEngine(grid_config, mock_exchange)
        engine.start()

        # 1. 初始tick - 创建开仓单
        result1 = engine.tick()
        initial_orders = result1['created_orders_count']
        assert initial_orders > 0

        # 2. 模拟第一个开仓单成交（选择特定层级）
        entry_intent = OrderIntent.objects.filter(
            config=grid_config,
            intent=OrderIntentType.ENTRY,
            level_index=1  # 指定层级
        ).first()
        engine.on_order_filled(entry_intent.order_id, OrderIntentType.ENTRY)

        # 3. 第二次tick - 创建平仓单
        result2 = engine.tick()
        assert result2['created_orders_count'] == 1  # 创建了1个平仓单

        # 4. 模拟平仓单成交
        exit_intent = OrderIntent.objects.filter(
            config=grid_config,
            level_index=entry_intent.level_index,
            intent=OrderIntentType.EXIT,
            status=OrderStatus.NEW
        ).first()
        engine.on_order_filled(exit_intent.order_id, OrderIntentType.EXIT)

        # 5. 第三次tick - 层级回到idle，应该重新创建开仓单
        result3 = engine.tick()
        assert result3['created_orders_count'] == 1  # 重新创建开仓单

        # 验证持仓已清零
        assert result3['current_position'] == Decimal('0')

    def test_position_limit_enforcement(self, grid_config, mock_exchange):
        """测试持仓限制执行"""
        engine = GridEngine(grid_config, mock_exchange)
        engine.start()

        # 持续成交直到达到持仓上限
        max_position = Decimal(str(grid_config.max_position_size))
        trade_amount = Decimal(str(grid_config.trade_amount))
        max_fills = int(max_position / trade_amount)

        filled_levels = []  # 记录已成交的层级
        for i in range(max_fills):
            # Tick
            result = engine.tick()
            if result['created_orders_count'] == 0:
                break

            # 成交一个开仓单（选择未成交的层级）
            entry_intent = OrderIntent.objects.filter(
                config=grid_config,
                intent=OrderIntentType.ENTRY,
                status=OrderStatus.NEW
            ).exclude(
                level_index__in=filled_levels
            ).first()

            if entry_intent:
                filled_levels.append(entry_intent.level_index)
                engine.on_order_filled(entry_intent.order_id, OrderIntentType.ENTRY)

        # 再次tick
        final_result = engine.tick()

        # 应该有订单被过滤
        assert final_result['filtered_orders_count'] > 0 or final_result['created_orders_count'] == 0

        # 验证持仓不超限
        final_position = abs(final_result['current_position'])
        assert final_position <= max_position

    def test_persist_grid_levels(self, grid_config, mock_exchange):
        """测试持久化网格层级"""
        engine = GridEngine(grid_config, mock_exchange)
        engine.start()

        # 执行一些操作
        engine.tick()

        # 手动触发持久化
        count = engine.persist_grid_levels()

        assert count == 20  # 20个网格层级

    def test_tick_without_start_raises_error(self, grid_config, mock_exchange):
        """测试未启动时执行tick抛出错误"""
        engine = GridEngine(grid_config, mock_exchange)

        with pytest.raises(RuntimeError, match="引擎未启动"):
            engine.tick()

    def test_start_unsupported_mode_raises_error(self, db, grid_config_data, mock_exchange):
        """测试启动不支持的网格模式抛出错误"""
        grid_config_data['grid_mode'] = 'LONG'
        config = GridConfig.objects.create(**grid_config_data)

        engine = GridEngine(config, mock_exchange)

        with pytest.raises(ValueError, match="暂不支持的网格模式"):
            engine.start()
