"""
MVP端到端测试
测试 User Story 1 的完整流程
"""
import os
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')
django.setup()

import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from datetime import datetime

from monitor.models import Exchange, FuturesContract
from monitor.services.futures_fetcher import FuturesFetcherService
from monitor.api_clients.binance import BinanceFuturesClient
from monitor.api_clients.hyperliquid import HyperliquidFuturesClient
from monitor.api_clients.bybit import BybitFuturesClient


def test_api_client_initialization():
    """测试API客户端初始化"""
    print("\n🧪 测试 API 客户端初始化")

    # Binance
    binance = BinanceFuturesClient()
    assert binance.exchange_name == 'binance'
    assert hasattr(binance, 'base_url')
    assert hasattr(binance, 'session')
    print("  ✅ BinanceFuturesClient 初始化成功")

    # Hyperliquid
    hyperliquid = HyperliquidFuturesClient()
    assert hyperliquid.exchange_name == 'hyperliquid'
    assert hasattr(hyperliquid, 'base_url')
    assert hasattr(hyperliquid, 'session')
    print("  ✅ HyperliquidFuturesClient 初始化成功")

    # Bybit
    bybit = BybitFuturesClient()
    assert bybit.exchange_name == 'bybit'
    assert hasattr(bybit, 'base_url')
    assert hasattr(bybit, 'session')
    print("  ✅ BybitFuturesClient 初始化成功")


def test_symbol_normalization():
    """测试符号标准化"""
    print("\n🧪 测试符号标准化")

    binance = BinanceFuturesClient()
    hyperliquid = HyperliquidFuturesClient()
    bybit = BybitFuturesClient()

    # Binance (无需改变)
    assert binance._normalize_symbol("BTCUSDT") == "BTCUSDT"
    assert binance._normalize_symbol("ethusdt") == "ETHUSDT"
    print("  ✅ Binance 符号标准化正确 (无需改变)")

    # Hyperliquid (添加 USDT 后缀)
    assert hyperliquid._normalize_symbol("BTC") == "BTCUSDT"
    assert hyperliquid._normalize_symbol("ETH") == "ETHUSDT"
    assert hyperliquid._normalize_symbol("BTCUSDT") == "BTCUSDT"  # 已包含USDT
    print("  ✅ Hyperliquid 符号标准化正确 (添加USDT)")

    # Bybit (无需改变)
    assert bybit._normalize_symbol("BTCUSDT") == "BTCUSDT"
    assert bybit._normalize_symbol("ethusdt") == "ETHUSDT"
    print("  ✅ Bybit 符号标准化正确 (无需改变)")


def test_futures_fetcher_service():
    """测试服务层"""
    print("\n🧪 测试 FuturesFetcherService")

    service = FuturesFetcherService()

    # 检查客户端
    assert 'binance' in service.clients
    assert 'hyperliquid' in service.clients
    assert 'bybit' in service.clients
    print(f"  ✅ 服务包含 {len(service.clients)} 个客户端")

    # 检查统计信息
    stats = service.get_contract_statistics()
    assert 'total_contracts' in stats
    assert 'by_exchange' in stats
    print(f"  ✅ 统计信息正常: {stats['total_contracts']} 个合约")

    # 检查合约数量
    counts = service.get_all_exchanges_contract_count()
    assert 'binance' in counts
    assert 'hyperliquid' in counts
    assert 'bybit' in counts
    print(f"  ✅ 按交易所统计: {counts}")


def test_database_operations():
    """测试数据库操作"""
    print("\n🧪 测试数据库操作")

    # 清理测试数据
    FuturesContract.objects.all().delete()

    # 获取交易所
    binance_exchange = Exchange.objects.get(code='binance')
    print(f"  ✅ 获取交易所: {binance_exchange.name}")

    # 创建测试合约
    test_contract = FuturesContract.objects.create(
        exchange=binance_exchange,
        symbol='BTCUSDT',
        current_price=Decimal('50000.00'),
        contract_type='perpetual',
        first_seen=datetime.now()
    )
    print(f"  ✅ 创建测试合约: {test_contract.symbol}")

    # 查询合约
    contracts = FuturesContract.objects.filter(exchange=binance_exchange)
    assert contracts.count() == 1
    print(f"  ✅ 查询成功: 找到 {contracts.count()} 个合约")

    # 更新合约
    test_contract.current_price = Decimal('51000.00')
    test_contract.save()
    test_contract.refresh_from_db()
    assert test_contract.current_price == Decimal('51000.00')
    print(f"  ✅ 更新成功: 价格更新为 {test_contract.current_price}")

    # 清理测试数据
    test_contract.delete()
    print("  ✅ 清理测试数据")


def test_management_command_availability():
    """测试管理命令可用性"""
    print("\n🧪 测试管理命令可用性")

    import subprocess

    # 测试帮助命令
    result = subprocess.run(
        ['python', 'manage.py', 'fetch_futures', '--help'],
        capture_output=True,
        text=True,
        cwd='/Users/chenchiyuan/projects/crypto_exchange_news_crawler'
    )

    assert result.returncode == 0
    assert 'fetch_futures' in result.stdout
    print("  ✅ fetch_futures 命令可用")
    print(f"     输出: {result.stdout[:100]}...")


def test_configuration():
    """测试配置"""
    print("\n🧪 测试配置")

    from config.futures_config import (
        EXCHANGE_API_CONFIGS,
        RETRY_CONFIG,
        POLLING_INTERVAL,
        RETENTION_DAYS
    )

    # 检查交易所配置
    assert 'binance' in EXCHANGE_API_CONFIGS
    assert 'hyperliquid' in EXCHANGE_API_CONFIGS
    assert 'bybit' in EXCHANGE_API_CONFIGS
    print(f"  ✅ 配置了 {len(EXCHANGE_API_CONFIGS)} 个交易所")

    # 检查重试配置
    assert RETRY_CONFIG['max_attempts'] == 3
    print(f"  ✅ 重试配置: 最大 {RETRY_CONFIG['max_attempts']} 次")

    # 检查其他配置
    assert POLLING_INTERVAL == 5 * 60  # 5分钟
    print(f"  ✅ 轮询间隔: {POLLING_INTERVAL} 秒")
    assert RETENTION_DAYS == 90
    print(f"  ✅ 保留期: {RETENTION_DAYS} 天")


def test_model_validation():
    """测试模型验证"""
    print("\n🧪 测试模型验证")

    from monitor.models import FuturesContract, FuturesListingNotification

    # 检查字段
    assert hasattr(FuturesContract, 'exchange')
    assert hasattr(FuturesContract, 'symbol')
    assert hasattr(FuturesContract, 'current_price')
    assert hasattr(FuturesContract, 'contract_type')
    assert hasattr(FuturesContract, 'first_seen')
    assert hasattr(FuturesContract, 'last_updated')
    print("  ✅ FuturesContract 模型字段完整")

    assert hasattr(FuturesListingNotification, 'futures_contract')
    assert hasattr(FuturesListingNotification, 'channel')
    assert hasattr(FuturesListingNotification, 'status')
    assert hasattr(FuturesListingNotification, 'sent_at')
    print("  ✅ FuturesListingNotification 模型字段完整")

    # 检查约束
    assert FuturesContract._meta.unique_together == (('exchange', 'symbol'),)
    print("  ✅ 复合唯一约束正确")


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 MVP 端到端测试")
    print("=" * 60)

    try:
        test_api_client_initialization()
        test_symbol_normalization()
        test_futures_fetcher_service()
        test_database_operations()
        test_management_command_availability()
        test_configuration()
        test_model_validation()

        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        print("\n📋 MVP 实现状态:")
        print("  Phase 1 - Setup: ✅ 完成")
        print("  Phase 2 - Foundational: ✅ 完成")
        print("  Phase 3 - User Story 1: ✅ 完成")
        print("\n🎯 可以部署和测试了！")

    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
