# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('grid_trading', '0009_add_has_spot_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='screeningresultmodel',
            name='volume_24h_calculated',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                default=0,
                help_text='24小时交易量(USDT) - 从1440根1m K线计算',
                max_digits=20,
                null=True,
                verbose_name='24h交易量(计算值)'
            ),
        ),
    ]
