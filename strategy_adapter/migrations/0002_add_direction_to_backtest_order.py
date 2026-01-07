# Generated manually for iteration 015

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('strategy_adapter', '0001_create_backtest_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='backtestorder',
            name='direction',
            field=models.CharField(
                choices=[('long', '做多'), ('short', '做空')],
                default='long',
                help_text='交易方向：long（做多）或 short（做空）',
                max_length=10,
                verbose_name='交易方向'
            ),
        ),
        migrations.AddIndex(
            model_name='backtestorder',
            index=models.Index(fields=['direction'], name='strategy_ad_directi_a7b9c3_idx'),
        ),
    ]
