"""
screen_short_grid Django Management Command

用途: 做空网格标的量化筛选命令行工具
关联FR: FR-034至FR-037
"""

from django.core.management.base import BaseCommand, CommandError
from decimal import Decimal

from grid_trading.utils.validators import (
    validate_weights,
    validate_top_n,
    validate_min_volume,
    validate_min_days,
)
from grid_trading.utils.formatters import (
    format_config_output,
    format_pipeline_progress,
    format_results_table,
    format_execution_summary,
    format_no_results_output,
)
from grid_trading.services.screening_engine import ScreeningEngine


class Command(BaseCommand):
    """
    做空网格标的量化筛选命令

    示例:
        python manage.py screen_short_grid
        python manage.py screen_short_grid --top-n 10 --weights "0.3,0.3,0.2,0.2"
    """

    help = "筛选币安永续合约市场中最适合做空网格的标的"

    def add_arguments(self, parser):
        """
        添加命令行参数 (FR-035, T045)
        """
        parser.add_argument(
            "--top-n",
            type=int,
            default=5,
            help="输出Top N标的 (默认5, 范围3-10)",
        )

        parser.add_argument(
            "--weights",
            type=str,
            default="0.2,0.2,0.3,0.3",
            help="自定义权重 (格式: w1,w2,w3,w4, 默认: 0.2,0.2,0.3,0.3)",
        )

        parser.add_argument(
            "--min-volume",
            type=float,
            default=50000000,
            help="最小流动性阈值 (USDT, 默认: 50000000)",
        )

        parser.add_argument(
            "--min-days",
            type=int,
            default=30,
            help="最小上市天数 (默认: 30)",
        )

        parser.add_argument(
            "--interval",
            type=str,
            default="4h",
            choices=["1h", "4h", "1d"],
            help="K线周期 (默认: 4h)",
        )

    def handle(self, *args, **options):
        """
        执行筛选命令 (FR-036, FR-037, T046, T047)
        """
        try:
            # ========== 参数验证 ==========
            top_n = validate_top_n(options["top_n"])
            weights = validate_weights(options["weights"])
            min_volume = validate_min_volume(options["min_volume"])
            min_days = validate_min_days(options["min_days"])
            interval = options["interval"]

            verbosity = options.get("verbosity", 1)

            # ========== 输出配置信息 (FR-036) ==========
            if verbosity >= 1:
                config_output = format_config_output(
                    weights=weights,
                    min_volume=min_volume,
                    min_days=min_days,
                    interval=interval,
                    top_n=top_n,
                )
                self.stdout.write(config_output)

            # ========== 创建筛选引擎 ==========
            engine = ScreeningEngine(
                top_n=top_n,
                weights=weights,
                min_volume=min_volume,
                min_days=min_days,
                interval=interval,
            )

            # ========== 执行筛选 ==========
            import time

            start_time = time.time()
            results = engine.run_screening()
            elapsed = time.time() - start_time

            # ========== 格式化输出结果 (FR-031至FR-033) ==========
            if not results:
                # 无合格标的 (SC-008)
                no_results_output = format_no_results_output(
                    total_symbols=0,  # TODO: 从engine获取
                    passed_symbols=0,
                    reason="初筛后无合格标的",
                )
                self.stdout.write(no_results_output)
                return

            # 输出结果表格 (FR-031)
            self.stdout.write("\n")
            terminal_rows = [r.to_terminal_row() for r in results]
            table_output = format_results_table(terminal_rows)
            self.stdout.write(table_output)

            # 输出执行摘要 (FR-033, FR-037)
            summary_output = format_execution_summary(
                duration=elapsed,
                total_symbols=0,  # TODO: 从engine获取
                passed_symbols=0,
                top_n_count=len(results),
            )
            self.stdout.write(summary_output)

            # 成功标记
            self.stdout.write(self.style.SUCCESS(f"✅ 筛选完成，找到 {len(results)} 个标的"))

        except CommandError as e:
            self.stdout.write(self.style.ERROR(f"❌ 参数错误: {str(e)}"))
            raise

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ 执行失败: {str(e)}"))
            if verbosity >= 2:
                import traceback

                self.stdout.write(traceback.format_exc())
            raise CommandError(f"筛选执行失败: {str(e)}")
