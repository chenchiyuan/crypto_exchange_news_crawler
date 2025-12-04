# Generated manually for entry recommendation fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('grid_trading', '0013_add_ma_slope_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='screeningresultmodel',
            name='rsi_15m',
            field=models.FloatField(default=50.0, help_text='15分钟RSI指标', verbose_name='RSI(15m)'),
        ),
        migrations.AddField(
            model_name='screeningresultmodel',
            name='recommended_entry_price',
            field=models.DecimalField(blank=True, decimal_places=8, help_text='推荐挂单价', max_digits=20, null=True, verbose_name='推荐挂单价'),
        ),
        migrations.AddField(
            model_name='screeningresultmodel',
            name='entry_trigger_prob_24h',
            field=models.FloatField(default=0.0, help_text='24小时内触发概率(0-1)', verbose_name='触发概率(24h)'),
        ),
        migrations.AddField(
            model_name='screeningresultmodel',
            name='entry_trigger_prob_72h',
            field=models.FloatField(default=0.0, help_text='72小时内触发概率(0-1)', verbose_name='触发概率(72h)'),
        ),
        migrations.AddField(
            model_name='screeningresultmodel',
            name='entry_strategy_label',
            field=models.CharField(default='立即入场', help_text='立即入场/保守反弹/理论反弹', max_length=20, verbose_name='入场策略'),
        ),
        migrations.AddField(
            model_name='screeningresultmodel',
            name='entry_rebound_pct',
            field=models.FloatField(default=0.0, help_text='相对当前价的反弹百分比', verbose_name='反弹幅度(%)'),
        ),
        migrations.AddField(
            model_name='screeningresultmodel',
            name='entry_avg_trigger_time',
            field=models.FloatField(default=0.0, help_text='历史平均触发时间（小时）', verbose_name='平均触发时间(h)'),
        ),
        migrations.AddField(
            model_name='screeningresultmodel',
            name='entry_expected_return_24h',
            field=models.FloatField(default=0.0, help_text='24小时期望收益', verbose_name='期望收益(24h)'),
        ),
    ]
