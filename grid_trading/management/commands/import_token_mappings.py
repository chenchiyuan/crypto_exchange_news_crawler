"""导入token映射关系到TokenMapping表

用途:
    从CSV文件导入币安symbol到CoinGecko ID的映射关系

使用方法:
    python manage.py import_token_mappings [--input path/to/token.csv] [--clear]
"""
import csv
import logging
from django.core.management.base import BaseCommand
from django.db import transaction

from grid_trading.models import TokenMapping


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '从CSV文件导入token映射关系到TokenMapping表'

    def add_arguments(self, parser):
        parser.add_argument(
            '--input',
            type=str,
            default='data/token.csv',
            help='输入CSV文件路径（默认: data/token.csv）'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='导入前清空现有数据'
        )

    def handle(self, *args, **options):
        input_file = options['input']
        clear_existing = options['clear']

        self.stdout.write('=' * 80)
        self.stdout.write('导入Token映射关系')
        self.stdout.write('=' * 80)

        # 如果需要清空现有数据
        if clear_existing:
            existing_count = TokenMapping.objects.count()
            if existing_count > 0:
                self.stdout.write(f'\n清空现有数据: {existing_count} 条记录')
                TokenMapping.objects.all().delete()
                self.stdout.write(self.style.WARNING('✓ 已清空'))

        # 读取CSV文件
        self.stdout.write(f'\n读取文件: {input_file}')

        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'✗ 文件不存在: {input_file}'))
            return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ 读取文件失败: {e}'))
            return

        self.stdout.write(self.style.SUCCESS(f'✓ 成功读取 {len(rows)} 行数据'))

        # 统计信息
        stats = {
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'error': 0,
        }

        # 逐行导入
        self.stdout.write('\n开始导入...')
        for i, row in enumerate(rows, 1):
            binance_symbol = row['binance_symbol']
            base_asset = row['base_asset']
            coingecko_id = row['coingecko_id']
            coingecko_symbol = row['coingecko_symbol']
            coingecko_name = row['coingecko_name']

            # 跳过空映射（CoinGecko ID为空）
            if not coingecko_id or not coingecko_id.strip():
                self.stdout.write(f'  [{i:3d}] ⊘ {binance_symbol:20s} - CoinGecko ID为空，跳过')
                stats['skipped'] += 1
                continue

            try:
                with transaction.atomic():
                    # 使用update_or_create确保幂等性
                    mapping, created = TokenMapping.objects.update_or_create(
                        symbol=binance_symbol,
                        defaults={
                            'base_token': base_asset,
                            'coingecko_id': coingecko_id,
                            'match_status': TokenMapping.MatchStatus.AUTO_MATCHED,
                            'alternatives': None,  # CSV中没有alternatives信息
                        }
                    )

                    if created:
                        stats['created'] += 1
                        status_icon = '✓'
                        status_text = '新增'
                    else:
                        stats['updated'] += 1
                        status_icon = '↻'
                        status_text = '更新'

                    # 每10条显示一次进度
                    if i % 10 == 0 or created:
                        self.stdout.write(
                            f'  [{i:3d}] {status_icon} {binance_symbol:20s} '
                            f'→ {coingecko_id:30s} ({status_text})'
                        )

            except Exception as e:
                stats['error'] += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'  [{i:3d}] ✗ {binance_symbol:20s} - 导入失败: {e}'
                    )
                )
                logger.exception(f'Failed to import {binance_symbol}')

        # 最终统计
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('✓ 导入完成'))
        self.stdout.write('=' * 80)

        total = len(rows)
        self.stdout.write(f'\n总计: {total} 行数据')
        self.stdout.write(f'  - 新增: {stats["created"]} ({stats["created"]/total*100:.1f}%)')
        self.stdout.write(f'  - 更新: {stats["updated"]} ({stats["updated"]/total*100:.1f}%)')
        self.stdout.write(f'  - 跳过: {stats["skipped"]} ({stats["skipped"]/total*100:.1f}%)')
        if stats['error'] > 0:
            self.stdout.write(self.style.ERROR(f'  - 错误: {stats["error"]} ({stats["error"]/total*100:.1f}%)'))

        # 显示数据库统计
        db_count = TokenMapping.objects.count()
        self.stdout.write(f'\n数据库当前记录数: {db_count}')

        # 显示一些示例
        self.stdout.write('\n前5个映射示例:')
        for mapping in TokenMapping.objects.all()[:5]:
            self.stdout.write(
                f'  - {mapping.symbol:20s} ({mapping.base_token:10s}) '
                f'→ {mapping.coingecko_id:30s} [{mapping.match_status}]'
            )
