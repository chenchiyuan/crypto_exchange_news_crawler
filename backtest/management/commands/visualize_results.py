"""
回测结果可视化命令
Visualize Backtest Results Command
"""
import logging
from django.core.management.base import BaseCommand

from backtest.models import BacktestResult
from backtest.services.result_analyzer import ResultAnalyzer

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '生成回测结果可视化图表'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ids',
            type=str,
            help='回测结果ID列表，逗号分隔，如: 1,2,3'
        )
        parser.add_argument(
            '--symbol',
            type=str,
            help='交易对筛选'
        )
        parser.add_argument(
            '--interval',
            type=str,
            help='时间周期筛选'
        )
        parser.add_argument(
            '--latest',
            type=int,
            help='最近N个结果'
        )
        parser.add_argument(
            '--type',
            type=str,
            default='all',
            choices=['equity', 'drawdown', 'returns', 'all'],
            help='图表类型'
        )
        parser.add_argument(
            '--output',
            type=str,
            default='backtest_reports',
            help='输出目录'
        )

    def handle(self, *args, **options):
        ids_str = options.get('ids')
        symbol = options.get('symbol')
        interval = options.get('interval')
        latest = options.get('latest')
        chart_type = options['type']
        output_dir = options['output']

        # 构建查询
        queryset = BacktestResult.objects.all()

        if ids_str:
            result_ids = [int(x.strip()) for x in ids_str.split(',')]
            queryset = queryset.filter(id__in=result_ids)

        if symbol:
            queryset = queryset.filter(symbol=symbol.upper())

        if interval:
            queryset = queryset.filter(interval=interval)

        if latest:
            queryset = queryset.order_by('-created_at')[:latest]

        result_ids = list(queryset.values_list('id', flat=True))

        if not result_ids:
            self.stderr.write(self.style.ERROR("未找到匹配的回测结果"))
            return

        self.stdout.write(f"\n{'='*80}")
        self.stdout.write(self.style.SUCCESS(f"回测结果可视化"))
        self.stdout.write(f"找到 {len(result_ids)} 个回测结果")
        self.stdout.write(f"{'='*80}\n")

        # 创建分析器
        analyzer = ResultAnalyzer(output_dir=output_dir)

        try:
            # 生成汇总表
            self.stdout.write("生成汇总表...")
            df = analyzer.generate_summary_table(result_ids)
            self.stdout.write(str(df.to_string(index=False)))
            self.stdout.write("")

            # 生成图表
            if chart_type in ['equity', 'all']:
                self.stdout.write("生成权益曲线...")
                equity_path = analyzer.plot_equity_curve(result_ids)
                self.stdout.write(self.style.SUCCESS(f"✓ 权益曲线: {equity_path}"))

            if chart_type in ['returns', 'all']:
                self.stdout.write("生成收益分布...")
                returns_path = analyzer.plot_returns_distribution(result_ids)
                self.stdout.write(self.style.SUCCESS(f"✓ 收益分布: {returns_path}"))

            if chart_type in ['drawdown', 'all']:
                # 回撤图只支持单个结果
                if len(result_ids) == 1:
                    self.stdout.write("生成回撤曲线...")
                    drawdown_path = analyzer.plot_drawdown(result_ids[0])
                    self.stdout.write(self.style.SUCCESS(f"✓ 回撤曲线: {drawdown_path}"))
                elif chart_type == 'drawdown':
                    self.stdout.write(self.style.WARNING(
                        "⚠ 回撤图只支持单个结果，请使用 --ids 指定单个ID"
                    ))

            self.stdout.write(f"\n{'='*80}")
            self.stdout.write(self.style.SUCCESS("可视化完成"))
            self.stdout.write(f"报告保存在: {output_dir}/")
            self.stdout.write(f"{'='*80}\n")

        except Exception as e:
            logger.exception("可视化失败")
            self.stderr.write(self.style.ERROR(f"✗ 错误: {e}"))
