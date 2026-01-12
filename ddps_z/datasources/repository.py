"""
K线数据仓库 - 统一的本地存取服务

负责从数据库加载K线并转换为标准格式，以及将标准K线保存到数据库。

Related:
    - Architecture: docs/iterations/024-ddps-multi-market-support/architecture.md
    - TASK: TASK-024-002
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from backtest.models import KLine
from ddps_z.models import StandardKLine, MarketType, Interval

logger = logging.getLogger(__name__)


class KLineRepository:
    """
    K线数据仓库 - 统一的本地存取服务

    职责：
    - 从数据库加载K线并转换为标准格式
    - 将标准K线保存到数据库
    - 处理向后兼容的market_type映射
    """

    def load(
        self,
        symbol: str,
        interval: str,
        market_type: str,
        limit: int = 500
    ) -> List[StandardKLine]:
        """
        从数据库加载K线数据

        Args:
            symbol: 交易对
            interval: K线周期
            market_type: 市场类型（支持旧格式自动转换）
            limit: 加载数量

        Returns:
            标准K线列表，按时间正序排列
        """
        # 转换为数据库存储格式（Bug-030修复）
        db_market_type = self._to_db_format(market_type)

        try:
            # 按时间倒序获取最新的K线
            queryset = KLine.objects.filter(
                symbol=symbol,
                interval=interval,
                market_type=db_market_type
            ).order_by('-open_time')[:limit]

            if not queryset.exists():
                logger.warning(
                    f"未找到K线数据: {symbol} {interval} {db_market_type}"
                )
                return []

            # 转换为StandardKLine并反转为时间正序
            klines = [self._to_standard(k) for k in queryset]
            klines.reverse()

            logger.debug(
                f"加载K线: {symbol} {interval} {db_market_type}, "
                f"数量={len(klines)}"
            )

            return klines

        except Exception as e:
            logger.error(f"加载K线失败: {symbol} {interval} - {e}")
            return []

    def save(
        self,
        klines: List[StandardKLine],
        symbol: str,
        interval: str,
        market_type: str
    ) -> int:
        """
        保存标准K线到数据库

        Args:
            klines: 标准K线列表
            symbol: 交易对
            interval: K线周期
            market_type: 市场类型

        Returns:
            新增记录数
        """
        # 转换为数据库存储格式（Bug-030修复）
        db_market_type = self._to_db_format(market_type)

        new_count = 0
        for kline in klines:
            try:
                open_time = datetime.fromtimestamp(
                    kline.timestamp / 1000, tz=timezone.utc
                )
                close_time = open_time + self._interval_to_delta(interval)

                _, created = KLine.objects.get_or_create(
                    symbol=symbol,
                    interval=interval,
                    market_type=db_market_type,
                    open_time=open_time,
                    defaults={
                        'open_price': kline.open,
                        'high_price': kline.high,
                        'low_price': kline.low,
                        'close_price': kline.close,
                        'volume': kline.volume,
                        'close_time': close_time,
                        'quote_volume': 0,
                        'trade_count': 0,
                        'taker_buy_volume': 0,
                        'taker_buy_quote_volume': 0,
                    }
                )
                if created:
                    new_count += 1

            except Exception as e:
                logger.error(f"保存K线失败: {kline.timestamp} - {e}")
                continue

        if new_count > 0:
            logger.info(
                f"保存K线: {symbol} {interval} {db_market_type}, "
                f"新增={new_count}"
            )

        return new_count

    def _to_standard(self, kline: KLine) -> StandardKLine:
        """
        将Django KLine模型转换为StandardKLine

        Args:
            kline: Django KLine实例

        Returns:
            StandardKLine实例
        """
        return StandardKLine(
            timestamp=int(kline.open_time.timestamp() * 1000),
            open=float(kline.open_price),
            high=float(kline.high_price),
            low=float(kline.low_price),
            close=float(kline.close_price),
            volume=float(kline.volume)
        )

    def _to_db_format(self, market_type: str) -> str:
        """
        将market_type转换为数据库存储格式

        数据库中存储的是旧格式（futures/spot），
        需要将新格式转回旧格式用于数据库查询。

        Bug-030: 修复normalize导致查询不匹配的问题

        Args:
            market_type: 市场类型（可能是新格式或旧格式）

        Returns:
            数据库存储格式的值
        """
        # 新格式 -> 旧格式（数据库存储格式）
        db_mapping = {
            'crypto_futures': 'futures',
            'crypto_spot': 'spot',
        }
        return db_mapping.get(market_type, market_type)

    def _interval_to_delta(self, interval: str) -> timedelta:
        """
        将interval转换为timedelta

        Args:
            interval: K线周期字符串

        Returns:
            对应的timedelta
        """
        seconds = Interval.to_seconds(interval)
        return timedelta(seconds=seconds)

    def get_latest_timestamp(
        self,
        symbol: str,
        interval: str,
        market_type: str
    ) -> Optional[int]:
        """
        获取最新K线的时间戳

        Args:
            symbol: 交易对
            interval: K线周期
            market_type: 市场类型

        Returns:
            最新K线的时间戳（毫秒），无数据返回None
        """
        db_market_type = self._to_db_format(market_type)

        try:
            latest = KLine.objects.filter(
                symbol=symbol,
                interval=interval,
                market_type=db_market_type
            ).order_by('-open_time').first()

            if latest:
                return int(latest.open_time.timestamp() * 1000)
            return None

        except Exception as e:
            logger.error(f"获取最新时间戳失败: {e}")
            return None

    def count(
        self,
        symbol: str,
        interval: str,
        market_type: str
    ) -> int:
        """
        获取K线数量

        Args:
            symbol: 交易对
            interval: K线周期
            market_type: 市场类型

        Returns:
            K线数量
        """
        db_market_type = self._to_db_format(market_type)

        return KLine.objects.filter(
            symbol=symbol,
            interval=interval,
            market_type=db_market_type
        ).count()
