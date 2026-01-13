"""
策略16运行器服务 (Strategy16Runner)

封装Strategy16LimitEntry的调用，负责数据格式转换和结果格式化。

v4.0升级：
- 使用动态仓位管理（DynamicPositionManager）
- bear_warning周期跳过入场
- 复利效应：盈利后单笔金额自动增加

止盈止损策略：
- 止盈：动态挂单止盈
  - 下跌期（bear_warning, bear_strong）: EMA25回归止盈
  - 震荡期（consolidation）: (P95 + EMA25) / 2 止盈
  - 上涨期（bull_warning, bull_strong）: P95止盈
  - 触发后下一根K线以挂单价卖出
- 止损：无

Related:
    - Architecture: docs/iterations/037-strategy16-detail-page/architecture.md
    - Task: TASK-037-001
"""

import logging
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np

from backtest.models import KLine
from strategy_adapter.strategies import Strategy16LimitEntry
from strategy_adapter.core.position_manager import DynamicPositionManager

logger = logging.getLogger(__name__)


class Strategy16Runner:
    """
    策略16运行器

    负责:
    1. 从K线QuerySet转换为DataFrame格式
    2. 调用Strategy16LimitEntry.run_backtest()
    3. 格式化返回结果，包含orders/holdings/pending_order/statistics
    4. 持仓列表按buy_timestamp倒序排列

    v4.0升级：
    - 使用动态仓位管理
    - bear_warning周期跳过

    止盈止损：
    - 止盈：动态挂单止盈（根据cycle_phase周期选择）
    - 止损：无
    """

    def __init__(
        self,
        discount: float = 0.001,
        max_positions: int = 10,
        initial_capital: Decimal = Decimal("10000")
    ):
        """
        初始化策略16运行器

        Args:
            discount: 挂单折扣比例
            max_positions: 最大持仓数量
            initial_capital: 初始资金
        """
        self.discount = discount
        self.max_positions = max_positions
        self.initial_capital = initial_capital

    def run(
        self,
        symbol: str,
        interval: str,
        market_type: str,
        current_price: Optional[Decimal] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 500
    ) -> Dict[str, Any]:
        """
        运行策略16回测并返回格式化结果

        Args:
            symbol: 交易对
            interval: K线周期
            market_type: 市场类型
            current_price: 当前价格（用于计算浮动盈亏）
            start_time: 开始时间戳（毫秒）
            end_time: 结束时间戳（毫秒）
            limit: K线数量限制

        Returns:
            {
                'orders': [...],           # 已完成订单
                'holdings': [...],         # 当前持仓（倒序）
                'pending_order': {...},    # 当前挂单
                'statistics': {...}        # 统计数据
            }
        """
        try:
            # 1. 获取K线数据
            klines_df = self._fetch_klines_as_dataframe(
                symbol=symbol,
                interval=interval,
                market_type=market_type,
                start_time=start_time,
                end_time=end_time,
                limit=limit
            )

            if klines_df is None or klines_df.empty:
                logger.warning(f"Strategy16Runner: 无K线数据 {symbol}")
                return self._empty_result()

            # 2. 获取当前价格
            if current_price is None:
                current_price = Decimal(str(klines_df['close'].iloc[-1]))

            # 3. 初始化并运行策略16（v4.0动态仓位管理）
            position_manager = DynamicPositionManager()
            strategy = Strategy16LimitEntry(
                position_manager=position_manager,
                discount=self.discount,
                max_positions=self.max_positions
            )

            result = strategy.run_backtest(
                klines_df=klines_df,
                initial_capital=self.initial_capital
            )

            # 4. 格式化结果
            formatted_result = self._format_result(
                strategy=strategy,
                backtest_result=result,
                current_price=current_price,
                klines_df=klines_df
            )

            logger.info(
                f"Strategy16Runner完成: {symbol}, "
                f"订单数={formatted_result['statistics']['total_orders']}, "
                f"持仓数={len(formatted_result['holdings'])}"
            )

            return formatted_result

        except Exception as e:
            logger.exception(f"Strategy16Runner运行失败: {symbol}, {e}")
            return self._empty_result()

    def _fetch_klines_as_dataframe(
        self,
        symbol: str,
        interval: str,
        market_type: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 500
    ) -> Optional[pd.DataFrame]:
        """
        获取K线数据并转换为DataFrame

        注意：当指定了时间范围时，获取全部符合条件的K线，不限制数量。
        limit参数仅在未指定start_time时生效。

        Returns:
            DataFrame with columns: open, high, low, close, volume
            Index: DatetimeIndex
        """
        queryset = KLine.objects.filter(
            symbol=symbol,
            interval=interval,
            market_type=market_type
        )

        # 时间范围过滤
        if start_time:
            start_dt = datetime.fromtimestamp(
                start_time / 1000, tz=dt_timezone.utc
            )
            queryset = queryset.filter(open_time__gte=start_dt)

        if end_time:
            end_dt = datetime.fromtimestamp(
                end_time / 1000, tz=dt_timezone.utc
            )
            queryset = queryset.filter(open_time__lte=end_dt)

        # 按时间升序排列
        queryset = queryset.order_by('open_time')

        # 如果指定了start_time，获取全部符合条件的K线（回测需要完整数据）
        # 如果没有指定start_time，使用limit限制数量
        if start_time:
            klines = list(queryset)
        else:
            # 没有指定start_time时，获取最新的limit条数据
            klines = list(queryset.order_by('-open_time')[:limit])
            # 反转为时间升序
            klines.reverse()

        if not klines:
            return None

        # 转换为DataFrame
        data = {
            'open': [float(k.open_price) for k in klines],
            'high': [float(k.high_price) for k in klines],
            'low': [float(k.low_price) for k in klines],
            'close': [float(k.close_price) for k in klines],
            'volume': [float(k.volume) for k in klines],
        }

        index = pd.DatetimeIndex([k.open_time for k in klines])

        return pd.DataFrame(data, index=index)

    def _format_result(
        self,
        strategy: Strategy16LimitEntry,
        backtest_result: Dict,
        current_price: Decimal,
        klines_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        格式化回测结果

        Args:
            strategy: 策略实例（包含holdings和pending_order状态）
            backtest_result: 回测返回结果
            current_price: 当前价格
            klines_df: K线DataFrame

        Returns:
            格式化后的结果字典
        """
        # 1. 格式化已完成订单
        orders = self._format_orders(backtest_result.get('orders', []))

        # 2. 格式化当前持仓（添加浮动盈亏）
        holdings = self._format_holdings(
            holdings_dict=strategy._holdings,
            current_price=current_price,
            klines_df=klines_df
        )

        # 3. 格式化当前挂单
        pending_order = self._format_pending_order(strategy._pending_order)

        # 4. 格式化统计数据
        statistics = self._format_statistics(
            backtest_result.get('statistics', {}),
            holdings_count=len(holdings),
            has_pending=pending_order is not None
        )

        return {
            'orders': orders,
            'holdings': holdings,
            'pending_order': pending_order,
            'statistics': statistics
        }

    def _format_orders(self, orders: List[Dict]) -> List[Dict]:
        """格式化已完成订单列表"""
        formatted = []
        for order in orders:
            formatted.append({
                'id': order.get('buy_order_id', ''),
                'buy_price': order.get('buy_price', 0),
                'sell_price': order.get('sell_price', 0),
                'quantity': order.get('quantity', 0),
                'amount': order.get('amount', 0),
                'profit_loss': order.get('profit_loss', 0),
                'profit_rate': order.get('profit_rate', 0),
                'buy_timestamp': order.get('buy_timestamp', 0),
                'sell_timestamp': order.get('sell_timestamp', 0),
                'exit_reason': order.get('exit_reason', ''),
            })
        return formatted

    def _format_holdings(
        self,
        holdings_dict: Dict[str, Dict],
        current_price: Decimal,
        klines_df: pd.DataFrame
    ) -> List[Dict]:
        """
        格式化当前持仓列表

        计算浮动盈亏，按买入时间倒序排列
        """
        holdings = []
        current_timestamp = int(klines_df.index[-1].timestamp() * 1000) if len(klines_df) > 0 else 0

        for order_id, holding in holdings_dict.items():
            buy_price = Decimal(str(holding['buy_price']))
            quantity = Decimal(str(holding['quantity']))
            amount = Decimal(str(holding['amount']))
            buy_timestamp = holding['buy_timestamp']

            # 计算浮动盈亏
            floating_pnl = (current_price - buy_price) * quantity
            floating_pnl_rate = float((current_price - buy_price) / buy_price * 100) if buy_price > 0 else 0

            # 计算持仓K线数
            holding_bars = holding.get('kline_index', 0)
            if 'kline_index' in holding:
                holding_bars = len(klines_df) - holding['kline_index']

            holdings.append({
                'id': order_id,
                'buy_price': float(buy_price),
                'quantity': float(quantity),
                'amount': float(amount),
                'buy_timestamp': buy_timestamp,
                'current_price': float(current_price),
                'floating_pnl': float(floating_pnl),
                'floating_pnl_rate': round(floating_pnl_rate, 2),
                'holding_bars': holding_bars,
            })

        # 按买入时间倒序排列（最新在前）
        holdings.sort(key=lambda x: x['buy_timestamp'], reverse=True)

        return holdings

    def _format_pending_order(self, pending_order) -> Optional[Dict]:
        """格式化当前挂单"""
        if pending_order is None:
            return None

        if not pending_order.is_pending():
            return None

        return {
            'order_id': pending_order.order_id,
            'price': float(pending_order.price),
            'amount': float(pending_order.amount),
            'quantity': float(pending_order.quantity),
            'status': pending_order.status.value,
            'created_at': pending_order.created_at,
            'base_price': pending_order.metadata.get('base_price'),
            'metadata': {
                'p5': pending_order.metadata.get('p5'),
                'close': pending_order.metadata.get('close'),
                'mid_p5': pending_order.metadata.get('mid_p5'),
            }
        }

    def _format_statistics(
        self,
        stats: Dict,
        holdings_count: int,
        has_pending: bool
    ) -> Dict[str, Any]:
        """格式化统计数据"""
        return {
            'total_orders': stats.get('total_orders', 0),
            'winning_orders': stats.get('winning_orders', 0),
            'losing_orders': stats.get('losing_orders', 0),
            'win_rate': round(stats.get('win_rate', 0), 2),
            'total_profit': round(stats.get('total_profit', 0), 2),
            'return_rate': round(stats.get('return_rate', 0), 2),
            'open_positions': holdings_count,
            'has_pending_order': has_pending,
            'initial_capital': stats.get('initial_capital', 10000),
            'final_capital': round(stats.get('final_capital', 10000), 2),
        }

    def _empty_result(self) -> Dict[str, Any]:
        """返回空结果"""
        return {
            'orders': [],
            'holdings': [],
            'pending_order': None,
            'statistics': {
                'total_orders': 0,
                'winning_orders': 0,
                'losing_orders': 0,
                'win_rate': 0,
                'total_profit': 0,
                'return_rate': 0,
                'open_positions': 0,
                'has_pending_order': False,
                'initial_capital': float(self.initial_capital),
                'final_capital': float(self.initial_capital),
            }
        }
