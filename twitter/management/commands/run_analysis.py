import logging
from datetime import datetime, timedelta, timezone
from django.core.management.base import BaseCommand, CommandError

from twitter.models import TwitterList, Tweet
from twitter.services.twitter_list_service import TwitterListService
from twitter.services.orchestrator import TwitterAnalysisOrchestrator

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '一键分析：从指定 Twitter List 自动收集最新推文并执行分析（带缓存）'

    def add_arguments(self, parser):
        # 位置参数
        parser.add_argument(
            'list_id',
            type=str,
            help='Twitter List ID'
        )

        # 时间参数
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='获取最近 N 小时的推文（默认 24）'
        )

        # 批次参数
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='每批获取的推文数量（50-1000，默认 500）'
        )

        # 模式参数
        parser.add_argument(
            '--no-cache',
            action='store_true',
            help='禁用缓存，获取所有推文'
        )
        parser.add_argument(
            '--collect-only',
            action='store_true',
            help='仅收集推文，不执行分析'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='试运行模式：只获取不保存到数据库'
        )
        parser.add_argument(
            '--save-prompt',
            action='store_true',
            help='保存推送给AI前的原始内容（用于调试）'
        )

    def handle(self, *args, **options):
        list_id = options['list_id']
        hours = options['hours']
        batch_size = options['batch_size']
        no_cache = options['no_cache']
        collect_only = options['collect_only']
        dry_run = options['dry_run']
        save_prompt = options.get('save_prompt', False)

        # 验证批次大小
        if not 50 <= batch_size <= 1000:
            raise CommandError('batch-size 必须在 50-1000 之间')

        # 显示配置
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('🚀 一键分析（自动缓存 + 分析）'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'List ID: {list_id}')
        self.stdout.write(f'模式: {"缓存模式" if not no_cache else "无缓存模式"}')
        self.stdout.write(f'收集范围: 最近 {hours} 小时')
        self.stdout.write(f'批次大小: {batch_size}')
        if collect_only:
            self.stdout.write(f'操作: 仅收集推文')
        else:
            self.stdout.write(f'操作: 收集 + 分析')
        if dry_run:
            self.stdout.write(f'模式: 试运行（不保存）')
        self.stdout.write(self.style.SUCCESS('=' * 60))

        # 获取或创建 TwitterList
        try:
            twitter_list, created = TwitterList.objects.get_or_create(
                list_id=list_id,
                defaults={
                    'name': f'List {list_id}',
                    'description': f'Auto-created for list_id {list_id}',
                    'status': 'active'
                }
            )

            if created:
                self.stdout.write(self.style.WARNING(
                    f'⚠️ 创建新 TwitterList: {twitter_list.name}'
                ))
            else:
                self.stdout.write(f'📋 使用现有 TwitterList: {twitter_list.name}')

        except Exception as e:
            raise CommandError(f'获取 TwitterList 失败: {e}')

        # === 第一步：收集推文（带缓存） ===
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('📥 步骤 1: 收集推文（自动缓存）'))
        self.stdout.write('=' * 60)

        # 计算时间范围
        now = datetime.now(timezone.utc)

        # 检查缓存：获取数据库中该 List 的最新推文时间
        start_time = None
        if not no_cache:
            latest_tweet = Tweet.objects.filter(
                twitter_list=twitter_list
            ).order_by('-created_at').first()

            if latest_tweet:
                start_time = latest_tweet.created_at
                # 加一些缓冲时间，确保不遗漏
                start_time = start_time - timedelta(minutes=5)
                self.stdout.write(f'✅ 使用缓存：从 {start_time} 开始获取')
                self.stdout.write(f'   数据库最新推文时间: {latest_tweet.created_at}')
            else:
                start_time = now - timedelta(hours=hours)
                self.stdout.write(f'📝 初次收集：获取最近 {hours} 小时的推文')
        else:
            start_time = now - timedelta(hours=hours)
            self.stdout.write(f'⚠️ 禁用缓存：获取最近 {hours} 小时的推文')

        end_time = now

        # 验证时间范围
        if start_time >= end_time:
            raise CommandError('开始时间必须早于结束时间')

        time_diff = end_time - start_time
        if time_diff.days > 7:
            raise CommandError('时间范围不能超过 7 天')

        self.stdout.write(f'\n时间范围: {start_time} ~ {end_time}')
        self.stdout.write(f'时间跨度: {time_diff.total_seconds() / 3600:.1f} 小时')

        # 执行收集
        try:
            service = TwitterListService(twitter_list)
            summary = service.collect_and_save_tweets(
                start_time=start_time,
                end_time=end_time,
                batch_size=batch_size,
                dry_run=dry_run
            )

            # 显示收集结果
            self.stdout.write('\n' + '=' * 60)
            self.stdout.write(self.style.SUCCESS('📥 收集结果'))
            self.stdout.write('=' * 60)
            self.stdout.write(f'处理批次数: {summary["batches_processed"]}')
            self.stdout.write(f'总获取推文数: {summary["total_fetched"]}')

            if not dry_run:
                self.stdout.write(self.style.SUCCESS(
                    f'新保存推文数: {summary["total_saved"]}'
                ))
                self.stdout.write(
                    f'重复推文数: {summary["total_duplicates"]}'
                )
            else:
                self.stdout.write(self.style.WARNING('试运行模式：未保存到数据库'))

            # 关闭服务
            service.close()

        except Exception as e:
            logger.exception(f'收集推文失败: {e}')
            raise CommandError(f'收集推文失败: {e}')

        # === 第二步：执行分析 ===
        if not collect_only:
            self.stdout.write('\n' + '=' * 60)
            self.stdout.write(self.style.SUCCESS('🔍 步骤 2: 执行分析'))
            self.stdout.write('=' * 60)

            # 获取待分析的推文
            # 如果有新的推文被收集，分析从 start_time 开始的所有推文
            # 如果没有新推文，分析最近的 200 条推文（避免分析太多）
            if summary['total_saved'] > 0:
                # 有新推文：分析从 start_time 开始的所有推文
                tweets_to_analyze = Tweet.objects.filter(
                    twitter_list=twitter_list,
                    created_at__gte=start_time
                ).order_by('-created_at')
                self.stdout.write(f'📊 分析模式: 新推文增量分析')
            else:
                # 没有新推文：分析最近的 200 条推文
                tweets_to_analyze = Tweet.objects.filter(
                    twitter_list=twitter_list
                ).order_by('-created_at')[:200]
                self.stdout.write(f'📊 分析模式: 历史数据分析（最近 200 条）')

            tweet_count = tweets_to_analyze.count()

            if tweet_count == 0:
                self.stdout.write(self.style.WARNING('\n⚠️ 没有待分析的推文'))
                return

            self.stdout.write(f'\n待分析推文数量: {tweet_count} 条')

            # 计算分析时间范围
            # 使用tweet_created_at（推文发布时间）而不是created_at（保存时间）
            # 这样可以确保获取所有需要分析的推文
            tweets_to_analyze_qs = Tweet.objects.filter(twitter_list=twitter_list)
            if tweets_to_analyze_qs.exists():
                earliest = tweets_to_analyze_qs.earliest('tweet_created_at')
                latest = tweets_to_analyze_qs.latest('tweet_created_at')
                analysis_start_time = earliest.tweet_created_at
                analysis_end_time = latest.tweet_created_at
                self.stdout.write(f'分析时间范围: {analysis_start_time} ~ {analysis_end_time}')
            else:
                analysis_start_time = start_time
                analysis_end_time = end_time

            # 执行分析
            try:
                # 显示使用的模板
                try:
                    from twitter.models import PromptTemplate
                    template = PromptTemplate.get_template_for_list(list_id)
                    self.stdout.write(f'\n✅ 自动选择模板: {template.name} ({template.get_analysis_type_display()})')
                except Exception as e:
                    self.stdout.write(f'\n⚠️ 使用默认模板: 通用加密货币分析')

                self.stdout.write('\n开始 AI 分析...')

                # 使用 orchestrator 执行分析
                orchestrator = TwitterAnalysisOrchestrator()
                task = orchestrator.run_analysis(
                    twitter_list=twitter_list,
                    start_time=analysis_start_time if tweet_count > 0 else start_time,
                    end_time=analysis_end_time if tweet_count > 0 else end_time,
                    prompt_template=None,  # 自动选择
                    max_cost=None,  # 使用默认
                    batch_mode=None,  # 自动判断
                    batch_size=batch_size,
                    dry_run=False,
                    save_prompt=save_prompt
                )

                # 显示分析结果
                self.stdout.write('\n' + '=' * 60)
                self.stdout.write(self.style.SUCCESS('✅ 分析完成'))
                self.stdout.write('=' * 60)
                self.stdout.write(f'任务 ID: {task.task_id}')
                self.stdout.write(f'推文数量: {tweet_count}')
                self.stdout.write(f'实际成本: ${task.cost_amount:.4f}')
                self.stdout.write(f'处理时长: {task.processing_time:.2f} 秒')
                self.stdout.write(f'分析状态: {"✅ 成功" if task.analysis_result else "❌ 失败"}')

                if task.analysis_result:
                    # 验证分析结果格式（JSONField 返回字典）
                    if isinstance(task.analysis_result, dict):
                        self.stdout.write('分析结果: ✅ 格式正确（字典类型）')
                        self.stdout.write(f'结果键数: {len(task.analysis_result)}')
                    elif isinstance(task.analysis_result, str):
                        # 尝试解析 JSON 字符串
                        try:
                            import json
                            json.loads(task.analysis_result)
                            self.stdout.write('JSON 格式: ✅ 正确')
                        except:
                            self.stdout.write('JSON 格式: ❌ 解析失败')
                    else:
                        self.stdout.write(f'分析结果类型: {type(task.analysis_result)}')

            except Exception as e:
                logger.exception(f'分析失败: {e}')
                self.stdout.write(self.style.ERROR(f'\n❌ 分析失败: {e}'))
                raise

        # === 总结 ===
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('✨ 任务完成'))
        self.stdout.write('=' * 60)

        if not dry_run and not collect_only:
            self.stdout.write('✅ 推文收集完成')
            self.stdout.write('✅ AI 分析完成')
            self.stdout.write('\n📊 查看结果:')
            self.stdout.write(f'   python check_result.py  # 查看最新分析结果')
            self.stdout.write(f'   python verify_data.py   # 数据统计')

        elif not dry_run:
            self.stdout.write('✅ 推文收集完成')

        self.stdout.write('=' * 60)