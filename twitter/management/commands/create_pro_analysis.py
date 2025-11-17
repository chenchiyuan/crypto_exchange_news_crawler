import logging
from datetime import datetime, timedelta, timezone
from django.core.management.base import BaseCommand
from django.db import transaction

from twitter.models import TwitterList, Tweet, PromptTemplate, TwitterAnalysisResult
from twitter.services.ai_analysis_service import AIAnalysisService
import uuid

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '创建专业投研分析结果'

    def add_arguments(self, parser):
        parser.add_argument('list_id', type=str, help='Twitter List ID')
        parser.add_argument('--hours', type=int, default=24, help='时间范围（小时）')

    def handle(self, *args, **options):
        list_id = options['list_id']
        hours = options['hours']

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('🎯 创建专业投研分析'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'List ID: {list_id}')
        self.stdout.write(f'时间范围: {hours} 小时')

        try:
            with transaction.atomic():
                # 1. 获取 TwitterList
                twitter_list = TwitterList.objects.get(list_id=list_id)

                # 2. 强制重新获取模板
                template = PromptTemplate.get_template_for_list(list_id)
                self.stdout.write(f'\n✅ 加载模板: {template.name}')
                self.stdout.write(f'   类型: {template.get_analysis_type_display()}')

                # 3. 获取推文
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

                # 4. 使用 AI 服务分析
                ai_service = AIAnalysisService()
                self.stdout.write(f'\n🧠 开始 AI 分析...')

                prompt_template = template.template_content

                result = ai_service.analyze_tweets(
                    tweets=list(tweets)[:10],  # 只分析前10条
                    prompt_template=prompt_template,
                    batch_mode=False
                )

                # 5. 创建分析结果记录
                task_id = str(uuid.uuid4())
                analysis_result = TwitterAnalysisResult.objects.create(
                    task_id=task_id,
                    twitter_list=twitter_list,
                    tweet_count=tweet_count,
                    start_time=start_time,
                    end_time=end_time,
                    cost_amount=result.get('cost', 0),
                    processing_time=result.get('processing_time', 0) / 1000,  # 转换为秒
                    analysis_result=result,
                    status='completed'
                )

                self.stdout.write(f'\n✅ 分析完成')
                self.stdout.write(f'   任务 ID: {task_id}')
                self.stdout.write(f'   推文数量: {tweet_count}')
                self.stdout.write(f'   成本: ${result.get("cost", 0):.4f}')
                self.stdout.write(f'   时长: {result.get("processing_time", 0)/1000:.2f} 秒')

                # 6. 检查结果格式
                if isinstance(result, dict):
                    required_keys = [
                        'consensus_statistics',
                        'viewpoints',
                        'operations',
                        'signals',
                        'comprehensive_analysis',
                        'risk_alerts',
                        'appendix',
                        'analysis_metadata'
                    ]

                    is_pro_format = all(key in result for key in required_keys)

                    if is_pro_format:
                        self.stdout.write(self.style.SUCCESS('\n✅ 格式验证: 专业投研格式（JSON）'))
                    else:
                        self.stdout.write(self.style.WARNING('\n⚠️ 格式验证: 非专业投研格式'))

                    # 打印关键字段
                    self.stdout.write(f'\n📋 结果结构:')
                    for key in sorted(result.keys()):
                        if isinstance(result[key], list):
                            self.stdout.write(f'  - {key}: [{len(result[key])} 项]')
                        elif isinstance(result[key], dict):
                            print(f'  - {key}: {{...}} ({len(result[key])} 键)')
                        else:
                            print(f'  - {key}')

                self.stdout.write(f'\n' + '=' * 60)
                self.stdout.write(self.style.SUCCESS('✨ 专业投研分析完成'))
                self.stdout.write(f'任务 ID: {task_id}')
                self.stdout.write('=' * 60)

        except Exception as e:
            logger.exception('创建分析失败')
            self.stdout.write(self.style.ERROR(f'❌ 失败: {e}'))
            raise
