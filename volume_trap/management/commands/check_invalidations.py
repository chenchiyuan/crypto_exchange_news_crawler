"""
失效检测命令

用途：检测价格收复情况，将监控记录标记为失效状态

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md (第四部分-6.3 失效检测任务)
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md (管理命令层)
    - Task: TASK-002-032
"""

import logging

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from volume_trap.services.invalidation_detector import InvalidationDetector

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """失效检测命令。

    调用InvalidationDetector检测价格收复，标记失效监控记录。

    业务逻辑：
        1. 初始化InvalidationDetector
        2. 调用detector.check_all(interval)检测所有非invalidated记录
        3. 对价格收复的监控记录（current_close > P_trigger）标记为invalidated
        4. 输出失效记录数统计
        5. 记录详细的执行日志

    使用方法：
        # 检测4h周期的失效记录（合约）
        python manage.py check_invalidations --interval 4h

        # 检测1h周期的失效记录（合约）
        python manage.py check_invalidations --interval 1h

        # 检测1d周期的失效记录（合约）
        python manage.py check_invalidations --interval 1d

        # 检测4h周期的失效记录（现货）
        python manage.py check_invalidations --interval 4h --market-type spot

        # 检测4h周期的失效记录（现货）
        python manage.py check_invalidations --interval 4h --market-type futures

    执行频率：
        - 1h周期：每小时15分执行（如 "15 * * * *"）
        - 4h周期：每4小时15分执行（如 "15 */4 * * *"）
        - 1d周期：每日00:15执行（如 "15 0 * * *"）

    设计原则：
        - 容错机制：单个合约失败不影响其他合约
        - 详细日志：记录每个失效记录的检测结果
        - 性能优化：使用Django ORM批量查询
        - 可监控：输出失效统计，便于监控告警

    Related:
        - PRD: 第四部分-6.3 失效检测任务
        - Architecture: 管理命令层 - check_invalidations
        - Task: TASK-002-032
    """

    help = "Check for price recovery and mark monitors as invalidated"

    def add_arguments(self, parser):
        """添加命令行参数。

        Args:
            parser: Django命令参数解析器
        """
        parser.add_argument(
            "--interval",
            type=str,
            default="4h",
            choices=["1h", "4h", "1d"],
            help="K线周期（1h/4h/1d），默认4h",
        )
        parser.add_argument(
            "--market-type",
            "-m",
            type=str,
            default="futures",
            choices=["spot", "futures"],
            help="市场类型（现货spot或合约futures），默认futures",
        )

    def handle(self, *args, **options):
        """执行失效检测。

        Args:
            *args: 位置参数（未使用）
            **options: 命令行参数，包含：
                - interval (str): K线周期
                - market_type (str): 市场类型

        Side Effects:
            - 更新VolumeTrapMonitor记录的status字段
            - 创建VolumeTrapStateTransition日志
            - 输出详细的执行日志

        Raises:
            CommandError: 当检测器异常时
        """
        interval = options["interval"]
        market_type = options["market_type"]

        # === 日志：开始执行 ===
        start_time = timezone.now()
        self.stdout.write(
            self.style.SUCCESS(
                f"\n=== 开始失效检测 (interval={interval}, market_type={market_type}) ==="
            )
        )
        logger.info(f"开始失效检测: interval={interval}, market_type={market_type}")

        try:
            # === Step 1: 初始化检测器 ===
            self.stdout.write("初始化失效检测器...")
            detector = InvalidationDetector()
            self.stdout.write(self.style.SUCCESS("✓ 检测器初始化完成"))

            # === Step 2: 执行失效检测 ===
            self.stdout.write(
                f"\n执行失效检测 (interval={interval}, market_type={market_type})...\n"
            )
            result = detector.check_all(interval=interval, market_type=market_type)

            # === Step 3: 输出统计结果 ===
            end_time = timezone.now()
            elapsed = (end_time - start_time).total_seconds()

            self.stdout.write(self.style.SUCCESS(f"\n=== 失效检测完成 ==="))
            self.stdout.write(f'  检测记录数: {result["checked_count"]}')
            self.stdout.write(f'  失效记录数: {result["invalidated_count"]}')

            # 输出错误信息（如果有）
            if result["errors"]:
                self.stdout.write(self.style.WARNING(f'  错误数: {len(result["errors"])}'))
                for error in result["errors"]:
                    self.stdout.write(self.style.ERROR(f"    - {error}"))

            self.stdout.write(f"  耗时: {elapsed:.2f}秒\n")

            logger.info(
                f"失效检测完成: 检测{result['checked_count']}, "
                f"失效{result['invalidated_count']}, "
                f"错误{len(result['errors'])}, "
                f"耗时{elapsed:.2f}秒"
            )

            # === Step 4: 错误检查 ===
            # 如果有错误，记录warning（不影响正常执行）
            if result["errors"]:
                self.stdout.write(
                    self.style.WARNING(f'\n⚠️  检测完成，但存在{len(result["errors"])}个错误')
                )

        except ValueError as e:
            # 参数错误
            logger.error(f"参数错误: {str(e)}")
            raise CommandError(f"参数错误: {str(e)}")

        except Exception as e:
            # 捕获未预期的异常
            logger.error(f"检测异常: {str(e)}", exc_info=True)
            raise CommandError(f"检测失败: {str(e)}")
