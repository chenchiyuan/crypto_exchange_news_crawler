"""
Django管理命令: update_futures_prices

专门用于定期更新合约价格和市场指标的后台任务命令
设计用于cron/systemd timer调度，输出简洁，日志完善
"""
import sys
import logging
from typing import List
from django.core.management.base import BaseCommand
from django.utils import timezone

from monitor.services.futures_fetcher import FuturesFetcherService
from monitor.models import Exchange

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """定期更新合约价格和市场指标"""

    help = "定期更新所有交易所的合约价格和市场指标（适用于cron调度）"

    def add_arguments(self, parser):
        """添加命令行参数"""
        parser.add_argument(
            '--exchange',
            type=str,
            choices=['binance', 'hyperliquid', 'bybit'],
            help='仅更新指定交易所（默认：所有）'
        )
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='静默模式：仅在错误时输出（适合cron）'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='测试运行：获取数据但不保存到数据库'
        )

    def handle(self, *args, **options):
        """执行价格更新任务"""
        start_time = timezone.now()
        quiet = options.get('quiet', False)
        dry_run = options.get('dry_run', False)

        # 确定要更新的交易所
        fetcher = FuturesFetcherService()
        if options.get('exchange'):
            exchange_codes = [options['exchange']]
        else:
            exchange_codes = list(fetcher.clients.keys())

        # 开始日志
        logger.info(f"开始定期更新任务 - 交易所: {', '.join(exchange_codes)}")
        if not quiet:
            self.stdout.write(f"🔄 开始更新合约价格 ({', '.join(exchange_codes).upper()})")

        if dry_run:
            logger.info("测试模式 - 不保存到数据库")
            if not quiet:
                self.stdout.write(self.style.WARNING("⚠️  测试模式"))

        # 验证交易所存在
        for exchange_code in exchange_codes:
            try:
                Exchange.objects.get(code=exchange_code)
            except Exchange.DoesNotExist:
                error_msg = f"交易所 {exchange_code} 不存在于数据库中"
                logger.error(error_msg)
                self.stderr.write(self.style.ERROR(f"❌ {error_msg}"))
                sys.exit(1)

        # 执行更新
        total_saved = 0
        total_new = 0
        total_updated = 0
        total_delisted = 0
        total_indicators = 0
        failed_exchanges = []

        for exchange_code in exchange_codes:
            try:
                logger.info(f"正在更新 {exchange_code} 数据...")

                if dry_run:
                    # 测试模式：仅获取，不保存
                    client = fetcher.clients[exchange_code]
                    contracts = client.fetch_contracts_with_indicators()
                    logger.info(f"{exchange_code} 测试获取: {len(contracts)} 个合约")
                    total_saved += len(contracts)
                else:
                    # 正常模式：获取并保存
                    result = fetcher.update_exchanges_manually([exchange_code])

                    if result[exchange_code]['status'] == 'success':
                        stats = result[exchange_code]
                        total_saved += stats['saved']
                        total_new += stats['new']
                        total_updated += stats['updated']
                        total_delisted += stats['delisted']
                        total_indicators += stats.get('indicators_saved', 0)

                        logger.info(
                            f"{exchange_code} 更新成功: "
                            f"新增={stats['new']}, 更新={stats['updated']}, "
                            f"下线={stats['delisted']}, 指标={stats.get('indicators_saved', 0)}"
                        )
                    else:
                        error = result[exchange_code]['error']
                        logger.error(f"{exchange_code} 更新失败: {error}")
                        failed_exchanges.append(exchange_code)
                        self.stderr.write(
                            self.style.ERROR(f"❌ {exchange_code}: {error}")
                        )

            except Exception as e:
                logger.exception(f"{exchange_code} 处理异常: {str(e)}")
                failed_exchanges.append(exchange_code)
                self.stderr.write(
                    self.style.ERROR(f"❌ {exchange_code}: {str(e)}")
                )

        # 计算执行时间
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()

        # 记录结果摘要
        success_count = len(exchange_codes) - len(failed_exchanges)
        summary = (
            f"更新完成 - "
            f"成功={success_count}/{len(exchange_codes)}, "
            f"合约={total_saved}, "
            f"新增={total_new}, "
            f"更新={total_updated}, "
            f"下线={total_delisted}, "
            f"指标={total_indicators}, "
            f"耗时={duration:.2f}秒"
        )
        logger.info(summary)

        # 输出结果（非静默模式）
        if not quiet or failed_exchanges:
            if failed_exchanges:
                self.stdout.write(
                    self.style.ERROR(
                        f"⚠️  部分失败: {', '.join(failed_exchanges)}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ {summary}"
                    )
                )

        # 返回退出码
        if failed_exchanges:
            logger.warning(f"任务完成但有失败: {failed_exchanges}")
            sys.exit(1)  # 有失败则返回非0退出码
        else:
            logger.info("任务完成，所有交易所更新成功")
            sys.exit(0)  # 全部成功则返回0
