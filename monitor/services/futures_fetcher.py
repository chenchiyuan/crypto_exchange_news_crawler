"""
合约数据获取服务
负责协调所有交易所API客户端，获取和更新合约数据
"""
import logging
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal

from django.utils import timezone
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from monitor.api_clients.binance import BinanceFuturesClient
from monitor.api_clients.hyperliquid import HyperliquidFuturesClient
from monitor.api_clients.bybit import BybitFuturesClient
from monitor.models import Exchange, FuturesContract, FuturesListingNotification, FuturesMarketIndicators
from config.futures_config import RETRY_CONFIG, PERFORMANCE_GOALS, INITIAL_DEPLOYMENT_FLAG

logger = logging.getLogger(__name__)


class FuturesFetcherService:
    """合约数据获取服务"""

    def __init__(self):
        """初始化服务"""
        self.clients = {
            'binance': BinanceFuturesClient(),
            'hyperliquid': HyperliquidFuturesClient(),
            'bybit': BybitFuturesClient(),
        }
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @retry(
        stop=stop_after_attempt(RETRY_CONFIG['max_attempts']),
        wait=wait_exponential(multiplier=RETRY_CONFIG['multiplier'], min=RETRY_CONFIG['min_wait'], max=RETRY_CONFIG['max_wait']),
        retry=retry_if_exception_type((Exception,))
    )
    def fetch_from_all_exchanges(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        从所有交易所获取合约数据

        Returns:
            Dict: {exchange_code: contracts_list}

        Raises:
            Exception: 如果所有交易所都失败
        """
        self.logger.info("开始从所有交易所获取合约数据")

        all_contracts = {}
        errors = []

        # 并行获取所有交易所数据
        for exchange_code, client in self.clients.items():
            try:
                self.logger.info(f"正在获取 {exchange_code} 数据")
                contracts = client.fetch_contracts()
                all_contracts[exchange_code] = contracts
                self.logger.info(f"成功从 {exchange_code} 获取 {len(contracts)} 个合约")
            except Exception as e:
                error_msg = f"从 {exchange_code} 获取数据失败: {str(e)}"
                self.logger.error(error_msg)
                errors.append(error_msg)
                all_contracts[exchange_code] = []  # 设置空列表

        if not all_contracts or all(len(contracts) == 0 for contracts in all_contracts.values()):
            self.logger.error("所有交易所数据获取失败")
            raise Exception(f"所有交易所数据获取失败: {errors}")

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
    ) -> Tuple[int, int, int]:
        """
        保存合约数据到数据库

        Args:
            exchange: 交易所实例
            contracts: 合约数据列表

        Returns:
            Tuple[saved_contracts, new_count, updated_count]

        Raises:
            Exception: 如果保存失败
        """
        self.logger.info(f"开始保存 {exchange.name} 的 {len(contracts)} 个合约到数据库")

        if not contracts:
            self.logger.info("没有合约需要保存")
            return 0, 0, 0

        saved_contracts = 0
        new_count = 0
        updated_count = 0

        for contract_data in contracts:
            try:
                symbol = contract_data['symbol']
                current_price = contract_data['current_price']
                contract_type = contract_data.get('contract_type', 'perpetual')

                # 获取或创建合约
                obj, created = FuturesContract.objects.get_or_create(
                    exchange=exchange,
                    symbol=symbol,
                    defaults={
                        'current_price': current_price,
                        'contract_type': contract_type,
                        'first_seen': timezone.now(),
                    }
                )

                if created:
                    new_count += 1
                    self.logger.info(f"新合约: {symbol}")
                else:
                    # 更新现有合约
                    obj.current_price = current_price
                    # contract_type 不应变化，保持不变
                    updated_count += 1
                    self.logger.debug(f"更新合约: {symbol}")

                obj.save()
                saved_contracts += 1

            except Exception as e:
                self.logger.error(f"保存合约失败 {contract_data.get('symbol', 'unknown')}: {str(e)}")
                raise

        self.logger.info(
            f"保存完成: 总计 {saved_contracts}, 新增 {new_count}, 更新 {updated_count}"
        )

        return saved_contracts, new_count, updated_count

    def save_contracts_with_indicators(
        self,
        exchange: Exchange,
        contracts: List[Dict[str, Any]]
    ) -> Tuple[int, int, int, int]:
        """
        保存合约和市场指标数据到数据库

        Args:
            exchange: 交易所实例
            contracts: 合约及市场指标数据列表

        Returns:
            Tuple[saved_contracts, new_count, updated_count, indicators_saved]

        Raises:
            Exception: 如果保存失败
        """
        self.logger.info(f"开始保存 {exchange.name} 的 {len(contracts)} 个合约及市场指标到数据库")

        if not contracts:
            self.logger.info("没有合约需要保存")
            return 0, 0, 0, 0

        saved_contracts = 0
        new_count = 0
        updated_count = 0
        indicators_saved = 0

        for contract_data in contracts:
            try:
                symbol = contract_data['symbol']
                current_price = contract_data['current_price']
                contract_type = contract_data.get('contract_type', 'perpetual')

                # 1. 保存/更新合约
                contract, created = FuturesContract.objects.get_or_create(
                    exchange=exchange,
                    symbol=symbol,
                    defaults={
                        'current_price': current_price,
                        'contract_type': contract_type,
                        'first_seen': timezone.now(),
                        'status': 'active'
                    }
                )

                if created:
                    new_count += 1
                    self.logger.info(f"新合约: {symbol}")
                else:
                    # 更新现有合约
                    contract.current_price = current_price
                    contract.status = 'active'
                    contract.save()
                    updated_count += 1
                    self.logger.debug(f"更新合约: {symbol}")

                saved_contracts += 1

                # 2. 保存/更新市场指标（如果有）
                if self._has_market_indicators(contract_data):
                    try:
                        self._save_market_indicators(contract, contract_data)
                        indicators_saved += 1
                    except Exception as e:
                        self.logger.warning(f"保存市场指标失败 {symbol}: {str(e)}")
                        # 指标保存失败不影响合约保存

            except Exception as e:
                self.logger.error(f"保存合约失败 {contract_data.get('symbol', 'unknown')}: {str(e)}")
                raise

        self.logger.info(
            f"保存完成: 总计 {saved_contracts}, 新增 {new_count}, 更新 {updated_count}, 指标 {indicators_saved}"
        )

        return saved_contracts, new_count, updated_count, indicators_saved

    def _has_market_indicators(self, contract_data: Dict[str, Any]) -> bool:
        """
        检查合约数据中是否包含市场指标

        Args:
            contract_data: 合约数据

        Returns:
            是否包含市场指标
        """
        indicator_fields = ['open_interest', 'volume_24h', 'funding_rate']
        return any(field in contract_data for field in indicator_fields)

    def _save_market_indicators(self, contract: FuturesContract, contract_data: Dict[str, Any]):
        """
        保存市场指标到数据库

        Args:
            contract: 合约实例
            contract_data: 包含市场指标的合约数据
        """
        # 计算年化资金费率
        funding_rate = contract_data.get('funding_rate')
        funding_interval_hours = contract_data.get('funding_interval_hours', 8)
        funding_rate_annual = None

        if funding_rate is not None:
            funding_rate_annual = self._calculate_annual_funding_rate(
                funding_rate,
                funding_interval_hours
            )

        # 保存/更新市场指标
        FuturesMarketIndicators.objects.update_or_create(
            futures_contract=contract,
            defaults={
                'open_interest': contract_data.get('open_interest'),
                'volume_24h': contract_data.get('volume_24h'),
                'funding_rate': funding_rate,
                'funding_rate_annual': funding_rate_annual,
                'next_funding_time': contract_data.get('next_funding_time'),
                'funding_interval_hours': funding_interval_hours,
                'funding_rate_cap': contract_data.get('funding_rate_cap'),
                'funding_rate_floor': contract_data.get('funding_rate_floor'),
            }
        )

    def _calculate_annual_funding_rate(
        self,
        current_rate: Decimal,
        interval_hours: int
    ) -> Decimal:
        """
        计算年化资金费率

        公式: (当前费率 / 间隔小时数 × 24) × 365

        Args:
            current_rate: 当前资金费率
            interval_hours: 资金费率间隔（小时）

        Returns:
            年化资金费率

        Examples:
            >>> _calculate_annual_funding_rate(Decimal('0.0001'), 8)
            Decimal('0.1095')  # 10.95%

            >>> _calculate_annual_funding_rate(Decimal('0.01'), 1)
            Decimal('87.60')  # 8760%
        """
        if current_rate is None or interval_hours <= 0:
            return Decimal('0')

        try:
            # 计算每天的费率
            daily_rate = (current_rate / Decimal(str(interval_hours))) * Decimal('24')

            # 计算年化费率
            annual_rate = daily_rate * Decimal('365')

            return annual_rate

        except Exception as e:
            self.logger.error(f"计算年化资金费率失败: {e}")
            return Decimal('0')

    def update_contracts_and_detect_delisted(
        self,
        exchange: Exchange,
        contracts: List[Dict[str, Any]]
    ) -> Tuple[int, int, int, int]:
        """
        更新合约并检测已下线合约

        Args:
            exchange: 交易所实例
            contracts: 新的合约数据

        Returns:
            Tuple[saved_contracts, new_count, updated_count, delisted_count]
        """
        self.logger.info(f"开始更新 {exchange.name} 的合约数据")

        # 1. 保存/更新合约
        saved_contracts, new_count, updated_count = self.save_contracts_to_database(exchange, contracts)

        # 2. 检测已下线合约
        # 获取当前数据库中的活跃合约
        current_symbols = {c['symbol'] for c in contracts}
        database_active_contracts = FuturesContract.objects.filter(
            exchange=exchange,
            status='active'
        )

        delisted_count = 0
        for db_contract in database_active_contracts:
            if db_contract.symbol not in current_symbols:
                # 标记为已下线
                db_contract.status = 'delisted'
                db_contract.save()
                delisted_count += 1
                self.logger.info(f"检测到下线合约: {db_contract.symbol}")

        self.logger.info(
            f"更新完成: 保存 {saved_contracts}, 新增 {new_count}, 更新 {updated_count}, 下线 {delisted_count}"
        )

        return saved_contracts, new_count, updated_count, delisted_count

    def update_all_exchanges(self) -> Tuple[int, int, int, int, int]:
        """
        更新所有交易所的合约数据

        Returns:
            Tuple[total_saved, new_count, updated_count, delisted_count, errors]

        Raises:
            Exception: 如果所有交易所都失败
        """
        self.logger.info("开始更新所有交易所的合约数据")

        total_saved = 0
        total_new = 0
        total_updated = 0
        total_delisted = 0
        total_errors = 0
        start_time = datetime.now()

        try:
            # 1. 从所有交易所获取数据
            all_contracts = self.fetch_from_all_exchanges()

            # 2. 逐个交易所保存数据
            for exchange_code, contracts in all_contracts.items():
                if not contracts:
                    self.logger.warning(f"交易所 {exchange_code} 没有合约数据，跳过")
                    continue

                try:
                    # 获取交易所实例
                    exchange = Exchange.objects.get(code=exchange_code)

                    # 保存数据
                    saved, new_count, updated_count, delisted_count = self.update_contracts_and_detect_delisted(
                        exchange, contracts
                    )

                    total_saved += saved
                    total_new += new_count
                    total_updated += updated_count
                    total_delisted += delisted_count

                except Exchange.DoesNotExist:
                    error_msg = f"交易所 {exchange_code} 不存在，跳过"
                    self.logger.error(error_msg)
                    total_errors += 1
                except Exception as e:
                    error_msg = f"处理 {exchange_code} 失败: {str(e)}"
                    self.logger.error(error_msg)
                    total_errors += 1

        except Exception as e:
            self.logger.error(f"更新所有交易所失败: {str(e)}")
            raise

        # 3. 检查性能
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        self.logger.info(
            f"更新完成: 总计 {total_saved}, 新增 {total_new}, 更新 {total_updated}, "
            f"下线 {total_delisted}, 错误 {total_errors}, 耗时 {duration:.2f}s"
        )

        # 4. 检查性能目标
        if duration > PERFORMANCE_GOALS['max_fetch_time']:
            self.logger.warning(
                f"性能警告: 耗时 {duration:.2f}s 超过目标 {PERFORMANCE_GOALS['max_fetch_time']}s"
            )

        return total_saved, total_new, total_updated, total_delisted, total_errors

    def update_exchanges_manually(self, exchange_codes: List[str]) -> Dict[str, Any]:
        """
        手动更新指定交易所

        Args:
            exchange_codes: 要更新的交易所代码列表

        Returns:
            Dict: 更新结果
        """
        self.logger.info(f"开始手动更新交易所: {exchange_codes}")

        results = {}
        start_time = datetime.now()

        for exchange_code in exchange_codes:
            if exchange_code not in self.clients:
                self.logger.error(f"未知交易所: {exchange_code}")
                results[exchange_code] = {
                    'status': 'error',
                    'error': f'未知交易所: {exchange_code}'
                }
                continue

            try:
                # 获取客户端
                client = self.clients[exchange_code]

                # 获取合约数据
                contracts = client.fetch_contracts()

                # 获取交易所实例
                exchange = Exchange.objects.get(code=exchange_code)

                # 保存数据
                saved, new_count, updated_count, delisted_count = self.update_contracts_and_detect_delisted(
                    exchange, contracts
                )

                results[exchange_code] = {
                    'status': 'success',
                    'saved': saved,
                    'new': new_count,
                    'updated': updated_count,
                    'delisted': delisted_count
                }

            except Exchange.DoesNotExist:
                error_msg = f"交易所 {exchange_code} 在数据库中不存在"
                self.logger.error(error_msg)
                results[exchange_code] = {
                    'status': 'error',
                    'error': error_msg
                }
            except Exception as e:
                error_msg = f"更新 {exchange_code} 失败: {str(e)}"
                self.logger.error(error_msg)
                results[exchange_code] = {
                    'status': 'error',
                    'error': str(e)
                }

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        self.logger.info(f"手动更新完成，耗时 {duration:.2f}s")
        return results

    def get_exchange_contract_count(self, exchange_code: str) -> int:
        """
        获取指定交易所的合约数量

        Args:
            exchange_code: 交易所代码

        Returns:
            合约数量
        """
        try:
            exchange = Exchange.objects.get(code=exchange_code)
            return FuturesContract.objects.filter(exchange=exchange).count()
        except Exchange.DoesNotExist:
            return 0

    def get_all_exchanges_contract_count(self) -> Dict[str, int]:
        """
        获取所有交易所的合约数量

        Returns:
            Dict: {exchange_code: count}
        """
        result = {}
        for exchange_code in self.clients.keys():
            result[exchange_code] = self.get_exchange_contract_count(exchange_code)
        return result

    def detect_new_listings(self) -> List[FuturesContract]:
        """
        检测新上线的合约

        条件: first_seen == last_updated (仅创建一次)

        Returns:
            新上线合约列表
        """
        self.logger.info("检测新上线的合约")

        # 检查初始部署标识
        if not self._is_initial_deployment_completed():
            self.logger.info("初始部署阶段，不发送新合约通知")
            return []

        # 查询新上线合约 (first_seen == last_updated 表示刚刚创建)
        threshold = timezone.now() - timedelta(minutes=10)  # 10分钟内的
        new_contracts = FuturesContract.objects.filter(
            first_seen__gte=threshold,
            last_updated__lte=timezone.now(),
            status='active'
        )

        # 过滤已发送过通知的合约
        notified_symbols = set(
            FuturesListingNotification.objects.values_list('futures_contract__symbol', flat=True)
        )

        result = [
            contract for contract in new_contracts
            if contract.symbol not in notified_symbols
        ]

        self.logger.info(f"检测到 {len(result)} 个新上线合约")

        return result

    def _is_initial_deployment_completed(self) -> bool:
        """
        检查初始部署是否完成

        Returns:
            是否完成
        """
        import os
        return os.path.exists(INITIAL_DEPLOYMENT_FLAG)

    def mark_initial_deployment_completed(self):
        """标记初始部署已完成"""
        import os
        from config.futures_config import INITIAL_DEPLOYMENT_FLAG

        try:
            # 创建标记文件
            with open(INITIAL_DEPLOYMENT_FLAG, 'w') as f:
                f.write(f'Initial deployment completed at {datetime.now()}')
            self.logger.info("标记初始部署已完成")
        except Exception as e:
            self.logger.error(f"标记初始部署失败: {str(e)}")

    def get_contract_statistics(self) -> Dict[str, Any]:
        """
        获取合约统计信息

        Returns:
            统计信息
        """
        stats = {
            'total_contracts': 0,
            'active_contracts': 0,
            'delisted_contracts': 0,
            'by_exchange': {}
        }

        # 按交易所统计
        for exchange_code, client in self.clients.items():
            try:
                exchange = Exchange.objects.get(code=exchange_code)

                total = FuturesContract.objects.filter(exchange=exchange).count()
                active = FuturesContract.objects.filter(exchange=exchange, status='active').count()
                delisted = FuturesContract.objects.filter(exchange=exchange, status='delisted').count()

                stats['by_exchange'][exchange_code] = {
                    'total': total,
                    'active': active,
                    'delisted': delisted
                }

                stats['total_contracts'] += total
                stats['active_contracts'] += active
                stats['delisted_contracts'] += delisted

            except Exchange.DoesNotExist:
                self.logger.warning(f"交易所 {exchange_code} 不存在，跳过统计")

        return stats

    def cleanup_old_delisted_contracts(self, days: int = 90) -> int:
        """
        清理旧的已下线合约

        Args:
            days: 保留天数

        Returns:
            清理数量
        """
        cutoff_date = timezone.now() - timedelta(days=days)

        old_contracts = FuturesContract.objects.filter(
            status='delisted',
            last_updated__lt=cutoff_date
        )

        count = old_contracts.count()

        if count > 0:
            old_contracts.delete()
            self.logger.info(f"清理了 {count} 个已下线的旧合约")

        return count
