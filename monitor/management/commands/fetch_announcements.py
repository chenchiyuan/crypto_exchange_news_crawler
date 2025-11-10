"""
手动获取交易所公告
Usage: python manage.py fetch_announcements --exchange binance
"""
from django.core.management.base import BaseCommand, CommandError
from monitor.models import Exchange
from monitor.services.crawler import CrawlerService


class Command(BaseCommand):
    help = '手动获取指定交易所的公告'

    def add_arguments(self, parser):
        parser.add_argument(
            '--exchange',
            type=str,
            required=True,
            help='交易所代码(binance, bybit, bitget)'
        )
        parser.add_argument(
            '--max-pages',
            type=int,
            default=2,
            help='最大爬取页数(默认2)'
        )
        parser.add_argument(
            '--hours',
            type=int,
            default=None,
            help='只获取最近N小时的公告(默认获取全部)'
        )

    def handle(self, *args, **options):
        exchange_code = options['exchange']
        max_pages = options['max_pages']
        hours = options['hours']

        if hours:
            self.stdout.write(f"开始获取 {exchange_code} 交易所最近{hours}小时的公告 (最大页数: {max_pages})...")
        else:
            self.stdout.write(f"开始获取 {exchange_code} 交易所公告 (最大页数: {max_pages})...")

        # 验证交易所是否存在
        try:
            exchange = Exchange.objects.get(code=exchange_code)
        except Exchange.DoesNotExist:
            raise CommandError(
                f"交易所不存在: {exchange_code}\n"
                f"请先运行: python manage.py init_exchanges"
            )

        if not exchange.enabled:
            self.stdout.write(
                self.style.WARNING(f"⚠ 警告: {exchange.name} 当前已禁用")
            )

        # 调用爬虫服务
        crawler = CrawlerService()

        self.stdout.write(f"正在调用Scrapy爬虫...")
        announcements = crawler.fetch_announcements(exchange_code, max_pages, hours=hours)

        if not announcements:
            self.stdout.write(
                self.style.WARNING("未获取到任何公告,可能原因:")
            )
            self.stdout.write("  1. Scrapy爬虫未正确配置")
            self.stdout.write("  2. 网络连接问题")
            self.stdout.write("  3. 交易所网站结构变更")
            return

        self.stdout.write(
            self.style.SUCCESS(f"✓ 成功获取 {len(announcements)} 条公告")
        )

        # 保存到数据库
        self.stdout.write("正在保存到数据库...")
        crawler.save_announcements_to_db(exchange_code, announcements)

        self.stdout.write(
            self.style.SUCCESS(f"\n完成! 公告已保存到数据库")
        )

        # 显示最近的几条公告
        from monitor.models import Announcement
        recent = Announcement.objects.filter(exchange=exchange).order_by('-announced_at')[:5]

        if recent:
            self.stdout.write("\n最近的5条公告:")
            for ann in recent:
                self.stdout.write(
                    f"  [{ann.announced_at.strftime('%Y-%m-%d %H:%M')}] {ann.title[:60]}..."
                )
