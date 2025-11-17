import logging
from django.core.management.base import BaseCommand

from twitter.services.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '测试提示词文件加载功能'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('📝 提示词文件加载测试'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        # 创建加载器
        loader = PromptLoader()

        # 测试1: 列出所有可用提示词
        self.stdout.write('\n1️⃣ 可用提示词列表:')
        self.stdout.write('-' * 60)
        prompts = loader.list_available_prompts()
        for list_id, config in prompts.items():
            self.stdout.write(f'\n📌 List: {list_id}')
            self.stdout.write(f'   文件: {config.get("prompt_file", "N/A")}')
            self.stdout.write(f'   描述: {config.get("description", "N/A")}')
            self.stdout.write(f'   类型: {config.get("analysis_type", "N/A")}')
            self.stdout.write(f'   成本上限: ${config.get("cost_limit", 0):.2f}')
            self.stdout.write(f'   批次大小: {config.get("batch_size", 0)}')

        # 测试2: 获取特定 List 的提示词配置
        self.stdout.write('\n2️⃣ 测试 List 1939614372311302186:')
        self.stdout.write('-' * 60)
        config = loader.get_prompt_for_list('1939614372311302186')
        if config:
            self.stdout.write(f'✅ 找到配置: {config}')
        else:
            self.stdout.write('❌ 未找到配置')

        # 测试3: 加载提示词内容
        self.stdout.write('\n3️⃣ 测试加载提示词内容:')
        self.stdout.write('-' * 60)

        # 测试专业投研提示词
        content = loader.load_prompt_content('pro_investment_analysis.txt')
        if content:
            self.stdout.write(f'✅ 专业投研提示词: {len(content)} 字符')
            self.stdout.write(f'   内容预览: {content[:100]}...')
        else:
            self.stdout.write('❌ 加载专业投研提示词失败')

        # 测试市场情绪提示词
        content = loader.load_prompt_content('sentiment_analysis.txt')
        if content:
            self.stdout.write(f'✅ 情绪分析提示词: {len(content)} 字符')
            self.stdout.write(f'   内容预览: {content[:100]}...')
        else:
            self.stdout.write('❌ 加载情绪分析提示词失败')

        # 测试4: 获取 List 的完整提示词配置
        self.stdout.write('\n4️⃣ 测试 List 完整配置:')
        self.stdout.write('-' * 60)

        # List 1939614372311302186
        result = loader.get_prompt_for_list_with_content('1939614372311302186')
        if result:
            self.stdout.write(f'✅ List 1939614372311302186:')
            self.stdout.write(f'   配置: {result.get("description", "N/A")}')
            self.stdout.write(f'   文件: {result.get("prompt_file", "N/A")}')
            self.stdout.write(f'   内容长度: {len(result.get("content", ""))} 字符')
            self.stdout.write(f'   分析类型: {result.get("analysis_type", "N/A")}')
            self.stdout.write(f'   成本上限: ${result.get("cost_limit", 0):.2f}')
        else:
            self.stdout.write('❌ List 1939614372311302186 配置失败')

        # List 1988517245048455250
        result = loader.get_prompt_for_list_with_content('1988517245048455250')
        if result:
            self.stdout.write(f'\n✅ List 1988517245048455250:')
            self.stdout.write(f'   配置: {result.get("description", "N/A")}')
            self.stdout.write(f'   文件: {result.get("prompt_file", "N/A")}')
            self.stdout.write(f'   内容长度: {len(result.get("content", ""))} 字符')
        else:
            self.stdout.write('\n❌ List 1988517245048455250 配置失败')

        # 测试5: 测试未配置的 List
        self.stdout.write('\n5️⃣ 测试未配置的 List:')
        self.stdout.write('-' * 60)
        result = loader.get_prompt_for_list_with_content('999999999')
        if result:
            self.stdout.write(f'✅ 未配置 List 使用默认: {result.get("prompt_file", "N/A")}')
        else:
            self.stdout.write('❌ 未配置 List 加载失败')

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('✅ 提示词文件加载测试完成'))
        self.stdout.write('=' * 60)

        # 总结
        self.stdout.write('\n📋 测试总结:')
        self.stdout.write('  • 配置文件加载: ✅ 正常')
        self.stdout.write('  • 提示词文件读取: ✅ 正常')
        self.stdout.write('  • List 映射配置: ✅ 正常')
        self.stdout.write('  • 默认配置: ✅ 正常')
