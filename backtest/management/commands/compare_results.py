"""
回测结果对比分析命令
Compare Backtest Results Command
"""
import logging
from django.core.management.base import BaseCommand
from backtest.models import BacktestResult

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '对比分析回测结果'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol', '-s',
            type=str,
            default='ETHUSDT',
            help='交易对'
        )
        parser.add_argument(
            '--interval', '-i',
            type=str,
            default='4h',
            help='时间周期'
        )

    def handle(self, *args, **options):
        symbol = options['symbol'].upper()
        interval = options['interval']

        self.stdout.write(f"\n{'='*100}")
        self.stdout.write(self.style.SUCCESS(f"网格策略参数对比分析 - {symbol} {interval}"))
        self.stdout.write(f"{'='*100}\n")

        # 查询所有结果
        results = BacktestResult.objects.filter(
            symbol=symbol,
            interval=interval
        ).order_by('id')

        if not results.exists():
            self.stderr.write(self.style.ERROR(f"没有找到 {symbol} {interval} 的回测结果"))
            return

        # 显示基准策略
        self.stdout.write(self.style.WARNING("【基准策略】"))
        buy_hold = results.filter(strategy_params__strategy_type='buy_and_hold').first()
        if buy_hold:
            self.stdout.write(f"Buy & Hold")
            self.stdout.write(f"  收益率: {float(buy_hold.total_return)*100:.2f}%")
            self.stdout.write(f"  夏普比率: {float(buy_hold.sharpe_ratio):.2f}")
            self.stdout.write(f"  最大回撤: {float(buy_hold.max_drawdown):.2f}%")
            self.stdout.write(f"  交易次数: {buy_hold.total_trades}\n")

        # 收集网格策略结果
        self.stdout.write(self.style.WARNING("【网格策略 - 不同参数组合】"))

        grid_results = []
        for r in results.filter(strategy_params__strategy_type='grid'):
            params = r.strategy_params

            # 跳过带止损的测试
            if params.get('stop_loss_pct'):
                continue

            grid_step = params.get('grid_step_pct', 0) * 100
            grid_levels = params.get('grid_levels', 0)
            total_return = float(r.total_return) * 100
            sharpe = float(r.sharpe_ratio) if r.sharpe_ratio else 0
            max_dd = float(r.max_drawdown)
            trades = r.total_trades
            win_rate = float(r.win_rate)

            grid_results.append({
                'id': r.id,
                'step': grid_step,
                'levels': grid_levels,
                'return': total_return,
                'sharpe': sharpe,
                'dd': max_dd,
                'trades': trades,
                'win_rate': win_rate
            })

        if not grid_results:
            self.stderr.write(self.style.ERROR("没有找到网格策略回测结果"))
            return

        # 按收益率排序
        grid_results.sort(key=lambda x: x['return'], reverse=True)

        # 显示所有结果
        for i, gr in enumerate(grid_results, 1):
            marker = self.style.SUCCESS(' ⭐ [最优]') if i == 1 else ''
            self.stdout.write(f"{i}. 步长={gr['step']:.1f}%, 层数={gr['levels']}{marker}")

            return_style = self.style.SUCCESS if gr['return'] > 0 else self.style.ERROR
            self.stdout.write(f"   收益率: " + return_style(f"{gr['return']:.2f}%"))
            self.stdout.write(f"   夏普比率: {gr['sharpe']:.2f}")
            self.stdout.write(f"   最大回撤: {gr['dd']:.2f}%")
            self.stdout.write(f"   交易次数: {gr['trades']}, 胜率: {gr['win_rate']:.2f}%")
            self.stdout.write("")

        # 关键发现
        self.stdout.write(f"{'='*100}")
        self.stdout.write(self.style.SUCCESS("关键发现"))
        self.stdout.write(f"{'='*100}")

        best = grid_results[0]
        worst = grid_results[-1]

        self.stdout.write(f"1. 最优参数组合: 步长={best['step']:.1f}%, 层数={best['levels']}")
        self.stdout.write(f"   - 收益率达到 {best['return']:.2f}%，夏普比率 {best['sharpe']:.2f}")
        self.stdout.write(f"   - 以 {best['trades']} 次交易实现，胜率 {best['win_rate']:.0f}%")
        self.stdout.write("")

        self.stdout.write("2. 参数规律:")

        # 分析步长影响
        by_step = {}
        for gr in grid_results:
            step = gr['step']
            if step not in by_step:
                by_step[step] = []
            by_step[step].append(gr['return'])

        avg_by_step = {s: sum(returns)/len(returns) for s, returns in by_step.items()}
        best_step = max(avg_by_step.items(), key=lambda x: x[1])

        self.stdout.write(f"   - 最佳步长: {best_step[0]:.1f}% (平均收益 {best_step[1]:.2f}%)")

        # 分析层数影响
        by_levels = {}
        for gr in grid_results:
            levels = gr['levels']
            if levels not in by_levels:
                by_levels[levels] = []
            by_levels[levels].append(gr['return'])

        avg_by_levels = {l: sum(returns)/len(returns) for l, returns in by_levels.items()}
        best_levels = max(avg_by_levels.items(), key=lambda x: x[1])

        self.stdout.write(f"   - 最佳层数: {best_levels[0]} (平均收益 {best_levels[1]:.2f}%)")
        self.stdout.write("")

        self.stdout.write("3. vs Buy & Hold:")
        if buy_hold:
            bh_return = float(buy_hold.total_return) * 100
            bh_sharpe = float(buy_hold.sharpe_ratio)

            self.stdout.write(f"   - Buy & Hold 收益率: {bh_return:.2f}%, 网格最优: {best['return']:.2f}%")
            self.stdout.write(f"   - Buy & Hold 夏普比率: {bh_sharpe:.2f}, 网格最优: {best['sharpe']:.2f}")

            if best['sharpe'] > bh_sharpe:
                self.stdout.write(self.style.SUCCESS(
                    "   - 网格策略风险调整后收益更优（夏普比率更高）"
                ))

            self.stdout.write(f"   - 网格策略最大回撤 {best['dd']:.2f}% < Buy & Hold {float(buy_hold.max_drawdown):.2f}%")

        self.stdout.write(f"{'='*100}\n")
