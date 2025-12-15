"""
同步币安期货所有合约列表
Sync All Binance Futures Contracts

用途:
    从币安API获取最新的USDT本位永续合约列表，与数据库对比并同步:
    - 新增不存在的合约
    - 更新已存在合约的信息
    - 标记已下线的合约

使用方法:
    python manage.py sync_all_contracts
    python manage.py sync_all_contracts --dry-run  # 预览模式
"""
import logging
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from grid_trading.django_models import SymbolInfo
from grid_trading.services.binance_futures_client import BinanceFuturesClient

logger = logging.getLogger("grid_trading")


class Command(BaseCommand):
    help = '从币安API同步所有USDT本位永续合约列表到数据库'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='预览模式，不实际写入数据库'
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)

        self.stdout.write('=' * 80)
        self.stdout.write(self.style.SUCCESS('币安期货合约列表同步'))
        self.stdout.write('=' * 80)

        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  预览模式 - 不会写入数据库\n'))

        # ========== 步骤1: 从币安API获取最新合约列表 ==========
        self.stdout.write('\n📡 步骤1: 从币安API获取最新合约列表...')

        client = BinanceFuturesClient()

        try:
            api_contracts = client.fetch_exchange_info()
            self.stdout.write(
                self.style.SUCCESS(f'  ✓ 成功获取 {len(api_contracts)} 个USDT本位永续合约')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'  ✗ API获取失败: {e}')
            )
            return

        # 构造API合约字典 {symbol: contract_info}
        api_contracts_dict = {
            contract['symbol']: contract for contract in api_contracts
        }
        api_symbols = set(api_contracts_dict.keys())

        # ========== 步骤2: 获取数据库现有合约 ==========
        self.stdout.write('\n💾 步骤2: 获取数据库现有合约...')

        db_contracts = SymbolInfo.objects.all()
        db_symbols = set(db_contracts.values_list('symbol', flat=True))

        self.stdout.write(f'  数据库现有合约: {len(db_symbols)} 个')

        # ========== 步骤3: 对比分析 ==========
        self.stdout.write('\n🔍 步骤3: 对比分析...')

        # 新增合约（API有但DB没有）
        new_symbols = api_symbols - db_symbols

        # 保留合约（API和DB都有）
        existing_symbols = api_symbols & db_symbols

        # 已下线合约（DB有但API没有）
        delisted_symbols = db_symbols - api_symbols

        self.stdout.write(f'  新增合约: {len(new_symbols)} 个')
        self.stdout.write(f'  保留合约: {len(existing_symbols)} 个')
        self.stdout.write(f'  已下线合约: {len(delisted_symbols)} 个')

        # ========== 步骤4: 执行同步 ==========
        self.stdout.write('\n🔄 步骤4: 执行同步...')

        if dry_run:
            self.stdout.write(self.style.WARNING('  （预览模式，跳过实际写入）'))
            self._print_preview(new_symbols, delisted_symbols, api_contracts_dict)
        else:
            stats = self._sync_contracts(
                new_symbols, existing_symbols, delisted_symbols, api_contracts_dict
            )
            self._print_summary(stats)

    def _print_preview(self, new_symbols, delisted_symbols, api_contracts_dict):
        """打印预览信息"""
        if new_symbols:
            self.stdout.write('\n  将新增的合约:')
            for symbol in sorted(list(new_symbols)[:10]):  # 只显示前10个
                contract = api_contracts_dict[symbol]
                onboard_date = datetime.fromtimestamp(
                    contract['onboardDate'] / 1000
                ) if contract['onboardDate'] > 0 else None
                self.stdout.write(
                    f'    + {symbol} (上市: {onboard_date.strftime("%Y-%m-%d") if onboard_date else "未知"})'
                )
            if len(new_symbols) > 10:
                self.stdout.write(f'    ... 及其他 {len(new_symbols) - 10} 个')

        if delisted_symbols:
            self.stdout.write('\n  将标记为下线的合约:')
            for symbol in sorted(list(delisted_symbols)[:10]):  # 只显示前10个
                self.stdout.write(f'    - {symbol}')
            if len(delisted_symbols) > 10:
                self.stdout.write(f'    ... 及其他 {len(delisted_symbols) - 10} 个')

    def _sync_contracts(self, new_symbols, existing_symbols, delisted_symbols, api_contracts_dict):
        """执行实际的数据库同步"""
        stats = {
            'new_added': 0,
            'updated': 0,
            'delisted': 0,
            'errors': 0
        }

        with transaction.atomic():
            # 1. 新增合约
            if new_symbols:
                self.stdout.write(f'\n  新增 {len(new_symbols)} 个合约...')
                for symbol in new_symbols:
                    try:
                        contract = api_contracts_dict[symbol]
                        base_asset = symbol.replace('USDT', '')

                        # 处理上市时间
                        listing_date = None
                        if contract['onboardDate'] > 0:
                            listing_date = datetime.fromtimestamp(
                                contract['onboardDate'] / 1000,
                                tz=timezone.get_current_timezone()
                            )

                        SymbolInfo.objects.create(
                            symbol=symbol,
                            base_asset=base_asset,
                            quote_asset='USDT',
                            contract_type=contract['contractType'],
                            listing_date=listing_date,
                            is_active=True
                        )
                        stats['new_added'] += 1

                        # 显示进度（每50个显示一次）
                        if stats['new_added'] % 50 == 0:
                            self.stdout.write(f'    已新增: {stats["new_added"]}/{len(new_symbols)}')

                    except Exception as e:
                        logger.error(f'新增合约失败: {symbol} - {e}')
                        stats['errors'] += 1

                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ 成功新增 {stats["new_added"]} 个合约')
                )

            # 2. 更新现有合约（确保is_active=True）
            if existing_symbols:
                self.stdout.write(f'\n  更新 {len(existing_symbols)} 个现有合约...')
                updated_count = SymbolInfo.objects.filter(
                    symbol__in=existing_symbols
                ).update(
                    is_active=True
                )
                stats['updated'] = updated_count
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ 成功更新 {stats["updated"]} 个合约')
                )

            # 3. 标记已下线合约
            if delisted_symbols:
                self.stdout.write(f'\n  标记 {len(delisted_symbols)} 个已下线合约...')
                delisted_count = SymbolInfo.objects.filter(
                    symbol__in=delisted_symbols
                ).update(
                    is_active=False
                )
                stats['delisted'] = delisted_count
                self.stdout.write(
                    self.style.WARNING(f'  ⚠️  已标记 {stats["delisted"]} 个合约为下线')
                )

        return stats

    def _print_summary(self, stats):
        """打印同步总结"""
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('✅ 同步完成'))
        self.stdout.write('=' * 80)

        # 统计当前活跃合约数
        active_count = SymbolInfo.objects.filter(is_active=True).count()
        total_count = SymbolInfo.objects.count()

        self.stdout.write(f'\n📊 同步统计:')
        self.stdout.write(f'  新增合约: {stats["new_added"]} 个')
        self.stdout.write(f'  更新合约: {stats["updated"]} 个')
        self.stdout.write(f'  下线合约: {stats["delisted"]} 个')
        if stats['errors'] > 0:
            self.stdout.write(
                self.style.ERROR(f'  错误数量: {stats["errors"]} 个')
            )

        self.stdout.write(f'\n📈 数据库状态:')
        self.stdout.write(f'  活跃合约: {active_count} 个')
        self.stdout.write(f'  总计合约: {total_count} 个')
        self.stdout.write(f'  下线合约: {total_count - active_count} 个')

        self.stdout.write('\n' + '=' * 80)
