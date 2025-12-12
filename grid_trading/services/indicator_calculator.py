"""
技术指标计算器

用途: 计算三维筛选框架的所有技术指标
关联FR: FR-005至FR-021.1
"""

import numpy as np
from scipy.stats import linregress
from typing import List, Dict, Any, Tuple
import logging

logger = logging.getLogger("grid_trading")


# ============================================================================
# 第一维度: 波动率指标 (Volatility Dimension)
# ============================================================================


def calculate_natr(klines: List[Dict[str, Any]], period: int = 14) -> float:
    """
    计算归一化ATR (FR-005, T025)

    公式:
        TR = max(H-L, |H-C_prev|, |L-C_prev|)
        ATR(14) = EMA(TR, period=14)
        NATR = ATR(14) / Close × 100

    Args:
        klines: K线数据列表
        period: ATR周期 (默认14)

    Returns:
        NATR值 (%)
    """
    if len(klines) < period + 1:
        return 0.0

    highs = np.array([k["high"] for k in klines])
    lows = np.array([k["low"] for k in klines])
    closes = np.array([k["close"] for k in klines])

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

    return float(natr)


def calculate_ker(prices: np.ndarray, window: int = 10) -> float:
    """
    计算考夫曼效率比 (FR-006, T026)

    公式:
        Direction = |Close_t - Close_{t-N}|
        Volatility = Σ|Close_{t-i} - Close_{t-i-1}|
        KER = Direction / Volatility

    Args:
        prices: 收盘价序列
        window: 窗口期 (默认10)

    Returns:
        KER值 (0-1)
    """
    if len(prices) < window + 1:
        return 0.0

    direction = abs(prices[-1] - prices[-window - 1])
    volatility = np.sum(np.abs(np.diff(prices[-window - 1 :])))

    # 处理除零edge case
    if volatility == 0:
        return 0.0

    return float(direction / volatility)


def calculate_rsi(klines: List[Dict[str, Any]], period: int = 14) -> float:
    """
    计算相对强弱指数 RSI (Relative Strength Index)

    公式:
        RS = 平均涨幅 / 平均跌幅
        RSI = 100 - 100 / (1 + RS)

    Args:
        klines: K线数据列表
        period: RSI周期 (默认14)

    Returns:
        RSI值 (0-100)
    """
    if len(klines) < period + 1:
        return 50.0  # 数据不足，返回中性值

    closes = np.array([k["close"] for k in klines])
    deltas = np.diff(closes)

    # 分离涨幅和跌幅
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    # 计算平均涨幅和平均跌幅
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])

    # 处理除零情况
    if avg_loss == 0:
        return 100.0  # 全部上涨

    rs = avg_gain / avg_loss
    rsi = 100 - 100 / (1 + rs)

    return float(rsi)


def calculate_amplitude_sum_15m(klines_15m: List[Dict[str, Any]], count: int = 100) -> float:
    """
    计算最近N根15分钟K线的振幅百分比累计之和

    公式:
        Amplitude_i = (High_i - Low_i) / Close_i × 100  (百分比)
        Amplitude_Sum = Σ Amplitude_i (最近N根)

    Args:
        klines_15m: 15分钟K线数据列表
        count: 计算K线根数 (默认100根)

    Returns:
        振幅百分比累计值 (%)
    """
    if not klines_15m or len(klines_15m) < count:
        return 0.0

    # 取最近count根K线
    recent_klines = klines_15m[-count:]

    # 计算每根K线的振幅百分比并累加
    amplitude_sum = sum(
        (float(k["high"]) - float(k["low"])) / float(k["close"]) * 100.0
        for k in recent_klines
    )

    return float(amplitude_sum)


def calculate_vdr(klines_1m: List[Dict[str, Any]]) -> float:
    """
    计算波动率-位移比 (FR-010.1, T027)

    公式:
        CIV = Σ |Close_i - Open_i| / Open_i (240根1分钟K线)
        Displacement = |Close_final - Close_initial| / Close_initial
        VDR = CIV / Displacement

    Args:
        klines_1m: 240根1分钟K线数据

    Returns:
        VDR值
    """
    if len(klines_1m) < 240:
        logger.warning(f"1分钟K线数据不足240根 (仅{len(klines_1m)}根), VDR降级跳过")
        return 0.0

    # 计算累积日内波动率（CIV）
    civ = 0.0
    for k in klines_1m:
        close = float(k["close"])
        open_price = float(k["open"])
        if open_price > 0:  # 避免除零
            civ += abs(close - open_price) / open_price

    # 计算净位移
    close_final = float(klines_1m[-1]["close"])
    close_initial = float(klines_1m[0]["close"])

    if close_initial == 0:
        return float("inf")

    displacement = abs(close_final - close_initial) / close_initial

    # 避免除零: 完全横盘，VDR无穷大
    if displacement == 0:
        return float("inf")

    return civ / displacement


def calculate_volume_24h_from_1m_klines(klines_1m: List[Dict[str, Any]]) -> float:
    """
    从1440根1分钟K线计算24小时交易量(USDT)

    公式:
        Volume_24h = Σ quote_volume_i (1440根1分钟K线)

    Args:
        klines_1m: 1440根1分钟K线数据

    Returns:
        24小时交易量(USDT)
    """
    if not klines_1m or len(klines_1m) < 1:
        logger.warning(f"1分钟K线数据为空或不足, 无法计算24h交易量")
        return 0.0

    # 累计所有quote_volume (USDT成交额)
    total_volume = 0.0
    for k in klines_1m:
        quote_volume = k.get("quote_volume", 0.0)
        if quote_volume:
            total_volume += float(quote_volume)

    logger.debug(f"24h交易量: {total_volume:.2f} USDT (来自{len(klines_1m)}根1m K线)")
    return total_volume


def calculate_percentile_rank(values: np.ndarray) -> np.ndarray:
    """
    计算百分位排名 (FR-010, T028)

    Args:
        values: 数值数组

    Returns:
        百分位排名数组 (0-1)
    """
    from scipy.stats import rankdata

    ranks = rankdata(values, method="average")
    percentiles = (ranks - 1) / (len(values) - 1) if len(values) > 1 else np.zeros_like(values)

    return percentiles


def calculate_ema_slope(prices: np.ndarray, ema_period: int, slope_window: int = 10) -> tuple:
    """
    计算指数移动平均线(EMA)的斜率

    算法:
    1. 计算EMA(period)序列
       - k = 2 / (N + 1)
       - EMA_t = k × Close_t + (1 − k) × EMA_{t−1}
       - 初值: EMA_0 = SMA(前N期)
    2. 对最近slope_window根K线的EMA值进行线性回归
    3. 标准化斜率 = (slope / current_ema) × 10000

    Args:
        prices: 收盘价序列
        ema_period: EMA周期 (如20, 99)
        slope_window: 计算斜率的窗口期 (默认10)

    Returns:
        (ema_current, ema_slope_normalized)
        - ema_current: 当前EMA值
        - ema_slope_normalized: 标准化斜率 (正值=上升, 负值=下降)
    """
    if len(prices) < ema_period + slope_window:
        return 0.0, 0.0

    # 计算EMA序列
    k = 2.0 / (ema_period + 1)  # 平滑系数
    ema_values = np.zeros(len(prices))

    # 初值: 使用前N期的SMA
    ema_values[ema_period - 1] = np.mean(prices[:ema_period])

    # 递推计算EMA
    for i in range(ema_period, len(prices)):
        ema_values[i] = k * prices[i] + (1 - k) * ema_values[i - 1]

    # 提取有效的EMA序列 (从ema_period开始)
    valid_ema = ema_values[ema_period - 1:]

    if len(valid_ema) < slope_window:
        return 0.0, 0.0

    # 取最近slope_window根EMA值
    recent_ema = valid_ema[-slope_window:]
    current_ema = valid_ema[-1]

    # 线性回归计算斜率
    x = np.arange(len(recent_ema))
    slope, intercept, r_value, p_value, std_err = linregress(x, recent_ema)

    # 标准化斜率 (避免除零)
    if current_ema > 0:
        normalized_slope = (slope / current_ema) * 10000
    else:
        normalized_slope = 0.0

    return float(current_ema), float(normalized_slope)


# ============================================================================
# 第二维度: 趋势指标 (Trend Dimension)
# ============================================================================


def calculate_linear_regression(prices: np.ndarray) -> Tuple[float, float]:
    """
    计算线性回归指标 (FR-011, T029)

    Args:
        prices: 收盘价序列

    Returns:
        (norm_slope, r_squared)
    """
    if len(prices) < 2:
        return 0.0, 0.0

    x = np.arange(len(prices))
    slope, intercept, r_value, p_value, std_err = linregress(x, prices)

    # 标准化斜率
    norm_slope = (slope / prices[-1]) * 10000

    # 判定系数
    r_squared = r_value**2

    return float(norm_slope), float(r_squared)


def calculate_hurst_exponent(prices: np.ndarray) -> float:
    """
    计算赫斯特指数 (FR-012, T030)

    使用R/S分析算法 (Rescaled Range Analysis):
    该算法由英国水文学家H.E. Hurst于1951年提出,用于评估时间序列的长期记忆性。

    核心原理:
    - H < 0.5: 均值回归 (Mean Reverting) - 价格倾向于回归均值
    - H = 0.5: 随机游走 (Random Walk) - 布朗运动
    - H > 0.5: 趋势持续 (Trending) - 价格倾向于保持当前方向

    算法步骤:
    1. 对不同窗口大小 n (10, 20, 30, 50, 100)
    2. 将价格序列分割为长度为 n 的子序列
    3. 对每个子序列:
       a. 计算对数收益率 r = log(P_t / P_{t-1})
       b. 计算累积偏差: X_t = Σ(r_i - mean(r))
       c. 计算极差 R = max(X) - min(X)
       d. 计算标准差 S = std(r)
       e. 计算重标极差 R/S
    4. 对多个窗口大小的 (n, R/S) 取对数并进行线性回归
    5. 回归斜率即为Hurst指数

    为什么对做空网格有用:
    - H < 0.5: 价格有很强的均值回归特性,适合网格交易
    - H > 0.5: 价格趋势性强,容易突破网格边界,不适合

    Args:
        prices: 收盘价序列 (至少需要100根K线)

    Returns:
        Hurst指数 (H < 0.5 = 均值回归, H > 0.5 = 趋势持续)
        数据不足时返回0.5 (中性值)
    """
    if len(prices) < 100:
        logger.warning(f"价格序列不足100根 (仅{len(prices)}根), Hurst指数降级为0.5")
        return 0.5

    # 步骤1: 定义窗口大小集合
    # 使用多个窗口捕捉不同时间尺度的行为
    window_sizes = [10, 20, 30, 50, 100]
    # 过滤掉超过序列长度一半的窗口
    window_sizes = [w for w in window_sizes if w <= len(prices) // 2]

    if not window_sizes:
        return 0.5

    rs_values = []  # 存储每个窗口的 (窗口大小, 平均R/S)

    for window in window_sizes:
        # 步骤2: 计算对数收益率
        # log(P_t / P_{t-1}) = log(P_t) - log(P_{t-1})
        log_returns = np.diff(np.log(prices))

        # 步骤3: 分段计算R/S
        num_windows = len(log_returns) // window
        if num_windows == 0:
            continue

        rs_window = []  # 存储当前窗口大小下所有段的R/S值

        for i in range(num_windows):
            # 提取当前段
            segment = log_returns[i * window : (i + 1) * window]

            # 步骤3a: 计算平均收益率
            mean_return = np.mean(segment)

            # 步骤3b: 计算累积偏差 (Cumulative Deviation)
            # X_t = Σ(r_i - mean(r)) 从开始到时刻t
            cumulative_deviation = np.cumsum(segment - mean_return)

            # 步骤3c: 计算极差 R (Range)
            # R = max(X) - min(X)
            # 这反映了序列的波动幅度
            R = np.max(cumulative_deviation) - np.min(cumulative_deviation)

            # 步骤3d: 计算标准差 S (Standard Deviation)
            # ddof=1 使用样本标准差 (分母为n-1)
            S = np.std(segment, ddof=1)

            # 步骤3e: 计算重标极差 R/S
            # 归一化处理,使不同窗口大小的R/S可比
            if S > 0:
                rs_window.append(R / S)

        # 对当前窗口大小,计算所有段的平均R/S
        if rs_window:
            rs_values.append((window, np.mean(rs_window)))

    if len(rs_values) < 2:
        return 0.5

    # 步骤4: 线性回归 log(R/S) vs log(n)
    # Hurst发现: R/S ∝ n^H
    # 取对数: log(R/S) = H * log(n) + C
    # 因此对 log(R/S) 和 log(n) 进行线性回归,斜率即为 H
    log_windows = np.log([r[0] for r in rs_values])  # log(n)
    log_rs = np.log([r[1] for r in rs_values])  # log(R/S)

    slope, intercept, r_value, p_value, std_err = linregress(log_windows, log_rs)

    # 步骤5: 返回Hurst指数 (斜率)
    return float(slope)


def calculate_z_score(prices: np.ndarray, window: int = 20) -> float:
    """
    计算价格Z-Score (FR-015.1, T031)

    公式:
        Z_Score = (Close_t - MA_N) / StdDev_N

    Args:
        prices: 收盘价序列
        window: 移动平均窗口期 (默认20)

    Returns:
        Z-Score值
    """
    if len(prices) < window:
        return 0.0

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

    return float(z_score)


# ============================================================================
# 第三维度: 微观结构指标 (Microstructure Dimension)
# ============================================================================


def calculate_ovr(open_interest: float, volume_24h: float) -> float:
    """
    计算持仓量/成交量比率 (FR-016, T032)

    公式:
        OVR = OpenInterest / 24h Volume

    Args:
        open_interest: 持仓量
        volume_24h: 24小时成交量

    Returns:
        OVR值
    """
    if volume_24h == 0:
        return 0.0

    return open_interest / volume_24h


def calculate_cvd(klines: List[Dict[str, Any]]) -> np.ndarray:
    """
    计算累积成交量增量 (FR-020, T033)

    公式:
        Delta = TakerBuyVolume - (TotalVolume - TakerBuyVolume)
        CVD_t = CVD_{t-1} + Delta_t

    Args:
        klines: K线数据列表

    Returns:
        CVD序列
    """
    if not klines or len(klines) == 0:
        return np.array([0.0])

    taker_buy_volume = np.array([k["taker_buy_base_volume"] for k in klines])
    total_volume = np.array([k["volume"] for k in klines])

    # Delta = 买盘量 - 卖盘量
    delta = taker_buy_volume - (total_volume - taker_buy_volume)

    # 累积和
    cvd = np.cumsum(delta)

    return cvd


def detect_cvd_divergence(prices: np.ndarray, cvd: np.ndarray, window: int = 20) -> bool:
    """
    检测CVD背离 (FR-021, T034)

    背离条件: 价格创新高但CVD未创新高 (熊市背离)

    Args:
        prices: 收盘价序列
        cvd: CVD序列
        window: 窗口期 (默认20)

    Returns:
        是否存在背离
    """
    if len(prices) < window or len(cvd) < window:
        return False

    # 最后window根K线
    price_window = prices[-window:]
    cvd_window = cvd[-window:]

    # 价格和CVD的最高点索引
    price_high_idx = np.argmax(price_window)
    cvd_high_idx = np.argmax(cvd_window)

    # 背离条件: 价格新高在最后一根，但CVD新高不在最后一根
    has_divergence = (price_high_idx == window - 1) and (cvd_high_idx < window - 1)

    return bool(has_divergence)


def calculate_cvd_roc(cvd_series: np.ndarray, period: int = 5) -> float:
    """
    计算CVD变化率 (FR-021.1, T035)

    公式:
        CVD_ROC = (CVD_t - CVD_{t-5}) / |CVD_{t-5}| × 100

    Args:
        cvd_series: CVD时间序列
        period: 变化率周期 (默认5)

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

    return float(cvd_roc)


def calculate_high_drawdown(klines: List[Dict[str, Any]], current_price: float) -> Tuple[float, float]:
    """
    计算300根4h K线的最高价及当前价格的回落比例

    回落比例 = (最高价 - 当前价) / 最高价 × 100%

    正值表示当前价格低于历史高点（已回落）
    负值表示当前价格高于历史高点（创新高）

    Args:
        klines: K线数据列表（建议300根4h K线=50天历史）
        current_price: 当前价格

    Returns:
        (highest_price, drawdown_pct)
        - highest_price: K线内的最高价
        - drawdown_pct: 回落比例（%），正值=回落，负值=创新高

    Examples:
        最高价=$100, 当前价=$80 → 回落20%
        最高价=$100, 当前价=$105 → 回落-5%（创新高5%）
    """
    # 处理current_price为None的情况
    if current_price is None:
        if klines and len(klines) > 0:
            # 使用最后一根K线的收盘价作为当前价格
            current_price = float(klines[-1]["close"])
        else:
            # 无K线数据，返回默认值
            return 0.0, 0.0

    if not klines or len(klines) == 0:
        return current_price, 0.0

    # 获取所有K线的最高价
    highs = [float(k["high"]) for k in klines]
    highest_price = max(highs)

    # 计算回落比例
    if highest_price == 0:
        return current_price, 0.0

    drawdown_pct = ((highest_price - current_price) / highest_price) * 100

    return highest_price, drawdown_pct


def calculate_price_percentile(klines: List[Dict[str, Any]], current_price: float, count: int = 100) -> float:
    """
    计算当前价格在最近N根4h K线中的分位数位置

    价格分位 = (当前价格 - 区间最低价) / (区间最高价 - 区间最低价) × 100

    返回值含义：
    - 100% = 当前价格在区间最高点（极强势）
    - 50% = 当前价格在区间中间位置（中性）
    - 0% = 当前价格在区间最低点（极弱势）

    Args:
        klines: 4h K线数据列表
        current_price: 当前价格
        count: 使用最近N根K线（默认100根 = 约16.7天）

    Returns:
        价格分位数（0-100%），价格越高分位越高

    Examples:
        高=$100, 低=$50, 当前=$75 → 分位 50%（中间位置）
        高=$100, 低=$50, 当前=$95 → 分位 90%（接近高点）
        高=$100, 低=$50, 当前=$55 → 分位 10%（接近低点）
    """
    # 处理current_price为None的情况
    if current_price is None:
        if klines and len(klines) > 0:
            # 使用最后一根K线的收盘价作为当前价格
            current_price = float(klines[-1]["close"])
        else:
            # 无K线数据，返回默认值
            return 50.0

    if not klines or len(klines) == 0:
        return 50.0  # 默认中性位置

    # 截取最近count根K线
    recent_klines = klines[-count:] if len(klines) > count else klines

    # 获取区间最高价和最低价
    highs = [float(k["high"]) for k in recent_klines]
    lows = [float(k["low"]) for k in recent_klines]

    highest_price = max(highs)
    lowest_price = min(lows)

    # 计算价格范围
    price_range = highest_price - lowest_price

    if price_range == 0:
        return 50.0  # 价格无波动，返回中性

    # 计算价格分位：价格越高，分位越高
    percentile = ((current_price - lowest_price) / price_range) * 100

    # 限制在[0, 100]范围内
    percentile = max(0.0, min(100.0, percentile))

    return percentile


def calculate_annualized_funding_rate(
    funding_history: List[Dict[str, Any]],
    funding_interval_hours: int = 8
) -> float:
    """
    计算年化资金费率（支持不同结算周期）

    基于过去24-48小时的历史资金费率计算平均值并年化。
    不同交易对的资金费率结算周期不同：
    - 标准合约: 8小时结算一次（每天3次）
    - 高频合约: 1小时/4小时结算一次（每天24次/6次）

    年化计算公式:
    - 日结算次数 = 24 / funding_interval_hours
    - 年化资金费率 = 平均单次费率 × 日结算次数 × 365 × 100

    正负值含义:
    - 正值: 多头支付给空头 (多头拥挤,适合做空)
    - 负值: 空头支付给多头 (空头拥挤,不适合做空)

    Args:
        funding_history: 历史资金费率列表，每条记录包含:
            - fundingRate: Decimal类型的资金费率
            - fundingTime: int类型的结算时间戳(毫秒)
        funding_interval_hours: 资金费率结算周期（小时），默认8小时

    Returns:
        年化资金费率 (%) 保留正负号
        - 正值表示做空有利(收取资金费)
        - 负值表示做空不利(支付资金费)
    """
    if not funding_history or len(funding_history) == 0:
        logger.warning("历史资金费率数据为空，返回0")
        return 0.0

    # 提取所有资金费率值（保留正负号）
    from decimal import Decimal

    funding_rates = [float(record["fundingRate"]) for record in funding_history]

    # 计算平均资金费率（保留正负号）
    avg_funding_rate = np.mean(funding_rates)

    # 年化计算:
    # 1. 计算每天结算次数 = 24 / funding_interval_hours
    # 2. 一年365天
    # 3. 转换为百分比
    settlements_per_day = 24 / funding_interval_hours
    annualized_rate = avg_funding_rate * settlements_per_day * 365 * 100

    logger.debug(
        f"资金费率统计: 历史记录数={len(funding_history)}, "
        f"结算周期={funding_interval_hours}h (每天{settlements_per_day:.1f}次), "
        f"平均费率={avg_funding_rate:.6f}, "
        f"年化={annualized_rate:.2f}%"
    )

    return float(annualized_rate)


# ============================================================================
# 整合函数 (T036)
# ============================================================================


def calculate_all_indicators(
    market_symbol,
    klines_4h: List[Dict[str, Any]],
    klines_1m: List[Dict[str, Any]],
    klines_1d: List[Dict[str, Any]],
    klines_1h: List[Dict[str, Any]],
    klines_15m: List[Dict[str, Any]] = None,
    funding_history: List[Dict[str, Any]] = None,
    funding_interval_hours: int = 8,
) -> Tuple:
    """
    计算所有指标 (T036)

    Args:
        market_symbol: MarketSymbol对象
        klines_4h: 4小时K线 (用于主要指标计算)
        klines_1m: 1分钟K线 (用于VDR计算)
        klines_1d: 日线K线 (用于网格参数计算)
        klines_1h: 小时线K线 (用于网格参数计算)
        klines_15m: 15分钟K线 (用于振幅累计计算)
        funding_history: 历史资金费率数据 (用于年化资金费率计算)

    Returns:
        (VolatilityMetrics, TrendMetrics, MicrostructureMetrics, atr_daily, atr_hourly)
    """
    from grid_trading.models import (
        VolatilityMetrics,
        TrendMetrics,
        MicrostructureMetrics,
    )

    # ========== 数据完整性检查与降级处理 ==========
    # 如果4h K线数据不足，使用降级策略填充默认值
    has_sufficient_data = len(klines_4h) >= 100  # 最低要求100根4h K线

    if not has_sufficient_data:
        logger.warning(
            f"{market_symbol.symbol} 4h K线不足100根 (仅{len(klines_4h)}根), "
            f"将使用降级模式计算指标"
        )

    # 提取价格序列
    prices_4h = np.array([k["close"] for k in klines_4h]) if klines_4h else np.array([float(market_symbol.current_price)])

    # ========== 波动率指标 ==========
    natr = calculate_natr(klines_4h, period=14)
    ker = calculate_ker(prices_4h, window=10)
    vdr = calculate_vdr(klines_1m) if klines_1m else 0.0
    amplitude_sum_15m = calculate_amplitude_sum_15m(klines_15m, count=100) if klines_15m else 0.0

    volatility_metrics = VolatilityMetrics(
        symbol=market_symbol.symbol,
        natr=natr,
        ker=ker,
        vdr=vdr,
        amplitude_sum_15m=amplitude_sum_15m,
        natr_percentile=0.0,  # 稍后由全局计算填充
        inv_ker_percentile=0.0,  # 稍后由全局计算填充
    )

    # ========== 趋势指标 ==========
    norm_slope, r_squared = calculate_linear_regression(prices_4h)
    hurst_exponent = calculate_hurst_exponent(prices_4h)
    z_score = calculate_z_score(prices_4h, window=20)

    # 计算EMA均线斜率
    ema99_value, ema99_slope = calculate_ema_slope(prices_4h, ema_period=99, slope_window=10)
    ema20_value, ema20_slope = calculate_ema_slope(prices_4h, ema_period=20, slope_window=10)

    # 判断强上升趋势
    is_strong_uptrend = (norm_slope > 50.0) and (r_squared > 0.8)

    trend_metrics = TrendMetrics(
        symbol=market_symbol.symbol,
        norm_slope=norm_slope,
        r_squared=r_squared,
        hurst_exponent=hurst_exponent,
        z_score=z_score,
        is_strong_uptrend=is_strong_uptrend,
        ma99_slope=ema99_slope,
        ma20_slope=ema20_slope,
    )

    # ========== 微观结构指标 ==========
    ovr = calculate_ovr(float(market_symbol.open_interest), float(market_symbol.volume_24h))

    cvd_series = calculate_cvd(klines_4h)
    has_cvd_divergence = detect_cvd_divergence(prices_4h, cvd_series, window=20)
    cvd_roc = calculate_cvd_roc(cvd_series, period=5)

    # 年化资金费率计算
    # 优先使用过去24-48小时的历史平均值，如无历史数据则降级使用当前费率
    if funding_history and len(funding_history) > 0:
        annual_funding_rate = calculate_annualized_funding_rate(
            funding_history, funding_interval_hours
        )
        logger.debug(
            f"{market_symbol.symbol} 使用历史平均资金费率计算: {annual_funding_rate:.2f}% "
            f"(结算周期={funding_interval_hours}h)"
        )
    else:
        # 降级: 使用当前资金费率估算
        settlements_per_day = 24 / funding_interval_hours
        annual_funding_rate = float(market_symbol.funding_rate) * 100 * settlements_per_day * 365
        logger.debug(
            f"{market_symbol.symbol} 降级使用当前资金费率: {annual_funding_rate:.2f}% "
            f"(结算周期={funding_interval_hours}h)"
        )

    microstructure_metrics = MicrostructureMetrics(
        symbol=market_symbol.symbol,
        ovr=ovr,
        funding_rate=market_symbol.funding_rate,
        annual_funding_rate=annual_funding_rate,
        cvd=float(cvd_series[-1]),
        cvd_roc=cvd_roc,
        has_cvd_divergence=has_cvd_divergence,
    )

    # ========== 网格参数用ATR ==========
    atr_daily = calculate_natr(klines_1d, period=14) * float(market_symbol.current_price) / 100 if klines_1d else 0.0
    atr_hourly = calculate_natr(klines_1h, period=14) * float(market_symbol.current_price) / 100 if klines_1h else 0.0

    # ========== RSI指标 (用于挂单建议) ==========
    rsi_15m = calculate_rsi(klines_15m, period=14) if klines_15m and len(klines_15m) >= 15 else 50.0

    # ========== 高点回落指标 (用于筛选) ==========
    highest_price_300, drawdown_pct = calculate_high_drawdown(klines_4h, float(market_symbol.current_price))

    # ========== 价格分位指标 (基于100根4h K线) ==========
    price_percentile_100 = calculate_price_percentile(klines_4h, float(market_symbol.current_price), count=100)

    # ========== 24小时资金流分析 (基于1440根1m K线) ==========
    from grid_trading.services.money_flow_calculator import calculate_tiered_money_flow
    money_flow_metrics = calculate_tiered_money_flow(klines_1m) if klines_1m else {
        'large_net_flow': 0.0,
        'money_flow_strength': 0.5,
        'large_dominance': 0.0
    }

    return volatility_metrics, trend_metrics, microstructure_metrics, atr_daily, atr_hourly, rsi_15m, highest_price_300, drawdown_pct, price_percentile_100, money_flow_metrics
