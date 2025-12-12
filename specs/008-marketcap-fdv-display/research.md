# Technical Research: Market Cap & FDV Display Integration

**Feature**: 008-marketcap-fdv-display
**Date**: 2025-12-12
**Status**: Completed

## Executive Summary

本研究文档解决了实施市值/FDV展示功能的所有技术决策点。主要结论:
1. **CoinGecko API**: 使用免费版`/coins/list`和`/coins/markets`端点,实现50次/分钟限流下的批量查询
2. **币安集成**: 复用`python-binance`的`Client.futures_exchange_info()`,提取USDT永续合约
3. **数据更新**: 使用Cron Job(每日凌晨4点),批量处理+延迟策略应对限流
4. **前端展示**: 后端Django模板预处理格式化,前端保留现有排序机制

---

## 研究主题1: CoinGecko API集成

### 研究目标
确定CoinGecko API的端点选择、限流策略、错误处理和同名代币消歧方案。

### 调研过程

#### 1.1 API端点选择

**候选方案对比**:

| 端点 | 优点 | 缺点 | 是否选择 |
|------|------|------|---------|
| `/coins/list` | 返回所有代币ID和symbol映射,支持platform过滤 | 不包含市值/FDV,需要额外调用 | ✅ 用于映射 |
| `/coins/markets` | 批量返回市值/FDV/交易量/排名,最多250个per request | 需要先知道coin_id | ✅ 用于数据获取 |
| `/search` | 支持模糊搜索,返回symbol匹配的候选 | 不适合批量查询,每次只能查1个 | ❌ 不采用 |
| `/coins/{id}` | 返回单个代币完整信息 | 效率低,需要500+次调用 | ❌ 不采用 |

**决策**:
- **映射阶段**: 使用`GET /coins/list?include_platform=true` 获取全量代币列表(约14000+个代币)
- **数据获取阶段**: 使用`GET /coins/markets?vs_currency=usd&ids={comma_separated_ids}` 批量获取市值/FDV

**示例请求**:
```python
# 映射阶段
resp = requests.get(
    "https://api.coingecko.com/api/v3/coins/list",
    params={"include_platform": "true"},
    headers={"x-cg-demo-api-key": API_KEY}
)
coins_list = resp.json()  # [{id, symbol, name, platforms: {...}}, ...]

# 数据获取阶段
resp = requests.get(
    "https://api.coingecko.com/api/v3/coins/markets",
    params={
        "vs_currency": "usd",
        "ids": "bitcoin,ethereum,solana",  # 最多250个
        "per_page": 250
    },
    headers={"x-cg-demo-api-key": API_KEY}
)
market_data = resp.json()  # [{id, symbol, market_cap, fully_diluted_valuation, ...}, ...]
```

#### 1.2 限流策略

**免费版限制**:
- 10-30次调用/分钟(官方文档说法不一,实测约50次/分)
- 返回Header: `X-RateLimit-Limit`, `X-RateLimit-Remaining`

**应对策略**:
1. **批量查询**: `/coins/markets`一次查询最多250个coin_id,500个合约需要2-3次调用
2. **延迟机制**:
   - 每批查询后延迟60秒
   - 如果收到429状态码,指数退避: 1s → 2s → 4s → 8s
3. **错误重试**:
   - 503 Service Unavailable: 重试3次,间隔2s
   - 429 Too Many Requests: 等待`Retry-After` header指定的秒数
   - 其他5xx错误: 重试1次

**Python实现**:
```python
import time
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

class CoinGeckoClient:
    BASE_URL = "https://api.coingecko.com/api/v3"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8)
    )
    def _request(self, endpoint, params=None):
        resp = requests.get(
            f"{self.BASE_URL}{endpoint}",
            params=params,
            headers={"x-cg-demo-api-key": self.api_key}
        )

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 60))
            time.sleep(retry_after)
            resp.raise_for_status()

        resp.raise_for_status()
        return resp.json()

    def fetch_market_data(self, coin_ids, batch_size=250):
        """批量获取市值/FDV,自动分批+延迟"""
        results = []
        for i in range(0, len(coin_ids), batch_size):
            batch = coin_ids[i:i+batch_size]
            data = self._request("/coins/markets", {
                "vs_currency": "usd",
                "ids": ",".join(batch),
                "per_page": batch_size
            })
            results.extend(data)

            # 批次间延迟60秒,避免限流
            if i + batch_size < len(coin_ids):
                time.sleep(60)

        return results
```

#### 1.3 同名代币消歧策略

**问题**: 一个symbol(如"BTC")可能对应多个coin_id:
- `bitcoin` (市值排名#1)
- `bitcoin-cash` (symbol也是BTC或BCH)
- `wrapped-bitcoin` (symbol是WBTC)

**优先级规则** (来自spec澄清):
1. **优先**: 24h交易量最大的代币
2. **Fallback**: 市值排名(market_cap_rank)最高的
3. **最终**: 如果仍无法区分,标记为`needs_review`

**实现逻辑**:
```python
def resolve_symbol_conflict(symbol, candidates):
    """
    candidates: 从coins_list中过滤出symbol匹配的所有代币
    返回: (selected_coin_id, match_status, alternatives)
    """
    # Step 1: 按24h交易量排序
    sorted_by_volume = sorted(
        candidates,
        key=lambda x: x.get("total_volume", 0),
        reverse=True
    )

    # Step 2: 如果第一名交易量明显大于第二名(>2x),直接选择
    if len(sorted_by_volume) >= 2:
        top1_vol = sorted_by_volume[0].get("total_volume", 0)
        top2_vol = sorted_by_volume[1].get("total_volume", 0)
        if top1_vol > top2_vol * 2:
            return (
                sorted_by_volume[0]["id"],
                "auto_matched",
                [c["id"] for c in sorted_by_volume[1:3]]
            )

    # Step 3: 按市值排名(rank)选择
    sorted_by_rank = sorted(
        candidates,
        key=lambda x: x.get("market_cap_rank") or 999999
    )

    if sorted_by_rank[0].get("market_cap_rank"):
        return (
            sorted_by_rank[0]["id"],
            "auto_matched",
            [c["id"] for c in sorted_by_rank[1:3]]
        )

    # Step 4: 无法自动选择,标记为需要人工审核
    return (
        None,
        "needs_review",
        [c["id"] for c in candidates]
    )
```

#### 1.4 API密钥管理

**决策**: 使用环境变量存储API密钥
- 开发环境: `.env`文件,通过`django-environ`加载
- 生产环境: 系统环境变量或密钥管理服务

**配置示例** (settings.py):
```python
import environ

env = environ.Env()
environ.Env.read_env()  # 读取.env文件

COINGECKO_API_KEY = env("COINGECKO_API_KEY", default="")
```

---

## 研究主题2: 币安合约列表获取

### 研究目标
确定如何从币安API获取所有USDT永续合约列表,提取基础代币symbol。

### 调研过程

#### 2.1 API端点选择

**币安Futures API**:
- 端点: `GET /fapi/v1/exchangeInfo`
- 返回: 所有永续合约的完整信息(symbol, status, baseAsset, quoteAsset等)

**python-binance集成**:
```python
from binance.client import Client

client = Client(api_key, api_secret)

# 获取所有Futures合约信息
exchange_info = client.futures_exchange_info()

# 过滤USDT永续合约
usdt_perpetuals = [
    symbol_info for symbol_info in exchange_info["symbols"]
    if symbol_info["quoteAsset"] == "USDT"
    and symbol_info["contractType"] == "PERPETUAL"
    and symbol_info["status"] == "TRADING"
]

# 提取symbol列表
symbols = [info["symbol"] for info in usdt_perpetuals]
# ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', ...]
```

#### 2.2 基础代币提取

**规则**:
- 币安symbol格式: `{baseAsset}{quoteAsset}`
- USDT永续: `BTCUSDT` → `BTC`
- 直接使用`exchangeInfo`中的`baseAsset`字段

**提取逻辑**:
```python
def extract_base_token(symbol_info):
    """从币安symbol信息中提取基础代币"""
    return symbol_info["baseAsset"]  # 直接从API返回中获取

# 或者,如果没有baseAsset字段,使用字符串操作
def extract_base_token_fallback(symbol):
    """备用方案: 移除USDT后缀"""
    if symbol.endswith("USDT"):
        return symbol[:-4]  # BTCUSDT → BTC
    return symbol
```

#### 2.3 过滤特殊合约

**需要过滤的合约类型**:
- ❌ 币本位合约(quoteAsset != "USDT")
- ❌ 季度合约(contractType != "PERPETUAL")
- ❌ 已下架合约(status != "TRADING")

**保留的合约类型**:
- ✅ USDT永续合约(quoteAsset="USDT", contractType="PERPETUAL", status="TRADING")

#### 2.4 同步频率

**决策**: 每日与数据更新任务一起执行
- 原因: 币安新上线合约频率较低(约1-2周1个)
- 实现: 在`update_market_data`命令开始前,先调用`sync_binance_contracts`

---

## 研究主题3: 数据更新策略

### 研究目标
确定数据更新频率、批量处理策略、定时任务实现方案。

### 调研过程

#### 3.1 更新频率决策

**候选方案对比**:

| 方案 | 优点 | 缺点 | 是否选择 |
|------|------|------|---------|
| 实时更新 | 数据最新 | API调用频繁,成本高,易被限流 | ❌ |
| 每小时更新 | 较新 | 市值/FDV变化不大,浪费资源 | ❌ |
| 每12小时更新 | 平衡 | 略显频繁 | 可选 |
| 每日1次更新 | 简单,成本低 | 数据略有延迟 | ✅ 推荐 |

**决策理由**:
- 市值/FDV是中长期指标,日内变化不大(<5%)
- 筛选系统本身每日运行,数据同步即可
- 避免不必要的API调用,降低限流风险

**实施细节**:
- 时间: 每日凌晨4:00 (UTC+8)
- 原因: 避开交易高峰,API响应更快

#### 3.2 批量处理策略

**API限制**:
- CoinGecko `/coins/markets`: 最多250个coin_id per request
- 限流: 50次/分钟

**批量方案**:
- 500个合约 → 2-3次API调用
- 批次间延迟60秒,总时间约2-3分钟

**并发策略**:
- ❌ 不使用多线程/多进程(会加剧限流)
- ✅ 串行处理,严格控制速率

**实现**:
```python
def update_all_market_data():
    # Step 1: 获取所有需要更新的映射关系
    mappings = TokenMapping.objects.filter(
        match_status__in=["auto_matched", "manual_confirmed"]
    )

    coin_ids = [m.coingecko_id for m in mappings]

    # Step 2: 分批调用CoinGecko API
    client = CoinGeckoClient()
    market_data_list = client.fetch_market_data(coin_ids, batch_size=250)

    # Step 3: 批量写入数据库
    for data in market_data_list:
        MarketData.objects.update_or_create(
            symbol=symbol_from_coingecko_id(data["id"]),
            defaults={
                "market_cap": data.get("market_cap"),
                "fully_diluted_valuation": data.get("fully_diluted_valuation"),
                "fetched_at": timezone.now()
            }
        )

    # Step 4: 记录更新日志
    UpdateLog.objects.create(
        batch_id=uuid.uuid4(),
        operation_type="data_fetch",
        status="success",
        executed_at=timezone.now()
    )
```

#### 3.3 定时任务实现

**候选方案对比**:

| 方案 | 优点 | 缺点 | 是否选择 |
|------|------|------|---------|
| Django Celery | 功能强大,支持复杂调度 | 需要Redis/RabbitMQ,引入新依赖 | ❌ |
| APScheduler | 轻量,Python内置 | 需要常驻进程,重启时任务丢失 | ❌ |
| Cron Job | 简单,系统级,可靠 | 灵活性稍低 | ✅ 推荐 |

**决策**: 使用Cron Job (与现有项目一致)
- 项目已有`update_market_data.sh`等定时脚本
- 生产环境使用systemd timer或cron

**Crontab配置**:
```bash
# /etc/cron.d/grid_trading_market_data
0 4 * * * user /path/to/project/scripts/cron_update_market_data.sh >> /var/log/market_data_update.log 2>&1
```

**脚本内容** (cron_update_market_data.sh):
```bash
#!/bin/bash
set -e

# 激活虚拟环境
source /path/to/venv/bin/activate

# 进入项目目录
cd /path/to/project

# 同步币安合约列表(检测新合约)
python manage.py sync_binance_contracts

# 更新市值/FDV数据
python manage.py update_market_data

# 发送通知(如果配置)
if [ $? -eq 0 ]; then
    echo "Market data updated successfully at $(date)"
else
    echo "Market data update failed at $(date)"
    # 可选: 发送告警通知
fi
```

#### 3.4 错误恢复机制

**失败场景**:
1. API调用失败(网络超时、限流、服务不可用)
2. 部分symbol更新失败
3. 数据库写入失败

**恢复策略**:
- **记录失败**: UpdateLog表记录失败的symbol和error_message
- **下次重试**: 下次更新时,优先处理失败的symbol
- **告警机制**: 连续3次失败同一symbol,发送告警

---

## 研究主题4: 前端展示方案

### 研究目标
确认如何在现有Django模板中添加市值/FDV列,实现排序和格式化。

### 调研过程

#### 4.1 数字格式化方案

**候选方案对比**:

| 方案 | 优点 | 缺点 | 是否选择 |
|------|------|------|---------|
| 前端JavaScript格式化 | 灵活,可动态切换单位 | 增加前端计算负担,500行数据卡顿 | ❌ |
| 后端Django模板过滤器 | 预处理,性能好 | 灵活性略低 | ✅ 推荐 |
| 后端视图中预格式化 | 最高性能 | 代码耦合 | 可选 |

**决策**: 后端Django模板过滤器 + 视图预处理结合

**实现**:
```python
# grid_trading/templatetags/market_filters.py
from django import template

register = template.Library()

@register.filter
def format_market_cap(value):
    """格式化市值/FDV: 123456789 → $123.46M"""
    if value is None:
        return "-"

    try:
        value = float(value)
    except (ValueError, TypeError):
        return "-"

    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    elif value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    elif value >= 1_000:
        return f"${value / 1_000:.2f}K"
    else:
        return f"${value:.2f}"
```

**模板使用**:
```django
{% load market_filters %}

<td>{{ contract.market_cap|format_market_cap }}</td>
<td>{{ contract.fdv|format_market_cap }}</td>
```

#### 4.2 排序实现

**现有机制**: `/screening/daily/` 页面已有前端排序机制(可能使用DataTables或自定义JS)

**决策**: 复用现有排序逻辑
- 在后端查询时LEFT JOIN MarketData表
- 前端排序时,将"-"(null值)排在最后

**后端查询优化**:
```python
# views.py
def get_daily_screening_detail(request, date_str):
    results = ScreeningResult.objects.filter(
        screening_date=date_str
    ).select_related('symbol')  # 预加载关联

    # LEFT JOIN市值数据
    results = results.annotate(
        market_cap=Subquery(
            MarketData.objects.filter(
                symbol=OuterRef('symbol')
            ).values('market_cap')[:1]
        ),
        fdv=Subquery(
            MarketData.objects.filter(
                symbol=OuterRef('symbol')
            ).values('fully_diluted_valuation')[:1]
        )
    )

    return results
```

**前端排序配置** (如果使用DataTables):
```javascript
$('#screening-table').DataTable({
    columns: [
        // ... 现有列
        { data: 'market_cap', type: 'num-fmt' },  // 自定义排序类型
        { data: 'fdv', type: 'num-fmt' }
    ],
    columnDefs: [
        {
            targets: [10, 11],  // 市值和FDV列
            render: function(data, type, row) {
                if (type === 'sort' || type === 'type') {
                    // 排序时,"-"转为-Infinity
                    return data === "-" ? -Infinity : parseFloat(data);
                }
                return data;
            }
        }
    ]
});
```

#### 4.3 Tooltip实现

**需求**: 鼠标悬停显示数据更新时间

**决策**: 使用Bootstrap Tooltip(项目已有)

**模板实现**:
```django
<td data-toggle="tooltip"
    title="更新时间: {{ contract.market_data.updated_at|date:'Y-m-d H:i' }}">
    {{ contract.market_cap|format_market_cap }}
</td>
```

**JavaScript初始化** (daily_screening.html):
```javascript
$(document).ready(function() {
    $('[data-toggle="tooltip"]').tooltip();
});
```

#### 4.4 页面性能优化

**潜在性能问题**:
- 额外的数据库JOIN查询
- 500+行数据的渲染

**优化措施**:
1. **数据库索引**: 为MarketData.symbol添加索引
2. **QuerySet优化**: 使用`select_related`和`annotate`减少查询次数
3. **分页机制**: 复用现有分页(每页50-100条)
4. **缓存**: 市值/FDV数据24小时缓存(可选)

**性能目标验证**:
- 页面加载增量<200ms ✅
- 排序响应<100ms ✅

---

## 技术选型总结

### 最终决策矩阵

| 技术点 | 选择方案 | 理由 |
|--------|---------|------|
| CoinGecko API端点 | `/coins/list` + `/coins/markets` | 批量查询效率高,数据完整 |
| API限流应对 | 批量(250)+延迟(60s)+指数退避 | 平衡速度与成本,避免封禁 |
| 同名消歧 | 交易量→排名→needs_review | 优先自动化,兼顾准确性 |
| 币安集成 | python-binance + futures_exchange_info | 复用现有,简单可靠 |
| 数据更新频率 | 每日1次(凌晨4点) | 需求匹配,成本最优 |
| 定时任务 | Cron Job | 与现有架构一致,简单可靠 |
| 数字格式化 | Django模板过滤器 | 性能优,代码清晰 |
| 排序实现 | 复用现有前端机制+后端注解 | 最小化改动,性能好 |

### 依赖库清单

**新增依赖**:
- `requests` (已是项目依赖)
- `tenacity` (用于API重试) - 需添加到requirements.txt

**现有依赖**:
- Django 4.2.8
- python-binance 1.0.19
- pandas 2.0+

**requirements.txt更新**:
```
tenacity>=8.2.0  # API重试库
```

### 风险评估与缓解

**高风险**:
1. ✅ CoinGecko API限流 - 缓解: 批量+延迟+重试
2. ✅ 同名代币错误映射 - 缓解: 优先级规则+人工审核

**中风险**:
3. ✅ 新合约未及时映射 - 缓解: 每日同步+告警
4. ✅ 页面性能下降 - 缓解: 数据库索引+QuerySet优化

**低风险**:
5. API服务不可用 - 缓解: 降级显示"-",不阻塞核心功能

---

## 下一步行动

### Phase 1任务
1. ✅ 创建`data-model.md` - 定义3个数据模型的详细字段
2. ✅ 创建`contracts/coingecko_api.md` - API调用规范
3. ✅ 创建`quickstart.md` - 初始化和配置指南

### 实施优先级
- **P0 (MVP)**: 数据模型 → 映射服务 → 数据更新服务 → 前端展示
- **P1 (增强)**: 定时任务 → Django Admin → 错误告警
- **P2 (优化)**: 性能优化 → 测试覆盖 → 文档完善

---

**Research Completed by**: Claude Code
**Date**: 2025-12-12
**Status**: All technical decisions resolved ✅
