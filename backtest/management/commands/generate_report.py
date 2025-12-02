"""
生成回测报告命令
Generate Backtest Report Command
"""
import logging
from pathlib import Path
from datetime import datetime
from django.core.management.base import BaseCommand

from backtest.models import BacktestResult
from backtest.services.result_analyzer import ResultAnalyzer

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '生成综合回测分析报告'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ids',
            type=str,
            help='回测结果ID列表，逗号分隔'
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
            default=10,
            help='最近N个结果，默认10'
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
        latest = options['latest']
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

        # 获取结果ID列表（先切片）
        result_ids = list(queryset.order_by('-created_at')[:latest].values_list('id', flat=True))

        if not result_ids:
            self.stderr.write(self.style.ERROR("未找到匹配的回测结果"))
            return

        # 重新查询以便后续排序（不切片）
        results = BacktestResult.objects.filter(id__in=result_ids)

        self.stdout.write(f"\n{'='*80}")
        self.stdout.write(self.style.SUCCESS(f"回测分析报告生成"))
        self.stdout.write(f"找到 {len(result_ids)} 个回测结果")
        self.stdout.write(f"{'='*80}\n")

        try:
            # 创建分析器
            analyzer = ResultAnalyzer(output_dir=output_dir)

            # 生成报告文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_name = f"backtest_report_{timestamp}"

            # 1. 生成汇总表
            self.stdout.write("1. 生成回测结果汇总表...")
            df = analyzer.generate_summary_table(result_ids)

            # 保存为CSV
            csv_path = Path(output_dir) / f"{report_name}.csv"
            df.to_csv(csv_path, index=False)
            self.stdout.write(self.style.SUCCESS(f"   ✓ CSV: {csv_path}\n"))

            # 显示表格
            self.stdout.write(df.to_string(index=False))
            self.stdout.write("")

            # 2. 生成权益曲线
            self.stdout.write("\n2. 生成权益曲线...")
            equity_path = analyzer.plot_equity_curve(
                result_ids,
                save_path=Path(output_dir) / f"{report_name}_equity.png"
            )
            self.stdout.write(self.style.SUCCESS(f"   ✓ {equity_path}"))

            # 3. 生成收益分布
            self.stdout.write("\n3. 生成收益分布...")
            returns_path = analyzer.plot_returns_distribution(
                result_ids,
                save_path=Path(output_dir) / f"{report_name}_returns.png"
            )
            self.stdout.write(self.style.SUCCESS(f"   ✓ {returns_path}"))

            # 4. 生成最佳策略的回撤图
            self.stdout.write("\n4. 生成最佳策略回撤曲线...")
            best_result = results.order_by('-sharpe_ratio').first()
            if best_result:
                drawdown_path = analyzer.plot_drawdown(
                    best_result.id,
                    save_path=Path(output_dir) / f"{report_name}_drawdown_best.png"
                )
                self.stdout.write(self.style.SUCCESS(
                    f"   ✓ {drawdown_path} (最佳策略: {best_result.name})"
                ))

            # 5. 生成Markdown报告
            self.stdout.write("\n5. 生成Markdown报告...")
            md_path = self._generate_markdown_report(
                results, df, output_dir, report_name
            )
            self.stdout.write(self.style.SUCCESS(f"   ✓ {md_path}"))

            self.stdout.write(f"\n{'='*80}")
            self.stdout.write(self.style.SUCCESS("报告生成完成"))
            self.stdout.write(f"报告位置: {output_dir}/{report_name}.*")
            self.stdout.write(f"{'='*80}\n")

        except Exception as e:
            logger.exception("报告生成失败")
            self.stderr.write(self.style.ERROR(f"✗ 错误: {e}"))

    def _generate_markdown_report(
        self,
        queryset,
        df,
        output_dir: str,
        report_name: str
    ) -> str:
        """生成Markdown格式报告"""

        md_content = []

        # 标题
        md_content.append(f"# 回测分析报告\n")
        md_content.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        md_content.append(f"**回测数量**: {len(queryset)}\n")

        # 概览
        md_content.append("## 回测概览\n")

        if queryset.exists():
            first = queryset.first()
            md_content.append(f"- **交易对**: {first.symbol}")
            md_content.append(f"- **时间周期**: {first.interval}")
            md_content.append(f"- **数据范围**: {first.start_date.strftime('%Y-%m-%d')} ~ {first.end_date.strftime('%Y-%m-%d')}")
            md_content.append(f"- **初始资金**: ${float(first.initial_cash):,.2f}\n")

        # 最佳策略
        md_content.append("## 最佳策略\n")

        best = queryset.order_by('-sharpe_ratio').first()
        if best:
            md_content.append(f"### {best.name}\n")
            md_content.append(f"**参数配置**:")

            params = best.strategy_params
            if 'grid_step_pct' in params:
                md_content.append(f"- 网格步长: {params['grid_step_pct']*100:.1f}%")
                md_content.append(f"- 网格层数: {params['grid_levels']}")

            md_content.append(f"\n**绩效指标**:")
            md_content.append(f"- 总收益率: **{float(best.total_return)*100:.2f}%**")
            md_content.append(f"- 夏普比率: **{float(best.sharpe_ratio):.2f}**")
            md_content.append(f"- 最大回撤: {float(best.max_drawdown):.2f}%")
            md_content.append(f"- 胜率: {float(best.win_rate):.2f}%")
            md_content.append(f"- 交易次数: {best.total_trades}")
            md_content.append(f"- 最终价值: ${float(best.final_value):,.2f}\n")

        # 策略对比表
        md_content.append("## 所有策略对比\n")
        md_content.append("| ID | 策略名称 | 步长 | 层数 | 收益率 | 夏普 | 回撤 | 胜率 | 交易次数 |")
        md_content.append("|---:|:---------|-----:|-----:|-------:|-----:|-----:|-----:|---------:|")

        for result in queryset.order_by('-sharpe_ratio'):
            params = result.strategy_params
            step = f"{params.get('grid_step_pct', 0)*100:.1f}%" if 'grid_step_pct' in params else 'N/A'
            levels = params.get('grid_levels', 'N/A')

            md_content.append(
                f"| {result.id} "
                f"| {result.name[:30]} "
                f"| {step} "
                f"| {levels} "
                f"| {float(result.total_return)*100:.2f}% "
                f"| {float(result.sharpe_ratio):.2f} "
                f"| {float(result.max_drawdown):.2f}% "
                f"| {float(result.win_rate):.2f}% "
                f"| {result.total_trades} |"
            )

        md_content.append("")

        # 关键发现
        md_content.append("## 关键发现\n")

        # 分析步长影响
        grid_results = queryset.filter(strategy_params__strategy_type='grid')
        if grid_results.exists():
            steps_analysis = {}
            for r in grid_results:
                step = r.strategy_params.get('grid_step_pct')
                if step:
                    if step not in steps_analysis:
                        steps_analysis[step] = []
                    steps_analysis[step].append(float(r.sharpe_ratio) if r.sharpe_ratio else 0)

            if steps_analysis:
                md_content.append("### 网格步长分析\n")
                for step, sharpes in sorted(steps_analysis.items()):
                    avg_sharpe = sum(sharpes) / len(sharpes)
                    md_content.append(f"- **{step*100:.1f}%**: 平均夏普比率 {avg_sharpe:.2f}")

        md_content.append("")

        # 图表
        md_content.append("## 可视化图表\n")
        md_content.append(f"### 权益曲线\n")
        md_content.append(f"![权益曲线]({report_name}_equity.png)\n")
        md_content.append(f"### 收益分布\n")
        md_content.append(f"![收益分布]({report_name}_returns.png)\n")
        md_content.append(f"### 最佳策略回撤\n")
        md_content.append(f"![回撤曲线]({report_name}_drawdown_best.png)\n")

        # 保存文件
        md_path = Path(output_dir) / f"{report_name}.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_content))

        return str(md_path)
