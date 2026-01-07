# DDPS-Z Calculators
# 延迟导入，避免循环依赖

__all__ = [
    'EMACalculator',
    'EWMACalculator',
    'ZScoreCalculator',
    'SignalEvaluator',
    # 迭代015: SignalCalculator（扩展BuySignalCalculator）
    'SignalCalculator',
    'BuySignalCalculator',  # 向后兼容别名
    'SignalError',
    'BuySignalError',  # 向后兼容别名
    'DataInsufficientError',
    'InvalidBetaError',
    'InvalidKlineError',
    # 迭代012: 订单追踪
    'OrderTracker',
    'OrderTrackerError',
    'VirtualOrder',
    'OrderStatistics',
    'TradeEvent',
]


def __getattr__(name):
    """延迟导入计算器类"""
    if name == 'EMACalculator':
        from .ema_calculator import EMACalculator
        return EMACalculator
    elif name == 'EWMACalculator':
        from .ewma_calculator import EWMACalculator
        return EWMACalculator
    elif name == 'ZScoreCalculator':
        from .zscore_calculator import ZScoreCalculator
        return ZScoreCalculator
    elif name == 'SignalEvaluator':
        from .signal_evaluator import SignalEvaluator
        return SignalEvaluator
    # 迭代015: SignalCalculator（扩展自BuySignalCalculator）
    elif name == 'SignalCalculator':
        from .signal_calculator import SignalCalculator
        return SignalCalculator
    elif name == 'BuySignalCalculator':
        # 向后兼容：从signal_calculator导入别名
        from .signal_calculator import BuySignalCalculator
        return BuySignalCalculator
    elif name == 'SignalError':
        from .signal_calculator import SignalError
        return SignalError
    elif name == 'BuySignalError':
        # 向后兼容别名
        from .signal_calculator import BuySignalError
        return BuySignalError
    elif name == 'DataInsufficientError':
        from .signal_calculator import DataInsufficientError
        return DataInsufficientError
    elif name == 'InvalidBetaError':
        from .signal_calculator import InvalidBetaError
        return InvalidBetaError
    elif name == 'InvalidKlineError':
        from .signal_calculator import InvalidKlineError
        return InvalidKlineError
    # 迭代012: 订单追踪
    elif name == 'OrderTracker':
        from .order_tracker import OrderTracker
        return OrderTracker
    elif name == 'OrderTrackerError':
        from .order_tracker import OrderTrackerError
        return OrderTrackerError
    elif name == 'VirtualOrder':
        from .order_tracker import VirtualOrder
        return VirtualOrder
    elif name == 'OrderStatistics':
        from .order_tracker import OrderStatistics
        return OrderStatistics
    elif name == 'TradeEvent':
        from .order_tracker import TradeEvent
        return TradeEvent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
