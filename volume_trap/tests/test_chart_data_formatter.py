"""
ChartDataFormatter单元测试

测试ChartDataFormatter核心功能，包括：
- format_chart_data方法基本转换
- Chart.js格式数据生成
- 数据类型转换（JavaScript兼容）
- 触发点标记功能
- 异常情况处理（数据格式错误、缺失字段等）

Related:
    - PRD: docs/iterations/006-volume-trap-dashboard/prd.md (F2.2)
    - Architecture: docs/iterations/006-volume-trap-dashboard/architecture.md (3.3)
    - Task: TASK-006-003
"""

import unittest
from datetime import datetime, timedelta

from django.test import TestCase
from django.utils import timezone as django_timezone

from volume_trap.exceptions import DataFormatError
from volume_trap.services.chart_data_formatter import ChartDataFormatter


class ChartDataFormatterInitTest(TestCase):
    """测试ChartDataFormatter初始化。"""

    def test_init_success(self):
        """测试服务初始化成功。"""
        formatter = ChartDataFormatter()

        self.assertIsNotNone(formatter)


class ChartDataFormatterFormatChartDataTest(TestCase):
    """测试format_chart_data方法。"""

    def setUp(self):
        """测试前准备：创建测试数据。"""
        self.formatter = ChartDataFormatter()
        self.now = django_timezone.now()

        # 创建测试K线数据（来自KLineDataService的返回格式）
        self.kline_data = [
            {
                "time": (self.now - timedelta(hours=8)).timestamp(),
                "open": 50000.0,
                "high": 50100.0,
                "low": 49900.0,
                "close": 50050.0,
                "volume": 1000.0,
                "market_type": "futures",
            },
            {
                "time": (self.now - timedelta(hours=4)).timestamp(),
                "open": 50050.0,
                "high": 50200.0,
                "low": 50000.0,
                "close": 50100.0,
                "volume": 1200.0,
                "market_type": "futures",
            },
            {
                "time": self.now.timestamp(),
                "open": 50100.0,
                "high": 50300.0,
                "low": 50050.0,
                "close": 50200.0,
                "volume": 1500.0,
                "market_type": "futures",
            },
        ]

        # 触发点（Discovery时刻）
        self.trigger_time = (self.now - timedelta(hours=4)).timestamp()
        self.trigger_price = 50100.0

    def test_format_chart_data_valid_input(self):
        """测试有效输入：应返回Chart.js格式数据。"""
        result = self.formatter.format_chart_data(
            kline_data=self.kline_data,
            trigger_time=self.trigger_time,
            trigger_price=self.trigger_price,
        )

        # 验证返回结构
        self.assertIsInstance(result, dict)
        self.assertIn("labels", result)
        self.assertIn("datasets", result)
        self.assertIn("trigger_marker", result)

        # 验证labels
        self.assertIsInstance(result["labels"], list)
        self.assertEqual(len(result["labels"]), 3)

        # 验证datasets
        self.assertIsInstance(result["datasets"], list)
        self.assertGreater(len(result["datasets"]), 0)

        # 验证trigger_marker
        self.assertIsInstance(result["trigger_marker"], dict)
        self.assertIn("time", result["trigger_marker"])
        self.assertIn("price", result["trigger_marker"])

        # 验证触发点标记准确性
        self.assertEqual(result["trigger_marker"]["time"], self.trigger_time)
        self.assertEqual(result["trigger_marker"]["price"], self.trigger_price)

    def test_format_chart_data_data_type_conversion(self):
        """测试数据类型转换：确保所有数值转换为JavaScript兼容格式。"""
        result = self.formatter.format_chart_data(
            kline_data=self.kline_data,
            trigger_time=self.trigger_time,
            trigger_price=self.trigger_price,
        )

        # 验证labels为字符串（JavaScript时间戳）
        for label in result["labels"]:
            self.assertIsInstance(label, str)

        # 验证datasets中的数值为float
        for dataset in result["datasets"]:
            if "data" in dataset:
                for data_point in dataset["data"]:
                    if isinstance(data_point, (list, tuple)) and len(data_point) >= 2:
                        # y值应该是float
                        self.assertIsInstance(data_point[1], (int, float))

    def test_format_chart_data_empty_kline_data(self):
        """测试空K线数据：应抛出DataFormatError。"""
        with self.assertRaises(DataFormatError) as context:
            self.formatter.format_chart_data(
                kline_data=[], trigger_time=self.trigger_time, trigger_price=self.trigger_price
            )

        self.assertIn("kline_data", str(context.exception))
        self.assertIn("不能为空", str(context.exception))

    def test_format_chart_data_missing_required_fields(self):
        """测试缺失必要字段：应抛出DataFormatError。"""
        # 缺少必要字段的K线数据
        invalid_kline_data = [
            {
                "time": self.now.timestamp(),
                "open": 50000.0,
                # 缺少 'high', 'low', 'close' 字段
                "volume": 1000.0,
            }
        ]

        with self.assertRaises(DataFormatError) as context:
            self.formatter.format_chart_data(
                kline_data=invalid_kline_data,
                trigger_time=self.trigger_time,
                trigger_price=self.trigger_price,
            )

        self.assertIn("high", str(context.exception))
        self.assertIn("low", str(context.exception))
        self.assertIn("close", str(context.exception))

    def test_format_chart_data_invalid_trigger_time(self):
        """测试无效触发时间：应抛出DataFormatError。"""
        with self.assertRaises(DataFormatError) as context:
            self.formatter.format_chart_data(
                kline_data=self.kline_data,
                trigger_time="invalid_time",  # 应该是数字时间戳
                trigger_price=self.trigger_price,
            )

        self.assertIn("trigger_time", str(context.exception))

    def test_format_chart_data_invalid_trigger_price(self):
        """测试无效触发价格：应抛出DataFormatError。"""
        with self.assertRaises(DataFormatError) as context:
            self.formatter.format_chart_data(
                kline_data=self.kline_data,
                trigger_time=self.trigger_time,
                trigger_price="invalid_price",  # 应该是数字
            )

        self.assertIn("trigger_price", str(context.exception))

    def test_format_chart_data_trigger_point_not_in_range(self):
        """测试触发点不在K线数据时间范围内：应仍能标记。"""
        # 触发时间超出K线数据范围
        trigger_time_out_of_range = (self.now + timedelta(hours=10)).timestamp()

        result = self.formatter.format_chart_data(
            kline_data=self.kline_data,
            trigger_time=trigger_time_out_of_range,
            trigger_price=self.trigger_price,
        )

        # 应该仍然返回结果，但触发点标记可能超出图表范围
        self.assertIn("trigger_marker", result)
        self.assertEqual(result["trigger_marker"]["time"], trigger_time_out_of_range)

    def test_format_chart_data_multiple_datasets(self):
        """测试返回多个数据集（开盘价、最高价、最低价、收盘价、成交量）。"""
        result = self.formatter.format_chart_data(
            kline_data=self.kline_data,
            trigger_time=self.trigger_time,
            trigger_price=self.trigger_price,
        )

        # 验证多个数据集
        self.assertGreater(len(result["datasets"]), 1)

        # 验证数据集包含价格和成交量数据
        dataset_labels = [ds.get("label", "") for ds in result["datasets"]]
        has_price_data = any(
            "price" in label.lower() or "close" in label.lower() for label in dataset_labels
        )
        has_volume_data = any("volume" in label.lower() for label in dataset_labels)

        self.assertTrue(has_price_data, "应该包含价格数据集")
        self.assertTrue(has_volume_data, "应该包含成交量数据集")

    def test_format_chart_data_single_kline(self):
        """测试单条K线数据：应正确处理。"""
        single_kline = [self.kline_data[1]]  # 只取一条K线

        result = self.formatter.format_chart_data(
            kline_data=single_kline,
            trigger_time=self.trigger_time,
            trigger_price=self.trigger_price,
        )

        # 验证返回结构
        self.assertEqual(len(result["labels"]), 1)
        self.assertEqual(len(result["datasets"][0]["data"]), 1)

    def test_format_chart_data_large_dataset(self):
        """测试大数据集：应能处理大量K线数据（性能测试）。"""
        import time

        # 创建1000条K线数据
        large_kline_data = []
        base_time = self.now.timestamp()
        for i in range(1000):
            large_kline_data.append(
                {
                    "time": base_time - (1000 - i) * 3600,  # 每小时一条
                    "open": 50000.0 + i,
                    "high": 50100.0 + i,
                    "low": 49900.0 + i,
                    "close": 50050.0 + i,
                    "volume": 1000.0 + i,
                    "market_type": "futures",
                }
            )

        start = time.time()
        result = self.formatter.format_chart_data(
            kline_data=large_kline_data,
            trigger_time=self.trigger_time,
            trigger_price=self.trigger_price,
        )
        elapsed = time.time() - start

        # 验证性能（应在1秒内完成）
        self.assertLess(elapsed, 1.0, f"处理1000条数据耗时{elapsed:.2f}秒，超过1秒限制")

        # 验证结果正确性
        self.assertEqual(len(result["labels"]), 1000)
        self.assertIn("trigger_marker", result)

    def test_format_chart_data_precision(self):
        """测试数值精度：确保价格和成交量的精度保持。"""
        # 使用高精度数据
        precise_kline_data = [
            {
                "time": self.now.timestamp(),
                "open": 50000.12345,
                "high": 50100.67890,
                "low": 49900.98765,
                "close": 50050.54321,
                "volume": 1000.123456789,
                "market_type": "futures",
            }
        ]

        result = self.formatter.format_chart_data(
            kline_data=precise_kline_data, trigger_time=self.trigger_time, trigger_price=50050.54321
        )

        # 验证精度保持（允许小的浮点误差）
        # 收盘价在第4个数据集中（索引3）
        dataset = result["datasets"][3]  # Close Price dataset
        if "data" in dataset and len(dataset["data"]) > 0:
            first_data_point = dataset["data"][0]
            if isinstance(first_data_point, (list, tuple)) and len(first_data_point) >= 2:
                close_price = first_data_point[1]
                self.assertAlmostEqual(close_price, 50050.54321, places=5)
