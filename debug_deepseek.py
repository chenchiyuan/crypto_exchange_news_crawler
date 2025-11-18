#!/usr/bin/env python
"""
DeepSeek API 调用链路完整诊断脚本
直接在线上运行，无需依赖Django环境
"""
import os
import sys
import json
import requests
from pathlib import Path

print("=" * 80)
print("🔍 DeepSeek API 完整调用链路诊断")
print("=" * 80)

# ============================================================
# 第1部分：Git 版本检查
# ============================================================
print("\n【1. Git 版本检查】")
try:
    import subprocess
    commit = subprocess.check_output(['git', 'log', '-1', '--oneline'], encoding='utf-8').strip()
    print(f"✅ 当前 commit: {commit}")

    expected_commit = "393806f"
    if expected_commit in commit:
        print(f"✅ 代码版本正确（包含修复 {expected_commit}）")
    else:
        print(f"⚠️  警告：当前版本不包含最新修复 {expected_commit}")
        print("   建议运行: git pull origin main")
except Exception as e:
    print(f"❌ 无法获取 Git 信息: {e}")

# ============================================================
# 第2部分：检查实际文件内容
# ============================================================
print("\n【2. 检查 settings.py 配置】")
settings_file = "listing_monitor_project/settings.py"
if os.path.exists(settings_file):
    with open(settings_file, 'r') as f:
        lines = f.readlines()
        for i, line in enumerate(lines, 1):
            if 'DEEPSEEK' in line and not line.strip().startswith('#'):
                print(f"  Line {i:3d}: {line.rstrip()}")

    # 检查关键配置
    content = ''.join(lines)
    if "https://deepseek.wanjiedata.com/v1/" in content:
        print("✅ BASE_URL 正确（末尾有斜杠）")
    elif "https://deepseek.wanjiedata.com/v1" in content:
        print("⚠️  BASE_URL 缺少末尾斜杠")
else:
    print(f"❌ 找不到文件: {settings_file}")

print("\n【3. 检查 deepseek_sdk.py 认证代码】")
sdk_file = "twitter/sdk/deepseek_sdk.py"
if os.path.exists(sdk_file):
    with open(sdk_file, 'r') as f:
        lines = f.readlines()

    # 查找 headers 设置部分（107-115行附近）
    print("  认证 header 设置代码:")
    in_header_section = False
    for i, line in enumerate(lines, 1):
        if 'self.session.headers.update' in line:
            in_header_section = True
            start_line = i

        if in_header_section:
            print(f"  Line {i:3d}: {line.rstrip()}")
            if line.strip() == '})':
                break

    # 检查是否有错误的 apiKey header
    content = ''.join(lines)
    if "'apiKey': self.api_key" in content or '"apiKey": self.api_key' in content:
        print("❌ 发现错误的 apiKey header！")
    elif "'Authorization': f'Bearer {self.api_key}'" in content:
        print("✅ 认证方式正确（使用 Authorization Bearer）")
    else:
        print("⚠️  认证代码格式不明确")
else:
    print(f"❌ 找不到文件: {sdk_file}")

# ============================================================
# 第4部分：检查 Python 缓存
# ============================================================
print("\n【4. Python 缓存检查】")
import glob
from datetime import datetime

cache_files = []
for pattern in ['twitter/sdk/__pycache__/deepseek_sdk*.pyc',
                'listing_monitor_project/__pycache__/settings*.pyc']:
    cache_files.extend(glob.glob(pattern))

if cache_files:
    print(f"⚠️  发现 {len(cache_files)} 个缓存文件:")
    for f in cache_files:
        mtime = os.path.getmtime(f)
        print(f"  {f}: {datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')}")
    print("  建议运行: find . -type d -name __pycache__ -exec rm -rf {{}} + 2>/dev/null")
else:
    print("✅ 未发现缓存文件")

# ============================================================
# 第5部分：Django 配置检查
# ============================================================
print("\n【5. Django 配置加载测试】")
try:
    # 设置 Django 环境
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')
    import django
    django.setup()

    from django.conf import settings

    print(f"  DEEPSEEK_API_KEY: {settings.DEEPSEEK_API_KEY[:30]}...{settings.DEEPSEEK_API_KEY[-20:]}")
    print(f"  DEEPSEEK_BASE_URL: {settings.DEEPSEEK_BASE_URL}")
    print(f"  DEEPSEEK_MODEL: {settings.DEEPSEEK_MODEL}")

    # 检查 URL 末尾
    if settings.DEEPSEEK_BASE_URL.endswith('/'):
        print("✅ BASE_URL 末尾有斜杠")
    else:
        print("⚠️  BASE_URL 末尾缺少斜杠")

except Exception as e:
    print(f"❌ Django 配置加载失败: {e}")
    import traceback
    traceback.print_exc()

# ============================================================
# 第6部分：SDK 实例化测试
# ============================================================
print("\n【6. DeepSeek SDK 实例化测试】")
try:
    from twitter.sdk.deepseek_sdk import DeepSeekSDK

    sdk = DeepSeekSDK()

    print(f"  API Key: {sdk.api_key[:30]}...{sdk.api_key[-20:]}")
    print(f"  Base URL: {sdk.base_url}")
    print(f"  Model: {sdk.model}")
    print(f"  Timeout: {sdk.timeout}")

    print("\n  HTTP Session Headers:")
    for key, value in sdk.session.headers.items():
        if key.lower() in ['authorization', 'apikey']:
            if 'Bearer' in value:
                print(f"    {key}: Bearer {value.split('Bearer')[1][:30]}...")
            else:
                print(f"    {key}: {value[:30]}...{value[-20:]}")
        else:
            print(f"    {key}: {value}")

    # 关键检查
    headers_dict = {k.lower(): v for k, v in sdk.session.headers.items()}

    if 'apikey' in headers_dict:
        print("\n❌ 发现错误的 'apiKey' header！")
        print(f"   apiKey 值: {headers_dict['apikey'][:30]}...")

    if 'authorization' in headers_dict:
        auth_value = headers_dict['authorization']
        if auth_value.startswith('Bearer '):
            print("\n✅ 认证方式正确（Authorization: Bearer）")
        else:
            print(f"\n⚠️  Authorization header 格式异常: {auth_value[:50]}")
    else:
        print("\n❌ 缺少 Authorization header！")

    sdk.close()

except Exception as e:
    print(f"❌ SDK 实例化失败: {e}")
    import traceback
    traceback.print_exc()

# ============================================================
# 第7部分：实际 API 调用测试
# ============================================================
print("\n【7. 实际 API 调用测试】")
try:
    from twitter.sdk.deepseek_sdk import DeepSeekSDK

    sdk = DeepSeekSDK()

    # 构造测试请求
    test_url = f"{sdk.base_url.rstrip('/')}/chat/completions"
    print(f"  请求 URL: {test_url}")

    test_payload = {
        "model": sdk.model,
        "messages": [
            {"role": "user", "content": "测试：请回复'OK'"}
        ],
        "max_tokens": 10,
        "temperature": 0.1
    }

    print(f"\n  发送测试请求...")
    print(f"  Headers:")
    for key, value in sdk.session.headers.items():
        if key.lower() in ['authorization', 'apikey']:
            print(f"    {key}: {value[:50]}...")
        else:
            print(f"    {key}: {value}")

    # 发送请求
    response = sdk.session.post(
        test_url,
        json=test_payload,
        timeout=30
    )

    print(f"\n  响应状态码: {response.status_code}")
    print(f"  响应 Content-Type: {response.headers.get('Content-Type', 'unknown')}")

    if response.status_code == 200:
        print("✅ API 调用成功！")
        try:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            print(f"  AI 响应: {content}")
        except:
            print(f"  响应内容: {response.text[:200]}")
    else:
        print(f"❌ API 调用失败！")
        print(f"  响应内容: {response.text[:500]}")

        # 特别检查 apiKey 错误
        if 'apiKey not found' in response.text:
            print("\n🔴 错误分析：服务器要求 'apiKey' header")
            print("   当前使用的认证方式:")
            if 'authorization' in {k.lower() for k in sdk.session.headers.keys()}:
                print("   - Authorization: Bearer (标准方式)")
            if 'apikey' in {k.lower() for k in sdk.session.headers.keys()}:
                print("   - apiKey: xxx (自定义方式)")

    sdk.close()

except Exception as e:
    print(f"❌ API 调用异常: {e}")
    import traceback
    traceback.print_exc()

# ============================================================
# 第8部分：测试所有可能的认证方式
# ============================================================
print("\n【8. 认证方式穷举测试】")
print("尝试所有可能的认证组合，找到正确的方式...")

try:
    import requests
    from django.conf import settings

    API_KEY = settings.DEEPSEEK_API_KEY
    BASE_URL = settings.DEEPSEEK_BASE_URL.rstrip('/')
    TEST_URL = f'{BASE_URL}/chat/completions'

    test_payload = {
        "model": "deepseek-v3",
        "messages": [{"role": "user", "content": "测试：请回复OK"}],
        "max_tokens": 10,
        "temperature": 0.1
    }

    # 测试方法列表
    test_methods = [
        {
            'name': '方法1: 只用 Authorization Bearer',
            'headers': {
                'Authorization': f'Bearer {API_KEY}',
                'Content-Type': 'application/json'
            }
        },
        {
            'name': '方法2: 只用 apiKey',
            'headers': {
                'apiKey': API_KEY,
                'Content-Type': 'application/json'
            }
        },
        {
            'name': '方法3: 同时用 Authorization Bearer + apiKey',
            'headers': {
                'Authorization': f'Bearer {API_KEY}',
                'apiKey': API_KEY,
                'Content-Type': 'application/json'
            }
        },
        {
            'name': '方法4: Authorization 空字符串 + apiKey',
            'headers': {
                'Authorization': '',
                'apiKey': API_KEY,
                'Content-Type': 'application/json'
            }
        }
    ]

    successful_method = None

    for i, method in enumerate(test_methods, 1):
        print(f"\n  【{method['name']}】")

        # 显示headers（隐藏敏感信息）
        display_headers = {}
        for k, v in method['headers'].items():
            if k.lower() in ['authorization', 'apikey'] and len(v) > 50:
                display_headers[k] = f"{v[:30]}...{v[-20:]}"
            else:
                display_headers[k] = v
        print(f"  Headers: {display_headers}")

        try:
            response = requests.post(TEST_URL, headers=method['headers'], json=test_payload, timeout=30)
            print(f"  状态码: {response.status_code}")

            if response.status_code == 200:
                print(f"  ✅ 成功！")
                try:
                    result = response.json()
                    content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                    print(f"  AI响应: {content}")
                    successful_method = i
                    break  # 找到成功的方法就停止
                except:
                    print(f"  响应: {response.text[:100]}")
            else:
                error_msg = response.text[:200] if response.text else '(空响应)'
                print(f"  ❌ 失败: {error_msg}")

        except Exception as e:
            print(f"  ❌ 异常: {str(e)[:100]}")

    # 总结
    print(f"\n  {'='*70}")
    if successful_method:
        print(f"  🎉 找到成功的认证方式：方法{successful_method}")
        print(f"  请使用: {test_methods[successful_method-1]['name']}")
    else:
        print(f"  ❌ 所有认证方式都失败了！")
        print(f"  建议检查:")
        print(f"  1. API Key 是否有效（过期时间：2026-01-13）")
        print(f"  2. 网络连接是否正常")
        print(f"  3. 万界数据服务是否可用")
    print(f"  {'='*70}")

except Exception as e:
    print(f"❌ 认证测试失败: {e}")
    import traceback
    traceback.print_exc()

# ============================================================
# 第9部分：诊断总结
# ============================================================
print("\n" + "=" * 80)
print("📊 诊断总结")
print("=" * 80)

print("\n如果发现问题，请按以下步骤修复：")
print("\n1. 如果 Git 版本不对:")
print("   git pull origin main")
print("\n2. 如果有 Python 缓存:")
print("   find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null")
print("   find . -name '*.pyc' -delete")
print("\n3. 如果 BASE_URL 缺少斜杠，需要修改 settings.py")
print("\n4. 如果发现 apiKey header，需要检查代码是否正确更新")

print("\n" + "=" * 80)
