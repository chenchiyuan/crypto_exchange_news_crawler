"""
backtest_grid Django Management Command

用途: 运行网格交易回测
"""

from django.core.management.base import BaseCommand, CommandError
from decimal import Decimal
from datetime import datetime
import os

from grid_trading.models import GridConfig
from grid_trading.services.backtest.backtest_engine import BacktestEngine
from grid_trading.services.backtest.kline_loader import KlineLoader
from grid_trading.services.backtest.report import BacktestReportGenerator


class Command(BaseCommand):
    """
    网格交易回测命令

    示例:
        python manage.py backtest_grid --config-id 1 --csv data/MONUSDT_1m.csv
        python manage.py backtest_grid --config-name mon_grid --csv data/MONUSDT_1m.csv --equity 10000
    """

    help = "运行网格交易策略回测"

    def add_arguments(self, parser):
        """添加命令行参数"""
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--config-id",
            type=int,
            help="网格配置ID",
        )
        group.add_argument(
            "--config-name",
            type=str,
            help="网格配置名称",
        )
        
        parser.add_argument(
            "--csv",
            type=str,
            required=True,
            help="K线数据CSV文件路径",
        )
        
        parser.add_argument(
            "--equity",
            type=float,
            default=10000,
            help="初始权益（默认10000）",
        )
        
        parser.add_argument(
            "--slippage",
            action="store_true",
            help="启用滑点模拟（默认关闭）",
        )
        
        parser.add_argument(
            "--tick-interval",
            type=int,
            default=1,
            help="每N根K线执行一次tick（默认1）",
        )
        
        parser.add_argument(
            "--output",
            type=str,
            help="输出报告文件路径（可选）",
        )
        
        parser.add_argument(
            "--output-format",
            type=str,
            choices=['text', 'json'],
            default='text',
            help="报告格式（text/json，默认text）",
        )

    def handle(self, *args, **options):
        """命令主逻辑"""
        try:
            # 加载配置
            config = self.load_config(options)
            
            self.stdout.write(
                self.style.SUCCESS(f"=== 网格交易回测 ===")
            )
            self.stdout.write(f"配置: {config.name}")
            self.stdout.write(f"交易对: {config.symbol}")
            self.stdout.write(f"网格模式: {config.grid_mode}")
            self.stdout.write(f"价格区间: {config.lower_price} - {config.upper_price}")
            self.stdout.write(f"网格层数: {config.grid_levels}")
            self.stdout.write(f"初始权益: {options['equity']}")
            self.stdout.write("")
            
            # 检查CSV文件
            csv_path = options['csv']
            if not os.path.exists(csv_path):
                raise CommandError(f"CSV文件不存在: {csv_path}")
            
            # 加载K线数据
            self.stdout.write("加载K线数据...")
            loader = KlineLoader()
            klines = loader.load_from_csv(csv_path)
            
            if not klines:
                raise CommandError("K线数据为空")
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ 加载了 {len(klines)} 条K线数据"
                )
            )
            self.stdout.write(
                f"  时间范围: {klines[0].timestamp} - {klines[-1].timestamp}"
            )
            self.stdout.write("")
            
            # 创建回测引擎
            initial_equity = Decimal(str(options['equity']))
            engine = BacktestEngine(
                config=config,
                initial_equity=initial_equity,
                enable_slippage=options['slippage']
            )
            
            # 运行回测
            self.stdout.write("开始回测...")
            self.stdout.write("")
            
            result = engine.run(
                klines=klines,
                tick_interval=options['tick_interval']
            )
            
            # 生成报告
            report_gen = BacktestReportGenerator(result, config.name)
            
            # 输出到终端
            self.stdout.write("")
            self.stdout.write(report_gen.generate_text_report())
            
            # 保存到文件
            output_path = options.get('output')
            if output_path:
                report_gen.save_to_file(
                    output_path,
                    format=options['output_format']
                )
                self.stdout.write("")
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ 报告已保存到: {output_path}"
                    )
                )
            
        except Exception as e:
            raise CommandError(f"回测失败: {str(e)}")

    def load_config(self, options):
        """加载网格配置"""
        config_id = options.get('config_id')
        config_name = options.get('config_name')
        
        try:
            if config_id:
                config = GridConfig.objects.get(id=config_id)
            else:
                config = GridConfig.objects.get(name=config_name)
            return config
        except GridConfig.DoesNotExist:
            if config_id:
                raise CommandError(f"未找到ID为 {config_id} 的配置")
            else:
                raise CommandError(f"未找到名称为 {config_name} 的配置")
