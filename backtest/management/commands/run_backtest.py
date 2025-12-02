"""
回测执行命令
Run Backtest Command
"""
import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import pytz

from backtest.services.backtest_engine import BacktestEngine
from backtest.services.buy_hold_strategy import BuyHoldStrategy
from backtest.services.grid_strategy_vbt import GridStrategyVBT
from backtest.services.grid_strategy_v2 import GridStrategyV2
from backtest.services.grid_strategy_v3 import GridStrategyV3
from backtest.services.grid_strategy_v4 import GridStrategyV4

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '运行回测'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol', '-s',
            type=str,
            required=True,
            help='交易对'
        )
        parser.add_argument(
            '--interval', '-i',
            type=str,
            required=True,
            help='时间周期'
        )
        parser.add_argument(
            '--strategy',
            type=str,
            default='buy_hold',
            choices=['buy_hold', 'grid', 'grid_v2', 'grid_v3', 'grid_v4'],
            help='策略类型'
        )
        parser.add_argument(
            '--days',
            type=int,
            help='回测天数（从最新数据往前），与--start-date/--end-date互斥'
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='回测开始日期，格式: YYYY-MM-DD，例如 2025-01-01'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='回测结束日期，格式: YYYY-MM-DD，例如 2025-06-30'
        )
        parser.add_argument(
            '--initial-cash',
            type=float,
            default=10000.0,
            help='初始资金，默认10000 USDT'
        )
        # 网格策略参数
        parser.add_argument(
            '--grid-step',
            type=float,
            default=0.01,
            help='网格步长百分比，默认0.01 (1%%)'
        )
        parser.add_argument(
            '--grid-levels',
            type=int,
            default=10,
            help='网格层数，默认10'
        )
        parser.add_argument(
            '--stop-loss',
            type=float,
            help='止损百分比，例如0.1表示10%%'
        )
        parser.add_argument(
            '--price-deviation',
            type=float,
            default=0.10,
            help='价格偏离百分比，默认0.10 (10%%)，即在±10%%范围内寻找支撑压力'
        )
        parser.add_argument(
            '--executor',
            type=str,
            default='progressive',
            choices=['simple', 'progressive'],
            help='执行器类型：simple(简单模式，支撑上界买满/压力下界卖光) 或 progressive(渐进模式，权重衰减)，默认progressive'
        )
        parser.add_argument(
            '--order-validity-days',
            type=int,
            default=3,
            help='挂单有效期（天），仅grid_v3策略使用，默认3天'
        )

    def handle(self, *args, **options):
        symbol = options['symbol'].upper()
        interval = options['interval']
        strategy_type = options['strategy']
        days = options.get('days')
        start_date_str = options.get('start_date')
        end_date_str = options.get('end_date')
        initial_cash = options['initial_cash']

        self.stdout.write(f"\n{'='*80}")
        self.stdout.write(self.style.SUCCESS(f"回测: {symbol} {interval}"))
        self.stdout.write(f"策略: {strategy_type}")
        self.stdout.write(f"初始资金: ${initial_cash}")
        self.stdout.write(f"{'='*80}\n")

        try:
            # 计算时间范围
            end_date = None
            start_date = None

            # 参数互斥检查
            if days and (start_date_str or end_date_str):
                raise CommandError(
                    "❌ 参数冲突: --days 与 --start-date/--end-date 不能同时使用\n"
                    "   请选择其中一种方式指定时间范围"
                )

            if (start_date_str and not end_date_str) or (end_date_str and not start_date_str):
                raise CommandError(
                    "❌ 参数不完整: --start-date 和 --end-date 必须同时指定"
                )

            # 方式1: 使用days参数（从最新数据往前）
            if days:
                end_date = timezone.now()
                start_date = end_date - timedelta(days=days)
                self.stdout.write(f"时间范围: 最近{days}天")
                self.stdout.write(f"  开始: {start_date.strftime('%Y-%m-%d %H:%M:%S')}")
                self.stdout.write(f"  结束: {end_date.strftime('%Y-%m-%d %H:%M:%S')}\n")

            # 方式2: 使用start-date和end-date参数（指定时间范围）
            elif start_date_str and end_date_str:
                try:
                    # 解析日期字符串（支持 YYYY-MM-DD 格式）
                    start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
                    end_dt = datetime.strptime(end_date_str, '%Y-%m-%d')

                    # 转换为timezone-aware datetime（UTC时区）
                    utc = pytz.UTC
                    start_date = utc.localize(start_dt)
                    # 结束日期设置为当天23:59:59
                    end_date = utc.localize(end_dt.replace(hour=23, minute=59, second=59))

                    # 验证时间范围合理性
                    if start_date >= end_date:
                        raise CommandError(
                            f"❌ 时间范围错误: 开始时间({start_date_str})必须早于结束时间({end_date_str})"
                        )

                    days_diff = (end_date - start_date).days
                    self.stdout.write(f"时间范围: {start_date_str} ~ {end_date_str} (共{days_diff}天)")
                    self.stdout.write(f"  开始: {start_date.strftime('%Y-%m-%d %H:%M:%S')}")
                    self.stdout.write(f"  结束: {end_date.strftime('%Y-%m-%d %H:%M:%S')}\n")

                except ValueError as e:
                    raise CommandError(
                        f"❌ 日期格式错误: {e}\n"
                        f"   正确格式: YYYY-MM-DD，例如 2025-01-01"
                    )

            # 方式3: 不指定时间范围（使用全部数据）
            else:
                self.stdout.write("时间范围: 全部可用数据\n")

            # 创建回测引擎
            engine = BacktestEngine(
                symbol=symbol,
                interval=interval,
                start_date=start_date,
                end_date=end_date,
                initial_cash=initial_cash
            )

            # 运行策略
            if strategy_type == 'buy_hold':
                strategy = BuyHoldStrategy(engine)
                result = strategy.run()
            elif strategy_type == 'grid':
                grid_step = options['grid_step']
                grid_levels = options['grid_levels']
                stop_loss = options.get('stop_loss')

                strategy = GridStrategyVBT(
                    engine=engine,
                    grid_step_pct=grid_step,
                    grid_levels=grid_levels,
                    stop_loss_pct=stop_loss
                )
                result = strategy.run()
            elif strategy_type == 'grid_v2':
                # Grid V2 不使用BacktestEngine，直接运行
                price_deviation = options.get('price_deviation', 0.10)
                executor_type = options.get('executor', 'progressive')

                strategy = GridStrategyV2(
                    symbol=symbol,
                    interval=interval,
                    start_date=start_date,
                    end_date=end_date,
                    initial_cash=initial_cash,
                    commission=0.001,
                    support_1_max_pct=0.20,
                    support_2_max_pct=0.30,
                    stop_loss_pct=0.03,
                    decay_k=3.0,
                    price_deviation_pct=price_deviation,
                    executor_type=executor_type
                )
                result = strategy.run()
            elif strategy_type == 'grid_v3':
                # Grid V3 - 带挂单系统
                price_deviation = options.get('price_deviation', 0.10)
                executor_type = options.get('executor', 'progressive')
                order_validity_days = options.get('order_validity_days', 3)

                strategy = GridStrategyV3(
                    symbol=symbol,
                    interval=interval,
                    start_date=start_date,
                    end_date=end_date,
                    initial_cash=initial_cash,
                    commission=0.001,
                    support_1_max_pct=0.20,
                    support_2_max_pct=0.30,
                    stop_loss_pct=0.03,
                    decay_k=3.0,
                    price_deviation_pct=price_deviation,
                    executor_type=executor_type,
                    order_validity_days=order_validity_days
                )
                result = strategy.run()
            elif strategy_type == 'grid_v4':
                # Grid V4 - 双向交易策略
                price_deviation = options.get('price_deviation', 0.10)
                stop_loss = options.get('stop_loss') or 0.03

                strategy = GridStrategyV4(
                    symbol=symbol,
                    interval=interval,
                    start_date=start_date,
                    end_date=end_date,
                    initial_cash=initial_cash,
                    stop_loss_pct=stop_loss,
                    commission=0.001,
                    price_deviation_pct=price_deviation
                )
                result = strategy.run()
            else:
                raise ValueError(f"不支持的策略类型: {strategy_type}")

            # 显示结果
            self.stdout.write("\n" + "="*80)
            self.stdout.write(self.style.SUCCESS("回测结果"))
            self.stdout.write("="*80)
            self.stdout.write(f"回测ID: {result.id}")
            self.stdout.write(f"时间范围: {result.start_date} ~ {result.end_date}")
            self.stdout.write(f"初始资金: ${float(result.initial_cash):.2f}")
            self.stdout.write(f"最终价值: ${float(result.final_value):.2f}")

            total_return_pct = float(result.total_return) * 100
            if total_return_pct > 0:
                self.stdout.write(
                    self.style.SUCCESS(f"总收益率: +{total_return_pct:.2f}%")
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"总收益率: {total_return_pct:.2f}%")
                )

            if result.sharpe_ratio:
                self.stdout.write(f"夏普比率: {float(result.sharpe_ratio):.2f}")
            self.stdout.write(f"最大回撤: {float(result.max_drawdown):.2f}%")
            self.stdout.write(f"总交易次数: {result.total_trades}")
            self.stdout.write(f"胜率: {float(result.win_rate):.2f}%")
            self.stdout.write("="*80 + "\n")

        except Exception as e:
            logger.exception("回测失败")
            self.stderr.write(self.style.ERROR(f"✗ 错误: {e}"))
