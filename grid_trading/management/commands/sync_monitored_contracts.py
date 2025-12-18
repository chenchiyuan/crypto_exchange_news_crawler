"""
自动同步监控合约脚本
Auto Sync Monitored Contracts Script

将7天累计高频合约自动同步到监控列表，与 /screening/daily/ 页面的"7天合约累计"保持完全一致
Feature: 001-price-alert-monitor
Task: T039-T046
"""
import sys
import logging
from typing import List, Dict
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from collections import defaultdict

from grid_trading.django_models import MonitoredContract
from grid_trading.models import ScreeningRecord, ScreeningResultModel
from grid_trading.services.detail_page_service import DetailPageService
from grid_trading.services.script_lock import acquire_lock, release_lock

logger = logging.getLogger("grid_trading")


class Command(BaseCommand):
    help = '自动同步监控合约列表（基于7天累计高频合约，与 /screening/daily/ 页面完全一致）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-lock',
            action='store_true',
            help='跳过脚本锁检查(仅用于测试)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='预览模式，不实际写入数据库'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='统计天数，默认7天'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='显示详细输出'
        )

    def handle(self, *args, **options):
        """
        主执行函数

        工作流程:
        1. 获取脚本锁
        2. 计算7天累计高频合约（与前端API完全一致）
        3. 对比现有监控列表
        4. 同步数据库（新增、更新、过期）
        5. 输出统计并释放锁
        """
        lock_name = 'sync_monitored_contracts'
        skip_lock = options.get('skip_lock', False)
        dry_run = options.get('dry_run', False)
        verbose = options.get('verbose', False)
        days = options.get('days', 7)

        # Step 1: 获取脚本锁
        if not skip_lock:
            if not acquire_lock(lock_name, timeout_minutes=5):
                self.stdout.write(
                    self.style.ERROR('✗ 脚本已在运行，跳过本次执行')
                )
                sys.exit(1)

        try:
            start_time = timezone.now()

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('=' * 70))
            self.stdout.write(self.style.SUCCESS('🔄 自动同步监控合约列表'))
            self.stdout.write(self.style.SUCCESS('=' * 70))

            if dry_run:
                self.stdout.write(self.style.WARNING('⚠️  试运行模式 - 不会修改数据库'))

            self.stdout.write(f'  统计天数: {days}天')
            self.stdout.write(f'  执行时间: {start_time.strftime("%Y-%m-%d %H:%M:%S")}')
            self.stdout.write('')

            # Step 2: 计算7天累计高频合约（与views.py:get_top_frequent_contracts_api完全一致）
            self.stdout.write('📅 Step 1: 获取最近筛选日期...')
            recent_dates = DetailPageService.get_available_dates(limit=days)

            if not recent_dates:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  没有找到最近{days}天的筛选记录')
                )
                return

            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ 找到 {len(recent_dates)} 个日期: {recent_dates[-1]} 至 {recent_dates[0]}'
                )
            )
            self.stdout.write('')

            # Step 3: 计算7天累计高频合约（应用筛选条件）
            self.stdout.write('🔍 Step 2: 计算7天累计高频合约...')

            # 后端筛选条件（与views.py:352-356一致）
            min_vdr = 6
            min_amplitude = 50
            max_ma99_slope = -10
            min_funding_rate = -10
            min_volume_millions_backend = 5  # 5M USDT（后端筛选）

            # 前端额外筛选条件（与daily_screening.html:743一致）
            min_oi_millions_frontend = 5  # 5M USDT（前端筛选）
            min_volume_millions_frontend = 8  # 8M USDT（前端筛选）

            self.stdout.write(f'  后端筛选条件:')
            self.stdout.write(f'    VDR >= {min_vdr}')
            self.stdout.write(f'    15m振幅 >= {min_amplitude}%')
            self.stdout.write(f'    EMA99斜率 <= {max_ma99_slope}')
            self.stdout.write(f'    年化资费 >= {min_funding_rate}%')
            self.stdout.write(f'    24h成交额 >= {min_volume_millions_backend}M USDT')
            self.stdout.write(f'  前端额外筛选条件:')
            self.stdout.write(f'    持仓量 >= {min_oi_millions_frontend}M USDT')
            self.stdout.write(f'    24h成交额 >= {min_volume_millions_frontend}M USDT')
            self.stdout.write('')

            # 获取筛选记录
            screening_records = ScreeningRecord.objects.filter(
                screening_date__in=recent_dates
            )

            # 统计每个合约的数据（对每天都应用完整的筛选条件）
            symbol_stats = defaultdict(lambda: {'dates': []})

            for record in screening_records:
                # 对每天的结果应用后端筛选条件
                filtered_results = ScreeningResultModel.objects.filter(
                    record=record,
                    vdr__gte=min_vdr,
                    amplitude_sum_15m__gte=min_amplitude,
                    ma99_slope__lte=max_ma99_slope,
                    annual_funding_rate__gte=min_funding_rate,
                    volume_24h_calculated__gte=min_volume_millions_backend * 1000000
                )

                # 对每天的结果也应用前端筛选条件
                for result in filtered_results:
                    oi_millions = float(result.open_interest or 0) / 1000000
                    vol_millions = float(result.volume_24h_calculated or 0) / 1000000

                    # 前端过滤：持仓量>=5M 且 成交额>=8M
                    # 只要某天符合条件，就计入该合约
                    if oi_millions >= min_oi_millions_frontend and vol_millions >= min_volume_millions_frontend:
                        symbol_stats[result.symbol]['dates'].append(record.screening_date)

            # 构建结果列表
            frequent_contracts = []
            for symbol, data in symbol_stats.items():
                dates = data['dates']
                appearance_count = len(dates)
                latest_date = max(dates)

                frequent_contracts.append({
                    'symbol': symbol,
                    'appearance_count': appearance_count,
                    'latest_date': latest_date
                })

            # 按出现次数排序
            frequent_contracts.sort(key=lambda x: x['appearance_count'], reverse=True)

            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ 找到 {len(frequent_contracts)} 个符合条件的7天累计合约'
                )
            )

            if verbose and frequent_contracts:
                self.stdout.write('  前10个合约:')
                for i, contract in enumerate(frequent_contracts[:10], 1):
                    self.stdout.write(
                        f'    {i}. {contract["symbol"]} - 出现{contract["appearance_count"]}次'
                    )

            self.stdout.write('')

            # Step 4: 获取当前监控合约
            self.stdout.write('📋 Step 3: 获取当前监控合约...')

            current_auto_contracts = MonitoredContract.objects.filter(
                source='auto'
            ).exclude(status='expired')

            current_manual_contracts = MonitoredContract.objects.filter(
                source='manual',
                status='enabled'
            )

            current_auto_symbols = set(current_auto_contracts.values_list('symbol', flat=True))
            current_manual_symbols = set(current_manual_contracts.values_list('symbol', flat=True))
            target_symbols = {c['symbol'] for c in frequent_contracts}

            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ 当前监控: 自动={len(current_auto_symbols)}个, 手动={len(current_manual_symbols)}个'
                )
            )
            self.stdout.write('')

            # Step 5: 对比并计算同步差异
            self.stdout.write('🔄 Step 4: 计算同步差异...')

            # 新增: 7天累计中有，但当前自动监控中没有
            to_add = target_symbols - current_auto_symbols
            # 更新: 7天累计中有，当前自动监控中也有
            to_update = target_symbols & current_auto_symbols
            # 过期: 当前自动监控中有，但7天累计中没有
            to_expire = current_auto_symbols - target_symbols

            stats = {
                'added': 0,
                'updated': 0,
                'expired': 0,
                'to_add': to_add,
                'to_update': to_update,
                'to_expire': to_expire,
                'target_count': len(target_symbols),
                'manual_count': len(current_manual_symbols)
            }

            # 输出同步摘要
            self.stdout.write('')
            self.stdout.write('=' * 70)
            self.stdout.write('📊 同步摘要:')
            self.stdout.write('=' * 70)
            self.stdout.write(f'  7天累计合约: {stats["target_count"]} 个')
            self.stdout.write(f'  当前自动监控: {len(current_auto_symbols)} 个')
            self.stdout.write(f'  当前手动监控: {stats["manual_count"]} 个')
            self.stdout.write('')
            self.stdout.write(f'  ➕ 新增: {len(to_add)} 个')
            self.stdout.write(f'  🔄 更新: {len(to_update)} 个')
            self.stdout.write(f'  ⊘ 过期: {len(to_expire)} 个')
            self.stdout.write('')
            self.stdout.write(f'  同步后总监控: {stats["target_count"] + stats["manual_count"]} 个 (自动{stats["target_count"]} + 手动{stats["manual_count"]})')
            self.stdout.write('=' * 70)

            # 显示详细列表
            if verbose:
                if to_add:
                    self.stdout.write('')
                    self.stdout.write('  新增合约:')
                    for symbol in sorted(to_add)[:20]:  # 最多显示20个
                        self.stdout.write(f'    ➕ {symbol}')
                    if len(to_add) > 20:
                        self.stdout.write(f'    ... 还有 {len(to_add) - 20} 个')

                if to_expire:
                    self.stdout.write('')
                    self.stdout.write('  过期合约:')
                    for symbol in sorted(to_expire)[:20]:
                        self.stdout.write(f'    ⊘ {symbol}')
                    if len(to_expire) > 20:
                        self.stdout.write(f'    ... 还有 {len(to_expire) - 20} 个')

            # Step 6: 执行同步
            if not dry_run:
                self.stdout.write('')
                self.stdout.write('💾 Step 5: 写入数据库...')

                with transaction.atomic():
                    # 新增合约（处理可能已存在但状态为expired的情况）
                    if to_add:
                        added_count = 0
                        for symbol in to_add:
                            contract_data = next(
                                c for c in frequent_contracts if c['symbol'] == symbol
                            )

                            # 尝试获取已存在的合约（可能是expired状态）
                            existing = MonitoredContract.objects.filter(symbol=symbol).first()

                            if existing:
                                # 如果已存在，更新状态和日期
                                existing.source = 'auto'
                                existing.status = 'enabled'
                                existing.last_screening_date = contract_data['latest_date']
                                existing.save()
                                added_count += 1
                            else:
                                # 如果不存在，创建新记录
                                MonitoredContract.objects.create(
                                    symbol=symbol,
                                    source='auto',
                                    status='enabled',
                                    last_screening_date=contract_data['latest_date']
                                )
                                added_count += 1

                        stats['added'] = added_count

                    # 更新合约
                    if to_update:
                        for symbol in to_update:
                            contract_data = next(
                                c for c in frequent_contracts if c['symbol'] == symbol
                            )
                            MonitoredContract.objects.filter(
                                symbol=symbol,
                                source='auto'
                            ).update(
                                last_screening_date=contract_data['latest_date'],
                                status='enabled'  # 重新激活可能之前被禁用的合约
                            )
                        stats['updated'] = len(to_update)

                    # 过期合约
                    if to_expire:
                        MonitoredContract.objects.filter(
                            symbol__in=to_expire,
                            source='auto'
                        ).update(
                            status='expired'
                        )
                        stats['expired'] = len(to_expire)

                logger.info(
                    f"✓ 同步完成: 新增{stats['added']}个, 更新{stats['updated']}个, 过期{stats['expired']}个"
                )

                self.stdout.write(self.style.SUCCESS('✓ 数据库更新完成'))

            # 最终统计
            self.stdout.write('')
            self.stdout.write('=' * 70)

            if not dry_run:
                final_auto_count = MonitoredContract.objects.filter(
                    source='auto',
                    status='enabled'
                ).count()

                final_manual_count = MonitoredContract.objects.filter(
                    source='manual',
                    status='enabled'
                ).count()

                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ 当前监控合约总数: {final_auto_count + final_manual_count} 个'
                    )
                )
                self.stdout.write(f'  自动: {final_auto_count} 个')
                self.stdout.write(f'  手动: {final_manual_count} 个')
            else:
                self.stdout.write(
                    self.style.WARNING('⚠️  试运行模式 - 数据未实际修改')
                )

            elapsed_seconds = (timezone.now() - start_time).total_seconds()
            self.stdout.write(f'  耗时: {elapsed_seconds:.1f} 秒')
            self.stdout.write('=' * 70)
            self.stdout.write('')

        except Exception as e:
            logger.error(f"同步监控合约异常: {e}", exc_info=True)
            self.stdout.write('')
            self.stdout.write(
                self.style.ERROR(f'✗ 同步失败: {e}')
            )
            import traceback
            traceback.print_exc()
            sys.exit(1)

        finally:
            # 释放脚本锁
            if not skip_lock:
                release_lock(lock_name)

