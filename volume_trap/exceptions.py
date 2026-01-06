"""
巨量诱多/弃盘检测系统 - 自定义异常类

定义系统专用的异常类型，遵循Fail-Fast原则，确保异常携带清晰的上下文信息。

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md
    - Task: TASK-002-010
"""


class DataInsufficientError(Exception):
    """数据不足异常。

    当K线数据量少于计算所需的最小数量时抛出。

    Attributes:
        required (int): 所需的最小K线数量
        actual (int): 实际可用的K线数量
        symbol (str): 交易对符号
        interval (str): K线周期

    Examples:
        >>> raise DataInsufficientError(
        ...     required=21,
        ...     actual=15,
        ...     symbol='BTCUSDT',
        ...     interval='4h'
        ... )
        DataInsufficientError: K线数据不足: symbol=BTCUSDT, interval=4h, required=21, actual=15
    """

    def __init__(self, required: int, actual: int, symbol: str, interval: str):
        """初始化数据不足异常。

        Args:
            required: 所需的最小K线数量
            actual: 实际可用的K线数量
            symbol: 交易对符号
            interval: K线周期
        """
        self.required = required
        self.actual = actual
        self.symbol = symbol
        self.interval = interval
        message = (
            f"K线数据不足: "
            f"symbol={symbol}, interval={interval}, "
            f"required={required}, actual={actual}"
        )
        super().__init__(message)


class InvalidDataError(Exception):
    """无效数据异常。

    当数据字段值不符合业务规则时抛出（如volume=0、price<0等）。

    Attributes:
        field (str): 无效字段名称
        value: 实际值
        context (str): 错误上下文说明

    Examples:
        >>> raise InvalidDataError(
        ...     field='volume',
        ...     value=0,
        ...     context='除零错误：成交量不能为0'
        ... )
        InvalidDataError: 无效数据: field=volume, value=0, context=除零错误：成交量不能为0
    """

    def __init__(self, field: str, value, context: str = ""):
        """初始化无效数据异常。

        Args:
            field: 无效字段名称
            value: 实际值
            context: 错误上下文说明（可选）
        """
        self.field = field
        self.value = value
        self.context = context
        message = f"无效数据: field={field}, value={value}"
        if context:
            message += f", context={context}"
        super().__init__(message)


class SymbolNotFoundError(Exception):
    """交易对不存在异常。

    当查询的交易对在数据库中不存在时抛出。

    Attributes:
        symbol (str): 交易对符号
        market_type (str): 市场类型（spot/futures）

    Examples:
        >>> raise SymbolNotFoundError(
        ...     symbol='NONEXISTENT',
        ...     market_type='futures'
        ... )
        SymbolNotFoundError: 交易对不存在: symbol=NONEXISTENT, market_type=futures
    """

    def __init__(self, symbol: str, market_type: str = None):
        """初始化交易对不存在异常。

        Args:
            symbol: 交易对符号
            market_type: 市场类型（spot/futures，可选）
        """
        self.symbol = symbol
        self.market_type = market_type
        message = f"交易对不存在: symbol={symbol}"
        if market_type:
            message += f", market_type={market_type}"
        super().__init__(message)


class DateRangeInvalidError(Exception):
    """日期范围无效异常。

    当提供的日期范围不符合业务规则时抛出（如start_time > end_time）。

    Attributes:
        start_time: 开始时间
        end_time: 结束时间
        reason (str): 错误原因说明

    Examples:
        >>> from datetime import datetime
        >>> start = datetime(2025, 12, 26)
        >>> end = datetime(2025, 12, 24)
        >>> raise DateRangeInvalidError(
        ...     start_time=start,
        ...     end_time=end,
        ...     reason='start_time不能大于end_time'
        ... )
        DateRangeInvalidError: 日期范围无效: start_time=2025-12-26 00:00:00, end_time=2025-12-24 00:00:00, reason=start_time不能大于end_time
    """

    def __init__(self, start_time, end_time, reason: str = ""):
        """初始化日期范围无效异常。

        Args:
            start_time: 开始时间
            end_time: 结束时间
            reason: 错误原因说明（可选）
        """
        self.start_time = start_time
        self.end_time = end_time
        self.reason = reason
        message = f"日期范围无效: start_time={start_time}, end_time={end_time}"
        if reason:
            message += f", reason={reason}"
        super().__init__(message)


class DataFormatError(Exception):
    """数据格式错误异常。

    当数据格式不符合预期或缺少必要字段时抛出。

    Attributes:
        field (str): 字段名称
        expected_format (str): 期望的格式描述
        actual_value: 实际值
        context (str): 错误上下文说明

    Examples:
        >>> raise DataFormatError(
        ...     field='kline_data',
        ...     expected_format='包含time、open、high、low、close字段的列表',
        ...     actual_value='[]',
        ...     context='K线数据不能为空'
        ... )
        DataFormatError: 数据格式错误: field=kline_data, expected_format=包含time、open、high、low、close字段的列表, actual_value=[], context=K线数据不能为空
    """

    def __init__(self, field: str, expected_format: str, actual_value=None, context: str = ""):
        """初始化数据格式错误异常。

        Args:
            field: 字段名称
            expected_format: 期望的格式描述
            actual_value: 实际值（可选）
            context: 错误上下文说明（可选）
        """
        self.field = field
        self.expected_format = expected_format
        self.actual_value = actual_value
        self.context = context
        message = f"数据格式错误: field={field}, expected_format={expected_format}"
        if actual_value is not None:
            message += f", actual_value={actual_value}"
        if context:
            message += f", context={context}"
        super().__init__(message)
