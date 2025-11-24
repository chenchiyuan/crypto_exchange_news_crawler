# Research: VP-Squeeze算法支撑压力位计算服务

**Created**: 2025-11-24
**Status**: Complete

## 1. 币安现货K线API

### Decision
使用币安现货API (`api.binance.com`) 获取K线数据，采用直接HTTP请求方式。

### Rationale
- 项目已有`monitor/api_clients/binance.py`实现期货API调用模式
- 现货API无需认证即可获取公开K线数据
- requests库已是项目依赖

### API Specification

**Endpoint**: `GET https://api.binance.com/api/v3/klines`

**Parameters**:
| 参数 | 类型 | 必需 | 说明 |
|-----|------|-----|------|
| symbol | STRING | 是 | 交易对，如BTCUSDT |
| interval | STRING | 是 | K线周期：1m,3m,5m,15m,30m,1h,2h,4h,6h,8h,12h,1d,3d,1w,1M |
| limit | INT | 否 | 返回数量，默认500，最大1500 |

**Response** (数组格式):
```json
[
  [
    1499040000000,      // 开盘时间 (毫秒时间戳)
    "0.01634790",       // 开盘价
    "0.80000000",       // 最高价
    "0.01575800",       // 最低价
    "0.01577100",       // 收盘价
    "148976.11427815",  // 成交量
    1499644799999,      // 收盘时间
    "2434.19055334",    // 成交额
    308,                // 成交笔数
    "1756.87402397",    // 主动买入成交量
    "28.46694368",      // 主动买入成交额
    "0"                 // 忽略
  ]
]
```

### Alternatives Considered
1. **CCXT库**: 功能全面但依赖重，本功能只需K线数据
2. **WebSocket**: 适合实时数据，本功能为按需查询

---

## 2. 技术指标纯Python实现

### Decision
使用纯Python实现所有技术指标计算（SMA、EMA、STD、ATR、BB、KC、VP）。

### Rationale
- 用户明确要求无NumPy依赖
- 计算逻辑清晰，便于测试和调试
- 性能足够（100根K线的计算量极小）

### Implementation Approach

#### 2.1 基础计算函数

```python
def sma(prices: list[float], period: int) -> list[float]:
    """简单移动平均"""
    result = []
    for i in range(len(prices)):
        if i < period - 1:
            result.append(None)
        else:
            result.append(sum(prices[i-period+1:i+1]) / period)
    return result

def ema(prices: list[float], period: int) -> list[float]:
    """指数移动平均"""
    result = []
    multiplier = 2 / (period + 1)
    for i, price in enumerate(prices):
        if i == 0:
            result.append(price)
        else:
            result.append((price - result[-1]) * multiplier + result[-1])
    return result

def std(prices: list[float], period: int) -> list[float]:
    """标准差"""
    sma_values = sma(prices, period)
    result = []
    for i in range(len(prices)):
        if i < period - 1:
            result.append(None)
        else:
            window = prices[i-period+1:i+1]
            mean = sma_values[i]
            variance = sum((x - mean) ** 2 for x in window) / period
            result.append(variance ** 0.5)
    return result

def atr(high: list[float], low: list[float], close: list[float], period: int) -> list[float]:
    """平均真实波幅"""
    tr = []
    for i in range(len(high)):
        if i == 0:
            tr.append(high[i] - low[i])
        else:
            tr.append(max(
                high[i] - low[i],
                abs(high[i] - close[i-1]),
                abs(low[i] - close[i-1])
            ))
    return ema(tr, period)
```

#### 2.2 Bollinger Bands (Period=20, Multiplier=2.0)

```python
def bollinger_bands(close: list[float], period: int = 20, multiplier: float = 2.0):
    middle = sma(close, period)
    std_values = std(close, period)
    upper = [m + multiplier * s if m and s else None for m, s in zip(middle, std_values)]
    lower = [m - multiplier * s if m and s else None for m, s in zip(middle, std_values)]
    return {'upper': upper, 'middle': middle, 'lower': lower}
```

#### 2.3 Keltner Channels (EMA=20, ATR=10, Multiplier=1.5)

```python
def keltner_channels(high: list[float], low: list[float], close: list[float],
                     ema_period: int = 20, atr_period: int = 10, multiplier: float = 1.5):
    middle = ema(close, ema_period)
    atr_values = atr(high, low, close, atr_period)
    upper = [m + multiplier * a if m and a else None for m, a in zip(middle, atr_values)]
    lower = [m - multiplier * a if m and a else None for m, a in zip(middle, atr_values)]
    return {'upper': upper, 'middle': middle, 'lower': lower}
```

#### 2.4 Squeeze判定

```python
def detect_squeeze(bb: dict, kc: dict, consecutive_required: int = 3) -> dict:
    """检测Squeeze状态：BB收缩进入KC内部"""
    squeeze_signals = []
    for i in range(len(bb['upper'])):
        if bb['upper'][i] and kc['upper'][i]:
            is_squeeze = (bb['upper'][i] < kc['upper'][i] and
                         bb['lower'][i] > kc['lower'][i])
            squeeze_signals.append(is_squeeze)
        else:
            squeeze_signals.append(False)

    # 检查最近N根K线是否连续满足Squeeze条件
    recent = squeeze_signals[-consecutive_required:]
    is_active = len(recent) == consecutive_required and all(recent)
    consecutive_count = 0
    for s in reversed(squeeze_signals):
        if s:
            consecutive_count += 1
        else:
            break

    return {
        'active': is_active,
        'consecutive_bars': consecutive_count,
        'signals': squeeze_signals
    }
```

### Alternatives Considered
1. **NumPy**: 性能更好，但用户明确拒绝
2. **TA-Lib**: 功能全面但安装复杂，需要C编译
3. **pandas-ta**: 依赖pandas和numpy

---

## 3. Volume Profile计算

### Decision
基于价格比例（0.1%）创建价格桶，计算成交量分布。

### Rationale
- 自适应不同价格级别的币种
- 70%价值区域是Volume Profile标准定义
- 百分位数识别HVN/LVN更稳健

### Implementation Approach

```python
def volume_profile(klines: list[dict], resolution_pct: float = 0.001) -> dict:
    """
    计算Volume Profile

    Args:
        klines: K线数据列表，每个包含 high, low, close, volume
        resolution_pct: 价格分辨率百分比（0.001 = 0.1%）

    Returns:
        {
            'vpoc': float,      # 成交量重心价格
            'vah': float,       # 价值区域上限 (70%)
            'val': float,       # 价值区域下限 (70%)
            'hvn': list[dict],  # 高量节点列表
            'lvn': list[dict],  # 低量节点列表
            'profile': dict     # 完整的价格-成交量分布
        }
    """
    # 1. 确定价格范围和分辨率
    all_prices = []
    for k in klines:
        all_prices.extend([k['high'], k['low']])
    price_min, price_max = min(all_prices), max(all_prices)

    # 使用当前价格的0.1%作为分辨率
    current_price = klines[-1]['close']
    bucket_size = current_price * resolution_pct

    # 2. 创建价格桶
    buckets = {}
    bucket_start = price_min - (price_min % bucket_size)
    while bucket_start <= price_max:
        buckets[bucket_start] = 0.0
        bucket_start += bucket_size

    # 3. 分配成交量到价格桶
    for k in klines:
        # 将K线成交量均匀分配到其价格范围内的桶
        kline_range = k['high'] - k['low']
        if kline_range == 0:
            # 价格没有变化，全部成交量放入一个桶
            bucket_key = k['close'] - (k['close'] % bucket_size)
            if bucket_key in buckets:
                buckets[bucket_key] += k['volume']
        else:
            # 按价格范围比例分配
            for bucket_price in buckets:
                bucket_high = bucket_price + bucket_size
                overlap_low = max(bucket_price, k['low'])
                overlap_high = min(bucket_high, k['high'])
                if overlap_high > overlap_low:
                    overlap_ratio = (overlap_high - overlap_low) / kline_range
                    buckets[bucket_price] += k['volume'] * overlap_ratio

    # 4. 计算VPOC（最大成交量价格）
    vpoc_bucket = max(buckets, key=buckets.get)
    vpoc = vpoc_bucket + bucket_size / 2

    # 5. 计算价值区域（70%成交量区间）
    total_volume = sum(buckets.values())
    target_volume = total_volume * 0.70

    # 从VPOC向两侧扩展
    sorted_buckets = sorted(buckets.items(), key=lambda x: x[0])
    vpoc_idx = next(i for i, (p, _) in enumerate(sorted_buckets) if p == vpoc_bucket)

    included_volume = buckets[vpoc_bucket]
    val_idx, vah_idx = vpoc_idx, vpoc_idx

    while included_volume < target_volume:
        left_vol = sorted_buckets[val_idx - 1][1] if val_idx > 0 else 0
        right_vol = sorted_buckets[vah_idx + 1][1] if vah_idx < len(sorted_buckets) - 1 else 0

        if left_vol >= right_vol and val_idx > 0:
            val_idx -= 1
            included_volume += left_vol
        elif vah_idx < len(sorted_buckets) - 1:
            vah_idx += 1
            included_volume += right_vol
        else:
            break

    val = sorted_buckets[val_idx][0]
    vah = sorted_buckets[vah_idx][0] + bucket_size

    # 6. 识别HVN和LVN（百分位数方式）
    volumes = list(buckets.values())
    volumes_sorted = sorted(volumes)
    p80 = volumes_sorted[int(len(volumes_sorted) * 0.8)]
    p20 = volumes_sorted[int(len(volumes_sorted) * 0.2)]

    hvn = [{'price': p + bucket_size/2, 'volume': v}
           for p, v in buckets.items() if v >= p80]
    lvn = [{'price': p + bucket_size/2, 'volume': v}
           for p, v in buckets.items() if v <= p20 and v > 0]

    return {
        'vpoc': vpoc,
        'vah': vah,
        'val': val,
        'hvn': hvn,
        'lvn': lvn,
        'profile': buckets
    }
```

### Alternatives Considered
1. **固定价格分辨率**: 对不同价格币种适应性差
2. **按K线范围分辨率**: 每次计算结果不可比
3. **成交笔数加权**: 数据不够精细

---

## 4. Symbol映射表

### Decision
预设TOP 10主流币种映射，用户输入简写自动转换为币安交易对。

### Implementation

```python
SYMBOL_MAP = {
    # TOP 10 主流币
    'btc': 'BTCUSDT',
    'eth': 'ETHUSDT',
    'bnb': 'BNBUSDT',
    'sol': 'SOLUSDT',
    'xrp': 'XRPUSDT',
    'doge': 'DOGEUSDT',
    'ada': 'ADAUSDT',
    'avax': 'AVAXUSDT',
    'dot': 'DOTUSDT',
    'matic': 'MATICUSDT',
}

VALID_INTERVALS = [
    '1m', '3m', '5m', '15m', '30m',
    '1h', '2h', '4h', '6h', '8h', '12h',
    '1d', '3d', '1w', '1M'
]

SYMBOL_GROUPS = {
    'top10': ['btc', 'eth', 'bnb', 'sol', 'xrp', 'doge', 'ada', 'avax', 'dot', 'matic'],
}

def normalize_symbol(symbol: str) -> str:
    """将用户输入的symbol转换为币安交易对格式"""
    symbol_lower = symbol.lower().strip()
    if symbol_lower in SYMBOL_MAP:
        return SYMBOL_MAP[symbol_lower]
    # 如果已经是完整格式，直接返回大写
    if symbol.upper().endswith('USDT'):
        return symbol.upper()
    raise ValueError(f"Unknown symbol: {symbol}. Supported: {list(SYMBOL_MAP.keys())}")

def validate_interval(interval: str) -> str:
    """验证时间周期是否有效"""
    if interval not in VALID_INTERVALS:
        raise ValueError(f"Invalid interval: {interval}. Valid: {VALID_INTERVALS}")
    return interval
```

---

## 5. 输出格式设计

### Decision
默认人类可读文本，`--json`参数输出JSON格式。

### Text Output Format

```
═══════════════════════════════════════════════════════════════
VP-Squeeze Analysis: ETHUSDT (4h) | 2025-11-24 16:30 UTC
═══════════════════════════════════════════════════════════════

📊 Squeeze状态: ✓ 有效 (连续5根K线)
   可靠度: 高

───────────────────────────────────────────────────────────────
📍 关键价位
───────────────────────────────────────────────────────────────
   支撑位 (VAL):    $3,120.50
   压力位 (VAH):    $3,280.00
   成交量重心 (VPOC): $3,195.00

───────────────────────────────────────────────────────────────
📈 高量节点 (HVN) - 强支撑/阻力区
───────────────────────────────────────────────────────────────
   • $3,180.00 - $3,210.00

📉 低量节点 (LVN) - 价格快速穿越区
───────────────────────────────────────────────────────────────
   • $3,250.00 - $3,270.00

═══════════════════════════════════════════════════════════════
```

### JSON Output Format

```json
{
  "symbol": "ETHUSDT",
  "interval": "4h",
  "timestamp": "2025-11-24T16:30:00Z",
  "squeeze": {
    "active": true,
    "consecutive_bars": 5,
    "reliability": "high"
  },
  "levels": {
    "val": 3120.50,
    "vah": 3280.00,
    "vpoc": 3195.00
  },
  "hvn": [
    {"low": 3180.00, "high": 3210.00, "volume": 12500.5}
  ],
  "lvn": [
    {"low": 3250.00, "high": 3270.00, "volume": 1200.3}
  ],
  "metadata": {
    "klines_count": 100,
    "price_range": {"min": 3050.00, "max": 3350.00},
    "total_volume": 150000.0
  }
}
```

---

## 6. 错误处理策略

### Decision
API调用失败时抛出异常终止，提供清晰错误信息。

### Implementation

```python
class VPSqueezeError(Exception):
    """VP-Squeeze分析基础异常"""
    pass

class BinanceAPIError(VPSqueezeError):
    """币安API调用错误"""
    def __init__(self, message: str, status_code: int = None, response: str = None):
        self.status_code = status_code
        self.response = response
        super().__init__(message)

class InsufficientDataError(VPSqueezeError):
    """数据不足错误"""
    def __init__(self, required: int, actual: int):
        self.required = required
        self.actual = actual
        super().__init__(f"Insufficient data: required {required} klines, got {actual}")

class InvalidSymbolError(VPSqueezeError):
    """无效交易对错误"""
    pass

class InvalidIntervalError(VPSqueezeError):
    """无效时间周期错误"""
    pass
```

---

## 7. 价格精度处理

### Decision
动态精度：价格>100保留2位，10-100保留3位，<10保留4位。

### Implementation

```python
def format_price(price: float) -> str:
    """根据价格量级格式化显示"""
    if price >= 100:
        return f"{price:,.2f}"
    elif price >= 10:
        return f"{price:,.3f}"
    else:
        return f"{price:,.4f}"
```

---

## Summary

所有技术决策已确认，无NEEDS CLARIFICATION项：

| 领域 | 决策 |
|-----|------|
| K线数据源 | 币安现货API (api.binance.com) |
| 技术指标 | 纯Python实现 |
| BB参数 | Period=20, Multiplier=2.0 |
| KC参数 | EMA=20, ATR=10, Multiplier=1.5 |
| Squeeze判定 | 连续3根K线 |
| VP分辨率 | 价格的0.1% |
| HVN/LVN | 百分位数（前/后20%） |
| 输出格式 | 文本(默认) + JSON(--json) |
| 错误处理 | 异常终止 |
| 最小数据量 | 30根K线 |
