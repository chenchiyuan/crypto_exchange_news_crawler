"""更新CoinGecko市值和FDV数据"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from grid_trading.services.market_data_service import MarketDataService


class Command(BaseCommand):
    help = '从CoinGecko更新市值和FDV数据'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol',
            type=str,
            help='只更新指定的symbol（如 BTCUSDT）'
        )

    def handle(self, *args, **options):
        symbol = options.get('symbol')

        self.stdout.write(self.style.SUCCESS(
            f"[{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            f"Starting market data update..."
        ))

        try:
            # 初始化服务
            service = MarketDataService()

            if symbol:
                # 单个symbol更新
                self.stdout.write(f"  Updating single symbol: {symbol}")
                success = service.update_single(symbol)

                if success:
                    self.stdout.write(self.style.SUCCESS(f"\n✓ Successfully updated {symbol}"))
                else:
                    self.stdout.write(self.style.ERROR(f"\n✗ Failed to update {symbol}"))

            else:
                # 批量更新
                stats = service.update_all()

                # 输出统计信息
                self.stdout.write("\n" + "=" * 60)
                self.stdout.write(self.style.SUCCESS("✓ Market data update completed"))
                self.stdout.write("=" * 60)
                self.stdout.write(f"  Batch ID: {stats['batch_id']}")
                self.stdout.write(f"  Total symbols: {stats['total']}")
                self.stdout.write(f"  Updated: {stats['updated']}")
                self.stdout.write(f"  Failed: {stats['failed']}")
                self.stdout.write(f"  Coverage: {stats['coverage']:.1f}%")
                self.stdout.write("")

                # 警告信息
                if stats['failed'] > 0:
                    self.stdout.write(self.style.WARNING(
                        f"  ⚠ {stats['failed']} symbols failed to update. Check UpdateLog for details:"
                    ))
                    self.stdout.write("    http://127.0.0.1:8000/admin/grid_trading/updatelog/")

                if stats['coverage'] < 95:
                    self.stdout.write(self.style.WARNING(
                        f"  ⚠ Coverage below 95% ({stats['coverage']:.1f}%). "
                        f"Some symbols may need manual review."
                    ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n✗ Market data update failed: {e}"))
            raise
