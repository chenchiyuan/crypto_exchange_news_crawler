"""
start_grid Django Management Command

用途: 启动网格交易策略
"""

from django.core.management.base import BaseCommand, CommandError
from decimal import Decimal
import logging
import time
import signal
import sys

from grid_trading.models import GridConfig
from grid_trading.services.grid.engine import GridEngine
from grid_trading.services.exchange.factory import create_adapter

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    启动网格交易命令

    示例:
        # 模拟模式（不连接交易所）
        python manage.py start_grid --config-id 1 --dry-run

        # 使用配置中指定的交易所
        python manage.py start_grid --config-id 1

        # 指定交易所（覆盖配置）
        python manage.py start_grid --config-name my_grid --exchange grvt

        # 自定义tick间隔
        python manage.py start_grid --config-id 1 --tick-interval 10
    """

    help = "启动指定的网格交易配置"

    def __init__(self):
        super().__init__()
        self.engine = None
        self.running = False

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
            "--tick-interval",
            type=int,
            default=5,
            help="Tick间隔（秒，默认5）",
        )

        parser.add_argument(
            "--exchange",
            type=str,
            help="交易所类型（如：grvt），不指定则使用配置中的exchange字段",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="模拟运行模式（不连接真实交易所）",
        )

    def handle(self, *args, **options):
        """命令主逻辑"""
        try:
            # 加载配置
            config = self.load_config(options)
            
            # 验证配置状态
            if not config.is_active:
                raise CommandError(f"配置 {config.name} 未激活，无法启动")
            
            self.stdout.write(
                self.style.SUCCESS(f"加载配置: {config.name}")
            )
            self.stdout.write(f"  交易对: {config.symbol}")
            self.stdout.write(f"  网格模式: {config.grid_mode}")
            self.stdout.write(f"  网格层数: {config.grid_levels}")
            self.stdout.write(f"  价格区间: {config.lower_price} - {config.upper_price}")

            # 创建交易所适配器
            exchange_adapter = None
            dry_run = options.get('dry_run', False)

            if not dry_run:
                # 确定使用的交易所
                exchange = options.get('exchange') or config.exchange

                if exchange:
                    try:
                        self.stdout.write(f"  交易所: {exchange}")
                        self.stdout.write("正在初始化交易所适配器...")
                        exchange_adapter = create_adapter(exchange)
                        self.stdout.write(
                            self.style.SUCCESS(f"✓ {exchange} 适配器初始化成功")
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f"⚠ 适配器初始化失败: {e}\n"
                                f"将以模拟模式运行（无实际交易）"
                            )
                        )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            "未指定交易所，将以模拟模式运行（无实际交易）"
                        )
                    )
            else:
                self.stdout.write(
                    self.style.WARNING("模拟运行模式（dry-run）：不会连接真实交易所")
                )

            # 创建并启动引擎
            self.engine = GridEngine(config, exchange_adapter=exchange_adapter)
            self.engine.start()
            
            self.stdout.write(
                self.style.SUCCESS(f"网格引擎已启动")
            )
            
            # 注册信号处理
            self.register_signals()
            
            # 主循环
            tick_interval = options['tick_interval']
            self.running = True
            
            self.stdout.write(
                self.style.WARNING(f"开始运行，Tick间隔={tick_interval}秒")
            )
            self.stdout.write("按Ctrl+C停止\n")
            
            tick_count = 0
            while self.running:
                try:
                    tick_count += 1
                    self.stdout.write(f"[Tick #{tick_count}] {time.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    # 执行一次同步
                    result = self.engine.tick()
                    
                    # 输出统计信息
                    self.stdout.write(
                        f"  持仓: {result['current_position']}, "
                        f"理想订单: {result['ideal_orders_count']}, "
                        f"创建: {result['created_orders_count']}, "
                        f"撤销: {result['cancelled_orders_count']}"
                    )
                    
                    if result['filtered_orders_count'] > 0:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  ⚠ {result['filtered_orders_count']} 个订单因持仓限制被过滤"
                            )
                        )
                    
                    # 等待下一个tick
                    time.sleep(tick_interval)
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logger.error(f"Tick执行出错: {e}", exc_info=True)
                    self.stdout.write(
                        self.style.ERROR(f"  错误: {str(e)}")
                    )
                    time.sleep(tick_interval)
            
            # 停止引擎
            self.shutdown()
            
        except KeyboardInterrupt:
            self.shutdown()
        except Exception as e:
            raise CommandError(f"启动失败: {str(e)}")

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

    def register_signals(self):
        """注册信号处理器"""
        def signal_handler(signum, frame):
            self.stdout.write("\n收到停止信号...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def shutdown(self):
        """关闭引擎"""
        if self.engine and self.engine.running:
            self.stdout.write("\n正在停止网格引擎...")
            self.engine.stop()
            self.stdout.write(
                self.style.SUCCESS("网格引擎已停止")
            )
