"""
Django管理命令：一键监控合约数据
集成数据获取和新合约通知功能
"""
import sys
import time
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from monitor.services.futures_fetcher import FuturesFetcherService
from monitor.services.futures_notifier import FuturesNotifierService


class Command(BaseCommand):
    help = '一键监控合约数据：获取最新数据并检测新合约上线'

    def add_arguments(self, parser):
        """添加命令参数"""
        parser.add_argument(
            '--exchange',
            type=str,
            help='指定交易所（binance, bybit, hyperliquid, all）',
            choices=['binance', 'bybit', 'hyperliquid', 'all'],
            default='all'
        )
        parser.add_argument(
            '--skip-notification',
            action='store_true',
            help='跳过新合约通知（仅用于测试）',
            default=False
        )
        parser.add_argument(
            '--test',
            action='store_true',
            help='测试模式 - 不保存到数据库，不发送通知',
            default=False
        )
        parser.add_argument(
            '--mark-initial-complete',
            action='store_true',
            help='标记初始部署已完成（用于生产环境首次部署后）',
            default=False
        )

    def handle(self, *args, **options):
        """处理命令执行"""
        start_time = time.time()

        # 解析参数
        self.verbosity = options.get('verbosity', 1)
        exchange = options['exchange']
        skip_notification = options['skip_notification']
        self.test_mode = options.get('test', False)
        mark_initial = options['mark_initial_complete']

        # 显示启动信息
        self._print_banner(exchange, skip_notification, self.test_mode)

        # 处理初始部署标记
        if mark_initial:
            self._mark_initial_deployment()
            return

        # 初始化服务
        fetcher = FuturesFetcherService()
        notifier = FuturesNotifierService()

        try:
            # 数据获取
            self.stdout.write("\n📡 正在获取合约数据...")

            # 解析交易所参数
            if exchange == 'all':
                exchange_codes = list(fetcher.clients.keys())
            else:
                exchange_codes = [exchange]

            # 获取数据并保存到数据库
            results = {}
            for exchange_code in exchange_codes:
                try:
                    self.stdout.write(
                        f"\n📡 正在获取 {exchange_code.upper()} 数据..."
                    )

                    if self.test_mode:
                        # 测试模式：只获取数据，不保存
                        client = fetcher.clients[exchange_code]
                        contracts = client.fetch_contracts()
                        results[exchange_code] = len(contracts)

                        if contracts:
                            self.stdout.write(
                                f"  ✓ 成功获取 {len(contracts)} 个合约"
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
                            results[exchange_code] = stats['saved']
                            self.stdout.write(
                                f"  ✓ 成功: 新增 {stats['new']}, 更新 {stats['updated']}, 下线 {stats['delisted']}"
                            )
                        else:
                            error = result[exchange_code]['error']
                            self.stdout.write(
                                self.style.ERROR(f"  ✗ 失败: {error}")
                            )
                            results[exchange_code] = 0

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  ✗ 处理 {exchange_code} 时发生错误: {str(e)}")
                    )
                    if self.verbosity > 1:
                        import traceback
                        traceback.print_exc()
                    results[exchange_code] = 0

            # 显示获取结果
            self._print_fetch_results(results)

            # 跳过通知
            if skip_notification or self.test_mode:
                if self.test_mode:
                    self.stdout.write(self.style.WARNING('\n⚠️  测试模式 - 跳过通知发送'))
                else:
                    self.stdout.write(self.style.WARNING('\n⚠️  已跳过通知发送'))
            else:
                # 检测并发送新合约通知
                self.stdout.write("\n🔍 正在检测新合约上线...")
                self._send_new_listing_notifications(notifier, results)

            # 显示执行摘要
            execution_time = time.time() - start_time
            self._print_summary(results, execution_time)

        except Exception as e:
            self.stderr.write(self.style.ERROR(f'\n❌ 执行过程中发生错误: {str(e)}'))
            raise

    def _print_banner(self, exchange: str, skip_notification: bool, test_mode: bool):
        """打印启动横幅"""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("🚀  合约监控系统启动")
        self.stdout.write("=" * 60)

        if test_mode:
            self.stdout.write(self.style.WARNING("⚠️  测试模式 - 不保存到数据库，不发送通知"))

        self.stdout.write(f"\n📋 配置信息:")
        self.stdout.write(f"  - 目标交易所: {exchange.upper()}")
        self.stdout.write(f"  - 通知功能: {'已禁用' if skip_notification else '已启用'}")
        self.stdout.write("=" * 60 + "\n")

    def _print_fetch_results(self, results: dict):
        """显示数据获取结果"""
        self.stdout.write("\n📊 数据获取结果:")

        for exchange_name, contract_count in results.items():
            if contract_count > 0:
                self.stdout.write(f"  ✓ {exchange_name.upper()}: {contract_count} 个合约")
            else:
                self.stdout.write(self.style.WARNING(f"  ⚠️  {exchange_name.upper()}: 0 个合约"))

    def _send_new_listing_notifications(self, notifier: FuturesNotifierService, results: dict):
        """发送新合约上线通知"""
        try:
            # 获取所有新合约（从结果中提取）
            all_contracts = []
            for exchange_name in results.keys():
                # 重新获取该交易所的合约用于检测新合约
                # 注意：这里需要从fetcher的结果中提取
                # 为了简化，我们在发送通知时检测数据库中的新记录

                # 这里暂时使用一个简单的方法：检测最近5分钟内创建的合约
                pass

            # 改进：直接从数据库检测新合约
            from monitor.models import FuturesContract
            from django.utils import timezone
            from datetime import timedelta

            # 查找最近5分钟内的合约（可能是新上线）
            new_contracts = FuturesContract.objects.filter(
                first_seen__gte=timezone.now() - timedelta(minutes=5),
                status=FuturesContract.ACTIVE
            )

            if not new_contracts.exists():
                self.stdout.write("  ✓ 未检测到新合约上线")
                return

            # 检测新合约（过滤已发送过通知的）
            contracts_to_notify = []
            for contract in new_contracts:
                from monitor.models import FuturesListingNotification
                existing = FuturesListingNotification.objects.filter(
                    futures_contract=contract,
                    status=FuturesListingNotification.SUCCESS
                ).exists()
                if not existing:
                    contracts_to_notify.append(contract)

            if not contracts_to_notify:
                self.stdout.write("  ✓ 未检测到需要通知的新合约")
                return

            # 发送通知
            self.stdout.write(f"  📢 检测到 {len(contracts_to_notify)} 个新合约，开始发送通知...")

            stats = notifier.send_new_listing_notifications(contracts_to_notify)

            # 显示通知结果
            self.stdout.write(f"  ✓ 通知发送完成: 成功 {stats['success']}, 失败 {stats['failed']}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ❌ 通知发送失败: {str(e)}"))
            import traceback
            self.stdout.write(traceback.format_exc())

    def _print_summary(self, results: dict, execution_time: float):
        """显示执行摘要"""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("📊 执行摘要")
        self.stdout.write("=" * 60)

        total_contracts = sum(results.values())
        exchanges = ', '.join([k.upper() for k in results.keys()])

        self.stdout.write(f"  处理交易所: {exchanges}")
        self.stdout.write(f"  合约总数: {total_contracts}")
        self.stdout.write(f"  执行时间: {execution_time:.2f} 秒")

        if not self.test_mode:
            self.stdout.write(f"  数据保存: 已保存到数据库")
        else:
            self.stdout.write(self.style.WARNING(f"  数据保存: 测试模式（未保存）"))

        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("\n✅ 执行完成"))
        self.stdout.write("=" * 60)

    def _mark_initial_deployment(self):
        """标记初始部署已完成"""
        fetcher = FuturesFetcherService()
        fetcher.mark_initial_deployment_completed()
        self.stdout.write(self.style.SUCCESS('\n✅ 已标记初始部署完成'))
        self.stdout.write('此后系统将开始发送新合约上线通知')
