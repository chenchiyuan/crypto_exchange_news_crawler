"""
参数优化命令
Parameter Optimization Command
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from backtest.services.parameter_optimizer import ParameterOptimizer

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '网格策略参数优化'

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
            '--days',
            type=int,
            help='回测天数'
        )
        parser.add_argument(
            '--initial-cash',
            type=float,
            default=10000.0,
            help='初始资金'
        )
        parser.add_argument(
            '--step-min',
            type=float,
            default=0.005,
            help='网格步长最小值，默认0.005 (0.5%%)'
        )
        parser.add_argument(
            '--step-max',
            type=float,
            default=0.02,
            help='网格步长最大值，默认0.02 (2%%)'
        )
        parser.add_argument(
            '--step-count',
            type=int,
            default=4,
            help='网格步长测试数量，默认4'
        )
        parser.add_argument(
            '--levels-min',
            type=int,
            default=5,
            help='网格层数最小值，默认5'
        )
        parser.add_argument(
            '--levels-max',
            type=int,
            default=20,
            help='网格层数最大值，默认20'
        )
        parser.add_argument(
            '--levels-step',
            type=int,
            default=5,
            help='网格层数步长，默认5'
        )
        parser.add_argument(
            '--metric',
            type=str,
            default='sharpe_ratio',
            choices=['total_return', 'sharpe_ratio', 'max_drawdown'],
            help='优化目标指标'
        )
        parser.add_argument(
            '--heatmap',
            action='store_true',
            help='生成热力图'
        )

    def handle(self, *args, **options):
        symbol = options['symbol'].upper()
        interval = options['interval']
        days = options.get('days')
        initial_cash = options['initial_cash']
        metric = options['metric']
        generate_heatmap = options['heatmap']

        # 参数范围
        step_min = options['step_min']
        step_max = options['step_max']
        step_count = options['step_count']
        levels_min = options['levels_min']
        levels_max = options['levels_max']
        levels_step = options['levels_step']

        self.stdout.write(f"\n{'='*80}")
        self.stdout.write(self.style.SUCCESS(f"参数优化: {symbol} {interval}"))
        self.stdout.write(f"初始资金: ${initial_cash}")
        self.stdout.write(f"优化目标: {metric}")
        self.stdout.write(f"{'='*80}\n")

        # 计算时间范围
        end_date = None
        start_date = None
        if days:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)

        try:
            # 创建优化器
            optimizer = ParameterOptimizer(
                symbol=symbol,
                interval=interval,
                start_date=start_date,
                end_date=end_date,
                initial_cash=initial_cash
            )

            # 生成参数范围
            import numpy as np

            grid_step_range = np.linspace(step_min, step_max, step_count).tolist()
            grid_levels_range = list(range(levels_min, levels_max + 1, levels_step))

            self.stdout.write(f"网格步长范围: {[f'{x*100:.1f}%' for x in grid_step_range]}")
            self.stdout.write(f"网格层数范围: {grid_levels_range}")
            self.stdout.write(f"总测试组合数: {len(grid_step_range) * len(grid_levels_range)}\n")

            # 执行网格搜索
            self.stdout.write("开始网格搜索...\n")

            df = optimizer.grid_search(
                grid_step_range=grid_step_range,
                grid_levels_range=grid_levels_range,
                stop_loss_range=None  # 暂不测试止损
            )

            # 显示最优参数
            self.stdout.write(f"\n{'='*80}")
            self.stdout.write(self.style.SUCCESS("优化结果 - Top 5"))
            self.stdout.write(f"{'='*80}\n")

            top_params = optimizer.get_best_params(df, metric=metric, top_n=5)

            for idx, row in enumerate(top_params.itertuples(), 1):
                marker = "⭐ " if idx == 1 else f"{idx}. "
                self.stdout.write(
                    self.style.SUCCESS(marker) if idx == 1 else f"{marker}"
                    f"步长={row.grid_step_display}, 层数={row.grid_levels}"
                )
                self.stdout.write(
                    f"   收益率: {row.total_return_display}, "
                    f"夏普比率: {row.sharpe_display}, "
                    f"最大回撤: {row.max_dd_display}, "
                    f"交易次数: {row.total_trades}"
                )

            # 生成热力图
            if generate_heatmap:
                self.stdout.write(f"\n{'='*80}")
                self.stdout.write("生成参数优化热力图...")
                self.stdout.write(f"{'='*80}\n")

                for m in ['sharpe_ratio', 'total_return', 'max_drawdown']:
                    heatmap_path = optimizer.plot_heatmap(df, metric=m)
                    self.stdout.write(self.style.SUCCESS(f"✓ {m} 热力图: {heatmap_path}"))

            # 保存结果表
            csv_path = f'backtest_reports/optimization_{symbol}_{interval}_{metric}.csv'
            df.to_csv(csv_path, index=False)
            self.stdout.write(f"\n✓ 优化结果已保存: {csv_path}")

            self.stdout.write(f"\n{'='*80}")
            self.stdout.write(self.style.SUCCESS("参数优化完成"))
            self.stdout.write(f"{'='*80}\n")

        except Exception as e:
            logger.exception("参数优化失败")
            self.stderr.write(self.style.ERROR(f"✗ 错误: {e}"))
