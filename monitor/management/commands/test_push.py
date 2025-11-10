"""
测试告警推送服务
Usage: python manage.py test_push
"""
from django.core.management.base import BaseCommand
from monitor.services.notifier import AlertPushService


class Command(BaseCommand):
    help = '测试告警推送服务连接'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('🧪 测试告警推送服务'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write('')

        # 创建推送服务实例
        push_service = AlertPushService()

        self.stdout.write('推送服务配置:')
        self.stdout.write(f'  API URL: {push_service.api_url}')
        self.stdout.write(f'  Channel: {push_service.channel}')
        self.stdout.write(f'  Token: {push_service.token[:10]}...')
        self.stdout.write('')

        # 测试连接
        self.stdout.write('正在发送测试消息...')

        if push_service.test_push():
            self.stdout.write(self.style.SUCCESS('\n✅ 推送服务测试成功！'))
            self.stdout.write('')
            self.stdout.write('测试消息已成功发送到慧诚告警平台')
        else:
            self.stdout.write(self.style.ERROR('\n❌ 推送服务测试失败'))
            self.stdout.write('')
            self.stdout.write('请检查:')
            self.stdout.write('  1. API URL 是否正确')
            self.stdout.write('  2. Token 是否有效')
            self.stdout.write('  3. 网络连接是否正常')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('='*70))
