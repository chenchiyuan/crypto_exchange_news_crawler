#!/usr/bin/env python
"""
测试万界数据的不同认证方式
"""
import requests
import json

# 配置
API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NzA5NjIzMDUsImtleSI6IjVLNzVaOFROQzlGNEhNMzdQOVk3In0.u3SNbt-pDQ9NIyY0K4OdcVb56hTvq8tqNuy2wZMcz0g'
BASE_URL = 'https://deepseek.wanjiedata.com/v1'
TEST_URL = f'{BASE_URL}/chat/completions'

# 测试payload
payload = {
    "model": "deepseek-v3",
    "messages": [{"role": "user", "content": "测试：请回复OK"}],
    "max_tokens": 10,
    "temperature": 0.1
}

print("=" * 80)
print("测试万界数据 DeepSeek API 的认证方式")
print("=" * 80)

# 方法1: 只使用 Authorization: Bearer
print("\n【方法1】只使用 Authorization: Bearer")
headers1 = {
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json'
}
print("Headers:", json.dumps({k: v[:50] + '...' if len(v) > 50 else v for k, v in headers1.items()}, indent=2))

try:
    response = requests.post(TEST_URL, headers=headers1, json=payload, timeout=30)
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.text[:200]}")
except Exception as e:
    print(f"错误: {e}")

# 方法2: 只使用 apiKey
print("\n【方法2】只使用 apiKey")
headers2 = {
    'apiKey': API_KEY,
    'Content-Type': 'application/json'
}
print("Headers:", json.dumps({k: v[:50] + '...' if len(v) > 50 else v for k, v in headers2.items()}, indent=2))

try:
    response = requests.post(TEST_URL, headers=headers2, json=payload, timeout=30)
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.text[:200]}")
except Exception as e:
    print(f"错误: {e}")

# 方法3: 同时使用 Authorization 和 apiKey
print("\n【方法3】同时使用 Authorization: Bearer 和 apiKey")
headers3 = {
    'Authorization': f'Bearer {API_KEY}',
    'apiKey': API_KEY,
    'Content-Type': 'application/json'
}
print("Headers:", json.dumps({k: v[:50] + '...' if len(v) > 50 else v for k, v in headers3.items()}, indent=2))

try:
    response = requests.post(TEST_URL, headers=headers3, json=payload, timeout=30)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
        print(f"✅ 成功! AI响应: {content}")
    else:
        print(f"响应: {response.text[:200]}")
except Exception as e:
    print(f"错误: {e}")

# 方法4: Authorization 用空字符串 + apiKey
print("\n【方法4】Authorization: (空) + apiKey")
headers4 = {
    'Authorization': '',
    'apiKey': API_KEY,
    'Content-Type': 'application/json'
}
print("Headers:", json.dumps({k: v[:50] + '...' if 'apiKey' in k and len(v) > 50 else v for k, v in headers4.items()}, indent=2))

try:
    response = requests.post(TEST_URL, headers=headers4, json=payload, timeout=30)
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.text[:200]}")
except Exception as e:
    print(f"错误: {e}")

print("\n" + "=" * 80)
print("测试完成")
print("=" * 80)
