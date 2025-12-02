"""
买入持有策略（用于测试）
Buy and Hold Strategy
"""
import pandas as pd
from backtest.services.backtest_engine import BacktestEngine


class BuyHoldStrategy:
    """买入持有策略"""

    def __init__(self, engine: BacktestEngine):
        self.engine = engine

    def generate_signals(self) -> tuple:
        """
        生成买入持有信号

        Returns:
            (entries, exits): 买入信号和卖出信号
        """
        df = self.engine.df

        # 第一天买入
        entries = pd.Series(False, index=df.index)
        entries.iloc[0] = True

        # 最后一天卖出
        exits = pd.Series(False, index=df.index)
        exits.iloc[-1] = True

        return entries, exits

    def run(self):
        """运行回测"""
        entries, exits = self.generate_signals()

        result = self.engine.run_backtest(
            entries=entries,
            exits=exits,
            strategy_name=f"Buy & Hold - {self.engine.symbol}",
            strategy_params={
                'strategy_type': 'buy_and_hold'
            }
        )

        return result
