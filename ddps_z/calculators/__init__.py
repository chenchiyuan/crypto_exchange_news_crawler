# DDPS-Z Calculators
# 延迟导入，避免循环依赖

__all__ = [
    'EMACalculator',
    'EWMACalculator',
    'ZScoreCalculator',
    'SignalEvaluator',
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
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
