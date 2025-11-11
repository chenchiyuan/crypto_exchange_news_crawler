"""
Django管理命令: fetch_futures

手动获取合约数据，支持指定交易所和详细输出
"""
import sys
from typing import List, Optional
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from monitor.services.futures_fetcher import FuturesFetcherService
from monitor.models import Exchange


class Command(BaseCommand):
    """获取合约数据的Django管理命令"""

    help = "手动获取合约数据从指定交易所"

    def add_arguments(self, parser):
        """添加命令行参数"""
        parser.add_argument(
            '--exchange',
            type=str,
            choices=['binance', 'hyperliquid', 'bybit'],
            help='指定要获取数据的交易所代码'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='获取所有交易所的数据'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='详细输出'
        )
        parser.add_argument(
            '--test',
            action='store_true',
            help='测试模式（不保存到数据库，仅打印结果）'
        )

    def handle(self, *args, **options):
        """处理命令执行"""
        # 初始化
        self.verbosity = options.get('verbosity', 1)
        self.test_mode = options.get('test', False)
        verbose = options.get('verbose', False)

        # 输出信息
        self.stdout.write(
            self.style.SUCCESS("🚀 开始获取合约数据")
        )

        # 初始化服务
        fetcher = FuturesFetcherService()

        # 解析交易所参数
        if options.get('all'):
            exchange_codes = list(fetcher.clients.keys())
        elif options.get('exchange'):
            exchange_codes = [options['exchange']]
        else:
            # 没有指定交易所，提示用户选择
            self.stdout.write(self.style.WARNING("未指定交易所，请选择:"))
            self.stdout.write("  1. --exchange binance")
            self.stdout.write("  2. --exchange hyperliquid")
            self.stdout.write("  3. --exchange bybit")
            self.stdout.write("  4. --all (获取所有交易所)")
            self.stdout.write("例如: python manage.py fetch_futures --exchange binance")
            return

        # 检查交易所是否有效
        invalid_exchanges = [code for code in exchange_codes if code not in fetcher.clients]
        if invalid_exchanges:
            raise CommandError(f"无效的交易所代码: {', '.join(invalid_exchanges)}")

        # 检查数据库中的交易所
        for exchange_code in exchange_codes:
            try:
                Exchange.objects.get(code=exchange_code)
            except Exchange.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"交易所 {exchange_code} 不存在于数据库中")
                )
                self.stdout.write(
                    self.style.WARNING(f"请先在Django Admin中创建交易所: {exchange_code}")
                )
                return

        # 获取数据
        total_saved = 0
        total_errors = 0
        start_time = timezone.now()

        if self.test_mode:
            self.stdout.write(
                self.style.WARNING("⚠️  测试模式 - 不保存到数据库")
            )

        for exchange_code in exchange_codes:
            try:
                self.stdout.write(
                    f"\n📡 正在获取 {exchange_code.upper()} 数据..."
                )

                if self.test_mode:
                    # 测试模式：只获取数据，不保存
                    client = fetcher.clients[exchange_code]
                    contracts = client.fetch_contracts()

                    if contracts:
                        self.stdout.write(
                            f"  ✓ 成功获取 {len(contracts)} 个合约"
                        )
                        if verbose:
                            for contract in contracts[:5]:  # 只显示前5个
                                self.stdout.write(
                                    f"    - {contract['symbol']}: ${contract['current_price']}"
                                )
                            if len(contracts) > 5:
                                self.stdout.write(
                                    f"    ... 还有 {len(contracts) - 5} 个合约"
                                )
                    else:
                        self.stdout.write(
                            self.style.WARNING("  ⚠️  未获取到任何合约数据")
                        )
                else:
                    # 正常模式：获取并保存
                    result = fetcher.update_exchanges_manually([exchange_code])

                    if result[exchange_code]['status'] == 'success':
                        stats = result[exchange_code]
                        self.stdout.write(
                            f"  ✓ 成功: 新增 {stats['new']}, 更新 {stats['updated']}, 下线 {stats['delisted']}"
                        )
                        total_saved += stats['saved']
                    else:
                        error = result[exchange_code]['error']
                        self.stdout.write(
                            self.style.ERROR(f"  ✗ 失败: {error}")
                        )
                        total_errors += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  ✗ 处理 {exchange_code} 时发生错误: {str(e)}")
                )
                if self.verbosity > 1:
                    import traceback
                    traceback.print_exc()
                total_errors += 1

        # 输出结果摘要
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("📊 执行摘要"))
        self.stdout.write(f"  处理交易所: {', '.join(exchange_codes)}")
        if not self.test_mode:
            self.stdout.write(f"  保存合约: {total_saved}")
            self.stdout.write(f"  错误数量: {total_errors}")
        self.stdout.write(f"  执行时间: {duration:.2f} 秒")
        self.stdout.write("=" * 50)

        # 返回适当的退出码
        if total_errors > 0 and not self.test_mode:
            self.stdout.write(
                self.style.ERROR("⚠️  部分交易所处理失败")
            )
            sys.exit(1)
        else:
            self.stdout.write(
                self.style.SUCCESS("✅ 执行完成")
            )
