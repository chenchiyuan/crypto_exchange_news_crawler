import json
import logging
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime
from django.conf import settings

from twitter.models import TwitterList, TwitterAnalysisResult, PromptTemplate
from twitter.services.orchestrator import TwitterAnalysisOrchestrator, CostLimitExceededError
from twitter.sdk.deepseek_sdk import DeepSeekAPIError


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '分析 Twitter List 推文内容并生成 AI 分析报告'

    def add_arguments(self, parser):
        # 位置参数
        parser.add_argument(
            'list_id',
            type=str,
            help='Twitter List ID'
        )

        # 时间范围参数
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='分析最近 N 小时的推文（默认 24）'
        )
        parser.add_argument(
            '--start-time',
            type=str,
            help='开始时间（ISO格式，如 2025-01-01T00:00:00+00:00）'
        )
        parser.add_argument(
            '--end-time',
            type=str,
            help='结束时间（ISO格式，如 2025-01-02T00:00:00+00:00）'
        )

        # Prompt 参数
        parser.add_argument(
            '--prompt',
            type=str,
            help='自定义 prompt 模板文件路径（默认使用预设的 crypto_analysis.txt）'
        )

        # 分析模式参数
        parser.add_argument(
            '--batch-mode',
            action='store_true',
            help='强制使用批次分析模式（默认自动判断：≥100条推文使用批次模式）'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='批次分析时每批推文数量（默认 100）'
        )

        # 成本控制参数
        parser.add_argument(
            '--max-cost',
            type=float,
            help=f'最大允许成本（美元，默认 ${getattr(settings, "MAX_COST_PER_ANALYSIS", 10.00)}）'
        )

        # 模式参数
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='试运行模式：仅估算成本和推文数量，不执行实际分析'
        )

        # 输出格式参数
        parser.add_argument(
            '--format',
            type=str,
            choices=['text', 'json'],
            default='text',
            help='输出格式（text=彩色摘要，json=完整JSON，默认 text）'
        )

    def handle(self, *args, **options):
        list_id = options['list_id']
        hours = options['hours']
        start_time_str = options.get('start_time')
        end_time_str = options.get('end_time')
        prompt_path = options.get('prompt')
        batch_mode = options.get('batch_mode')
        batch_size = options['batch_size']
        max_cost_value = options.get('max_cost')
        dry_run = options['dry_run']
        output_format = options['format']

        # 解析时间参数
        try:
            start_time, end_time = self._parse_time_range(
                hours, start_time_str, end_time_str
            )
        except ValueError as e:
            raise CommandError(str(e))

        # 加载 prompt 模板
        try:
            if prompt_path:
                # 使用自定义 prompt 文件
                prompt_template = self._load_custom_prompt(prompt_path)
                self.stdout.write(self.style.SUCCESS(f'✓ 使用自定义 Prompt: {prompt_path}'))
            else:
                # 自动选择合适的模板
                try:
                    template = PromptTemplate.get_template_for_list(list_id)
                    prompt_template = template.template_content
                    self.stdout.write(self.style.SUCCESS(
                        f'✓ 自动选择模板: {template.name} '
                        f'({template.get_analysis_type_display()})'
                    ))
                except PromptTemplate.DoesNotExist:
                    # 回退到默认模板
                    prompt_template = self._load_default_prompt()
                    self.stdout.write('✓ 使用默认 Prompt 模板: crypto_analysis.txt')
        except FileNotFoundError as e:
            raise CommandError(str(e))

        # 解析成本上限
        max_cost = Decimal(str(max_cost_value)) if max_cost_value else None

        # 显示配置
        self._print_header(list_id, start_time, end_time, batch_mode,
                          batch_size, max_cost, dry_run)

        # 获取 TwitterList
        try:
            twitter_list = TwitterList.objects.get(list_id=list_id)
            self.stdout.write(f'Twitter List: {twitter_list.name}')
        except TwitterList.DoesNotExist:
            raise CommandError(
                f'TwitterList {list_id} 不存在。\n'
                f'请先运行: python manage.py collect_twitter_list {list_id}'
            )

        # 执行分析
        try:
            orchestrator = TwitterAnalysisOrchestrator()

            task = orchestrator.run_analysis(
                twitter_list=twitter_list,
                start_time=start_time,
                end_time=end_time,
                prompt_template=prompt_template,
                max_cost=max_cost,
                batch_mode=batch_mode,
                batch_size=batch_size,
                dry_run=dry_run
            )

            # 输出结果
            if output_format == 'json':
                self._print_json_output(task)
            else:
                self._print_text_summary(task, dry_run)

        except ValueError as e:
            raise CommandError(f'参数错误: {str(e)}')
        except CostLimitExceededError as e:
            self.stdout.write(self.style.ERROR('=' * 60))
            self.stdout.write(self.style.ERROR('成本超限！'))
            self.stdout.write(self.style.ERROR('=' * 60))
            self.stdout.write(f'预估成本: ${e.estimated_cost:.4f}')
            self.stdout.write(f'允许上限: ${e.max_cost:.4f}')
            self.stdout.write(self.style.WARNING(
                '\n提示: 可以使用 --max-cost 参数调整上限，'
                '或缩小时间范围以减少推文数量'
            ))
            raise CommandError('分析取消')
        except DeepSeekAPIError as e:
            raise CommandError(f'AI API 调用失败: {str(e)}')
        except Exception as e:
            logger.exception("分析过程发生未知错误")
            raise CommandError(f'分析失败: {str(e)}')

    def _parse_time_range(self, hours, start_time_str, end_time_str):
        """解析时间范围参数"""
        if start_time_str and end_time_str:
            # 使用绝对时间
            start_time = parse_datetime(start_time_str)
            end_time = parse_datetime(end_time_str)

            if not start_time or not end_time:
                raise ValueError('时间格式错误，请使用 ISO 格式（如 2025-01-01T00:00:00+00:00）')

            if start_time >= end_time:
                raise ValueError('开始时间必须早于结束时间')

        else:
            # 使用相对时间
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=hours)

        # 验证时间范围（最多 30 天）
        time_delta = end_time - start_time
        if time_delta.days > 30:
            raise ValueError('时间范围不能超过 30 天')

        return start_time, end_time

    def _load_custom_prompt(self, prompt_path):
        """加载自定义 prompt 模板"""
        path = Path(prompt_path)

        if not path.is_absolute():
            path = Path(settings.BASE_DIR) / path

        if not path.exists():
            raise FileNotFoundError(f'Prompt 文件不存在: {prompt_path}')

        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def _load_default_prompt(self):
        """加载默认的 crypto_analysis.txt 模板"""
        default_path = Path('twitter/templates/prompts/crypto_analysis.txt')

        if not default_path.is_absolute():
            default_path = Path(settings.BASE_DIR) / default_path

        if not default_path.exists():
            raise FileNotFoundError('默认模板文件不存在')

        with open(default_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _print_header(self, list_id, start_time, end_time, batch_mode,
                     batch_size, max_cost, dry_run):
        """打印配置信息头部"""
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Twitter List AI 分析'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'List ID: {list_id}')
        self.stdout.write(f'时间范围: {start_time} ~ {end_time}')

        if batch_mode:
            self.stdout.write(f'分析模式: 批次模式（每批 {batch_size} 条）')
        else:
            self.stdout.write(f'分析模式: 自动判断（批次大小 {batch_size}）')

        if max_cost:
            self.stdout.write(f'成本上限: ${max_cost:.2f}')
        else:
            default_max = getattr(settings, 'MAX_COST_PER_ANALYSIS', Decimal('10.00'))
            self.stdout.write(f'成本上限: ${default_max:.2f} (默认)')

        if dry_run:
            self.stdout.write(self.style.WARNING('模式: 试运行 (仅估算，不执行分析)'))
        else:
            self.stdout.write('模式: 正常执行')

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')

    def _print_text_summary(self, task: TwitterAnalysisResult, dry_run: bool):
        """打印文本格式的分析摘要"""
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))

        if dry_run:
            self.stdout.write(self.style.SUCCESS('试运行完成'))
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write(f'推文数量: {task.tweet_count}')
            self.stdout.write(self.style.WARNING('(未执行实际分析)'))
            return

        self.stdout.write(self.style.SUCCESS('分析完成'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        # 基本信息
        self.stdout.write(f'任务 ID: {task.task_id}')
        self.stdout.write(f'推文数量: {task.tweet_count}')
        self.stdout.write(f'实际成本: ${task.cost_amount:.4f}')
        self.stdout.write(f'处理时长: {task.processing_time:.2f} 秒')
        self.stdout.write('')

        # 分析结果
        if task.analysis_result:
            result = task.analysis_result

            # 情绪分析
            sentiment = result.get('sentiment', {})
            if sentiment:
                self.stdout.write(self.style.SUCCESS('【市场情绪】'))
                self.stdout.write(f'  多头: {sentiment.get("bullish", 0)} 条 '
                                f'({sentiment.get("bullish_percentage", 0):.1f}%)')
                self.stdout.write(f'  空头: {sentiment.get("bearish", 0)} 条 '
                                f'({sentiment.get("bearish_percentage", 0):.1f}%)')
                self.stdout.write(f'  中性: {sentiment.get("neutral", 0)} 条 '
                                f'({sentiment.get("neutral_percentage", 0):.1f}%)')
                self.stdout.write('')

            # 关键话题
            topics = result.get('key_topics', [])
            if topics:
                self.stdout.write(self.style.SUCCESS('【关键话题】'))
                for i, topic in enumerate(topics[:5], 1):
                    sentiment_icon = {
                        'bullish': '📈',
                        'bearish': '📉',
                        'neutral': '➖'
                    }.get(topic.get('sentiment', 'neutral'), '➖')
                    self.stdout.write(
                        f'  {i}. {topic["topic"]} '
                        f'({topic["count"]} 次) {sentiment_icon}'
                    )
                self.stdout.write('')

            # 重要推文
            important_tweets = result.get('important_tweets', [])
            if important_tweets:
                self.stdout.write(self.style.SUCCESS('【重要推文】'))
                for i, tweet in enumerate(important_tweets[:3], 1):
                    self.stdout.write(
                        f'  {i}. @{tweet.get("screen_name", "unknown")} '
                        f'(互动: {tweet.get("engagement", 0)})'
                    )
                    content = tweet.get('content', '')[:80]
                    self.stdout.write(f'     {content}...')
                    self.stdout.write(f'     原因: {tweet.get("reason", "N/A")}')
                self.stdout.write('')

            # 市场总结
            summary = result.get('market_summary', '')
            if summary:
                self.stdout.write(self.style.SUCCESS('【市场总结】'))
                self.stdout.write(f'  {summary}')
                self.stdout.write('')

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'\n查询完整结果: python manage.py query_analysis_task {task.task_id} --result')

    def _print_json_output(self, task: TwitterAnalysisResult):
        """打印 JSON 格式的完整输出"""
        output = {
            'task_id': str(task.task_id),
            'status': task.status,
            'twitter_list_id': task.twitter_list.list_id,
            'tweet_count': task.tweet_count,
            'cost_amount': float(task.cost_amount),
            'processing_time': task.processing_time,
            'analysis_result': task.analysis_result,
            'created_at': task.created_at.isoformat(),
            'updated_at': task.updated_at.isoformat(),
        }

        if task.error_message:
            output['error_message'] = task.error_message

        self.stdout.write(json.dumps(output, ensure_ascii=False, indent=2))
