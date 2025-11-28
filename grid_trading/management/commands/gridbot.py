"""
网格交易机器人命令
GridBot Management Command

功能:
1. 监控GridZone，价格进入区间时启动网格
2. 监控已有策略的订单撮合
3. 更新策略盈亏
"""
import logging
import time
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from grid_trading.models import GridZone, GridStrategy, GridOrder
from grid_trading.services.config_loader import load_config
from grid_trading.services.price_service import get_current_price
from grid_trading.services.atr_calculator import ATRCalculator
from grid_trading.services.order_generator import GridOrderGenerator
from grid_trading.services.order_simulator import OrderSimulator
from grid_trading.services.risk_manager import get_risk_manager

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '网格交易机器人 - 监控价格并自动执行网格策略'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol', '-s',
            type=str,
            required=True,
            help='交易对，如: btc 或 BTCUSDT'
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='只运行一次（用于测试）'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='显示详细日志'
        )

    def handle(self, *args, **options):
        symbol_input = options['symbol']
        run_once = options['once']
        verbose = options['verbose']

        # 配置日志
        if verbose:
            logging.getLogger('grid_trading').setLevel(logging.INFO)

        # 加载配置
        try:
            config = load_config(symbol_input)
            symbol_full = config['symbol']  # BTCUSDT
            check_interval = config.get('check_interval_seconds', 60)

            self.stdout.write(f"[GridBot] 启动 - {symbol_full}")
            self.stdout.write(f"检查间隔: {check_interval}秒")

            # 初始化服务
            atr_calculator = ATRCalculator()
            order_generator = GridOrderGenerator()
            order_simulator = OrderSimulator()

            # 主循环
            iteration = 0
            while True:
                iteration += 1

                try:
                    self.stdout.write(f"\n[Iteration {iteration}] {timezone.now().strftime('%H:%M:%S')}")

                    # 1. 获取当前价格
                    current_price = get_current_price(symbol_input)
                    self.stdout.write(f"当前价格: ${current_price:.2f}")

                    # 2. 检查是否需要启动新策略
                    self._check_and_start_strategy(
                        symbol_full, current_price, config,
                        atr_calculator, order_generator
                    )

                    # 3. 更新已有策略
                    self._update_active_strategies(
                        symbol_full, current_price, order_simulator
                    )

                except KeyboardInterrupt:
                    self.stdout.write(self.style.WARNING("\n[GridBot] 用户中断"))
                    break
                except Exception as e:
                    logger.exception("GridBot执行异常")
                    self.stderr.write(self.style.ERROR(f"错误: {e}"))

                if run_once:
                    break

                # 等待下次检查
                time.sleep(check_interval)

            self.stdout.write(self.style.SUCCESS("\n[GridBot] 已停止"))

        except ValueError as e:
            self.stderr.write(self.style.ERROR(f"配置错误: {e}"))
        except Exception as e:
            logger.exception("GridBot启动失败")
            self.stderr.write(self.style.ERROR(f"启动失败: {e}"))

    def _check_and_start_strategy(
        self,
        symbol: str,
        current_price: float,
        config: dict,
        atr_calculator: ATRCalculator,
        order_generator: GridOrderGenerator
    ):
        """
        检查是否需要启动新策略

        逻辑:
        1. 查询活跃的GridZone
        2. 检查价格是否进入支撑区
        3. 如果进入且没有active策略，创建做多网格
        """
        # 检查是否已有active策略
        active_strategies = GridStrategy.objects.filter(
            symbol=symbol,
            status='active'
        )

        if active_strategies.exists():
            # 已有策略在运行，不创建新策略
            return

        # 查询活跃的支撑区
        support_zones = GridZone.objects.filter(
            symbol=symbol,
            zone_type='support',
            is_active=True,
            expires_at__gt=timezone.now()
        ).order_by('price_low')

        # 检查价格是否进入任何支撑区
        for zone in support_zones:
            if zone.is_price_in_zone(Decimal(str(current_price))):
                self.stdout.write(
                    f"✅ 价格进入支撑区: "
                    f"${zone.price_low:.2f} - ${zone.price_high:.2f} "
                    f"(置信度:{zone.confidence}分)"
                )

                # 启动做多网格
                self._start_long_grid(
                    symbol, current_price, config,
                    atr_calculator, order_generator, zone
                )
                break

    @transaction.atomic
    def _start_long_grid(
        self,
        symbol: str,
        entry_price: float,
        config: dict,
        atr_calculator: ATRCalculator,
        order_generator: GridOrderGenerator,
        trigger_zone: GridZone
    ):
        """
        启动做多网格策略

        Args:
            symbol: 交易对
            entry_price: 入场价格
            config: 策略配置
            atr_calculator: ATR计算器
            order_generator: 订单生成器
            trigger_zone: 触发的支撑区
        """
        self.stdout.write(f"🚀 启动做多网格 @ ${entry_price:.2f}")

        # 1. 风险检查
        risk_manager = get_risk_manager()
        estimated_position = order_generator.estimate_max_position_value(
            grid_levels=config['grid_levels'],
            order_size_usdt=config['order_size_usdt'],
            strategy_type='long'
        )

        allowed, reject_reason = risk_manager.validate_new_strategy(
            symbol=symbol,
            estimated_position_value=estimated_position,
            max_position_usdt=config['max_position_usdt']
        )

        if not allowed:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️ 风险检查失败: {reject_reason}"
                )
            )
            return

        # 2. 计算网格步长
        grid_step = atr_calculator.calculate_grid_step(
            symbol,
            atr_multiplier=config['atr_multiplier']
        )

        grid_step_pct = order_generator.calculate_grid_step_percentage(
            entry_price, grid_step
        )

        self.stdout.write(
            f"网格步长: ${grid_step:.2f} ({grid_step_pct*100:.2f}%)"
        )

        # 3. 创建GridStrategy
        strategy = GridStrategy.objects.create(
            symbol=symbol,
            strategy_type='long',
            grid_step_pct=Decimal(str(grid_step_pct)),
            grid_levels=config['grid_levels'],
            order_size=Decimal(str(config['order_size_usdt'] / entry_price)),
            stop_loss_pct=Decimal(str(config['stop_loss_pct'])),
            status='active',
            entry_price=Decimal(str(entry_price)),
            current_pnl=Decimal('0.00'),
            started_at=timezone.now()
        )

        # 4. 生成网格订单
        order_plans = order_generator.generate_grid_orders(
            entry_price=entry_price,
            grid_step=grid_step,
            grid_levels=config['grid_levels'],
            order_size_usdt=config['order_size_usdt'],
            strategy_type='long'
        )

        # 5. 创建订单记录
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

        self.stdout.write(
            f"策略创建成功: strategy_id={strategy.id}, "
            f"orders={len(created_orders)}"
        )

        # 6. 输出订单摘要
        buy_orders = [o for o in created_orders if o.order_type == 'buy']
        sell_orders = [o for o in created_orders if o.order_type == 'sell']

        self.stdout.write(f"  买单: {len(buy_orders)}个")
        self.stdout.write(f"  卖单: {len(sell_orders)}个")

    def _update_active_strategies(
        self,
        symbol: str,
        current_price: float,
        order_simulator: OrderSimulator
    ):
        """
        更新已有策略

        逻辑:
        1. 查询active策略
        2. 撮合pending订单
        3. 更新策略盈亏
        4. 检查止损
        """
        active_strategies = GridStrategy.objects.filter(
            symbol=symbol,
            status='active'
        )

        for strategy in active_strategies:
            self._process_strategy(strategy, current_price, order_simulator)

    @transaction.atomic
    def _process_strategy(
        self,
        strategy: GridStrategy,
        current_price: float,
        order_simulator: OrderSimulator
    ):
        """
        处理单个策略

        Args:
            strategy: 策略实例
            current_price: 当前价格
            order_simulator: 订单模拟器
        """
        # 1. 撮合pending订单
        pending_orders = strategy.gridorder_set.filter(status='pending')
        filled_orders = order_simulator.check_and_fill_orders(
            list(pending_orders), current_price
        )

        if filled_orders:
            self.stdout.write(
                f"  [Strategy {strategy.id}] 订单成交: {len(filled_orders)}个"
            )

        # 2. 计算盈亏
        self._update_strategy_pnl(strategy, current_price)

        # 3. 检查止损
        self._check_stop_loss(strategy, current_price)

    def _update_strategy_pnl(self, strategy: GridStrategy, current_price: float):
        """
        更新策略盈亏

        Args:
            strategy: 策略
            current_price: 当前价格
        """
        filled_orders = strategy.gridorder_set.filter(status='filled')

        total_pnl = Decimal('0.00')
        for order in filled_orders:
            pnl = order.calculate_pnl(current_price)
            total_pnl += Decimal(str(pnl))

        strategy.current_pnl = total_pnl
        strategy.save(update_fields=['current_pnl'])

    def _check_stop_loss(self, strategy: GridStrategy, current_price: float):
        """
        检查止损

        Args:
            strategy: 策略
            current_price: 当前价格
        """
        if not strategy.entry_price:
            return

        entry_price = float(strategy.entry_price)
        stop_loss_pct = float(strategy.stop_loss_pct)

        # 计算止损价格
        if strategy.strategy_type == 'long':
            # 做多: 价格下跌超过止损百分比
            stop_loss_price = entry_price * (1 - stop_loss_pct)
            if current_price <= stop_loss_price:
                self._trigger_stop_loss(strategy, current_price)
        elif strategy.strategy_type == 'short':
            # 做空: 价格上涨超过止损百分比
            stop_loss_price = entry_price * (1 + stop_loss_pct)
            if current_price >= stop_loss_price:
                self._trigger_stop_loss(strategy, current_price)

    def _trigger_stop_loss(self, strategy: GridStrategy, current_price: float):
        """
        触发止损

        Args:
            strategy: 策略
            current_price: 当前价格
        """
        self.stdout.write(
            self.style.ERROR(
                f"⚠️ 止损触发: strategy_id={strategy.id}, "
                f"entry=${float(strategy.entry_price):.2f}, "
                f"current=${current_price:.2f}"
            )
        )

        # 1. 撤销所有pending订单
        pending_count = strategy.gridorder_set.filter(status='pending').update(
            status='cancelled'
        )

        # 2. 停止策略
        strategy.status = 'stopped'
        strategy.stopped_at = timezone.now()
        strategy.save()

        self.stdout.write(
            f"  策略已停止: cancelled_orders={pending_count}, "
            f"final_pnl=${float(strategy.current_pnl):.2f}"
        )
