"""
Volume Trap 策略统计计算服务

实现整体策略的聚合统计指标计算。

Related:
    - PRD: docs/iterations/007-backtest-framework/prd.md
    - Architecture: docs/iterations/007-backtest-framework/architecture.md
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from django.db.models import Avg, Count, Max, Min, Q, QuerySet
from django.db.models.functions import Coalesce

from volume_trap.models import BacktestResult, BacktestStatistics


class StatisticsCalculator:
    """统计计算器。

    计算整体策略的聚合统计指标，支持多维度分组统计。

    Examples:
        >>> calc = StatisticsCalculator()
        >>> stats = calc.calculate_overall_stats()
        >>> print(f"胜率: {stats.win_rate}%")
    """

    def calculate_overall_stats(
        self,
        backtest_results: Optional[QuerySet] = None,
        market_type: Optional[str] = None,
        interval: Optional[str] = None,
        status_filter: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> BacktestStatistics:
        """计算整体策略统计。

        Args:
            backtest_results: 回测结果查询集（可选，默认查询全部）
            market_type: 市场类型筛选（spot/futures）
            interval: K线周期筛选（1h/4h/1d）
            status_filter: 状态筛选（completed等）
            start_date: 开始日期（YYYY-MM-DD格式）
            end_date: 结束日期（YYYY-MM-DD格式）

        Returns:
            BacktestStatistics: 统计结果对象
        """
        # 构建查询条件
        queryset = backtest_results or BacktestResult.objects.all()

        if market_type:
            queryset = queryset.filter(market_type=market_type)
        if interval:
            queryset = queryset.filter(interval=interval)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if start_date:
            queryset = queryset.filter(entry_time__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(entry_time__date__lte=end_date)

        # 只计算已完成的回测
        queryset = queryset.filter(status="completed")

        # 计算基础统计
        total_trades = queryset.count()
        if total_trades == 0:
            # 如果没有数据，返回默认统计
            return self._create_default_statistics(
                market_type, interval, status_filter, start_date, end_date
            )

        # 计算胜率
        win_rate = self.calculate_win_rate(queryset)

        # 计算收益指标
        profit_metrics = self.calculate_profit_metrics(queryset)

        # 计算风险指标
        risk_metrics = self.calculate_risk_metrics(queryset)

        # 计算时间指标
        time_metrics = self.calculate_time_metrics(queryset)

        # 计算盈亏比
        profit_factor = self.calculate_profit_factor(queryset)

        # 生成统计名称
        name = self._generate_statistics_name(
            market_type, interval, status_filter, start_date, end_date
        )

        # 创建统计记录
        stats = BacktestStatistics.objects.create(
            name=name,
            market_type=market_type or "all",
            interval=interval or "all",
            status_filter=status_filter,
            start_date=start_date,
            end_date=end_date,
            observation_bars=0,  # 观察全部历史数据
            total_trades=total_trades,
            profitable_trades=profit_metrics["profitable_trades"],
            losing_trades=profit_metrics["losing_trades"],
            win_rate=Decimal(str(win_rate)),
            avg_profit_percent=profit_metrics["avg_profit"],
            max_profit_percent=profit_metrics["max_profit"],
            min_profit_percent=profit_metrics["min_profit"],
            total_profit_percent=profit_metrics["total_profit"],
            avg_max_drawdown=risk_metrics["avg_drawdown"],
            worst_drawdown=risk_metrics["worst_drawdown"],
            avg_bars_to_lowest=time_metrics["avg_bars"],
            profit_factor=Decimal(str(profit_factor)),
        )

        return stats

    def calculate_win_rate(self, queryset: QuerySet) -> float:
        """计算胜率。

        胜率 = 盈利交易数 / 总交易数 × 100%

        Args:
            queryset: 回测结果查询集

        Returns:
            float: 胜率百分比
        """
        total = queryset.count()
        if total == 0:
            return 0.0

        profitable = queryset.filter(is_profitable=True).count()
        win_rate = (profitable / total) * 100
        return round(win_rate, 2)

    def calculate_profit_metrics(
        self, queryset: QuerySet
    ) -> Dict[str, float]:
        """计算收益指标。

        Args:
            queryset: 回测结果查询集

        Returns:
            dict: 包含各项收益指标的字典
        """
        # 计算盈利和亏损交易数
        profitable_trades = queryset.filter(is_profitable=True).count()
        losing_trades = queryset.filter(is_profitable=False).count()

        # 计算平均收益率
        avg_profit = queryset.aggregate(
            avg=Coalesce(Avg("final_profit_percent"), Decimal("0"))
        )["avg"]
        avg_profit = float(avg_profit)

        # 计算最大收益和最小收益
        max_profit_result = queryset.aggregate(
            max=Coalesce(Max("final_profit_percent"), Decimal("0"))
        )
        min_profit_result = queryset.aggregate(
            min=Coalesce(Min("final_profit_percent"), Decimal("0"))
        )

        max_profit = float(max_profit_result["max"])
        min_profit = float(min_profit_result["min"])

        # 计算总收益率（所有交易的平均收益）
        total_profit = avg_profit

        return {
            "profitable_trades": profitable_trades,
            "losing_trades": losing_trades,
            "avg_profit": round(avg_profit, 2),
            "max_profit": round(max_profit, 2),
            "min_profit": round(min_profit, 2),
            "total_profit": round(total_profit, 2),
        }

    def calculate_risk_metrics(self, queryset: QuerySet) -> Dict[str, float]:
        """计算风险指标。

        Args:
            queryset: 回测结果查询集

        Returns:
            dict: 包含各项风险指标的字典
        """
        # 计算平均最大回撤
        avg_drawdown_result = queryset.aggregate(
            avg=Coalesce(Avg("max_drawdown_percent"), Decimal("0"))
        )
        avg_drawdown = float(avg_drawdown_result["avg"])

        # 计算最差回撤
        worst_drawdown_result = queryset.aggregate(
            min=Coalesce(Min("max_drawdown_percent"), Decimal("0"))
        )
        worst_drawdown = float(worst_drawdown_result["min"])

        return {
            "avg_drawdown": round(avg_drawdown, 2),
            "worst_drawdown": round(worst_drawdown, 2),
        }

    def calculate_time_metrics(self, queryset: QuerySet) -> Dict[str, float]:
        """计算时间指标。

        Args:
            queryset: 回测结果查询集

        Returns:
            dict: 包含时间指标的字典
        """
        from django.db.models import FloatField

        # 计算平均到达最低点K线数
        avg_bars_result = queryset.aggregate(
            avg=Coalesce(Avg("bars_to_lowest"), 0.0, output_field=FloatField())
        )
        avg_bars = float(avg_bars_result["avg"])

        return {
            "avg_bars": round(avg_bars, 2),
        }

    def calculate_profit_factor(self, queryset: QuerySet) -> float:
        """计算盈亏比。

        盈亏比 = 总盈利 / 总亏损

        Args:
            queryset: 回测结果查询集

        Returns:
            float: 盈亏比
        """
        # 分离盈利和亏损交易
        profitable_trades = queryset.filter(is_profitable=True)
        losing_trades = queryset.filter(is_profitable=False)

        # 计算总盈利和总亏损
        total_profit = sum(
            [float(t.final_profit_percent or 0) for t in profitable_trades]
        )
        total_loss = abs(
            sum([float(t.final_profit_percent or 0) for t in losing_trades])
        )

        # 计算盈亏比
        if total_loss == 0:
            # 如果没有亏损，盈亏比为无穷大，返回一个大的数值
            return float("inf") if total_profit > 0 else 0.0

        profit_factor = total_profit / total_loss
        return round(profit_factor, 2)

    def _create_default_statistics(
        self,
        market_type: Optional[str],
        interval: Optional[str],
        status_filter: Optional[str],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> BacktestStatistics:
        """创建默认统计（当没有数据时）。"""
        name = self._generate_statistics_name(
            market_type, interval, status_filter, start_date, end_date
        )

        return BacktestStatistics.objects.create(
            name=name,
            market_type=market_type or "all",
            interval=interval or "all",
            status_filter=status_filter,
            start_date=start_date,
            end_date=end_date,
            observation_bars=0,
            total_trades=0,
            profitable_trades=0,
            losing_trades=0,
            win_rate=Decimal("0"),
            avg_profit_percent=Decimal("0"),
            max_profit_percent=Decimal("0"),
            min_profit_percent=Decimal("0"),
            total_profit_percent=Decimal("0"),
            avg_max_drawdown=Decimal("0"),
            worst_drawdown=Decimal("0"),
            avg_bars_to_lowest=Decimal("0"),
            profit_factor=Decimal("0"),
        )

    def _generate_statistics_name(
        self,
        market_type: Optional[str],
        interval: Optional[str],
        status_filter: Optional[str],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> str:
        """生成统计名称。"""
        name_parts = []

        if market_type:
            name_parts.append(market_type)
        if interval:
            name_parts.append(interval)
        if status_filter:
            name_parts.append(status_filter)
        if start_date:
            name_parts.append(f"from_{start_date}")
        if end_date:
            name_parts.append(f"to_{end_date}")

        if not name_parts:
            return "overall_statistics"

        return "_".join(name_parts) + "_statistics"


class MultiDimensionalStatistics:
    """多维度统计计算器。

    支持按多个维度分组计算统计指标。

    Examples:
        >>> multi_calc = MultiDimensionalStatistics()
        >>> results = multi_calc.calculate_by_dimensions(['market_type', 'interval'])
        >>> for result in results:
        ...     print(f"{result.name}: 胜率{result.win_rate}%")
    """

    def __init__(self):
        self.calculator = StatisticsCalculator()

    def calculate_by_dimensions(
        self, dimensions: List[str]
    ) -> List[BacktestStatistics]:
        """按指定维度分组计算统计。

        Args:
            dimensions: 维度列表，如 ['market_type', 'interval']

        Returns:
            List[BacktestStatistics]: 统计结果列表
        """
        results = []

        # 获取所有唯一值组合
        queryset = BacktestResult.objects.filter(status="completed")

        # 按维度分组获取唯一值
        unique_values = self._get_unique_values(queryset, dimensions)

        # 计算每个组合的统计
        for value_combination in unique_values:
            filters = dict(zip(dimensions, value_combination))

            stats = self.calculator.calculate_overall_stats(
                market_type=filters.get("market_type"),
                interval=filters.get("interval"),
                status_filter=filters.get("status"),
            )

            results.append(stats)

        return results

    def _get_unique_values(
        self, queryset: QuerySet, dimensions: List[str]
    ) -> List[Tuple]:
        """获取维度的唯一值组合。"""
        # 这里简化实现，实际应该动态构建查询
        # 为简化，这里返回一些示例值
        unique_values = []

        if "market_type" in dimensions and "interval" in dimensions:
            # 示例：现货4h、现货1d、合约4h、合约1d
            combinations = [
                ("spot", "4h"),
                ("spot", "1d"),
                ("futures", "4h"),
                ("futures", "1d"),
            ]
            for combo in combinations:
                # 检查这个组合是否有数据
                filtered_qs = queryset
                if combo[0]:
                    filtered_qs = filtered_qs.filter(market_type=combo[0])
                if combo[1]:
                    filtered_qs = filtered_qs.filter(interval=combo[1])

                if filtered_qs.exists():
                    unique_values.append(combo)

        return unique_values
