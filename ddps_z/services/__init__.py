# DDPS-Z Services
# 延迟导入，避免循环依赖

__all__ = [
    'DDPSService',
    'ChartDataService',
]


def __getattr__(name):
    """延迟导入服务类"""
    if name == 'DDPSService':
        from .ddps_service import DDPSService
        return DDPSService
    elif name == 'ChartDataService':
        from .chart_data_service import ChartDataService
        return ChartDataService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
