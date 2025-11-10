"""
批量获取所有已启用交易所的公告
Usage: python manage.py fetch_all_announcements [--hours 24]
"""
from django.core.management.base import BaseCommand
from monitor.models import Exchange
from monitor.services.crawler import CrawlerService


class Command(BaseCommand):
    help = '批量获取所有已启用交易所的公告'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-pages',
            type=int,
            default=2,
            help='每个交易所最大爬取页数(默认2)'
        )
        parser.add_argument(
            '--hours',
            type=int,
            default=None,
            help='只获取最近N小时的公告(默认获取全部)'
        )
        parser.add_argument(
            '--exchanges',
            type=str,
            default='binance,bybit,bitget,hyperliquid',
            help='指定要获取的交易所,逗号分隔(默认: binance,bybit,bitget,hyperliquid)'
        )

    def handle(self, *args, **options):
        max_pages = options['max_pages']
        hours = options['hours']
        exchange_codes = [code.strip() for code in options['exchanges'].split(',')]

        if hours:
            self.stdout.write(
                self.style.SUCCESS(
                    f"开始批量获取公告 (最近{hours}小时, 最大页数: {max_pages})\n"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"开始批量获取公告 (最大页数: {max_pages})\n"
                )
            )

        # 显示配置的交易所列表
        self.stdout.write(f"配置的交易所: {', '.join(exchange_codes)}\n")

        # 获取已启用的交易所
        enabled_exchanges = Exchange.objects.filter(
            code__in=exchange_codes,
            enabled=True
        )

        if not enabled_exchanges.exists():
            self.stdout.write(
                self.style.ERROR(
                    "❌ 没有找到已启用的交易所!\n"
                    "请运行: python manage.py init_exchanges"
                )
            )
            return

        total_announcements = 0
        success_count = 0
        failed_exchanges = []

        # 创建爬虫服务
        crawler = CrawlerService()

        # 逐个获取交易所公告
        for exchange in enabled_exchanges:
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write(f"正在获取: {exchange.name} ({exchange.code})")
            self.stdout.write(f"{'='*60}\n")

            try:
                # 调用爬虫
                announcements = crawler.fetch_announcements(
                    exchange.code,
                    max_pages,
                    hours=hours
                )

                if announcements:
                    # 保存到数据库
                    crawler.save_announcements_to_db(exchange.code, announcements)
                    count = len(announcements)
                    total_announcements += count
                    success_count += 1

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ {exchange.name}: 成功获取 {count} 条公告\n"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠ {exchange.name}: 未获取到公告\n"
                        )
                    )
                    failed_exchanges.append(exchange.name)

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"✗ {exchange.name}: 获取失败 - {str(e)}\n"
                    )
                )
                failed_exchanges.append(exchange.name)

        # 显示汇总结果
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("汇总结果")
        self.stdout.write(f"{'='*60}\n")

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ 成功: {success_count}/{len(enabled_exchanges)} 个交易所"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"✓ 总计获取: {total_announcements} 条公告"
            )
        )

        if failed_exchanges:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠ 失败的交易所: {', '.join(failed_exchanges)}"
                )
            )

        self.stdout.write("")

        # 显示数据库统计
        from monitor.models import Announcement
        db_stats = Announcement.objects.values('exchange__name').annotate(
            count=__import__('django.db.models', fromlist=['Count']).Count('id')
        ).order_by('-count')

        if db_stats:
            self.stdout.write("\n数据库统计:")
            for stat in db_stats:
                self.stdout.write(f"  - {stat['exchange__name']}: {stat['count']} 条公告")

        self.stdout.write("")
