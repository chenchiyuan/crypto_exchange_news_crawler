"""VP-Squeeze异常类定义"""


class VPSqueezeError(Exception):
    """VP-Squeeze分析基础异常"""
    pass


class BinanceAPIError(VPSqueezeError):
    """币安API调用错误"""
    def __init__(self, message: str, status_code: int = None, response: str = None):
        self.status_code = status_code
        self.response = response
        super().__init__(message)


class InsufficientDataError(VPSqueezeError):
    """数据不足错误"""
    def __init__(self, required: int, actual: int):
        self.required = required
        self.actual = actual
        super().__init__(f"数据不足: 需要 {required} 根K线, 实际获取 {actual} 根")


class InvalidSymbolError(VPSqueezeError):
    """无效交易对错误"""
    def __init__(self, symbol: str, supported: list = None):
        self.symbol = symbol
        self.supported = supported or []
        supported_str = ', '.join(self.supported) if self.supported else '无'
        super().__init__(f"无效的交易对: {symbol}。支持的交易对: {supported_str}")


class InvalidIntervalError(VPSqueezeError):
    """无效时间周期错误"""
    def __init__(self, interval: str, valid_intervals: list = None):
        self.interval = interval
        self.valid_intervals = valid_intervals or []
        valid_str = ', '.join(self.valid_intervals) if self.valid_intervals else '无'
        super().__init__(f"无效的时间周期: {interval}。有效周期: {valid_str}")
