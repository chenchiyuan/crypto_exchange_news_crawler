"""
批量市场数据更新命令
Batch Market Data Update Command

整合多个周期的K线数据更新任务，替代update_market_data.sh脚本
使用Django management command实现，便于维护和扩展
"""
import sys
import logging
from datetime import datetime
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone

logger = logging.getLogger("grid_trading")


class Command(BaseCommand):
    help = '批量更新不同周期的K线数据缓存'

    def add_arguments(self, parser):
        parser.add_argument(
            '--min-volume',
            type=str,
            help='最小成交量过滤(如: 50M, 100M)'
        )
        parser.add_argument(
            '--skip-task',
            type=str,
            action='append',
            help='跳过指定任务(可多次使用): 4h, 1m, 1h, 1d'
        )
        parser.add_argument(
            '--only-task',
            type=str,
            help='只执行指定任务: 4h, 1m, 1h, 1d'
        )

    def handle(self, *args, **options):
        """
        主执行函数

        工作流程:
        1. 显示脚本信息
        2. 执行多个更新任务
        3. 显示缓存统计
        4. 输出执行总结
        """
        start_time = timezone.now()

        self.stdout.write('=' * 70)
        self.stdout.write(
            self.style.SUCCESS('市场数据批量更新脚本')
        )
        self.stdout.write(f'开始时间: {start_time.strftime("%Y-%m-%d %H:%M:%S")}')
        self.stdout.write('=' * 70)
        self.stdout.write('')

        # 获取参数
        min_volume = options.get('min_volume')
        skip_tasks = set(options.get('skip_task') or [])
        only_task = options.get('only_task')

        if min_volume:
            self.stdout.write(f'✓ 启用成交量过滤: {min_volume}')
            self.stdout.write('')

        # 定义更新任务列表
        tasks = [
            {
                'name': '4h K线',
                'key': '4h',
                'params': ['--warmup-klines', '--interval', '4h', '--limit', '300']
            },
            {
                'name': '1分钟K线',
                'key': '1m',
                'params': ['--warmup-klines', '--interval', '1m', '--limit', '1000']
            },
            {
                'name': '1小时K线',
                'key': '1h',
                'params': ['--warmup-klines', '--interval', '1h', '--limit', '200']
            },
            {
                'name': '日线K线',
                'key': '1d',
                'params': ['--warmup-klines', '--interval', '1d', '--limit', '50']
            },
        ]

        # 过滤任务
        if only_task:
            tasks = [t for t in tasks if t['key'] == only_task]
            if not tasks:
                self.stdout.write(
                    self.style.ERROR(f'✗ 无效的任务标识: {only_task}')
                )
                sys.exit(1)
        elif skip_tasks:
            tasks = [t for t in tasks if t['key'] not in skip_tasks]

        # 统计变量
        total_tasks = len(tasks)
        success_count = 0
        failed_count = 0
        failed_tasks = []

        self.stdout.write(
            self.style.SUCCESS(f'开始执行 {total_tasks} 个更新任务...\n')
        )

        # 执行每个任务
        for idx, task in enumerate(tasks, 1):
            self.stdout.write('=' * 70)
            self.stdout.write(
                self.style.SUCCESS(f'[{idx}/{total_tasks}] 更新 {task["name"]}')
            )
            self.stdout.write('=' * 70)

            # 构建命令参数
            cmd_args = task['params'].copy()
            if min_volume:
                cmd_args.extend(['--min-volume', min_volume])

            self.stdout.write(
                f'执行命令: update_market_data {" ".join(cmd_args)}\n'
            )

            # 执行命令
            task_start = datetime.now()
            try:
                call_command('update_market_data', *cmd_args)

                task_duration = (datetime.now() - task_start).total_seconds()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n✓ [{idx}/{total_tasks}] {task["name"]} 更新完成 '
                        f'(耗时: {task_duration:.1f}秒)\n'
                    )
                )
                success_count += 1

            except Exception as e:
                task_duration = (datetime.now() - task_start).total_seconds()
                self.stdout.write(
                    self.style.ERROR(
                        f'\n✗ [{idx}/{total_tasks}] {task["name"]} 更新失败 '
                        f'(耗时: {task_duration:.1f}秒)'
                    )
                )
                self.stdout.write(
                    self.style.ERROR(f'错误信息: {str(e)}\n')
                )
                logger.error(f'{task["name"]}更新失败: {e}', exc_info=True)
                failed_count += 1
                failed_tasks.append(task['name'])

        # 显示缓存统计
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS('K线缓存统计'))
        self.stdout.write('=' * 70)

        try:
            call_command('cache_stats')
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'⚠️ 缓存统计命令不存在或执行失败: {e}')
            )

        self.stdout.write('')

        # 计算总耗时
        end_time = timezone.now()
        total_duration = (end_time - start_time).total_seconds()
        minutes = int(total_duration // 60)
        seconds = int(total_duration % 60)

        # 输出执行总结
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS('执行总结'))
        self.stdout.write('=' * 70)
        self.stdout.write(f'总任务数: {total_tasks}')
        self.stdout.write(
            self.style.SUCCESS(f'成功任务: {success_count}')
        )

        if failed_count > 0:
            self.stdout.write(
                self.style.ERROR(f'失败任务: {failed_count}')
            )
            self.stdout.write(self.style.ERROR('失败列表:'))
            for failed_task in failed_tasks:
                self.stdout.write(f'  ✗ {failed_task}')
        else:
            self.stdout.write(
                self.style.SUCCESS('失败任务: 0')
            )

        self.stdout.write(f'总耗时: {minutes}分{seconds}秒')
        self.stdout.write(f'结束时间: {end_time.strftime("%Y-%m-%d %H:%M:%S")}')
        self.stdout.write('=' * 70)

        # 根据结果显示建议
        if failed_count == 0:
            self.stdout.write('')
            self.stdout.write(
                self.style.SUCCESS('✅ 所有更新任务执行成功！')
            )
            self.stdout.write('')
            self.stdout.write('💡 下一步: 运行筛选命令')
            self.stdout.write(
                '   python manage.py screen_simple --min-volume 100000000 --top-n 20'
            )
            self.stdout.write('')
        else:
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING('⚠️ 部分任务执行失败，请检查错误信息')
            )
            self.stdout.write('')
            sys.exit(1)
