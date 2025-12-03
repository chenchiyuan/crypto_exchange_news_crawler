"""
MarketSymbol 数据模型

用途: 代表币安永续合约的基础信息
关联FR: FR-001, FR-002, FR-003, FR-004
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass
class MarketSymbol:
    """
    市场标的数据类

    属性:
        symbol: 交易对代码 (如 "BTCUSDT")
        exchange: 交易所 (如 "binance")
        contract_type: 合约类型 (如 "perpetual")
        listing_date: 上市时间
        current_price: 当前标记价格
        volume_24h: 24小时成交量 (USDT)
        open_interest: 持仓量 (张)
        funding_rate: 当前资金费率
        funding_interval_hours: 资金费率结算间隔 (小时)
        next_funding_time: 下次资金费率结算时间
        market_cap_rank: 市值排名 (可选, 用于FR-027.1)
    """

    symbol: str
    exchange: str
    contract_type: str
    listing_date: datetime
    current_price: Decimal
    volume_24h: Decimal
    open_interest: Decimal
    funding_rate: Decimal
    funding_interval_hours: int
    next_funding_time: datetime
    market_cap_rank: Optional[int] = None

    def passes_initial_filter(self, min_volume: Decimal, min_days: int) -> bool:
        """
        初筛验证 (FR-002, FR-003)

        Args:
            min_volume: 最小流动性阈值 (USDT)
            min_days: 最小上市天数

        Returns:
            是否通过初筛
        """
        from datetime import timedelta
        from django.utils import timezone

        # 流动性检查 (FR-002)
        if self.volume_24h < min_volume:
            return False

        # 上市时间检查 (FR-003)
        cutoff_date = timezone.now() - timedelta(days=min_days)
        if self.listing_date > cutoff_date:
            return False

        return True
