"""
Bybit合约API客户端实现
"""
import logging
import requests
from typing import List, Dict, Any
from decimal import Decimal
from tenacity import retry, stop_after_attempt, wait_exponential
from ratelimit import limits, sleep_and_retry

from monitor.api_clients.base import BaseFuturesClient
from config.futures_config import EXCHANGE_API_CONFIGS, RETRY_CONFIG, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


class BybitFuturesClient(BaseFuturesClient):
    """Bybit合约客户端"""

    def __init__(self, exchange_name: str = 'bybit'):
        """初始化Bybit客户端"""
        super().__init__(exchange_name)
        self.config = EXCHANGE_API_CONFIGS[exchange_name]
        self.base_url = self.config['base_url']
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
    @limits(calls=EXCHANGE_API_CONFIGS['bybit']['rate_limit'], period=1)
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
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")

            response.raise_for_status()
            data = response.json()

            # 检查retCode
            if isinstance(data, dict) and 'retCode' in data:
                if data['retCode'] != 0:
                    error_msg = data.get('retMsg', 'Unknown error')
                    raise Exception(f"API错误: {error_msg}")

            return data

        except requests.RequestException as e:
            self._log_fetch_error(e)
            logger.error(f"API请求失败: {url} - {str(e)}")
            raise

    def fetch_contracts(self) -> List[Dict[str, Any]]:
        """
        获取合约列表和当前价格

        Returns:
            List[Dict]: 标准化的合约数据列表
        """
        try:
            # 1. 获取合约列表
            self.logger.info("开始获取Bybit合约信息")

            instruments = self._fetch_instruments()
            if not instruments:
                self.logger.info("未找到活跃的永续合约")
                return []

            # 2. 获取价格数据
            tickers = self._fetch_ticker_data()
            if not tickers:
                self.logger.warning("未能获取价格数据")
                return []

            # 3. 合并数据并标准化
            contracts = self._build_standardized_contracts(instruments, tickers)

            if not contracts:
                self.logger.info("未找到有效的合约数据")
                return []

            self._log_fetch_success(len(contracts))
            return contracts

        except Exception as e:
            self._log_fetch_error(e)
            logger.error(f"获取合约数据失败: {str(e)}")
            raise

    def fetch_contracts_with_indicators(self) -> List[Dict[str, Any]]:
        """
        获取合约列表及市场指标（Bybit优化：一次API调用获取所有数据）

        Returns:
            List[Dict]: 包含市场指标的合约数据列表
        """
        try:
            self.logger.info("开始获取Bybit合约及市场指标")

            # Bybit的/v5/market/tickers端点包含所有需要的数据
            tickers = self._fetch_ticker_data_with_indicators()

            if not tickers:
                self.logger.info("未找到活跃的永续合约")
                return []

            # 构建标准化合约数据（包含指标）
            contracts = self._build_contracts_with_indicators(tickers)

            if not contracts:
                self.logger.info("未找到有效的合约数据")
                return []

            self._log_fetch_success(len(contracts))
            return contracts

        except Exception as e:
            self._log_fetch_error(e)
            logger.error(f"获取合约及指标失败: {str(e)}")
            raise

    def _fetch_ticker_data_with_indicators(self) -> List[Dict]:
        """
        获取包含市场指标的ticker数据

        Returns:
            ticker数据列表（包含OI、资金费率等）
        """
        params = {
            'category': 'linear'
        }

        response = self._make_request('GET', self.config['endpoints']['tickers'], params=params)

        if not isinstance(response, dict) or 'result' not in response:
            self.logger.warning("响应格式异常：未找到result字段")
            return []

        result = response['result']

        if not isinstance(result, dict) or 'list' not in result:
            self.logger.warning("响应格式异常：未找到list字段")
            return []

        # 过滤USDT永续合约
        tickers = result['list']
        usdt_perpetual_tickers = [
            t for t in tickers
            if t.get('symbol', '').endswith('USDT')
        ]

        return usdt_perpetual_tickers

    def _build_contracts_with_indicators(self, tickers: List[Dict]) -> List[Dict[str, Any]]:
        """
        构建包含市场指标的标准化合约数据

        Args:
            tickers: Bybit ticker数据

        Returns:
            标准化的合约列表（含指标）
        """
        from datetime import datetime
        from django.utils import timezone

        contracts = []

        for ticker in tickers:
            try:
                symbol = ticker.get('symbol')
                if not symbol:
                    continue

                # 解析价格
                last_price_str = ticker.get('lastPrice')
                if not last_price_str:
                    self.logger.debug(f"符号 {symbol} 缺少lastPrice")
                    continue

                current_price = Decimal(str(last_price_str))
                if current_price <= 0:
                    continue

                # 解析市场指标
                open_interest = self._safe_decimal(ticker.get('openInterest'), '0')
                volume_24h = self._safe_decimal(ticker.get('volume24h'), '0')
                funding_rate = self._safe_decimal(ticker.get('fundingRate'), '0')

                # 解析下次资金费率时间
                next_funding_time_ms = ticker.get('nextFundingTime')
                next_funding_time = None
                if next_funding_time_ms:
                    try:
                        # Bybit返回毫秒时间戳
                        timestamp_sec = int(next_funding_time_ms) / 1000
                        next_funding_time = datetime.fromtimestamp(timestamp_sec, tz=timezone.get_current_timezone())
                    except (ValueError, TypeError) as e:
                        self.logger.debug(f"解析nextFundingTime失败 {symbol}: {e}")

                # Bybit固定8小时间隔
                funding_interval_hours = 8

                # 标准化符号
                normalized_symbol = self._normalize_symbol(symbol)

                # 构建合约数据
                contract = {
                    'symbol': normalized_symbol,
                    'current_price': current_price,
                    'contract_type': 'perpetual',
                    'exchange': self.exchange_name,
                    # 市场指标
                    'open_interest': open_interest,
                    'volume_24h': volume_24h,
                    'funding_rate': funding_rate,
                    'next_funding_time': next_funding_time,
                    'funding_interval_hours': funding_interval_hours,
                    # Bybit没有显式的cap/floor，但默认限制为±2.5%
                    'funding_rate_cap': Decimal('0.025'),
                    'funding_rate_floor': Decimal('-0.025'),
                }

                contracts.append(contract)

            except Exception as e:
                self.logger.warning(f"处理ticker数据失败 {ticker.get('symbol', 'unknown')}: {e}")
                continue

        return contracts

    def _safe_decimal(self, value: Any, default: str = '0') -> Decimal:
        """
        安全地将值转换为Decimal

        Args:
            value: 要转换的值
            default: 默认值

        Returns:
            Decimal对象
        """
        if value is None or value == '':
            return Decimal(default)

        try:
            return Decimal(str(value))
        except (ValueError, TypeError) as e:
            self.logger.debug(f"Decimal转换失败，使用默认值 {default}: {e}")
            return Decimal(default)

    def _fetch_instruments(self) -> List[Dict]:
        """
        获取合约信息

        Returns:
            合约信息列表
        """
        params = {
            'category': 'linear',
            'status': 'Trading'
        }

        response = self._make_request('GET', self.config['endpoints']['instruments_info'], params=params)

        if not isinstance(response, dict) or 'result' not in response:
            self.logger.warning("响应格式异常：未找到result字段")
            return []

        result = response['result']

        if not isinstance(result, dict) or 'list' not in result:
            self.logger.warning("响应格式异常：未找到list字段")
            return []

        contracts = result['list']

        # 过滤永续USDT合约
        perpetual_contracts = [
            c for c in contracts
            if c.get('contractType') == 'LinearPerpetual'
            and c.get('quoteCoin') == 'USDT'
            and c.get('status') == 'Trading'
        ]

        return perpetual_contracts

    def _fetch_ticker_data(self) -> List[Dict]:
        """
        获取ticker数据

        Returns:
            ticker数据列表
        """
        params = {
            'category': 'linear'
        }

        response = self._make_request('GET', self.config['endpoints']['tickers'], params=params)

        if not isinstance(response, dict) or 'result' not in response:
            self.logger.warning("响应格式异常：未找到result字段")
            return []

        result = response['result']

        if not isinstance(result, dict) or 'list' not in result:
            self.logger.warning("响应格式异常：未找到list字段")
            return []

        return result['list']

    def _build_standardized_contracts(self, instruments: List[Dict], tickers: List[Dict]) -> List[Dict[str, Any]]:
        """
        构建标准化的合约数据结构

        Args:
            instruments: 合约信息
            tickers: 价格数据

        Returns:
            标准化的合约列表
        """
        # 创建价格映射
        price_map = {}
        for ticker in tickers:
            symbol = ticker.get('symbol')
            if not symbol:
                continue

            last_price_str = ticker.get('lastPrice')
            if not last_price_str:
                continue

            try:
                # Bybit 只有一个lastPrice，使用它
                last_price = Decimal(str(last_price_str))
                price_map[symbol] = last_price
            except (ValueError, TypeError) as e:
                self.logger.debug(f"价格转换失败 {symbol}: {str(e)}")
                continue

        # 构建合约数据
        contracts = []

        for instrument in instruments:
            symbol = instrument.get('symbol')

            if not symbol or symbol not in price_map:
                self.logger.debug(f"符号 {symbol} 缺少价格数据，跳过")
                continue

            # 标准化符号格式
            normalized_symbol = self._normalize_symbol(symbol)

            current_price = price_map[symbol]

            if current_price <= 0:
                self.logger.debug(f"价格无效 {symbol}: {current_price}")
                continue

            # 构建合约数据
            contract = {
                'symbol': normalized_symbol,
                'current_price': current_price,
                'contract_type': 'perpetual',  # Bybit 已经是 perpetual
                'exchange': self.exchange_name,
                # 额外字段 - 用于扩展分析
                'details': {
                    'base_symbol': instrument.get('baseCoin', ''),
                    'quote_symbol': instrument.get('quoteCoin', ''),
                    'launch_time': instrument.get('launchTime', ''),
                    'delivery_time': instrument.get('deliveryTime', ''),
                    'price_scale': instrument.get('priceScale', '2'),
                    # ticker 中的额外信息
                    'mark_price': tickers[next((i for i, t in enumerate(tickers) if t.get('symbol') == symbol), None)].get('markPrice', ''),
                    'index_price': tickers[next((i for i, t in enumerate(tickers) if t.get('symbol') == symbol), None)].get('indexPrice', ''),
                }
            }

            contracts.append(contract)

        return contracts

    def _normalize_symbol(self, raw_symbol: str) -> str:
        """
        标准化合约符号

        Args:
            raw_symbol: 原始符号

        Returns:
            标准化符号
        """
        # Bybit的符号已经是标准格式 (BTCUSDT)
        return raw_symbol.upper()

    @retry(
        stop=stop_after_attempt(RETRY_CONFIG['max_attempts']),
        wait=wait_exponential(multiplier=RETRY_CONFIG['multiplier'], min=RETRY_CONFIG['min_wait'], max=RETRY_CONFIG['max_wait']),
        reraise=True
    )
    def get_contract_info(self, symbol: str) -> Dict[str, Any]:
        """
        获取单个合约的详细信息

        Args:
            symbol: 标准化符号

        Returns:
            合约信息

        Raises:
            ValueError: 如果合约不存在
        """
        instruments = self._fetch_instruments()

        for instrument in instruments:
            if instrument.get('symbol') == symbol:
                return {
                    'symbol': instrument.get('symbol'),
                    'contractType': instrument.get('contractType'),
                    'status': instrument.get('status'),
                    'baseCoin': instrument.get('baseCoin'),
                    'quoteCoin': instrument.get('quoteCoin'),
                    'launchTime': instrument.get('launchTime'),
                    'deliveryTime': instrument.get('deliveryTime'),
                    'priceScale': instrument.get('priceScale'),
                }

        raise ValueError(f"未找到合约 {symbol}")

    def validate_contract_exists(self, symbol: str) -> bool:
        """
        验证合约是否存在

        Args:
            symbol: 标准化符号

        Returns:
            是否存在
        """
        try:
            self.get_contract_info(symbol)
            return True
        except ValueError:
            return False

    @property
    def supported_contract_types(self) -> List[str]:
        """获取支持的合约类型"""
        return ['LinearPerpetual', 'LinearFutures', 'InversePerpetual', 'InverseFutures']

    @property
    def active_contract_status(self) -> List[str]:
        """获取活跃合约的状态"""
        return ['Trading', 'Settling', 'PreOpen']


# 测试验证函数
def validate_bybit_response_format(contracts: List[Dict]) -> bool:
    """验证Bybit响应格式"""
    if not isinstance(contracts, list):
        return False

    for contract in contracts:
        if not all(key in contract for key in ['symbol', 'current_price', 'contract_type', 'exchange']):
            return False

        if not isinstance(contract['current_price'], Decimal):
            return False

        if not contract['symbol'].endswith('USDT'):
            return False

    return True


def get_bybit_test_contract() -> Dict[str, Any]:
    """获取测试用的模拟Bybit合约数据"""
    from decimal import Decimal
    return {
        'symbol': 'BTCUSDT',
        'current_price': Decimal('44000.00'),
        'contract_type': 'perpetual',
        'exchange': 'bybit',
        'details': {
            'base_symbol': 'BTC',
            'quote_symbol': 'USDT',
            'launch_time': '1590969600000',
            'delivery_time': '0',
            'price_scale': '2',
        }
    }
