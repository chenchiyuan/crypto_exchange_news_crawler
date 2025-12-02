"""
可视化回测服务
Visual Backtest Service
"""
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from backtest.services.backtest_engine import BacktestEngine
from backtest.models import BacktestResult

logger = logging.getLogger(__name__)


class VisualBacktest:
    """可视化回测器"""

    def __init__(self, output_dir: str = 'backtest_reports'):
        """
        初始化

        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False

    def visualize_grid_backtest(
        self,
        result: BacktestResult,
        engine: BacktestEngine,
        entries: pd.Series,
        exits: pd.Series,
        grid_levels: List[float] = None,
        base_price: float = None,
        stop_loss_price: float = None,
        save_path: Optional[str] = None,
        show: bool = True
    ) -> str:
        """
        可视化网格策略回测全过程

        Args:
            result: 回测结果
            engine: 回测引擎
            entries: 买入信号
            exits: 卖出信号
            grid_levels: 网格价格层级 [(buy_price, sell_price), ...]
            base_price: 基准价格
            stop_loss_price: 止损价格
            save_path: 保存路径
            show: 是否显示

        Returns:
            str: 保存的文件路径
        """
        df = engine.df
        close = df['Close']

        # 创建图表（3个子图）
        fig = plt.figure(figsize=(20, 12))
        gs = fig.add_gridspec(3, 1, height_ratios=[3, 1, 1], hspace=0.3)

        # 子图1: 价格、网格、买卖信号
        ax1 = fig.add_subplot(gs[0])
        # 子图2: 持仓状态
        ax2 = fig.add_subplot(gs[1], sharex=ax1)
        # 子图3: 资金曲线
        ax3 = fig.add_subplot(gs[2], sharex=ax1)

        # ========== 子图1: 价格图 ==========
        # 绘制价格曲线
        ax1.plot(close.index, close.values,
                label='Price', linewidth=1.5, color='black', alpha=0.7)

        # 绘制网格线
        if grid_levels and base_price:
            # 基准价格线
            ax1.axhline(y=base_price, color='blue', linestyle='--',
                       linewidth=1, alpha=0.5, label='Base Price')

            # 买入网格线（绿色）
            for i, (buy_price, _) in enumerate(grid_levels):
                ax1.axhline(y=buy_price, color='green', linestyle=':',
                           linewidth=0.8, alpha=0.4)
                if i == 0:  # 只在第一条线上添加标签
                    ax1.text(close.index[0], buy_price, f' Buy Grid',
                            fontsize=8, color='green', va='center')

            # 卖出网格线（红色）
            for i, (_, sell_price) in enumerate(grid_levels):
                ax1.axhline(y=sell_price, color='red', linestyle=':',
                           linewidth=0.8, alpha=0.4)
                if i == 0:
                    ax1.text(close.index[0], sell_price, f' Sell Grid',
                            fontsize=8, color='red', va='center')

        # 绘制止损线
        if stop_loss_price:
            ax1.axhline(y=stop_loss_price, color='purple', linestyle='--',
                       linewidth=1.5, alpha=0.7, label='Stop Loss')

        # 标注买入信号
        buy_signals = entries[entries == True]
        if len(buy_signals) > 0:
            ax1.scatter(buy_signals.index,
                       close.loc[buy_signals.index],
                       marker='^', color='green', s=200,
                       label='Buy Signal', zorder=5, edgecolors='darkgreen', linewidths=2)

        # 标注卖出信号
        sell_signals = exits[exits == True]
        if len(sell_signals) > 0:
            ax1.scatter(sell_signals.index,
                       close.loc[sell_signals.index],
                       marker='v', color='red', s=200,
                       label='Sell Signal', zorder=5, edgecolors='darkred', linewidths=2)

        ax1.set_ylabel('Price (USDT)', fontsize=12, fontweight='bold')
        ax1.set_title(f'{result.name} - Complete Backtest Visualization',
                     fontsize=14, fontweight='bold', pad=20)
        ax1.legend(loc='upper left', fontsize=10)
        ax1.grid(True, alpha=0.3)

        # ========== 子图2: 持仓状态 ==========
        # 计算持仓状态
        position = pd.Series(0, index=close.index)
        current_position = 0

        for i in range(len(close)):
            if entries.iloc[i]:
                current_position = 1
            elif exits.iloc[i]:
                current_position = 0
            position.iloc[i] = current_position

        # 绘制持仓状态
        ax2.fill_between(position.index, 0, position.values,
                        where=(position.values > 0),
                        color='lightgreen', alpha=0.5, label='Holding')
        ax2.fill_between(position.index, 0, position.values,
                        where=(position.values == 0),
                        color='lightgray', alpha=0.3, label='Empty')

        ax2.set_ylabel('Position', fontsize=12, fontweight='bold')
        ax2.set_ylim(-0.1, 1.1)
        ax2.set_yticks([0, 1])
        ax2.set_yticklabels(['Empty', 'Holding'])
        ax2.legend(loc='upper left', fontsize=10)
        ax2.grid(True, alpha=0.3, axis='x')

        # ========== 子图3: 资金曲线 ==========
        if result.equity_curve:
            equity_df = pd.DataFrame([
                {'time': pd.Timestamp(k), 'value': v}
                for k, v in result.equity_curve.items()
            ]).sort_values('time')

            ax3.plot(equity_df['time'], equity_df['value'],
                    linewidth=2, color='blue', label='Portfolio Value')
            ax3.axhline(y=float(result.initial_cash), color='gray',
                       linestyle='--', linewidth=1, alpha=0.5,
                       label=f'Initial Cash (${float(result.initial_cash):,.0f})')

            # 标注最终价值
            final_value = equity_df['value'].iloc[-1]
            ax3.text(equity_df['time'].iloc[-1], final_value,
                    f' ${final_value:,.2f}',
                    fontsize=10, color='blue', fontweight='bold', va='center')

        ax3.set_xlabel('Time', fontsize=12, fontweight='bold')
        ax3.set_ylabel('Portfolio Value (USDT)', fontsize=12, fontweight='bold')
        ax3.legend(loc='upper left', fontsize=10)
        ax3.grid(True, alpha=0.3)
        ax3.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

        # ========== 添加统计信息文本框 ==========
        stats_text = (
            f"📊 Backtest Statistics\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Total Return: {float(result.total_return)*100:+.2f}%\n"
            f"Sharpe Ratio: {float(result.sharpe_ratio):.2f}\n"
            f"Max Drawdown: {float(result.max_drawdown):.2f}%\n"
            f"Win Rate: {float(result.win_rate):.1f}%\n"
            f"Total Trades: {result.total_trades}\n"
            f"Profitable: {result.profitable_trades}\n"
            f"Losing: {result.losing_trades}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Initial: ${float(result.initial_cash):,.2f}\n"
            f"Final: ${float(result.final_value):,.2f}"
        )

        # 放置在右上角
        ax1.text(0.98, 0.98, stats_text,
                transform=ax1.transAxes,
                fontsize=10,
                verticalalignment='top',
                horizontalalignment='right',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
                family='monospace')

        plt.tight_layout()

        # 保存
        if not save_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            save_path = self.output_dir / f'visual_backtest_{timestamp}.png'
        else:
            save_path = Path(save_path)

        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"可视化回测图已保存: {save_path}")

        if show:
            plt.show()
        else:
            plt.close()

        return str(save_path)

    def create_trade_timeline(
        self,
        result: BacktestResult,
        save_path: Optional[str] = None,
        show: bool = True
    ) -> str:
        """
        创建交易时间线图

        Args:
            result: 回测结果
            save_path: 保存路径
            show: 是否显示

        Returns:
            str: 保存的文件路径
        """
        trades = result.trades_detail

        if not trades:
            logger.warning("没有交易记录")
            return ""

        fig, ax = plt.subplots(figsize=(16, 8))

        # 转换为DataFrame
        trades_df = pd.DataFrame(trades)

        # 确保时间列是datetime类型
        for col in ['Entry Timestamp', 'Exit Timestamp']:
            if col in trades_df.columns:
                trades_df[col] = pd.to_datetime(trades_df[col])

        # 绘制每笔交易
        for idx, trade in trades_df.iterrows():
            entry_time = trade.get('Entry Timestamp')
            exit_time = trade.get('Exit Timestamp')
            pnl = trade.get('PnL', 0)
            return_pct = trade.get('Return', 0) * 100

            # 颜色：盈利为绿色，亏损为红色
            color = 'green' if pnl > 0 else 'red'
            alpha = 0.6

            # 绘制交易区间
            if entry_time and exit_time:
                ax.barh(idx, (exit_time - entry_time).total_seconds() / 3600,
                       left=entry_time, height=0.8, color=color, alpha=alpha,
                       edgecolor='black', linewidth=1)

                # 标注收益
                mid_time = entry_time + (exit_time - entry_time) / 2
                ax.text(mid_time, idx, f'{return_pct:+.1f}%',
                       ha='center', va='center', fontsize=9,
                       fontweight='bold', color='white')

        ax.set_xlabel('Time', fontsize=12, fontweight='bold')
        ax.set_ylabel('Trade Number', fontsize=12, fontweight='bold')
        ax.set_title(f'{result.name} - Trade Timeline',
                    fontsize=14, fontweight='bold')
        ax.set_yticks(range(len(trades_df)))
        ax.set_yticklabels([f'Trade {i+1}' for i in range(len(trades_df))])
        ax.grid(True, alpha=0.3, axis='x')

        # 添加图例
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='green', alpha=0.6, label='Profitable'),
            Patch(facecolor='red', alpha=0.6, label='Losing')
        ]
        ax.legend(handles=legend_elements, loc='upper right')

        plt.tight_layout()

        # 保存
        if not save_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            save_path = self.output_dir / f'trade_timeline_{timestamp}.png'
        else:
            save_path = Path(save_path)

        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"交易时间线图已保存: {save_path}")

        if show:
            plt.show()
        else:
            plt.close()

        return str(save_path)
