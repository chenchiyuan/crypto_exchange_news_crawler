"""
Volume Trap 回测结果服务

提供回测结果的查询、格式化和API支持。

Related:
    - PRD: docs/iterations/007-backtest-framework/prd.md
    - Architecture: docs/iterations/007-backtest-framework/architecture.md
"""

from typing import Dict, List, Optional

from django.core.paginator import Paginator
from django.db.models import Q, QuerySet
from django.http import QueryDict

from volume_trap.models import BacktestResult


class BacktestResultService:
    """回测结果服务。

    负责查询和格式化回测数据，支持分页、筛选、排序等功能。

    Examples:
        >>> service = BacktestResultService()
        >>> result = service.get_backtest_by_id(1)
        >>> print(f"交易对: {result.symbol}")
    """

    def get_backtest_by_id(self, backtest_id: int) -> Optional[BacktestResult]:
        """根据ID获取单个回测结果。

        Args:
            backtest_id: 回测结果ID

        Returns:
            BacktestResult: 回测结果对象，如果不存在则返回None
        """
        try:
            return BacktestResult.objects.get(id=backtest_id)
        except BacktestResult.DoesNotExist:
            return None

    def get_backtest_list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        symbol: Optional[str] = None,
        interval: Optional[str] = None,
        market_type: Optional[str] = None,
        is_profitable: Optional[bool] = None,
        order_by: str = "-entry_time",
    ) -> Dict:
        """获取回测结果列表。

        Args:
            page: 页码（从1开始）
            page_size: 每页数量
            status: 状态筛选
            symbol: 交易对符号筛选
            interval: K线周期筛选
            market_type: 市场类型筛选
            is_profitable: 是否盈利筛选
            order_by: 排序字段（默认为按入场时间倒序）

        Returns:
            dict: 包含列表数据和分页元数据的字典
        """
        # 构建查询
        queryset = BacktestResult.objects.all()

        # 应用筛选条件
        if status:
            queryset = queryset.filter(status=status)
        if symbol:
            queryset = queryset.filter(symbol__icontains=symbol)
        if interval:
            queryset = queryset.filter(interval=interval)
        if market_type:
            queryset = queryset.filter(market_type=market_type)
        if is_profitable is not None:
            queryset = queryset.filter(is_profitable=is_profitable)

        # 应用排序
        queryset = queryset.order_by(order_by)

        # 分页
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)

        # 格式化结果
        results = [
            self._format_backtest_result(bt) for bt in page_obj.object_list
        ]

        return {
            "results": results,
            "pagination": {
                "current_page": page_obj.number,
                "total_pages": paginator.num_pages,
                "total_count": paginator.count,
                "page_size": page_size,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
                "next_page_number": page_obj.next_page_number() if page_obj.has_next() else None,
                "previous_page_number": page_obj.previous_page_number() if page_obj.has_previous() else None,
            },
        }

    def _format_backtest_result(self, backtest_result: BacktestResult) -> Dict:
        """格式化单个回测结果。

        Args:
            backtest_result: 回测结果对象

        Returns:
            dict: 格式化后的字典
        """
        return {
            "id": backtest_result.id,
            "symbol": backtest_result.symbol,
            "interval": backtest_result.interval,
            "market_type": backtest_result.market_type,
            "entry_time": backtest_result.entry_time.isoformat() if backtest_result.entry_time else None,
            "entry_price": str(backtest_result.entry_price) if backtest_result.entry_price else None,
            "lowest_time": backtest_result.lowest_time.isoformat() if backtest_result.lowest_time else None,
            "lowest_price": str(backtest_result.lowest_price) if backtest_result.lowest_price else None,
            "bars_to_lowest": backtest_result.bars_to_lowest,
            "max_profit_percent": str(backtest_result.max_profit_percent) if backtest_result.max_profit_percent else None,
            "has_rebound": backtest_result.has_rebound,
            "rebound_high_price": str(backtest_result.rebound_high_price) if backtest_result.rebound_high_price else None,
            "rebound_percent": str(backtest_result.rebound_percent) if backtest_result.rebound_percent else None,
            "max_drawdown_percent": str(backtest_result.max_drawdown_percent) if backtest_result.max_drawdown_percent else None,
            "exit_time": backtest_result.exit_time.isoformat() if backtest_result.exit_time else None,
            "exit_price": str(backtest_result.exit_price) if backtest_result.exit_price else None,
            "final_profit_percent": str(backtest_result.final_profit_percent) if backtest_result.final_profit_percent else None,
            "is_profitable": backtest_result.is_profitable,
            "observation_bars": backtest_result.observation_bars,
            "status": backtest_result.status,
            "created_at": backtest_result.created_at.isoformat(),
        }

    def get_statistics_summary(self) -> Dict:
        """获取回测结果统计摘要。

        Returns:
            dict: 统计摘要
        """
        from django.db.models import Count, Avg

        # 总数统计
        total_count = BacktestResult.objects.count()

        # 按状态统计
        status_stats = (
            BacktestResult.objects.values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        )

        # 按市场类型统计
        market_type_stats = (
            BacktestResult.objects.values("market_type")
            .annotate(count=Count("id"))
            .order_by("market_type")
        )

        # 按K线周期统计
        interval_stats = (
            BacktestResult.objects.values("interval")
            .annotate(count=Count("id"))
            .order_by("interval")
        )

        # 盈利统计
        profitable_count = BacktestResult.objects.filter(is_profitable=True).count()
        unprofitable_count = BacktestResult.objects.filter(
            is_profitable=False
        ).count()

        # 平均收益率
        avg_profit = BacktestResult.objects.filter(
            final_profit_percent__isnull=False
        ).aggregate(avg=Avg("final_profit_percent"))["avg"]

        return {
            "total_count": total_count,
            "profitable_count": profitable_count,
            "unprofitable_count": unprofitable_count,
            "win_rate": round((profitable_count / total_count * 100), 2) if total_count > 0 else 0,
            "avg_profit_percent": round(float(avg_profit), 2) if avg_profit else 0,
            "status_distribution": {stat["status"]: stat["count"] for stat in status_stats},
            "market_type_distribution": {stat["market_type"]: stat["count"] for stat in market_type_stats},
            "interval_distribution": {stat["interval"]: stat["count"] for stat in interval_stats},
        }

    def search_backtest_results(
        self,
        query: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict:
        """搜索回测结果。

        Args:
            query: 搜索关键词（交易对符号）
            page: 页码
            page_size: 每页数量

        Returns:
            dict: 搜索结果
        """
        queryset = BacktestResult.objects.filter(
            symbol__icontains=query
        ).order_by("-entry_time")

        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)

        results = [
            self._format_backtest_result(bt) for bt in page_obj.object_list
        ]

        return {
            "results": results,
            "query": query,
            "pagination": {
                "current_page": page_obj.number,
                "total_pages": paginator.num_pages,
                "total_count": paginator.count,
                "page_size": page_size,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
            },
        }

    def get_backtest_by_monitor_id(self, monitor_id: int) -> Optional[BacktestResult]:
        """根据监控记录ID获取回测结果。

        Args:
            monitor_id: VolumeTrapMonitor ID

        Returns:
            BacktestResult: 回测结果对象
        """
        try:
            return BacktestResult.objects.get(monitor_id=monitor_id)
        except BacktestResult.DoesNotExist:
            return None
