"""
交易所适配器工厂
Exchange Adapter Factory

根据配置创建不同的交易所适配器实例
"""
import logging
from typing import Optional, Literal

from .adapter import ExchangeAdapter
from .grvt_adapter import GRVTExchangeAdapter, GRVTCredentials

logger = logging.getLogger(__name__)

# 支持的交易所类型
ExchangeType = Literal["grvt"]


def create_adapter(
    exchange: ExchangeType,
    credentials: Optional[dict] = None
) -> ExchangeAdapter:
    """创建交易所适配器

    Args:
        exchange: 交易所类型 (grvt)
        credentials: 认证凭据字典，如果为None则从环境变量读取

    Returns:
        交易所适配器实例

    Raises:
        ValueError: 不支持的交易所类型
    """
    exchange_lower = exchange.lower()

    if exchange_lower == "grvt":
        if credentials:
            grvt_creds = GRVTCredentials(
                api_key=credentials.get("api_key"),
                private_key=credentials.get("private_key"),
                trading_account_id=credentials.get("trading_account_id"),
                env=credentials.get("env", "testnet"),
            )
        else:
            grvt_creds = None

        logger.info(f"创建GRVT适配器")
        return GRVTExchangeAdapter(grvt_creds)

    else:
        raise ValueError(f"不支持的交易所类型: {exchange}")


def get_supported_exchanges() -> list[str]:
    """获取支持的交易所列表

    Returns:
        交易所名称列表
    """
    return ["grvt"]
