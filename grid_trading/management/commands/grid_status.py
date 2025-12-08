"""
grid_status Django Management Command

用途: 查看网格交易状态
"""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Q

from grid_trading.models import (
    GridConfig, GridLevel, OrderIntent, 
    GridLevelStatus, OrderStatus
)

class Command(BaseCommand):
    """
    查看网格交易状态命令

    示例:
        python manage.py grid_status --config-id 1
        python manage.py grid_status --config-name my_grid
        python manage.py grid_status --all
    """

    help = "查看网格交易的当前状态"

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
        group.add_argument(
            "--all",
            action="store_true",
            help="显示所有配置的状态",
        )
        
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="显示详细信息（包括每个层级的状态）",
        )

    def handle(self, *args, **options):
        """命令主逻辑"""
        try:
            if options['all']:
                configs = GridConfig.objects.all()
                for config in configs:
                    self.show_config_status(config, options['verbose'])
                    self.stdout.write("")  # 空行分隔
            else:
                config = self.load_config(options)
                self.show_config_status(config, options['verbose'])
                
        except Exception as e:
            raise CommandError(f"查询失败: {str(e)}")

    def show_config_status(self, config, verbose=False):
        """显示单个配置的状态"""
        # 配置基本信息
        self.stdout.write(
            self.style.SUCCESS(f"=== {config.name} ===")
        )
        self.stdout.write(f"ID: {config.id}")
        self.stdout.write(f"交易对: {config.symbol}")
        self.stdout.write(f"网格模式: {config.grid_mode}")
        self.stdout.write(f"激活状态: {'✓ 激活' if config.is_active else '✗ 未激活'}")
        self.stdout.write(f"价格区间: {config.lower_price} - {config.upper_price}")
        self.stdout.write(f"网格层数: {config.grid_levels}")
        self.stdout.write(f"单笔交易量: {config.trade_amount}")
        self.stdout.write(f"最大持仓: {config.max_position_size}")
        
        # 网格层级统计
        levels = GridLevel.objects.filter(config=config)
        status_counts = levels.values('status').annotate(count=Count('id'))
        
        self.stdout.write("\n网格层级状态:")
        total = levels.count()
        
        status_map = {
            GridLevelStatus.IDLE: "空闲",
            GridLevelStatus.ENTRY_WORKING: "开仓挂单中",
            GridLevelStatus.POSITION_OPEN: "持仓中",
            GridLevelStatus.EXIT_WORKING: "平仓挂单中",
        }
        
        for item in status_counts:
            status = item['status']
            count = item['count']
            status_name = status_map.get(status, status)
            percentage = (count / total * 100) if total > 0 else 0
            
            self.stdout.write(
                f"  {status_name}: {count}/{total} ({percentage:.1f}%)"
            )
        
        # 订单统计
        active_orders = OrderIntent.objects.filter(
            config=config,
            status__in=[OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED]
        )
        filled_orders = OrderIntent.objects.filter(
            config=config,
            status=OrderStatus.FILLED
        )
        canceled_orders = OrderIntent.objects.filter(
            config=config,
            status=OrderStatus.CANCELED
        )
        
        self.stdout.write("\n订单统计:")
        self.stdout.write(f"  活跃订单: {active_orders.count()}")
        self.stdout.write(f"  已成交: {filled_orders.count()}")
        self.stdout.write(f"  已撤销: {canceled_orders.count()}")
        
        # 持仓统计
        position_levels = levels.filter(
            status__in=[GridLevelStatus.POSITION_OPEN, GridLevelStatus.EXIT_WORKING]
        ).count()
        
        from decimal import Decimal
        current_position = Decimal(str(config.trade_amount)) * Decimal(position_levels)
        
        # 做空网格持仓是负数
        if config.grid_mode.upper() == 'SHORT':
            current_position = -current_position
        
        max_position = Decimal(str(config.max_position_size))
        position_usage = (abs(current_position) / max_position * 100) if max_position > 0 else 0
        
        self.stdout.write("\n持仓信息:")
        self.stdout.write(f"  当前持仓: {current_position}")
        self.stdout.write(f"  最大持仓: {max_position}")
        self.stdout.write(f"  使用率: {position_usage:.1f}%")
        
        # 详细信息
        if verbose:
            self.stdout.write("\n层级详情:")
            self.stdout.write(
                f"{'层级':>4} {'价格':>12} {'方向':>6} {'状态':>12} {'开仓单':>20} {'平仓单':>20}"
            )
            self.stdout.write("-" * 80)
            
            for level in levels.order_by('level_index'):
                side_symbol = "SELL" if level.side == "SELL" else "BUY"
                status_name = status_map.get(level.status, level.status)
                entry_id = level.entry_client_id or "-"
                exit_id = level.exit_client_id or "-"
                
                # 截断长ID
                if len(entry_id) > 20:
                    entry_id = entry_id[:17] + "..."
                if len(exit_id) > 20:
                    exit_id = exit_id[:17] + "..."
                
                self.stdout.write(
                    f"{level.level_index:>4} {level.price:>12} {side_symbol:>6} "
                    f"{status_name:>12} {entry_id:>20} {exit_id:>20}"
                )

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
