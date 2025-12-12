"""市值/FDV数据更新服务"""
import logging
from typing import List, Dict, Optional
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from grid_trading.models import TokenMapping, MarketData, UpdateLog
from grid_trading.services.coingecko_client import CoingeckoClient


logger = logging.getLogger(__name__)


class MarketDataService:
    """市值/FDV数据更新服务

    职责:
    - 批量更新市值和FDV数据
    - 单个symbol数据更新（失败重试）
    - 记录UpdateLog审计日志
    """

    def __init__(self, coingecko_client: Optional[CoingeckoClient] = None):
        """初始化市场数据服务

        Args:
            coingecko_client: CoinGecko API客户端（可选）
        """
        self.coingecko_client = coingecko_client or CoingeckoClient()

    @transaction.atomic
    def update_all(self) -> Dict:
        """批量更新所有ready状态的symbol的市值/FDV数据

        工作流程:
        1. 查询TokenMapping中ready状态的记录（auto_matched/manual_confirmed）
        2. 分批调用CoinGecko API获取市场数据
        3. 更新或创建MarketData记录
        4. 记录UpdateLog批次日志

        Returns:
            统计字典:
            - total: 总symbol数
            - updated: 成功更新数
            - failed: 失败数
            - coverage: 覆盖率（成功数/总数）
            - batch_id: 批次UUID

        Example:
            >>> service = MarketDataService()
            >>> result = service.update_all()
            >>> print(result)
            {
                'total': 500,
                'updated': 478,
                'failed': 22,
                'coverage': 95.6,
                'batch_id': UUID('...')
            }
        """
        # 开始批次
        batch_id, _ = UpdateLog.log_batch_start(
            operation_type=UpdateLog.OperationType.MARKET_DATA_UPDATE
        )

        logger.info(f"[Batch {batch_id}] Starting market data update...")

        stats = {
            'total': 0,
            'updated': 0,
            'failed': 0,
            'coverage': 0.0,
            'batch_id': str(batch_id)
        }

        try:
            # 1. 查询ready状态的TokenMapping
            ready_mappings = TokenMapping.objects.filter(
                match_status__in=[
                    TokenMapping.MatchStatus.AUTO_MATCHED,
                    TokenMapping.MatchStatus.MANUAL_CONFIRMED
                ]
            ).exclude(coingecko_id__isnull=True).exclude(coingecko_id='')

            stats['total'] = ready_mappings.count()
            logger.info(f"Found {stats['total']} ready mappings to update")

            if stats['total'] == 0:
                logger.warning("No ready mappings found. Run generate_token_mapping first.")
                UpdateLog.log_batch_complete(
                    batch_id=batch_id,
                    operation_type=UpdateLog.OperationType.MARKET_DATA_UPDATE,
                    status=UpdateLog.Status.SUCCESS,
                    metadata={**stats, 'warning': 'No ready mappings'}
                )
                return stats

            # 2. 提取coingecko_id列表
            coingecko_ids = list(ready_mappings.values_list('coingecko_id', flat=True))

            # 3. 分批获取市场数据（自动处理限流）
            logger.info(f"Fetching market data for {len(coingecko_ids)} coins...")
            market_data_list = self.coingecko_client.fetch_market_data_batch(
                coingecko_ids=coingecko_ids,
                vs_currency='usd'
            )

            # 构建 coingecko_id -> market_data 映射
            market_data_dict = {item['id']: item for item in market_data_list}

            # 4. 更新MarketData记录
            fetched_at = timezone.now()

            for mapping in ready_mappings:
                symbol = mapping.symbol
                coingecko_id = mapping.coingecko_id

                # 查找对应的市场数据
                coin_data = market_data_dict.get(coingecko_id)

                if not coin_data:
                    logger.warning(f"No market data found for {symbol} ({coingecko_id})")
                    stats['failed'] += 1
                    UpdateLog.log_symbol_error(
                        batch_id=batch_id,
                        symbol=symbol,
                        operation_type=UpdateLog.OperationType.MARKET_DATA_UPDATE,
                        error_message=f"No market data returned from CoinGecko for {coingecko_id}"
                    )
                    continue

                try:
                    # 提取市值和FDV
                    market_cap = coin_data.get('market_cap')
                    fdv = coin_data.get('fully_diluted_valuation')

                    # 更新或创建MarketData
                    market_data, created = MarketData.objects.update_or_create(
                        symbol=symbol,
                        defaults={
                            'market_cap': Decimal(str(market_cap)) if market_cap else None,
                            'fully_diluted_valuation': Decimal(str(fdv)) if fdv else None,
                            'data_source': 'coingecko',
                            'fetched_at': fetched_at
                        }
                    )

                    stats['updated'] += 1
                    action = "Created" if created else "Updated"
                    logger.debug(
                        f"{action} market data for {symbol}: "
                        f"MC=${market_cap:,.0f}, FDV=${fdv:,.0f}" if market_cap else
                        f"{action} market data for {symbol}"
                    )

                except Exception as e:
                    logger.error(f"Failed to update market data for {symbol}: {e}")
                    stats['failed'] += 1
                    UpdateLog.log_symbol_error(
                        batch_id=batch_id,
                        symbol=symbol,
                        operation_type=UpdateLog.OperationType.MARKET_DATA_UPDATE,
                        error_message=str(e)
                    )

            # 5. 计算覆盖率
            stats['coverage'] = (stats['updated'] / stats['total'] * 100) if stats['total'] > 0 else 0

            # 6. 记录批次完成
            status = UpdateLog.Status.SUCCESS if stats['failed'] == 0 else UpdateLog.Status.PARTIAL_SUCCESS
            UpdateLog.log_batch_complete(
                batch_id=batch_id,
                operation_type=UpdateLog.OperationType.MARKET_DATA_UPDATE,
                status=status,
                metadata={
                    **stats,
                    'coverage_pct': f"{stats['coverage']:.1f}%"
                }
            )

            logger.info(
                f"[Batch {batch_id}] Market data update complete. "
                f"Updated: {stats['updated']}/{stats['total']} ({stats['coverage']:.1f}%), "
                f"Failed: {stats['failed']}"
            )

            return stats

        except Exception as e:
            # 记录批次失败
            UpdateLog.log_batch_complete(
                batch_id=batch_id,
                operation_type=UpdateLog.OperationType.MARKET_DATA_UPDATE,
                status=UpdateLog.Status.FAILED,
                metadata={'error': str(e), **stats}
            )
            logger.error(f"[Batch {batch_id}] Market data update failed: {e}")
            raise

    def update_single(self, symbol: str) -> bool:
        """更新单个symbol的市值/FDV数据

        用于:
        - 失败重试
        - 手动刷新指定symbol的数据

        Args:
            symbol: 币安交易对symbol（如 "BTCUSDT"）

        Returns:
            是否更新成功

        Example:
            >>> service = MarketDataService()
            >>> success = service.update_single("BTCUSDT")
            >>> print(success)
            True
        """
        logger.info(f"Updating market data for {symbol}...")

        try:
            # 1. 查询TokenMapping
            try:
                mapping = TokenMapping.objects.get(symbol=symbol)
            except TokenMapping.DoesNotExist:
                logger.error(f"TokenMapping not found for {symbol}")
                return False

            # 2. 检查是否ready
            if not mapping.is_ready_for_update():
                logger.error(
                    f"TokenMapping not ready for {symbol}. "
                    f"Status: {mapping.match_status}, ID: {mapping.coingecko_id}"
                )
                return False

            # 3. 获取市场数据
            coingecko_id = mapping.coingecko_id
            market_data_list = self.coingecko_client.fetch_market_data(
                coingecko_ids=[coingecko_id],
                vs_currency='usd'
            )

            if not market_data_list or len(market_data_list) == 0:
                logger.error(f"No market data returned for {symbol} ({coingecko_id})")
                return False

            coin_data = market_data_list[0]

            # 4. 更新MarketData
            market_cap = coin_data.get('market_cap')
            fdv = coin_data.get('fully_diluted_valuation')

            market_data, created = MarketData.objects.update_or_create(
                symbol=symbol,
                defaults={
                    'market_cap': Decimal(str(market_cap)) if market_cap else None,
                    'fully_diluted_valuation': Decimal(str(fdv)) if fdv else None,
                    'data_source': 'coingecko',
                    'fetched_at': timezone.now()
                }
            )

            action = "Created" if created else "Updated"
            logger.info(
                f"{action} market data for {symbol}: "
                f"MC=${market_cap:,.0f}, FDV=${fdv:,.0f}" if market_cap else
                f"{action} market data for {symbol}"
            )

            return True

        except Exception as e:
            logger.error(f"Failed to update market data for {symbol}: {e}")
            return False
