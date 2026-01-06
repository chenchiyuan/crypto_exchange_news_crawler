"""
Binance现货API客户端实现

提供现货交易对数据获取功能，镜像BinanceFuturesClient的实现。
"""
import logging
import requests
from typing import List, Dict, Any
from decimal import Decimal, InvalidOperation as DecimalInvalidOperation
from tenacity import retry, stop_after_attempt, wait_exponential
from ratelimit import limits, sleep_and_retry

from monitor.api_clients.base import BaseFuturesClient
from config.futures_config import EXCHANGE_API_CONFIGS, RETRY_CONFIG, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


class BinanceSpotClient(BaseFuturesClient):
    """
    Binance现货客户端

    负责从Binance现货API获取交易对列表和价格数据，
    支持USDT本位现货交易对（如BTC/USDT、ETH/USDT）。

    主要功能：
    1. 获取现货交易对列表（/api/v3/exchangeInfo）
    2. 获取当前价格数据（/api/v3/ticker/price）
    3. 标准化现货符号格式（BTC/USDT）

    继承自BaseFuturesClient，复用重试和限流机制。

    Attributes:
        exchange_name (str): 交易所名称（固定为'binance'）
        base_url (str): API基础URL
        session (requests.Session): HTTP会话
        config (dict): 交易所API配置

    Examples:
        >>> client = BinanceSpotClient()
        >>> contracts = client.fetch_contracts()
        >>> print(f"获取到 {len(contracts)} 个现货交易对")
    """

    def __init__(self, exchange_name: str = 'binance'):
        """
        初始化Binance现货客户端

        Args:
            exchange_name: 交易所名称，默认为'binance'
        """
        super().__init__(exchange_name)
        self.config = EXCHANGE_API_CONFIGS[exchange_name]
        # 现货API使用不同的base_url
        self.base_url = 'https://api.binance.com'
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'python-monitoring/1.0.0'
        })

    @retry(
        stop=stop_after_attempt(RETRY_CONFIG['max_attempts']),
        wait=wait_exponential(multiplier=RETRY_CONFIG['multiplier'], min=RETRY_CONFIG['min_wait'], max=RETRY_CONFIG['max_wait']),
        reraise=True
    )
    @sleep_and_retry
    @limits(calls=EXCHANGE_API_CONFIGS['binance']['rate_limit'], period=1)
    def _make_request(self, method: str, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        发送API请求

        Args:
            method: HTTP方法
            endpoint: API端点
            params: 请求参数

        Returns:
            API响应数据

        Raises:
            requests.RequestException: 请求失败
        """
        url = f"{self.base_url}{endpoint}"

        self._log_fetch_start()

        try:
            if method.upper() == 'GET':
                response = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=params, timeout=REQUEST_TIMEOUT)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")

            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            self._log_fetch_error(e)
            logger.error(f"API请求失败: {url} - {str(e)}")
            raise

    @property
    def _spot_config(self) -> Dict[str, str]:
        """
        获取现货API端点配置

        Returns:
            现货API端点字典
        """
        return {
            'exchange_info': '/api/v3/exchangeInfo',
            'ticker': '/api/v3/ticker/price'
        }

    def fetch_contracts(self) -> List[Dict[str, Any]]:
        """
        获取现货交易对列表和当前价格

        Returns:
            List[Dict]: 标准化的现货交易对数据列表，每个字典包含:
                - symbol: str - 标准化后的交易对代码 (如BTC/USDT)
                - current_price: Decimal - 当前价格
                - contract_type: str - 交易对类型 (固定为'spot')
                - exchange: str - 交易所名称

        Raises:
            Exception: API调用失败时抛出异常

        Examples:
            >>> client = BinanceSpotClient()
            >>> contracts = client.fetch_contracts()
            >>> for contract in contracts[:3]:
            ...     print(f"{contract['symbol']}: {contract['current_price']}")
            BTC/USDT: Decimal('50000.00')
            ETH/USDT: Decimal('3000.00')
        """
        try:
            self.logger.info("开始获取Binance现货交易对信息")

            # 1. 获取交易所信息
            exchange_info = self._make_request('GET', self._spot_config['exchange_info'])

            if 'symbols' not in exchange_info:
                self.logger.warning("未找到symbols字段 in exchange_info")
                return []

            # 2. 过滤USDT现货交易对
            spot_trading_pairs = [
                symbol for symbol in exchange_info['symbols']
                if symbol.get('quoteAsset') == 'USDT'
                and symbol.get('isSpotTradingAllowed') == True
                and symbol.get('status') == 'TRADING'
            ]

            if not spot_trading_pairs:
                self.logger.info("未找到活跃的USDT现货交易对")
                return []

            self.logger.info(f"找到 {len(spot_trading_pairs)} 个USDT现货交易对")

            # 3. 提取符号列表用于获取价格
            symbols = [pair['symbol'] for pair in spot_trading_pairs]

            # 4. 获取当前价格
            prices = self._fetch_current_prices(symbols)

            if not prices:
                self.logger.warning("未能获取任何现货交易对的价格数据")
                return []

            # 5. 合并数据并标准化格式
            contracts = self._build_standardized_contracts(spot_trading_pairs, prices)

            self._log_fetch_success(len(contracts))
            return contracts

        except Exception as e:
            self._log_fetch_error(e)
            logger.error(f"获取现货交易对数据失败: {str(e)}")
            raise

    def _fetch_current_prices(self, symbols: List[str]) -> Dict[str, Decimal]:
        """
        获取现货交易对当前价格

        Args:
            symbols: 交易对符号列表

        Returns:
            符号到价格的映射字典

        Raises:
            Exception: API调用失败时抛出异常
        """
        try:
            # 现货ticker端点不支持批量参数，需要获取所有ticker然后过滤
            ticker_data = self._make_request('GET', self._spot_config['ticker'])

            # 确保ticker_data是列表类型
            if not isinstance(ticker_data, list):
                self.logger.warning(f"ticker数据不是列表格式: {type(ticker_data)}")
                return {}

            prices = {}
            for ticker in ticker_data:
                # 确保ticker是字典类型
                if not isinstance(ticker, dict):
                    continue

                symbol = ticker.get('symbol')
                if symbol not in symbols:
                    # 只保留我们需要的符号
                    continue

                price_str = ticker.get('price')
                if symbol and price_str:
                    try:
                        prices[symbol] = Decimal(str(price_str))
                    except (ValueError, TypeError, DecimalInvalidOperation) as e:
                        self.logger.debug(f"价格转换失败 {symbol}: {e}")
                        continue

            self.logger.debug(f"获取到 {len(prices)} 个现货交易对价格")
            return prices

        except Exception as e:
            self.logger.error(f"获取现货价格失败: {str(e)}")
            raise

    def _build_standardized_contracts(
        self,
        raw_symbols: List[Dict],
        prices: Dict[str, Decimal]
    ) -> List[Dict[str, Any]]:
        """
        构建标准化的现货交易对数据结构

        Args:
            raw_symbols: 原始交易对数据列表
            prices: 价格数据字典

        Returns:
            标准化的现货交易对列表

        Examples:
            >>> prices = {'BTCUSDT': Decimal('50000.00')}
            >>> raw_symbols = [{'symbol': 'BTCUSDT', 'baseAsset': 'BTC', 'quoteAsset': 'USDT'}]
            >>> contracts = self._build_standardized_contracts(raw_symbols, prices)
            >>> print(contracts[0]['symbol'])
            BTC/USDT
        """
        contracts = []

        for symbol_data in raw_symbols:
            symbol = symbol_data['symbol']

            if symbol not in prices:
                self.logger.debug(f"交易对 {symbol} 没有价格数据，跳过")
                continue

            # 标准化符号格式（现货格式：BTC/USDT）
            normalized_symbol = self._normalize_symbol(symbol)

            contract = {
                'symbol': normalized_symbol,
                'current_price': prices[symbol],
                'contract_type': 'spot',  # 现货交易对
                'exchange': self.exchange_name,
                # 额外字段 - 用于扩展分析
                'details': {
                    'base_symbol': symbol_data.get('baseAsset'),
                    'quote_symbol': symbol_data.get('quoteAsset'),
                    'raw_symbol': symbol  # 原始符号（Binance格式）
                }
            }

            contracts.append(contract)

        return contracts

    def _normalize_symbol(self, raw_symbol: str) -> str:
        """
        标准化现货交易对符号格式

        将Binance格式的现货符号（BinanceSymbol，如BTCUSDT）
        转换为标准现货格式（Symbol/Symbol，如BTC/USDT）

        Args:
            raw_symbol: 原始符号（Binance现货格式，如BTCUSDT）

        Returns:
            标准化符号（现货格式，如BTC/USDT）

        Raises:
            ValueError: 当符号格式无法识别时抛出

        Examples:
            >>> client._normalize_symbol('BTCUSDT')
            'BTC/USDT'
            >>> client._normalize_symbol('ETHUSDT')
            'ETH/USDT'
            >>> client._normalize_symbol('INVALID')
            Traceback (most recent call last):
                ...
            ValueError: 无法识别的现货符号格式: INVALID

        Note:
            仅支持USDT本位现货交易对。对于无法识别的格式，
            会抛出ValueError异常。
        """
        if not raw_symbol:
            raise ValueError("符号不能为空")

        # Binance现货符号格式：基础货币+计价货币（如BTCUSDT）
        # 常见的计价货币列表
        quote_assets = ['USDT', 'BUSD', 'BTC', 'ETH', 'BNB', 'TUSD', 'USDC']

        # 尝试匹配已知的计价货币后缀
        for quote in quote_assets:
            if raw_symbol.endswith(quote):
                base = raw_symbol[:-len(quote)]
                if base:
                    return f"{base}/{quote}"

        # 如果没有匹配到，抛出异常
        raise ValueError(f"无法识别的现货符号格式: {raw_symbol}")

    def fetch_contracts_with_indicators(self) -> List[Dict[str, Any]]:
        """
        获取现货交易对列表及市场指标

        Note:
            现货交易对通常不包含持仓量、资金费率等期货特有指标，
            此方法返回与fetch_contracts()相同的数据结构。

        Returns:
            List[Dict]: 标准化的现货交易对数据列表

        Raises:
            Exception: API调用失败时抛出异常
        """
        # 现货交易对没有特殊的指标数据，直接复用fetch_contracts
        return self.fetch_contracts()


# 测试验证函数 - 供单元测试使用
def validate_binance_spot_response_format(contracts: List[Dict]) -> bool:
    """
    验证Binance现货响应格式

    Args:
        contracts: 要验证的合约列表

    Returns:
        bool: 格式是否正确
    """
    if not isinstance(contracts, list):
        return False

    for contract in contracts:
        # 检查必需字段
        if not all(key in contract for key in ['symbol', 'current_price', 'contract_type', 'exchange']):
            return False

        # 检查类型
        if not isinstance(contract['current_price'], Decimal):
            return False

        # 检查交易对类型
        if contract['contract_type'] != 'spot':
            return False

        # 检查符号格式（应该包含'/'）
        if '/' not in contract['symbol']:
            return False

    return True


def get_binance_test_spot_contract() -> Dict[str, Any]:
    """
    获取测试用的模拟Binance现货交易对数据

    Returns:
        Dict: 模拟的现货交易对数据
    """
    from decimal import Decimal
    return {
        'symbol': 'BTC/USDT',
        'current_price': Decimal('50000.00'),
        'contract_type': 'spot',
        'exchange': 'binance',
        'details': {
            'base_symbol': 'BTC',
            'quote_symbol': 'USDT',
            'raw_symbol': 'BTCUSDT'
        }
    }
