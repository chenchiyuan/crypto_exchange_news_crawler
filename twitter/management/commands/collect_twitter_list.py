import logging
from datetime import datetime, timedelta, timezone
from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from twitter.models import TwitterList
from twitter.services.twitter_list_service import TwitterListService


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '从指定 Twitter List 收集推文并存储到数据库'

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
            help='获取最近 N 小时的推文（默认 24）'
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

        # 批次参数
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='每批获取的推文数量（50-1000，默认 500）'
        )

        # 模式参数
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='试运行模式：只获取不保存到数据库'
        )

    def handle(self, *args, **options):
        list_id = options['list_id']
        hours = options['hours']
        start_time_str = options.get('start_time')
        end_time_str = options.get('end_time')
        batch_size = options['batch_size']
        dry_run = options['dry_run']

        # 解析时间参数
        try:
            start_time, end_time = self._parse_time_range(
                hours, start_time_str, end_time_str
            )
        except ValueError as e:
            raise CommandError(str(e))

        # 验证批次大小
        if not 50 <= batch_size <= 1000:
            raise CommandError('batch-size 必须在 50-1000 之间')

        # 显示配置
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS(f'Twitter List 推文收集'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'List ID: {list_id}')
        self.stdout.write(f'时间范围: {start_time} ~ {end_time}')
        self.stdout.write(f'批次大小: {batch_size}')
        self.stdout.write(f'模式: {"试运行 (不保存)" if dry_run else "正常"}')
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
                    f'创建新 TwitterList: {twitter_list.name}'
                ))
            else:
                self.stdout.write(f'使用现有 TwitterList: {twitter_list.name}')

        except Exception as e:
            raise CommandError(f'获取 TwitterList 失败: {e}')

        # 执行收集
        try:
            service = TwitterListService(twitter_list)

            self.stdout.write('\n开始收集推文...')

            # 执行收集并保存
            summary = service.collect_and_save_tweets(
                start_time=start_time,
                end_time=end_time,
                batch_size=batch_size,
                dry_run=dry_run
            )

            # 显示摘要
            self._display_summary(summary, dry_run)

            # 关闭服务
            service.close()

        except Exception as e:
            logger.exception(f'收集推文失败: {e}')
            raise CommandError(f'收集推文失败: {e}')

    def _parse_time_range(self, hours, start_time_str, end_time_str):
        """
        解析时间范围参数

        Args:
            hours: 小时数（相对时间）
            start_time_str: 开始时间字符串（绝对时间）
            end_time_str: 结束时间字符串（绝对时间）

        Returns:
            tuple: (start_time, end_time)

        Raises:
            ValueError: 参数无效
        """
        now = datetime.now(timezone.utc)

        # 优先使用绝对时间
        if start_time_str and end_time_str:
            start_time = parse_datetime(start_time_str)
            end_time = parse_datetime(end_time_str)

            if not start_time or not end_time:
                raise ValueError('时间格式无效，请使用 ISO 格式（如 2025-01-01T00:00:00+00:00）')

            # 确保时区感知
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)

            if start_time >= end_time:
                raise ValueError('start-time 必须早于 end-time')

            # 检查时间范围限制（7天）
            time_diff = end_time - start_time
            if time_diff.days > 7:
                raise ValueError('时间范围不能超过 7 天')

            return start_time, end_time

        # 使用相对时间（hours 参数）
        else:
            if hours <= 0:
                raise ValueError('hours 必须大于 0')
            if hours > 168:  # 7天
                raise ValueError('hours 不能超过 168（7天）')

            end_time = now
            start_time = now - timedelta(hours=hours)

            return start_time, end_time

    def _display_summary(self, summary, dry_run):
        """显示执行摘要"""
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('执行摘要'))
        self.stdout.write('=' * 60)

        self.stdout.write(f'List ID: {summary["list_id"]}')
        self.stdout.write(f'List 名称: {summary["list_name"]}')
        self.stdout.write(f'处理批次数: {summary["batches_processed"]}')
        self.stdout.write(f'总获取推文数: {summary["total_fetched"]}')

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(
                f'新保存推文数: {summary["total_saved"]}'
            ))
            self.stdout.write(self.style.WARNING(
                f'重复推文数: {summary["total_duplicates"]}'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                '试运行模式：未保存到数据库'
            ))

        self.stdout.write('=' * 60)

        # 成功提示
        if not dry_run and summary["total_saved"] > 0:
            self.stdout.write(self.style.SUCCESS(
                f'\n✓ 成功保存 {summary["total_saved"]} 条推文！'
            ))
        elif dry_run:
            self.stdout.write(self.style.WARNING(
                f'\n✓ 试运行完成！预计可获取 {summary["total_fetched"]} 条推文'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                '\n! 未发现新推文'
            ))
