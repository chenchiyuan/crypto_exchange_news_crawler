# API Contracts: CoinGecko & Internal Services

**Feature**: 008-marketcap-fdv-display
**Date**: 2025-12-12
**Status**: Design Complete

## Overview

本文档定义了市值/FDV展示功能涉及的所有API契约,包括:
1. **外部API**: CoinGecko API的端点、请求/响应格式、错误处理
2. **内部服务**: CoingeckoClient、MappingService、MarketDataService的接口定义

所有API调用遵循以下原则:
- 明确的错误处理和重试策略
- 结构化的日志记录
- 批量操作优化
- 限流应对机制

---

## External API: CoinGecko

### Base Configuration

```python
BASE_URL = "https://api.coingecko.com/api/v3"
TIMEOUT = 30  # 秒
MAX_RETRIES = 3
RETRY_BACKOFF = [1, 2, 4, 8]  # 指数退避(秒)
```

### Authentication

```python
headers = {
    "x-cg-demo-api-key": COINGECKO_API_KEY  # 从环境变量读取
}
```

### Rate Limiting

**免费版限制**:
- 50次调用/分钟(实测值)
- 429状态码触发限流
- 响应Header包含: `X-RateLimit-Limit`, `X-RateLimit-Remaining`

**应对策略**:
- 批量查询: 每批最多250个coin_id
- 批次间延迟: 60秒
- 429错误: 等待`Retry-After` header指定的秒数(默认60秒)
- 其他5xx错误: 指数退避重试

---

## API Endpoint 1: GET /coins/list

### 用途
获取CoinGecko支持的所有代币列表,用于建立币安symbol与CoinGecko ID的映射关系。

### Request

```http
GET /api/v3/coins/list?include_platform=true HTTP/1.1
Host: api.coingecko.com
x-cg-demo-api-key: YOUR_API_KEY
```

**Query Parameters**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| include_platform | boolean | 否 | 是否包含区块链平台信息(默认false) |

### Response

**Status: 200 OK**

```json
[
  {
    "id": "bitcoin",
    "symbol": "btc",
    "name": "Bitcoin",
    "platforms": {
      "ethereum": "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",
      "binance-smart-chain": "0x7130d2a12b9bcbfae4f2634d864a1ee1ce3ead9c"
    }
  },
  {
    "id": "ethereum",
    "symbol": "eth",
    "name": "Ethereum",
    "platforms": {}
  },
  {
    "id": "mon-protocol",
    "symbol": "mon",
    "name": "MON Protocol",
    "platforms": {
      "solana": "mona8KgfHzLXFRmP5mfqFkRfm3QQEqVq5eBaNWxQVAb"
    }
  }
]
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | CoinGecko唯一标识符 |
| symbol | string | 代币符号(小写) |
| name | string | 代币全称 |
| platforms | object | 区块链平台合约地址映射 |

### Error Responses

**429 Too Many Requests**:
```json
{
  "status": {
    "error_code": 429,
    "error_message": "Rate limit exceeded"
  }
}
```
**Response Headers**:
- `Retry-After: 60` (秒)

**503 Service Unavailable**:
```json
{
  "error": "Service temporarily unavailable"
}
```

### Python Implementation

```python
def fetch_coins_list(self) -> List[Dict[str, Any]]:
    """获取所有代币列表

    Returns:
        List[Dict]: 代币列表,每个元素包含id, symbol, name, platforms

    Raises:
        requests.exceptions.HTTPError: API调用失败
        requests.exceptions.Timeout: 请求超时
    """
    try:
        response = self._request(
            "/coins/list",
            params={"include_platform": "true"}
        )
        return response
    except requests.exceptions.HTTPError as e:
        logger.error(f"Failed to fetch coins list: {e}")
        raise
```

---

## API Endpoint 2: GET /coins/markets

### 用途
批量获取代币的市值、FDV、交易量等市场数据。

### Request

```http
GET /api/v3/coins/markets?vs_currency=usd&ids=bitcoin,ethereum,solana&per_page=250 HTTP/1.1
Host: api.coingecko.com
x-cg-demo-api-key: YOUR_API_KEY
```

**Query Parameters**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| vs_currency | string | 是 | 基准货币(固定为"usd") |
| ids | string | 是 | 逗号分隔的coin_id列表,最多250个 |
| per_page | integer | 否 | 每页返回数量(默认100,最大250) |
| order | string | 否 | 排序方式(market_cap_desc/volume_desc等) |

### Response

**Status: 200 OK**

```json
[
  {
    "id": "bitcoin",
    "symbol": "btc",
    "name": "Bitcoin",
    "image": "https://assets.coingecko.com/coins/images/1/large/bitcoin.png",
    "current_price": 42350.12,
    "market_cap": 828765432109.87,
    "market_cap_rank": 1,
    "fully_diluted_valuation": 890000000000.00,
    "total_volume": 23456789012.34,
    "high_24h": 43200.00,
    "low_24h": 41800.00,
    "price_change_24h": 850.12,
    "price_change_percentage_24h": 2.05,
    "market_cap_change_24h": 15000000000.00,
    "market_cap_change_percentage_24h": 1.85,
    "circulating_supply": 19500000.00,
    "total_supply": 21000000.00,
    "max_supply": 21000000.00,
    "ath": 69000.00,
    "ath_change_percentage": -38.62,
    "ath_date": "2021-11-10T14:24:11.849Z",
    "atl": 67.81,
    "atl_change_percentage": 62384.12,
    "atl_date": "2013-07-06T00:00:00.000Z",
    "last_updated": "2025-12-12T04:05:23.456Z"
  },
  {
    "id": "ethereum",
    "symbol": "eth",
    "name": "Ethereum",
    "current_price": 2234.56,
    "market_cap": 268500000000.00,
    "market_cap_rank": 2,
    "fully_diluted_valuation": null,
    "total_volume": 12000000000.00,
    "circulating_supply": 120000000.00,
    "total_supply": 120000000.00,
    "max_supply": null,
    "last_updated": "2025-12-12T04:05:23.456Z"
  }
]
```

**字段说明**:

| 字段 | 类型 | 说明 | 我们需要的 |
|------|------|------|-----------|
| id | string | CoinGecko ID | ✅ 用于反向映射 |
| symbol | string | 代币符号 | - |
| market_cap | float/null | 市值(USD) | ✅ 核心数据 |
| fully_diluted_valuation | float/null | 全稀释估值(USD) | ✅ 核心数据 |
| total_volume | float | 24h交易量(USD) | ✅ 用于消歧 |
| market_cap_rank | integer/null | 市值排名 | ✅ 用于消歧 |
| last_updated | string(ISO8601) | 数据更新时间 | ✅ 存为fetched_at |

**NULL值说明**:
- `fully_diluted_valuation`: 当总供应量未知时为null
- `market_cap_rank`: 当市值不可用时为null

### Error Responses

**400 Bad Request** (无效的coin_id):
```json
{
  "error": "coin not found"
}
```

**429 Too Many Requests**:
```json
{
  "status": {
    "error_code": 429,
    "error_message": "You've exceeded the Rate Limit. Please visit https://www.coingecko.com/en/api/pricing to subscribe to a plan."
  }
}
```

### Python Implementation

```python
def fetch_market_data(
    self,
    coin_ids: List[str],
    batch_size: int = 250
) -> List[Dict[str, Any]]:
    """批量获取市值和FDV数据

    Args:
        coin_ids: CoinGecko ID列表
        batch_size: 每批查询的数量(默认250)

    Returns:
        List[Dict]: 市场数据列表

    Raises:
        requests.exceptions.HTTPError: API调用失败
    """
    results = []

    for i in range(0, len(coin_ids), batch_size):
        batch = coin_ids[i:i+batch_size]

        try:
            data = self._request(
                "/coins/markets",
                params={
                    "vs_currency": "usd",
                    "ids": ",".join(batch),
                    "per_page": batch_size
                }
            )
            results.extend(data)

            # 批次间延迟,避免限流
            if i + batch_size < len(coin_ids):
                logger.info(f"Processed batch {i//batch_size + 1}, waiting 60s...")
                time.sleep(60)

        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to fetch market data for batch {i//batch_size + 1}: {e}")
            # 记录失败的coin_ids
            for coin_id in batch:
                UpdateLog.log_symbol_error(
                    batch_id=self.current_batch_id,
                    symbol=coin_id,
                    error=str(e)
                )
            continue

    return results
```

---

## Internal Service 1: CoingeckoClient

### 职责
封装所有CoinGecko API调用,处理限流、重试、错误日志。

### Class Definition

```python
class CoingeckoClient:
    """CoinGecko API客户端

    Attributes:
        api_key: CoinGecko API密钥
        base_url: API基础URL
        timeout: 请求超时时间(秒)
        session: requests.Session实例
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.coingecko.com/api/v3"
        self.timeout = 30
        self.session = requests.Session()
        self.session.headers.update({
            "x-cg-demo-api-key": api_key
        })
```

### Method 1: _request (私有方法)

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError
    ))
)
def _request(self, endpoint: str, params: Dict = None) -> Any:
    """执行API请求(带重试机制)

    Args:
        endpoint: API端点(如"/coins/list")
        params: 查询参数

    Returns:
        JSON响应数据

    Raises:
        requests.exceptions.HTTPError: API返回4xx/5xx错误
        requests.exceptions.Timeout: 请求超时
    """
    url = f"{self.base_url}{endpoint}"

    try:
        response = self.session.get(
            url,
            params=params,
            timeout=self.timeout
        )

        # 处理限流
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            logger.warning(f"Rate limited, waiting {retry_after}s...")
            time.sleep(retry_after)
            response = self.session.get(url, params=params, timeout=self.timeout)

        response.raise_for_status()
        return response.json()

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error: {e}, URL: {url}, Params: {params}")
        raise
    except requests.exceptions.Timeout as e:
        logger.error(f"Request timeout: {e}, URL: {url}")
        raise
```

### Method 2: fetch_coins_list

```python
def fetch_coins_list(self) -> List[Dict[str, Any]]:
    """获取所有代币列表

    Returns:
        List[Dict]: 包含id, symbol, name, platforms的代币列表
    """
    return self._request("/coins/list", params={"include_platform": "true"})
```

### Method 3: fetch_market_data

```python
def fetch_market_data(
    self,
    coin_ids: List[str],
    batch_size: int = 250
) -> List[Dict[str, Any]]:
    """批量获取市值和FDV数据

    Args:
        coin_ids: CoinGecko ID列表
        batch_size: 每批查询数量(默认250)

    Returns:
        List[Dict]: 市场数据列表
    """
    # 实现见上文"API Endpoint 2"的Python Implementation
```

### Error Handling Strategy

```python
# 使用tenacity库实现重试
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

# 可重试的错误类型
RETRYABLE_ERRORS = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    # 503 Service Unavailable会触发HTTPError,但可重试
)

# 不可重试的错误类型
NON_RETRYABLE_ERRORS = (
    # 400 Bad Request: 参数错误,重试无意义
    # 401 Unauthorized: API密钥错误
    # 404 Not Found: coin_id不存在
)
```

---

## Internal Service 2: MappingService

### 职责
管理币安symbol与CoinGecko ID的映射关系,包括自动匹配、消歧逻辑、数据库操作。

### Class Definition

```python
class MappingService:
    """映射关系管理服务

    Attributes:
        coingecko_client: CoinGecko API客户端
        binance_client: 币安API客户端
    """

    def __init__(
        self,
        coingecko_client: CoingeckoClient,
        binance_client: Client
    ):
        self.coingecko_client = coingecko_client
        self.binance_client = binance_client
```

### Method 1: get_binance_usdt_perpetuals

```python
def get_binance_usdt_perpetuals(self) -> List[Dict[str, str]]:
    """获取所有币安USDT永续合约

    Returns:
        List[Dict]: 包含symbol和baseAsset的合约列表
        [
            {"symbol": "BTCUSDT", "base_token": "BTC"},
            {"symbol": "ETHUSDT", "base_token": "ETH"},
            ...
        ]
    """
    exchange_info = self.binance_client.futures_exchange_info()

    usdt_perpetuals = [
        {
            "symbol": symbol_info["symbol"],
            "base_token": symbol_info["baseAsset"]
        }
        for symbol_info in exchange_info["symbols"]
        if (
            symbol_info["quoteAsset"] == "USDT"
            and symbol_info["contractType"] == "PERPETUAL"
            and symbol_info["status"] == "TRADING"
        )
    ]

    logger.info(f"Found {len(usdt_perpetuals)} USDT perpetual contracts")
    return usdt_perpetuals
```

### Method 2: match_coingecko_id

```python
def match_coingecko_id(
    self,
    base_token: str,
    coins_list: List[Dict[str, Any]]
) -> Tuple[Optional[str], str, List[str]]:
    """匹配CoinGecko ID

    Args:
        base_token: 基础代币symbol(如BTC)
        coins_list: CoinGecko代币列表

    Returns:
        Tuple[Optional[str], str, List[str]]:
            - coingecko_id: 匹配到的ID(如果唯一或自动选择成功)
            - match_status: auto_matched/needs_review
            - alternatives: 候选ID列表
    """
    # Step 1: 过滤出symbol匹配的所有代币
    candidates = [
        coin for coin in coins_list
        if coin["symbol"].lower() == base_token.lower()
    ]

    if len(candidates) == 0:
        logger.warning(f"No CoinGecko match found for {base_token}")
        return (None, "needs_review", [])

    if len(candidates) == 1:
        logger.info(f"Unique match for {base_token}: {candidates[0]['id']}")
        return (candidates[0]["id"], "auto_matched", [])

    # Step 2: 同名冲突,需要消歧
    logger.warning(f"Multiple matches for {base_token}: {len(candidates)} candidates")
    return self._resolve_conflict(base_token, candidates)
```

### Method 3: _resolve_conflict (私有方法)

```python
def _resolve_conflict(
    self,
    base_token: str,
    candidates: List[Dict[str, Any]]
) -> Tuple[Optional[str], str, List[str]]:
    """解决同名代币冲突

    优先级规则:
    1. 24h交易量最大(差距>2x)
    2. 市值排名最高
    3. 仍无法区分则标记needs_review

    Args:
        base_token: 基础代币symbol
        candidates: 候选代币列表

    Returns:
        Tuple[coingecko_id, match_status, alternatives]
    """
    # 获取候选代币的市场数据(包含交易量和排名)
    coin_ids = [c["id"] for c in candidates]
    market_data = self.coingecko_client.fetch_market_data(coin_ids)

    # 构建id -> market_data映射
    market_map = {md["id"]: md for md in market_data}

    # Step 1: 按24h交易量排序
    sorted_by_volume = sorted(
        candidates,
        key=lambda c: market_map.get(c["id"], {}).get("total_volume", 0),
        reverse=True
    )

    top1_vol = market_map.get(sorted_by_volume[0]["id"], {}).get("total_volume", 0)
    top2_vol = market_map.get(sorted_by_volume[1]["id"], {}).get("total_volume", 0) if len(sorted_by_volume) > 1 else 0

    if top1_vol > top2_vol * 2:
        selected_id = sorted_by_volume[0]["id"]
        logger.info(f"Auto-matched {base_token} by volume: {selected_id} (vol={top1_vol})")
        return (
            selected_id,
            "auto_matched",
            [c["id"] for c in sorted_by_volume[1:3]]
        )

    # Step 2: 按市值排名排序
    sorted_by_rank = sorted(
        candidates,
        key=lambda c: market_map.get(c["id"], {}).get("market_cap_rank") or 999999
    )

    top_rank = market_map.get(sorted_by_rank[0]["id"], {}).get("market_cap_rank")

    if top_rank is not None:
        selected_id = sorted_by_rank[0]["id"]
        logger.info(f"Auto-matched {base_token} by rank: {selected_id} (rank={top_rank})")
        return (
            selected_id,
            "auto_matched",
            [c["id"] for c in sorted_by_rank[1:3]]
        )

    # Step 3: 无法自动选择,标记needs_review
    logger.warning(f"Cannot auto-match {base_token}, marking as needs_review")
    return (
        None,
        "needs_review",
        [c["id"] for c in candidates]
    )
```

### Method 4: generate_mappings

```python
@transaction.atomic
def generate_mappings(self) -> Dict[str, Any]:
    """生成所有币安合约的映射关系

    Returns:
        Dict: 统计信息
        {
            "total": 500,
            "auto_matched": 450,
            "needs_review": 50,
            "details": [...]
        }
    """
    batch_id = UpdateLog.log_batch_start("mapping_update")
    start_time = time.time()

    # Step 1: 获取币安合约列表
    contracts = self.get_binance_usdt_perpetuals()

    # Step 2: 获取CoinGecko代币列表
    coins_list = self.coingecko_client.fetch_coins_list()

    # Step 3: 逐个匹配
    stats = {
        "total": len(contracts),
        "auto_matched": 0,
        "needs_review": 0,
        "details": []
    }

    for contract in contracts:
        symbol = contract["symbol"]
        base_token = contract["base_token"]

        coingecko_id, match_status, alternatives = self.match_coingecko_id(
            base_token,
            coins_list
        )

        # 写入数据库
        TokenMapping.objects.update_or_create(
            symbol=symbol,
            defaults={
                "base_token": base_token,
                "coingecko_id": coingecko_id,
                "match_status": match_status,
                "alternatives": alternatives if alternatives else None
            }
        )

        # 统计
        if match_status == "auto_matched":
            stats["auto_matched"] += 1
        else:
            stats["needs_review"] += 1

        stats["details"].append({
            "symbol": symbol,
            "base_token": base_token,
            "coingecko_id": coingecko_id,
            "match_status": match_status
        })

    # Step 4: 记录日志
    duration = time.time() - start_time
    UpdateLog.log_batch_complete(
        batch_id=batch_id,
        total=stats["total"],
        success=stats["auto_matched"],
        failed=stats["needs_review"],
        duration=duration
    )

    logger.info(f"Mapping generation completed: {stats}")
    return stats
```

---

## Internal Service 3: MarketDataService

### 职责
管理市值和FDV数据的获取、存储、更新流程。

### Class Definition

```python
class MarketDataService:
    """市场数据服务

    Attributes:
        coingecko_client: CoinGecko API客户端
    """

    def __init__(self, coingecko_client: CoingeckoClient):
        self.coingecko_client = coingecko_client
```

### Method 1: update_all

```python
@transaction.atomic
def update_all(self) -> Dict[str, Any]:
    """更新所有映射关系对应的市值/FDV数据

    Returns:
        Dict: 更新统计信息
        {
            "total": 450,
            "success": 430,
            "failed": 20,
            "failed_symbols": ["XYZUSDT", ...],
            "duration_seconds": 180
        }
    """
    batch_id = UpdateLog.log_batch_start("data_fetch")
    start_time = time.time()

    # Step 1: 获取所有需要更新的映射关系
    mappings = TokenMapping.objects.filter(
        match_status__in=["auto_matched", "manual_confirmed"],
        coingecko_id__isnull=False
    )

    coin_ids = [m.coingecko_id for m in mappings]
    logger.info(f"Updating market data for {len(coin_ids)} symbols")

    # Step 2: 批量获取市场数据
    market_data_list = self.coingecko_client.fetch_market_data(coin_ids)

    # 构建coingecko_id -> market_data映射
    market_map = {md["id"]: md for md in market_data_list}

    # Step 3: 更新数据库
    stats = {
        "total": len(mappings),
        "success": 0,
        "failed": 0,
        "failed_symbols": []
    }

    for mapping in mappings:
        market_data = market_map.get(mapping.coingecko_id)

        if market_data is None:
            logger.warning(f"No market data for {mapping.symbol} (id={mapping.coingecko_id})")
            stats["failed"] += 1
            stats["failed_symbols"].append(mapping.symbol)

            UpdateLog.log_symbol_error(
                batch_id=batch_id,
                symbol=mapping.symbol,
                error="No market data returned from CoinGecko"
            )
            continue

        try:
            MarketData.objects.update_or_create(
                symbol=mapping.symbol,
                defaults={
                    "market_cap": market_data.get("market_cap"),
                    "fully_diluted_valuation": market_data.get("fully_diluted_valuation"),
                    "data_source": "coingecko",
                    "fetched_at": timezone.now()
                }
            )
            stats["success"] += 1

        except Exception as e:
            logger.error(f"Failed to update {mapping.symbol}: {e}")
            stats["failed"] += 1
            stats["failed_symbols"].append(mapping.symbol)

            UpdateLog.log_symbol_error(
                batch_id=batch_id,
                symbol=mapping.symbol,
                error=str(e)
            )

    # Step 4: 记录批次完成
    duration = time.time() - start_time
    UpdateLog.log_batch_complete(
        batch_id=batch_id,
        total=stats["total"],
        success=stats["success"],
        failed=stats["failed"],
        duration=duration
    )

    logger.info(f"Market data update completed: {stats}")
    return stats
```

### Method 2: update_single

```python
def update_single(self, symbol: str) -> bool:
    """更新单个symbol的市值/FDV数据

    Args:
        symbol: 币安交易对symbol

    Returns:
        bool: 更新是否成功
    """
    try:
        mapping = TokenMapping.objects.get(symbol=symbol)

        if not mapping.is_ready_for_update():
            logger.warning(f"{symbol} is not ready for update (status={mapping.match_status})")
            return False

        # 获取市场数据
        market_data_list = self.coingecko_client.fetch_market_data([mapping.coingecko_id])

        if not market_data_list:
            logger.error(f"No market data returned for {symbol}")
            return False

        market_data = market_data_list[0]

        # 更新数据库
        MarketData.objects.update_or_create(
            symbol=symbol,
            defaults={
                "market_cap": market_data.get("market_cap"),
                "fully_diluted_valuation": market_data.get("fully_diluted_valuation"),
                "data_source": "coingecko",
                "fetched_at": timezone.now()
            }
        )

        logger.info(f"Updated market data for {symbol}")
        return True

    except TokenMapping.DoesNotExist:
        logger.error(f"No mapping found for {symbol}")
        return False
    except Exception as e:
        logger.error(f"Failed to update {symbol}: {e}")
        return False
```

---

## Error Codes Reference

### CoinGecko API Error Codes

| 状态码 | 说明 | 重试 | 处理策略 |
|--------|------|------|---------|
| 200 | 成功 | - | 正常处理 |
| 400 | 请求参数错误 | ❌ | 检查参数,记录错误 |
| 401 | API密钥无效 | ❌ | 检查环境变量,停止执行 |
| 404 | coin_id不存在 | ❌ | 标记为needs_review |
| 429 | 限流超限 | ✅ | 等待Retry-After秒数 |
| 500 | 服务器内部错误 | ✅ | 指数退避重试 |
| 503 | 服务不可用 | ✅ | 指数退避重试 |

### Internal Service Error Codes

```python
class ServiceError(Exception):
    """服务层基础异常"""
    pass

class MappingError(ServiceError):
    """映射相关错误"""
    pass

class DataFetchError(ServiceError):
    """数据获取错误"""
    pass

class APIClientError(ServiceError):
    """API客户端错误"""
    pass
```

---

## Testing Contracts

### Unit Test: CoingeckoClient

```python
def test_fetch_coins_list_success(mock_requests):
    """测试成功获取代币列表"""
    mock_response = [
        {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"}
    ]
    mock_requests.get.return_value.json.return_value = mock_response

    client = CoingeckoClient(api_key="test_key")
    result = client.fetch_coins_list()

    assert len(result) == 1
    assert result[0]["id"] == "bitcoin"

def test_fetch_market_data_with_rate_limit(mock_requests):
    """测试限流情况下的重试"""
    # 第一次调用返回429
    mock_requests.get.return_value.status_code = 429
    mock_requests.get.return_value.headers = {"Retry-After": "1"}

    # 第二次调用成功
    mock_response = [{"id": "bitcoin", "market_cap": 800000000000}]
    mock_requests.get.return_value.json.return_value = mock_response

    client = CoingeckoClient(api_key="test_key")
    result = client.fetch_market_data(["bitcoin"])

    assert len(result) == 1
    assert mock_requests.get.call_count == 2  # 重试了一次
```

### Integration Test: MappingService

```python
def test_generate_mappings_with_conflicts(db, mock_coingecko, mock_binance):
    """测试包含同名冲突的映射生成"""
    # Mock币安返回
    mock_binance.futures_exchange_info.return_value = {
        "symbols": [
            {"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT",
             "contractType": "PERPETUAL", "status": "TRADING"}
        ]
    }

    # Mock CoinGecko返回(BTC有2个候选)
    mock_coingecko.fetch_coins_list.return_value = [
        {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"},
        {"id": "bitcoin-cash", "symbol": "btc", "name": "Bitcoin Cash"}
    ]

    # Mock市场数据(bitcoin交易量更大)
    mock_coingecko.fetch_market_data.return_value = [
        {"id": "bitcoin", "total_volume": 20000000000, "market_cap_rank": 1},
        {"id": "bitcoin-cash", "total_volume": 500000000, "market_cap_rank": 30}
    ]

    service = MappingService(mock_coingecko, mock_binance)
    stats = service.generate_mappings()

    assert stats["total"] == 1
    assert stats["auto_matched"] == 1  # 自动选择了bitcoin

    mapping = TokenMapping.objects.get(symbol="BTCUSDT")
    assert mapping.coingecko_id == "bitcoin"
    assert mapping.match_status == "auto_matched"
```

---

**API Contracts Defined by**: Claude Code
**Date**: 2025-12-12
**Status**: Ready for Implementation ✅
