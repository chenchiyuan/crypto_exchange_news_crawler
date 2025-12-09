"""
价格监控数据更新脚本
Price Monitor Data Update Script

每5分钟执行一次，批量更新所有监控合约的K线数据(1m/15m/4h)和当前价格
Feature: 001-price-alert-monitor
Task: T010, T012, T013, T014, T016
"""
import sys
import time
import logging
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from grid_trading.django_models import (
    MonitoredContract,
    DataUpdateLog,
    KlineData
)
from grid_trading.services.script_lock import acquire_lock, release_lock
from grid_trading.services.kline_cache import KlineCache
from grid_trading.services.binance_futures_client import BinanceFuturesClient
from grid_trading.services.rule_utils import validate_kline_continuity

logger = logging.getLogger("grid_trading")


class Command(BaseCommand):
    help = '更新价格监控系统的K线数据(1m/15m/4h)和当前价格'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-lock',
            action='store_true',
            help='跳过脚本锁检查(仅用于测试)'
        )
        parser.add_argument(
            '--symbols',
            type=str,
            help='指定更新的合约(逗号分隔)，如: BTCUSDT,ETHUSDT'
        )
        parser.add_argument(
            '--intervals',
            type=str,
            default='1m,15m,4h',
            help='指定更新的K线周期(逗号分隔)，默认: 1m,15m,4h'
        )

    def handle(self, *args, **options):
        """
        主执行函数

        工作流程:
        1. 获取脚本锁
        2. 创建执行日志
        3. 查询启用的监控合约
        4. 批量更新K线数据(串行处理，避免API限流)
        5. 检测数据完整性
        6. 更新执行日志并释放锁
        """
        lock_name = 'price_monitor_data_update'
        skip_lock = options.get('skip_lock', False)

        # Step 1: 获取脚本锁
        if not skip_lock:
            if not acquire_lock(lock_name, timeout_minutes=10):
                self.stdout.write(
                    self.style.ERROR('✗ 脚本已在运行，跳过本次执行')
                )
                sys.exit(1)

        try:
            # Step 2: 创建执行日志
            log = DataUpdateLog.objects.create()
            self.stdout.write(
                self.style.SUCCESS(
                    f'[{timezone.now().strftime("%Y-%m-%d %H:%M:%S")}] '
                    f'开始数据更新...'
                )
            )

            # Step 3: 查询监控合约
            if options.get('symbols'):
                symbols = options['symbols'].split(',')
                contracts = MonitoredContract.objects.filter(
                    symbol__in=symbols,
                    status='enabled'
                )
            else:
                contracts = MonitoredContract.objects.filter(status='enabled')

            contracts_count = contracts.count()
            log.contracts_count = contracts_count

            self.stdout.write(
                self.style.SUCCESS(f'获取到 {contracts_count} 个启用的监控合约')
            )

            if contracts_count == 0:
                self.stdout.write(
                    self.style.WARNING('⚠️ 没有启用的监控合约，退出执行')
                )
                log.complete(status='success', error_message='无启用合约')
                return

            # Step 4: 批量更新K线数据
            intervals = options['intervals'].split(',')
            total_klines = self._update_klines(contracts, intervals, log)

            log.klines_count = total_klines

            # Step 6: 标记执行完成
            log.complete(status='success')

            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ 数据更新完成，耗时 {log.execution_seconds} 秒'
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'统计: 更新 {contracts_count} 个合约，'
                    f'获取 {total_klines} 条K线'
                )
            )

        except Exception as e:
            logger.error(f"数据更新异常: {e}", exc_info=True)
            if 'log' in locals():
                log.complete(status='failed', error_message=str(e))

            self.stdout.write(
                self.style.ERROR(f'✗ 数据更新失败: {e}')
            )
            sys.exit(1)

        finally:
            # 释放脚本锁
            if not skip_lock:
                release_lock(lock_name)

    def _update_klines(self, contracts, intervals, log):
        """
        更新所有合约的K线数据

        Args:
            contracts: 监控合约查询集
            intervals: K线周期列表
            log: 执行日志对象

        Returns:
            int: 获取的K线总数
        """
        # 初始化币安客户端和K线缓存
        try:
            client = BinanceFuturesClient()
            cache = KlineCache(api_client=client)
        except Exception as e:
            logger.error(f"初始化币安客户端失败: {e}")
            raise

        total_klines = 0
        failed_contracts = []

        # 遍历每个合约
        for idx, contract in enumerate(contracts, 1):
            symbol = contract.symbol
            self.stdout.write(
                f'\n[{idx}/{contracts.count()}] 更新 {symbol}...'
            )

            contract_klines = 0
            failed_intervals = []

            # 遍历每个周期
            for interval in intervals:
                try:
                    # 计算需要获取的K线数量
                    limit = self._get_limit_for_interval(interval)

                    # 使用KlineCache增量更新
                    start_time = time.time()
                    klines = cache.get_klines(
                        symbol=symbol,
                        interval=interval,
                        limit=limit,
                        use_cache=True
                    )
                    elapsed = time.time() - start_time

                    klines_count = len(klines) if klines else 0
                    contract_klines += klines_count

                    self.stdout.write(
                        f'  ✓ {interval:4s}: {klines_count:4d} 条 '
                        f'({elapsed:.2f}s)'
                    )

                    # Step 5: 检测数据完整性(仅4h周期)
                    if interval == '4h' and klines_count > 0:
                        continuity = validate_kline_continuity(
                            klines,
                            interval,
                            tolerance_pct=10.0
                        )

                        if not continuity['is_continuous']:
                            logger.warning(
                                f"{symbol} {interval} K线不连续: "
                                f"{continuity['message']}"
                            )
                            self.stdout.write(
                                self.style.WARNING(
                                    f'    ⚠️ 数据不连续: '
                                    f'缺失 {continuity["missing_pct"]:.1f}%'
                                )
                            )

                    # 控制API请求频率(每个请求间隔50ms)
                    time.sleep(0.05)

                except Exception as e:
                    logger.error(
                        f"更新 {symbol} {interval} 失败: {e}",
                        exc_info=True
                    )
                    failed_intervals.append(interval)
                    self.stdout.write(
                        self.style.ERROR(f'  ✗ {interval}: 失败 - {e}')
                    )

            total_klines += contract_klines

            # 更新合约的最后数据更新时间
            if len(failed_intervals) < len(intervals):
                contract.last_data_update_at = timezone.now()
                contract.save(update_fields=['last_data_update_at'])

            # 记录失败的合约
            if failed_intervals:
                failed_contracts.append({
                    'symbol': symbol,
                    'failed_intervals': failed_intervals
                })

        # 输出失败统计
        if failed_contracts:
            self.stdout.write(
                self.style.WARNING(
                    f'\n⚠️ {len(failed_contracts)} 个合约部分更新失败:'
                )
            )
            for item in failed_contracts[:5]:  # 只显示前5个
                self.stdout.write(
                    f"  - {item['symbol']}: "
                    f"{', '.join(item['failed_intervals'])}"
                )

        return total_klines

    def _get_limit_for_interval(self, interval: str) -> int:
        """
        根据K线周期计算需要获取的数量

        Args:
            interval: K线周期

        Returns:
            int: 需要获取的K线数量

        规则:
        - 1m: 150根 (2.5小时)
        - 15m: 96根 (24小时)
        - 4h: 42根 (7天)
        """
        limits = {
            '1m': 150,   # 2.5小时
            '5m': 288,   # 24小时
            '15m': 96,   # 24小时
            '1h': 168,   # 7天
            '4h': 42,    # 7天
            '1d': 30,    # 30天
        }

        return limits.get(interval, 100)
