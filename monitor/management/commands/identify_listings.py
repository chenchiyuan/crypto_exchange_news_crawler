"""
识别新币上线
Usage: python manage.py identify_listings [--exchange binance]
"""
from django.core.management.base import BaseCommand
from monitor.models import Exchange, Announcement, Listing
from monitor.services.identifier import ListingIdentifier


class Command(BaseCommand):
    help = '识别新币上线公告'

    def add_arguments(self, parser):
        parser.add_argument(
            '--exchange',
            type=str,
            default=None,
            help='指定交易所代码(可选,默认处理所有)'
        )
        parser.add_argument(
            '--show-details',
            action='store_true',
            help='显示识别详情'
        )

    def handle(self, *args, **options):
        exchange_code = options['exchange']
        show_details = options['show_details']

        if exchange_code:
            self.stdout.write(f"开始识别 {exchange_code} 交易所的新币上线...")
        else:
            self.stdout.write("开始识别所有交易所的新币上线...")

        # 检查未处理公告数量
        query = Announcement.objects.filter(processed=False)
        if exchange_code:
            try:
                exchange = Exchange.objects.get(code=exchange_code)
                query = query.filter(exchange=exchange)
            except Exchange.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"✗ 交易所不存在: {exchange_code}")
                )
                return

        unprocessed_count = query.count()
        self.stdout.write(f"未处理公告数量: {unprocessed_count}")

        if unprocessed_count == 0:
            self.stdout.write(
                self.style.WARNING("没有未处理的公告,请先运行: python manage.py fetch_announcements")
            )
            return

        # 调用识别服务
        identifier = ListingIdentifier()
        identified_count = identifier.process_announcements(exchange_code)

        self.stdout.write(
            self.style.SUCCESS(f"\n✓ 识别完成! 共识别出 {identified_count} 个新币上线")
        )

        # 显示识别结果
        if identified_count > 0:
            self.stdout.write("\n识别结果:")

            query = Listing.objects.all()
            if exchange_code:
                query = query.filter(announcement__exchange__code=exchange_code)

            recent_listings = query.order_by('-identified_at')[:10]

            for listing in recent_listings:
                exchange_name = listing.get_exchange().name
                status_icon = "✓" if listing.status == Listing.CONFIRMED else "?"

                output = (
                    f"  {status_icon} {listing.coin_symbol} "
                    f"({listing.get_listing_type_display()}) "
                    f"- {exchange_name} "
                    f"[置信度: {listing.confidence:.2f}]"
                )

                if listing.status == Listing.CONFIRMED:
                    self.stdout.write(self.style.SUCCESS(output))
                else:
                    self.stdout.write(self.style.WARNING(output))

                if show_details:
                    self.stdout.write(f"    标题: {listing.announcement.title[:80]}...")

        # 显示统计
        self.stdout.write("\n统计信息:")
        total = Listing.objects.count()
        confirmed = Listing.objects.filter(status=Listing.CONFIRMED).count()
        pending = Listing.objects.filter(status=Listing.PENDING_REVIEW).count()

        self.stdout.write(f"  总计: {total} 个新币上线")
        self.stdout.write(f"  已确认: {confirmed} 个")
        self.stdout.write(f"  待审核: {pending} 个")
