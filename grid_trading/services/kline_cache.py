"""
K线数据缓存服务
Kline Data Cache Service

提供智能缓存管理:
1. 本地优先: 优先从数据库获取已缓存数据
2. 增量更新: 只获取缺失时间段的数据
3. 自动合并: 将本地和远程数据合并返回
"""

import logging
from datetime import datetime, timedelta, timezone as dt_timezone
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

        # ========== Step 3: 缓存不足，按需增量获取直到满足需求或API无更多数据 ==========
        logger.info(
            f"本地缓存不足 ({len(cached_klines)}/{limit})，开始增量获取: {symbol} {interval}"
        )

        need_count = limit - len(cached_klines)
        all_fetched = []

        # 设置初始的end_time（从缓存最早时间开始向前获取）
        if cached_klines:
            fetch_end_time = cached_klines[0].open_time
        else:
            fetch_end_time = end_time

        # 如果用户指定了end_time，且比缓存更早，则使用用户指定的
        if end_time is not None and cached_klines:
            if isinstance(end_time, datetime):
                end_time_aware = end_time if end_time.tzinfo else timezone.make_aware(end_time)
                if end_time_aware < fetch_end_time:
                    fetch_end_time = end_time_aware

        # 循环获取，直到满足需求或API无更多数据
        max_fetch_rounds = 5  # 最多尝试5轮，避免无限循环
        round_num = 0

        while need_count > 0 and round_num < max_fetch_rounds:
            round_num += 1
            logger.info(f"  第{round_num}轮获取: 需要{need_count}根，endTime={fetch_end_time}")

            # 从API获取数据
            fetched = self._fetch_from_api(
                symbol, interval, need_count, end_time=fetch_end_time
            )

            if not fetched:
                logger.info(f"  第{round_num}轮: API无数据返回，停止获取")
                break

            # 新获取的数据添加到前面（因为是更早的数据）
            all_fetched = fetched + all_fetched
            need_count -= len(fetched)

            logger.info(f"  第{round_num}轮: 获取{len(fetched)}根，还需{need_count}根")

            # 判断是否已经到达历史起点
            # 如果API返回的数量少于我们本轮请求的数量，说明已经没有更多历史数据了
            requested_count = need_count + len(fetched)  # 本轮请求的数量
            if len(fetched) < requested_count:
                logger.info(f"  API返回数据不足（返回{len(fetched)}/{requested_count}），已到达历史起点")
                break

            # 更新end_time为本轮最早的时间，准备下一轮获取
            if fetched:
                first_kline_time = fetched[0].get('open_time')
                if isinstance(first_kline_time, int):
                    # 毫秒时间戳
                    fetch_end_time = datetime.fromtimestamp(
                        first_kline_time / 1000, tz=dt_timezone.utc
                    )
                else:
                    fetch_end_time = first_kline_time

        # 保存所有新获取的数据
        if all_fetched:
            self._save_klines(symbol, interval, all_fetched)

        # 合并数据: 新获取的(更早) + 缓存的(更晚)
        result = all_fetched + [kline.to_dict() for kline in cached_klines]

        logger.info(
            f"✓ 增量获取完成: {symbol} {interval} "
            f"(新增{len(all_fetched)}根 + 缓存{len(cached_klines)}根 = 总计{len(result)}根)"
        )

        # 返回需要的数量（可能仍然不足limit，这是正常的）
        return result[:limit] if len(result) >= limit else result

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
