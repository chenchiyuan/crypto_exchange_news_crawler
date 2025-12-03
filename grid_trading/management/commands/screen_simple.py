"""
简化筛选命令 - 只基于VDR/KER/OVR/CVD四个核心指标

用途: 生成HTML报告,展示所有候选标的并按综合指数排序
"""

from django.core.management.base import BaseCommand, CommandError
from decimal import Decimal
from pathlib import Path

from grid_trading.services.screening_engine import ScreeningEngine
from grid_trading.services.html_report import HTMLReportGenerator


class Command(BaseCommand):
    """
    简化筛选命令

    示例:
        # 生成HTML报告(默认权重)
        python manage.py screen_simple

        # 自定义权重
        python manage.py screen_simple --vdr-weight 0.5 --ker-weight 0.3

        # 指定输出路径
        python manage.py screen_simple --output results.html
    """

    help = "基于VDR/KER/OVR/CVD四维指标筛选并生成HTML报告"

    def add_arguments(self, parser):
        """添加命令行参数"""
        # 初筛参数
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

        # 权重参数
        parser.add_argument(
            "--vdr-weight",
            type=float,
            default=0.40,
            help="VDR权重 (默认: 0.40, 即40%%)",
        )

        parser.add_argument(
            "--ker-weight",
            type=float,
            default=0.30,
            help="KER权重 (默认: 0.30, 即30%%)",
        )

        parser.add_argument(
            "--ovr-weight",
            type=float,
            default=0.20,
            help="OVR权重 (默认: 0.20, 即20%%)",
        )

        parser.add_argument(
            "--cvd-weight",
            type=float,
            default=0.10,
            help="CVD权重 (默认: 0.10, 即10%%)",
        )

        # 输出参数
        parser.add_argument(
            "--output",
            type=str,
            default="screening_reports/simple_screening_report.html",
            help="HTML报告输出路径 (默认: screening_reports/simple_screening_report.html)",
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
        """执行简化筛选"""
        try:
            # ========== 参数验证 ==========
            vdr_weight = options["vdr_weight"]
            ker_weight = options["ker_weight"]
            ovr_weight = options["ovr_weight"]
            cvd_weight = options["cvd_weight"]

            # 验证权重之和
            total_weight = vdr_weight + ker_weight + ovr_weight + cvd_weight
            if abs(total_weight - 1.0) > 0.001:
                raise CommandError(
                    f"权重之和必须为1.0, 当前为{total_weight:.3f}"
                )

            min_volume = Decimal(str(options["min_volume"]))
            min_days = options["min_days"]
            use_cache = options.get("use_cache", True)
            output_path = options["output"]

            verbosity = options.get("verbosity", 1)

            # ========== 输出配置信息 ==========
            if verbosity >= 1:
                self.stdout.write("=" * 70)
                self.stdout.write("🎯 简化筛选模式 (VDR/KER/OVR/CVD)")
                self.stdout.write("=" * 70)
                self.stdout.write(f"\n初筛条件:")
                self.stdout.write(f"  最小流动性: ${min_volume:,} USDT")
                self.stdout.write(f"  最小上市天数: {min_days} 天")
                self.stdout.write(f"\n权重配置:")
                self.stdout.write(f"  VDR权重: {vdr_weight:.0%} (震荡性)")
                self.stdout.write(f"  KER权重: {ker_weight:.0%} (低效率)")
                self.stdout.write(f"  OVR权重: {ovr_weight:.0%} (低拥挤)")
                self.stdout.write(f"  CVD权重: {cvd_weight:.0%} (背离信号)")
                self.stdout.write(f"\n输出设置:")
                self.stdout.write(f"  HTML报告: {output_path}")
                self.stdout.write(f"  使用缓存: {'是' if use_cache else '否'}")
                self.stdout.write("")

            # ========== 创建筛选引擎 ==========
            engine = ScreeningEngine(
                top_n=999,  # 不限制数量,返回所有结果
                weights=[0.25, 0.25, 0.25, 0.25],  # 简化模式不使用这个权重
                min_volume=min_volume,
                min_days=min_days,
                interval="4h",
                use_cache=use_cache,
            )

            # ========== 执行简化筛选 ==========
            import time
            start_time = time.time()

            results = engine.run_simple_screening(
                vdr_weight=vdr_weight,
                ker_weight=ker_weight,
                ovr_weight=ovr_weight,
                cvd_weight=cvd_weight,
            )

            elapsed = time.time() - start_time

            # ========== 保存到数据库 ==========
            if not results:
                self.stdout.write(self.style.WARNING("\n⚠️ 无合格标的，跳过报告生成和数据保存"))
                return

            self.stdout.write("\n" + "=" * 70)
            self.stdout.write("💾 保存到数据库")
            self.stdout.write("=" * 70)

            from grid_trading.models import ScreeningRecord, ScreeningResultModel

            # 创建筛选记录
            record = ScreeningRecord.objects.create(
                min_volume=min_volume,
                min_days=min_days,
                vdr_weight=vdr_weight,
                ker_weight=ker_weight,
                ovr_weight=ovr_weight,
                cvd_weight=cvd_weight,
                total_candidates=len(results),
                execution_time=elapsed,
                notes=f"简化筛选 - VDR:{vdr_weight*100:.0f}% KER:{ker_weight*100:.0f}% OVR:{ovr_weight*100:.0f}% CVD:{cvd_weight*100:.0f}%"
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
                    )
                )

            ScreeningResultModel.objects.bulk_create(screening_results)

            self.stdout.write(self.style.SUCCESS(f"✓ 已保存筛选记录 ID={record.id}"))
            self.stdout.write(f"  包含 {len(screening_results)} 个标的")

            # ========== 生成HTML报告 ==========
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write("📄 生成HTML报告")
            self.stdout.write("=" * 70)

            generator = HTMLReportGenerator()
            output_file = generator.generate_report(results, output_path)

            self.stdout.write(self.style.SUCCESS(f"\n✅ HTML报告已生成: {output_file}"))
            self.stdout.write(f"  候选标的总数: {len(results)}")
            self.stdout.write(f"  Top 3 标的:")

            for i, score in enumerate(results[:3], 1):
                data = score.to_dict()
                self.stdout.write(
                    f"    {i}. {data['symbol']:15} "
                    f"综合指数={data['composite_index']:.4f} "
                    f"VDR={data['vdr']:.1f} "
                    f"KER={data['ker']:.3f} "
                    f"OVR={data['ovr']:.2f} "
                    f"CVD={data['cvd']}"
                )

            # ========== 输出执行摘要 ==========
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write(f"✅ 筛选完成")
            self.stdout.write("=" * 70)
            self.stdout.write(f"  执行时长: {elapsed:.1f}秒")
            self.stdout.write(f"  候选标的: {len(results)} 个")
            self.stdout.write(f"  HTML报告: {output_file}")
            self.stdout.write("")

            # 提示用户打开报告
            abs_path = Path(output_file).resolve()
            self.stdout.write(self.style.SUCCESS(f"👉 静态HTML报告: file://{abs_path}"))
            self.stdout.write(self.style.SUCCESS(f"👉 动态查询页面: http://127.0.0.1:8000/screening/"))
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("💡 提示: 动态页面支持按日期查询历史筛选结果"))
            self.stdout.write("")

        except CommandError as e:
            self.stdout.write(self.style.ERROR(f"\n❌ 参数错误: {str(e)}"))
            raise

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ 执行失败: {str(e)}"))
            if verbosity >= 2:
                import traceback
                self.stdout.write(traceback.format_exc())
            raise CommandError(f"简化筛选执行失败: {str(e)}")
