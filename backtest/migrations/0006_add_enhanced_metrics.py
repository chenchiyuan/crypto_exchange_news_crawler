# Generated manually for enhanced metrics

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backtest', '0005_pendingorder'),
    ]

    operations = [
        # 年化指标
        migrations.AddField(
            model_name='backtestresult',
            name='annual_return',
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                help_text='年化收益率 (APR)',
                max_digits=10,
                null=True,
                verbose_name='年化收益率'
            ),
        ),
        migrations.AddField(
            model_name='backtestresult',
            name='annual_volatility',
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                help_text='年化波动率',
                max_digits=10,
                null=True,
                verbose_name='年化波动率'
            ),
        ),
        # 风险调整收益指标
        migrations.AddField(
            model_name='backtestresult',
            name='sortino_ratio',
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                help_text='索提诺比率（只考虑下行风险）',
                max_digits=10,
                null=True,
                verbose_name='索提诺比率'
            ),
        ),
        migrations.AddField(
            model_name='backtestresult',
            name='calmar_ratio',
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                help_text='卡玛比率（年化收益率/最大回撤）',
                max_digits=10,
                null=True,
                verbose_name='卡玛比率'
            ),
        ),
        # 回撤分析
        migrations.AddField(
            model_name='backtestresult',
            name='max_drawdown_duration',
            field=models.IntegerField(
                blank=True,
                help_text='最大回撤持续期（天）',
                null=True,
                verbose_name='最大回撤持续期'
            ),
        ),
        # 交易质量指标
        migrations.AddField(
            model_name='backtestresult',
            name='profit_factor',
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                help_text='盈亏比（总盈利/总亏损）',
                max_digits=10,
                null=True,
                verbose_name='盈亏比'
            ),
        ),
        migrations.AddField(
            model_name='backtestresult',
            name='avg_win',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='平均盈利',
                max_digits=20,
                null=True,
                verbose_name='平均盈利'
            ),
        ),
        migrations.AddField(
            model_name='backtestresult',
            name='avg_loss',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='平均亏损',
                max_digits=20,
                null=True,
                verbose_name='平均亏损'
            ),
        ),
    ]
