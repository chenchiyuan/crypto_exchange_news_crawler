"""
网格策略（vectorbt版本）
Grid Strategy for vectorbt
"""
import logging
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any

from backtest.services.backtest_engine import BacktestEngine

logger = logging.getLogger(__name__)


class GridStrategyVBT:
    """网格交易策略（vectorbt格式）"""

    def __init__(
        self,
        engine: BacktestEngine,
        grid_step_pct: float = 0.01,  # 1%
        grid_levels: int = 10,
        order_size_pct: float = 0.1,  # 每次交易10%资金
        stop_loss_pct: Optional[float] = None
    ):
        """
        初始化网格策略

        Args:
            engine: 回测引擎
            grid_step_pct: 网格步长百分比
            grid_levels: 网格层数
            order_size_pct: 每次交易占总资金的百分比
            stop_loss_pct: 止损百分比
        """
        self.engine = engine
        self.grid_step_pct = grid_step_pct
        self.grid_levels = grid_levels
        self.order_size_pct = order_size_pct
        self.stop_loss_pct = stop_loss_pct

        logger.info(
            f"网格策略初始化: "
            f"步长={grid_step_pct*100:.1f}%, "
            f"层数={grid_levels}, "
            f"仓位={order_size_pct*100:.0f}%"
        )

    def calculate_atr(self, window: int = 14) -> pd.Series:
        """
        计算ATR（Average True Range）

        Args:
            window: ATR周期

        Returns:
            pd.Series: ATR值
        """
        df = self.engine.df

        high = df['High']
        low = df['Low']
        close = df['Close']

        # 计算True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # 计算ATR
        atr = tr.rolling(window=window).mean()

        return atr

    def generate_signals(self) -> tuple:
        """
        生成网格交易信号

        Returns:
            (entries, exits): 买入信号和卖出信号
        """
        df = self.engine.df
        close = df['Close']

        # 初始化信号
        entries = pd.Series(False, index=df.index)
        exits = pd.Series(False, index=df.index)

        # 计算基准价格（使用第一个价格）
        base_price = close.iloc[0]

        # 生成网格价格层级（做多网格）
        buy_levels = []
        sell_levels = []

        for i in range(1, self.grid_levels + 1):
            # 买单价格：逐级下降
            buy_price = base_price * (1 - self.grid_step_pct * i)
            buy_levels.append(buy_price)

            # 卖单价格：逐级上升
            sell_price = base_price * (1 + self.grid_step_pct * i)
            sell_levels.append(sell_price)

        logger.info(f"网格价格层级生成: 买单{len(buy_levels)}层, 卖单{len(sell_levels)}层")
        logger.info(f"价格范围: ${min(buy_levels):.2f} ~ ${max(sell_levels):.2f}")

        # 生成交易信号
        # 简化版本：当价格下跌到买入层级时买入，上涨到卖出层级时卖出
        position = 0  # 当前持仓状态: 0=空仓, 1=持仓

        for i in range(1, len(close)):
            current_price = close.iloc[i]
            prev_price = close.iloc[i-1]

            # 检查是否触及买入层级（价格从上往下穿过）
            if position == 0:
                for buy_level in buy_levels:
                    if prev_price > buy_level >= current_price:
                        entries.iloc[i] = True
                        position = 1
                        break

            # 检查是否触及卖出层级（价格从下往上穿过）
            elif position == 1:
                for sell_level in sell_levels:
                    if prev_price < sell_level <= current_price:
                        exits.iloc[i] = True
                        position = 0
                        break

            # 止损检查
            if self.stop_loss_pct and position == 1:
                # 计算从入场以来的跌幅
                entry_idx = entries[:i][entries[:i]].index[-1] if entries[:i].any() else None
                if entry_idx is not None:
                    entry_price = close.loc[entry_idx]
                    drawdown = (current_price - entry_price) / entry_price

                    if drawdown <= -self.stop_loss_pct:
                        exits.iloc[i] = True
                        position = 0
                        logger.info(f"止损触发: {current_price:.2f}, 跌幅={drawdown*100:.2f}%")

        # 确保最后平仓
        if position == 1:
            exits.iloc[-1] = True

        logger.info(f"信号生成完成: 买入={entries.sum()}次, 卖出={exits.sum()}次")

        return entries, exits

    def run(self) -> 'BacktestResult':
        """运行回测"""
        entries, exits = self.generate_signals()

        strategy_params = {
            'strategy_type': 'grid',
            'grid_step_pct': self.grid_step_pct,
            'grid_levels': self.grid_levels,
            'order_size_pct': self.order_size_pct,
            'stop_loss_pct': self.stop_loss_pct
        }

        result = self.engine.run_backtest(
            entries=entries,
            exits=exits,
            strategy_name=f"Grid Strategy - {self.engine.symbol}",
            strategy_params=strategy_params
        )

        return result
