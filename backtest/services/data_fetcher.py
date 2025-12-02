"""
数据获取服务
Data Fetcher Service
"""
import logging
import time
from typing import List
from datetime import timedelta
from django.utils import timezone

from vp_squeeze.services.binance_kline_service import fetch_klines
from vp_squeeze.dto import KLineData
from backtest.models import KLine

logger = logging.getLogger(__name__)


class DataFetcher:
    """历史数据获取器"""

    def __init__(self, symbol: str, interval: str):
        """
        初始化

        Args:
            symbol: 交易对，如'ETHUSDT'
            interval: 时间周期，如'4h'
        """
        self.symbol = symbol.upper()
        self.interval = interval

    def fetch_historical_data(
        self,
        days: int = 180,
        batch_size: int = 1000
    ) -> int:
        """
        获取历史数据并存储到数据库（支持分批获取）

        Args:
            days: 获取天数
            batch_size: 每批最大数量，默认1000（币安API限制）

        Returns:
            int: 新增数据条数
        """
        logger.info(
            f"开始获取历史数据: {self.symbol} {self.interval}, "
            f"天数={days}"
        )

        # 计算需要的K线数量
        interval_map = {
            '1h': 24,
            '4h': 6,
            '1d': 1,
        }
        bars_per_day = interval_map.get(self.interval, 6)
        total_bars_needed = days * bars_per_day

        logger.info(
            f"预计需要获取 {total_bars_needed} 根K线 "
            f"({days}天 × {bars_per_day}根/天)"
        )

        # 如果需要的数据量超过单次限制，需要分批获取
        if total_bars_needed <= batch_size:
            # 单次获取即可
            return self._fetch_single_batch(total_bars_needed)
        else:
            # 分批获取
            return self._fetch_multiple_batches(total_bars_needed, batch_size)

    def _fetch_single_batch(self, limit: int) -> int:
        """
        单次获取数据

        Args:
            limit: 获取数量

        Returns:
            int: 新增数据条数
        """
        kline_data_list = fetch_klines(
            symbol=self.symbol,
            interval=self.interval,
            limit=limit
        )

        logger.info(f"从币安获取 {len(kline_data_list)} 条K线数据")
        saved_count = self._save_klines(kline_data_list)

        logger.info(f"数据获取完成: 新增{saved_count}条")
        return saved_count

    def _fetch_multiple_batches(
        self,
        total_needed: int,
        batch_size: int
    ) -> int:
        """
        分批获取历史数据

        Args:
            total_needed: 总共需要的数量
            batch_size: 每批数量

        Returns:
            int: 新增数据条数
        """
        all_klines = []
        total_saved = 0
        batches = (total_needed + batch_size - 1) // batch_size  # 向上取整

        logger.info(f"需要分 {batches} 批次获取数据")

        # 从最新数据开始获取
        end_time = None  # None表示获取最新数据

        for batch_idx in range(batches):
            remaining = total_needed - len(all_klines)
            current_limit = min(remaining, batch_size)

            logger.info(
                f"[批次 {batch_idx + 1}/{batches}] "
                f"获取 {current_limit} 条K线..."
            )

            try:
                # 获取数据
                kline_data_list = fetch_klines(
                    symbol=self.symbol,
                    interval=self.interval,
                    limit=current_limit,
                    end_time=end_time
                )

                if not kline_data_list:
                    logger.warning(f"批次 {batch_idx + 1} 未获取到数据，停止")
                    break

                logger.info(f"批次 {batch_idx + 1} 获取到 {len(kline_data_list)} 条K线")

                # 保存当前批次
                saved_count = self._save_klines(kline_data_list)
                total_saved += saved_count

                all_klines.extend(kline_data_list)

                # 如果这批数据不足，说明已经获取到最早的数据了
                if len(kline_data_list) < current_limit:
                    logger.info(f"已获取到所有可用的历史数据")
                    break

                # 更新end_time为当前批次最早的K线时间（减1毫秒，避免重复）
                earliest_kline = min(kline_data_list, key=lambda x: x.open_time)
                end_time = int(earliest_kline.open_time.timestamp() * 1000) - 1

                # 如果还有更多批次，等待1秒避免触发币安API限流
                if batch_idx < batches - 1:
                    time.sleep(1)

            except Exception as e:
                logger.error(f"批次 {batch_idx + 1} 获取失败: {e}")
                break

        logger.info(
            f"分批获取完成: 总共获取 {len(all_klines)} 条K线, "
            f"新增 {total_saved} 条"
        )

        return total_saved

    def _save_klines(self, kline_data_list: List[KLineData]) -> int:
        """
        保存K线数据到数据库

        Args:
            kline_data_list: KLineData列表

        Returns:
            int: 新增数据条数
        """
        new_klines = []

        for kline_data in kline_data_list:
            # 检查是否已存在（防止重复）
            exists = KLine.objects.filter(
                symbol=self.symbol,
                interval=self.interval,
                open_time=kline_data.open_time
            ).exists()

            if not exists:
                new_klines.append(KLine(
                    symbol=self.symbol,
                    interval=self.interval,
                    open_time=kline_data.open_time,
                    close_time=kline_data.close_time,
                    open_price=kline_data.open,
                    high_price=kline_data.high,
                    low_price=kline_data.low,
                    close_price=kline_data.close,
                    volume=kline_data.volume,
                    quote_volume=kline_data.quote_volume,
                    trade_count=kline_data.trade_count,
                    taker_buy_volume=kline_data.taker_buy_volume,
                    taker_buy_quote_volume=kline_data.taker_buy_quote_volume
                ))

        # 批量创建
        if new_klines:
            KLine.objects.bulk_create(new_klines, batch_size=500)
            logger.info(f"批量创建{len(new_klines)}条K线记录")

        return len(new_klines)

    def update_latest_data(self, limit: int = 100) -> int:
        """
        增量更新最新数据

        Args:
            limit: 获取最新N条

        Returns:
            int: 新增数据条数
        """
        logger.info(f"增量更新数据: {self.symbol} {self.interval}")

        # 获取最新数据
        kline_data_list = fetch_klines(
            symbol=self.symbol,
            interval=self.interval,
            limit=limit
        )

        # 保存
        saved_count = self._save_klines(kline_data_list)

        logger.info(f"增量更新完成: 新增{saved_count}条")
        return saved_count
