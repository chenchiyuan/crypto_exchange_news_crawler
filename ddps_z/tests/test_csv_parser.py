"""
CSVParser单元测试

Related:
    - TASK: TASK-025-003
"""

import tempfile
from pathlib import Path

import pytest

from ddps_z.datasources.csv_parser import CSVParser
from ddps_z.models import StandardKLine


class TestCSVParser:
    """CSVParser测试类"""

    def test_parse_binance_format(self):
        """测试解析币安12列格式"""
        # 准备测试数据（微秒时间戳）
        csv_content = """1764547200000000,2991.25,2991.50,2990.00,2991.00,100.5,1764547260000000,300000,50,60,180000,0
1764547260000000,2991.00,2992.00,2990.50,2991.75,150.0,1764547320000000,450000,75,80,240000,0"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            csv_path = f.name

        try:
            parser = CSVParser(timestamp_unit='microseconds')
            klines = parser.parse(csv_path)

            assert len(klines) == 2
            assert isinstance(klines[0], StandardKLine)

            # 验证第一根K线
            assert klines[0].open == 2991.25
            assert klines[0].high == 2991.50
            assert klines[0].low == 2990.00
            assert klines[0].close == 2991.00
            assert klines[0].volume == 100.5
        finally:
            Path(csv_path).unlink()

    def test_timestamp_conversion_microseconds(self):
        """测试微秒时间戳转换"""
        csv_content = """1764547200000000,100,101,99,100,10,0,0,0,0,0,0"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            csv_path = f.name

        try:
            parser = CSVParser(timestamp_unit='microseconds')
            klines = parser.parse(csv_path)

            # 微秒转毫秒：1764547200000000 / 1000 = 1764547200000
            assert klines[0].timestamp == 1764547200000
        finally:
            Path(csv_path).unlink()

    def test_timestamp_conversion_milliseconds(self):
        """测试毫秒时间戳转换"""
        csv_content = """1764547200000,100,101,99,100,10,0,0,0,0,0,0"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            csv_path = f.name

        try:
            parser = CSVParser(timestamp_unit='milliseconds')
            klines = parser.parse(csv_path)

            # 毫秒无需转换
            assert klines[0].timestamp == 1764547200000
        finally:
            Path(csv_path).unlink()

    def test_timestamp_conversion_seconds(self):
        """测试秒时间戳转换"""
        csv_content = """1764547200,100,101,99,100,10,0,0,0,0,0,0"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            csv_path = f.name

        try:
            parser = CSVParser(timestamp_unit='seconds')
            klines = parser.parse(csv_path)

            # 秒转毫秒：1764547200 * 1000 = 1764547200000
            assert klines[0].timestamp == 1764547200000
        finally:
            Path(csv_path).unlink()

    def test_no_header_csv(self):
        """测试无表头CSV"""
        # CSV无表头，直接是数据行
        csv_content = """1764547200000000,100,101,99,100,10,0,0,0,0,0,0
1764547260000000,100.5,102,98.5,101,15,0,0,0,0,0,0"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            csv_path = f.name

        try:
            parser = CSVParser(timestamp_unit='microseconds')
            klines = parser.parse(csv_path)

            # 应该解析出2根K线，而非将第一行当作表头
            assert len(klines) == 2
            assert klines[0].open == 100
            assert klines[1].open == 100.5
        finally:
            Path(csv_path).unlink()

    def test_file_not_found(self):
        """测试文件不存在异常"""
        parser = CSVParser()

        with pytest.raises(FileNotFoundError) as exc_info:
            parser.parse('/nonexistent/path/data.csv')

        assert "CSV文件不存在" in str(exc_info.value)

    def test_default_timestamp_unit(self):
        """测试默认时间戳单位为微秒"""
        parser = CSVParser()
        assert parser.timestamp_unit == 'microseconds'
        assert parser._divisor == 1000.0

    def test_ohlcv_data_types(self):
        """测试OHLCV数据类型正确"""
        csv_content = """1764547200000000,2991.25,2991.50,2990.00,2991.00,100.5,0,0,0,0,0,0"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            csv_path = f.name

        try:
            parser = CSVParser()
            klines = parser.parse(csv_path)

            kline = klines[0]
            assert isinstance(kline.timestamp, int)
            assert isinstance(kline.open, float)
            assert isinstance(kline.high, float)
            assert isinstance(kline.low, float)
            assert isinstance(kline.close, float)
            assert isinstance(kline.volume, float)
        finally:
            Path(csv_path).unlink()

    def test_large_dataset_performance(self):
        """测试大数据集解析性能（生成1000行数据）"""
        import time

        # 生成1000行测试数据
        lines = []
        base_timestamp = 1764547200000000
        for i in range(1000):
            ts = base_timestamp + i * 1000000  # 每秒一根
            lines.append(f"{ts},100,101,99,100,10,0,0,0,0,0,0")

        csv_content = "\n".join(lines)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            csv_path = f.name

        try:
            parser = CSVParser()

            start = time.time()
            klines = parser.parse(csv_path)
            elapsed = time.time() - start

            assert len(klines) == 1000
            # 1000行应该在1秒内完成
            assert elapsed < 1.0, f"解析耗时过长: {elapsed:.2f}秒"
        finally:
            Path(csv_path).unlink()
