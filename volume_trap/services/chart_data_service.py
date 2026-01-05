"""
Volume Trap 图表数据服务

提供K线图表数据的格式化和关键点标注功能。

Related:
    - PRD: docs/iterations/007-backtest-framework/prd.md
    - Architecture: docs/iterations/007-backtest-framework/architecture.md
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

from django.db.models import QuerySet

from backtest.models import KLine
from volume_trap.models import BacktestResult


class ChartDataService:
    """图表数据服务。

    负责将K线数据和回测结果转换为Chart.js可用的格式，并标注关键点位。

    Examples:
        >>> service = ChartDataService()
        >>> chart_data = service.get_kline_chart_data(backtest_id=1)
        >>> print(f"K线数据点: {len(chart_data['candles'])}")
    """

    def get_kline_chart_data(
        self,
        backtest_result: BacktestResult,
        max_bars: int = 500,
    ) -> Dict:
        """获取K线图表数据。

        Args:
            backtest_result: 回测结果对象
            max_bars: 最大K线数量（用于性能优化）

        Returns:
            dict: 包含K线数据、关键点标注和元数据的字典
        """
        # 获取K线数据
        klines = self._get_klines_for_chart(
            backtest_result, max_bars
        )

        # 转换为Chart.js格式
        candles = self._format_klines(klines)

        # 添加关键点标注
        annotations = self._create_annotations(backtest_result, klines)

        # 计算技术指标（可选）
        indicators = self._calculate_indicators(klines)

        return {
            "symbol": backtest_result.symbol,
            "interval": backtest_result.interval,
            "candles": candles,
            "annotations": annotations,
            "indicators": indicators,
            "metadata": {
                "entry_time": backtest_result.entry_time.isoformat(),
                "entry_price": str(backtest_result.entry_price),
                "exit_time": backtest_result.exit_time.isoformat() if backtest_result.exit_time else None,
                "exit_price": str(backtest_result.exit_price) if backtest_result.exit_price else None,
                "total_bars": len(klines),
                "observation_bars": backtest_result.observation_bars,
            },
        }

    def _get_klines_for_chart(
        self,
        backtest_result: BacktestResult,
        max_bars: int,
        start_date: datetime = None,
    ) -> List[KLine]:
        """获取用于图表的K线数据。

        Args:
            backtest_result: 回测结果对象
            max_bars: 最大K线数量
            start_date: 起始日期（默认2025-01-01）

        Returns:
            List[KLine]: K线对象列表
        """
        # 默认从2025-01-01开始获取全量数据
        if start_date is None:
            start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)

        # 查询K线数据：从起始日期到当前
        queryset = KLine.objects.filter(
            symbol=backtest_result.symbol,
            interval=backtest_result.interval,
            open_time__gte=start_date,
        )

        # 按时间排序
        klines = list(queryset.order_by("open_time"))

        # 如果数据量过大，进行压缩
        if len(klines) > max_bars:
            klines = self._compress_klines(klines, max_bars)

        return klines

    def _format_klines(self, klines: List[KLine]) -> List[Dict]:
        """格式化K线数据为Chart.js格式。

        Args:
            klines: K线对象列表

        Returns:
            List[Dict]: 格式化的K线数据
        """
        candles = []

        for kline in klines:
            candles.append({
                "t": int(kline.open_time.timestamp() * 1000),  # 转换为毫秒时间戳
                "o": float(kline.open_price),
                "h": float(kline.high_price),
                "l": float(kline.low_price),
                "c": float(kline.close_price),
                "v": float(kline.volume),
            })

        return candles

    def _create_annotations(
        self,
        backtest_result: BacktestResult,
        klines: List[KLine],
    ) -> Dict:
        """创建关键点标注。

        Args:
            backtest_result: 回测结果对象
            klines: K线对象列表

        Returns:
            dict: 关键点标注数据
        """
        annotations = {
            "entry": None,
            "lowest": None,
            "exit": None,
            "rebound_high": None,
        }

        # 入场点标注
        if backtest_result.entry_time and backtest_result.entry_price:
            annotations["entry"] = {
                "time": int(backtest_result.entry_time.timestamp() * 1000),
                "price": float(backtest_result.entry_price),
                "label": "入场",
                "color": "#4CAF50",  # 绿色
            }

        # 最低点标注
        if backtest_result.lowest_time and backtest_result.lowest_price:
            annotations["lowest"] = {
                "time": int(backtest_result.lowest_time.timestamp() * 1000),
                "price": float(backtest_result.lowest_price),
                "label": "最低点",
                "color": "#F44336",  # 红色
            }

        # 出场点标注
        if backtest_result.exit_time and backtest_result.exit_price:
            annotations["exit"] = {
                "time": int(backtest_result.exit_time.timestamp() * 1000),
                "price": float(backtest_result.exit_price),
                "label": "出场",
                "color": "#9E9E9E",  # 灰色
            }

        # 反弹高点标注
        if (
            backtest_result.has_rebound
            and backtest_result.rebound_high_price
            and backtest_result.rebound_percent
        ):
            # 找到反弹最高价对应的K线
            rebound_kline = None
            if backtest_result.lowest_time:
                rebound_kline = next(
                    (k for k in klines if k.open_time > backtest_result.lowest_time),
                    None,
                )

            if rebound_kline:
                annotations["rebound_high"] = {
                    "time": int(rebound_kline.open_time.timestamp() * 1000),
                    "price": float(backtest_result.rebound_high_price),
                    "label": f"反弹 {backtest_result.rebound_percent}%",
                    "color": "#FF9800",  # 橙色
                }

        return annotations

    def _calculate_indicators(self, klines: List[KLine]) -> Dict:
        """计算技术指标。

        计算MA7/MA25/MA99移动平均线和MACD指标。

        Args:
            klines: K线对象列表

        Returns:
            dict: 技术指标数据，包含ma7, ma25, ma99, macd
        """
        indicators = {}

        # 计算MA7
        if len(klines) >= 7:
            indicators["ma7"] = self._calculate_moving_average(klines, 7)

        # 计算MA25
        if len(klines) >= 25:
            indicators["ma25"] = self._calculate_moving_average(klines, 25)

        # 计算MA99
        if len(klines) >= 99:
            indicators["ma99"] = self._calculate_moving_average(klines, 99)

        # 计算MACD (12, 26, 9)
        if len(klines) >= 35:  # 至少需要26+9=35根K线
            indicators["macd"] = self._calculate_macd(klines)

        return indicators

    def _calculate_macd(
        self,
        klines: List[KLine],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> Dict:
        """计算MACD指标。

        MACD = EMA(12) - EMA(26)
        Signal = EMA(MACD, 9)
        Histogram = MACD - Signal

        Args:
            klines: K线对象列表
            fast_period: 快线周期，默认12
            slow_period: 慢线周期，默认26
            signal_period: 信号线周期，默认9

        Returns:
            dict: 包含dif, dea, histogram的数据
        """
        close_prices = [float(k.close_price) for k in klines]
        timestamps = [int(k.open_time.timestamp() * 1000) for k in klines]

        # 计算EMA
        ema_fast = self._calculate_ema(close_prices, fast_period)
        ema_slow = self._calculate_ema(close_prices, slow_period)

        # 计算DIF (MACD线)
        dif = []
        start_idx = slow_period - 1
        for i in range(start_idx, len(close_prices)):
            dif_value = ema_fast[i] - ema_slow[i]
            dif.append(dif_value)

        # 计算DEA (信号线)
        dea = self._calculate_ema(dif, signal_period)

        # 计算Histogram (柱状图)
        histogram = []
        dif_data = []
        dea_data = []

        signal_start = signal_period - 1
        for i in range(signal_start, len(dif)):
            hist_value = (dif[i] - dea[i]) * 2  # 乘2使柱状图更明显
            timestamp = timestamps[start_idx + i]

            dif_data.append({"t": timestamp, "value": round(dif[i], 8)})
            dea_data.append({"t": timestamp, "value": round(dea[i], 8)})
            histogram.append({"t": timestamp, "value": round(hist_value, 8)})

        return {
            "dif": dif_data,
            "dea": dea_data,
            "histogram": histogram,
        }

    def _calculate_ema(self, prices: List[float], period: int) -> List[float]:
        """计算指数移动平均线。

        Args:
            prices: 价格列表
            period: 周期

        Returns:
            List[float]: EMA值列表（与prices长度相同）
        """
        if len(prices) < period:
            return []

        ema = [0.0] * len(prices)
        multiplier = 2 / (period + 1)

        # 初始EMA使用SMA
        sma = sum(prices[:period]) / period
        ema[period - 1] = sma

        # 计算后续EMA
        for i in range(period, len(prices)):
            ema[i] = (prices[i] - ema[i - 1]) * multiplier + ema[i - 1]

        return ema

    def _calculate_moving_average(self, klines: List[KLine], period: int) -> List[Dict]:
        """计算移动平均线。

        Args:
            klines: K线对象列表
            period: 周期

        Returns:
            List[Dict]: MA数据点
        """
        ma_data = []

        for i in range(period - 1, len(klines)):
            # 计算平均值
            prices = [float(k.close_price) for k in klines[i - period + 1 : i + 1]]
            ma_value = sum(prices) / period

            ma_data.append({
                "t": int(klines[i].open_time.timestamp() * 1000),
                "value": round(ma_value, 8),
            })

        return ma_data

    def _compress_klines(self, klines: List[KLine], max_bars: int) -> List[KLine]:
        """压缩K线数据（用于大数据量优化）。

        Args:
            klines: 原始K线列表
            max_bars: 最大保留数量

        Returns:
            List[KLine]: 压缩后的K线列表
        """
        if len(klines) <= max_bars:
            return klines

        # 简单的抽样压缩策略
        step = len(klines) // max_bars
        compressed = klines[::step]

        # 确保包含最后一个K线
        if compressed[-1] != klines[-1]:
            compressed.append(klines[-1])

        return compressed

    def get_price_series(
        self,
        backtest_result: BacktestResult,
        include_indicators: bool = True,
    ) -> Dict:
        """获取价格时间序列数据（用于简单图表）。

        Args:
            backtest_result: 回测结果对象
            include_indicators: 是否包含技术指标

        Returns:
            dict: 价格序列数据
        """
        # 获取K线数据
        klines = self._get_klines_for_chart(backtest_result, 1000)

        # 构建时间序列
        time_series = []
        for kline in klines:
            time_series.append({
                "time": int(kline.open_time.timestamp() * 1000),
                "price": float(kline.close_price),
            })

        # 添加技术指标（如果需要）
        indicators = {}
        if include_indicators:
            indicators = self._calculate_indicators(klines)

        return {
            "symbol": backtest_result.symbol,
            "interval": backtest_result.interval,
            "series": time_series,
            "indicators": indicators,
            "annotations": self._create_annotations(backtest_result, klines),
        }

    def export_chart_data(
        self,
        backtest_result: BacktestResult,
        format: str = "json",
    ) -> str:
        """导出图表数据。

        Args:
            backtest_result: 回测结果对象
            format: 导出格式（json/csv）

        Returns:
            str: 导出的数据字符串
        """
        import json

        chart_data = self.get_kline_chart_data(backtest_result)

        if format.lower() == "json":
            return json.dumps(chart_data, indent=2, ensure_ascii=False)
        elif format.lower() == "csv":
            # 简化的CSV导出
            candles = chart_data["candles"]
            csv_lines = ["timestamp,open,high,low,close,volume"]

            for candle in candles:
                csv_lines.append(
                    f"{candle['t']},{candle['o']},{candle['h']},{candle['l']},{candle['c']},{candle['v']}"
                )

            return "\n".join(csv_lines)
        else:
            raise ValueError(f"不支持的导出格式: {format}")
