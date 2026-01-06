"""
KLine模型market_type扩展测试

测试KLine模型的market_type字段功能和迁移
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from decimal import Decimal
from datetime import datetime

from backtest.models import KLine


class KLineMarketTypeTest(TestCase):
    """KLine模型market_type字段测试套件"""

    def setUp(self):
        """设置测试数据"""
        pass

    def test_create_kline_with_market_type_spot(self):
        """TC-003: 测试创建market_type='spot'的KLine记录"""
        kline = KLine.objects.create(
            symbol='BTC/USDT',
            interval='4h',
            market_type='spot',
            open_time=datetime(2025, 1, 1, 0, 0),
            close_time=datetime(2025, 1, 1, 4, 0),
            open_price=Decimal('50000.00'),
            high_price=Decimal('51000.00'),
            low_price=Decimal('49000.00'),
            close_price=Decimal('50500.00'),
            volume=Decimal('100.00'),
            quote_volume=Decimal('5050000.00')
        )
        
        # 验证创建成功
        self.assertIsInstance(kline, KLine)
        self.assertEqual(kline.symbol, 'BTC/USDT')
        self.assertEqual(kline.market_type, 'spot')
        self.assertEqual(kline.interval, '4h')

    def test_create_kline_with_market_type_futures(self):
        """测试创建market_type='futures'的KLine记录"""
        kline = KLine.objects.create(
            symbol='BTCUSDT',
            interval='4h',
            market_type='futures',
            open_time=datetime(2025, 1, 1, 0, 0),
            close_time=datetime(2025, 1, 1, 4, 0),
            open_price=Decimal('50000.00'),
            high_price=Decimal('51000.00'),
            low_price=Decimal('49000.00'),
            close_price=Decimal('50500.00'),
            volume=Decimal('100.00'),
            quote_volume=Decimal('5050000.00')
        )
        
        # 验证创建成功
        self.assertIsInstance(kline, KLine)
        self.assertEqual(kline.symbol, 'BTCUSDT')
        self.assertEqual(kline.market_type, 'futures')
        self.assertEqual(kline.interval, '4h')

    def test_invalid_market_type(self):
        """TC-004: 测试无效market_type抛出ValidationError"""
        with self.assertRaises(ValidationError):
            kline = KLine.objects.create(
                symbol='ETH/USDT',
                interval='4h',
                market_type='invalid',  # 无效值
                open_time=datetime(2025, 1, 1, 0, 0),
                close_time=datetime(2025, 1, 1, 4, 0),
                open_price=Decimal('3000.00'),
                high_price=Decimal('3100.00'),
                low_price=Decimal('2900.00'),
                close_price=Decimal('3050.00'),
                volume=Decimal('200.00'),
                quote_volume=Decimal('610000.00')
            )
            kline.full_clean()  # 触发验证

    def test_unique_constraint_with_market_type(self):
        """测试unique_together包含market_type"""
        # 创建第一个记录
        kline1 = KLine.objects.create(
            symbol='BTC/USDT',
            interval='4h',
            market_type='spot',
            open_time=datetime(2025, 1, 1, 0, 0),
            close_time=datetime(2025, 1, 1, 4, 0),
            open_price=Decimal('50000.00'),
            high_price=Decimal('51000.00'),
            low_price=Decimal('49000.00'),
            close_price=Decimal('50500.00'),
            volume=Decimal('100.00'),
            quote_volume=Decimal('5050000.00')
        )
        
        # 尝试创建重复(symbol, interval, market_type, open_time)，预期抛出IntegrityError
        with self.assertRaises(IntegrityError):
            kline2 = KLine.objects.create(
                symbol='BTC/USDT',
                interval='4h',
                market_type='spot',
                open_time=datetime(2025, 1, 1, 0, 0),  # 相同时间
                close_time=datetime(2025, 1, 1, 4, 0),
                open_price=Decimal('50000.00'),
                high_price=Decimal('51000.00'),
                low_price=Decimal('49000.00'),
                close_price=Decimal('50600.00'),  # 不同收盘价
                volume=Decimal('150.00'),
                quote_volume=Decimal('7590000.00')
            )

    def test_same_symbol_different_market_types(self):
        """测试相同symbol但不同market_type可以共存"""
        # 创建现货K线
        spot_kline = KLine.objects.create(
            symbol='BTC/USDT',
            interval='4h',
            market_type='spot',
            open_time=datetime(2025, 1, 1, 0, 0),
            close_time=datetime(2025, 1, 1, 4, 0),
            open_price=Decimal('50000.00'),
            high_price=Decimal('51000.00'),
            low_price=Decimal('49000.00'),
            close_price=Decimal('50500.00'),
            volume=Decimal('100.00'),
            quote_volume=Decimal('5050000.00')
        )
        
        # 创建合约K线（相同时间）
        futures_kline = KLine.objects.create(
            symbol='BTCUSDT',
            interval='4h',
            market_type='futures',
            open_time=datetime(2025, 1, 1, 0, 0),
            close_time=datetime(2025, 1, 1, 4, 0),
            open_price=Decimal('50100.00'),
            high_price=Decimal('51100.00'),
            low_price=Decimal('49100.00'),
            close_price=Decimal('50600.00'),
            volume=Decimal('120.00'),
            quote_volume=Decimal('6072000.00')
        )
        
        # 验证两者都创建成功
        self.assertEqual(KLine.objects.count(), 2)
        self.assertNotEqual(spot_kline.market_type, futures_kline.market_type)

    def test_market_type_choices(self):
        """测试market_type字段choices"""
        # 验证Choices属性
        self.assertTrue(hasattr(KLine, 'MARKET_TYPE_SPOT'))
        self.assertTrue(hasattr(KLine, 'MARKET_TYPE_FUTURES'))
        self.assertEqual(KLine.MARKET_TYPE_SPOT, 'spot')
        self.assertEqual(KLine.MARKET_TYPE_FUTURES, 'futures')
        
        # 验证Choices
        choices = KLine.MARKET_TYPE_CHOICES
        self.assertEqual(len(choices), 2)
        self.assertIn(('spot', '现货'), choices)
        self.assertIn(('futures', '合约'), choices)

    def test_filter_by_market_type(self):
        """测试按market_type查询"""
        # 创建现货数据
        KLine.objects.create(
            symbol='BTC/USDT',
            interval='4h',
            market_type='spot',
            open_time=datetime(2025, 1, 1, 0, 0),
            close_time=datetime(2025, 1, 1, 4, 0),
            open_price=Decimal('50000.00'),
            high_price=Decimal('51000.00'),
            low_price=Decimal('49000.00'),
            close_price=Decimal('50500.00'),
            volume=Decimal('100.00'),
            quote_volume=Decimal('5050000.00')
        )
        
        # 创建合约数据
        KLine.objects.create(
            symbol='BTCUSDT',
            interval='4h',
            market_type='futures',
            open_time=datetime(2025, 1, 1, 0, 0),
            close_time=datetime(2025, 1, 1, 4, 0),
            open_price=Decimal('50100.00'),
            high_price=Decimal('51100.00'),
            low_price=Decimal('49100.00'),
            close_price=Decimal('50600.00'),
            volume=Decimal('120.00'),
            quote_volume=Decimal('6072000.00')
        )
        
        # 测试筛选
        spot_count = KLine.objects.filter(market_type='spot').count()
        futures_count = KLine.objects.filter(market_type='futures').count()
        
        self.assertEqual(spot_count, 1)
        self.assertEqual(futures_count, 1)
