"""
数据更新管理命令
Update KLines Command
"""
import logging
from django.core.management.base import BaseCommand

from backtest.services.data_fetcher import DataFetcher

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '增量更新K线数据'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol', '-s',
            type=str,
            required=True,
            help='交易对'
        )
        parser.add_argument(
            '--interval', '-i',
            type=str,
            required=True,
            help='时间周期'
        )
        parser.add_argument(
            '--limit', '-l',
            type=int,
            default=100,
            help='获取最新N条，默认100'
        )

    def handle(self, *args, **options):
        symbol = options['symbol'].upper()
        interval = options['interval']
        limit = options['limit']

        self.stdout.write(f"更新数据: {symbol} {interval}...")

        try:
            fetcher = DataFetcher(symbol, interval)
            saved_count = fetcher.update_latest_data(limit=limit)

            self.stdout.write(
                self.style.SUCCESS(f"✓ 更新完成: 新增{saved_count}条")
            )

        except Exception as e:
            logger.exception("数据更新失败")
            self.stderr.write(self.style.ERROR(f"✗ 错误: {e}"))
