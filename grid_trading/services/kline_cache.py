"""
K线数据缓存服务
Kline Data Cache Service

提供智能缓存管理:
1. 本地优先: 优先从数据库获取已缓存数据
2. 增量更新: 只获取缺失时间段的数据
3. 自动合并: 将本地和远程数据合并返回
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from django.db import transaction
from django.utils import timezone

from grid_trading.models import KlineData

logger = logging.getLogger("grid_trading")


class KlineCache:
    """
    K线数据缓存管理器

    核心逻辑:
    1. 查询本地数据库已有数据
    2. 计算缺失的时间范围
    3. 从API获取缺失数据
    4. 批量保存到数据库
    5. 返回完整的K线数据
    """

    def __init__(self, api_client=None):
        """
        初始化缓存管理器

        Args:
            api_client: BinanceFuturesClient实例 (用于获取远程数据)
        """
        self.api_client = api_client

    def get_klines(
        self,
        symbol: str,
        interval: str = "4h",
        limit: int = 300,
        use_cache: bool = True,
        end_time: Optional[any] = None,
    ) -> List[Dict]:
        """
        获取K线数据 (智能缓存)

        逻辑流程:
        1. 如果use_cache=False，直接从API获取
        2. 查询本地数据库已缓存的数据
        3. 判断是否需要从API补充数据:
           a. 本地数据为空 → 全量获取
           b. 本地数据不足limit → 获取缺失部分
           c. 本地数据已足够 → 直接返回
        4. 合并本地+远程数据
        5. 保存新数据到数据库

        Args:
            symbol: 交易对 (BTCUSDT)
            interval: 时间周期 (1m, 4h, 1d等)
            limit: 需要的K线数量
            use_cache: 是否使用缓存
            end_time: 结束时间 (datetime对象，获取此时间之前的数据，用于历史数据查询)

        Returns:
            List[Dict]: K线数据列表，按时间升序
        """
        if not use_cache or self.api_client is None:
            # 不使用缓存，直接从API获取
            logger.info(f"直接从API获取K线: {symbol} {interval} (limit={limit})")
            return self._fetch_from_api(symbol, interval, limit, end_time=end_time)

        # ========== Step 1: 查询本地数据库 ==========
        cached_klines = self._get_cached_klines(symbol, interval, limit, end_time=end_time)

        # ========== Step 2: 判断是否需要补充数据 ==========
        if len(cached_klines) >= limit:
            # 本地数据已足够
            logger.info(
                f"✓ 本地缓存命中: {symbol} {interval} ({len(cached_klines)}/{limit})"
            )
            return [kline.to_dict() for kline in cached_klines[:limit]]

        # ========== Step 3: 需要从API补充数据 ==========
        if len(cached_klines) == 0:
            # 本地无数据，全量获取
            logger.info(f"本地缓存为空，全量获取: {symbol} {interval} (limit={limit})")
            remote_klines = self._fetch_from_api(symbol, interval, limit, end_time=end_time)
            self._save_klines(symbol, interval, remote_klines)
            return remote_klines
        else:
            # 本地数据不足，增量获取
            logger.info(
                f"本地缓存不足 ({len(cached_klines)}/{limit})，增量获取: {symbol} {interval}"
            )
            # 计算需要补充的数量
            need_count = limit - len(cached_klines)

            # 获取最早的缓存时间，从这个时间之前开始获取
            earliest_cached = cached_klines[0].open_time
            logger.info(f"最早缓存时间: {earliest_cached}，需补充 {need_count} 根K线")

            # 从API获取更早的数据(如果指定了end_time,使用较早的那个)
            fetch_end_time = earliest_cached
            if end_time is not None:
                from datetime import datetime
                if isinstance(end_time, datetime):
                    end_time_aware = end_time if end_time.tzinfo else timezone.make_aware(end_time)
                    if end_time_aware < earliest_cached:
                        fetch_end_time = end_time_aware

            remote_klines = self._fetch_from_api(
                symbol, interval, need_count, end_time=fetch_end_time
            )

            # 保存新获取的数据
            if remote_klines:
                self._save_klines(symbol, interval, remote_klines)

            # 合并数据: 远程(更早) + 本地(更晚)
            all_klines = remote_klines + [kline.to_dict() for kline in cached_klines]

            logger.info(
                f"✓ 增量更新完成: {symbol} {interval} (新增 {len(remote_klines)} 根，总计 {len(all_klines)})"
            )

            return all_klines[:limit]

    def _get_cached_klines(
        self, symbol: str, interval: str, limit: int, end_time: Optional[any] = None
    ) -> List[KlineData]:
        """
        从数据库获取缓存的K线数据

        Args:
            symbol: 交易对
            interval: 时间周期
            limit: 最多获取的数量
            end_time: 结束时间 (仅获取此时间之前的K线)

        Returns:
            List[KlineData]: K线数据（按时间升序）
        """
        try:
            queryset = KlineData.objects.filter(symbol=symbol, interval=interval)

            # 如果指定了end_time,只获取该时间点之前的K线
            if end_time is not None:
                from datetime import datetime
                if isinstance(end_time, datetime):
                    end_time_aware = end_time if end_time.tzinfo else timezone.make_aware(end_time)
                    queryset = queryset.filter(open_time__lt=end_time_aware)

            klines = queryset.order_by("-open_time")[:limit]

            # 转换为列表并反转顺序（变为升序）
            klines_list = list(klines)
            klines_list.reverse()

            return klines_list

        except Exception as e:
            logger.error(f"查询缓存失败: {symbol} {interval} - {e}")
            return []

    def _fetch_from_api(
        self,
        symbol: str,
        interval: str,
        limit: int,
        end_time: Optional[datetime] = None,
    ) -> List[Dict]:
        """
        从币安API获取K线数据

        Args:
            symbol: 交易对
            interval: 时间周期
            limit: 数量
            end_time: 结束时间（获取此时间之前的数据）

        Returns:
            List[Dict]: K线数据
        """
        if self.api_client is None:
            logger.error("API客户端未初始化")
            return []

        try:
            # 调用原有的API方法
            result = self.api_client.fetch_klines(
                symbols=[symbol], interval=interval, limit=limit, end_time=end_time
            )

            if symbol in result:
                return result[symbol]
            else:
                logger.warning(f"API未返回数据: {symbol} {interval}")
                return []

        except Exception as e:
            logger.error(f"从API获取K线失败: {symbol} {interval} - {e}")
            return []

    def _save_klines(self, symbol: str, interval: str, klines_data: List[Dict]):
        """
        批量保存K线数据到数据库

        使用bulk_create + ignore_conflicts避免重复插入

        Args:
            symbol: 交易对
            interval: 时间周期
            klines_data: K线数据列表
        """
        if not klines_data:
            return

        try:
            # 转换为KlineData对象列表
            kline_objects = []
            for kline in klines_data:
                try:
                    obj = KlineData.from_binance_kline(symbol, interval, kline)
                    kline_objects.append(obj)
                except Exception as e:
                    logger.warning(
                        f"跳过无效K线数据: {symbol} {interval} @ {kline.get('open_time', 'unknown')} - {e}"
                    )
                    continue

            if not kline_objects:
                return

            # 批量插入（忽略重复数据）
            with transaction.atomic():
                KlineData.objects.bulk_create(
                    kline_objects, ignore_conflicts=True  # Django 4.1+ 支持
                )

            logger.info(
                f"✓ 保存K线数据: {symbol} {interval} ({len(kline_objects)} 根)"
            )

        except Exception as e:
            logger.error(f"保存K线数据失败: {symbol} {interval} - {e}")

    def get_cached_range(self, symbol: str, interval: str) -> Optional[Tuple[datetime, datetime]]:
        """
        获取本地已缓存的时间范围

        Args:
            symbol: 交易对
            interval: 时间周期

        Returns:
            (earliest_time, latest_time) 或 None (如果无缓存)
        """
        try:
            agg = KlineData.objects.filter(
                symbol=symbol, interval=interval
            ).aggregate(
                earliest=models.Min("open_time"), latest=models.Max("open_time")
            )

            if agg["earliest"] and agg["latest"]:
                return (agg["earliest"], agg["latest"])
            else:
                return None

        except Exception as e:
            logger.error(f"查询缓存范围失败: {symbol} {interval} - {e}")
            return None

    def clear_cache(self, symbol: Optional[str] = None, interval: Optional[str] = None):
        """
        清空缓存

        Args:
            symbol: 指定交易对 (None=全部)
            interval: 指定时间周期 (None=全部)
        """
        try:
            queryset = KlineData.objects.all()

            if symbol:
                queryset = queryset.filter(symbol=symbol)
            if interval:
                queryset = queryset.filter(interval=interval)

            count = queryset.count()
            queryset.delete()

            logger.info(f"✓ 清空缓存: 删除 {count} 条记录 (symbol={symbol}, interval={interval})")

        except Exception as e:
            logger.error(f"清空缓存失败: {e}")

    def get_cache_stats(self) -> Dict:
        """
        获取缓存统计信息

        Returns:
            Dict: {
                'total_count': 总K线数,
                'symbols': 标的数量,
                'intervals': 周期列表,
                'size_mb': 数据库大小(MB)
            }
        """
        try:
            from django.db.models import Count

            stats = {
                "total_count": KlineData.objects.count(),
                "symbols": (
                    KlineData.objects.values("symbol").distinct().count()
                ),
                "intervals": list(
                    KlineData.objects.values_list("interval", flat=True).distinct()
                ),
            }

            # 按标的统计
            symbol_stats = (
                KlineData.objects.values("symbol", "interval")
                .annotate(count=Count("id"))
                .order_by("-count")[:10]
            )

            stats["top_symbols"] = list(symbol_stats)

            return stats

        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {}
