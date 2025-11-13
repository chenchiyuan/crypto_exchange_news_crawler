#!/usr/bin/env python
"""
测试 API 配置是否正确加载

运行方式：
python test_api_config.py
"""

import os
import django
import sys
from pathlib import Path

# 设置 Django 环境
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')
django.setup()

from django.conf import settings

def test_twitter_config():
    """测试 Twitter API 配置"""
    print("=" * 60)
    print("Twitter API 配置测试")
    print("=" * 60)

    twitter_api_key = settings.TWITTER_API_KEY
    twitter_base_url = settings.TWITTER_API_BASE_URL

    print(f"Twitter API Key: {twitter_api_key[:20]}..." if twitter_api_key else "❌ 未配置")
    print(f"Twitter Base URL: {twitter_base_url}")
    print(f"Rate Limit: {settings.TWITTER_RATE_LIMIT_PER_MINUTE} 请求/分钟")

    if twitter_api_key and twitter_api_key != '':
        print("✅ Twitter API 配置已加载")
        return True
    else:
        print("❌ Twitter API Key 未配置")
        return False

def test_deepseek_config():
    """测试 DeepSeek API 配置"""
    print("\n" + "=" * 60)
    print("DeepSeek AI 配置测试")
    print("=" * 60)

    deepseek_api_key = settings.DEEPSEEK_API_KEY
    deepseek_base_url = settings.DEEPSEEK_BASE_URL
    deepseek_model = settings.DEEPSEEK_MODEL

    print(f"DeepSeek API Key: {deepseek_api_key[:40]}..." if deepseek_api_key else "❌ 未配置")
    print(f"DeepSeek Base URL: {deepseek_base_url}")
    print(f"DeepSeek Model: {deepseek_model}")
    print(f"Max Cost: ${settings.MAX_COST_PER_ANALYSIS}")
    print(f"Alert Threshold: ${settings.COST_ALERT_THRESHOLD}")

    if deepseek_api_key and deepseek_api_key != '':
        print("✅ DeepSeek API 配置已加载")
        return True
    else:
        print("❌ DeepSeek API Key 未配置")
        return False

def test_sdk_initialization():
    """测试 SDK 初始化"""
    print("\n" + "=" * 60)
    print("SDK 初始化测试")
    print("=" * 60)

    try:
        from twitter.sdk.twitter_sdk import TwitterSDK
        from twitter.sdk.deepseek_sdk import DeepSeekSDK

        # 测试 TwitterSDK 初始化
        twitter_sdk = TwitterSDK()
        print("✅ TwitterSDK 初始化成功")
        print(f"   - API Key: {twitter_sdk.api_key[:20]}...")
        print(f"   - Base URL: {twitter_sdk.base_url}")

        # 测试 DeepSeekSDK 初始化
        deepseek_sdk = DeepSeekSDK()
        print("✅ DeepSeekSDK 初始化成功")
        print(f"   - API Key: {deepseek_sdk.api_key[:40]}...")
        print(f"   - Base URL: {deepseek_sdk.base_url}")
        print(f"   - Model: {deepseek_sdk.model}")

        return True

    except Exception as e:
        print(f"❌ SDK 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("\n" + "🔍 开始测试 API 配置..." + "\n")

    twitter_ok = test_twitter_config()
    deepseek_ok = test_deepseek_config()
    sdk_ok = test_sdk_initialization()

    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    if twitter_ok and deepseek_ok and sdk_ok:
        print("✅ 所有配置测试通过！")
        print("\n可以运行以下命令测试推文收集：")
        print("python manage.py collect_twitter_list <list_id> --hours 1 --dry-run")
        sys.exit(0)
    else:
        print("❌ 部分配置测试失败，请检查 .env 文件")
        sys.exit(1)
