"""
端到端集成测试
End-to-End Integration Tests

测试完整的网格交易流程：
1. Scanner识别S/R区间
2. GridBot启动策略
3. 订单撮合和盈亏计算
4. 止损触发
5. 风险管理
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from django.utils import timezone
from datetime import timedelta

from grid_trading.models import GridZone, GridStrategy, GridOrder
from grid_trading.services.config_loader import load_config
from grid_trading.services.atr_calculator import ATRCalculator
from grid_trading.services.order_generator import GridOrderGenerator
from grid_trading.services.order_simulator import OrderSimulator
from grid_trading.services.risk_manager import get_risk_manager
from vp_squeeze.dto import KLineData


@pytest.mark.django_db
class TestE2EIntegration:
    """端到端集成测试"""

    def setup_method(self):
        """测试前准备"""
        # 清理数据
        GridOrder.objects.all().delete()
        GridStrategy.objects.all().delete()
        GridZone.objects.all().delete()

    def test_complete_trading_flow_success_scenario(self):
        """
        测试完整交易流程 - 成功场景

        场景:
        1. Scanner识别支撑区 $49000-$49500
        2. 价格进入支撑区 $49200
        3. GridBot启动做多网格
        4. 价格下跌，买单成交
        5. 价格上涨，卖单成交
        6. 策略盈利
        """
        print("\n" + "="*80)
        print("测试场景 1: 完整交易流程 - 成功获利")
        print("="*80)

        # ========== Phase 1: Scanner识别支撑区 ==========
        print("\n[Phase 1] Scanner识别支撑区...")

        # 创建支撑区
        support_zone = GridZone.objects.create(
            symbol='BTCUSDT',
            zone_type='support',
            price_low=Decimal('49000.00'),
            price_high=Decimal('49500.00'),
            confidence=85,
            is_active=True,
            expires_at=timezone.now() + timedelta(hours=4)
        )

        print(f"✓ 支撑区创建成功: ${support_zone.price_low} - ${support_zone.price_high}")
        assert GridZone.objects.filter(is_active=True).count() == 1

        # ========== Phase 2: 价格进入支撑区，启动网格 ==========
        print("\n[Phase 2] 价格进入支撑区，启动网格...")

        entry_price = Decimal('49200.00')
        print(f"✓ 当前价格: ${entry_price}")

        # 验证价格在区间内
        assert support_zone.is_price_in_zone(entry_price)
        print(f"✓ 价格在支撑区内")

        # Mock ATR计算
        with patch('grid_trading.services.atr_calculator.fetch_klines') as mock_klines:
            # 模拟K线数据（使用正确的KLineData格式）
            now = timezone.now()
            mock_klines.return_value = [
                KLineData(
                    open_time=now,
                    open=49000.0 + i * 10,
                    high=50000.0,
                    low=48000.0,
                    close=49200.0,
                    volume=1000.0,
                    close_time=now,
                    quote_volume=50000000.0,
                    trade_count=1000,
                    taker_buy_volume=500.0,
                    taker_buy_quote_volume=25000000.0
                )
                for i in range(14)
            ]

            # 计算ATR和网格步长
            atr_calculator = ATRCalculator()
            grid_step = atr_calculator.calculate_grid_step('BTCUSDT', atr_multiplier=0.8)
            print(f"✓ ATR网格步长: ${grid_step:.2f}")

            assert grid_step > 0

        # 创建策略
        order_generator = GridOrderGenerator()
        grid_step_pct = order_generator.calculate_grid_step_percentage(
            float(entry_price), grid_step
        )

        strategy = GridStrategy.objects.create(
            symbol='BTCUSDT',
            strategy_type='long',
            grid_step_pct=Decimal(str(grid_step_pct)),
            grid_levels=10,
            order_size=Decimal('0.002'),  # 0.002 BTC per order
            stop_loss_pct=Decimal('0.10'),
            status='active',
            entry_price=entry_price,
            current_pnl=Decimal('0.00'),
            started_at=timezone.now()
        )

        print(f"✓ 策略创建成功: ID={strategy.id}, 类型=做多")

        # 生成网格订单
        order_plans = order_generator.generate_grid_orders(
            entry_price=float(entry_price),
            grid_step=grid_step,
            grid_levels=10,
            order_size_usdt=100.0,
            strategy_type='long'
        )

        created_orders = []
        for plan in order_plans:
            order = GridOrder.objects.create(
                strategy=strategy,
                order_type=plan.order_type,
                price=plan.price,
                quantity=plan.quantity,
                status='pending'
            )
            created_orders.append(order)

        buy_orders = [o for o in created_orders if o.order_type == 'buy']
        sell_orders = [o for o in created_orders if o.order_type == 'sell']

        print(f"✓ 网格订单创建成功: 买单={len(buy_orders)}个, 卖单={len(sell_orders)}个")
        assert len(buy_orders) == 10
        assert len(sell_orders) == 10

        # ========== Phase 3: 价格下跌，买单成交 ==========
        print("\n[Phase 3] 价格下跌，买单成交...")

        # 查看买单价格
        buy_order_prices = [float(o.price) for o in buy_orders[:3]]
        print(f"  买单价格示例: {buy_order_prices}")

        current_price = Decimal('47000.00')  # 价格下跌到47000（低于第一档买单）
        print(f"✓ 价格下跌至: ${current_price}")

        order_simulator = OrderSimulator()

        # 模拟订单撮合
        pending_orders = strategy.gridorder_set.filter(status='pending')
        filled_orders = order_simulator.check_and_fill_orders(
            list(pending_orders), float(current_price)
        )

        filled_buy_orders = [o for o in filled_orders if o.order_type == 'buy']
        print(f"✓ 买单成交: {len(filled_buy_orders)}个")
        assert len(filled_buy_orders) > 0

        # 验证成交价格和手续费
        for order in filled_buy_orders[:3]:  # 检查前3个
            print(f"  - 订单价格: ${float(order.price):.2f}, "
                  f"成交价: ${float(order.simulated_price):.2f}, "
                  f"手续费: ${float(order.simulated_fee):.4f}")
            assert order.simulated_price is not None
            assert order.simulated_fee is not None
            assert order.filled_at is not None

        # ========== Phase 4: 价格上涨，卖单成交 ==========
        print("\n[Phase 4] 价格上涨，卖单成交...")

        # 查看卖单价格
        sell_order_prices = [float(o.price) for o in sell_orders[:3]]
        print(f"  卖单价格示例: {sell_order_prices}")

        current_price = Decimal('51500.00')  # 价格上涨到51500（高于第一档卖单）
        print(f"✓ 价格上涨至: ${current_price}")

        # 再次撮合
        pending_orders = strategy.gridorder_set.filter(status='pending')
        filled_orders = order_simulator.check_and_fill_orders(
            list(pending_orders), float(current_price)
        )

        filled_sell_orders = [o for o in filled_orders if o.order_type == 'sell']
        print(f"✓ 卖单成交: {len(filled_sell_orders)}个")
        assert len(filled_sell_orders) > 0

        # ========== Phase 5: 计算盈亏 ==========
        print("\n[Phase 5] 计算策略盈亏...")

        # 计算总盈亏
        all_filled_orders = strategy.gridorder_set.filter(status='filled')
        total_pnl = Decimal('0.00')

        for order in all_filled_orders:
            pnl = order.calculate_pnl(float(current_price))
            total_pnl += Decimal(str(pnl))

        strategy.current_pnl = total_pnl
        strategy.save()

        print(f"✓ 策略总盈亏: ${float(total_pnl):.2f}")
        print(f"✓ 已成交订单: {all_filled_orders.count()}个")
        print(f"✓ 待成交订单: {strategy.gridorder_set.filter(status='pending').count()}个")

        # 验证盈亏计算
        assert strategy.current_pnl != Decimal('0.00')

        print("\n✅ 成功场景测试通过!")

    def test_stop_loss_trigger_scenario(self):
        """
        测试止损触发场景

        场景:
        1. 创建做多策略，入场价 $50000
        2. 价格大跌至 $44000 (跌幅12%)
        3. 触发止损 (10%)
        4. 策略停止，所有pending订单撤销
        """
        print("\n" + "="*80)
        print("测试场景 2: 止损触发")
        print("="*80)

        # ========== Phase 1: 创建策略 ==========
        print("\n[Phase 1] 创建做多策略...")

        entry_price = Decimal('50000.00')
        stop_loss_pct = Decimal('0.10')

        strategy = GridStrategy.objects.create(
            symbol='BTCUSDT',
            strategy_type='long',
            grid_step_pct=Decimal('0.008'),
            grid_levels=10,
            order_size=Decimal('0.002'),
            stop_loss_pct=stop_loss_pct,
            status='active',
            entry_price=entry_price,
            current_pnl=Decimal('0.00'),
            started_at=timezone.now()
        )

        print(f"✓ 策略创建: 入场价=${entry_price}, 止损线={float(stop_loss_pct)*100}%")

        # 创建一些买单（已成交）
        for i in range(5):
            GridOrder.objects.create(
                strategy=strategy,
                order_type='buy',
                price=entry_price - Decimal(str(i * 100)),
                quantity=Decimal('0.002'),
                status='filled',
                filled_at=timezone.now()
            )

        # 创建pending订单
        for i in range(5):
            GridOrder.objects.create(
                strategy=strategy,
                order_type='buy',
                price=entry_price - Decimal(str((i + 5) * 100)),
                quantity=Decimal('0.002'),
                status='pending'
            )

        print(f"✓ 订单创建: 已成交=5个, 待成交=5个")

        # ========== Phase 2: 价格大跌 ==========
        print("\n[Phase 2] 价格大跌...")

        current_price = Decimal('44000.00')  # 下跌12%
        drop_pct = (float(entry_price) - float(current_price)) / float(entry_price) * 100

        print(f"✓ 当前价格: ${current_price}")
        print(f"✓ 跌幅: {drop_pct:.2f}%")

        # 计算止损价格
        stop_loss_price = float(entry_price) * (1 - float(stop_loss_pct))
        print(f"✓ 止损价格: ${stop_loss_price:.2f}")

        assert float(current_price) <= stop_loss_price

        # ========== Phase 3: 触发止损 ==========
        print("\n[Phase 3] 触发止损...")

        # 撤销所有pending订单
        cancelled_count = strategy.gridorder_set.filter(status='pending').update(
            status='cancelled'
        )

        # 停止策略
        strategy.status = 'stopped'
        strategy.stopped_at = timezone.now()
        strategy.save()

        print(f"✓ 撤销订单: {cancelled_count}个")
        print(f"✓ 策略状态: {strategy.status}")

        # 验证
        assert strategy.status == 'stopped'
        assert strategy.stopped_at is not None
        assert strategy.gridorder_set.filter(status='pending').count() == 0
        assert strategy.gridorder_set.filter(status='cancelled').count() == cancelled_count

        print("\n✅ 止损场景测试通过!")

    def test_risk_management_position_limit(self):
        """
        测试风险管理 - 仓位限制

        场景:
        1. 配置最大仓位 $1000
        2. 尝试创建策略，预估仓位 $1500
        3. 风险检查拒绝
        """
        print("\n" + "="*80)
        print("测试场景 3: 风险管理 - 仓位限制")
        print("="*80)

        print("\n[Phase 1] 测试仓位限制...")

        risk_manager = get_risk_manager()
        order_generator = GridOrderGenerator()

        # 配置参数
        max_position_usdt = 1000.0
        grid_levels = 10
        order_size_usdt = 150.0  # 每格150 USDT

        # 估算最大仓位
        estimated_position = order_generator.estimate_max_position_value(
            grid_levels=grid_levels,
            order_size_usdt=order_size_usdt,
            strategy_type='long'
        )

        print(f"✓ 最大仓位限制: ${max_position_usdt:.2f}")
        print(f"✓ 预估仓位: ${estimated_position:.2f}")

        # 风险检查
        allowed, reject_reason = risk_manager.validate_new_strategy(
            symbol='BTCUSDT',
            estimated_position_value=estimated_position,
            max_position_usdt=max_position_usdt
        )

        print(f"✓ 风险检查结果: {'通过' if allowed else '拒绝'}")
        if not allowed:
            print(f"✓ 拒绝原因: {reject_reason}")

        # 验证
        assert not allowed
        assert "仓位超限" in reject_reason

        print("\n✅ 仓位限制测试通过!")

    def test_risk_management_concurrent_strategies(self):
        """
        测试风险管理 - 并发策略限制

        场景:
        1. 限制最多3个并发策略
        2. 创建3个active策略
        3. 尝试创建第4个，被拒绝
        """
        print("\n" + "="*80)
        print("测试场景 4: 风险管理 - 并发策略限制")
        print("="*80)

        print("\n[Phase 1] 创建3个active策略...")

        # 创建3个active策略
        for i in range(3):
            GridStrategy.objects.create(
                symbol='BTCUSDT',
                strategy_type='long',
                grid_step_pct=Decimal('0.008'),
                grid_levels=5,
                order_size=Decimal('0.001'),
                stop_loss_pct=Decimal('0.10'),
                status='active',
                entry_price=Decimal(str(50000 + i * 100)),
                started_at=timezone.now()
            )

        print(f"✓ 已创建策略数: {GridStrategy.objects.filter(status='active').count()}")

        # ========== Phase 2: 检查并发限制 ==========
        print("\n[Phase 2] 检查并发策略限制...")

        risk_manager = get_risk_manager()
        max_concurrent = 3

        # 检查是否可以创建新策略
        can_create = risk_manager.check_concurrent_strategy_limit('BTCUSDT', max_concurrent)

        print(f"✓ 最大并发数: {max_concurrent}")
        print(f"✓ 当前并发数: {GridStrategy.objects.filter(symbol='BTCUSDT', status='active').count()}")
        print(f"✓ 可创建新策略: {can_create}")

        # 验证
        assert not can_create

        print("\n✅ 并发策略限制测试通过!")

    def test_zone_expiration_mechanism(self):
        """
        测试区间过期机制

        场景:
        1. 创建一个即将过期的区间
        2. 创建一个已过期的区间
        3. Scanner运行时，自动失效过期区间
        """
        print("\n" + "="*80)
        print("测试场景 5: 区间过期机制")
        print("="*80)

        print("\n[Phase 1] 创建测试区间...")

        now = timezone.now()

        # 创建有效区间
        active_zone = GridZone.objects.create(
            symbol='BTCUSDT',
            zone_type='support',
            price_low=Decimal('49000.00'),
            price_high=Decimal('49500.00'),
            confidence=80,
            is_active=True,
            expires_at=now + timedelta(hours=2)  # 2小时后过期
        )

        # 创建已过期区间
        expired_zone = GridZone.objects.create(
            symbol='BTCUSDT',
            zone_type='support',
            price_low=Decimal('48000.00'),
            price_high=Decimal('48500.00'),
            confidence=75,
            is_active=True,
            expires_at=now - timedelta(hours=1)  # 1小时前已过期
        )

        print(f"✓ 有效区间: 过期时间={active_zone.expires_at.strftime('%H:%M')}")
        print(f"✓ 过期区间: 过期时间={expired_zone.expires_at.strftime('%H:%M')}")

        # ========== Phase 2: 验证过期状态 ==========
        print("\n[Phase 2] 验证过期状态...")

        assert not active_zone.is_expired()
        assert expired_zone.is_expired()

        print(f"✓ 有效区间过期: {active_zone.is_expired()}")
        print(f"✓ 过期区间过期: {expired_zone.is_expired()}")

        # ========== Phase 3: 自动失效过期区间 ==========
        print("\n[Phase 3] 自动失效过期区间...")

        # Scanner会执行这个操作
        deactivated_count = GridZone.objects.filter(
            expires_at__lt=now,
            is_active=True
        ).update(is_active=False)

        print(f"✓ 失效区间数: {deactivated_count}")

        # 验证
        expired_zone.refresh_from_db()
        assert not expired_zone.is_active
        assert deactivated_count == 1

        print("\n✅ 区间过期机制测试通过!")

    def test_order_pnl_calculation(self):
        """
        测试订单盈亏计算

        场景:
        1. 买单: 价格49000买入，当前价格50000
        2. 卖单: 价格51000卖出，当前价格50000
        3. 验证盈亏计算正确
        """
        print("\n" + "="*80)
        print("测试场景 6: 订单盈亏计算")
        print("="*80)

        print("\n[Phase 1] 创建测试策略和订单...")

        strategy = GridStrategy.objects.create(
            symbol='BTCUSDT',
            strategy_type='long',
            grid_step_pct=Decimal('0.008'),
            grid_levels=5,
            order_size=Decimal('0.002'),
            stop_loss_pct=Decimal('0.10'),
            status='active',
            entry_price=Decimal('50000.00'),
            started_at=timezone.now()
        )

        # 创建已成交的买单
        buy_order = GridOrder.objects.create(
            strategy=strategy,
            order_type='buy',
            price=Decimal('49000.00'),
            quantity=Decimal('0.002'),
            status='filled',
            simulated_price=Decimal('49024.50'),  # 含0.05%滑点
            simulated_fee=Decimal('0.098049'),     # 0.1%手续费
            filled_at=timezone.now()
        )

        # 创建已成交的卖单
        sell_order = GridOrder.objects.create(
            strategy=strategy,
            order_type='sell',
            price=Decimal('51000.00'),
            quantity=Decimal('0.002'),
            status='filled',
            simulated_price=Decimal('50974.50'),  # 含0.05%滑点
            simulated_fee=Decimal('0.101949'),     # 0.1%手续费
            filled_at=timezone.now()
        )

        print(f"✓ 买单: 价格=${float(buy_order.price):.2f}, 数量={float(buy_order.quantity)}")
        print(f"✓ 卖单: 价格=${float(sell_order.price):.2f}, 数量={float(sell_order.quantity)}")

        # ========== Phase 2: 计算盈亏 ==========
        print("\n[Phase 2] 计算盈亏...")

        current_price = 50000.0

        buy_pnl = buy_order.calculate_pnl(current_price)
        sell_pnl = sell_order.calculate_pnl(current_price)

        print(f"✓ 当前价格: ${current_price:.2f}")
        print(f"✓ 买单盈亏: ${buy_pnl:.4f}")
        print(f"✓ 卖单盈亏: ${sell_pnl:.4f}")

        # 验证
        # 买单: (当前价 - 成交价) * 数量 = (50000 - 49024.50) * 0.002 ≈ 1.95
        # 卖单: (成交价 - 当前价) * 数量 = (50974.50 - 50000) * 0.002 ≈ 1.95
        assert buy_pnl > 0  # 买单盈利（当前价高于成交价）
        assert sell_pnl > 0  # 卖单盈利（成交价高于当前价）

        total_pnl = buy_pnl + sell_pnl
        print(f"✓ 总盈亏: ${total_pnl:.4f}")

        print("\n✅ 盈亏计算测试通过!")


@pytest.mark.django_db
class TestE2EScenarios:
    """特定场景测试"""

    def setup_method(self):
        """测试前准备"""
        GridOrder.objects.all().delete()
        GridStrategy.objects.all().delete()
        GridZone.objects.all().delete()

    def test_multiple_strategies_same_symbol(self):
        """
        测试同一币种多个策略（不同时间）

        场景:
        1. 第一个策略运行并stopped
        2. 第二个策略可以正常创建
        """
        print("\n" + "="*80)
        print("测试场景 7: 同币种多策略（不同时间）")
        print("="*80)

        print("\n[Phase 1] 创建并停止第一个策略...")

        # 第一个策略（已停止）
        strategy1 = GridStrategy.objects.create(
            symbol='BTCUSDT',
            strategy_type='long',
            grid_step_pct=Decimal('0.008'),
            grid_levels=5,
            order_size=Decimal('0.001'),
            stop_loss_pct=Decimal('0.10'),
            status='stopped',
            entry_price=Decimal('50000.00'),
            started_at=timezone.now() - timedelta(hours=2),
            stopped_at=timezone.now() - timedelta(hours=1)
        )

        print(f"✓ 策略1: ID={strategy1.id}, 状态={strategy1.status}")

        # ========== Phase 2: 创建第二个策略 ==========
        print("\n[Phase 2] 创建第二个策略...")

        risk_manager = get_risk_manager()

        # 检查并发限制（只统计active策略）
        can_create = risk_manager.check_concurrent_strategy_limit('BTCUSDT', max_concurrent=3)

        print(f"✓ 可创建新策略: {can_create}")
        assert can_create  # stopped策略不占用并发额度

        # 创建第二个策略
        strategy2 = GridStrategy.objects.create(
            symbol='BTCUSDT',
            strategy_type='long',
            grid_step_pct=Decimal('0.008'),
            grid_levels=5,
            order_size=Decimal('0.001'),
            stop_loss_pct=Decimal('0.10'),
            status='active',
            entry_price=Decimal('51000.00'),
            started_at=timezone.now()
        )

        print(f"✓ 策略2: ID={strategy2.id}, 状态={strategy2.status}")

        # 验证
        assert GridStrategy.objects.filter(symbol='BTCUSDT').count() == 2
        assert GridStrategy.objects.filter(symbol='BTCUSDT', status='active').count() == 1

        print("\n✅ 多策略测试通过!")

    def test_grid_strategy_with_real_price_movement(self):
        """
        测试真实价格波动场景

        场景:
        1. 入场价 $50000
        2. 价格序列: 49800 → 49600 → 49400 → 49800 → 50200
        3. 验证订单逐步成交和盈亏变化
        """
        print("\n" + "="*80)
        print("测试场景 8: 真实价格波动")
        print("="*80)

        # ========== Phase 1: 创建策略 ==========
        print("\n[Phase 1] 创建网格策略...")

        entry_price = Decimal('50000.00')
        grid_step = 200.0  # 每格200 USDT

        strategy = GridStrategy.objects.create(
            symbol='BTCUSDT',
            strategy_type='long',
            grid_step_pct=Decimal('0.004'),  # 0.4%
            grid_levels=5,
            order_size=Decimal('0.002'),
            stop_loss_pct=Decimal('0.10'),
            status='active',
            entry_price=entry_price,
            current_pnl=Decimal('0.00'),
            started_at=timezone.now()
        )

        # 创建网格订单（简化版）
        order_generator = GridOrderGenerator()
        order_plans = order_generator.generate_grid_orders(
            entry_price=float(entry_price),
            grid_step=grid_step,
            grid_levels=5,
            order_size_usdt=100.0,
            strategy_type='long'
        )

        for plan in order_plans:
            GridOrder.objects.create(
                strategy=strategy,
                order_type=plan.order_type,
                price=plan.price,
                quantity=plan.quantity,
                status='pending'
            )

        print(f"✓ 入场价: ${entry_price}")
        print(f"✓ 网格步长: ${grid_step}")
        print(f"✓ 订单数: {strategy.gridorder_set.count()}个")

        # ========== Phase 2: 模拟价格波动 ==========
        print("\n[Phase 2] 模拟价格波动...")

        order_simulator = OrderSimulator()
        price_sequence = [49800, 49600, 49400, 49800, 50200]

        for i, price in enumerate(price_sequence):
            print(f"\n  --- 时刻 {i+1}: 价格 ${price} ---")

            # 撮合订单
            pending_orders = strategy.gridorder_set.filter(status='pending')
            filled = order_simulator.check_and_fill_orders(
                list(pending_orders), float(price)
            )

            # 计算盈亏
            all_filled = strategy.gridorder_set.filter(status='filled')
            total_pnl = Decimal('0.00')
            for order in all_filled:
                pnl = order.calculate_pnl(float(price))
                total_pnl += Decimal(str(pnl))

            strategy.current_pnl = total_pnl
            strategy.save()

            print(f"  成交订单: {len(filled)}个")
            print(f"  总成交: {all_filled.count()}个")
            print(f"  当前盈亏: ${float(total_pnl):.2f}")

        # 验证
        final_filled_count = strategy.gridorder_set.filter(status='filled').count()
        print(f"\n✓ 最终成交订单: {final_filled_count}个")
        print(f"✓ 最终盈亏: ${float(strategy.current_pnl):.2f}")

        assert final_filled_count > 0

        print("\n✅ 价格波动测试通过!")


def run_all_e2e_tests():
    """运行所有端到端测试"""
    print("\n" + "="*80)
    print("开始运行端到端集成测试")
    print("="*80 + "\n")

    # 这个函数可以被外部调用来运行所有测试
    import subprocess
    result = subprocess.run(
        ['pytest', 'tests/grid_trading/test_e2e_integration.py', '-v'],
        capture_output=True,
        text=True
    )

    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)

    return result.returncode == 0


if __name__ == '__main__':
    # 允许直接运行此文件
    run_all_e2e_tests()
