"""
Binance合约API客户端实现
"""
import logging
import requests
from typing import List, Dict, Any
from decimal import Decimal
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_exponential
from ratelimit import limits, sleep_and_retry

from monitor.api_clients.base import BaseFuturesClient
from config.futures_config import EXCHANGE_API_CONFIGS, RETRY_CONFIG, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


class BinanceFuturesClient(BaseFuturesClient):
    """Binance合约客户端"""

    def __init__(self, exchange_name: str = 'binance'):
        """初始化Binance客户端"""
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
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()

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
            self.logger.info("开始获取Binance合约信息")

            exchange_info = self._make_request('GET', self.config['endpoints']['exchange_info'])

            if 'symbols' not in exchange_info:
                self.logger.warning("未找到symbols字段 in exchange_info")
                return []

            # 2. 过滤永续USDT合约
            continuous_contracts = [
                symbol for symbol in exchange_info['symbols']
                if symbol.get('contractType') == 'PERPETUAL'
                and symbol.get('quoteAsset') == 'USDT'
                and symbol.get('status') == 'TRADING'
            ]

            if not continuous_contracts:
                self.logger.info("未找到活跃的USDT永续合约")
                return []

            # 3. 提取符号列表用于获取价格
            symbols = [c['symbol'] for c in continuous_contracts]

            # 4. 获取当前价格（分批获取，避免单次请求过大）
            spore = self._fetch_current_prices(symbols)

            if not spore:
                self.logger.warning("未能获取任何合约的价格数据")
                return []

            # 5. 合并数据并标准化格式 {}
            contracts = self._build_standardized_contracts(continuous_contracts, spore)

            self._log_fetch_success(len(contracts))
            return contracts

        except Exception as e:
            self._log_fetch_error(e)
            logger.error(f"获取合约数据失败: {str(e)}")
            raise

    def _fetch_current_prices(self, symbols: List[str]) -> Dict[str, Decimal]:
        """
        获取合约当前价格

        Args:
            symbols: 符号列表

        Returns:
            符号到价格的映射
        """
        try:
            # Binance ticker端点一次最多支持100个符号
            if len(symbols) > 100:
                # 分批处理
                price_data = {}
                for i in range(0, len(symbols), 100):
                    batch_symbols = symbols[i:i+100]
                    batch_data = self._fetch_ticker_data(batch_symbols)
                    price_data.update(batch_data)
                return price_data
            else:
                return self._fetch_ticker_data(symbols)

        except Exception as e:
            self.logger.warning(f"获取价格失败: {str(e)}")
            return {}

    def _fetch_ticker_data(self, symbols: List[str]) -> Dict[str, Decimal]:
        """
        获取一批符号的价格数据

        注意：Binance ticker/bookTicker端点不支持批量参数，
        所以我们获取所有ticker然后在本地过滤所需符号
        """
        try:
            # Binance的/bookTicker端点不支持批量参数，直接获取所有ticker
            ticker_data = self._make_request('GET', self.config['endpoints']['ticker'])

            prices = {}
            for ticker in ticker_data:
                symbol = ticker.get('symbol')
                if symbol not in symbols:
                    # 只保留我们需要的符号
                    continue

                bid_price = Decimal(ticker.get('bidPrice', '0'))
                ask_price = Decimal(ticker.get('askPrice', '0'))

                if symbol and bid_price > 0 and ask_price > 0:
                    # 使用bid/ask平均价作为当前价格
                    average_price = (bid_price + ask_price) / 2
                    prices[symbol] = average_price

            return prices

        except Exception as e:
            self.logger.error(f"获取ticker数据失败: {str(e)}")
            return {}

    def _build_standardized_contracts(self, raw_symbols: List[Dict], prices: Dict[str, Decimal]) -> List[Dict[str, Any]]:
        """
        构建标准化的合约数据结构

        Args:
            raw_symbols: 原始合约数据
            prices: 价格数据

        Returns:
            标准化的合约列表
        """
        contracts = []

        for symbol_data in raw_symbols:
            symbol = symbol_data['symbol']

            if symbol not in prices:
                self.logger.debug(f"符号 {symbol} 没有价格数据，跳过")
                continue

            # 标准化符号格式
            normalized_symbol = self._normalize_symbol(symbol)

            contract = {
                'symbol': normalized_symbol,
                'current_price': prices[symbol],
                'contract_type': 'perpetual',  # Binance已经是perpetual
                'exchange': self.exchange_name,
                # 额外字段 - 用于扩展分析
                'details': {
                    'base_symbol': symbol_data.get('baseAsset'),
                    'quote_symbol': symbol_data.get('quoteAsset'),
                    'max_leverage': self._extract_max_leverage_from_filters(symbol_data.get('filters', [])),
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
        # Binance的符号已经是标准格式 (BTCUSDT)
        return raw_symbol.upper()

    def _extract_max_leverage_from_filters(self, filters: List[Dict]) -> str:
        """
        从filters中提取最大杠杆倍数

        Args:
            filters: 过滤器列表

        Returns:
            最大杠杆倍数
        """
        for filter_item in filters:
            if filter_item.get('filterType') == 'LEVERAGE':
                return filter_item.get('maxLeverage', '0')
        return '20'  # 默认20倍

    @retry(
        stop=stop_after_attempt(RETRY_CONFIG['max_attempts']),
        wait=wait_exponential(multiplier=RETRY_CONFIG['multiplier'], min=RETRY_CONFIG['min_wait'], max=RETRY_CONFIG['max_wait']),
        reraise=True
    )
    def _make_request_with_fallback(self, method: str, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        带回退的请求方法

        如果主请求失败，尝试备用端点
        """
        try:
            return self._make_request(method, endpoint, params)
        except Exception as e:
            # 如果ticker失败，尝试使用24小时ticker
            if 'ticker' in endpoint and 'ticker/24hr' not in endpoint:
                self.logger.info("尝试使用24小时ticker数据")
                fallback_endpoint = '/fapi/v1/ticker/24hr'
                return self._make_request(method, fallback_endpoint, params)
            else:
                raise


    def fetch_contracts_with_indicators(self) -> List[Dict[str, Any]]:
        """
        获取合约列表及市场指标（Binance优化：并行请求3个端点）

        Returns:
            List[Dict]: 包含市场指标的合约数据列表
        """
        try:
            self.logger.info("开始获取Binance合约及市场指标")

            # 1. 获取交易所信息（合约列表）
            exchange_info = self._make_request('GET', self.config['endpoints']['exchange_info'])

            if 'symbols' not in exchange_info:
                self.logger.warning("未找到symbols字段")
                return []

            # 过滤永续USDT合约
            perpetual_symbols = [
                symbol for symbol in exchange_info['symbols']
                if symbol.get('contractType') == 'PERPETUAL'
                and symbol.get('quoteAsset') == 'USDT'
                and symbol.get('status') == 'TRADING'
            ]

            if not perpetual_symbols:
                self.logger.info("未找到活跃的USDT永续合约")
                return []

            self.logger.info(f"找到 {len(perpetual_symbols)} 个永续合约")

            # 2. 并行获取市场数据（3个端点）
            ticker_24h_data, premium_data, funding_info_data = self._fetch_market_data_parallel()

            # 3. 构建数据映射
            ticker_map = {t['symbol']: t for t in ticker_24h_data}
            premium_map = {p['symbol']: p for p in premium_data}
            funding_info_map = {f['symbol']: f for f in funding_info_data}

            # 4. 合并所有数据
            contracts = self._build_contracts_with_indicators(
                perpetual_symbols,
                ticker_map,
                premium_map,
                funding_info_map
            )

            self._log_fetch_success(len(contracts))
            return contracts

        except Exception as e:
            self._log_fetch_error(e)
            logger.error(f"获取合约及指标失败: {str(e)}")
            raise

    def _fetch_market_data_parallel(self) -> tuple:
        """
        并行获取市场数据（优化性能）

        Returns:
            Tuple[ticker_24h_data, premium_data, funding_info_data]
        """
        self.logger.info("并行获取市场数据...")

        ticker_24h_data = []
        premium_data = []
        funding_info_data = []

        with ThreadPoolExecutor(max_workers=3) as executor:
            # 提交3个并行任务
            future_ticker = executor.submit(self._fetch_24h_ticker)
            future_premium = executor.submit(self._fetch_premium_index)
            future_funding_info = executor.submit(self._fetch_funding_info)

            # 等待所有任务完成
            ticker_24h_data = future_ticker.result()
            premium_data = future_premium.result()
            funding_info_data = future_funding_info.result()

        self.logger.info(
            f"并行获取完成: ticker={len(ticker_24h_data)}, "
            f"premium={len(premium_data)}, funding_info={len(funding_info_data)}"
        )

        return ticker_24h_data, premium_data, funding_info_data

    def _fetch_24h_ticker(self) -> List[Dict]:
        """获取24小时ticker数据"""
        try:
            response = self._make_request('GET', '/fapi/v1/ticker/24hr')
            return response if isinstance(response, list) else []
        except Exception as e:
            self.logger.error(f"获取24h ticker失败: {e}")
            return []

    def _fetch_premium_index(self) -> List[Dict]:
        """获取premium index（包含资金费率）"""
        try:
            response = self._make_request('GET', '/fapi/v1/premiumIndex')
            return response if isinstance(response, list) else []
        except Exception as e:
            self.logger.error(f"获取premium index失败: {e}")
            return []

    def _fetch_funding_info(self) -> List[Dict]:
        """获取资金费率配置信息"""
        try:
            response = self._make_request('GET', '/fapi/v1/fundingInfo')
            return response if isinstance(response, list) else []
        except Exception as e:
            self.logger.error(f"获取funding info失败: {e}")
            return []

    def _build_contracts_with_indicators(
        self,
        symbols: List[Dict],
        ticker_map: Dict[str, Dict],
        premium_map: Dict[str, Dict],
        funding_info_map: Dict[str, Dict]
    ) -> List[Dict[str, Any]]:
        """
        构建包含市场指标的标准化合约数据

        Args:
            symbols: 合约符号列表
            ticker_map: 24小时ticker数据映射
            premium_map: premium数据映射
            funding_info_map: 资金费率配置映射

        Returns:
            标准化的合约列表（含指标）
        """
        from django.utils import timezone

        contracts = []

        for symbol_data in symbols:
            try:
                symbol = symbol_data['symbol']

                # 检查是否有完整数据
                if symbol not in ticker_map or symbol not in premium_map:
                    self.logger.debug(f"符号 {symbol} 缺少必需数据，跳过")
                    continue

                ticker = ticker_map[symbol]
                premium = premium_map[symbol]
                funding_info = funding_info_map.get(symbol, {})

                # 解析价格（使用mark price）
                mark_price = self._safe_decimal(premium.get('markPrice'), '0')
                if mark_price <= 0:
                    self.logger.debug(f"符号 {symbol} mark price无效")
                    continue

                # 解析市场指标
                open_interest = self._safe_decimal(premium.get('openInterest'), '0')
                volume_24h = self._safe_decimal(ticker.get('volume'), '0')
                funding_rate = self._safe_decimal(premium.get('lastFundingRate'), '0')

                # 解析下次资金费率时间
                next_funding_time_ms = premium.get('nextFundingTime')
                next_funding_time = None
                if next_funding_time_ms:
                    try:
                        timestamp_sec = int(next_funding_time_ms) / 1000
                        next_funding_time = datetime.fromtimestamp(timestamp_sec, tz=timezone.get_current_timezone())
                    except (ValueError, TypeError) as e:
                        self.logger.debug(f"解析nextFundingTime失败 {symbol}: {e}")

                # 获取资金费率配置
                funding_interval_hours = int(funding_info.get('fundingIntervalHours', 8))
                funding_rate_cap = self._safe_decimal(funding_info.get('fundingRateCap'), None)
                funding_rate_floor = self._safe_decimal(funding_info.get('fundingRateFloor'), None)

                # 标准化符号
                normalized_symbol = self._normalize_symbol(symbol)

                # 构建合约数据
                contract = {
                    'symbol': normalized_symbol,
                    'current_price': mark_price,
                    'contract_type': 'perpetual',
                    'exchange': self.exchange_name,
                    # 市场指标
                    'open_interest': open_interest,
                    'volume_24h': volume_24h,
                    'funding_rate': funding_rate,
                    'next_funding_time': next_funding_time,
                    'funding_interval_hours': funding_interval_hours,
                    'funding_rate_cap': funding_rate_cap,
                    'funding_rate_floor': funding_rate_floor,
                }

                contracts.append(contract)

            except Exception as e:
                self.logger.warning(f"处理合约数据失败 {symbol_data.get('symbol', 'unknown')}: {e}")
                continue

        return contracts

    def _safe_decimal(self, value: Any, default: str = '0') -> Decimal:
        """
        安全地将值转换为Decimal

        Args:
            value: 要转换的值
            default: 默认值（如果为None则返回None）

        Returns:
            Decimal对象或None
        """
        if value is None:
            return None if default is None else Decimal(default)

        if value == '':
            return None if default is None else Decimal(default)

        try:
            return Decimal(str(value))
        except (ValueError, TypeError) as e:
            self.logger.debug(f"Decimal转换失败，使用默认值 {default}: {e}")
            return None if default is None else Decimal(default)


# 测试验证函数 - 供单元测试使用
def validate_binance_response_format(contracts: List[Dict]) -> bool:
    """验证Binance响应格式"""
    if not isinstance(contracts, list):
        return False

    for contract in contracts:
        if not all(key in contract for key in ['symbol', 'current_price', 'contract_type', 'exchange']):
            return False

        if not isinstance(contract['current_price'], Decimal):
            return False

        if contract['contract_type'] != 'perpetual':
            return False

    return True

def get_binance_test_contract() -> Dict[str, Any]:
    """获取测试用的模拟Binance合约数据"""
    from decimal import Decimal
    return {
        'symbol': 'BTCUSDT',
        'current_price': Decimal('44000.50'),
        'contract_type': 'perpetual',
        'exchange': 'binance'
    }