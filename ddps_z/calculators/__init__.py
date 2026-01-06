# DDPS-Z Calculators
# 延迟导入，避免循环依赖

__all__ = [
    'EMACalculator',
    'EWMACalculator',
    'ZScoreCalculator',
    'SignalEvaluator',
    'BuySignalCalculator',
    'BuySignalError',
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
    elif name == 'BuySignalCalculator':
        from .buy_signal_calculator import BuySignalCalculator
        return BuySignalCalculator
    elif name == 'BuySignalError':
        from .buy_signal_calculator import BuySignalError
        return BuySignalError
    elif name == 'DataInsufficientError':
        from .buy_signal_calculator import DataInsufficientError
        return DataInsufficientError
    elif name == 'InvalidBetaError':
        from .buy_signal_calculator import InvalidBetaError
        return InvalidBetaError
    elif name == 'InvalidKlineError':
        from .buy_signal_calculator import InvalidKlineError
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
