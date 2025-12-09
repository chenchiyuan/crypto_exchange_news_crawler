"""
初始化价格告警规则
Initialize Price Alert Rules

创建或更新系统的5个价格告警规则配置
Feature: 001-price-alert-monitor
"""
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from grid_trading.django_models import PriceAlertRule

logger = logging.getLogger("grid_trading")


class Command(BaseCommand):
    help = '初始化或更新价格告警规则配置'

    def add_arguments(self, parser):
        parser.add_argument(
            '--disable-all',
            action='store_true',
            help='禁用所有规则（用于维护模式）'
        )
        parser.add_argument(
            '--enable-all',
            action='store_true',
            help='启用所有规则'
        )
        parser.add_argument(
            '--rule-id',
            type=int,
            help='只操作指定规则ID（配合--enable或--disable使用）'
        )
        parser.add_argument(
            '--enable',
            action='store_true',
            help='启用指定规则（需配合--rule-id）'
        )
        parser.add_argument(
            '--disable',
            action='store_true',
            help='禁用指定规则（需配合--rule-id）'
        )

    def handle(self, *args, **options):
        """
        主执行函数

        工作流程:
        1. 定义5个规则的配置数据
        2. 批量创建或更新规则
        3. 根据参数启用/禁用规则
        4. 显示最终状态
        """
        self.stdout.write('=' * 60)
        self.stdout.write(
            self.style.SUCCESS('价格告警规则初始化')
        )
        self.stdout.write('=' * 60)
        self.stdout.write('')

        # 处理特殊操作
        if options.get('disable_all'):
            self._disable_all_rules()
            return

        if options.get('enable_all'):
            self._enable_all_rules()
            return

        if options.get('rule_id'):
            self._toggle_single_rule(options)
            return

        # 默认操作：初始化所有规则
        self._initialize_rules()

    def _initialize_rules(self):
        """初始化所有规则"""
        # 定义5个价格告警规则
        rules_data = [
            {
                'rule_id': 1,
                'name': '7天价格新高(4h)',
                'description': '当前价格突破过去7天(42根4h K线)的最高价',
                'enabled': True,
                'parameters': {
                    'lookback_period': 42,
                    'interval': '4h',
                    'direction': 'high'
                }
            },
            {
                'rule_id': 2,
                'name': '7天价格新低(4h)',
                'description': '当前价格跌破过去7天(42根4h K线)的最低价',
                'enabled': True,
                'parameters': {
                    'lookback_period': 42,
                    'interval': '4h',
                    'direction': 'low'
                }
            },
            {
                'rule_id': 3,
                'name': '价格触及MA20',
                'description': '当前价格触及或突破MA20移动平均线',
                'enabled': True,
                'parameters': {
                    'ma_period': 20,
                    'tolerance_pct': 0.5
                }
            },
            {
                'rule_id': 4,
                'name': '价格触及MA99',
                'description': '当前价格触及或突破MA99移动平均线',
                'enabled': True,
                'parameters': {
                    'ma_period': 99,
                    'tolerance_pct': 0.5
                }
            },
            {
                'rule_id': 5,
                'name': '价格达到分布区间90%极值',
                'description': '当前价格达到过去7天价格分布的90%分位数上限或下限',
                'enabled': True,
                'parameters': {
                    'lookback_period': 42,
                    'percentile_upper': 90,
                    'percentile_lower': 10
                }
            }
        ]

        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for rule_data in rules_data:
                rule, created = PriceAlertRule.objects.update_or_create(
                    rule_id=rule_data['rule_id'],
                    defaults={
                        'name': rule_data['name'],
                        'description': rule_data['description'],
                        'enabled': rule_data['enabled'],
                        'parameters': rule_data['parameters']
                    }
                )
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ 创建规则 [{rule.rule_id}] {rule.name}"
                        )
                    )
                    logger.info(f"创建价格告警规则: {rule.name}")
                else:
                    updated_count += 1
                    self.stdout.write(
                        f"✓ 更新规则 [{rule.rule_id}] {rule.name}"
                    )
                    logger.info(f"更新价格告警规则: {rule.name}")

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f"总计: 创建 {created_count} 个，更新 {updated_count} 个"
            )
        )

        # 显示最终状态
        self._show_rules_status()

    def _disable_all_rules(self):
        """禁用所有规则"""
        count = PriceAlertRule.objects.update(enabled=False)
        self.stdout.write(
            self.style.WARNING(f"✓ 已禁用所有规则 ({count} 个)")
        )
        logger.info(f"禁用所有价格告警规则: {count}个")
        self.stdout.write('')
        self._show_rules_status()

    def _enable_all_rules(self):
        """启用所有规则"""
        count = PriceAlertRule.objects.update(enabled=True)
        self.stdout.write(
            self.style.SUCCESS(f"✓ 已启用所有规则 ({count} 个)")
        )
        logger.info(f"启用所有价格告警规则: {count}个")
        self.stdout.write('')
        self._show_rules_status()

    def _toggle_single_rule(self, options):
        """启用/禁用单个规则"""
        rule_id = options['rule_id']
        enable = options.get('enable', False)
        disable = options.get('disable', False)

        if not enable and not disable:
            self.stdout.write(
                self.style.ERROR(
                    '✗ 请指定 --enable 或 --disable'
                )
            )
            return

        try:
            rule = PriceAlertRule.objects.get(rule_id=rule_id)

            if enable:
                rule.enabled = True
                rule.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ 已启用规则 [{rule.rule_id}] {rule.name}"
                    )
                )
                logger.info(f"启用价格告警规则: {rule.name}")
            else:
                rule.enabled = False
                rule.save()
                self.stdout.write(
                    self.style.WARNING(
                        f"✓ 已禁用规则 [{rule.rule_id}] {rule.name}"
                    )
                )
                logger.info(f"禁用价格告警规则: {rule.name}")

            self.stdout.write('')
            self._show_rules_status()

        except PriceAlertRule.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    f"✗ 规则ID {rule_id} 不存在，请先运行初始化"
                )
            )

    def _show_rules_status(self):
        """显示所有规则的状态"""
        rules = PriceAlertRule.objects.all().order_by('rule_id')

        if not rules.exists():
            self.stdout.write(
                self.style.WARNING('⚠️ 数据库中没有规则')
            )
            return

        self.stdout.write('当前规则状态:')
        self.stdout.write('-' * 60)

        enabled_count = 0
        for rule in rules:
            if rule.enabled:
                status = self.style.SUCCESS("✓ 启用")
                enabled_count += 1
            else:
                status = self.style.WARNING("✗ 禁用")

            self.stdout.write(
                f"{status}  [规则{rule.rule_id}] {rule.name}"
            )
            self.stdout.write(
                f"     {rule.description}"
            )

        self.stdout.write('-' * 60)
        self.stdout.write(
            self.style.SUCCESS(
                f"启用规则: {enabled_count}/{rules.count()}"
            )
        )
        self.stdout.write('')

        if enabled_count == 0:
            self.stdout.write(
                self.style.WARNING(
                    '⚠️ 没有启用的规则，价格检测将无法工作'
                )
            )
            self.stdout.write(
                '提示: 运行 python manage.py init_price_alert_rules --enable-all'
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    '✅ 规则已就绪，可以运行价格检测'
                )
            )
            self.stdout.write(
                '下一步: python manage.py check_price_alerts'
            )
