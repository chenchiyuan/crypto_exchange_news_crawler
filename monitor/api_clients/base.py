"""
合约API客户端抽象基类

定义所有交易所API客户端必须实现的接口
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class BaseFuturesClient(ABC):
    """合约API客户端抽象基类"""

    def __init__(self, exchange_name: str):
        """
        初始化API客户端

        Args:
            exchange_name: 交易所名称
        """
        self.exchange_name = exchange_name
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def fetch_contracts(self) -> List[Dict[str, Any]]:
        """
        获取合约列表和当前价格

        Returns:
            List[Dict]: 合约数据列表，每个字典包含:
                - symbol: str - 标准化后的合约代码 (如BTCUSDT)
                - current_price: float - 当前价格
                - contract_type: str - 合约类型 (固定为'perpetual')

        Raises:
            Exception: API调用失败时抛出异常
        """
        pass

    @abstractmethod
    def fetch_contracts_with_indicators(self) -> List[Dict[str, Any]]:
        """
        获取合约列表及市场指标数据

        Returns:
            List[Dict]: 合约及市场指标数据列表，每个字典包含:
                - symbol: str - 标准化后的合约代码 (如BTCUSDT)
                - current_price: Decimal - 当前价格
                - contract_type: str - 合约类型 (固定为'perpetual')
                - open_interest: Decimal - 持仓量 (可选)
                - volume_24h: Decimal - 24小时交易量 (可选)
                - funding_rate: Decimal - 当前资金费率 (可选)
                - next_funding_time: datetime - 下次结算时间 (可选)
                - funding_interval_hours: int - 资金费率间隔 (可选)
                - funding_rate_cap: Decimal - 费率上限 (可选)
                - funding_rate_floor: Decimal - 费率下限 (可选)

        Raises:
            Exception: API调用失败时抛出异常
        """
        pass

    @abstractmethod
    def _normalize_symbol(self, raw_symbol: str) -> str:
        """
        标准化合约代码格式

        将交易所特定的符号格式转换为统一的标准格式(BTCUSDT)

        Args:
            raw_symbol: 交易所原始符号

        Returns:
            str: 标准化后的符号

        Examples:
            Binance: BTCUSDT → BTCUSDT (无需转换)
            Hyperliquid: BTC → BTCUSDT (需要添加USDT后缀)
            Bybit: BTCUSDT → BTCUSDT (无需转换)
        """
        pass

    def _log_fetch_start(self):
        """记录开始获取合约数据"""
        self.logger.info(f"开始从 {self.exchange_name} 获取合约数据")

    def _log_fetch_success(self, count: int):
        """记录成功获取合约数据"""
        self.logger.info(f"成功从 {self.exchange_name} 获取 {count} 个合约")

    def _log_fetch_error(self, error: Exception):
        """记录获取失败"""
        self.logger.error(f"从 {self.exchange_name} 获取合约数据失败: {str(error)}")
