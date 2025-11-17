import os
import sys
import django
import subprocess

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')
sys.path.insert(0, '/Users/chenchiyuan/projects/crypto_exchange_news_crawler')
django.setup()

from django.core.management.base import BaseCommand
from twitter.services.notifier import TwitterNotificationService

class Command(BaseCommand):
    help = '快速设置推送通知'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('🔔 推送通知快速配置'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        # 检查当前配置
        self.stdout.write('\n1️⃣ 当前推送配置:')
        try:
            notifier = TwitterNotificationService()

            if notifier.is_enabled():
                self.stdout.write(f'   ✅ 通知服务: 已启用')
                self.stdout.write(f'   ✅ Token: {notifier.token[:20]}...')
                self.stdout.write(f'   ✅ 渠道: {notifier.channel}')

                # 检查是否配置了 Bark
                from django.conf import settings
                bark_url = getattr(settings, 'BARK_PUSH_URL', '')
                if bark_url:
                    self.stdout.write(f'   ✅ Bark URL: {bark_url[:50]}...')
                    self.stdout.write(self.style.SUCCESS(f'   🎉 Bark 已配置，推送功能完全可用！'))
                else:
                    self.stdout.write(self.style.WARNING(f'   ⚠️ Bark URL: 未配置'))
                    self.stdout.write(self.style.WARNING(f'   💡 建议配置 Bark 以获得更好的推送体验'))

            else:
                self.stdout.write(self.style.ERROR(f'   ❌ 通知服务: 已禁用'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ 检查失败: {e}'))

        # 提供配置选项
        self.stdout.write('\n2️⃣ 配置选项:')
        self.stdout.write('   ')
        self.stdout.write(self.style.SUCCESS('方案 A: Bark 推送（推荐 - 简单免费）'))
        self.stdout.write('   ' + '-' * 50)
        self.stdout.write('   1. 在 iPhone 上安装 "Bark" 应用')
        self.stdout.write('   2. 打开应用获取推送 URL')
        self.stdout.write('   3. 运行以下命令配置:')
        self.stdout.write('')
        self.stdout.write('   export BARK_PUSH_URL="https://api.day.app/your_device_key"')
        self.stdout.write('')

        self.stdout.write('   ')
        self.stdout.write(self.style.SUCCESS('方案 B: 慧诚告警推送'))
        self.stdout.write('   ' + '-' * 50)
        self.stdout.write('   1. 访问: https://huicheng.powerby.com.cn/api/simple/alert/')
        self.stdout.write('   2. 注册账号并配置接收渠道')
        self.stdout.write('   3. 运行以下命令配置:')
        self.stdout.write('')
        self.stdout.write('   export ALERT_PUSH_TOKEN="your_token"')
        self.stdout.write('   export ALERT_PUSH_CHANNEL="twitter_analysis"')
        self.stdout.write('')

        self.stdout.write('3️⃣ 快速测试:')
        self.stdout.write('   配置完成后运行:')
        self.stdout.write('   python manage.py test_notification')

        self.stdout.write('\n4️⃣ 验证推送:')
        self.stdout.write('   运行一次完整分析:')
        self.stdout.write('   python manage.py run_analysis 1939614372311302186 --hours 24')

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('✨ 配置指南完成'))
        self.stdout.write('=' * 60)

        self.stdout.write('\n📚 详细说明请参考: PUSH_NOTIFICATION_GUIDE.md')
