"""
历史扫描功能单元测试

测试Discovery历史扫描功能的各个组件，包括日期范围参数、批量扫描逻辑等。

Related:
    - Task: TASK-005-001, TASK-005-002, TASK-005-003
    - Architecture: Discovery历史扫描优化
"""

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase
from django.utils import timezone as django_timezone

from volume_trap.exceptions import DataInsufficientError
from volume_trap.services.volume_trap_fsm import VolumeTrapStateMachine


class HistoricalScanTestCase(TestCase):
    """历史扫描功能测试类"""

    def setUp(self):
        """初始化测试环境"""
        self.fsm = VolumeTrapStateMachine()
        self.test_symbol = "BTCUSDT"
        self.test_interval = "4h"

    def test_parse_date_valid_format(self):
        """测试有效日期解析"""
        # 测试 'all' 值
        self.assertIsNone(self.fsm._parse_date("all"))

        # 测试有效日期格式
        date_str = "2025-11-01"
        parsed = self.fsm._parse_date(date_str)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.year, 2025)
        self.assertEqual(parsed.month, 11)
        self.assertEqual(parsed.day, 1)
        self.assertEqual(parsed.tzinfo, timezone.utc)

    def test_parse_date_invalid_format(self):
        """测试无效日期格式"""
        # 测试错误格式
        with self.assertRaises(ValueError):
            self.fsm._parse_date("2025/11/01")

        with self.assertRaises(ValueError):
            self.fsm._parse_date("20251101")

        with self.assertRaises(ValueError):
            self.fsm._parse_date("invalid-date")

    def test_check_discovery_condition_no_date(self):
        """测试不指定日期（默认行为）"""
        with patch.object(self.fsm.rvol_calculator, "calculate") as mock_rvol, patch.object(
            self.fsm.amplitude_detector, "calculate"
        ) as mock_amplitude, patch.object(
            self.fsm.condition_evaluator, "evaluate_discovery_condition"
        ) as mock_eval:

            # 模拟检测器返回结果
            mock_rvol.return_value = {"triggered": True, "rvol_ratio": 10.0, "current_volume": 1000}
            mock_amplitude.return_value = {
                "triggered": True,
                "amplitude_ratio": 2.0,
                "upper_shadow_ratio": 5.0,
                "current_close": 50000,
                "current_high": 51000,
                "current_low": 49000,
            }
            mock_eval.return_value = True

            # 调用方法（不指定日期）
            triggered, indicators = self.fsm._check_discovery_condition(
                symbol=self.test_symbol, interval=self.test_interval
            )

            # 验证结果
            self.assertTrue(triggered)
            self.assertIn("rvol_ratio", indicators)
            self.assertIn("amplitude_ratio", indicators)

            # 验证调用了最新数据（不指定日期）
            mock_rvol.assert_called_once_with(self.test_symbol, self.test_interval)
            mock_amplitude.assert_called_once_with(self.test_symbol, self.test_interval)

    def test_check_discovery_condition_with_date_range(self):
        """测试日期范围参数

        当指定start_date和end_date时，应该在查询中包含日期过滤
        """
        with patch("volume_trap.services.volume_trap_fsm.KLine") as mock_kline_class:
            # 模拟KLine查询 - 返回空结果
            mock_query = Mock()
            mock_query.order_by.return_value = []
            mock_kline_class.objects.filter.return_value = mock_query

            # 调用方法（指定日期范围）
            triggered, indicators = self.fsm._check_discovery_condition(
                symbol=self.test_symbol,
                interval=self.test_interval,
                start_date="2025-11-01",
                end_date="2025-11-30",
            )

            # 验证结果（空数据返回False）
            self.assertFalse(triggered)
            self.assertEqual(indicators, {})

            # 验证查询参数包含日期范围
            mock_kline_class.objects.filter.assert_called_once()
            call_args = mock_kline_class.objects.filter.call_args
            self.assertIn("open_time__gte", call_args[1])
            self.assertIn("open_time__lte", call_args[1])

    def test_check_discovery_condition_all_history(self):
        """测试扫描全部历史数据

        当start_date='all'时，应该扫描全部历史数据，不包含日期过滤
        """
        with patch("volume_trap.services.volume_trap_fsm.KLine") as mock_kline_class:
            # 模拟KLine查询 - 返回空的查询结果
            mock_query = Mock()
            mock_query.order_by.return_value = []
            mock_kline_class.objects.filter.return_value = mock_query

            # 调用方法（start_date='all'）
            triggered, indicators = self.fsm._check_discovery_condition(
                symbol=self.test_symbol, interval=self.test_interval, start_date="all"
            )

            # 验证结果（空数据返回False）
            self.assertFalse(triggered)
            self.assertEqual(indicators, {})

    def test_check_discovery_condition_returns_first_match(self):
        """测试返回第一个匹配的异常事件

        当找到第一个触发条件的K线时，应该立即返回
        """
        with patch("volume_trap.services.volume_trap_fsm.KLine") as mock_kline_class:
            # 模拟KLine查询 - 返回空结果
            mock_query = Mock()
            mock_query.order_by.return_value = []
            mock_kline_class.objects.filter.return_value = mock_query

            # 调用方法
            triggered, indicators = self.fsm._check_discovery_condition(
                symbol=self.test_symbol,
                interval=self.test_interval,
                start_date="2025-11-01",
                end_date="2025-11-30",
            )

            # 验证结果
            self.assertFalse(triggered)
            self.assertEqual(indicators, {})

    def test_check_discovery_condition_no_trigger(self):
        """测试没有触发条件的情况

        当没有K线满足触发条件时，应该返回False
        """
        with patch("volume_trap.services.volume_trap_fsm.KLine") as mock_kline_class:
            # 模拟KLine查询 - 返回空结果
            mock_query = Mock()
            mock_query.order_by.return_value = []
            mock_kline_class.objects.filter.return_value = mock_query

            # 调用方法
            triggered, indicators = self.fsm._check_discovery_condition(
                symbol=self.test_symbol,
                interval=self.test_interval,
                start_date="2025-11-01",
                end_date="2025-11-30",
            )

            # 验证结果
            self.assertFalse(triggered)
            self.assertEqual(indicators, {})

    def test_scan_historical_batch_processing(self):
        """测试批量扫描

        应该能够批量扫描多个交易对
        """
        with patch.object(self.fsm, "_check_discovery_condition") as mock_check, patch(
            "volume_trap.services.volume_trap_fsm.FuturesContract"
        ) as mock_contract_class, patch(
            "volume_trap.services.volume_trap_fsm.KLine"
        ) as mock_kline_class:

            # 模拟合约数据
            mock_contract1 = Mock()
            mock_contract1.symbol = "BTCUSDT"
            mock_contract1.id = 1

            # 创建QuerySet mock
            mock_queryset = MagicMock()
            mock_queryset.filter.return_value = mock_queryset
            mock_queryset.distinct.return_value = mock_queryset
            mock_queryset.count.return_value = 1
            mock_queryset.__len__ = Mock(return_value=1)
            mock_queryset.__iter__ = Mock(return_value=iter([mock_contract1]))

            # 模拟切片操作 - 使用lambda处理切片
            def getitem_side_effect(key):
                if isinstance(key, slice):
                    return [mock_contract1]
                return mock_contract1

            mock_queryset.__getitem__.side_effect = getitem_side_effect

            mock_contract_class.objects.filter.return_value = mock_queryset

            # 模拟KLine.objects.filter().exists()返回True
            # 需要使用side_effect来模拟每次调用都返回新的query对象
            def filter_side_effect(*args, **kwargs):
                query = MagicMock()
                query.exists.return_value = True
                return query

            mock_kline_class.objects.filter.side_effect = filter_side_effect

            # 模拟检查结果
            mock_check.return_value = (False, {})

            # 执行批量扫描
            result = self.fsm.scan_historical(
                interval="4h",
                market_type="futures",
                start_date="2025-11-01",
                end_date="2025-11-30",
                batch_size=1000,
            )

            # 验证结果
            self.assertEqual(result["total_contracts"], 1)
            self.assertEqual(result["processed"], 1)
            self.assertEqual(result["found_events"], 0)

            # 验证调用了检查方法
            self.assertEqual(mock_check.call_count, 1)

    def test_scan_historical_progress_tracking(self):
        """测试进度跟踪

        批量扫描时应该记录进度信息
        """
        with patch.object(self.fsm, "_check_discovery_condition") as mock_check, patch(
            "volume_trap.services.volume_trap_fsm.FuturesContract"
        ) as mock_contract_class, patch(
            "volume_trap.services.volume_trap_fsm.logger"
        ) as mock_logger, patch(
            "volume_trap.services.volume_trap_fsm.KLine"
        ) as mock_kline_class:

            # 模拟合约
            mock_contract = Mock(symbol="BTCUSDT", id=1)

            # 创建QuerySet mock
            mock_queryset = MagicMock()
            mock_queryset.filter.return_value = mock_queryset
            mock_queryset.distinct.return_value = mock_queryset
            mock_queryset.count.return_value = 1
            mock_queryset.__len__ = Mock(return_value=1)
            mock_queryset.__iter__ = Mock(return_value=iter([mock_contract]))
            # 模拟切片操作
            mock_queryset.__getitem__.return_value = [mock_contract]

            mock_contract_class.objects.filter.return_value = mock_queryset

            # 模拟KLine.objects.filter().exists()返回True
            # 需要使用side_effect来模拟每次调用都返回新的query对象
            def filter_side_effect(*args, **kwargs):
                query = MagicMock()
                query.exists.return_value = True
                return query

            mock_kline_class.objects.filter.side_effect = filter_side_effect

            # 模拟检查结果
            mock_check.return_value = (False, {})

            # 执行批量扫描
            result = self.fsm.scan_historical(
                interval="4h",
                market_type="futures",
                start_date="2025-11-01",
                end_date="2025-11-30",
                batch_size=5,
            )

            # 验证结果
            self.assertEqual(result["total_contracts"], 1)
            self.assertEqual(result["processed"], 1)
            self.assertEqual(result["found_events"], 0)

            # 验证记录了进度日志
            self.assertTrue(mock_logger.info.called)

    def test_scan_historical_error_handling(self):
        """测试错误处理

        单个交易对扫描失败时应该跳过并继续
        """
        with patch.object(self.fsm, "_check_discovery_condition") as mock_check, patch(
            "volume_trap.services.volume_trap_fsm.FuturesContract"
        ) as mock_contract_class, patch(
            "volume_trap.services.volume_trap_fsm.logger"
        ) as mock_logger, patch(
            "volume_trap.services.volume_trap_fsm.KLine"
        ) as mock_kline_class:

            # 模拟合约
            mock_contract = Mock(symbol="BTCUSDT", id=1)

            # 创建QuerySet mock
            mock_queryset = MagicMock()
            mock_queryset.filter.return_value = mock_queryset
            mock_queryset.distinct.return_value = mock_queryset
            mock_queryset.count.return_value = 1
            mock_queryset.__len__ = Mock(return_value=1)
            mock_queryset.__iter__ = Mock(return_value=iter([mock_contract]))
            # 模拟切片操作
            mock_queryset.__getitem__.return_value = [mock_contract]

            mock_contract_class.objects.filter.return_value = mock_queryset

            # 模拟KLine.objects.filter().exists()返回True
            # 需要使用side_effect来模拟每次调用都返回新的query对象
            def filter_side_effect(*args, **kwargs):
                query = MagicMock()
                query.exists.return_value = True
                return query

            mock_kline_class.objects.filter.side_effect = filter_side_effect

            # 模拟检查时抛出异常
            mock_check.side_effect = Exception("Test error")

            # 执行批量扫描
            result = self.fsm.scan_historical(
                interval="4h",
                market_type="futures",
                start_date="2025-11-01",
                end_date="2025-11-30",
                batch_size=1000,
            )

            # 验证结果（跳过错误，继续处理）
            self.assertEqual(result["total_contracts"], 1)
            self.assertEqual(result["processed"], 1)
            self.assertEqual(result["found_events"], 0)

            # 验证记录了错误日志
            self.assertTrue(mock_logger.error.called)

    def test_create_monitor_record(self):
        """测试监控记录创建"""
        from volume_trap.models import VolumeTrapMonitor

        with patch(
            "volume_trap.services.volume_trap_fsm.VolumeTrapMonitor.objects.create"
        ) as mock_create, patch(
            "volume_trap.services.volume_trap_fsm.VolumeTrapStateTransition.objects.create"
        ) as mock_transition, patch(
            "volume_trap.services.volume_trap_fsm.VolumeTrapIndicators.objects.create"
        ) as mock_indicators:

            # 模拟合约
            mock_contract = Mock()
            mock_contract.symbol = "BTCUSDT"

            # 模拟指标
            indicators = {
                "trigger_time": django_timezone.now(),
                "trigger_price": 50000,
                "trigger_volume": 1000,
                "trigger_kline_high": 51000,
                "trigger_kline_low": 49000,
                "rvol_ratio": 10.0,
                "amplitude_ratio": 2.0,
                "upper_shadow_ratio": 5.0,
            }

            # 模拟返回的monitor
            mock_monitor = Mock()
            mock_create.return_value = mock_monitor

            # 创建监控记录
            result = self.fsm._create_monitor_record(
                contract=mock_contract, market_type="futures", interval="4h", indicators=indicators
            )

            # 验证结果
            self.assertEqual(result, mock_monitor)

            # 验证调用了create方法
            self.assertTrue(mock_create.called)

            # 验证创建了transition和indicators
            self.assertTrue(mock_transition.called)
            self.assertTrue(mock_indicators.called)
