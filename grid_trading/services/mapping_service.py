"""映射服务 - 管理币安symbol与CoinGecko ID的映射关系"""
import logging
from typing import List, Dict, Optional, Tuple
from binance.client import Client as BinanceClient
from django.db import transaction
from django.utils import timezone

from grid_trading.models import TokenMapping, UpdateLog
from grid_trading.services.coingecko_client import CoingeckoClient


logger = logging.getLogger(__name__)


class MappingService:
    """映射服务

    职责:
    - 获取币安USDT永续合约列表
    - 匹配CoinGecko ID（基于symbol）
    - 处理同名冲突（消歧逻辑）
    - 生成和更新TokenMapping记录
    """

    def __init__(
        self,
        coingecko_client: Optional[CoingeckoClient] = None,
        binance_client: Optional[BinanceClient] = None
    ):
        """初始化映射服务

        Args:
            coingecko_client: CoinGecko API客户端（可选）
            binance_client: 币安API客户端（可选）
        """
        self.coingecko_client = coingecko_client or CoingeckoClient()
        self.binance_client = binance_client  # 延迟初始化，避免API密钥问题

    def get_binance_usdt_perpetuals(self) -> List[Dict]:
        """获取币安USDT永续合约列表

        使用币安API的futures_exchange_info端点

        Returns:
            合约列表，每个元素包含:
            - symbol: 交易对symbol（如 "BTCUSDT"）
            - base_asset: 基础资产（如 "BTC"）
            - quote_asset: 计价资产（固定为 "USDT"）
            - status: 合约状态（只返回TRADING状态）

        Example:
            >>> service = MappingService()
            >>> contracts = service.get_binance_usdt_perpetuals()
            >>> print(contracts[0])
            {'symbol': 'BTCUSDT', 'base_asset': 'BTC', 'quote_asset': 'USDT', 'status': 'TRADING'}
        """
        if self.binance_client is None:
            # 延迟初始化币安客户端（使用默认API配置）
            # 使用python-binance库的Client类（已在Line 4导入为BinanceClient）
            self.binance_client = BinanceClient()

        logger.info("Fetching Binance USDT perpetual contracts...")

        try:
            exchange_info = self.binance_client.futures_exchange_info()
            symbols = exchange_info.get('symbols', [])

            # 过滤USDT永续合约（TRADING状态）
            usdt_perpetuals = [
                {
                    'symbol': s['symbol'],
                    'base_asset': s['baseAsset'],
                    'quote_asset': s['quoteAsset'],
                    'status': s['status']
                }
                for s in symbols
                if s['quoteAsset'] == 'USDT'
                and s['contractType'] == 'PERPETUAL'
                and s['status'] == 'TRADING'
            ]

            logger.info(f"Found {len(usdt_perpetuals)} active USDT perpetual contracts")
            return usdt_perpetuals

        except Exception as e:
            logger.error(f"Failed to fetch Binance contracts: {e}")
            raise

    def match_coingecko_id(
        self,
        base_token: str,
        coins_list: List[Dict]
    ) -> Tuple[Optional[str], List[str], str]:
        """匹配CoinGecko ID（基于symbol）

        匹配逻辑:
        1. 精确匹配: symbol小写完全相等
        2. 同名冲突: 如果有多个匹配，调用_resolve_conflict消歧

        Args:
            base_token: 基础代币symbol（如 "BTC"）
            coins_list: CoinGecko完整代币列表

        Returns:
            元组 (coingecko_id, alternatives, match_status):
            - coingecko_id: 匹配的CoinGecko ID（唯一匹配时）或None
            - alternatives: 所有候选ID列表
            - match_status: 匹配状态（auto_matched/needs_review）

        Example:
            >>> service = MappingService()
            >>> coins = [{'id': 'bitcoin', 'symbol': 'btc', 'name': 'Bitcoin'}]
            >>> id, alts, status = service.match_coingecko_id('BTC', coins)
            >>> print(id, status)
            'bitcoin' 'auto_matched'
        """
        base_token_lower = base_token.lower()

        # 1. 精确匹配symbol
        candidates = [
            coin for coin in coins_list
            if coin['symbol'].lower() == base_token_lower
        ]

        if not candidates:
            logger.debug(f"No CoinGecko match found for {base_token}")
            return None, [], TokenMapping.MatchStatus.NEEDS_REVIEW

        # 2. 唯一匹配
        if len(candidates) == 1:
            coingecko_id = candidates[0]['id']
            logger.debug(f"Unique match: {base_token} → {coingecko_id}")
            return coingecko_id, [coingecko_id], TokenMapping.MatchStatus.AUTO_MATCHED

        # 3. 同名冲突 - 调用消歧逻辑
        alternatives = [c['id'] for c in candidates]
        logger.debug(f"Multiple matches for {base_token}: {alternatives}")

        resolved_id, status = self._resolve_conflict(base_token, candidates)
        return resolved_id, alternatives, status

    def _resolve_conflict(
        self,
        base_token: str,
        candidates: List[Dict]
    ) -> Tuple[Optional[str], str]:
        """同名冲突消歧逻辑

        优先级链:
        1. 交易量排序: 获取市场数据，选择24h交易量最大的
        2. 市值排名: 如果交易量API失败，使用市值排名（假设高市值=主流币）
        3. needs_review: 如果两者都失败，标记为需要人工审核

        Args:
            base_token: 基础代币symbol
            candidates: 候选CoinGecko代币列表

        Returns:
            元组 (coingecko_id, match_status)

        Note:
            - 这个方法会调用CoinGecko API获取市场数据
            - 限流考虑: 同名冲突场景较少，不会触发大规模调用
        """
        logger.info(f"Resolving conflict for {base_token} ({len(candidates)} candidates)...")

        try:
            # 策略1: 使用交易量排序
            ids = [c['id'] for c in candidates]
            market_data = self.coingecko_client.fetch_market_data(
                coingecko_ids=ids,
                order='volume_desc',  # 按交易量降序
                per_page=len(ids)
            )

            if market_data and len(market_data) > 0:
                # 选择交易量最大的
                top_coin = market_data[0]
                coingecko_id = top_coin['id']
                logger.info(
                    f"Resolved by volume: {base_token} → {coingecko_id} "
                    f"(24h_volume: ${top_coin.get('total_volume', 0):,.0f})"
                )
                return coingecko_id, TokenMapping.MatchStatus.AUTO_MATCHED

        except Exception as e:
            logger.warning(f"Volume-based resolution failed for {base_token}: {e}")

        try:
            # 策略2: 使用市值排名
            market_data = self.coingecko_client.fetch_market_data(
                coingecko_ids=ids,
                order='market_cap_desc',  # 按市值降序
                per_page=len(ids)
            )

            if market_data and len(market_data) > 0:
                # 选择市值最大的
                top_coin = market_data[0]
                coingecko_id = top_coin['id']
                logger.info(
                    f"Resolved by market cap: {base_token} → {coingecko_id} "
                    f"(market_cap: ${top_coin.get('market_cap', 0):,.0f})"
                )
                return coingecko_id, TokenMapping.MatchStatus.AUTO_MATCHED

        except Exception as e:
            logger.warning(f"Market cap-based resolution failed for {base_token}: {e}")

        # 策略3: 无法自动消歧，需要人工审核
        logger.warning(
            f"Cannot auto-resolve conflict for {base_token}. "
            f"Candidates: {[c['id'] for c in candidates]}. Needs manual review."
        )
        return None, TokenMapping.MatchStatus.NEEDS_REVIEW

    def generate_mappings(self, force_refresh: bool = False) -> Dict:
        """生成完整的映射关系

        工作流程:
        1. 获取币安USDT永续合约列表
        2. 获取CoinGecko完整代币列表
        3. 逐个匹配并创建TokenMapping记录
        4. 记录UpdateLog批次日志

        Args:
            force_refresh: 是否强制刷新已存在的映射（默认False，跳过已存在记录）

        Returns:
            统计字典:
            - total: 总合约数
            - created: 新创建记录数
            - skipped: 跳过记录数
            - auto_matched: 自动匹配成功数
            - needs_review: 需要人工审核数
            - batch_id: 批次UUID

        Example:
            >>> service = MappingService()
            >>> result = service.generate_mappings()
            >>> print(result)
            {
                'total': 531,
                'created': 531,
                'skipped': 0,
                'auto_matched': 450,
                'needs_review': 81,
                'batch_id': UUID('...')
            }
        """
        # 开始批次
        batch_id, _ = UpdateLog.log_batch_start(
            operation_type=UpdateLog.OperationType.MAPPING_GENERATION,
            metadata={'force_refresh': force_refresh}
        )

        logger.info(f"[Batch {batch_id}] Starting mapping generation...")

        stats = {
            'total': 0,
            'created': 0,
            'skipped': 0,
            'auto_matched': 0,
            'needs_review': 0,
            'batch_id': str(batch_id)
        }

        try:
            # 1. 获取币安合约列表
            contracts = self.get_binance_usdt_perpetuals()
            stats['total'] = len(contracts)

            # 2. 获取CoinGecko代币列表
            logger.info("Fetching CoinGecko coins list...")
            coins_list = self.coingecko_client.fetch_coins_list()
            logger.info(f"Fetched {len(coins_list)} coins from CoinGecko")

            # 3. 逐个匹配并创建记录
            for contract in contracts:
                symbol = contract['symbol']
                base_token = contract['base_asset']

                try:
                    # 跳过已存在记录（除非force_refresh）
                    if not force_refresh and TokenMapping.objects.filter(symbol=symbol).exists():
                        logger.debug(f"Skipping existing mapping: {symbol}")
                        stats['skipped'] += 1
                        continue

                    # 匹配CoinGecko ID（API调用，不在事务内）
                    coingecko_id, alternatives, match_status = self.match_coingecko_id(
                        base_token, coins_list
                    )

                    # 创建或更新TokenMapping（单个记录的原子操作）
                    with transaction.atomic():
                        mapping, created = TokenMapping.objects.update_or_create(
                            symbol=symbol,
                            defaults={
                                'base_token': base_token,
                                'coingecko_id': coingecko_id,
                                'match_status': match_status,
                                'alternatives': alternatives if len(alternatives) > 1 else None,
                            }
                        )

                    if created:
                        stats['created'] += 1
                        logger.debug(f"Created mapping: {symbol} → {coingecko_id or 'None'} ({match_status})")

                    # 统计匹配状态
                    if match_status == TokenMapping.MatchStatus.AUTO_MATCHED:
                        stats['auto_matched'] += 1
                    elif match_status == TokenMapping.MatchStatus.NEEDS_REVIEW:
                        stats['needs_review'] += 1

                except Exception as e:
                    # 单个symbol失败不影响其他symbol
                    logger.error(f"Failed to process {symbol}: {e}")
                    UpdateLog.log_symbol_error(
                        batch_id=batch_id,
                        symbol=symbol,
                        error_message=str(e)
                    )
                    continue

            # 4. 记录批次完成
            success_rate = (stats['auto_matched'] / stats['total'] * 100) if stats['total'] > 0 else 0
            UpdateLog.log_batch_complete(
                batch_id=batch_id,
                operation_type=UpdateLog.OperationType.MAPPING_GENERATION,
                status=UpdateLog.Status.SUCCESS,
                metadata={
                    **stats,
                    'success_rate': f"{success_rate:.1f}%"
                }
            )

            logger.info(
                f"[Batch {batch_id}] Mapping generation complete. "
                f"Total: {stats['total']}, Created: {stats['created']}, "
                f"Auto-matched: {stats['auto_matched']} ({success_rate:.1f}%), "
                f"Needs review: {stats['needs_review']}"
            )

            return stats

        except Exception as e:
            # 记录批次失败
            UpdateLog.log_batch_complete(
                batch_id=batch_id,
                operation_type=UpdateLog.OperationType.MAPPING_GENERATION,
                status=UpdateLog.Status.FAILED,
                metadata={'error': str(e), **stats}
            )
            logger.error(f"[Batch {batch_id}] Mapping generation failed: {e}")
            raise

    def update_mapping_for_symbols(
        self,
        symbols: List[str],
        force_overwrite: bool = False
    ) -> Dict:
        """更新指定symbol的映射关系

        用于:
        - 新合约上线后手动添加映射
        - 修正错误的映射关系
        - 手动确认needs_review状态的映射

        Args:
            symbols: 要更新的symbol列表
            force_overwrite: 是否强制覆盖现有映射（默认False，会提示确认）

        Returns:
            统计字典:
            - total: 总更新数
            - updated: 成功更新数
            - failed: 失败数
            - not_found: 未找到数
            - batch_id: 批次UUID
        """
        batch_id, _ = UpdateLog.log_batch_start(
            operation_type=UpdateLog.OperationType.MAPPING_UPDATE,
            metadata={'symbols': symbols, 'force_overwrite': force_overwrite}
        )

        logger.info(f"[Batch {batch_id}] Updating mappings for {len(symbols)} symbols...")

        stats = {
            'total': len(symbols),
            'updated': 0,
            'failed': 0,
            'not_found': 0,
            'batch_id': str(batch_id)
        }

        # 获取CoinGecko代币列表（用于重新匹配）
        coins_list = self.coingecko_client.fetch_coins_list()

        for symbol in symbols:
            try:
                # 检查symbol是否存在于数据库
                try:
                    mapping = TokenMapping.objects.get(symbol=symbol)
                    base_token = mapping.base_token
                except TokenMapping.DoesNotExist:
                    logger.warning(f"Symbol not found in database: {symbol}")
                    stats['not_found'] += 1
                    UpdateLog.log_symbol_error(
                        batch_id=batch_id,
                        symbol=symbol,
                        operation_type=UpdateLog.OperationType.MAPPING_UPDATE,
                        error_message="Symbol not found in database"
                    )
                    continue

                # 重新匹配CoinGecko ID
                new_id, alternatives, match_status = self.match_coingecko_id(
                    base_token, coins_list
                )

                # 检查是否需要覆盖
                if mapping.coingecko_id and mapping.coingecko_id != new_id and not force_overwrite:
                    logger.warning(
                        f"Mapping exists for {symbol}: {mapping.coingecko_id} → {new_id}. "
                        f"Use force_overwrite=True to update."
                    )
                    stats['failed'] += 1
                    continue

                # 更新映射
                old_id = mapping.coingecko_id
                mapping.coingecko_id = new_id
                mapping.match_status = match_status
                mapping.alternatives = alternatives if len(alternatives) > 1 else None
                mapping.save()

                stats['updated'] += 1
                logger.info(f"Updated mapping: {symbol} {old_id} → {new_id} ({match_status})")

            except Exception as e:
                logger.error(f"Failed to update mapping for {symbol}: {e}")
                stats['failed'] += 1
                UpdateLog.log_symbol_error(
                    batch_id=batch_id,
                    symbol=symbol,
                    operation_type=UpdateLog.OperationType.MAPPING_UPDATE,
                    error_message=str(e)
                )

        # 记录批次完成
        status = UpdateLog.Status.SUCCESS if stats['failed'] == 0 else UpdateLog.Status.PARTIAL_SUCCESS
        UpdateLog.log_batch_complete(
            batch_id=batch_id,
            operation_type=UpdateLog.OperationType.MAPPING_UPDATE,
            status=status,
            metadata=stats
        )

        logger.info(
            f"[Batch {batch_id}] Mapping update complete. "
            f"Updated: {stats['updated']}/{stats['total']}, "
            f"Failed: {stats['failed']}, Not found: {stats['not_found']}"
        )

        return stats
