"""
scan_ddps 管理命令

计算指定交易对的DDPS指标（动态偏离概率空间）。

Usage:
    python manage.py scan_ddps BTCUSDT
    python manage.py scan_ddps BTCUSDT --interval 1h
    python manage.py scan_ddps BTCUSDT ETHUSDT --verbose

Related:
    - PRD: docs/iterations/009-ddps-z-probability-engine/prd.md
    - TASK: TASK-009-012
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from ddps_z.services.ddps_service import DDPSService


class Command(BaseCommand):
    help = '计算指定交易对的DDPS指标（动态偏离概率空间）'

    def add_arguments(self, parser):
        parser.add_argument(
            'symbols',
            nargs='+',
            type=str,
            help='交易对符号，如BTCUSDT、ETHUSDT（可指定多个）'
        )
        parser.add_argument(
            '--interval',
            type=str,
            default=settings.DDPS_CONFIG['DEFAULT_INTERVAL'],
            help=f'K线周期（默认: {settings.DDPS_CONFIG["DEFAULT_INTERVAL"]}）'
        )
        parser.add_argument(
            '--market-type',
            type=str,
            default='futures',
            choices=['futures', 'spot'],
            help='市场类型（默认: futures）'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='显示详细信息'
        )

    def handle(self, *args, **options):
        symbols = [s.upper() for s in options['symbols']]
        interval = options['interval']
        market_type = options['market_type']
        verbose = options['verbose']

        service = DDPSService()

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\n=== DDPS-Z 动态偏离概率空间 ===\n'
        ))
        self.stdout.write(f'周期: {interval}')
        self.stdout.write(f'市场: {market_type}')
        self.stdout.write(f'交易对: {", ".join(symbols)}\n')

        success_count = 0
        fail_count = 0

        for symbol in symbols:
            self.stdout.write(self.style.MIGRATE_LABEL(f'\n--- {symbol} ---'))

            result = service.calculate(symbol, interval, market_type)

            if result['success']:
                success_count += 1
                data = result['data']

                # 根据区间选择颜色
                zone = data['zone']
                if zone in ['extreme_oversold', 'oversold']:
                    zone_style = self.style.ERROR  # 红色
                elif zone in ['extreme_overbought', 'overbought']:
                    zone_style = self.style.SUCCESS  # 绿色
                else:
                    zone_style = self.style.WARNING  # 黄色

                self.stdout.write(f'当前价格: {data["current_price"]:.4f}')
                self.stdout.write(f'EMA({settings.DDPS_CONFIG["EMA_PERIOD"]}): {data["current_ema"]:.4f}')
                self.stdout.write(f'偏离率: {data["current_deviation"]:.2%}')
                self.stdout.write(f'Z-Score: {data["zscore"]:.4f}')
                self.stdout.write(f'百分位: {data["percentile"]:.2f}%')
                self.stdout.write(zone_style(f'区间: {data["zone_label"]}'))

                if data['rvol']:
                    self.stdout.write(f'RVOL: {data["rvol"]:.2f}x')

                # 信号
                signal = data['signal']
                if signal['strength'] == 'strong':
                    self.stdout.write(self.style.SUCCESS(f'信号: {signal["description"]}'))
                elif signal['strength'] == 'weak':
                    self.stdout.write(self.style.WARNING(f'信号: {signal["description"]}'))
                else:
                    self.stdout.write(f'信号: {signal["description"]}')

                if verbose:
                    self.stdout.write(f'EWMA均值: {data["ewma_mean"]:.4%}')
                    self.stdout.write(f'EWMA标准差: {data["ewma_std"]:.4%}')
                    self.stdout.write(f'K线数量: {data["kline_count"]}')

            else:
                fail_count += 1
                self.stdout.write(self.style.ERROR(f'计算失败: {result["error"]}'))

        # 汇总
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\n=== 汇总 ===\n'
        ))
        self.stdout.write(f'成功: {success_count}')
        self.stdout.write(f'失败: {fail_count}')

        if fail_count > 0:
            self.stdout.write(self.style.WARNING(
                '\n提示: 失败可能是因为K线数据不足，请确保已同步足够的历史数据'
            ))
