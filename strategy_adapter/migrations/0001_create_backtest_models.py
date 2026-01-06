# Generated manually for TASK-014-012, TASK-014-013

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """
    创建回测结果数据模型

    Purpose:
        创建 BacktestResult 和 BacktestOrder 两个表，用于持久化存储回测结果。

    关联任务: TASK-014-012, TASK-014-013, TASK-014-015
    关联需求: FP-014-018, FP-014-019（prd.md）
    """

    initial = True

    dependencies = []

    operations = [
        # BacktestResult 表
        migrations.CreateModel(
            name='BacktestResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                # 基本信息
                ('strategy_name', models.CharField(help_text='回测使用的策略名称，如 DDPS-Z', max_length=100, verbose_name='策略名称')),
                ('symbol', models.CharField(help_text='交易对符号，如 BTCUSDT', max_length=20, verbose_name='交易对')),
                ('interval', models.CharField(help_text='K线周期，如 4h, 1d', max_length=10, verbose_name='K线周期')),
                ('market_type', models.CharField(choices=[('futures', '合约'), ('spot', '现货')], default='futures', help_text='市场类型：futures（合约）或 spot（现货）', max_length=10, verbose_name='市场类型')),
                ('start_date', models.DateField(help_text='回测开始日期', verbose_name='开始日期')),
                ('end_date', models.DateField(help_text='回测结束日期', verbose_name='结束日期')),
                # 回测参数
                ('initial_cash', models.DecimalField(decimal_places=2, help_text='回测初始资金（USDT）', max_digits=20, verbose_name='初始资金')),
                ('position_size', models.DecimalField(decimal_places=2, help_text='单笔买入金额（USDT）', max_digits=20, verbose_name='单笔金额')),
                ('commission_rate', models.DecimalField(decimal_places=6, help_text='交易手续费率，如 0.001 表示千一', max_digits=10, verbose_name='手续费率')),
                ('risk_free_rate', models.DecimalField(decimal_places=4, help_text='年化无风险收益率（百分比），如 3.00 表示 3%', max_digits=10, verbose_name='无风险收益率')),
                # 结果数据
                ('equity_curve', models.JSONField(default=list, help_text='权益曲线数据（JSON数组），每个元素包含 timestamp, cash, position_value, equity, equity_rate', verbose_name='权益曲线')),
                ('metrics', models.JSONField(default=dict, help_text='量化指标数据（JSON对象），包含17个P0指标', verbose_name='量化指标')),
                # 元数据
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='记录创建时间', verbose_name='创建时间')),
            ],
            options={
                'verbose_name': '回测结果',
                'verbose_name_plural': '回测结果',
                'db_table': 'strategy_adapter_backtest_result',
                'ordering': ['-created_at'],
            },
        ),
        # 索引
        migrations.AddIndex(
            model_name='backtestresult',
            index=models.Index(fields=['strategy_name'], name='strategy_ad_strateg_8e5fb5_idx'),
        ),
        migrations.AddIndex(
            model_name='backtestresult',
            index=models.Index(fields=['symbol'], name='strategy_ad_symbol_4b6ea3_idx'),
        ),
        migrations.AddIndex(
            model_name='backtestresult',
            index=models.Index(fields=['market_type'], name='strategy_ad_market__f3e8e5_idx'),
        ),
        migrations.AddIndex(
            model_name='backtestresult',
            index=models.Index(fields=['created_at'], name='strategy_ad_created_d7e4a9_idx'),
        ),
        # BacktestOrder 表
        migrations.CreateModel(
            name='BacktestOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                # 订单信息
                ('order_id', models.CharField(help_text='策略内部订单标识', max_length=100, verbose_name='订单ID')),
                ('status', models.CharField(choices=[('filled', '持仓中'), ('closed', '已平仓')], help_text='订单状态：filled（持仓中）或 closed（已平仓）', max_length=20, verbose_name='订单状态')),
                ('buy_price', models.DecimalField(decimal_places=8, help_text='买入成交价格', max_digits=20, verbose_name='买入价格')),
                ('buy_timestamp', models.BigIntegerField(help_text='买入时间戳（毫秒）', verbose_name='买入时间戳')),
                ('sell_price', models.DecimalField(blank=True, decimal_places=8, help_text='卖出成交价格（持仓中为空）', max_digits=20, null=True, verbose_name='卖出价格')),
                ('sell_timestamp', models.BigIntegerField(blank=True, help_text='卖出时间戳（毫秒，持仓中为空）', null=True, verbose_name='卖出时间戳')),
                # 持仓信息
                ('quantity', models.DecimalField(decimal_places=8, help_text='持仓数量（币数）', max_digits=20, verbose_name='持仓数量')),
                ('position_value', models.DecimalField(decimal_places=2, help_text='持仓市值（USDT）', max_digits=20, verbose_name='持仓市值')),
                ('commission', models.DecimalField(decimal_places=8, help_text='总手续费（开仓+平仓）', max_digits=20, verbose_name='手续费')),
                # 收益信息
                ('profit_loss', models.DecimalField(blank=True, decimal_places=2, help_text='盈亏金额（USDT，持仓中为空）', max_digits=20, null=True, verbose_name='盈亏金额')),
                ('profit_loss_rate', models.DecimalField(blank=True, decimal_places=2, help_text='盈亏率（%，持仓中为空）', max_digits=10, null=True, verbose_name='盈亏率')),
                ('holding_periods', models.IntegerField(blank=True, help_text='持仓K线数（持仓中为空）', null=True, verbose_name='持仓K线数')),
                # 外键关联
                ('backtest_result', models.ForeignKey(help_text='关联的回测结果', on_delete=django.db.models.deletion.CASCADE, related_name='orders', to='strategy_adapter.backtestresult', verbose_name='回测结果')),
            ],
            options={
                'verbose_name': '回测订单',
                'verbose_name_plural': '回测订单',
                'db_table': 'strategy_adapter_backtest_order',
                'ordering': ['buy_timestamp'],
            },
        ),
        # 索引
        migrations.AddIndex(
            model_name='backtestorder',
            index=models.Index(fields=['order_id'], name='strategy_ad_order_i_1a2c3d_idx'),
        ),
        migrations.AddIndex(
            model_name='backtestorder',
            index=models.Index(fields=['status'], name='strategy_ad_status_4e5f6g_idx'),
        ),
        migrations.AddIndex(
            model_name='backtestorder',
            index=models.Index(fields=['buy_timestamp'], name='strategy_ad_buy_tim_7h8i9j_idx'),
        ),
    ]
