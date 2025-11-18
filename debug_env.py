#!/usr/bin/env python
"""
环境诊断脚本 - 对比本地和线上的配置差异
"""
import os
import sys
import django

# 设置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')
django.setup()

from django.conf import settings

print("=" * 60)
print("🔍 DeepSeek API 配置诊断")
print("=" * 60)

# 1. 检查配置值
print("\n【1. Django Settings 配置】")
print(f"DEEPSEEK_API_KEY: {settings.DEEPSEEK_API_KEY[:20]}...{settings.DEEPSEEK_API_KEY[-20:]}")
print(f"DEEPSEEK_BASE_URL: {settings.DEEPSEEK_BASE_URL}")
print(f"DEEPSEEK_MODEL: {settings.DEEPSEEK_MODEL}")

# 2. 检查环境变量
print("\n【2. 环境变量】")
for key in ['DEEPSEEK_API_KEY', 'DEEPSEEK_BASE_URL', 'DEEPSEEK_MODEL', 'OPENAI_API_KEY', 'OPENAI_BASE_URL']:
    value = os.getenv(key)
    if value:
        if 'KEY' in key:
            print(f"{key}: {value[:20]}...{value[-20:]}")
        else:
            print(f"{key}: {value}")
    else:
        print(f"{key}: (未设置)")

# 3. 检查实际的 SDK 初始化
print("\n【3. DeepSeek SDK 实际配置】")
try:
    from twitter.sdk.deepseek_sdk import DeepSeekSDK

    # 创建 SDK 实例
    sdk = DeepSeekSDK()

    print(f"API Key (前20字符): {sdk.api_key[:20]}...")
    print(f"API Key (后20字符): ...{sdk.api_key[-20:]}")
    print(f"Base URL: {sdk.base_url}")
    print(f"Model: {sdk.model}")
    print(f"Timeout: {sdk.timeout}")

    # 4. 检查 HTTP headers
    print("\n【4. HTTP Headers】")
    for key, value in sdk.session.headers.items():
        if key.lower() in ['authorization', 'apikey']:
            if key.lower() == 'authorization':
                # 只显示前缀
                print(f"{key}: {value[:30]}...")
            else:
                print(f"{key}: {value[:20]}...{value[-20:]}")
        else:
            print(f"{key}: {value}")

    # 5. 检查实际请求 URL
    print("\n【5. 实际请求 URL】")
    test_endpoint = '/chat/completions'
    url = f"{sdk.base_url.rstrip('/')}/{test_endpoint.lstrip('/')}"
    print(f"完整 URL: {url}")

    sdk.close()

except Exception as e:
    print(f"❌ SDK 初始化失败: {e}")
    import traceback
    traceback.print_exc()

# 6. 检查 .env 文件
print("\n【6. .env 文件检查】")
env_files = ['.env', '.env.local', '.env.production']
for env_file in env_files:
    if os.path.exists(env_file):
        print(f"✅ 发现文件: {env_file}")
        with open(env_file, 'r') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            for line in lines:
                if 'DEEPSEEK' in line or 'OPENAI' in line:
                    # 隐藏敏感信息
                    if '=' in line:
                        key, value = line.split('=', 1)
                        if 'KEY' in key:
                            print(f"  {key}={value[:20]}...{value[-20:]}")
                        else:
                            print(f"  {line}")
    else:
        print(f"❌ 未发现: {env_file}")

# 7. Git 版本信息
print("\n【7. Git 版本信息】")
import subprocess
try:
    commit = subprocess.check_output(['git', 'log', '-1', '--oneline'], encoding='utf-8').strip()
    print(f"当前 commit: {commit}")

    status = subprocess.check_output(['git', 'status', '--short'], encoding='utf-8').strip()
    if status:
        print(f"未提交的修改:\n{status}")
    else:
        print("工作区干净")
except Exception as e:
    print(f"无法获取 Git 信息: {e}")

# 8. Python 缓存文件
print("\n【8. Python 缓存检查】")
import glob
pyc_files = glob.glob('twitter/sdk/__pycache__/deepseek_sdk*.pyc')
if pyc_files:
    print(f"发现 {len(pyc_files)} 个缓存文件:")
    for f in pyc_files:
        mtime = os.path.getmtime(f)
        from datetime import datetime
        print(f"  {f}: {datetime.fromtimestamp(mtime)}")
else:
    print("未发现缓存文件")

print("\n" + "=" * 60)
print("✅ 诊断完成")
print("=" * 60)
