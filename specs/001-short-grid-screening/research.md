# Research: 做空网格标的量化筛选系统

**Date**: 2025-12-03
**Feature**: 001-short-grid-screening

## Executive Summary

基于项目现有技术栈研究,本特性可完全复用现有的币安API客户端和并行计算模式。主要技术挑战集中在赫斯特指数(Hurst Exponent)的R/S分析实现和500+标的的性能优化。

**关键决策**:
- **币安API客户端**: 复用 `monitor/api_clients/binance.py` 的并行请求模式
- **并行计算**: 采用项目已验证的 `ThreadPoolExecutor` 模式(3并发)
- **Hurst指数**: 引入 `scipy` 库实现R/S分析(项目缺失,需新增依赖)
- **技术指标计算**: 使用 NumPy/Pandas 手动实现(避免引入TA-Lib)

## Research Findings

### 1. 赫斯特指数 (Hurst Exponent) R/S分析算法

#### 决策: 使用scipy实现R/S分析

**理由**:
- 项目当前**没有**Hurst指数实现
- scipy是轻量级选择,已被推荐为依赖(spec.md line 173)
- R/S分析的数学原理适合手工实现,避免引入专门的hurst库

#### 算法原理

重标极差分析(Rescaled Range Analysis, R/S):

```
步骤1: 将时间序列Y分成n个等长子序列
步骤2: 对每个子序列k:
   a) 计算均值 mean_k
   b) 计算累积偏差 X(t,k) = Σ(Y_i - mean_k)
   c) 计算极差 R_k = max(X) - min(X)
   d) 计算标准差 S_k
   e) 计算重标极差 (R/S)_k = R_k / S_k
步骤3: 对所有n,计算平均 E[R/S_n]
步骤4: 线性回归 log(E[R/S]) vs log(n),斜率即为H
```

**Hurst指数解释**:
- H < 0.5: 反持久性(均值回归),理想做空网格标的
- H = 0.5: 随机游走
- H > 0.5: 持久性(趋势延续),不适合网格

#### Python实现

```python
import numpy as np
from scipy.stats import linregress

def calculate_hurst_exponent(prices: np.ndarray, window_sizes: list = None) -> float:
    """
    计算赫斯特指数

    Args:
        prices: 价格序列(至少300个数据点)
        window_sizes: 窗口大小列表,默认[10, 20, 30, 50, 100]

    Returns:
        Hurst指数 (0 ~ 1)
    """
    if window_sizes is None:
        window_sizes = [10, 20, 30, 50, 100]

    N = len(prices)
    rs_values = []

    for window in window_sizes:
        if window >= N:
            continue

        # 将序列分成多个窗口
        num_windows = N // window
        rs_window = []

        for i in range(num_windows):
            subset = prices[i * window:(i + 1) * window]

            # 计算均值
            mean = np.mean(subset)

            # 计算累积偏差
            deviations = subset - mean
            cumulative_deviations = np.cumsum(deviations)

            # 计算极差
            R = np.max(cumulative_deviations) - np.min(cumulative_deviations)

            # 计算标准差
            S = np.std(subset, ddof=1)

            # 避免除零
            if S > 0:
                rs_window.append(R / S)

        if rs_window:
            rs_values.append((window, np.mean(rs_window)))

    # 线性回归 log(R/S) vs log(n)
    if len(rs_values) < 2:
        return 0.5  # 默认随机游走

    log_n = np.log([w for w, _ in rs_values])
    log_rs = np.log([rs for _, rs in rs_values])

    slope, intercept, r_value, p_value, std_err = linregress(log_n, log_rs)

    return slope
```

#### 性能预估

- **单次计算**: ~5-10ms (300根K线,5个窗口)
- **500标的并行**: 使用3线程池 → 预计1-2秒
- **内存占用**: 每个标的~50KB (300 × float64 × 8 bytes)

#### 替代方案(如性能不足)

简化算法:单窗口R/S计算,窗口=100:
```python
def simple_hurst(prices: np.ndarray, window: int = 100) -> float:
    """快速近似Hurst指数,窗口固定"""
    # 实现仅一个窗口的R/S计算
    # 性能提升~5倍,精度损失~10%
```

---

### 2. 币安Futures API最佳实践

#### 决策: 复用monitor/api_clients/binance.py的并行模式

**可复用代码**: `/Users/chenchiyuan/projects/crypto_exchange_news_crawler/monitor/api_clients/binance.py`

#### 现有实现分析

**已验证的并行请求模式** (line 330-359):
```python
with ThreadPoolExecutor(max_workers=3) as executor:
    future_ticker = executor.submit(self._fetch_24h_ticker)
    future_premium = executor.submit(self._fetch_premium_index)
    future_funding_info = executor.submit(self._fetch_funding_info)

    ticker_24h_data = future_ticker.result()
    premium_data = future_premium.result()
    funding_info_data = future_funding_info.result()
```

**现有错误处理**:
- `@retry` 装饰器: 最多3次重试,指数退避(line 33-37)
- `@sleep_and_retry + @limits`: 速率限制(line 38-39)
- 请求超时: `REQUEST_TIMEOUT` 配置(line 61)

#### API速率限制

根据币安官方文档:
- **/fapi/v1/exchangeInfo**: 权重10, 1200/分钟
- **/fapi/v1/ticker/24hr**: 权重40(全市场), 1200/分钟
- **/fapi/v1/klines**: 权重1(单标的), 1200/分钟
- **/fapi/v1/openInterest**: 权重1(单标的)
- **/fapi/v1/fundingRate**: 权重1(全市场)

#### 批量请求策略

**推荐方案**: 串行获取全市场数据 + 并行计算指标

```
阶段1: 全市场数据获取(串行)
  ├─ exchangeInfo (10权重)
  ├─ ticker/24hr (40权重)
  ├─ fundingRate (1权重) ← 全市场一次请求
  └─ 500个标的 × openInterest (500权重)
     └─ 分100批,每批5个,并发3 → 预计17秒

阶段2: 指标计算(并行)
  └─ 500个标的 × 三维指标
     └─ ThreadPoolExecutor(max_workers=4) → 预计15秒
```

#### K线数据获取优化

**关键发现**: `vp_squeeze/services/binance_kline_service.py` 已有Futures K线获取逻辑(需改造)

**改造方案**:
- 基础URL: `https://fapi.binance.com` (Futures API)
- 端点: `/fapi/v1/klines`
- 并发策略: 每批20个标的,3并发 → 预计25秒(500标的×300根K线)

**TakerBuyVolume可用性**: 币安K线接口字段[7] = takerBuyBaseAssetVolume ✅

#### 全市场扫描时间预估

```
exchangeInfo:        1秒
ticker/24hr:         1秒
fundingRate:         1秒
openInterest(500):  17秒
klines(500):        25秒
指标计算:            15秒
----------------------
总计:               60秒 ✅ 满足SC-001要求
```

#### 错误处理策略

**429限流**:
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    retry=retry_if_exception_type(requests.exceptions.HTTPError)
)
```

**数据缺失**:
- K线不足300根: 跳过该标的,记录WARNING
- TakerBuyVolume缺失: 降级为简化CVD计算

---

### 3. 并行计算性能优化方案

#### 决策: 采用ThreadPoolExecutor(项目验证模式)

**理由**:
- 项目已在 `monitor/api_clients/binance.py` (line 343)使用ThreadPoolExecutor
- I/O密集型任务(API请求)适合多线程
- 避免引入新并发模型(保持一致性)

#### 现有并行计算模式

**已验证的实现** (monitor/api_clients/binance.py:330-359):
- 并发度: `max_workers=3`
- 应用场景: 并行请求3个API端点
- 内存管理: 无需特殊处理(Django ORM管理)

#### 性能目标分解

**目标**: 60秒完成500+标的筛选(SC-001)

**分解**:
```
1. API数据获取:         45秒 (I/O bound)
   ├─ 基础数据(全市场):  3秒
   ├─ 持仓量(500请求): 17秒
   └─ K线(500×300):    25秒

2. 指标计算:            15秒 (CPU bound)
   ├─ NATR计算:        2秒 (NumPy向量化)
   ├─ KER计算:         1秒 (NumPy向量化)
   ├─ Hurst指数:       5秒 (scipy线性回归)
   ├─ 线性回归(趋势):  2秒 (numpy.polyfit)
   ├─ CVD计算:         3秒 (NumPy累积和)
   └─ 评分排序:        2秒
```

#### 并行方案设计

**方案1: 两阶段并行**(推荐)

```python
from concurrent.futures import ThreadPoolExecutor
import numpy as np

def screen_short_grid_targets(symbols: List[str]) -> List[ScreeningResult]:
    """
    筛选做空网格标的
    """
    # 阶段1: 并行获取数据
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {
            executor.submit(fetch_symbol_data, symbol): symbol
            for symbol in symbols
        }

        symbol_data_map = {}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                data = future.result()
                symbol_data_map[symbol] = data
            except Exception as e:
                logger.warning(f"获取{symbol}数据失败: {e}")

    # 阶段2: 并行计算指标
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(
            calculate_indicators,
            symbol_data_map.values()
        ))

    # 排序和筛选
    return rank_and_filter(results)
```

**并发度选择**:
- 数据获取: `max_workers=20` (I/O密集,受API限流约束)
- 指标计算: `max_workers=4` (CPU密集,受CPU核心数约束)

**方案2: asyncio(备选,如时间不足)**

仅在ThreadPoolExecutor无法达到60秒目标时考虑。

#### 内存管理

**内存占用预估**:
```
500标的 × 300根K线 × 8字段 × 8字节(float64) = 9.6MB
500标的 × 指标结果(~1KB) = 0.5MB
临时计算缓存: ~50MB
-------------------------------------------
总计: ~60MB (远低于2GB限制 ✅)
```

**优化策略**:
- 使用NumPy向量化避免Python循环
- 及时释放中间结果(`del` 临时变量)
- 不持久化到数据库(内存模型 spec.md line 142)

#### 示例代码(核心并行逻辑)

```python
def calculate_indicators(symbol_data: dict) -> dict:
    """
    计算单个标的的三维指标(纯计算,无I/O)
    """
    klines = symbol_data['klines']
    close_prices = np.array([k['close'] for k in klines])

    # 波动率维度
    natr = calculate_natr(klines)
    ker = calculate_ker(close_prices, window=10)

    # 趋势维度
    norm_slope, r_squared = calculate_trend_metrics(close_prices)
    hurst = calculate_hurst_exponent(close_prices)

    # 微观结构维度
    ovr = symbol_data['open_interest'] / symbol_data['volume_24h']
    funding_rate = symbol_data['funding_rate']
    cvd_divergence = detect_cvd_divergence(klines)

    return {
        'symbol': symbol_data['symbol'],
        'natr': natr,
        'ker': ker,
        'hurst': hurst,
        'norm_slope': norm_slope,
        'r_squared': r_squared,
        'ovr': ovr,
        'funding_rate': funding_rate,
        'cvd_divergence': cvd_divergence
    }
```

---

## Dependencies Summary

### 新增依赖

| 库 | 用途 | 安装 | 理由 |
|----|------|------|------|
| **scipy** | Hurst指数R/S分析(linregress) | `conda install scipy` | spec.md推荐(line 173) |
| **numpy** | 数值计算(已含于scipy依赖) | 跟随scipy | 必需 |
| **pandas** | DataFrame操作(已含于scipy依赖) | 跟随scipy | 必需 |

### 无需新增

- **币安SDK**: 直接使用requests(已有)
- **TA-Lib**: 手动实现ATR/KER(避免编译问题)
- **multiprocessing**: 使用ThreadPoolExecutor(已有)

### environment.yml更新

```yaml
dependencies:
  # ... 现有依赖 ...
  - scipy>=1.11.0  # 新增: Hurst指数R/S分析
  - numpy>=1.24.0  # scipy依赖,显式声明
  - pandas>=2.0.0  # scipy依赖,显式声明
```

---

## Alternatives Considered

### 替代方案1: 使用TA-Lib计算ATR

**拒绝理由**:
- TA-Lib需要C编译,跨平台兼容性差
- ATR公式简单,NumPy手动实现仅5行代码
- 项目已有VP-Squeeze手动计算先例

### 替代方案2: 使用专门的hurst库

**拒绝理由**:
- 额外依赖(hurst库维护不活跃)
- scipy的linregress足够实现R/S分析
- 保持依赖最小化原则

### 替代方案3: asyncio异步并发

**拒绝理由**:
- 项目无asyncio先例,引入新范式
- ThreadPoolExecutor已验证有效
- 性能提升不明显(I/O瓶颈在API限流)

---

## Risk Mitigation

### 风险1: API限流导致超时

**缓解策略**:
- 分批请求,控制并发度(max_workers=20)
- 使用tenacity自动重试(已有依赖)
- 降级处理:部分标的失败不影响整体

### 风险2: Hurst指数计算耗时过长

**缓解策略**:
- 简化窗口数量(5个窗口 → 3个)
- 使用NumPy向量化优化
- 极端情况:降级为单窗口快速算法

### 风险3: 内存溢出

**缓解策略**:
- 流式处理:分批加载K线数据
- 及时释放中间结果
- 监控内存占用(预估仅60MB,安全)

---

## Implementation Recommendations

### 优先级1: 复用现有代码

- 直接复制 `monitor/api_clients/binance.py` 的请求模式
- 参考 `vp_squeeze/services/binance_kline_service.py` 的K线获取逻辑

### 优先级2: 最小化依赖

- 仅引入scipy(必需)
- 手动实现ATR/KER(避免TA-Lib)

### 优先级3: 性能优化

- 使用NumPy向量化(不写Python for循环)
- ThreadPoolExecutor并行(复用项目模式)
- 及时释放大对象(避免内存泄漏)

### 开发顺序

1. **Week 1**: 币安API客户端改造(Futures端点)
2. **Week 1**: 技术指标计算模块(NATR/KER/Hurst)
3. **Week 2**: 评分模型实现(GSS公式)
4. **Week 2**: Django Management Command封装
5. **Week 3**: 性能优化与测试

---

## Conclusion

通过复用项目现有的币安API客户端和ThreadPoolExecutor并行模式,结合新增scipy库实现Hurst指数,可在**60秒内完成500+标的的三维筛选**,满足所有性能要求。

**关键成功因素**:
✅ 复用验证过的代码模式
✅ 最小化新依赖(仅scipy)
✅ NumPy向量化优化性能
✅ 合理的并发度设计(I/O:20, CPU:4)
