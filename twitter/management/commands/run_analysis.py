import logging
import os
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
        parser.add_argument(
            '--force-fetch-days',
            type=int,
            default=None,
            help='强制从API获取最近 N 天的推文（忽略缓存，用于数据初始化）'
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
            '--filter-only',
            action='store_true',
            help='仅按时间过滤推文，不执行AI分析'
        )
        parser.add_argument(
            '--direct-analysis',
            action='store_true',
            help='直接分析模式：使用固定提示词，返回AI原始响应（无修改）'
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
        parser.add_argument(
            '--push-only-on-new',
            action='store_true',
            help='仅在获取到新推文时发送推送（节省通知成本）'
        )

    def handle(self, *args, **options):
        list_id = options['list_id']
        hours = options['hours']
        batch_size = options['batch_size']
        no_cache = options['no_cache']
        collect_only = options['collect_only']
        filter_only = options['filter_only']
        direct_analysis = options['direct_analysis']
        dry_run = options['dry_run']
        save_prompt = options.get('save_prompt', False)
        push_only_on_new = options.get('push_only_on_new', False)
        force_fetch_days = options.get('force_fetch_days', None)

        # 验证批次大小
        if not 50 <= batch_size <= 1000:
            raise CommandError('batch-size 必须在 50-1000 之间')

        # 显示配置
        self.stdout.write(self.style.SUCCESS('=' * 60))
        if filter_only:
            self.stdout.write(self.style.SUCCESS('🔍 推文时间过滤（仅按时间过滤，不分析）'))
        elif collect_only:
            self.stdout.write(self.style.SUCCESS('📥 推文收集器（仅收集，不分析）'))
        elif direct_analysis:
            self.stdout.write(self.style.SUCCESS('🤖 直接分析模式（返回AI原始响应）'))
        else:
            self.stdout.write(self.style.SUCCESS('🚀 一键分析（自动缓存 + 分析）'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'List ID: {list_id}')

        # 显示模式和时间窗口
        if force_fetch_days:
            self.stdout.write(f'模式: 强制获取模式（忽略缓存）')
            self.stdout.write(f'时间窗口: 最近 {force_fetch_days} 天')
        else:
            self.stdout.write(f'模式: {"缓存模式" if not no_cache else "无缓存模式"}')
            self.stdout.write(f'时间窗口: 最近 {hours} 小时')

        # 显示操作模式
        if collect_only:
            self.stdout.write(f'操作: 仅收集推文')
        elif filter_only:
            self.stdout.write(f'操作: 按时间过滤推文（无AI分析）')
        elif direct_analysis:
            self.stdout.write(f'操作: 直接AI分析（无修改返回）')
        else:
            self.stdout.write(f'批次大小: {batch_size}')
            self.stdout.write(f'操作: 收集 + AI分析')

        if dry_run:
            self.stdout.write(f'模式: 试运行（不保存）')
        if push_only_on_new:
            self.stdout.write(f'推送策略: 仅新推文时推送（节省通知成本）')
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

        # 检查是否强制获取指定天数的推文
        start_time = None
        if force_fetch_days:
            # 强制从 API 获取指定天数的推文（忽略缓存）
            start_time = now - timedelta(days=force_fetch_days)
            self.stdout.write(self.style.WARNING(f'⚠️ 强制获取模式：获取最近 {force_fetch_days} 天的推文'))
            self.stdout.write(f'   时间范围: {start_time} ~ {now}')
            self.stdout.write(f'   注意：将忽略数据库缓存，强制从API获取')
        elif not no_cache:
            # 检查缓存：获取数据库中该 List 的最新推文时间
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

        # 强制获取模式允许更长的时间范围（最多30天）
        if force_fetch_days:
            if time_diff.days > 30:
                raise CommandError('强制获取模式下时间范围不能超过 30 天')
        else:
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

        # === 第二步：按时间过滤推文（无AI分析） ===
        if filter_only:
            self.stdout.write('\n' + '=' * 60)
            self.stdout.write(self.style.SUCCESS('🔍 步骤 2: 按时间过滤推文'))
            self.stdout.write('=' * 60)

            # 获取推文（限制在时间窗口内）
            tweets = Tweet.objects.filter(
                twitter_list=twitter_list,
                tweet_created_at__gte=start_time
            ).order_by('-tweet_created_at')[:500]

            tweet_count = tweets.count()
            self.stdout.write(f'时间窗口: {start_time.strftime("%Y-%m-%d %H:%M")} ~ {end_time.strftime("%Y-%m-%d %H:%M")}')
            self.stdout.write(f'推文数量: {tweet_count} 条')

            if tweet_count == 0:
                self.stdout.write(self.style.WARNING('\n⚠️ 没有找到推文'))
                return

            # 保存结果到文件
            output_file = os.path.join('data', f"time_filtered_tweets_{list_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"按时间过滤结果 - List {list_id}\n")
                f.write(f"时间范围: {start_time} ~ {end_time}\n")
                f.write(f"推文总数: {tweet_count} 条\n")
                f.write('=' * 80 + '\n\n')

                for i, tweet in enumerate(tweets, 1):
                    f.write(f"{i}. [@{tweet.screen_name}] ({tweet.tweet_created_at.strftime('%Y-%m-%d %H:%M')})\n")
                    f.write(f"   内容: {tweet.content}\n")
                    f.write(f"   互动: 👍{tweet.favorite_count} 🔄{tweet.retweet_count} 💬{tweet.reply_count}\n")
                    f.write(f"   Tweet ID: {tweet.tweet_id}\n\n")

            self.stdout.write(f'\n💾 结果已保存到: {output_file}')
            self.stdout.write('\n' + '=' * 60)
            self.stdout.write(self.style.SUCCESS('✨ 时间过滤完成'))
            self.stdout.write('=' * 60)
            return

        # === 第二步：直接AI分析（返回原始响应）===
        if direct_analysis:
            self.stdout.write('\n' + '=' * 60)
            self.stdout.write(self.style.SUCCESS('🤖 步骤 2: 直接AI分析'))
            self.stdout.write('=' * 60)

            # 获取待分析的推文（限制在时间窗口内）
            tweets = Tweet.objects.filter(
                twitter_list=twitter_list,
                tweet_created_at__gte=start_time
            ).order_by('-tweet_created_at')[:200]

            tweet_count = tweets.count()
            self.stdout.write(f'待分析推文数量: {tweet_count} 条')
            self.stdout.write(f'时间范围: {start_time.strftime("%Y-%m-%d %H:%M")} ~ {end_time.strftime("%Y-%m-%d %H:%M")}')

            if tweet_count == 0:
                self.stdout.write(self.style.WARNING('\n⚠️ 没有待分析的推文'))
                return

            # 格式化推文
            from twitter.services.ai_analysis_service import AIAnalysisService
            formatter = AIAnalysisService()
            tweets_text = formatter.format_tweets_for_analysis(tweets)

            # 加载直接分析提示词
            prompt_file = 'twitter/prompts/pro_investment_analysis_direct.txt'
            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompt_template = f.read()

            # 构建完整的AI输入
            full_input = f'{prompt_template}\n\n{tweets_text}'

            # 调用DeepSeek API
            from twitter.sdk.deepseek_sdk import DeepSeekSDK
            sdk = DeepSeekSDK()

            try:
                self.stdout.write('\n🚀 正在调用DeepSeek API...')
                response = sdk.analyze_content(
                    content=tweets_text,
                    prompt_template=prompt_template,
                    task_id=f'direct_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
                )

                # 直接输出原始响应
                self.stdout.write('\n' + '=' * 60)
                self.stdout.write(self.style.SUCCESS('📊 DeepSeek 分析结果（原始响应）'))
                self.stdout.write('=' * 60)
                self.stdout.write(response.content)
                self.stdout.write('=' * 60)

                # 保存结果到文件
                output_file = os.path.join('data', f"direct_analysis_result_{list_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(f"直接分析结果 - List {list_id}\n")
                    f.write(f"时间范围: {start_time} ~ {end_time}\n")
                    f.write(f"推文数量: {tweet_count} 条\n")
                    f.write('=' * 80 + '\n\n')
                    f.write(response.content)

                self.stdout.write(f'\n💾 原始结果已保存到: {output_file}')

                # 推送分析结果
                try:
                    from twitter.services.notifier import TwitterNotificationService

                    # 提取总结作为推送标题
                    # 查找多种可能的总结标题格式
                    content = response.content
                    summary_line = None

                    # 查找总结部分（支持多种格式）
                    lines = content.split('\n')
                    summary_patterns = [
                        '7️⃣ 一句话总结',   # 标准格式
                        '### 7️⃣ 一句话总结',  # Markdown格式
                        '7️⃣ 总结',          # 简化格式
                        '### 7️⃣ 总结',      # Markdown简化格式
                        '一句话总结',        # 纯文本格式
                    ]

                    for i, line in enumerate(lines):
                        # 检查是否包含任一总结标题格式
                        if any(pattern in line for pattern in summary_patterns):
                            # 检查是否在同一行（冒号后面直接跟内容）
                            if '：' in line or ':' in line:
                                # 提取冒号后的内容
                                if '：' in line:
                                    summary_line = line.split('：', 1)[1].strip()
                                else:
                                    summary_line = line.split(':', 1)[1].strip()
                                if summary_line:  # 如果冒号后有内容
                                    break

                            # 否则查找下一行非空内容作为总结
                            for j in range(i + 1, len(lines)):
                                next_line = lines[j].strip()
                                if next_line:  # 非空行
                                    summary_line = next_line
                                    break
                            break

                    # 如果找到了总结，使用总结作为标题；否则使用默认标题
                    if summary_line and summary_line:
                        # 限制标题长度（推送标题不宜过长）
                        if len(summary_line) > 100:
                            summary_line = summary_line[:97] + "..."
                        push_title = summary_line
                    else:
                        push_title = f"Twitter分析结果 - List {list_id}"

                    push_content = content

                    # 检查是否需要发送推送
                    should_push = True
                    if push_only_on_new:
                        # 如果设置了"仅新推文推送"，检查是否有新推文
                        if summary.get('total_saved', 0) == 0:
                            should_push = False
                            self.stdout.write('ℹ️ 跳过推送：无新推文')

                    # 发送推送
                    if should_push:
                        notification_service = TwitterNotificationService()
                        notification_service.send_notification(
                            title=push_title,
                            content=push_content
                        )
                        self.stdout.write('✅ 推送成功')
                    else:
                        self.stdout.write('ℹ️ 推送已跳过')

                except Exception as push_error:
                    self.stdout.write(self.style.WARNING(f'⚠️ 推送失败: {push_error}'))

                self.stdout.write('\n' + '=' * 60)
                self.stdout.write(self.style.SUCCESS('✨ 直接分析完成'))
                self.stdout.write('=' * 60)
                return

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'\n❌ AI分析失败: {e}'))
                raise

        # === 第二步：执行AI分析 ===
        if not collect_only:
            self.stdout.write('\n' + '=' * 60)
            self.stdout.write(self.style.SUCCESS('🔍 步骤 2: 执行分析'))
            self.stdout.write('=' * 60)

            # 获取待分析的推文
            # 所有分析都限制在指定的 --hours 时间窗口内
            if summary['total_saved'] > 0:
                # 有新推文：分析从 start_time 开始的所有推文
                tweets_to_analyze = Tweet.objects.filter(
                    twitter_list=twitter_list,
                    tweet_created_at__gte=start_time  # 使用 tweet_created_at 而不是 created_at
                ).order_by('-tweet_created_at')
                self.stdout.write(f'📊 分析模式: 新推文增量分析（限定 {hours} 小时窗口）')
            else:
                # 没有新推文：分析最近 N 小时内最多 200 条推文
                tweets_to_analyze = Tweet.objects.filter(
                    twitter_list=twitter_list,
                    tweet_created_at__gte=start_time  # 限定在时间窗口内
                ).order_by('-tweet_created_at')[:200]
                self.stdout.write(f'📊 分析模式: 历史数据分析（限定 {hours} 小时窗口，最多 200 条）')

            tweet_count = tweets_to_analyze.count()

            if tweet_count == 0:
                self.stdout.write(self.style.WARNING('\n⚠️ 没有待分析的推文'))
                return

            self.stdout.write(f'\n待分析推文数量: {tweet_count} 条')

            # 计算分析时间范围
            # 使用实际要分析的推文的时间范围，限制在指定窗口内
            if tweet_count > 0:
                # 先获取查询结果，再计算时间范围（避免切片查询的Django限制）
                tweet_list = list(tweets_to_analyze)
                earliest = min(tweet_list, key=lambda t: t.tweet_created_at)
                latest = max(tweet_list, key=lambda t: t.tweet_created_at)
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