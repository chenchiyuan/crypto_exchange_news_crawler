"""
回测报告生成器
Backtest Report Generator

生成详细的回测报告
"""
from decimal import Decimal
from typing import Dict
from datetime import datetime
import logging

from grid_trading.services.backtest.backtest_engine import BacktestResult

logger = logging.getLogger(__name__)


class BacktestReportGenerator:
    """回测报告生成器"""
    
    def __init__(self, result: BacktestResult, config_name: str):
        """
        初始化报告生成器
        
        Args:
            result: 回测结果
            config_name: 配置名称
        """
        self.result = result
        self.config_name = config_name
    
    def generate_text_report(self) -> str:
        """
        生成文本格式报告
        
        Returns:
            报告文本
        """
        lines = []
        lines.append("=" * 60)
        lines.append(f"网格交易回测报告 - {self.config_name}")
        lines.append("=" * 60)
        lines.append("")
        
        # 基本信息
        lines.append("【基本信息】")
        lines.append(f"回测时间: {self.result.start_time} - {self.result.end_time}")
        
        if self.result.start_time and self.result.end_time:
            duration = self.result.end_time - self.result.start_time
            lines.append(f"回测时长: {duration.days}天 {duration.seconds // 3600}小时")
        
        lines.append(f"K线数量: {self.result.total_klines}")
        lines.append("")
        
        # 盈亏统计
        lines.append("【盈亏统计】")
        lines.append(f"已实现盈亏: {self.result.realized_pnl:.4f}")
        lines.append(f"未实现盈亏: {self.result.unrealized_pnl:.4f}")
        lines.append(f"总盈亏:     {self.result.total_pnl:.4f}")
        lines.append(f"总收益率:   {self.result.total_return_pct:.2f}%")
        lines.append("")
        
        # 交易统计
        lines.append("【交易统计】")
        lines.append(f"总交易次数: {self.result.total_trades}")
        lines.append(f"完整轮次:   {self.result.total_rounds}")
        lines.append(f"盈利轮次:   {self.result.winning_rounds}")
        lines.append(f"亏损轮次:   {self.result.losing_rounds}")
        
        if self.result.total_rounds > 0:
            win_rate = self.result.winning_rounds / self.result.total_rounds * 100
            lines.append(f"胜率:       {win_rate:.2f}%")
        lines.append("")
        
        # 风险指标
        lines.append("【风险指标】")
        lines.append(f"最大回撤:   {self.result.max_drawdown:.4f}")
        lines.append(f"最大回撤率: {self.result.max_drawdown_pct:.2f}%")
        lines.append("")
        
        # 权益曲线摘要
        if self.result.equity_curve:
            lines.append("【权益曲线】")
            lines.append(f"起始权益: {self.result.equity_curve[0]['equity']:.2f}")
            lines.append(f"最终权益: {self.result.equity_curve[-1]['equity']:.2f}")
            
            max_equity = max(p['equity'] for p in self.result.equity_curve)
            min_equity = min(p['equity'] for p in self.result.equity_curve)
            lines.append(f"最高权益: {max_equity:.2f}")
            lines.append(f"最低权益: {min_equity:.2f}")
            lines.append("")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def generate_json_report(self) -> Dict:
        """
        生成JSON格式报告
        
        Returns:
            报告字典
        """
        return {
            'config_name': self.config_name,
            'backtest_period': {
                'start': self.result.start_time.isoformat() if self.result.start_time else None,
                'end': self.result.end_time.isoformat() if self.result.end_time else None,
                'total_klines': self.result.total_klines
            },
            'pnl': {
                'realized': float(self.result.realized_pnl),
                'unrealized': float(self.result.unrealized_pnl),
                'total': float(self.result.total_pnl),
                'return_pct': float(self.result.total_return_pct)
            },
            'trades': {
                'total_trades': self.result.total_trades,
                'total_rounds': self.result.total_rounds,
                'winning_rounds': self.result.winning_rounds,
                'losing_rounds': self.result.losing_rounds,
                'win_rate': float(self.result.win_rate) if hasattr(self.result, 'win_rate') else 0
            },
            'risk': {
                'max_drawdown': float(self.result.max_drawdown),
                'max_drawdown_pct': float(self.result.max_drawdown_pct)
            },
            'equity_curve': [
                {
                    'timestamp': p['timestamp'].isoformat(),
                    'equity': float(p['equity']),
                    'realized_pnl': float(p['realized_pnl']),
                    'unrealized_pnl': float(p['unrealized_pnl'])
                }
                for p in self.result.equity_curve
            ]
        }
    
    def save_to_file(self, filepath: str, format: str = 'text'):
        """
        保存报告到文件
        
        Args:
            filepath: 文件路径
            format: 格式 (text/json)
        """
        if format == 'text':
            content = self.generate_text_report()
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        
        elif format == 'json':
            import json
            content = self.generate_json_report()
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(content, f, indent=2, ensure_ascii=False)
        
        logger.info(f"报告已保存到: {filepath}")
