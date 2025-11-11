"""
合约监控配置文件

包含交易所API配置、重试策略、轮询间隔等设置
"""

# 交易所API端点配置
EXCHANGE_API_CONFIGS = {
    'binance': {
        'name': 'Binance',
        'base_url': 'https://fapi.binance.com',
        'endpoints': {
            'exchange_info': '/fapi/v1/exchangeInfo',
            'ticker': '/fapi/v1/ticker/bookTicker',
        },
        'rate_limit': 20,  # 请求/秒
        'weight_limit': 1200,  # weight/分钟
    },
    'hyperliquid': {
        'name': 'Hyperliquid',
        'base_url': 'https://api.hyperliquid.xyz',
        'endpoints': {
            'info': '/info',
        },
        'rate_limit': 20,  # 请求/秒
        'weight_limit': 1200,  # weight/分钟
    },
    'bybit': {
        'name': 'Bybit',
        'base_url': 'https://api.bybit.com',
        'endpoints': {
            'instruments_info': '/v5/market/instruments-info',
            'tickers': '/v5/market/tickers',
        },
        'rate_limit': 20,  # 请求/秒
    },
}

# 重试策略配置
RETRY_CONFIG = {
    'max_attempts': 3,  # 最大重试次数
    'multiplier': 1,  # 指数退避乘数
    'min_wait': 1,  # 最小等待时间(秒)
    'max_wait': 4,  # 最大等待时间(秒)
}

# 轮询间隔配置
POLLING_INTERVAL = 5 * 60  # 5分钟 (单位: 秒)

# 数据保留配置
RETENTION_DAYS = 90  # 下线合约保留天数

# 请求超时配置
REQUEST_TIMEOUT = 10  # 单个请求超时时间(秒)

# 性能目标
PERFORMANCE_GOALS = {
    'max_fetch_time': 30,  # 所有交易所总计最大获取时间(秒)
}

# 合约类型过滤
CONTRACT_TYPES = ['PERPETUAL']  # 仅USDT永续合约

# 初始部署标识文件路径
INITIAL_DEPLOYMENT_FLAG = '.futures_monitor_initialized'
