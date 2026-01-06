"""
Volume Trap 回测管理命令

提供CLI接口执行批量回测和统计计算。

Usage:
    python manage.py volume_trap_backtest
    python manage.py volume_trap_backtest --status suspected_abandonment
    python manage.py volume_trap_backtest --interval 4h
    python manage.py volume_trap_backtest --market-type futures
    python manage.py volume_trap_backtest --start-date 2024-01-01
    python manage.py volume_trap_backtest --observation-bars 100
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from backtest.models import KLine
from volume_trap.models import VolumeTrapMonitor
from volume_trap.services.backtest_engine import BatchBacktestRunner
from volume_trap.services.statistics_service import StatisticsCalculator


class Command(BaseCommand):
    help = "执行Volume Trap策略批量回测分析"

    def add_arguments(self, parser):
        """添加命令行参数。"""
        parser.add_argument(
            "--status",
            type=str,
            help="异常事件状态筛选 (pending/suspected_abandonment/confirmed_abandonment)",
        )
        parser.add_argument(
            "--market-type",
            type=str,
            choices=["spot", "futures"],
            help="市场类型筛选 (spot/futures)",
        )
        parser.add_argument(
            "--interval",
            type=str,
            choices=["1h", "4h", "1d"],
            help="K线周期筛选 (1h/4h/1d)",
        )
        parser.add_argument(
            "--symbol",
            type=str,
            help="交易对符号筛选 (如 BTCUSDT)",
        )
        parser.add_argument(
            "--start-date",
            type=str,
            help="开始日期筛选 (YYYY-MM-DD格式)",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            help="结束日期筛选 (YYYY-MM-DD格式)",
        )
        parser.add_argument(
            "--observation-bars",
            type=int,
            default=0,
            help="观察K线数 (0表示观察全部历史数据，默认0)",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="跳过已有回测结果的记录",
        )
        parser.add_argument(
            "--skip-errors",
            action="store_true",
            default=True,
            help="遇到错误时跳过继续执行 (默认True)",
        )
        parser.add_argument(
            "--no-skip-errors",
            action="store_false",
            dest="skip_errors",
            help="遇到错误时停止执行",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="强制重新执行所有筛选的记录（忽略已有回测结果）",
        )
        parser.add_argument(
            "--calculate-stats",
            action="store_true",
            help="计算整体统计指标",
        )

    def handle(self, *args, **options):
        """执行命令主逻辑。"""
        self.stdout.write(
            self.style.SUCCESS("=== Volume Trap 回测分析开始 ===")
        )
        start_time = timezone.now()

        # 解析筛选条件
        filters = self._parse_filters(options)
        self.stdout.write(f"筛选条件: {filters}")

        # 获取异常事件查询集
        queryset = self._get_monitor_queryset(filters, options["force"])

        if not queryset.exists():
            self.stdout.write(
                self.style.WARNING("没有找到符合条件的异常事件")
            )
            return

        self.stdout.write(f"找到 {queryset.count()} 个异常事件待处理")

        # 执行批量回测
        success_count, error_count, errors = self._run_batch_backtest(
            queryset, options
        )

        # 显示执行结果
        self._display_results(
            success_count, error_count, errors, start_time
        )

        # 计算整体统计（如果需要）
        if options["calculate_stats"]:
            self._calculate_statistics(filters)

        self.stdout.write(
            self.style.SUCCESS("=== 回测分析完成 ===")
        )

    def _parse_filters(self, options):
        """解析筛选条件。"""
        filters = {}

        if options["status"]:
            filters["status"] = options["status"]
        if options["market_type"]:
            filters["market_type"] = options["market_type"]
        if options["interval"]:
            filters["interval"] = options["interval"]
        if options["symbol"]:
            filters["symbol"] = options["symbol"]
        if options["start_date"]:
            filters["start_date"] = options["start_date"]
        if options["end_date"]:
            filters["end_date"] = options["end_date"]

        return filters

    def _get_monitor_queryset(self, filters, force=False):
        """获取异常事件查询集。"""
        queryset = VolumeTrapMonitor.objects.all()

        # 应用筛选条件
        if "status" in filters:
            queryset = queryset.filter(status=filters["status"])
        if "market_type" in filters:
            queryset = queryset.filter(market_type=filters["market_type"])
        if "interval" in filters:
            queryset = queryset.filter(interval=filters["interval"])

        # 交易对筛选需要通过关联表
        if "symbol" in filters:
            symbol = filters["symbol"]
            queryset = queryset.filter(
                Q(futures_contract__symbol__icontains=symbol)
                | Q(spot_contract__symbol__icontains=symbol)
            )

        # 日期筛选
        if "start_date" in filters:
            queryset = queryset.filter(trigger_time__date__gte=filters["start_date"])
        if "end_date" in filters:
            queryset = queryset.filter(trigger_time__date__lte=filters["end_date"])

        # 如果不强制执行，跳过已有回测结果的记录
        if not force:
            queryset = queryset.filter(backtest_result__isnull=True)

        return queryset.order_by("trigger_time")

    def _run_batch_backtest(self, queryset, options):
        """执行批量回测。"""
        self.stdout.write("\n开始执行批量回测...")

        # 创建批量回测器
        runner = BatchBacktestRunner()

        # 设置参数
        observation_bars = options["observation_bars"]
        skip_errors = options["skip_errors"]

        # 执行批量回测
        success_count, error_count, errors = runner.run_batch_backtest(
            queryset,
            observation_bars=observation_bars,
            skip_on_error=skip_errors,
        )

        return success_count, error_count, errors

    def _display_results(self, success_count, error_count, errors, start_time):
        """显示执行结果。"""
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("回测执行结果:")
        self.stdout.write(f"  成功: {success_count} 个")
        self.stdout.write(f"  失败: {error_count} 个")
        self.stdout.write(f"  总耗时: {duration:.2f} 秒")

        if errors:
            self.stdout.write(
                self.style.WARNING(f"\n错误详情 (前10个):")
            )
            for i, error in enumerate(errors[:10], 1):
                self.stdout.write(
                    f"  {i}. {error['symbol']}: {error['error']}"
                )

            if len(errors) > 10:
                self.stdout.write(
                    f"  ... 还有 {len(errors) - 10} 个错误"
                )

    def _calculate_statistics(self, filters):
        """计算整体统计指标。"""
        self.stdout.write("\n开始计算整体统计指标...")

        try:
            calculator = StatisticsCalculator()

            # 计算整体统计
            stats = calculator.calculate_overall_stats(
                market_type=filters.get("market_type"),
                interval=filters.get("interval"),
                status_filter=filters.get("status"),
                start_date=filters.get("start_date"),
                end_date=filters.get("end_date"),
            )

            # 显示统计结果
            self.stdout.write("\n" + "=" * 50)
            self.stdout.write("整体统计结果:")
            self.stdout.write(f"  统计名称: {stats.name}")
            self.stdout.write(f"  总交易数: {stats.total_trades}")
            self.stdout.write(f"  盈利交易数: {stats.profitable_trades}")
            self.stdout.write(f"  亏损交易数: {stats.losing_trades}")
            self.stdout.write(f"  胜率: {stats.win_rate}%")
            self.stdout.write(f"  平均收益率: {stats.avg_profit_percent}%")
            self.stdout.write(f"  最大收益: {stats.max_profit_percent}%")
            self.stdout.write(f"  最小收益: {stats.min_profit_percent}%")
            self.stdout.write(f"  平均回撤: {stats.avg_max_drawdown}%")
            self.stdout.write(f"  最差回撤: {stats.worst_drawdown}%")
            self.stdout.write(f"  盈亏比: {stats.profit_factor}")

            self.stdout.write(
                self.style.SUCCESS("统计计算完成")
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"统计计算失败: {e}")
            )
            raise
