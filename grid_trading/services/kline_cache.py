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
        # 如果不使用缓存且有API客户端，直接从API获取
        if not use_cache and self.api_client is not None:
            logger.info(f"直接从API获取K线(跳过缓存): {symbol} {interval} (limit={limit})")
            return self._fetch_from_api(symbol, interval, limit, end_time=end_time)

        # 如果API客户端为空，只能使用缓存
        if self.api_client is None:
            logger.info(f"API客户端未初始化，仅使用本地缓存: {symbol} {interval}")

        # ========== Step 1: 查询本地数据库 ==========
        cached_klines = self._get_cached_klines(symbol, interval, limit, end_time=end_time)

        # ========== Step 2: 判断是否需要补充数据 ==========
        # 检查缓存时效性：历史模式检查是否覆盖请求时间，实时模式检查是否包含最新数据
        needs_refresh = False
        if cached_klines:
            latest_cached_time = cached_klines[-1].open_time if cached_klines else None

            if end_time is not None:
                # 历史模式：检查缓存的最新时间是否接近请求时间
                if isinstance(end_time, datetime):
                    end_time_aware = end_time if end_time.tzinfo else timezone.make_aware(end_time)
                else:
                    end_time_aware = end_time

                if latest_cached_time:
                    time_gap = (end_time_aware - latest_cached_time).total_seconds() / 3600  # 小时
                    # 对于4h K线，如果gap > 24小时，视为过时
                    # 对于1h K线，如果gap > 4小时，视为过时
                    # 对于1m K线，如果gap > 1小时，视为过时
                    gap_threshold = {"4h": 24, "1h": 4, "1m": 1, "15m": 2, "1d": 48}.get(interval, 24)
                    if time_gap > gap_threshold:
                        needs_refresh = True
                        logger.info(
                            f"历史模式缓存过时: {symbol} {interval} "
                            f"(最新缓存={latest_cached_time}, 请求时间={end_time_aware}, gap={time_gap:.1f}h)"
                        )
            else:
                # 实时模式：检查缓存的最新时间距离当前时间是否过久
                current_time = timezone.now()
                if latest_cached_time:
                    time_gap = (current_time - latest_cached_time).total_seconds() / 3600  # 小时
                    # 实时模式使用更严格的阈值：确保数据新鲜度
                    # 4h K线：超过4小时就刷新
                    # 1h K线：超过1小时就刷新
                    # 15m K线：超过15分钟就刷新
                    gap_threshold = {"4h": 4, "1h": 1, "1m": 1/60, "15m": 0.25, "1d": 24}.get(interval, 4)
                    if time_gap > gap_threshold:
                        needs_refresh = True
                        logger.info(
                            f"实时模式缓存过时: {symbol} {interval} "
                            f"(最新缓存={latest_cached_time}, 当前时间={current_time}, gap={time_gap:.1f}h)"
                        )

        if len(cached_klines) >= limit and not needs_refresh:
            # 本地数据已足够且时效性OK
            logger.info(
                f"✓ 本地缓存命中: {symbol} {interval} ({len(cached_klines)}/{limit})"
            )
            return [kline.to_dict() for kline in cached_klines[:limit]]

        # ========== Step 3: 缓存不足或过时，按需增量获取直到满足需求或API无更多数据 ==========
        # 如果API客户端为空，只能返回现有缓存
        if self.api_client is None:
            if cached_klines:
                logger.warning(
                    f"API客户端未初始化，返回现有缓存 ({len(cached_klines)}/{limit}): {symbol} {interval}"
                )
                return [kline.to_dict() for kline in cached_klines]
            else:
                logger.error(
                    f"API客户端未初始化且无本地缓存: {symbol} {interval}"
                )
                return []

        if needs_refresh:
            logger.info(
                f"缓存需要刷新，从最新缓存时间向前补充: {symbol} {interval}"
            )
        else:
            logger.info(
                f"本地缓存不足 ({len(cached_klines)}/{limit})，开始增量获取: {symbol} {interval}"
            )

        need_count = limit - len(cached_klines)
        all_fetched = []

        # 设置初始的end_time
        if needs_refresh and cached_klines:
            # 刷新模式：从缓存的最新时间之后开始获取，补充到目标时间
            fetch_start_time = cached_klines[-1].open_time

            # 确定目标时间：历史模式用请求时间，实时模式用当前时间
            if end_time is not None:
                # 历史模式
                if isinstance(end_time, datetime):
                    target_time = end_time if end_time.tzinfo else timezone.make_aware(end_time)
                else:
                    target_time = end_time
                mode_label = "历史模式"
            else:
                # 实时模式：获取当前时间之前的最新数据
                target_time = timezone.now()
                mode_label = "实时模式"

            # 计算时间差对应的K线数量
            time_diff_hours = (target_time - fetch_start_time).total_seconds() / 3600
            interval_hours = {"4h": 4, "1h": 1, "1m": 1/60, "15m": 0.25, "1d": 24}.get(interval, 4)
            estimated_klines = int(time_diff_hours / interval_hours) + 10  # +10作为缓冲

            # 币安API的limit最大值是1500，需要分批获取
            MAX_API_LIMIT = 1500
            need_count = min(estimated_klines, MAX_API_LIMIT)

            # 在刷新模式下，我们要获取从start_time到target_time之间的数据
            # 实时模式不传end_time给API（获取最新数据），历史模式传end_time
            fetch_end_time = None if end_time is None else target_time

            logger.info(f"  {mode_label}刷新范围: {fetch_start_time} → {target_time}")
            logger.info(f"  预计需要补充: {estimated_klines}根K线 (单次最多{need_count}根)")
        elif cached_klines:
            # 数量不足模式：从缓存最早时间向历史方向获取
            fetch_end_time = cached_klines[0].open_time
        else:
            # 无缓存：直接用请求的end_time
            fetch_end_time = end_time

        # 如果用户指定了end_time，且比缓存更早，则使用用户指定的
        if end_time is not None and cached_klines and not needs_refresh:
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

        # 合并数据
        if needs_refresh:
            # 刷新模式: 需要过滤掉已有的K线，只保留新的
            # 获取缓存中最新的时间
            if cached_klines:
                latest_cached_time_ms = int(cached_klines[-1].open_time.timestamp() * 1000)
                # 过滤all_fetched，只保留比缓存更新的K线
                new_klines = [k for k in all_fetched if k['open_time'] > latest_cached_time_ms]
                logger.info(f"  过滤重复K线: {len(all_fetched)}根 → {len(new_klines)}根新K线")
                result = [kline.to_dict() for kline in cached_klines] + new_klines
            else:
                result = all_fetched
        else:
            # 补充模式: 新获取的(更早) + 缓存的(更晚)
            result = all_fetched + [kline.to_dict() for kline in cached_klines]

        logger.info(
            f"✓ 增量获取完成: {symbol} {interval} "
            f"(新增{len(all_fetched)}根 + 缓存{len(cached_klines)}根 = 总计{len(result)}根)"
        )

        # 返回需要的数量（可能仍然不足limit，这是正常的）
        # 在刷新模式下，我们需要返回end_time之前最新的limit根
        if needs_refresh and end_time:
            # 重新查询数据库，获取刷新后的最新limit根
            refreshed_klines = self._get_cached_klines(symbol, interval, limit, end_time=end_time)
            return [kline.to_dict() for kline in refreshed_klines[:limit]]
        else:
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
