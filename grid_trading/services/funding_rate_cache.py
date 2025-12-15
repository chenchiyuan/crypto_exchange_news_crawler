"""
资金费率缓存管理器
Funding Rate Cache Manager

用途: 管理历史资金费率的数据库缓存，避免重复API调用
"""

import logging
from typing import List, Dict, Optional
from decimal import Decimal

logger = logging.getLogger("grid_trading")


class FundingRateCache:
    """资金费率缓存管理器"""

    @staticmethod
    def get_cached_history(
        symbol: str,
        start_time: int,
        end_time: int = None
    ) -> List[Dict]:
        """
        从数据库获取缓存的历史资金费率

        Args:
            symbol: 交易对（如BTCUSDT）
            start_time: 开始时间戳(毫秒)
            end_time: 结束时间戳(毫秒)，None表示当前时间

        Returns:
            历史资金费率列表 [{'fundingRate': Decimal, 'fundingTime': int}, ...]
        """
        from grid_trading.django_models import FundingRateHistory
        from datetime import datetime

        if end_time is None:
            end_time = int(datetime.now().timestamp() * 1000)

        records = FundingRateHistory.objects.filter(
            symbol=symbol,
            funding_time__gte=start_time,
            funding_time__lte=end_time
        ).order_by('funding_time')

        return [{
            'fundingRate': record.funding_rate,
            'fundingTime': record.funding_time,
        } for record in records]

    @staticmethod
    def save_funding_history(
        symbol: str,
        history: List[Dict],
        funding_interval_hours: int = 8
    ) -> int:
        """
        保存历史资金费率到数据库（批量插入，忽略重复）

        Args:
            symbol: 交易对
            history: 资金费率列表 [{'fundingRate': Decimal, 'fundingTime': int}, ...]
            funding_interval_hours: 结算周期（小时）

        Returns:
            新增记录数
        """
        from grid_trading.django_models import FundingRateHistory

        if not history:
            return 0

        records_to_create = []
        for item in history:
            records_to_create.append(
                FundingRateHistory(
                    symbol=symbol,
                    funding_rate=item['fundingRate'],
                    funding_time=item['fundingTime'],
                    funding_interval_hours=funding_interval_hours
                )
            )

        # 使用ignore_conflicts避免重复插入错误
        created_records = FundingRateHistory.objects.bulk_create(
            records_to_create,
            ignore_conflicts=True
        )

        return len(created_records)

    @staticmethod
    def get_funding_interval(symbol: str) -> int:
        """
        从缓存中获取资金费率结算周期

        Args:
            symbol: 交易对

        Returns:
            结算周期(小时)，默认8
        """
        from grid_trading.django_models import FundingRateHistory

        record = FundingRateHistory.objects.filter(
            symbol=symbol
        ).first()

        return record.funding_interval_hours if record else 8

    @staticmethod
    def get_latest_funding_time(symbol: str) -> Optional[int]:
        """
        获取缓存中最新的资金费率时间戳

        Args:
            symbol: 交易对

        Returns:
            最新时间戳(毫秒)，无缓存返回None
        """
        from grid_trading.django_models import FundingRateHistory

        record = FundingRateHistory.objects.filter(
            symbol=symbol
        ).order_by('-funding_time').first()

        return record.funding_time if record else None

    @staticmethod
    def get_cache_stats(symbols: List[str] = None) -> Dict:
        """
        获取缓存统计信息

        Args:
            symbols: 交易对列表，None表示所有

        Returns:
            统计信息字典
        """
        from grid_trading.django_models import FundingRateHistory
        from django.db.models import Count, Min, Max

        queryset = FundingRateHistory.objects.all()

        if symbols:
            queryset = queryset.filter(symbol__in=symbols)

        stats = queryset.aggregate(
            total_records=Count('id'),
            symbol_count=Count('symbol', distinct=True),
            earliest_time=Min('funding_time'),
            latest_time=Max('funding_time'),
        )

        return {
            'total_records': stats['total_records'] or 0,
            'cached_symbols': stats['symbol_count'] or 0,
            'earliest_time': stats['earliest_time'],
            'latest_time': stats['latest_time'],
        }

    @staticmethod
    def clear_old_data(days_to_keep: int = 90) -> int:
        """
        清理超过指定天数的旧数据（可选维护功能）

        Args:
            days_to_keep: 保留最近多少天的数据

        Returns:
            删除的记录数
        """
        from grid_trading.django_models import FundingRateHistory
        from datetime import datetime, timedelta

        cutoff_time = int((datetime.now() - timedelta(days=days_to_keep)).timestamp() * 1000)

        deleted_count, _ = FundingRateHistory.objects.filter(
            funding_time__lt=cutoff_time
        ).delete()

        logger.info(f"清理旧资金费率数据: 删除 {deleted_count} 条记录（保留最近{days_to_keep}天）")
        return deleted_count
