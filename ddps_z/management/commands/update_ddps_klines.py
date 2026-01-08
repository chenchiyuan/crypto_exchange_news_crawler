"""
DDPS K线数据更新命令
Update DDPS KLines Command

独立的K线数据更新命令，用于DDPS价格监控服务。
复用backtest.management.commands.update_klines的核心逻辑。

功能特性:
    - 支持--symbols参数指定交易对
    - 不指定时使用settings.DDPS_MONITOR_CONFIG默认列表
    - 返回更新成功/失败的统计信息

使用示例:
    # 使用默认交易对列表
    python manage.py update_ddps_klines

    # 指定交易对
    python manage.py update_ddps_klines --symbols ETHUSDT,BTCUSDT

    # 指定周期
    python manage.py update_ddps_klines --interval 4h

Related:
    - PRD: docs/iterations/023-ddps-price-monitor/prd.md
    - Task: TASK-023-003
"""

import logging
import time
from typing import List, Tuple

from django.conf import settings
from django.core.management.base import BaseCommand

from backtest.services.data_fetcher import DataFetcher

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '更新DDPS监控交易对的K线数据'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbols',
            type=str,
            required=False,
            help='交易对列表，逗号分隔（如ETHUSDT,BTCUSDT）。不指定则使用默认配置。'
        )
        parser.add_argument(
            '--interval',
            type=str,
            default=None,
            choices=['1h', '4h', '1d'],
            help='K线周期，默认使用配置中的interval'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=500,
            help='获取最新N条K线，默认500'
        )

    def handle(self, *args, **options):
        """执行K线数据更新"""
        # 获取配置
        config = getattr(settings, 'DDPS_MONITOR_CONFIG', {})

        # 解析交易对列表
        symbols_str = options.get('symbols')
        if symbols_str:
            symbols = [s.strip().upper() for s in symbols_str.split(',')]
        else:
            symbols = config.get('default_symbols', [])

        if not symbols:
            self.stdout.write(
                self.style.ERROR('错误：未配置交易对列表。请使用--symbols参数或配置DDPS_MONITOR_CONFIG。')
            )
            return

        # 获取参数
        interval = options.get('interval') or config.get('interval', '4h')
        market_type = config.get('market_type', 'futures')
        limit = options.get('limit')

        self.stdout.write(
            self.style.MIGRATE_HEADING('\n=== DDPS K线数据更新 ===\n')
        )
        self.stdout.write(f'交易对: {", ".join(symbols)}')
        self.stdout.write(f'周期: {interval}')
        self.stdout.write(f'市场: {market_type}')
        self.stdout.write(f'数量: {limit}')
        self.stdout.write('')

        # 执行更新
        success_list, failed_list = self._update_symbols(
            symbols=symbols,
            interval=interval,
            market_type=market_type,
            limit=limit
        )

        # 输出统计
        self._display_stats(success_list, failed_list)

    def _update_symbols(
        self,
        symbols: List[str],
        interval: str,
        market_type: str,
        limit: int
    ) -> Tuple[List[Tuple[str, int]], List[Tuple[str, str]]]:
        """
        更新多个交易对的K线数据

        Args:
            symbols: 交易对列表
            interval: K线周期
            market_type: 市场类型
            limit: 获取数量

        Returns:
            Tuple[List, List]: (成功列表, 失败列表)
        """
        success_list = []
        failed_list = []

        total = len(symbols)
        start_time = time.time()

        for idx, symbol in enumerate(symbols, start=1):
            try:
                saved_count = self._update_single_symbol(
                    symbol=symbol,
                    interval=interval,
                    market_type=market_type,
                    limit=limit
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'[{idx}/{total}] {symbol}: ✓ 新增 {saved_count} 条'
                    )
                )
                success_list.append((symbol, saved_count))

            except Exception as e:
                error_msg = str(e)
                logger.error(f'更新{symbol}失败: {error_msg}', exc_info=True)
                self.stdout.write(
                    self.style.ERROR(
                        f'[{idx}/{total}] {symbol}: ✗ 错误: {error_msg}'
                    )
                )
                failed_list.append((symbol, error_msg))

            # 延迟控制（避免API限流）
            if idx < total:
                time.sleep(0.1)

        elapsed = time.time() - start_time
        self.stdout.write(f'\n总耗时: {elapsed:.1f}秒')

        return success_list, failed_list

    def _update_single_symbol(
        self,
        symbol: str,
        interval: str,
        market_type: str,
        limit: int
    ) -> int:
        """
        更新单个交易对的K线数据

        Args:
            symbol: 交易对
            interval: K线周期
            market_type: 市场类型
            limit: 获取数量

        Returns:
            int: 新增的K线数量
        """
        fetcher = DataFetcher(symbol, interval, market_type)
        saved_count = fetcher.update_latest_data(limit=limit)
        return saved_count

    def _display_stats(
        self,
        success_list: List[Tuple[str, int]],
        failed_list: List[Tuple[str, str]]
    ):
        """
        显示更新统计信息

        Args:
            success_list: 成功列表 [(symbol, count), ...]
            failed_list: 失败列表 [(symbol, error), ...]
        """
        self.stdout.write('\n=== 更新统计 ===')
        self.stdout.write(f'成功: {len(success_list)} 个交易对')
        self.stdout.write(f'失败: {len(failed_list)} 个交易对')

        if success_list:
            total_saved = sum(count for _, count in success_list)
            self.stdout.write(f'总新增: {total_saved} 条K线')

        if failed_list:
            self.stdout.write(self.style.WARNING('\n失败列表:'))
            for symbol, error in failed_list:
                self.stdout.write(f'  - {symbol}: {error}')

        self.stdout.write('')
