"""从CoinGecko更新市值和FDV数据

用途:
    批量获取币安合约的市值和FDV数据，存储到MarketData表

使用方法:
    python manage.py update_market_data [--batch-size 250] [--symbols BTC,ETH]
"""
import logging
import time
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from grid_trading.models import TokenMapping, MarketData, UpdateLog
from grid_trading.services.coingecko_client import CoingeckoClient


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '从CoinGecko批量更新市值和FDV数据到MarketData表'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=250,
            help='每批次获取的代币数量（默认: 250，CoinGecko API限制）'
        )
        parser.add_argument(
            '--symbols',
            type=str,
            help='指定要更新的symbol列表（逗号分隔），如: BTC,ETH,SOL'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='演练模式，不实际写入数据库'
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        symbols_filter = options.get('symbols')
        dry_run = options['dry_run']

        self.stdout.write('=' * 80)
        self.stdout.write('更新市值和FDV数据')
        self.stdout.write('=' * 80)

        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  演练模式 - 不会写入数据库'))

        # 获取需要更新的TokenMapping
        mappings_query = TokenMapping.objects.exclude(
            coingecko_id__isnull=True
        ).exclude(
            coingecko_id=''
        )

        # 如果指定了symbols，过滤
        if symbols_filter:
            symbols_list = [s.strip() for s in symbols_filter.split(',')]
            mappings_query = mappings_query.filter(symbol__in=symbols_list)

        mappings = list(mappings_query.order_by('symbol'))

        self.stdout.write(f'\n需要更新的代币数: {len(mappings)}')

        if len(mappings) == 0:
            self.stdout.write(self.style.WARNING('没有需要更新的代币'))
            return

        # 创建更新日志
        batch_id = None
        if not dry_run:
            batch_id, _ = UpdateLog.log_batch_start(
                operation_type=UpdateLog.OperationType.MARKET_DATA_UPDATE,
                metadata={'total_coins': len(mappings)}
            )

        # 初始化CoinGecko客户端
        client = CoingeckoClient()

        # 统计信息
        stats = {
            'total': len(mappings),
            'success': 0,
            'not_found': 0,
            'api_error': 0,
            'skipped': 0,
        }

        # 分批处理
        self.stdout.write(f'\n批次大小: {batch_size}')
        self.stdout.write('开始获取数据...\n')

        for batch_start in range(0, len(mappings), batch_size):
            batch_end = min(batch_start + batch_size, len(mappings))
            batch_mappings = mappings[batch_start:batch_end]
            batch_num = (batch_start // batch_size) + 1
            total_batches = (len(mappings) + batch_size - 1) // batch_size

            self.stdout.write(
                f'\n批次 {batch_num}/{total_batches} '
                f'({batch_start + 1}-{batch_end} / {len(mappings)})'
            )
            self.stdout.write('-' * 80)

            # 准备CoinGecko ID列表
            coingecko_ids = [m.coingecko_id for m in batch_mappings]

            try:
                # 调用CoinGecko API获取市场数据
                market_data_list = client.fetch_market_data(
                    coingecko_ids=coingecko_ids,
                    per_page=batch_size
                )

                if not market_data_list:
                    self.stdout.write(self.style.WARNING('  ⚠️  API返回空数据'))
                    stats['api_error'] += len(batch_mappings)
                    continue

                # 创建ID到市场数据的映射
                market_data_dict = {item['id']: item for item in market_data_list}

                # 处理每个mapping
                for i, mapping in enumerate(batch_mappings, 1):
                    symbol = mapping.symbol
                    cg_id = mapping.coingecko_id

                    # 查找市场数据
                    market_info = market_data_dict.get(cg_id)

                    if not market_info:
                        self.stdout.write(
                            f'  [{batch_start + i:3d}] ⊘ {symbol:20s} '
                            f'→ {cg_id:30s} (未找到数据)'
                        )
                        stats['not_found'] += 1

                        if not dry_run and batch_id:
                            UpdateLog.log_symbol_error(
                                batch_id=batch_id,
                                symbol=symbol,
                                operation_type=UpdateLog.OperationType.MARKET_DATA_UPDATE,
                                error_message=f'CoinGecko未返回{cg_id}的数据'
                            )
                        continue

                    # 提取数据
                    market_cap = market_info.get('market_cap')
                    fdv = market_info.get('fully_diluted_valuation')
                    price = market_info.get('current_price')
                    volume_24h = market_info.get('total_volume')

                    # 显示信息
                    mc_str = f'${market_cap/1e9:.2f}B' if market_cap else 'N/A'
                    fdv_str = f'${fdv/1e9:.2f}B' if fdv else 'N/A'

                    self.stdout.write(
                        f'  [{batch_start + i:3d}] ✓ {symbol:20s} '
                        f'MC: {mc_str:10s} FDV: {fdv_str:10s}'
                    )

                    # 写入数据库
                    if not dry_run:
                        try:
                            with transaction.atomic():
                                MarketData.objects.update_or_create(
                                    symbol=symbol,
                                    defaults={
                                        'market_cap': market_cap,
                                        'fully_diluted_valuation': fdv,
                                        'data_source': 'coingecko',
                                        'fetched_at': timezone.now(),
                                    }
                                )
                            stats['success'] += 1

                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(f'      ✗ 数据库写入失败: {e}')
                            )
                            if batch_id:
                                UpdateLog.log_symbol_error(
                                    batch_id=batch_id,
                                    symbol=symbol,
                                    operation_type=UpdateLog.OperationType.MARKET_DATA_UPDATE,
                                    error_message=f'数据库写入失败: {e}'
                                )
                            stats['api_error'] += 1
                    else:
                        stats['success'] += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'\n  ✗ 批次{batch_num}失败: {e}')
                )
                logger.exception(f'Batch {batch_num} failed')
                stats['api_error'] += len(batch_mappings)

                if not dry_run and batch_id:
                    for mapping in batch_mappings:
                        UpdateLog.log_symbol_error(
                            batch_id=batch_id,
                            symbol=mapping.symbol,
                            operation_type=UpdateLog.OperationType.MARKET_DATA_UPDATE,
                            error_message=f'批次API调用失败: {e}'
                        )

            # 批次间延迟（符合CoinGecko Demo API限制：10 calls/minute）
            if batch_num < total_batches and not dry_run:
                delay = client.BATCH_DELAY
                self.stdout.write(f'\n⏱️  等待 {delay}秒 (避免限流)...')
                time.sleep(delay)

        # 完成更新日志
        if not dry_run and batch_id:
            status = UpdateLog.Status.SUCCESS if stats['success'] == stats['total'] else \
                     UpdateLog.Status.PARTIAL_SUCCESS if stats['success'] > 0 else \
                     UpdateLog.Status.FAILED
            UpdateLog.log_batch_complete(
                batch_id=batch_id,
                operation_type=UpdateLog.OperationType.MARKET_DATA_UPDATE,
                status=status,
                metadata={
                    'total': stats['total'],
                    'success': stats['success'],
                    'not_found': stats['not_found'],
                    'api_error': stats['api_error']
                }
            )

        # 最终统计
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('✓ 更新完成'))
        self.stdout.write('=' * 80)

        self.stdout.write(f'\n总计: {stats["total"]} 个代币')
        self.stdout.write(f'  - 成功: {stats["success"]} ({stats["success"]/stats["total"]*100:.1f}%)')
        self.stdout.write(f'  - 未找到: {stats["not_found"]} ({stats["not_found"]/stats["total"]*100:.1f}%)')
        self.stdout.write(f'  - 错误: {stats["api_error"]} ({stats["api_error"]/stats["total"]*100:.1f}%)')

        if not dry_run:
            # 显示数据库统计
            db_count = MarketData.objects.count()
            self.stdout.write(f'\nMarketData表当前记录数: {db_count}')

            # 显示最新的数据示例
            self.stdout.write('\n最新更新的5个数据:')
            for data in MarketData.objects.order_by('-fetched_at')[:5]:
                mc = f'${float(data.market_cap)/1e9:.2f}B' if data.market_cap else 'N/A'
                fdv = f'${float(data.fully_diluted_valuation)/1e9:.2f}B' if data.fully_diluted_valuation else 'N/A'
                self.stdout.write(
                    f'  - {data.symbol:15s} MC: {mc:10s} FDV: {fdv:10s} '
                    f'({data.fetched_at.strftime("%Y-%m-%d %H:%M")})'
                )
        else:
            self.stdout.write(self.style.WARNING('\n⚠️  演练模式 - 未写入数据库'))
