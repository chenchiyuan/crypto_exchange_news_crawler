"""
K线缓存管理命令
Kline Cache Management Command

用途:
- 查看缓存统计信息
- 清空缓存数据
"""

from django.core.management.base import BaseCommand
from grid_trading.services.kline_cache import KlineCache
from grid_trading.models import KlineData


class Command(BaseCommand):
    """
    K线缓存统计和管理命令

    示例:
        python manage.py cache_stats                    # 查看统计
        python manage.py cache_stats --clear            # 清空所有缓存
        python manage.py cache_stats --clear --symbol BTCUSDT  # 清空指定标的
    """

    help = "查看K线缓存统计信息或清空缓存"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="清空缓存数据",
        )

        parser.add_argument(
            "--symbol",
            type=str,
            help="指定标的 (配合--clear使用)",
        )

        parser.add_argument(
            "--interval",
            type=str,
            help="指定周期 (配合--clear使用)",
        )

    def handle(self, *args, **options):
        cache = KlineCache()

        if options.get("clear"):
            # 清空缓存
            symbol = options.get("symbol")
            interval = options.get("interval")

            self.stdout.write("=" * 70)
            self.stdout.write("🗑️  清空K线缓存")
            self.stdout.write("=" * 70)

            if symbol or interval:
                self.stdout.write(
                    f"\n清空条件: symbol={symbol or '全部'}, interval={interval or '全部'}\n"
                )
            else:
                self.stdout.write("\n⚠️  即将清空所有缓存数据！\n")
                confirm = input("确认清空？ (yes/no): ")
                if confirm.lower() != "yes":
                    self.stdout.write(self.style.WARNING("已取消"))
                    return

            cache.clear_cache(symbol=symbol, interval=interval)
            self.stdout.write(self.style.SUCCESS("\n✅ 缓存已清空"))

        else:
            # 查看统计
            stats = cache.get_cache_stats()

            self.stdout.write("=" * 70)
            self.stdout.write("📊 K线缓存统计")
            self.stdout.write("=" * 70)

            self.stdout.write(f"\n总K线数: {stats.get('total_count', 0):,} 根")
            self.stdout.write(f"标的数量: {stats.get('symbols', 0)}")
            self.stdout.write(f"时间周期: {', '.join(stats.get('intervals', []))}")

            top_symbols = stats.get("top_symbols", [])
            if top_symbols:
                self.stdout.write("\n" + "-" * 70)
                self.stdout.write("Top 10 标的 (按K线数量):")
                self.stdout.write("-" * 70)
                for item in top_symbols:
                    self.stdout.write(
                        f"  {item['symbol']:15} {item['interval']:5} {item['count']:6,} 根"
                    )

            # 数据库表大小
            total_count = KlineData.objects.count()
            if total_count > 0:
                avg_size = 500  # 每条记录约500字节估算
                total_mb = total_count * avg_size / 1024 / 1024
                self.stdout.write("\n" + "-" * 70)
                self.stdout.write(f"估算占用空间: {total_mb:.2f} MB")

            self.stdout.write("\n" + "=" * 70)

            # 提示
            self.stdout.write("\n💡 提示:")
            self.stdout.write("  - 使用 --clear 清空所有缓存")
            self.stdout.write("  - 使用 --clear --symbol BTCUSDT 清空指定标的")
            self.stdout.write("  - 使用 --clear --interval 4h 清空指定周期")
            self.stdout.write("")
