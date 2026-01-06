"""
现货数据获取服务

负责协调现货API客户端，获取和更新现货交易对数据。
"""
import logging
from typing import Dict, List, Any, Optional
from decimal import Decimal

from django.utils import timezone
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from monitor.api_clients.binance_spot import BinanceSpotClient
from monitor.models import Exchange, SpotContract
from config.futures_config import RETRY_CONFIG

logger = logging.getLogger(__name__)


class SpotFetcherService:
    """
    现货交易对数据获取服务

    负责从各个交易所API获取现货交易对列表和价格数据，
    并更新到SpotContract模型中。

    主要功能：
    1. 支持多交易所现货数据获取（初期仅binance）
    2. 自动创建和更新交易所记录
    3. 增量更新现货交易对数据
    4. 提供统计信息（新增、更新、下线数量）

    Attributes:
        clients (Dict[str, Any]): 交易所API客户端字典

    Examples:
        >>> service = SpotFetcherService()
        >>> result = service.update_exchanges_manually(['binance'])
        >>> print(result)
        {'binance': {'status': 'success', 'new': 10, 'updated': 5, 'delisted': 0}}
    """

    def __init__(self):
        """
        初始化现货数据获取服务

        当前仅支持binance交易所，后续可扩展其他交易所。
        """
        self.clients = {
            'binance': BinanceSpotClient(),
        }
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @retry(
        stop=stop_after_attempt(RETRY_CONFIG['max_attempts']),
        wait=wait_exponential(multiplier=RETRY_CONFIG['multiplier'], min=RETRY_CONFIG['min_wait'], max=RETRY_CONFIG['max_wait']),
        retry=retry_if_exception_type((Exception,))
    )
    def fetch_from_all_exchanges(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        从所有配置的交易所获取现货交易对数据

        Returns:
            Dict: {exchange_code: contracts_list}

        Raises:
            Exception: 如果所有交易所都失败

        Examples:
            >>> service = SpotFetcherService()
            >>> data = service.fetch_from_all_exchanges()
            >>> print(f"Binance现货交易对数量: {len(data['binance'])}")
        """
        self.logger.info("开始从所有交易所获取现货交易对数据")

        all_contracts = {}
        errors = []

        # 并行获取所有交易所数据
        for exchange_code, client in self.clients.items():
            try:
                self.logger.info(f"正在获取 {exchange_code} 现货数据")
                contracts = client.fetch_contracts()
                all_contracts[exchange_code] = contracts
                self.logger.info(f"成功从 {exchange_code} 获取 {len(contracts)} 个现货交易对")
            except Exception as e:
                error_msg = f"从 {exchange_code} 获取现货数据失败: {str(e)}"
                self.logger.error(error_msg)
                errors.append(error_msg)
                all_contracts[exchange_code] = []  # 设置空列表

        # 记录错误
        if errors:
            self.logger.warning(f"部分交易所获取失败: {errors}")

        return all_contracts

    @retry(
        stop=stop_after_attempt(RETRY_CONFIG['max_attempts']),
        wait=wait_exponential(multiplier=RETRY_CONFIG['multiplier'], min=RETRY_CONFIG['min_wait'], max=RETRY_CONFIG['max_wait']),
        retry=retry_if_exception_type((Exception,))
    )
    def save_contracts_to_database(
        self,
        exchange: Exchange,
        contracts: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        保存现货交易对数据到数据库

        Args:
            exchange: 交易所实例
            contracts: 现货交易对数据列表

        Returns:
            Dict: 包含统计信息 {'new': int, 'updated': int, 'delisted': int, 'saved': int}

        Raises:
            Exception: 如果保存失败

        Examples:
            >>> exchange = Exchange.objects.get(code='binance')
            >>> contracts = [{'symbol': 'BTC/USDT', 'current_price': Decimal('50000')}]
            >>> stats = service.save_contracts_to_database(exchange, contracts)
            >>> print(f"新增: {stats['new']}, 更新: {stats['updated']}")
        """
        self.logger.info(f"开始保存 {exchange.name} 的 {len(contracts)} 个现货交易对到数据库")

        new_count = 0
        updated_count = 0
        saved_count = 0

        # 获取当前数据库中该交易所的所有现货交易对
        existing_contracts = {
            contract.symbol: contract
            for contract in SpotContract.objects.filter(exchange=exchange)
        }

        # 获取API返回的交易对符号列表，用于检测下线
        api_symbols = set(contract['symbol'] for contract in contracts)

        # 处理每个API返回的交易对
        for contract_data in contracts:
            try:
                symbol = contract_data['symbol']
                current_price = contract_data['current_price']

                if symbol in existing_contracts:
                    # 更新现有记录
                    spot_contract = existing_contracts[symbol]
                    spot_contract.current_price = current_price
                    spot_contract.status = SpotContract.ACTIVE
                    spot_contract.last_updated = timezone.now()
                    spot_contract.save(update_fields=['current_price', 'status', 'last_updated'])
                    updated_count += 1
                    saved_count += 1

                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug(f"更新现货交易对: {symbol} - {current_price}")

                else:
                    # 创建新记录
                    SpotContract.objects.create(
                        exchange=exchange,
                        symbol=symbol,
                        status=SpotContract.ACTIVE,
                        current_price=current_price
                    )
                    new_count += 1
                    saved_count += 1

                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug(f"创建现货交易对: {symbol} - {current_price}")

            except Exception as e:
                self.logger.error(f"保存现货交易对失败 {contract_data.get('symbol', 'unknown')}: {str(e)}")
                raise

        # 检测下线的交易对
        delisted_count = 0
        for symbol, spot_contract in existing_contracts.items():
            if symbol not in api_symbols:
                # 标记为下线
                spot_contract.status = SpotContract.DELISTED
                spot_contract.last_updated = timezone.now()
                spot_contract.save(update_fields=['status', 'last_updated'])
                delisted_count += 1

                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(f"标记下线现货交易对: {symbol}")

        stats = {
            'new': new_count,
            'updated': updated_count,
            'delisted': delisted_count,
            'saved': saved_count
        }

        self.logger.info(
            f"保存完成: 新增={new_count}, 更新={updated_count}, "
            f"下线={delisted_count}, 总计保存={saved_count}"
        )

        return stats

    def update_exchanges_manually(self, exchange_codes: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        手动更新指定交易所的现货交易对数据

        Args:
            exchange_codes: 交易所代码列表，如 ['binance']

        Returns:
            Dict: {exchange_code: {'status': str, 'new': int, 'updated': int, 'delisted': int, 'saved': int} | {'status': 'error', 'error': str}}

        Examples:
            >>> service = SpotFetcherService()
            >>> result = service.update_exchanges_manually(['binance'])
            >>> if result['binance']['status'] == 'success':
            ...     stats = result['binance']
            ...     print(f"新增: {stats['new']}, 更新: {stats['updated']}")
        """
        self.logger.info(f"开始手动更新交易所现货数据: {exchange_codes}")

        results = {}

        for exchange_code in exchange_codes:
            try:
                # 检查交易所代码是否有效
                if exchange_code not in self.clients:
                    results[exchange_code] = {
                        'status': 'error',
                        'error': f'不支持的交易所: {exchange_code}'
                    }
                    continue

                # 获取交易所实例
                exchange, created = Exchange.objects.get_or_create(
                    code=exchange_code,
                    defaults={
                        'name': exchange_code.capitalize(),
                        'enabled': True,
                        'announcement_url': '',
                    }
                )

                if created:
                    self.logger.info(f"自动创建交易所: {exchange.name} ({exchange.code})")

                # 获取现货数据
                client = self.clients[exchange_code]
                contracts = client.fetch_contracts()

                if not contracts:
                    self.logger.warning(f"未获取到 {exchange_code} 的现货交易对数据")
                    results[exchange_code] = {
                        'status': 'error',
                        'error': '未获取到现货交易对数据'
                    }
                    continue

                # 保存到数据库
                stats = self.save_contracts_to_database(exchange, contracts)

                results[exchange_code] = {
                    'status': 'success',
                    **stats
                }

                self.logger.info(f"成功更新 {exchange_code} 现货数据: {stats}")

            except Exception as e:
                error_msg = str(e)
                self.logger.error(f"更新 {exchange_code} 现货数据失败: {error_msg}")
                results[exchange_code] = {
                    'status': 'error',
                    'error': error_msg
                }

        return results

    def get_supported_exchanges(self) -> List[str]:
        """
        获取支持的交易所列表

        Returns:
            List[str]: 支持的交易所代码列表

        Examples:
            >>> service = SpotFetcherService()
            >>> exchanges = service.get_supported_exchanges()
            >>> print(f"支持的交易所: {exchanges}")
        """
        return list(self.clients.keys())
