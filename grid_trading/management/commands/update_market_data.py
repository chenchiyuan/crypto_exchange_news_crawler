"""
市场数据更新命令
Update Market Data Command

用途:
- 更新合约基本信息 (SymbolInfo)
- 批量预热K线缓存 (KlineData)
- 定时任务：建议每天运行一次

设计理念:
- 职责单一：专注数据同步
- 批量操作：提升效率
- 增量更新：只更新变化的数据
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from decimal import Decimal
from datetime import datetime

from grid_trading.models import SymbolInfo, KlineData
from grid_trading.services.binance_futures_client import BinanceFuturesClient
from grid_trading.services.kline_cache import KlineCache

logger = logging.getLogger("grid_trading")


class Command(BaseCommand):
    """
    市场数据更新命令

    示例:
        # 更新合约信息
        python manage.py update_market_data

        # 更新合约信息 + 预热4小时K线缓存
        python manage.py update_market_data --warmup-klines --interval 4h

        # 只更新特定标的
        python manage.py update_market_data --symbols BTCUSDT,ETHUSDT
    """

    help = "更新合约信息和K线缓存数据"

    def add_arguments(self, parser):
        parser.add_argument(
            "--symbols",
            type=str,
            help="指定标的列表（逗号分隔，如BTCUSDT,ETHUSDT），不指定则更新全部",
        )

        parser.add_argument(
            "--warmup-klines",
            action="store_true",
            help="预热K线缓存（批量获取并保存K线数据）",
        )

        parser.add_argument(
            "--interval",
            type=str,
            default="4h",
            choices=["1m", "1h", "4h", "1d"],
            help="预热K线的时间周期（默认4h）",
        )

        parser.add_argument(
            "--limit",
            type=int,
            default=300,
            help="预热K线的数量（默认300根）",
        )

        parser.add_argument(
            "--min-volume",
            type=float,
            default=10000000,
            help="最小流动性阈值（USDT，默认10M，用于筛选需要预热的标的）",
        )

    def handle(self, *args, **options):
        self.stdout.write("=" * 70)
        self.stdout.write("🔄 市场数据更新任务")
        self.stdout.write("=" * 70)

        start_time = datetime.now()

        try:
            # ========== 初始化 ==========
            client = BinanceFuturesClient()
            specified_symbols = (
                options["symbols"].split(",") if options.get("symbols") else None
            )

            # ========== Step 1: 更新合约基本信息 ==========
            self.stdout.write("\n📥 步骤1: 更新合约基本信息")
            self.stdout.write("-" * 70)

            symbols_updated = self._update_symbol_info(
                client, specified_symbols=specified_symbols
            )

            self.stdout.write(
                self.style.SUCCESS(f"✓ 成功更新 {symbols_updated} 个合约信息")
            )

            # ========== Step 2: 预热K线缓存（可选） ==========
            if options.get("warmup_klines"):
                self.stdout.write("\n🔥 步骤2: 预热K线缓存")
                self.stdout.write("-" * 70)

                klines_cached = self._warmup_klines(
                    client,
                    interval=options["interval"],
                    limit=options["limit"],
                    min_volume=Decimal(str(options["min_volume"])),
                    specified_symbols=specified_symbols,
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ 成功预热 {klines_cached} 个标的的K线缓存"
                    )
                )

            # ========== 完成 ==========
            elapsed = (datetime.now() - start_time).total_seconds()

            self.stdout.write("\n" + "=" * 70)
            self.stdout.write(f"✅ 数据更新完成 (用时: {elapsed:.2f}秒)")
            self.stdout.write("=" * 70)

            # 显示统计信息
            self._print_stats()

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ 更新失败: {str(e)}"))
            import traceback

            self.stdout.write(traceback.format_exc())
            raise CommandError(f"数据更新失败: {str(e)}")

    def _update_symbol_info(
        self, client: BinanceFuturesClient, specified_symbols=None
    ) -> int:
        """
        更新合约基本信息到 SymbolInfo 表

        Returns:
            更新的合约数量
        """
        # 获取合约列表
        self.stdout.write("  获取合约列表...")
        exchange_info = client.fetch_exchange_info()

        if specified_symbols:
            exchange_info = [
                info for info in exchange_info if info["symbol"] in specified_symbols
            ]

        self.stdout.write(f"  获取到 {len(exchange_info)} 个合约")

        # 获取24小时ticker数据
        self.stdout.write("  获取24小时行情...")
        ticker_data = client.fetch_24h_ticker()

        # 获取资金费率
        self.stdout.write("  获取资金费率...")
        funding_data = client.fetch_funding_rate()

        # 批量更新数据库
        self.stdout.write("  批量更新数据库...")
        updated_count = 0

        with transaction.atomic():
            for info in exchange_info:
                symbol = info["symbol"]

                # 提取ticker数据
                ticker = ticker_data.get(symbol, {})
                funding = funding_data.get(symbol, {})

                # 获取或创建SymbolInfo
                symbol_info, created = SymbolInfo.objects.update_or_create(
                    symbol=symbol,
                    defaults={
                        "base_asset": symbol.replace("USDT", ""),  # 简化处理
                        "quote_asset": "USDT",
                        "contract_type": info.get("contractType", "PERPETUAL"),
                        "listing_date": datetime.fromtimestamp(
                            info["onboardDate"] / 1000
                        )
                        if info.get("onboardDate")
                        else None,
                        "current_price": Decimal(str(ticker.get("lastPrice", 0)))
                        if ticker.get("lastPrice")
                        else None,
                        "volume_24h": Decimal(str(ticker.get("volume", 0)))
                        * Decimal(str(ticker.get("lastPrice", 0)))
                        if ticker.get("volume") and ticker.get("lastPrice")
                        else None,
                        "funding_rate": Decimal(str(funding.get("lastFundingRate", 0)))
                        if funding.get("lastFundingRate")
                        else None,
                        "next_funding_time": datetime.fromtimestamp(
                            funding["nextFundingTime"] / 1000
                        )
                        if funding.get("nextFundingTime")
                        else None,
                        "is_active": True,
                    },
                )

                updated_count += 1

                if created:
                    self.stdout.write(f"    ✓ 新增: {symbol}")
                elif updated_count % 50 == 0:
                    self.stdout.write(
                        f"    处理中... ({updated_count}/{len(exchange_info)})"
                    )

        return updated_count

    def _warmup_klines(
        self,
        client: BinanceFuturesClient,
        interval: str,
        limit: int,
        min_volume: Decimal,
        specified_symbols=None,
    ) -> int:
        """
        预热K线缓存

        只预热流动性高的标的，避免浪费资源

        Returns:
            预热的标的数量
        """
        # 查询需要预热的标的
        queryset = SymbolInfo.objects.filter(is_active=True)

        if specified_symbols:
            queryset = queryset.filter(symbol__in=specified_symbols)
        else:
            # 按流动性筛选
            queryset = queryset.filter(volume_24h__gte=min_volume)

        symbols = list(queryset.values_list("symbol", flat=True))

        self.stdout.write(f"  准备预热 {len(symbols)} 个标的的K线数据")

        # 使用KlineCache批量获取并缓存
        cache = KlineCache(api_client=client)
        cached_count = 0

        for i, symbol in enumerate(symbols, 1):
            try:
                # 获取K线（会自动缓存）
                klines = cache.get_klines(symbol, interval=interval, limit=limit)

                if klines:
                    cached_count += 1

                # 进度提示
                if i % 50 == 0:
                    self.stdout.write(f"    进度: {i}/{len(symbols)} ({cached_count} 个已缓存)")

            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f"    ⚠️  {symbol} 缓存失败: {str(e)}")
                )
                continue

        return cached_count

    def _print_stats(self):
        """打印统计信息"""
        self.stdout.write("\n📊 数据统计:")
        self.stdout.write("-" * 70)

        # SymbolInfo统计
        total_symbols = SymbolInfo.objects.count()
        active_symbols = SymbolInfo.objects.filter(is_active=True).count()
        self.stdout.write(f"  合约总数: {total_symbols}")
        self.stdout.write(f"  活跃合约: {active_symbols}")

        # KlineData统计
        total_klines = KlineData.objects.count()
        kline_symbols = KlineData.objects.values("symbol").distinct().count()
        self.stdout.write(f"  K线总数: {total_klines:,} 根")
        self.stdout.write(f"  缓存标的: {kline_symbols} 个")

        # 估算大小
        if total_klines > 0:
            avg_size = 500  # 每条约500字节
            total_mb = total_klines * avg_size / 1024 / 1024
            self.stdout.write(f"  估算占用: {total_mb:.2f} MB")

        self.stdout.write("")
