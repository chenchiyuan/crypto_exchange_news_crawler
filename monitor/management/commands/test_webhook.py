"""
测试Webhook推送
Usage: python manage.py test_webhook --url https://your-webhook-url.com
"""
from django.core.management.base import BaseCommand, CommandError
from monitor.services.notifier import WebhookNotifier
from monitor.models import Listing


class Command(BaseCommand):
    help = '测试Webhook推送功能'

    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            type=str,
            required=False,
            help='Webhook URL(可选,默认从环境变量WEBHOOK_URL读取)'
        )
        parser.add_argument(
            '--listing-id',
            type=int,
            default=None,
            help='指定Listing ID发送真实通知(可选)'
        )
        parser.add_argument(
            '--test-only',
            action='store_true',
            help='仅测试连接,不发送真实通知'
        )

    def handle(self, *args, **options):
        webhook_url = options['url']
        listing_id = options['listing_id']
        test_only = options['test_only']

        # 获取Webhook URL
        if not webhook_url:
            import os
            webhook_url = os.getenv('WEBHOOK_URL', '').strip()

        if not webhook_url:
            raise CommandError(
                "未提供Webhook URL!\n"
                "使用方法:\n"
                "  1. python manage.py test_webhook --url https://your-url.com\n"
                "  2. 或设置环境变量: export WEBHOOK_URL=https://your-url.com"
            )

        self.stdout.write(f"Webhook URL: {webhook_url}")

        # 创建通知器
        notifier = WebhookNotifier(webhook_url, max_retries=3, retry_delay=5)

        # 测试连接
        if test_only or not listing_id:
            self.stdout.write("\n正在测试Webhook连接...")
            if notifier.test_webhook():
                self.stdout.write(
                    self.style.SUCCESS("✓ Webhook连接测试成功!")
                )
            else:
                self.stdout.write(
                    self.style.ERROR("✗ Webhook连接测试失败!")
                )
            return

        # 发送真实通知
        try:
            listing = Listing.objects.get(id=listing_id)
        except Listing.DoesNotExist:
            raise CommandError(
                f"Listing ID {listing_id} 不存在!\n"
                f"请先运行: python manage.py identify_listings"
            )

        self.stdout.write(f"\n正在发送通知...")
        self.stdout.write(f"  币种: {listing.coin_symbol}")
        self.stdout.write(f"  交易所: {listing.get_exchange().name}")
        self.stdout.write(f"  类型: {listing.get_listing_type_display()}")

        if notifier.send_notification(listing, create_record=True):
            self.stdout.write(
                self.style.SUCCESS("\n✓ 通知发送成功!")
            )

            # 显示通知记录
            from monitor.models import NotificationRecord
            recent_record = NotificationRecord.objects.filter(
                listing=listing
            ).order_by('-created_at').first()

            if recent_record:
                self.stdout.write("\n通知记录:")
                self.stdout.write(f"  状态: {recent_record.get_status_display()}")
                self.stdout.write(f"  渠道: {recent_record.get_channel_display()}")
                self.stdout.write(f"  重试次数: {recent_record.retry_count}")
                if recent_record.sent_at:
                    self.stdout.write(
                        f"  发送时间: {recent_record.sent_at.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
        else:
            self.stdout.write(
                self.style.ERROR("\n✗ 通知发送失败!")
            )

        # 批量通知示例
        self.stdout.write("\n提示: 批量发送通知:")
        self.stdout.write("  from monitor.models import Listing")
        self.stdout.write("  from monitor.services.notifier import WebhookNotifier")
        self.stdout.write("  listings = Listing.objects.filter(status='confirmed')[:5]")
        self.stdout.write(f"  notifier = WebhookNotifier('{webhook_url}')")
        self.stdout.write("  notifier.send_batch_notifications(listings)")
