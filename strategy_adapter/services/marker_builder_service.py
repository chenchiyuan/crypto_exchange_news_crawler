"""
订单标记构建服务

Purpose:
    将BacktestOrder转换为TradingView Lightweight Charts的Marker格式。
    用于在K线图上显示买入/卖出点。

关联任务: TASK-016-002
关联功能点: F2.2

Example:
    >>> service = MarkerBuilderService()
    >>> orders = BacktestOrder.objects.filter(backtest_result_id=1)
    >>> markers = service.build_markers(orders)
    >>> print(markers[0])
    {
        'time': 1704067200,
        'position': 'belowBar',
        'color': '#28a745',
        'shape': 'arrowUp',
        'text': 'B',
        'size': 1
    }
"""

import logging
from typing import List

logger = logging.getLogger(__name__)


class MarkerBuilderService:
    """
    订单标记构建服务

    Attributes:
        BUY_COLOR: 买入标记颜色（绿色）
        SELL_COLOR: 卖出标记颜色（红色）
    """

    # 颜色常量
    BUY_COLOR = "#28a745"   # Bootstrap success绿色
    SELL_COLOR = "#dc3545"  # Bootstrap danger红色

    def build_markers(self, orders) -> List[dict]:
        """
        构建订单标记列表

        为每个订单生成买入标记，为已平仓订单额外生成卖出标记。
        标记按时间戳升序排列。

        Args:
            orders: BacktestOrder查询集或列表

        Returns:
            Marker格式列表，按时间戳升序排列:
            [
                {
                    'time': int,       # 秒级时间戳
                    'position': str,   # 'belowBar' 或 'aboveBar'
                    'color': str,      # 十六进制颜色
                    'shape': str,      # 'arrowUp' 或 'arrowDown'
                    'text': str,       # 显示文字
                    'size': int        # 标记大小
                },
                ...
            ]
        """
        markers = []

        for order in orders:
            # 买入标记（所有订单都有）
            buy_marker = self._build_buy_marker(order)
            markers.append(buy_marker)

            # 卖出标记（仅已平仓订单）
            if order.status == 'closed' and order.sell_timestamp:
                sell_marker = self._build_sell_marker(order)
                markers.append(sell_marker)

        # 按时间戳升序排列
        markers.sort(key=lambda x: x['time'])

        logger.info(f"构建订单标记完成: 订单数={len(list(orders))}, 标记数={len(markers)}")

        return markers

    def _build_buy_marker(self, order) -> dict:
        """
        构建买入标记

        Args:
            order: BacktestOrder对象

        Returns:
            买入标记字典（TradingView Marker格式）
        """
        return {
            'time': order.buy_timestamp // 1000,  # 毫秒转秒
            'position': 'belowBar',               # K线下方
            'color': self.BUY_COLOR,              # 绿色
            'shape': 'arrowUp',                   # 向上箭头
            'text': 'B',                          # 显示文字
            'size': 1                             # 标记大小
        }

    def _build_sell_marker(self, order) -> dict:
        """
        构建卖出标记

        Args:
            order: BacktestOrder对象（必须是已平仓状态）

        Returns:
            卖出标记字典（TradingView Marker格式）
        """
        return {
            'time': order.sell_timestamp // 1000,  # 毫秒转秒
            'position': 'aboveBar',                # K线上方
            'color': self.SELL_COLOR,              # 红色
            'shape': 'arrowDown',                  # 向下箭头
            'text': 'S',                           # 显示文字
            'size': 1                              # 标记大小
        }
