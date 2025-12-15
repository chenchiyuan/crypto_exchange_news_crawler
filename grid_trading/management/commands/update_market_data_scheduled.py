"""
市值/FDV数据定期更新命令 - Feature 008

用途: 定期更新所有Token的市值和FDV数据（适合配置到crontab）

使用方法:
    python manage.py update_market_data_scheduled              # 正常更新
    python manage.py update_market_data_scheduled --quiet      # 静默模式（适合cron）
    python manage.py update_market_data_scheduled --dry-run    # 测试模式

推荐配置到crontab:
    # 每天凌晨4点更新
    0 4 * * * cd /path/to/project && python manage.py update_market_data_scheduled --quiet >> logs/market_data.log 2>&1

    # 每12小时更新一次
    0 */12 * * * cd /path/to/project && python manage.py update_market_data_scheduled --quiet >> logs/market_data.log 2>&1

执行内容:
    1. 环境检查（数据库、API Key）
    2. 更新市值/FDV数据
    3. 生成统计报告
    4. 清理旧日志（30天前）
"""
import logging
import time
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from grid_trading.models import TokenMapping, MarketData, UpdateLog
from grid_trading.services.coingecko_client import CoingeckoClient

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '定期更新市值/FDV数据（适合配置到cron）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='静默模式：只输出关键信息和错误（适合cron）'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='测试模式：不实际更新数据'
        )
        parser.add_argument(
            '--cleanup-days',
            type=int,
            default=30,
            help='清理N天前的UpdateLog（默认30天）'
        )

    def handle(self, *args, **options):
        self.quiet = options['quiet']
        self.dry_run = options['dry_run']
        self.cleanup_days = options['cleanup_days']
        
        self.start_time = timezone.now()

        # 显示标题
        if not self.quiet:
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write(self.style.SUCCESS('  市值/FDV数据定期更新'))
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write(f'开始时间: {self.start_time.strftime("%Y-%m-%d %H:%M:%S")}')
            self.stdout.write('')

        if self.dry_run:
            self.info('【测试模式】不会实际写入数据')

        try:
            # 1. 环境检查
            self.info('步骤 1/5: 环境检查')
            self._check_environment()
            self.success('✓ 环境检查通过')

            # 2. 获取更新前统计
            self.info('步骤 2/5: 获取当前统计')
            before_stats = self._get_stats()

            # 3. 执行更新
            self.info('步骤 3/5: 执行更新')
            update_stats = self._run_update()
            self.success(f'✓ 更新完成: {update_stats}')

            # 4. 生成报告
            self.info('步骤 4/5: 生成报告')
            self._generate_report(before_stats)

            # 5. 清理旧日志
            self.info('步骤 5/5: 清理旧日志')
            self._cleanup_old_logs()

            # 完成
            end_time = timezone.now()
            duration = (end_time - self.start_time).total_seconds()

            if not self.quiet:
                self.stdout.write('')
                self.stdout.write(f'完成时间: {end_time.strftime("%Y-%m-%d %H:%M:%S")}')
                self.stdout.write(f'总耗时: {duration:.1f}秒')
                self.stdout.write(self.style.SUCCESS('=' * 60))

        except Exception as e:
            self.error(f'更新失败: {e}')
            raise CommandError(f'更新失败: {e}')

    def info(self, message):
        """普通信息输出"""
        if not self.quiet:
            self.stdout.write(message)
        logger.info(message)

    def success(self, message):
        """成功信息输出"""
        if not self.quiet:
            self.stdout.write(self.style.SUCCESS(message))
        logger.info(message)

    def warning(self, message):
        """警告信息输出"""
        self.stdout.write(self.style.WARNING(message))
        logger.warning(message)

    def error(self, message):
        """错误信息输出"""
        self.stdout.write(self.style.ERROR(message))
        logger.error(message)

    def _check_environment(self):
        """检查环境配置"""
        # 检查API Key
        api_key = getattr(settings, 'COINGECKO_API_KEY', None)
        if not api_key:
            raise CommandError('CoinGecko API Key未配置')

        # 检查数据库连接
        from django.db import connection
        connection.ensure_connection()

        if not self.quiet:
            self.stdout.write('  ✓ API Key已配置')
            self.stdout.write('  ✓ 数据库连接正常')

    def _get_stats(self):
        """获取当前统计数据"""
        mapping_count = TokenMapping.objects.count()
        market_data_count = MarketData.objects.count()

        # 24小时内更新过的数据
        recent_count = MarketData.objects.filter(
            fetched_at__gte=timezone.now() - timedelta(hours=24)
        ).count()

        if not self.quiet:
            self.stdout.write(f'  Token映射数: {mapping_count}')
            self.stdout.write(f'  市值数据数: {market_data_count}')
            self.stdout.write(f'  24h内更新: {recent_count}')

        return {
            'mapping_count': mapping_count,
            'market_data_count': market_data_count,
            'recent_count': recent_count
        }

    def _run_update(self):
        """执行市值数据更新"""
        if self.dry_run:
            return "测试模式：跳过实际更新"

        # 获取所有有效映射
        mappings = list(TokenMapping.objects.exclude(
            coingecko_id__isnull=True
        ).exclude(
            coingecko_id=''
        ).order_by('symbol'))

        total = len(mappings)
        
        if not self.quiet:
            self.stdout.write(f'  需要更新 {total} 个代币')

        # 创建批次日志
        batch_id, _ = UpdateLog.log_batch_start(
            operation_type=UpdateLog.OperationType.MARKET_DATA_UPDATE,
            metadata={'total_coins': total, 'source': 'scheduled_command'}
        )

        # 初始化客户端
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

            if not self.quiet:
                self.stdout.write(f'  批次 {batch_num}/{total_batches}...', ending='\r')

            # 获取CoinGecko IDs
            coingecko_ids = [m.coingecko_id for m in batch_mappings]

            try:
                # 获取市值数据
                market_data_list = client.fetch_market_data(coingecko_ids=coingecko_ids)
                market_data_dict = {item['id']: item for item in market_data_list}

                # 更新数据
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
                        logger.warning(f"No data for {mapping.symbol} ({mapping.coingecko_id})")

            except Exception as e:
                logger.error(f"Batch {batch_num} failed: {e}")
                failed_count += len(batch_mappings)

            # 批次间延迟
            if batch_num < total_batches:
                time.sleep(client.BATCH_DELAY)

        # 记录批次完成
        UpdateLog.log_batch_complete(
            batch_id=batch_id,
            operation_type=UpdateLog.OperationType.MARKET_DATA_UPDATE,
            status=UpdateLog.Status.SUCCESS if failed_count == 0 else UpdateLog.Status.PARTIAL_SUCCESS,
            metadata={
                'success_count': success_count,
                'failed_count': failed_count,
                'total': total
            }
        )

        return f"成功 {success_count}, 失败 {failed_count}, 总计 {total}"

    def _generate_report(self, before_stats):
        """生成更新报告"""
        # 获取更新后统计
        mapping_count = TokenMapping.objects.count()
        market_data_count = MarketData.objects.count()
        coverage = (market_data_count / mapping_count * 100) if mapping_count > 0 else 0

        # 本次更新的数据
        updated_count = MarketData.objects.filter(
            fetched_at__gte=self.start_time
        ).count()

        # 获取最新批次的失败数
        latest_batch = UpdateLog.objects.filter(
            operation_type='market_data_update'
        ).order_by('-executed_at').first()

        failed_count = 0
        if latest_batch:
            failed_count = UpdateLog.objects.filter(
                batch_id=latest_batch.batch_id,
                status='failed'
            ).count()

        # 输出报告
        if not self.quiet:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'))
            self.stdout.write(self.style.SUCCESS('  更新报告'))
            self.stdout.write(self.style.SUCCESS('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'))
            self.stdout.write('')
            self.stdout.write(f'Token映射数: {mapping_count}')
            self.stdout.write(f'市值数据数: {market_data_count}')
            self.stdout.write(f'数据覆盖率: {coverage:.1f}%')
            self.stdout.write('')
            self.stdout.write(f'本次更新:')
            self.stdout.write(f'  - 更新成功: {updated_count} 个')
            self.stdout.write(f'  - 更新失败: {failed_count} 个')
            self.stdout.write('')

        # 检查并发出警告
        if coverage < 90:
            self.warning(f'⚠ 数据覆盖率低于90%: {coverage:.1f}%')

        if failed_count > 50:
            self.warning(f'⚠ 失败数量较多: {failed_count}')

    def _cleanup_old_logs(self):
        """清理旧的UpdateLog"""
        if self.dry_run:
            return

        cutoff_date = timezone.now() - timedelta(days=self.cleanup_days)
        deleted_count, _ = UpdateLog.objects.filter(
            executed_at__lt=cutoff_date
        ).delete()

        if not self.quiet:
            self.stdout.write(f'  ✓ 清理了 {deleted_count} 条旧日志（{self.cleanup_days}天前）')
