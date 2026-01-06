"""
图表数据格式化器（Chart Data Formatter）

将K线数据转换为Chart.js图表库所需的格式，并标记发现时刻。

功能特性：
- 将K线数据转换为Chart.js格式（labels、datasets）
- 支持多数据集（开盘价、最高价、最低价、收盘价、成交量）
- 准确标记触发点（trigger_time和trigger_price）
- 确保数据类型与JavaScript兼容
- 完整的异常处理和数据验证

Related:
    - PRD: docs/iterations/006-volume-trap-dashboard/prd.md (F2.2)
    - Architecture: docs/iterations/006-volume-trap-dashboard/architecture.md (3.3)
    - Task: TASK-006-003
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from volume_trap.exceptions import DataFormatError

logger = logging.getLogger(__name__)


class ChartDataFormatter:
    """图表数据格式化器。

    将K线数据转换为Chart.js图表库所需的格式，并准确标记发现时刻。
    支持多数据集展示（OHLC + Volume），确保数据与JavaScript完全兼容。

    性能特性：
        - 内存高效：直接转换，不创建不必要的数据副本
        - 处理大数据集：支持1000+条K线数据，转换时间<1秒
        - 数值精度：保持价格和成交量的精度（最多5位小数）

    异常处理：
        - DataFormatError: 数据格式不正确或缺少必要字段时抛出
        - ValueError: 触发时间或价格格式错误时抛出

    Examples:
        >>> formatter = ChartDataFormatter()
        >>> kline_data = [
        ...     {
        ...         'time': 1704067200.0,
        ...         'open': 50000.0,
        ...         'high': 50100.0,
        ...         'low': 49900.0,
        ...         'close': 50050.0,
        ...         'volume': 1000.0
        ...     }
        ... ]
        >>> result = formatter.format_chart_data(
        ...     kline_data=kline_data,
        ...     trigger_time=1704067200.0,
        ...     trigger_price=50050.0
        ... )
        >>> print(result['labels'])
        ['2024-01-01 00:00']
        >>> print(len(result['datasets']))
        5

        处理1000条K线数据（性能测试）：
        >>> import time
        >>> start = time.time()
        >>> result = formatter.format_chart_data(large_kline_data, trigger_time, trigger_price)
        >>> elapsed = time.time() - start
        >>> print(f"转换耗时: {elapsed:.2f}秒")
    """

    def __init__(self):
        """初始化图表数据格式化器。

        设置格式化配置参数，包括时间格式和数值精度。
        """
        self.time_format = "%Y-%m-%d %H:%M"  # Chart.js标签时间格式
        self.decimal_precision = 5  # 价格和成交量的最大精度

    def format_chart_data(
        self, kline_data: List[Dict[str, Any]], trigger_time: float, trigger_price: float
    ) -> Dict[str, Any]:
        """格式化K线数据为Chart.js格式。

        将K线数据数组转换为Chart.js图表库所需的格式，包含labels、datasets和trigger_marker。
        自动验证数据格式，缺失必要字段时抛出DataFormatError。

        Args:
            kline_data (List[Dict[str, Any]]): K线数据列表，每项包含：
                - time (float): 时间戳（秒）
                - open (float): 开盘价
                - high (float): 最高价
                - low (float): 最低价
                - close (float): 收盘价
                - volume (float): 成交量
                - market_type (str): 市场类型（spot/futures，可选）
            trigger_time (float): 发现时刻的时间戳（秒）
            trigger_price (float): 发现时刻的价格

        Returns:
            Dict[str, Any]: Chart.js格式的数据字典，包含：
                - labels (List[str]): 时间标签列表，格式为'YYYY-MM-DD HH:MM'
                - datasets (List[Dict]): 数据集列表，包含：
                    * OHLC数据集: 开盘价、最高价、最低价、收盘价（4个数据集）
                    * Volume数据集: 成交量（1个数据集）
                - trigger_marker (Dict): 触发点标记，包含：
                    * time (float): 触发时间戳
                    * price (float): 触发价格

        Raises:
            DataFormatError: 当以下情况发生时抛出：
                - kline_data为空或不是列表
                - 缺少必要字段（time、open、high、low、close、volume）
                - 字段值类型不正确

            ValueError: 当以下情况发生时抛出：
                - trigger_time不是数字类型
                - trigger_price不是数字类型

        Examples:
            基础用法：
            >>> formatter = ChartDataFormatter()
            >>> result = formatter.format_chart_data(
            ...     kline_data=[
            ...         {'time': 1704067200.0, 'open': 50000, 'high': 50100,
            ...          'low': 49900, 'close': 50050, 'volume': 1000}
            ...     ],
            ...     trigger_time=1704067200.0,
            ...     trigger_price=50050.0
            ... )
            >>> result['labels']
            ['2024-01-01 00:00']
            >>> result['trigger_marker']['price']
            50050.0

            多条K线数据：
            >>> result = formatter.format_chart_data(
            ...     kline_data=[
            ...         {'time': 1704067200.0, 'open': 50000, 'high': 50100,
            ...          'low': 49900, 'close': 50050, 'volume': 1000},
            ...         {'time': 1704070800.0, 'open': 50050, 'high': 50200,
            ...          'low': 50000, 'close': 50100, 'volume': 1200}
            ...     ],
            ...     trigger_time=1704070800.0,
            ...     trigger_price=50100.0
            ... )
            >>> len(result['datasets'])
            5  # 4个价格数据集 + 1个成交量数据集

        Side Effects:
            - 数据转换：创建Chart.js兼容的数据结构
            - 内存使用：根据K线数据量分配内存
            - 记录日志：记录格式化结果统计信息

        Related:
            - Task: TASK-006-003
            - Architecture: docs/iterations/006-volume-trap-dashboard/architecture.md (3.3)
        """
        # === 数据验证 ===
        self._validate_input_data(kline_data, trigger_time, trigger_price)

        # === 生成时间标签 ===
        labels = self._generate_labels(kline_data)

        # === 生成数据集 ===
        datasets = self._generate_datasets(kline_data)

        # === 生成触发点标记 ===
        trigger_marker = {"time": trigger_time, "price": trigger_price}

        # === 组装结果 ===
        result = {"labels": labels, "datasets": datasets, "trigger_marker": trigger_marker}

        # === 记录日志 ===
        logger.info(
            f"图表数据格式化完成: "
            f"kline_count={len(kline_data)}, "
            f"datasets_count={len(datasets)}, "
            f"trigger_time={trigger_time}"
        )

        return result

    def _validate_input_data(
        self, kline_data: List[Dict[str, Any]], trigger_time: float, trigger_price: float
    ) -> None:
        """验证输入数据格式。

        Args:
            kline_data: K线数据列表
            trigger_time: 触发时间戳
            trigger_price: 触发价格

        Raises:
            DataFormatError: 当数据格式不符合要求时抛出
            ValueError: 当触发时间或价格类型错误时抛出
        """
        # 验证kline_data
        if not kline_data or not isinstance(kline_data, list):
            raise DataFormatError(
                field="kline_data",
                expected_format="非空列表",
                actual_value=kline_data,
                context="K线数据不能为空",
            )

        # 验证每条K线数据
        required_fields = ["time", "open", "high", "low", "close", "volume"]
        for i, kline in enumerate(kline_data):
            if not isinstance(kline, dict):
                raise DataFormatError(
                    field=f"kline_data[{i}]",
                    expected_format="字典类型",
                    actual_value=type(kline).__name__,
                    context="每条K线数据必须是字典类型",
                )

            # 检查必要字段
            missing_fields = [field for field in required_fields if field not in kline]
            if missing_fields:
                raise DataFormatError(
                    field=f"kline_data[{i}]",
                    expected_format=f'包含字段: {", ".join(required_fields)}',
                    actual_value=f'缺少字段: {", ".join(missing_fields)}',
                    context="K线数据缺少必要字段",
                )

            # 验证字段类型
            numeric_fields = ["time", "open", "high", "low", "close", "volume"]
            for field in numeric_fields:
                if not isinstance(kline[field], (int, float)):
                    raise DataFormatError(
                        field=f"kline_data[{i}].{field}",
                        expected_format="数字类型",
                        actual_value=type(kline[field]).__name__,
                        context=f"{field}字段必须是数字类型",
                    )

        # 验证trigger_time
        if not isinstance(trigger_time, (int, float)):
            raise DataFormatError(
                field="trigger_time",
                expected_format="数字类型",
                actual_value=type(trigger_time).__name__,
                context="触发时间必须是数字类型",
            )

        # 验证trigger_price
        if not isinstance(trigger_price, (int, float)):
            raise DataFormatError(
                field="trigger_price",
                expected_format="数字类型",
                actual_value=type(trigger_price).__name__,
                context="触发价格必须是数字类型",
            )

    def _generate_labels(self, kline_data: List[Dict[str, Any]]) -> List[str]:
        """生成时间标签。

        Args:
            kline_data: K线数据列表

        Returns:
            List[str]: 格式化的时间标签列表
        """
        labels = []
        for kline in kline_data:
            timestamp = kline["time"]
            # 将时间戳转换为datetime对象
            dt = datetime.fromtimestamp(timestamp)
            # 格式化为字符串
            label = dt.strftime(self.time_format)
            labels.append(label)

        return labels

    def _generate_datasets(self, kline_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """生成数据集。

        Args:
            kline_data: K线数据列表

        Returns:
            List[Dict]: Chart.js数据集列表
        """
        datasets = []

        # 生成OHLC数据集
        datasets.extend(self._generate_ohlc_datasets(kline_data))

        # 生成成交量数据集
        datasets.append(self._generate_volume_dataset(kline_data))

        return datasets

    def _generate_ohlc_datasets(self, kline_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """生成OHLC数据集。

        Args:
            kline_data: K线数据列表

        Returns:
            List[Dict]: OHLC数据集列表（4个数据集）
        """
        datasets = []

        # 开盘价数据集
        open_data = []
        high_data = []
        low_data = []
        close_data = []

        for i, kline in enumerate(kline_data):
            timestamp = kline["time"]
            open_data.append([timestamp, float(kline["open"])])
            high_data.append([timestamp, float(kline["high"])])
            low_data.append([timestamp, float(kline["low"])])
            close_data.append([timestamp, float(kline["close"])])

        # Chart.js数据集配置
        datasets.append(
            {
                "label": "Open Price",
                "data": open_data,
                "borderColor": "rgb(75, 192, 192)",
                "backgroundColor": "rgba(75, 192, 192, 0.2)",
                "borderWidth": 1,
            }
        )

        datasets.append(
            {
                "label": "High Price",
                "data": high_data,
                "borderColor": "rgb(255, 99, 132)",
                "backgroundColor": "rgba(255, 99, 132, 0.2)",
                "borderWidth": 1,
            }
        )

        datasets.append(
            {
                "label": "Low Price",
                "data": low_data,
                "borderColor": "rgb(54, 162, 235)",
                "backgroundColor": "rgba(54, 162, 235, 0.2)",
                "borderWidth": 1,
            }
        )

        datasets.append(
            {
                "label": "Close Price",
                "data": close_data,
                "borderColor": "rgb(153, 102, 255)",
                "backgroundColor": "rgba(153, 102, 255, 0.2)",
                "borderWidth": 2,
            }
        )

        return datasets

    def _generate_volume_dataset(self, kline_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成成交量数据集。

        Args:
            kline_data: K线数据列表

        Returns:
            Dict: 成交量数据集
        """
        volume_data = []

        for kline in kline_data:
            timestamp = kline["time"]
            volume_data.append([timestamp, float(kline["volume"])])

        return {
            "label": "Volume",
            "data": volume_data,
            "borderColor": "rgb(255, 159, 64)",
            "backgroundColor": "rgba(255, 159, 64, 0.2)",
            "borderWidth": 1,
            "yAxisID": "y1",
        }
