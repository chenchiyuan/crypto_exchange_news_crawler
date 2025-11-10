"""
测试推送指定的新币信息
Usage: python manage.py test_listing_push --listing-id <id>
"""
from django.core.management.base import BaseCommand
from monitor.models import Listing
from monitor.services.notifier import AlertPushService


class Command(BaseCommand):
    help = '测试推送指定新币的告警信息'

    def add_arguments(self, parser):
        parser.add_argument(
            '--listing-id',
            type=int,
            help='要推送的新币ID'
        )

    def handle(self, *args, **options):
        listing_id = options.get('listing_id')

        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('🧪 测试新币推送'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write('')

        # 如果没有指定ID，显示可用的新币列表
        if not listing_id:
            self.stdout.write('可用的已确认新币:')
            confirmed_listings = Listing.objects.filter(
                status=Listing.CONFIRMED
            ).select_related('announcement__exchange').order_by('-identified_at')[:5]

            if not confirmed_listings:
                self.stdout.write(self.style.WARNING('  未找到已确认的新币'))
                self.stdout.write('')
                self.stdout.write('提示: 先运行 python manage.py monitor 来识别新币')
                return

            for listing in confirmed_listings:
                exchange_name = listing.announcement.exchange.name
                self.stdout.write(
                    f"  ID {listing.id}: {listing.coin_symbol} "
                    f"({listing.get_listing_type_display()}) "
                    f"- {exchange_name}"
                )

            self.stdout.write('')
            self.stdout.write('使用方法: python manage.py test_listing_push --listing-id <ID>')
            return

        # 获取指定的新币
        try:
            listing = Listing.objects.select_related(
                'announcement__exchange'
            ).get(id=listing_id)
        except Listing.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ 未找到ID为 {listing_id} 的新币'))
            return

        # 显示新币信息
        exchange = listing.announcement.exchange
        self.stdout.write('新币信息:')
        self.stdout.write(f'  币种: {listing.coin_symbol}')
        self.stdout.write(f'  类型: {listing.get_listing_type_display()}')
        self.stdout.write(f'  交易所: {exchange.name}')
        self.stdout.write(f'  置信度: {listing.confidence:.0%}')
        self.stdout.write(f'  状态: {listing.get_status_display()}')
        self.stdout.write('')

        # 创建推送服务并发送
        push_service = AlertPushService()

        self.stdout.write('正在发送告警推送...')

        if push_service.send_notification(listing, create_record=False):
            self.stdout.write(self.style.SUCCESS('\n✅ 推送成功！'))
            self.stdout.write('')
            self.stdout.write('推送内容预览:')
            self.stdout.write(f'标题: {push_service.format_title(listing)}')
            self.stdout.write('')
            self.stdout.write('内容:')
            for line in push_service.format_content(listing).split('\n'):
                self.stdout.write(f'  {line}')
        else:
            self.stdout.write(self.style.ERROR('\n❌ 推送失败'))
            self.stdout.write('')
            self.stdout.write('请检查日志获取详细错误信息')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('='*70))
