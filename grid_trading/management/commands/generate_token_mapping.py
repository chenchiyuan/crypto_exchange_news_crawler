"""生成币安symbol与CoinGecko ID的映射关系"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from grid_trading.services.mapping_service import MappingService


class Command(BaseCommand):
    help = '生成币安symbol与CoinGecko ID的映射关系'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='强制刷新已存在的映射关系'
        )

    def handle(self, *args, **options):
        force_refresh = options['force']

        self.stdout.write(self.style.SUCCESS(
            f"[{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            f"Starting token mapping generation..."
        ))

        if force_refresh:
            self.stdout.write(self.style.WARNING("  Force refresh mode enabled"))

        try:
            # 初始化映射服务
            service = MappingService()

            # 生成映射
            stats = service.generate_mappings(force_refresh=force_refresh)

            # 输出统计信息
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.SUCCESS("✓ Mapping generation completed"))
            self.stdout.write("=" * 60)
            self.stdout.write(f"  Batch ID: {stats['batch_id']}")
            self.stdout.write(f"  Total contracts: {stats['total']}")
            self.stdout.write(f"  Created: {stats['created']}")
            self.stdout.write(f"  Skipped: {stats['skipped']}")
            self.stdout.write("")
            self.stdout.write(f"  Auto-matched: {stats['auto_matched']} "
                              f"({stats['auto_matched']/stats['total']*100:.1f}%)")
            self.stdout.write(f"  Needs review: {stats['needs_review']} "
                              f"({stats['needs_review']/stats['total']*100:.1f}%)")
            self.stdout.write("")

            # 提示审核
            if stats['needs_review'] > 0:
                self.stdout.write(self.style.WARNING(
                    f"  ⚠ {stats['needs_review']} mappings need manual review in Django Admin:"
                ))
                self.stdout.write("    http://127.0.0.1:8000/admin/grid_trading/tokenmapping/")
                self.stdout.write("    Filter by: match_status = needs_review")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n✗ Mapping generation failed: {e}"))
            raise
