# Generated migration for adding config_strategy_id field
# TASK-017-011: 为多策略回测添加配置策略ID字段

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('strategy_adapter', '0002_add_direction_to_backtest_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='backtestorder',
            name='config_strategy_id',
            field=models.CharField(
                blank=True,
                help_text='多策略回测时的配置策略ID（如 strategy_1, strategy_2）',
                max_length=100,
                null=True,
                verbose_name='配置策略ID'
            ),
        ),
    ]
