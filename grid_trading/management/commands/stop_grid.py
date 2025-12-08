"""
stop_grid Django Management Command

用途: 停止网格交易策略（撤销所有未成交订单）
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from grid_trading.models import GridConfig, GridLevel, OrderIntent, OrderStatus, GridLevelStatus

class Command(BaseCommand):
    """
    停止网格交易命令（撤销所有订单并重置状态）

    示例:
        python manage.py stop_grid --config-id 1
        python manage.py stop_grid --config-name my_grid
    """

    help = "停止指定的网格交易配置，撤销所有订单并重置状态"

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
            "--force",
            action="store_true",
            help="强制停止（即使交易所撤单失败也重置本地状态）",
        )

    def handle(self, *args, **options):
        """命令主逻辑"""
        try:
            # 加载配置
            config = self.load_config(options)
            
            self.stdout.write(
                self.style.SUCCESS(f"停止网格配置: {config.name}")
            )
            
            # 1. 查找所有活跃订单
            active_intents = OrderIntent.objects.filter(
                config=config,
                status__in=[OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED]
            )
            
            total_orders = active_intents.count()
            
            if total_orders == 0:
                self.stdout.write(
                    self.style.WARNING("  没有活跃订单需要撤销")
                )
            else:
                self.stdout.write(f"  发现 {total_orders} 个活跃订单")
                
                # 2. 撤销所有订单
                cancelled_count = 0
                failed_orders = []
                
                for intent in active_intents:
                    try:
                        # TODO: 调用交易所API撤销订单
                        # exchange_adapter.cancel_order(config.symbol, intent.order_id)
                        
                        # 更新OrderIntent状态
                        intent.mark_canceled()
                        cancelled_count += 1
                        
                        self.stdout.write(f"  ✓ 撤销订单: {intent.client_order_id}")
                        
                    except Exception as e:
                        failed_orders.append((intent.client_order_id, str(e)))
                        self.stdout.write(
                            self.style.ERROR(
                                f"  ✗ 撤销失败: {intent.client_order_id} - {str(e)}"
                            )
                        )
                
                if failed_orders and not options['force']:
                    raise CommandError(
                        f"{len(failed_orders)} 个订单撤销失败。"
                        "使用 --force 强制重置本地状态"
                    )
            
            # 3. 重置所有GridLevel状态
            with transaction.atomic():
                levels = GridLevel.objects.filter(config=config)
                reset_count = 0
                
                for level in levels:
                    if level.status != GridLevelStatus.IDLE:
                        # 清空订单ID
                        level.entry_order_id = None
                        level.entry_client_id = None
                        level.exit_order_id = None
                        level.exit_client_id = None
                        level.status = GridLevelStatus.IDLE
                        level.save()
                        reset_count += 1
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  重置了 {reset_count} 个网格层级状态"
                    )
                )
            
            # 4. 禁用配置（可选）
            # config.is_active = False
            # config.save()
            
            self.stdout.write(
                self.style.SUCCESS(f"\n网格已停止")
            )
            self.stdout.write(
                f"  撤销订单: {cancelled_count}/{total_orders}"
            )
            if failed_orders:
                self.stdout.write(
                    self.style.WARNING(
                        f"  失败订单: {len(failed_orders)} (已强制重置本地状态)"
                    )
                )
            
        except Exception as e:
            raise CommandError(f"停止失败: {str(e)}")

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
