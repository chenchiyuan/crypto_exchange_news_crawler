"""
量化指标计算器
Quantitative Metrics Calculator

用于计算回测结果的各种量化指标，包括：
- 年化指标（APR, 年化波动率）
- 风险调整收益（索提诺比率、卡玛比率）
- 回撤分析（最大回撤持续期）
- 交易质量（盈亏比、平均盈亏）
"""
import logging
import numpy as np
import pandas as pd
from decimal import Decimal
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """量化指标计算器"""

    def __init__(self, risk_free_rate: float = 0.0, trading_days_per_year: int = 365):
        """
        初始化计算器

        Args:
            risk_free_rate: 无风险利率（年化），默认0%
            trading_days_per_year: 每年交易日数，加密货币默认365天
        """
        self.risk_free_rate = risk_free_rate
        self.trading_days_per_year = trading_days_per_year

    def calculate_annual_return(
        self,
        total_return: float,
        days: int
    ) -> Optional[float]:
        """
        计算年化收益率 (Annual Percentage Rate)

        公式: APR = (1 + total_return) ^ (365 / days) - 1

        Args:
            total_return: 总收益率（小数形式，如0.5表示50%）
            days: 回测天数

        Returns:
            float: 年化收益率，如果计算失败返回None
        """
        if days <= 0:
            logger.warning(f"无效的回测天数: {days}")
            return None

        try:
            apr = (1 + total_return) ** (self.trading_days_per_year / days) - 1
            return apr
        except (ValueError, OverflowError) as e:
            logger.error(f"年化收益率计算失败: {e}")
            return None

    def calculate_annual_volatility(
        self,
        daily_returns: pd.Series
    ) -> Optional[float]:
        """
        计算年化波动率

        公式: Annual_Vol = daily_returns.std() * sqrt(trading_days_per_year)

        Args:
            daily_returns: 每日收益率序列

        Returns:
            float: 年化波动率，如果计算失败返回None
        """
        if daily_returns.empty:
            logger.warning("每日收益率数据为空")
            return None

        try:
            # 过滤NaN值
            valid_returns = daily_returns.dropna()
            if len(valid_returns) < 2:
                logger.warning("有效收益率数据点不足")
                return None

            std = valid_returns.std()
            annual_vol = std * np.sqrt(self.trading_days_per_year)
            return annual_vol
        except Exception as e:
            logger.error(f"年化波动率计算失败: {e}")
            return None

    def calculate_sortino_ratio(
        self,
        daily_returns: pd.Series,
        risk_free_rate: Optional[float] = None
    ) -> Optional[float]:
        """
        计算索提诺比率 (Sortino Ratio)

        只考虑下行波动的风险调整收益指标
        公式: Sortino = (avg_return - rf) / downside_std * sqrt(trading_days)

        Args:
            daily_returns: 每日收益率序列
            risk_free_rate: 无风险利率（年化），如果为None则使用初始化的值

        Returns:
            float: 索提诺比率，如果计算失败返回None
        """
        if daily_returns.empty:
            logger.warning("每日收益率数据为空")
            return None

        rf = risk_free_rate if risk_free_rate is not None else self.risk_free_rate
        daily_rf = rf / self.trading_days_per_year

        try:
            # 过滤NaN值
            valid_returns = daily_returns.dropna()
            if len(valid_returns) < 2:
                logger.warning("有效收益率数据点不足")
                return None

            # 计算超额收益
            excess_returns = valid_returns - daily_rf

            # 只考虑负收益（下行风险）
            downside_returns = valid_returns[valid_returns < 0]

            if len(downside_returns) == 0:
                # 没有负收益，索提诺比率为无穷大
                return float('inf') if excess_returns.mean() > 0 else 0.0

            # 下行标准差
            downside_std = downside_returns.std()

            if downside_std == 0:
                return float('inf') if excess_returns.mean() > 0 else 0.0

            # 年化索提诺比率
            sortino = (excess_returns.mean() * self.trading_days_per_year) / \
                      (downside_std * np.sqrt(self.trading_days_per_year))

            return sortino
        except Exception as e:
            logger.error(f"索提诺比率计算失败: {e}")
            return None

    def calculate_calmar_ratio(
        self,
        annual_return: float,
        max_drawdown: float
    ) -> Optional[float]:
        """
        计算卡玛比率 (Calmar Ratio)

        年化收益率与最大回撤的比值，衡量风险调整后的收益
        公式: Calmar = annual_return / abs(max_drawdown)

        Args:
            annual_return: 年化收益率
            max_drawdown: 最大回撤（小数形式，如-0.2表示-20%）

        Returns:
            float: 卡玛比率，如果计算失败返回None
        """
        try:
            abs_max_dd = abs(max_drawdown)

            if abs_max_dd == 0:
                # 没有回撤，卡玛比率为无穷大（如果有正收益）
                return float('inf') if annual_return > 0 else 0.0

            calmar = annual_return / abs_max_dd
            return calmar
        except Exception as e:
            logger.error(f"卡玛比率计算失败: {e}")
            return None

    def calculate_max_drawdown_duration(
        self,
        equity_curve: pd.Series
    ) -> Optional[int]:
        """
        计算最大回撤持续期

        从峰值到恢复峰值的最长时间（天数）

        Args:
            equity_curve: 权益曲线序列（时间索引）

        Returns:
            int: 最大回撤持续期（天数），如果计算失败返回None
        """
        if equity_curve.empty:
            logger.warning("权益曲线数据为空")
            return None

        try:
            # 计算滚动最大值
            running_max = equity_curve.expanding().max()

            # 计算回撤
            drawdown = (equity_curve - running_max) / running_max

            # 标记是否处于回撤期
            in_drawdown = drawdown < 0

            # 查找所有回撤期的持续时间
            drawdown_periods = []
            start_idx = None

            for i in range(len(in_drawdown)):
                if in_drawdown.iloc[i] and start_idx is None:
                    # 回撤开始
                    start_idx = i
                elif not in_drawdown.iloc[i] and start_idx is not None:
                    # 回撤结束（恢复到峰值）
                    duration = i - start_idx
                    drawdown_periods.append(duration)
                    start_idx = None

            # 如果最后仍在回撤中，计算到当前时刻
            if start_idx is not None:
                duration = len(in_drawdown) - start_idx
                drawdown_periods.append(duration)

            if not drawdown_periods:
                return 0

            # 返回最长回撤持续期
            max_duration = max(drawdown_periods)

            # 转换为天数（根据时间索引计算）
            if isinstance(equity_curve.index, pd.DatetimeIndex):
                # 根据K线间隔计算实际天数
                time_diff = equity_curve.index[-1] - equity_curve.index[0]
                total_days = time_diff.days
                avg_interval_days = total_days / len(equity_curve) if len(equity_curve) > 1 else 1
                max_duration_days = int(max_duration * avg_interval_days)
            else:
                # 如果没有时间索引，返回K线根数
                max_duration_days = max_duration

            return max_duration_days

        except Exception as e:
            logger.error(f"最大回撤持续期计算失败: {e}")
            return None

    def calculate_profit_factor(
        self,
        trades_pnl: List[float]
    ) -> Optional[float]:
        """
        计算盈亏比 (Profit Factor)

        总盈利 / 总亏损的比值

        Args:
            trades_pnl: 每笔交易的盈亏列表

        Returns:
            float: 盈亏比，如果计算失败返回None
        """
        if not trades_pnl:
            logger.warning("交易盈亏数据为空")
            return None

        try:
            trades_array = np.array(trades_pnl)

            # 总盈利
            profits = trades_array[trades_array > 0]
            total_profit = profits.sum() if len(profits) > 0 else 0

            # 总亏损（绝对值）
            losses = trades_array[trades_array < 0]
            total_loss = abs(losses.sum()) if len(losses) > 0 else 0

            if total_loss == 0:
                # 没有亏损交易
                return float('inf') if total_profit > 0 else 0.0

            profit_factor = total_profit / total_loss
            return profit_factor

        except Exception as e:
            logger.error(f"盈亏比计算失败: {e}")
            return None

    def calculate_avg_win_loss(
        self,
        trades_pnl: List[float]
    ) -> Dict[str, Optional[float]]:
        """
        计算平均盈利和平均亏损

        Args:
            trades_pnl: 每笔交易的盈亏列表

        Returns:
            dict: {'avg_win': 平均盈利, 'avg_loss': 平均亏损}
        """
        if not trades_pnl:
            logger.warning("交易盈亏数据为空")
            return {'avg_win': None, 'avg_loss': None}

        try:
            trades_array = np.array(trades_pnl)

            # 盈利交易
            profits = trades_array[trades_array > 0]
            avg_win = profits.mean() if len(profits) > 0 else 0.0

            # 亏损交易
            losses = trades_array[trades_array < 0]
            avg_loss = losses.mean() if len(losses) > 0 else 0.0

            return {
                'avg_win': float(avg_win),
                'avg_loss': float(avg_loss)
            }

        except Exception as e:
            logger.error(f"平均盈亏计算失败: {e}")
            return {'avg_win': None, 'avg_loss': None}

    def calculate_all_metrics(
        self,
        total_return: float,
        days: int,
        daily_returns: pd.Series,
        equity_curve: pd.Series,
        trades_pnl: List[float],
        max_drawdown: float
    ) -> Dict[str, Any]:
        """
        计算所有增强指标

        Args:
            total_return: 总收益率
            days: 回测天数
            daily_returns: 每日收益率序列
            equity_curve: 权益曲线序列
            trades_pnl: 每笔交易盈亏列表
            max_drawdown: 最大回撤

        Returns:
            dict: 包含所有计算出的指标
        """
        logger.info("开始计算增强指标...")

        # 年化指标
        annual_return = self.calculate_annual_return(total_return, days)
        annual_volatility = self.calculate_annual_volatility(daily_returns)

        # 风险调整收益
        sortino_ratio = self.calculate_sortino_ratio(daily_returns)
        calmar_ratio = self.calculate_calmar_ratio(
            annual_return if annual_return else 0,
            max_drawdown
        )

        # 回撤分析
        max_dd_duration = self.calculate_max_drawdown_duration(equity_curve)

        # 交易质量
        profit_factor = self.calculate_profit_factor(trades_pnl)
        avg_win_loss = self.calculate_avg_win_loss(trades_pnl)

        metrics = {
            'annual_return': annual_return,
            'annual_volatility': annual_volatility,
            'sortino_ratio': sortino_ratio,
            'calmar_ratio': calmar_ratio,
            'max_drawdown_duration': max_dd_duration,
            'profit_factor': profit_factor,
            'avg_win': avg_win_loss['avg_win'],
            'avg_loss': avg_win_loss['avg_loss']
        }

        # 记录计算结果
        logger.info(f"增强指标计算完成:")
        logger.info(f"  年化收益率: {annual_return:.2%}" if annual_return else "  年化收益率: N/A")
        logger.info(f"  年化波动率: {annual_volatility:.2%}" if annual_volatility else "  年化波动率: N/A")
        logger.info(f"  索提诺比率: {sortino_ratio:.2f}" if sortino_ratio and not np.isinf(sortino_ratio) else "  索提诺比率: N/A")
        logger.info(f"  卡玛比率: {calmar_ratio:.2f}" if calmar_ratio and not np.isinf(calmar_ratio) else "  卡玛比率: N/A")
        logger.info(f"  最大回撤持续期: {max_dd_duration}天" if max_dd_duration is not None else "  最大回撤持续期: N/A")
        logger.info(f"  盈亏比: {profit_factor:.2f}" if profit_factor and not np.isinf(profit_factor) else "  盈亏比: N/A")

        return metrics
