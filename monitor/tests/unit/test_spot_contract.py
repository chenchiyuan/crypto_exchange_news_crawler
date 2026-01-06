"""
SpotContract模型测试

测试现货交易对模型的创建、验证和约束
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from decimal import Decimal

from monitor.models import Exchange, SpotContract


class SpotContractTest(TestCase):
    """SpotContract模型测试套件"""

    def setUp(self):
        """设置测试数据"""
        self.exchange = Exchange.objects.create(
            code='binance',
            name='Binance',
            enabled=True
        )

    def test_create_spot_contract(self):
        """TC-001: 测试创建现货交易对"""
        # 创建现货交易对
        contract = SpotContract.objects.create(
            exchange=self.exchange,
            symbol='BTC/USDT',
            status='active',
            current_price=Decimal('50000.00')
        )
        
        # 验证创建成功
        self.assertIsInstance(contract, SpotContract)
        self.assertEqual(contract.symbol, 'BTC/USDT')
        self.assertEqual(contract.status, 'active')
        self.assertEqual(contract.current_price, Decimal('50000.00'))
        self.assertEqual(contract.exchange, self.exchange)
        
        # 验证可以查询到记录
        retrieved = SpotContract.objects.get(symbol='BTC/USDT', exchange=self.exchange)
        self.assertEqual(retrieved.symbol, 'BTC/USDT')

    def test_unique_constraint(self):
        """TC-002: 测试(exchange, symbol)唯一性约束"""
        # 创建第一个记录
        SpotContract.objects.create(
            exchange=self.exchange,
            symbol='ETH/USDT',
            status='active',
            current_price=Decimal('3000.00')
        )
        
        # 尝试创建重复记录，预期抛出IntegrityError
        with self.assertRaises(IntegrityError):
            SpotContract.objects.create(
                exchange=self.exchange,
                symbol='ETH/USDT',
                status='active',
                current_price=Decimal('3100.00')
            )

    def test_str_representation(self):
        """测试__str__方法"""
        contract = SpotContract.objects.create(
            exchange=self.exchange,
            symbol='BTC/USDT',
            status='active',
            current_price=Decimal('50000.00')
        )
        
        # 验证字符串表示
        expected = f"{self.exchange.name} - {contract.symbol} ({contract.current_price})"
        self.assertEqual(str(contract), expected)

    def test_status_choices(self):
        """测试status字段的选择约束"""
        # 测试有效状态
        valid_statuses = ['active', 'delisted']
        for i, status in enumerate(valid_statuses):
            contract = SpotContract.objects.create(
                exchange=self.exchange,
                symbol=f'TEST{i}/USDT',  # 使用不同的symbol
                status=status,
                current_price=Decimal('100.00')
            )
            self.assertEqual(contract.status, status)

    def test_delisted_status(self):
        """测试已下线状态"""
        contract = SpotContract.objects.create(
            exchange=self.exchange,
            symbol='DOGE/USDT',
            status='delisted',
            current_price=Decimal('0.10')
        )
        
        self.assertEqual(contract.status, 'delisted')

    def test_current_price_decimal(self):
        """测试current_price字段使用Decimal类型"""
        contract = SpotContract.objects.create(
            exchange=self.exchange,
            symbol='BNB/USDT',
            status='active',
            current_price=Decimal('300.12345678')
        )
        
        # 验证Decimal精度
        self.assertEqual(contract.current_price, Decimal('300.12345678'))
        self.assertIsInstance(contract.current_price, Decimal)

    def test_timestamps(self):
        """测试时间戳字段"""
        before = timezone.now()
        contract = SpotContract.objects.create(
            exchange=self.exchange,
            symbol='ADA/USDT',
            status='active',
            current_price=Decimal('1.00')
        )
        after = timezone.now()
        
        # 验证时间戳
        self.assertIsNotNone(contract.first_seen)
        self.assertIsNotNone(contract.last_updated)
        self.assertGreaterEqual(contract.first_seen, before)
        self.assertLessEqual(contract.first_seen, after)
        self.assertGreaterEqual(contract.last_updated, before)
        self.assertLessEqual(contract.last_updated, after)

    def test_multiple_exchanges(self):
        """测试多个交易所的交易对"""
        # 创建第二个交易所
        exchange2 = Exchange.objects.create(
            code='okx',
            name='OKX',
            enabled=True
        )
        
        # 创建两个交易所的相同币种
        btc_binance = SpotContract.objects.create(
            exchange=self.exchange,
            symbol='BTC/USDT',
            status='active',
            current_price=Decimal('50000.00')
        )
        
        btc_okx = SpotContract.objects.create(
            exchange=exchange2,
            symbol='BTC/USDT',
            status='active',
            current_price=Decimal('50100.00')
        )
        
        # 验证可以同时存在（不同交易所）
        self.assertEqual(SpotContract.objects.filter(symbol='BTC/USDT').count(), 2)
        self.assertNotEqual(btc_binance.exchange, btc_okx.exchange)

    def test_symbol_field_constraints(self):
        """测试symbol字段约束"""
        # symbol字段为CharField，最大长度通常为50
        long_symbol = 'A' * 50  # 边界值
        contract = SpotContract.objects.create(
            exchange=self.exchange,
            symbol=long_symbol,
            status='active',
            current_price=Decimal('1.00')
        )
        self.assertEqual(len(contract.symbol), 50)

    def test_exchange_foreign_key(self):
        """测试与Exchange的外键关系"""
        contract = SpotContract.objects.create(
            exchange=self.exchange,
            symbol='LINK/USDT',
            status='active',
            current_price=Decimal('15.00')
        )
        
        # 验证外键关系
        self.assertEqual(contract.exchange.id, self.exchange.id)
        self.assertEqual(contract.exchange.code, 'binance')
        
        # 验证级联删除
        self.exchange.delete()
        self.assertEqual(SpotContract.objects.filter(symbol='LINK/USDT').count(), 0)
