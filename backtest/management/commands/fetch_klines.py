"""
数据获取管理命令
Fetch KLines Command
"""
import logging
from django.core.management.base import BaseCommand

from backtest.services.data_fetcher import DataFetcher
from backtest.services.data_validator import DataValidator

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '从币安获取历史K线数据并存储到数据库'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol', '-s',
            type=str,
            required=True,
            help='交易对，如: ETHUSDT, BTCUSDT'
        )
        parser.add_argument(
            '--interval', '-i',
            type=str,
            required=True,
            help='时间周期，如: 1h, 4h, 1d'
        )
        parser.add_argument(
            '--days', '-d',
            type=int,
            default=180,
            help='获取天数，默认180天（6个月）'
        )
        parser.add_argument(
            '--validate',
            action='store_true',
            help='获取后验证数据'
        )

    def handle(self, *args, **options):
        symbol = options['symbol'].upper()
        interval = options['interval']
        days = options['days']
        validate = options['validate']

        self.stdout.write(f"\n{'='*80}")
        self.stdout.write(self.style.SUCCESS(f"数据获取: {symbol} {interval}"))
        self.stdout.write(f"时间范围: {days}天")
        self.stdout.write(f"{'='*80}\n")

        try:
            # 1. 获取数据
            fetcher = DataFetcher(symbol, interval)
            saved_count = fetcher.fetch_historical_data(days=days)

            self.stdout.write(
                self.style.SUCCESS(f"✓ 数据获取成功: 新增{saved_count}条K线")
            )

            # 2. 验证数据（可选）
            if validate:
                self.stdout.write("\n验证数据...")
                validator = DataValidator()
                is_valid, errors = validator.validate_klines(symbol, interval)

                if is_valid:
                    self.stdout.write(self.style.SUCCESS("✓ 数据验证通过"))
                else:
                    self.stdout.write(
                        self.style.WARNING(f"⚠ 数据验证发现{len(errors)}个问题:")
                    )
                    for error in errors[:10]:  # 只显示前10个
                        self.stdout.write(f"  - {error}")

            self.stdout.write(f"\n{'='*80}")
            self.stdout.write(self.style.SUCCESS("数据获取完成"))
            self.stdout.write(f"{'='*80}\n")

        except Exception as e:
            logger.exception("数据获取失败")
            self.stderr.write(self.style.ERROR(f"✗ 错误: {e}"))
