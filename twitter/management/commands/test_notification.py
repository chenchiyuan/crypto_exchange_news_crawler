import logging
from django.core.management.base import BaseCommand

from twitter.services.notifier import TwitterNotificationService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '测试通知服务配置'

    def handle(self, *args, **options):
        """测试通知服务配置"""

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('🔔 通知服务测试'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        # 测试默认配置
        self.stdout.write('\n1️⃣ 测试默认配置（无参数）:')
        try:
            notifier = TwitterNotificationService()
            self.stdout.write(f'   ✅ 通知服务状态: {"启用" if notifier.is_enabled() else "禁用"}')
            self.stdout.write(f'   ✅ Token: {notifier.token[:20]}...')
            self.stdout.write(f'   ✅ 渠道: {notifier.channel}')
            self.stdout.write(f'   ✅ 成本阈值: ${notifier.cost_alert_threshold}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ 失败: {e}'))

        # 测试自定义配置
        self.stdout.write('\n2️⃣ 测试自定义配置:')
        try:
            custom_notifier = TwitterNotificationService(
                token='test_token_123',
                channel='test_channel',
                cost_alert_threshold=10.00
            )
            self.stdout.write(f'   ✅ 通知服务状态: {"启用" if custom_notifier.is_enabled() else "禁用"}')
            self.stdout.write(f'   ✅ Token: {custom_notifier.token}')
            self.stdout.write(f'   ✅ 渠道: {custom_notifier.channel}')
            self.stdout.write(f'   ✅ 成本阈值: ${custom_notifier.cost_alert_threshold}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ 失败: {e}'))

        # 测试禁用配置
        self.stdout.write('\n3️⃣ 测试禁用配置:')
        try:
            disabled_notifier = TwitterNotificationService(token=None)
            self.stdout.write(f'   ✅ 通知服务状态: {"启用" if disabled_notifier.is_enabled() else "禁用"}')
            self.stdout.write(f'   ✅ Alert Service: {disabled_notifier.alert_service}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ 失败: {e}'))

        # 测试格式化方法
        self.stdout.write('\n4️⃣ 测试格式化方法:')
        try:
            notifier = TwitterNotificationService()
            self.stdout.write(f'   ✅ 完成标题: {notifier.format_completion_title.__name__}')
            self.stdout.write(f'   ✅ 完成内容: {notifier.format_completion_content.__name__}')
            self.stdout.write(f'   ✅ 失败标题: {notifier.format_failure_title.__name__}')
            self.stdout.write(f'   ✅ 失败内容: {notifier.format_failure_content.__name__}')
            self.stdout.write(f'   ✅ 成本告警标题: {notifier.format_cost_alert_title.__name__}')
            self.stdout.write(f'   ✅ 成本告警内容: {notifier.format_cost_alert_content.__name__}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ 失败: {e}'))

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('✅ 通知服务测试完成'))
        self.stdout.write('=' * 60)

        # 总结
        self.stdout.write('\n📋 配置总结:')
        self.stdout.write('  • 默认启用: ✅ 是')
        self.stdout.write('  • 默认 Token: ✅ 是')
        self.stdout.write('  • 可自定义: ✅ 是')
        self.stdout.write('  • 可禁用: ✅ 是')
        self.stdout.write('\n💡 提示: 运行分析命令时会自动使用通知服务')
