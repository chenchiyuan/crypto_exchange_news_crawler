"""VP-Squeeze常量和配置"""

# Symbol映射表：用户简写 -> 币安交易对
SYMBOL_MAP = {
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

# 有效的时间周期（币安支持）
VALID_INTERVALS = [
    '1m', '3m', '5m', '15m', '30m',
    '1h', '2h', '4h', '6h', '8h', '12h',
    '1d', '3d', '1w', '1M'
]

# 预设交易对组合
SYMBOL_GROUPS = {
    'top10': ['btc', 'eth', 'bnb', 'sol', 'xrp', 'doge', 'ada', 'avax', 'dot', 'matic'],
    'major': ['btc', 'eth', 'bnb', 'sol'],
    'alt': ['xrp', 'doge', 'ada', 'avax', 'dot', 'matic'],
}

# K线数量限制
MIN_KLINES = 30  # 最少30根（BB周期20 + 缓冲）
MAX_KLINES = 1500  # 币安API最大限制
DEFAULT_KLINES = 100  # 默认数量

# Bollinger Bands参数
BB_PERIOD = 20
BB_MULTIPLIER = 2.0

# Keltner Channels参数
KC_EMA_PERIOD = 20
KC_ATR_PERIOD = 10
KC_MULTIPLIER = 1.5

# Squeeze检测参数
SQUEEZE_CONSECUTIVE_BARS = 3  # 连续满足条件的K线数

# Volume Profile参数
VP_RESOLUTION_PCT = 0.001  # 价格分辨率（0.1%）
VP_VALUE_AREA_PCT = 0.70  # 价值区域覆盖比例（70%）
VP_HVN_PERCENTILE = 0.80  # 高量节点阈值（前20%）
VP_LVN_PERCENTILE = 0.20  # 低量节点阈值（后20%）

# 币安API配置
# 现货市场
BINANCE_SPOT_BASE_URL = 'https://api.binance.com'
BINANCE_SPOT_KLINES_ENDPOINT = '/api/v3/klines'

# 合约市场
BINANCE_FUTURES_BASE_URL = 'https://fapi.binance.com'
BINANCE_FUTURES_KLINES_ENDPOINT = '/fapi/v1/klines'

# 请求超时
BINANCE_REQUEST_TIMEOUT = 30  # 秒

# 向后兼容
BINANCE_KLINES_ENDPOINT = BINANCE_SPOT_KLINES_ENDPOINT
