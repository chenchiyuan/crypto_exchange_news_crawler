import requests
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 测试 API 调用
api_url = "https://huicheng.powerby.com.cn/api/simple/alert/"
token = "6020867bc6334c609d4f348c22f90f14"
channel = "twitter_analysis"

payload = {
    "token": token,
    "title": "测试通知",
    "content": "这是一条测试通知",
    "channel": channel
}

print("=" * 60)
print("🔍 调试通知 API")
print("=" * 60)
print(f"URL: {api_url}")
print(f"Token: {token}")
print(f"Channel: {channel}")
print(f"\nPayload: {json.dumps(payload, ensure_ascii=False, indent=2)}")

try:
    print("\n📤 发送请求...")
    response = requests.post(
        api_url,
        json=payload,
        headers={'Content-Type': 'application/json'},
        timeout=30
    )

    print(f"\n📥 响应信息:")
    print(f"  状态码: {response.status_code}")
    print(f"  响应头: {dict(response.headers)}")
    print(f"  原始响应: {response.text}")

    try:
        response_data = response.json()
        print(f"\n✅ JSON 解析成功:")
        print(f"  响应数据: {json.dumps(response_data, ensure_ascii=False, indent=2)}")

        if response_data.get('errcode') == 0:
            print(f"\n✅ 推送成功: errcode = 0")
        else:
            print(f"\n❌ 推送失败:")
            print(f"  errcode: {response_data.get('errcode')}")
            print(f"  msg: {response_data.get('msg')}")

    except json.JSONDecodeError as e:
        print(f"\n❌ JSON 解析失败:")
        print(f"  错误: {e}")
        print(f"  响应内容不是有效的 JSON")

except requests.exceptions.Timeout:
    print("\n❌ 请求超时")
except requests.exceptions.RequestException as e:
    print(f"\n❌ 请求异常: {e}")
except Exception as e:
    print(f"\n❌ 未知错误: {e}", exc_info=True)

print("\n" + "=" * 60)
