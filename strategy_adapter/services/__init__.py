"""
策略适配层服务模块

Purpose:
    提供回测系统所需的独立服务，与其他模块解耦。

Services:
    - KlineDataService: K线数据获取服务
    - MarkerBuilderService: 订单标记构建服务

关联迭代: 016
"""

from .kline_data_service import KlineDataService
from .marker_builder_service import MarkerBuilderService

__all__ = ['KlineDataService', 'MarkerBuilderService']
