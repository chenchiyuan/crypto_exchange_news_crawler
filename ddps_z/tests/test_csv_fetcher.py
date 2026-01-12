"""
CSVFetcher单元测试

Related:
    - TASK: TASK-025-007
"""

import tempfile
from pathlib import Path

import pytest

from ddps_z.datasources.base import KLineFetcher
from ddps_z.datasources.csv_fetcher import CSVFetcher


class TestCSVFetcher:
    """CSVFetcher测试类"""

    @pytest.fixture
    def sample_csv(self):
        """创建测试用CSV文件"""
        # 生成10根K线，时间戳间隔1秒（微秒单位）
        lines = []
        base_ts = 1764547200000000  # 微秒
        for i in range(10):
            ts = base_ts + i * 1000000
            price = 3000 + i * 10
            lines.append(f"{ts},{price},{price+5},{price-5},{price+2},{100+i},0,0,0,0,0,0")

        csv_content = "\n".join(lines)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            csv_path = f.name

        yield csv_path

        # 清理
        Path(csv_path).unlink()

    def test_inherits_kline_fetcher(self, sample_csv):
        """测试正确继承KLineFetcher"""
        fetcher = CSVFetcher(csv_path=sample_csv, interval='1s')
        assert isinstance(fetcher, KLineFetcher)

    def test_market_type_property(self, sample_csv):
        """测试market_type返回csv_local"""
        fetcher = CSVFetcher(csv_path=sample_csv, interval='1s')
        assert fetcher.market_type == 'csv_local'

    def test_custom_market_type(self, sample_csv):
        """测试自定义market_type"""
        fetcher = CSVFetcher(
            csv_path=sample_csv,
            interval='1s',
            market_type='custom_csv'
        )
        assert fetcher.market_type == 'custom_csv'

    def test_supports_interval_1s(self, sample_csv):
        """测试支持1s周期"""
        fetcher = CSVFetcher(csv_path=sample_csv, interval='1s')
        assert fetcher.supports_interval('1s') is True

    def test_supports_interval_1m(self, sample_csv):
        """测试支持1m周期"""
        fetcher = CSVFetcher(csv_path=sample_csv, interval='1m')
        assert fetcher.supports_interval('1m') is True

    def test_not_supports_interval_4h(self, sample_csv):
        """测试不支持4h周期"""
        fetcher = CSVFetcher(csv_path=sample_csv, interval='1s')
        assert fetcher.supports_interval('4h') is False

    def test_invalid_interval_raises_error(self, sample_csv):
        """测试无效周期抛出异常"""
        with pytest.raises(ValueError) as exc_info:
            CSVFetcher(csv_path=sample_csv, interval='4h')
        assert "不支持的K线周期" in str(exc_info.value)

    def test_fetch_lazy_load(self, sample_csv):
        """测试懒加载机制"""
        fetcher = CSVFetcher(csv_path=sample_csv, interval='1s')

        # 初始化后缓存应为空
        assert fetcher.is_loaded is False
        assert fetcher.kline_count == 0

        # 首次fetch触发加载
        klines = fetcher.fetch('ETHUSDT', '1s')

        assert fetcher.is_loaded is True
        assert fetcher.kline_count == 10
        assert len(klines) == 10

    def test_fetch_cache_hit(self, sample_csv):
        """测试缓存命中"""
        fetcher = CSVFetcher(csv_path=sample_csv, interval='1s')

        # 第一次调用
        klines1 = fetcher.fetch('ETHUSDT', '1s')
        count_after_first = fetcher.kline_count

        # 第二次调用（应使用缓存）
        klines2 = fetcher.fetch('ETHUSDT', '1s')
        count_after_second = fetcher.kline_count

        # 缓存数量不变
        assert count_after_first == count_after_second
        assert len(klines1) == len(klines2)

    def test_fetch_time_filter_start(self, sample_csv):
        """测试时间范围过滤（起始时间）"""
        fetcher = CSVFetcher(csv_path=sample_csv, interval='1s')

        # 过滤掉前5根K线
        start_time = 1764547200000 + 5000  # 第5秒之后（毫秒）
        klines = fetcher.fetch('ETHUSDT', '1s', start_time=start_time)

        assert len(klines) == 5

    def test_fetch_time_filter_end(self, sample_csv):
        """测试时间范围过滤（结束时间）"""
        fetcher = CSVFetcher(csv_path=sample_csv, interval='1s')

        # 只取前5根K线
        end_time = 1764547200000 + 4999  # 第5秒之前（毫秒）
        klines = fetcher.fetch('ETHUSDT', '1s', end_time=end_time)

        assert len(klines) == 5

    def test_fetch_time_filter_range(self, sample_csv):
        """测试时间范围过滤（起始+结束）"""
        fetcher = CSVFetcher(csv_path=sample_csv, interval='1s')

        # 取中间3根K线（第3-5秒）
        start_time = 1764547200000 + 2000
        end_time = 1764547200000 + 4999
        klines = fetcher.fetch('ETHUSDT', '1s', start_time=start_time, end_time=end_time)

        assert len(klines) == 3

    def test_fetch_limit(self, sample_csv):
        """测试limit参数"""
        fetcher = CSVFetcher(csv_path=sample_csv, interval='1s')

        klines = fetcher.fetch('ETHUSDT', '1s', limit=5)

        # 应该返回最后5根
        assert len(klines) == 5
        # 验证是最后5根（价格递增）
        assert klines[0].close == 3052  # 第6根（index 5）
        assert klines[-1].close == 3092  # 最后一根（index 9）

    def test_fetch_limit_with_time_filter(self, sample_csv):
        """测试limit与时间过滤组合"""
        fetcher = CSVFetcher(csv_path=sample_csv, interval='1s')

        # 先过滤时间（只剩8根），再限制3根
        start_time = 1764547200000 + 2000  # 跳过前2根
        klines = fetcher.fetch('ETHUSDT', '1s', limit=3, start_time=start_time)

        assert len(klines) == 3

    def test_fetch_no_filter(self, sample_csv):
        """测试无过滤条件"""
        fetcher = CSVFetcher(csv_path=sample_csv, interval='1s')

        klines = fetcher.fetch('ETHUSDT', '1s', limit=0)  # limit=0表示不限制

        assert len(klines) == 10

    def test_csv_path_property(self, sample_csv):
        """测试csv_path属性"""
        fetcher = CSVFetcher(csv_path=sample_csv, interval='1s')
        assert fetcher.csv_path == sample_csv

    def test_timestamp_conversion(self, sample_csv):
        """测试时间戳正确转换"""
        fetcher = CSVFetcher(csv_path=sample_csv, interval='1s')
        klines = fetcher.fetch('ETHUSDT', '1s')

        # 微秒转毫秒
        assert klines[0].timestamp == 1764547200000
        assert klines[1].timestamp == 1764547201000

    def test_fetch_returns_copy(self, sample_csv):
        """测试fetch返回的是副本而非缓存引用"""
        fetcher = CSVFetcher(csv_path=sample_csv, interval='1s')

        klines1 = fetcher.fetch('ETHUSDT', '1s')
        klines2 = fetcher.fetch('ETHUSDT', '1s')

        # 应该是不同的列表对象
        assert klines1 is not klines2

    def test_supports_symbol_always_true(self, sample_csv):
        """测试supports_symbol总是返回True"""
        fetcher = CSVFetcher(csv_path=sample_csv, interval='1s')

        # CSV不区分交易对，总是返回True
        assert fetcher.supports_symbol('BTCUSDT') is True
        assert fetcher.supports_symbol('ETHUSDT') is True
        assert fetcher.supports_symbol('ANY') is True
