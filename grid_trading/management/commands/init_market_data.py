"""
市值/FDV数据初始化命令 - Feature 008

用途: 生产环境首次部署或数据重置时，初始化Token映射和市值数据

使用方法:
    python manage.py init_market_data              # 增量导入（默认）
    python manage.py init_market_data --reset      # 清空后重新导入
    python manage.py init_market_data --dry-run    # 测试模式

执行步骤:
    1. 检查环境（API Key、数据文件）
    2. 导入Token映射关系（355个）
    3. 更新市值/FDV数据（从CoinGecko）
    4. 验证数据完整性并生成报告

注意事项:
    - 确保 COINGECKO_API_KEY 已配置
    - 确保 data/token_mappings_initial.csv 存在
    - 更新过程需要2-3分钟（API限流）
"""
import csv
import logging
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from grid_trading.models import TokenMapping, MarketData, UpdateLog
from grid_trading.services.coingecko_client import CoingeckoClient

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '初始化市值/FDV数据（导入Token映射 + 更新市值数据）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--input',
            type=str,
            default='data/token_mappings_initial.csv',
            help='Token映射CSV文件路径（默认: data/token_mappings_initial.csv）'
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='清空现有TokenMapping数据后重新导入（慎用！）'
        )
        parser.add_argument(
            '--skip-update',
            action='store_true',
            help='只导入映射，跳过市值数据更新'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='测试模式：不实际写入数据库'
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.reset = options['reset']
        self.skip_update = options['skip_update']
        self.input_file = options['input']

        # 显示标题
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('  市值/FDV数据初始化 - Feature 008'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')

        if self.dry_run:
            self.stdout.write(self.style.WARNING('【测试模式】不会实际写入数据'))
            self.stdout.write('')

        try:
            # 步骤1: 环境检查
            self.stdout.write(self.style.HTTP_INFO('步骤 1/4: 环境检查'))
            self._check_environment()
            self.stdout.write(self.style.SUCCESS('✓ 环境检查通过'))
            self.stdout.write('')

            # 步骤2: 导入Token映射
            self.stdout.write(self.style.HTTP_INFO('步骤 2/4: 导入Token映射'))
            mapping_stats = self._import_mappings()
            self.stdout.write(self.style.SUCCESS(f'✓ 导入完成: {mapping_stats}'))
            self.stdout.write('')

            # 步骤3: 更新市值数据
            if not self.skip_update:
                self.stdout.write(self.style.HTTP_INFO('步骤 3/4: 更新市值数据'))
                self.stdout.write('预计耗时: 2-3分钟（355个代币，分4批次）')
                update_stats = self._update_market_data()
                self.stdout.write(self.style.SUCCESS(f'✓ 更新完成: {update_stats}'))
            else:
                self.stdout.write(self.style.WARNING('步骤 3/4: 跳过市值数据更新'))
            self.stdout.write('')

            # 步骤4: 验证数据
            self.stdout.write(self.style.HTTP_INFO('步骤 4/4: 验证数据'))
            self._verify_data()
            self.stdout.write('')

            # 完成
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write(self.style.SUCCESS('  ✓ 初始化成功完成！'))
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write('')
            self.stdout.write('下一步:')
            self.stdout.write('  1. 访问 /screening/daily/ 页面查看FDV列')
            self.stdout.write('  2. 配置定期更新: python manage.py update_market_data_scheduled')
            self.stdout.write('')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ 初始化失败: {e}'))
            raise CommandError(f'初始化失败: {e}')

    def _check_environment(self):
        """检查环境配置"""
        # 检查API Key
        api_key = getattr(settings, 'COINGECKO_API_KEY', None)
        if not api_key:
            raise CommandError('CoinGecko API Key未配置，请在settings.py或.env中设置COINGECKO_API_KEY')
        self.stdout.write(f'  ✓ API Key: {api_key[:10]}...')

        # 检查CSV文件
        if not os.path.exists(self.input_file):
            raise CommandError(f'Token映射文件不存在: {self.input_file}')
        self.stdout.write(f'  ✓ 数据文件: {self.input_file}')

        # 检查数据库连接
        from django.db import connection
        connection.ensure_connection()
        self.stdout.write('  ✓ 数据库连接正常')

    def _import_mappings(self):
        """导入Token映射关系"""
        if self.reset and not self.dry_run:
            existing_count = TokenMapping.objects.count()
            if existing_count > 0:
                self.stdout.write(self.style.WARNING(f'  警告: 将删除现有 {existing_count} 条映射'))
                TokenMapping.objects.all().delete()
                self.stdout.write('  ✓ 已清空现有数据')

        # 读取CSV
        with open(self.input_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.stdout.write(f'  读取到 {len(rows)} 条映射关系')

        stats = {'created': 0, 'updated': 0, 'skipped': 0, 'error': 0}

        for i, row in enumerate(rows, 1):
            if not row['coingecko_id'] or not row['coingecko_id'].strip():
                stats['skipped'] += 1
                continue

            try:
                if not self.dry_run:
                    with transaction.atomic():
                        mapping, created = TokenMapping.objects.update_or_create(
                            symbol=row['binance_symbol'],
                            defaults={
                                'base_token': row['base_asset'],
                                'coingecko_id': row['coingecko_id'],
                                'match_status': TokenMapping.MatchStatus.AUTO_MATCHED,
                            }
                        )
                    if created:
                        stats['created'] += 1
                    else:
                        stats['updated'] += 1
                else:
                    stats['created'] += 1

                # 每50条显示进度
                if i % 50 == 0:
                    self.stdout.write(f'  进度: {i}/{len(rows)}', ending='\r')

            except Exception as e:
                stats['error'] += 1
                logger.error(f"Failed to import {row['binance_symbol']}: {e}")

        return f"创建 {stats['created']}, 更新 {stats['updated']}, 跳过 {stats['skipped']}, 错误 {stats['error']}"

    def _update_market_data(self):
        """更新市值/FDV数据"""
        if self.dry_run:
            return "测试模式：跳过实际更新"

        # 获取所有有效映射
        mappings = list(TokenMapping.objects.exclude(
            coingecko_id__isnull=True
        ).exclude(
            coingecko_id=''
        ).order_by('symbol'))

        total = len(mappings)
        self.stdout.write(f'  需要更新 {total} 个代币')

        # 创建批次日志
        batch_id, _ = UpdateLog.log_batch_start(
            operation_type=UpdateLog.OperationType.MARKET_DATA_UPDATE,
            metadata={'total_coins': total, 'source': 'init_command'}
        )

        # 初始化CoinGecko客户端
        client = CoingeckoClient()
        batch_size = client.BATCH_SIZE

        success_count = 0
        failed_count = 0

        # 分批处理
        total_batches = (total + batch_size - 1) // batch_size

        for batch_num in range(1, total_batches + 1):
            batch_start = (batch_num - 1) * batch_size
            batch_end = min(batch_start + batch_size, total)
            batch_mappings = mappings[batch_start:batch_end]

            self.stdout.write(f'  批次 {batch_num}/{total_batches}: 处理 {len(batch_mappings)} 个代币', ending='\r')

            # 获取CoinGecko IDs
            coingecko_ids = [m.coingecko_id for m in batch_mappings]

            try:
                # 获取市值数据
                market_data_list = client.fetch_market_data(coingecko_ids=coingecko_ids)
                market_data_dict = {item['id']: item for item in market_data_list}

                # 更新每个symbol
                for mapping in batch_mappings:
                    market_info = market_data_dict.get(mapping.coingecko_id)

                    if market_info:
                        with transaction.atomic():
                            MarketData.objects.update_or_create(
                                symbol=mapping.symbol,
                                defaults={
                                    'market_cap': market_info.get('market_cap'),
                                    'fully_diluted_valuation': market_info.get('fully_diluted_valuation'),
                                    'data_source': 'coingecko',
                                    'fetched_at': timezone.now(),
                                }
                            )
                        success_count += 1
                    else:
                        failed_count += 1

            except Exception as e:
                logger.error(f"Batch {batch_num} failed: {e}")
                failed_count += len(batch_mappings)

            # 批次间延迟
            if batch_num < total_batches:
                import time
                time.sleep(client.BATCH_DELAY)

        # 记录批次完成
        UpdateLog.log_batch_complete(
            batch_id=batch_id,
            status=UpdateLog.Status.SUCCESS if failed_count == 0 else UpdateLog.Status.PARTIAL_SUCCESS,
            metadata={
                'success_count': success_count,
                'failed_count': failed_count,
                'total': total
            }
        )

        return f"成功 {success_count}, 失败 {failed_count}, 总计 {total}"

    def _verify_data(self):
        """验证数据完整性"""
        mapping_count = TokenMapping.objects.count()
        market_data_count = MarketData.objects.count()
        coverage = (market_data_count / mapping_count * 100) if mapping_count > 0 else 0

        self.stdout.write(f'  TokenMapping记录数: {mapping_count}')
        self.stdout.write(f'  MarketData记录数: {market_data_count}')
        self.stdout.write(f'  数据覆盖率: {coverage:.1f}%')

        if coverage < 90:
            self.stdout.write(self.style.WARNING(f'  ⚠ 数据覆盖率低于90%'))
        else:
            self.stdout.write(self.style.SUCCESS(f'  ✓ 数据覆盖率正常'))
