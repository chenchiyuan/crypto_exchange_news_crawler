#!/usr/bin/env python
"""
测试 GRVT 认证流程
"""
import os
import asyncio
import aiohttp
import logging

logging.basicConfig(level=logging.DEBUG)

async def test_auth():
    api_key = os.getenv("GRVT_API_KEY", "35jheXLEmRgN9xRlMer2AZUZ7yW")
    env = os.getenv("GRVT_ENV", "prod")

    # 根据环境选择 URL
    if env == "prod":
        url = "https://edge.grvt.io/auth/api_key/login"
    else:
        url = "https://edge.testnet.grvt.io/auth/api_key/login"

    print(f"Environment: {env}")
    print(f"URL: {url}")
    print(f"API Key: {api_key[:10]}...\n")

    headers = {
        "Content-Type": "application/json",
        "Cookie": "rm=true;",
    }
    payload = {"api_key": api_key}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
            print(f"\n状态码: {response.status}")
            print(f"\n响应头:")
            for key, value in response.headers.items():
                print(f"  {key}: {value}")

            print(f"\n响应体:")
            text = await response.text()
            print(text)

            # 检查 Set-Cookie
            set_cookie = response.headers.get("Set-Cookie")
            print(f"\nSet-Cookie: {set_cookie}")

            # 检查 account_id
            account_id = response.headers.get("x-grvt-account-id") or response.headers.get("X-Grvt-Account-Id")
            print(f"Account ID: {account_id}")


if __name__ == "__main__":
    asyncio.run(test_auth())
