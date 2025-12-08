"""
reset_grid Django Management Command

用途: 重置网格状态（清空所有层级和订单记录）
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from grid_trading.models import GridConfig, GridLevel, OrderIntent

class Command(BaseCommand):
    """
    重置网格状态命令（危险操作！）

    示例:
        python manage.py reset_grid --config-id 1
        python manage.py reset_grid --config-name my_grid --confirm
    """

    help = "重置网格状态，清空所有层级和订单记录"

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
            "--confirm",
            action="store_true",
            help="确认执行重置（必须）",
        )

    def handle(self, *args, **options):
        """命令主逻辑"""
        if not options['confirm']:
            raise CommandError(
                "重置操作会删除所有网格层级和订单记录！\n"
                "如果确认执行，请添加 --confirm 参数"
            )
        
        try:
            # 加载配置
            config = self.load_config(options)
            
            self.stdout.write(
                self.style.WARNING(f"=== 重置网格配置: {config.name} ===")
            )
            
            # 统计要删除的数据
            levels_count = GridLevel.objects.filter(config=config).count()
            intents_count = OrderIntent.objects.filter(config=config).count()
            
            self.stdout.write(f"将删除:")
            self.stdout.write(f"  {levels_count} 个网格层级")
            self.stdout.write(f"  {intents_count} 个订单记录")
            
            # 再次确认
            self.stdout.write("")
            user_input = input("确认继续吗？(yes/no): ")
            
            if user_input.lower() != 'yes':
                self.stdout.write(
                    self.style.WARNING("已取消操作")
                )
                return
            
            # 执行删除
            with transaction.atomic():
                deleted_levels = GridLevel.objects.filter(config=config).delete()
                deleted_intents = OrderIntent.objects.filter(config=config).delete()
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n已删除 {deleted_levels[0]} 个网格层级"
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"已删除 {deleted_intents[0]} 个订单记录"
                    )
                )
            
            self.stdout.write("")
            self.stdout.write(
                self.style.SUCCESS("重置完成！")
            )
            self.stdout.write(
                "提示: 使用 GridEngine.initialize_grid() 重新初始化网格"
            )
            
        except Exception as e:
            raise CommandError(f"重置失败: {str(e)}")

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
