"""
回测结果分析服务
Backtest Result Analyzer Service
"""
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from backtest.models import BacktestResult

logger = logging.getLogger(__name__)


class ResultAnalyzer:
    """回测结果分析器"""

    def __init__(self, output_dir: str = 'backtest_reports'):
        """
        初始化分析器

        Args:
            output_dir: 报告输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 设置中文字体支持
        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False

    def plot_equity_curve(
        self,
        result_ids: List[int],
        save_path: Optional[str] = None,
        show: bool = False
    ) -> str:
        """
        绘制权益曲线

        Args:
            result_ids: 回测结果ID列表
            save_path: 保存路径（可选）
            show: 是否显示图表

        Returns:
            str: 保存的文件路径
        """
        results = BacktestResult.objects.filter(id__in=result_ids)

        if not results.exists():
            raise ValueError(f"未找到回测结果: {result_ids}")

        fig, ax = plt.subplots(figsize=(14, 8))

        # 为每个策略绘制权益曲线
        for result in results:
            equity_curve = result.equity_curve

            if not equity_curve:
                logger.warning(f"回测结果{result.id}没有权益曲线数据")
                continue

            # 转换为DataFrame
            df = pd.DataFrame([
                {'time': pd.Timestamp(k), 'value': v}
                for k, v in equity_curve.items()
            ])
            df = df.sort_values('time')

            # 绘制曲线
            label = f"{result.name} ({float(result.total_return)*100:.2f}%)"
            ax.plot(df['time'], df['value'], label=label, linewidth=2)

        # 添加基准线（初始资金）
        if results.exists():
            initial_cash = float(results.first().initial_cash)
            ax.axhline(y=initial_cash, color='gray', linestyle='--',
                      linewidth=1, label=f'Initial Cash (${initial_cash:,.0f})')

        # 图表设置
        ax.set_xlabel('Time', fontsize=12)
        ax.set_ylabel('Portfolio Value (USDT)', fontsize=12)
        ax.set_title('Equity Curve Comparison', fontsize=14, fontweight='bold')
        ax.legend(loc='best', fontsize=10)
        ax.grid(True, alpha=0.3)

        # 格式化y轴为货币格式
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

        plt.tight_layout()

        # 保存图表
        if not save_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            save_path = self.output_dir / f'equity_curve_{timestamp}.png'
        else:
            save_path = Path(save_path)

        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"权益曲线已保存: {save_path}")

        if show:
            plt.show()
        else:
            plt.close()

        return str(save_path)

    def plot_drawdown(
        self,
        result_id: int,
        save_path: Optional[str] = None,
        show: bool = False
    ) -> str:
        """
        绘制回撤曲线

        Args:
            result_id: 回测结果ID
            save_path: 保存路径
            show: 是否显示

        Returns:
            str: 保存的文件路径
        """
        result = BacktestResult.objects.get(id=result_id)
        equity_curve = result.equity_curve

        if not equity_curve:
            raise ValueError(f"回测结果{result_id}没有权益曲线数据")

        # 转换为Series
        equity_series = pd.Series({
            pd.Timestamp(k): v for k, v in equity_curve.items()
        }).sort_index()

        # 计算回撤
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max * 100

        # 绘制
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

        # 权益曲线
        ax1.plot(equity_series.index, equity_series.values,
                label='Portfolio Value', linewidth=2, color='blue')
        ax1.plot(running_max.index, running_max.values,
                label='Running Maximum', linewidth=1,
                linestyle='--', color='green', alpha=0.7)
        ax1.set_ylabel('Portfolio Value (USDT)', fontsize=12)
        ax1.set_title(f'{result.name} - Equity & Drawdown',
                     fontsize=14, fontweight='bold')
        ax1.legend(loc='best')
        ax1.grid(True, alpha=0.3)
        ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

        # 回撤曲线
        ax2.fill_between(drawdown.index, 0, drawdown.values,
                        alpha=0.3, color='red', label='Drawdown')
        ax2.plot(drawdown.index, drawdown.values,
                linewidth=1, color='darkred')
        ax2.set_xlabel('Time', fontsize=12)
        ax2.set_ylabel('Drawdown (%)', fontsize=12)
        ax2.legend(loc='best')
        ax2.grid(True, alpha=0.3)

        # 标注最大回撤
        max_dd_idx = drawdown.idxmin()
        max_dd_value = drawdown.min()
        ax2.annotate(f'Max DD: {max_dd_value:.2f}%',
                    xy=(max_dd_idx, max_dd_value),
                    xytext=(10, 10), textcoords='offset points',
                    bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.7),
                    arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))

        plt.tight_layout()

        # 保存
        if not save_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            save_path = self.output_dir / f'drawdown_{result_id}_{timestamp}.png'
        else:
            save_path = Path(save_path)

        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"回撤曲线已保存: {save_path}")

        if show:
            plt.show()
        else:
            plt.close()

        return str(save_path)

    def plot_returns_distribution(
        self,
        result_ids: List[int],
        save_path: Optional[str] = None,
        show: bool = False
    ) -> str:
        """
        绘制收益分布直方图

        Args:
            result_ids: 回测结果ID列表
            save_path: 保存路径
            show: 是否显示

        Returns:
            str: 保存的文件路径
        """
        results = BacktestResult.objects.filter(id__in=result_ids)

        fig, axes = plt.subplots(1, len(results), figsize=(7*len(results), 6))
        if len(results) == 1:
            axes = [axes]

        for idx, result in enumerate(results):
            daily_returns = result.daily_returns

            if not daily_returns:
                logger.warning(f"回测结果{result.id}没有每日收益数据")
                continue

            # 转换为Series
            returns_series = pd.Series({
                pd.Timestamp(k): v for k, v in daily_returns.items()
            }).sort_index()

            # 转换为百分比
            returns_pct = returns_series * 100

            # 绘制直方图
            ax = axes[idx]
            ax.hist(returns_pct, bins=50, alpha=0.7, color='steelblue',
                   edgecolor='black')

            # 统计信息
            mean_return = returns_pct.mean()
            std_return = returns_pct.std()

            # 添加统计线
            ax.axvline(mean_return, color='red', linestyle='--',
                      linewidth=2, label=f'Mean: {mean_return:.3f}%')
            ax.axvline(0, color='gray', linestyle='-',
                      linewidth=1, alpha=0.5)

            # 标注
            ax.set_xlabel('Daily Returns (%)', fontsize=12)
            ax.set_ylabel('Frequency', fontsize=12)
            ax.set_title(f'{result.name}\nReturns Distribution',
                        fontsize=12, fontweight='bold')
            ax.legend()
            ax.grid(True, alpha=0.3)

            # 添加文本框
            textstr = f'Mean: {mean_return:.3f}%\nStd: {std_return:.3f}%\nSharpe: {float(result.sharpe_ratio):.2f}'
            ax.text(0.02, 0.98, textstr, transform=ax.transAxes,
                   fontsize=10, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        plt.tight_layout()

        # 保存
        if not save_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            save_path = self.output_dir / f'returns_dist_{timestamp}.png'
        else:
            save_path = Path(save_path)

        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"收益分布图已保存: {save_path}")

        if show:
            plt.show()
        else:
            plt.close()

        return str(save_path)

    def generate_summary_table(
        self,
        result_ids: List[int]
    ) -> pd.DataFrame:
        """
        生成回测结果汇总表

        Args:
            result_ids: 回测结果ID列表

        Returns:
            pd.DataFrame: 汇总表
        """
        results = BacktestResult.objects.filter(id__in=result_ids).order_by('-total_return')

        data = []
        for result in results:
            params = result.strategy_params
            data.append({
                'ID': result.id,
                'Strategy': result.name,
                'Symbol': result.symbol,
                'Interval': result.interval,
                'Grid Step': f"{params.get('grid_step_pct', 0)*100:.1f}%" if 'grid_step_pct' in params else 'N/A',
                'Grid Levels': params.get('grid_levels', 'N/A'),
                'Total Return': f"{float(result.total_return)*100:.2f}%",
                'Sharpe Ratio': f"{float(result.sharpe_ratio):.2f}" if result.sharpe_ratio else 'N/A',
                'Max Drawdown': f"{float(result.max_drawdown):.2f}%",
                'Win Rate': f"{float(result.win_rate):.2f}%",
                'Total Trades': result.total_trades,
                'Final Value': f"${float(result.final_value):,.2f}",
            })

        df = pd.DataFrame(data)
        return df
