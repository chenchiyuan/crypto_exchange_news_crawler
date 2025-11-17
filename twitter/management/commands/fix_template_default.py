import logging
from django.core.management.base import BaseCommand
from django.db import transaction

from twitter.models import PromptTemplate

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '修复模板默认设置'

    def handle(self, *args, **options):
        """修复默认模板设置"""

        try:
            with transaction.atomic():
                # 1. 先取消所有交易信号分析类型的默认设置
                trading_templates = PromptTemplate.objects.filter(
                    analysis_type=PromptTemplate.ANALYSIS_TYPE_TRADING
                )
                for t in trading_templates:
                    t.is_default = False
                    t.save()
                    self.stdout.write(f'取消默认: {t.name} ({t.get_analysis_type_display()})')

                # 2. 找到专业投研模板并设为默认
                pro_template = PromptTemplate.objects.get(
                    name='专业投研分析模板',
                    analysis_type=PromptTemplate.ANALYSIS_TYPE_TRADING
                )
                pro_template.is_default = True
                pro_template.save()

                self.stdout.write(self.style.SUCCESS(f'\n✅ 设置默认: {pro_template.name}'))

                # 3. 同样处理项目机会分析类型
                opportunity_templates = PromptTemplate.objects.filter(
                    analysis_type=PromptTemplate.ANALYSIS_TYPE_OPPORTUNITY
                )
                for t in opportunity_templates:
                    t.is_default = True
                    t.save()
                    self.stdout.write(f'设置默认: {t.name} ({t.get_analysis_type_display()})')

                # 4. 处理通用分析类型
                general_templates = PromptTemplate.objects.filter(
                    analysis_type=PromptTemplate.ANALYSIS_TYPE_GENERAL
                )
                for t in general_templates:
                    t.is_default = True
                    t.save()
                    self.stdout.write(f'设置默认: {t.name} ({t.get_analysis_type_display()})')

                # 5. 处理市场情绪分析类型
                sentiment_templates = PromptTemplate.objects.filter(
                    analysis_type=PromptTemplate.ANALYSIS_TYPE_SENTIMENT
                )
                for t in sentiment_templates:
                    t.is_default = True
                    t.save()
                    self.stdout.write(f'设置默认: {t.name} ({t.get_analysis_type_display()})')

                self.stdout.write(self.style.SUCCESS('\n✨ 所有默认模板设置完成！'))

                # 验证结果
                self.stdout.write('\n📋 当前默认模板:')
                default_templates = PromptTemplate.objects.filter(is_default=True)
                for t in default_templates:
                    self.stdout.write(f'  ✅ {t.get_analysis_type_display()}: {t.name}')

        except Exception as e:
            logger.exception('修复默认模板失败')
            self.stdout.write(self.style.ERROR(f'❌ 修复失败: {e}'))
            raise
