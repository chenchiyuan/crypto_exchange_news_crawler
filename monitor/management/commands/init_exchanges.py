"""
初始化交易所数据
Usage: python manage.py init_exchanges
"""
from django.core.management.base import BaseCommand
from monitor.models import Exchange


class Command(BaseCommand):
    help = '初始化交易所数据'

    def handle(self, *args, **options):
        self.stdout.write("开始初始化交易所数据...")

        exchanges_data = [
            {
                'name': 'Binance',
                'code': 'binance',
                'announcement_url': 'https://www.binance.com/en/support/announcement/',
                'enabled': True
            },
            {
                'name': 'Bybit',
                'code': 'bybit',
                'announcement_url': 'https://www.bybit.com/en/announcement-info/',
                'enabled': True
            },
            {
                'name': 'Bitget',
                'code': 'bitget',
                'announcement_url': 'https://www.bitget.com/en/support/announcement/',
                'enabled': True
            },
            {
                'name': 'Hyperliquid',
                'code': 'hyperliquid',
                'announcement_url': 'https://app.hyperliquid.xyz/announcements',
                'enabled': True
            },
        ]

        created_count = 0
        updated_count = 0

        for data in exchanges_data:
            exchange, created = Exchange.objects.update_or_create(
                code=data['code'],
                defaults={
                    'name': data['name'],
                    'announcement_url': data['announcement_url'],
                    'enabled': data['enabled']
                }
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✓ 创建交易所: {exchange.name} ({exchange.code})")
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f"✓ 更新交易所: {exchange.name} ({exchange.code})")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n初始化完成! 创建 {created_count} 个, 更新 {updated_count} 个交易所"
            )
        )

        # 显示当前交易所列表
        self.stdout.write("\n当前交易所列表:")
        exchanges = Exchange.objects.all()
        for exchange in exchanges:
            status = "✓ 已启用" if exchange.enabled else "✗ 已禁用"
            self.stdout.write(f"  - {exchange.name} ({exchange.code}): {status}")
