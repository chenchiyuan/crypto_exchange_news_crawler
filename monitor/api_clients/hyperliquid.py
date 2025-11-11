"""
Hyperliquid合约API客户端实现
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


class HyperliquidFuturesClient(BaseFuturesClient):
    """Hyperliquid合约客户端"""

    def __init__(self, exchange_name: str = 'hyperliquid'):
        """初始化Hyperliquid客户端"""
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
    @limits(calls=EXCHANGE_API_CONFIGS['hyperliquid']['rate_limit'], period=1)
    def _make_post_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送POST请求

        Args:
            payload: 请求载荷

        Returns:
            API响应数据
        """
        url = f"{self.base_url}/info"

        self._log_fetch_start()

        try:
            response = self.session.post(url, json=payload, timeout=REQUEST_TIMEOUT)
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
            # Hyperliquid 使用单个POST端点获取所有数据
            self.logger.info("开始获取Hyperliquid合约信息")

            payload = {"type": "metaAndAssetCtxs"}
            response = self._make_post_request(payload)

            # Hyperliquid返回列表: [meta_dict, asset_contexts_list]
            if not isinstance(response, list) or len(response) < 2:
                self.logger.warning("响应格式异常：结构不完整")
                return []

            meta = response[0]  # 第一个元素是meta信息
            asset_contexts = response[1]  # 第二个元素是资产上下文列表

            if not isinstance(meta, dict) or 'universe' not in meta:
                self.logger.warning("响应格式异常：未找到universe字段")
                return []

            universe = meta['universe']

            if not isinstance(universe, list) or not universe:
                self.logger.info("未找到任何合约数据")
                return []

            # 构建标准化的合约数据
            contracts = self._build_standardized_contracts(universe, asset_contexts)

            if not contracts:
                self.logger.info("未找到有效的合约数据")
                return []

            self._log_fetch_success(len(contracts))
            return contracts

        except Exception as e:
            self._log_fetch_error(e)
            logger.error(f"获取合约数据失败: {str(e)}")
            raise

    def _build_standardized_contracts(self, universe: List[Dict], asset_contexts: List[Dict]) -> List[Dict[str, Any]]:
        """
        构建标准化的合约数据结构

        Args:
            universe: 原始合约数据
            asset_contexts: 资产上下文列表 (包含价格信息，与universe索引对应)

        Returns:
            标准化的合约列表
        """
        contracts = []

        # 遍历universe
        for i, item in enumerate(universe):
            # 提取基础数据
            name = item.get('name', '')

            # 检查必要字段
            if not name:
                self.logger.debug(f"跳过无效合约数据: {item}")
                continue

            # 标准化符号格式 (BTC -> BTCUSDT)
            normalized_symbol = self._normalize_symbol(name)

            # 获取价格信息 (优先使用markPx, 其次oraclePx)
            current_price = None
            price_source = None
            ctx = None

            # 用索引获取对应的asset context
            if i < len(asset_contexts):
                ctx = asset_contexts[i]
                # 优先使用markPx
                if 'markPx' in ctx and ctx['markPx']:
                    current_price = ctx['markPx']
                    price_source = 'markPx'
                # 其次使用oraclePx
                elif 'oraclePx' in ctx and ctx['oraclePx']:
                    current_price = ctx['oraclePx']
                    price_source = 'oraclePx'

            # 如果没有价格，跳过
            if not current_price:
                self.logger.debug(f"跳过无价格数据: {name}")
                continue

            # 价格转换
            try:
                price = Decimal(str(current_price))
            except (ValueError, TypeError) as e:
                self.logger.warning(f"价格转换失败 {name}: {str(e)}")
                continue

            if price <= 0:
                self.logger.debug(f"价格无效 {name}: {price}")
                continue

            # 构建合约数据
            contract = {
                'symbol': normalized_symbol,
                'current_price': price.normalize(),  # 标准化精度
                'contract_type': 'perpetual',  # Hyperliquid 默认为永续
                'exchange': self.exchange_name,
                # 额外字段 - 用于扩展分析
                'details': {
                    'name': name,  # 原始符号
                    'max_leverage': str(item.get('maxLeverage', '0')),
                    'max_position': str(item.get('maxPosition', '0')),
                    'sz_decimals': str(item.get('szDecimals', '0')),
                    'price_source': price_source,  # 价格来源
                    'mark_price': str(ctx.get('markPx', '')) if ctx else '',
                    'oracle_price': str(ctx.get('oraclePx', '')) if ctx else '',
                    'open_interest': str(ctx.get('openInterest', '')) if ctx else '',
                    'funding': str(ctx.get('funding', '')) if ctx else '',
                }
            }

            contracts.append(contract)

        return contracts

    def _normalize_symbol(self, raw_symbol: str) -> str:
        """
        标准化合约符号

        关键特性: Hyperliquid使用基础货币作为符号，需要添加USDT后缀
        例如: BTC -> BTCUSDT, ETH -> ETHUSDT

        Args:
            raw_symbol: 原始符号 (如BTC, ETH)

        Returns:
            标准化符号 (如BTCUSDT, ETHUSDT)
        """
        # 确保大写
        symbol = raw_symbol.upper()

        # 检查是否已包含USDT
        if symbol.endswith('USDT'):
            # 已经是标准格式
            return symbol
        else:
            # 添加USDT后缀
            return f"{symbol}USDT"

    @retry(
        stop=stop_after_attempt(RETRY_CONFIG['max_attempts']),
        wait=wait_exponential(multiplier=RETRY_CONFIG['multiplier'], min=RETRY_CONFIG['min_wait'], max=RETRY_CONFIG['max_wait']),
        reraise=True
    )
    def fetch_single_contract_price(self, symbol: str) -> Decimal:
        """
        获取单个合约的价格（用于备用）

        Args:
            symbol: 标准化符号 (如BTCUSDT)

        Returns:
            价格

        Raises:
            ValueError: 如果符号或价格无效
        """
        payload = {
            "type": "meta",
            "userState": None
        }

        response = self._make_post_request(payload)

        if 'meta' not in response or 'universe' not in response['meta']:
            raise ValueError("无效的响应格式")

        universe = response['meta']['universe']

        for item in universe:
            if item.get('name') == symbol:
                price_str = item.get('oraclePx')
                if price_str:
                    return Decimal(str(price_str))

        raise ValueError(f"未找到合约 {symbol} 的价格")

    @property
    def all_exchange_codes(self) -> List[str]:
        """获取所有支持的交易所代码"""
        return ['binance', 'bybit', 'bitget', 'coinbase']  # 可扩展

    @property
    def status_indicators(self) -> Dict[str, str]:
        """获取状态指示器"""
        return {
            'active': '活跃',
            'delisted': '已下线',
            'pending': '待上线'
        }

    def validate_contract_data(self, contract: Dict[str, Any]) -> bool:
        """
        验证合约数据完整性

        Args:
            contract: 合约数据

        Returns:
            是否有效
        """
        required_fields = ['symbol', 'current_price', 'contract_type', 'exchange']
        for field in required_fields:
            if field not in contract:
                return False

        # 检查价格有效性
        if not isinstance(contract['current_price'], Decimal):
            return False

        if contract['current_price'] <= 0:
            return False

        # 检查符号格式
        if not isinstance(contract['symbol'], str) or not contract['symbol']:
            return False

        return True


    def fetch_contracts_with_indicators(self) -> List[Dict[str, Any]]:
        """
        获取合约列表及市场指标（Hyperliquid优化：2次info请求）

        Returns:
            List[Dict]: 包含市场指标的合约数据列表
        """
        try:
            self.logger.info("开始获取Hyperliquid合约及市场指标")

            # 1. 获取meta和asset contexts
            meta_payload = {"type": "metaAndAssetCtxs"}
            meta_response = self._make_post_request(meta_payload)

            if not isinstance(meta_response, list) or len(meta_response) < 2:
                self.logger.warning("meta响应格式异常")
                return []

            meta = meta_response[0]
            asset_contexts = meta_response[1]

            if not isinstance(meta, dict) or 'universe' not in meta:
                self.logger.warning("未找到universe字段")
                return []

            universe = meta['universe']

            if not isinstance(universe, list) or not universe:
                self.logger.info("未找到任何合约")
                return []

            self.logger.info(f"找到 {len(universe)} 个合约")

            # 2. 获取所有mid prices（用于当前价格）
            all_mids_payload = {"type": "allMids"}
            all_mids = self._make_post_request(all_mids_payload)

            if not isinstance(all_mids, dict) or 'mids' not in all_mids:
                self.logger.warning("allMids响应格式异常")
                all_mids = {'mids': {}}

            mid_prices = all_mids.get('mids', {})

            # 3. 构建包含市场指标的合约数据
            contracts = self._build_contracts_with_indicators(
                universe,
                asset_contexts,
                mid_prices
            )

            self._log_fetch_success(len(contracts))
            return contracts

        except Exception as e:
            self._log_fetch_error(e)
            logger.error(f"获取合约及指标失败: {str(e)}")
            raise

    def _build_contracts_with_indicators(
        self,
        universe: List[Dict],
        asset_contexts: List[Dict],
        mid_prices: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        构建包含市场指标的标准化合约数据

        Args:
            universe: 合约universe数据
            asset_contexts: 资产上下文数据
            mid_prices: 中间价格映射

        Returns:
            标准化的合约列表（含指标）
        """
        from datetime import datetime, timedelta
        from django.utils import timezone

        contracts = []

        for idx, asset in enumerate(universe):
            try:
                name = asset.get('name', '')
                if not name:
                    continue

                # 获取对应的asset context
                ctx = asset_contexts[idx] if idx < len(asset_contexts) else {}

                # 获取当前价格（优先使用mid price）
                current_price_str = mid_prices.get(name)
                if not current_price_str:
                    # 降级使用markPx
                    current_price_str = ctx.get('markPx', '0')

                current_price = self._safe_decimal(current_price_str, '0')
                if current_price <= 0:
                    self.logger.debug(f"符号 {name} 价格无效")
                    continue

                # 解析市场指标
                open_interest = self._safe_decimal(ctx.get('openInterest'), '0')

                # Hyperliquid的24H交易量需要从dayNtlVlm获取
                volume_24h_str = ctx.get('dayNtlVlm')
                volume_24h = self._safe_decimal(volume_24h_str, '0')

                # 解析资金费率
                funding_rate_str = ctx.get('funding')
                funding_rate = self._safe_decimal(funding_rate_str, '0')

                # Hyperliquid固定1小时间隔
                funding_interval_hours = 1

                # 计算下次资金费率时间（每小时整点）
                now = timezone.now()
                next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                next_funding_time = next_hour

                # Hyperliquid资金费率上下限为 ±4%/小时
                funding_rate_cap = Decimal('0.04')
                funding_rate_floor = Decimal('-0.04')

                # 标准化符号（Hyperliquid使用基础货币，需要添加USDT）
                normalized_symbol = self._normalize_symbol(name)

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
                    'funding_rate_cap': funding_rate_cap,
                    'funding_rate_floor': funding_rate_floor,
                }

                contracts.append(contract)

            except Exception as e:
                self.logger.warning(f"处理合约数据失败 {universe[idx].get('name', 'unknown')}: {e}")
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


# 测试验证函数
def validate_hyperliquid_response_format(contracts: List[Dict]) -> bool:
    """验证Hyperliquid响应格式"""
    if not isinstance(contracts, list):
        return False

    for contract in contracts:
        if not all(key in contract for key in ['symbol', 'current_price', 'contract_type', 'exchange']):
            return False

        if not isinstance(contract['current_price'], Decimal):
            return False

        # 检查符号是否正确转换
        if not contract['symbol'].endswith('USDT'):
            return False

    return True


def get_hyperliquid_test_contract() -> Dict[str, Any]:
    """获取测试用的模拟Hyperliquid合约数据"""
    from decimal import Decimal
    return {
        'symbol': 'BTCUSDT',  # 转换后
        'current_price': Decimal('44000.00000000'),
        'contract_type': 'perpetual',
        'exchange': 'hyperliquid',
        'details': {
            'name': 'BTC',  # 原始符号
            'max_leverage': '50',
            'max_position': '10000000',
            'sz_decimals': '5',
        }
    }
