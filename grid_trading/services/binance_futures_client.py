"""
Binance Futures API客户端

用途: 专门为做空网格筛选系统设计的币安永续合约API客户端
关联FR: FR-001, FR-002, FR-003, FR-004, FR-016, FR-017, FR-020
"""

import logging
import requests
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from ratelimit import limits, sleep_and_retry

from grid_trading.models import MarketSymbol

logger = logging.getLogger("grid_trading")


class BinanceFuturesClient:
    """
    币安永续合约API客户端

    设计原则:
    - 复用项目现有的请求模式 (tenacity + ratelimit)
    - 专注于筛选系统所需的公开市场数据接口
    - 无需API Key或交易权限
    """

    BASE_URL = "https://fapi.binance.com"
    SPOT_BASE_URL = "https://api.binance.com"  # 现货API
    RATE_LIMIT_CALLS = 1200  # 权重/分钟
    RATE_LIMIT_PERIOD = 60  # 秒

    def __init__(self):
        """初始化客户端"""
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "python-grid-screening/1.0.0",
        })

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        reraise=True,
    )
    @sleep_and_retry
    @limits(calls=600, period=60)  # 限制为600次/分钟（币安实际限制1200权重/分钟）
    def _make_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None, base_url: Optional[str] = None
    ) -> Any:
        """
        发送API请求 (FR-040: API限流重试)

        Args:
            endpoint: API端点 (如 "/fapi/v1/exchangeInfo")
            params: 请求参数
            base_url: 自定义base URL（默认使用期货API）

        Returns:
            API响应数据

        Raises:
            requests.RequestException: 请求失败 (包括429限流错误)
        """
        url = f"{base_url or self.BASE_URL}{endpoint}"

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.warning(f"API限流 (429), 将自动重试: {endpoint}")
            else:
                logger.error(f"API请求失败: {url} - {str(e)}")
            raise

        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求异常: {url} - {str(e)}")
            raise

    def fetch_exchange_info(self) -> List[Dict[str, Any]]:
        """
        获取合约列表 (FR-001)

        调用端点: /fapi/v1/exchangeInfo
        权重: 1

        Returns:
            USDT本位永续合约列表，每个元素包含:
            - symbol: 交易对代码 (如 "BTCUSDT")
            - contractType: 合约类型 (如 "PERPETUAL")
            - onboardDate: 上市时间戳 (毫秒)
        """
        logger.info("获取币安永续合约列表...")

        data = self._make_request("/fapi/v1/exchangeInfo")

        # 筛选USDT本位永续合约
        perpetual_contracts = []
        for symbol_info in data.get("symbols", []):
            if (
                symbol_info.get("contractType") == "PERPETUAL"
                and symbol_info.get("quoteAsset") == "USDT"
                and symbol_info.get("status") == "TRADING"
            ):
                perpetual_contracts.append(
                    {
                        "symbol": symbol_info["symbol"],
                        "contractType": symbol_info["contractType"],
                        "onboardDate": symbol_info.get("onboardDate", 0),
                    }
                )

        logger.info(f"获取到 {len(perpetual_contracts)} 个USDT本位永续合约")
        return perpetual_contracts

    def fetch_24h_ticker(self) -> Dict[str, Dict[str, Any]]:
        """
        获取24小时Ticker数据 (FR-002, FR-020)

        调用端点: /fapi/v1/ticker/24hr
        权重: 40 (全市场)

        Returns:
            Dict[symbol, ticker_data]，ticker_data包含:
            - volume: 24小时成交量 (USDT)
            - lastPrice: 当前价格
        """
        logger.info("获取24小时Ticker数据...")

        data = self._make_request("/fapi/v1/ticker/24hr")

        ticker_dict = {}
        for ticker in data:
            symbol = ticker["symbol"]
            ticker_dict[symbol] = {
                "volume": Decimal(ticker.get("quoteVolume", "0")),  # USDT成交量
                "lastPrice": Decimal(ticker.get("lastPrice", "0")),
            }

        logger.info(f"获取到 {len(ticker_dict)} 个标的的Ticker数据")
        return ticker_dict

    def fetch_funding_rate(self) -> Dict[str, Dict[str, Any]]:
        """
        获取资金费率 (FR-017)

        调用端点: /fapi/v1/premiumIndex
        权重: 1

        Returns:
            Dict[symbol, funding_data]，funding_data包含:
            - fundingRate: 当前资金费率
            - nextFundingTime: 下次结算时间 (毫秒时间戳)
        """
        logger.info("获取资金费率数据...")

        data = self._make_request("/fapi/v1/premiumIndex")

        funding_dict = {}
        for item in data:
            symbol = item["symbol"]
            funding_dict[symbol] = {
                "fundingRate": Decimal(item.get("lastFundingRate", "0")),
                "nextFundingTime": int(item.get("nextFundingTime", 0)),
            }

        logger.info(f"获取到 {len(funding_dict)} 个标的的资金费率")
        return funding_dict

    def fetch_funding_rate_history(
        self, symbols: List[str], start_time: Optional[int] = None, limit: int = 100
    ) -> Dict[str, Dict[str, Any]]:
        """
        批量获取历史资金费率（含结算周期）

        调用端点: /fapi/v1/fundingRate
        权重: 1/标的
        并发策略: 每批10个标的，并发3

        Args:
            symbols: 标的代码列表
            start_time: 开始时间戳(毫秒)，默认为24小时前
            limit: 返回记录数量，默认100（最大1000）

        Returns:
            Dict[symbol, info]，每个info包含:
            - history: List[Dict] 历史资金费率列表
            - funding_interval_hours: int 结算周期（小时）
        """
        from datetime import datetime, timedelta

        logger.info(f"获取 {len(symbols)} 个标的的历史资金费率...")

        # 默认获取过去48小时的数据（用于计算结算周期）
        if start_time is None:
            start_time = int((datetime.now() - timedelta(hours=48)).timestamp() * 1000)

        funding_info_dict = {}
        max_workers = 3

        def fetch_single_history(symbol: str) -> tuple:
            """获取单个标的的历史资金费率并计算结算周期"""
            try:
                params = {
                    "symbol": symbol,
                    "startTime": start_time,
                    "limit": limit,
                }
                data = self._make_request("/fapi/v1/fundingRate", params)

                if not data or len(data) < 2:
                    return (symbol, {"history": [], "funding_interval_hours": 8})  # 默认8小时

                # 解析历史数据
                history = []
                for item in data:
                    history.append({
                        "fundingRate": Decimal(str(item.get("fundingRate", "0"))),
                        "fundingTime": int(item.get("fundingTime", 0)),
                    })

                # 计算结算周期（取前10个时间间隔的平均值）
                intervals = []
                for i in range(min(10, len(data) - 1)):
                    interval_ms = data[i + 1]['fundingTime'] - data[i]['fundingTime']
                    interval_hours = interval_ms / (1000 * 3600)
                    intervals.append(interval_hours)

                avg_interval = sum(intervals) / len(intervals) if intervals else 8.0
                funding_interval_hours = round(avg_interval)  # 四舍五入到整数小时

                return (symbol, {
                    "history": history,
                    "funding_interval_hours": funding_interval_hours
                })
            except Exception as e:
                logger.warning(f"获取 {symbol} 历史资金费率失败: {str(e)}")
                return (symbol, {"history": [], "funding_interval_hours": 8})  # 默认8小时

        # 分批并发获取
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(fetch_single_history, symbol) for symbol in symbols]

            for future in as_completed(futures):
                symbol, info = future.result()
                funding_info_dict[symbol] = info

        logger.info(f"成功获取 {len(funding_info_dict)} 个标的的历史资金费率")
        return funding_info_dict

    def fetch_open_interest(self, symbols: List[str]) -> Dict[str, Decimal]:
        """
        批量获取持仓量 (FR-016)

        调用端点: /fapi/v1/openInterest
        权重: 1/标的
        并发策略: 每批5个标的，并发3

        Args:
            symbols: 标的代码列表

        Returns:
            Dict[symbol, open_interest]
        """
        logger.info(f"获取 {len(symbols)} 个标的的持仓量...")

        oi_dict = {}
        batch_size = 5
        max_workers = 3

        def fetch_single_oi(symbol: str) -> tuple:
            """获取单个标的的持仓量"""
            try:
                data = self._make_request("/fapi/v1/openInterest", {"symbol": symbol})
                oi = Decimal(data.get("openInterest", "0"))
                return (symbol, oi)
            except Exception as e:
                logger.warning(f"获取 {symbol} 持仓量失败: {str(e)}")
                return (symbol, Decimal("0"))

        # 分批并发获取
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(fetch_single_oi, symbol) for symbol in symbols]

            for future in as_completed(futures):
                symbol, oi = future.result()
                oi_dict[symbol] = oi

        logger.info(f"成功获取 {len(oi_dict)} 个标的的持仓量")
        return oi_dict

    def fetch_klines(
        self,
        symbols: List[str],
        interval: str = "4h",
        limit: int = 300,
        end_time: Optional[Any] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        批量获取K线数据 (FR-005, FR-020)

        调用端点: /fapi/v1/klines
        权重: 1-5 (取决于limit)
        并发策略: 每批20个标的，并发3

        Args:
            symbols: 标的代码列表
            interval: K线周期 (1m/4h/1d)
            limit: K线数量 (默认300根)
            end_time: 结束时间 (datetime对象，获取此时间之前的数据，用于增量更新)

        Returns:
            Dict[symbol, klines]，每根K线包含:
            - open_time: 开盘时间 (毫秒)
            - open: 开盘价
            - high: 最高价
            - low: 最低价
            - close: 收盘价
            - volume: 成交量 (基础货币)
            - taker_buy_base_volume: Taker买入量 (用于CVD计算)
        """
        logger.info(f"获取 {len(symbols)} 个标的的K线数据 (interval={interval}, limit={limit})...")

        klines_dict = {}
        max_workers = 3

        def fetch_single_klines(symbol: str) -> tuple:
            """获取单个标的的K线"""
            try:
                params = {
                    "symbol": symbol,
                    "interval": interval,
                    "limit": limit,
                }

                # 如果指定了结束时间，转换为毫秒时间戳 (用于增量更新)
                if end_time is not None:
                    from datetime import datetime
                    if isinstance(end_time, datetime):
                        params["endTime"] = int(end_time.timestamp() * 1000)
                    else:
                        params["endTime"] = int(end_time)

                data = self._make_request("/fapi/v1/klines", params)

                # 解析K线数据
                klines = []
                for k in data:
                    klines.append({
                        "open_time": int(k[0]),
                        "open": float(k[1]),
                        "high": float(k[2]),
                        "low": float(k[3]),
                        "close": float(k[4]),
                        "volume": float(k[5]),
                        "close_time": int(k[6]),
                        "quote_volume": float(k[7]),
                        "trades": int(k[8]),
                        "taker_buy_base_volume": float(k[9]),  # 用于CVD
                        "taker_buy_quote_volume": float(k[10]),
                    })

                # 验证K线数量 (FR-039)
                if len(klines) < limit:
                    logger.warning(
                        f"{symbol} K线数据不足 {limit} 根 (仅{len(klines)}根), 将跳过该标的"
                    )
                    return (symbol, None)

                return (symbol, klines)

            except Exception as e:
                logger.warning(f"获取 {symbol} K线失败: {str(e)}")
                return (symbol, None)

        # 并发获取
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(fetch_single_klines, symbol) for symbol in symbols]

            for future in as_completed(futures):
                symbol, klines = future.result()
                if klines is not None:
                    klines_dict[symbol] = klines

        logger.info(f"成功获取 {len(klines_dict)}/{len(symbols)} 个标的的K线数据")
        return klines_dict

    def fetch_all_market_data(
        self,
        min_volume: Decimal,
        min_days: int,
    ) -> List[MarketSymbol]:
        """
        整合数据获取并执行初筛 (FR-001至FR-004, T024)

        流程:
        1. 并行调用 fetch_exchange_info, fetch_24h_ticker, fetch_funding_rate
        2. 执行初筛: 流动性>min_volume, 上市>min_days
        3. 对通过初筛的标的并行获取K线和持仓量
        4. 返回 List[MarketSymbol]

        Args:
            min_volume: 最小流动性阈值 (USDT)
            min_days: 最小上市天数

        Returns:
            通过初筛的MarketSymbol列表
        """
        from datetime import timedelta
        from django.utils import timezone

        logger.info("=" * 70)
        logger.info("📥 步骤1: 全市场扫描与初筛")
        logger.info("-" * 70)

        # 并行获取基础数据
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_contracts = executor.submit(self.fetch_exchange_info)
            future_tickers = executor.submit(self.fetch_24h_ticker)
            future_funding = executor.submit(self.fetch_funding_rate)

            contracts = future_contracts.result()
            tickers = future_tickers.result()
            funding_rates = future_funding.result()

        logger.info(f"  获取合约列表... ✓ {len(contracts)} 个永续合约")

        # 执行初筛
        passed_symbols = []
        cutoff_date = timezone.now() - timedelta(days=min_days)

        for contract in contracts:
            symbol = contract["symbol"]

            # 检查是否有Ticker和资金费率数据
            if symbol not in tickers or symbol not in funding_rates:
                continue

            ticker = tickers[symbol]
            funding = funding_rates[symbol]

            # 流动性过滤 (FR-002)
            if ticker["volume"] < min_volume:
                continue

            # 上市时间过滤 (FR-003)
            onboard_timestamp_ms = contract.get("onboardDate", 0)
            if onboard_timestamp_ms == 0:
                continue  # 无上市时间数据，跳过

            listing_date = datetime.fromtimestamp(onboard_timestamp_ms / 1000, tz=timezone.utc)
            if listing_date > cutoff_date:
                continue

            # 构建MarketSymbol对象
            market_symbol = MarketSymbol(
                symbol=symbol,
                exchange="binance",
                contract_type=contract["contractType"],
                listing_date=listing_date,
                current_price=ticker["lastPrice"],
                volume_24h=ticker["volume"],
                open_interest=Decimal("0"),  # 稍后填充
                funding_rate=funding["fundingRate"],
                funding_interval_hours=8,  # 币安默认8小时
                next_funding_time=datetime.fromtimestamp(
                    funding["nextFundingTime"] / 1000, tz=timezone.utc
                ),
            )

            passed_symbols.append(market_symbol)

        logger.info(
            f"  执行初筛... ✓ 通过流动性: {len([s for s in passed_symbols])}, "
            f"总通过数: {len(passed_symbols)}"
        )

        # 输出初筛统计 (FR-004)
        logger.info(f"  总标的数: {len(contracts)}, 初筛通过数: {len(passed_symbols)}, "
                    f"被过滤数: {len(contracts) - len(passed_symbols)}")

        # 如果无合格标的，直接返回 (SC-008)
        if not passed_symbols:
            logger.warning("  ⚠️ 初筛后无合格标的")
            return []

        # 获取通过初筛标的的持仓量
        symbol_list = [s.symbol for s in passed_symbols]
        oi_dict = self.fetch_open_interest(symbol_list)

        # 填充持仓量
        for market_symbol in passed_symbols:
            market_symbol.open_interest = oi_dict.get(market_symbol.symbol, Decimal("0"))

        logger.info(f"✓ 完成全市场数据获取，通过初筛: {len(passed_symbols)} 个标的")

        return passed_symbols

    def fetch_spot_symbols(self) -> set:
        """
        获取币安现货市场交易对列表

        调用端点: /api/v3/exchangeInfo (现货API)
        权重: 10

        Returns:
            Set[str]: 现货USDT交易对集合 (如 {"BTCUSDT", "ETHUSDT", ...})
        """
        logger.info("获取币安现货交易对列表...")

        try:
            data = self._make_request("/api/v3/exchangeInfo", base_url=self.SPOT_BASE_URL)

            # 筛选USDT现货交易对
            spot_symbols = set()
            for symbol_info in data.get("symbols", []):
                if (
                    symbol_info.get("quoteAsset") == "USDT"
                    and symbol_info.get("status") == "TRADING"
                    and symbol_info.get("isSpotTradingAllowed", False)
                ):
                    spot_symbols.add(symbol_info["symbol"])

            logger.info(f"获取到 {len(spot_symbols)} 个现货USDT交易对")
            return spot_symbols

        except Exception as e:
            logger.error(f"获取现货交易对列表失败: {str(e)}")
            # 发生错误时返回空集合，不影响主流程
            return set()
