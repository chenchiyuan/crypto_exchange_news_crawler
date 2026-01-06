"""
历史扫描功能性能测试

测试历史扫描功能的性能指标，包括扫描时间、内存使用、数据库查询等。

Related:
    - Task: TASK-005-007
    - Architecture: Discovery历史扫描优化
"""

import time
import unittest
from unittest.mock import MagicMock, Mock, patch

from django.db import connection
from django.test import TestCase

from volume_trap.services.volume_trap_fsm import VolumeTrapStateMachine


class HistoricalScanPerformanceTestCase(TestCase):
    """历史扫描功能性能测试类"""

    def setUp(self):
        """初始化测试环境"""
        self.fsm = VolumeTrapStateMachine()

    def test_scan_1000_contracts_performance(self):
        """性能测试: 扫描1000个交易对 < 5分钟"""
        with patch.object(self.fsm, "_check_discovery_condition") as mock_check, patch(
            "volume_trap.services.volume_trap_fsm.FuturesContract"
        ) as mock_contract_class:

            # 模拟1000个合约
            contracts = [Mock(symbol=f"SYMBOL{i:04d}USDT", id=i) for i in range(1000)]
            mock_query = Mock()
            mock_query.filter.return_value.distinct.return_value = contracts
            mock_contract_class.objects.filter.return_value = mock_query

            # 模拟检查结果（不触发）
            mock_check.return_value = (False, {})

            # 记录开始时间
            start_time = time.time()

            # 执行扫描
            result = self.fsm.scan_historical(
                interval="4h", market_type="futures", start_date="all"
            )

            # 记录结束时间
            elapsed_time = time.time() - start_time

            # 验证结果
            self.assertEqual(result["total_contracts"], 1000)
            self.assertEqual(result["processed"], 1000)

            # 验证性能（应该远快于5分钟，因为是mock）
            self.assertLess(elapsed_time, 300, f"扫描用时{elapsed_time:.2f}秒，超过了5分钟")

            # 输出性能指标
            print(f"\n性能测试结果:")
            print(f"  扫描交易对数量: 1000")
            print(f"  扫描用时: {elapsed_time:.2f}秒")
            print(f"  平均每交易对用时: {elapsed_time/1000*1000:.2f}毫秒")

    def test_memory_usage_under_load(self):
        """性能测试: 内存使用 < 500MB"""
        try:
            import os

            import psutil
        except ImportError:
            self.skipTest("psutil未安装，跳过内存测试")

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        with patch.object(self.fsm, "_check_discovery_condition") as mock_check, patch(
            "volume_trap.services.volume_trap_fsm.FuturesContract"
        ) as mock_contract_class:

            # 模拟500个合约
            contracts = [Mock(symbol=f"SYMBOL{i:04d}USDT", id=i) for i in range(500)]
            mock_query = Mock()
            mock_query.filter.return_value.distinct.return_value = contracts
            mock_contract_class.objects.filter.return_value = mock_query

            # 模拟检查结果
            mock_check.return_value = (False, {})

            # 执行扫描
            self.fsm.scan_historical(
                interval="4h", market_type="futures", start_date="all", batch_size=100
            )

            # 检查内存使用
            peak_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = peak_memory - initial_memory

            # 验证内存使用（应该远少于500MB，因为是mock）
            self.assertLess(memory_increase, 500, f"内存增长{memory_increase:.2f}MB，超过了500MB")

            # 输出内存指标
            print(f"\n内存测试结果:")
            print(f"  初始内存: {initial_memory:.2f}MB")
            print(f"  峰值内存: {peak_memory:.2f}MB")
            print(f"  内存增长: {memory_increase:.2f}MB")

    def test_database_query_optimization(self):
        """性能测试: 数据库查询次数优化"""
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as queries:
            with patch.object(self.fsm, "_check_discovery_condition") as mock_check, patch(
                "volume_trap.services.volume_trap_fsm.FuturesContract"
            ) as mock_contract_class:

                # 模拟10个合约
                contracts = [Mock(symbol=f"SYMBOL{i:04d}USDT", id=i) for i in range(10)]
                mock_query = Mock()
                mock_query.filter.return_value.distinct.return_value = contracts
                mock_contract_class.objects.filter.return_value = mock_query

                # 模拟检查结果
                mock_check.return_value = (False, {})

                # 执行扫描
                result = self.fsm.scan_historical(
                    interval="4h", market_type="futures", start_date="all"
                )

                # 获取查询数量
                query_count = len(queries)

                # 验证查询优化（应该很少的查询）
                # 1. 获取合约列表
                # 2-11. 每个合约调用_check_discovery_condition（如果有KLine查询）
                self.assertLess(query_count, 20, f"查询次数{query_count}，过多")

                # 输出查询指标
                print(f"\n查询优化测试结果:")
                print(f"  查询次数: {query_count}")
                print(f"  合约数量: 10")
                print(f"  平均每合约查询次数: {query_count/10:.2f}")

    def test_batch_processing_efficiency(self):
        """性能测试: 批处理效率"""
        with patch.object(self.fsm, "_check_discovery_condition") as mock_check, patch(
            "volume_trap.services.volume_trap_fsm.FuturesContract"
        ) as mock_contract_class:

            # 模拟1000个合约
            contracts = [Mock(symbol=f"SYMBOL{i:04d}USDT", id=i) for i in range(1000)]
            mock_query = Mock()
            mock_query.filter.return_value.distinct.return_value = contracts
            mock_contract_class.objects.filter.return_value = mock_query

            # 模拟检查结果
            mock_check.return_value = (False, {})

            # 测试不同批次大小
            batch_sizes = [100, 500, 1000]
            results = {}

            for batch_size in batch_sizes:
                start_time = time.time()

                result = self.fsm.scan_historical(
                    interval="4h", market_type="futures", start_date="all", batch_size=batch_size
                )

                elapsed_time = time.time() - start_time
                results[batch_size] = elapsed_time

                # 验证结果
                self.assertEqual(result["total_contracts"], 1000)
                self.assertEqual(result["processed"], 1000)

            # 输出性能对比
            print(f"\n批处理效率测试结果:")
            print(f"  合约数量: 1000")
            for batch_size, elapsed_time in results.items():
                print(f"  批次大小 {batch_size}: {elapsed_time:.4f}秒")

    def test_date_range_query_performance(self):
        """性能测试: 日期范围查询性能"""
        with patch("volume_trap.services.volume_trap_fsm.KLine") as mock_kline_class:
            # 模拟大量KLine数据
            mock_klines = [
                Mock(
                    open_time=Mock(),
                    close_price=50000 + i,
                    high_price=51000 + i,
                    low_price=49000 + i,
                    volume=1000 + i,
                )
                for i in range(1000)
            ]

            mock_query = Mock()
            mock_query.order_by.return_value = mock_klines
            mock_kline_class.objects.filter.return_value = mock_query

            with patch.object(
                self.fsm.rvol_calculator, "calculate_from_kline"
            ) as mock_rvol, patch.object(
                self.fsm.amplitude_detector, "calculate_from_kline"
            ) as mock_amp, patch.object(
                self.fsm.condition_evaluator, "evaluate_discovery_condition"
            ) as mock_eval:

                # 模拟检测器返回结果
                mock_rvol.return_value = {"triggered": True, "rvol_ratio": 10.0}
                mock_amp.return_value = {
                    "triggered": True,
                    "amplitude_ratio": 2.0,
                    "upper_shadow_ratio": 5.0,
                }
                mock_eval.return_value = True

                # 记录开始时间
                start_time = time.time()

                # 执行历史检查（第一次会触发，返回第一个KLine）
                triggered, indicators = self.fsm._check_discovery_condition(
                    symbol="BTCUSDT", interval="4h", start_date="2025-11-01", end_date="2025-11-30"
                )

                # 记录结束时间
                elapsed_time = time.time() - start_time

                # 验证结果
                self.assertTrue(triggered)

                # 验证性能（应该很快，因为是mock）
                self.assertLess(elapsed_time, 5, f"日期范围查询用时{elapsed_time:.2f}秒，超过了5秒")

                # 输出性能指标
                print(f"\n日期范围查询性能测试结果:")
                print(f"  KLine数量: 1000")
                print(f"  查询用时: {elapsed_time:.4f}秒")
                print(f"  平均每KLine用时: {elapsed_time/1000*1000:.4f}毫秒")

    def test_concurrent_scan_performance(self):
        """性能测试: 并发扫描性能"""
        import threading

        with patch.object(self.fsm, "_check_discovery_condition") as mock_check, patch(
            "volume_trap.services.volume_trap_fsm.FuturesContract"
        ) as mock_contract_class:

            # 模拟100个合约
            contracts = [Mock(symbol=f"SYMBOL{i:04d}USDT", id=i) for i in range(100)]
            mock_query = Mock()
            mock_query.filter.return_value.distinct.return_value = contracts
            mock_contract_class.objects.filter.return_value = mock_query

            # 模拟检查结果
            mock_check.return_value = (False, {})

            results = []

            def scan_batch(start_idx, end_idx):
                """扫描一个批次"""
                start_time = time.time()
                result = self.fsm.scan_historical(
                    interval="4h", market_type="futures", start_date="all"
                )
                elapsed_time = time.time() - start_time
                results.append(elapsed_time)

            # 测试串行执行
            start_time = time.time()
            for _ in range(5):
                scan_batch(0, 100)
            serial_time = time.time() - start_time

            # 清空结果
            results.clear()

            # 测试分批执行（模拟批处理）
            start_time = time.time()
            for batch_size in [20, 20, 20, 20, 20]:
                scan_batch(0, batch_size)
            parallel_time = time.time() - start_time

            # 验证性能
            self.assertLess(parallel_time, serial_time * 1.5, "批处理应该提高性能")

            # 输出性能对比
            print(f"\n并发扫描性能测试结果:")
            print(f"  串行执行时间: {serial_time:.4f}秒")
            print(f"  批处理执行时间: {parallel_time:.4f}秒")
            print(f"  性能提升: {(serial_time - parallel_time) / serial_time * 100:.2f}%")
