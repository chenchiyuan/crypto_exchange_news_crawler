# Data Model: 做空网格标的量化筛选系统

**Feature**: 001-short-grid-screening
**Date**: 2025-12-03
**Type**: 内存模型 (In-Memory Models, 无数据库持久化)

## Overview

本特性采用**纯内存数据模型**,所有数据在命令执行过程中存储在内存中,最终通过终端格式化输出展示结果,不涉及数据库持久化。

数据模型使用Python `dataclass` 定义,便于类型检查和IDE支持,同时保持轻量级。

---

## Entity Definitions

### 1. MarketSymbol (市场标的)

**用途**: 代表币安永续合约的基础信息

**属性**:

| 字段 | 类型 | 必需 | 说明 | 示例 |
|------|------|------|------|------|
| `symbol` | str | ✅ | 交易对代码 | "BTCUSDT" |
| `exchange` | str | ✅ | 交易所 | "binance" |
| `contract_type` | str | ✅ | 合约类型 | "perpetual" |
| `listing_date` | datetime | ✅ | 上市时间 | 2020-09-10 |
| `current_price` | Decimal | ✅ | 当前标记价格 | 44000.50 |
| `volume_24h` | Decimal | ✅ | 24小时成交量(USDT) | 987654321.00 |
| `open_interest` | Decimal | ✅ | 持仓量(张) | 1234567890.00 |
| `funding_rate` | Decimal | ✅ | 当前资金费率 | 0.0001 (0.01%) |
| `funding_interval_hours` | int | ✅ | 资金费率结算间隔(小时) | 8 |
| `next_funding_time` | datetime | ✅ | 下次资金费率结算时间 | 2025-12-03 16:00:00 |
| `market_cap_rank` | int | ❌ | 市值排名 | 25 (可选,用于FR-027.1) |

**数据源**: 币安Futures API
- `exchangeInfo`: symbol, listing_date
- `ticker/24hr`: volume_24h
- `premiumIndex`: current_price, funding_rate, next_funding_time
- `openInterest`: open_interest

**验证规则** (FR-002, FR-003):
- `volume_24h` > 50,000,000 USDT
- `listing_date` < (today - 30 days)

**Python实现**:
```python
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

@dataclass
class MarketSymbol:
    symbol: str
    exchange: str
    contract_type: str
    listing_date: datetime
    current_price: Decimal
    volume_24h: Decimal
    open_interest: Decimal
    funding_rate: Decimal
    funding_interval_hours: int
    next_funding_time: datetime

    def passes_initial_filter(self, min_volume: Decimal, min_days: int) -> bool:
        """
        初筛验证(FR-002, FR-003)

        Args:
            min_volume: 最小流动性阈值(USDT)
            min_days: 最小上市天数

        Returns:
            是否通过初筛
        """
        from datetime import timedelta
        from django.utils import timezone

        # 流动性检查
        if self.volume_24h < min_volume:
            return False

        # 上市时间检查
        cutoff_date = timezone.now() - timedelta(days=min_days)
        if self.listing_date > cutoff_date:
            return False

        return True
```

---

### 2. VolatilityMetrics (波动率指标)

**用途**: 第一维度筛选 - 波动率特征

**属性**:

| 字段 | 类型 | 必需 | 说明 | 公式 / 示例 |
|------|------|------|------|------------|
| `symbol` | str | ✅ | 关联标的 | "BTCUSDT" |
| `natr` | float | ✅ | 归一化ATR (%) | ATR(14) / Close × 100 = 2.5% |
| `ker` | float | ✅ | 考夫曼效率比 | Direction / Volatility = 0.25 |
| `vdr` | float | ✅ | 波动率-位移比 | CIV / Displacement = 8.5 |
| `natr_percentile` | float | ✅ | NATR百分位排名(0-1) | 0.85 (前15%) |
| `inv_ker_percentile` | float | ✅ | (1-KER)百分位排名(0-1) | 0.75 |

**计算方法**:

**NATR** (FR-005):
```python
def calculate_natr(klines: List[dict], period: int = 14) -> float:
    """
    计算归一化ATR

    TR = max(H - L, |H - C_prev|, |L - C_prev|)
    ATR(14) = EMA(TR, period=14)
    NATR = ATR(14) / Close × 100
    """
    import numpy as np

    highs = np.array([k['high'] for k in klines])
    lows = np.array([k['low'] for k in klines])
    closes = np.array([k['close'] for k in klines])

    # 计算真实波幅TR
    hl = highs - lows
    hc = np.abs(highs[1:] - closes[:-1])
    lc = np.abs(lows[1:] - closes[:-1])

    tr = np.maximum(hl[1:], np.maximum(hc, lc))

    # EMA计算ATR
    alpha = 2 / (period + 1)
    atr = np.zeros_like(tr)
    atr[0] = tr[0]
    for i in range(1, len(tr)):
        atr[i] = alpha * tr[i] + (1 - alpha) * atr[i - 1]

    # 归一化
    natr = (atr[-1] / closes[-1]) * 100
    return natr
```

**KER** (FR-006):
```python
def calculate_ker(prices: np.ndarray, window: int = 10) -> float:
    """
    计算考夫曼效率比

    Direction = |Close_t - Close_{t-N}|
    Volatility = Σ|Close_{t-i} - Close_{t-i-1}|
    KER = Direction / Volatility
    """
    direction = abs(prices[-1] - prices[-window])
    volatility = np.sum(np.abs(np.diff(prices[-window:])))

    if volatility == 0:
        return 0.0

    return direction / volatility
```

**VDR** (FR-010.1):
```python
def calculate_vdr(klines_1m: List[dict]) -> float:
    """
    计算波动率-位移比

    Args:
        klines_1m: 240根1分钟K线数据

    Returns:
        VDR值
    """
    import numpy as np

    # 计算累积日内波动率（CIV）
    civ = 0.0
    for k in klines_1m:
        close = float(k['close'])
        open_price = float(k['open'])
        civ += abs(close - open_price) / open_price

    # 计算净位移
    close_final = float(klines_1m[-1]['close'])
    close_initial = float(klines_1m[0]['close'])
    displacement = abs(close_final - close_initial) / close_initial

    # 避免除零
    if displacement == 0:
        return float('inf')  # 完全横盘，VDR无穷大

    return civ / displacement
```

**筛选条件** (FR-007, FR-008, FR-009, FR-010.1):
- NATR ≥ 前20%分位
- KER < 0.3
- 1% ≤ NATR ≤ 10%

**Python实现**:
```python
@dataclass
class VolatilityMetrics:
    symbol: str
    natr: float
    ker: float
    vdr: float  # 新增
    natr_percentile: float
    inv_ker_percentile: float

    def passes_filter(self) -> bool:
        """
        波动率筛选(FR-007, FR-008, FR-009)
        """
        # NATR范围检查
        if not (1.0 <= self.natr <= 10.0):
            return False

        # KER效率检查
        if self.ker >= 0.3:
            return False

        # NATR分位数检查(前20%)
        if self.natr_percentile < 0.80:
            return False

        return True

    @property
    def warning_flags(self) -> List[str]:
        """
        生成警告标记和优势标记(FR-032)
        """
        flags = []
        if self.natr > 10.0:
            flags.append("⚠️ 极端波动")
        if self.natr < 1.0:
            flags.append("⚠️ 静默期")
        if self.vdr > 10.0:
            flags.append("✓ 高VDR - 完美震荡")
        return flags
```

---

### 3. TrendMetrics (趋势指标)

**用途**: 第二维度筛选 - 趋势特征(负面滤网)

**属性**:

| 字段 | 类型 | 必需 | 说明 | 公式 / 示例 |
|------|------|------|------|------------|
| `symbol` | str | ✅ | 关联标的 | "BTCUSDT" |
| `norm_slope` | float | ✅ | 标准化斜率 | (slope / Close_t) × 10000 = 15.5 |
| `r_squared` | float | ✅ | 线性拟合优度 | 0.75 |
| `hurst_exponent` | float | ✅ | 赫斯特指数 | 0.45 (均值回归) |
| `z_score` | float | ✅ | 价格Z-Score | (Close - MA_20) / StdDev_20 = 2.3 |
| `is_strong_uptrend` | bool | ✅ | 强上升趋势标记 | True (触发否决) |

**计算方法**:

**线性回归** (FR-011):
```python
def calculate_trend_metrics(prices: np.ndarray) -> tuple:
    """
    计算趋势指标

    Returns:
        (norm_slope, r_squared)
    """
    from scipy.stats import linregress

    x = np.arange(len(prices))
    slope, intercept, r_value, p_value, std_err = linregress(x, prices)

    # 标准化斜率
    norm_slope = (slope / prices[-1]) * 10000

    # 判定系数
    r_squared = r_value ** 2

    return norm_slope, r_squared
```

**赫斯特指数** (FR-012, 详见research.md):
```python
def calculate_hurst_exponent(prices: np.ndarray) -> float:
    """
    R/S分析计算Hurst指数

    详细实现见research.md
    """
    # ... (研究文档中的完整实现)
    pass
```

**Z-Score** (FR-015.1):
```python
def calculate_z_score(prices: np.ndarray, window: int = 20) -> float:
    """
    计算价格Z-Score（价格偏离度）

    Args:
        prices: 收盘价序列
        window: 移动平均窗口期（默认20）

    Returns:
        Z-Score值
    """
    import numpy as np

    # 计算简单移动平均
    ma = np.mean(prices[-window:])

    # 计算标准差
    std_dev = np.std(prices[-window:], ddof=1)

    # 当前价格
    current_price = prices[-1]

    # 避免除零
    if std_dev == 0:
        return 0.0

    # Z-Score公式
    z_score = (current_price - ma) / std_dev

    return z_score
```

**筛选条件** (FR-013, FR-014, FR-015, FR-015.2):
- H < 0.5 (反持久性)
- NormSlope > 阈值 且 R² > 0.8 → GSS归零(否决)
- NormSlope ≈ 0 优选

**Python实现**:
```python
@dataclass
class TrendMetrics:
    symbol: str
    norm_slope: float
    r_squared: float
    hurst_exponent: float
    z_score: float  # 新增
    is_strong_uptrend: bool

    def passes_filter(self) -> bool:
        """
        趋势筛选(FR-013)
        """
        if self.hurst_exponent >= 0.5:
            return False
        return True

    def calculate_trend_score(self, norm_slope_threshold: float = 50.0, ker: float = 0.0) -> float:
        """
        计算趋势评分I_Trend (FR-024)

        Args:
            norm_slope_threshold: 强趋势阈值
            ker: 考夫曼效率比（用于Z-Score加分判断）

        Returns:
            趋势得分(0-1)
        """
        # 否决机制(FR-014)
        if self.norm_slope > norm_slope_threshold and self.r_squared > 0.8:
            return 0.0

        # 水平震荡优选(FR-015)
        if abs(self.norm_slope) < 5.0:
            base_score = 1.0
        else:
            # 斜率惩罚
            base_score = max(0.0, 1.0 - abs(self.norm_slope) / 100.0)

        # Hurst加分(FR-024)
        if self.hurst_exponent < 0.5:
            hurst_bonus = (0.5 - self.hurst_exponent) * 0.5
        else:
            hurst_bonus = 0.0

        # Z-Score假突破加分(FR-024, FR-015.2)
        z_score_bonus = 0.0
        if self.z_score > 2.0 and ker < 0.3:
            z_score_bonus = 0.2  # 假突破优势位置

        return min(1.0, base_score + hurst_bonus + z_score_bonus)

    @property
    def warning_flags(self) -> List[str]:
        """
        生成优势标记(FR-032)
        """
        flags = []
        if self.z_score > 2.0:
            flags.append("✓ 假突破优势")
        return flags
```

---

### 4. MicrostructureMetrics (微观结构指标)

**用途**: 第三维度筛选 - 资金/持仓特征

**属性**:

| 字段 | 类型 | 必需 | 说明 | 公式 / 示例 |
|------|------|------|------|------------|
| `symbol` | str | ✅ | 关联标的 | "BTCUSDT" |
| `ovr` | float | ✅ | 持仓量/成交量比率 | OI / 24h_Volume = 1.2 |
| `funding_rate` | Decimal | ✅ | 资金费率(%) | 0.0100 (1%) |
| `annual_funding_rate` | float | ✅ | 年化资金费率(%) | 10.95% |
| `cvd` | float | ✅ | 累积成交量增量 | 1234567.89 |
| `cvd_roc` | float | ✅ | CVD变化率(%) | 35.5% (5周期变化率) |
| `has_cvd_divergence` | bool | ✅ | CVD背离检测 | True (熊市背离) |
| `cvd_divergence_type` | str | ❌ | 背离类型 | "bearish" / None |

**计算方法**:

**OVR** (FR-016):
```python
def calculate_ovr(open_interest: Decimal, volume_24h: Decimal) -> float:
    """
    持仓量/成交量比率
    """
    if volume_24h == 0:
        return 0.0
    return float(open_interest / volume_24h)
```

**CVD背离** (FR-020, FR-021):
```python
def calculate_cvd_divergence(klines: List[dict]) -> tuple:
    """
    计算CVD并检测背离

    Returns:
        (cvd_value, has_divergence)
    """
    import numpy as np

    # 计算Delta
    taker_buy_volume = np.array([k['taker_buy_volume'] for k in klines])
    total_volume = np.array([k['volume'] for k in klines])
    delta = taker_buy_volume - (total_volume - taker_buy_volume)

    # 累积CVD
    cvd = np.cumsum(delta)

    # 检测熊市背离(FR-021)
    prices = np.array([k['close'] for k in klines])
    window = 20

    price_high_idx = np.argmax(prices[-window:])
    cvd_high_idx = np.argmax(cvd[-window:])

    # 价格新高但CVD未创新高
    has_divergence = (price_high_idx == window - 1) and (cvd_high_idx < window - 1)

    return cvd[-1], has_divergence
```

**CVD变化率 (CVD_ROC)** (FR-021.1):
```python
def calculate_cvd_roc(cvd_series: np.ndarray, period: int = 5) -> float:
    """
    计算CVD变化率（Rate of Change）

    Args:
        cvd_series: CVD时间序列
        period: 变化率周期（默认5）

    Returns:
        CVD_ROC百分比
    """
    if len(cvd_series) < period + 1:
        return 0.0

    cvd_current = cvd_series[-1]
    cvd_past = cvd_series[-period - 1]

    # 避免除零
    if abs(cvd_past) < 1e-9:
        return 0.0

    cvd_roc = (cvd_current - cvd_past) / abs(cvd_past) * 100

    return cvd_roc
```

**筛选条件** (FR-018, FR-019, FR-021.1):
- Funding Rate > 0.01% (正费率)
- OVR ≤ 2.0 (非过度拥挤)
- Funding Rate 0.01% - 0.1% (温和正费率优选)

**Python实现**:
```python
@dataclass
class MicrostructureMetrics:
    symbol: str
    ovr: float
    funding_rate: Decimal
    annual_funding_rate: float
    cvd: float
    cvd_roc: float  # 新增
    has_cvd_divergence: bool

    def passes_filter(self) -> bool:
        """
        微观结构筛选(FR-018, FR-019)
        """
        # 正资金费率检查
        if self.funding_rate <= Decimal('0.0001'):  # 0.01%
            return False

        # OVR检查
        if self.ovr > 2.0:
            return False

        return True

    def calculate_micro_score(self, vdr: float = 0.0) -> float:
        """
        计算微观结构评分I_Micro (FR-025)

        Args:
            vdr: 波动率-位移比（用于VDR加分判断）

        Returns:
            微观结构得分(0-1)
        """
        score = 0.5  # 基础分

        # CVD背离加分
        if self.has_cvd_divergence:
            score += 0.3

        # 温和正费率加分(0.01% - 0.1%)
        funding_pct = float(self.funding_rate) * 100
        if 0.01 <= funding_pct <= 0.1:
            score += 0.2
        elif funding_pct > 0.1:
            # 高费率扣分(逼空风险)
            score -= 0.2

        # 高OVR扣分
        if self.ovr > 1.5:
            score -= 0.2

        # VDR加分 (FR-025)
        if vdr > 5.0:
            score += 0.2

        # CVD_ROC异常扣分 (FR-025)
        if self.cvd_roc > 50.0:
            score -= 0.3

        return max(0.0, min(1.0, score))

    @property
    def warning_flags(self) -> List[str]:
        """
        生成警告标记(FR-032)
        """
        flags = []
        if self.ovr > 2.0:
            flags.append("⚠️ 高杠杆拥挤")
        if float(self.funding_rate) * 100 > 0.1:
            flags.append("⚠️ 逼空风险")
        if self.cvd_roc > 50.0:
            flags.append("⚠️ CVD异常买盘")
        return flags
```

---

### 5. ScreeningResult (筛选结果)

**用途**: 最终输出的筛选结果,整合三维指标和GSS评分

**属性**:

| 字段 | 类型 | 必需 | 说明 | 示例 |
|------|------|------|------|------|
| `rank` | int | ✅ | 排名 | 1 |
| `symbol` | str | ✅ | 标的代码 | "BTCUSDT" |
| `current_price` | Decimal | ✅ | 当前价格 | 44000.50 |
| `volatility` | VolatilityMetrics | ✅ | 波动率指标 | (对象) |
| `trend` | TrendMetrics | ✅ | 趋势指标 | (对象) |
| `microstructure` | MicrostructureMetrics | ✅ | 微观结构指标 | (对象) |
| `gss_score` | float | ✅ | GSS评分(0-1) | 0.8523 |
| `grid_upper_limit` | Decimal | ✅ | 推荐网格上限 | 46000.00 |
| `grid_lower_limit` | Decimal | ✅ | 推荐网格下限 | 41000.00 |
| `grid_count` | int | ✅ | 推荐格数 | 15 |

**GSS评分公式** (FR-022, FR-023):
```
GSS = w₁·Rank(NATR) + w₂·Rank(1-KER) + w₃·I_Trend + w₄·I_Micro

默认权重:
w₁ = 0.2 (NATR排名)
w₂ = 0.2 ((1-KER)排名)
w₃ = 0.3 (趋势评分)
w₄ = 0.3 (微观结构评分)
```

**网格参数计算** (FR-030):
```python
def calculate_grid_parameters(
    current_price: Decimal,
    atr_daily: float,
    atr_hourly: float
) -> tuple:
    """
    计算推荐网格参数

    Upper Limit = Current Price + 2 × ATR_daily
    Lower Limit = Current Price - 3 × ATR_daily
    Grid Count = (Upper - Lower) / (0.5 × ATR_hourly)

    Returns:
        (upper_limit, lower_limit, grid_count)
    """
    upper = current_price + Decimal(str(2 * atr_daily))
    lower = current_price - Decimal(str(3 * atr_daily))
    grid_step = 0.5 * atr_hourly
    grid_count = int((float(upper - lower) / grid_step)) + 1

    return upper, lower, grid_count
```

**Python实现**:
```python
@dataclass
class ScreeningResult:
    rank: int
    symbol: str
    current_price: Decimal
    volatility: VolatilityMetrics
    trend: TrendMetrics
    microstructure: MicrostructureMetrics
    gss_score: float
    grid_upper_limit: Decimal
    grid_lower_limit: Decimal
    grid_count: int

    @classmethod
    def from_metrics(
        cls,
        rank: int,
        symbol: str,
        current_price: Decimal,
        volatility: VolatilityMetrics,
        trend: TrendMetrics,
        microstructure: MicrostructureMetrics,
        gss_score: float,
        atr_daily: float,
        atr_hourly: float
    ) -> 'ScreeningResult':
        """
        从三维指标构建筛选结果
        """
        upper, lower, grid_count = calculate_grid_parameters(
            current_price, atr_daily, atr_hourly
        )

        return cls(
            rank=rank,
            symbol=symbol,
            current_price=current_price,
            volatility=volatility,
            trend=trend,
            microstructure=microstructure,
            gss_score=gss_score,
            grid_upper_limit=upper,
            grid_lower_limit=lower,
            grid_count=grid_count
        )

    def to_terminal_row(self) -> dict:
        """
        转换为终端输出行(FR-031)
        """
        warnings = (
            self.volatility.warning_flags +
            self.microstructure.warning_flags
        )

        return {
            'rank': self.rank,
            'symbol': self.symbol,
            'price': f"${self.current_price:,.2f}",
            'natr': f"{self.volatility.natr:.2f}%",
            'ker': f"{self.volatility.ker:.3f}",
            'hurst': f"{self.trend.hurst_exponent:.3f}",
            'slope': f"{self.trend.norm_slope:.1f}",
            'r2': f"{self.trend.r_squared:.3f}",
            'ovr': f"{self.microstructure.ovr:.2f}",
            'funding': f"{float(self.microstructure.funding_rate) * 100:.4f}%",
            'cvd': '✓' if self.microstructure.has_cvd_divergence else '✗',
            'gss': f"{self.gss_score:.4f}",
            'grid_upper': f"${self.grid_upper_limit:,.2f}",
            'grid_lower': f"${self.grid_lower_limit:,.2f}",
            'warnings': ' '.join(warnings) if warnings else '-'
        }
```

---

## Data Flow

### Pipeline流程

```
1. 数据获取 (Binance API)
   ↓
   List[MarketSymbol] (500+标的)

2. 初筛 (FR-002, FR-003)
   ↓
   List[MarketSymbol] (通过流动性和时间过滤)

3. K线数据获取
   ↓
   List[tuple(MarketSymbol, KLines)]

4. 指标计算 (并行)
   ↓
   List[tuple(
       MarketSymbol,
       VolatilityMetrics,
       TrendMetrics,
       MicrostructureMetrics
   )]

5. 评分与排序 (FR-022)
   ↓
   List[ScreeningResult] (按GSS降序)

6. Top N筛选 (FR-029)
   ↓
   List[ScreeningResult] (Top 5, 可配置)

7. 终端输出 (FR-031)
   ↓
   格式化表格 + 执行摘要
```

---

## State Management

### 内存生命周期

| 阶段 | 内存占用 | 释放时机 |
|------|---------|---------|
| 数据获取 | ~10MB (500标的 × 基础数据) | 初筛完成后释放未通过标的 |
| K线数据 | ~10MB (300根K线 × 通过初筛标的) | 指标计算后释放原始K线 |
| 指标计算 | ~5MB (三维指标对象) | 保持到输出完成 |
| 筛选结果 | ~50KB (Top 5对象) | 命令退出时自动释放 |
| **峰值** | ~25MB | |

### 无持久化设计

- **优点**: 零数据库依赖,快速迭代,无迁移成本
- **限制**: 无法验证筛选稳定性(重叠度),无历史追溯
- **后续扩展**: 如需持久化,可在`grid_trading/models/`添加Django ORM模型

---

## Validation Summary

### FR映射

| Entity | Functional Requirements |
|--------|------------------------|
| MarketSymbol | FR-001, FR-002, FR-003, FR-004 |
| VolatilityMetrics | FR-005, FR-006, FR-007, FR-008, FR-009, FR-010 |
| TrendMetrics | FR-011, FR-012, FR-013, FR-014, FR-015, FR-024 |
| MicrostructureMetrics | FR-016, FR-017, FR-018, FR-019, FR-020, FR-021, FR-025 |
| ScreeningResult | FR-022, FR-023, FR-028, FR-029, FR-030, FR-031, FR-032, FR-033 |

### Success Criteria映射

| SC | Data Model Support |
|----|-------------------|
| SC-001 (60秒性能) | 内存模型避免数据库I/O,支持并行计算 |
| SC-002 (NATR精度) | VolatilityMetrics.calculate_natr() NumPy实现 |
| SC-003 (Top 5条件) | 各Metrics的passes_filter()方法验证 |
| SC-005 (输出格式) | ScreeningResult.to_terminal_row()格式化 |
| SC-006 (可配置性) | 所有阈值和权重作为参数传入 |
| SC-007 (趋势归零) | TrendMetrics.calculate_trend_score()否决机制 |

---

## Next Steps

1. **Phase 1继续**: 创建quickstart.md(用户使用指南)
2. **Phase 2 (tasks生成)**: 运行`/speckit.tasks`生成开发任务清单
3. **实现顺序**:
   - VolatilityMetrics (最简单,先验证NumPy)
   - MicrostructureMetrics (API数据直接)
   - TrendMetrics (最复杂,Hurst指数)
   - ScreeningResult (整合三维)
