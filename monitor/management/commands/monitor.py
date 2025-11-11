"""
一键监控脚本：获取公告 → 识别新币 → 发送通知
Usage: python manage.py monitor [--hours 24]
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from monitor.models import Exchange, Listing
from monitor.services.crawler import CrawlerService
from monitor.services.identifier import ListingIdentifier
from monitor.services.notifier import WebhookNotifier, AlertPushService
import os


class Command(BaseCommand):
    help = '一键监控：获取公告→识别新币→发送通知'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='只处理最近N小时的公告(默认24小时)'
        )
        parser.add_argument(
            '--max-pages',
            type=int,
            default=3,
            help='每个交易所最大爬取页数(默认3)'
        )
        parser.add_argument(
            '--exchanges',
            type=str,
            default='binance,bybit,hyperliquid',
            help='要监控的交易所(默认: binance,bybit,hyperliquid)'
        )
        parser.add_argument(
            '--webhook-url',
            type=str,
            default=None,
            help='Webhook通知URL(可选,默认从环境变量WEBHOOK_URL读取)'
        )
        parser.add_argument(
            '--skip-notification',
            action='store_true',
            help='跳过通知步骤，只获取和识别'
        )

    def handle(self, *args, **options):
        hours = options['hours']
        max_pages = options['max_pages']
        exchange_codes = [code.strip() for code in options['exchanges'].split(',')]
        webhook_url = options['webhook_url'] or os.getenv('WEBHOOK_URL', '').strip()
        skip_notification = options['skip_notification']

        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('🚀 加密货币新币上线监控系统'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(f"⏰ 时间范围: 最近 {hours} 小时")
        self.stdout.write(f"📊 交易所: {', '.join(exchange_codes)}")
        self.stdout.write(f"📄 最大页数: {max_pages}")
        if skip_notification:
            self.stdout.write(f"🔕 通知: 已跳过")
        elif webhook_url:
            self.stdout.write(f"🔔 通知: Webhook模式")
        else:
            self.stdout.write(f"📢 通知: 告警推送模式（默认）")
        self.stdout.write('')

        # ========== 步骤1: 获取公告 ==========
        self.stdout.write(self.style.SUCCESS('\n📥 步骤1: 获取交易所公告'))
        self.stdout.write('-'*70)

        enabled_exchanges = Exchange.objects.filter(
            code__in=exchange_codes,
            enabled=True
        )

        if not enabled_exchanges.exists():
            self.stdout.write(
                self.style.ERROR('❌ 没有找到已启用的交易所，请先运行: python manage.py init_exchanges')
            )
            return

        crawler = CrawlerService()
        total_announcements = 0

        for exchange in enabled_exchanges:
            self.stdout.write(f"  正在获取: {exchange.name}...", ending='')
            try:
                announcements = crawler.fetch_announcements(
                    exchange.code,
                    max_pages,
                    hours=hours
                )

                if announcements:
                    crawler.save_announcements_to_db(exchange.code, announcements)
                    count = len(announcements)
                    total_announcements += count
                    self.stdout.write(self.style.SUCCESS(f" ✓ {count} 条"))
                else:
                    self.stdout.write(self.style.WARNING(' ⚠ 0 条'))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f' ✗ 失败: {str(e)}'))

        self.stdout.write(f"\n  📊 总计获取: {total_announcements} 条公告")

        if total_announcements == 0:
            self.stdout.write(self.style.WARNING('\n⚠ 没有获取到新公告，监控结束'))
            return

        # ========== 步骤2: 识别新币上线 ==========
        self.stdout.write(self.style.SUCCESS('\n🔍 步骤2: 识别新币上线'))
        self.stdout.write('-'*70)

        identifier = ListingIdentifier()
        identified_count = identifier.process_announcements(exchange_code=None)

        if identified_count == 0:
            self.stdout.write(self.style.WARNING('  ⚠ 未识别到新币上线'))
            return

        self.stdout.write(self.style.SUCCESS(f'  ✓ 识别出 {identified_count} 个新币上线'))

        # 显示识别结果（严格按照公告发布时间过滤）
        recent_listings = Listing.objects.filter(
            announcement__announced_at__gte=timezone.now() - timezone.timedelta(hours=hours)
        ).select_related('announcement__exchange').order_by('-announcement__announced_at')[:10]

        self.stdout.write('\n  识别结果:')
        for listing in recent_listings:
            exchange_name = listing.announcement.exchange.name
            status_icon = "✓" if listing.status == Listing.CONFIRMED else "?"
            color = self.style.SUCCESS if listing.status == Listing.CONFIRMED else self.style.WARNING

            self.stdout.write(
                color(
                    f"    {status_icon} {listing.coin_symbol} "
                    f"({listing.get_listing_type_display()}) "
                    f"- {exchange_name} "
                    f"[置信度: {listing.confidence:.2f}]"
                )
            )

        # ========== 步骤3: 发送通知 ==========
        if skip_notification:
            self.stdout.write(self.style.WARNING('\n🔕 步骤3: 通知 (已跳过)'))
        else:
            # 决定使用哪种通知服务
            if webhook_url:
                # 用户提供了webhook URL，使用传统 Webhook 通知
                self.stdout.write(self.style.SUCCESS('\n🔔 步骤3: 发送Webhook通知'))
                self.stdout.write('-'*70)
                notifier = WebhookNotifier(webhook_url, max_retries=3, retry_delay=5)
                notification_type = "Webhook"
            else:
                # 默认使用慧诚告警推送服务
                self.stdout.write(self.style.SUCCESS('\n📢 步骤3: 发送告警推送'))
                self.stdout.write('-'*70)
                notifier = AlertPushService()
                notification_type = "告警推送"

            # 只通知已确认的新币
            confirmed_listings = [l for l in recent_listings if l.status == Listing.CONFIRMED]

            if not confirmed_listings:
                self.stdout.write(self.style.WARNING('  ⚠ 没有已确认的新币，跳过通知'))
            else:
                # 过滤掉已发送过通知的新币（去重）
                from monitor.models import NotificationRecord
                listings_to_notify = []
                for listing in confirmed_listings:
                    existing = NotificationRecord.objects.filter(
                        listing=listing,
                        status=NotificationRecord.SUCCESS
                    ).exists()
                    if not existing:
                        listings_to_notify.append(listing)

                if not listings_to_notify:
                    self.stdout.write(self.style.WARNING('  ⚠ 所有新币均已发送过通知，跳过'))
                else:
                    success_count = 0
                    failed_count = 0

                    for listing in listings_to_notify:
                        self.stdout.write(f"  推送: {listing.coin_symbol}...", ending='')
                        if notifier.send_notification(listing, create_record=True):
                            success_count += 1
                            self.stdout.write(self.style.SUCCESS(' ✓'))
                        else:
                            failed_count += 1
                            self.stdout.write(self.style.ERROR(' ✗'))

                    self.stdout.write(
                        f"\n  📊 {notification_type}统计: 成功 {success_count}, 失败 {failed_count}"
                    )

        # ========== 汇总结果 ==========
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('✅ 监控完成'))
        self.stdout.write(self.style.SUCCESS('='*70))

        # 统计信息
        total_listings = Listing.objects.count()
        confirmed = Listing.objects.filter(status=Listing.CONFIRMED).count()
        pending = Listing.objects.filter(status=Listing.PENDING_REVIEW).count()

        self.stdout.write('\n📊 数据库统计:')
        self.stdout.write(f"  - 新币总数: {total_listings}")
        self.stdout.write(f"  - 已确认: {confirmed}")
        self.stdout.write(f"  - 待审核: {pending}")
        self.stdout.write('')
