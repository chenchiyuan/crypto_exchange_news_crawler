# 加密货币交易所USDT永续合约API调研报告

**调研日期**: 2025-11-10
**功能**: Futures Contract Data Monitor (002-futures-data-monitor)

## 调研目标

**原始调研范围** (完整版):
为4个加密货币交易所(Binance, Bybit, Bitget, Hyperliquid)调研获取USDT永续合约数据的API,包括:
- 合约列表
- Open Interest (持仓量)
- 24小时交易量
- 资金费率
- 资金费率上下限
- 下次资金费率结算时间

**MVP阶段实施范围** (简化版 - 2025-11-10更新):
- **实施的交易所** (按优先级): Binance (P1) → Hyperliquid (P2) → Bybit (P3)
- **延后实施**: Bitget (暂不实现)
- **实施的指标**: 合约列表 + 当前价格
- **延后的指标**: Open Interest, 24小时交易量, 资金费率, 资金费率上下限, 下次资金费率结算时间

**注意**: 本调研报告保留完整的技术调研内容,以便 Phase 2 扩展时参考。

## 1. Binance (币安)

### 关键发现
- ✅ 提供完整的资金费率上下限信息
- ✅ 所有端点均为公开接口
- ⚠️ 需要调用3-4个不同端点获取完整数据

### API端点汇总

| 端点 | 用途 | Weight | URL |
|------|------|--------|-----|
| exchangeInfo | 获取合约列表 | 1 | `https://fapi.binance.com/fapi/v1/exchangeInfo` |
| ticker/24hr | 获取24小时交易数据 | 1/40 | `https://fapi.binance.com/fapi/v1/ticker/24hr` |
| premiumIndex | 获取资金费率 | 1/10 | `https://fapi.binance.com/fapi/v1/premiumIndex` |
| openInterest | 获取持仓量 | 1 | `https://fapi.binance.com/fapi/v1/openInterest` |
| fundingInfo | 获取费率上下限 | 1 | `https://fapi.binance.com/fapi/v1/fundingInfo` |

### 字段映射

| 需求字段 | API响应字段 | 来源端点 | 数据类型 | 示例值 |
|---------|------------|---------|---------|--------|
| Symbol | symbol | exchangeInfo | string | "BTCUSDT" |
| Contract Type | contractType | exchangeInfo | string | "PERPETUAL" |
| Open Interest | openInterest | openInterest | string | "10659.509" |
| 24H Volume | volume | ticker/24hr | string | "8913.30000000" |
| 24H Quote Volume | quoteVolume | ticker/24hr | string | "15.30000000" |
| Funding Rate | lastFundingRate | premiumIndex | string | "0.00038246" |
| Next Funding Time | nextFundingTime | premiumIndex | integer | 1597392000000 |
| Upper Bound | adjustedFundingRateCap | fundingInfo | string | "0.02500000" |
| Lower Bound | adjustedFundingRateFloor | fundingInfo | "-0.02500000" |
| Mark Price | markPrice | premiumIndex | string | "11793.63104562" |

### Rate Limit
- **限制**: 1200 weight/分钟 (约20请求/秒)
- **机制**: 基于weight的滑动窗口
- **响应头**: `x-mbx-used-weight-1m`

### 实现建议
```python
# 分3步获取完整数据
1. GET /fapi/v1/exchangeInfo  # 获取所有PERPETUAL合约
2. GET /fapi/v1/ticker/24hr  # 批量获取24小时数据
3. GET /fapi/v1/premiumIndex  # 批量获取资金费率
4. GET /fapi/v1/fundingInfo  # 批量获取费率上下限
```

**参考文档**: https://developers.binance.com/docs/derivatives/usds-margined-futures

---

## 2. Bybit

### 关键发现
- ✅ tickers端点非常全面,一次调用包含大部分数据
- ✅ V5 API设计现代化,响应结构清晰
- ⚠️ 不提供资金费率上下限

### API端点汇总

| 端点 | 用途 | Weight | URL |
|------|------|--------|-----|
| instruments-info | 获取合约配置 | - | `https://api.bybit.com/v5/market/instruments-info?category=linear` |
| tickers | 获取行情(含OI/Volume/Funding) | - | `https://api.bybit.com/v5/market/tickers?category=linear` |

### 字段映射

| 需求字段 | API响应字段 | 来源端点 | 数据类型 | 示例值 |
|---------|------------|---------|---------|--------|
| Symbol | symbol | instruments-info | string | "BTCUSDT" |
| Contract Type | contractType | instruments-info | string | "LinearPerpetual" |
| Open Interest | openInterest | tickers | string | "373504.053" |
| 24H Volume | volume24h | tickers | string | "49337318" |
| 24H Turnover | turnover24h | tickers | string | "2352.94950046" |
| Funding Rate | fundingRate | tickers | string | "0.0001" |
| Next Funding Time | nextFundingTime | tickers | string | "1672387200000" |
| Upper Bound | ❌ | - | - | Not Available |
| Lower Bound | ❌ | - | - | Not Available |
| Mark Price | markPrice | tickers | string | "16596.00" |

### Rate Limit
- **限制**: 约1200 weight/分钟 (约20请求/秒)
- **机制**: 基于weight和请求数
- **响应头**: `X-Bapi-Limit-Status`, `X-Bapi-Limit`, `X-Bapi-Limit-Reset-Timestamp`

### 实现建议
```python
# 2步获取完整数据(最简洁)
1. GET /v5/market/instruments-info?category=linear  # 获取合约列表
2. GET /v5/market/tickers?category=linear  # 批量获取所有数据
```

**参考文档**: https://bybit-exchange.github.io/docs/v5/intro

---

## 3. Bitget ⚠️ **MVP阶段延后实施**

> **注意**: 根据2025-11-10的优先级调整,Bitget交易所暂不在MVP阶段实现。本调研内容保留供Phase 2参考。

### 关键发现
- ✅ 提供完整的资金费率上下限信息
- ✅ current-fund-rate端点包含min/maxFundingRate字段
- ⚠️ 需要调用3-4个端点获取完整数据

### API端点汇总

| 端点 | 用途 | Rate Limit | URL |
|------|------|-----------|-----|
| contracts | 获取合约配置 | 20 req/s | `https://api.bitget.com/api/v2/mix/market/contracts?productType=usdt-futures` |
| tickers | 获取行情数据 | 20 req/s | `https://api.bitget.com/api/v2/mix/market/tickers?productType=usdt-futures` |
| current-fund-rate | 获取资金费率(含上下限) | 20 req/s | `https://api.bitget.com/api/v2/mix/market/current-fund-rate` |
| open-interest | 获取持仓量 | 10 req/s | `https://api.bitget.com/api/v2/mix/market/open-interest` |

### 字段映射

| 需求字段 | API响应字段 | 来源端点 | 数据类型 | 示例值 |
|---------|------------|---------|---------|--------|
| Symbol | symbol | contracts | string | "BTCUSDT" |
| Symbol Type | symbolType | contracts | string | "perpetual" |
| Open Interest | amount / holdingAmount | open-interest / tickers | string | "12345.678" |
| 24H Volume | baseVolume | tickers | string | "375206.363" |
| 24H Quote Volume | quoteVolume | tickers | string | "10220763408.0341" |
| Funding Rate | fundingRate | current-fund-rate | string | "0.000068" |
| Next Funding Time | nextUpdate | current-fund-rate | string | "1743062400000" |
| Upper Bound | maxFundingRate | current-fund-rate | string | "0.003" |
| Lower Bound | minFundingRate | current-fund-rate | string | "-0.003" |
| Funding Interval | fundingRateInterval | current-fund-rate | string | "8" |

### Rate Limit
- **限制**: 20请求/秒/IP (大部分端点)
- **机制**: 基于IP的速率限制
- **响应头**: 标准HTTP头

### 实现建议
```python
# 分3步获取完整数据
1. GET /api/v2/mix/market/contracts?productType=usdt-futures  # 获取合约列表
2. GET /api/v2/mix/market/tickers?productType=usdt-futures  # 批量获取行情
3. GET /api/v2/mix/market/current-fund-rate (逐个symbol)  # 获取资金费率及上下限
```

**参考文档**: https://www.bitget.com/api-doc/contract/intro

---

## 4. Hyperliquid

### 关键发现
- ✅ 一个端点返回所有数据,非常高效
- ✅ POST方法,JSON body指定查询类型
- ⚠️ 符号格式不同: "BTC" 而非 "BTCUSDT"
- ⚠️ 不提供资金费率上下限
- ⚠️ 不提供明确的Next Funding Time

### API端点

| 端点 | 用途 | Weight | URL |
|------|------|--------|-----|
| /info (metaAndAssetCtxs) | 获取所有合约数据 | 20 | `https://api.hyperliquid.xyz/info` |

### 请求格式
```json
POST https://api.hyperliquid.xyz/info
Content-Type: application/json

{
  "type": "metaAndAssetCtxs"
}
```

### 响应结构
返回一个包含2个元素的数组:
- 第1个元素: `universe` (合约元数据数组)
- 第2个元素: `assetCtxs` (市场数据数组,按索引与universe对应)

### 字段映射

| 需求字段 | API响应字段 | 索引位置 | 数据类型 | 示例值 |
|---------|------------|---------|---------|--------|
| Symbol | name | universe[i] | string | "BTC" ⚠️ 注意格式 |
| Max Leverage | maxLeverage | universe[i] | integer | 50 |
| Open Interest | openInterest | assetCtxs[i] | string | "688.11" |
| 24H Volume | dayNtlVlm | assetCtxs[i] | string | "1169046.29406" |
| Funding Rate | funding | assetCtxs[i] | string | "0.0000125" |
| Next Funding Time | ❌ | - | - | Not Available |
| Upper Bound | ❌ | - | - | Not Available |
| Lower Bound | ❌ | - | - | Not Available |
| Mark Price | markPx | assetCtxs[i] | string | "14.3161" |
| Oracle Price | oraclePx | assetCtxs[i] | string | "14.32" |
| Premium | premium | assetCtxs[i] | string | "0.00031774" |

### Rate Limit
- **机制**: Token bucket (最大100 tokens, 每秒补充10)
- **限制**: metaAndAssetCtxs请求 weight=20
- **限流**: 1200 weight/分钟 (约20请求/秒)
- **被限流后**: 每10秒允许1个请求

### 实现建议
```python
# 一次POST请求获取所有数据
POST /info
Body: {"type": "metaAndAssetCtxs"}

# 处理响应
universe = response[0]  # 合约元数据
assetCtxs = response[1]  # 市场数据

# 遍历并组合
for i, meta in enumerate(universe):
    symbol = meta["name"]  # ⚠️ 需要转换为 "BTCUSDT" 格式
    data = assetCtxs[i]
    # ... 处理数据
```

**符号格式转换**:
```python
# Hyperliquid: "BTC" → 标准格式: "BTCUSDT"
standard_symbol = f"{hyperliquid_symbol}USDT"
```

**参考文档**: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api

---

## 综合对比分析

### 数据完整性

| 特性 | Binance | Bybit | Bitget | Hyperliquid |
|------|---------|-------|--------|-------------|
| 合约列表 | ✅ | ✅ | ✅ | ✅ |
| Open Interest | ✅ | ✅ | ✅ | ✅ |
| 24H Volume | ✅ | ✅ | ✅ | ✅ |
| Funding Rate | ✅ | ✅ | ✅ | ✅ |
| Next Funding Time | ✅ | ✅ | ✅ | ❌ |
| Upper Bound | ✅ | ❌ | ✅ | ❌ |
| Lower Bound | ✅ | ❌ | ✅ | ❌ |
| 符号格式 | BTCUSDT | BTCUSDT | BTCUSDT | BTC ⚠️ |

### API设计评分

| 交易所 | 端点数量 | 数据集中度 | 易用性 | Rate Limit | 综合评分 |
|--------|---------|----------|--------|-----------|---------|
| **Binance** | 4-5个 | 低 | ⭐⭐⭐ | 20 req/s | ⭐⭐⭐⭐⭐ |
| **Bybit** | 2个 | 高 | ⭐⭐⭐⭐⭐ | 20 req/s | ⭐⭐⭐⭐ |
| **Bitget** | 3-4个 | 中 | ⭐⭐⭐⭐ | 20 req/s | ⭐⭐⭐⭐⭐ |
| **Hyperliquid** | 1个 | 极高 | ⭐⭐⭐ | 20 req/s | ⭐⭐⭐ |

**评分说明**:
- Bybit: 易用性最佳,tickers端点包含几乎所有数据
- Bitget: 数据最完整,提供资金费率上下限
- Binance: 最稳定可靠,数据最权威
- Hyperliquid: 最高效(一次请求),但格式特殊且缺少部分字段

### 实现复杂度排序

1. **Bybit** (最简单) - 2个端点,数据集中
2. **Hyperliquid** (简单) - 1个端点,但需要格式转换和缺失字段处理
3. **Bitget** (中等) - 3-4个端点,逻辑清晰
4. **Binance** (复杂) - 4-5个端点,需要多次调用

---

## 技术决策

### 决策1: API客户端架构

**选择**: 抽象基类 + 独立实现

**理由**:
1. 每个交易所的API设计差异大(端点数量、响应格式、符号命名)
2. 符合开闭原则,方便后续扩展新交易所
3. 便于单独测试和维护

**实现模式**:
```python
class BaseFuturesClient(ABC):
    @abstractmethod
    def fetch_contracts(self) -> List[FuturesContract]:
        pass

    @abstractmethod
    def _normalize_symbol(self, raw_symbol: str) -> str:
        """统一符号格式为 BTCUSDT"""
        pass

class BinanceFuturesClient(BaseFuturesClient):
    def fetch_contracts(self):
        # 调用4个端点并合并数据
        pass

class HyperliquidFuturesClient(BaseFuturesClient):
    def _normalize_symbol(self, raw_symbol: str) -> str:
        return f"{raw_symbol}USDT"  # BTC → BTCUSDT
```

### 决策2: 缺失字段处理

**问题**: Bybit和Hyperliquid不提供资金费率上下限

**选择**: 存储为 NULL,在Admin界面显示 "N/A"

**理由**:
1. 保持数据模型一致性
2. 明确标识数据不可用,而非错误的零值
3. 未来如果交易所提供,可直接填充

**数据库字段**:
```python
funding_rate_upper = models.DecimalField(
    null=True, blank=True,  # 允许NULL
    help_text="Bybit和Hyperliquid不提供此字段"
)
```

### 决策3: 重试策略

**配置**:
- 重试次数: 3次
- 退避策略: 指数退避 (1s, 2s, 4s)
- 超时设置: 10秒/请求

**理由**:
1. 遵循规范要求(FR-008)
2. 平衡可靠性和性能
3. 符合行业最佳实践

**实现**:
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4)
)
def fetch_with_retry(url):
    return requests.get(url, timeout=10)
```

### 决策4: Rate Limit控制

**策略**: 每个交易所独立的速率限制器

**实现**:
```python
from ratelimit import limits, sleep_and_retry

class BinanceFuturesClient:
    @sleep_and_retry
    @limits(calls=20, period=1)  # 20请求/秒
    def _make_request(self, endpoint):
        pass
```

**理由**:
1. 避免触发交易所限流
2. 4个交易所并行请求互不影响
3. 符合宪法"尊重服务器"原则

---

## 备选方案考虑

### 备选方案1: 使用CCXT库

**优点**:
- 统一的接口,无需自己实现每个交易所
- 已处理符号格式转换和错误处理
- 社区维护,稳定可靠

**缺点**:
- 引入额外依赖(较重)
- 可能不支持所有我们需要的字段(如资金费率上下限)
- 学习曲线

**决策**: ❌ 不采用

**理由**:
1. 我们只需要4个交易所,自己实现更轻量
2. 需要的字段很特定,CCXT不一定都支持
3. 符合"简单至上"原则

### 备选方案2: 使用WebSocket实时数据流

**优点**:
- 实时性更好
- 减少轮询请求

**缺点**:
- 实现复杂度高
- 需要维护长连接
- Hyperliquid的WebSocket文档不完整

**决策**: ❌ 不采用 (在Scope中已明确排除)

**理由**:
1. 5分钟轮询已满足需求
2. 符合"简单至上"和"务实主义"原则
3. 降低系统复杂度

---

## 实施建议

### 开发顺序 (MVP阶段 - 2025-11-10更新)

**优先级1: Binance** (最权威,先实现)
- 理由: 作为最大交易所,数据最权威,优先级最高
- MVP简化: 只需调用 `exchangeInfo` 获取合约列表 + `ticker/bookTicker` 获取当前价格
- 完整版 (Phase 2): 4个端点获取完整数据 (OI, Volume, Funding)

**优先级2: Hyperliquid** (新兴交易所,高关注度)
- 理由: 新兴交易所,用户高度关注
- MVP简化: 调用 `metaAndAssetCtxs` 获取合约列表和 `markPx` (当前价格)
- 特殊处理: 符号格式转换 (BTC → BTCUSDT)
- 完整版 (Phase 2): 添加 OI, Volume, Funding 字段

**优先级3: Bybit** (API最简洁)
- 理由: API设计最简洁,2个端点即可
- MVP简化: `instruments-info` + `tickers` (提取 `lastPrice`)
- 完整版 (Phase 2): tickers端点已包含几乎所有数据

**延后至Phase 2: Bitget**
- 理由: MVP阶段暂不实现
- 保留调研: 供未来扩展参考

### 测试策略

1. **单元测试**: 每个API客户端独立测试
   - Mock API响应
   - 测试数据解析和转换
   - 测试错误处理

2. **集成测试**: 真实API调用(有限次数)
   - 验证端点可用性
   - 验证响应格式
   - 验证rate limit处理

3. **边界测试**:
   - Hyperliquid符号格式转换
   - 缺失字段处理
   - API失败和重试

---

## 附录: 示例代码片段

### Hyperliquid符号格式处理

```python
def normalize_hyperliquid_symbol(hl_symbol: str) -> str:
    """
    将Hyperliquid的符号格式转换为标准格式

    Args:
        hl_symbol: Hyperliquid符号 (例如: "BTC")

    Returns:
        标准符号 (例如: "BTCUSDT")
    """
    return f"{hl_symbol}USDT"

def denormalize_to_hyperliquid(standard_symbol: str) -> str:
    """
    将标准符号转换为Hyperliquid格式

    Args:
        standard_symbol: 标准符号 (例如: "BTCUSDT")

    Returns:
        Hyperliquid符号 (例如: "BTC")
    """
    if standard_symbol.endswith("USDT"):
        return standard_symbol[:-4]
    return standard_symbol
```

### 缺失字段处理

```python
def safe_get_funding_bounds(data: dict, exchange: str) -> tuple:
    """
    安全获取资金费率上下限

    Returns:
        (upper_bound, lower_bound) 或 (None, None)
    """
    if exchange in ["bybit", "hyperliquid"]:
        return None, None

    return (
        data.get("maxFundingRate") or data.get("adjustedFundingRateCap"),
        data.get("minFundingRate") or data.get("adjustedFundingRateFloor")
    )
```

---

**调研完成时间**: 2025-11-10
**下一步**: 根据本调研结果设计数据模型和API客户端架构
