"""
一键回测命令 - 智能数据获取 + 策略选择 + 可视化回测
Quick Backtest Command
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from backtest.models import KLine
from backtest.services.data_fetcher import DataFetcher
from backtest.services.backtest_engine import BacktestEngine
from backtest.services.grid_strategy_vbt import GridStrategyVBT
from backtest.services.buy_hold_strategy import BuyHoldStrategy
from backtest.services.visual_backtest import VisualBacktest

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '一键运行可视化回测（智能数据获取 + 策略选择 + 图形化展示）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol', '-s',
            type=str,
            default='ETHUSDT',
            help='交易对，默认ETHUSDT'
        )
        parser.add_argument(
            '--interval', '-i',
            type=str,
            default='4h',
            help='时间周期，默认4h'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=180,
            help='回测天数，默认180天'
        )
        parser.add_argument(
            '--initial-cash',
            type=float,
            default=10000.0,
            help='初始资金，默认10000 USDT'
        )
        parser.add_argument(
            '--strategy',
            type=str,
            choices=['grid', 'buy_hold', 'ask'],
            default='ask',
            help='策略类型（ask=交互式选择）'
        )
        parser.add_argument(
            '--grid-step',
            type=float,
            default=1.5,
            help='网格步长百分比（直接输入数值，如1.5表示1.5%%），默认1.5'
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
            help='止损百分比，如0.1表示10%%'
        )
        parser.add_argument(
            '--no-visual',
            action='store_true',
            help='不显示可视化图表'
        )

    def handle(self, *args, **options):
        symbol = options['symbol'].upper()
        interval = options['interval']
        days = options['days']
        initial_cash = options['initial_cash']
        strategy_type = options['strategy']
        show_visual = not options['no_visual']

        self.stdout.write(f"\n{'='*80}")
        self.stdout.write(self.style.SUCCESS("🚀 一键可视化回测系统"))
        self.stdout.write(f"{'='*80}\n")

        try:
            # ========== Step 1: 智能数据获取 ==========
            self.stdout.write(self.style.WARNING("📊 Step 1: 检查并获取历史数据"))
            self.stdout.write(f"   交易对: {symbol}")
            self.stdout.write(f"   周期: {interval}")
            self.stdout.write(f"   时间范围: {days}天\n")

            data_ready = self._ensure_data(symbol, interval, days)

            if not data_ready:
                self.stderr.write(self.style.ERROR("✗ 数据获取失败"))
                return

            # ========== Step 2: 策略选择 ==========
            self.stdout.write(f"\n{'='*80}")
            self.stdout.write(self.style.WARNING("🎯 Step 2: 策略配置"))

            if strategy_type == 'ask':
                strategy_config = self._interactive_strategy_selection()
            else:
                strategy_config = {
                    'type': strategy_type,
                    'grid_step': options['grid_step'] / 100,  # 转换为小数
                    'grid_levels': options['grid_levels'],
                    'stop_loss': options.get('stop_loss') / 100 if options.get('stop_loss') else None
                }

            self.stdout.write(f"\n   策略: {strategy_config['type']}")
            if strategy_config['type'] == 'grid':
                self.stdout.write(f"   网格步长: {strategy_config['grid_step']*100:.1f}%")
                self.stdout.write(f"   网格层数: {strategy_config['grid_levels']}")
                if strategy_config.get('stop_loss'):
                    self.stdout.write(f"   止损: {strategy_config['stop_loss']*100:.0f}%")

            # ========== Step 3: 执行回测 ==========
            self.stdout.write(f"\n{'='*80}")
            self.stdout.write(self.style.WARNING("⚡ Step 3: 执行回测"))
            self.stdout.write("")

            result, entries, exits, grid_info = self._run_backtest(
                symbol, interval, days, initial_cash, strategy_config
            )

            # ========== Step 4: 显示结果 ==========
            self.stdout.write(f"\n{'='*80}")
            self.stdout.write(self.style.SUCCESS("📈 Step 4: 回测结果"))
            self.stdout.write(f"{'='*80}")

            self._display_results(result)

            # ========== Step 5: 可视化 ==========
            self.stdout.write(f"\n{'='*80}")
            self.stdout.write(self.style.WARNING("🎨 Step 5: 生成可视化图表"))
            self.stdout.write(f"{'='*80}\n")

            self._generate_visualization(
                result, symbol, interval, days, initial_cash,
                entries, exits, grid_info, show_visual
            )

            self.stdout.write(f"\n{'='*80}")
            self.stdout.write(self.style.SUCCESS("✅ 回测完成！"))
            self.stdout.write(f"{'='*80}\n")

        except Exception as e:
            logger.exception("回测执行失败")
            self.stderr.write(self.style.ERROR(f"\n✗ 错误: {e}\n"))

    def _ensure_data(self, symbol: str, interval: str, days: int) -> bool:
        """确保数据可用（优先数据库，不存在则从API获取）"""

        # 计算需要的K线数量
        interval_map = {'1h': 24, '4h': 6, '1d': 1}
        bars_per_day = interval_map.get(interval, 6)
        needed_bars = days * bars_per_day

        # 检查数据库
        existing_count = KLine.objects.filter(
            symbol=symbol,
            interval=interval
        ).count()

        self.stdout.write(f"   数据库现有: {existing_count} 根K线")
        self.stdout.write(f"   所需数量: {needed_bars} 根K线")

        if existing_count >= needed_bars:
            self.stdout.write(self.style.SUCCESS(f"   ✓ 数据充足，使用数据库数据\n"))
            return True

        # 数据不足，从API获取
        self.stdout.write(self.style.WARNING(f"   ⚠ 数据不足，从币安API获取..."))

        try:
            fetcher = DataFetcher(symbol, interval)
            saved_count = fetcher.fetch_historical_data(days=days)

            self.stdout.write(self.style.SUCCESS(
                f"   ✓ 成功获取并保存 {saved_count} 根新K线\n"
            ))
            return True

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"   ✗ 数据获取失败: {e}"))
            return False

    def _interactive_strategy_selection(self) -> dict:
        """交互式策略选择"""

        self.stdout.write("\n   请选择策略:")
        self.stdout.write("   1. 网格策略 (Grid Trading)")
        self.stdout.write("   2. 买入持有 (Buy & Hold)")

        choice = input("\n   输入选项 (1/2) [默认: 1]: ").strip() or "1"

        if choice == "2":
            return {'type': 'buy_hold'}

        # 网格策略参数
        self.stdout.write("\n   配置网格策略参数:")

        grid_step = input("   网格步长百分比 (0.5-5.0) [默认: 1.5]: ").strip()
        grid_step = float(grid_step) / 100 if grid_step else 0.015

        grid_levels = input("   网格层数 (5-20) [默认: 10]: ").strip()
        grid_levels = int(grid_levels) if grid_levels else 10

        use_stop_loss = input("   是否启用止损? (y/n) [默认: n]: ").strip().lower()

        stop_loss = None
        if use_stop_loss == 'y':
            sl_input = input("   止损百分比 (5-20) [默认: 10]: ").strip()
            stop_loss = float(sl_input) / 100 if sl_input else 0.10

        return {
            'type': 'grid',
            'grid_step': grid_step,
            'grid_levels': grid_levels,
            'stop_loss': stop_loss
        }

    def _run_backtest(
        self,
        symbol: str,
        interval: str,
        days: int,
        initial_cash: float,
        strategy_config: dict
    ):
        """执行回测"""

        # 计算时间范围
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # 创建回测引擎
        engine = BacktestEngine(
            symbol=symbol,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash
        )

        self.stdout.write(f"   回测引擎初始化完成")
        self.stdout.write(f"   数据量: {len(engine.df)} 根K线")
        self.stdout.write(f"   时间范围: {engine.df.index[0]} ~ {engine.df.index[-1]}\n")

        # 运行策略
        grid_info = None

        if strategy_config['type'] == 'buy_hold':
            self.stdout.write("   执行买入持有策略...")
            strategy = BuyHoldStrategy(engine)
            entries, exits = strategy.generate_signals()
            result = strategy.run()

        else:  # grid
            self.stdout.write("   执行网格策略...")
            strategy = GridStrategyVBT(
                engine=engine,
                grid_step_pct=strategy_config['grid_step'],
                grid_levels=strategy_config['grid_levels'],
                stop_loss_pct=strategy_config.get('stop_loss')
            )
            entries, exits = strategy.generate_signals()
            result = strategy.run()

            # 获取网格信息用于可视化
            base_price = engine.df['Close'].iloc[0]
            grid_levels_list = []
            for i in range(1, strategy_config['grid_levels'] + 1):
                buy_price = base_price * (1 - strategy_config['grid_step'] * i)
                sell_price = base_price * (1 + strategy_config['grid_step'] * i)
                grid_levels_list.append((buy_price, sell_price))

            stop_loss_price = None
            if strategy_config.get('stop_loss'):
                stop_loss_price = base_price * (1 - strategy_config['stop_loss'])

            grid_info = {
                'base_price': base_price,
                'grid_levels': grid_levels_list,
                'stop_loss_price': stop_loss_price
            }

        self.stdout.write(self.style.SUCCESS(f"   ✓ 回测执行完成\n"))

        return result, entries, exits, grid_info

    def _display_results(self, result):
        """显示回测结果"""

        total_return_pct = float(result.total_return) * 100

        # 使用颜色高亮显示
        if total_return_pct > 0:
            return_text = self.style.SUCCESS(f"+{total_return_pct:.2f}%")
        else:
            return_text = self.style.ERROR(f"{total_return_pct:.2f}%")

        self.stdout.write(f"回测ID: {result.id}")
        self.stdout.write(f"策略名称: {result.name}")
        self.stdout.write(f"")
        self.stdout.write(f"📊 绩效指标:")
        self.stdout.write(f"  初始资金: ${float(result.initial_cash):,.2f}")
        self.stdout.write(f"  最终价值: ${float(result.final_value):,.2f}")
        self.stdout.write(f"  总收益率: {return_text}")
        self.stdout.write(f"  夏普比率: {float(result.sharpe_ratio):.2f}")
        self.stdout.write(f"  最大回撤: {float(result.max_drawdown):.2f}%")
        self.stdout.write(f"")
        self.stdout.write(f"📈 交易统计:")
        self.stdout.write(f"  总交易次数: {result.total_trades}")
        self.stdout.write(f"  盈利交易: {result.profitable_trades}")
        self.stdout.write(f"  亏损交易: {result.losing_trades}")
        self.stdout.write(f"  胜率: {float(result.win_rate):.1f}%")

    def _generate_visualization(
        self,
        result,
        symbol,
        interval,
        days,
        initial_cash,
        entries,
        exits,
        grid_info,
        show
    ):
        """生成可视化"""

        visualizer = VisualBacktest()

        # 重新创建引擎用于可视化
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        engine = BacktestEngine(
            symbol=symbol,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash
        )

        # 生成主可视化图
        self.stdout.write("   生成策略执行过程可视化...")

        viz_path = visualizer.visualize_grid_backtest(
            result=result,
            engine=engine,
            entries=entries,
            exits=exits,
            grid_levels=grid_info['grid_levels'] if grid_info else None,
            base_price=grid_info['base_price'] if grid_info else None,
            stop_loss_price=grid_info['stop_loss_price'] if grid_info else None,
            show=show
        )

        self.stdout.write(self.style.SUCCESS(f"   ✓ 主图: {viz_path}"))

        # 生成交易时间线
        if result.total_trades > 0:
            self.stdout.write("   生成交易时间线...")
            timeline_path = visualizer.create_trade_timeline(result, show=show)
            self.stdout.write(self.style.SUCCESS(f"   ✓ 时间线: {timeline_path}"))
