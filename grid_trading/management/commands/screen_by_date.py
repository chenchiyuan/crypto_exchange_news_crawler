"""
按日期筛选命令 - 基于每日10点前数据分析

用途: 以交易日为单位，分析符合选币条件的合约标的
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from decimal import Decimal
from pathlib import Path
from datetime import datetime, time, timedelta
import pytz

from grid_trading.services.screening_engine import ScreeningEngine
from grid_trading.services.html_report import HTMLReportGenerator
from grid_trading.models import ScreeningRecord, ScreeningResultModel


class Command(BaseCommand):
    """
    按日期筛选命令

    说明:
        - 如果指定日期已存在筛选记录，会自动删除旧记录并重新计算
        - 每次执行都会使用最新的市场数据重新分析

    示例:
        # 执行当天分析（默认）
        python manage.py screen_by_date

        # 指定日期（自动更新已有记录）
        python manage.py screen_by_date --date 2024-12-05

        # 批量执行日期范围
        python manage.py screen_by_date --from-date 2024-12-01 --to-date 2024-12-05

        # 自定义筛选条件
        python manage.py screen_by_date --min-vdr 6 --min-amplitude 50
    """

    help = "按交易日筛选合约标的（基于每日10点前数据）"

    def add_arguments(self, parser):
        """添加命令行参数"""
        # 日期参数
        parser.add_argument(
            "--date",
            type=str,
            default=None,
            help="指定筛选日期 (格式: YYYY-MM-DD)，默认为当天",
        )

        parser.add_argument(
            "--from-date",
            type=str,
            default=None,
            help="批量执行起始日期 (格式: YYYY-MM-DD)",
        )

        parser.add_argument(
            "--to-date",
            type=str,
            default=None,
            help="批量执行结束日期 (格式: YYYY-MM-DD)",
        )

        # 初筛参数
        parser.add_argument(
            "--min-volume",
            type=float,
            default=5000000,  # 默认500万USDT
            help="最小24h交易量阈值 (USDT, 默认: 5000000)",
        )

        parser.add_argument(
            "--min-days",
            type=int,
            default=0,
            help="最小上市天数 (默认: 0, 不限制)",
        )

        # 权重参数
        parser.add_argument(
            "--vdr-weight",
            type=float,
            default=0.40,
            help="VDR权重 (默认: 0.40)",
        )

        parser.add_argument(
            "--ker-weight",
            type=float,
            default=0.30,
            help="KER权重 (默认: 0.30)",
        )

        parser.add_argument(
            "--ovr-weight",
            type=float,
            default=0.20,
            help="OVR权重 (默认: 0.20)",
        )

        parser.add_argument(
            "--cvd-weight",
            type=float,
            default=0.10,
            help="CVD权重 (默认: 0.10)",
        )

        # 过滤参数（默认不过滤,只保存所有分析结果）
        parser.add_argument(
            "--min-vdr",
            type=float,
            default=None,
            help="VDR最小值 (默认: 不过滤)",
        )

        parser.add_argument(
            "--min-ker",
            type=float,
            default=None,
            help="KER最小值 (默认: 不过滤)",
        )

        parser.add_argument(
            "--min-amplitude",
            type=float,
            default=None,
            help="15分钟振幅累计最小值(百分比) (默认: 不过滤)",
        )

        parser.add_argument(
            "--min-funding-rate",
            type=float,
            default=None,
            help="年化资金费率最小值(百分比) (默认: 不过滤)",
        )

        parser.add_argument(
            "--max-ma99-slope",
            type=float,
            default=None,
            help="EMA99斜率最大值 (默认: 不过滤)",
        )

        # 执行控制
        parser.add_argument(
            "--no-html",
            action="store_true",
            help="不生成HTML报告",
        )

        # K线缓存
        parser.add_argument(
            "--use-cache",
            action="store_true",
            default=True,
            help="使用K线数据缓存 (默认启用)",
        )

        parser.add_argument(
            "--no-cache",
            dest="use_cache",
            action="store_false",
            help="禁用缓存,直接从API获取数据",
        )

    def handle(self, *args, **options):
        """执行命令"""
        try:
            # ========== 解析日期参数 ==========
            single_date = options.get("date")
            from_date = options.get("from_date")
            to_date = options.get("to_date")

            # 确定执行模式
            if from_date and to_date:
                # 批量模式
                dates_to_process = self._get_date_range(from_date, to_date)
                self.stdout.write(f"📅 批量执行模式: {from_date} 至 {to_date} (共{len(dates_to_process)}天)")
            elif single_date:
                # 单日模式
                dates_to_process = [self._parse_date(single_date)]
                self.stdout.write(f"📅 单日执行模式: {single_date}")
            else:
                # 默认当天
                dates_to_process = [timezone.now().date()]
                self.stdout.write(f"📅 默认当天模式: {dates_to_process[0]}")

            # ========== 执行筛选 ==========
            success_count = 0
            fail_count = 0

            for target_date in dates_to_process:
                try:
                    result = self._screen_for_date(target_date, options)
                    if result == "success":
                        success_count += 1
                except Exception as e:
                    fail_count += 1
                    self.stdout.write(
                        self.style.ERROR(f"❌ 日期 {target_date} 执行失败: {str(e)}")
                    )
                    continue

            # ========== 输出总结 ==========
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write("✅ 批量执行完成")
            self.stdout.write("=" * 70)
            self.stdout.write(f"  成功: {success_count} 天")
            self.stdout.write(f"  失败: {fail_count} 天")
            self.stdout.write("")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ 执行失败: {str(e)}"))
            raise CommandError(f"按日期筛选执行失败: {str(e)}")

    def _screen_for_date(self, target_date, options):
        """
        执行指定日期的筛选

        Args:
            target_date: date对象
            options: 命令行参数

        Returns:
            "success"
        """
        verbosity = options.get("verbosity", 1)

        # ========== 检查并删除已有记录（自动更新模式）==========
        existing = ScreeningRecord.objects.filter(screening_date=target_date).first()
        if existing:
            self.stdout.write(f"🔄 发现已有记录 (ID={existing.id})，删除后重新计算...")
            existing.delete()

        # ========== 输出配置信息 ==========
        if verbosity >= 1:
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write(f"🎯 筛选日期: {target_date}")
            self.stdout.write("=" * 70)

        # ========== 解析参数 ==========
        vdr_weight = options["vdr_weight"]
        ker_weight = options["ker_weight"]
        ovr_weight = options["ovr_weight"]
        cvd_weight = options["cvd_weight"]

        # 验证权重之和
        total_weight = vdr_weight + ker_weight + ovr_weight + cvd_weight
        if abs(total_weight - 1.0) > 0.001:
            raise CommandError(f"权重之和必须为1.0, 当前为{total_weight:.3f}")

        min_volume = Decimal(str(options["min_volume"]))
        min_days = options["min_days"]
        use_cache = options.get("use_cache", True)
        no_html = options.get("no_html", False)

        # 过滤条件
        min_vdr = options.get("min_vdr")
        min_ker = options.get("min_ker")
        min_amplitude = options.get("min_amplitude")
        min_funding_rate = options.get("min_funding_rate")
        max_ma99_slope = options.get("max_ma99_slope")

        if verbosity >= 1:
            self.stdout.write(f"\n筛选条件:")
            self.stdout.write(f"  VDR >= {min_vdr}")
            self.stdout.write(f"  15m振幅 >= {min_amplitude}%")
            self.stdout.write(f"  年化资费 >= {min_funding_rate}%")
            self.stdout.write(f"  EMA99斜率 <= {max_ma99_slope}")
            self.stdout.write(f"  24h成交量 >= ${min_volume:,}")
            self.stdout.write(f"\n权重配置:")
            self.stdout.write(f"  VDR={vdr_weight:.0%} KER={ker_weight:.0%} OVR={ovr_weight:.0%} CVD={cvd_weight:.0%}")
            self.stdout.write("")

        # ========== 计算数据截止时间（当天10点） ==========
        from datetime import datetime, time as dt_time
        import pytz

        # 使用UTC+8时区（币安时区）
        tz = pytz.timezone('Asia/Shanghai')
        cutoff_datetime = datetime.combine(target_date, dt_time(10, 0))
        cutoff_datetime = tz.localize(cutoff_datetime)

        if verbosity >= 1:
            self.stdout.write(f"  数据截止时间: {cutoff_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        # ========== 创建筛选引擎 ==========
        # 使用缓存模式: KlineCache会智能地按需获取历史数据并保存到数据库
        engine = ScreeningEngine(
            top_n=999,
            weights=[0.25, 0.25, 0.25, 0.25],
            min_volume=min_volume,
            min_days=min_days,
            interval="4h",
            use_cache=use_cache,  # 启用智能缓存(按需获取+自动补全)
        )

        # ========== 执行筛选 ==========
        import time
        start_time = time.time()

        results = engine.run_simple_screening(
            vdr_weight=vdr_weight,
            ker_weight=ker_weight,
            ovr_weight=ovr_weight,
            cvd_weight=cvd_weight,
            min_vdr=min_vdr,
            min_ker=min_ker,
            min_amplitude=min_amplitude,
            min_funding_rate=min_funding_rate,
            max_ma99_slope=max_ma99_slope,
            end_time=cutoff_datetime,
        )

        elapsed = time.time() - start_time

        # ========== 保存到数据库 ==========
        if not results:
            self.stdout.write(self.style.WARNING("\n⚠️ 无合格标的，跳过保存"))
            return "success"

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("💾 保存到数据库")
        self.stdout.write("=" * 70)

        # 创建筛选记录（关键：设置screening_date）
        record = ScreeningRecord.objects.create(
            screening_date=target_date,  # ← 关键字段
            min_volume=min_volume,
            min_days=min_days,
            vdr_weight=vdr_weight,
            ker_weight=ker_weight,
            ovr_weight=ovr_weight,
            cvd_weight=cvd_weight,
            filter_min_vdr=min_vdr,
            filter_min_ker=min_ker,
            filter_min_amplitude=min_amplitude,
            filter_min_funding_rate=min_funding_rate,
            filter_max_ma99_slope=max_ma99_slope,
            total_candidates=len(results),
            execution_time=elapsed,
            notes=f"日历筛选 {target_date} - VDR:{vdr_weight*100:.0f}% KER:{ker_weight*100:.0f}%"
        )

        # 批量创建筛选结果
        screening_results = []
        for rank, score in enumerate(results, 1):
            screening_results.append(
                ScreeningResultModel(
                    record=record,
                    rank=rank,
                    symbol=score.symbol,
                    current_price=score.current_price,
                    vdr=score.vdr,
                    ker=score.ker,
                    ovr=score.ovr,
                    cvd_divergence=score.cvd_divergence,
                    amplitude_sum_15m=score.amplitude_sum_15m,
                    annual_funding_rate=score.annual_funding_rate,
                    open_interest=score.open_interest,
                    volume_24h_calculated=score.volume_24h_calculated,
                    vol_oi_ratio=score.vol_oi_ratio,
                    fdv=score.fdv,
                    oi_fdv_ratio=score.oi_fdv_ratio,
                    has_spot=score.has_spot,
                    ma99_slope=score.ma99_slope,
                    ma20_slope=score.ma20_slope,
                    vdr_score=score.vdr_score,
                    ker_score=score.ker_score,
                    ovr_score=score.ovr_score,
                    cvd_score=score.cvd_score,
                    composite_index=score.composite_index,
                    grid_upper_limit=score.grid_upper_limit,
                    grid_lower_limit=score.grid_lower_limit,
                    grid_count=score.grid_count,
                    grid_step=score.grid_step,
                    take_profit_price=score.take_profit_price,
                    stop_loss_price=score.stop_loss_price,
                    take_profit_pct=score.take_profit_pct,
                    stop_loss_pct=score.stop_loss_pct,
                    rsi_15m=score.rsi_15m,
                    recommended_entry_price=score.recommended_entry_price,
                    entry_trigger_prob_24h=score.entry_trigger_prob_24h,
                    entry_trigger_prob_72h=score.entry_trigger_prob_72h,
                    entry_strategy_label=score.entry_strategy_label,
                    entry_rebound_pct=score.entry_rebound_pct,
                    entry_avg_trigger_time=score.entry_avg_trigger_time,
                    entry_expected_return_24h=score.entry_expected_return_24h,
                    entry_candidates_json=score.entry_candidates if score.entry_candidates else [],
                    highest_price_300=score.highest_price_300,
                    drawdown_from_high_pct=score.drawdown_from_high_pct,
                )
            )

        ScreeningResultModel.objects.bulk_create(screening_results)

        self.stdout.write(self.style.SUCCESS(f"✓ 已保存筛选记录 ID={record.id}"))
        self.stdout.write(f"  日期: {target_date}")
        self.stdout.write(f"  标的数: {len(screening_results)}")
        self.stdout.write(f"  耗时: {elapsed:.1f}秒")

        # ========== 生成HTML报告（可选） ==========
        if not no_html:
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write("📄 生成HTML报告")
            self.stdout.write("=" * 70)

            generator = HTMLReportGenerator()
            output_path = f"screening_reports/daily_{target_date}.html"
            output_file = generator.generate_report(results, output_path)

            self.stdout.write(self.style.SUCCESS(f"\n✅ HTML报告: {output_file}"))

            abs_path = Path(output_file).resolve()
            self.stdout.write(self.style.SUCCESS(f"👉 file://{abs_path}"))

        self.stdout.write("")
        return "success"

    def _parse_date(self, date_str):
        """解析日期字符串"""
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise CommandError(f"日期格式错误: {date_str}，正确格式为 YYYY-MM-DD")

    def _get_date_range(self, from_date_str, to_date_str):
        """获取日期范围列表"""
        from_date = self._parse_date(from_date_str)
        to_date = self._parse_date(to_date_str)

        if from_date > to_date:
            raise CommandError("起始日期不能晚于结束日期")

        dates = []
        current = from_date
        while current <= to_date:
            dates.append(current)
            current += timedelta(days=1)

        return dates
