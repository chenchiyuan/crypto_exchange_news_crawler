"""
数据更新管理命令
Update KLines Command

功能增强 (迭代003):
    - 支持批量更新所有active合约（不指定--symbol时）
    - 默认获取2000条K线（4h周期约一年数据）
    - 支持强制更新模式（--force删除旧数据）
    - 保持向后兼容（--symbol参数仍可用）
    - 支持现货/合约市场分离（--market-type）

市场类型说明:
    - futures: 合约市场（默认），使用 https://fapi.binance.com API
    - spot: 现货市场，使用 https://api.binance.com API

使用示例:
    # 更新单个合约
    python manage.py update_klines --symbol BTCUSDT --interval 4h --market-type futures

    # 更新单个现货
    python manage.py update_klines --symbol ETHUSDT --interval 4h --market-type spot

    # 批量更新所有合约（默认）
    python manage.py update_klines --interval 4h

    # 批量更新所有现货
    python manage.py update_klines --interval 4h --market-type spot

Related:
    - PRD: docs/iterations/003-klines-batch-update/prd.md
    - Architecture: docs/iterations/003-klines-batch-update/architecture.md
    - Tasks: docs/iterations/003-klines-batch-update/tasks.md
"""
import logging
from django.core.management.base import BaseCommand

from backtest.services.data_fetcher import DataFetcher

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '增量更新K线数据（支持批量更新所有合约）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol', '-s',
            type=str,
            required=False,  # 修改：改为可选
            help='交易对，不指定则更新所有active合约'
        )
        parser.add_argument(
            '--interval', '-i',
            type=str,
            required=True,
            choices=['1h', '4h', '1d'],
            help='K线周期（1h/4h/1d）'
        )
        parser.add_argument(
            '--market-type', '-m',
            type=str,
            default='futures',
            choices=['spot', 'futures'],
            help='市场类型（现货spot或合约futures），默认futures'
        )
        parser.add_argument(
            '--limit', '-l',
            type=int,
            default=2000,  # 修改：默认值从100改为2000
            help='获取最新N条，默认2000（4h周期约一年数据）'
        )
        parser.add_argument(
            '--force', '-f',
            action='store_true',
            default=False,
            help='强制更新（删除旧数据并重新获取）'
        )

    def handle(self, *args, **options):
        symbol = options.get('symbol')  # 修改：使用get()获取可选参数
        interval = options['interval']
        market_type = options['market_type']
        limit = options['limit']
        force = options['force']

        if symbol:
            # 单个交易对更新（向后兼容）
            self._update_single_symbol(symbol, interval, market_type, limit, force, show_output=True)
        else:
            # 批量更新所有合约
            self._update_all_symbols(interval, market_type, limit, force)

    def _update_single_symbol(
        self,
        symbol: str,
        interval: str,
        market_type: str,
        limit: int,
        force: bool = False,
        show_output: bool = True
    ) -> int:
        """更新单个交易对的K线数据。

        Args:
            symbol: 交易对代码（如BTCUSDT或BTC/USDT）
            interval: K线周期（1h/4h/1d）
            market_type: 市场类型（现货spot或合约futures）
            limit: 获取数量
            force: 是否强制更新（删除旧数据）
            show_output: 是否显示详细输出（批量更新时为False）

        Returns:
            int: 新增的K线数量

        Side Effects:
            - 查询/删除KLine数据
            - 调用Binance API
            - 输出进度信息（如果show_output=True）

        Raises:
            Exception: API请求失败、数据库操作失败等
        """
        from backtest.models import KLine

        symbol = symbol.upper()

        # 市场类型显示
        market_label = '合约' if market_type == 'futures' else '现货'

        if show_output:
            self.stdout.write(f"更新数据: {symbol} {interval} ({market_label})...")

        # 强制更新：删除旧数据
        if force:
            deleted_count = KLine.objects.filter(
                symbol=symbol,
                interval=interval,
                market_type=market_type
            ).delete()[0]

            if show_output:
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠️  强制更新模式：已删除 {deleted_count} 条历史数据"
                    )
                )

        # 创建DataFetcher实例
        fetcher = DataFetcher(symbol, interval, market_type)

        # 根据limit选择更新方法
        if limit > 1000:
            # 使用fetch_historical_data()分批获取
            days = self._calculate_days(interval, limit)
            saved_count = fetcher.fetch_historical_data(days=days)
        else:
            # 使用update_latest_data()增量更新
            saved_count = fetcher.update_latest_data(limit=limit)

        if show_output:
            self.stdout.write(
                self.style.SUCCESS(f"✓ 更新完成: 新增{saved_count}条")
            )

        return saved_count

    def _update_all_symbols(self, interval: str, market_type: str, limit: int, force: bool):
        """批量更新所有活跃合约或现货。

        Args:
            interval: K线周期（1h/4h/1d）
            market_type: 市场类型（现货spot或合约futures）
            limit: 每个交易对获取的数量
            force: 是否强制更新（删除旧数据）

        Side Effects:
            - 查询FuturesContract或SpotContract模型
            - 调用_update_single_symbol()更新每个交易对
            - 输出进度和统计信息
        """
        from monitor.models import FuturesContract, SpotContract
        import time

        # 根据market_type查询对应的交易对
        if market_type == 'futures':
            contracts = FuturesContract.objects.filter(status='active').order_by('symbol')
            contract_type_name = '活跃合约'
            fetch_cmd = 'fetch_futures'
        elif market_type == 'spot':
            contracts = SpotContract.objects.filter(status='active').order_by('symbol')
            contract_type_name = '活跃现货交易对'
            fetch_cmd = 'fetch_spot_contracts'
        else:
            raise ValueError(f"无效的market_type: {market_type}")

        total = contracts.count()

        # 检查交易对数据是否为空
        if total == 0:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️  未找到任何{contract_type_name}数据。\n"
                    f"请先运行以下命令初始化{fetch_cmd}数据:\n"
                    f"  python manage.py {fetch_cmd} --all\n"
                    f"或指定特定交易所:\n"
                    f"  python manage.py {fetch_cmd} --exchange binance"
                )
            )
            return  # 提前退出，不执行后续逻辑

        self.stdout.write(
            f"正在更新所有{contract_type_name}的K线数据 (interval={interval}, market_type={market_type}, limit={limit})..."
        )
        self.stdout.write(f"找到 {total} 个{contract_type_name}\n")

        # 统计信息
        success_count = 0
        failed_list = []
        start_time = time.time()

        # 遍历每个交易对
        for idx, contract in enumerate(contracts, start=1):
            try:
                saved_count = self._update_single_symbol(
                    symbol=contract.symbol,
                    interval=interval,
                    market_type=market_type,
                    limit=limit,
                    force=force,
                    show_output=False
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"[{idx}/{total}] {contract.symbol}: ✓ 新增 {saved_count} 条"
                    )
                )
                success_count += 1

            except Exception as e:
                error_msg = str(e)
                logger.error(f"更新{contract.symbol}失败: {error_msg}", exc_info=True)
                self.stdout.write(
                    self.style.ERROR(
                        f"[{idx}/{total}] {contract.symbol}: ✗ 错误: {error_msg}"
                    )
                )
                failed_list.append((contract.symbol, error_msg))

            # 延迟控制（避免API限流）
            if idx < total:
                time.sleep(0.1)

        # 显示统计信息
        elapsed = time.time() - start_time
        self.stdout.write("\n=== 更新完成 ===")
        self.stdout.write(f"  成功: {success_count} 个")
        self.stdout.write(f"  失败: {len(failed_list)} 个")
        self.stdout.write(f"  总耗时: {self._format_time(elapsed)}")

        if failed_list:
            self.stdout.write("\n失败列表:")
            for symbol, error in failed_list:
                self.stdout.write(f"  - {symbol}: {error}")

    def _calculate_days(self, interval: str, limit: int) -> int:
        """根据interval和limit计算需要的天数。

        Args:
            interval: K线周期（1h/4h/1d）
            limit: K线数量

        Returns:
            int: 需要获取的天数

        Examples:
            >>> _calculate_days('4h', 2000)
            334  # (2000 // 6) + 1
            >>> _calculate_days('1h', 2000)
            84   # (2000 // 24) + 1
        """
        interval_map = {
            '1h': 24,   # 每天24根
            '4h': 6,    # 每天6根
            '1d': 1,    # 每天1根
        }

        bars_per_day = interval_map.get(interval, 6)
        days = (limit // bars_per_day) + 1  # 向上取整+1天缓冲

        return days

    def _format_time(self, seconds: float) -> str:
        """格式化耗时。

        Args:
            seconds: 秒数

        Returns:
            str: 格式化后的时间字符串

        Examples:
            >>> _format_time(30)
            '30.0秒'
            >>> _format_time(150)
            '2分30秒'
            >>> _format_time(3720)
            '1小时2分钟'
        """
        if seconds < 60:
            return f"{seconds:.1f}秒"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{int(minutes)}分{int(secs)}秒"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{int(hours)}小时{int(minutes)}分钟"
