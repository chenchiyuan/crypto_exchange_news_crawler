import logging
from datetime import datetime, timedelta, timezone
from django.core.management.base import BaseCommand, CommandError

from twitter.models import TwitterList, Tweet, PromptTemplate
from twitter.services.orchestrator import TwitterAnalysisOrchestrator

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '强制刷新模板分析'

    def add_arguments(self, parser):
        parser.add_argument('list_id', type=str, help='Twitter List ID')
        parser.add_argument('--hours', type=int, default=24, help='时间范围（小时）')

    def handle(self, *args, **options):
        list_id = options['list_id']
        hours = options['hours']

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('🔄 强制刷新模板分析'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'List ID: {list_id}')
        self.stdout.write(f'时间范围: {hours} 小时')

        try:
            # 1. 获取 TwitterList
            twitter_list = TwitterList.objects.get(list_id=list_id)

            # 2. 强制重新获取模板
            template = PromptTemplate.get_template_for_list(list_id)
            self.stdout.write(f'\n✅ 加载模板: {template.name}')
            self.stdout.write(f'   类型: {template.get_analysis_type_display()}')
            self.stdout.write(f'   长度: {len(template.template_content)} 字符')

            # 3. 打印模板内容的开头部分
            self.stdout.write(f'\n📝 模板内容预览（前 200 字符）:')
            self.stdout.write(template.template_content[:200])
            self.stdout.write('...')

            # 4. 获取推文
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=hours)

            tweets = Tweet.objects.filter(
                twitter_list=twitter_list,
                created_at__gte=start_time,
                created_at__lte=end_time
            ).order_by('-created_at')

            tweet_count = tweets.count()
            self.stdout.write(f'\n📊 获取到 {tweet_count} 条推文')

            if tweet_count == 0:
                self.stdout.write(self.style.WARNING('⚠️ 没有推文可分析'))
                return

            # 5. 直接使用 AI 服务分析（绕过 orchestrator 的模板加载）
            from twitter.services.ai_analysis_service import AIAnalysisService

            ai_service = AIAnalysisService()
            self.stdout.write(f'\n🧠 使用 AI 服务直接分析...')

            # 使用我们加载的模板
            prompt_template = template.template_content

            result = ai_service.analyze_tweets(
                tweets=list(tweets)[:10],  # 只分析前10条
                prompt_template=prompt_template,
                batch_mode=False  # 一次性分析
            )

            self.stdout.write(f'\n✅ 分析完成')
            self.stdout.write(f'   成本: ${result.get("cost", 0):.4f}')
            self.stdout.write(f'   时长: {result.get("processing_time", 0):.2f} 秒')

            # 6. 打印结果结构
            self.stdout.write(f'\n📋 结果结构:')
            for key in result.keys():
                self.stdout.write(f'   - {key}')

            self.stdout.write(f'\n' + '=' * 60)
            self.stdout.write(self.style.SUCCESS('✨ 强制刷新完成'))
            self.stdout.write('=' * 60)

        except Exception as e:
            logger.exception('强制刷新失败')
            self.stdout.write(self.style.ERROR(f'❌ 失败: {e}'))
            raise
