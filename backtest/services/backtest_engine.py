"""
回测引擎
Backtest Engine using vectorbt
"""
import logging
import pandas as pd
import numpy as np
import vectorbt as vbt
from datetime import datetime
from typing import Dict, Any, Optional
from decimal import Decimal

from django.utils import timezone
from backtest.models import KLine, BacktestResult
from backtest.services.metrics_calculator import MetricsCalculator

logger = logging.getLogger(__name__)


class BacktestEngine:
    """vectorbt回测引擎"""

    def __init__(
        self,
        symbol: str,
        interval: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        initial_cash: float = 10000.0,
        commission: float = 0.001,  # 0.1%
        slippage: float = 0.0005    # 0.05%
    ):
        """
        初始化回测引擎

        Args:
            symbol: 交易对
            interval: 时间周期
            start_date: 开始日期
            end_date: 结束日期
            initial_cash: 初始资金
            commission: 手续费率
            slippage: 滑点
        """
        self.symbol = symbol
        self.interval = interval
        self.start_date = start_date
        self.end_date = end_date
        self.initial_cash = initial_cash
        self.commission = commission
        self.slippage = slippage

        # 加载数据
        self.df = self._load_data()

        logger.info(
            f"回测引擎初始化: {symbol} {interval}, "
            f"数据量={len(self.df)}, "
            f"时间范围={self.df.index[0]} ~ {self.df.index[-1]}"
        )

    def _load_data(self) -> pd.DataFrame:
        """从数据库加载K线数据"""
        queryset = KLine.objects.filter(
            symbol=self.symbol,
            interval=self.interval
        )

        if self.start_date:
            queryset = queryset.filter(open_time__gte=self.start_date)
        if self.end_date:
            queryset = queryset.filter(open_time__lte=self.end_date)

        queryset = queryset.order_by('open_time')

        if not queryset.exists():
            raise ValueError(f"没有找到数据: {self.symbol} {self.interval}")

        # 转换为DataFrame
        data = list(queryset.values(
            'open_time', 'open_price', 'high_price',
            'low_price', 'close_price', 'volume'
        ))

        df = pd.DataFrame(data)

        # 重命名列
        df = df.rename(columns={
            'open_price': 'Open',
            'high_price': 'High',
            'low_price': 'Low',
            'close_price': 'Close',
            'volume': 'Volume'
        })

        # 转换为float（从Decimal）
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = df[col].astype(float)

        # 设置索引
        df['open_time'] = pd.to_datetime(df['open_time'])
        df = df.set_index('open_time')

        return df

    def run_backtest(
        self,
        entries: pd.Series,
        exits: pd.Series,
        strategy_name: str = "Custom Strategy",
        strategy_params: Optional[Dict[str, Any]] = None
    ) -> BacktestResult:
        """
        运行回测

        Args:
            entries: 买入信号（True/False）
            exits: 卖出信号（True/False）
            strategy_name: 策略名称
            strategy_params: 策略参数

        Returns:
            BacktestResult: 回测结果对象
        """
        logger.info(f"开始回测: {strategy_name}")

        # 创建Portfolio
        portfolio = vbt.Portfolio.from_signals(
            close=self.df['Close'],
            entries=entries,
            exits=exits,
            init_cash=self.initial_cash,
            fees=self.commission,
            slippage=self.slippage,
            freq=self.interval
        )

        # 计算指标
        total_return = portfolio.total_return()
        sharpe_ratio = portfolio.sharpe_ratio()
        max_drawdown = portfolio.max_drawdown()

        # 处理无效的夏普比率（Infinity, NaN等）
        if pd.isna(sharpe_ratio) or np.isinf(sharpe_ratio):
            sharpe_ratio = None

        # 交易统计
        trades = portfolio.trades.records_readable
        total_trades = len(trades)
        profitable_trades = len(trades[trades['PnL'] > 0]) if not trades.empty else 0
        losing_trades = len(trades[trades['PnL'] < 0]) if not trades.empty else 0
        win_rate = profitable_trades / total_trades * 100 if total_trades > 0 else 0

        # 权益曲线
        equity_curve = portfolio.value().to_dict()
        equity_curve = {str(k): float(v) for k, v in equity_curve.items()}

        # 交易明细
        trades_detail = trades.to_dict('records') if not trades.empty else []
        # 转换 Timestamp 为 string
        for trade in trades_detail:
            for key, value in trade.items():
                if isinstance(value, pd.Timestamp):
                    trade[key] = str(value)
                elif isinstance(value, (np.integer, np.floating)):
                    trade[key] = float(value)

        # 每日收益
        daily_returns = portfolio.returns().to_dict()
        daily_returns = {str(k): float(v) for k, v in daily_returns.items()}

        # 计算增强指标
        metrics_calc = MetricsCalculator()
        days = (self.df.index[-1] - self.df.index[0]).days
        daily_returns_series = portfolio.returns()
        equity_curve_series = portfolio.value()
        trades_pnl = trades['PnL'].tolist() if not trades.empty else []

        enhanced_metrics = metrics_calc.calculate_all_metrics(
            total_return=total_return,
            days=days,
            daily_returns=daily_returns_series,
            equity_curve=equity_curve_series,
            trades_pnl=trades_pnl,
            max_drawdown=max_drawdown
        )

        # 创建回测结果
        result = BacktestResult.objects.create(
            name=strategy_name,
            symbol=self.symbol,
            interval=self.interval,
            start_date=self.df.index[0],
            end_date=self.df.index[-1],
            strategy_params=strategy_params or {},
            initial_cash=Decimal(str(self.initial_cash)),
            final_value=Decimal(str(portfolio.final_value())),
            total_return=Decimal(str(total_return)),
            sharpe_ratio=Decimal(str(sharpe_ratio)) if not pd.isna(sharpe_ratio) else None,
            max_drawdown=Decimal(str(abs(max_drawdown))),
            win_rate=Decimal(str(win_rate)),
            total_trades=total_trades,
            profitable_trades=profitable_trades,
            losing_trades=losing_trades,
            equity_curve=equity_curve,
            trades_detail=trades_detail,
            daily_returns=daily_returns,
            # 增强指标
            annual_return=Decimal(str(enhanced_metrics['annual_return'])) if enhanced_metrics['annual_return'] is not None else None,
            annual_volatility=Decimal(str(enhanced_metrics['annual_volatility'])) if enhanced_metrics['annual_volatility'] is not None else None,
            sortino_ratio=Decimal(str(enhanced_metrics['sortino_ratio'])) if enhanced_metrics['sortino_ratio'] is not None and not np.isinf(enhanced_metrics['sortino_ratio']) else None,
            calmar_ratio=Decimal(str(enhanced_metrics['calmar_ratio'])) if enhanced_metrics['calmar_ratio'] is not None and not np.isinf(enhanced_metrics['calmar_ratio']) else None,
            max_drawdown_duration=enhanced_metrics['max_drawdown_duration'],
            profit_factor=Decimal(str(enhanced_metrics['profit_factor'])) if enhanced_metrics['profit_factor'] is not None and not np.isinf(enhanced_metrics['profit_factor']) else None,
            avg_win=Decimal(str(enhanced_metrics['avg_win'])) if enhanced_metrics['avg_win'] is not None else None,
            avg_loss=Decimal(str(enhanced_metrics['avg_loss'])) if enhanced_metrics['avg_loss'] is not None else None,
        )

        logger.info(
            f"回测完成: {strategy_name}, "
            f"收益率={total_return:.2%}, "
            f"年化收益率={enhanced_metrics['annual_return']:.2%}, " if enhanced_metrics['annual_return'] else ""
            f"夏普比率={sharpe_ratio:.2f}, "
            f"最大回撤={max_drawdown:.2%}"
        )

        return result
