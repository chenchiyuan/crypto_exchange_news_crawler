"""
巨量诱多/弃盘检测扫描命令

用途：执行三阶段状态机扫描，检测巨量诱多/弃盘信号

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md (第四部分-6.2 监控扫描任务)
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md (管理命令层)
    - Task: TASK-002-031
"""

import json
import logging
import os
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from volume_trap.services.volume_trap_fsm import VolumeTrapStateMachine

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """巨量诱多/弃盘检测扫描命令。

    调用VolumeTrapStateMachine执行三阶段扫描，检测弃盘信号。

    业务逻辑：
        1. 初始化VolumeTrapStateMachine（注入所有检测器）
        2. 调用FSM.scan(interval)执行三阶段扫描：
           - Discovery（发现）：全量扫描 → 创建Monitor记录
           - Confirmation（确认）：pending → suspected_abandonment
           - Validation（验证）：suspected → confirmed_abandonment
        3. 输出三阶段统计结果
        4. 记录详细的执行日志

    使用方法：
        # 默认：扫描全历史数据（4h周期）
        python manage.py scan_volume_traps --interval 4h

        # 历史扫描：指定日期范围
        python manage.py scan_volume_traps --interval 4h --start 2025-12-01 --end 2025-12-31

        # 实时扫描：只检查最新数据
        python manage.py scan_volume_traps --interval 4h --mode realtime

        # 扫描1h周期
        python manage.py scan_volume_traps --interval 1h

        # 扫描1d周期
        python manage.py scan_volume_traps --interval 1d

    执行频率：
        - 1h周期：每小时10分执行（如 "10 * * * *"）
        - 4h周期：每4小时10分执行（如 "10 */4 * * *"）
        - 1d周期：每日00:10执行（如 "10 0 * * *"）

    扫描模式：
        - historical（默认）：扫描全部历史时期或指定日期范围
        - realtime：只检查最新K线数据，执行三阶段状态机扫描

    设计原则：
        - 容错机制：单个合约失败不影响其他合约
        - 详细日志：记录每个阶段的扫描结果
        - 性能优化：使用Django ORM批量查询
        - 可监控：输出三阶段统计，便于监控告警

    Related:
        - PRD: 第四部分-6.2 监控扫描任务
        - Architecture: 管理命令层 - scan_volume_traps
        - Task: TASK-002-031
    """

    help = "Scan for volume trap signals using three-phase state machine (默认扫描全历史数据)"

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
        parser.add_argument("--start", type=str, help='开始日期 (YYYY-MM-DD) 或 "all" (全部历史)')
        parser.add_argument("--end", type=str, help="结束日期 (YYYY-MM-DD)")
        parser.add_argument("--batch-size", type=int, default=1000, help="批处理大小 (默认1000)")
        parser.add_argument(
            "--mode",
            type=str,
            choices=["historical", "realtime"],
            default="historical",
            help="扫描模式：historical(历史扫描，默认)或realtime(实时扫描)",
        )

    def handle(self, *args, **options):
        """执行扫描（支持实时扫描和历史扫描）。

        Args:
            *args: 位置参数（未使用）
            **options: 命令行参数，包含：
                - interval (str): K线周期
                - market_type (str): 市场类型
                - start (str): 开始日期（可选）
                - end (str): 结束日期（可选）
                - batch_size (int): 批处理大小（可选）

        Side Effects:
            - 创建/更新VolumeTrapMonitor记录
            - 创建VolumeTrapStateTransition日志
            - 创建VolumeTrapIndicators快照
            - 输出详细的执行日志

        Raises:
            CommandError: 当FSM异常时

        Context:
            - TASK-005-003: 实现scan_volume_traps命令参数解析
            - Architecture: Discovery历史扫描优化

        Examples:
            # 默认：历史扫描（全部历史数据）
            python manage.py scan_volume_traps --interval 4h

            # 历史扫描（指定范围）
            python manage.py scan_volume_traps --interval 4h --start 2025-11-01 --end 2025-11-30

            # 实时扫描（只检查最新数据）
            python manage.py scan_volume_traps --interval 4h --mode realtime

            # 自定义批处理大小
            python manage.py scan_volume_traps --interval 4h --batch-size 500
        """
        interval = options["interval"]
        market_type = options["market_type"]
        start_date = options.get("start")
        end_date = options.get("end")
        batch_size = options.get("batch_size")
        scan_mode = options.get("mode", "historical")

        # === 验证日期参数 ===
        if start_date and start_date != "all":
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                raise CommandError("日期格式应为YYYY-MM-DD")

        if end_date:
            try:
                datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                raise CommandError("日期格式应为YYYY-MM-DD")

        # === 默认值处理 ===
        # 默认扫描模式：historical（历史扫描）
        # 如果没有指定start_date，且是历史模式，则默认为'all'（全部历史）
        if scan_mode == "historical" and not start_date:
            start_date = "all"

        # === 日志：开始执行 ===
        start_time = timezone.now()

        # 判断是历史扫描还是实时扫描
        is_historical = scan_mode == "historical"

        if is_historical:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n=== 开始历史扫描 (interval={interval}, market_type={market_type}) ==="
                )
            )
            self.stdout.write(f'  日期范围: {start_date} 到 {end_date or "最新"}')
            self.stdout.write(f"  批处理大小: {batch_size}")
            logger.info(
                f"开始历史扫描: interval={interval}, market_type={market_type}, "
                f"start={start_date}, end={end_date}, batch_size={batch_size}"
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n=== 开始实时扫描 (interval={interval}, market_type={market_type}) ==="
                )
            )
            logger.info(f"开始实时扫描: interval={interval}, market_type={market_type}")

        try:
            # === Step 1: 初始化状态机 ===
            self.stdout.write("\n初始化状态机...")
            fsm = VolumeTrapStateMachine()
            self.stdout.write(self.style.SUCCESS("✓ 状态机初始化完成"))

            # === Step 2: 执行扫描 ===
            if is_historical:
                # 历史扫描
                self.stdout.write(f"\n执行历史扫描...\n")
                result = fsm.scan_historical(
                    interval=interval,
                    market_type=market_type,
                    start_date=start_date,
                    end_date=end_date,
                    batch_size=batch_size,
                )

                # 输出历史扫描结果
                self.stdout.write(self.style.SUCCESS(f"\n=== 历史扫描完成 ==="))
                self.stdout.write(f'  总交易对: {result["total_contracts"]}个')
                self.stdout.write(f'  已处理: {result["processed"]}个')
                self.stdout.write(self.style.SUCCESS(f'  发现异常事件: {result["found_events"]}个'))

            # === Step 3: 计算耗时 ===
            end_time = timezone.now()
            elapsed = (end_time - start_time).total_seconds()

            # === Step 4: 保存JSON结果（仅历史扫描）===
            if is_historical:
                try:
                    # 确保data目录存在（项目根目录的data目录）
                    project_root = os.path.dirname(
                        os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                    )
                    data_dir = os.path.join(project_root, "data")
                    os.makedirs(data_dir, exist_ok=True)

                    # 生成时间戳文件名
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"historical_scan_{interval}_{market_type}_{timestamp}.json"
                    filepath = os.path.join(data_dir, filename)

                    # 准备JSON数据（包含元数据）
                    json_data = {
                        "scan_metadata": {
                            "scan_type": "historical",
                            "interval": interval,
                            "market_type": market_type,
                            "start_date": start_date,
                            "end_date": end_date or "latest",
                            "batch_size": batch_size,
                            "scan_time": start_time.isoformat(),
                            "completion_time": end_time.isoformat(),
                            "elapsed_seconds": elapsed,
                        },
                        "scan_statistics": {
                            "total_contracts": result["total_contracts"],
                            "processed_contracts": result["processed"],
                            "found_events": result["found_events"],
                        },
                        "scan_results": [
                            {
                                "symbol": (
                                    event.futures_contract.symbol
                                    if hasattr(event, "futures_contract") and event.futures_contract
                                    else (
                                        event.spot_contract.symbol
                                        if hasattr(event, "spot_contract") and event.spot_contract
                                        else None
                                    )
                                ),
                                "interval": event.interval,
                                "status": event.status,
                                "trigger_time": (
                                    event.trigger_time.isoformat()
                                    if hasattr(event, "trigger_time") and event.trigger_time
                                    else None
                                ),
                                "trigger_price": (
                                    str(event.trigger_price)
                                    if hasattr(event, "trigger_price")
                                    else None
                                ),
                                "created_at": (
                                    event.created_at.isoformat()
                                    if hasattr(event, "created_at")
                                    else None
                                ),
                            }
                            for event in result.get("events", [])
                        ],
                    }

                    # 保存JSON文件
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)

                    # 友好打印扫描摘要
                    self.stdout.write(self.style.SUCCESS(f"\n✓ 扫描结果已保存到: {filepath}"))
                    self.stdout.write(
                        f"  📊 扫描摘要:\n"
                        f'     - 扫描范围: {start_date} 到 {end_date or "最新"}\n'
                        f'     - 交易对总数: {result["total_contracts"]}个\n'
                        f'     - 已处理: {result["processed"]}个\n'
                        f'     - 发现异常: {result["found_events"]}个\n'
                        f'     - 异常率: {result["found_events"]/result["processed"]*100:.2f}%\n'
                        f"     - JSON大小: {os.path.getsize(filepath)/1024:.1f}KB"
                    )

                    # 友好预览前5个异常事件
                    if result.get("events"):
                        self.stdout.write(f"\n  🔍 前5个异常事件预览:\n")
                        for i, event in enumerate(result["events"][:5], 1):
                            symbol = (
                                event.futures_contract.symbol
                                if hasattr(event, "futures_contract") and event.futures_contract
                                else (
                                    event.spot_contract.symbol
                                    if hasattr(event, "spot_contract") and event.spot_contract
                                    else "Unknown"
                                )
                            )
                            self.stdout.write(
                                f"     {i}. {symbol} - {event.status} - 触发价: {event.trigger_price}"
                            )
                        if len(result["events"]) > 5:
                            self.stdout.write(
                                f'     ... 还有 {len(result["events"]) - 5} 个事件，详见JSON文件'
                            )

                    # 友好日志记录
                    logger.info(
                        f"历史扫描完成: interval={interval}, contracts={result['processed']}, "
                        f"events={result['found_events']}, elapsed={elapsed:.2f}s, "
                        f"output={filepath}"
                    )

                except Exception as e:
                    # JSON保存失败不影响主流程
                    logger.error(f"保存JSON文件失败: {str(e)}", exc_info=True)
                    self.stdout.write(self.style.WARNING(f"\n⚠️  保存JSON文件失败: {str(e)}"))

            else:
                # 实时扫描（三阶段）
                self.stdout.write(f"\n执行三阶段扫描...\n")
                result = fsm.scan(interval=interval, market_type=market_type)

                # 输出实时扫描结果
                self.stdout.write(self.style.SUCCESS(f"\n=== 实时扫描完成 ==="))
                self.stdout.write(f'  阶段1 - Discovery（发现）: {result["discovery"]}个')
                self.stdout.write(f'  阶段2 - Confirmation（确认）: {result["confirmation"]}个')
                self.stdout.write(f'  阶段3 - Validation（验证）: {result["validation"]}个')

                # 输出错误信息（如果有）
                if result["errors"]:
                    self.stdout.write(self.style.WARNING(f'  错误数: {len(result["errors"])}'))
                    for error in result["errors"]:
                        self.stdout.write(self.style.ERROR(f"    - {error}"))

            # === Step 5: 输出耗时 ===
            self.stdout.write(f"  耗时: {elapsed:.2f}秒\n")

            logger.info(
                f"扫描完成: {interval} {market_type}, contracts={result['processed']}, "
                f"events={result['found_events']}, elapsed={elapsed:.2f}秒"
            )

            # === Step 6: 错误检查 ===
            # 如果有错误，以非0退出码退出（便于监控）
            if "errors" in result and result["errors"]:
                raise CommandError(f'扫描完成，但存在{len(result["errors"])}个错误')

        except ValueError as e:
            # 参数错误
            logger.error(f"参数错误: {str(e)}")
            raise CommandError(f"参数错误: {str(e)}")

        except Exception as e:
            # 捕获未预期的异常
            logger.error(f"扫描异常: {str(e)}", exc_info=True)
            raise CommandError(f"扫描失败: {str(e)}")
