"""
网格统计模型 (GridStatistics)
记录网格策略的统计指标
"""
from django.db import models


class GridStatistics(models.Model):
    """网格统计模型"""
    
    # 关联
    config = models.ForeignKey(
        'GridConfig',
        on_delete=models.CASCADE,
        related_name='statistics',
        verbose_name='网格配置'
    )
    
    # 统计周期
    period_start = models.DateTimeField(
        verbose_name='统计周期起始',
        help_text='统计周期的开始时间'
    )
    period_end = models.DateTimeField(
        verbose_name='统计周期结束',
        help_text='统计周期的结束时间'
    )
    
    # 交易统计
    total_trades = models.IntegerField(
        default=0,
        verbose_name='总交易次数',
        help_text='该周期内所有订单的数量'
    )
    filled_entry_orders = models.IntegerField(
        default=0,
        verbose_name='成交开仓单数',
        help_text='开仓订单成交数量'
    )
    filled_exit_orders = models.IntegerField(
        default=0,
        verbose_name='成交平仓单数',
        help_text='平仓订单成交数量'
    )
    canceled_orders = models.IntegerField(
        default=0,
        verbose_name='撤单数',
        help_text='撤销订单的数量'
    )
    
    # 盈亏统计
    realized_pnl = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=0,
        verbose_name='已实现盈亏',
        help_text='已平仓的盈亏'
    )
    unrealized_pnl = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=0,
        verbose_name='未实现盈亏',
        help_text='当前持仓的浮动盈亏'
    )
    total_pnl = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=0,
        verbose_name='总盈亏',
        help_text='已实现 + 未实现盈亏'
    )
    
    # 持仓统计
    max_position_size = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=0,
        verbose_name='最大持仓',
        help_text='该周期内的最大持仓数量'
    )
    avg_position_size = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=0,
        verbose_name='平均持仓',
        help_text='该周期内的平均持仓数量'
    )
    current_position_size = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=0,
        verbose_name='当前持仓',
        help_text='统计时刻的持仓数量'
    )
    
    # 风险统计
    stop_loss_triggered_count = models.IntegerField(
        default=0,
        verbose_name='止损触发次数',
        help_text='止损被触发的次数'
    )
    max_drawdown = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0,
        verbose_name='最大回撤',
        help_text='最大回撤百分比'
    )
    
    # 扩展统计字段(可选)
    skipped_orders_count = models.IntegerField(
        default=0,
        verbose_name='跳过订单数',
        help_text='因持仓限制等原因跳过的订单数'
    )
    avg_fill_time_seconds = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='平均成交时间(秒)',
        help_text='订单从挂单到成交的平均时间'
    )
    grid_utilization_pct = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        verbose_name='网格利用率(%)',
        help_text='被触及的网格层级占总层级的百分比'
    )
    
    # 时间戳
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    
    class Meta:
        verbose_name = '网格统计'
        verbose_name_plural = '网格统计'
        db_table = 'grid_statistics'
        indexes = [
            models.Index(fields=['config', '-period_end'], name='idx_stats_config_period'),
        ]
        ordering = ['-period_end']  # 默认按周期结束时间倒序
    
    def __str__(self):
        return f"{self.config.name} 统计 ({self.period_start} ~ {self.period_end})"
    
    @property
    def fill_rate(self):
        """计算成交率"""
        if self.total_trades == 0:
            return 0
        filled_count = self.filled_entry_orders + self.filled_exit_orders
        return (filled_count / self.total_trades) * 100
    
    @property
    def roi_pct(self):
        """计算收益率百分比 (ROI%)"""
        # 需要知道初始投入，这里假设在config中有initial_capital字段
        # 或者基于max_position_size * avg_price估算
        # 简化版本：基于总盈亏计算
        if hasattr(self.config, 'initial_capital') and self.config.initial_capital > 0:
            return (float(self.total_pnl) / float(self.config.initial_capital)) * 100
        return 0
    
    def update_position_stats(self, current_position):
        """更新持仓统计"""
        if abs(current_position) > abs(self.max_position_size):
            self.max_position_size = abs(current_position)
        self.current_position_size = current_position
        # 平均持仓需要加权计算，这里简化处理
        self.save()
    
    def record_trade(self, is_entry, is_filled, is_canceled=False):
        """记录交易"""
        self.total_trades += 1
        if is_filled:
            if is_entry:
                self.filled_entry_orders += 1
            else:
                self.filled_exit_orders += 1
        if is_canceled:
            self.canceled_orders += 1
        self.save()
    
    def update_pnl(self, realized=None, unrealized=None):
        """更新盈亏"""
        if realized is not None:
            self.realized_pnl = realized
        if unrealized is not None:
            self.unrealized_pnl = unrealized
        self.total_pnl = self.realized_pnl + self.unrealized_pnl
        self.save()
