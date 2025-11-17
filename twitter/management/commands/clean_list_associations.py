import logging
from django.core.management.base import BaseCommand
from django.db import transaction

from twitter.models import PromptTemplate, TwitterList

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '清理 List 的模板关联'

    def handle(self, *args, **options):
        """清理指定 List 的所有模板关联，只保留专业投研模板"""

        list_id = '1939614372311302186'

        try:
            with transaction.atomic():
                # 获取 TwitterList
                twitter_list = TwitterList.objects.get(list_id=list_id)

                # 获取所有关联的模板
                templates = list(twitter_list.prompt_templates.all())

                self.stdout.write(f'📋 当前关联的模板 ({len(templates)} 个):')
                for t in templates:
                    self.stdout.write(f'  - {t.name} ({t.get_analysis_type_display()})')

                # 移除除了专业投研模板之外的所有模板
                for t in templates:
                    if t.name != '专业投研分析模板':
                        twitter_list.prompt_templates.remove(t)
                        self.stdout.write(self.style.WARNING(f'  ❌ 移除: {t.name}'))

                # 确保专业投研模板已关联
                pro_template = PromptTemplate.objects.get(
                    name='专业投研分析模板',
                    analysis_type=PromptTemplate.ANALYSIS_TYPE_TRADING
                )
                twitter_list.prompt_templates.add(pro_template)
                self.stdout.write(self.style.SUCCESS(f'  ✅ 确保关联: {pro_template.name}'))

                # 显示最终结果
                final_templates = list(twitter_list.prompt_templates.all())
                self.stdout.write(f'\n📋 最终关联的模板 ({len(final_templates)} 个):')
                for t in final_templates:
                    self.stdout.write(f'  ✅ {t.name} ({t.get_analysis_type_display()})')

                # 验证自动选择
                selected = PromptTemplate.get_template_for_list(list_id)
                self.stdout.write(self.style.SUCCESS(f'\n✅ 自动选择将使用: {selected.name}'))

                self.stdout.write(self.style.SUCCESS('\n✨ List 模板关联清理完成！'))

        except Exception as e:
            logger.exception('清理失败')
            self.stdout.write(self.style.ERROR(f'❌ 清理失败: {e}'))
            raise
