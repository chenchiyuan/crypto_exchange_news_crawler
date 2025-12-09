"""
自动同步监控合约脚本
Auto Sync Monitored Contracts Script

从筛选系统数据库直接读取符合条件的合约并同步到监控列表
Feature: 001-price-alert-monitor
Task: T039-T046
"""
import sys
import logging
from typing import List, Dict
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from grid_trading.django_models import (
    MonitoredContract,
    SystemConfig
)
from grid_trading.models import ScreeningRecord, ScreeningResultModel
from grid_trading.services.script_lock import acquire_lock, release_lock

logger = logging.getLogger("grid_trading")


class Command(BaseCommand):
    help = '从筛选系统数据库直接读取符合条件的合约并同步到监控列表'

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
            '--max-contracts',
            type=int,
            help='最大监控合约数量限制(默认从SystemConfig读取)'
        )
        parser.add_argument(
            '--days-back',
            type=int,
            default=3,
            help='查找最近N天的筛选记录(默认3天)'
        )

    def handle(self, *args, **options):
        """
        主执行函数

        工作流程:
        1. 获取脚本锁
        2. 从数据库查询最近的筛选记录
        3. 应用筛选条件获取符合条件的合约列表
        4. 对比现有监控列表，识别新增/保留/移除的合约
        5. 更新数据库(新增auto源合约，标记expired)
        6. 输出同步统计并释放锁
        """
        lock_name = 'sync_monitored_contracts'
        skip_lock = options.get('skip_lock', False)
        dry_run = options.get('dry_run', False)

        # Step 1: 获取脚本锁
        if not skip_lock:
            if not acquire_lock(lock_name, timeout_minutes=5):
                self.stdout.write(
                    self.style.ERROR('✗ 脚本已在运行，跳过本次执行')
                )
                sys.exit(1)

        try:
            start_time = timezone.now()
            self.stdout.write(
                self.style.SUCCESS(
                    f'[{start_time.strftime("%Y-%m-%d %H:%M:%S")}] '
                    f'开始同步监控合约...'
                )
            )

            if dry_run:
                self.stdout.write(
                    self.style.WARNING('⚠️ 预览模式：不会实际修改数据库\n')
                )

            # Step 2: 从数据库获取筛选结果
            days_back = options.get('days_back', 3)
            screening_symbols = self._fetch_screening_from_db(days_back)

            if screening_symbols is None:
                self.stdout.write(
                    self.style.ERROR('✗ 获取筛选结果失败，退出执行')
                )
                sys.exit(1)

            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ 获取到 {len(screening_symbols)} 个筛选结果\n'
                )
            )

            # Step 3: 对比现有监控列表
            stats = self._compute_sync_diff(screening_symbols)

            self._print_sync_summary(stats)

            # 检查数量限制
            max_contracts = options.get('max_contracts') or int(
                SystemConfig.get_value('max_monitored_contracts', 500)
            )

            if stats['total_after'] > max_contracts:
                self.stdout.write(
                    self.style.ERROR(
                        f'\n✗ 同步后合约数量({stats["total_after"]})超过限制({max_contracts})，'
                        f'请调整筛选条件或提高限制'
                    )
                )
                sys.exit(1)

            # Step 4: 更新数据库
            if not dry_run:
                self._apply_sync_changes(stats)
                self.stdout.write(
                    self.style.SUCCESS('\n✓ 数据库更新完成')
                )
            else:
                self.stdout.write(
                    self.style.WARNING('\n⚠️ 预览模式：未实际修改数据库')
                )

            # Step 5: 输出执行统计
            elapsed_seconds = (timezone.now() - start_time).total_seconds()

            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ 同步完成，耗时 {elapsed_seconds:.1f} 秒'
                )
            )

        except Exception as e:
            logger.error(f"同步监控合约异常: {e}", exc_info=True)
            self.stdout.write(
                self.style.ERROR(f'✗ 同步失败: {e}')
            )
            sys.exit(1)

        finally:
            # 释放脚本锁
            if not skip_lock:
                release_lock(lock_name)

    def _fetch_screening_from_db(self, days_back: int) -> List[str]:
        """
        从数据库直接查询筛选结果

        Args:
            days_back: 查找最近N天的筛选记录

        Returns:
            List[str]: 符合条件的合约代码列表，失败返回None
        """
        try:
            # 1. 查找最近的筛选记录
            cutoff_date = timezone.now() - timedelta(days=days_back)
            latest_record = ScreeningRecord.objects.filter(
                created_at__gte=cutoff_date
            ).order_by('-created_at').first()

            if not latest_record:
                logger.error(f"未找到最近{days_back}天内的筛选记录")
                self.stdout.write(
                    self.style.ERROR(
                        f'✗ 未找到最近{days_back}天内的筛选记录'
                    )
                )
                self.stdout.write(
                    self.style.WARNING(
                        '提示: 请先运行 python manage.py screen_simple 生成筛选数据'
                    )
                )
                return None

            self.stdout.write(
                f'使用筛选记录: {latest_record.created_at.strftime("%Y-%m-%d %H:%M:%S")} '
                f'({latest_record.total_candidates}个候选)'
            )

            # 2. 从SystemConfig读取筛选条件（与Dashboard前端保持一致）
            filter_config = {
                'min_vdr': float(SystemConfig.get_value('screening_min_vdr', 6)),
                'min_amplitude': float(SystemConfig.get_value('screening_min_amplitude', 50)),
                'max_ma99_slope': float(SystemConfig.get_value('screening_max_ma99_slope', -10)),
                'min_funding_rate': float(SystemConfig.get_value('screening_min_funding_rate', -10)),
                'min_volume': float(SystemConfig.get_value('screening_min_volume', 5000000)),
            }

            self.stdout.write('筛选条件:')
            for key, value in filter_config.items():
                self.stdout.write(f'  {key}: {value}')

            # 3. 应用筛选条件查询数据库
            results = ScreeningResultModel.objects.filter(
                record=latest_record,
                vdr__gte=filter_config['min_vdr'],
                amplitude_sum_15m__gte=filter_config['min_amplitude'],
                ma99_slope__lte=filter_config['max_ma99_slope'],
                funding_rate__gte=filter_config['min_funding_rate'],
                volume_24h__gte=filter_config['min_volume']
            ).values_list('symbol', flat=True)

            symbols = list(results)

            logger.info(
                f"✓ 从筛选记录{latest_record.id}获取到{len(symbols)}个符合条件的合约"
            )

            return symbols

        except Exception as e:
            logger.error(f"从数据库获取筛选结果异常: {e}", exc_info=True)
            return None

    def _compute_sync_diff(self, screening_symbols: List[str]) -> Dict:
        """
        对比筛选结果和现有监控列表，计算同步差异

        Args:
            screening_symbols: 筛选结果合约列表

        Returns:
            dict: 同步统计信息
        """
        # 查询现有的auto源合约
        existing_auto = set(
            MonitoredContract.objects.filter(
                source='auto',
                status__in=['enabled', 'disabled']
            ).values_list('symbol', flat=True)
        )

        # 查询现有的manual源合约
        existing_manual = set(
            MonitoredContract.objects.filter(
                source='manual',
                status__in=['enabled', 'disabled']
            ).values_list('symbol', flat=True)
        )

        screening_set = set(screening_symbols)

        # 计算差异
        to_add = screening_set - existing_auto - existing_manual  # 新增
        to_keep = screening_set & existing_auto  # 保留(auto源)
        to_remove = existing_auto - screening_set  # 移除(auto源)

        stats = {
            'screening_count': len(screening_symbols),
            'existing_auto_count': len(existing_auto),
            'existing_manual_count': len(existing_manual),
            'to_add': list(to_add),
            'to_keep': list(to_keep),
            'to_remove': list(to_remove),
            'total_after': len(to_add) + len(to_keep) + len(existing_manual),
        }

        return stats

    def _print_sync_summary(self, stats: Dict):
        """
        打印同步摘要

        Args:
            stats: 同步统计信息
        """
        self.stdout.write('=' * 60)
        self.stdout.write('同步摘要:')
        self.stdout.write('=' * 60)

        self.stdout.write(
            f'筛选结果数量: {stats["screening_count"]}'
        )
        self.stdout.write(
            f'现有监控合约: {stats["existing_auto_count"]} (auto源) + '
            f'{stats["existing_manual_count"]} (manual源)'
        )
        self.stdout.write('')

        self.stdout.write(
            self.style.SUCCESS(f'✓ 保留: {len(stats["to_keep"])} 个合约')
        )
        self.stdout.write(
            self.style.WARNING(f'+ 新增: {len(stats["to_add"])} 个合约')
        )
        self.stdout.write(
            self.style.ERROR(f'- 移除: {len(stats["to_remove"])} 个合约')
        )
        self.stdout.write('')

        self.stdout.write(
            f'同步后总数: {stats["total_after"]} (auto + manual)'
        )

        # 显示详细列表(最多显示前10个)
        if stats['to_add']:
            self.stdout.write('\n新增合约(前10个):')
            for symbol in list(stats['to_add'])[:10]:
                self.stdout.write(f'  + {symbol}')
            if len(stats['to_add']) > 10:
                self.stdout.write(f'  ... 还有 {len(stats["to_add"]) - 10} 个')

        if stats['to_remove']:
            self.stdout.write('\n移除合约(前10个):')
            for symbol in list(stats['to_remove'])[:10]:
                self.stdout.write(f'  - {symbol}')
            if len(stats['to_remove']) > 10:
                self.stdout.write(f'  ... 还有 {len(stats["to_remove"]) - 10} 个')

        self.stdout.write('=' * 60)

    def _apply_sync_changes(self, stats: Dict):
        """
        应用同步变更到数据库

        Args:
            stats: 同步统计信息
        """
        today = timezone.now().date()

        # 1. 新增合约(source=auto, status=enabled)
        to_add_objects = [
            MonitoredContract(
                symbol=symbol,
                source='auto',
                status='enabled',
                last_screening_date=today
            )
            for symbol in stats['to_add']
        ]

        if to_add_objects:
            MonitoredContract.objects.bulk_create(
                to_add_objects,
                ignore_conflicts=True
            )
            logger.info(f"✓ 新增 {len(to_add_objects)} 个auto源合约")

        # 2. 移除合约(标记为expired)
        if stats['to_remove']:
            removed_count = MonitoredContract.objects.filter(
                symbol__in=stats['to_remove'],
                source='auto'
            ).update(status='expired')
            logger.info(f"✓ 移除 {removed_count} 个auto源合约")

        # 3. 保留合约(更新last_screening_date)
        if stats['to_keep']:
            keep_count = MonitoredContract.objects.filter(
                symbol__in=stats['to_keep'],
                source='auto'
            ).update(last_screening_date=today)
            logger.info(f"✓ 保留 {keep_count} 个auto源合约")

        logger.info(
            f"✓ 同步完成: auto={len(stats['to_keep']) + len(stats['to_add'])}, "
            f"manual={stats['existing_manual_count']}"
        )
