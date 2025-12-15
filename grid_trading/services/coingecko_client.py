"""CoinGecko API客户端 - 封装API调用、限流和重试逻辑"""
import logging
import time
from typing import List, Dict, Optional
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from django.conf import settings


logger = logging.getLogger(__name__)


class CoinGeckoRateLimitError(Exception):
    """CoinGecko API限流错误"""
    pass


class CoinGeckoAPIError(Exception):
    """CoinGecko API通用错误"""
    pass


class CoingeckoClient:
    """CoinGecko API客户端

    功能:
    - API封装: 统一处理HTTP请求和响应
    - 限流处理: 批量250个symbol + 60s延迟
    - 重试机制: 使用tenacity处理429/503错误
    - 错误处理: 统一异常类型
    """

    BASE_URL = "https://api.coingecko.com/api/v3"

    # 限流配置（Demo API: 10 calls/minute, max 100 results per call）
    BATCH_SIZE = 100  # 每批查询的symbol数量（免费API单次最多返回100个结果）
    BATCH_DELAY = 6  # 批次间延迟（秒）- Demo API限制为10 calls/minute，即每6秒1次

    # 重试配置
    MAX_RETRIES = 3
    RETRY_WAIT_MULTIPLIER = 2  # 指数退避倍数（2s, 4s, 8s）
    RETRY_WAIT_MAX = 60  # 最大等待时间（秒）

    def __init__(self, api_key: Optional[str] = None):
        """初始化CoinGecko客户端

        Args:
            api_key: CoinGecko API密钥（可选，优先使用参数，否则从settings读取）
        """
        self.api_key = api_key or settings.COINGECKO_API_KEY

        if not self.api_key:
            logger.warning("CoinGecko API key not configured. Some features may be limited.")

        self.session = requests.Session()
        if self.api_key:
            # 根据CoinGecko API文档，免费Demo API使用x-cg-demo-api-key header
            self.session.headers.update({
                'x-cg-demo-api-key': self.api_key
            })

    def _request(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        method: str = "GET"
    ) -> Dict:
        """发送HTTP请求（带重试机制）

        使用tenacity实现指数退避重试:
        - 最多重试3次
        - 等待时间: 2s, 4s, 8s (最大60s)
        - 仅重试429(限流)和503(服务不可用)错误

        Args:
            endpoint: API端点路径（如 /coins/list）
            params: 查询参数
            method: HTTP方法

        Returns:
            解析后的JSON响应数据

        Raises:
            CoinGeckoRateLimitError: 达到限流上限（429）
            CoinGeckoAPIError: 其他API错误
        """

        @retry(
            retry=retry_if_exception_type((CoinGeckoRateLimitError, requests.exceptions.RequestException)),
            stop=stop_after_attempt(self.MAX_RETRIES),
            wait=wait_exponential(multiplier=self.RETRY_WAIT_MULTIPLIER, max=self.RETRY_WAIT_MAX),
            before_sleep=before_sleep_log(logger, logging.WARNING)
        )
        def _do_request():
            url = f"{self.BASE_URL}{endpoint}"

            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params or {},
                    timeout=30
                )

                # 处理429限流错误
                if response.status_code == 429:
                    retry_after = response.headers.get('Retry-After', self.BATCH_DELAY)
                    logger.warning(
                        f"CoinGecko rate limit hit (429). Retry after {retry_after}s. "
                        f"Endpoint: {endpoint}"
                    )
                    time.sleep(int(retry_after))
                    raise CoinGeckoRateLimitError(f"Rate limit exceeded. Retry after {retry_after}s")

                # 处理503服务不可用
                if response.status_code == 503:
                    logger.warning(f"CoinGecko service unavailable (503). Endpoint: {endpoint}")
                    raise requests.exceptions.RequestException("Service unavailable")

                # 处理其他HTTP错误
                response.raise_for_status()

                return response.json()

            except requests.exceptions.RequestException as e:
                logger.error(f"CoinGecko API request failed: {endpoint}, error: {e}")
                raise CoinGeckoAPIError(f"API request failed: {e}") from e

        return _do_request()

    def fetch_coins_list(self, include_platform: bool = False) -> List[Dict]:
        """获取CoinGecko完整代币列表

        调用 GET /coins/list 端点

        Args:
            include_platform: 是否包含平台信息（链上合约地址）

        Returns:
            代币列表，每个元素包含:
            - id: CoinGecko ID (如 "bitcoin")
            - symbol: 代币符号 (如 "btc")
            - name: 代币名称 (如 "Bitcoin")

        Example:
            >>> client = CoingeckoClient()
            >>> coins = client.fetch_coins_list()
            >>> print(coins[0])
            {'id': 'bitcoin', 'symbol': 'btc', 'name': 'Bitcoin'}
        """
        logger.info("Fetching coins list from CoinGecko...")

        params = {}
        if include_platform:
            params['include_platform'] = 'true'

        try:
            data = self._request('/coins/list', params=params)
            logger.info(f"Fetched {len(data)} coins from CoinGecko")
            return data
        except Exception as e:
            logger.error(f"Failed to fetch coins list: {e}")
            raise

    def fetch_market_data(
        self,
        coingecko_ids: List[str],
        vs_currency: str = 'usd',
        order: str = 'market_cap_desc',
        per_page: int = 250,
        page: int = 1,
        sparkline: bool = False,
        price_change_percentage: str = ''
    ) -> List[Dict]:
        """获取市值和FDV数据（批量）

        调用 GET /coins/markets 端点

        注意: CoinGecko限流策略
        - 单次最多查询250个symbol
        - 批次间建议延迟60秒

        Args:
            coingecko_ids: CoinGecko ID列表（如 ["bitcoin", "ethereum"]）
            vs_currency: 基准货币（默认 usd）
            order: 排序方式（market_cap_desc, volume_desc等）
            per_page: 每页数量（最大250）
            page: 页码
            sparkline: 是否包含7天价格走势
            price_change_percentage: 价格变化周期（如 "1h,24h,7d"）

        Returns:
            市场数据列表，每个元素包含:
            - id: CoinGecko ID
            - symbol: 代币符号
            - current_price: 当前价格
            - market_cap: 市值
            - fully_diluted_valuation: 全稀释估值
            - total_volume: 24h交易量
            - ... 更多字段见CoinGecko文档

        Example:
            >>> client = CoingeckoClient()
            >>> data = client.fetch_market_data(['bitcoin', 'ethereum'])
            >>> print(data[0]['market_cap'])
            850000000000
        """
        if not coingecko_ids:
            logger.warning("Empty coingecko_ids list provided")
            return []

        # 限制批次大小
        if len(coingecko_ids) > self.BATCH_SIZE:
            logger.warning(
                f"Requested {len(coingecko_ids)} coins, "
                f"but batch size is limited to {self.BATCH_SIZE}. "
                f"Consider splitting into multiple calls."
            )
            coingecko_ids = coingecko_ids[:self.BATCH_SIZE]

        logger.info(f"Fetching market data for {len(coingecko_ids)} coins...")

        # 使用最简参数以避免免费API的限制
        params = {
            'vs_currency': vs_currency,
            'ids': ','.join(coingecko_ids),
        }

        # 可选参数（免费API可能不支持某些组合）
        if sparkline:
            params['sparkline'] = 'true'
        if price_change_percentage:
            params['price_change_percentage'] = price_change_percentage

        try:
            data = self._request('/coins/markets', params=params)
            logger.info(f"Fetched market data for {len(data)} coins")
            return data
        except Exception as e:
            logger.error(f"Failed to fetch market data: {e}")
            raise

    def fetch_market_data_batch(
        self,
        coingecko_ids: List[str],
        batch_size: Optional[int] = None,
        delay: Optional[int] = None,
        **kwargs
    ) -> List[Dict]:
        """批量获取市值和FDV数据（自动分批+延迟）

        自动将大量symbol分批处理，避免触发限流

        Args:
            coingecko_ids: CoinGecko ID列表
            batch_size: 每批数量（默认250）
            delay: 批次间延迟秒数（默认60）
            **kwargs: 传递给fetch_market_data的其他参数

        Returns:
            所有批次的市场数据合并列表

        Example:
            >>> client = CoingeckoClient()
            >>> # 获取500个symbol的数据（自动分2批，间隔60秒）
            >>> ids = [f'coin-{i}' for i in range(500)]
            >>> data = client.fetch_market_data_batch(ids)
            >>> print(len(data))
            500
        """
        batch_size = batch_size or self.BATCH_SIZE
        delay = delay or self.BATCH_DELAY

        total = len(coingecko_ids)
        batches = [coingecko_ids[i:i + batch_size] for i in range(0, total, batch_size)]

        logger.info(
            f"Fetching market data for {total} coins in {len(batches)} batches "
            f"(batch_size={batch_size}, delay={delay}s)"
        )

        all_data = []
        for i, batch in enumerate(batches, 1):
            logger.info(f"Processing batch {i}/{len(batches)} ({len(batch)} coins)...")

            try:
                batch_data = self.fetch_market_data(batch, **kwargs)
                all_data.extend(batch_data)
            except Exception as e:
                logger.error(f"Batch {i} failed: {e}")
                # 继续处理下一批
                continue

            # 批次间延迟（最后一批无需等待）
            if i < len(batches):
                logger.info(f"Waiting {delay}s before next batch...")
                time.sleep(delay)

        logger.info(f"Batch processing complete. Fetched {len(all_data)}/{total} coins")
        return all_data
