"""币安K线数据获取服务"""
import logging
import requests
from typing import List

from vp_squeeze.dto import KLineData
from vp_squeeze.constants import (
    SYMBOL_MAP,
    VALID_INTERVALS,
    MIN_KLINES,
    MAX_KLINES,
    BINANCE_SPOT_BASE_URL,
    BINANCE_KLINES_ENDPOINT,
    BINANCE_REQUEST_TIMEOUT,
)
from vp_squeeze.exceptions import (
    BinanceAPIError,
    InsufficientDataError,
    InvalidSymbolError,
    InvalidIntervalError,
)

logger = logging.getLogger(__name__)


def normalize_symbol(symbol: str) -> str:
    """
    将用户输入的symbol转换为币安交易对格式

    Args:
        symbol: 用户输入，如 'eth' 或 'ETHUSDT'

    Returns:
        币安交易对格式，如 'ETHUSDT'

    Raises:
        InvalidSymbolError: symbol不在支持列表中
    """
    symbol_lower = symbol.lower().strip()
    if symbol_lower in SYMBOL_MAP:
        return SYMBOL_MAP[symbol_lower]

    # 如果已经是完整格式，直接返回大写
    if symbol.upper().endswith('USDT'):
        return symbol.upper()

    raise InvalidSymbolError(symbol, list(SYMBOL_MAP.keys()))


def validate_interval(interval: str) -> str:
    """
    验证时间周期是否有效

    Args:
        interval: 时间周期，如 '4h'

    Returns:
        验证后的时间周期

    Raises:
        InvalidIntervalError: interval不在有效列表中
    """
    if interval not in VALID_INTERVALS:
        raise InvalidIntervalError(interval, VALID_INTERVALS)
    return interval


def fetch_klines(
    symbol: str,
    interval: str,
    limit: int = 100,
    start_time: int = None,
    end_time: int = None
) -> List[KLineData]:
    """
    从币安现货API获取K线数据

    Args:
        symbol: 用户输入的交易对（会自动标准化）
        interval: 时间周期
        limit: K线数量，默认100，最大1000
        start_time: 开始时间戳（毫秒），可选
        end_time: 结束时间戳（毫秒），可选

    Returns:
        KLineData列表

    Raises:
        InvalidSymbolError: 无效的交易对
        InvalidIntervalError: 无效的时间周期
        InsufficientDataError: 获取的数据不足
        BinanceAPIError: API调用失败
    """
    # 标准化和验证参数
    binance_symbol = normalize_symbol(symbol)
    validate_interval(interval)

    # 限制K线数量范围
    limit = max(MIN_KLINES, min(limit, MAX_KLINES))

    # 构建请求URL
    url = f"{BINANCE_SPOT_BASE_URL}{BINANCE_KLINES_ENDPOINT}"
    params = {
        'symbol': binance_symbol,
        'interval': interval,
        'limit': limit
    }

    # 添加时间范围参数（如果提供）
    if start_time is not None:
        params['startTime'] = start_time
    if end_time is not None:
        params['endTime'] = end_time

    logger.info(f"获取K线数据: {binance_symbol} {interval} limit={limit}")

    try:
        response = requests.get(url, params=params, timeout=BINANCE_REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.Timeout:
        raise BinanceAPIError(f"请求超时: {url}", status_code=None, response=None)
    except requests.exceptions.HTTPError as e:
        raise BinanceAPIError(
            f"HTTP错误: {e}",
            status_code=response.status_code if response else None,
            response=response.text if response else None
        )
    except requests.exceptions.RequestException as e:
        raise BinanceAPIError(f"请求失败: {e}")
    except ValueError as e:
        raise BinanceAPIError(f"JSON解析失败: {e}", response=response.text if response else None)

    # 检查数据量
    if len(data) < MIN_KLINES:
        raise InsufficientDataError(MIN_KLINES, len(data))

    # 转换为KLineData对象
    klines = [KLineData.from_binance_response(item) for item in data]

    logger.info(f"成功获取 {len(klines)} 根K线")

    return klines
