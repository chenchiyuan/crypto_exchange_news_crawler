"""
Volume Trap 策略回测引擎

实现对单个异常事件的后续表现分析。

Related:
    - PRD: docs/iterations/007-backtest-framework/IMPLEMENTATION_PLAN.md
"""

from datetime import timedelta
from decimal import Decimal

from backtest.models import KLine
from volume_trap.exceptions import DataInsufficientError
from volume_trap.models import BacktestResult, VolumeTrapMonitor


class VolumeTrapBacktestEngine:
    """Volume Trap 策略回测引擎。

    分析发现异常事件后的价格表现，计算做空策略的收益情况。

    Examples:
        >>> engine = VolumeTrapBacktestEngine()
        >>> result = engine.run_backtest(monitor_id=1, observation_bars=0)
        >>> print(f"最大盈利: {result.max_profit_percent}%")
    """

    def run_backtest(
        self,
        monitor: VolumeTrapMonitor,
        observation_bars: int = 0,
        min_bars_to_lowest: int = 1,
        min_bars_to_rebound: int = 3,
    ) -> BacktestResult:
        """运行单个异常事件的回测。

        策略：发现异常后，在下一根K线收盘价做空，持续持仓观察。

        Args:
            monitor: 异常事件监控记录
            observation_bars: 观察K线数（0表示观察全部历史数据）
            min_bars_to_lowest: 最低点需要至少间隔的K线数
            min_bars_to_rebound: 反弹需要至少间隔的K线数

        Returns:
            BacktestResult: 回测结果对象

        Raises:
            DataInsufficientError: 数据不足时抛出
        """
        # 确定交易对
        symbol = self._get_symbol(monitor)
        interval = monitor.interval

        # 获取入场点（触发后下一根K线）
        entry_kline = self._get_entry_kline(monitor)
        if not entry_kline:
            raise DataInsufficientError(
                required=1,
                actual=0,
                symbol=symbol,
                interval=interval
            )

        # 获取观察期间的K线数据
        observation_klines = self._get_observation_klines(
            entry_kline, observation_bars
        )
        actual_count = len(observation_klines)
        if actual_count < min_bars_to_lowest:
            raise DataInsufficientError(
                required=min_bars_to_lowest,
                actual=actual_count,
                symbol=symbol,
                interval=interval
            )

        # 计算关键指标
        analysis_result = self._analyze_price_performance(
            entry_kline, observation_klines, min_bars_to_lowest, min_bars_to_rebound
        )

        # 创建回测结果
        backtest_result = self._create_backtest_result(
            monitor, symbol, entry_kline, analysis_result, observation_bars
        )

        return backtest_result

    def _get_symbol(self, monitor: VolumeTrapMonitor) -> str:
        """获取交易对符号。"""
        contract = (
            monitor.futures_contract
            if monitor.futures_contract
            else monitor.spot_contract
        )
        return contract.symbol

    def _get_entry_kline(self, monitor: VolumeTrapMonitor):
        """获取入场K线（触发后的下一根K线）。

        触发时间 T_trigger，找第一根 open_time > T_trigger 的K线作为入场点。
        """
        symbol = self._get_symbol(monitor)
        interval = monitor.interval

        # 找触发时间后的第一根K线
        entry_kline = (
            KLine.objects.filter(
                symbol=symbol,
                interval=interval,
                open_time__gt=monitor.trigger_time,
            )
            .order_by("open_time")
            .first()
        )

        return entry_kline

    def _get_observation_klines(self, entry_kline, observation_bars: int):
        """获取观察期间的K线数据。

        包括入场K线以及后续的K线数据。如果observation_bars为0，则获取全部历史数据。
        """
        if observation_bars > 0:
            limit = observation_bars + 1
            return list(
                KLine.objects.filter(
                    symbol=entry_kline.symbol,
                    interval=entry_kline.interval,
                    open_time__gte=entry_kline.open_time,
                )
                .order_by("open_time")[:limit]
            )
        else:
            return list(
                KLine.objects.filter(
                    symbol=entry_kline.symbol,
                    interval=entry_kline.interval,
                    open_time__gte=entry_kline.open_time,
                )
                .order_by("open_time")
            )

    def _analyze_price_performance(
        self,
        entry_kline,
        holding_klines,
        min_bars_to_lowest: int,
        min_bars_to_rebound: int,
    ):
        """分析持仓期间的价格表现。

        Args:
            entry_kline: 入场K线
            holding_klines: 持仓期间所有K线
            min_bars_to_lowest: 最低点最小间隔
            min_bars_to_rebound: 反弹最小间隔

        Returns:
            dict: 包含分析结果
        """
        entry_price = Decimal(str(entry_kline.close_price))
        kline_list = list(holding_klines)

        # 1. 找到最低点
        lowest_idx, lowest_price = self._find_lowest_point(
            kline_list, min_bars_to_lowest
        )

        # 2. 计算最大盈利（做空视角）
        max_profit_percent = None
        if lowest_idx is not None:
            max_profit_percent = self._calculate_profit_percent(
                entry_price, lowest_price
            )

        # 3. 找到反弹点
        rebound_result = self._find_rebound_point(
            kline_list, lowest_idx, min_bars_to_rebound
        )

        # 4. 计算最大回撤（做空视角的不利波动）
        max_drawdown_percent = self._calculate_max_drawdown(
            entry_price, kline_list
        )

        # 5. 计算最终结果
        exit_price, final_profit_percent, is_profitable = self._calculate_final_result(
            entry_price, kline_list
        )

        return {
            "lowest_idx": lowest_idx,
            "lowest_price": lowest_price,
            "lowest_time": kline_list[lowest_idx].open_time
            if lowest_idx is not None
            else None,
            "bars_to_lowest": lowest_idx,
            "max_profit_percent": max_profit_percent,
            "rebound_result": rebound_result,
            "max_drawdown_percent": max_drawdown_percent,
            "exit_price": exit_price,
            "exit_time": kline_list[-1].open_time if kline_list else None,
            "final_profit_percent": final_profit_percent,
            "is_profitable": is_profitable,
        }

    def _find_lowest_point(self, kline_list, min_bars: int):
        """找到持仓期间的最低点。

        做空策略关注最低点，找到最低价后可以平仓获得最大收益。

        Returns:
            tuple: (index, price) 最低点位置和价格，如果没有找到返回 (None, None)
        """
        if len(kline_list) < min_bars:
            return None, None

        # 在有效范围内寻找最低价
        valid_range = kline_list[min_bars:]
        if not valid_range:
            return None, None

        lowest_kline = min(valid_range, key=lambda k: float(k.low_price))
        lowest_idx = kline_list.index(lowest_kline)

        return lowest_idx, Decimal(str(lowest_kline.low_price))

    def _find_rebound_point(self, kline_list, lowest_idx, min_bars: int):
        """找到反弹点。

        反弹定义为从最低点后，K线上涨超过一定幅度。

        Args:
            kline_list: K线列表
            lowest_idx: 最低点索引
            min_bars: 最小间隔K线数

        Returns:
            dict: 反弹信息
        """
        if lowest_idx is None:
            return {
                "has_rebound": False,
                "rebound_high_price": None,
                "rebound_percent": None,
            }

        # 找到最低点后的所有K线
        rebound_klines = kline_list[lowest_idx + min_bars :]
        if not rebound_klines:
            return {
                "has_rebound": False,
                "rebound_high_price": None,
                "rebound_percent": None,
            }

        # 找到反弹后的最高价
        rebound_high_kline = max(
            rebound_klines, key=lambda k: float(k.high_price)
        )
        rebound_high_price = Decimal(str(rebound_high_kline.high_price))

        # 计算反弹幅度
        lowest_price = Decimal(str(kline_list[lowest_idx].low_price))
        rebound_percent = self._calculate_profit_percent(
            lowest_price, rebound_high_price
        )

        # 判断是否有显著反弹（>20%）
        has_rebound = rebound_percent >= Decimal("20.00")

        return {
            "has_rebound": has_rebound,
            "rebound_high_price": rebound_high_price,
            "rebound_percent": rebound_percent,
        }

    def _calculate_max_drawdown(self, entry_price: Decimal, kline_list):
        """计算最大回撤（做空视角）。

        持仓期间，价格上涨导致的浮亏最大幅度。

        Returns:
            Decimal: 最大回撤百分比
        """
        max_drawdown = Decimal("0")
        entry_price = Decimal(str(entry_price))

        for kline in kline_list:
            current_high = Decimal(str(kline.high_price))
            # 做空时价格上涨导致亏损
            if current_high > entry_price:
                drawdown = self._calculate_profit_percent(
                    entry_price, current_high
                )
                # 取负数表示亏损
                max_drawdown = max(max_drawdown, -drawdown)

        return max_drawdown

    def _calculate_final_result(self, entry_price: Decimal, kline_list):
        """计算最终结果。

        以最后一根K线作为出场点计算收益率。

        Returns:
            tuple: (exit_price, final_profit_percent, is_profitable)
        """
        if not kline_list:
            return None, None, None

        exit_price = Decimal(str(kline_list[-1].close_price))
        final_profit_percent = self._calculate_profit_percent(
            entry_price, exit_price
        )
        is_profitable = final_profit_percent > Decimal("0")

        return exit_price, final_profit_percent, is_profitable

    def _calculate_profit_percent(self, entry_price: Decimal, exit_price: Decimal):
        """计算收益率百分比。

        做空策略：(entry_price - exit_price) / entry_price * 100
        正数表示盈利，负数表示亏损。

        Args:
            entry_price: 入场价格
            exit_price: 出场价格

        Returns:
            Decimal: 收益率百分比
        """
        entry_price = Decimal(str(entry_price))
        exit_price = Decimal(str(exit_price))

        if entry_price == 0:
            return Decimal("0")

        profit_percent = (entry_price - exit_price) / entry_price * Decimal(
            "100"
        )
        return profit_percent.quantize(Decimal("0.01"))

    def _create_backtest_result(
        self,
        monitor: VolumeTrapMonitor,
        symbol: str,
        entry_kline,
        analysis_result,
        observation_bars: int,
    ):
        """创建回测结果对象。"""
        rebound_result = analysis_result["rebound_result"]

        backtest_result = BacktestResult.objects.create(
            monitor=monitor,
            symbol=symbol,
            interval=monitor.interval,
            market_type=monitor.market_type,
            entry_time=entry_kline.open_time,
            entry_price=Decimal(str(entry_kline.close_price)),
            lowest_time=analysis_result["lowest_time"],
            lowest_price=analysis_result["lowest_price"],
            bars_to_lowest=analysis_result["bars_to_lowest"],
            max_profit_percent=analysis_result["max_profit_percent"],
            has_rebound=rebound_result["has_rebound"],
            rebound_high_price=rebound_result["rebound_high_price"],
            rebound_percent=rebound_result["rebound_percent"],
            max_drawdown_percent=analysis_result["max_drawdown_percent"],
            exit_time=analysis_result["exit_time"],
            exit_price=analysis_result["exit_price"],
            final_profit_percent=analysis_result["final_profit_percent"],
            is_profitable=analysis_result["is_profitable"],
            observation_bars=observation_bars,
            status="completed",
        )

        return backtest_result


class BatchBacktestRunner:
    """批量回测运行器。

    对一批异常事件进行批量回测分析。
    """

    def __init__(self):
        self.engine = VolumeTrapBacktestEngine()

    def run_batch_backtest(
        self,
        monitors_queryset,
        observation_bars: int = 0,
        skip_on_error: bool = True,
    ):
        """批量运行回测。

        Args:
            monitors_queryset: 异常事件查询集
            observation_bars: 观察K线数
            skip_on_error: 遇到错误时是否跳过

        Returns:
            tuple: (成功数量, 失败数量, 错误列表)
        """
        success_count = 0
        error_count = 0
        errors = []

        for monitor in monitors_queryset:
            try:
                # 检查是否已有回测结果
                if hasattr(monitor, "backtest_result"):
                    continue

                self.engine.run_backtest(monitor, observation_bars)
                success_count += 1

            except Exception as e:
                error_count += 1
                if not skip_on_error:
                    raise

                errors.append(
                    {
                        "monitor_id": monitor.id,
                        "symbol": self.engine._get_symbol(monitor),
                        "error": str(e),
                    }
                )

        return success_count, error_count, errors
