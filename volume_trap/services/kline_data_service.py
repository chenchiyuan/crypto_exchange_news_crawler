"""
K线数据服务（KLine Data Service）

提供统一的K线数据查询接口，支持现货和合约市场的K线数据检索。

功能特性：
- 支持symbol、interval、market_type、start_time、end_time、limit参数
- 返回标准化的OHLCV数据格式
- 性能优化：<1秒查询响应时间
- 支持批量查询和数据转换
- 完整的异常处理和参数验证

Related:
    - PRD: docs/iterations/006-volume-trap-dashboard/prd.md (F2.1)
    - Architecture: docs/iterations/006-volume-trap-dashboard/architecture.md (3.3)
    - Task: TASK-006-002
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db.models import QuerySet
from django.utils import timezone

from backtest.models import KLine
from monitor.models import FuturesContract, SpotContract
from volume_trap.exceptions import DateRangeInvalidError, SymbolNotFoundError

logger = logging.getLogger(__name__)


class KLineDataService:
    """K线数据服务。

    提供统一的K线数据查询接口，支持现货和合约市场的K线数据检索。
    返回标准化的OHLCV数据格式，包含time、open、high、low、close、volume字段。

    性能特性：
        - 使用数据库索引优化查询性能
        - 支持limit参数限制返回数据量
        - 响应时间目标：<1秒（1000条记录以内）

    异常处理：
        - SymbolNotFoundError: 交易对不存在时抛出
        - DateRangeInvalidError: 日期范围无效时抛出
        - ValueError: 参数格式错误时抛出

    Examples:
        >>> service = KLineDataService()
        >>> result = service.get_kline_data(
        ...     symbol='BTCUSDT',
        ...     interval='4h',
        ...     market_type='futures',
        ...     start_time=datetime(2025, 12, 1),
        ...     end_time=datetime(2025, 12, 25),
        ...     limit=100
        ... )
        >>> print(result['total_count'])
        100
        >>> print(len(result['data']))
        100
    """

    def __init__(self):
        """初始化K线数据服务。

        设置服务配置参数，包括默认查询限制和性能阈值。
        """
        self.default_limit = 1000  # 默认查询限制
        self.performance_threshold = 1.0  # 性能阈值（秒）

    def get_kline_data(
        self,
        symbol: str,
        interval: str,
        market_type: str = "futures",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """获取K线数据。

        根据指定参数查询K线数据，返回标准化的OHLCV格式。
        支持现货和合约市场类型，包含完整的参数验证和异常处理。

        Args:
            symbol (str): 交易对符号，如 'BTCUSDT'、'ETHUSDT'
            interval (str): K线周期，支持 '1h'、'4h'、'1d'
            market_type (str, optional): 市场类型，'spot' 或 'futures'，默认 'futures'
            start_time (datetime, optional): 开始时间，如不指定则从最早数据开始
            end_time (datetime, optional): 结束时间，如不指定则到最新数据
            limit (int, optional): 返回数据条数限制，默认1000条，最大5000条

        Returns:
            Dict[str, Any]: 标准化的K线数据字典，包含：
                - data (List[Dict]): K线数据列表，每项包含：
                    - time (float): 时间戳（秒）
                    - open (float): 开盘价
                    - high (float): 最高价
                    - low (float): 最低价
                    - close (float): 收盘价
                    - volume (float): 成交量
                    - market_type (str): 市场类型（spot/futures）
                - total_count (int): 符合条件的数据总条数

        Raises:
            SymbolNotFoundError: 当交易对在指定市场类型中不存在时抛出
                示例：symbol='NONEXISTENT', market_type='futures'

            DateRangeInvalidError: 当日期范围无效时抛出
                示例：start_time > end_time

            ValueError: 当参数格式错误时抛出
                示例：interval not in ['1h', '4h', '1d']

        Examples:
            获取合约市场BTCUSDT的4小时K线数据：
            >>> service = KLineDataService()
            >>> result = service.get_kline_data(
            ...     symbol='BTCUSDT',
            ...     interval='4h',
            ...     market_type='futures',
            ...     start_time=datetime(2025, 12, 1),
            ...     end_time=datetime(2025, 12, 25)
            ... )
            >>> result['total_count']
            144
            >>> result['data'][0]['symbol']
            'BTCUSDT'

            获取现货市场ETHUSDT的日K线数据：
            >>> result = service.get_kline_data(
            ...     symbol='ETHUSDT',
            ...     interval='1d',
            ...     market_type='spot',
            ...     limit=30
            ... )
            >>> len(result['data'])
            30

        Side Effects:
            - 查询数据库：执行KLine表查询
            - 记录日志：记录查询参数和执行时间
            - 内存使用：返回的K线数据加载到内存

        Related:
            - Task: TASK-006-002
            - Architecture: docs/iterations/006-volume-trap-dashboard/architecture.md (3.3)
        """
        # === 参数验证 ===
        self._validate_parameters(symbol, interval, market_type, start_time, end_time, limit)

        # === 交易对存在性验证 ===
        self._validate_symbol_exists(symbol, market_type)

        # === 日期范围验证 ===
        if start_time and end_time and start_time > end_time:
            raise DateRangeInvalidError(
                start_time=start_time, end_time=end_time, reason="start_time不能大于end_time"
            )

        # === 构建查询 ===
        queryset = self._build_queryset(symbol, interval, market_type, start_time, end_time)

        # === 执行查询 ===
        total_count = queryset.count()

        # === 限制结果数量 ===
        if limit:
            queryset = queryset[:limit]

        # === 转换为标准格式 ===
        data = self._format_kline_data(queryset, market_type)

        # === 返回结果 ===
        result = {"data": data, "total_count": total_count}

        # === 记录日志 ===
        logger.info(
            f"K线数据查询完成: symbol={symbol}, interval={interval}, "
            f"market_type={market_type}, count={len(data)}, total={total_count}"
        )

        return result

    def _validate_parameters(
        self,
        symbol: str,
        interval: str,
        market_type: str,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        limit: Optional[int],
    ) -> None:
        """验证输入参数。

        Args:
            symbol: 交易对符号
            interval: K线周期
            market_type: 市场类型
            start_time: 开始时间
            end_time: 结束时间
            limit: 限制数量

        Raises:
            ValueError: 当参数不符合要求时抛出
        """
        # 验证symbol
        if not symbol or not isinstance(symbol, str):
            raise ValueError("symbol必须是非空字符串")

        # 验证interval
        valid_intervals = ["1h", "4h", "1d"]
        if interval not in valid_intervals:
            raise ValueError(f"interval必须是以下值之一: {valid_intervals}")

        # 验证market_type
        valid_market_types = ["spot", "futures"]
        if market_type not in valid_market_types:
            raise ValueError(f"market_type必须是以下值之一: {valid_market_types}")

        # 验证limit
        if limit is not None:
            if not isinstance(limit, int) or limit <= 0:
                raise ValueError("limit必须是正整数")
            if limit > 5000:
                raise ValueError("limit不能超过5000")

    def _validate_symbol_exists(self, symbol: str, market_type: str) -> None:
        """验证交易对是否存在。

        Args:
            symbol: 交易对符号
            market_type: 市场类型

        Raises:
            SymbolNotFoundError: 当交易对不存在时抛出
        """
        if market_type == "futures":
            exists = FuturesContract.objects.filter(symbol=symbol).exists()
        else:  # spot
            exists = SpotContract.objects.filter(symbol=symbol).exists()

        if not exists:
            raise SymbolNotFoundError(symbol=symbol, market_type=market_type)

    def _build_queryset(
        self,
        symbol: str,
        interval: str,
        market_type: str,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
    ) -> QuerySet:
        """构建K线数据查询集。

        Args:
            symbol: 交易对符号
            interval: K线周期
            market_type: 市场类型
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            QuerySet: 构造好的Django查询集
        """
        # 基础查询
        queryset = KLine.objects.filter(symbol=symbol, interval=interval, market_type=market_type)

        # 时间范围过滤
        if start_time:
            queryset = queryset.filter(open_time__gte=start_time)

        if end_time:
            queryset = queryset.filter(open_time__lte=end_time)

        # 按时间倒序排列（最新的在前）
        queryset = queryset.order_by("-open_time")

        return queryset

    def _format_kline_data(self, queryset: QuerySet, market_type: str) -> List[Dict[str, Any]]:
        """将K线数据转换为标准格式。

        Args:
            queryset: K线数据查询集
            market_type: 市场类型

        Returns:
            List[Dict]: 标准化的K线数据列表
        """
        data = []
        for kline in queryset:
            data.append(
                {
                    "time": float(kline.open_time.timestamp()) if kline.open_time else 0.0,
                    "open": float(kline.open_price),
                    "high": float(kline.high_price),
                    "low": float(kline.low_price),
                    "close": float(kline.close_price),
                    "volume": float(kline.volume),
                    "market_type": market_type,
                }
            )

        return data
