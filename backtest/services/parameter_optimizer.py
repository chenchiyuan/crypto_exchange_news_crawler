"""
参数优化服务
Parameter Optimizer Service
"""
import logging
import itertools
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime

from backtest.services.backtest_engine import BacktestEngine
from backtest.services.grid_strategy_vbt import GridStrategyVBT
from backtest.models import BacktestResult

logger = logging.getLogger(__name__)


class ParameterOptimizer:
    """参数优化器"""

    def __init__(
        self,
        symbol: str,
        interval: str,
        start_date=None,
        end_date=None,
        initial_cash: float = 10000.0
    ):
        """
        初始化优化器

        Args:
            symbol: 交易对
            interval: 时间周期
            start_date: 开始日期
            end_date: 结束日期
            initial_cash: 初始资金
        """
        self.symbol = symbol
        self.interval = interval
        self.start_date = start_date
        self.end_date = end_date
        self.initial_cash = initial_cash

        # 创建回测引擎
        self.engine = BacktestEngine(
            symbol=symbol,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash
        )

    def grid_search(
        self,
        grid_step_range: List[float],
        grid_levels_range: List[int],
        stop_loss_range: Optional[List[float]] = None
    ) -> pd.DataFrame:
        """
        网格搜索最优参数

        Args:
            grid_step_range: 网格步长范围，如 [0.005, 0.01, 0.015, 0.02]
            grid_levels_range: 网格层数范围，如 [5, 10, 15, 20]
            stop_loss_range: 止损范围，如 [None, 0.05, 0.10]

        Returns:
            pd.DataFrame: 优化结果表
        """
        logger.info(
            f"开始参数网格搜索: "
            f"步长={len(grid_step_range)}种, "
            f"层数={len(grid_levels_range)}种"
        )

        results = []

        # 生成参数组合
        if stop_loss_range is None:
            stop_loss_range = [None]

        param_combinations = list(itertools.product(
            grid_step_range,
            grid_levels_range,
            stop_loss_range
        ))

        total = len(param_combinations)
        logger.info(f"总共需要测试 {total} 种参数组合")

        # 遍历所有组合
        for idx, (grid_step, grid_levels, stop_loss) in enumerate(param_combinations, 1):
            stop_loss_str = f"{stop_loss*100:.0f}%" if stop_loss else "None"
            logger.info(
                f"[{idx}/{total}] 测试参数: "
                f"步长={grid_step*100:.1f}%, 层数={grid_levels}, "
                f"止损={stop_loss_str}"
            )

            try:
                # 创建策略
                strategy = GridStrategyVBT(
                    engine=self.engine,
                    grid_step_pct=grid_step,
                    grid_levels=grid_levels,
                    stop_loss_pct=stop_loss
                )

                # 运行回测
                result = strategy.run()

                # 记录结果
                results.append({
                    'grid_step_pct': grid_step,
                    'grid_levels': grid_levels,
                    'stop_loss_pct': stop_loss,
                    'total_return': float(result.total_return),
                    'sharpe_ratio': float(result.sharpe_ratio) if result.sharpe_ratio else np.nan,
                    'max_drawdown': float(result.max_drawdown),
                    'win_rate': float(result.win_rate),
                    'total_trades': result.total_trades,
                    'final_value': float(result.final_value),
                    'result_id': result.id
                })

            except Exception as e:
                logger.error(f"参数组合测试失败: {e}")
                results.append({
                    'grid_step_pct': grid_step,
                    'grid_levels': grid_levels,
                    'stop_loss_pct': stop_loss,
                    'total_return': np.nan,
                    'sharpe_ratio': np.nan,
                    'max_drawdown': np.nan,
                    'win_rate': np.nan,
                    'total_trades': 0,
                    'final_value': np.nan,
                    'result_id': None
                })

        # 转换为DataFrame
        df = pd.DataFrame(results)

        # 排序（按夏普比率）
        df = df.sort_values('sharpe_ratio', ascending=False, na_position='last')

        logger.info(f"参数网格搜索完成，共测试 {len(df)} 种组合")

        return df

    def plot_heatmap(
        self,
        df: pd.DataFrame,
        metric: str = 'sharpe_ratio',
        save_path: Optional[str] = None,
        show: bool = False
    ) -> str:
        """
        绘制参数优化热力图

        Args:
            df: 优化结果DataFrame
            metric: 指标名称 (total_return, sharpe_ratio, max_drawdown)
            save_path: 保存路径
            show: 是否显示

        Returns:
            str: 保存的文件路径
        """
        # 过滤掉有止损的结果（简化热力图）
        df_no_sl = df[df['stop_loss_pct'].isna()].copy()

        if df_no_sl.empty:
            logger.warning("没有无止损的结果，无法生成热力图")
            return ""

        # 创建pivot表
        pivot = df_no_sl.pivot_table(
            values=metric,
            index='grid_levels',
            columns='grid_step_pct',
            aggfunc='mean'
        )

        # 绘制热力图
        fig, ax = plt.subplots(figsize=(12, 8))

        # 根据指标选择颜色方案
        if metric == 'max_drawdown':
            cmap = 'RdYlGn_r'  # 回撤越小越好（绿色）
        else:
            cmap = 'RdYlGn'    # 值越大越好（绿色）

        im = ax.imshow(pivot.values, cmap=cmap, aspect='auto')

        # 设置坐标轴
        ax.set_xticks(np.arange(len(pivot.columns)))
        ax.set_yticks(np.arange(len(pivot.index)))
        ax.set_xticklabels([f'{x*100:.1f}%' for x in pivot.columns])
        ax.set_yticklabels(pivot.index)

        ax.set_xlabel('Grid Step (%)', fontsize=12, fontweight='bold')
        ax.set_ylabel('Grid Levels', fontsize=12, fontweight='bold')

        # 标题
        metric_name_map = {
            'total_return': 'Total Return',
            'sharpe_ratio': 'Sharpe Ratio',
            'max_drawdown': 'Max Drawdown',
            'win_rate': 'Win Rate'
        }
        title = f'Parameter Optimization Heatmap - {metric_name_map.get(metric, metric)}'
        ax.set_title(title, fontsize=14, fontweight='bold')

        # 添加数值标注
        for i in range(len(pivot.index)):
            for j in range(len(pivot.columns)):
                value = pivot.values[i, j]
                if not np.isnan(value):
                    if metric in ['total_return', 'max_drawdown', 'win_rate']:
                        text = f'{value*100:.1f}%' if metric != 'win_rate' else f'{value:.1f}%'
                    else:
                        text = f'{value:.2f}'

                    ax.text(j, i, text, ha="center", va="center",
                           color="black", fontsize=9, fontweight='bold')

        # 颜色条
        cbar = plt.colorbar(im, ax=ax)
        if metric in ['total_return', 'max_drawdown', 'win_rate']:
            cbar.set_label(f'{metric_name_map.get(metric, metric)} (%)', fontsize=10)
        else:
            cbar.set_label(metric_name_map.get(metric, metric), fontsize=10)

        plt.tight_layout()

        # 保存
        if not save_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            save_path = f'backtest_reports/heatmap_{metric}_{timestamp}.png'

        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"热力图已保存: {save_path}")

        if show:
            plt.show()
        else:
            plt.close()

        return str(save_path)

    def get_best_params(
        self,
        df: pd.DataFrame,
        metric: str = 'sharpe_ratio',
        top_n: int = 5
    ) -> pd.DataFrame:
        """
        获取最优参数

        Args:
            df: 优化结果DataFrame
            metric: 优化目标指标
            top_n: 返回前N个

        Returns:
            pd.DataFrame: 最优参数表
        """
        # 按指标排序
        ascending = (metric == 'max_drawdown')  # 回撤越小越好
        df_sorted = df.sort_values(metric, ascending=ascending, na_position='last')

        # 选择前N个
        top_params = df_sorted.head(top_n).copy()

        # 格式化显示
        top_params['grid_step_display'] = top_params['grid_step_pct'].apply(lambda x: f'{x*100:.1f}%')
        top_params['total_return_display'] = top_params['total_return'].apply(lambda x: f'{x*100:.2f}%')
        top_params['sharpe_display'] = top_params['sharpe_ratio'].apply(lambda x: f'{x:.2f}' if not pd.isna(x) else 'N/A')
        top_params['max_dd_display'] = top_params['max_drawdown'].apply(lambda x: f'{x*100:.2f}%' if not pd.isna(x) else 'N/A')

        return top_params
